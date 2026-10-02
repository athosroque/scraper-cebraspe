import pytest

from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def test_listar_questoes_sem_filtro_total_2781_utilizaveis(cliente):
    response = cliente.get("/api/v1/questoes")
    assert response.status_code == 200
    dados = response.json()
    assert dados["total"] == 2781
    assert len(dados["itens"]) == 20
    assert dados["pagina"] == 1
    assert dados["tamanho_pagina"] == 20
    assert dados["total_paginas"] == 140


def test_filtro_subassunto_lingua_portuguesa_superior(cliente):
    # S-c33faee4a4 = Concordância verbal e nominal
    response = cliente.get("/api/v1/questoes?no_id=S-c33faee4a4&nivel=superior")
    assert response.status_code == 200
    dados = response.json()

    assert dados["total"] == 7
    chaves = [item["questao_chave"] for item in dados["itens"]]

    chaves_esperadas = [
        "CD_25_NS|167_CDNS_CG1_01|2",
        "IBAMA_25|057_IBAMA_CB1_01|3",
        "IBAMA_25|057_IBAMA_CB2_01|8",
        "PF_25_ADM|094_PF_CB1_01|13",
        "PF_25_ADM|094_PF_CB1_01|14",
        "STM_25|072_STM_CG3_01|6",
        "STM_25|072_STM_CG5_01|9",
    ]
    assert chaves == chaves_esperadas


def test_detalhe_questao_chave(cliente):
    chave = "PF_25_ADM|094_PF_CB1_01|13"
    response = cliente.get(f"/api/v1/questoes/{chave}")
    assert response.status_code == 200
    dados = response.json()

    assert dados["questao_chave"] == chave
    assert dados["gabarito"] == "C"
    assert dados["concurso"] == "PF_25_ADM"
    assert dados["codigo_caderno"] == "094_PF_CB1_01"

    # Texto-base da PF
    assert dados["tem_texto_base"] is True
    assert "Vigiar e punir" in dados["texto_base_texto"]

    # Link do PDF
    assert "link_pdf" in dados
    assert "094_PF_CB1_01.pdf" in dados["link_pdf"]


def test_detalhe_questao_nao_encontrada(cliente):
    response = cliente.get("/api/v1/questoes/NAO_EXISTE|123|1")
    assert response.status_code == 404


def test_arvore_hierarquica(cliente):
    response = cliente.get("/api/v1/arvore")
    assert response.status_code == 200
    arvore = response.json()

    assert len(arvore) > 0
    # Verifica a matéria Língua Portuguesa
    mat_pt = next(n for n in arvore if n["nome"] == "LÍNGUA PORTUGUESA")
    assert mat_pt["total_questoes"] == 178
    assert len(mat_pt["filhos"]) > 0


def test_facetas(cliente):
    response = cliente.get("/api/v1/facetas")
    assert response.status_code == 200
    dados = response.json()

    # Total de bancas (só CEBRASPE)
    assert len(dados["bancas"]) == 1
    assert dados["bancas"][0]["valor"] == "CEBRASPE"

    # Órgãos (PF, STM, IBAMA, CD, TCU)
    orgaos = {o["valor"]: o["total"] for o in dados["orgaos"]}
    assert orgaos["PF"] == 1131
    assert orgaos["STM"] == 950
    assert orgaos["IBAMA"] == 310
    assert orgaos["CD"] == 270
    assert orgaos["TCU"] == 120


def test_permissoes_role_site_leitura():
    """Testa isoladamente que a role site_leitura não tem permissão de DELETE"""
    import psycopg2
    from app.config import settings

    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.site_db_leitura_user,
        password=settings.site_db_leitura_password,
    )
    with conn.cursor() as cur:
        # SELECT nas views funciona
        cur.execute("SELECT count(*) FROM vw_questoes")
        assert cur.fetchone()[0] == 4075

        # INSERT ou DELETE em tabelas falha
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM questoes")

    conn.close()


def test_utilizaveis_todas_inclui_as_19_ilegiveis(cliente):
    todas = cliente.get("/api/v1/questoes?utilizaveis=todas").json()
    assert todas["total"] == 2800
    ilegiveis = cliente.get(
        "/api/v1/questoes?utilizaveis=todas&concurso=PF_25_ADM&tamanho_pagina=50"
    ).json()
    chave = "PF_25_ADM|094_PF_005_01|52"
    padrao = cliente.get("/api/v1/questoes?concurso=PF_25_ADM&tamanho_pagina=50").json()
    assert ilegiveis["total"] - padrao["total"] == 19
    # O detalhe por chave continua acessível (link direto), marcado como não utilizável.
    assert cliente.get(f"/api/v1/questoes/{chave}").json()["utilizavel"] is False


def test_filtro_invalido_devolve_422(cliente):
    assert cliente.get("/api/v1/questoes?anuladas=xyz").status_code == 422
    assert cliente.get("/api/v1/questoes?fora_do_edital=talvez").status_code == 422
    assert cliente.get("/api/v1/questoes?tamanho_pagina=51").status_code == 422


def test_saude_ok(cliente):
    resposta = cliente.get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


CHAVE_PF = "PF_25_ADM|094_PF_CB1_01|13"


def test_parecidas_mesmo_no_sem_a_propria(cliente):
    detalhe = cliente.get(f"/api/v1/questoes/{CHAVE_PF}").json()
    principal = next(n for n in detalhe["nos"] if n["papel"] == "principal")

    response = cliente.get(f"/api/v1/questoes/{CHAVE_PF}/parecidas?limite=20")
    assert response.status_code == 200
    itens = response.json()
    assert 0 < len(itens) <= 20
    chaves = [i["questao_chave"] for i in itens]
    assert CHAVE_PF not in chaves
    assert len(set(chaves)) == len(chaves)
    for item in itens:
        ids = set()
        for n in item["nos"]:
            ids |= {n["no_id"], n["assunto_id"], n["materia_id"]}
        assert principal["no_id"] in ids
    # Sem enunciado repetido entre si nem com a própria questão.
    enunciados = [i["enunciado"] for i in itens]
    assert len(set(enunciados)) == len(enunciados)
    assert detalhe["enunciado"] not in enunciados


def test_parecidas_404(cliente):
    response = cliente.get("/api/v1/questoes/NAO|EXISTE|1/parecidas")
    assert response.status_code == 404


def test_incidencia_na_listagem_e_no_detalhe(cliente):
    itens = cliente.get("/api/v1/questoes?tamanho_pagina=50").json()["itens"]
    com = [i for i in itens if i["incidencia"]]
    assert com
    for i in com:
        inc = i["incidencia"]
        assert 1 <= inc["posicao"] <= inc["total_subassuntos"]
        principal = next(n for n in i["nos"] if n["papel"] == "principal")
        assert inc["no_id"] == principal["no_id"]
    chave = com[0]["questao_chave"]
    detalhe = cliente.get(f"/api/v1/questoes/{chave}").json()
    assert detalhe["incidencia"] == com[0]["incidencia"]
