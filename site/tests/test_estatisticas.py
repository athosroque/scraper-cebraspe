"""Páginas e API de estatística (5F.4) contra as views da 5E, com o banco real."""

import re
from urllib.parse import parse_qs, urlparse

import pytest

from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

LP = "LÍNGUA PORTUGUESA"


def _consulta(sql, params=()):
    # Usuário do pipeline: confere o site (roles do site) contra as views.
    with stats_writer.conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _id_materia(nome):
    return _consulta(
        "SELECT id FROM vw_no_caminho WHERE nivel = 'materia' AND nome = %s", (nome,)
    )[0][0]


@pytest.mark.parametrize("nivel", ["superior", "medio"])
def test_top10_lingua_portuguesa_por_nivel(cliente, nivel):
    """Exemplo 1 da 5E: top 10 subassuntos de LP em superior × médio."""
    materia = _id_materia(LP)
    esperado = _consulta(
        """
        SELECT no_id, questoes FROM fn_prova_cobra('subassunto', p_nivel => %s)
        WHERE materia_id = %s
        ORDER BY questoes DESC, pct_medio_por_concurso DESC, no_nome LIMIT 10
        """,
        (nivel, materia),
    )
    api = cliente.get(
        "/api/v1/estatisticas/prova-cobra",
        params={"materia_id": materia, "nivel": nivel, "limite": 10},
    ).json()
    assert [(r["no_id"], r["questoes"]) for r in api] == esperado

    html = cliente.get(
        "/estatisticas", params={"materia_id": materia, "nivel": nivel}
    ).text
    assert f"no_id={esperado[0][0]}" in html


def test_link_do_ranking_abre_a_lista_filtrada(cliente):
    """Exemplo 2 da 5E: questões de um subassunto filtradas por cargo e nível."""
    filtros = {"concurso": "PF_25_ADM", "cargo_numero": 1, "nivel": "superior"}
    linha = cliente.get(
        "/api/v1/estatisticas/prova-cobra", params={**filtros, "limite": 1}
    ).json()[0]
    html = cliente.get("/estatisticas", params=filtros).text
    href = (
        re.search(r'href="(/questoes\?no_id=[^"]+)"', html)
        .group(1)
        .replace("&amp;", "&")
    )
    params = {k: v[0] for k, v in parse_qs(urlparse(href).query).items()}
    assert params == {
        "no_id": linha["no_id"],
        "anuladas": "excluir",
        "concurso": "PF_25_ADM",
        "cargo_numero": "1",
        "nivel": "superior",
    }
    lista = cliente.get("/api/v1/questoes", params=params).json()
    # A lista mostra o mesmo enunciado repetido em cadernos diferentes; a
    # estatística conta a questão canônica uma vez.
    assert lista["total"] >= linha["questoes"] > 0


def test_edital_vs_prova_pf_cargo_1(cliente):
    """Exemplo 3 da 5E: "no edital, nunca cobrado" do PF_25_ADM cargo 1."""
    esperado = dict(
        _consulta(
            """
            SELECT situacao, count(*) FROM vw_edital_vs_prova
            WHERE concurso = 'PF_25_ADM' AND cargo_numero = 1
              AND situacao <> 'cobrado_fora_do_edital'
            GROUP BY situacao
            """
        )
    )
    nunca = {
        r[0]
        for r in _consulta(
            """
            SELECT no_id FROM vw_edital_vs_prova
            WHERE concurso = 'PF_25_ADM' AND cargo_numero = 1
              AND situacao = 'no_edital_nunca_cobrado'
            """
        )
    }
    params = {"concurso": "PF_25_ADM", "cargo_numero": 1}
    api = cliente.get("/api/v1/estatisticas/edital-vs-prova", params=params).json()
    assert api["resumo"] == esperado
    assert {
        n["no_id"] for n in api["nos"] if n["situacao"] == "no_edital_nunca_cobrado"
    } == nunca
    assert api["peso_materias"]
    # "Cobrado fora do edital" saiu do site (ADR-035, 2026-10-07): nem na API
    # nem na página, mesmo que a view ainda tenha a situação.
    assert "cobrado_fora_do_edital" not in api["resumo"]
    assert {n["situacao"] for n in api["nos"]} <= {
        "cobrado_no_edital",
        "no_edital_nunca_cobrado",
    }

    html = cliente.get("/estatisticas/edital-vs-prova", params=params).text
    assert (
        f"Previsto e nunca cobrado</strong> ({esperado['no_edital_nunca_cobrado']})"
        in html
    )
    assert f"Cobrado e previsto</strong> ({esperado['cobrado_no_edital']})" in html
    assert "fora do edital" not in html.lower()


def test_edital_vs_prova_cargo_inexistente(cliente):
    params = {"concurso": "NAO_EXISTE", "cargo_numero": 1}
    assert (
        cliente.get("/api/v1/estatisticas/edital-vs-prova", params=params).status_code
        == 404
    )
    html = cliente.get("/estatisticas/edital-vs-prova", params=params).text
    assert "Escolha um concurso e um cargo" in html


@pytest.mark.parametrize("nivel_alvo", ["materia", "assunto", "subassunto"])
def test_edital_cobra_sem_filtro_igual_as_views(cliente, nivel_alvo):
    esperado = _consulta(
        f"SELECT no_id, ocorrencias FROM vw_edital_cobra_{nivel_alvo} "
        "ORDER BY ocorrencias DESC, no_id"
    )
    api = cliente.get(
        "/api/v1/estatisticas/edital-cobra",
        params={"nivel_alvo": nivel_alvo, "limite": 200},
    ).json()
    obtido = {(r["no_id"], r["ocorrencias"]) for r in api}
    assert obtido <= set(esperado)
    assert len(obtido) == min(200, len(esperado))


def test_edital_cobra_filtro_de_cargo(cliente):
    params = {"nivel_alvo": "materia", "concurso": "PF_25_ADM", "cargo_numero": 1}
    api = cliente.get("/api/v1/estatisticas/edital-cobra", params=params).json()
    esperado = _consulta(
        """
        SELECT no_materia_id, count(DISTINCT taxonomia_item_id)
        FROM vw_arvore_edital_por_cargo
        WHERE concurso = 'PF_25_ADM' AND cargo_numero = 1
          AND status_revisao = 'aprovado'
        GROUP BY 1
        """
    )
    assert {(r["no_id"], r["ocorrencias"]) for r in api} == set(esperado)


def test_cargo_sem_concurso_e_ignorado(cliente):
    com = cliente.get("/estatisticas", params={"cargo_numero": 1}).text
    sem = cliente.get("/estatisticas").text
    assert com.replace("?cargo_numero=1", "") == sem


def test_rotas_html_de_estatistica_fora_do_openapi(cliente):
    caminhos = cliente.get("/openapi.json").json()["paths"]
    assert "/api/v1/estatisticas/prova-cobra" in caminhos
    assert not any(p.startswith("/estatisticas") for p in caminhos)


def test_trocar_concurso_manda_cargo_vazio(cliente):
    r = cliente.get(
        "/estatisticas/edital-vs-prova",
        params={"concurso": "STM_25", "cargo_numero": ""},
    )
    assert r.status_code == 200
    assert 'name="cargo_numero"' in r.text
    r = cliente.get(
        "/estatisticas", params={"concurso": "PF_25_ADM", "cargo_numero": ""}
    )
    assert r.status_code == 200
