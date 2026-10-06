import json
import re

import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def _opcoes(html, nome):
    m = re.search(rf'<select name="{nome}".*?</select>', html, re.DOTALL)
    assert m, f"select {nome} ausente"
    return re.findall(r'<option value="([^"]*)"', m.group(0))


def test_favicon_e_og_image_servidos(cliente):
    assert cliente.get("/static/favicon.svg").status_code == 200
    r = cliente.get("/static/og.png")
    assert r.status_code == 200
    assert r.content.startswith(b"\x89PNG")


def test_canonical_og_e_twitter_presentes(cliente):
    html = cliente.get("/sobre?x=1").text
    assert re.search(r'<link rel="canonical" href="[^"?]*/sobre"', html)
    for marca in (
        'property="og:title"',
        'property="og:description"',
        'property="og:image"',
        'name="twitter:title"',
        'name="twitter:description"',
    ):
        assert marca in html
    assert 'aria-expanded="false"' in html and ":aria-expanded" in html


def _facetas_do_painel(html):
    m = re.search(
        r'<script type="application/json" id="dados-facetas"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert m, "facetas do painel ausentes"
    return json.loads(m.group(1))


def test_selects_de_concurso_usam_slug(cliente):
    valores = [v for v in _opcoes(cliente.get("/simulado").text, "concurso") if v]
    # 5G.4: na lista, o concurso é faceta (checkbox), com o slug como valor.
    painel = _facetas_do_painel(cliente.get("/questoes").text)
    valores += [f["valor"] for f in painel["concurso"]]
    assert valores
    assert all(re.fullmatch(r"[A-Z0-9_]+", v) for v in valores), valores


def test_ordem_dos_filtros(cliente):
    html = cliente.get("/questoes").text
    ordem = ("materia", "assunto", "subassunto", "orgao", "ano", "concurso", "cargo")
    pos = [html.index(f'data-chave="{n}"') for n in ordem]
    assert pos == sorted(pos)


def test_localstorage_sem_expressao_fragil(cliente):
    html = cliente.get("/questoes").text
    assert "window.sessaoAcertos" in html
    # nenhum acesso direto a localStorage em atributo Alpine
    assert not re.search(r'x-(?:data|init)="[^"]*localStorage', html)
