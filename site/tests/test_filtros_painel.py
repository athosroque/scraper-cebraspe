"""Painel de filtros no topo (5H.3): aplicação só no Filtrar, recontagem das
facetas em `/questoes/facetas`, atalho do ID curto, "Excluir questões" e
"Questões com" (inclusive o histórico, que pede login)."""

import json
import re

import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

HX = {"HX-Request": "true"}
CHAVE = "PF_25_ADM|094_PF_CB1_01|1"


def _total_api(cliente, **params):
    r = cliente.get("/api/v1/questoes", params={**params, "tamanho_pagina": 1})
    assert r.status_code == 200, r.text
    return r.json()["total"]


def _total_html(texto: str) -> int:
    m = re.search(r">([\d.]+)</strong> questões encontradas", texto)
    assert m, "total ausente no HTML"
    return int(m.group(1).replace(".", ""))


def _tag(texto: str, padrao: str) -> str:
    m = re.search(padrao, texto, re.DOTALL)
    assert m, padrao
    return m.group(0)


# --- gatilho só no submit ------------------------------------------------------


def test_form_aplica_so_no_submit(cliente):
    r = cliente.get("/questoes")
    form = _tag(r.text, r'<form id="form-filtros"[^>]*>')
    gatilho = re.search(r'hx-trigger="([^"]*)"', form).group(1)
    # Mudar um campo não busca: só o botão Filtrar (submit).
    assert gatilho == "submit"
    assert "change" not in gatilho
    assert 'hx-get="/questoes"' in form
    # A recontagem é um elemento à parte, que não troca a lista.
    recontagem = _tag(r.text, r'<div id="recontagem"[^>]*>')
    assert 'hx-get="/questoes/facetas"' in recontagem
    assert 'hx-include="#form-filtros"' in recontagem
    assert 'hx-swap="none"' in recontagem
    # Nenhum controle do form dispara busca sozinho.
    corpo = r.text.split(form, 1)[1].split("</form>", 1)[0]
    assert "hx-get=" not in corpo
    assert re.search(r'<button[^>]*type="submit"[^>]*>\s*Filtrar', corpo) or (
        "Filtrar" in corpo and 'type="submit"' in corpo
    )


# --- /questoes/facetas ---------------------------------------------------------


def test_facetas_devolve_so_o_oob(cliente):
    r = cliente.get("/questoes/facetas", params={"orgao": "PF"}, headers=HX)
    assert r.status_code == 200
    texto = r.text.strip()
    assert texto.startswith('<script type="application/json" id="dados-facetas"')
    assert 'hx-swap-oob="true"' in texto
    assert texto.count("<script") == 1
    # Nada da lista: nem cards nem total nem paginação.
    assert "questões encontradas" not in texto
    assert "<article" not in texto and "<nav" not in texto


def test_facetas_contam_o_form_pendente(cliente):
    def dados(params):
        r = cliente.get("/questoes/facetas", params=params, headers=HX)
        bruto = re.search(r"<script[^>]*>(.*)</script>", r.text, re.DOTALL).group(1)
        return json.loads(bruto)

    sem = dados({})
    com = dados({"orgao": "PF", "anuladas": "excluir"})
    assert sem.keys() == com.keys()
    total_pf = _total_api(cliente, orgao="PF", anuladas="excluir")
    # A faceta de ano conta o recorte inteiro (PF, sem anuladas).
    assert sum(a["total"] for a in com["ano"]) == total_pf
    assert sum(a["total"] for a in sem["ano"]) == _total_api(cliente)
    # Valor estranho vira o padrão, sem 422.
    r = cliente.get("/questoes/facetas", params={"ano": "abc", "anuladas": "x"})
    assert r.status_code == 200


# --- ID curto na palavra-chave -------------------------------------------------


def test_id_curto_no_submit_htmx_redireciona(cliente):
    from app.servicos.formatacao import codigo_curto

    codigo = codigo_curto(CHAVE)
    for termo in (codigo, f"  {codigo.lower()} "):
        r = cliente.get("/questoes", params={"texto": termo}, headers=HX)
        assert r.status_code == 200
        assert r.headers["HX-Redirect"] == "/q/PF_25_ADM/094_PF_CB1_01/1"
        assert r.text == ""


def test_id_curto_sem_htmx_da_303(cliente):
    from app.servicos.formatacao import codigo_curto

    r = cliente.get(
        "/questoes", params={"texto": codigo_curto(CHAVE)}, follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/q/PF_25_ADM/094_PF_CB1_01/1"


def test_id_curto_desconhecido_nao_redireciona(cliente):
    r = cliente.get("/questoes", params={"texto": "Q00000000"}, headers=HX)
    assert "HX-Redirect" not in r.headers
    assert r.status_code == 200


# --- Excluir questões / Questões com -------------------------------------------


@pytest.mark.parametrize(
    ("nome", "valor", "params"),
    [
        ("anuladas", "excluir", {"anuladas": "excluir"}),
        ("com", "texto_base", {"com": "texto_base"}),
        ("com", "figuras", {"com": "figuras"}),
    ],
)
def test_checkbox_do_painel_filtra_e_fica_marcada(cliente, nome, valor, params):
    sem = cliente.get("/questoes")
    caixa = rf'<input type="checkbox" name="{nome}" value="{valor}"[^>]*>'
    assert " checked" not in _tag(sem.text, caixa)

    pagina = cliente.get("/questoes", params=params)
    assert " checked" in _tag(pagina.text, caixa)
    total = _total_api(cliente, **params)
    todas = _total_api(cliente)
    assert 0 < total < todas
    assert _total_html(pagina.text) == total
    parcial = cliente.get("/questoes", params=params, headers=HX)
    assert _total_html(parcial.text) == total


def test_fora_do_edital_saiu_do_painel(cliente):
    """Decisão do dono (2026-10-07, ADR-035): a banca só cobra o que o edital
    prevê, então "fora do edital" não tem valor e sai do site. Link antigo com
    o parâmetro é ignorado em silêncio (sem 422, sem chip, mesmo total)."""
    todas = _total_api(cliente)
    pagina = cliente.get("/questoes")
    assert 'name="fora_do_edital"' not in pagina.text
    assert "fora do edital" not in pagina.text.lower()
    for valor in ("nao", "sim", "x"):
        for headers in ({}, HX):
            r = cliente.get(
                "/questoes", params={"fora_do_edital": valor}, headers=headers
            )
            assert r.status_code == 200
            assert _total_html(r.text) == todas
            assert "fora do edital" not in r.text.lower()
        r = cliente.get(
            "/questoes/facetas", params={"fora_do_edital": valor}, headers=HX
        )
        assert r.status_code == 200
    # Sem chip nem hidden "extra" para o parâmetro antigo.
    r = cliente.get("/questoes", params={"fora_do_edital": "sim"})
    assert 'name="fora_do_edital"' not in r.text
    assert 'aria-label="Remover filtro' not in r.text  # chip do <noscript>


def test_excluir_anuladas_e_o_complemento_das_anuladas(cliente):
    todas = _total_api(cliente)
    assert (
        _total_api(cliente, anuladas="excluir") + _total_api(cliente, anuladas="so")
        == todas
    )


def test_historico_desabilitado_sem_login(cliente):
    r = cliente.get("/questoes")
    for valor in ("nao_resolvidas", "erradas"):
        caixa = _tag(
            r.text, rf'<input type="checkbox" name="historico" value="{valor}"[^>]*>'
        )
        assert "disabled" in caixa
    # Link com histórico sem login vale "todas", sem 422.
    r = cliente.get("/questoes", params={"historico": "erradas"}, headers=HX)
    assert _total_html(r.text) == _total_api(cliente)


def test_historico_com_login(cliente_logado):
    c, _ = cliente_logado
    itens = c.get(
        "/api/v1/questoes",
        params={"tamanho_pagina": 3, "anuladas": "excluir", "concurso": "PF_25_ADM"},
    ).json()["itens"]
    certa, errada = itens[0], itens[1]
    c.post(
        "/api/v1/respostas",
        json={"questao_chave": certa["questao_chave"], "resposta": certa["gabarito"]},
    )
    c.post(
        "/api/v1/respostas",
        json={
            "questao_chave": errada["questao_chave"],
            "resposta": "E" if errada["gabarito"] == "C" else "C",
        },
    )

    pagina = c.get("/questoes")
    for valor in ("nao_resolvidas", "erradas"):
        caixa = _tag(
            pagina.text,
            rf'<input type="checkbox" name="historico" value="{valor}"[^>]*>',
        )
        assert "disabled" not in caixa

    # "Que errei" (Questões com) e "Já resolvidas" (Excluir questões).
    r = c.get("/questoes", params={"historico": "erradas"}, headers=HX)
    assert _total_html(r.text) == 1
    assert errada["codigo"] in r.text
    todas = _total_api(c)
    r = c.get("/questoes", params={"historico": "nao_resolvidas"}, headers=HX)
    assert _total_html(r.text) == todas - 2
    marcada = c.get("/questoes", params={"historico": "erradas"})
    caixa = _tag(
        marcada.text, r'<input type="checkbox" name="historico" value="erradas"[^>]*>'
    )
    assert " checked" in caixa
