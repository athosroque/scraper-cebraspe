"""Rotas HTML do site (5F.2). Reusam a camada `servicos`, como a API v1."""

import hashlib
import pathlib
from typing import Literal

from app.modelos import FiltroQuestoes
from app.servicos import questoes_servico
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
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
    )
    pagina = max(pagina, 1)
    tamanho_pagina = min(max(tamanho_pagina, 1), 50)
    pagina_questoes = questoes_servico.listar_questoes(filtros, pagina, tamanho_pagina)

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


@router.post("/q/correcao", response_class=HTMLResponse)
def corrigir_questao(
    request: Request,
    chave: str = Form(...),
    resposta: Literal["C", "E"] = Form(...),
):
    questao = questoes_servico.obter_questao_por_chave(chave)
    if not questao:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="_correcao.html",
        context={
            "questao": questao,
            "resposta": resposta,
            "acertou": questao.gabarito == resposta,
        },
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
