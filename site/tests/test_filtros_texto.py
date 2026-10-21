"""Filtros de conteúdo (5H.4): palavra-chave sem acento/caixa, `com` e o
atalho do ID curto, conferidos contra uma contagem independente do banco."""

import unicodedata

import pytest

from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel

pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)

# Termo real sem nó correspondente: no banco só aparece acentuado ("exceção"),
# então sem `unaccent` a busca daria 0.
TERMO = "excecao"


def _total(cliente, params):
    r = cliente.get("/api/v1/questoes", params={**params, "tamanho_pagina": 1})
    assert r.status_code == 200, r.text
    return r.json()["total"]


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


@pytest.fixture(scope="module")
def textos() -> dict[int, str]:
    """questao_id → enunciado + seção sem acento e em minúsculas (utilizáveis),
    normalizado em Python, sem `unaccent`."""
    conn = stats_writer.conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT questao_id, enunciado, secao"
                " FROM vw_questoes WHERE utilizavel"
            )
            return {
                qid: _sem_acento(f"{enunciado or ''} {secao or ''}")
                for qid, enunciado, secao in cur.fetchall()
            }
    finally:
        conn.close()


def _contar(textos: dict[int, str], *palavras: str) -> int:
    return sum(all(p in t for p in palavras) for t in textos.values())


def _sql_total(condicao: str) -> int:
    conn = stats_writer.conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(DISTINCT questao_id) FROM vw_questoes"
                f" WHERE utilizavel AND {condicao}"
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


# -- Modelo --
def test_modelo_texto_aparado_vazio_e_limite():
    from app.modelos import TAMANHO_MAX_TEXTO, FiltroQuestoes

    assert FiltroQuestoes(texto="  ação   penal ").texto == "ação penal"
    assert FiltroQuestoes(texto="   ").texto is None
    assert FiltroQuestoes(texto="").texto is None
    assert len(FiltroQuestoes(texto="x" * 500).texto) == TAMANHO_MAX_TEXTO


def test_modelo_com_descarta_desconhecidos():
    from app.modelos import FiltroQuestoes

    assert FiltroQuestoes(com="figuras").com == ["figuras"]
    assert FiltroQuestoes(com=["texto_base", "lixo", "", "texto_base"]).com == [
        "texto_base"
    ]
    assert FiltroQuestoes(com=["lixo", ""]).com is None


# -- Palavra-chave --
def test_texto_sem_acento_acha_acentuado(cliente, textos):
    esperado = _contar(textos, TERMO)
    assert esperado > 0
    assert _total(cliente, {"texto": TERMO}) == esperado
    # A forma acentuada e em maiúsculas dá o mesmo resultado.
    assert _total(cliente, {"texto": "EXCEÇÃO"}) == esperado
    assert _total(cliente, {"texto": "  Exceção  "}) == esperado
    itens = cliente.get(
        "/api/v1/questoes", params={"texto": TERMO, "tamanho_pagina": 50}
    ).json()["itens"]
    assert itens and all(
        TERMO in _sem_acento(f"{q['enunciado']} {q['secao'] or ''}") for q in itens
    )


def test_texto_varias_palavras_e(cliente, textos):
    esperado = _contar(textos, TERMO, "lei")
    assert 0 < esperado < _contar(textos, TERMO)
    assert _total(cliente, {"texto": f"{TERMO} lei"}) == esperado
    # Ordem indiferente.
    assert _total(cliente, {"texto": f"lei {TERMO}"}) == esperado


def test_texto_curinga_vale_como_literal(cliente, textos):
    sem_filtro = _total(cliente, {})
    for termo in ("%", "_", "50%", "\\"):
        esperado = _contar(textos, termo)
        assert esperado < sem_filtro
        assert _total(cliente, {"texto": termo}) == esperado, termo


def test_texto_vazio_e_sem_filtro(cliente):
    sem_filtro = _total(cliente, {})
    assert sem_filtro == 2781
    assert _total(cliente, {"texto": ""}) == sem_filtro
    assert _total(cliente, {"texto": "   "}) == sem_filtro


def test_texto_combina_com_outros_filtros(cliente, textos):
    total = _total(cliente, {"texto": TERMO})
    por_orgao = _total(cliente, {"texto": TERMO, "orgao": "PF"})
    assert por_orgao <= total
    assert _total(cliente, {"texto": TERMO, "anuladas": "excluir"}) <= total


# -- Questões com --
def test_com_texto_base_figuras_e_os_dois(cliente):
    tb = _sql_total("tem_texto_base")
    fig = _sql_total("tem_figuras")
    dois = _sql_total("tem_texto_base AND tem_figuras")
    assert 0 < dois <= min(tb, fig)
    assert _total(cliente, {"com": "texto_base"}) == tb
    assert _total(cliente, {"com": "figuras"}) == fig
    assert _total(cliente, {"com": ["texto_base", "figuras"]}) == dois
    # Valor desconhecido é descartado (sem 422).
    assert _total(cliente, {"com": ["lixo", ""]}) == _total(cliente, {})
    itens = cliente.get(
        "/api/v1/questoes", params={"com": "figuras", "tamanho_pagina": 50}
    ).json()["itens"]
    assert itens and all(q["tem_figuras"] for q in itens)


# -- Facetas --
def test_facetas_respeitam_texto_e_com(cliente):
    for params in (
        {"texto": TERMO},
        {"com": "figuras"},
        {"texto": TERMO, "com": "texto_base"},
    ):
        total = _total(cliente, params)
        facetas = cliente.get("/api/v1/facetas", params=params).json()
        # Cada questão tem um órgão, um concurso e um estado de anulação.
        assert sum(o["total"] for o in facetas["orgaos"]) == total, params
        assert sum(c["total"] for c in facetas["concursos"]) == total, params
        assert sum(a["total"] for a in facetas["anuladas"]) == total, params
        # O próprio filtro de órgão continua respeitando a palavra-chave.
        pf = next((o for o in facetas["orgaos"] if o["valor"] == "PF"), None)
        if pf:
            assert pf["total"] == _total(cliente, {**params, "orgao": "PF"})


def test_servico_lista_e_facetas_com_texto(cliente, textos):
    from app.modelos import FiltroQuestoes
    from app.servicos import questoes_servico

    filtros = FiltroQuestoes(texto=TERMO, com=["texto_base"])
    pagina = questoes_servico.listar_questoes(filtros, 1, 5)
    assert pagina.total == _total(cliente, {"texto": TERMO, "com": "texto_base"})
    facetas = questoes_servico.obter_facetas(filtros)
    assert sum(o.total for o in facetas.orgaos) == pagina.total


# -- Atalho do ID curto --
def test_texto_com_id_curto_filtra_a_questao(cliente):
    from app.servicos import questoes_servico
    from app.servicos.formatacao import codigo_curto

    chave = "PF_25_ADM|094_PF_CB1_01|1"
    codigo = codigo_curto(chave)
    assert questoes_servico.chave_do_termo(codigo) == chave
    assert questoes_servico.chave_do_termo(f"  {codigo.lower()} ") == chave
    for termo in (codigo, codigo.lower()):
        dados = cliente.get("/api/v1/questoes", params={"texto": termo}).json()
        assert dados["total"] == 1
        assert dados["itens"][0]["questao_chave"] == chave
        assert dados["itens"][0]["codigo"] == codigo
    facetas = cliente.get("/api/v1/facetas", params={"texto": codigo}).json()
    assert sum(o["total"] for o in facetas["orgaos"]) == 1


def test_chave_do_termo_invalido_devolve_none():
    from app.servicos import questoes_servico

    for termo in (None, "", "   ", "licitação", "Q123", "QZZZZZZZZ", "Q6AAB4214 x"):
        assert questoes_servico.chave_do_termo(termo) is None, termo


def test_id_curto_desconhecido_vira_busca_comum(cliente, textos):
    from app.servicos import questoes_servico

    codigos = set(questoes_servico._chaves_por_codigo())
    desconhecido = next(
        f"Q{n:08X}" for n in range(10_000) if f"Q{n:08X}" not in codigos
    )
    assert questoes_servico.chave_do_termo(desconhecido) is None
    esperado = _contar(textos, desconhecido.lower())
    assert _total(cliente, {"texto": desconhecido}) == esperado
