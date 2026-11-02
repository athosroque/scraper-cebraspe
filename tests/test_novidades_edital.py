"""Novidades de um edital contra a árvore mestre (src/novidades_edital.py)."""

import pytest

from src.arvore import ArvoreMestre, criar_no, mapear
from src.novidades_edital import novidades_do_edital


@pytest.fixture
def arvore():
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-DA")
    criar_no(arv, "assunto", "Atos administrativos", "M-DA", id_override="A-ATO")
    criar_no(arv, "subassunto", "Anulação e revogação", "A-ATO", id_override="S-ANU")
    mapear(arv, "direito administrativo", ["M-DA"])
    mapear(arv, "direito administrativo|atos administrativos", ["A-ATO"])
    mapear(
        arv,
        "direito administrativo|atos administrativos|anulacao e revogacao",
        ["S-ANU"],
    )
    return arv


DISCIPLINAS = ["Direito Administrativo"]


def _edital(materia, topico, subs):
    return {
        "edital": "x.pdf",
        "concurso": {"slug": "XX_25", "orgao": "XX", "ano": 2025},
        "cargos": [],
        "resultados": [
            {
                "chunk_index": 0,
                "materia_chunk": materia,
                "materia_origem": "cabecalho",
                "taxonomia_extraida": {
                    "materia": materia,
                    "topicos": [{"nome": topico, "subtopicos": subs}],
                },
            }
        ],
    }


def test_tudo_conhecido(arvore):
    r = novidades_do_edital(
        _edital(
            "Direito Administrativo", "Atos administrativos", ["Anulação e revogação"]
        ),
        DISCIPLINAS,
        arvore,
    )
    assert r == {
        "disciplinas_novas": [],
        "assuntos_novos": [],
        "total_disciplinas": 0,
        "total_assuntos": 0,
        "total_itens_novos": 0,
        "propostas": [],
        "total_propostas": 0,
    }


def test_disciplina_nova(arvore):
    r = novidades_do_edital(
        _edital("Física Quântica", "Átomos", ["Spin"]), DISCIPLINAS, arvore
    )
    assert r["disciplinas_novas"] == ["Física Quântica"]
    assert r["assuntos_novos"] == [
        {"disciplina": "Física Quântica", "assunto": "Átomos", "subassuntos": ["Spin"]}
    ]
    assert (r["total_disciplinas"], r["total_assuntos"], r["total_itens_novos"]) == (
        1,
        1,
        3,
    )


def test_assunto_novo_em_disciplina_conhecida(arvore):
    r = novidades_do_edital(
        _edital("Direito Administrativo", "Licitações", ["Dispensa"]),
        DISCIPLINAS,
        arvore,
    )
    assert r["disciplinas_novas"] == []
    assert r["assuntos_novos"][0]["assunto"] == "Licitações"
    assert r["total_itens_novos"] == 2


def test_subassunto_novo_em_assunto_conhecido(arvore):
    r = novidades_do_edital(
        _edital(
            "Direito Administrativo",
            "Atos administrativos",
            ["Anulação e revogação", "Convalidação"],
        ),
        DISCIPLINAS,
        arvore,
    )
    assert r["assuntos_novos"] == [
        {
            "disciplina": "Direito Administrativo",
            "assunto": "Atos administrativos",
            "subassuntos": ["Convalidação"],
        }
    ]
    assert r["total_itens_novos"] == 1


def test_normalizacao_acento_caixa_e_nocoes(arvore):
    r = novidades_do_edital(
        _edital(
            "NOÇÕES DE DIREITO ADMINISTRATIVO",
            "ATOS ADMINISTRATIVOS",
            ["ANULACAO E REVOGACAO"],
        ),
        DISCIPLINAS,
        arvore,
    )
    assert r["total_itens_novos"] == 0


def test_titulo_de_bloco_que_e_assunto_nao_e_disciplina(arvore):
    r = novidades_do_edital(
        _edital("Atos Administrativos", "Anulação", []), DISCIPLINAS, arvore
    )
    assert r["disciplinas_novas"] == []


@pytest.fixture
def arvore_com_propostas(arvore):
    criar_no(arvore, "assunto", "Licitação pública", "M-DA", id_override="A-LIC")
    criar_no(
        arvore, "subassunto", "Dispensa de licitação", "A-LIC", id_override="S-DIS"
    )
    mapear(
        arvore,
        "direito administrativo|licitacoes",
        ["A-LIC"],
        origem="llm",
        status="proposto",
    )
    mapear(
        arvore,
        "direito administrativo|atos administrativos|convalidacao",
        ["S-DIS"],
        origem="llm",
        status="proposto",
    )
    mapear(arvore, "fisica", ["M-DA"], origem="llm", status="proposto")
    return arvore


def test_assunto_proposto_nao_e_novo(arvore_com_propostas):
    r = novidades_do_edital(
        _edital("Direito Administrativo", "Licitações", ["Dispensa"]),
        DISCIPLINAS,
        arvore_com_propostas,
    )
    assert r["total_itens_novos"] == 1  # só o subassunto; o assunto não é novo
    assert r["total_propostas"] == 1
    p = r["propostas"][0]
    assert (p["nivel"], p["item"], p["no_id"]) == ("assunto", "Licitações", "A-LIC")
    assert p["no_caminho"] == "Direito Administrativo › Licitação pública"
    assert "confianca" not in p


def test_assunto_proposto_so_conta_subassunto_realmente_novo(arvore_com_propostas):
    r = novidades_do_edital(
        _edital("Direito Administrativo", "Licitações", ["Dispensa"]),
        DISCIPLINAS,
        arvore_com_propostas,
    )
    assert r["total_disciplinas"] == 0
    assert r["total_itens_novos"] == 1  # só o subassunto "Dispensa"
    assert r["assuntos_novos"][0]["subassuntos"] == ["Dispensa"]


def test_subassunto_proposto(arvore_com_propostas):
    r = novidades_do_edital(
        _edital("Direito Administrativo", "Atos administrativos", ["Convalidação"]),
        DISCIPLINAS,
        arvore_com_propostas,
    )
    assert r["assuntos_novos"] == []
    assert r["total_itens_novos"] == 0
    assert r["propostas"] == [
        {
            "nivel": "subassunto",
            "item": "Convalidação",
            "disciplina": "Direito Administrativo",
            "assunto": "Atos administrativos",
            "no_id": "S-DIS",
            "no_caminho": "Direito Administrativo › Licitação pública › Dispensa de licitação",
        }
    ]


def test_disciplina_proposta_nao_e_nova(arvore_com_propostas):
    r = novidades_do_edital(
        _edital("Física", "Átomos", []), DISCIPLINAS, arvore_com_propostas
    )
    assert r["disciplinas_novas"] == []
    assert r["propostas"][0]["nivel"] == "disciplina"
    assert r["propostas"][0]["no_caminho"] == "Direito Administrativo"


def test_proposta_rejeitada_continua_nova(arvore):
    mapear(arvore, "fisica", ["M-DA"], origem="llm", status="rejeitado")
    r = novidades_do_edital(_edital("Física", "Átomos", []), DISCIPLINAS, arvore)
    assert r["disciplinas_novas"] == ["Física"]
    assert r["propostas"] == []


def test_aprovado_prevalece_sobre_proposto(arvore):
    mapear(arvore, "direito administrativo|licitacoes", ["A-ATO"], status="aprovado")
    mapear(
        arvore,
        "direito administrativo|licitacoes",
        ["M-DA"],
        origem="llm",
        status="proposto",
    )
    r = novidades_do_edital(
        _edital("Direito Administrativo", "Licitações", []), DISCIPLINAS, arvore
    )
    assert r["propostas"] == []
    assert r["total_itens_novos"] == 0
