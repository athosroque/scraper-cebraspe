"""Núcleo genérico de chamada ao OpenRouter com resposta JSON validada por
schema Pydantic (Etapa 5B, ADR-029).

Extraído de `taxonomia_extractor._chamar_llm_uma_vez` para ser reaproveitado
pela proposta de sinônimos (`scripts/propor_sinonimos.py`) e, na Etapa 5D,
pela classificação de questões. Mantém as regras já decididas:

- REST direto ao OpenRouter, sem SDK de LLM (ADR-011);
- status de falha tipados por exceção/etapa, nunca um "falha" genérico
  (ADR-022), também gravados em `metadata["tipo_erro"]` no Langfuse;
- Langfuse via SDK oficial, com a generation aberta logo antes da chamada
  HTTP para a latência ser a real (ADR-023);
- `max_tokens` generoso: `glm-5.3-flash` é modelo de raciocínio e gasta parte
  do orçamento em `reasoning_content` antes do `content` (LESSONS.md).

Validação semântica específica de cada uso (reparo de nome numérico no
extrator, lista fechada de IDs na proposta de sinônimos) entra pelo gancho
`pos_validacao`, que roda antes de fechar a generation: o desfecho dela vai
para o mesmo registro no Langfuse.
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv
from langfuse import Langfuse, propagate_attributes
from pydantic import BaseModel, ValidationError

from src.logger import logger

load_dotenv()

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("OPENROUTER_MODEL", "z-ai/glm-5.3-flash")

# Uma chave do OpenRouter por etapa, com o mesmo nome no painel do OpenRouter
# e no trace do Langfuse, para separar custo e uso de cada etapa.
# Etapa -> (variável no .env, nome da chave no OpenRouter = nome do trace).
ETAPA_TAXONOMIA_EDITAL = (
    "OPENROUTER_KEY_TAXONOMIA_EDITAL",
    "cebraspe-4-taxonomia-edital",
)
ETAPA_SINONIMOS = ("OPENROUTER_KEY_SINONIMOS", "cebraspe-5b-sinonimos")
ETAPA_CURADORIA_ARVORE = (
    "OPENROUTER_KEY_CURADORIA_ARVORE",
    "cebraspe-5b2-curadoria-arvore",
)
ETAPA_CLASSIFICACAO_QUESTOES = (
    "OPENROUTER_KEY_CLASSIFICACAO_QUESTOES",
    "cebraspe-5d-classificacao-questoes",
)
ETAPA_TELEGRAM = ("OPENROUTER_KEY_TELEGRAM", "cebraspe-telegram-bot")


def chave_openrouter(etapa: tuple[str, str], *fallbacks: str) -> str:
    """Chave da etapa; sem ela, usa os `fallbacks` e por fim `OPENROUTER_API_KEY`."""
    nome_env, _ = etapa
    chave = os.getenv(nome_env, "")
    if chave:
        return chave
    for alternativa in (*fallbacks, "OPENROUTER_API_KEY"):
        chave = os.getenv(alternativa, "")
        if chave:
            logger.warning(f"[CHAVE_FALLBACK] {nome_env} vazia; usando {alternativa}.")
            return chave
    return ""


LANGFUSE_HOST = os.getenv("LANGFUSE_HOST") or os.getenv(
    "LANGFUSE_BASE_URL", "https://cloud.langfuse.com"
)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

MAX_TOKENS_PADRAO = 12000
TIMEOUT_PADRAO = 120
TEMPERATURA_PADRAO = 0.1
# Limite de reasoning de TODA chamada LLM do projeto (decisão do dono,
# 2026-09-25): fonte única, usada como default de `chamar_llm_json`, pelo
# extrator de taxonomia e pelo bot do Telegram. `glm-5.3-flash` gasta parte do
# `max_tokens` em reasoning antes do `content`; o teto evita que o reasoning
# consuma o orçamento da resposta.
REASONING_PADRAO = {"reasoning": {"max_tokens": 3000}}

# Status técnicos da chamada (ADR-022). Timeout/conexão/rate-limit tendem a
# ser transitórios; conteúdo vazio/parse/schema tendem a se repetir com os
# mesmos parâmetros.
STATUS_FALHA_TIMEOUT = "falha_timeout"
STATUS_FALHA_CONEXAO = "falha_conexao"
STATUS_FALHA_RATE_LIMIT = "falha_rate_limit"
STATUS_FALHA_HTTP = "falha_http"
STATUS_FALHA_REDE = "falha_rede"
STATUS_FALHA_CONTEUDO_VAZIO = "falha_conteudo_vazio"
STATUS_FALHA_PARSE_JSON = "falha_parse_json"
STATUS_FALHA_VALIDACAO_SCHEMA = "falha_validacao_schema"

HEADERS_EXTRAS = {
    "HTTP-Referer": "https://github.com/athosroque/scraper_cebraspe",
    "X-Title": "Scraper Cebraspe",
}


@dataclass
class ResultadoPosValidacao:
    """Desfecho do gancho `pos_validacao`.

    `motivo` None = sucesso (com `objeto`, possivelmente reparado in-place);
    senão é o status tipado da falha semântica, e `erro` vai para o log e
    para o Langfuse. `metadata` é mesclado ao metadata da generation nos dois
    desfechos.
    """

    objeto: Any = None
    motivo: str | None = None
    erro: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ResultadoChamada:
    """`objeto` validado (ou None) + `motivo` tipado da falha + `usage` bruto
    do OpenRouter (para contabilizar tokens/custo de um lote)."""

    objeto: Any = None
    motivo: str | None = None
    usage: dict | None = None


def strip_markdown_fence(text: str) -> str:
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
def langfuse_client() -> Langfuse | None:
    """Cliente único do SDK por processo, ou `None` sem chaves (telemetria opcional)."""
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return None
    return Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )


def abrir_generation(
    client,
    nome: str,
    entrada: Any,
    max_tokens: int,
    timeout: int,
    modelo: str = LLM_MODEL,
    *,
    nome_trace: str | None = None,
    user_id: str | None = None,
):
    """Abre a generation antes da chamada HTTP, pra latência ser a real.

    SDK v4: nome do trace e user_id só entram por `propagate_attributes`, ativo
    quando a observation é criada (não existe mais `update_trace`).
    """
    if client is None:
        return None
    try:
        with propagate_attributes(trace_name=nome_trace, user_id=user_id):
            return client.start_observation(
                as_type="generation",
                name=nome,
                model=modelo,
                input=entrada,
                model_parameters={"max_tokens": max_tokens, "timeout": timeout},
            )
    except Exception as e:  # noqa: BLE001 — telemetria nunca derruba a chamada
        logger.warning(f"Falha ao abrir generation no Langfuse: {e}")
        return None


def registrar_generation(
    gen,
    *,
    resposta: str | None,
    usage: dict | None,
    sucesso: bool,
    erro: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Fecha a generation com o desfecho e grava `metadata` (ex: `tipo_erro`) nela."""
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
            metadata=metadata or {},
        )
        gen.end()
    except Exception as e:  # noqa: BLE001 — telemetria nunca derruba a chamada
        logger.warning(f"Falha ao registrar generation no Langfuse: {e}")


def _falha(
    tag: str,
    mensagem: str,
    motivo: str,
    gen,
    registrar,
    metadata: dict | None,
    **kwargs,
) -> ResultadoChamada:
    logger.error(f"{tag} {mensagem}")
    registrar(
        gen,
        resposta=kwargs.get("resposta"),
        usage=kwargs.get("usage"),
        sucesso=False,
        erro=kwargs.get("erro", mensagem),
        metadata={**(metadata or {}), "tipo_erro": motivo},
    )
    return ResultadoChamada(None, motivo, kwargs.get("usage"))


def chamar_llm_json(
    prompt_sistema: str,
    prompt_usuario: str,
    schema_pydantic: type[BaseModel],
    *,
    max_tokens: int = MAX_TOKENS_PADRAO,
    timeout: int = TIMEOUT_PADRAO,
    reasoning: dict | None = REASONING_PADRAO,
    extras_payload: dict | None = None,
    temperatura: float = TEMPERATURA_PADRAO,
    metadata: dict | None = None,
    pos_validacao: Callable[[Any, str], ResultadoPosValidacao] | None = None,
    nome_generation: str = "chamar_llm_json",
    nome_trace: str = "llm_openrouter",
    abrir: Callable[[], Any] | None = None,
    registrar: Callable[..., None] | None = None,
    api_key: str | None = None,
    modelo: str | None = None,
) -> ResultadoChamada:
    """Uma tentativa de chamada ao OpenRouter que espera JSON no `schema_pydantic`.

    Falhas técnicas devolvem o status tipado (ADR-022) em `motivo`. Se o JSON
    for válido, `pos_validacao(objeto, content_limpo)` (opcional) decide o
    desfecho semântico. `abrir`/`registrar` permitem ao chamador manter os
    próprios ganchos de telemetria (o extrator de taxonomia usa isso para
    preservar o nome do trace e os pontos de mock dos testes); o padrão é o
    cliente Langfuse deste módulo.
    """
    modelo = modelo or LLM_MODEL
    if registrar is None:

        def registrar(gen, **kw):
            registrar_generation(gen, **kw)

    payload_requisicao = {
        "model": modelo,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario},
        ],
        "max_tokens": max_tokens,
        "temperature": temperatura,
    }
    if reasoning:
        payload_requisicao.update(reasoning)
    if extras_payload:
        # Ex.: {"usage": {"include": True}} faz o OpenRouter devolver o custo.
        payload_requisicao.update(extras_payload)

    headers = {
        "Authorization": f"Bearer {api_key if api_key is not None else OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        **HEADERS_EXTRAS,
    }

    gen = (
        abrir()
        if abrir
        else abrir_generation(
            langfuse_client(),
            nome_generation,
            prompt_usuario,
            max_tokens,
            timeout,
            modelo,
            nome_trace=nome_trace,
        )
    )
    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload_requisicao,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.exceptions.Timeout as e:
        return _falha(
            "[FALHA_TIMEOUT]",
            f"Timeout na chamada ao OpenRouter: {e}",
            STATUS_FALHA_TIMEOUT,
            gen,
            registrar,
            metadata,
        )
    except requests.exceptions.ConnectionError as e:
        return _falha(
            "[FALHA_CONEXAO]",
            f"Falha de conexão com o OpenRouter: {e}",
            STATUS_FALHA_CONEXAO,
            gen,
            registrar,
            metadata,
        )
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        motivo = STATUS_FALHA_RATE_LIMIT if status_code == 429 else STATUS_FALHA_HTTP
        tag = "[FALHA_RATE_LIMIT]" if status_code == 429 else "[FALHA_HTTP]"
        return _falha(
            tag,
            f"OpenRouter respondeu HTTP {status_code}: {e}",
            motivo,
            gen,
            registrar,
            metadata,
        )
    except requests.RequestException as e:
        return _falha(
            "[FALHA_REDE]",
            f"Falha de rede não classificada na chamada ao OpenRouter: {e}",
            STATUS_FALHA_REDE,
            gen,
            registrar,
            metadata,
        )

    data = response.json()
    message = data["choices"][0]["message"]
    content = message.get("content")
    usage = data.get("usage")

    if not content:
        finish_reason = data["choices"][0].get("finish_reason")
        return _falha(
            "[FALHA_CONTEUDO_VAZIO]",
            f"Resposta do LLM sem content (finish_reason={finish_reason}) — "
            "possivelmente max_tokens insuficiente para o reasoning do modelo",
            STATUS_FALHA_CONTEUDO_VAZIO,
            gen,
            registrar,
            metadata,
            usage=usage,
        )

    content_limpo = strip_markdown_fence(content)
    try:
        objeto = schema_pydantic.model_validate(json.loads(content_limpo))
    except json.JSONDecodeError as e:
        return _falha(
            "[FALHA_PARSE_JSON]",
            f"Resposta do LLM não é JSON válido: {e}\nConteúdo bruto: {content[:500]}",
            STATUS_FALHA_PARSE_JSON,
            gen,
            registrar,
            metadata,
            resposta=content,
            usage=usage,
            erro=str(e),
        )
    except ValidationError as e:
        return _falha(
            "[FALHA_VALIDACAO_SCHEMA]",
            f"Resposta do LLM não bateu com {schema_pydantic.__name__}: {e}\nConteúdo bruto: {content[:500]}",
            STATUS_FALHA_VALIDACAO_SCHEMA,
            gen,
            registrar,
            metadata,
            resposta=content,
            usage=usage,
            erro=str(e),
        )

    meta_final = dict(metadata or {})
    if pos_validacao is not None:
        desfecho = pos_validacao(objeto, content_limpo)
        meta_final.update(desfecho.metadata)
        if desfecho.motivo is not None:
            logger.error(desfecho.erro or desfecho.motivo)
            registrar(
                gen,
                resposta=content_limpo,
                usage=usage,
                sucesso=False,
                erro=desfecho.erro,
                metadata={**meta_final, "tipo_erro": desfecho.motivo},
            )
            return ResultadoChamada(None, desfecho.motivo, usage)
        objeto = desfecho.objeto if desfecho.objeto is not None else objeto

    registrar(
        gen,
        resposta=content_limpo,
        usage=usage,
        sucesso=True,
        metadata=meta_final or None,
    )
    return ResultadoChamada(objeto, None, usage)


def chamar_llm_json_com_retry(
    prompt_sistema: str,
    prompt_usuario: str,
    schema_pydantic: type[BaseModel],
    *,
    tentativas: int = 2,
    backoff_segundos: tuple[int, ...] = (5, 15),
    metadata: dict | None = None,
    **kwargs,
) -> tuple[ResultadoChamada, list[ResultadoChamada]]:
    """`chamar_llm_json` com retry e backoff. Retorna o resultado final (motivo
    da última tentativa se todas falharem) e a lista de todas as tentativas
    (para contabilizar chamadas, tokens e falhas por tipo)."""
    historico: list[ResultadoChamada] = []
    for tentativa in range(1, tentativas + 1):
        resultado = chamar_llm_json(
            prompt_sistema,
            prompt_usuario,
            schema_pydantic,
            metadata={**(metadata or {}), "tentativa": tentativa},
            **kwargs,
        )
        historico.append(resultado)
        if resultado.motivo is None:
            return resultado, historico
        if tentativa < tentativas:
            pausa = backoff_segundos[min(tentativa - 1, len(backoff_segundos) - 1)]
            logger.warning(
                f"Tentativa {tentativa}/{tentativas} falhou ({resultado.motivo}) — nova tentativa em {pausa}s."
            )
            time.sleep(pausa)
    return historico[-1], historico
