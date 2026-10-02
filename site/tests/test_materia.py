"""Painel da matéria (5F.10): ranking por subassunto via `fn_prova_cobra`."""

import re

import pytest
from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def _consulta(sql, params=()):
    with stats_writer.conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _id_lp():
    return _consulta(
        "SELECT id FROM vw_no_caminho WHERE nivel = 'materia' "
        "AND nome = 'LÍNGUA PORTUGUESA'"
    )[0][0]


def test_painel_lista_top_igual_fn_prova_cobra(cliente):
    materia = _id_lp()
    esperado = _consulta(
        """
        SELECT no_id FROM fn_prova_cobra('subassunto', p_nivel => 'medio')
        WHERE materia_id = %s AND (questoes > 0 OR anuladas > 0)
        ORDER BY questoes DESC, pct_medio_por_concurso DESC, no_nome LIMIT 15
        """,
        (materia,),
    )
    r = cliente.get(f"/materias/{materia}?nivel=medio&cargo_numero=")
    assert r.status_code == 200
    assert "LÍNGUA PORTUGUESA" in r.text
    ids = re.findall(r'href="/questoes\?no_id=((?!M-)[^&"]+)&amp;', r.text)
    assert ids == [e[0] for e in esperado]
    assert "anuladas=excluir" not in r.text
    assert "nivel=medio" in r.text
    assert "Resolver questões desta matéria" in r.text


def test_no_que_nao_e_materia_da_404(cliente):
    assunto = _consulta("SELECT id FROM vw_no_caminho WHERE nivel = 'assunto' LIMIT 1")
    assert cliente.get(f"/materias/{assunto[0][0]}").status_code == 404
    assert cliente.get("/materias/nao-existe").status_code == 404


def test_reconciliacao_ranking_com_total_independente_lp(cliente):
    """O total mostrado vem da fn_prova_cobra no nível matéria, não do próprio ranking."""
    materia = _id_lp()
    total = _consulta(
        "SELECT questoes FROM fn_prova_cobra('materia') WHERE no_id = %s", (materia,)
    )[0][0]
    r = cliente.get(f"/materias/{materia}")
    assert r.status_code == 200
    texto = re.sub(r"\s+", " ", r.text)
    m = re.search(r"somam ([\d.]+) (?:para|de) ([\d.]+) questões", texto)
    assert m is not None, "Texto de reconciliação não encontrado"
    soma, total_pagina = (int(x.replace(".", "")) for x in m.groups())
    assert total_pagina == total
    assert soma > 0
    assert "Anuladas ficam fora" not in texto


# -- API de matérias e busca (5F.7) --
def test_api_materias_lp_com_139_distintas(cliente):
    r = cliente.get("/api/v1/materias")
    assert r.status_code == 200
    lp = next(m for m in r.json() if m["nome"] == "LÍNGUA PORTUGUESA")
    assert lp["total_questoes"] == 139
    assert lp["nome_de_cargo"] is False
    assert 0 < lp["pct_incidencia"] < 100


def test_api_materia_detalhe_bate_com_fn_prova_cobra(cliente):
    materia = _id_lp()
    esperado = _consulta(
        """
        SELECT no_id, questoes FROM fn_prova_cobra('subassunto')
        WHERE materia_id = %s AND (questoes > 0 OR anuladas > 0)
        ORDER BY questoes DESC, pct_medio_por_concurso DESC, no_nome LIMIT 15
        """,
        (materia,),
    )
    r = cliente.get(f"/api/v1/materias/{materia}")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total_questoes"] == 139
    assert [(s["no_id"], s["questoes"]) for s in corpo["top_subassuntos"]] == [
        tuple(e) for e in esperado
    ]


def test_api_materia_404(cliente):
    assunto = _consulta("SELECT id FROM vw_no_caminho WHERE nivel = 'assunto' LIMIT 1")
    assert cliente.get(f"/api/v1/materias/{assunto[0][0]}").status_code == 404
    assert cliente.get("/api/v1/materias/nao-existe").status_code == 404


def test_api_busca_sem_acento_e_caixa(cliente):
    r = cliente.get("/api/v1/busca", params={"q": "LINGUA portuguesa"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo[0]["nome"] == "LÍNGUA PORTUGUESA"
    assert cliente.get("/api/v1/busca", params={"q": "a"}).status_code == 422
    assert len(cliente.get("/api/v1/busca", params={"q": "de"}).json()) == 20


def test_inicio_mostra_incidencia(cliente):
    assert "% das questões" in cliente.get("/").text
