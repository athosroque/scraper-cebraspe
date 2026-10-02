"""Rotas HTML do site (5F.2). Reusam a camada `servicos`, como a API v1."""

import hashlib
import logging
import pathlib
from typing import Literal
from urllib.parse import urlencode

from app import auth
from app.modelos import FiltroEstatistica, FiltroQuestoes, NivelAlvo
from app.servicos import (
    contas_servico,
    estatisticas_servico,
    questoes_servico,
    simulados_servico,
)
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


def _url_lista(no_id: str, filtros: FiltroEstatistica) -> str:
    """Lista de questões já filtrada pelo nó e pelos filtros da estatística."""
    # Anuladas fora, como na contagem da estatística.
    params = {
        "no_id": no_id,
        "anuladas": "excluir",
        **filtros.model_dump(exclude_none=True),
    }
    return "/questoes?" + urlencode(params)


templates.env.globals["url_lista"] = _url_lista


def _nome_do_no(arvore, no_id: str | None) -> str | None:
    pilha = list(arvore)
    while no_id and pilha:
        no = pilha.pop()
        if no.id == no_id:
            return no.nome
        pilha.extend(no.filhos)
    return None


def _nao_encontrada(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request, name="nao_encontrada.html", status_code=404
    )


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    # Grade de matérias (5F.9/5F.7): mesma lista de /api/v1/materias.
    materias = estatisticas_servico.listar_materias()
    return templates.TemplateResponse(
        request=request, name="inicio.html", context={"materias": materias}
    )


@router.get("/questoes", response_class=HTMLResponse)
def index(
    request: Request,
    usuario_id: int | None = Depends(auth.usuario_id_atual),
    banca: str | None = None,
    orgao: str | None = None,
    ano: int | None = None,
    concurso: str | None = None,
    # str: trocar o concurso manda `cargo_numero=`, que como int daria 422.
    cargo_numero: str | None = None,
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
        cargo_numero=int(cargo_numero)
        if cargo_numero and cargo_numero.isdigit()
        else None,
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
    # O chip do assunto precisa do nome também no fragmento.
    arvore = questoes_servico.obter_arvore() if filtros.no_id or not parcial else []
    contexto["no_nome"] = _nome_do_no(arvore, filtros.no_id)
    if parcial:
        nome = "_lista_parcial.html"
    else:
        nome = "lista_questoes.html"
        contexto["arvore"] = arvore
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


@router.get("/q/{concurso}/{caderno}/{numero}/parecidas", response_class=HTMLResponse)
def parecidas_questao(request: Request, concurso: str, caderno: str, numero: int):
    """Questões parecidas, carregadas sob demanda pelo card da lista."""
    parecidas = questoes_servico.parecidas(f"{concurso}|{caderno}|{numero}")
    if parecidas is None:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request, name="_parecidas.html", context={"parecidas": parecidas}
    )


@router.get("/q/{concurso}/{caderno}/{numero}", response_class=HTMLResponse)
def detalhe_questao(request: Request, concurso: str, caderno: str, numero: int):
    chave = f"{concurso}|{caderno}|{numero}"
    questao = questoes_servico.obter_questao_por_chave(chave)
    if not questao:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="questao_detalhe.html",
        context={
            "questao": questao,
            "anexos_inline": True,
            "parecidas": questoes_servico.parecidas(chave) or [],
        },
    )


@router.get("/sobre", response_class=HTMLResponse)
def sobre(request: Request):
    return templates.TemplateResponse(request=request, name="sobre.html")


# -- Estatísticas (5F.4) --
def _filtro_estatistica(
    concurso: str | None,
    cargo_numero: str | None,
    nivel: str | None,
    tipo_conhecimento: str | None,
) -> FiltroEstatistica:
    # Select vazio chega como "": vale como "sem filtro" (o cargo é str porque
    # trocar o concurso manda `cargo_numero=`, que como int daria 422). Cargo
    # sem concurso não identifica nada (o número se repete entre concursos).
    concurso = concurso or None
    numero = int(cargo_numero) if cargo_numero and cargo_numero.isdigit() else None
    return FiltroEstatistica(
        concurso=concurso,
        cargo_numero=numero if concurso else None,
        nivel=nivel or None,
        tipo_conhecimento=tipo_conhecimento or None,
    )


def _ranking(
    request: Request,
    aba: Literal["prova", "edital"],
    nivel_alvo: NivelAlvo,
    materia_id: str | None,
    filtros: FiltroEstatistica,
):
    materia_id = materia_id or None
    if aba == "prova":
        linhas = estatisticas_servico.prova_cobra(nivel_alvo, filtros, materia_id, 30)
        maximo = max((r.questoes for r in linhas), default=0)
    else:
        linhas = estatisticas_servico.edital_cobra(nivel_alvo, filtros, materia_id, 30)
        maximo = max((r.ocorrencias for r in linhas), default=0)
    return templates.TemplateResponse(
        request=request,
        name="estatisticas.html",
        context={
            "aba": aba,
            "linhas": linhas,
            "maximo": maximo,
            "nivel_alvo": nivel_alvo,
            "materia_id": materia_id,
            "filtros": filtros,
            "materias": estatisticas_servico.materias(),
            "cargos": estatisticas_servico.cargos(),
        },
    )


@router.get("/estatisticas", response_class=HTMLResponse)
def estatisticas_prova(
    request: Request,
    nivel_alvo: NivelAlvo = "subassunto",
    materia_id: str | None = None,
    concurso: str | None = None,
    cargo_numero: str | None = None,
    nivel: str | None = None,
    tipo_conhecimento: str | None = None,
):
    filtros = _filtro_estatistica(concurso, cargo_numero, nivel, tipo_conhecimento)
    return _ranking(request, "prova", nivel_alvo, materia_id, filtros)


@router.get("/estatisticas/edital", response_class=HTMLResponse)
def estatisticas_edital(
    request: Request,
    nivel_alvo: NivelAlvo = "subassunto",
    materia_id: str | None = None,
    concurso: str | None = None,
    cargo_numero: str | None = None,
    nivel: str | None = None,
    tipo_conhecimento: str | None = None,
):
    filtros = _filtro_estatistica(concurso, cargo_numero, nivel, tipo_conhecimento)
    return _ranking(request, "edital", nivel_alvo, materia_id, filtros)


@router.get("/estatisticas/edital-vs-prova", response_class=HTMLResponse)
def estatisticas_edital_vs_prova(
    request: Request,
    concurso: str | None = None,
    cargo_numero: str | None = None,
):
    filtros = _filtro_estatistica(concurso, cargo_numero, None, None)
    resultado = None
    if filtros.concurso and filtros.cargo_numero:
        resultado = estatisticas_servico.edital_vs_prova(
            filtros.concurso, filtros.cargo_numero
        )
    return templates.TemplateResponse(
        request=request,
        name="edital_vs_prova.html",
        context={
            "aba": "edital_vs_prova",
            "filtros": filtros,
            "resultado": resultado,
            "cargos": estatisticas_servico.cargos(),
        },
    )


# -- Simulado (5F.5) --
_PREFIXO_RESPOSTA = "r:"


def _respostas_do_form(form) -> dict[str, str]:
    """Campos `r:<chave>` com C/E; em branco ou valor inválido fica de fora."""
    return {
        campo[len(_PREFIXO_RESPOSTA) :]: valor
        for campo, valor in form.items()
        if campo.startswith(_PREFIXO_RESPOSTA) and valor in ("C", "E")
    }


@router.get("/simulado", response_class=HTMLResponse)
def simulado_inicio(
    request: Request,
    concurso: str | None = None,
    cargo_numero: str | None = None,
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    filtros = _filtro_estatistica(concurso, cargo_numero, None, None)
    return templates.TemplateResponse(
        request=request,
        name="simulado_inicio.html",
        context={
            "filtros": filtros,
            "cargos": estatisticas_servico.cargos(),
            "simulados": simulados_servico.listar(usuario_id) if usuario_id else [],
        },
    )


@router.post("/simulado/iniciar", dependencies=[Depends(auth.verificar_csrf)])
def simulado_iniciar(
    request: Request,
    concurso: str = Form(...),
    cargo_numero: int = Form(...),
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    # Sem login, a prova roda sem registro; com login, o simulado nasce aqui
    # (o início vale para o cronômetro e para o histórico).
    if usuario_id is None:
        query = urlencode({"concurso": concurso, "cargo_numero": cargo_numero})
        return RedirectResponse(f"/simulado/prova?{query}", status_code=303)
    simulado_id = simulados_servico.iniciar(usuario_id, concurso, cargo_numero)
    if simulado_id is None:
        return _nao_encontrada(request)
    return RedirectResponse(f"/simulado/{simulado_id}", status_code=303)


@router.get("/simulado/prova", response_class=HTMLResponse)
def simulado_prova_avulsa(request: Request, concurso: str, cargo_numero: int):
    prova = simulados_servico.montar_prova(concurso, cargo_numero)
    if not prova:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request, name="simulado_prova.html", context={"prova": prova}
    )


@router.get("/simulado/{simulado_id}/revisar", response_class=HTMLResponse)
def simulado_revisar(
    request: Request,
    simulado_id: int,
    situacao: Literal["errado", "branco"] = "errado",
    pagina: int = 1,
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    """Questões erradas (ou em branco) de um simulado encerrado, para refazer."""
    if usuario_id is None:
        voltar = f"/simulado/{simulado_id}/revisar?situacao={situacao}&pagina={pagina}"
        return RedirectResponse(
            "/entrar?" + urlencode({"voltar": voltar}), status_code=303
        )
    try:
        pagina_questoes = simulados_servico.questoes_por_situacao(
            simulado_id, usuario_id, situacao, max(pagina, 1), 20
        )
    except simulados_servico.SimuladoAberto:
        return RedirectResponse(f"/simulado/{simulado_id}", status_code=303)
    if pagina_questoes is None:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="simulado_revisar.html",
        context={
            "pagina_questoes": pagina_questoes,
            "simulado": simulados_servico.obter_simulado(simulado_id, usuario_id),
            "situacao": situacao,
        },
    )


@router.get("/simulado/{simulado_id}", response_class=HTMLResponse)
def simulado_gravado(
    request: Request,
    simulado_id: int,
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    if usuario_id is None:
        return RedirectResponse(
            f"/entrar?voltar=/simulado/{simulado_id}", status_code=303
        )
    simulado = simulados_servico.obter_simulado(simulado_id, usuario_id)
    if not simulado:
        return _nao_encontrada(request)
    if simulado["fim"] is not None:
        return templates.TemplateResponse(
            request=request,
            name="simulado_resultado.html",
            context={
                "resultado": simulados_servico.obter_resultado(simulado_id, usuario_id)
            },
        )
    prova = simulados_servico.montar_prova(
        simulado["concurso"], simulado["cargo_numero"]
    )
    if not prova:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="simulado_prova.html",
        context={"prova": prova, "simulado": simulado},
    )


@router.post(
    "/simulado/corrigir",
    response_class=HTMLResponse,
    dependencies=[Depends(auth.verificar_csrf)],
)
async def simulado_corrigir(
    request: Request, usuario_id: int | None = Depends(auth.usuario_id_atual)
):
    form = await request.form()
    respostas = _respostas_do_form(form)
    simulado_id = form.get("simulado_id", "")
    if simulado_id.isdigit() and usuario_id is None:
        # Login caiu no meio da prova: corrigir como avulso deixaria o simulado
        # aberto para sempre. Volta pela prova gravada (o rascunho continua lá).
        return RedirectResponse(
            f"/entrar?voltar=/simulado/{simulado_id}", status_code=303
        )
    if simulado_id.isdigit():
        try:
            if not simulados_servico.encerrar(int(simulado_id), usuario_id, respostas):
                return _nao_encontrada(request)
        except simulados_servico.SimuladoJaEncerrado:
            pass  # reenvio do form: mostra o resultado já gravado
        return RedirectResponse(f"/simulado/{simulado_id}", status_code=303)
    cargo = form.get("cargo_numero", "")
    resultado = cargo.isdigit() and simulados_servico.corrigir_avulso(
        form.get("concurso", ""), int(cargo), respostas
    )
    if not resultado:
        return _nao_encontrada(request)
    return templates.TemplateResponse(
        request=request,
        name="simulado_resultado.html",
        context={"resultado": resultado},
    )


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
            "resumo": contas_servico.resumo_completo(usuario_id),
            "prioridades": contas_servico.prioridades(usuario_id, 5),
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


# -- Painel da matéria (5F.10) --
@router.get("/materias/{no_id}", response_class=HTMLResponse)
def painel_materia(
    request: Request,
    no_id: str,
    concurso: str | None = None,
    cargo_numero: str | None = None,
    nivel: str | None = None,
):
    filtros = _filtro_estatistica(concurso, cargo_numero, nivel, None)
    # Mesmo serviço de /api/v1/materias/{id}. Anulada também se resolve (com
    # aviso no card): subassunto só com anuladas fica no ranking, com 0 válidas.
    materia = estatisticas_servico.detalhe_materia(no_id, filtros, 15)
    if materia is None:
        return _nao_encontrada(request)
    linhas = materia.top_subassuntos
    filtros_lista = filtros.model_dump(exclude_none=True)
    return templates.TemplateResponse(
        request=request,
        name="materia.html",
        context={
            "materia": materia,
            "linhas": linhas,
            "maximo": max((r.questoes for r in linhas), default=0),
            "filtros": filtros,
            "cargos": estatisticas_servico.cargos(),
            "url_resolver": "/questoes?" + urlencode({"no_id": no_id, **filtros_lista}),
            "urls_subassunto": {
                r.no_id: "/questoes?" + urlencode({"no_id": r.no_id, **filtros_lista})
                for r in linhas
            },
        },
    )
