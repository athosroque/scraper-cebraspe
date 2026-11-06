"""Origem do mapeamento por item de edital (src/mapeamento_revisao.py)."""

import json
from pathlib import Path

import pytest
import sqlite_utils

from scripts.gerar_db_datasette import gerar_db
from scripts.gerar_relatorio_revisao import gerar_relatorios, renderizar_edital
from src import arvore as arv_mod
from src import canonico
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


def test_classifica_as_quatro_categorias(arvore):
    linhas = mr.classificar_itens(_edital(TOPICOS), arvore, PROPOSTOS, DISCIPLINAS)
    it = _por_item(linhas)
    assert it["Direito Administrativo"]["categoria"] == "auto"
    assert it["Atos administrativos"]["categoria"] == "dono"
    assert it["Licitações"]["categoria"] == "auto"
    # M1: nome igual ao de um nó-filho não resolve nada sem mapeamento aprovado.
    assert it["Anulação"]["categoria"] == "sem_equivalente"
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
        "dono": 1,
        "proposta": 1,
        "sem_equivalente": 4,
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
    assert "proposto pela IA ou por regra (a conferir)" in html
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
    saida = gerar_relatorios(tmp_path, novidades_fn=lambda r: {})
    assert "De onde veio cada mapeamento" in (saida / "x.html").read_text("utf-8")


# M1 (Etapa 5B.4): o relatório reporta exatamente o que o passo determinístico faria.


def _pendentes_do_relatorio(linhas):
    """Chaves sem destino aprovado, na visão do relatório."""
    return {
        l["chave"] for l in linhas if l["categoria"] in ("proposta", "sem_equivalente")
    }


def _sem_aprovado(arvore, linhas):
    return {
        l["chave"]
        for l in linhas
        if not any(
            m.status == "aprovado" for m in arvore.mapeamentos.get(l["chave"], [])
        )
    }


def test_relatorio_depois_do_passo_mapeia_o_que_o_passo_mapeia(tmp_path, arvore):
    edital = _edital(
        [
            {"nome": "ATOS ADMINISTRATIVOS", "subtopicos": ["Anulação"]},
            {"nome": "Licitações", "subtopicos": []},
        ]
    )
    edital["resultados"][0]["materia_chunk"] = "NOÇÕES DE DIREITO ADMINISTRATIVO"
    edital["resultados"][0]["taxonomia_extraida"]["materia"] = (
        "NOÇÕES DE DIREITO ADMINISTRATIVO"
    )
    (tmp_path / "x.json").write_text(json.dumps(edital), encoding="utf-8")
    antes = mr.classificar_itens(edital, arvore, {})
    sim, res = canonico.arvore_apos_passo(tmp_path, arvore)
    depois = mr.classificar_itens(edital, sim, {})
    it_antes, it_depois = _por_item(antes), _por_item(depois)
    # ATOS ADMINISTRATIVOS casa com um item já aprovado (mesma regra, mesmo pai).
    assert it_antes["ATOS ADMINISTRATIVOS"]["categoria"] == "sem_equivalente"
    assert it_depois["ATOS ADMINISTRATIVOS"]["categoria"] == "auto"
    # Anulação só tem nó-filho de mesmo nome: o ramo do filho único (KAN-97) a mapeia,
    # depois que ATOS ADMINISTRATIVOS (o pai) resolve na mesma execução.
    assert it_depois["Anulação"]["categoria"] == "auto"
    assert res.por_filho == 1
    assert _pendentes_do_relatorio(depois) == set(res.chaves_pendentes) | {
        l["chave"] for l in depois if l["categoria"] == "proposta"
    }
    # a árvore recebida não muda
    assert "direito administrativo|atos administrativos" in arvore.mapeamentos
    assert not any(
        m.origem == "regra" and m.status == "aprovado"
        for m in arvore.mapeamentos.get("direito administrativo|anulacao", [])
    )


def test_pendentes_do_relatorio_igual_aos_do_passo_nos_editais_reais():
    """Para cada `<edital>.json` de `revisao_piloto/` com a árvore real: o conjunto
    de pendentes do relatório (cópia após o passo) é o dos itens sem mapeamento
    aprovado depois de `mapear_novos_itens(gravar=False)`. Só leitura."""
    from src.stats_writer import listar_jsons_edital

    revisao_dir = Path(__file__).resolve().parent.parent / "revisao_piloto"
    jsons = listar_jsons_edital(revisao_dir)
    if not jsons or not arv_mod.ARVORE_PADRAO.exists():
        pytest.skip("sem revisao_piloto ou árvore local")
    arvore = arv_mod.carregar()
    sim, res = canonico.arvore_apos_passo(revisao_dir, arvore)
    referencia = arv_mod.carregar()
    res_ref = canonico.mapear_novos_itens(
        revisao_dir, gravar=False, arvore_mem=referencia
    )
    assert res_ref.chaves_pendentes == res.chaves_pendentes
    for caminho in jsons:
        resultado = json.loads(caminho.read_text(encoding="utf-8"))
        linhas = mr.classificar_itens(resultado, sim, {})
        assert _pendentes_do_relatorio(linhas) == _sem_aprovado(referencia, linhas), (
            caminho.name
        )
        # o que o passo deixou pendente (sem entrada) está sempre no relatório
        assert set(res.chaves_pendentes) & {l["chave"] for l in linhas} <= (
            _pendentes_do_relatorio(linhas)
        )


def test_gerar_db_usa_a_arvore_apos_o_passo(tmp_path, arvore, monkeypatch):
    edital = _edital([{"nome": "Licitações", "subtopicos": []}])
    edital["resultados"][0]["materia_chunk"] = "NOÇÕES DE DIREITO ADMINISTRATIVO"
    edital["resultados"][0]["taxonomia_extraida"]["materia"] = (
        "NOÇÕES DE DIREITO ADMINISTRATIVO"
    )
    (tmp_path / "x.json").write_text(json.dumps(edital), encoding="utf-8")
    monkeypatch.setattr("scripts.gerar_db_datasette.arv_mod.carregar", lambda: arvore)
    db = sqlite_utils.Database(gerar_db(tmp_path))
    linha = next(db["mapeamento_itens"].rows_where("nivel = ?", ["disciplina"]))
    assert (linha["status"], linha["origem"], linha["no_id"]) == (
        "aprovado",
        "regra",
        "M-DA",
    )


def test_gerar_relatorios_nao_mostra_como_novo_o_que_o_passo_mapeia(
    tmp_path, arvore, monkeypatch
):
    edital = _edital([{"nome": "Licitações", "subtopicos": []}])
    edital["resultados"][0]["materia_chunk"] = "NOÇÕES DE DIREITO ADMINISTRATIVO"
    edital["resultados"][0]["taxonomia_extraida"]["materia"] = (
        "NOÇÕES DE DIREITO ADMINISTRATIVO"
    )
    (tmp_path / "x.json").write_text(json.dumps(edital), encoding="utf-8")
    (tmp_path / "x.auditoria.json").write_text(
        json.dumps({"edital": "x.pdf", "chunks": []}), encoding="utf-8"
    )
    monkeypatch.setattr(
        "scripts.gerar_relatorio_revisao.arv_mod.carregar", lambda: arvore
    )
    html = (gerar_relatorios(tmp_path) / "x.html").read_text("utf-8")
    assert "novo-tag'>DISCIPLINA" not in html
    assert "Nada a decidir" in html
