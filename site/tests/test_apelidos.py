"""Apelidos de busca (KAN-64): a LAI e a LGPD acham o próprio nó por qualquer nome.

Os apelidos vêm de `vw_no_apelidos` (nós fundidos e itens de edital que apontam
para um único nó). Item de nome composto (2+ nós) não vira apelido."""

import json
import re

import pytest

from app.servicos import estatisticas_servico
from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel

com_banco = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

LAI = "S-256fbea4b7"
LGPD = "NS-11c10a8ea6"


def _consulta(sql, params=()):
    with stats_writer.conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _json(texto: str, id_: str):
    m = re.search(rf'<script[^>]*id="{id_}"[^>]*>(.*?)</script>', texto, re.DOTALL)
    assert m, id_
    return json.loads(m.group(1))


@pytest.mark.parametrize(
    "q",
    ["7.724", "7724", "decreto 7.724", "decreto nº 7.724", "LAI", "12527", "12.527"],
)
@com_banco
def test_busca_acha_lai(cliente, q):
    r = cliente.get("/api/v1/busca", params={"q": q})
    assert r.status_code == 200, r.text
    assert LAI in [no["id"] for no in r.json()], q


@pytest.mark.parametrize("q", ["lgpd", "13.709", "13709", "Lei Geral de Proteção"])
@com_banco
def test_busca_acha_lgpd(cliente, q):
    r = cliente.get("/api/v1/busca", params={"q": q})
    assert r.status_code == 200, r.text
    assert LGPD in [no["id"] for no in r.json()], q


@com_banco
def test_apelidos_da_lai_e_da_lgpd(cliente):
    from app.repositorio import estatisticas_repo

    apelidos = estatisticas_repo.apelidos_por_no()
    # 8: a curadoria completa do SEFA_PR_25 (KAN-56/KAN-92) carregou um 2º item da LAI
    # ("Lei Federal nº 12.527/2011 e suas alterações..."), além do que já entrara pelo
    # casamento global (KAN-87) com 7.
    assert len(apelidos[LAI]) == 8
    assert "Lei nº 12.527/2011 e Decreto nº 7.724/2012" in apelidos[LAI]
    assert len(apelidos[LGPD]) == 5


_SQL_ITENS = """
    SELECT 't' || p.topico_id AS k, n.nome, c.no_efetivo
    FROM topico_no p
    JOIN dim_topico n ON n.id = p.topico_id
    JOIN vw_no_caminho c ON c.id = p.no_id
    UNION ALL
    SELECT 's' || p.subtopico_id, n.nome, c.no_efetivo
    FROM subtopico_no p
    JOIN dim_subtopico n ON n.id = p.subtopico_id
    JOIN vw_no_caminho c ON c.id = p.no_id
"""


@com_banco
def test_item_composto_nao_vira_apelido(cliente):
    # Item (chave única) que aponta para 2+ nós efetivos não entra como apelido.
    # O nome só aparece se outro item de nó único tiver o mesmo nome.
    compostos = _consulta(
        f"WITH item AS ({_SQL_ITENS}) SELECT k, nome FROM item "
        "GROUP BY k, nome HAVING count(DISTINCT no_efetivo) >= 2"
    )
    assert compostos, "esperava ao menos um item composto na base"
    unicos = {
        nome
        for (nome,) in _consulta(
            f"WITH item AS ({_SQL_ITENS}) SELECT nome FROM item "
            "GROUP BY k, nome HAVING count(DISTINCT no_efetivo) = 1"
        )
    }
    from app.repositorio import estatisticas_repo

    todos = {a for lista in estatisticas_repo.apelidos_por_no().values() for a in lista}
    for _, nome in compostos:
        assert nome not in todos or nome in unicos, nome


@com_banco
def test_painel_direito_administrativo_busca_7724(cliente):
    r = cliente.get("/questoes")
    assert r.status_code == 200
    opcoes = _json(r.text, "dados-facetas")["materia"]
    da = [o for o in opcoes if o["rotulo"] == "Direito Administrativo"]
    assert da, "Direito Administrativo fora das facetas"
    assert "7.724" in da[0]["busca"]


def test_normalizar_tira_ponto_de_milhar_e_numero_de_norma():
    assert "7724" in estatisticas_servico._normalizar("Decreto nº 7.724/2012")
    assert estatisticas_servico._normalizar("Decreto nº 7.724/2012") == (
        "decreto 7724/2012"
    )
    assert estatisticas_servico._normalizar("7.724") == "7724"
    assert estatisticas_servico._normalizar("Língua Portuguesa") == "lingua portuguesa"


@com_banco
def test_busca_nao_repete_no_fundido(cliente):
    """`vw_no_caminho` tem uma linha por ID original, inclusive os fundidos; a
    busca devolve só o nó efetivo (Etapa 5B.3: "Ciclo orçamentário" tinha 3 hits)."""
    r = cliente.get("/api/v1/busca", params={"q": "Ciclo orçamentário"})
    assert r.status_code == 200, r.text
    achados = [no for no in r.json() if no["nome"] == "Ciclo orçamentário"]
    assert [no["id"] for no in achados] == ["A-e46d2efa1f"]
