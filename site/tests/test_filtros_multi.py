"""Filtros multisseleção (5G.4): OU dentro do filtro, E entre filtros."""

import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

HX = {"HX-Request": "true"}
CARGOS = ["PF_25_ADM:1", "STM_25:1"]


def _total(cliente, params):
    r = cliente.get("/api/v1/questoes", params={**params, "tamanho_pagina": 1})
    assert r.status_code == 200, r.text
    return r.json()["total"]


def _tres_assuntos(cliente):
    facetas = cliente.get("/api/v1/facetas", params={"cargo": CARGOS}).json()
    assuntos = [a for a in facetas["assuntos"] if a["total"] > 0][:3]
    assert len(assuntos) == 3
    return [a["valor"] for a in assuntos]


def test_modelo_aceita_valor_unico_lista_e_vazio():
    from app.modelos import FiltroQuestoes

    f = FiltroQuestoes(
        ano="2025",
        orgao=["PF", "", "PF", "STM"],
        cargo=["PF_25_ADM:1", "lixo", ""],
        cargo_numero=["", "x"],
        no_id="",
    )
    assert f.ano == [2025]
    assert f.orgao == ["PF", "STM"]
    assert f.cargo == ["PF_25_ADM:1"]
    assert f.cargo_numero is None
    assert f.no_id is None


def test_ou_dentro_do_filtro(cliente):
    a, b = (_total(cliente, {"cargo": c}) for c in CARGOS)
    # Concursos diferentes não dividem questão: a união é a soma.
    assert _total(cliente, {"cargo": CARGOS}) == a + b
    assert _total(cliente, {"ano": [2025, 2024]}) == _total(cliente, {"ano": 2025})


def test_combinacao_2_anos_2_cargos_3_assuntos(cliente):
    assuntos = _tres_assuntos(cliente)
    params = {"ano": [2025, 2024], "cargo": CARGOS, "no_id": assuntos}
    dados = cliente.get(
        "/api/v1/questoes", params={**params, "tamanho_pagina": 50}
    ).json()
    assert 0 < dados["total"] < _total(cliente, {"cargo": CARGOS})
    # Cada filtro com um só valor nunca passa da combinação com OU.
    for assunto in assuntos:
        assert _total(cliente, {**params, "no_id": assunto}) <= dados["total"]
    soma = sum(_total(cliente, {**params, "no_id": a}) for a in assuntos)
    assert soma >= dados["total"]
    for q in dados["itens"]:
        cargos = {f"{q['concurso']}:{c['cargo_numero']}" for c in q["cargos"]}
        assert cargos & set(CARGOS)
        nos = {n["assunto_id"] for n in q["nos"]} | {n["no_id"] for n in q["nos"]}
        assert nos & set(assuntos)

    # A página HTML com a mesma URL (parâmetros repetidos) dá o mesmo total.
    r = cliente.get("/questoes", params=params, headers=HX)
    assert r.status_code == 200
    total_fmt = f"{dados['total']:,}".replace(",", ".")
    assert f">{total_fmt}</strong> questões encontradas" in r.text
    # Um chip por valor marcado (2024 não tem questão, mas segue marcado). Desde
    # a 5H.3 os chips do servidor ficam no <noscript> da página inteira.
    pagina = cliente.get("/questoes", params=params)
    noscript = pagina.text.split("<noscript>")
    chips = sum(
        t.split("</noscript>")[0].count('aria-label="Remover filtro')
        for t in noscript[1:]
    )
    # Desde a cascata (5H.3), o assunto sem disciplina marcada é link direto:
    # a disciplina de cada um entra na seleção e ganha chip.
    from app.servicos import questoes_servico

    nos = questoes_servico.info_nos()
    disciplinas = {nos[a].pai for a in assuntos}
    assert chips == 2 + 2 + 3 + len(disciplinas)


def test_servico_lista_com_listas(cliente):
    from app.modelos import FiltroQuestoes
    from app.servicos import questoes_servico

    assuntos = _tres_assuntos(cliente)
    filtros = FiltroQuestoes(ano=[2025, 2024], cargo=CARGOS, no_id=assuntos)
    pagina = questoes_servico.listar_questoes(filtros, 1, 5)
    api = _total(cliente, {"ano": [2025, 2024], "cargo": CARGOS, "no_id": assuntos})
    assert pagina.total == api > 0


def test_valor_unico_compativel(cliente):
    assert _total(cliente, {"orgao": "PF"}) == _total(cliente, {"orgao": ["PF"]})
    antigo = _total(cliente, {"concurso": "PF_25_ADM", "cargo_numero": 1})
    assert antigo == _total(cliente, {"cargo": "PF_25_ADM:1"})
    # A página converte o link antigo no cargo novo, com o mesmo total.
    r = cliente.get(
        "/questoes", params={"concurso": "PF_25_ADM", "cargo_numero": "1"}, headers=HX
    )
    assert f">{antigo:,}".replace(",", ".") + "</strong>" in r.text


def test_parametro_vazio_nao_da_422(cliente):
    vazio = {
        k: ""
        for k in (
            "banca",
            "orgao",
            "ano",
            "concurso",
            "cargo",
            "cargo_numero",
            "nivel",
            "tipo_conhecimento",
            "no_id",
            "anuladas",
            "historico",
        )
    }
    for headers in ({}, HX):
        r = cliente.get("/questoes", params=vazio, headers=headers)
        assert r.status_code == 200
        assert ">2.781</strong> questões encontradas" in r.text
    r = cliente.get("/questoes", params={"ano": ["", "2025", "abc"]}, headers=HX)
    assert r.status_code == 200


def test_facetas_consideram_os_outros_filtros(cliente):
    sem = cliente.get("/api/v1/facetas").json()
    com = cliente.get("/api/v1/facetas", params={"orgao": "PF", "ano": 2025}).json()
    # A faceta do próprio filtro não se restringe por ele: os outros órgãos seguem.
    assert {o["valor"] for o in com["orgaos"]} == {o["valor"] for o in sem["orgaos"]}
    pf = _total(cliente, {"orgao": "PF"})
    assert next(a for a in com["anos"] if a["valor"] == 2025)["total"] == pf
    # Os cargos passam a contar só o recorte da PF.
    assert all(c["concurso"] == "PF_25_ADM" for c in com["cargos"] if c["total"])
    assert all(
        c["valor"] == f"{c['concurso']}:{c['cargo_numero']}" for c in com["cargos"]
    )
    # Nós com o caminho a partir da matéria.
    sub = com["subassuntos"][0]
    assert sub["nivel"] == "subassunto" and sub["caminho"].count(" › ") == 2


def test_faceta_marcada_aparece_mesmo_zerada(cliente):
    facetas = cliente.get(
        "/api/v1/facetas", params={"orgao": "PF", "cargo": "STM_25:1"}
    ).json()
    stm = next(c for c in facetas["cargos"] if c["valor"] == "STM_25:1")
    assert stm["total"] == 0


def test_painel_traz_facetas_oob_no_fragmento(cliente):
    r = cliente.get("/questoes", params={"orgao": "PF"}, headers=HX)
    assert 'id="dados-facetas" hx-swap-oob="true"' in r.text
    inteira = cliente.get("/questoes", params={"orgao": "PF"}).text
    assert inteira.count('id="dados-facetas"') == 1
    assert "hx-swap-oob" not in inteira.split('id="dados-facetas"')[1][:20]
