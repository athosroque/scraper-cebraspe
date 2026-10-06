import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def test_login_google_redirect(cliente):
    # GET /entrar redireciona para o Google OAuth
    r = cliente.get("/entrar", params={"voltar": "/conta"}, follow_redirects=False)
    # 303 Redirect to Google
    assert r.status_code == 302
    assert "accounts.google.com" in r.headers.get("location", "")


def test_abas_estatisticas_avancadas_renderizam_200(cliente):
    # /estatisticas
    r_estatisticas = cliente.get("/estatisticas")
    assert r_estatisticas.status_code == 200

    # /estatisticas/edital
    r_edital = cliente.get("/estatisticas/edital")
    assert r_edital.status_code == 200

    # /estatisticas/edital-vs-prova
    r_edital_prova = cliente.get("/estatisticas/edital-vs-prova")
    assert r_edital_prova.status_code == 200


def test_simulado_completo_fluxo(cliente_logado):
    c, _usuario_id = cliente_logado

    # 1. Chamar endpoint de criar
    prova_form = {"concurso": "PF_25_ADM", "cargo_numero": "1"}
    r_iniciar = c.post("/simulado/iniciar", data=prova_form, follow_redirects=False)
    assert r_iniciar.status_code == 303
    url_prova = r_iniciar.headers["location"]

    # 2. Renderizar prova
    r_prova = c.get(url_prova)
    assert r_prova.status_code == 200
    assert "simulado_id" in r_prova.text

    simulado_id = int(url_prova.rsplit("/", 1)[1])

    from test_simulado import _gabaritos

    # Busca gabaritos do endpoint de questoes
    gabs = _gabaritos(c)
    validas = [k for k, (gab, anulada) in gabs.items() if not anulada]

    # Vamos responder algumas questoes (metade certo, metade invertido)
    respostas = {
        "simulado_id": str(simulado_id),
        "concurso": "PF_25_ADM",
        "cargo_numero": "1",
    }
    for i, chave in enumerate(validas[:10]):
        gab = gabs[chave][0]
        # Acerta os pares, erra os ímpares
        resp = gab if i % 2 == 0 else ("E" if gab == "C" else "C")
        respostas[f"r:{chave}"] = resp

    # 3. Interagir com questoes (enviar respostas e corrigir)
    r_corrigir = c.post("/simulado/corrigir", data=respostas, follow_redirects=False)
    assert r_corrigir.status_code == 303
    assert r_corrigir.headers["location"] == url_prova

    # 4. Ver resultado final
    r_resultado = c.get(url_prova)
    assert r_resultado.status_code == 200
    assert "Resultado do simulado" in r_resultado.text
    assert (
        "Você encerrou este simulado" in r_resultado.text
        or "Revisar" in r_resultado.text
    )
