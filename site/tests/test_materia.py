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
        WHERE materia_id = %s AND questoes > 0
        ORDER BY questoes DESC, pct_medio_por_concurso DESC, no_nome LIMIT 15
        """,
        (materia,),
    )
    r = cliente.get(f"/materias/{materia}?nivel=medio&cargo_numero=")
    assert r.status_code == 200
    assert "LÍNGUA PORTUGUESA" in r.text
    ids = re.findall(r'href="/questoes\?no_id=([^&"]+)&amp;anuladas', r.text)
    assert ids == [e[0] for e in esperado]
    assert "nivel=medio" in r.text
    assert "Resolver questões desta matéria" in r.text


def test_no_que_nao_e_materia_da_404(cliente):
    assunto = _consulta("SELECT id FROM vw_no_caminho WHERE nivel = 'assunto' LIMIT 1")
    assert cliente.get(f"/materias/{assunto[0][0]}").status_code == 404
    assert cliente.get("/materias/nao-existe").status_code == 404
