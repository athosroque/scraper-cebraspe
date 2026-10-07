import logging
import pathlib
from contextlib import asynccontextmanager
from typing import Literal

import psycopg2
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.rotas_conta import router as router_conta
from app.api.v1.rotas_estatisticas import router as router_estatisticas
from app.api.v1.rotas_materias import router as router_materias
from app.api.v1.rotas_questoes import router as router_questoes
from app.api.v1.rotas_questoes import router_arvore, router_facetas
from app.api.v1.rotas_simulados import router as router_simulados
from app.config import settings
from app.db import fechar_pools, get_conexao_leitura, inicializar_pools
from app.web.rotas_web import router as router_web
from app.web.rotas_web import router_auth

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_pools()
    yield
    fechar_pools()


DESCRICAO = """
API do site público de questões CEBRASPE (piloto 2025: PF, STM, IBAMA, CD e TCU).

**Autenticação.** Login só com Google (`GET /entrar`). A sessão é o cookie
assinado `sessao`. Todo `POST`/`DELETE` exige o header `X-CSRFToken` com o
token da sessão (exposto no `hx-headers` do `<body>` das páginas). No botão
**Authorize**, `sessao` e `csrf` descrevem esses dois valores. Rotas de leitura
pública não pedem login.

**Chave da questão.** Toda questão é identificada pela chave estável
`concurso|caderno|numero` (ex.: `PF_25_ADM|094_PF_CB1_01|1`); no caminho da URL,
codifique `|` como `%7C`. Use a chave, nunca `questao_id`, para guardar
referências.

**Erros.** Sempre `{"detail": "..."}` (modelo `Erro`).

**Fonte.** Questões, gabaritos e cadernos são do CEBRASPE (cebraspe.org.br);
cite a fonte ao republicar. Pedidos de remoção: athosroque@hotmail.com.

**Fora do contrato.** As rotas HTML do site (`/`, `/q/...`, `/conta`,
`/simulado`, `/estatisticas`...) não fazem parte desta API; só login e logout
aparecem aqui, na tag Autenticação.
"""

TAGS = [
    {
        "name": "Questões",
        "description": "Listagem filtrável e detalhe das questões objetivas (certo/errado).",
    },
    {
        "name": "Árvore",
        "description": "Árvore mestre disciplina → assunto → subassunto com contagem de questões.",
    },
    {
        "name": "Facetas",
        "description": "Valores possíveis dos filtros, com o total de questões de cada um.",
    },
    {
        "name": "Disciplinas",
        "description": "Disciplinas da árvore com resumo e os subassuntos que mais caem.",
    },
    {
        "name": "Conta",
        "description": "Resposta a questões, dados da conta e desempenho pessoal (com login).",
    },
    {
        "name": "Estatísticas",
        "description": "O que mais cai na prova, o que o edital cobra e edital × prova.",
    },
    {
        "name": "Simulado",
        "description": "Prova de um cargo sem gabarito e correção no padrão CEBRASPE (certo +1, errado −1).",
    },
    {
        "name": "Autenticação",
        "description": "Login com Google e logout. Respondem com redirecionamento (303).",
    },
    {"name": "Infra", "description": "Checagem de saúde do serviço."},
]

app = FastAPI(
    title="Questões CEBRASPE",
    description=DESCRICAO,
    openapi_tags=TAGS,
    version="1.0.0",
    lifespan=lifespan,
)

from fastapi import Request
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.web.rotas_web import templates


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    accept = request.headers.get("accept", "")
    if request.url.path.startswith("/api/") or "text/html" not in accept:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if exc.status_code in (404, 405):
        e405 = exc.status_code == 405
        resp = templates.TemplateResponse(
            request=request,
            name="nao_encontrada.html",
            status_code=exc.status_code,
            context={
                "codigo": exc.status_code,
                "titulo": "Método não permitido" if e405 else "Página não encontrada",
                "mensagem": "Esta página não aceita esse tipo de requisição."
                if e405
                else "O endereço pode estar errado ou a página foi removida.",
            },
        )
        # Preserva o Allow do 405 (RFC 9110).
        if exc.headers:
            resp.headers.update(exc.headers)
        return resp
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


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
app.include_router(router_estatisticas, prefix="/api/v1")
app.include_router(router_materias, prefix="/api/v1")
app.include_router(router_simulados, prefix="/api/v1")
app.include_router(router_auth)
app.include_router(router_web)


class Saude(BaseModel):
    """Estado do serviço."""

    status: Literal["ok", "erro"] = Field(
        description="`ok` quando o banco de leitura responde; `erro` caso contrário."
    )


@app.get(
    "/saude",
    tags=["Infra"],
    summary="Checagem de saúde (banco de leitura)",
    description="Executa `SELECT 1` no banco de leitura. Banco fora do ar: 503.",
    response_model=Saude,
    responses={503: {"model": Saude, "description": "Banco de leitura indisponível."}},
)
def saude():
    try:
        with get_conexao_leitura() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except psycopg2.Error:
        logger.exception("Falha na checagem de saúde do banco")
        return JSONResponse(status_code=503, content={"status": "erro"})
    return {"status": "ok"}
