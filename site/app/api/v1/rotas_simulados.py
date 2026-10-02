"""Simulado (5F.5): a prova sem gabarito e a correção no padrão CEBRASPE."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import exigir_usuario_id, verificar_csrf
from app.modelos import (
    ProvaSimulado,
    RespostasSimulado,
    ResultadoSimulado,
    SimuladoEntrada,
    SimuladoInicio,
    SimuladoResumo,
)
from app.servicos import simulados_servico

router = APIRouter(prefix="/simulados", tags=["Simulado"])

_401 = {401: {"description": "Login necessário"}}
_403 = {403: {"description": "Token CSRF inválido (header `X-CSRFToken`)"}}
_404 = {404: {"description": "Cargo sem prova ou simulado não encontrado"}}


@router.get(
    "/prova",
    response_model=ProvaSimulado,
    summary="Prova de um cargo para o simulado (sem gabarito)",
    description=(
        "Itens na ordem da prova (básico, depois específico; caderno e número) e "
        "as discursivas sem o padrão de resposta."
    ),
    responses=_404,
)
def prova(concurso: str = Query(...), cargo_numero: int = Query(...)):
    resultado = simulados_servico.montar_prova(concurso, cargo_numero)
    if not resultado:
        raise HTTPException(status_code=404, detail="Cargo sem prova")
    return resultado


@router.post(
    "/correcao",
    response_model=ResultadoSimulado,
    summary="Corrige um simulado sem gravar",
    description="Certo +1, errado −1, branco 0; anulada fica fora da nota e do máximo.",
    dependencies=[Depends(verificar_csrf)],
    responses={**_404, **_403},
)
def corrigir(entrada: SimuladoEntrada):
    resultado = simulados_servico.corrigir_avulso(
        entrada.concurso, entrada.cargo_numero, entrada.respostas
    )
    if not resultado:
        raise HTTPException(status_code=404, detail="Cargo sem prova")
    return resultado


@router.get(
    "",
    response_model=list[SimuladoResumo],
    summary="Meus simulados",
    responses=_401,
)
def listar(usuario_id: int = Depends(exigir_usuario_id)):
    return simulados_servico.listar(usuario_id)


@router.post(
    "",
    response_model=SimuladoResumo,
    status_code=201,
    summary="Inicia um simulado gravado (o início vale para o cronômetro)",
    dependencies=[Depends(verificar_csrf)],
    responses={**_401, **_403, **_404},
)
def iniciar(entrada: SimuladoInicio, usuario_id: int = Depends(exigir_usuario_id)):
    simulado_id = simulados_servico.iniciar(
        usuario_id, entrada.concurso, entrada.cargo_numero
    )
    if simulado_id is None:
        raise HTTPException(status_code=404, detail="Cargo sem prova")
    return simulados_servico.obter_simulado(simulado_id, usuario_id)


@router.post(
    "/{simulado_id}/correcao",
    response_model=ResultadoSimulado,
    summary="Encerra e corrige um simulado gravado",
    description="Grava nota, fim e respostas. Só encerra uma vez (409 depois).",
    dependencies=[Depends(verificar_csrf)],
    responses={**_401, **_403, **_404, 409: {"description": "Simulado já encerrado"}},
)
def encerrar(
    simulado_id: int,
    entrada: RespostasSimulado,
    usuario_id: int = Depends(exigir_usuario_id),
):
    try:
        resultado = simulados_servico.encerrar(
            simulado_id, usuario_id, entrada.respostas
        )
    except simulados_servico.SimuladoJaEncerrado:
        raise HTTPException(status_code=409, detail="Simulado já encerrado")
    if not resultado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    return resultado


@router.get(
    "/{simulado_id}",
    response_model=ResultadoSimulado,
    summary="Resultado de um simulado encerrado",
    responses={**_401, **_404},
)
def resultado(simulado_id: int, usuario_id: int = Depends(exigir_usuario_id)):
    resultado = simulados_servico.obter_resultado(simulado_id, usuario_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado ou aberto")
    return resultado
