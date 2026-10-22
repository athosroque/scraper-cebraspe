"""Plano de estudo e concurso-alvo (5F.8)."""

import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

ALVO = {"concurso": "PF_25_ADM", "cargo_numero": 1}


def test_sem_login_e_401(cliente):
    assert cliente.get("/api/v1/eu/plano", params=ALVO).status_code == 401
    assert cliente.get("/api/v1/eu/concurso-alvo").status_code == 401
    assert cliente.put("/api/v1/eu/concurso-alvo", json=ALVO).status_code == 401


def test_put_sem_csrf_e_403(cliente_logado):
    c, _ = cliente_logado
    r = c.put("/api/v1/eu/concurso-alvo", json=ALVO, headers={"X-CSRFToken": "x"})
    assert r.status_code == 403


def test_concurso_alvo_salva_e_aparece_no_eu(cliente_logado):
    c, _ = cliente_logado
    assert c.get("/api/v1/eu/concurso-alvo").json() is None
    assert c.get("/api/v1/eu").json()["concurso_alvo"] is None
    r = c.put("/api/v1/eu/concurso-alvo", json=ALVO)
    assert r.status_code == 200
    assert c.get("/api/v1/eu/concurso-alvo").json() == ALVO
    eu = c.get("/api/v1/eu").json()
    assert (eu["concurso_alvo"], eu["cargo_alvo"]) == ("PF_25_ADM", 1)


def test_concurso_ou_cargo_inexistente(cliente_logado):
    c, _ = cliente_logado
    inexistente = {"concurso": "NAO_EXISTE", "cargo_numero": 1}
    assert c.put("/api/v1/eu/concurso-alvo", json=inexistente).status_code == 404
    sem_cargo = {"concurso": "PF_25_ADM", "cargo_numero": 999}
    assert c.put("/api/v1/eu/concurso-alvo", json=sem_cargo).status_code == 404
    assert c.get("/api/v1/eu/plano", params=sem_cargo).status_code == 404
    r = c.put("/api/v1/eu/concurso-alvo", json={"concurso": "X"})
    assert r.status_code == 422
    r = c.get("/api/v1/eu/plano", params={"concurso": "PF_25_ADM"})
    assert r.status_code == 422


def test_plano_sem_respostas_comeca_por_aof(cliente_logado):
    c, _ = cliente_logado
    plano = c.get("/api/v1/eu/plano", params=ALVO).json()
    primeiro = plano["itens"][0]
    assert primeiro["rotulo_materia"] == "Administração Financeira e Orçamentária"
    assert primeiro["pct_da_prova"] == pytest.approx(17.80, abs=0.01)
    assert primeiro["acerto"] == 0
    assert primeiro["prioridade"] == primeiro["pct_da_prova"]
    prioridades = [i["prioridade"] for i in plano["itens"]]
    assert prioridades == sorted(prioridades, reverse=True)


def test_acerto_reduz_prioridade(cliente_logado):
    c, _ = cliente_logado
    antes = c.get("/api/v1/eu/plano", params=ALVO).json()["itens"][0]
    params = {
        **ALVO,
        "no_id": antes["materia_id"],
        "anuladas": "excluir",
        "tamanho_pagina": 2,
    }
    qs = c.get("/api/v1/questoes", params=params).json()["itens"]
    for q in qs:
        c.post(
            "/api/v1/respostas",
            json={"questao_chave": q["questao_chave"], "resposta": q["gabarito"]},
        )
    itens = c.get("/api/v1/eu/plano", params=ALVO).json()["itens"]
    depois = next(i for i in itens if i["materia_id"] == antes["materia_id"])
    assert depois["respondidas"] == 2
    assert depois["acerto"] == 1
    assert depois["prioridade"] == 0


def test_pagina_salva_alvo_e_mostra_plano(cliente_logado):
    c, _ = cliente_logado
    html = c.get("/estatisticas/edital-vs-prova", params=ALVO).text
    assert "Salvar como concurso-alvo" in html
    r = c.post(
        "/estatisticas/concurso-alvo",
        data={**ALVO, "csrf_token": "token-csrf-teste"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Sem parâmetros na URL, a página abre no alvo salvo, com o plano.
    html = c.get("/estatisticas/edital-vs-prova").text
    assert "Concurso-alvo" in html and "Seu concurso-alvo" in html
    assert "sem respostas" in html


def test_pagina_anonima_nao_oferece_salvar(cliente):
    html = cliente.get("/estatisticas/edital-vs-prova", params=ALVO).text
    assert "Salvar como concurso-alvo" not in html
