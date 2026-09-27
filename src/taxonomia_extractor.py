"""Extração de taxonomia (matéria → tópicos → subtópicos) de um chunk de
edital via LLM (Etapa 4). A chamada HTTP ao OpenRouter, os status de falha
tipados (ADR-022) e a telemetria Langfuse (ADR-023) moram no núcleo genérico
`src/llm_openrouter.py` (ADR-029); aqui ficam o prompt e os reparos
semânticos locais pós-LLM (ADR-021, ADR-025).
"""

import os
import time
from functools import lru_cache

import requests  # noqa: F401 — ponto de mock dos testes (`te.requests.post`)
from dotenv import load_dotenv
from langfuse import Langfuse

from src import llm_openrouter
from src.comparacao_texto import PADRAO_SUBITEM, contido, divergencia_leve, normalizar
from src.edital_parser import extrair_itens_numerados, remover_assinatura_final
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
OPENROUTER_API_KEY = llm_openrouter.OPENROUTER_API_KEY
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
        nome_trace="taxonomia_extractor",
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
