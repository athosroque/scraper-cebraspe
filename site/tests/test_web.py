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
    r = cliente.get("/questoes")
    assert r.status_code == 200
    assert "Árvore de Assuntos" in r.text
    assert ">2.781</strong> questões encontradas" in r.text
    assert '<meta name="description"' in r.text


def test_home_htmx_devolve_so_fragmento(cliente):
    r = cliente.get("/questoes", headers=HX)
    assert "<html" not in r.text
    assert "Árvore de Assuntos" not in r.text
    assert "questões encontradas" in r.text
    assert "HX-Request" in r.headers["vary"]


def test_restauracao_de_historico_devolve_pagina_inteira(cliente):
    r = cliente.get("/questoes", headers={**HX, "HX-History-Restore-Request": "true"})
    assert "<html" in r.text


def test_filtros_combinados_e_select_vazio(cliente):
    # O form manda todos os campos juntos; select "Todos" chega vazio.
    r = cliente.get(
        "/questoes",
        params={"orgao": "", "nivel": "superior", "no_id": "S-c33faee4a4"},
        headers=HX,
    )
    api = cliente.get(
        "/api/v1/questoes", params={"nivel": "superior", "no_id": "S-c33faee4a4"}
    ).json()
    assert f">{api['total']}</strong> questões encontradas" in r.text


def test_no_id_nao_entra_na_expressao_do_alpine(cliente):
    payload = "x');alert(1);//"
    r = cliente.get("/questoes", params={"no_id": payload})
    assert "alert(1)" not in r.text.split("x-data")[1].split("}")[0]
    assert 'data-no-id="x&#39;);alert(1);//"' in r.text


def test_hx_target_da_correcao_e_seletor_css_valido(cliente):
    r = cliente.get("/questoes", headers=HX)
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

    lista = cliente.get("/questoes", params=params, headers=HX).text
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
    assert "Fonte: CEBRASPE" in r.text
    assert "/questoes?no_id=" in r.text
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


def test_filtro_de_assunto_mostra_o_nome(cliente):
    materia = cliente.get("/api/v1/arvore").json()[0]
    r = cliente.get("/questoes", params={"no_id": materia["id"]})
    assert f'data-no-nome="{materia["nome"]}"' in r.text


def test_inicio_grade_de_materias(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Escolha sua matéria" in r.text
    assert "pico.min.css" not in r.text
    materia = cliente.get("/api/v1/arvore").json()[0]
    assert f'href="/materias/{materia["id"]}"' in r.text
    assert f'href="/questoes?no_id={materia["id"]}"' in r.text
    # O chip do assunto também sai no fragmento, com o nome.
    parcial = cliente.get("/questoes", params={"no_id": materia["id"]}, headers=HX)
    assert f"Assunto: {materia['nome']}" in parcial.text


def test_cargo_vazio_ao_trocar_concurso_nao_da_422(cliente):
    r = cliente.get(
        "/questoes", params={"concurso": "PF_25_ADM", "cargo_numero": ""}, headers=HX
    )
    assert r.status_code == 200


def test_chip_remove_so_aquele_filtro(cliente):
    r = cliente.get(
        "/questoes",
        params={"concurso": "PF_25_ADM", "cargo_numero": "1", "nivel": "superior"},
        headers=HX,
    )
    assert 'href="/questoes?concurso=PF_25_ADM&amp;cargo_numero=1"' in r.text
    # Tirar o concurso tira o cargo junto.
    assert 'href="/questoes?nivel=superior"' in r.text


def test_lista_aponta_para_questoes(cliente):
    r = cliente.get("/questoes", params={"concurso": "PF_25_ADM"})
    assert 'hx-get="/"' not in r.text
    assert 'hx-get="/questoes"' in r.text


def test_parecidas_html_sob_demanda(cliente):
    r = cliente.get("/q/PF_25_ADM/094_PF_CB1_01/13/parecidas")
    assert r.status_code == 200
    assert "/q/" in r.text
    assert cliente.get("/q/NAO/EXISTE/1/parecidas").status_code == 404


def test_detalhe_mostra_parecidas(cliente):
    r = cliente.get("/q/PF_25_ADM/094_PF_CB1_01/13")
    assert "Questões parecidas" in r.text
    assert "em breve" not in r.text


# -- Sessão 1 do plano de correções: paginação e 404/405 --
def test_pagina_fora_do_intervalo_redireciona_para_a_ultima(cliente):
    r = cliente.get("/questoes?pagina=999", follow_redirects=False)
    assert r.status_code in (302, 303, 307)
    assert "pagina=0" not in r.headers["location"]


def test_404_html_com_layout(cliente):
    r = cliente.get("/nao-existe", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "Página não encontrada" in r.text
    assert "Erro 404" in r.text


def test_404_api_responde_json(cliente):
    r = cliente.get("/api/v1/nao-existe", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert "detail" in r.json()


def test_404_de_materia_tem_texto_proprio(cliente):
    r = cliente.get("/materias/nao-existe", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "Matéria não encontrada" in r.text


def test_405_preserva_allow_e_mostra_405(cliente):
    r = cliente.post("/sobre", headers={"accept": "text/html"})
    assert r.status_code == 405
    assert "Erro 405" in r.text
    assert "allow" in r.headers


def test_simulado_inexistente_tem_texto_proprio(cliente_logado):
    cliente_logado, _ = cliente_logado
    r = cliente_logado.get("/simulado/999999999", headers={"accept": "text/html"})
    assert r.status_code == 404
    assert "Simulado não encontrado" in r.text


def test_facetas_tem_rotulos_legiveis(cliente):
    f = cliente.get("/api/v1/facetas").json()
    assert all("_" not in x["rotulo"] for x in f["concursos"])
    assert {x["rotulo"] for x in f["niveis"]} <= {"Superior", "Médio"}
    assert {x["rotulo"] for x in f["tipos_conhecimento"]} <= {"Básico", "Específico"}


def test_chips_de_nivel_e_tipo_com_rotulo(cliente):
    html = cliente.get(
        "/questoes", params={"nivel": "superior", "tipo_conhecimento": "basico"}
    ).text
    assert "Superior" in html and "Básico" in html
    assert "Nível: superior" not in html and "Tipo: basico" not in html


def test_milhar_com_ponto_nos_totais(cliente):
    html = cliente.get("/questoes").text
    assert ">2.781</strong>" in html and ">2781<" not in html


def test_materia_de_cargo_com_rotulo(cliente):
    arvore = cliente.get("/api/v1/arvore").json()
    mat = next((m for m in arvore if m.get("nome_de_cargo")), None)
    assert mat is not None
    html = cliente.get(f"/materias/{mat['id']}").text
    assert f"Conhecimentos específicos — {mat['nome']}" in html


def test_comando_e_assunto_no_topo_da_pagina_canonica(cliente):
    # PF_25_ADM 094_PF_CB2_01 item 24: os dados do item estão só no comando.
    q = cliente.get("/api/v1/questoes/PF_25_ADM|094_PF_CB2_01|24").json()
    assert "60 pessoas" in q["secao"]
    html = cliente.get("/q/PF_25_ADM/094_PF_CB2_01/24").text
    card = html[html.index("<article") :]
    rodape = card.index("<footer")
    i_assunto = card.index("data-assunto-topo")
    i_comando = card.index("data-comando")
    i_enunciado = card.index(q["enunciado"][:30])
    assert i_assunto < i_comando < i_enunciado < rodape
    assert "60 pessoas" in card[i_comando:i_enunciado]
    assert "data-assunto-topo" not in card[rodape:]


def test_lista_mostra_comando_e_recolhe_repetido(cliente):
    html = cliente.get("/questoes", params={"tamanho_pagina": 50}).text
    assert "data-comando" in html
    assert "Mesmo comando da questão anterior" in html


def test_simulado_traz_comando_sem_gabarito(cliente):
    params = {"concurso": "PF_25_ADM", "cargo_numero": 1}
    itens = cliente.get("/api/v1/simulados/prova", params=params).json()["itens"]
    assert any(i["secao"] for i in itens)
    assert all("gabarito" not in i for i in itens)
    html = cliente.get("/simulado/prova", params=params).text
    assert "data-comando" in html
