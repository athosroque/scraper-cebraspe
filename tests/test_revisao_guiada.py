"""Leitura guiada da revisão: seções, sugestão por similaridade e Datasette (M10, KAN-89).

A sugestão é só apresentação (P79): nenhum teste aqui pode mudar o que é pendente
(P74) nem gravar na árvore (A27).
"""

import copy
import json
import sqlite3

import pytest
import sqlite_utils

from scripts.gerar_db_datasette import (
    METADATA_SUBDIR,
    VISOES_REVISAO,
    gerar_db,
    metadata_revisao,
)
from scripts.gerar_relatorio_revisao import gerar_relatorios, renderizar_edital
from src import mapeamento_revisao as mr
from src.arvore import ArvoreMestre, criar_no

PROVISORIAS = {"banco de dados": "M-TI", "performance": "M-TI"}


@pytest.fixture
def arvore():
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Tecnologia da Informação", None, id_override="M-TI")
    criar_no(arv, "assunto", "Banco de dados", "M-TI", id_override="A-BD")
    criar_no(arv, "assunto", "Redes de computadores", "M-TI", id_override="A-RC")
    criar_no(arv, "subassunto", "Controle de concorrência", "A-BD", id_override="S-CC")
    criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-DA")
    criar_no(arv, "assunto", "Contratos administrativos", "M-DA", id_override="A-CTR")
    criar_no(arv, "assunto", "Estrutura programática", "M-DA", id_override="A-EP")
    return arv


def _chunk(indice, materia, cargo, topicos):
    return {
        "chunk_index": indice,
        "cargo": f"cargo {cargo}" if cargo else None,
        "cargo_numero": cargo,
        "tipo_conhecimento": "especifico" if cargo else "basico",
        "nivel": "superior",
        "materia_chunk": materia,
        "materia_origem": "cabecalho",
        "taxonomia_extraida": {
            "materia": materia,
            "topicos": [{"nome": n, "subtopicos": s} for n, s in topicos],
        },
    }


def _edital():
    return {
        "edital": "guiado.pdf",
        "concurso": {"slug": "GU_25", "orgao": "GU", "ano": 2025},
        "cargos": [
            {"numero": 1, "nome": "Analista de TI", "nivel": "superior"},
            {"numero": 2, "nome": "Técnico de TI", "nivel": "superior"},
        ],
        "total_chunks": 3,
        "extraidos_com_sucesso": 3,
        "falhas": 0,
        "chunks_com_falha": [],
        "status_revisao_humana": "PENDENTE",
        "resultados": [
            _chunk(
                0,
                "BANCO DE DADOS",
                1,
                [
                    ("Controle de concorrência e recuperação de falhas", []),
                    ("Quantum computing", []),
                    ("Contratos administrativos", []),
                    ("Contratos de seguros", []),
                    ("Conceitos básicos", []),
                ],
            ),
            _chunk(
                1,
                "PERFORMANCE",
                2,
                [("Controle de concorrência e recuperação de falhas", [])],
            ),
            _chunk(
                2,
                "CONCEITOS GERAIS",
                None,
                [("Projeto de dados", ["Normalização"])],
            ),
        ],
    }


def _revisao(arvore, edital=None):
    edital = edital or _edital()
    linhas = mr.classificar_itens(edital, arvore, {})
    return linhas, mr.montar_revisao(
        linhas,
        arvore,
        provisorias=PROVISORIAS,
        filhos={},
        cargos=mr.cargos_por_chave(edital),
    )


def _por_chave(linhas):
    return {li["chave"]: li for li in linhas}


def test_decisao_de_bloco_destrava_os_filhos_e_usa_a_disciplina_do_cargo(arvore):
    _, rev = _revisao(arvore)
    bloco = _por_chave(rev)["banco de dados"]
    assert bloco["secao"] == "decisao_bloco"
    assert bloco["pai_provisorio"] is True
    assert bloco["itens_bloco"] == 5
    # título de bloco vira assunto (P72): nunca sugere a matéria
    assert all(s["no_nivel"] == "assunto" for s in bloco["sugestoes"])


def test_sugestao_top1_fica_na_disciplina_e_traz_score_caminho_e_comando(arvore):
    _, rev = _revisao(arvore)
    item = _por_chave(rev)[
        "banco de dados|controle de concorrencia e recuperacao de falhas"
    ]
    assert item["secao"] == "com_sugestao"
    assert item["sugestao_no"] == "S-CC"
    assert item["score"] >= mr.LIMIAR_SUGESTAO
    assert item["sugestao_caminho"] == (
        "Tecnologia da Informação › Banco de dados › Controle de concorrência"
    )
    assert item["disciplina_do_no"] == "Tecnologia da Informação"
    assert len(item["sugestoes"]) <= mr.TOP_K
    assert item["curar"] == (
        "python -m scripts.curar_arvore --mapear "
        "'banco de dados|controle de concorrencia e recuperacao de falhas:S-CC'"
    )


def test_sem_nome_parecido_o_item_e_realmente_novo_e_sem_comando(arvore):
    _, rev = _revisao(arvore)
    item = _por_chave(rev)["banco de dados|quantum computing"]
    assert item["secao"] == "novo"
    assert item["curar"] is None


def test_outra_disciplina_so_com_o_mesmo_nome(arvore):
    _, rev = _revisao(arvore)
    mesmo = _por_chave(rev)["banco de dados|contratos administrativos"]
    assert mesmo["sugestao_no"] == "A-CTR"
    assert mesmo["disciplina_do_no"] == "Direito Administrativo"
    parecido = _por_chave(rev)["banco de dados|contratos de seguros"]
    assert parecido["secao"] == "novo"  # "contratos" sozinho não atravessa disciplina


def test_nome_parecido_de_outra_disciplina_nao_atravessa(arvore):
    """ "Programação estruturada" não é "Estrutura programática" do orçamento."""
    edital = _edital()
    edital["resultados"][0]["taxonomia_extraida"]["topicos"] = [
        {"nome": "Programação estruturada", "subtopicos": []}
    ]
    _, rev = _revisao(arvore, edital)
    item = _por_chave(rev)["banco de dados|programacao estruturada"]
    assert all(s["no_id"] != "A-EP" for s in item["sugestoes"])


def test_nome_generico_nao_recebe_sugestao(arvore):
    _, rev = _revisao(arvore)
    item = _por_chave(rev)["banco de dados|conceitos basicos"]
    assert item["sugestoes"] == [] and item["secao"] == "novo"


def test_sem_pai_nem_disciplina_do_cargo_o_filho_fica_travado(arvore):
    _, rev = _revisao(arvore)
    ch = _por_chave(rev)
    bloco = ch["conceitos gerais"]
    assert bloco["secao"] == "decisao_bloco" and not bloco["pai_provisorio"]
    assert bloco["itens_bloco"] == 2 and bloco["travados"] == 2
    assunto = ch["conceitos gerais|projeto de dados"]
    sub = ch["conceitos gerais|projeto de dados|normalizacao"]
    assert assunto["travado"] and assunto["secao"] == "travado"
    assert sub["travado"] and sub["secao"] == "travado"
    assert assunto["sugestoes"] == [] and assunto["curar"] is None


def test_mesmo_item_em_dois_blocos_vira_um_grupo_com_os_dois_cargos(arvore):
    _, rev = _revisao(arvore)
    ch = _por_chave(rev)
    a = ch["banco de dados|controle de concorrencia e recuperacao de falhas"]
    b = ch["performance|controle de concorrencia e recuperacao de falhas"]
    assert a["grupo"] == b["grupo"] and a["repete"] == b["repete"] == 2
    assert a["representante"] and not b["representante"]
    assert a["cargos_grupo"] == ["Analista de TI", "Técnico de TI"]
    assert a["blocos_grupo"] == ["BANCO DE DADOS", "PERFORMANCE"]
    # a linha do dono leva um comando por chave do grupo
    assert len(a["curar_grupo"]) == 2
    assert (
        mr.contar_por_secao(rev)["com_sugestao"]
        < mr.contar_por_secao(rev, so_representantes=False)["com_sugestao"]
    )


def test_apresentacao_nao_muda_categoria_nem_pendentes_nem_arvore(arvore):
    antes = copy.deepcopy(arvore)
    linhas, rev = _revisao(arvore)
    assert [(l["chave"], l["categoria"]) for l in rev] == [
        (l["chave"], l["categoria"]) for l in linhas
    ]
    pendentes = {l["chave"] for l in linhas if l["categoria"] == "sem_equivalente"}
    assert pendentes == {
        l["chave"] for l in rev if l["secao"] not in ("resolvido", "proposta")
    }
    assert arvore.mapeamentos == antes.mapeamentos
    assert arvore.nos == antes.nos


def test_gerar_db_acrescenta_colunas_visoes_e_metadata(tmp_path, arvore, monkeypatch):
    (tmp_path / "x.json").write_text(json.dumps(_edital()), encoding="utf-8")
    monkeypatch.setattr("scripts.gerar_db_datasette.arv_mod.carregar", lambda: arvore)
    monkeypatch.setattr(
        "scripts.gerar_db_datasette.mapeamento_revisao.contexto_revisao",
        lambda *a, **k: {"provisorias": PROVISORIAS, "filhos": {}},
    )
    db = sqlite_utils.Database(gerar_db(tmp_path))
    colunas = {c.name for c in db["mapeamento_itens"].columns}
    assert set(mr.COLUNAS_REVISAO) <= colunas
    linha = next(
        db["mapeamento_itens"].rows_where(
            "chave = ?",
            ["banco de dados|controle de concorrencia e recuperacao de falhas"],
        )
    )
    assert (linha["secao"], linha["sugestao_no"], linha["representante"]) == (
        "com_sugestao",
        "S-CC",
        1,
    )
    assert linha["disciplina"] == "BANCO DE DADOS"  # título do bloco, compatibilidade
    assert linha["disciplina_do_no"] == "Tecnologia da Informação"
    assert "Analista de TI" in linha["cargos"] and "Técnico de TI" in linha["cargos"]
    assert "--mapear" in linha["curar_arvore"]
    assert "S-CC" in linha["sugestoes"]
    # visões: só o representante do grupo aparece
    for nome in VISOES_REVISAO:
        assert nome in db.view_names()
    con = sqlite3.connect(tmp_path / "revisao.db")
    sugestoes = con.execute("SELECT item FROM revisao_com_sugestao").fetchall()
    assert len(sugestoes) == len({s[0] for s in sugestoes})
    decisoes = con.execute(
        "SELECT titulo_do_bloco, itens_bloco FROM revisao_decisoes_de_bloco "
        "ORDER BY itens_bloco DESC"
    ).fetchall()
    # BANCO DE DADOS casa por nome com o assunto homônimo (o passo o mapeia): sai da lista
    assert ("CONCEITOS GERAIS", 2) in decisoes
    assert all(d[0] != "BANCO DE DADOS" for d in decisoes)
    assert (
        con.execute("SELECT COUNT(*) FROM revisao_travados_pelo_pai").fetchone()[0] == 2
    )
    # metadata fora do glob `*.json` dos editais (senão viraria "edital")
    assert (tmp_path / METADATA_SUBDIR / "metadata.json").exists()
    assert not (tmp_path / "metadata.json").exists()


def test_metadata_tem_consultas_salvas_com_parametro():
    consultas = metadata_revisao()["databases"]["revisao"]["queries"]
    assert {"pendentes_por_bloco", "sugestoes_altas", "travados_pelo_pai"} <= set(
        consultas
    )
    assert ":minimo" in consultas["sugestoes_altas"]["sql"]


def test_relatorio_mostra_leitura_guiada_com_comando_escapado(arvore):
    edital = _edital()
    auditoria = {
        "chunks": [{"chunk_index": i, "texto_enviado_llm": "t"} for i in range(3)]
    }
    linhas, rev = _revisao(arvore, edital)
    html = renderizar_edital(edital, auditoria, None, None, linhas, rev)
    assert "Leitura guiada" in html
    assert "decisões de bloco" in html and "travados pelo pai" in html
    assert "Decisões de bloco (3)" in html
    assert "curar_arvore --mapear" in html and "class='copiar'" in html
    # item repetido aparece numa linha só, com o aviso
    assert html.count("repete em 2 blocos") == 1
    assert "<script>alert" not in html


def test_relatorio_sem_revisao_continua_no_formato_antigo(arvore):
    edital = _edital()
    auditoria = {
        "chunks": [{"chunk_index": i, "texto_enviado_llm": "t"} for i in range(3)]
    }
    linhas = mr.classificar_itens(edital, arvore, {})
    html = renderizar_edital(edital, auditoria, None, None, linhas)
    assert "Leitura guiada" not in html


def test_gerar_relatorios_integra_a_leitura_guiada(tmp_path, arvore, monkeypatch):
    edital = _edital()
    (tmp_path / "x.json").write_text(json.dumps(edital), encoding="utf-8")
    auditoria = {
        "chunks": [{"chunk_index": i, "texto_enviado_llm": "t"} for i in range(3)]
    }
    (tmp_path / "x.auditoria.json").write_text(json.dumps(auditoria), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.gerar_relatorio_revisao.arv_mod.carregar", lambda: arvore
    )
    monkeypatch.setattr(
        "scripts.gerar_relatorio_revisao.mapeamento_revisao.contexto_revisao",
        lambda *a, **k: {"provisorias": PROVISORIAS, "filhos": {}},
    )
    saida = gerar_relatorios(tmp_path)
    html = (saida / "x.html").read_text(encoding="utf-8")
    assert "Leitura guiada" in html
