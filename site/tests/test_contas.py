import re

import pytest

from app.auth import destino_seguro
from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def _questoes(cliente, n, **params):
    dados = cliente.get(
        "/api/v1/questoes", params={"tamanho_pagina": n, **params}
    ).json()
    return dados["itens"]


def _errada(gabarito):
    return "E" if gabarito == "C" else "C"


def test_destino_seguro_bloqueia_open_redirect():
    assert destino_seguro("/conta") == "/conta"
    assert destino_seguro("//evil.com") == "/"
    assert destino_seguro("/\\evil.com") == "/"
    assert destino_seguro("https://evil.com") == "/"
    assert destino_seguro(None) == "/"


def test_post_sem_csrf_e_recusado(cliente):
    q = _questoes(cliente, 1)[0]
    dados = {"chave": q["questao_chave"], "resposta": "C"}
    r = cliente.post("/q/correcao", data=dados, headers={"X-CSRFToken": "errado"})
    assert r.status_code == 403
    r = cliente.post(
        "/api/v1/respostas",
        json={"questao_chave": q["questao_chave"], "resposta": "C"},
        headers={"X-CSRFToken": "errado"},
    )
    assert r.status_code == 403


def test_form_com_csrf_no_campo(cliente):
    token = cliente.headers.pop("X-CSRFToken")
    q = _questoes(cliente, 1)[0]
    r = cliente.post(
        "/q/correcao",
        data={"chave": q["questao_chave"], "resposta": "C", "csrf_token": token},
    )
    assert r.status_code == 200


def test_anonimo_corrige_sem_gravar(cliente):
    q = _questoes(cliente, 1, anuladas="excluir")[0]
    r = cliente.post(
        "/api/v1/respostas", json={"questao_chave": q["questao_chave"], "resposta": "C"}
    )
    assert r.status_code == 200
    assert r.json()["gravada"] is False
    assert cliente.get("/api/v1/eu").status_code == 401
    assert cliente.get("/api/v1/eu/desempenho").status_code == 401
    assert cliente.get("/api/v1/questoes?historico=erradas").status_code == 401
    assert cliente.get("/conta", follow_redirects=False).status_code == 303


def test_historico_e_desempenho(cliente_logado):
    c, _ = cliente_logado
    assert c.get("/api/v1/eu").json()["nome"] == "Usuário Teste"
    qs = _questoes(c, 6, anuladas="excluir", concurso="PF_25_ADM")
    certas, erradas = qs[:4], qs[4:]
    for q in certas:
        c.post(
            "/q/correcao",
            data={"chave": q["questao_chave"], "resposta": _errada(q["gabarito"])},
        )
        # A resposta mais recente é a que vale.
        r = c.post(
            "/api/v1/respostas",
            json={"questao_chave": q["questao_chave"], "resposta": q["gabarito"]},
        )
        assert r.json() == {**r.json(), "acertou": True, "gravada": True}
    for q in erradas:
        r = c.post(
            "/q/correcao",
            data={"chave": q["questao_chave"], "resposta": _errada(q["gabarito"])},
        )
        assert "salva no seu histórico" in r.text

    def chaves(historico):
        itens = c.get(
            "/api/v1/questoes",
            params={"historico": historico, "tamanho_pagina": 50},
        ).json()["itens"]
        return {i["questao_chave"] for i in itens}

    assert chaves("resolvidas") == {q["questao_chave"] for q in qs}
    assert chaves("certas") == {q["questao_chave"] for q in certas}
    assert chaves("erradas") == {q["questao_chave"] for q in erradas}
    nao = c.get("/api/v1/questoes", params={"historico": "nao_resolvidas"}).json()
    todas = c.get("/api/v1/questoes").json()
    assert nao["total"] == todas["total"] - 6

    # Desempenho: cada matéria conta cada questão uma vez.
    desempenho = c.get("/api/v1/eu/desempenho").json()
    assert sum(m["total"] for m in desempenho) >= 6
    for m in desempenho:
        for a in m["filhos"]:
            assert a["total"] <= m["total"]
            for s in a["filhos"]:
                assert s["total"] <= a["total"]
    esperado = {}
    for q in qs:
        materias = {n["materia_id"] for n in q["nos"]}
        for materia in materias:
            t, a = esperado.get(materia, (0, 0))
            esperado[materia] = (t + 1, a + (q in certas))
    obtido = {m["id"]: (m["total"], m["acertos"]) for m in desempenho}
    assert obtido == esperado

    pagina = c.get("/conta")
    assert pagina.status_code == 200
    assert "Desempenho por assunto" in pagina.text
    assert "Caderno de erros" in pagina.text
    # Logado, "Já resolvidas" e "Que errei" ficam habilitados (5H.3).
    lista = c.get("/questoes").text
    for valor in ("nao_resolvidas", "erradas"):
        tag = re.search(rf'<input[^>]*name="historico" value="{valor}"[^>]*>', lista)
        assert tag and "disabled" not in tag.group(0)


def test_anulada_nao_grava(cliente_logado):
    c, _ = cliente_logado
    q = _questoes(c, 1, anuladas="so")[0]
    r = c.post(
        "/api/v1/respostas", json={"questao_chave": q["questao_chave"], "resposta": "C"}
    )
    assert r.json()["gravada"] is False
    assert c.get("/api/v1/questoes?historico=resolvidas").json()["total"] == 0


def test_apagar_conta(cliente_logado):
    c, usuario_id = cliente_logado
    q = _questoes(c, 1, anuladas="excluir")[0]
    c.post(
        "/api/v1/respostas", json={"questao_chave": q["questao_chave"], "resposta": "C"}
    )
    r = c.post(
        "/conta/apagar", data={"csrf_token": "token-csrf-teste"}, follow_redirects=False
    )
    assert r.status_code == 303
    from app.repositorio import usuarios_repo

    assert usuarios_repo.obter_usuario(usuario_id) is None
    assert usuarios_repo.ultimas_respostas(usuario_id) == {}
    assert c.get("/api/v1/eu").status_code == 401
