from app.servicos.formatacao import rotulo_concurso
from app.web.rotas_web import filtro_num, filtro_pct


def test_filtro_num():
    assert filtro_num(2532) == "2.532"
    assert filtro_num(1000000) == "1.000.000"
    assert filtro_num(42) == "42"
    assert filtro_num(None) == ""


def test_filtro_pct():
    assert filtro_pct(10.46) == "10,46%"
    assert filtro_pct(0.5) == "0,50%"
    assert filtro_pct(None) == ""


def test_rotulo_concurso():
    assert rotulo_concurso("CD_25_NS") == "CD 2025 — Nível Superior"
    assert rotulo_concurso("PF_25_ADM") == "PF 2025"
    assert rotulo_concurso("XYZ_23_BLA") == "XYZ 2023"
    assert rotulo_concurso("ORGAO_19") == "ORGAO 2019"
    assert rotulo_concurso("AB") == "AB"
    # Órgão com UF no meio: o ano não está na segunda posição (KAN-56). Antes
    # destes casos o rótulo caía no slug cru e aparecia com underline no site.
    assert rotulo_concurso("SEFA_PR_25") == "SEFA-PR 2025"
    assert rotulo_concurso("TCE_MG_25") == "TCE-MG 2025"
    assert rotulo_concurso("SEFAZ_SE_25_AUDITOR") == "SEFAZ-SE 2025"
    assert rotulo_concurso("SEED_SE_25_PROFESSOR") == "SEED-SE 2025"
    assert rotulo_concurso("PGE_ES_25_PROCURADOR") == "PGE-ES 2025"
    # Sem ano reconhecível, segue devolvendo o slug como está.
    assert rotulo_concurso("ORGAO_SEM_ANO") == "ORGAO_SEM_ANO"


def test_rotulos_de_nivel_tipo_e_materia():
    from app.servicos.formatacao import (
        rotulo_materia,
        rotulo_nivel,
        rotulo_tipo_conhecimento,
    )

    assert rotulo_nivel("medio") == "Médio"
    assert rotulo_tipo_conhecimento("especifico") == "Específico"
    assert rotulo_tipo_conhecimento("basico") == "Básico"
    assert rotulo_materia("Analista", True) == "Conhecimentos específicos — Analista"
    assert rotulo_materia("Direito Penal", False) == "Direito Penal"


def test_codigo_curto_formato_estavel():
    from app.servicos.formatacao import codigo_curto

    # SHA-1 da chave: o valor não pode mudar entre versões (links publicados).
    assert codigo_curto("PF_25_ADM|094_PF_CB1_01|1") == "Q6AAB4214"
