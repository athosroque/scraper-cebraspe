import json
import os
import time
from functools import lru_cache

import requests
from dotenv import load_dotenv
from langfuse import Langfuse
from pydantic import ValidationError

from src.comparacao_texto import PADRAO_SUBITEM, contido, divergencia_leve, normalizar
from src.edital_parser import extrair_itens_numerados, remover_assinatura_final
from src.logger import logger
from src.models_scraper import TaxonomiaEdital, Topico

load_dotenv()

# OpenRouter (acesso direto, sem proxy intermediário e sem SDK)
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")

# Langfuse via SDK oficial (OTel). A API REST v3 de ingestão deixa de aceitar
# trace/generation em 2026-11-16 (ver ADR-023).
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

# glm-5.3-flash é um modelo de raciocínio: parte do orçamento de tokens vai
# para reasoning antes do content final. Orçamento amplo evita "finish_reason=length"
# em matérias com dezenas de tópicos (ex: Contabilidade com 41 tópicos).
MAX_TOKENS = 12000
REQUEST_TIMEOUT = 120
REASONING_PADRAO = {"reasoning": {"max_tokens": 3000}}

# Retry com backoff para resiliência contra instabilidades transitórias
TENTATIVAS_PADRAO = 2
BACKOFF_SEGUNDOS = (5, 15)

# Status específico (não o "falha" genérico de rede/timeout/parse) para o
# caso em que o reparo local não conseguiu mapear algum numeral de
# `topico.nome` — sinaliza que o problema não é uma instabilidade técnica
# comum (repetir a chamada pode não resolver sozinho, já que depende de o
# texto-fonte ter a numeração que o LLM usou), então nem o status persistido
# nem a seleção padrão de reprocessamento devem tratar como "falha" igual às
# demais (ver ADR-021).
STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO = "falha_nome_numerico_nao_mapeado"

# Status técnicos distintos por tipo de exceção/etapa da chamada ao
# OpenRouter (ver ADR-022) — cada um rastreável separadamente no status
# persistido do chunk e no metadata do Langfuse (`tipo_erro`), em vez de
# colapsar toda falha técnica no mesmo "falha" genérico. A distinção importa
# pra decidir reprocessamento: timeout/conexão/rate-limit são tipicamente
# transitórios (retry tende a ajudar); conteúdo vazio/parse/schema tendem a
# se repetir com os mesmos parâmetros (retry sozinho não resolve).
STATUS_FALHA_TIMEOUT = "falha_timeout"
STATUS_FALHA_CONEXAO = "falha_conexao"
STATUS_FALHA_RATE_LIMIT = "falha_rate_limit"
STATUS_FALHA_HTTP = "falha_http"
STATUS_FALHA_REDE = "falha_rede"
STATUS_FALHA_CONTEUDO_VAZIO = "falha_conteudo_vazio"
STATUS_FALHA_PARSE_JSON = "falha_parse_json"
STATUS_FALHA_VALIDACAO_SCHEMA = "falha_validacao_schema"

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


def _strip_markdown_fence(text: str) -> str:
    """Remove um possível bloco ```json ... ``` ao redor da resposta do LLM."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    text = text.split("\n", 1)[1] if "\n" in text else text
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text


@lru_cache(maxsize=1)
def _langfuse_client() -> Langfuse | None:
    """Cliente único do SDK por processo, ou `None` sem chaves (telemetria opcional).

    O SDK exporta em thread de fundo e registra `atexit` para o flush final,
    então scripts batch curtos não precisam chamar `flush()` explicitamente.
    """
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return None
    return Langfuse(public_key=LANGFUSE_PUBLIC_KEY, secret_key=LANGFUSE_SECRET_KEY, host=LANGFUSE_HOST)


def _abrir_generation(chunk_text: str, max_tokens: int, timeout: int):
    """Abre a generation antes da chamada ao OpenRouter, pra latência ser a real."""
    client = _langfuse_client()
    if client is None:
        return None
    try:
        return client.start_observation(
            as_type="generation",
            name="extrair_taxonomia_chunk",
            model=LLM_MODEL,
            input=chunk_text,
            model_parameters={"max_tokens": max_tokens, "timeout": timeout},
        )
    except Exception as e:  # noqa: BLE001 — telemetria nunca derruba a extração
        logger.warning(f"Falha ao abrir generation no Langfuse: {e}")
        return None


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
    if gen is None:
        return
    try:
        gen.update(
            output=resposta,
            usage_details={
                "input": (usage or {}).get("prompt_tokens", 0),
                "output": (usage or {}).get("completion_tokens", 0),
                "total": (usage or {}).get("total_tokens", 0),
            },
            level="DEFAULT" if sucesso else "ERROR",
            status_message=erro,
        )
        gen.update_trace(name="taxonomia_extractor", metadata=metadata or {})
        gen.end()
    except Exception as e:  # noqa: BLE001 — telemetria nunca derruba a extração
        logger.warning(f"Falha ao registrar generation no Langfuse: {e}")


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
            next((t_idx for t_idx, texto in extraidos if contido(normalizar(texto), item_norm)), None)
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
        if any(divergencia_leve(texto, [item_texto], item_norm) for _, texto in extraidos):
            continue
        destino = next((c for c in cobertura[pos + 1 :] if c is not None), len(taxonomia.topicos))
        taxonomia.topicos.insert(destino, Topico(nome=nome))
        reinjetados.append(numero)
        logger.warning(
            f"[REPARO_ITEM_AUSENTE] item '{numero}' omitido pelo LLM reinjetado localmente "
            f"a partir do texto-fonte: '{nome[:60]}'"
        )
    return sorted(reinjetados, key=int)


def _falha_chamada(
    tag: str,
    mensagem: str,
    motivo: str,
    gen,
    metadata: dict | None,
) -> tuple[None, str]:
    """Loga e registra no Langfuse uma falha da chamada de rede ao OpenRouter,
    com tag própria e status específico por tipo de exceção (ver ADR-022) —
    evita que timeout, conexão recusada, HTTP 429/5xx e qualquer outra
    `RequestException` não classificada colapsem no mesmo "falha" genérico.
    """
    logger.error(f"{tag} {mensagem}")
    _registrar_langfuse(
        gen,
        resposta=None,
        usage=None,
        sucesso=False,
        erro=mensagem,
        metadata={**(metadata or {}), "tipo_erro": motivo},
    )
    return None, motivo


def _chamar_llm_uma_vez(
    chunk_text: str,
    max_tokens: int,
    timeout: int,
    reasoning: dict | None,
    metadata: dict | None = None,
) -> tuple[TaxonomiaEdital | None, str | None]:
    """Uma única tentativa de extração via OpenRouter REST — sem SDK e sem proxy.

    Retorna `(taxonomia, motivo_falha)`: sucesso é `(TaxonomiaEdital, None)`;
    toda falha devolve um `motivo` específico (nunca `None`) que também vira
    o `tipo_erro` no metadata do Langfuse — `STATUS_FALHA_TIMEOUT`,
    `STATUS_FALHA_CONEXAO`, `STATUS_FALHA_RATE_LIMIT`, `STATUS_FALHA_HTTP`,
    `STATUS_FALHA_REDE` (rede/HTTP, ver ADR-022), `STATUS_FALHA_CONTEUDO_VAZIO`,
    `STATUS_FALHA_PARSE_JSON`, `STATUS_FALHA_VALIDACAO_SCHEMA` (parse da
    resposta) ou `STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO` (falha semântica
    identificada, ver ADR-021).
    """
    payload_requisicao = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": chunk_text},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    if reasoning:
        payload_requisicao.update(reasoning)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/athosroque/scraper_cebraspe",
        "X-Title": "Scraper Cebraspe",
    }

    gen = _abrir_generation(chunk_text, max_tokens, timeout)
    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload_requisicao,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        return _falha_chamada(
            "[FALHA_TIMEOUT]", f"Timeout na chamada ao OpenRouter: {e}", STATUS_FALHA_TIMEOUT, gen, metadata
        )
    except requests.exceptions.ConnectionError as e:
        return _falha_chamada(
            "[FALHA_CONEXAO]", f"Falha de conexão com o OpenRouter: {e}", STATUS_FALHA_CONEXAO, gen, metadata
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        motivo = STATUS_FALHA_RATE_LIMIT if status_code == 429 else STATUS_FALHA_HTTP
        tag = "[FALHA_RATE_LIMIT]" if status_code == 429 else "[FALHA_HTTP]"
        return _falha_chamada(
            tag, f"OpenRouter respondeu HTTP {status_code}: {e}", motivo, gen, metadata
        )
    except requests.RequestException as e:
        return _falha_chamada(
            "[FALHA_REDE]", f"Falha de rede não classificada na chamada ao OpenRouter: {e}", STATUS_FALHA_REDE,
            gen, metadata,
        )

    data = response.json()
    message = data["choices"][0]["message"]
    content = message.get("content")
    usage = data.get("usage")

    if not content:
        finish_reason = data["choices"][0].get("finish_reason")
        err_msg = (
            f"[FALHA_CONTEUDO_VAZIO] Resposta do LLM sem content (finish_reason={finish_reason}) — "
            "possivelmente max_tokens insuficiente para o reasoning do modelo"
        )
        logger.error(err_msg)
        _registrar_langfuse(
            gen,
            resposta=None,
            usage=usage,
            sucesso=False,
            erro=err_msg,
            metadata={**(metadata or {}), "tipo_erro": STATUS_FALHA_CONTEUDO_VAZIO},
        )
        return None, STATUS_FALHA_CONTEUDO_VAZIO

    content_limpo = _strip_markdown_fence(content)
    try:
        payload = json.loads(content_limpo)
        taxonomia = TaxonomiaEdital.model_validate(payload)

        # Estruturalmente válido não é o mesmo que semanticamente correto: o
        # LLM às vezes preenche "nome" com o numeral do item da fonte ("1",
        # "2", ...) em vez do texto do tópico, jogando o texto real para
        # "subtopicos" (achado ao vivo em PF_25_ADM, ver LESSONS.md/ADR-021).
        # Em vez de simplesmente repetir a mesma chamada ao LLM torcendo por
        # sorte (custa tokens de novo, sem garantia, e não deixa rastro
        # próprio no log), reparamos localmente: o texto-fonte já tem o item
        # completo pra cada numeral, então usamos o mesmo mapeamento
        # numero->texto que `validar_taxonomia.py` já usa pra comparação.
        numerais_antes_do_reparo = [t.nome.strip() for t in taxonomia.topicos if t.nome.strip().isdigit()]
        numerais_nao_mapeados = _reparar_nomes_numericos(taxonomia, chunk_text)
        if numerais_antes_do_reparo:
            # Marca no metadata do Langfuse os dois desfechos possíveis
            # (reparado ou não) com o mesmo campo estruturado — sem isso, só
            # o desfecho de sucesso ficava filtrável no dashboard, e o de
            # falha só existia como texto livre em `erro` (rastreabilidade
            # pedida na revisão, ver ADR-021).
            metadata = {
                **(metadata or {}),
                "reparo_nome_numerico": {
                    "numerais_detectados": numerais_antes_do_reparo,
                    "numerais_nao_mapeados": numerais_nao_mapeados,
                    "status": "falhou" if numerais_nao_mapeados else "reparado",
                },
            }
        itens_reinjetados = reinjetar_itens_ausentes(taxonomia, chunk_text) if not numerais_nao_mapeados else []
        if itens_reinjetados:
            metadata = {
                **(metadata or {}),
                "reparo_item_ausente": {"itens": itens_reinjetados, "status": "reparado"},
            }
        if numerais_nao_mapeados:
            err_msg = (
                f"[REPARO_NOME_NUMERICO_FALHOU] Nome de tópico numérico sem "
                f"correspondência no texto-fonte após reparo local "
                f"(numerais: {numerais_nao_mapeados}) — chunk fica pendente "
                "de revisão humana."
            )
            logger.error(err_msg)
            _registrar_langfuse(
                gen,
                resposta=content_limpo,
                usage=usage,
                sucesso=False,
                erro=err_msg,
                metadata={**metadata, "tipo_erro": STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO},
            )
            return None, STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO

        _registrar_langfuse(
            gen,
            resposta=content_limpo,
            usage=usage,
            sucesso=True,
            metadata=metadata,
        )
        return taxonomia, None
    except json.JSONDecodeError as e:
        err_msg = f"[FALHA_PARSE_JSON] Resposta do LLM não é JSON válido: {e}\nConteúdo bruto: {content[:500]}"
        logger.error(err_msg)
        _registrar_langfuse(
            gen,
            resposta=content,
            usage=usage,
            sucesso=False,
            erro=str(e),
            metadata={**(metadata or {}), "tipo_erro": STATUS_FALHA_PARSE_JSON},
        )
        return None, STATUS_FALHA_PARSE_JSON
    except ValidationError as e:
        err_msg = f"[FALHA_VALIDACAO_SCHEMA] Resposta do LLM não bateu com TaxonomiaEdital: {e}\nConteúdo bruto: {content[:500]}"
        logger.error(err_msg)
        _registrar_langfuse(
            gen,
            resposta=content,
            usage=usage,
            sucesso=False,
            erro=str(e),
            metadata={**(metadata or {}), "tipo_erro": STATUS_FALHA_VALIDACAO_SCHEMA},
        )
        return None, STATUS_FALHA_VALIDACAO_SCHEMA


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
        resultado, motivo_falha = _chamar_llm_uma_vez(chunk_text, max_tokens, timeout, reasoning, metadata=meta_tentativa)
        if resultado is not None:
            return resultado, None
        if tentativa < tentativas:
            pausa = backoff_segundos[min(tentativa - 1, len(backoff_segundos) - 1)]
            logger.warning(f"Tentativa {tentativa}/{tentativas} falhou — nova tentativa em {pausa}s.")
            time.sleep(pausa)
    return None, motivo_falha
