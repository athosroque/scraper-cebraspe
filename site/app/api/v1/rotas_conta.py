"""Conta e histórico (5F.3). A sessão vem do cookie do login com Google."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.v1.respostas_comuns import R401, R403, r404
from app.auth import exigir_usuario_id, usuario_id_atual, verificar_csrf
from app.modelos import (
    FiltroQuestoes,
    NoDesempenho,
    RespostaEntrada,
    RespostaResultado,
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
    description="Dados da conta da sessão atual (cookie `sessao`). Sem login: 401.",
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
