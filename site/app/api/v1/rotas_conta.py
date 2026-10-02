"""Conta e histórico (5F.3). A sessão vem do cookie do login com Google."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.v1.respostas_comuns import R401, R403, r404
from app.auth import exigir_usuario_id, usuario_id_atual, verificar_csrf
from app.modelos import (
    ConcursoAlvo,
    FiltroQuestoes,
    NoDesempenho,
    PlanoEstudo,
    Prioridade,
    RespostaEntrada,
    RespostaResultado,
    ResumoConta,
    Usuario,
)
from app.servicos import contas_servico

router = APIRouter(tags=["Conta"])

_401 = R401
_403 = R403


@router.post(
    "/respostas",
    response_model=RespostaResultado,
    summary="Corrige uma resposta (e grava no histórico, com login)",
    description="Sem login, só corrige. Questão anulada nunca é gravada.",
    dependencies=[Depends(verificar_csrf)],
    responses={**r404("Questão não encontrada."), **_403},
)
def responder(entrada: RespostaEntrada, request: Request):
    resultado = contas_servico.responder(
        entrada.questao_chave, entrada.resposta, usuario_id_atual(request)
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return resultado


@router.get(
    "/eu",
    response_model=Usuario,
    summary="Usuário logado",
    description=(
        "Dados da conta da sessão atual (cookie `sessao`), com o concurso-alvo "
        "salvo (nulo se não houver). Sem login: 401."
    ),
    responses=_401,
)
def eu(usuario_id: int = Depends(exigir_usuario_id)):
    usuario = contas_servico.obter_usuario(usuario_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Login necessário")
    return usuario


@router.delete(
    "/eu",
    status_code=204,
    summary="Apaga a conta e todo o histórico",
    description=(
        "Remove o usuário, as respostas e os simulados (cascata) e encerra a "
        "sessão. Irreversível."
    ),
    dependencies=[Depends(verificar_csrf)],
    responses={**_401, **_403},
)
def apagar_conta(request: Request, usuario_id: int = Depends(exigir_usuario_id)):
    contas_servico.apagar_conta(usuario_id)
    request.session.clear()
    return Response(status_code=204)


@router.get(
    "/eu/resumo",
    response_model=ResumoConta,
    summary="Resumo da conta (KPIs)",
    description=(
        "Resolvidas, certas, erradas e acerto pela resposta mais recente de cada "
        "questão (fora de simulado); nota líquida na regra CEBRASPE (certas − "
        "erradas); erradas pendentes (caderno de erros) e dias seguidos com "
        "resposta no fuso America/Sao_Paulo."
    ),
    responses={401: {"description": "Login necessário"}},
)
def resumo_conta(usuario_id: int = Depends(exigir_usuario_id)):
    """KPIs do painel "Meu desempenho"."""
    return contas_servico.resumo_completo(usuario_id)


@router.get(
    "/eu/prioridades",
    response_model=list[Prioridade],
    summary="O que estudar agora",
    description=(
        "Subassuntos com pelo menos 2 questões respondidas, ordenados por "
        "incidência na prova (`fn_prova_cobra`, % médio por concurso) × taxa de "
        "erro do usuário. Respostas e incidência são lidas em separado e "
        "cruzadas no serviço."
    ),
    responses={401: {"description": "Login necessário"}},
)
def prioridades(
    usuario_id: int = Depends(exigir_usuario_id),
    limite: int = Query(10, ge=1, le=50, description="Máximo de subassuntos."),
):
    """Ranking de subassuntos para revisar primeiro."""
    return contas_servico.prioridades(usuario_id, limite)


@router.get(
    "/eu/desempenho",
    response_model=list[NoDesempenho],
    summary="Desempenho por nó da árvore",
    description=(
        "Acertos sobre a resposta mais recente de cada questão. A questão sobe a "
        "árvore e conta uma vez por nó (regra da 5E); anuladas ficam de fora. "
        "Aceita os mesmos filtros da listagem."
    ),
    responses=_401,
)
def desempenho(
    usuario_id: int = Depends(exigir_usuario_id),
    orgao: str | None = Query(None, description="Órgão (ex.: `PF`)."),
    ano: int | None = Query(None, description="Ano do concurso."),
    concurso: str | None = Query(
        None, description="Slug do concurso (ex.: `PF_25_ADM`)."
    ),
    cargo_numero: int | None = Query(
        None, description="Número do cargo no edital. Use junto com `concurso`."
    ),
    nivel: str | None = Query(None, description="`superior` ou `medio`."),
    tipo_conhecimento: str | None = Query(
        None, description="`basico` ou `especifico`."
    ),
    no_id: str | None = Query(
        None, description="Nó da árvore; inclui os descendentes."
    ),
    fora_do_edital: Literal["todos", "sim", "nao"] = Query(
        "todos", description="Recorte por questão fora do edital do cargo."
    ),
):
    filtros = FiltroQuestoes(
        orgao=orgao,
        ano=ano,
        concurso=concurso,
        cargo_numero=cargo_numero,
        nivel=nivel,
        tipo_conhecimento=tipo_conhecimento,
        no_id=no_id,
        fora_do_edital=fora_do_edital,
    )
    return contas_servico.desempenho(usuario_id, filtros)


# -- Plano de estudo e concurso-alvo (5F.8) --
_404_CONCURSO = {404: {"description": "Concurso ou cargo sem prova na base"}}


@router.get(
    "/eu/concurso-alvo",
    response_model=ConcursoAlvo | None,
    summary="Concurso-alvo salvo",
    description="Concurso e cargo que o usuário estuda; `null` se nada foi salvo.",
    responses=_401,
)
def obter_concurso_alvo(usuario_id: int = Depends(exigir_usuario_id)):
    """Lê o concurso-alvo da conta logada."""
    return contas_servico.obter_concurso_alvo(usuario_id)


@router.put(
    "/eu/concurso-alvo",
    response_model=ConcursoAlvo,
    summary="Salva o concurso-alvo",
    description=(
        "Grava concurso e cargo na conta. O par precisa existir na base "
        "(cargo com prova); senão, 404. Exige o header `X-CSRFToken`."
    ),
    dependencies=[Depends(verificar_csrf)],
    responses={**_401, **_403, **_404_CONCURSO},
)
def salvar_concurso_alvo(
    alvo: ConcursoAlvo, usuario_id: int = Depends(exigir_usuario_id)
):
    """Substitui o concurso-alvo da conta logada."""
    try:
        gravou = contas_servico.salvar_concurso_alvo(usuario_id, alvo)
    except contas_servico.ConcursoInexistente:
        raise HTTPException(status_code=404, detail="Concurso ou cargo não encontrado")
    if not gravou:
        raise HTTPException(status_code=401, detail="Login necessário")
    return alvo


@router.get(
    "/eu/plano",
    response_model=PlanoEstudo,
    summary="Plano de estudo do cargo",
    description=(
        "Matérias do cargo ordenadas por `prioridade` = peso da matéria na prova "
        "(`vw_peso_materia_cargo`) × (1 − acerto do usuário na matéria). O acerto "
        "usa a resposta mais recente de cada questão, de qualquer prova; sem "
        "respostas na matéria, o acerto é 0 e a prioridade é o próprio peso."
    ),
    responses={**_401, **_404_CONCURSO},
)
def plano(
    usuario_id: int = Depends(exigir_usuario_id),
    concurso: str = Query(description="Slug do concurso.", examples=["PF_25_ADM"]),
    cargo_numero: int = Query(ge=1, description="Número do cargo.", examples=[1]),
):
    """Monta o plano de estudo da conta logada para um cargo."""
    try:
        return contas_servico.plano_estudo(usuario_id, concurso, cargo_numero)
    except contas_servico.ConcursoInexistente:
        raise HTTPException(status_code=404, detail="Concurso ou cargo não encontrado")
