import pytest
from tests.test_stats_writer import _postgres_disponivel

from app.servicos.simulados_servico import corrigir, placar

banco = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

PROVA = {"concurso": "PF_25_ADM", "cargo_numero": 1}


def _item(chave, gabarito, anulada=False, materia="M-1"):
    return {
        "questao_chave": chave,
        "numero": int(chave.split("|")[-1]),
        "codigo_caderno": "CAD",
        "gabarito": gabarito,
        "anulada": anulada,
        "materia_id": materia,
        "materia_nome": materia,
    }


# -- Correção CEBRASPE (sem banco) --
def test_placar_vazio():
    p = placar([])
    assert (p.nota, p.nota_maxima) == (0, 0)


def test_tudo_em_branco_da_zero():
    itens = [_item("X|C|1", "C"), _item("X|C|2", "E")]
    p, _, corrigidos = corrigir(itens, {})
    assert (p.nota, p.brancos, p.nota_maxima) == (0, 2, 2)
    assert {i.situacao for i in corrigidos} == {"branco"}


def test_tudo_errado_da_nota_negativa():
    itens = [_item("X|C|1", "C"), _item("X|C|2", "E")]
    p, _, _ = corrigir(itens, {"X|C|1": "E", "X|C|2": "C"})
    assert (p.nota, p.erradas) == (-2, 2)


def test_errado_anula_certo():
    itens = [_item("X|C|1", "C"), _item("X|C|2", "E"), _item("X|C|3", "C")]
    p, _, _ = corrigir(itens, {"X|C|1": "C", "X|C|2": "C"})
    assert (p.certas, p.erradas, p.brancos, p.nota) == (1, 1, 1, 0)


def test_anulada_fica_fora_da_nota_e_do_maximo():
    itens = [_item("X|C|1", "X", anulada=True), _item("X|C|2", "C")]
    for resposta in ("C", "E", None):
        respostas = {"X|C|2": "C"}
        if resposta:
            respostas["X|C|1"] = resposta
        p, _, corrigidos = corrigir(itens, respostas)
        assert (p.nota, p.nota_maxima, p.anuladas) == (1, 1, 1)
        assert corrigidos[0].situacao == "anulada"


def test_resposta_fora_da_prova_e_ignorada():
    p, _, _ = corrigir([_item("X|C|1", "C")], {"Y|C|9": "C"})
    assert (p.nota, p.brancos) == (0, 1)


def test_placar_por_materia_soma_o_geral():
    itens = [
        _item("X|C|1", "C", materia="A"),
        _item("X|C|2", "E", materia="A"),
        _item("X|C|3", "C", materia="B"),
        _item("X|C|4", "X", anulada=True, materia="B"),
    ]
    p, materias, _ = corrigir(itens, {"X|C|1": "C", "X|C|2": "C", "X|C|3": "C"})
    assert p.nota == 1
    por_id = {m.materia_id: m for m in materias}
    assert (por_id["A"].nota, por_id["A"].nota_maxima) == (0, 2)
    assert (por_id["B"].nota, por_id["B"].nota_maxima, por_id["B"].anuladas) == (
        1,
        1,
        1,
    )
    assert sum(m.nota for m in materias) == p.nota


# -- Prova real PF_25_ADM cargo 1 (com banco) --
@banco
def test_prova_em_ordem_e_sem_gabarito(cliente):
    r = cliente.get("/api/v1/simulados/prova", params=PROVA)
    assert r.status_code == 200
    prova = r.json()
    itens = prova["itens"]
    assert len(itens) == 120
    # Básico primeiro, depois específico; dentro do caderno, pelo número.
    tipos = [i["tipo_conhecimento"] for i in itens]
    assert tipos == sorted(tipos, key=lambda t: t != "basico")
    assert itens[0]["codigo_caderno"] == "094_PF_CB1_01"
    assert [i["numero"] for i in itens[:50]] == sorted(i["numero"] for i in itens[:50])
    assert "gabarito" not in itens[0]
    assert prova["discursivas"] and prova["discursivas"][0]["padrao_resposta"] is None
    html = cliente.get("/simulado/prova", params=PROVA).text
    assert "Encerrar e corrigir" in html
    assert "Padrão de resposta" not in html


@banco
def test_cargo_sem_prova_da_404(cliente):
    r = cliente.get(
        "/api/v1/simulados/prova", params={"concurso": "NAO_EXISTE", "cargo_numero": 1}
    )
    assert r.status_code == 404
    assert cliente.get("/simulado/prova?concurso=X&cargo_numero=1").status_code == 404


def _gabaritos(cliente):
    """Gabarito de cada item pela API de questões (fonte independente da correção)."""
    gabs, pagina = {}, 1
    while True:
        dados = cliente.get(
            "/api/v1/questoes",
            params={**PROVA, "tamanho_pagina": 50, "pagina": pagina},
        ).json()
        gabs.update(
            {q["questao_chave"]: (q["gabarito"], q["anulada"]) for q in dados["itens"]}
        )
        if pagina >= dados["total_paginas"]:
            return gabs
        pagina += 1


@banco
def test_padrao_conhecido_confere_a_mao(cliente):
    gabs = _gabaritos(cliente)
    validas = [c for c, (_, anulada) in gabs.items() if not anulada]
    # Padrão: tudo "C". Nota esperada = (#gabarito C) − (#gabarito E).
    certos = sum(1 for c in validas if gabs[c][0] == "C")
    errados = len(validas) - certos
    r = cliente.post(
        "/api/v1/simulados/correcao",
        json={**PROVA, "respostas": {c: "C" for c in gabs}},
    )
    placar_api = r.json()["placar"]
    assert placar_api["nota"] == certos - errados
    assert placar_api["nota_maxima"] == len(validas)
    assert placar_api["anuladas"] == len(gabs) - len(validas)
    # Padrão: gabarito em todas → nota máxima; nenhuma resposta → 0.
    r = cliente.post(
        "/api/v1/simulados/correcao",
        json={**PROVA, "respostas": {c: g for c, (g, a) in gabs.items() if not a}},
    )
    assert r.json()["placar"]["nota"] == len(validas)
    r = cliente.post("/api/v1/simulados/correcao", json={**PROVA, "respostas": {}})
    assert r.json()["placar"]["nota"] == 0
    assert r.json()["discursivas"][0]["padrao_resposta"]


@banco
def test_form_anonimo_corrige_sem_gravar(cliente):
    gabs = _gabaritos(cliente)
    chave = next(c for c, (g, a) in gabs.items() if not a)
    r = cliente.post("/simulado/iniciar", data=PROVA, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/simulado/prova?")
    r = cliente.post(
        "/simulado/corrigir",
        data={**PROVA, f"r:{chave}": gabs[chave][0], "r:lixo": "Z"},
    )
    assert r.status_code == 200
    assert "Resultado do simulado" in r.text
    assert "não fica guardado" in r.text


@banco
def test_simulado_gravado_encerra_uma_vez(cliente_logado):
    c, _ = cliente_logado
    r = c.post("/simulado/iniciar", data=PROVA, follow_redirects=False)
    url = r.headers["location"]
    simulado_id = int(url.rsplit("/", 1)[1])
    assert "Encerrar e corrigir" in c.get(url).text

    gabs = _gabaritos(c)
    validas = [k for k, (_, a) in gabs.items() if not a]
    certa, errada, anulada = (
        validas[0],
        validas[1],
        next(k for k, (_, a) in gabs.items() if a),
    )
    respostas = {
        f"r:{certa}": gabs[certa][0],
        f"r:{errada}": "E" if gabs[errada][0] == "C" else "C",
        f"r:{anulada}": "C",
        "simulado_id": str(simulado_id),
        **PROVA,
    }
    r = c.post("/simulado/corrigir", data=respostas, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == url

    resultado = c.get(f"/api/v1/simulados/{simulado_id}").json()
    assert resultado["placar"]["nota"] == 0
    assert resultado["placar"]["certas"] == 1 and resultado["placar"]["erradas"] == 1
    assert "Resultado do simulado" in c.get(url).text

    lista = c.get("/api/v1/simulados").json()
    assert lista[0]["id"] == simulado_id and lista[0]["nota"] == 0

    # Reenvio do form não duplica; pela API dá 409.
    c.post("/simulado/corrigir", data=respostas)
    r = c.post(f"/api/v1/simulados/{simulado_id}/correcao", json={"respostas": {}})
    assert r.status_code == 409
    again = c.get(f"/api/v1/simulados/{simulado_id}").json()
    assert again["placar"] == resultado["placar"]

    # O simulado não entra no histórico de questões avulsas.
    assert c.get("/api/v1/eu/desempenho").json() == []


@banco
def test_simulado_de_outro_usuario_nao_aparece(cliente_logado):
    c, _ = cliente_logado
    r = c.post("/api/v1/simulados", json=PROVA)
    assert r.status_code == 201
    simulado_id = r.json()["id"]
    # Outro usuário logado não enxerga o simulado.
    from app.servicos import contas_servico, simulados_servico

    outro = contas_servico.entrar_com_google(
        "teste-outro-simulado", "o@example.com", None
    )
    try:
        assert simulados_servico.obter_resultado(simulado_id, outro.id) is None
        assert simulados_servico.encerrar(simulado_id, outro.id, {}) is None
    finally:
        contas_servico.apagar_conta(outro.id)
    c.cookies.clear()
    assert c.get(f"/api/v1/simulados/{simulado_id}").status_code == 401
    r = c.get(f"/simulado/{simulado_id}", follow_redirects=False)
    assert r.status_code == 303


@banco
def test_cargo_com_itens_ilegiveis_avisa(cliente):
    # PF_25_ADM cargo 5: as 19 questões com `utilizavel=false` ficam de fora.
    params = {"concurso": "PF_25_ADM", "cargo_numero": 5}
    prova = cliente.get("/api/v1/simulados/prova", params=params).json()
    assert prova["itens_omitidos"] == 19
    assert (
        "19 itens desta prova ficaram de fora"
        in cliente.get("/simulado/prova", params=params).text
    )
    assert (
        cliente.get("/api/v1/simulados/prova", params=PROVA).json()["itens_omitidos"]
        == 0
    )


@banco
def test_rascunho_so_some_no_resultado(cliente):
    html = cliente.get("/simulado/prova", params=PROVA).text
    assert "removeItem" not in html
    r = cliente.post(
        "/simulado/corrigir",
        data=PROVA,
    )
    assert 'data-rascunho="simulado:PF_25_ADM|1"' in r.text
    assert "removeItem" in r.text


@banco
def test_login_caido_nao_corrige_simulado_gravado_como_avulso(cliente_logado):
    import base64
    import json

    from itsdangerous import TimestampSigner

    from app.config import settings

    c, _ = cliente_logado
    r = c.post("/simulado/iniciar", data=PROVA, follow_redirects=False)
    simulado_id = r.headers["location"].rsplit("/", 1)[1]
    # Sessão sem o usuário (login caiu), mas com o mesmo CSRF.
    corpo = base64.b64encode(json.dumps({"csrf": c.headers["X-CSRFToken"]}).encode())
    c.cookies.set(
        "sessao", TimestampSigner(settings.session_secret).sign(corpo).decode()
    )
    r = c.post(
        "/simulado/corrigir",
        data={**PROVA, "simulado_id": simulado_id},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/entrar?voltar=/simulado/{simulado_id}"


@banco
def test_duracao_nota_anterior_e_revisar_erradas(cliente_logado):
    c, _ = cliente_logado
    gabs = _gabaritos(c)
    validas = [k for k, (_, a) in gabs.items() if not a]
    errada = validas[0]
    contra = "E" if gabs[errada][0] == "C" else "C"

    # 1º simulado: uma certa (nota 1). Aberto, o endpoint dá 409.
    s1 = c.post("/api/v1/simulados", json=PROVA).json()["id"]
    assert c.get(f"/api/v1/simulados/{s1}/questoes").status_code == 409
    r1 = c.post(
        f"/api/v1/simulados/{s1}/correcao",
        json={"respostas": {validas[1]: gabs[validas[1]][0]}},
    ).json()
    assert r1["nota_anterior"] is None
    assert r1["duracao_segundos"] is not None and r1["duracao_segundos"] >= 0

    # 2º simulado: uma errada (nota −1); a anterior é a do 1º.
    s2 = c.post("/api/v1/simulados", json=PROVA).json()["id"]
    r2 = c.post(
        f"/api/v1/simulados/{s2}/correcao", json={"respostas": {errada: contra}}
    ).json()
    assert r2["nota_anterior"] == 1 and r2["placar"]["nota"] == -1
    assert c.get(f"/api/v1/simulados/{s2}").json()["nota_anterior"] == 1

    erradas = c.get(f"/api/v1/simulados/{s2}/questoes?situacao=errado").json()
    assert [q["questao_chave"] for q in erradas["itens"]] == [errada]
    brancos = c.get(f"/api/v1/simulados/{s2}/questoes?situacao=branco").json()
    assert brancos["total"] == r2["placar"]["brancos"]
    assert c.get("/api/v1/simulados/999999999/questoes").status_code == 404

    html = c.get(f"/simulado/{s2}").text
    assert "Duração" in html and "Simulado anterior" in html
    assert f"/simulado/{s2}/revisar?situacao=errado" in html
    assert "Questão" in c.get(f"/simulado/{s2}/revisar").text

    c.cookies.clear()
    assert c.get(f"/api/v1/simulados/{s2}/questoes").status_code == 401
