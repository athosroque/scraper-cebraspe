import math
import threading

from app.modelos import (
    FacetasResponse,
    FiltroQuestoes,
    Incidencia,
    NoArvore,
    PaginaQuestoes,
    QuestaoDetalhe,
    QuestaoResumo,
)
from app.repositorio import questoes_repo
from app.servicos.formatacao import (
    rotulo_concurso,
    rotulo_materia,
    rotulo_nivel,
    rotulo_tipo_conhecimento,
)


def listar_questoes(
    filtros: FiltroQuestoes,
    pagina: int,
    tamanho_pagina: int,
    usuario_id: int | None = None,
    chaves_incluir: list[str] | None = None,
) -> PaginaQuestoes:
    """Lista paginada. `chaves_incluir` restringe a um conjunto de chaves
    (ex.: as erradas de um simulado), somado aos filtros."""
    tamanho_pagina = max(1, min(50, tamanho_pagina))
    pagina = max(1, pagina)
    offset = (pagina - 1) * tamanho_pagina

    # Import tardio: contas_servico importa este módulo.
    from app.servicos.contas_servico import filtros_com_historico

    filtros_dict = filtros_com_historico(filtros, usuario_id)
    if chaves_incluir is not None:
        anteriores = filtros_dict.get("chaves_incluir")
        filtros_dict["chaves_incluir"] = (
            list(chaves_incluir)
            if anteriores is None
            else [c for c in chaves_incluir if c in set(anteriores)]
        )

    linhas, total = questoes_repo.buscar_questoes(filtros_dict, tamanho_pagina, offset)

    total_paginas = math.ceil(total / tamanho_pagina) if total > 0 else 0

    itens = [_com_incidencia(QuestaoResumo(**row)) for row in linhas]

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

    # Formatar as figuras para adicionar um fallback se precisarmos servir do `/figuras`
    figuras = row.get("figuras") or []
    for f in figuras:
        if "url" not in f and "path_relativo" in f:
            f["url"] = f"/figuras/{f['path_relativo']}"

    row["figuras"] = figuras
    return _com_incidencia(QuestaoDetalhe(**row))


# -- Incidência (5F.7) --
# O ranking só muda quando a carga do banco muda, então fica em memória por
# processo (reiniciar o site recarrega).
_ranking: dict[str, Incidencia] | None = None
_trava_ranking = threading.Lock()


def _ranking_por_no() -> dict[str, Incidencia]:
    global _ranking
    if _ranking is None:
        with _trava_ranking:
            if _ranking is None:
                linhas = questoes_repo.ranking_subassuntos()
                por_materia: dict[str | None, list[dict]] = {}
                for r in linhas:
                    por_materia.setdefault(r["materia_id"], []).append(r)
                ranking = {}
                for materia_id, rs in por_materia.items():
                    for posicao, r in enumerate(rs, start=1):
                        ranking[r["no_id"]] = Incidencia(
                            no_id=r["no_id"],
                            materia_id=materia_id,
                            posicao=posicao,
                            total_subassuntos=len(rs),
                            questoes=r["questoes"],
                        )
                _ranking = ranking
    return _ranking


def limpar_cache_incidencia() -> None:
    global _ranking
    _ranking = None


def _no_principal(questao: QuestaoResumo):
    principais = [n for n in questao.nos if n.papel == "principal"]
    return (principais or questao.nos or [None])[0]


def _com_incidencia(questao):
    no = _no_principal(questao)
    if no is not None and no.no_nivel == "subassunto":
        questao.incidencia = _ranking_por_no().get(no.no_id)
    return questao


def parecidas(chave: str, limite: int = 5) -> list[QuestaoResumo] | None:
    """Questões do mesmo nó principal, sem a própria e sem enunciado repetido.

    `None` quando a chave não existe.
    """
    questao = obter_questao_por_chave(chave)
    if not questao:
        return None
    no = _no_principal(questao)
    if no is None:
        return []
    mesmo_enunciado = questoes_repo.chaves_mesmo_enunciado(chave) or [chave]
    filtros = {
        "no_id": no.no_id,
        "chaves_excluir": mesmo_enunciado,
        "apenas_canonicas": True,
    }
    linhas, _ = questoes_repo.buscar_questoes(filtros, max(1, min(20, limite)), 0)
    return [_com_incidencia(QuestaoResumo(**r)) for r in linhas]


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
            nome_de_cargo=bool(r.get("nome_de_cargo")),
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


def _mapa_nos() -> dict[str, tuple[str, str, str]]:
    """id → (nome, nível, caminho com ` › `), a partir da árvore em cache."""
    mapa: dict[str, tuple[str, str, str]] = {}

    def visitar(nos, prefixo):
        for no in nos:
            nome = rotulo_materia(no.nome, no.nome_de_cargo)
            caminho = f"{prefixo} › {nome}" if prefixo else nome
            mapa[no.id] = (nome, no.nivel, caminho)
            visitar(no.filhos, caminho)

    visitar(obter_arvore(apenas_com_questoes=False), "")
    return mapa


def obter_facetas(
    filtros: FiltroQuestoes | None = None, usuario_id: int | None = None
) -> FacetasResponse:
    """Facetas da listagem. Com filtros, o total de cada valor considera os
    outros filtros; valor zerado só aparece se estiver marcado."""
    filtros = filtros or FiltroQuestoes()
    from app.servicos.contas_servico import filtros_com_historico

    filtros_dict = filtros_com_historico(filtros, usuario_id)
    dados = questoes_repo.obter_facetas(filtros_dict)

    def manter(r, campo) -> bool:
        marcados = {str(v) for v in (filtros_dict.get(campo) or [])}
        return r["total"] > 0 or str(r["valor"]) in marcados

    def valores(faceta, campo, rotulo=str, conv=lambda v: v):
        return [
            {
                "valor": conv(r["valor"]),
                "rotulo": rotulo(str(r["valor"])),
                "total": r["total"],
            }
            for r in dados.get(faceta, [])
            if r["valor"] is not None and manter(r, campo)
        ]

    mapa = _mapa_nos()

    def nos(faceta):
        saida = []
        for r in dados.get(faceta, []):
            if r["valor"] not in mapa or not manter(r, "no_id"):
                continue
            nome, nivel, caminho = mapa[r["valor"]]
            saida.append(
                {
                    "valor": r["valor"],
                    "rotulo": nome,
                    "nivel": nivel,
                    "caminho": caminho,
                    "total": r["total"],
                }
            )
        return saida

    return FacetasResponse(
        bancas=valores("banca", "banca"),
        orgaos=valores("orgao", "orgao"),
        anos=valores("ano", "ano", conv=int),
        concursos=valores("concurso", "concurso", rotulo_concurso),
        niveis=valores("nivel", "nivel", rotulo_nivel),
        tipos_conhecimento=valores(
            "tipo_conhecimento", "tipo_conhecimento", rotulo_tipo_conhecimento
        ),
        cargos=[
            {
                "valor": r["valor"],
                "cargo_numero": r["cargo_numero"],
                "cargo": r["cargo"],
                "concurso": r["concurso"],
                "nivel": r["nivel"],
                "total": r["total"],
            }
            for r in dados.get("cargo", [])
            if manter(r, "cargo")
        ],
        materias=nos("materia"),
        assuntos=nos("assunto"),
        subassuntos=nos("subassunto"),
        anuladas=[
            {
                "valor": r["valor"] == "true",
                "rotulo": "Anuladas" if r["valor"] == "true" else "Não anuladas",
                "total": r["total"],
            }
            for r in dados.get("anuladas", [])
        ],
    )
