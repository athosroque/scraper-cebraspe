import logging
import os
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from langfuse import Langfuse
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src import llm_openrouter
from src.llm_openrouter import REASONING_PADRAO

load_dotenv()

# Configura log
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
if ALLOWED_USER_ID:
    ALLOWED_USER_ID = int(ALLOWED_USER_ID)

# OpenRouter (acesso direto REST via httpx, sem proxy)
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = llm_openrouter.chave_openrouter(
    llm_openrouter.ETAPA_TELEGRAM, "TELEGRAM_OPENROUTER_API_KEY"
)
NOME_TRACE = llm_openrouter.ETAPA_TELEGRAM[1]
MODEL_NAME = os.getenv("TELEGRAM_OPENROUTER_MODEL", "z-ai/glm-5.3-flash")

# Langfuse via SDK oficial (OTel, credenciais dedicadas do Telegram com fallback)
LANGFUSE_HOST = (
    os.getenv("TELEGRAM_LANGFUSE_HOST")
    or os.getenv("LANGFUSE_HOST")
    or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
)
LANGFUSE_PUBLIC_KEY = os.getenv("TELEGRAM_LANGFUSE_PUBLIC_KEY") or os.getenv(
    "LANGFUSE_PUBLIC_KEY", ""
)
LANGFUSE_SECRET_KEY = os.getenv("TELEGRAM_LANGFUSE_SECRET_KEY") or os.getenv(
    "LANGFUSE_SECRET_KEY", ""
)

PROJECT_CONTEXT = ""


def load_project_context() -> str:
    """Retorna um resumo conciso e estruturado da arquitetura e componentes do projeto."""
    return """=== PROJETO: Scraper CEBRASPE ===
Pipeline automatizado de rastreamento, download, extração de conteúdo programático e estruturação taxonômica de editais, provas e gabaritos de concursos públicos do CEBRASPE.

--- ESTRUTURA DE DIRETÓRIOS E COMPONENTES ---
• src/spider.py: Crawler Playwright para /concursos/encerrado. Extrai ano e órgão do slug da URL (_YY), mapeia links de PDFs (editais, provas, gabaritos) e controla idempotência em data/processed_concursos.json.
• src/downloader.py: Downloader com dupla desduplicação (URL via .manifest.json e hash SHA256 em disco) e validação de integridade por magic bytes (%PDF-).
• src/edital_parser.py: Parser PyMuPDF que recorta a seção 'OBJETOS DE AVALIAÇÃO' e divide o conteúdo programático em chunks por cargo e matéria.
• src/taxonomia_extractor.py: Extrator de taxonomia estruturada (matéria -> tópico -> subtópico) via OpenRouter REST API (z-ai/glm-5.3-flash), validado por TaxonomiaEdital (Pydantic), com retry e auditoria.
• src/models_scraper.py: Schemas e modelos de dados Pydantic (TaxonomiaEdital, Topico, CargoEdital, ConcursoMetadados).
• src/logger.py: Logger unificado com ancoragem em logs/scraper_cebraspe.log.
• src/telegram_bot.py: Assistente técnico do desenvolvedor no Telegram, com chamadas diretas REST ao OpenRouter e telemetria no Langfuse.
• scripts/gerar_db_datasette.py: Constrói o banco SQLite revisao_piloto/revisao.db com busca textual FTS5.
• scripts/revisar_taxonomia_piloto.py: Orquestrador de extração do edital piloto com trilha de auditoria (.auditoria.json).
• scripts/reprocessar_falhas_piloto.py: Reprocessador de chunks que falharam na extração.
• data/: Armazenamento físico de PDFs baixados (data/<ano>/CEBRASPE/<orgao>/) e manifesto de download.
• revisao_piloto/: Armazenamento de resultados JSON (<edital>.json) e trilhas de auditoria (<edital>.auditoria.json).
• docs/ & docs/adr/: Documentação arquitetural e Registros de Decisões de Arquitetura (ADRs 001 a 016).
• tests/: Suíte de testes com pytest cobrindo crawler, downloader, parser, extrator e bot.

--- FERRAMENTAS E SERVIÇOS DISPONÍVEIS ---
1. OpenRouter API: Endpoint REST oficial (https://openrouter.ai/api/v1/chat/completions) para inferência com o modelo z-ai/glm-5.3-flash.
2. Langfuse via SDK oficial (OTel): Ingestão de traces e métricas de observabilidade com chaves e projetos dedicados.
3. Playwright: Automação e raspagem de páginas web com stealth.
4. PyMuPDF (fitz): Leitura de arquivos PDF e inspeção de layout e blocos de texto.
5. Datasette + Traefik + Cloudflare Tunnel: Interface de revisão de dados com SSO (https://datasette.projetoathos.com.br).
6. PostgreSQL 16 (scraper-cebraspe-db): Banco próprio do projeto, independente do study-rag-agent (porta 127.0.0.1:5435 / rede homelab_default, ADR-026)."""


def get_system_prompt() -> str:
    """Gera o prompt de sistema otimizado com o contexto essencial do projeto."""
    return f"""Você é o assistente técnico de desenvolvimento e troubleshooting do projeto Scraper CEBRASPE.
Sua missão é ajudar o desenvolvedor a entender o funcionamento do pipeline, debugar erros, planejar melhorias e navegar na estrutura do repositório. Responda em português de forma concisa, direta e tecnicamente precisa.

Contexto geral do projeto, localização de arquivos, funções e ferramentas disponíveis:

{PROJECT_CONTEXT}
"""


def is_allowed(update: Update) -> bool:
    """Verifica se o usuário está autorizado a usar o bot."""
    if not ALLOWED_USER_ID:
        return True  # Se não tiver ID configurado, permite todos

    if not update.effective_user:
        return False

    user_id = update.effective_user.id
    if user_id == ALLOWED_USER_ID:
        return True

    logger.warning(f"Mensagem ignorada do usuário não autorizado: ID {user_id}")
    return False


@lru_cache(maxsize=1)
def _langfuse_client() -> Langfuse | None:
    """Cliente único do SDK por processo, ou `None` sem chaves (telemetria opcional).

    O SDK exporta em thread de fundo e registra `atexit` para o flush final.
    """
    if not (LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY):
        return None
    return Langfuse(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
    )


def _abrir_generation(prompt: str, model: str):
    """Abre a generation antes da chamada ao OpenRouter para latência real."""
    client = _langfuse_client()
    if client is None:
        return None
    try:
        return client.start_observation(
            as_type="generation",
            name="telegram_response",
            model=model,
            input=prompt,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Falha ao abrir generation no Langfuse: {e}")
        return None


def _registrar_langfuse(
    gen,
    *,
    resposta: str | None,
    usage: dict | None,
    sucesso: bool,
    erro: str | None = None,
    user_id: int | str | None = None,
) -> None:
    """Fecha a generation com o desfecho e associa user_id e nome no trace."""
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
        gen.update_trace(
            name=NOME_TRACE,
            user_id=str(user_id) if user_id else None,
        )
        gen.end()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Falha ao registrar generation no Langfuse: {e}")


async def chamar_openrouter(
    messages: list[dict],
    user_id: int | str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> str:
    """Chama diretamente a API REST do OpenRouter via httpx."""
    key = OPENROUTER_API_KEY if api_key is None else api_key
    if not key:
        raise ValueError(
            "Chave da API do OpenRouter não configurada. Defina OPENROUTER_KEY_TELEGRAM no .env."
        )

    endpoint = base_url or OPENROUTER_BASE_URL
    model_name = model or MODEL_NAME

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/athosroque/scraper_cebraspe",
        "X-Title": "Scraper Cebraspe Telegram Bot",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
        # Limite de reasoning comum a toda chamada LLM do projeto.
        **REASONING_PADRAO,
    }

    user_prompt = messages[-1]["content"] if messages else ""
    gen = _abrir_generation(user_prompt, model_name)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{endpoint}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        logger.error(f"Erro na chamada do OpenRouter: {e}")
        _registrar_langfuse(
            gen,
            resposta=None,
            usage=None,
            sucesso=False,
            erro=str(e),
            user_id=user_id,
        )
        raise

    choice = data.get("choices", [{}])[0]
    answer = choice.get("message", {}).get("content") or ""
    usage = data.get("usage")

    _registrar_langfuse(
        gen,
        resposta=answer,
        usage=usage,
        sucesso=True,
        user_id=user_id,
    )
    return answer


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update) or not update.message:
        return
    await update.message.reply_text(
        "Olá! Sou o assistente técnico de desenvolvimento do Scraper CEBRASPE.\n"
        "Tenho conhecimento de toda a arquitetura, estrutura de diretórios, funções dos módulos e ferramentas integradas.\n"
        "Me pergunte qualquer coisa sobre o projeto ou peça auxílio na depuração!\n\n"
        "Comandos úteis:\n"
        "/ajuda - Exibe visão geral da arquitetura, diretórios e ferramentas.\n"
        "/reload_context - Recarrega o resumo contextual do projeto."
    )


async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update) or not update.message:
        return
    await update.message.reply_text(
        "📌 *Guia Rápido do Scraper CEBRASPE*\n\n"
        "• *Pipeline*: Spider (Playwright) ➔ Downloader (PDFs + Dedup) ➔ Parser (PyMuPDF) ➔ Extrator (OpenRouter REST) ➔ Revisão (Datasette)\n"
        "• *Módulos*: `src/` (código central), `scripts/` (revisão e banco), `docs/` (ADRs e arquitetura)\n"
        "• *Ferramentas*: OpenRouter (`z-ai/glm-5.3-flash`), Langfuse Cloud REST, Playwright, PyMuPDF, Datasette (FTS5), Postgres (`scraper-cebraspe-db`)\n\n"
        "Envie sua pergunta ou instrução técnica que irei te ajudar!",
        parse_mode="Markdown",
    )


async def reload_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update) or not update.message:
        return

    global PROJECT_CONTEXT
    PROJECT_CONTEXT = load_project_context()
    await update.message.reply_text(
        "Contexto arquitetural do projeto recarregado com sucesso!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update) or not update.message or not update.effective_chat:
        return

    user_message = update.message.text or ""
    user_id = update.effective_user.id if update.effective_user else None

    # Adiciona indicativo de digitando
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": user_message},
        ]

        answer = await chamar_openrouter(messages, user_id=user_id)

        # O Telegram tem limite de 4096 caracteres por mensagem
        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                await update.message.reply_text(answer[i : i + 4000])
        else:
            await update.message.reply_text(answer)

    except Exception as e:  # noqa: BLE001
        logger.error(f"Erro ao processar mensagem do Telegram: {e}")
        await update.message.reply_text(
            f"Ocorreu um erro ao processar sua requisição: {e!s}"
        )


def main() -> None:
    global PROJECT_CONTEXT
    PROJECT_CONTEXT = load_project_context()
    logger.info("Contexto do projeto carregado.")

    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN não configurado no .env.")

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler(["ajuda", "help"], ajuda))
    application.add_handler(CommandHandler("reload_context", reload_context))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("Iniciando o bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
