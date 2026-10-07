"""Estatísticas do site (5F.4): "o que mais cai", "o que o edital cobra" e edital × prova."""

import unicodedata
from collections import Counter

from app.modelos import (
    EditalVsProva,
    FiltroEstatistica,
    LinhaEditalCobra,
    LinhaEditalVsProva,
    LinhaProvaCobra,
    MateriaDetalhe,
    MateriaResumo,
    NivelAlvo,
    PesoMateria,
    ResultadoBusca,
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


# "Cobrado fora do edital" saiu do site (decisão do dono, 2026-10-07, ADR-035):
# a banca só cobra o que o edital prevê. A view guarda a situação (histórico).
_SITUACOES_DO_SITE = ("cobrado_no_edital", "no_edital_nunca_cobrado")


def edital_vs_prova(concurso: str, cargo_numero: int) -> EditalVsProva | None:
    nos = [
        LinhaEditalVsProva(**r)
        for r in estatisticas_repo.edital_vs_prova(concurso, cargo_numero)
        if r["situacao"] in _SITUACOES_DO_SITE
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


def materia_ativa(no_id: str) -> dict | None:
    return estatisticas_repo.materia_ativa(no_id)


# -- Matérias e busca (5F.7) --
LIMITE_BUSCA = 20
_ORDEM_NIVEL = {"materia": 0, "assunto": 1, "subassunto": 2}


def listar_materias() -> list[MateriaResumo]:
    return [MateriaResumo(**r) for r in estatisticas_repo.materias_com_contagem()]


def detalhe_materia(
    materia_id: str, filtros: FiltroEstatistica, limite: int = 15
) -> MateriaDetalhe | None:
    # Com id, a consulta devolve a matéria ativa mesmo sem questão (LEFT JOIN);
    # sem linha, o id não é matéria ativa. Sem questão, `nome_de_cargo` fica
    # false: a flag só chega à role de leitura via `vw_questoes`.
    linhas = estatisticas_repo.materias_com_contagem(materia_id)
    if not linhas:
        return None
    base = linhas[0]
    # Linha da própria matéria em fn_prova_cobra: nunca soma de cargos.
    recorte = prova_cobra("materia", filtros, materia_id, LIMITE_MAXIMO)
    linha = next((r for r in recorte if r.no_id == materia_id), None)
    edital = edital_cobra("materia", filtros, materia_id, LIMITE_MAXIMO)
    itens = next((r.ocorrencias for r in edital if r.no_id == materia_id), 0)
    top = [
        r
        for r in prova_cobra("subassunto", filtros, materia_id, limite)
        if r.questoes or r.anuladas
    ]
    return MateriaDetalhe(
        **base,
        questoes_recorte=linha.questoes if linha else 0,
        anuladas_recorte=linha.anuladas if linha else 0,
        pct_do_universo=linha.pct_do_universo if linha else 0.0,
        itens_edital=itens,
        top_subassuntos=top,
    )


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore")
    return " ".join(sem_acento.decode().lower().split())


def buscar_nos(q: str) -> list[ResultadoBusca]:
    alvo = _normalizar(q)
    if not alvo:
        return []
    achados = []
    for r in estatisticas_repo.nos_ativos():
        nome = _normalizar(r["nome"])
        if alvo in nome:
            chave = (not nome.startswith(alvo), _ORDEM_NIVEL.get(r["nivel"], 9), nome)
            achados.append((chave, r))
    achados.sort(key=lambda par: par[0])
    return [ResultadoBusca(**r) for _, r in achados[:LIMITE_BUSCA]]
