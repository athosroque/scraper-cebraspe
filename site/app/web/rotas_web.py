"""Rotas HTML do site (5F.2). Reusam a camada `servicos`, como a API v1."""

import hashlib
import logging
import pathlib
from typing import Literal

from app import auth
from app.modelos import FiltroQuestoes
from app.servicos import contas_servico, questoes_servico
from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Web"], include_in_schema=False)
templates = Jinja2Templates(
    directory=str(pathlib.Path(__file__).parent.parent / "templates")
)


def dom_id(chave: str) -> str:
    # A chave estável tem `|`, que em seletor CSS separa namespace: o
    # `hx-target="#..."` quebraria no querySelector do HTMX.
    return "q-" + hashlib.sha1(chave.encode()).hexdigest()[:12]


templates.env.globals["dom_id"] = dom_id
templates.env.globals["csrf_token"] = auth.token_csrf
templates.env.globals["login_habilitado"] = auth.login_habilitado

logger = logging.getLogger(__name__)


def _url_questao(chave: str) -> str:
    concurso, caderno, numero = chave.split("|")
    return f"/q/{concurso}/{caderno}/{numero}"


templates.env.globals["url_questao"] = _url_questao


def _nao_encontrada(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="nao_encontrada.html", status_code=404
    )


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    usuario_id: int | None = Depends(auth.usuario_id_atual),
    banca: str | None = None,
    orgao: str | None = None,
    ano: int | None = None,
    concurso: str | None = None,
    cargo_numero: int | None = None,
    nivel: str | None = None,
    tipo_conhecimento: str | None = None,
    no_id: str | None = None,
    anuladas: Literal["incluir", "excluir", "so"] = "incluir",
    fora_do_edital: Literal["todos", "sim", "nao"] = "todos",
    utilizaveis: Literal["so", "todas"] = "so",
    historico: Literal[
        "todas", "resolvidas", "nao_resolvidas", "certas", "erradas"
    ] = "todas",
    pagina: int = 1,
    tamanho_pagina: int = 20,
):
    # Select vazio chega como "": vale como "sem filtro".
    filtros = FiltroQuestoes(
        banca=banca or None,
        orgao=orgao or None,
        ano=ano,
        concurso=concurso or None,
        cargo_numero=cargo_numero,
        nivel=nivel or None,
        tipo_conhecimento=tipo_conhecimento or None,
        no_id=no_id or None,
        anuladas=anuladas,
        fora_do_edital=fora_do_edital,
        utilizaveis=utilizaveis,
        # Sem login o filtro de histórico não aparece; link antigo vale "todas".
        historico=historico if usuario_id else "todas",
    )
    pagina = max(pagina, 1)
    tamanho_pagina = min(max(tamanho_pagina, 1), 50)
    pagina_questoes = questoes_servico.listar_questoes(
        filtros, pagina, tamanho_pagina, usuario_id
    )

    # A restauração de histórico do HTMX também manda HX-Request, mas espera a
    # página inteira.
    parcial = request.headers.get("HX-Request") and not request.headers.get(
        "HX-History-Restore-Request"
    )
    contexto = {"pagina_questoes": pagina_questoes, "filtros": filtros}
    if parcial:
        nome = "_lista_parcial.html"
    else:
        nome = "lista_questoes.html"
        contexto["arvore"] = questoes_servico.obter_arvore()
        contexto["facetas"] = questoes_servico.obter_facetas()

    resposta = templates.TemplateResponse(request=request, name=nome, context=contexto)
    resposta.headers["Vary"] = "HX-Request"
    return resposta


@router.post(
    "/q/correcao",
    response_class=HTMLResponse,
    dependencies=[Depends(auth.verificar_csrf)],
)
def corrigir_questao(
    request: Request,
    chave: str = Form(...),
    resposta: Literal["C", "E"] = Form(...),
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    resultado = contas_servico.responder(chave, resposta, usuario_id)
    if not resultado:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="_correcao.html",
        context={"resultado": resultado, "logado": usuario_id is not None},
    )


@router.get("/q/{concurso}/{caderno}/{numero}/anexos", response_class=HTMLResponse)
def anexos_questao(request: Request, concurso: str, caderno: str, numero: int):
    """Texto-base e figuras, carregados sob demanda pelo card da lista."""
    questao = questoes_servico.obter_questao_por_chave(f"{concurso}|{caderno}|{numero}")
    if not questao:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request, name="_anexos.html", context={"questao": questao}
    )


@router.get("/q/{concurso}/{caderno}/{numero}", response_class=HTMLResponse)
def detalhe_questao(request: Request, concurso: str, caderno: str, numero: int):
    questao = questoes_servico.obter_questao_por_chave(f"{concurso}|{caderno}|{numero}")
    if not questao:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="questao_detalhe.html",
        context={"questao": questao, "anexos_inline": True},
    )


@router.get("/sobre", response_class=HTMLResponse)
def sobre(request: Request):
    return templates.TemplateResponse(request=request, name="sobre.html")


# -- Contas (5F.3) --
@router.get("/entrar")
async def entrar(request: Request, voltar: str | None = None):
    if not auth.login_habilitado():
        return RedirectResponse("/", status_code=303)
    request.session["voltar"] = auth.destino_seguro(voltar)
    return await auth.oauth.google.authorize_redirect(
        request, str(request.url_for("auth_google"))
    )


@router.get("/auth/google", name="auth_google")
async def auth_google(request: Request):
    voltar = auth.destino_seguro(request.session.pop("voltar", None))
    try:
        token = await auth.oauth.google.authorize_access_token(request)
    except OAuthError:
        logger.warning("Falha no retorno do Google OAuth", exc_info=True)
        return RedirectResponse("/", status_code=303)
    info = token.get("userinfo") or {}
    if not info.get("sub") or not info.get("email_verified"):
        return RedirectResponse("/", status_code=303)
    usuario = contas_servico.entrar_com_google(
        info["sub"], info["email"], info.get("name")
    )
    auth.iniciar_sessao(request, usuario.id, usuario.nome or usuario.email)
    return RedirectResponse(voltar, status_code=303)


@router.post("/sair", dependencies=[Depends(auth.verificar_csrf)])
def sair(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@router.get("/conta", response_class=HTMLResponse)
def conta(
    request: Request,
    concurso: str | None = None,
    nivel: str | None = None,
    tipo_conhecimento: str | None = None,
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    if usuario_id is None:
        return RedirectResponse("/entrar?voltar=/conta", status_code=303)
    usuario = contas_servico.obter_usuario(usuario_id)
    if not usuario:
        # Conta apagada em outra sessão: o cookie ficou órfão.
        request.session.clear()
        return RedirectResponse("/", status_code=303)
    filtros = FiltroQuestoes(
        concurso=concurso or None,
        nivel=nivel or None,
        tipo_conhecimento=tipo_conhecimento or None,
    )
    return templates.TemplateResponse(
        request=request,
        name="conta.html",
        context={
            "usuario": usuario,
            "filtros": filtros,
            "desempenho": contas_servico.desempenho(usuario_id, filtros),
            "facetas": questoes_servico.obter_facetas(),
        },
    )


@router.post("/conta/apagar", dependencies=[Depends(auth.verificar_csrf)])
def apagar_conta(
    request: Request, usuario_id: int | None = Depends(auth.usuario_id_atual)
):
    if usuario_id is not None:
        contas_servico.apagar_conta(usuario_id)
    request.session.clear()
    return RedirectResponse("/", status_code=303)
