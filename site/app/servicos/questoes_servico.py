import math
import re
import threading
from typing import NamedTuple

from app.cache import cache_ttl
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
    codigo_curto,
    rotulo_concurso,
    rotulo_materia,
    rotulo_nivel,
    rotulo_tipo_conhecimento,
    rotulo_tipo_questao,
)


def _montar(modelo, row: dict):
    return modelo(**row, codigo=codigo_curto(row["questao_chave"]))


def listar_questoes(
    filtros: FiltroQuestoes,
    pagina: int,
    tamanho_pagina: int,
    usuario_id: int | None = None,
    chaves_incluir: list[str] | None = None,
) -> PaginaQuestoes:
    """Lista paginada. `chaves_incluir` restringe a um conjunto de chaves
    (ex.: as erradas de um simulado), somado aos filtros. Os nós seguem a
    cascata (`nos_da_consulta`), no site e na API."""
    tamanho_pagina = max(1, min(50, tamanho_pagina))
    pagina = max(1, pagina)
    offset = (pagina - 1) * tamanho_pagina

    filtros_dict = filtros_para_repo(filtros, usuario_id)
    if chaves_incluir is not None:
        anteriores = filtros_dict.get("chaves_incluir")
        filtros_dict["chaves_incluir"] = (
            list(chaves_incluir)
            if anteriores is None
            else [c for c in chaves_incluir if c in set(anteriores)]
        )

    linhas, total = questoes_repo.buscar_questoes(filtros_dict, tamanho_pagina, offset)

    total_paginas = math.ceil(total / tamanho_pagina) if total > 0 else 0

    itens = [_com_incidencia(_montar(QuestaoResumo, row)) for row in linhas]

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
    return _com_incidencia(_montar(QuestaoDetalhe, row))


# -- ID curto (5H.1) --
_PADRAO_CODIGO = re.compile(r"^Q[0-9A-F]{8}$")


@cache_ttl(300)
def _chaves_por_codigo() -> dict[str, str]:
    return {codigo_curto(c): c for c in questoes_repo.todas_as_chaves()}


def chave_por_codigo(codigo: str) -> str | None:
    """Chave da questão a partir do ID curto (aceita minúsculas). `None` se não existe."""
    codigo = codigo.strip().upper()
    if not _PADRAO_CODIGO.match(codigo):
        return None
    return _chaves_por_codigo().get(codigo)


def chave_do_termo(texto: str | None) -> str | None:
    """Atalho do ID curto na palavra-chave (5H.4): a chave da questão quando o
    termo inteiro (aparado, minúsculas aceitas) é um ID curto que existe.
    `None` para termo vazio, outro texto ou ID desconhecido."""
    if not texto:
        return None
    return chave_por_codigo(texto)


def filtros_para_repo(filtros: FiltroQuestoes, usuario_id: int | None) -> dict:
    """Filtros prontos para o repositório: histórico do usuário (5F.3), o
    atalho do ID curto, que troca a palavra-chave pela própria questão, e os
    nós da cascata (`nos_da_consulta`, 5H.3).

    Levanta `LoginNecessario` quando o histórico pede login e não há usuário.
    """
    # Import tardio: contas_servico importa este módulo.
    from app.servicos.contas_servico import filtros_com_historico

    filtros_dict = filtros_com_historico(filtros, usuario_id)
    chave = chave_do_termo(filtros.texto)
    if chave is not None:
        filtros_dict.pop("texto", None)
        filtros_dict["chave_codigo"] = chave
    if filtros_dict.get("no_id"):
        filtros_dict["no_id"] = nos_da_consulta(filtros_dict["no_id"])
    return filtros_dict


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
    return [_com_incidencia(_montar(QuestaoResumo, r)) for r in linhas]


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


class NoInfo(NamedTuple):
    nome: str
    nivel: str
    caminho: str
    pai: str | None


def _mapa_nos() -> dict[str, NoInfo]:
    """id → nome, nível, caminho com ` › ` e pai, a partir da árvore em cache."""
    mapa: dict[str, NoInfo] = {}

    def visitar(nos, prefixo, pai):
        for no in nos:
            nome = rotulo_materia(no.nome, no.nome_de_cargo)
            caminho = f"{prefixo} › {nome}" if prefixo else nome
            mapa[no.id] = NoInfo(nome, no.nivel, caminho, pai)
            visitar(no.filhos, caminho, no.id)

    visitar(obter_arvore(apenas_com_questoes=False), "", None)
    return mapa


def info_nos() -> dict[str, NoInfo]:
    """Nós da árvore inteira (inclusive sem questão) por id."""
    return _mapa_nos()


# -- Cascata disciplina → assunto → subassunto (5H.3) --
# Vale para o site e para toda a API que aceita `no_id` (decisão do dono,
# 2026-10-07): a mesma URL dá o mesmo resultado nos dois.
_NIVEIS = ("materia", "assunto", "subassunto")


def _ancestral(mapa: dict[str, NoInfo], no_id: str, nivel: str) -> str | None:
    atual = mapa[no_id].pai
    while atual is not None and atual in mapa:
        if mapa[atual].nivel == nivel:
            return atual
        atual = mapa[atual].pai
    return None


def coerir_nos(no_ids: list[str] | None) -> list[str] | None:
    """Seleção de nós coerente com a cascata do painel, de cima para baixo.

    - Assunto cuja disciplina não está marcada, quando há disciplina marcada,
      é órfão e sai (o painel o teria limpado ao desmarcar a disciplina).
      Idem subassunto cujo assunto (ou disciplina) não está marcado.
    - Sem nenhum nó marcado no nível de cima, o filho é link direto (card,
      estatística, painel da disciplina): os ancestrais entram, para o painel
      mostrar a cadeia marcada e o resultado continuar o mesmo.

    Id desconhecido (fora da árvore) fica como veio, no fim.
    """
    if not no_ids:
        return no_ids
    mapa = _mapa_nos()
    por_nivel: dict[str, list[str]] = {n: [] for n in _NIVEIS}
    desconhecidos: list[str] = []
    for no_id in dict.fromkeys(no_ids):
        info = mapa.get(no_id)
        if info and info.nivel in por_nivel:
            por_nivel[info.nivel].append(no_id)
        else:
            desconhecidos.append(no_id)

    marcados: dict[str, list[str]] = {"materia": list(por_nivel["materia"])}
    for nivel, acima in (
        ("assunto", ["materia"]),
        ("subassunto", ["materia", "assunto"]),
    ):
        # O que já estava marcado em cada nível de cima antes de completar.
        havia = {n: set(marcados[n]) for n in acima}
        marcados[nivel] = []
        for no_id in por_nivel[nivel]:
            cadeia = {n: _ancestral(mapa, no_id, n) for n in acima}
            if any(havia[n] and cadeia[n] not in havia[n] for n in acima):
                continue  # órfão
            marcados[nivel].append(no_id)
            for n in acima:
                if cadeia[n] and cadeia[n] not in marcados[n]:
                    marcados[n].append(cadeia[n])
    return [
        *marcados["materia"],
        *marcados["assunto"],
        *marcados["subassunto"],
        *desconhecidos,
    ]


def refinar_por_ramo(no_ids: list[str] | None) -> list[str] | None:
    """No mesmo ramo vale o nó mais específico.

    Disciplina com assunto marcado fica só com os assuntos marcados (e assunto
    com subassunto, só com os subassuntos); disciplina sem filho marcado vale
    inteira. Os nós restantes combinam em OU.
    """
    if not no_ids:
        return no_ids
    mapa = _mapa_nos()
    com_filho: set[str] = set()
    for no_id in no_ids:
        atual = mapa[no_id].pai if no_id in mapa else None
        while atual is not None:
            com_filho.add(atual)
            atual = mapa[atual].pai if atual in mapa else None
    return [n for n in no_ids if n not in com_filho]


def nos_da_consulta(no_ids: list[str] | None) -> list[str] | None:
    """Nós que entram na consulta: seleção coerente (`coerir_nos`) e, no
    mesmo ramo, só o mais específico (`refinar_por_ramo`). Idempotente: a
    seleção que o site já coeriu dá o mesmo resultado."""
    return refinar_por_ramo(coerir_nos(no_ids))


def textos_busca(apelidos: dict[str, list[str]]) -> dict[str, str]:
    """Texto de busca de cada nó: nome e apelidos dele e de todos os descendentes.

    Assim "LGPD" acha a disciplina que contém o nó da LGPD (KAN-64). Montado
    uma vez por requisição, a partir da árvore em cache."""
    mapa = _mapa_nos()
    filhos: dict[str, list[str]] = {}
    for no_id, info in mapa.items():
        if info.pai is not None:
            filhos.setdefault(info.pai, []).append(no_id)

    def coletar(no_id: str) -> list[str]:
        partes = [mapa[no_id].nome, *apelidos.get(no_id, [])]
        for filho in filhos.get(no_id, []):
            partes.extend(coletar(filho))
        return partes

    return {no_id: " | ".join(coletar(no_id)) for no_id in mapa}


def opcoes_em_cascata(
    facetas: FacetasResponse,
    no_ids: list[str] | None,
    textos: dict[str, str] | None = None,
) -> dict[str, list[dict]]:
    """Opções de disciplina, assunto e subassunto do painel do site.

    Assunto só das disciplinas marcadas e subassunto só dos assuntos marcados
    (sem pai marcado, a lista vem vazia). Cada opção leva o próprio nome e o
    `pai`, nunca o caminho: o painel agrupa sob o nome do pai. `busca` é o
    texto de `textos_busca` (nome e apelidos, com os descendentes).
    """
    mapa = _mapa_nos()
    marcados = set(no_ids or [])
    textos = textos or {}

    def opcoes(lista, restringir: bool):
        saida = []
        for n in lista:
            pai = mapa[n.valor].pai if n.valor in mapa else None
            if restringir and pai not in marcados:
                continue
            saida.append(
                {
                    "valor": n.valor,
                    "rotulo": n.rotulo,
                    "total": n.total,
                    "pai": pai,
                    "busca": textos.get(n.valor, ""),
                }
            )
        return saida

    return {
        "materia": opcoes(facetas.materias, False),
        "assunto": opcoes(facetas.assuntos, True),
        "subassunto": opcoes(facetas.subassuntos, True),
    }


def obter_facetas(
    filtros: FiltroQuestoes | None = None,
    usuario_id: int | None = None,
) -> FacetasResponse:
    """Facetas da listagem. Com filtros, o total de cada valor considera os
    outros filtros; valor zerado só aparece se estiver marcado. A consulta usa
    os nós da cascata, como em `listar_questoes`, mas o nó marcado (inclusive
    o pai que o refino tira) continua nas facetas."""
    filtros = filtros or FiltroQuestoes()
    filtros_dict = filtros_para_repo(filtros, usuario_id)
    selecionados = {**filtros_dict, "no_id": coerir_nos(filtros.no_id)}
    dados = questoes_repo.obter_facetas(filtros_dict)

    def manter(r, campo) -> bool:
        marcados = {str(v) for v in (selecionados.get(campo) or [])}
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
            nome, nivel, caminho, _ = mapa[r["valor"]]
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
        tipos=valores("tipo", "tipo", rotulo_tipo_questao),
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
