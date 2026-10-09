from pathlib import Path

import pymupdf
import pytest

from src import gabarito_parser
from src.gabarito_parser import (
    TIPO_GRADE,
    TIPO_JUSTIFICATIVA,
    TIPO_PADRAO_RESPOSTA,
    VERSAO_DEFINITIVO,
    VERSAO_PRELIMINAR,
    GradeGabarito,
    _padrao_de_paginas,
    classificar_documento,
    classificar_versao,
    codigo_caderno_do_texto,
    dividir_padrao_resposta,
    ler_documento,
    ler_grade,
    ler_grade_de_linhas,
    ler_grade_tipada_de_linhas,
    token_caderno,
)

CE = gabarito_parser.QUESTAO_CERTO_ERRADO
ME = gabarito_parser.QUESTAO_MULTIPLA_ESCOLHA

FIXTURES = Path(__file__).parent / "fixtures" / "questoes"
AMOSTRAS_DIR = Path(__file__).resolve().parent.parent / "data" / "inventario_amostra"


def _palavra(x, texto, y=100):
    # Mesmo formato de `page.get_text("words")`: (x0, y0, x1, y1, texto, ...)
    return (x, y, x + 8, y + 7, texto, 0, 0, 0)


def _linha(y, rotulo, valores, x0=45, passo=24):
    return [_palavra(30, rotulo, y)] + [
        _palavra(x0 + i * passo, v, y) for i, v in enumerate(valores)
    ]


def gerar_pdf_grade(
    path: Path,
    codigo: str,
    respostas: dict[int, str],
    titulo: str = "GABARITOS OFICIAIS DEFINITIVOS",
    rotulo_item: str = "Item",
) -> Path:
    """PDF sintético no layout da grade do CEBRASPE: linhas `Item` ou `Questão` e
    `Gabarito` de 20 colunas, com `0` de enchimento."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((200, 60), titulo, fontsize=9)
    page.insert_text((450, 80), codigo, fontsize=9)
    numeros = sorted(respostas)
    y = 120
    for i in range(0, len(numeros), 20):
        fatia = numeros[i : i + 20]
        cel_num = [str(n) for n in fatia] + ["0"] * (20 - len(fatia))
        cel_let = [respostas[n] for n in fatia] + ["0"] * (20 - len(fatia))
        page.insert_text((30, y), rotulo_item, fontsize=7)
        page.insert_text((30, y + 8), "Gabarito", fontsize=7)
        for j, (num, let) in enumerate(zip(cel_num, cel_let)):
            page.insert_text((70 + j * 24, y), num, fontsize=7)
            page.insert_text((72 + j * 24, y + 8), let, fontsize=7)
        y += 22
    doc.save(path)
    return path


class TestGradePorPosicao:
    def test_casa_numero_e_letra_pela_coluna_e_descarta_enchimento(self):
        linhas = [
            _linha(100, "Item", ["41", "42", "43", "0", "0"]),
            _linha(108, "Gabarito", ["C", "X", "E", "0", "0"]),
            _linha(120, "0", ["0", "0"]),  # linha só de enchimento
        ]
        respostas, alertas = ler_grade_de_linhas(linhas)
        assert respostas == {41: "C", 42: "X", 43: "E"}
        assert alertas == []

    def test_letra_invalida_vira_alerta(self):
        linhas = [
            _linha(100, "Item", ["1", "2"]),
            _linha(108, "Gabarito", ["C", "Z"]),
        ]
        respostas, alertas = ler_grade_de_linhas(linhas)
        assert respostas == {1: "C"}
        assert alertas == ["item 2 com gabarito inválido 'Z'"]

    def test_linha_de_itens_sem_gabarito_abaixo(self):
        respostas, alertas = ler_grade_de_linhas([_linha(100, "Item", ["1", "2"])])
        assert respostas == {}
        assert "sem linha de gabarito abaixo" in alertas[0]

    def test_pdf_sintetico(self, tmp_path):
        esperado = {n: "CEX"[n % 3] for n in range(51, 76)}
        pdf = gerar_pdf_grade(tmp_path / "g.pdf", "001_XX_001_01", esperado)
        grade = ler_grade(pdf)
        assert grade.respostas == esperado
        assert grade.codigo_caderno == "001_XX_001_01"
        assert grade.tipo_detectado == "certo_errado"
        assert grade.tipos == dict.fromkeys(esperado, CE)

    def test_multipla_escolha_com_rotulo_questao_e_letras_a_a_e(self):
        linhas = [
            _linha(100, "Questão", ["1", "2", "3", "4", "5", "6"]),
            _linha(108, "Gabarito", ["A", "B", "C", "D", "E", "X"]),
        ]
        respostas, alertas = ler_grade_de_linhas(linhas)
        assert respostas == {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "X"}
        assert alertas == []

    def test_multipla_escolha_com_rotulo_questao_sem_acento(self):
        linhas = [
            _linha(100, "Questao", ["10", "11"]),
            _linha(108, "Gabarito", ["A", "D"]),
        ]
        respostas, alertas = ler_grade_de_linhas(linhas)
        assert respostas == {10: "A", 11: "D"}
        assert alertas == []

    def test_me_com_letra_invalida_fora_de_a_a_e_x_vira_alerta(self):
        linhas = [
            _linha(100, "Questão", ["1", "2", "3"]),
            _linha(108, "Gabarito", ["A", "F", "Z"]),
        ]
        respostas, alertas = ler_grade_de_linhas(linhas)
        assert respostas == {1: "A"}
        assert alertas == [
            "item 2 com gabarito inválido 'F'",
            "item 3 com gabarito inválido 'Z'",
        ]

    def test_pdf_sintetico_multipla_escolha(self, tmp_path):
        letras = ["A", "B", "C", "D", "E", "X"]
        esperado = {n: letras[n % len(letras)] for n in range(1, 31)}
        pdf = gerar_pdf_grade(
            tmp_path / "g_me.pdf",
            "002_YY_001_01",
            esperado,
            rotulo_item="Questão",
        )
        grade = ler_grade(pdf)
        assert grade.respostas == esperado
        assert grade.codigo_caderno == "002_YY_001_01"
        assert grade.tipo_detectado == "multipla_escolha"
        assert grade.tipos == dict.fromkeys(esperado, ME)
        assert grade.alertas == []

    def test_pdf_sintetico_grade_item_com_letra_de_me_alerta_e_segue_ce(self, tmp_path):
        # Letra espúria numa grade `Item` não pode virar ME calada.
        respostas = {1: "C", 2: "A", 3: "E", 4: "X"}
        pdf = gerar_pdf_grade(tmp_path / "g.pdf", "001_XX_001_01", respostas)
        grade = ler_grade(pdf)
        assert grade.respostas == {1: "C", 3: "E", 4: "X"}
        assert grade.alertas == [
            "item 2 com gabarito inválido 'A'",
            "grade com buraco na numeração: [2]",
        ]
        assert grade.tipo_detectado == "certo_errado"


class TestTipoPorRotulo:
    def test_item_aceita_so_c_e_x(self):
        linhas = [
            _linha(100, "Item", ["1", "2", "3", "4", "5", "6"]),
            _linha(108, "Gabarito", ["C", "E", "X", "A", "B", "D"]),
        ]
        respostas, tipos, alertas = ler_grade_tipada_de_linhas(linhas)
        assert respostas == {1: "C", 2: "E", 3: "X"}
        assert tipos == {1: CE, 2: CE, 3: CE}
        assert alertas == [
            "item 4 com gabarito inválido 'A'",
            "item 5 com gabarito inválido 'B'",
            "item 6 com gabarito inválido 'D'",
        ]

    def test_questao_aceita_a_a_e_e_x(self):
        linhas = [
            _linha(100, "Questão", ["1", "2", "3", "4", "5", "6"]),
            _linha(108, "Gabarito", ["A", "B", "C", "D", "E", "X"]),
        ]
        respostas, tipos, alertas = ler_grade_tipada_de_linhas(linhas)
        assert respostas == {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "X"}
        assert tipos == dict.fromkeys(range(1, 7), ME)
        assert alertas == []

    def test_questao_so_com_c_e_continua_me(self):
        # Caderno ME cujo gabarito só tem C e E: o rótulo decide, não as letras.
        linhas = [
            _linha(100, "Questao", ["1", "2"]),
            _linha(108, "Gabarito", ["C", "E"]),
        ]
        respostas, tipos, alertas = ler_grade_tipada_de_linhas(linhas)
        assert respostas == {1: "C", 2: "E"}
        assert tipos == {1: ME, 2: ME}
        assert GradeGabarito("x", respostas, tipos=tipos).tipo_detectado == ME

    def test_rotulo_desconhecido_e_ignorado(self):
        linhas = [
            _linha(100, "Número", ["1", "2"]),
            _linha(108, "Gabarito", ["A", "B"]),
        ]
        assert ler_grade_tipada_de_linhas(linhas) == ({}, {}, [])

    def test_pdf_com_linhas_item_e_questao_alerta_grade_mista(self, tmp_path):
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((200, 60), "GABARITOS OFICIAIS DEFINITIVOS", fontsize=9)
        for y, rotulo, numero, letra in (
            (120, "Item", "1", "C"),
            (150, "Questão", "2", "A"),
        ):
            page.insert_text((30, y), rotulo, fontsize=7)
            page.insert_text((30, y + 8), "Gabarito", fontsize=7)
            page.insert_text((70, y), numero, fontsize=7)
            page.insert_text((72, y + 8), letra, fontsize=7)
        doc.save(tmp_path / "misto.pdf")
        grade = ler_grade(tmp_path / "misto.pdf")
        assert grade.respostas == {1: "C", 2: "A"}
        assert grade.tipos == {1: CE, 2: ME}
        assert grade.tipo_detectado == gabarito_parser.GRADE_MISTA
        assert grade.alertas == [
            "grade com linhas `Item` e `Questão` misturadas: "
            "['certo_errado', 'multipla_escolha']"
        ]

    def test_ler_grade_de_linhas_mantem_retorno_sem_tipos(self):
        linhas = [
            _linha(100, "Item", ["1"]),
            _linha(108, "Gabarito", ["C"]),
        ]
        assert ler_grade_de_linhas(linhas) == ({1: "C"}, [])


class TestGabaritosReais:
    def test_grade_pf_cb1(self):
        grade = ler_grade(FIXTURES / "Gab_Definitivo_094_PF_CB1_01.pdf")
        assert grade.codigo_caderno == "094_PF_CB1_01"
        assert grade.numeros == list(range(1, 51))
        assert grade.anulados == [37]
        assert (grade.respostas[1], grade.respostas[2], grade.respostas[50]) == (
            "C",
            "E",
            "C",
        )
        assert (
            grade.cabecalho == "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR"
        )
        assert grade.alertas == []
        assert grade.tipos == dict.fromkeys(range(1, 51), CE)
        assert grade.tipo_detectado == "certo_errado"

    def test_gabarito_em_hash_traz_o_codigo_do_caderno_no_conteudo(self):
        doc = ler_documento(FIXTURES / "gabarito_hash_CD_001.pdf")
        assert doc["tipo"] == TIPO_GRADE
        assert doc["codigo_caderno"] == "167_CDNS_001_01"
        grade = doc["grade"]
        assert grade.numeros == list(range(91, 181))
        assert grade.anulados == [93, 97, 115, 117, 126, 155, 166]
        assert grade.cabecalho.startswith("CARGO 1: ANALISTA LEGISLATIVO")

    def test_grade_banrisul_me_real(self):
        pdf = AMOSTRAS_DIR / "Gab_BANRISUL_25_CB1.pdf"
        if not pdf.exists():
            pytest.skip("Amostra Gab_BANRISUL_25_CB1.pdf não encontrada")
        grade = ler_grade(pdf)
        assert grade.codigo_caderno == "077_BANRISUL_CB1_01"
        assert grade.tipos == dict.fromkeys(range(1, 31), ME)
        assert len(grade.respostas) == 30
        assert grade.numeros == list(range(1, 31))
        assert grade.anulados == [15]
        assert set(grade.respostas.values()).issubset({"A", "B", "C", "D", "E", "X"})
        assert grade.tipo_detectado == "multipla_escolha"
        assert grade.alertas == []

    def test_grade_sebrae_me_real(self):
        pdf = AMOSTRAS_DIR / "Gab_SEBRAE_26_TIPO2.pdf"
        if not pdf.exists():
            pytest.skip("Amostra Gab_SEBRAE_26_TIPO2.pdf não encontrada")
        grade = ler_grade(pdf)
        # Sigla com sublinhado (SEBRAE_26_PSE_1): sem ela o gabarito não liga
        # ao caderno no pipeline.
        assert grade.codigo_caderno == "169_SEBRAE_26_PSE_1_CG1_02"
        assert token_caderno(grade.codigo_caderno) == "CG1"
        assert ler_documento(pdf)["codigo_caderno"] == "169_SEBRAE_26_PSE_1_CG1_02"
        assert grade.tipos == dict.fromkeys(range(1, 16), ME)
        assert len(grade.respostas) == 15
        assert grade.numeros == list(range(1, 16))
        assert grade.anulados == []
        assert set(grade.respostas.values()).issubset({"A", "B", "C", "D", "E", "X"})
        assert grade.tipo_detectado == "multipla_escolha"
        assert grade.alertas == []

    def test_grade_sefa_pr_me_real(self):
        pdf = AMOSTRAS_DIR / "Gab_SEFA_PR_25_CARGO1.pdf"
        if not pdf.exists():
            pytest.skip("Amostra Gab_SEFA_PR_25_CARGO1.pdf não encontrada")
        grade = ler_grade(pdf)
        assert grade.codigo_caderno == "177_SEFAPR_001_01"
        assert grade.tipos == dict.fromkeys(range(1, 51), ME)
        assert len(grade.respostas) == 50
        assert grade.numeros == list(range(1, 51))
        assert grade.anulados == [4, 39]
        assert set(grade.respostas.values()).issubset({"A", "B", "C", "D", "E", "X"})
        assert grade.tipo_detectado == "multipla_escolha"
        assert grade.alertas == []


class TestClassificacaoECodigo:
    @pytest.mark.parametrize(
        ("texto", "tipo"),
        [
            ("Justificativas de alteração do gabarito de itens", TIPO_JUSTIFICATIVA),
            (
                "CARGO 1: ADMINISTRADOR\nProva Discursiva\nPADRÃO DE RESPOSTA DEFINITIVO",
                TIPO_PADRAO_RESPOSTA,
            ),
            ("GABARITOS OFICIAIS DEFINITIVOS\nItem\n1\n2", TIPO_GRADE),
            ("GABARITOS OFICIAIS DEFINITIVOS\nQuestão\n1\n2", TIPO_GRADE),
            ("GABARITOS OFICIAIS DEFINITIVOS\nQuestao\n1\n2", TIPO_GRADE),
            ("GABARITO OFICIAL PRELIMINAR\n  Questão 1\n2", TIPO_GRADE),
            ("qualquer outra coisa", gabarito_parser.TIPO_DESCONHECIDO),
        ],
    )
    def test_classificar_documento(self, texto, tipo):
        assert classificar_documento(texto) == tipo

    @pytest.mark.parametrize(
        ("codigo", "token"),
        [
            ("094_PF_CB1_01", "CB1"),
            ("072_STM_CG5_01", "CG5"),
            ("167_CDNS_002_01", "002"),
            ("108_TCUTEFC_001_01", "001"),
            ("169_SEBRAE_26_PSE_1_CG1_02", "CG1"),
            ("053_SEBRAE_PSE_CG1_02", "CG1"),
            ("084_PC_CE_001_01", "001"),
            ("077_BANRISUL_CB1", None),
            (None, None),
            ("lixo", None),
        ],
    )
    def test_token_caderno(self, codigo, token):
        assert token_caderno(codigo) == token

    def test_codigo_no_meio_do_texto(self):
        assert codigo_caderno_do_texto("0\n0\n167_CDNS_CG1_01\n0") == "167_CDNS_CG1_01"
        assert codigo_caderno_do_texto("sem código") is None

    def test_codigo_com_sublinhado_na_sigla(self):
        texto = "Aplicação: 15/03/2026\n169_SEBRAE_26_PSE_1_CG1_02\n0"
        assert codigo_caderno_do_texto(texto) == "169_SEBRAE_26_PSE_1_CG1_02"

    def test_codigo_sem_sublinhado_casa_o_mesmo_trecho(self):
        # A sigla com segmentos extras não estica um código antigo: o trecho
        # casado e o token são os mesmos de antes.
        texto = "x 094_PF_CB1_01 y 167_CDNS_002_01"
        assert codigo_caderno_do_texto(texto) == "094_PF_CB1_01"
        assert codigo_caderno_do_texto("CÓDIGO 167_CDNS_002_01.") == "167_CDNS_002_01"


class TestPadraoResposta:
    def test_divide_por_questao(self):
        texto = (
            "Prova Discursiva – Questão 1 – Conhecimentos Básicos\nresposta um\n"
            "Prova Discursiva – Questão 2\nresposta dois\n"
            "Prova Discursiva – Peça de natureza técnica\nresposta peça"
        )
        secoes = dividir_padrao_resposta(texto)
        assert [s["titulo"] for s in secoes] == [
            "Prova Discursiva – Questão 1 – Conhecimentos Básicos",
            "Prova Discursiva – Questão 2",
            "Prova Discursiva – Peça de natureza técnica",
        ]
        assert "resposta dois" in secoes[1]["texto"]

    def test_sem_cabecalho_e_uma_secao_so(self):
        assert dividir_padrao_resposta("texto livre") == [
            {"titulo": None, "texto": "texto livre"}
        ]

    def test_limpeza_cabecalho_institucional_no_fim_da_secao(self):
        texto = (
            "Prova Discursiva – Questão 1\n"
            "Texto da resposta 1.\n\n"
            "CÂMARA DOS DEPUTADOS\n"
            "CARGO 1: ANALISTA LEGISLATIVO\n"
            "Prova Discursiva – Questão 2\n"
            "Texto da resposta 2.\n\n"
            "TRIBUNAL DE CONTAS DA UNIÃO\n"
            "Prova Discursiva – Peça de natureza técnica\n"
            "Texto da peça."
        )
        secoes = dividir_padrao_resposta(texto)
        assert len(secoes) == 3
        assert (
            secoes[0]["texto"] == "Prova Discursiva – Questão 1\nTexto da resposta 1."
        )
        assert "CÂMARA DOS DEPUTADOS" not in secoes[0]["texto"]
        assert (
            secoes[1]["texto"] == "Prova Discursiva – Questão 2\nTexto da resposta 2."
        )
        assert "TRIBUNAL DE CONTAS DA UNIÃO" not in secoes[1]["texto"]

    def test_cabecalho_institucional_real_cd_e_tcu_cortado(self):
        # Formato visto nos padrões reais da CD e do TCU.
        texto = (
            "Prova Discursiva – Questão 1\n"
            "Conceito 3 – Aborda corretamente.\n"
            "CÂMARA DOS DEPUTADOS\n"
            "CARGO 2: TÉCNICO LEGISLATIVO\n"
            "ESPECIALIDADE: ASSISTENTE LEGISLATIVO E ADMINISTRATIVO\n"
            "CÓDIGO: CD-AL- 026\n"
            "Prova Discursiva – Questão 2\n"
            "Conceito 2 – Citou três circunstâncias.\n"
            "TRIBUNAL DE CONTAS DA UNIÃO\n"
            "DISCURSIVA PARA O CARGO DE TÉCNICO FEDERAL DE CONTROLE EXTERNO\n"
        )
        secoes = dividir_padrao_resposta(texto)
        assert secoes[0]["texto"] == (
            "Prova Discursiva – Questão 1\nConceito 3 – Aborda corretamente."
        )
        assert secoes[1]["texto"] == (
            "Prova Discursiva – Questão 2\nConceito 2 – Citou três circunstâncias."
        )

    def test_camara_dos_deputados_no_corpo_nao_corta(self):
        texto = (
            "Prova Discursiva – Questão 1\n"
            "O candidato deve mencionar que a\n"
            "Câmara dos Deputados aprovou o projeto em 2024.\n"
            "Conceito 3 – Abordou os dois aspectos."
        )
        secoes = dividir_padrao_resposta(texto)
        assert secoes[0]["texto"] == texto

    def test_marca_em_caixa_alta_seguida_de_conteudo_nao_corta(self):
        texto = (
            "Prova Discursiva – Questão 1\n"
            "Resposta sobre o controle externo exercido pelo\n"
            "TRIBUNAL DE CONTAS DA UNIÃO\n"
            "com auxílio do Congresso Nacional.\n"
            "CÂMARA DOS DEPUTADOS\n"
            "Conceito 3 – Abordou os dois aspectos."
        )
        secoes = dividir_padrao_resposta(texto)
        assert secoes[0]["texto"] == texto

    def test_marca_seguida_de_muitas_linhas_nao_corta(self):
        linhas_caixa_alta = "\n".join(f"LINHA {i}" for i in range(7))
        texto = (
            "Prova Discursiva – Questão 1\n"
            "Resposta.\n"
            "CÂMARA DOS DEPUTADOS\n" + linhas_caixa_alta
        )
        assert dividir_padrao_resposta(texto)[0]["texto"] == texto

    def test_limpeza_rodape_multiplas_paginas(self):
        pag1 = (
            "Prova Discursiva – Questão 1\n"
            "Conteúdo da questão 1 na página 1.\n"
            "CEBRASPE - Tecnologia e Avaliação\n"
            "Página 1 de 2"
        )
        pag2 = (
            "Continuação da resposta na página 2.\n"
            "Conceito 3 - resposta completa.\n"
            "CEBRASPE - Tecnologia e Avaliação\n"
            "Página 1 de 2"
        )
        pr = _padrao_de_paginas([pag1, pag2])
        assert "CEBRASPE - Tecnologia e Avaliação" not in pr.texto
        assert "Página 1 de 2" not in pr.texto
        assert "Conteúdo da questão 1" in pr.texto
        assert "Conceito 3" in pr.texto

    def test_limpeza_rodape_pagina_unica_cd(self):
        pag = (
            "Prova Discursiva\n"
            "Conteúdo da questão única.\n"
            "CÂMARA DOS DEPUTADOS | Coordenação de Concursos"
        )
        pr = _padrao_de_paginas([pag])
        assert "CÂMARA DOS DEPUTADOS | Coordenação" not in pr.texto
        assert "Conteúdo da questão única." in pr.texto


class TestClassificarVersao:
    def test_grade_definitiva(self):
        texto = "GABARITOS OFICIAIS DEFINITIVOS\nItem 1 2 3..."
        assert classificar_versao(texto) == VERSAO_DEFINITIVO

    def test_grade_preliminar(self):
        texto = "GABARITOS OFICIAIS PRELIMINARES\nItem 1 2 3..."
        assert classificar_versao(texto) == VERSAO_PRELIMINAR

    def test_padrao_definitivo(self):
        assert (
            classificar_versao(
                "CARGO 1\nProva Discursiva\nPADRÃO DE RESPOSTA DEFINITIVO"
            )
            == VERSAO_DEFINITIVO
        )
        assert (
            classificar_versao(
                "CARGO 2\nProva Discursiva\nPADRÃO DEFINITIVO DE RESPOSTA"
            )
            == VERSAO_DEFINITIVO
        )

    def test_padrao_preliminar(self):
        assert (
            classificar_versao(
                "CARGO 1\nProva Discursiva\nPADRÃO DE RESPOSTAS PRELIMINAR"
            )
            == VERSAO_PRELIMINAR
        )

    def test_definitivo_solto_apenas_no_corpo_retorna_none(self):
        # Palavra definitivo solta no corpo (fora do cabeçalho ou sem regex específica)
        texto_corpo = (
            "A" * 700 + "\nDecisão em caráter definitivo da banca examinadora."
        )
        assert classificar_versao(texto_corpo) is None

        texto_sem_cabecalho_padrao = (
            "Enunciado da questão dissertando sobre o ato administrativo definitivo."
        )
        assert classificar_versao(texto_sem_cabecalho_padrao) is None

    def test_fallback_nome_arquivo(self):
        assert (
            classificar_versao("", "Gab_Definitivo_094_PF_CB1_01.pdf")
            == VERSAO_DEFINITIVO
        )
        assert (
            classificar_versao("", "Gab_Preliminar_094_PF_CB1_01.pdf")
            == VERSAO_PRELIMINAR
        )
        assert classificar_versao("", "hash_abc123.pdf") is None


class TestLeituraDocumento:
    def test_ler_documento_abre_pdf_uma_unica_vez(self, monkeypatch, tmp_path):
        pdf = gerar_pdf_grade(tmp_path / "g.pdf", "001_XX_001_01", {1: "C"})
        chamadas = []
        real_open = pymupdf.open

        def _spy_open(*args, **kwargs):
            chamadas.append(args)
            return real_open(*args, **kwargs)

        monkeypatch.setattr(gabarito_parser.pymupdf, "open", _spy_open)
        doc = ler_documento(pdf)
        assert len(chamadas) == 1
        assert doc["tipo"] == TIPO_GRADE
        assert doc["versao"] == VERSAO_DEFINITIVO


class TestTipoDetectado:
    def test_certo_errado_apenas_c_e_x(self):
        grade = GradeGabarito(codigo_caderno="001", respostas={1: "C", 2: "E", 3: "X"})
        assert grade.tipo_detectado == "certo_errado"

    def test_certo_errado_grade_vazia(self):
        grade = GradeGabarito(codigo_caderno="001")
        assert grade.tipo_detectado == "certo_errado"

    def test_multipla_escolha_com_a_b_ou_d(self):
        for letra in ("A", "B", "D"):
            grade = GradeGabarito(codigo_caderno="001", respostas={1: letra, 2: "C"})
            assert grade.tipo_detectado == "multipla_escolha"

    def test_tipos_por_numero_decidem_sobre_as_letras(self):
        so_c_e = {1: "C", 2: "E"}
        grade = GradeGabarito("001", so_c_e, tipos={1: ME, 2: ME})
        assert grade.tipo_detectado == "multipla_escolha"
        grade = GradeGabarito("001", {1: "C"}, tipos={1: CE})
        assert grade.tipo_detectado == "certo_errado"

    def test_tipos_misturados_viram_grade_mista(self):
        grade = GradeGabarito("001", {1: "C", 2: "A"}, tipos={1: CE, 2: ME})
        assert grade.tipo_detectado == gabarito_parser.GRADE_MISTA

    def test_tipo_detectado_explicito_preservado(self):
        grade = GradeGabarito(
            codigo_caderno="001",
            respostas={1: "C"},
            tipo_detectado="multipla_escolha",
        )
        assert grade.tipo_detectado == "multipla_escolha"
