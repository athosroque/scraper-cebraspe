"""Layout `caderno_com_gabarito` (8.M/S3): questões e respostas no mesmo PDF.

Linhas sintéticas para as regras de `prova_parser.separar_gabarito_embutido` e
PDFs reais de `data/inventario_amostra/caderno_com_gabarito/` (pulados quando
o PDF não está no disco, como os outros testes que leem `data/`).
"""

from functools import cache
from pathlib import Path

import pytest

from src.gabarito_parser import (
    QUESTAO_CERTO_ERRADO,
    QUESTAO_MULTIPLA_ESCOLHA,
    VERSAO_DEFINITIVO,
    VERSAO_PRELIMINAR,
    ler_documento,
)
from src.prova_parser import (
    FORMATO_CODIGO_CE,
    FORMATO_JUSTIFICATIVA,
    PADRAO_CODIGO_ITEM_INICIO,
    PADRAO_MARCA_JUSTIFICATIVA,
    STATUS_FALHA_ITENS_DIVERGENTES,
    STATUS_SUCESSO,
    Linha,
    _veredito,
    extrair_caderno_objetivo,
    ler_gabarito_embutido,
    separar_gabarito_embutido,
)
from src.stats_writer import (
    classificar_prova,
    codigo_caderno_do_nome,
    identificador_prova,
    stem_caderno,
)

AMOSTRA = (
    Path(__file__).parent.parent
    / "data"
    / "inventario_amostra"
    / "caderno_com_gabarito"
)
DEFINITIVOS = AMOSTRA / "definitivos"


def _l(texto, x0=28.0, y0=0.0, primeiro_span=None, pagina=0):
    return Linha(
        pagina=pagina,
        bloco=1,
        texto=texto,
        x0=x0,
        y0=y0,
        x1=290.0,
        y1=y0 + 10,
        inicio_bloco=True,
        primeiro_span=primeiro_span if primeiro_span is not None else texto,
    )


def _linhas(*especificacoes):
    """`(texto, x0)` ou `(texto, x0, primeiro_span)`, uma linha a cada 12 pt."""
    return [
        _l(*esp[:2], y0=12.0 * i, primeiro_span=(esp[2:] or (None,))[0])
        for i, esp in enumerate(especificacoes)
    ]


class TestVeredito:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            ("Certo. A assertiva consiste em uma paráfrase", "certo"),
            ("CERTO, pois a alocação ótima", "certo"),
            ("Correta.O circulo de Mohr", "certo"),
            ("Incorreta. A circunstância", "errado"),
            ("Opção incorreta. Erro na alternativa", "errado"),
            ("Errada", "errado"),
            ("5.1 Relação professor/aluno. Incorreta. A relação docente", "errado"),
            ("1 Constituição (artigos 101 a 105-B)_INCORRETA. De acordo", "errado"),
            ("3 Macroeconomia. 3.1 As contas nacionais;_ERRADA. A soma", "errado"),
            ("Anulada", "anulado"),
            ("A assertiva está de acordo com a lei", None),
        ],
    )
    def test_veredito(self, texto, esperado):
        assert _veredito(texto) == esperado


class TestSepararGabaritoEmbutido:
    def test_caderno_comum_volta_intacto(self):
        linhas = _linhas(
            ("Julgue os itens a seguir.", 28),
            ("1 O item fala de JUSTIFICATIVAS de alteração.", 28, "1"),
            ("JUSTIFICATIVA", 46),
            ("for (i = 0; i < n; i++) { /* comentário */ }", 46),
        )
        mantidas, embutido = separar_gabarito_embutido(linhas)
        assert embutido is None
        assert mantidas is linhas

    def test_justificativa_ce_sai_do_texto_e_vira_resposta(self):
        linhas = _linhas(
            ("Julgue os itens a seguir.", 28),
            ("1 Primeiro item", 28, "1"),
            ("continua o item.", 46),
            ("JUSTIFICATIVA - Certo. Porque sim.", 46),
            ("mais justificativa.", 46),
            ("<FimJust>", 46),
            ("2 Segundo item.", 28, "2"),
            ("JUSTIFICATIVA – ERRADO, pois não.", 46),
            ("<FimJust>", 46),
        )
        mantidas, embutido = separar_gabarito_embutido(linhas)
        assert embutido.formato == FORMATO_JUSTIFICATIVA
        assert embutido.versao == VERSAO_PRELIMINAR
        assert embutido.respostas == {1: "C", 2: "E"}
        assert set(embutido.tipos.values()) == {QUESTAO_CERTO_ERRADO}
        assert embutido.alertas == []
        assert [linha.texto for linha in mantidas] == [
            "Julgue os itens a seguir.",
            "1 Primeiro item",
            "continua o item.",
            "2 Segundo item.",
        ]

    def test_justificativa_ce_sem_fimjust_acaba_na_margem(self):
        # PC_DF_24 e TC_DF_23 têm item sem <FimJust>: o próximo item (ou o
        # comando do grupo seguinte) vem na margem da coluna.
        linhas = _linhas(
            ("1 Primeiro item.", 28, "1"),
            ("JUSTIFICATIVA - Certo. Sem fecho.", 46),
            ("Julgue o próximo item.", 28),
            ("2 Segundo item.", 28, "2"),
            ("JUSTIFICATIVA - Errado. Com fecho.", 46),
            ("<FimJust>", 46),
        )
        mantidas, embutido = separar_gabarito_embutido(linhas)
        assert embutido.respostas == {1: "C", 2: "E"}
        assert embutido.alertas == []
        assert embutido.avisos == ["item 1: justificativa sem <FimJust>, fim na margem"]
        assert "Julgue o próximo item." in [linha.texto for linha in mantidas]

    def _questao_me(self, numero, certa, entradas=None):
        letras = "ABCDE"
        entradas = entradas or [
            f"||{letra}|| - {'Correta' if letra == certa else 'Incorreta'}. Motivo.*/"
            for letra in letras
        ]
        return [
            (f"Questão {numero}", 50),
            ("Assinale a opção correta.", 28),
            *((f"{letra} opção {letra}", 28, letra) for letra in letras),
            ("||JUSTIFICATIVAS||", 28),
            *((entrada, 28) for entrada in entradas),
        ]

    def test_justificativa_me_e_contagem_de_entradas(self):
        linhas = _linhas(*self._questao_me(1, "B"), *self._questao_me(2, "E"))
        mantidas, embutido = separar_gabarito_embutido(linhas)
        assert embutido.respostas == {1: "B", 2: "E"}
        assert set(embutido.tipos.values()) == {QUESTAO_MULTIPLA_ESCOLHA}
        assert embutido.alternativas == {1: 5, 2: 5}
        assert not any(
            PADRAO_MARCA_JUSTIFICATIVA.search(linha.texto) for linha in mantidas
        )
        assert len(mantidas) == 2 * 7

    def test_entrada_me_sem_travessao_e_sem_fecho_no_meio(self):
        # CAESB_24: "||E|| Incorreta." sem travessão; a entrada A sem "*/"
        # acaba antes da B.
        entradas = [
            "||A|| - Incorreta. Sem fecho,",
            "continua a entrada A.",
            "||B|| - Incorreta. b*/",
            "||C|| - Correta. c*/",
            "||D|| - Incorreta. d*/",
            "||E|| Incorreta. e*/",
        ]
        linhas = _linhas(*self._questao_me(7, None, entradas))
        _, embutido = separar_gabarito_embutido(linhas)
        assert embutido.respostas == {7: "C"}
        assert embutido.alternativas == {7: 5}
        assert embutido.alertas == []

    def test_ultima_entrada_me_sem_fecho_acaba_antes_da_questao_seguinte(self):
        entradas = [
            "||A|| - Incorreta. a*/",
            "||B|| - Incorreta. b*/",
            "||C|| - Incorreta. c*/",
            "||D|| - Correta. d*/",
            "||E|| - Incorreta. Sem fecho",
            "e sem mais nada.",
        ]
        linhas = _linhas(
            *self._questao_me(3, None, entradas),
            ("Texto CG1A2", 28),
            ("Texto-base da questão 4.", 28),
            *self._questao_me(4, "A"),
        )
        mantidas, embutido = separar_gabarito_embutido(linhas)
        assert embutido.respostas == {3: "D", 4: "A"}
        assert embutido.avisos == [
            "questão 3: última justificativa sem */, fim antes da questão seguinte"
        ]
        textos = [linha.texto for linha in mantidas]
        assert "Texto CG1A2" in textos and "Texto-base da questão 4." in textos

    def test_justificativa_me_no_formato_letra_travessao(self):
        # SEPLAD_DF_22: "JUSTIFICATIVAS" e "A – Errado." (travessão), 4 opções.
        linhas = _linhas(
            ("Questão 9", 50),
            ("Enunciado.", 28),
            *((f"{letra} opção", 28, letra) for letra in "ABCD"),
            ("JUSTIFICATIVAS", 28),
            ("A – Errado. a*/", 28),
            ("B – 3 Macroeconomia. 3.1 Contas;_CERTO. b*/", 28),
            ("C - Opção incorreta. c*/", 28),
            ("D - Errado. d*/", 28),
        )
        _, embutido = separar_gabarito_embutido(linhas)
        assert embutido.respostas == {9: "B"}

    def test_resposta_me_ambigua_fica_fora_da_grade(self):
        entradas = [
            f"||{letra}|| - {'Correta' if letra in 'AB' else 'Incorreta'}. x*/"
            for letra in "ABCDE"
        ]
        _, embutido = separar_gabarito_embutido(
            _linhas(*self._questao_me(5, None, entradas))
        )
        assert embutido.respostas == {}
        assert embutido.alertas and "sem resposta legível" in embutido.alertas[0]

    def test_formato_codigo_com_anulada(self):
        linhas = _linhas(
            ("GABARITO DEFINITIVO", 120),
            ("PROVA DE CONHECIMENTOS BÁSICOS", 200),
            ("Curso: Agência", 170),
            ("<<N. Cargo/>> <<Nome do Cargo/>>", 32),
            ("CB2 CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL MÉDIO", 40, "CB2 "),
            ("Com base no Código de Ética, julgue o próximo item.", 28),
            ("1 J2418111 - ERRADO | Primeiro item", 28, "1 "),
            ("continua.", 46),
            ("Com base no Código de Ética, julgue o próximo item.", 28),
            ("2 B0702949 – CORRETO - ANULADO | Segundo item.", 28, "2 "),
        )
        mantidas, embutido = separar_gabarito_embutido(linhas)
        assert embutido.formato == FORMATO_CODIGO_CE
        assert embutido.versao == VERSAO_DEFINITIVO
        assert embutido.respostas == {1: "E", 2: "X"}
        assert [linha.texto for linha in mantidas] == [
            "Com base no Código de Ética, julgue o próximo item.",
            "1 Primeiro item",
            "continua.",
            "Com base no Código de Ética, julgue o próximo item.",
            "2 Segundo item.",
        ]

    def test_buraco_na_numeracao_vira_alerta(self):
        # A conferência itens × gabarito só olha as pontas da faixa: sem o
        # alerta, o item 2 seria engolido pelo 1.
        linhas = _linhas(
            ("1 Item um.", 28, "1"),
            ("JUSTIFICATIVA - Certo.", 46),
            ("<FimJust>", 46),
            ("2 Item dois, sem justificativa.", 28, "2"),
            ("3 Item três.", 28, "3"),
            ("JUSTIFICATIVA - Errado.", 46),
            ("<FimJust>", 46),
        )
        _, embutido = separar_gabarito_embutido(linhas)
        assert embutido.respostas == {1: "C", 3: "E"}
        assert embutido.alertas == ["questões sem resposta no caderno: ['2']"]


# PDFs reais ------------------------------------------------------------------

# Conferidos à mão nos PDFs: formato, versão, número de questões e algumas
# respostas (a anulada no definitivo é a questão que muda para X).
CADERNOS = {
    "CAESB_24_MATRIZ_039_CAESB_CG1_00_Com_Justificativas_atualizado.pdf": {
        "formato": FORMATO_JUSTIFICATIVA,
        "versao": VERSAO_PRELIMINAR,
        "tipo": QUESTAO_MULTIPLA_ESCOLHA,
        "numeros": range(1, 31),
        "respostas": {1: "D", 2: "A", 13: "A", 18: "C"},
        "definitivo": ("Gab_Definitivo_MATRIZ_039_CAESB_CG1_00.pdf", {18}),
    },
    # Questão 35: a justificativa da alternativa E não fecha com "*/"; o fim
    # é presumido antes da questão 36 (alerta informativo).
    "CAESB_24_P2_CARGO9_905BAE8B.pdf": {
        "formato": FORMATO_JUSTIFICATIVA,
        "versao": VERSAO_PRELIMINAR,
        "tipo": QUESTAO_MULTIPLA_ESCOLHA,
        "numeros": range(31, 71),
        "respostas": {35: "C", 36: "D"},
        "fim_presumido": True,
    },
    "PM_DF_25_CFO_P1_337DECAC.pdf": {
        "formato": FORMATO_JUSTIFICATIVA,
        "versao": VERSAO_PRELIMINAR,
        "tipo": QUESTAO_MULTIPLA_ESCOLHA,
        "numeros": range(1, 41),
        "respostas": {1: "B", 40: "A"},
        "definitivo": ("PM_DF_25_CFO_GAB_DEF_P1_A9642254.pdf", {29}),
    },
    "TC_DF_23_897_TCDF_CB1_01_COM_JUSTIFICATIVA.PDF": {
        "formato": FORMATO_JUSTIFICATIVA,
        "versao": VERSAO_PRELIMINAR,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 36),
        "respostas": {1: "C", 3: "E", 28: "C", 29: "E"},
        "definitivo": ("GAB_DEFINITIVO_897_TCDF_CB1_01.PDF", {18}),
    },
    "PC_DF_24_ADM_021_PCDF_CB1_01.PDF": {
        "formato": FORMATO_JUSTIFICATIVA,
        "versao": VERSAO_PRELIMINAR,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 51),
        "respostas": {1: "E", 50: "C"},
        "definitivo": ("GAB_DEFINITIVO_021_PCDF_CB1_01.PDF", {31}),
    },
    "AGSUS_25_CCE_BASICO_SUPERIOR_7EF273AD.pdf": {
        "formato": FORMATO_CODIGO_CE,
        "versao": VERSAO_DEFINITIVO,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 21),
        "respostas": {1: "E", 3: "C", 20: "E"},
    },
    "AGSUS_25_CCE_ESPECIFICO_CARGO1_5B0C591D.pdf": {
        "formato": FORMATO_CODIGO_CE,
        "versao": VERSAO_DEFINITIVO,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 21),
        "respostas": {1: "C", 2: "E", 20: "E"},
    },
    "AGSUS_26_RD_BASICO_MEDIO_E630B638.pdf": {
        "formato": FORMATO_CODIGO_CE,
        "versao": VERSAO_DEFINITIVO,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 21),
        "respostas": {1: "C", 2: "E", 4: "X"},
    },
    "AGSUS_26_RD_CARGO21_20EE6D4F.pdf": {
        "formato": FORMATO_CODIGO_CE,
        "versao": VERSAO_DEFINITIVO,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 21),
        "respostas": {1: "C", 2: "E"},
    },
    "AGSUS_26_RD_CARGOS_60_A_70_28D98E90.pdf": {
        "formato": FORMATO_CODIGO_CE,
        "versao": VERSAO_DEFINITIVO,
        "tipo": QUESTAO_CERTO_ERRADO,
        "numeros": range(1, 21),
        "respostas": {1: "C", 2: "E"},
    },
}


def _pdf(nome: str) -> Path:
    pdf = AMOSTRA / nome
    if not pdf.exists():
        pytest.skip(f"PDF de amostra {nome} não encontrado")
    return pdf


@cache
def _extrair(nome: str) -> tuple[dict, dict, dict]:
    pdf = _pdf(nome)
    doc = ler_gabarito_embutido(pdf)
    grade = doc["grade"]
    resultado, auditoria = extrair_caderno_objetivo(
        pdf, grade.respostas, nome, tipos=grade.tipos
    )
    return doc, resultado, auditoria


class TestCadernosReais:
    @pytest.mark.parametrize("nome", sorted(CADERNOS))
    def test_grade_do_proprio_caderno(self, nome):
        esperado = CADERNOS[nome]
        doc, _, _ = _extrair(nome)
        grade = doc["grade"]
        assert doc["formato"] == esperado["formato"]
        assert doc["versao"] == esperado["versao"]
        assert grade.numeros == list(esperado["numeros"])
        assert grade.tipo_detectado == esperado["tipo"]
        assert grade.alertas == []
        for numero, letra in esperado["respostas"].items():
            assert grade.respostas[numero] == letra, numero

    @pytest.mark.parametrize("nome", sorted(CADERNOS))
    def test_questoes_igual_grade_e_sem_justificativa_no_texto(self, nome):
        doc, resultado, auditoria = _extrair(nome)
        grade = doc["grade"]
        assert resultado["status"] == STATUS_SUCESSO
        assert resultado["itens_extraidos"] == len(grade.respostas)
        assert [q["numero"] for q in resultado["questoes"]] == grade.numeros
        assert resultado["itens_faltando"] == []
        assert resultado["itens_fora_do_gabarito"] == []
        assert auditoria["gabarito_embutido"]["linhas_removidas"]
        presumido = [
            a
            for a in resultado["alertas"]
            if a["tipo"] == "gabarito_embutido_fim_presumido"
        ]
        assert bool(presumido) == CADERNOS[nome].get("fim_presumido", False)
        assert all(a["severidade"] == "informativo" for a in presumido)
        textos = [tb["texto"] for tb in resultado["textos_base"]]
        for q in resultado["questoes"]:
            assert q["gabarito"] == grade.respostas[q["numero"]]
            assert q["anulada"] == (q["gabarito"] == "X")
            textos += [q["enunciado"]] + [a["texto"] for a in q["alternativas"] or []]
            if CADERNOS[nome]["tipo"] == QUESTAO_MULTIPLA_ESCOLHA:
                assert len(q["alternativas"]) == 5, q["numero"]
        for texto in textos:
            assert not PADRAO_MARCA_JUSTIFICATIVA.search(texto), texto[:80]
            assert not PADRAO_CODIGO_ITEM_INICIO.match(texto), texto[:80]
            assert "GABARITO DEFINITIVO" not in texto

    @pytest.mark.parametrize(
        "nome", sorted(n for n, e in CADERNOS.items() if "definitivo" in e)
    )
    def test_preliminar_impresso_bate_com_o_definitivo(self, nome):
        # O definitivo à parte muda só as anuladas destes cadernos: a leitura
        # do preliminar está certa e o definitivo tem de prevalecer.
        arquivo, anuladas = CADERNOS[nome]["definitivo"]
        if not (DEFINITIVOS / arquivo).exists():
            pytest.skip(f"Gabarito definitivo {arquivo} não encontrado")
        doc, _, _ = _extrair(nome)
        definitivo = ler_documento(DEFINITIVOS / arquivo)["grade"].respostas
        preliminar = doc["grade"].respostas
        assert set(definitivo) == set(preliminar)
        diferentes = {n for n in definitivo if definitivo[n] != preliminar[n]}
        assert diferentes == anuladas
        assert {definitivo[n] for n in diferentes} == {"X"}

    def test_figuras_da_justificativa_saem_e_a_da_questao_fica(self):
        # CAESB_24 CG1: a planilha da Q13 é figura da questão; as 5 telas da
        # justificativa (uma por alternativa) e os selos "Questão N"
        # desenhados não são.
        _, resultado, auditoria = _extrair(
            "CAESB_24_MATRIZ_039_CAESB_CG1_00_Com_Justificativas_atualizado.pdf"
        )
        assert resultado["total_figuras"] == 1
        assert {
            q["numero"]: len(q["figuras"])
            for q in resultado["questoes"]
            if q["figuras"]
        } == {13: 1}
        assert len(auditoria["gabarito_embutido"]["figuras_descartadas"]) == 5

    @pytest.mark.parametrize(
        ("nome", "trecho_do_alerta"),
        [
            # Questão 45: entradas sem fecho reconhecível; a justificativa
            # fica no texto e a questão, fora da grade.
            (
                "lote/CAESB_24__MATRIZ_039_CAESB_004_00_Com_Justificativas_OK.pdf",
                "questões sem resposta no caderno: ['45']",
            ),
            # Página 30: colunas fora de ordem, questões 97 e 98 trocadas.
            (
                "SEPLAD_DF_22_AUDITOR_798_SEPLAD_DFCB1_CE1_COM_JUSTIFICATIVAS.PDF",
                "questões sem resposta no caderno: ['97–98']",
            ),
        ],
    )
    def test_irregular_falha_explicita(self, nome, trecho_do_alerta):
        doc, resultado, _ = _extrair(nome)
        assert resultado["status"] == STATUS_FALHA_ITENS_DIVERGENTES
        irregular = [
            a
            for a in resultado["alertas"]
            if a["tipo"] == "gabarito_embutido_irregular"
        ]
        assert irregular and irregular[0]["severidade"] == "bloqueante"
        assert any(trecho_do_alerta in d for d in irregular[0]["detalhes"])

    @pytest.mark.parametrize(
        "nome",
        [
            # Tabela "ITEM N / GABARITO: CERTO" e rótulo "CORRETA"/"ERRADA" por
            # alternativa: fora desta etapa, ficam sem gabarito (falha
            # explícita `falha_sem_gabarito` no consumidor).
            "AGSUS_25_EC_BASICO_SUPERIOR_BC35E9B9.pdf",
            "AGSUS_25_EC_CARGO3_C61A21B0.pdf",
            "AGU_23_ESTAGIARIO_920_AGU_23_ESTAGIARIO_GABARITO_DEFINITIVO.PDF",
        ],
    )
    def test_formato_nao_suportado_fica_sem_gabarito(self, nome):
        assert ler_gabarito_embutido(_pdf(nome)) is None


# Fila (stats_writer) ----------------------------------------------------------


class TestClassificacaoNaFila:
    @pytest.mark.parametrize(
        ("nome", "stem", "identificador", "codigo"),
        [
            (
                "MATRIZ_039_CAESB_CG1_00_Com Justificativas_atualizado.pdf",
                "MATRIZ_039_CAESB_CG1_00",
                "CG1",
                None,
            ),
            (
                "897_TCDF_CB1_01_COM_JUSTIFICATIVA.PDF",
                "897_TCDF_CB1_01",
                "CB1",
                "897_TCDF_CB1_01",
            ),
            (
                "896_TCDF_002_01_COMJUSTIFICATIVA.PDF",
                "896_TCDF_002_01",
                "002",
                "896_TCDF_002_01",
            ),
            ("094_PF_CB1_01.pdf", "094_PF_CB1_01", "CB1", "094_PF_CB1_01"),
        ],
    )
    def test_sufixo_de_justificativa_sai_do_nome(
        self, nome, stem, identificador, codigo
    ):
        assert stem_caderno(nome) == stem
        assert identificador_prova(nome) == identificador
        assert codigo_caderno_do_nome(nome) == codigo

    @pytest.mark.parametrize(
        ("texto", "arquivo", "esperado"),
        [
            (
                "PROVA OBJETIVA (P1) E GABARITO PRELIMINAR COM JUSTIFICATIVAS - "
                "CARGOS 1 AO 18 (ATUALIZADO)",
                "MATRIZ_039_CAESB_CG1_00_Com Justificativas_atualizado.pdf",
                {"tipo": "objetiva_basica", "cargos_numeros": list(range(1, 19))},
            ),
            (
                "PROVA OBJETIVA (P2) E GABARITO PRELIMINAR COM JUSTIFICATIVAS - CARGO 1",
                "MATRIZ_039_CAESB_001_00_Com Justificativas_OK.pdf",
                {"tipo": "objetiva_especifica", "cargos_numeros": [1]},
            ),
            (
                "PROVA E GABARITO DEFINITIVO – CONHECIMENTOS ESPECÍFICOS - CARGOS 60 A 70",
                "28D98E90.pdf",
                {"tipo": "objetiva_especifica", "cargos_numeros": list(range(60, 71))},
            ),
            (
                "PROVA E GABARITO DEFINITIVO – CONHECIMENTOS BÁSICOS PARA O CARGO DE "
                "NÍVEL SUPERIOR",
                "7EF273AD.pdf",
                {"tipo": "objetiva_basica", "cargos_numeros": []},
            ),
            # Versão substituída por outra "(ATUALIZADO)".
            (
                "PROVA OBJETIVA (P1) E GABARITO PRELIMINAR COM JUSTIFICATIVAS - "
                "CARGOS 1 AO 18 (SEM EFEITO)",
                "MATRIZ_039_CAESB_CG1_00_Com Justificativas_OK.pdf",
                None,
            ),
            # "EXCETO" e "ESPECIALIDADE N": a lista de cargos sairia errada.
            (
                "PROVA OBJETIVA (P1) E GABARITO PRELIMINAR COM JUSTIFICATIVAS – PARA "
                "TODOS OS CARGOS (EXCETO 1, 2, 3, 7 E 17)",
                "021_PCDF_CB1_01.PDF",
                None,
            ),
            (
                "PROVA OBJETIVA (P3) E GABARITO PRELIMINAR COM JUSTIFICATIVAS – "
                "ESPECIALIDADE 1",
                "012_TCDF_AUDITOR_001_01.PDF",
                None,
            ),
            # Token e número da prova discordam (no TC_DF_24, `CG1` é a P2).
            (
                "PROVA OBJETIVA (P2) E GABARITO PRELIMINAR COM JUSTIFICATIVAS",
                "012_TCDF_AUDITOR_CG1_01.PDF",
                None,
            ),
            # Nome em hash e texto sem "conhecimentos": sem tipo seguro.
            (
                "PROVA OBJETIVA (P1) E GABARITO PRELIMINAR COM JUSTIFICATIVAS",
                "337DECAC06D244D3.pdf",
                None,
            ),
            # Caderno comum segue a regra de sempre.
            (
                "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS PARA OS CARGOS 1 E 2",
                "001_XX_CB1_01.pdf",
                {"tipo": "objetiva_basica", "cargos_numeros": [1, 2]},
            ),
        ],
    )
    def test_classificar_prova(self, texto, arquivo, esperado):
        assert classificar_prova(texto, arquivo) == esperado
