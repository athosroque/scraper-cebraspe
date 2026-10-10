from fastapi import APIRouter, HTTPException, Query

from app.api.v1.respostas_comuns import r404
from app.modelos import (
    EditalVsProva,
    FiltroEstatistica,
    LinhaEditalCobra,
    LinhaProvaCobra,
    NivelAlvo,
)
from app.servicos import estatisticas_servico

router = APIRouter(prefix="/estatisticas", tags=["Estatísticas"])


_CONCURSO = Query(None, description="Slug do concurso (ex.: `PF_25_ADM`).")
_CARGO = Query(None, description="Número do cargo no edital. Use junto com `concurso`.")
_NIVEL = Query(None, description="`superior` ou `medio`.")
_TIPO = Query(None, description="`basico` ou `especifico`.")


def _filtros(concurso, cargo_numero, nivel, tipo_conhecimento) -> FiltroEstatistica:
    return FiltroEstatistica(
        concurso=concurso,
        cargo_numero=cargo_numero,
        nivel=nivel,
        tipo_conhecimento=tipo_conhecimento,
    )


_NIVEL_ALVO = Query("subassunto", description="Nível da árvore do ranking.")
_MATERIA = Query(None, description="Restringe o ranking a uma disciplina (id do nó).")
_LIMITE = Query(20, ge=1, le=200, description="Tamanho do ranking (máx. 200).")


@router.get(
    "/prova-cobra",
    response_model=list[LinhaProvaCobra],
    summary="O que mais cai na prova",
    description=(
        "Ranking de nós pelo % médio na prova (`fn_prova_cobra`): para cada prova "
        "do recorte, a fatia das questões dela no nó; o número é a média das "
        "provas distintas de cada concurso (cargos com a mesma prova contam uma "
        "vez) e depois entre os concursos, com cada concurso pesando 1 (nunca "
        "soma bruta entre provas). A questão "
        "sobe a árvore e a básica aplicada a vários cargos conta uma vez em "
        "`questoes`."
    ),
)
def prova_cobra(
    nivel_alvo: NivelAlvo = _NIVEL_ALVO,
    materia_id: str | None = _MATERIA,
    limite: int = _LIMITE,
    concurso: str | None = _CONCURSO,
    cargo_numero: int | None = _CARGO,
    nivel: str | None = _NIVEL,
    tipo_conhecimento: str | None = _TIPO,
):
    filtros = _filtros(concurso, cargo_numero, nivel, tipo_conhecimento)
    return estatisticas_servico.prova_cobra(nivel_alvo, filtros, materia_id, limite)


@router.get(
    "/edital-cobra",
    response_model=list[LinhaEditalCobra],
    summary="O que o edital cobra",
    description=(
        "Ranking de nós por itens de edital distintos (concursos aprovados), "
        "subindo a árvore; o item básico vale para cada cargo do nível."
    ),
)
def edital_cobra(
    nivel_alvo: NivelAlvo = _NIVEL_ALVO,
    materia_id: str | None = _MATERIA,
    limite: int = _LIMITE,
    concurso: str | None = _CONCURSO,
    cargo_numero: int | None = _CARGO,
    nivel: str | None = _NIVEL,
    tipo_conhecimento: str | None = _TIPO,
):
    filtros = _filtros(concurso, cargo_numero, nivel, tipo_conhecimento)
    return estatisticas_servico.edital_cobra(nivel_alvo, filtros, materia_id, limite)


@router.get(
    "/edital-vs-prova",
    response_model=EditalVsProva,
    summary="Edital × prova de um cargo",
    description=(
        "Cada nó do edital do cargo, com a situação: previsto e cobrado, ou previsto "
        "e nunca cobrado. Inclui o peso de cada disciplina na prova."
    ),
    responses=r404("Cargo sem edital nem prova."),
)
def edital_vs_prova(
    concurso: str = Query(..., description="Slug do concurso."),
    cargo_numero: int = Query(..., description="Número do cargo no edital."),
):
    resultado = estatisticas_servico.edital_vs_prova(concurso, cargo_numero)
    if not resultado:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    return resultado
