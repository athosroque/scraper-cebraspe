"""Conta e histórico (5F.3). A sessão vem do cookie do login com Google."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

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

_401 = {401: {"description": "Login necessário"}}
_403 = {403: {"description": "Token CSRF inválido (header `X-CSRFToken`)"}}


@router.post(
    "/respostas",
    response_model=RespostaResultado,
    summary="Corrige uma resposta (e grava no histórico, com login)",
    description="Sem login, só corrige. Questão anulada nunca é gravada.",
    dependencies=[Depends(verificar_csrf)],
    responses={404: {"description": "Questão não encontrada"}, **_403},
)
def responder(entrada: RespostaEntrada, request: Request):
    resultado = contas_servico.responder(
        entrada.questao_chave, entrada.resposta, usuario_id_atual(request)
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return resultado


@router.get("/eu", response_model=Usuario, summary="Usuário logado", responses=_401)
def eu(usuario_id: int = Depends(exigir_usuario_id)):
    usuario = contas_servico.obter_usuario(usuario_id)
    if not usuario:
        raise HTTPException(status_code=401, detail="Login necessário")
    return usuario


@router.delete(
    "/eu",
    status_code=204,
    summary="Apaga a conta e todo o histórico",
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
    orgao: str | None = Query(None),
    ano: int | None = Query(None),
    concurso: str | None = Query(None),
    cargo_numero: int | None = Query(None),
    nivel: str | None = Query(None),
    tipo_conhecimento: str | None = Query(None),
    no_id: str | None = Query(None),
    fora_do_edital: Literal["todos", "sim", "nao"] = Query("todos"),
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
