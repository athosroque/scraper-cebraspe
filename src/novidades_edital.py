"""O que um edital traz de novo em relação à árvore mestre (ADR-030).

Função pura para o relatório de revisão: mostra ao dono o que a carga criaria
ou deixaria pendente, a saber disciplina fora de `canonico/disciplinas.json` e
assunto/subassunto sem nó na árvore. Não grava nada.

Um item é conhecido quando (a) a chave natural dele (`chave_item`) tem
mapeamento aprovado na árvore, ou (b) existe nó ativo de mesma `chave_regra`
no nó-pai (a mesma equivalência de `canonico.mapear_novos_itens_por_regra`:
caixa, acento, "noções de", artigo, qualificador entre parênteses, singular).
Título de bloco fora da lista de disciplinas que bate com um assunto existente
não é disciplina nova (P72).

Um terceiro estado separa o "realmente novo" do "proposto": item sem nó
aprovado, mas com mapeamento `proposto` (a IA achou um nó existente) não é
novo; vai para `propostas`, para o dono conferir e aprovar via `curar_arvore`.
Só é "realmente novo" o item sem equivalente aprovado nem proposto.
"""

import json
from pathlib import Path

from src import arvore as arv_mod
from src.canonico import chave_regra, normalizar
from src.stats_writer import montar_carga_concurso

DISCIPLINAS_PADRAO = arv_mod.PROJETO_DIR / "canonico" / "disciplinas.json"


def carregar_disciplinas(path: Path = DISCIPLINAS_PADRAO) -> list[str]:
    if not path.exists():
        return []
    dados = json.loads(path.read_text(encoding="utf-8"))
    return [d["nome"] for d in dados.get("disciplinas", [])]


def _nos_aprovados(arv: arv_mod.ArvoreMestre, chave: str) -> set[str]:
    return {
        arv_mod.resolver_no(arv, m.no_id)
        for m in arv.mapeamentos.get(chave, [])
        if m.status == "aprovado"
    }


def _proposto(arv: arv_mod.ArvoreMestre, chave: str) -> arv_mod.Mapeamento | None:
    """Primeiro mapeamento `proposto` da chave para nó ainda utilizável."""
    for m in arv.mapeamentos.get(chave, []):
        if m.status != "proposto":
            continue
        no = arv.nos.get(arv_mod.resolver_no(arv, m.no_id))
        if no is not None and no.status != "aposentado":
            return m
    return None


def _caminho(arv: arv_mod.ArvoreMestre, no_id: str) -> str:
    nomes = []
    atual = arv_mod.resolver_no(arv, no_id)
    vistos: set[str] = set()
    while atual in arv.nos and atual not in vistos:
        vistos.add(atual)
        nomes.append(arv.nos[atual].nome)
        pai = arv.nos[atual].pai
        atual = arv_mod.resolver_no(arv, pai) if pai else ""
    return " › ".join(reversed(nomes))


def _titulos_sem_destino(
    resultado: dict, disciplinas: dict[str, str], assuntos: dict
) -> list[dict]:
    """Título de bloco sem nó, com o que ele trava, do que mais trava ao que menos.

    Não é disciplina nova (P72): é a decisão de para onde o título vai. Os
    `itens_travados` são os assuntos sem nó sob o título e os subassuntos deles,
    que só serão comparados com a árvore depois dessa decisão.
    """
    titulos = []
    for chave, nome in disciplinas.items():
        travados = sum(
            1 + len(e["subassuntos"])
            for e in assuntos.values()
            if e["_materia_chave"] == chave and e["_novo"]
        )
        chunks = []
        for r in resultado.get("resultados", []):
            materia = (r.get("taxonomia_extraida") or {}).get("materia")
            idx = r.get("chunk_index")
            if normalizar(materia or "") == chave and idx not in chunks:
                chunks.append(idx)
        titulos.append({"titulo": nome, "chunks": chunks, "itens_travados": travados})
    return sorted(titulos, key=lambda t: -t["itens_travados"])


def novidades_do_edital(
    resultado: dict,
    disciplinas_conhecidas: list[str] | None = None,
    arvore: arv_mod.ArvoreMestre | None = None,
) -> dict:
    """Disciplinas e assuntos/subassuntos do edital sem correspondente na árvore.

    `assuntos_novos` lista, por disciplina, cada assunto que tem algo novo: o
    próprio assunto novo (com todos os seus subassuntos) ou assunto já conhecido
    com subassuntos novos. `total_assuntos` conta essas entradas;
    `total_itens_novos` soma disciplinas novas, assuntos realmente novos e
    subassuntos novos. "Novo" aqui é "realmente novo": sem nó aprovado nem
    proposto. `titulos_sem_destino` (alias antigo: `disciplinas_novas`) lista os
    títulos de bloco sem nó com `chunks` e `itens_travados`, ordenados por
    itens travados; `total_itens_travados` os soma. Os itens com nó só proposto vão para `propostas` (e
    `total_propostas`), com `nivel`, `item`, `disciplina`, `assunto` (nos
    subassuntos), `no_id`, `no_caminho` e `confianca` quando existir.
    """
    if disciplinas_conhecidas is None:
        disciplinas_conhecidas = carregar_disciplinas()
    if arvore is None:
        arvore = arv_mod.carregar()

    regras_disc = {chave_regra(n).chave for n in disciplinas_conhecidas}
    ativos = [n for n in arvore.nos.values() if n.status == "ativo"]
    filhos: dict[str, list] = {}
    for n in ativos:
        if n.pai:
            filhos.setdefault(arv_mod.resolver_no(arvore, n.pai), []).append(n)
    materias_por_regra: dict[str, set[str]] = {}
    assuntos_por_regra: dict[str, set[str]] = {}
    for n in ativos:
        r = chave_regra(n.nome).chave
        if n.nivel == "materia":
            materias_por_regra.setdefault(r, set()).add(n.id)
        elif n.nivel == "assunto":
            assuntos_por_regra.setdefault(r, set()).add(n.id)

    def filho_equivalente(pais: set[str], nome: str) -> set[str]:
        regra = chave_regra(nome).chave
        return {
            f.id
            for p in pais
            for f in filhos.get(p, [])
            if chave_regra(f.nome).chave == regra
        }

    carga = montar_carga_concurso(resultado)
    disciplinas: dict[str, str] = {}  # chave -> nome, na ordem de aparição
    assuntos: dict[tuple[str, str], dict] = {}
    propostas: dict[str, dict] = {}  # chave_item -> proposta

    def registrar_proposta(
        chave: str, m: arv_mod.Mapeamento, nivel: str, nome: str, disc: str, ass=None
    ) -> set[str]:
        no_id = arv_mod.resolver_no(arvore, m.no_id)
        if chave not in propostas:
            p = {"nivel": nivel, "item": nome, "disciplina": disc}
            if ass is not None:
                p["assunto"] = ass
            p["no_id"] = no_id
            p["no_caminho"] = _caminho(arvore, no_id)
            confianca = getattr(m, "confianca", None)
            if confianca is not None:
                p["confianca"] = confianca
            propostas[chave] = p
        return {no_id}

    for item in carga["itens"]:
        m_chave, m_nome = item["materia_chave"], item["materia_nome"]
        regra_m = chave_regra(m_nome).chave
        nos_m = _nos_aprovados(arvore, arv_mod.chave_item(m_chave))
        if not nos_m:
            nos_m = materias_por_regra.get(regra_m, set())
        if not nos_m and regra_m in regras_disc:
            nos_m = {"?"}  # disciplina da lista fechada ainda sem nó
        if not nos_m:
            nos_m = assuntos_por_regra.get(regra_m, set())  # P72: vira assunto
            if not nos_m:
                prop = _proposto(arvore, arv_mod.chave_item(m_chave))
                if prop:
                    nos_m = registrar_proposta(
                        arv_mod.chave_item(m_chave), prop, "disciplina", m_nome, m_nome
                    )
                else:
                    disciplinas.setdefault(m_chave, m_nome)

        t_chave = item["topico_chave"]
        nos_t = _nos_aprovados(arvore, arv_mod.chave_item((m_chave, t_chave)))
        if not nos_t:
            nos_t = filho_equivalente(nos_m, item["topico_nome"])
        if not nos_t:
            chave_t = arv_mod.chave_item((m_chave, t_chave))
            prop = _proposto(arvore, chave_t)
            if prop:
                nos_t = registrar_proposta(
                    chave_t, prop, "assunto", item["topico_nome"], m_nome
                )
        entrada = None
        subs_novos: list[str] = []
        for sub in item["subtopicos"]:
            s_chave = normalizar(sub)
            if not s_chave:
                continue
            chave_s = arv_mod.chave_item((m_chave, t_chave, s_chave))
            if nos_t and (
                _nos_aprovados(arvore, chave_s) or filho_equivalente(nos_t, sub)
            ):
                continue
            prop = _proposto(arvore, chave_s)
            if nos_t and prop:
                registrar_proposta(
                    chave_s, prop, "subassunto", sub, m_nome, item["topico_nome"]
                )
                continue
            subs_novos.append(sub)
        if not nos_t or subs_novos:
            entrada = assuntos.setdefault(
                (m_chave, t_chave),
                {
                    "disciplina": m_nome,
                    "assunto": item["topico_nome"],
                    "subassuntos": [],
                    "_novo": not nos_t,
                    "_materia_chave": m_chave,
                },
            )
            for sub in subs_novos:
                if sub not in entrada["subassuntos"]:
                    entrada["subassuntos"].append(sub)

    lista = [
        {k: v for k, v in e.items() if not k.startswith("_")} for e in assuntos.values()
    ]
    n_assuntos_novos = sum(1 for e in assuntos.values() if e["_novo"])
    n_subs = sum(len(e["subassuntos"]) for e in assuntos.values())
    titulos = _titulos_sem_destino(resultado, disciplinas, assuntos)
    return {
        "titulos_sem_destino": titulos,
        "total_titulos_sem_destino": len(titulos),
        "total_itens_travados": sum(t["itens_travados"] for t in titulos),
        # alias de compatibilidade: nomes dos títulos, na ordem de aparição
        "disciplinas_novas": list(disciplinas.values()),
        "assuntos_novos": lista,
        "total_disciplinas": len(disciplinas),
        "total_assuntos": len(lista),
        "total_itens_novos": len(disciplinas) + n_assuntos_novos + n_subs,
        "propostas": list(propostas.values()),
        "total_propostas": len(propostas),
    }
