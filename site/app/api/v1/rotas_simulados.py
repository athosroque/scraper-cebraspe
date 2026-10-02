"""Simulado (5F.5): a prova sem gabarito e a correção no padrão CEBRASPE."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.v1.respostas_comuns import R401, R403, r404, r409
from app.auth import exigir_usuario_id, verificar_csrf
from app.modelos import (
    PaginaQuestoes,
    ProvaSimulado,
    RespostasSimulado,
    ResultadoSimulado,
    SimuladoEntrada,
    SimuladoInicio,
    SimuladoResumo,
)
from app.servicos import simulados_servico

router = APIRouter(prefix="/simulados", tags=["Simulado"])

_401 = R401
_403 = R403
_ID = Path(description="Id do simulado (devolvido no início).")
_404 = r404("Cargo sem prova ou simulado não encontrado.")


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
def prova(
    concurso: str = Query(..., description="Slug do concurso (ex.: `PF_25_ADM`)."),
    cargo_numero: int = Query(..., description="Número do cargo no edital."),
):
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
    description="Simulados gravados do usuário logado, do mais recente ao mais antigo.",
    responses=_401,
)
def listar(usuario_id: int = Depends(exigir_usuario_id)):
    return simulados_servico.listar(usuario_id)


@router.post(
    "",
    response_model=SimuladoResumo,
    status_code=201,
    summary="Inicia um simulado gravado (o início vale para o cronômetro)",
    description=(
        "Cria o simulado do usuário logado para o cargo e devolve o resumo com o "
        "`id`. A prova vem de `GET /simulados/prova`; o encerramento é "
        "`POST /simulados/{simulado_id}/correcao`."
    ),
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
    responses={**_401, **_403, **_404, **r409("Simulado já encerrado.")},
)
def encerrar(
    entrada: RespostasSimulado,
    simulado_id: int = _ID,
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
    "/{simulado_id}/questoes",
    response_model=PaginaQuestoes,
    summary="Questões do simulado por situação (para revisar)",
    description=(
        "Lista paginada (mesmo formato de `GET /api/v1/questoes`) das questões "
        "de um simulado encerrado que ficaram com a situação pedida: `errado` "
        "(resposta diferente do gabarito) ou `branco` (sem resposta). A "
        "situação usa o gabarito atual, como o resultado. Anuladas nunca entram."
    ),
    responses={
        401: {"description": "Login necessário"},
        404: {"description": "Simulado não existe ou não é do usuário"},
        409: {"description": "Simulado ainda não encerrado"},
    },
)
def questoes(
    simulado_id: int = _ID,
    situacao: Literal["errado", "branco"] = Query(
        "errado", description="Situação do item no simulado: `errado` ou `branco`."
    ),
    pagina: int = Query(1, ge=1, description="Página (começa em 1)."),
    tamanho_pagina: int = Query(
        20, ge=1, le=50, description="Itens por página (máximo 50)."
    ),
    usuario_id: int = Depends(exigir_usuario_id),
):
    """Questões erradas ou em branco de um simulado encerrado do usuário."""
    try:
        pagina_questoes = simulados_servico.questoes_por_situacao(
            simulado_id, usuario_id, situacao, pagina, tamanho_pagina
        )
    except simulados_servico.SimuladoAberto:
        raise HTTPException(status_code=409, detail="Simulado ainda não encerrado")
    if pagina_questoes is None:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")
    return pagina_questoes


@router.get(
    "/{simulado_id}",
    response_model=ResultadoSimulado,
    summary="Resultado de um simulado encerrado",
    description=(
        "Placar, correção por item e padrões de resposta das discursivas. Só o "
        "dono vê; simulado aberto ou de outro usuário dá 404."
    ),
    responses={**_401, **_404},
)
def resultado(simulado_id: int = _ID, usuario_id: int = Depends(exigir_usuario_id)):
    resultado = simulados_servico.obter_resultado(simulado_id, usuario_id)
    if not resultado:
        raise HTTPException(status_code=404, detail="Simulado não encontrado ou aberto")
    return resultado
