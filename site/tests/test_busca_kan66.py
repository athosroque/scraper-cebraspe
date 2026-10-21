"""Testes das partes 2, 3 e 4 do KAN-66 (busca do site).

- Palavra-chave = texto + classificação
- Sigla como palavra inteira ("LAI" não casa "laicização")
- Variações de número da lei ("12.527", "12527", "nº 12.527")
- Sugestões ao digitar na palavra-chave
- Cascata sem trava (assunto e subassunto sem disciplina marcada)
- "LGPD", "LAI", "12527" e "LRF" na palavra-chave trazem as questões do nó
"""

import pytest

from tests.test_stats_writer import _postgres_disponivel

com_banco = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

HX = {"HX-Request": "true"}


@com_banco
def test_busca_traz_questoes_classificadas_no_no(cliente):
    """Palavra-chave traz questões classificadas no nó mesmo quando o texto não cita o termo."""
    # LGPD: 13 no nó, 11 no texto, 17 na união (6 questões do nó não citam LGPD no texto)
    r_lgpd = cliente.get(
        "/api/v1/questoes", params={"texto": "LGPD", "tamanho_pagina": 50}
    )
    assert r_lgpd.status_code == 200
    dados_lgpd = r_lgpd.json()
    assert dados_lgpd["total"] == 17

    # Todas as 13 questões classificadas no nó da LGPD estão presentes nos resultados
    r_no = cliente.get(
        "/api/v1/questoes", params={"no_id": "NS-11c10a8ea6", "tamanho_pagina": 50}
    )
    chaves_do_no = {q["questao_chave"] for q in r_no.json()["itens"]}
    assert len(chaves_do_no) == 13

    # Busca em páginas maiores ou consulta de chaves
    r_todas = cliente.get(
        "/api/v1/questoes", params={"texto": "LGPD", "tamanho_pagina": 50}
    )
    chaves_busca = {q["questao_chave"] for q in r_todas.json()["itens"]}
    assert chaves_do_no.issubset(chaves_busca)


@com_banco
def test_sigla_como_palavra_inteira_nao_casa_subpalavra(cliente):
    """'LAI' não casa 'laicização' (PF_25_ADM|094_PF_002_01|105 tem laicização)."""
    r = cliente.get("/api/v1/questoes", params={"texto": "LAI", "tamanho_pagina": 50})
    assert r.status_code == 200
    chaves = {q["questao_chave"] for q in r.json()["itens"]}
    assert "PF_25_ADM|094_PF_002_01|105" not in chaves


@com_banco
def test_variacoes_numero_lei_mesmo_resultado(cliente):
    """'12.527', '12527' e 'nº 12.527' dão o mesmo resultado."""
    t1 = cliente.get(
        "/api/v1/questoes", params={"texto": "12.527", "tamanho_pagina": 50}
    ).json()
    t2 = cliente.get(
        "/api/v1/questoes", params={"texto": "12527", "tamanho_pagina": 50}
    ).json()
    t3 = cliente.get(
        "/api/v1/questoes", params={"texto": "nº 12.527", "tamanho_pagina": 50}
    ).json()

    assert t1["total"] == t2["total"] == t3["total"] == 13
    chaves1 = {q["questao_chave"] for q in t1["itens"]}
    chaves2 = {q["questao_chave"] for q in t2["itens"]}
    chaves3 = {q["questao_chave"] for q in t3["itens"]}
    assert chaves1 == chaves2 == chaves3


@com_banco
def test_lrf_traz_questoes_do_no(cliente):
    """'LRF' na palavra-chave traz as questões classificadas sob o nó da LRF."""
    r = cliente.get("/api/v1/questoes", params={"texto": "LRF", "tamanho_pagina": 50})
    assert r.status_code == 200
    dados = r.json()
    # 18 questões classificadas sob o assunto AL-02b4bc3a67 e descendentes + 1 no texto fora do nó = 19
    assert dados["total"] == 19

    # Confere que as 18 do nó estão inclusas
    r_no = cliente.get(
        "/api/v1/questoes", params={"no_id": "AL-02b4bc3a67", "tamanho_pagina": 50}
    )
    chaves_do_no = {q["questao_chave"] for q in r_no.json()["itens"]}
    assert len(chaves_do_no) == 18
    chaves_busca = {q["questao_chave"] for q in dados["itens"]}
    assert chaves_do_no.issubset(chaves_busca)


@com_banco
def test_sugestoes_ao_digitar_na_palavra_chave(cliente):
    """Endpoint /questoes/sugestoes devolve sugestões formatadas com caminho e total."""
    r = cliente.get("/questoes/sugestoes", params={"q": "LGPD"})
    assert r.status_code == 200
    itens = r.json()
    assert len(itens) >= 1
    lgpd = next(i for i in itens if i["id"] == "NS-11c10a8ea6")
    assert lgpd["total"] == 13
    assert "LGPD" in lgpd["rotulo"]
    assert "Acesso à informação e proteção de dados" in lgpd["rotulo"]
    assert "(13)" in lgpd["rotulo"]

    # Termo curto (< 2 caracteres) devolve vazio
    assert cliente.get("/questoes/sugestoes", params={"q": "L"}).json() == []


@com_banco
def test_cascata_sem_trava_permite_assunto_e_subassunto_sem_disciplina(cliente):
    """Assunto e Subassunto aceitam busca e marcação sem disciplina marcada."""
    import re

    r = cliente.get("/questoes")
    assert r.status_code == 200
    botao_assunto = re.search(r'<button[^>]*id="botao-assunto"[^>]*>', r.text).group(0)
    botao_sub = re.search(r'<button[^>]*id="botao-subassunto"[^>]*>', r.text).group(0)
    assert not re.search(r"\sdisabled[\s>]", botao_assunto)
    assert not re.search(r"\sdisabled[\s>]", botao_sub)

    # Pode filtrar diretamente por um assunto sem disciplina
    r_assunto = cliente.get("/api/v1/questoes", params={"no_id": "A-73eefa53ea"})
    assert r_assunto.status_code == 200
    assert r_assunto.json()["total"] > 0
