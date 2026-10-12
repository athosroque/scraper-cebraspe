"""Extração de taxonomia (matéria → tópicos → subtópicos) de um chunk de
edital via LLM (Etapa 4). A chamada HTTP ao OpenRouter, os status de falha
tipados (ADR-022) e a telemetria Langfuse (ADR-023) moram no núcleo genérico
`src/llm_openrouter.py` (ADR-029); aqui ficam o prompt e os reparos
semânticos locais pós-LLM (ADR-021, ADR-025).
"""

import os
import re
import time
from functools import lru_cache

import requests  # noqa: F401 — ponto de mock dos testes (`te.requests.post`)
from dotenv import load_dotenv
from langfuse import Langfuse

from src import llm_openrouter
from src.comparacao_texto import (
    PADRAO_SUBITEM,
    contido,
    divergencia_leve,
    item_coberto,
    normalizar,
)
from src.edital_parser import (
    extrair_itens_numerados,
    extrair_subitens_numerados,
    remover_assinatura_final,
)
from src.llm_openrouter import (
    STATUS_FALHA_CONEXAO,  # noqa: F401 — reexportados: contrato público do módulo
    STATUS_FALHA_CONTEUDO_VAZIO,  # noqa: F401
    STATUS_FALHA_HTTP,  # noqa: F401
    STATUS_FALHA_PARSE_JSON,  # noqa: F401
    STATUS_FALHA_RATE_LIMIT,  # noqa: F401
    STATUS_FALHA_REDE,  # noqa: F401
    STATUS_FALHA_TIMEOUT,  # noqa: F401
    STATUS_FALHA_VALIDACAO_SCHEMA,  # noqa: F401
    ResultadoPosValidacao,
)
from src.llm_openrouter import (
    strip_markdown_fence as _strip_markdown_fence,  # noqa: F401
)
from src.logger import logger
from src.models_scraper import TaxonomiaEdital, Topico

load_dotenv()

OPENROUTER_BASE_URL = llm_openrouter.OPENROUTER_BASE_URL
OPENROUTER_API_KEY = llm_openrouter.chave_openrouter(
    llm_openrouter.ETAPA_TAXONOMIA_EDITAL
)
NOME_TRACE = llm_openrouter.ETAPA_TAXONOMIA_EDITAL[1]
LLM_MODEL = llm_openrouter.LLM_MODEL

# Langfuse via SDK oficial (OTel). A API REST v3 de ingestão deixa de aceitar
# trace/generation em 2026-11-16 (ver ADR-023).
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST") or os.getenv(
    "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# glm-5.3-flash é um modelo de raciocínio: parte do orçamento de tokens vai
# para reasoning antes do content final. Orçamento amplo evita "finish_reason=length"
# em matérias com dezenas de tópicos (ex: Contabilidade com 41 tópicos).
MAX_TOKENS = 12000
REQUEST_TIMEOUT = 120
# Limite de reasoning: fonte única no núcleo (`llm_openrouter.REASONING_PADRAO`).
REASONING_PADRAO = llm_openrouter.REASONING_PADRAO

# Retry com backoff para resiliência contra instabilidades transitórias
TENTATIVAS_PADRAO = 2
BACKOFF_SEGUNDOS = (5, 15)

# Status específico (não o "falha" genérico de rede/timeout/parse) para o
# caso em que o reparo local não conseguiu mapear algum numeral de
# `topico.nome` — sinaliza que o problema não é uma instabilidade técnica
# comum (repetir a chamada pode não resolver sozinho, já que depende de o
# texto-fonte ter a numeração que o LLM usou), então nem o status persistido
# nem a seleção padrão de reprocessamento devem tratar como "falha" igual às
# demais (ver ADR-021). Os status técnicos (ADR-022) vêm do núcleo
# `llm_openrouter` e são reexportados acima.
STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO = "falha_nome_numerico_nao_mapeado"

# Teto de tamanho do texto de um item da fonte para ser reinjetado como
# tópico sem passar pelo LLM (ver `reinjetar_itens_ausentes`). Item longo
# quase sempre tem estrutura interna que só o LLM saberia quebrar — nesses
# casos o reparo não age e o validador mantém o `topico_ausente`.
TAMANHO_MAXIMO_ITEM_REINJETAVEL = 150

PROMPT_SISTEMA = """Você é um extrator de taxonomia de editais de concurso público brasileiro.
Dado um trecho do edital (conteúdo programático de uma matéria), devolva APENAS um JSON válido
no formato:
{"materia": "<nome da matéria>", "topicos": [{"nome": "<tópico>", "subtopicos": ["<subtópico>", ...]}, ...]}
Regras:
- Use os tópicos numerados do próprio edital como "nome" de cada tópico,
  mas "nome" é sempre o TEXTO do tópico (ex.: "Direitos e garantias
  fundamentais") — nunca apenas o número do item ("1", "2", "3", ...)
  isolado sem o texto que o acompanha.
- Quebre em "subtopicos" as alíneas/itens dentro de cada tópico, se existirem.
- Todo item numerado de primeiro nível vira exatamente um tópico, inclusive
  itens curtos que são só uma norma ou sigla (ex.: "IN Ibama 05/2021",
  "Lei nº 8.112/1990") — nunca pule um item.
- Não acrescente qualificadores ao "nome" que não estejam no texto; se o
  edital repete o mesmo item, repita o tópico com o mesmo nome.
- Não invente conteúdo que não está no texto.
- Não inclua texto fora do JSON (sem markdown, sem explicação)."""


@lru_cache(maxsize=1)
def _langfuse_client() -> Langfuse | None:
    """Cliente único do SDK por processo, ou `None` sem chaves (telemetria opcional).

    O SDK exporta em thread de fundo e registra `atexit` para o flush final,
    então scripts batch curtos não precisam chamar `flush()` explicitamente.
    """
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return None
    return Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )


def _abrir_generation(chunk_text: str, max_tokens: int, timeout: int):
    """Abre a generation antes da chamada ao OpenRouter, pra latência ser a real."""
    return llm_openrouter.abrir_generation(
        _langfuse_client(),
        "extrair_taxonomia_chunk",
        chunk_text,
        max_tokens,
        timeout,
        LLM_MODEL,
        nome_trace=NOME_TRACE,
    )


def _registrar_langfuse(
    gen,
    *,
    resposta: str | None,
    usage: dict | None,
    sucesso: bool,
    erro: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Fecha a generation com o desfecho e grava `metadata` (ex: `tipo_erro`) no trace."""
    llm_openrouter.registrar_generation(
        gen,
        resposta=resposta,
        usage=usage,
        sucesso=sucesso,
        erro=erro,
        metadata=metadata,
    )


def _reparar_nomes_numericos(taxonomia: TaxonomiaEdital, chunk_text: str) -> list[str]:
    """Substitui, in-place, todo `topico.nome` puramente numérico pelo texto
    do item correspondente no texto-fonte (`chunk_text`) — determinístico,
    sem nova chamada ao LLM (ver ADR-021: uma chamada corretiva "às cegas",
    repetindo o mesmo prompt sem contexto do erro, não tem garantia de
    corrigir e não deixa rastro distinto de um retry por falha de rede).

    Usa o mesmo mapeamento numero->texto que `validar_taxonomia.py` usa pra
    comparação de-para (`extrair_itens_numerados`), pra reparo e validação
    nunca divergirem sobre o que é "o item de origem".

    Retorna a lista de numerais que não acharam correspondência no
    texto-fonte (chunk deve ser tratado como falha se a lista não for
    vazia); lista vazia == reparo completo (ou nada a reparar).
    """
    topicos_numericos = [t for t in taxonomia.topicos if t.nome.strip().isdigit()]
    if not topicos_numericos:
        return []

    mapa_numero_para_texto = dict(extrair_itens_numerados(chunk_text))
    nao_mapeados = []
    for topico in topicos_numericos:
        numero = topico.nome.strip()
        texto_item = mapa_numero_para_texto.get(numero)
        if texto_item is None:
            nao_mapeados.append(numero)
            continue
        logger.warning(
            f"[REPARO_NOME_NUMERICO] tópico '{numero}' reparado localmente "
            f"a partir do texto-fonte: '{texto_item[:60]}'"
        )
        topico.nome = texto_item
    return nao_mapeados


def reinjetar_itens_ausentes(taxonomia: TaxonomiaEdital, chunk_text: str) -> list[str]:
    """Insere, in-place, como tópico novo todo item de primeiro nível do
    texto-fonte que o LLM omitiu por completo — determinístico, sem nova
    chamada ao LLM (mesma lógica do ADR-021, ver ADR-025). Achado real:
    IBAMA_25 chunk 32, o LLM pulou `1 IN Ibama 05/2021.` (único item só com
    sigla e número de norma) e começou a taxonomia no item 2.

    "Omitido" usa exatamente os mesmos critérios de `validar_taxonomia.py`
    (`contido` contra tópicos e subtópicos, e `divergencia_leve` pra não
    reinjetar em duplicata um item que o LLM só parafraseou/corrigiu), então
    reparo e validação nunca divergem sobre o que é "item coberto".

    Só reinjeta item simples: sem subitens (`N.1 ...`) e com até
    `TAMANHO_MAXIMO_ITEM_REINJETAVEL` chars. O tópico entra na posição
    relativa da fonte (antes do tópico que cobre o próximo item). Retorna os
    números dos itens reinjetados; item omitido mas não reinjetável não vira
    falha — segue como `topico_ausente` no validador.
    """
    itens = extrair_itens_numerados(remover_assinatura_final(chunk_text))
    if not itens:
        return []
    extraidos: list[tuple[int, str]] = []
    for t_idx, topico in enumerate(taxonomia.topicos):
        extraidos.append((t_idx, topico.nome))
        extraidos.extend((t_idx, s) for s in topico.subtopicos if s)

    cobertura: list[int | None] = []
    for _, item_texto in itens:
        item_norm = normalizar(item_texto)
        cobertura.append(
            next(
                (
                    t_idx
                    for t_idx, texto in extraidos
                    if contido(normalizar(texto), item_norm)
                ),
                None,
            )
        )

    reinjetados: list[str] = []
    # De trás pra frente: inserir num índice maior não desloca os menores,
    # e dois itens omitidos seguidos saem na ordem certa.
    for pos in range(len(itens) - 1, -1, -1):
        if cobertura[pos] is not None:
            continue
        numero, item_texto = itens[pos]
        if PADRAO_SUBITEM.search(item_texto):
            continue
        nome = " ".join(item_texto.split()).rstrip(" .;")
        if not nome or len(nome) > TAMANHO_MAXIMO_ITEM_REINJETAVEL:
            continue
        # Comparação restrita a ESTE item (não ao texto-fonte inteiro): senão
        # um tópico parafraseado de outro item do chunk bloquearia o reparo.
        item_norm = normalizar(item_texto)
        if any(
            divergencia_leve(texto, [item_texto], item_norm) for _, texto in extraidos
        ):
            continue
        destino = next(
            (c for c in cobertura[pos + 1 :] if c is not None), len(taxonomia.topicos)
        )
        taxonomia.topicos.insert(destino, Topico(nome=nome))
        reinjetados.append(numero)
        logger.warning(
            f"[REPARO_ITEM_AUSENTE] item '{numero}' omitido pelo LLM reinjetado localmente "
            f"a partir do texto-fonte: '{nome[:60]}'"
        )
    return sorted(reinjetados, key=int)


# Nome de subtópico reinjetado acima disso (cadeia de títulos longa demais)
# indica subitem mal segmentado: fica como `subitem_ausente` para revisão.
TAMANHO_MAXIMO_SUBTOPICO_REINJETAVEL = 300


def _limpar_nome_subitem(texto: str) -> str:
    return " ".join(texto.split()).rstrip(" .;")


def _nome_em_cadeia(numero: str, texto_por_numero: dict[str, str]) -> str | None:
    """Textos próprios do ancestral de 2º nível até `numero`, unidos por " - ";
    None se algum elo não tem texto próprio."""
    partes = numero.split(".")
    cadeia = [
        texto_por_numero.get(".".join(partes[:n])) for n in range(2, len(partes) + 1)
    ]
    if not all(cadeia):
        return None
    return " - ".join(_limpar_nome_subitem(c) for c in cadeia)


def _texto_proprio_do_item(
    texto_item: str, subitens_do_item: list[tuple[str, str]]
) -> str:
    """Trecho do item de 1º nível antes do seu primeiro subitem (o item sem
    os filhos). Sem subitem localizável, devolve o texto inteiro."""
    for numero, _ in subitens_do_item:
        achado = re.search(r"(?<![\d.])" + re.escape(numero) + r"(?!\d)", texto_item)
        if achado:
            return texto_item[: achado.start()]
    return texto_item


def _casa_por_fronteira(a: str, b: str) -> bool:
    """Textos normalizados: iguais ou um contido no outro com fronteira de palavra."""
    if not a or not b:
        return False
    return a == b or bool(
        re.search(r"\b" + re.escape(a) + r"\b", b)
        or re.search(r"\b" + re.escape(b) + r"\b", a)
    )


def _topico_destino_do_item(
    taxonomia: TaxonomiaEdital,
    texto_item_primeiro_nivel: str,
    subitens_do_item: list[tuple[str, str]],
    numero_item: str = "",
) -> Topico | None:
    """Tópico do item de 1º nível. Compara o nome com o TEXTO PRÓPRIO do item
    (antes do 1º subitem), não com o item inteiro: o subitem "Mensuração de
    ativos e passivos..." do item 21 não pode levar ao tópico do item 5.
    Mais de um casamento: prefere o tópico cujos subtópicos já cobrem subitens
    do mesmo item e, depois, o de maior proporção do texto próprio. Sem
    casamento, cai na regra ampla (nome `contido` no item inteiro)."""
    proprio_norm = normalizar(
        _texto_proprio_do_item(texto_item_primeiro_nivel, subitens_do_item)
    )
    candidatos = []
    for topico in taxonomia.topicos:
        nome_norm = normalizar(topico.nome)
        if not _casa_por_fronteira(nome_norm, proprio_norm):
            continue
        tem_subs = any(
            item_coberto(p, [sub])
            for sub in topico.subtopicos
            if sub
            for _, p in subitens_do_item
        )
        proporcao = min(len(nome_norm), len(proprio_norm)) / max(
            len(nome_norm), len(proprio_norm)
        )
        candidatos.append((tem_subs, proporcao, topico))
    if candidatos:
        return max(candidatos, key=lambda c: (c[0], c[1]))[2]

    logger.warning(
        f"[REPARO_SUBITEM_AUSENTE] destino por regra ampla para o item '{numero_item}'."
    )
    item_norm = normalizar(texto_item_primeiro_nivel)
    for topico in taxonomia.topicos:
        if contido(normalizar(topico.nome), item_norm):
            return topico
    for topico in taxonomia.topicos:
        if any(contido(normalizar(s), item_norm) for s in topico.subtopicos if s):
            return topico
    return None


def reinjetar_subitens_ausentes(
    taxonomia: TaxonomiaEdital, chunk_text: str
) -> list[str]:
    """Insere, in-place, como subtópico todo subitem (profundidade >= 2) do
    texto-fonte que o LLM descartou — determinístico, sem LLM (ADR-025,
    atualização C1a). Achado real: SEFA_PR_25 ECONOMIA, taxonomia só com o
    1º e o 2º nível e 128 `subitem_ausente`.

    "Ausente" é `not item_coberto(texto_proprio, todos os tópicos e subtópicos
    do chunk)`, a mesma regra do validador. Destino: o tópico que cobre o item
    de 1º nível do subitem; sem ele, não reinjeta. Nome: cadeia dos textos
    próprios do ancestral de 2º nível até o subitem, unida por " - " (só o
    texto próprio na profundidade 2); acima de
    `TAMANHO_MAXIMO_SUBTOPICO_REINJETAVEL` não reinjeta. Posição: logo depois
    do subtópico que cobre o subitem de ordem mais próxima (anterior ou o
    próprio ancestral/irmão) do mesmo item de 1º nível; senão, no fim.
    Retorna os números reinjetados, na ordem da fonte.
    """
    texto = remover_assinatura_final(chunk_text)
    subitens = extrair_subitens_numerados(texto)
    if not subitens:
        return []
    texto_por_numero = dict(subitens)
    itens_primeiro_nivel = dict(extrair_itens_numerados(texto))

    reinjetados: list[str] = []
    for ordem, (numero, proprio) in enumerate(subitens):
        extraidos = []
        for t in taxonomia.topicos:
            extraidos.append(t.nome)
            extraidos.extend(s for s in t.subtopicos if s)
        if item_coberto(proprio, extraidos):
            continue

        partes = numero.split(".")
        texto_item = itens_primeiro_nivel.get(partes[0])
        destino = (
            _topico_destino_do_item(
                taxonomia,
                texto_item,
                [(n, p) for n, p in subitens if n.split(".")[0] == partes[0]],
                partes[0],
            )
            if texto_item
            else None
        )
        if destino is None:
            logger.warning(
                f"[REPARO_SUBITEM_AUSENTE] subitem '{numero}' sem tópico destino; "
                "segue como subitem_ausente."
            )
            continue

        nome = _nome_em_cadeia(numero, texto_por_numero)
        if not nome:
            logger.warning(
                f"[REPARO_SUBITEM_AUSENTE] subitem '{numero}' com ancestral sem "
                "texto próprio; não reinjetado."
            )
            continue
        if len(nome) > TAMANHO_MAXIMO_SUBTOPICO_REINJETAVEL:
            logger.warning(
                f"[REPARO_SUBITEM_AUSENTE] subitem '{numero}' com nome de "
                f"{len(nome)} chars (> {TAMANHO_MAXIMO_SUBTOPICO_REINJETAVEL}); "
                "não reinjetado."
            )
            continue

        # Posição: ancora pelo nome em cadeia (não pela cobertura textual, que
        # confunde "Fatores de produção" de 1.1.2 com o de 1.3.1.1). Percorre os
        # subitens anteriores do mesmo item de 1º nível, do mais próximo ao mais
        # distante, e insere depois do último subtópico igual à cadeia da âncora
        # ou descendente dela (cadeia + " - ").
        posicao = len(destino.subtopicos)
        for n_anc, _ in reversed(
            [(n, p) for n, p in subitens[:ordem] if n.split(".")[0] == partes[0]]
        ):
            chave = _nome_em_cadeia(n_anc, texto_por_numero)
            if not chave:
                continue
            chave = chave.casefold()
            achados = [
                idx
                for idx, sub in enumerate(destino.subtopicos)
                if _limpar_nome_subitem(sub).casefold() == chave
                or _limpar_nome_subitem(sub).casefold().startswith(chave + " - ")
            ]
            if achados:
                posicao = achados[-1] + 1
                break
        destino.subtopicos.insert(posicao, nome)
        reinjetados.append(numero)
        logger.warning(
            f"[REPARO_SUBITEM_AUSENTE] subitem '{numero}' omitido pelo LLM "
            f"reinjetado em '{destino.nome[:40]}': '{nome[:80]}'"
        )
    return reinjetados


def _pos_validacao_taxonomia(chunk_text: str):
    """Gancho semântico do núcleo `chamar_llm_json`: reparo de nome numérico
    (ADR-021) e reinjeção de item omitido (ADR-025), sem nova chamada ao LLM.
    O desfecho dos dois vai para o metadata da mesma generation."""

    def pos_validacao(
        taxonomia: TaxonomiaEdital, _content: str
    ) -> ResultadoPosValidacao:
        metadata: dict = {}
        # Estruturalmente válido não é o mesmo que semanticamente correto: o
        # LLM às vezes preenche "nome" com o numeral do item da fonte ("1",
        # "2", ...) em vez do texto do tópico. Em vez de repetir a chamada
        # torcendo por sorte, reparamos localmente a partir do texto-fonte.
        numerais_antes_do_reparo = [
            t.nome.strip() for t in taxonomia.topicos if t.nome.strip().isdigit()
        ]
        numerais_nao_mapeados = _reparar_nomes_numericos(taxonomia, chunk_text)
        if numerais_antes_do_reparo:
            # Os dois desfechos (reparado ou não) ficam filtráveis no Langfuse
            # pelo mesmo campo estruturado (ADR-021).
            metadata["reparo_nome_numerico"] = {
                "numerais_detectados": numerais_antes_do_reparo,
                "numerais_nao_mapeados": numerais_nao_mapeados,
                "status": "falhou" if numerais_nao_mapeados else "reparado",
            }
        if numerais_nao_mapeados:
            return ResultadoPosValidacao(
                motivo=STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO,
                erro=(
                    f"[REPARO_NOME_NUMERICO_FALHOU] Nome de tópico numérico sem "
                    f"correspondência no texto-fonte após reparo local "
                    f"(numerais: {numerais_nao_mapeados}) — chunk fica pendente "
                    "de revisão humana."
                ),
                metadata=metadata,
            )
        itens_reinjetados = reinjetar_itens_ausentes(taxonomia, chunk_text)
        if itens_reinjetados:
            metadata["reparo_item_ausente"] = {
                "itens": itens_reinjetados,
                "status": "reparado",
            }
        subitens_reinjetados = reinjetar_subitens_ausentes(taxonomia, chunk_text)
        if subitens_reinjetados:
            metadata["reparo_subitem_ausente"] = {
                "subitens": subitens_reinjetados,
                "status": "reparado",
            }
        return ResultadoPosValidacao(objeto=taxonomia, metadata=metadata)

    return pos_validacao


def _chamar_llm_uma_vez(
    chunk_text: str,
    max_tokens: int,
    timeout: int,
    reasoning: dict | None,
    metadata: dict | None = None,
) -> tuple[TaxonomiaEdital | None, str | None]:
    """Uma única tentativa de extração via núcleo `llm_openrouter.chamar_llm_json`.

    Retorna `(taxonomia, motivo_falha)`: sucesso é `(TaxonomiaEdital, None)`;
    toda falha devolve um `motivo` específico (nunca `None`) que também vira
    o `tipo_erro` no metadata do Langfuse — status técnicos do ADR-022 ou
    `STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO` (falha semântica, ADR-021).
    """
    resultado = llm_openrouter.chamar_llm_json(
        PROMPT_SISTEMA,
        chunk_text,
        TaxonomiaEdital,
        max_tokens=max_tokens,
        timeout=timeout,
        reasoning=reasoning,
        metadata=metadata,
        pos_validacao=_pos_validacao_taxonomia(chunk_text),
        # Ganchos resolvidos na hora da chamada: os testes fazem patch de
        # `te._registrar_langfuse`/`te._abrir_generation`.
        abrir=lambda: _abrir_generation(chunk_text, max_tokens, timeout),
        registrar=lambda gen, **kw: _registrar_langfuse(gen, **kw),
        api_key=OPENROUTER_API_KEY,
        modelo=LLM_MODEL,
    )
    return resultado.objeto, resultado.motivo


def extrair_taxonomia_chunk(
    chunk_text: str,
    *,
    max_tokens: int = MAX_TOKENS,
    timeout: int = REQUEST_TIMEOUT,
    reasoning: dict | None = REASONING_PADRAO,
    tentativas: int = TENTATIVAS_PADRAO,
    backoff_segundos: tuple[int, ...] = BACKOFF_SEGUNDOS,
    metadata: dict | None = None,
) -> tuple[TaxonomiaEdital | None, str | None]:
    """Envia um chunk (conteúdo programático de 1 matéria) diretamente ao OpenRouter
    e valida a resposta contra `TaxonomiaEdital`, tentando novamente em caso de falha.
    Registra métricas no Langfuse via SDK oficial (OTel).

    Retorna `(taxonomia, motivo_falha)` — ver `_chamar_llm_uma_vez` para o
    significado de `motivo_falha` (sempre um status específico por tipo de
    exceção/etapa, nunca genérico — ADR-022). Em caso de sucesso em qualquer
    tentativa, `motivo_falha` é sempre `None` (o motivo de tentativas
    anteriores que falharam não importa mais). Se todas as tentativas
    falharem, o motivo devolvido é o da **última** tentativa.
    """
    motivo_falha = None
    for tentativa in range(1, tentativas + 1):
        meta_tentativa = dict(metadata or {})
        meta_tentativa["tentativa"] = tentativa
        resultado, motivo_falha = _chamar_llm_uma_vez(
            chunk_text, max_tokens, timeout, reasoning, metadata=meta_tentativa
        )
        if resultado is not None:
            return resultado, None
        if tentativa < tentativas:
            pausa = backoff_segundos[min(tentativa - 1, len(backoff_segundos) - 1)]
            logger.warning(
                f"Tentativa {tentativa}/{tentativas} falhou — nova tentativa em {pausa}s."
            )
            time.sleep(pausa)
    return None, motivo_falha
