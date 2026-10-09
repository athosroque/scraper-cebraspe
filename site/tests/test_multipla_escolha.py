from types import SimpleNamespace

import pytest

from app.modelos import (
    RespostaEntrada,
)
from app.servicos.formatacao import letras_validas, rotulo_tipo_questao
from app.servicos.simulados_servico import corrigir, placar
from tests.test_stats_writer import _postgres_disponivel

banco = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


# -- Testes unitários de pontuação CEBRASPE (CE vs ME) --


def test_rotulo_tipo_questao():
    assert rotulo_tipo_questao("certo_errado") == "Certo/Errado"
    assert rotulo_tipo_questao("multipla_escolha") == "Múltipla Escolha"
    assert rotulo_tipo_questao("outro") == "Outro"


def test_placar_multipla_escolha_erro_nao_subtrai():
    # Em ME: acerto = +1, erro = 0, branco = 0, anulada = 0
    situacoes = [
        ("certo", "multipla_escolha"),
        ("errado", "multipla_escolha"),
        ("branco", "multipla_escolha"),
        ("anulada", "multipla_escolha"),
    ]
    p = placar(situacoes)
    assert p.certas == 1
    assert p.erradas == 1
    assert p.brancos == 1
    assert p.anuladas == 1
    assert p.nota == 1  # 1 acerto (+1), 1 erro (0) => nota 1
    assert p.nota_maxima == 3  # anulada não entra


def test_placar_certo_errado_erro_subtrai():
    # Em CE: acerto = +1, erro = -1, branco = 0, anulada = 0
    situacoes = [
        ("certo", "certo_errado"),
        ("errado", "certo_errado"),
        ("branco", "certo_errado"),
        ("anulada", "certo_errado"),
    ]
    p = placar(situacoes)
    assert p.certas == 1
    assert p.erradas == 1
    assert p.brancos == 1
    assert p.anuladas == 1
    assert p.nota == 0  # 1 acerto (+1), 1 erro (-1) => nota 0
    assert p.nota_maxima == 3


def test_placar_misto_ce_e_me():
    # 2 itens CE: 1 certo (+1), 1 errado (-1) => saldo CE = 0
    # 2 itens ME: 1 certo (+1), 1 errado (0)  => saldo ME = 1
    # Total esperado = 1
    situacoes = [
        ("certo", "certo_errado"),
        ("errado", "certo_errado"),
        ("certo", "multipla_escolha"),
        ("errado", "multipla_escolha"),
    ]
    p = placar(situacoes)
    assert p.certas == 2
    assert p.erradas == 2
    assert p.nota == 1
    assert p.nota_maxima == 4


def test_corrigir_itens_multipla_escolha():
    itens = [
        {
            "questao_chave": "TESTE|CAD|1",
            "numero": 1,
            "codigo_caderno": "CAD",
            "gabarito": "A",
            "anulada": False,
            "tipo": "multipla_escolha",
            "materia_id": "M1",
            "materia_nome": "Português",
        },
        {
            "questao_chave": "TESTE|CAD|2",
            "numero": 2,
            "codigo_caderno": "CAD",
            "gabarito": "B",
            "anulada": False,
            "tipo": "multipla_escolha",
            "materia_id": "M1",
            "materia_nome": "Português",
        },
        {
            "questao_chave": "TESTE|CAD|3",
            "numero": 3,
            "codigo_caderno": "CAD",
            "gabarito": "C",
            "anulada": False,
            "tipo": "multipla_escolha",
            "materia_id": "M1",
            "materia_nome": "Português",
        },
    ]
    # Usuário acertou o 1 (A), errou o 2 (marcou D), deixou o 3 em branco
    respostas = {"TESTE|CAD|1": "A", "TESTE|CAD|2": "D"}
    p, materias, corrigidos = corrigir(itens, respostas)

    assert p.certas == 1
    assert p.erradas == 1
    assert p.brancos == 1
    assert p.nota == 1  # No ME, o erro não anula o acerto
    assert p.nota_maxima == 3
    assert materias[0].nota == 1
    assert materias[0].nota_maxima == 3

    assert corrigidos[0].situacao == "certo"
    assert corrigidos[1].situacao == "errado"
    assert corrigidos[2].situacao == "branco"


def test_letras_validas_por_tipo():
    assert letras_validas("certo_errado") == ("C", "E")
    quatro = [{"letra": x, "texto": x} for x in "ABCD"]
    assert letras_validas("multipla_escolha", quatro) == ("A", "B", "C", "D")
    # ME sem alternativas extraídas aceita A–E.
    assert letras_validas("multipla_escolha", []) == ("A", "B", "C", "D", "E")


def test_corrigir_letra_fora_do_formato_conta_como_branco():
    itens = [
        {
            "questao_chave": "TESTE|CAD|1",
            "numero": 1,
            "codigo_caderno": "CAD",
            "gabarito": "C",
            "anulada": False,
            "tipo": "certo_errado",
        },
        {
            "questao_chave": "TESTE|CAD|2",
            "numero": 2,
            "codigo_caderno": "CAD",
            "gabarito": "A",
            "anulada": False,
            "tipo": "multipla_escolha",
            "alternativas": [{"letra": x, "texto": x} for x in "ABCD"],
        },
    ]
    # "A" num C/E e "E" num ME de A a D não existem na questão.
    p, _, corrigidos = corrigir(itens, {"TESTE|CAD|1": "A", "TESTE|CAD|2": "E"})
    assert [c.situacao for c in corrigidos] == ["branco", "branco"]
    assert [c.resposta for c in corrigidos] == [None, None]
    assert p.brancos == 2 and p.nota == 0


def test_modelo_resposta_aceita_a_ate_e():
    for letra in ("A", "B", "C", "D", "E"):
        r = RespostaEntrada(questao_chave="TESTE|CAD|1", resposta=letra)
        assert r.resposta == letra

    with pytest.raises(Exception):
        RespostaEntrada(questao_chave="TESTE|CAD|1", resposta="F")


# -- Testes com banco e endpoints --


@banco
def test_facetas_incluem_tipo_e_filtram(cliente):
    r = cliente.get("/api/v1/facetas")
    assert r.status_code == 200
    dados = r.json()
    assert "tipos" in dados
    tipos = {item["valor"]: item["total"] for item in dados["tipos"]}
    assert "certo_errado" in tipos
    assert tipos["certo_errado"] > 0

    # Filtro por tipo=certo_errado
    r_ce = cliente.get("/api/v1/questoes", params={"tipo": "certo_errado"})
    assert r_ce.status_code == 200
    dados_ce = r_ce.json()
    assert dados_ce["total"] == tipos["certo_errado"]
    for item in dados_ce["itens"]:
        assert item["tipo"] == "certo_errado"


@banco
def test_responder_api_confere_letra_com_o_tipo(cliente_logado):
    c, usuario = cliente_logado
    # O piloto só tem C/E: "A" não existe na questão e não pode ir ao histórico.
    itens = c.get("/api/v1/questoes", params={"tamanho_pagina": 1}).json()["itens"]
    assert len(itens) == 1 and itens[0]["tipo"] == "certo_errado"
    chave = itens[0]["questao_chave"]

    r = c.post("/api/v1/respostas", json={"questao_chave": chave, "resposta": "A"})
    assert r.status_code == 422
    assert "C, E" in r.json()["detail"]

    r_inv = c.post("/api/v1/respostas", json={"questao_chave": chave, "resposta": "Z"})
    assert r_inv.status_code == 422

    r_ok = c.post("/api/v1/respostas", json={"questao_chave": chave, "resposta": "C"})
    assert r_ok.status_code == 200
    assert r_ok.json()["tipo"] == "certo_errado"
    assert r_ok.json()["gravada"] is True


@banco
def test_corrigir_questao_web_certo_errado_recusa_letra_de_alternativa(cliente):
    itens = cliente.get("/api/v1/questoes", params={"tamanho_pagina": 1}).json()[
        "itens"
    ]
    chave = itens[0]["questao_chave"]

    # O tipo vem do banco: "A" num C/E devolve o form de Certo/Errado com aviso.
    r = cliente.post("/q/correcao", data={"chave": chave, "resposta": "A"})
    assert r.status_code == 200
    assert "Marque Certo ou Errado antes de responder." in r.text
    assert "Sua resposta:" not in r.text

    r_c = cliente.post("/q/correcao", data={"chave": chave, "resposta": "C"})
    assert "Sua resposta:" in r_c.text


@banco
def test_corrigir_questao_web_multipla_escolha(cliente, monkeypatch):
    # Ainda não há questão ME no banco: a questão vem do serviço simulado.
    from app.servicos import questoes_servico

    alts = [{"letra": x, "texto": f"Opção {x}"} for x in "ABCD"]
    questao = SimpleNamespace(
        tipo="multipla_escolha", alternativas=alts, gabarito="B", anulada=False
    )
    monkeypatch.setattr(questoes_servico, "obter_questao_por_chave", lambda _: questao)

    sem = cliente.post("/q/correcao", data={"chave": "TESTE|CAD|1"})
    assert "Escolha uma alternativa antes de responder." in sem.text
    assert sem.text.count('type="radio"') == 4

    # "E" não existe numa questão de A a D.
    fora = cliente.post("/q/correcao", data={"chave": "TESTE|CAD|1", "resposta": "E"})
    assert "Escolha uma alternativa antes de responder." in fora.text

    certo = cliente.post("/q/correcao", data={"chave": "TESTE|CAD|1", "resposta": "B"})
    assert "Você acertou! O gabarito é Alternativa B." in certo.text

    errado = cliente.post("/q/correcao", data={"chave": "TESTE|CAD|1", "resposta": "C"})
    assert "Sua resposta: <strong>Alternativa C</strong>" in errado.text


def test_render_componente_form_resposta_multipla_escolha(cliente):
    # Testa renderização do macro form_resposta quando tipo é multipla_escolha
    from app.web.rotas_web import templates

    alts = [
        {"letra": "A", "texto": "Opção Primeira"},
        {"letra": "B", "texto": "Opção Segunda"},
        {"letra": "C", "texto": "Opção Terceira"},
        {"letra": "D", "texto": "Opção Quarta"},
        {"letra": "E", "texto": "Opção Quinta"},
    ]
    template_str = """
    {% import "_componentes.html" as c %}
    {{ c.form_resposta("TESTE|CAD|1", tipo="multipla_escolha", alternativas=alts) }}
    """
    tmpl = templates.env.from_string(template_str)
    html = tmpl.render(alts=alts)

    assert 'value="A"' in html
    assert 'value="B"' in html
    assert 'value="C"' in html
    assert 'value="D"' in html
    assert 'value="E"' in html
    assert "Opção Primeira" in html
    assert "Opção Quinta" in html
    assert "destaque-600" in html
    # Garante que não existem classes proibidas de cor azul
    assert "blue-" not in html


def test_render_correcao_multipla_escolha(cliente):
    from app.web.rotas_web import templates

    alts = [
        {"letra": "A", "texto": "Opção A"},
        {"letra": "B", "texto": "Opção B"},
        {"letra": "C", "texto": "Opção C"},
        {"letra": "D", "texto": "Opção D"},
        {"letra": "E", "texto": "Opção E"},
    ]
    resultado = {
        "questao_chave": "TESTE|CAD|1",
        "gabarito": "B",
        "resposta": "B",
        "acertou": True,
        "anulada": False,
        "tipo": "multipla_escolha",
        "alternativas": alts,
        "gravada": False,
    }
    html = templates.TemplateResponse(
        request=None,
        name="_correcao.html",
        context={"resultado": resultado, "logado": False},
    ).body.decode()

    assert "Você acertou! O gabarito é Alternativa B." in html
    assert "Sua resposta: <strong>Alternativa B</strong>" in html
    assert "Gabarito" in html
    assert "blue-" not in html
