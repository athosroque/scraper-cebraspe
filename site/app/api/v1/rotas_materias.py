"""Disciplinas e busca na árvore (5F.7)."""

from fastapi import APIRouter, HTTPException, Path, Query

from app.modelos import FiltroEstatistica, MateriaDetalhe, MateriaResumo, ResultadoBusca
from app.servicos import estatisticas_servico

router = APIRouter(tags=["Disciplinas"])

_RESPOSTA_404 = {
    404: {"description": "O id não é uma disciplina ativa da árvore mestre."}
}
_RESPOSTA_422 = {422: {"description": "Parâmetro de consulta inválido."}}


@router.get(
    "/materias",
    response_model=list[MateriaResumo],
    summary="Lista as disciplinas com o volume de questões",
    description=(
        "Disciplinas da árvore mestre ativa que têm questão objetiva utilizável, com o "
        "total de questões válidas distintas (a contagem sobe a árvore, anuladas "
        "fora) e o % de incidência: média, entre as provas (concurso × cargo), da "
        "fatia da prova que é da disciplina. Maior incidência primeiro."
    ),
)
def listar_materias():
    return estatisticas_servico.listar_materias()


@router.get(
    "/materias/{materia_id}",
    response_model=MateriaDetalhe,
    summary="Resumo de uma disciplina",
    description=(
        "Resumo da disciplina e os subassuntos que mais caem (`fn_prova_cobra`, "
        "pelo % médio na prova por concurso × cargo) no recorte de concurso, cargo "
        "e nível. O cargo só vale junto com o concurso."
    ),
    responses={**_RESPOSTA_404, **_RESPOSTA_422},
)
def detalhe_materia(
    materia_id: str = Path(
        description="ID do nó da disciplina na árvore mestre (ex.: `M-0f9a364d06`)."
    ),
    concurso: str | None = Query(
        None, description="Slug do concurso (ex.: `PF_25_ADM`)."
    ),
    cargo_numero: int | None = Query(
        None, description="Número do cargo no edital. Use junto com `concurso`."
    ),
    nivel: str | None = Query(None, description="`superior` ou `medio`."),
    limite: int = Query(15, ge=1, le=200, description="Tamanho do top de subassuntos."),
):
    filtros = FiltroEstatistica(
        concurso=concurso,
        cargo_numero=cargo_numero if concurso else None,
        nivel=nivel,
    )
    detalhe = estatisticas_servico.detalhe_materia(materia_id, filtros, limite)
    if detalhe is None:
        raise HTTPException(status_code=404, detail="Disciplina não encontrada")
    return detalhe


@router.get(
    "/busca",
    response_model=list[ResultadoBusca],
    summary="Busca nós da árvore por nome",
    description=(
        "Nós ativos (disciplina, assunto, subassunto) cujo nome contém o termo, sem "
        "acento e sem caixa (`lingua` acha `LÍNGUA PORTUGUESA`). Começo do nome "
        "primeiro, depois disciplina → assunto → subassunto. Máximo de 20."
    ),
    responses=_RESPOSTA_422,
)
def buscar(
    q: str = Query(..., min_length=2, max_length=100, description="Termo de busca."),
):
    return estatisticas_servico.buscar_nos(q)
