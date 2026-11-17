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
    total = cliente.get("/api/v1/questoes", params={"tamanho_pagina": 1}).json()[
        "total"
    ]
    total_fmt = f"{total:,}".replace(",", ".")
    r = cliente.get("/questoes")
    assert r.status_code == 200
    assert 'data-chave="materia"' in r.text
    assert f">{total_fmt}</strong> questões encontradas" in r.text
    assert '<meta name="description"' in r.text


def test_home_htmx_devolve_so_fragmento(cliente):
    r = cliente.get("/questoes", headers=HX)
    assert "<html" not in r.text
    assert 'data-chave="materia"' not in r.text
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
    # O valor só entra em JSON (tojson escapa a aspa), nunca em expressão.
    for expr in re.findall(
        r'(?:x-data|x-init|:value|@click|@change)="([^"]*)"', r.text
    ):
        assert "alert" not in expr
    assert '"x\\u0027);alert(1);//"' in r.text


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


@pytest.mark.parametrize("resposta", [None, "", "X"])
def test_correcao_sem_marcacao_devolve_o_form_com_aviso(cliente, resposta):
    # Sem marcação o HTMX troca o form por ele mesmo com o aviso (não um 422).
    # O tipo é pedido explicitamente: o aviso deste caso é o de Certo/Errado, e
    # desde o BANRISUL_25 a 1ª questão sem filtro pode ser de múltipla escolha.
    q = _questao(cliente, tipo="certo_errado")
    dados = {"chave": q["questao_chave"]}
    if resposta is not None:
        dados["resposta"] = resposta
    r = cliente.post("/q/correcao", data=dados)
    assert r.status_code == 200
    assert "Marque Certo ou Errado antes de responder." in r.text
    assert re.search(r'<div id="q-[0-9a-f]{12}">', r.text)
    assert r.text.count('name="resposta"') == 2
    assert "Você acertou" not in r.text and "Você errou" not in r.text


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
    # Chip "Disciplina: <nome>" (5H.3: só o nome do nó, sem caminho), removível.
    assert 'aria-label="Remover filtro Disciplina: ' + materia["nome"] + '"' in r.text


def test_inicio_grade_de_materias(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Escolha sua disciplina" in r.text
    assert "pico.min.css" not in r.text
    materia = cliente.get("/api/v1/arvore").json()[0]
    assert f'href="/materias/{materia["id"]}"' in r.text
    assert f'href="/questoes?no_id={materia["id"]}"' in r.text
    # Desde a 5H.3 o chip mora no "Filtrar por:" do painel (Alpine; <noscript>
    # com o link do servidor), não no fragmento da lista. A página inteira traz
    # o chip com o nome; o fragmento leva o nome nas facetas (OOB), que o
    # painel usa para rotular o chip.
    pagina = cliente.get("/questoes", params={"no_id": materia["id"]})
    assert (
        'aria-label="Remover filtro Disciplina: ' + materia["nome"] + '"' in pagina.text
    )
    parcial = cliente.get("/questoes", params={"no_id": materia["id"]}, headers=HX)
    assert 'id="dados-facetas"' in parcial.text
    assert "Remover filtro" not in parcial.text
    assert materia["nome"] in parcial.text


def test_cargo_vazio_ao_trocar_concurso_nao_da_422(cliente):
    r = cliente.get(
        "/questoes", params={"concurso": "PF_25_ADM", "cargo_numero": ""}, headers=HX
    )
    assert r.status_code == 200


def test_chip_remove_so_aquele_filtro(cliente):
    # Os chips do servidor ficam no <noscript> do painel (página inteira, 5H.3).
    r = cliente.get(
        "/questoes",
        params={"concurso": "PF_25_ADM", "cargo_numero": "1", "nivel": "superior"},
    )
    # O link antigo vira o cargo `PF_25_ADM:1` (5G.4).
    assert 'href="/questoes?concurso=PF_25_ADM&amp;cargo=PF_25_ADM%3A1"' in r.text
    # Tirar o concurso tira o cargo dele junto.
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
    assert "Disciplina não encontrada" in r.text


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
    # Formatação com separador de milhar, não o valor (que cresce a cada
    # concurso novo): confere o formatado e que a forma sem ponto não aparece.
    total = cliente.get("/api/v1/questoes", params={"tamanho_pagina": 1}).json()[
        "total"
    ]
    assert total >= 1000, "teste pressupõe total de 4 dígitos para checar o separador"
    total_fmt = f"{total:,}".replace(",", ".")
    html = cliente.get("/questoes").text
    assert f">{total_fmt}</strong>" in html and f">{total}<" not in html


def test_disciplina_curada_mostra_area_e_edital_mostra_cargo(cliente):
    # 2026-10-07 (ADR-030): as 12 disciplinas com nome de cargo da PF viraram
    # a área (Estatística, Psicologia...). O nó nunca vira "Conhecimentos
    # específicos — <nome do nó>"; esse rótulo é só do lado do edital, com o
    # cargo de verdade e por concurso.
    arvore = cliente.get("/api/v1/arvore").json()
    nomes = {m["nome"] for m in arvore}
    assert {"Estatística", "Psicologia", "Pedagogia", "Comunicação Social"} <= nomes
    assert (
        not {"ESTATÍSTICO", "PSICÓLOGO CLÍNICO", "TÉCNICO EM COMUNICAÇÃO SOCIAL"}
        & nomes
    )
    assert not any(m.get("nome_de_cargo") for m in arvore)
    mat = next(m for m in arvore if m["nome"] == "Estatística")
    html = cliente.get(f"/materias/{mat['id']}").text
    assert (
        "Estatística" in html and "Conhecimentos específicos — Estatística" not in html
    )

    def rotulos(concurso, cargo):
        params = {"concurso": concurso, "cargo_numero": cargo}
        api = cliente.get("/api/v1/estatisticas/edital-vs-prova", params=params)
        return {p["rotulo_materia"] for p in api.json()["peso_materias"]}

    # PF cargo 14 e STM cargo 4 caem no mesmo nó (Comunicação Social).
    assert "Conhecimentos específicos — TÉCNICO EM COMUNICAÇÃO SOCIAL" in rotulos(
        "PF_25_ADM", 14
    )
    stm = rotulos("STM_25", 4)
    assert "Comunicação Social" in stm
    assert not any(r.startswith("Conhecimentos específicos") for r in stm)


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


# -- 5H.2: card novo da questão --
def _cards(html):
    return html.split("<article")[1:]


def test_card_da_lista_tem_posicao_codigo_e_resposta(cliente):
    # `tipo` fixo porque o corpo do teste conta os 2 radios do Certo/Errado; sem
    # ele, uma questão de múltipla escolha (5 radios) entra na página e quebra.
    params = {"tamanho_pagina": 5, "pagina": 2, "tipo": "certo_errado"}
    api = cliente.get("/api/v1/questoes", params=params).json()["itens"]
    cards = _cards(cliente.get("/questoes", params=params, headers=HX).text)
    assert len(cards) == len(api)
    for i, (item, card) in enumerate(zip(api, cards), start=6):
        assert re.search(rf"data-posicao[^>]*>{i}</span>", card)
        assert f">{item['codigo']}</a>" in card
        # Dois radios e o Responder sem `disabled` estático (só o do Alpine).
        assert card.count('type="radio" name="resposta"') == 2
        botao = re.search(r"<button[^>]*>Responder</button>", card).group(0)
        assert ":disabled=" in botao
        assert re.search(r"\sdisabled[\s>=]", botao.replace(":disabled=", "")) is None
        assert '<legend class="sr-only">Sua resposta</legend>' in card


def test_detalhe_nao_mostra_posicao(cliente):
    q = _questao(cliente)
    html = cliente.get(_url(q["questao_chave"])).text
    assert "data-posicao" not in html
    assert f">{q['codigo']}</a>" in html


def test_card_metadados_e_acoes(cliente):
    q = cliente.get("/api/v1/questoes/PF_25_ADM|094_PF_CB2_01|24").json()
    card = _cards(cliente.get("/q/PF_25_ADM/094_PF_CB2_01/24").text)[0]
    assert 'href="/questoes?banca=CEBRASPE"' in card
    assert 'href="/questoes?orgao=PF"' in card
    assert 'href="/questoes?concurso=PF_25_ADM"' in card
    cargo = q["cargos"][0]
    assert (
        f"CEBRASPE - 2025 - PF - Cargo {cargo['cargo_numero']}: {cargo['cargo']}"
        in card
    )
    # Cada nível do caminho do nó principal linka a lista daquele nó.
    principal = next(n for n in q["nos"] if n["papel"] == "principal")
    for no_id in (principal["materia_id"], principal["no_id"]):
        assert f'href="/questoes?no_id={no_id}"' in card
    assert f'href="/materias/{principal["materia_id"]}"' in card
    assert f"subject=Erro%20na%20quest%C3%A3o%20{q['codigo']}" in card
    assert f'href="{q["link_pdf"]}"' in card and "Caderno (PDF)" in card
    # Crédito da fonte continua obrigatório (ADR-033).
    assert "Fonte: CEBRASPE — PF 2025, caderno 094_PF_CB2_01, item 24." in card


def test_card_da_lista_sem_pdf_e_com_parecidas_sob_demanda(cliente):
    html = cliente.get("/questoes", params={"tamanho_pagina": 3}, headers=HX).text
    assert "Caderno (PDF)" not in html
    assert 'hx-trigger="toggle[target.open] once"' in html
    assert "Notificar erro" in html


def test_caderno_basico_mostra_quantos_cargos(cliente):
    # Caderno básico CB1 da PF: aplicado aos cargos de nível superior.
    q = cliente.get("/api/v1/questoes/PF_25_ADM|094_PF_CB1_01|13").json()
    assert len(q["cargos"]) > 1
    card = _cards(cliente.get(_url(q["questao_chave"])).text)[0]
    assert f"· {len(q['cargos'])} cargos" in card
    assert "CEBRASPE - 2025 - PF</a>" in card
