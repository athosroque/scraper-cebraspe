"""Rotas HTML do site (5F.2). Reusam a camada `servicos`, como a API v1."""

import logging
import pathlib
import re
from typing import Annotated, Literal
from urllib.parse import urlencode

from app import auth
from app.api.v1.respostas_comuns import R403
from app.modelos import ConcursoAlvo, FiltroEstatistica, FiltroQuestoes, NivelAlvo
from app.servicos import (
    contas_servico,
    estatisticas_servico,
    questoes_servico,
    simulados_servico,
)
from app.servicos.formatacao import (
    ROTULO_NIVEL,
    hash_chave,
    rotulo_concurso,
    rotulo_materia,
    rotulo_nivel,
    rotulo_tipo_conhecimento,
)
from authlib.integrations.base_client import OAuthError
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Web"], include_in_schema=False)
# Login/logout ficam no contrato (5F.6); as demais rotas HTML, não.
router_auth = APIRouter(tags=["Autenticação"])
_303 = {303: {"description": "Redireciona (header `Location`)."}}
templates = Jinja2Templates(
    directory=str(pathlib.Path(__file__).parent.parent / "templates")
)


def dom_id(chave: str) -> str:
    # A chave estável tem `|`, que em seletor CSS separa namespace: o
    # `hx-target="#..."` quebraria no querySelector do HTMX.
    return "q-" + hash_chave(chave)[:12]


def filtro_num(valor: float | None) -> str:
    if valor is None:
        return ""
    return f"{valor:,.0f}".replace(",", ".")


def filtro_pct(valor: float | None) -> str:
    if valor is None:
        return ""
    return f"{valor:.2f}%".replace(".", ",")


templates.env.filters["num"] = filtro_num
templates.env.filters["pct"] = filtro_pct
templates.env.globals["dom_id"] = dom_id
templates.env.globals["csrf_token"] = auth.token_csrf
templates.env.globals["login_habilitado"] = auth.login_habilitado
templates.env.globals["ROTULO_NIVEL"] = ROTULO_NIVEL
templates.env.globals["rotulo_concurso"] = rotulo_concurso
templates.env.globals["rotulo_materia"] = rotulo_materia
templates.env.globals["rotulo_nivel"] = rotulo_nivel
templates.env.globals["rotulo_tipo_conhecimento"] = rotulo_tipo_conhecimento

logger = logging.getLogger(__name__)


def _url_questao(chave: str) -> str:
    concurso, caderno, numero = chave.split("|")
    return f"/q/{concurso}/{caderno}/{numero}"


templates.env.globals["url_questao"] = _url_questao


def _nos_do_card(nos) -> list[dict]:
    """Nós da questão para a barra do card: principal primeiro, cada um com o
    caminho em partes (nome + id do nó daquele nível, quando conhecido)."""
    saida = []
    for no in sorted(nos or [], key=lambda n: n.papel != "principal"):
        # O caminho vem montado da árvore; o separador varia entre " > " e " › ".
        partes = [p.strip() for p in re.split(r" [>›] ", no.no_caminho or "")]
        partes = [p for p in partes if p] or [no.no_nome]
        ids = {
            "subassunto": [no.materia_id, no.assunto_id, no.no_id],
            "assunto": [no.materia_id, no.no_id],
        }.get(no.no_nivel, [no.no_id])
        if len(ids) == len(partes):
            # A 1ª parte é a matéria: matéria com nome de cargo ganha o rótulo.
            partes[0] = no.rotulo_materia or partes[0]
        else:
            # Caminho fora do padrão: só a última parte tem id garantido.
            ids = [None] * (len(partes) - 1) + [no.no_id]
        itens = [{"nome": n, "no_id": i} for n, i in zip(partes, ids)]
        if saida:
            # Secundário: só o trecho que difere do principal (", Concordância"
            # em vez de repetir "LÍNGUA PORTUGUESA ▸ ..."); a última parte fica.
            comum = 0
            for a, b in zip(saida[0]["partes"], itens[:-1]):
                if a["nome"] != b["nome"]:
                    break
                comum += 1
            itens = itens[comum:]
        saida.append({"no_id": no.no_id, "materia_id": no.materia_id, "partes": itens})
    return saida


templates.env.globals["nos_do_card"] = _nos_do_card


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


def _nao_encontrada(
    request: Request,
    titulo: str = "Página não encontrada",
    mensagem: str = "O endereço pode estar errado ou a página foi removida.",
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="nao_encontrada.html",
        status_code=404,
        context={"titulo": titulo, "mensagem": mensagem},
    )


@router.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    # Grade de matérias (5F.9/5F.7): mesma lista de /api/v1/materias.
    materias = estatisticas_servico.listar_materias()
    return templates.TemplateResponse(
        request=request, name="inicio.html", context={"materias": materias}
    )


def _filtros_da_query(
    usuario_id: int | None = Depends(auth.usuario_id_atual),
    # Tudo como lista de texto: o modelo descarta vazio e valor inválido
    # (`ano=` ou `cargo_numero=` como int dariam 422).
    banca: Annotated[list[str] | None, Query()] = None,
    orgao: Annotated[list[str] | None, Query()] = None,
    ano: Annotated[list[str] | None, Query()] = None,
    concurso: Annotated[list[str] | None, Query()] = None,
    cargo: Annotated[list[str] | None, Query()] = None,
    cargo_numero: Annotated[list[str] | None, Query()] = None,
    nivel: Annotated[list[str] | None, Query()] = None,
    tipo_conhecimento: Annotated[list[str] | None, Query()] = None,
    no_id: Annotated[list[str] | None, Query()] = None,
    texto: str | None = None,
    com: Annotated[list[str] | None, Query()] = None,
    anuladas: str = "incluir",
    fora_do_edital: str = "todos",
    utilizaveis: str = "so",
    historico: str = "todas",
) -> FiltroQuestoes:
    """Filtros da lista a partir da query string (rota `/questoes` e a
    recontagem `/questoes/facetas`). Valor estranho vira o padrão, sem 422."""
    if anuladas not in ("incluir", "excluir", "so"):
        anuladas = "incluir"
    if fora_do_edital not in ("todos", "sim", "nao"):
        fora_do_edital = "todos"
    if utilizaveis not in ("so", "todas"):
        utilizaveis = "so"
    if historico not in ("todas", "resolvidas", "nao_resolvidas", "certas", "erradas"):
        historico = "todas"
    # Link antigo (`concurso=X&cargo_numero=N`, ex.: da estatística) vira o
    # cargo `X:N` do filtro multisseleção.
    concursos = [c for c in concurso or [] if c]
    numeros = [n for n in cargo_numero or [] if n.strip().isdigit()]
    if len(concursos) == 1 and numeros:
        cargo = [*(cargo or []), *(f"{concursos[0]}:{n.strip()}" for n in numeros)]
        cargo_numero = []
    return FiltroQuestoes(
        banca=banca,
        orgao=orgao,
        ano=ano,
        concurso=concurso,
        cargo=cargo,
        cargo_numero=cargo_numero,
        nivel=nivel,
        tipo_conhecimento=tipo_conhecimento,
        no_id=no_id,
        texto=texto,
        com=com,
        anuladas=anuladas,
        fora_do_edital=fora_do_edital,
        utilizaveis=utilizaveis,
        # Sem login o filtro de histórico não aparece; link antigo vale "todas".
        historico=historico if usuario_id else "todas",
    )


def _eh_fragmento(request: Request) -> bool:
    # A restauração de histórico do HTMX também manda HX-Request, mas espera a
    # página inteira.
    return bool(
        request.headers.get("HX-Request")
        and not request.headers.get("HX-History-Restore-Request")
    )


@router.get("/questoes", response_class=HTMLResponse)
def index(
    request: Request,
    filtros: Annotated[FiltroQuestoes, Depends(_filtros_da_query)],
    usuario_id: int | None = Depends(auth.usuario_id_atual),
    pagina: int = 1,
    tamanho_pagina: int = 20,
):
    parcial = _eh_fragmento(request)
    # Palavra-chave que é um ID curto existente abre a própria questão (5H.4).
    chave = questoes_servico.chave_do_termo(filtros.texto)
    if chave:
        if parcial:
            # Submit do form pelo HTMX: ele segue o header e troca a página.
            return HTMLResponse("", headers={"HX-Redirect": _url_questao(chave)})
        return RedirectResponse(_url_questao(chave), status_code=303)

    pagina = max(pagina, 1)
    tamanho_pagina = min(max(tamanho_pagina, 1), 50)
    pagina_questoes = questoes_servico.listar_questoes(
        filtros, pagina, tamanho_pagina, usuario_id
    )

    if pagina > 1 and pagina > max(pagina_questoes.total_paginas, 1):
        params = [
            (k, v) for k, v in request.query_params.multi_items() if k != "pagina"
        ]
        params.append(("pagina", str(max(pagina_questoes.total_paginas, 1))))
        return RedirectResponse(f"/questoes?{urlencode(params)}", status_code=307)

    # Facetas sempre: o fragmento leva as contagens novas (OOB) para o painel.
    facetas = questoes_servico.obter_facetas(filtros, usuario_id)
    # Paginação com os filtros aplicados (a URL), não com o form: ele pode ter
    # mudanças pendentes, que só valem no botão Filtrar.
    query_aplicada = [
        (k, v) for k, v in request.query_params.multi_items() if k != "pagina"
    ]
    contexto = {
        "pagina_questoes": pagina_questoes,
        "filtros": filtros,
        "facetas": facetas,
        "chips": _chips(filtros, facetas),
        "extras": _filtros_extras(filtros),
        "dados_facetas": _dados_facetas(facetas),
        "materia_unica": _materia_unica(filtros, facetas),
        "query_aplicada": query_aplicada,
        "logado": usuario_id is not None,
        "parcial": parcial,
    }
    nome = "_lista_parcial.html" if parcial else "lista_questoes.html"
    resposta = templates.TemplateResponse(request=request, name=nome, context=contexto)
    resposta.headers["Vary"] = "HX-Request"
    return resposta


@router.get("/questoes/facetas", response_class=HTMLResponse)
def recontar_facetas(
    request: Request,
    filtros: Annotated[FiltroQuestoes, Depends(_filtros_da_query)],
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    """Só as contagens das facetas para o form ainda não aplicado (ao fechar
    um dropdown). O painel relê o `#dados-facetas` trocado por OOB."""
    facetas = questoes_servico.obter_facetas(filtros, usuario_id)
    return templates.TemplateResponse(
        request=request,
        name="_dados_facetas.html",
        context={"dados_facetas": _dados_facetas(facetas), "oob": True},
    )


def _url_pagina(query: list[tuple[str, str]], pagina: int) -> str:
    return "/questoes?" + urlencode([*query, ("pagina", str(pagina))])


templates.env.globals["url_pagina"] = _url_pagina


def _materia_unica(filtros: FiltroQuestoes, facetas) -> str | None:
    """Nome da matéria quando exatamente uma está marcada ("Sobre ...")."""
    marcados = set(filtros.no_id or [])
    nomes = [m.rotulo for m in facetas.materias if m.valor in marcados]
    if len(nomes) != 1:
        return None
    # Nome todo em maiúsculas ("LÍNGUA PORTUGUESA") vira minúsculas, como no
    # Gran; nome já com caixa mista fica como está (siglas).
    return nomes[0].lower() if nomes[0].isupper() else nomes[0]


# Filtros aceitos na URL sem controle no painel (link antigo, estatística,
# opções que saíram da UI na 5H.3): seguem no form como hidden e viram chip.
_ROTULO_EXTRA = {
    ("anuladas", "so"): "Só anuladas",
    ("fora_do_edital", "sim"): "Só fora do edital",
    ("utilizaveis", "todas"): "Itens: todos (inclui ilegíveis)",
    ("historico", "resolvidas"): "Histórico: só resolvidas",
    ("historico", "certas"): "Histórico: acertei",
}


def _filtros_extras(filtros: FiltroQuestoes) -> list[dict]:
    extras = [
        {"nome": "cargo_numero", "valor": str(n), "rotulo": f"Cargo nº: {n}"}
        for n in filtros.cargo_numero or []
    ]
    for campo in ("anuladas", "fora_do_edital", "utilizaveis", "historico"):
        valor = getattr(filtros, campo)
        rotulo = _ROTULO_EXTRA.get((campo, valor))
        if rotulo:
            extras.append({"nome": campo, "valor": valor, "rotulo": rotulo})
    return extras


def _dados_facetas(facetas) -> dict[str, list[dict]]:
    """Facetas no formato do painel (JSON lido pelo Alpine, nunca interpolado)."""

    def simples(lista):
        return [
            {"valor": str(f.valor), "rotulo": f.rotulo, "total": f.total} for f in lista
        ]

    def nos(lista):
        return [
            {
                "valor": n.valor,
                "rotulo": n.rotulo,
                "caminho": n.caminho,
                "total": n.total,
            }
            for n in lista
        ]

    return {
        "orgao": simples(facetas.orgaos),
        "ano": simples(facetas.anos),
        "concurso": simples(facetas.concursos),
        "cargo": [
            {
                "valor": c.valor,
                "rotulo": f"{c.cargo_numero} — {c.cargo} ({rotulo_nivel(c.nivel)})",
                "caminho": rotulo_concurso(c.concurso),
                "total": c.total,
            }
            for c in facetas.cargos
        ],
        "nivel": simples(facetas.niveis),
        "tipo_conhecimento": simples(facetas.tipos_conhecimento),
        "banca": simples(facetas.bancas),
        "materia": nos(facetas.materias),
        "assunto": nos(facetas.assuntos),
        "subassunto": nos(facetas.subassuntos),
        "anuladas": [
            {
                "valor": "so" if f.valor else "excluir",
                "rotulo": f.rotulo,
                "total": f.total,
            }
            for f in facetas.anuladas
        ],
    }


# Mesmos rótulos dos chips do painel (Alpine) e dos extras.
_ROTULO_ANULADAS = {"excluir": "Excluir: anuladas", "so": "Só anuladas"}
_ROTULO_HISTORICO = {
    "resolvidas": "Histórico: só resolvidas",
    "nao_resolvidas": "Excluir: já resolvidas",
    "certas": "Histórico: acertei",
    "erradas": "Com: que errei",
}
_ROTULO_COM = {"texto_base": "Com: texto associado", "figuras": "Com: figuras"}


def _chips(filtros: FiltroQuestoes, facetas) -> list[dict]:
    """Chips dos filtros ativos, cada um com a URL da lista sem aquele valor."""
    pares: list[tuple[str, str]] = []
    for campo, valor in filtros.model_dump(exclude_defaults=True).items():
        for v in valor if isinstance(valor, list) else [valor]:
            pares.append((campo, str(v)))

    rotulos: dict[tuple[str, str], str] = {}
    for campo, lista in [
        ("banca", facetas.bancas),
        ("orgao", facetas.orgaos),
        ("ano", facetas.anos),
        ("concurso", facetas.concursos),
        ("nivel", facetas.niveis),
        ("tipo_conhecimento", facetas.tipos_conhecimento),
    ]:
        for f in lista:
            rotulos[(campo, str(f.valor))] = f.rotulo
    for c in facetas.cargos:
        rotulos[("cargo", c.valor)] = (
            f"{rotulo_concurso(c.concurso)} · {c.cargo_numero} — {c.cargo}"
        )
    for n in [*facetas.materias, *facetas.assuntos, *facetas.subassuntos]:
        rotulos[("no_id", n.valor)] = n.caminho
    prefixos = {
        "banca": "Banca",
        "orgao": "Órgão",
        "ano": "Ano",
        "cargo_numero": "Cargo nº",
        "nivel": "Nível",
        "tipo_conhecimento": "Conhecimento",
        "texto": "Palavra-chave",
    }

    chips = []
    for i, (campo, valor) in enumerate(pares):
        resto = [p for j, p in enumerate(pares) if j != i]
        if campo == "concurso":
            # Os cargos do concurso (e o número antigo) saem junto.
            resto = [
                p
                for p in resto
                if p[0] != "cargo_numero"
                and not (p[0] == "cargo" and p[1].startswith(valor + ":"))
            ]
        if campo == "anuladas":
            texto = _ROTULO_ANULADAS.get(valor, valor)
        elif campo == "historico":
            texto = _ROTULO_HISTORICO.get(valor, valor)
        elif campo == "com":
            texto = _ROTULO_COM.get(valor, valor)
        elif campo == "fora_do_edital":
            texto = {"nao": "Excluir: fora do edital"}.get(valor, "Só fora do edital")
        elif campo == "utilizaveis":
            texto = _ROTULO_EXTRA[("utilizaveis", "todas")]
        elif campo in ("concurso", "cargo", "no_id"):
            texto = rotulos.get((campo, valor), valor)
        else:
            texto = (
                f"{prefixos.get(campo, campo)}: {rotulos.get((campo, valor), valor)}"
            )
        url = "/questoes" + (f"?{urlencode(resto)}" if resto else "")
        chips.append({"rotulo": texto, "url": url})
    return chips


@router.post(
    "/q/correcao",
    response_class=HTMLResponse,
    dependencies=[Depends(auth.verificar_csrf)],
)
def corrigir_questao(
    request: Request,
    chave: str = Form(...),
    resposta: str | None = Form(None),
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    if resposta not in ("C", "E"):
        # Sem marcação (ou valor estranho): o HTMX troca o form por ele mesmo
        # com o aviso, em vez de um 422 que ele não mostraria.
        return templates.TemplateResponse(
            request=request,
            name="_form_resposta.html",
            context={
                "chave": chave,
                "aviso": "Marque Certo ou Errado antes de responder.",
            },
        )
    resultado = contas_servico.responder(chave, resposta, usuario_id)
    if not resultado:
        return _nao_encontrada(
            request,
            titulo="Questão não encontrada",
            mensagem="O endereço pode estar errado ou a questão foi removida.",
        )
    return templates.TemplateResponse(
        request=request,
        name="_correcao.html",
        context={"resultado": resultado, "logado": usuario_id is not None},
    )


@router.get("/q/{codigo}", response_class=HTMLResponse)
def questao_por_codigo(request: Request, codigo: str):
    """Atalho do ID curto (`Q` + 8 hex) para a URL canônica da questão."""
    chave = questoes_servico.chave_por_codigo(codigo)
    if not chave:
        return _nao_encontrada(
            request,
            titulo="Questão não encontrada",
            mensagem="O código pode estar errado ou a questão foi removida.",
        )
    return RedirectResponse(_url_questao(chave), status_code=301)


@router.get("/q/{concurso}/{caderno}/{numero}/anexos", response_class=HTMLResponse)
def anexos_questao(request: Request, concurso: str, caderno: str, numero: int):
    """Texto-base e figuras, carregados sob demanda pelo card da lista."""
    questao = questoes_servico.obter_questao_por_chave(f"{concurso}|{caderno}|{numero}")
    if not questao:
        return _nao_encontrada(
            request,
            titulo="Questão não encontrada",
            mensagem="O endereço pode estar errado ou a questão foi removida.",
        )
    return templates.TemplateResponse(
        request=request, name="_anexos.html", context={"questao": questao}
    )


@router.get("/q/{concurso}/{caderno}/{numero}/parecidas", response_class=HTMLResponse)
def parecidas_questao(request: Request, concurso: str, caderno: str, numero: int):
    """Questões parecidas, carregadas sob demanda pelo card da lista."""
    parecidas = questoes_servico.parecidas(f"{concurso}|{caderno}|{numero}")
    if parecidas is None:
        return _nao_encontrada(
            request,
            titulo="Questão não encontrada",
            mensagem="O endereço pode estar errado ou a questão foi removida.",
        )
    return templates.TemplateResponse(
        request=request, name="_parecidas.html", context={"parecidas": parecidas}
    )


@router.get("/q/{concurso}/{caderno}/{numero}", response_class=HTMLResponse)
def detalhe_questao(request: Request, concurso: str, caderno: str, numero: int):
    chave = f"{concurso}|{caderno}|{numero}"
    questao = questoes_servico.obter_questao_por_chave(chave)
    if not questao:
        return _nao_encontrada(
            request,
            titulo="Questão não encontrada",
            mensagem="O endereço pode estar errado ou a questão foi removida.",
        )
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
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    alvo = contas_servico.obter_concurso_alvo(usuario_id) if usuario_id else None
    if alvo and concurso is None and cargo_numero is None:
        # Logado e sem escolha na URL: abre no concurso-alvo salvo (5F.8).
        concurso, cargo_numero = alvo.concurso, str(alvo.cargo_numero)
    filtros = _filtro_estatistica(concurso, cargo_numero, None, None)
    resultado = plano = None
    if filtros.concurso and filtros.cargo_numero:
        resultado = estatisticas_servico.edital_vs_prova(
            filtros.concurso, filtros.cargo_numero
        )
        if usuario_id and resultado.peso_materias:
            plano = contas_servico.plano_estudo(
                usuario_id, filtros.concurso, filtros.cargo_numero
            )
    return templates.TemplateResponse(
        request=request,
        name="edital_vs_prova.html",
        context={
            "aba": "edital_vs_prova",
            "filtros": filtros,
            "resultado": resultado,
            "cargos": estatisticas_servico.cargos(),
            "alvo": alvo,
            "plano": plano,
            "logado": usuario_id is not None,
        },
    )


@router.post("/estatisticas/concurso-alvo", dependencies=[Depends(auth.verificar_csrf)])
def salvar_concurso_alvo(
    request: Request,
    concurso: str = Form(...),
    cargo_numero: str = Form(""),
    usuario_id: int | None = Depends(auth.usuario_id_atual),
):
    # Cargo como str: select vazio chega como "" (int daria 422, ver §7).
    if usuario_id is None:
        return RedirectResponse("/entrar?voltar=/estatisticas/edital-vs-prova", 303)
    if not cargo_numero.isdigit():
        return _nao_encontrada(
            request,
            titulo="Cargo não encontrado",
            mensagem="O cargo informado não existe ou não tem edital nem prova na base.",
        )
    alvo = ConcursoAlvo(concurso=concurso, cargo_numero=int(cargo_numero))
    try:
        contas_servico.salvar_concurso_alvo(usuario_id, alvo)
    except contas_servico.ConcursoInexistente:
        return _nao_encontrada(
            request,
            titulo="Cargo não encontrado",
            mensagem="O cargo informado não existe ou não tem edital nem prova na base.",
        )
    query = urlencode({"concurso": alvo.concurso, "cargo_numero": alvo.cargo_numero})
    return RedirectResponse(f"/estatisticas/edital-vs-prova?{query}", status_code=303)


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
        return _nao_encontrada(
            request,
            titulo="Simulado não encontrado",
            mensagem="O simulado não existe ou não pertence à sua conta.",
        )
    return RedirectResponse(f"/simulado/{simulado_id}", status_code=303)


@router.get("/simulado/prova", response_class=HTMLResponse)
def simulado_prova_avulsa(request: Request, concurso: str, cargo_numero: int):
    prova = simulados_servico.montar_prova(concurso, cargo_numero)
    if not prova:
        return _nao_encontrada(
            request,
            titulo="Prova não encontrada",
            mensagem="Não há prova na base para esse concurso e cargo.",
        )
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
    pagina = max(pagina, 1)
    if usuario_id is None:
        voltar = f"/simulado/{simulado_id}/revisar?situacao={situacao}&pagina={pagina}"
        return RedirectResponse(
            "/entrar?" + urlencode({"voltar": voltar}), status_code=303
        )
    try:
        pagina_questoes = simulados_servico.questoes_por_situacao(
            simulado_id, usuario_id, situacao, pagina, 20
        )
    except simulados_servico.SimuladoAberto:
        return RedirectResponse(f"/simulado/{simulado_id}", status_code=303)
    if pagina_questoes is None:
        return _nao_encontrada(
            request,
            titulo="Simulado não encontrado",
            mensagem="O simulado não existe ou não pertence à sua conta.",
        )
    if pagina > 1 and pagina > max(pagina_questoes.total_paginas, 1):
        destino = urlencode(
            {"situacao": situacao, "pagina": max(pagina_questoes.total_paginas, 1)}
        )
        return RedirectResponse(
            f"/simulado/{simulado_id}/revisar?{destino}", status_code=307
        )
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
        return _nao_encontrada(
            request,
            titulo="Simulado não encontrado",
            mensagem="O simulado não existe ou não pertence à sua conta.",
        )
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
        return _nao_encontrada(
            request,
            titulo="Prova não encontrada",
            mensagem="Não há prova na base para esse concurso e cargo.",
        )
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
                return _nao_encontrada(
                    request,
                    titulo="Simulado não encontrado",
                    mensagem="O simulado não existe, já foi encerrado ou não pertence à sua conta.",
                )
        except simulados_servico.SimuladoJaEncerrado:
            pass  # reenvio do form: mostra o resultado já gravado
        return RedirectResponse(f"/simulado/{simulado_id}", status_code=303)
    cargo = form.get("cargo_numero", "")
    resultado = cargo.isdigit() and simulados_servico.corrigir_avulso(
        form.get("concurso", ""), int(cargo), respostas
    )
    if not resultado:
        return _nao_encontrada(
            request,
            titulo="Simulado não encontrado",
            mensagem="O simulado não existe ou não pertence à sua conta.",
        )
    return templates.TemplateResponse(
        request=request,
        name="simulado_resultado.html",
        context={"resultado": resultado},
    )


# -- Contas (5F.3) --
@router_auth.get(
    "/entrar",
    summary="Inicia o login com Google",
    description=(
        "Redireciona para o consentimento do Google OAuth. `voltar` é o caminho "
        "local para onde o usuário volta depois do login. Sem login configurado, "
        "redireciona para `/`."
    ),
    status_code=303,
    response_class=RedirectResponse,
    responses={
        **_303,
        302: {"description": "Redireciona para o consentimento do Google."},
    },
)
async def entrar(
    request: Request,
    voltar: str | None = Query(
        None, description="Caminho local de retorno (ex.: `/conta`)."
    ),
):
    if not auth.login_habilitado():
        return RedirectResponse("/", status_code=303)
    request.session["voltar"] = auth.destino_seguro(voltar)
    return await auth.oauth.google.authorize_redirect(
        request, str(request.url_for("auth_google"))
    )


@router_auth.get(
    "/auth/google",
    name="auth_google",
    summary="Retorno do Google OAuth",
    description=(
        "Callback chamado pelo Google: cria ou acha o usuário, abre a sessão "
        "(cookie `sessao`) e redireciona para o `voltar` do `/entrar`. Falha no "
        "OAuth ou e-mail não verificado redireciona para `/` sem login."
    ),
    status_code=303,
    response_class=RedirectResponse,
    responses=_303,
)
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


@router_auth.post(
    "/sair",
    summary="Encerra a sessão",
    description="Limpa o cookie de sessão e redireciona para `/`. Exige CSRF.",
    dependencies=[Depends(auth.verificar_csrf)],
    status_code=303,
    response_class=RedirectResponse,
    responses={**_303, **R403},
)
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
        return _nao_encontrada(
            request,
            titulo="Matéria não encontrada",
            mensagem="O endereço pode estar errado ou a matéria foi removida.",
        )
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
