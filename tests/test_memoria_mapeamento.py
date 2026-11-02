"""Testes de src/memoria_mapeamento.py: funções puras sobre a árvore, sem LLM."""

from __future__ import annotations

import pytest

from src import arvore
from src import memoria_mapeamento as mem
from src.canonico import chave_regra


def regra(nome: str) -> str:
    return chave_regra(nome).chave


@pytest.fixture
def arv():
    a = arvore.ArvoreMestre()
    arvore.criar_no(a, "materia", "Direito Administrativo", None, id_override="M-DA")
    arvore.criar_no(a, "materia", "Direito Penal", None, id_override="M-DP")
    arvore.criar_no(a, "assunto", "Atos administrativos", "M-DA", id_override="A-ATO")
    arvore.criar_no(a, "assunto", "Licitações", "M-DA", id_override="A-LIC")
    arvore.criar_no(a, "assunto", "Crimes contra a vida", "M-DP", id_override="A-VIDA")
    arvore.criar_no(
        a, "subassunto", "Anulação e revogação", "A-ATO", id_override="S-ANUL"
    )
    arvore.mapear(a, "direito administrativo", ["M-DA"], "regra", "aprovado")
    arvore.mapear(a, "direito penal", ["M-DP"], "regra", "aprovado")
    return a


def pais_da(a, chave: str):
    return mem.nos_aprovados_do_pai(a, chave)


def test_repete_decisao_aprovada_de_outro_edital(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "humano")
    pais = pais_da(arv, "direito administrativo|CONTROLE")
    assert mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais) == {
        "A-ATO"
    }


def test_nao_resolve_sob_outro_pai(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "humano")
    pais_outro = pais_da(arv, "direito penal|controle")
    assert (
        mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais_outro) is None
    )


def test_decisoes_divergentes_sao_ambiguas(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "humano")
    arvore.mapear(arv, "direito administrativo|a controle x", ["A-LIC"], "humano")
    # Mesma regra "controle" com dois destinos diferentes no mesmo pai.
    arvore.mapear(arv, "direito administrativo|controle (nova)", ["A-LIC"], "humano")
    pais = pais_da(arv, "direito administrativo|controle")
    assert mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais) is None


def test_proposta_nao_aprovada_nao_e_fonte(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "llm", "proposto")
    pais = pais_da(arv, "direito administrativo|x")
    assert mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais) is None


def test_proposta_llm_aprovada_pelo_dono_vira_fonte(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "llm", "proposto")
    arvore.aprovar(arv, "direito administrativo|controle", "A-ATO")
    pais = pais_da(arv, "direito administrativo|x")
    assert mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais) == {
        "A-ATO"
    }


def test_pai_so_proposto_nao_resolve(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "humano")
    arvore.mapear(arv, "novo bloco", ["M-DA"], "llm", "proposto")
    pais = pais_da(arv, "novo bloco|controle")  # pai sem nó aprovado
    assert pais == frozenset()
    assert mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais) is None


def test_apelido_de_no_fundido(arv):
    arvore.criar_no(
        arv, "assunto", "Atos do poder público", "M-DA", id_override="A-ANT"
    )
    arvore.fundir_nos(arv, "A-ANT", "A-ATO")
    pais = pais_da(arv, "direito administrativo|x")
    assert mem.resolver_por_memoria(
        arv, regra("Atos do Poder Público"), "assunto", pais
    ) == {"A-ATO"}


def test_no_ativo_semente_ou_humano_nao_vira_apelido(arv):
    pais = pais_da(arv, "direito administrativo|x")
    arvore.criar_no(arv, "assunto", "Probidade", "M-DA", "humano", id_override="A-PRO")
    arvore.criar_no(
        arv, "assunto", "Improbidade", "M-DA", "semente", id_override="A-IMP"
    )
    assert mem.resolver_por_memoria(arv, regra("Probidade"), "assunto", pais) is None
    assert mem.resolver_por_memoria(arv, regra("Improbidade"), "assunto", pais) is None
    assert mem.construir_indice(arv).apelidos.get(regra("Probidade")) is None


def test_apelido_de_fundido_respeita_disciplina_e_nivel(arv):
    pais_da_ = pais_da(arv, "direito administrativo|x")
    arvore.criar_no(arv, "assunto", "Probidade", "M-DA", "humano", id_override="A-PRO")
    arvore.fundir_nos(arv, "A-PRO", "A-LIC")
    assert mem.resolver_por_memoria(arv, regra("Probidade"), "assunto", pais_da_) == {
        "A-LIC"
    }
    pais_pen = pais_da(arv, "direito penal|x")
    assert (
        mem.resolver_por_memoria(arv, regra("Probidade"), "assunto", pais_pen) is None
    )
    # Nível errado: subtópico não aponta para assunto.
    assert (
        mem.resolver_por_memoria(arv, regra("Probidade"), "subassunto", pais_da_)
        is None
    )


def test_no_ativo_de_origem_llm_nao_e_apelido(arv):
    arvore.criar_no(arv, "assunto", "Probidade", "M-DA", "llm", id_override="A-PRO")
    pais = pais_da(arv, "direito administrativo|x")
    assert mem.resolver_por_memoria(arv, regra("Probidade"), "assunto", pais) is None


def test_par_rejeitado_nunca_e_devolvido(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "humano")
    arvore.mapear(arv, "direito administrativo|controle x", ["A-LIC"], "humano")
    arvore.rejeitar(arv, "direito administrativo|controle x", "A-LIC")
    # Rejeição de OUTRO item de mesma regra bloqueia o par (regra, nó).
    arvore.mapear(arv, "direito administrativo|outro", ["A-ATO"], "humano")
    arvore.mapear(arv, "direito penal|outro", ["A-ATO"], "humano", "proposto")
    arvore.rejeitar(arv, "direito penal|outro", "A-ATO")
    pais = pais_da(arv, "direito administrativo|z")
    assert (regra("outro"), "A-ATO") in mem.rejeicoes(arv)
    assert mem.resolver_por_memoria(arv, regra("Outro"), "assunto", pais) is None


def test_rejeicoes_traz_pares_de_qualquer_origem(arv):
    arvore.mapear(arv, "direito penal|homicidio", ["A-VIDA"], "llm", "proposto")
    arvore.rejeitar(arv, "direito penal|homicidio", "A-VIDA")
    assert mem.rejeicoes(arv) == {(regra("homicidio"), "A-VIDA"): "homicidio"}


def test_exemplos_so_humano_ou_llm_aprovado_da_mesma_disciplina(arv):
    arvore.mapear(arv, "direito administrativo|revogacao do ato", ["S-ANUL"], "humano")
    arvore.mapear(arv, "direito administrativo|licitacoes", ["A-LIC"], "semente")
    arvore.mapear(arv, "direito administrativo|proposto", ["A-ATO"], "llm", "proposto")
    arvore.mapear(arv, "direito penal|homicidio", ["A-VIDA"], "humano")
    ex = mem.exemplos_aprovados(arv, "assunto", "M-DA", 5)
    assert [(e.item, e.no_id) for e in ex] == [("revogacao do ato", "S-ANUL")]
    assert ex[0].caminho == (
        "Direito Administrativo › Atos administrativos › Anulação e revogação"
    )
    # Outro nível e outra disciplina ficam de fora.
    assert mem.exemplos_aprovados(arv, "subassunto", "M-DA", 5) == []
    assert [e.no_id for e in mem.exemplos_aprovados(arv, "assunto", {"M-DP"}, 5)] == [
        "A-VIDA"
    ]


def test_exemplos_ordenados_por_similaridade_e_limitados(arv):
    arvore.mapear(arv, "direito administrativo|zeta qualquer", ["A-LIC"], "humano")
    arvore.mapear(arv, "direito administrativo|revogacao de ato", ["S-ANUL"], "humano")
    arvore.mapear(arv, "direito administrativo|outra coisa", ["A-ATO"], "humano")
    ex = mem.exemplos_aprovados(
        arv, "assunto", "M-DA", 2, referencia="Revogação de atos administrativos"
    )
    assert len(ex) == 2 and ex[0].item == "revogacao de ato"


def test_exemplos_usam_rotulo_original(arv):
    arvore.mapear(arv, "direito administrativo|revogacao do ato", ["S-ANUL"], "humano")
    ex = mem.exemplos_aprovados(
        arv,
        "assunto",
        "M-DA",
        3,
        rotulos={"direito administrativo|revogacao do ato": "Revogação do ato"},
    )
    assert ex[0].item == "Revogação do ato"


def test_funcoes_nao_alteram_a_arvore(arv):
    arvore.mapear(arv, "direito administrativo|controle", ["A-ATO"], "llm", "proposto")
    antes = {
        k: [(m.no_id, m.origem, m.status) for m in v]
        for k, v in arv.mapeamentos.items()
    }
    pais = pais_da(arv, "direito administrativo|x")
    mem.resolver_por_memoria(arv, regra("Controle"), "assunto", pais)
    mem.exemplos_aprovados(arv, "assunto", "M-DA", 5)
    mem.rejeicoes(arv)
    depois = {
        k: [(m.no_id, m.origem, m.status) for m in v]
        for k, v in arv.mapeamentos.items()
    }
    assert antes == depois
