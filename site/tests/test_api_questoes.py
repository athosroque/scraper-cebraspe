import pytest

from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def _consulta(sql, params=()):
    with stats_writer.conectar() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# O piloto (P71/K22) é invariante: 5 concursos, 2.800 itens, 2.781 utilizáveis.
# Testes que precisam de um total fixo filtram por ele, em vez do total global
# do banco (que cresce a cada concurso novo).
PILOTO = ["PF_25_ADM", "TCU_25_TEFC", "IBAMA_25", "STM_25", "CD_25_NS"]


def test_listar_questoes_piloto_sem_filtro_total_2781_utilizaveis(cliente):
    response = cliente.get("/api/v1/questoes", params={"concurso": PILOTO})
    assert response.status_code == 200
    dados = response.json()
    assert dados["total"] == 2781
    assert len(dados["itens"]) == 20
    assert dados["pagina"] == 1
    assert dados["tamanho_pagina"] == 20
    assert dados["total_paginas"] == 140


def test_filtro_subassunto_lingua_portuguesa_superior(cliente):
    # S-c33faee4a4 = Concordância verbal e nominal. Restrito ao piloto: outro
    # concurso pode classificar questões no mesmo subassunto sem quebrar o teste.
    response = cliente.get(
        "/api/v1/questoes",
        params={"no_id": "S-c33faee4a4", "nivel": "superior", "concurso": PILOTO},
    )
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
    # Verifica a matéria Língua Portuguesa. `/api/v1/arvore` não aceita filtro
    # de concurso (lista a árvore inteira), então o total não é fixo: cresce
    # a cada classificação aprovada (ADR-044 §5). O esperado vem de
    # `fn_prova_cobra('materia')`, a mesma base que `obter_arvore_com_contagens`
    # soma para montar a contagem de cada nó.
    materia_id = _consulta(
        "SELECT id FROM vw_no_caminho WHERE nivel = 'materia' "
        "AND nome = 'Língua Portuguesa'"
    )[0][0]
    esperado = _consulta(
        "SELECT questoes FROM fn_prova_cobra('materia') WHERE no_id = %s",
        (materia_id,),
    )[0][0]
    mat_pt = next(n for n in arvore if n["nome"] == "Língua Portuguesa")
    assert mat_pt["total_questoes"] == esperado
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
    """Testa isoladamente que a role site_leitura não tem permissão de DELETE
    e que enxerga os mesmos dados que a role de escrita — sem fixar o total
    (o banco cresce a cada concurso novo)."""
    import psycopg2

    from app.config import settings
    from src import stats_writer

    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.site_db_leitura_user,
        password=settings.site_db_leitura_password,
    )
    admin = stats_writer.conectar()
    try:
        with admin.cursor() as cur_admin:
            cur_admin.execute("SELECT count(*) FROM vw_questoes")
            esperado = cur_admin.fetchone()[0]
        assert esperado > 0

        with conn.cursor() as cur:
            # SELECT nas views funciona e vê o mesmo total da role de escrita
            cur.execute("SELECT count(*) FROM vw_questoes")
            assert cur.fetchone()[0] == esperado

            # INSERT ou DELETE em tabelas falha
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cur.execute("DELETE FROM questoes")
    finally:
        conn.close()
        admin.close()


def test_utilizaveis_todas_inclui_as_19_ilegiveis(cliente):
    todas = cliente.get(
        "/api/v1/questoes", params={"utilizaveis": "todas", "concurso": PILOTO}
    ).json()
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
    assert cliente.get("/api/v1/questoes?tamanho_pagina=51").status_code == 422


def test_fora_do_edital_antigo_e_ignorado(cliente):
    """O filtro saiu do site (ADR-035, 2026-10-07): link antigo com o parâmetro
    não dá 422 e devolve o mesmo que sem ele."""
    todas = cliente.get("/api/v1/questoes?tamanho_pagina=1").json()["total"]
    for valor in ("nao", "sim", "talvez"):
        r = cliente.get(f"/api/v1/questoes?fora_do_edital={valor}&tamanho_pagina=1")
        assert r.status_code == 200
        assert r.json()["total"] == todas
        r = cliente.get(f"/api/v1/facetas?fora_do_edital={valor}")
        assert r.status_code == 200
    # Nem o filtro nem o campo do nó aparecem no contrato.
    contrato = cliente.get("/openapi.json").text
    assert "fora_do_edital" not in contrato
    questao = cliente.get("/api/v1/questoes?tamanho_pagina=1").json()["itens"][0]
    assert all("fora_do_edital" not in n for n in questao["nos"])


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


def test_facetas_ordenacao(cliente):
    response = cliente.get("/api/v1/facetas")
    assert response.status_code == 200
    dados = response.json()

    # concurso por orgao e ano
    concursos = [c["valor"] for c in dados["concursos"]]
    assert (
        concursos == sorted(concursos)
    )  # Wait, it sorts by orgao then ano. Since slug is ORGAO_ANO, sorting alphabetically works, let's just assert that it's ordered by orgao, ano.

    # nivel Superior antes de Medio
    niveis = [n["valor"] for n in dados["niveis"]]
    assert niveis == ["superior", "medio"]

    # cargos por numero
    cargos = [(c["concurso"], c["cargo_numero"]) for c in dados["cargos"]]
    # check that for each concurso, cargo_numero is ascending
    from itertools import groupby

    for _, grupo in groupby(cargos, key=lambda x: x[0]):
        numeros = [x[1] for x in grupo]
        assert numeros == sorted(numeros)
