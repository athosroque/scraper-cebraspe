"""ID curto estável da questão (5H.1): `codigo` na API e atalho `/q/<codigo>`."""

import re

import pytest

from app.servicos.formatacao import codigo_curto
from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)

_CHAVE = "PF_25_ADM|094_PF_CB1_01|1"


def test_codigos_distintos_para_todas_as_chaves(cliente):
    # Guarda contra colisão: 8 hex dão folga, mas a base pode crescer.
    from app.repositorio import questoes_repo

    chaves = questoes_repo.todas_as_chaves()
    assert len(chaves) == 2800
    assert len({codigo_curto(c) for c in chaves}) == len(chaves)


def test_api_traz_codigo_coerente_com_a_chave(cliente):
    dados = cliente.get("/api/v1/questoes", params={"tamanho_pagina": 50}).json()
    assert dados["itens"]
    for item in dados["itens"]:
        assert re.fullmatch(r"Q[0-9A-F]{8}", item["codigo"])
        assert item["codigo"] == codigo_curto(item["questao_chave"])
    detalhe = cliente.get(f"/api/v1/questoes/{_CHAVE}").json()
    assert detalhe["codigo"] == codigo_curto(_CHAVE)


def test_codigo_redireciona_301_para_a_canonica(cliente):
    codigo = codigo_curto(_CHAVE)
    for variante in (codigo, codigo.lower()):
        r = cliente.get(f"/q/{variante}", follow_redirects=False)
        assert r.status_code == 301
        assert r.headers["location"] == "/q/PF_25_ADM/094_PF_CB1_01/1"
    assert cliente.get(f"/q/{codigo}").status_code == 200


def test_codigo_da_questao_ilegivel_tambem_redireciona(cliente):
    # O detalhe por chave segue acessível para as 19 não utilizáveis (5F.1).
    chave = "PF_25_ADM|094_PF_005_01|52"
    r = cliente.get(f"/q/{codigo_curto(chave)}", follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "/q/PF_25_ADM/094_PF_005_01/52"


@pytest.mark.parametrize("codigo", ["Q00000000", "QZZZZZZZZ", "Q1234", "X1234ABCD"])
def test_codigo_invalido_ou_desconhecido_da_404_com_layout(cliente, codigo):
    r = cliente.get(f"/q/{codigo}", follow_redirects=False)
    assert r.status_code == 404
    assert "Questão não encontrada" in r.text
    assert "<html" in r.text
