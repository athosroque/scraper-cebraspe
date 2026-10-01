import logging
import pathlib
from contextlib import asynccontextmanager

import psycopg2
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.rotas_conta import router as router_conta
from app.api.v1.rotas_questoes import router as router_questoes
from app.api.v1.rotas_questoes import router_arvore, router_facetas
from app.config import settings
from app.db import fechar_pools, get_conexao_leitura, inicializar_pools
from app.web.rotas_web import router as router_web

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_pools()
    yield
    fechar_pools()


app = FastAPI(
    title="Questões CEBRASPE",
    description=(
        "API de leitura do site público de questões CEBRASPE (piloto 2025). "
        "Fonte das questões: CEBRASPE (cebraspe.org.br). Ver ADR-033."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Sessão em cookie assinado (5F.3): só id do usuário, nome e token CSRF.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    session_cookie="sessao",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_https_only,
)

# Arquivos estáticos do frontend (Pico, HTMX, Alpine)
static_path = pathlib.Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Servir figuras locais (fallback se não houver URL estática)
if settings.figuras_dir.exists():
    app.mount(
        "/figuras", StaticFiles(directory=str(settings.figuras_dir)), name="figuras"
    )

# Incluir rotas
app.include_router(router_questoes, prefix="/api/v1")
app.include_router(router_arvore, prefix="/api/v1")
app.include_router(router_facetas, prefix="/api/v1")
app.include_router(router_conta, prefix="/api/v1")
app.include_router(router_web)


@app.get("/saude", tags=["Infra"], summary="Checagem de saúde (banco de leitura)")
def saude():
    try:
        with get_conexao_leitura() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except psycopg2.Error:
        logger.exception("Falha na checagem de saúde do banco")
        return JSONResponse(status_code=503, content={"status": "erro"})
    return {"status": "ok"}
