import math

from app.modelos import (
    FacetasResponse,
    FiltroQuestoes,
    NoArvore,
    PaginaQuestoes,
    QuestaoDetalhe,
    QuestaoResumo,
)
from app.repositorio import questoes_repo


def listar_questoes(
    filtros: FiltroQuestoes, pagina: int, tamanho_pagina: int
) -> PaginaQuestoes:
    tamanho_pagina = max(1, min(50, tamanho_pagina))
    pagina = max(1, pagina)
    offset = (pagina - 1) * tamanho_pagina

    filtros_dict = filtros.model_dump(exclude_none=True)

    linhas, total = questoes_repo.buscar_questoes(filtros_dict, tamanho_pagina, offset)

    total_paginas = math.ceil(total / tamanho_pagina) if total > 0 else 0

    itens = [QuestaoResumo(**row) for row in linhas]

    return PaginaQuestoes(
        total=total,
        pagina=pagina,
        tamanho_pagina=tamanho_pagina,
        total_paginas=total_paginas,
        itens=itens,
    )


def obter_questao_por_chave(chave: str) -> QuestaoDetalhe | None:
    row = questoes_repo.obter_questao_por_chave(chave)
    if not row:
        return None

    # Formatar as figuras para adicionar um fallback se precisarmos servir do `/static`
    figuras = row.get("figuras") or []
    for f in figuras:
        if "url" not in f and "path_relativo" in f:
            f["url"] = f"/static/{f['path_relativo']}"

    row["figuras"] = figuras
    return QuestaoDetalhe(**row)


def obter_arvore(apenas_com_questoes: bool = True) -> list[NoArvore]:
    linhas = questoes_repo.obter_arvore_com_contagens()

    if apenas_com_questoes:
        linhas = [r for r in linhas if r["total_questoes"] > 0]

    nodes_by_id = {
        r["id"]: NoArvore(
            id=r["id"],
            nome=r["nome"],
            nivel=r["nivel"],
            total_questoes=r["total_questoes"],
            filhos=[],
        )
        for r in linhas
    }

    arvore = []

    for r in linhas:
        node = nodes_by_id[r["id"]]
        pai_id = r.get("pai_id")

        if pai_id and pai_id in nodes_by_id:
            nodes_by_id[pai_id].filhos.append(node)
        elif not pai_id or r["nivel"] == "materia":
            arvore.append(node)

    return arvore


def obter_facetas() -> FacetasResponse:
    dados = questoes_repo.obter_facetas()

    return FacetasResponse(
        bancas=[
            {"valor": r["valor"], "rotulo": str(r["valor"]), "total": r["total"]}
            for r in dados["banca"]
        ],
        orgaos=[
            {"valor": r["valor"], "rotulo": str(r["valor"]), "total": r["total"]}
            for r in dados["orgao"]
        ],
        anos=[
            {"valor": r["valor"], "rotulo": str(r["valor"]), "total": r["total"]}
            for r in dados["ano"]
        ],
        concursos=[
            {"valor": r["valor"], "rotulo": str(r["valor"]), "total": r["total"]}
            for r in dados["concurso"]
        ],
        niveis=[
            {"valor": r["valor"], "rotulo": str(r["valor"]), "total": r["total"]}
            for r in dados["nivel"]
        ],
        tipos_conhecimento=[
            {"valor": r["valor"], "rotulo": str(r["valor"]), "total": r["total"]}
            for r in dados["tipo_conhecimento"]
        ],
        cargos=dados["cargos"],
    )
