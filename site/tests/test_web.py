import re

import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

HX = {"HX-Request": "true"}


def _questao(cliente, **params):
    dados = cliente.get(
        "/api/v1/questoes", params={"tamanho_pagina": 1, **params}
    ).json()
    assert dados["total"] > 0
    return dados["itens"][0]


def _url(chave):
    return "/q/" + chave.replace("|", "/")


def test_home_pagina_inteira(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Árvore de Assuntos" in r.text
    assert "2781 questões encontradas" in r.text
    assert '<meta name="description"' in r.text


def test_home_htmx_devolve_so_fragmento(cliente):
    r = cliente.get("/", headers=HX)
    assert "<html" not in r.text
    assert "Árvore de Assuntos" not in r.text
    assert "questões encontradas" in r.text
    assert "HX-Request" in r.headers["vary"]


def test_restauracao_de_historico_devolve_pagina_inteira(cliente):
    r = cliente.get("/", headers={**HX, "HX-History-Restore-Request": "true"})
    assert "<html" in r.text


def test_filtros_combinados_e_select_vazio(cliente):
    # O form manda todos os campos juntos; select "Todos" chega vazio.
    r = cliente.get(
        "/",
        params={"orgao": "", "nivel": "superior", "no_id": "S-c33faee4a4"},
        headers=HX,
    )
    api = cliente.get(
        "/api/v1/questoes", params={"nivel": "superior", "no_id": "S-c33faee4a4"}
    ).json()
    assert f"{api['total']} questões encontradas" in r.text


def test_no_id_nao_entra_na_expressao_do_alpine(cliente):
    payload = "x');alert(1);//"
    r = cliente.get("/", params={"no_id": payload})
    assert "alert(1)" not in r.text.split("x-data")[1].split("}")[0]
    assert 'data-no-id="x&#39;);alert(1);//"' in r.text


def test_hx_target_da_correcao_e_seletor_css_valido(cliente):
    r = cliente.get("/", headers=HX)
    alvos = re.findall(r'hx-target="#([^"]+)"', r.text)
    assert alvos
    assert all(re.fullmatch(r"[A-Za-z][\w-]*", a) for a in alvos)


def test_texto_base_sob_demanda(cliente):
    params = {"concurso": "PF_25_ADM", "tamanho_pagina": 50}
    itens = cliente.get("/api/v1/questoes", params=params).json()["itens"]
    q = next(i for i in itens if i["tem_texto_base"])
    trecho = cliente.get(f"/api/v1/questoes/{q['questao_chave']}").json()[
        "texto_base_texto"
    ][:30]

    lista = cliente.get("/", params=params, headers=HX).text
    assert _url(q["questao_chave"]) + "/anexos" in lista
    assert trecho not in lista

    anexos = cliente.get(_url(q["questao_chave"]) + "/anexos")
    assert anexos.status_code == 200
    assert "<html" not in anexos.text
    assert trecho in anexos.text


def test_correcao_certo_e_errado(cliente):
    q = _questao(cliente, anuladas="excluir")
    certo = cliente.post(
        "/q/correcao", data={"chave": q["questao_chave"], "resposta": q["gabarito"]}
    )
    assert "Você acertou!" in certo.text
    outra = "E" if q["gabarito"] == "C" else "C"
    errado = cliente.post(
        "/q/correcao", data={"chave": q["questao_chave"], "resposta": outra}
    )
    assert "Você errou." in errado.text


def test_correcao_anulada(cliente):
    q = _questao(cliente, anuladas="so")
    r = cliente.post("/q/correcao", data={"chave": q["questao_chave"], "resposta": "C"})
    assert "anulada pela banca" in r.text


def test_correcao_rejeita_resposta_invalida(cliente):
    q = _questao(cliente)
    r = cliente.post("/q/correcao", data={"chave": q["questao_chave"], "resposta": "X"})
    assert r.status_code == 422


def test_pagina_canonica(cliente):
    q = _questao(cliente)
    r = cliente.get(_url(q["questao_chave"]))
    assert r.status_code == 200
    assert "Fonte: CEBRASPE" in r.text
    assert "Fonte Original" in r.text
    assert f"Questão {q['numero']} (" in r.text  # meta description


def test_questao_inexistente_404_com_layout(cliente):
    r = cliente.get("/q/NAO_EXISTE/x/1")
    assert r.status_code == 404
    assert "<html" in r.text


def test_sobre(cliente):
    r = cliente.get("/sobre")
    assert "Sobre e Fontes" in r.text
    assert "athosroque@hotmail.com" in r.text


def test_rotas_web_fora_do_openapi(cliente):
    caminhos = cliente.get("/openapi.json").json()["paths"]
    assert not any(p == "/" or p.startswith("/q/") for p in caminhos)
