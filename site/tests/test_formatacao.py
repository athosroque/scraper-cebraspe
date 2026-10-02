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
