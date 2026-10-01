"""Estatísticas do site (5F.4): "o que mais cai", "o que o edital cobra" e edital × prova."""

from collections import Counter

from app.modelos import (
    EditalVsProva,
    FiltroEstatistica,
    LinhaEditalCobra,
    LinhaEditalVsProva,
    LinhaProvaCobra,
    NivelAlvo,
    PesoMateria,
)
from app.repositorio import estatisticas_repo

LIMITE_MAXIMO = 200


def _limite(limite: int) -> int:
    return max(1, min(LIMITE_MAXIMO, limite))


def prova_cobra(
    nivel_alvo: NivelAlvo,
    filtros: FiltroEstatistica,
    materia_id: str | None = None,
    limite: int = 20,
) -> list[LinhaProvaCobra]:
    linhas = estatisticas_repo.prova_cobra(
        nivel_alvo, filtros.model_dump(), materia_id, _limite(limite)
    )
    return [LinhaProvaCobra(**r) for r in linhas]


def edital_cobra(
    nivel_alvo: NivelAlvo,
    filtros: FiltroEstatistica,
    materia_id: str | None = None,
    limite: int = 20,
) -> list[LinhaEditalCobra]:
    linhas = estatisticas_repo.edital_cobra(
        nivel_alvo, filtros.model_dump(), materia_id, _limite(limite)
    )
    return [LinhaEditalCobra(**r) for r in linhas]


def edital_vs_prova(concurso: str, cargo_numero: int) -> EditalVsProva | None:
    nos = [
        LinhaEditalVsProva(**r)
        for r in estatisticas_repo.edital_vs_prova(concurso, cargo_numero)
    ]
    if not nos:
        return None
    pesos = [
        PesoMateria(**r)
        for r in estatisticas_repo.peso_materia_cargo(concurso, cargo_numero)
    ]
    return EditalVsProva(
        concurso=concurso,
        cargo_numero=cargo_numero,
        resumo=dict(Counter(n.situacao for n in nos)),
        nos=nos,
        peso_materias=pesos,
    )


def materias() -> list[dict]:
    return estatisticas_repo.materias()


def cargos() -> list[dict]:
    return estatisticas_repo.cargos()
