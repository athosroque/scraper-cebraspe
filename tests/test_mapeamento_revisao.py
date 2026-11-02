"""Origem do mapeamento por item de edital (src/mapeamento_revisao.py)."""

import json

import pytest
import sqlite_utils

from scripts.gerar_db_datasette import gerar_db
from scripts.gerar_relatorio_revisao import gerar_relatorios, renderizar_edital
from src import mapeamento_revisao as mr
from src.arvore import ArvoreMestre, criar_no, mapear

DISCIPLINAS = ["Direito Administrativo"]


@pytest.fixture
def arvore():
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-DA")
    criar_no(arv, "assunto", "Atos administrativos", "M-DA", id_override="A-ATO")
    criar_no(arv, "assunto", "Licitações", "M-DA", id_override="A-LIC")
    criar_no(arv, "assunto", "Poderes", "M-DA", id_override="A-POD")
    criar_no(arv, "subassunto", "Anulação", "A-ATO", id_override="S-ANU")
    mapear(arv, "direito administrativo", ["M-DA"], origem="regra", status="aprovado")
    mapear(
        arv,
        "direito administrativo|atos administrativos",
        ["A-ATO"],
        origem="humano",
        status="aprovado",
    )
    mapear(
        arv,
        "direito administrativo|licitacoes",
        ["A-LIC"],
        origem="regra",
        status="aprovado",
    )
    mapear(
        arv,
        "direito administrativo|poderes administrativos",
        ["A-POD"],
        origem="llm",
        status="proposto",
    )
    return arv


def _edital(topicos):
    return {
        "edital": "x.pdf",
        "concurso": {"slug": "XX_25", "orgao": "XX", "ano": 2025},
        "cargos": [],
        "total_chunks": 1,
        "extraidos_com_sucesso": 1,
        "falhas": 0,
        "chunks_com_falha": [],
        "status_revisao_humana": "PENDENTE",
        "resultados": [
            {
                "chunk_index": 0,
                "cargo": "C",
                "materia_chunk": "Direito Administrativo",
                "materia_origem": "cabecalho",
                "taxonomia_extraida": {
                    "materia": "Direito Administrativo",
                    "topicos": topicos,
                },
            }
        ],
    }


TOPICOS = [
    {"nome": "Atos administrativos", "subtopicos": ["Anulação", "Revogação"]},
    {"nome": "Licitações", "subtopicos": []},
    {"nome": "Poderes administrativos", "subtopicos": []},
    {"nome": "Assunto inédito", "subtopicos": ["Sub inédito"]},
]
PROPOSTOS = {
    "direito administrativo|poderes administrativos": {
        "no": "A-POD",
        "confianca": "alta",
        "justificativa": "mesmo tema <b>x</b>",
    }
}


def _por_item(linhas):
    return {l["item"]: l for l in linhas}


def test_classifica_as_cinco_categorias(arvore):
    linhas = mr.classificar_itens(_edital(TOPICOS), arvore, PROPOSTOS, DISCIPLINAS)
    it = _por_item(linhas)
    assert it["Direito Administrativo"]["categoria"] == "auto"
    assert it["Atos administrativos"]["categoria"] == "dono"
    assert it["Licitações"]["categoria"] == "auto"
    assert it["Anulação"]["categoria"] == "regra_nome"
    assert it["Anulação"]["no_id"] == "S-ANU"
    assert it["Revogação"]["categoria"] == "sem_equivalente"
    assert it["Revogação"]["status"] == "sem_equivalente"
    p = it["Poderes administrativos"]
    assert (p["categoria"], p["status"], p["origem"]) == ("proposta", "proposto", "llm")
    assert p["confianca"] == "alta"
    assert "mesmo tema" in p["justificativa"]
    assert p["no_caminho"] == "Direito Administrativo › Poderes"
    assert it["Assunto inédito"]["categoria"] == "sem_equivalente"
    assert it["Sub inédito"]["categoria"] == "sem_equivalente"
    assert mr.contar_por_categoria(linhas) == {
        "auto": 2,
        "regra_nome": 1,
        "dono": 1,
        "proposta": 1,
        "sem_equivalente": 3,
    }


def test_proposta_sem_cache_fica_sem_confianca(arvore):
    linhas = mr.classificar_itens(_edital(TOPICOS), arvore, {}, DISCIPLINAS)
    p = _por_item(linhas)["Poderes administrativos"]
    assert p["categoria"] == "proposta"
    assert p["confianca"] is None and p["justificativa"] is None


def test_cache_ausente_ou_corrompido_vira_vazio(tmp_path):
    assert mr.carregar_cache_propostos(tmp_path / "nao_existe.json") == {}
    ruim = tmp_path / "c.json"
    ruim.write_text("{quebrado", encoding="utf-8")
    assert mr.carregar_cache_propostos(ruim) == {}
    ruim.write_text("[1, 2]", encoding="utf-8")
    assert mr.carregar_cache_propostos(ruim) == {}
    ruim.write_text(json.dumps({"propostos": {"a": {"no": "X"}}}), encoding="utf-8")
    assert mr.carregar_cache_propostos(ruim) == {"a": {"no": "X"}}


def test_relatorio_mostra_quadro_confianca_e_justificativa_escapada(arvore):
    resultado = _edital(TOPICOS)
    linhas = mr.classificar_itens(resultado, arvore, PROPOSTOS, DISCIPLINAS)
    auditoria = {"chunks": []}
    novidades = {
        "propostas": [
            {
                "nivel": "assunto",
                "item": "Poderes administrativos",
                "disciplina": "Direito Administrativo",
                "no_id": "A-POD",
                "no_caminho": "Direito Administrativo › Poderes",
            }
        ],
        "total_propostas": 1,
    }
    html = renderizar_edital(resultado, auditoria, None, novidades, linhas)
    assert "De onde veio cada mapeamento" in html
    assert "automático (regra/memória)" in html
    assert "proposto pela IA (a conferir)" in html
    assert "sem equivalente (a decidir)" in html
    assert "<td>alta</td>" in html
    assert "mesmo tema &lt;b&gt;x&lt;/b&gt;" in html
    assert "Nada a decidir" not in html


def test_relatorio_sem_pendencia_mostra_nada_a_decidir(arvore):
    resultado = _edital([TOPICOS[0], TOPICOS[1]][:2])
    resultado["resultados"][0]["taxonomia_extraida"]["topicos"][0]["subtopicos"] = [
        "Anulação"
    ]
    linhas = mr.classificar_itens(resultado, arvore, {}, DISCIPLINAS)
    html = renderizar_edital(resultado, {"chunks": []}, None, {}, linhas)
    assert "nada-a-decidir" in html and "Nada a decidir" in html


def test_relatorio_sem_mapeamento_nao_quebra(arvore):
    html = renderizar_edital(_edital(TOPICOS), {"chunks": []}, None, {}, None)
    assert "De onde veio" not in html


def _montar_dir(tmp_path, auditoria=True):
    (tmp_path / "x.json").write_text(
        json.dumps(_edital(TOPICOS), ensure_ascii=False), encoding="utf-8"
    )
    if auditoria:
        (tmp_path / "x.auditoria.json").write_text(
            json.dumps({"edital": "x.pdf", "chunks": []}), encoding="utf-8"
        )


def test_gerar_db_cria_tabela_mapeamento_itens(tmp_path, arvore, monkeypatch):
    _montar_dir(tmp_path, auditoria=False)
    monkeypatch.setattr("scripts.gerar_db_datasette.arv_mod.carregar", lambda: arvore)
    monkeypatch.setattr(
        mr, "carregar_cache_propostos", lambda path=mr.CACHE_PADRAO: PROPOSTOS
    )
    monkeypatch.setattr(mr, "carregar_disciplinas", lambda: DISCIPLINAS)
    db = sqlite_utils.Database(gerar_db(tmp_path))
    linhas = list(db["mapeamento_itens"].rows_where("status = ?", ["proposto"]))
    assert len(linhas) == 1 and linhas[0]["confianca"] == "alta"
    assert {c.name for c in db["mapeamento_itens"].columns} >= set(mr.COLUNAS_TABELA)


def test_gerar_db_tolera_arvore_quebrada(tmp_path, monkeypatch):
    _montar_dir(tmp_path, auditoria=False)

    def quebra():
        raise ValueError("árvore corrompida")

    monkeypatch.setattr("scripts.gerar_db_datasette.arv_mod.carregar", quebra)
    db = sqlite_utils.Database(gerar_db(tmp_path))
    assert db["mapeamento_itens"].exists() and db["mapeamento_itens"].count == 0


def test_gerar_relatorios_integra_quadro(tmp_path, arvore, monkeypatch):
    _montar_dir(tmp_path)
    monkeypatch.setattr(
        "scripts.gerar_relatorio_revisao.arv_mod.carregar", lambda: arvore
    )
    monkeypatch.setattr(mr, "carregar_disciplinas", lambda: DISCIPLINAS)
    saida = gerar_relatorios(tmp_path, novidades_fn=lambda r: {})
    assert "De onde veio cada mapeamento" in (saida / "x.html").read_text("utf-8")
