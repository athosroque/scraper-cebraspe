"""Novidades de um edital contra a árvore mestre (src/novidades_edital.py)."""

import json

import pytest

from src.arvore import ArvoreMestre, criar_no, mapear
from src.canonico import arvore_apos_passo
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
        "titulos_sem_destino": [],
        "total_titulos_sem_destino": 0,
        "total_itens_travados": 0,
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


def _apos_passo(arvore, edital, tmp_path):
    """Árvore com o passo determinístico aplicado, como o relatório a recebe (M1)."""
    (tmp_path / "x.json").write_text(json.dumps(edital), encoding="utf-8")
    copia, _ = arvore_apos_passo(tmp_path, arvore)
    return copia


def test_normalizacao_acento_caixa_e_nocoes(arvore, tmp_path):
    edital = _edital(
        "NOÇÕES DE DIREITO ADMINISTRATIVO",
        "ATOS ADMINISTRATIVOS",
        ["ANULACAO E REVOGACAO"],
    )
    r = novidades_do_edital(edital, DISCIPLINAS, _apos_passo(arvore, edital, tmp_path))
    assert r["total_itens_novos"] == 0


def test_sem_o_passo_a_equivalencia_de_nome_nao_conta(arvore):
    """M1: o relatório não tem critério de nome próprio; só vale o que está
    aprovado na árvore recebida (o passo grava ou a cópia em memória)."""
    edital = _edital(
        "NOÇÕES DE DIREITO ADMINISTRATIVO",
        "ATOS ADMINISTRATIVOS",
        ["ANULACAO E REVOGACAO"],
    )
    r = novidades_do_edital(edital, DISCIPLINAS, arvore)
    assert r["total_itens_novos"] == 3


def test_nome_igual_a_no_filho_unico_nao_e_novidade(arvore, tmp_path):
    """O passo mapeia item que casa com um único nó-filho de mesmo nome (KAN-97, M14,
    que tirou o caso do SEFA_PR_25 da lista de pendentes); o relatório não o lista."""
    criar_no(arvore, "subassunto", "Convalidação", "A-ATO", id_override="S-CON")
    edital = _edital("Direito Administrativo", "Atos administrativos", ["Convalidação"])
    r = novidades_do_edital(edital, DISCIPLINAS, _apos_passo(arvore, edital, tmp_path))
    assert r["assuntos_novos"] == []


def test_titulo_de_bloco_que_e_assunto_nao_e_disciplina(arvore, tmp_path):
    edital = _edital("Atos Administrativos", "Anulação", [])
    r = novidades_do_edital(edital, DISCIPLINAS, _apos_passo(arvore, edital, tmp_path))
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


def test_titulo_sem_destino_conta_itens_travados(arvore):
    r = novidades_do_edital(
        _edital("Física Quântica", "Átomos", ["Spin", "Quark"]), DISCIPLINAS, arvore
    )
    assert r["titulos_sem_destino"] == [
        {"titulo": "Física Quântica", "chunks": [0], "itens_travados": 3}
    ]
    assert r["total_titulos_sem_destino"] == 1
    assert r["total_itens_travados"] == 3
    # chaves antigas continuam
    assert r["disciplinas_novas"] == ["Física Quântica"]
    assert r["total_itens_novos"] == 4  # título + assunto + 2 subassuntos


def test_titulos_ordenados_por_itens_travados(arvore):
    base = _edital("Pequeno", "A1", [])
    grande = _edital("Grande", "B1", ["x", "y", "z"])
    base["resultados"] += grande["resultados"]
    r = novidades_do_edital(base, DISCIPLINAS, arvore)
    assert [t["titulo"] for t in r["titulos_sem_destino"]] == ["Grande", "Pequeno"]
    assert r["total_itens_travados"] == 5
    assert r["disciplinas_novas"] == ["Pequeno", "Grande"]  # ordem de aparição


def test_titulo_conhecido_nao_trava_nada(arvore):
    r = novidades_do_edital(
        _edital("Direito Administrativo", "Licitações", ["Dispensa"]),
        DISCIPLINAS,
        arvore,
    )
    assert r["titulos_sem_destino"] == []
    assert r["total_itens_travados"] == 0
