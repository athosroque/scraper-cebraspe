"""Testes do módulo de inventário e classificação pura de links de PDFs."""

import json
from pathlib import Path

import pymupdf as fitz
import pytest

from src.comparacao_texto import (
    PADRAO_EDITAL_ADMINISTRATIVO,
    PADRAO_PADRAO_RESPOSTA,
)
from src.inventario import (
    FORMATO_CE,
    FORMATO_DESCONHECIDO,
    FORMATO_ME,
    FORMATO_MISTO,
    INVENTARIO_ANOS_PATH,
    INVENTARIO_CONCURSOS_PATH,
    INVENTARIO_EXCLUSOES_PATH,
    INVENTARIO_RELATORIO_PATH,
    SLUGS_NAVEGACAO,
    TIPO_ADMINISTRATIVO,
    TIPO_CADERNO_COM_GABARITO,
    TIPO_CADERNO_DISCURSIVO,
    TIPO_CADERNO_OBJETIVO,
    TIPO_EDITAL_ABERTURA,
    TIPO_GABARITO,
    TIPO_NAO_CLASSIFICADO,
    TIPO_PADRAO_RESPOSTA,
    TIPO_PROVA_OUTRA,
    adicionar_concurso_jsonl,
    aplicar_exclusao,
    carregar_anos_json,
    carregar_concursos_jsonl,
    carregar_exclusoes,
    classificar_formato_texto,
    classificar_link_pdf,
    cobertura_por_ano,
    detectar_formato_caderno,
    escolher_cadernos_calibracao_me,
    escolher_edital_extracao,
    gerar_relatorio_md,
    iterar_concursos_jsonl,
    reclassificar_inventario,
    reclassificar_registro,
    resumir_pdfs,
    salvar_anos_json,
    salvar_concursos_jsonl,
    salvar_relatorio_md,
)

PROJETO_DIR = Path(__file__).resolve().parent.parent
PILOTO_DIR = PROJETO_DIR / "data" / "2025" / "CEBRASPE"
# Órgãos do piloto: outro concurso de 2025 baixado na mesma pasta (SEFA_PR no
# Gate da 8.M) não entra na regressão do piloto.
ORGAOS_PILOTO = ("CD", "IBAMA", "PF", "STM", "TCU")
AMOSTRA_DIR_TESTE = PROJETO_DIR / "data" / "inventario_amostra"
SEM_DADOS_PILOTO = (
    "data/2025/CEBRASPE ausente (PDFs e manifestos do piloto são gitignored; "
    "só existem no checkout com os dados baixados)"
)


class TestClassificarLinkPdfSonda:
    """Testa os casos reais identificados na sonda e especificados na Etapa 8.0."""

    def test_padrao_resposta_singular_definitivo(self):
        res = classificar_link_pdf("PADRÃO DEFINITIVO DE RESPOSTAS")
        assert res["tipo"] == TIPO_PADRAO_RESPOSTA
        assert res["versao"] == "definitivo"
        assert res["curso_formacao"] is False

    def test_padrao_resposta_plural_com_mencao_a_provas_discursivas(self):
        res = classificar_link_pdf(
            "PADRÕES DEFINITIVOS DE RESPOSTAS – PROVAS DISCURSIVAS(P3)"
        )
        assert res["tipo"] == TIPO_PADRAO_RESPOSTA
        assert res["versao"] == "definitivo"
        assert res["curso_formacao"] is False

    def test_comunicado_local_realizacao_prova_e_administrativo(self):
        res = classificar_link_pdf("COMUNICADO – LOCAL DE REALIZAÇÃO DA PROVA OBJETIVA")
        assert res["tipo"] == TIPO_ADMINISTRATIVO
        assert res["curso_formacao"] is False

    def test_edital_retificacao_e_reabertura_e_administrativo(self):
        res = classificar_link_pdf(
            "EDITAL Nº 8 - RETIFICAÇÃO E REABERTURA DO PERÍODO DE ACESSO"
        )
        assert res["tipo"] == TIPO_ADMINISTRATIVO
        assert res["curso_formacao"] is False

    def test_edital_abertura_atualizado_conforme_retificacoes(self):
        res = classificar_link_pdf(
            "EDITAL Nº 1 – ABERTURA – ATUALIZADO CONFORME RETIFICAÇÕES"
        )
        assert res["tipo"] == TIPO_EDITAL_ABERTURA
        assert res["curso_formacao"] is False

    def test_edital_abertura_simples(self):
        res = classificar_link_pdf("EDITAL Nº 1 – ABERTURA")
        assert res["tipo"] == TIPO_EDITAL_ABERTURA
        assert res["curso_formacao"] is False

    def test_edital_retificacao_simples_e_administrativo(self):
        res = classificar_link_pdf("EDITAL Nº 2 - RETIFICAÇÃO DO EDITAL DE ABERTURA")
        assert res["tipo"] == TIPO_ADMINISTRATIVO
        assert res["curso_formacao"] is False

    def test_prova_objetiva_conhecimentos_basicos(self):
        res = classificar_link_pdf("PROVA OBJETIVA – CONHECIMENTOS BÁSICOS")
        assert res["tipo"] == TIPO_CADERNO_OBJETIVO
        assert res["versao"] == "desconhecida"
        assert res["curso_formacao"] is False

    def test_prova_objetiva_curso_de_formacao(self):
        res = classificar_link_pdf("PROVA OBJETIVA – CURSO DE FORMAÇÃO")
        assert res["tipo"] == TIPO_CADERNO_OBJETIVO
        assert res["curso_formacao"] is True

    def test_gabarito_definitivo(self):
        res = classificar_link_pdf("GABARITO DEFINITIVO")
        assert res["tipo"] == TIPO_GABARITO
        assert res["versao"] == "definitivo"
        assert res["curso_formacao"] is False

    def test_gabarito_preliminar(self):
        res = classificar_link_pdf("GABARITO PRELIMINAR")
        assert res["tipo"] == TIPO_GABARITO
        assert res["versao"] == "preliminar"
        assert res["curso_formacao"] is False

    def test_caderno_discursivo(self):
        res = classificar_link_pdf("PROVA DISCURSIVA – CARGO 1")
        assert res["tipo"] == TIPO_CADERNO_DISCURSIVO
        assert res["curso_formacao"] is False

    def test_caderno_discursivo_plural(self):
        res = classificar_link_pdf("PROVAS DISCURSIVAS (P3)")
        assert res["tipo"] == TIPO_CADERNO_DISCURSIVO
        assert res["curso_formacao"] is False

    def test_edital_administrativo_resultado_provisorio(self):
        res = classificar_link_pdf(
            "EDITAL Nº 6 – RESULTADO FINAL NAS PROVAS OBJETIVAS E O RESULTADO PROVISÓRIO NA PROVA DISCURSIVA"
        )
        assert res["tipo"] == TIPO_ADMINISTRATIVO
        assert res["versao"] == "preliminar"

    def test_edital_administrativo_locais_aplicacao(self):
        res = classificar_link_pdf(
            "EDITAL Nº 5 – LOCAIS DE APLICAÇÃO DAS PROVAS OBJETIVAS E DA PROVA DISCURSIVA"
        )
        assert res["tipo"] == TIPO_ADMINISTRATIVO

    def test_nao_classificado_para_documento_generico(self):
        res = classificar_link_pdf("INFORME GERAL AOS CANDIDATOS")
        assert res["tipo"] == TIPO_NAO_CLASSIFICADO
        assert res["versao"] == "desconhecida"
        assert res["curso_formacao"] is False

    def test_texto_vazio_ou_none(self):
        res = classificar_link_pdf("")
        assert res["tipo"] == TIPO_NAO_CLASSIFICADO


# Textos reais de link (inventário 2020+, 2026-10-08) que o classificador
# antigo jogava em caderno_objetivo só por conterem "prova".
TEXTOS_FALSO_CADERNO_OBJETIVO = [
    ("PROVA ESCRITA DE POLÍTICA INTERNACIONAL – SEGUNDA FASE", TIPO_CADERNO_DISCURSIVO),
    ("PROVA ESCRITA DE ECONOMIA – SEGUNDA FASE", TIPO_CADERNO_DISCURSIVO),
    ("PROVA ESCRITA DE DIREITO – SEGUNDA FASE", TIPO_CADERNO_DISCURSIVO),
    ("PROVA SUBJETIVA – P2", TIPO_CADERNO_DISCURSIVO),
    ("PROVA PRÁTICA - P3", TIPO_CADERNO_DISCURSIVO),
    ("PROVA ESCRITA E PRÁTICA - PROVIMENTO", TIPO_CADERNO_DISCURSIVO),
    ("PROVA ESCRITA – CARGO 1", TIPO_CADERNO_DISCURSIVO),
    ("PROVAS ESCRITAS – TEÓRICA E PRÁTICA", TIPO_CADERNO_DISCURSIVO),
    ("PROVA ESCRITA TEÓRICO-PRÁTICA (P2)", TIPO_CADERNO_DISCURSIVO),
    ("PROVA ORAL - MALOTE 1", TIPO_PROVA_OUTRA),
    ("PROVA ORAL", TIPO_PROVA_OUTRA),
    ("Prova Oral - malote 1 - ponto 1", TIPO_PROVA_OUTRA),
    ("PROVA ORAL (APLICADA EM 29/03/2026) SUB JUDICE", TIPO_PROVA_OUTRA),
    ("PROVA ORAL - PONTO 2 - QUESTÃO 1", TIPO_PROVA_OUTRA),
    ("PROVA DE TRIBUNA - CASO HIPOTÉTICO (TEMA) 2", TIPO_PROVA_OUTRA),
    (
        "Prova de desempenho teórico-prático - cargo 16 - téc. de laboratório - "
        "área: análises clínicas",
        TIPO_PROVA_OUTRA,
    ),
    ("Comunicado - Suspensão da prova objetiva", TIPO_ADMINISTRATIVO),
    (
        "Comunicado – Relação final dos candidatos com a inscrição deferida para "
        "concorrer como PCD e informações sobre a prova",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado – Justificativas da banca para o deferimento ou indeferimento "
        "dos recursos interpostos contra a relação provisória da prova",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado - Relação final dos candidatos habilitados para a realização "
        "da prova escrita e prática",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Relação final dos candidatos habilitados para a realização da prova "
        "escrita e prática",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Relação provisória dos candidatos habilitados para a realização da "
        "prova escrita",
        TIPO_ADMINISTRATIVO,
    ),
    ("Comunicado – Data prova oral", TIPO_ADMINISTRATIVO),
    (
        "Comunicado – Prorrogação do prazo para agendamento para assistir à prova oral",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado – Espelhos definitivos da prova escrita atualizados",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado – Prova didática: Temas sorteados e ordem de apresentação",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Composição da Banca Examinadora (titulares e suplentes) da prova escrita",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado nº 5 – Informações sobre locais, horários e link de consulta "
        "aos locais de prova",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado – Aplicação das provas objetivas e da prova discursiva",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Movimentação financeira após a etapa: aplicação prova objetiva e discursiva",
        TIPO_ADMINISTRATIVO,
    ),
    ("Manual da prova prática (Libras)", TIPO_ADMINISTRATIVO),
    ("Orientações referentes à prova prática", TIPO_ADMINISTRATIVO),
    ("Sorteio dos temas da prova prática", TIPO_ADMINISTRATIVO),
    ("Adiamento das provas", TIPO_ADMINISTRATIVO),
    ("Relatório de movimentação financeira - Prova objetiva", TIPO_ADMINISTRATIVO),
    (
        "Edital N° 20/2026 - orientações para realização da prova on-line",
        TIPO_ADMINISTRATIVO,
    ),
    ("PROVA PRÁTICA DE HABILIDADES CLÍNICAS - 1º E 2º DIA", TIPO_PROVA_OUTRA),
    ("CTI_23_PROVA_ORAL_PADRAO_DE_RESPOSTA", TIPO_PADRAO_RESPOSTA),
    (
        "Portaria DG/PRF nº 650, de 22 de setembro de 2021 – Aprova o Regulamento "
        "do Curso de Formação Policial",
        TIPO_NAO_CLASSIFICADO,
    ),
]

# Cadernos reais que têm de continuar caderno: inventário 2020+ e os textos
# de link do piloto (data/2025/CEBRASPE/*/provas_texto_link.json).
TEXTOS_CADERNO_REAL = [
    ("PROVA OBJETIVA – CURSO DE FORMAÇÃO", TIPO_CADERNO_OBJETIVO),
    ("PROVA OBJETIVA – CURSO DE FORMAÇÃO (PROVA 2)", TIPO_CADERNO_OBJETIVO),
    ("CADERNO DE PROVA – CARGO 3", TIPO_CADERNO_OBJETIVO),
    ("PROVA OBJETIVA – CONHECIMENTOS BÁSICOS", TIPO_CADERNO_OBJETIVO),
    ("PROVA PREAMBULAR (OBJETIVA)", TIPO_CADERNO_OBJETIVO),
    ("PROVA OBJETIVA DE SELEÇÃO – OUTORGA POR PROVIMENTO", TIPO_CADERNO_OBJETIVO),
    ("PROVA OBJETIVA – PRIMEIRA FASE – PERÍODO DA MANHÃ", TIPO_CADERNO_OBJETIVO),
    (
        "PROVA OBJETIVA (P1) – CONHECIMENTOS ESPECÍFICOS – CARGO 2",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA O CARGO 15", TIPO_CADERNO_OBJETIVO),
    (
        "PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA OS CARGOS DE 1 A 14",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA OBJETIVA - CONHECIMENTOS ESPECÍFICOS – CARGO 10", TIPO_CADERNO_OBJETIVO),
    ("PROVA OBJETIVA - CONHECIMENTOS GERAIS PARA O CARGO 1", TIPO_CADERNO_OBJETIVO),
    (
        "PROVA OBJETIVA - CONHECIMENTOS GERAIS PARA OS CARGOS 2, 4, 5 E 7",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA OBJETIVA – CONHECIMENTOS BÁSICOS PARA O CARGO 1", TIPO_CADERNO_OBJETIVO),
    (
        "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS PARA OS CARGOS 2 E 3",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS", TIPO_CADERNO_OBJETIVO),
    (
        "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS PARA O CARGO 1",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 9", TIPO_CADERNO_OBJETIVO),
    (
        "PROVA OBJETIVA – CONHECIMENTOS GERAIS PARA OS CARGOS 1 E 2",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA ESCRITA OBJETIVA (P1)", TIPO_CADERNO_OBJETIVO),
    ("PROVA OBJETIVA COM JUSTIFICATIVAS", TIPO_CADERNO_OBJETIVO),
    ("1.ª PROVA OBJETIVA - CURSO DE FORMAÇÃO", TIPO_CADERNO_OBJETIVO),
    ("REAPLICAÇÃO SÃO MATEUS/ES - PROVA OBJETIVA", TIPO_CADERNO_OBJETIVO),
    ("CADERNO DE PROVAS - ENFERMAGEM", TIPO_CADERNO_OBJETIVO),
    # Caderno único com parte objetiva e discursiva: vale a parte objetiva.
    (
        "PROVAS OBJETIVAS E DISCURSIVA – CARGO 15: ASSESSOR JURÍDICO – ÁREA: DIREITO",
        TIPO_CADERNO_OBJETIVO,
    ),
    ("PROVA DISCURSIVA - CARGO 1", TIPO_CADERNO_DISCURSIVO),
    ("PROVA DISCURSIVA – CARGO 15", TIPO_CADERNO_DISCURSIVO),
    ("PROVAS DISCURSIVAS (P3)", TIPO_CADERNO_DISCURSIVO),
    (
        "PADRÃO DEFINITIVO DE RESPOSTA – PROVA DISCURSIVA – CARGO 1",
        TIPO_PADRAO_RESPOSTA,
    ),
    (
        "PADRÃO DEFINITIVO DE RESPOSTAS – PROVA DISCURSIVA – CARGO 2",
        TIPO_PADRAO_RESPOSTA,
    ),
    (
        "EDITAL Nº 5 – LOCAIS DE APLICAÇÃO DAS PROVAS OBJETIVAS E DA PROVA "
        "DISCURSIVA, BEM COMO A RENUMERAÇÃO DE TÓPICOS",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "EDITAL Nº 6 – RESULTADO FINAL NAS PROVAS OBJETIVAS E O RESULTADO "
        "PROVISÓRIO NA PROVA DISCURSIVA",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "EDITAL Nº 7 – RESULTADO FINAL NA PROVA DISCURSIVA, A CONVOCAÇÃO PARA A "
        "AVALIAÇÃO BIOPSICOSSOCIAL",
        TIPO_ADMINISTRATIVO,
    ),
]


# Falsos positivos da validação ao vivo de 2026-10-08 (ADR-037), textos reais.
TEXTOS_VALIDACAO_AO_VIVO = [
    # Prova e gabarito no mesmo PDF (AGSUS, AGU estagiário, CAESB, PC_DF, TC_DF)
    (
        "PROVA E GABARITO DEFINITIVO – CONHECIMENTOS BÁSICOS PARA O CARGO DE "
        "NÍVEL SUPERIOR",
        TIPO_CADERNO_COM_GABARITO,
    ),
    ("PROVA OBJETIVA E GABARITO DEFINITIVO", TIPO_CADERNO_COM_GABARITO),
    (
        "PROVA OBJETIVA (P2) E GABARITO PRELIMINAR COM JUSTIFICATIVAS - CARGO 9",
        TIPO_CADERNO_COM_GABARITO,
    ),
    (
        "PROVAS OBJETIVAS (P1 E P2) E GABARITO PRELIMINAR COM JUSTIFICATIVAS - CARGO 2",
        TIPO_CADERNO_COM_GABARITO,
    ),
    # Só o gabarito da prova (DEPEN) e gabarito com "recursos" no cargo
    (
        "1ª PROVA OBJETIVA - GABARITO PRELIMINAR - CURSO DE FORMAÇÃO PROFISSIONAL",
        TIPO_GABARITO,
    ),
    (
        "GABARITO DEFINITIVO - 16: FUNÇÃO – PROFESSOR DA EDUCAÇÃO ESPECIAL "
        "(PROFESSORES DAS SALAS DE RECURSOS, PAEE)",
        TIPO_GABARITO,
    ),
    ("Edital nº 8 – Gabaritos oficiais preliminares da prova objetiva", TIPO_GABARITO),
    # Cita o gabarito sem ser ele
    ("Justificativas de alterações de gabarito", TIPO_ADMINISTRATIVO),
    (
        "Edital nº 4 – Prorrogação do link para interpor recursos contra os "
        "gabaritos oficiais preliminares da prova objetiva",
        TIPO_ADMINISTRATIVO,
    ),
    (
        "Comunicado – Consulta aos gabaritos oficiais preliminares da prova "
        "objetiva e o caderno de prova",
        TIPO_ADMINISTRATIVO,
    ),
    # Abertura do SEBRAE (comunicado) e consolidação sem "atualizado"
    ("Comunicado nº 1 – Abertura", TIPO_EDITAL_ABERTURA),
    (
        "Comunicado nº 1 – Abertura – Atualizado conforme retificações",
        TIPO_EDITAL_ABERTURA,
    ),
    ("Edital nº 1 – Abertura, conforme retificações", TIPO_EDITAL_ABERTURA),
    ("Edital n° 017/2022 - Abertura", TIPO_EDITAL_ABERTURA),
    ("Portaria Conjunta e Edital nº 1 Abertura", TIPO_EDITAL_ABERTURA),
    # Abertura citada no meio ou "abertura do prazo/link/portões"
    (
        "Edital nº 21 – Prorrogação do prazo para comprovação da prática forense "
        "na forma do subitem 2.1.2 do edital de abertura",
        TIPO_ADMINISTRATIVO,
    ),
    ("Respostas às impugnações ao Edital nº 1 - Abertura", TIPO_ADMINISTRATIVO),
    (
        "Comunicado - Prorrogação do período de impugnação do edital de abertura",
        TIPO_ADMINISTRATIVO,
    ),
    ("Comunicado - Abertura dos Portões", TIPO_ADMINISTRATIVO),
    (
        "Edital nº 6 - Abertura de prazo - opção de língua estrangeira",
        TIPO_ADMINISTRATIVO,
    ),
    # Caderno discursivo do SEBRAE sem a palavra "prova"
    ("QUESTÃO DISCURSIVA (ESTUDO DE CASO) - PERFIL 1", TIPO_CADERNO_DISCURSIVO),
    ("QUESTÃO DISCURSIVA – PERFIL III", TIPO_CADERNO_DISCURSIVO),
    (
        "PADRÃO DEFINITIVO DE RESPOSTA - QUESTÃO DISCURSIVA (ESTUDO DE CASO) - PERFIL 1",
        TIPO_PADRAO_RESPOSTA,
    ),
]


class TestClassificadorFinoTextosReais:
    """Escrita/subjetiva/prática é discursiva; oral/didática/desempenho é
    `prova_outra` (sem caderno a extrair); comunicado/relação é administrativo."""

    @pytest.mark.parametrize(("texto", "esperado"), TEXTOS_VALIDACAO_AO_VIVO)
    def test_validacao_ao_vivo(self, texto, esperado):
        assert classificar_link_pdf(texto)["tipo"] == esperado

    @pytest.mark.parametrize(("texto", "esperado"), TEXTOS_FALSO_CADERNO_OBJETIVO)
    def test_nao_e_caderno_objetivo(self, texto, esperado):
        assert classificar_link_pdf(texto)["tipo"] == esperado

    @pytest.mark.parametrize(("texto", "esperado"), TEXTOS_CADERNO_REAL)
    def test_caderno_real_mantido(self, texto, esperado):
        assert classificar_link_pdf(texto)["tipo"] == esperado

    def test_relacao_sem_prova_e_administrativo(self):
        res = classificar_link_pdf(
            "Relação final dos candidatos com a inscrição deferida"
        )
        assert res["tipo"] == TIPO_ADMINISTRATIVO


class TestReclassificacaoOffline:
    """Recalcula tipo, contagens e alertas a partir de `pdfs[].texto`."""

    def _registro(self):
        return {
            "slug": "XX_2021_CF",
            "ano": 2021,
            "formato_provavel": "ce",
            "qtd_cadernos": 2,
            "alertas": [],
            "pdfs": [
                {
                    "url": "u1",
                    "texto": "PROVA ORAL - MALOTE 1",
                    "tipo": "caderno_objetivo",
                },
                {
                    "url": "u2",
                    "texto": "PROVA ESCRITA – CARGO 1",
                    "tipo": "caderno_objetivo",
                },
                {"url": "u3", "texto": "GABARITO DEFINITIVO", "tipo": "gabarito"},
            ],
        }

    def test_reclassificar_registro(self):
        novo = reclassificar_registro(self._registro())
        assert [p["tipo"] for p in novo["pdfs"]] == [
            TIPO_PROVA_OUTRA,
            TIPO_CADERNO_DISCURSIVO,
            TIPO_GABARITO,
        ]
        assert novo["pdfs"][0]["url"] == "u1"
        assert novo["qtd_cadernos"] == 1
        assert novo["contagens"][TIPO_CADERNO_OBJETIVO] == 0
        assert novo["contagens"][TIPO_PROVA_OUTRA] == 1
        assert novo["alertas"] == [
            "sem_edital_abertura",
            "curso_formacao",
            "ano_4_digitos",
        ]
        assert novo["formato_provavel"] == "ce"

    def test_resumir_pdfs_sem_nada(self):
        resumo = resumir_pdfs("AB_25", [])
        assert resumo["qtd_cadernos"] == 0
        assert resumo["alertas"] == ["sem_edital_abertura", "sem_caderno"]

    def test_sem_prova_ainda_aguarda_e_encerrado_e_pendencia(self):
        edital = {"tipo": TIPO_EDITAL_ABERTURA}
        for situacao in ("em_andamento", "inscricoes_abertas", "novos"):
            assert resumir_pdfs("AB_26", [edital], situacao)["alertas"] == [
                "aguardando_prova"
            ]
        assert resumir_pdfs("AB_26", [edital], "encerrado")["alertas"] == [
            "sem_caderno"
        ]
        # Em andamento com gabarito publicado e sem caderno é pendência.
        gab = {"tipo": TIPO_GABARITO}
        assert resumir_pdfs("AB_26", [edital, gab], "em_andamento")["alertas"] == [
            "sem_caderno"
        ]

    def test_sem_gabarito_so_com_caderno_objetivo(self):
        edital = {"tipo": TIPO_EDITAL_ABERTURA}
        discursiva = [
            edital,
            {"tipo": TIPO_CADERNO_DISCURSIVO},
            {"tipo": TIPO_PADRAO_RESPOSTA},
        ]
        assert resumir_pdfs("AB_23", discursiva, "encerrado")["alertas"] == []
        objetiva = [edital, {"tipo": TIPO_CADERNO_OBJETIVO}]
        assert resumir_pdfs("AB_23", objetiva, "encerrado")["alertas"] == [
            "sem_gabarito"
        ]

    def test_concurso_de_ingresso_cfo_nao_e_curso_de_formacao(self):
        pdfs = [
            {"tipo": TIPO_EDITAL_ABERTURA},
            {"tipo": TIPO_CADERNO_OBJETIVO},
            {"tipo": TIPO_GABARITO},
        ]
        assert resumir_pdfs("PM_DF_25_CFO", pdfs, "encerrado")["alertas"] == []
        assert resumir_pdfs("PM_PA_23_CFP", pdfs, "encerrado")["qtd_cadernos"] == 1
        assert "curso_formacao" in resumir_pdfs("ANEEL_25_CF", pdfs)["alertas"]

    def test_caderno_com_gabarito_conta_nos_dois(self):
        resumo = resumir_pdfs(
            "AB_24",
            [{"tipo": TIPO_EDITAL_ABERTURA}, {"tipo": TIPO_CADERNO_COM_GABARITO}],
            "encerrado",
        )
        assert resumo["qtd_cadernos"] == 1
        assert resumo["qtd_gabaritos"] == 1
        assert resumo["alertas"] == []

    def test_curso_de_formacao_nao_conta_para_o_site(self):
        pdfs = [
            {"tipo": TIPO_EDITAL_ABERTURA},
            {"tipo": TIPO_CADERNO_OBJETIVO, "curso_formacao": True},
            {"tipo": TIPO_GABARITO, "curso_formacao": True},
        ]
        resumo = resumir_pdfs("AB_24", pdfs, "encerrado")
        assert resumo["contagens"][TIPO_CADERNO_OBJETIVO] == 1
        assert resumo["qtd_cadernos"] == 0
        assert resumo["qtd_gabaritos"] == 0
        assert resumo["qtd_curso_formacao"] == 2
        assert resumo["alertas"] == ["sem_caderno", "curso_formacao"]

    def test_reclassificar_inventario_ordena_e_conta(self, tmp_path):
        caminho = tmp_path / "concursos.jsonl"
        outro = {"slug": "AA_25", "pdfs": []}
        salvar_concursos_jsonl([self._registro(), outro], caminho)
        resultado = reclassificar_inventario(caminho)
        assert resultado["antes"][TIPO_CADERNO_OBJETIVO] == 2
        assert resultado["depois"][TIPO_CADERNO_OBJETIVO] == 0
        assert [r["slug"] for r in carregar_concursos_jsonl(caminho)] == [
            "AA_25",
            "XX_2021_CF",
        ]


class TestPadroesRegexReutilizaveis:
    """Verifica as regexes PADRAO_PADRAO_RESPOSTA e PADRAO_EDITAL_ADMINISTRATIVO."""

    @pytest.mark.parametrize(
        "texto",
        [
            "PADRÃO DEFINITIVO DE RESPOSTAS",
            "PADRÕES DEFINITIVOS DE RESPOSTAS",
            "PADRÃO DE RESPOSTA",
            "padrao definitivo de respostas",
            "padroes definitivos de respostas",
            "PADRÃO DEFINITIVO DE RESPOSTA – PROVA DISCURSIVA – CARGO 1",
        ],
    )
    def test_padrao_padrao_resposta_casa_variacoes(self, texto):
        assert PADRAO_PADRAO_RESPOSTA.search(texto) is not None

    @pytest.mark.parametrize(
        "texto",
        [
            "EDITAL Nº 8",
            "edital no 8",
            "RESULTADO FINAL",
            "LOCAIS DE APLICAÇÃO",
            "COMUNICADO – LOCAL DE PROVA",
            "CONVOCAÇÃO",
            "REABERTURA",
            "RETIFICAÇÃO",
        ],
    )
    def test_padrao_edital_administrativo_casa_variacoes(self, texto):
        assert PADRAO_EDITAL_ADMINISTRATIVO.search(texto) is not None


class TestManifestosPiloto2025:
    """Verifica a classificação contra todos os links dos 5 concursos do piloto."""

    @pytest.fixture
    def pilot_dir(self):
        if not PILOTO_DIR.is_dir():
            pytest.skip(SEM_DADOS_PILOTO)
        return PILOTO_DIR

    def test_classificacao_todos_manifestos_piloto(self, pilot_dir):
        manifest_files = sorted(
            mf
            for mf in pilot_dir.glob("*/provas_texto_link.json")
            if mf.parent.name in ORGAOS_PILOTO
        )
        assert len(manifest_files) == 5, (
            f"Esperados 5 manifestos, encontrados: {manifest_files}"
        )

        contagens_totais: dict[str, int] = {}
        contagens_por_orgao: dict[str, dict[str, int]] = {}

        for mf in manifest_files:
            orgao = mf.parent.name
            dados = json.loads(mf.read_text(encoding="utf-8"))
            contagens_por_orgao[orgao] = {}

            for _arquivo, texto in dados.items():
                cls = classificar_link_pdf(texto)
                tipo = cls["tipo"]
                contagens_totais[tipo] = contagens_totais.get(tipo, 0) + 1
                contagens_por_orgao[orgao][tipo] = (
                    contagens_por_orgao[orgao].get(tipo, 0) + 1
                )

        # Regressão estrita com a contagem do piloto:
        # Total de provas = 70 cadernos (42 objetivo + 28 discursivo)
        total_provas = contagens_totais.get(
            TIPO_CADERNO_OBJETIVO, 0
        ) + contagens_totais.get(TIPO_CADERNO_DISCURSIVO, 0)
        assert total_provas == 70
        assert contagens_totais[TIPO_CADERNO_OBJETIVO] == 42
        assert contagens_totais[TIPO_CADERNO_DISCURSIVO] == 28
        assert contagens_totais[TIPO_PADRAO_RESPOSTA] == 27
        assert contagens_totais[TIPO_ADMINISTRATIVO] == 3
        assert contagens_totais.get(TIPO_NAO_CLASSIFICADO, 0) == 0

        # Verificações por órgão
        assert contagens_por_orgao["CD"] == {
            TIPO_PADRAO_RESPOSTA: 2,
            TIPO_CADERNO_OBJETIVO: 3,
            TIPO_CADERNO_DISCURSIVO: 2,
        }
        assert contagens_por_orgao["IBAMA"] == {
            TIPO_PADRAO_RESPOSTA: 3,
            TIPO_CADERNO_OBJETIVO: 5,
            TIPO_CADERNO_DISCURSIVO: 3,
        }
        assert contagens_por_orgao["PF"] == {
            TIPO_ADMINISTRATIVO: 3,
            TIPO_PADRAO_RESPOSTA: 15,
            TIPO_CADERNO_OBJETIVO: 17,
            TIPO_CADERNO_DISCURSIVO: 15,
        }
        assert contagens_por_orgao["STM"] == {
            TIPO_PADRAO_RESPOSTA: 7,
            TIPO_CADERNO_OBJETIVO: 15,
            TIPO_CADERNO_DISCURSIVO: 7,
        }
        assert contagens_por_orgao["TCU"] == {
            TIPO_CADERNO_OBJETIVO: 2,
            TIPO_CADERNO_DISCURSIVO: 1,
        }


class TestInventarioIO:
    """Testa funções canônicas de leitura e escrita em JSON e JSONL."""

    def test_salvar_e_carregar_anos_json(self, tmp_path):
        caminho = tmp_path / "inventario" / "anos.json"
        dados = {
            "2025": {
                "encerrado": ["CD_25_NS", "IBAMA_24"],
                "em_andamento": ["PF_25_ADM"],
                "outros": [],
            },
            "órgãos": ["Câmara dos Deputados", "Polícia Federal"],
        }

        # Salva e verifica que cria pastas pai
        salvar_anos_json(dados, caminho)
        assert caminho.exists()

        # Carrega e valida round-trip preservando caracteres especiais/acentos
        carregados = carregar_anos_json(caminho)
        assert carregados == dados

    def test_carregar_anos_json_inexistente_retorna_vazio(self, tmp_path):
        caminho = tmp_path / "inexistente.json"
        assert carregar_anos_json(caminho) == {}

    def test_salvar_e_carregar_concursos_jsonl(self, tmp_path):
        caminho = tmp_path / "inventario" / "concursos.jsonl"
        registros = [
            {"slug": "CD_25_NS", "ano": 2025, "situacao": "encerrado"},
            {"slug": "PF_25_ADM", "ano": 2025, "situacao": "em_andamento"},
        ]

        salvar_concursos_jsonl(registros, caminho)
        assert caminho.exists()

        carregados = carregar_concursos_jsonl(caminho)
        assert carregados == registros

        iterados = list(iterar_concursos_jsonl(caminho))
        assert iterados == registros

    def test_adicionar_concurso_jsonl(self, tmp_path):
        caminho = tmp_path / "concursos.jsonl"
        reg1 = {"slug": "TCU_25_TEFC", "ano": 2025}
        reg2 = {"slug": "STM_25", "ano": 2025}

        adicionar_concurso_jsonl(reg1, caminho)
        adicionar_concurso_jsonl(reg2, caminho)

        carregados = carregar_concursos_jsonl(caminho)
        assert len(carregados) == 2
        assert carregados[0]["slug"] == "TCU_25_TEFC"
        assert carregados[1]["slug"] == "STM_25"

    def test_carregar_concursos_jsonl_inexistente_retorna_vazio(self, tmp_path):
        caminho = tmp_path / "nao_existe.jsonl"
        assert carregar_concursos_jsonl(caminho) == []
        assert list(iterar_concursos_jsonl(caminho)) == []

    def test_constantes_e_caminhos(self):
        assert "em-andamento" in SLUGS_NAVEGACAO
        assert "encerrado" in SLUGS_NAVEGACAO
        assert "inscricoes-abertas" in SLUGS_NAVEGACAO
        assert "novos" in SLUGS_NAVEGACAO
        assert "main" in SLUGS_NAVEGACAO

        assert INVENTARIO_ANOS_PATH.name == "anos.json"
        assert INVENTARIO_CONCURSOS_PATH.name == "concursos.jsonl"
        assert INVENTARIO_RELATORIO_PATH.name == "RELATORIO.md"


class TestDetectarFormatoCaderno:
    """Valida a detecção de formato de caderno (ME, CE, misto ou ?) via PyMuPDF."""

    def test_pdf_sintetico_certo_errado(self):
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Julgue os itens a seguir... C E\n1 Item de teste.")
        pdf_bytes = doc.tobytes()
        doc.close()

        assert detectar_formato_caderno(pdf_bytes) == FORMATO_CE

    def test_pdf_sintetico_multipla_escolha(self):
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text(
            (50, 50),
            "Questão 1. Assinale a opção correta.\n"
            "(A) opção 1\n(B) opção 2\n(C) opção 3\n(D) opção 4\n(E) opção 5",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        assert detectar_formato_caderno(pdf_bytes) == FORMATO_ME

    def test_pdf_sintetico_multipla_escolha_variacao_letras_com_parentese_fechando(
        self,
    ):
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text(
            (50, 50),
            "1 Acerca de direito administrativo:\n"
            "A) primeira alternativa\n"
            "B) segunda alternativa\n"
            "C) terceira alternativa\n"
            "D) quarta alternativa\n"
            "E) quinta alternativa",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        assert detectar_formato_caderno(pdf_bytes) == FORMATO_ME

    def test_pdf_sintetico_misto(self):
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text(
            (50, 50),
            "Questão 1\nJulgue os itens a seguir... C E\n"
            "1 O item está correto.\n\n"
            "Questão 2\nJulgue o item seguinte.\n2 O item está errado.\n\n"
            "Questão 3. Assinale a opção correta.\n"
            "(A) opção 1\n(B) opção 2\n(C) opção 3\n(D) opção 4\n(E) opção 5\n"
            "Questão 4. Assinale a opção correta.\n"
            "(A) opção 1\n(B) opção 2\n(C) opção 3\n(D) opção 4\n(E) opção 5",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        assert detectar_formato_caderno(pdf_bytes) == FORMATO_MISTO

    def test_pdf_vazio_ou_sem_texto_retorna_desconhecido(self):
        doc = fitz.open()
        doc.new_page()  # Página em branco
        pdf_bytes = doc.tobytes()
        doc.close()

        assert detectar_formato_caderno(pdf_bytes) == FORMATO_DESCONHECIDO
        assert detectar_formato_caderno(b"") == FORMATO_DESCONHECIDO

    def test_pdf_corrompido_ou_inexistente_retorna_desconhecido(self, tmp_path):
        assert detectar_formato_caderno(b"nao e um pdf valido") == FORMATO_DESCONHECIDO
        caminho_inexistente = tmp_path / "nao_existe.pdf"
        assert detectar_formato_caderno(caminho_inexistente) == FORMATO_DESCONHECIDO

    def test_detectar_formato_a_partir_de_arquivo_em_disco(self, tmp_path):
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((50, 50), "Julgue os itens subsecutivos... C E")
        caminho = tmp_path / "caderno_ce.pdf"
        doc.save(str(caminho))
        doc.close()

        # Aceita Path e str
        assert detectar_formato_caderno(caminho) == FORMATO_CE
        assert detectar_formato_caderno(str(caminho)) == FORMATO_CE

    def test_pdf_real_do_piloto_identificado_como_ce(self):
        caminho_real = PILOTO_DIR / "IBAMA" / "Provas" / "057_IBAMA_001_01.pdf"
        if not caminho_real.exists():
            pytest.skip(SEM_DADOS_PILOTO)
        assert detectar_formato_caderno(caminho_real) == FORMATO_CE


# Questão ME real do CEBRASPE (MTE_25, caderno 090_MTECF_001_01): cabeçalho
# "Questão N", alternativas "A texto" sem parênteses e "Julgue os itens ...
# Assinale a opção correta" dentro da própria questão.
TRECHO_ME_CEBRASPE = """Questão 1

Para assegurar a independência dos inspetores, a Convenção n.º 81 prevê que

A os inspetores sejam remunerados também pelas empresas
fiscalizadas.
B inspetores sejam contratados sem estatuto de servidor público.
C a inspeção esteja subordinada aos sindicatos.
D a inspeção seja gerida por autoridades locais.
E inspetores devem ter estabilidade no emprego.

Questão 2

Julgue os itens a seguir, acerca da inspeção do trabalho.
I A fiscalização indireta dispensa a visita.
II A dupla visita é obrigatória.
Assinale a opção correta.

A Apenas o item I está certo.
B Apenas o item II está certo.
C Apenas os itens I e II estão certos.
D Nenhum item está certo.
E Todos os itens estão certos.
"""

TRECHO_CE_CEBRASPE = """A Constituição Federal garante a todos o acesso à justiça.
E o Estado deve prestar assistência jurídica integral.
Considerando o texto precedente, julgue os itens a seguir.
1 O acesso à justiça é direito fundamental.
2 A assistência jurídica é facultativa.
Julgue os próximos itens, relativos a atos administrativos.
3 A presunção de legitimidade é absoluta.
"""


class TestClassificarFormatoTexto:
    def test_me_cebraspe_com_julgue_dentro_da_questao(self):
        assert classificar_formato_texto(TRECHO_ME_CEBRASPE) == FORMATO_ME

    def test_ce_com_linhas_iniciadas_por_artigo(self):
        assert classificar_formato_texto(TRECHO_CE_CEBRASPE) == FORMATO_CE

    def test_um_julgue_solto_nao_vira_misto(self):
        texto = TRECHO_ME_CEBRASPE * 4 + "\nQuestão 9\nJulgue o item.\n"
        assert classificar_formato_texto(texto) == FORMATO_ME

    def test_misto_com_peso_de_ce(self):
        texto = TRECHO_CE_CEBRASPE + "\nQuestão 9\n" + TRECHO_ME_CEBRASPE
        assert classificar_formato_texto(texto) == FORMATO_MISTO

    def test_vazio(self):
        assert classificar_formato_texto("") == FORMATO_DESCONHECIDO
        assert classificar_formato_texto("Texto sem prova.") == FORMATO_DESCONHECIDO


# Cadernos reais em data/inventario_amostra (gitignored): os 4 primeiros saíam
# "misto" com a heurística antiga e são ME puros.
AMOSTRA_ME_REAL = [
    "MTE_25_090_MTECF_001_01.pdf",
    "PGE_PI_25_092_PGEPI_001_01.pdf",
    "TCE_MS_25_CONSELHEIRO_288849B0809C8C86070794E694DC7FD230510A3C84A10D51584955755F01411C.pdf",
    "UNIVESP_25_PSS_082_UNIVESP_PSS_CG1_01.pdf",
    "PC_CE_25_DELEGADO_084_PC_CE_001_01.pdf",
    "BANRISUL_25_077_BANRISUL_CB1_01.pdf",
    "SEDUC_PI_25_PROFESSOR_36C1CD17BF9F56A1B988654F309FB56EAA9C3EFA41C9A24884E6229878D6D10A.pdf",
    "TCE_MG_25_320D70B97CC0EDBE166890B55FCDA7A4D04AC4E219402DE1DDEE1BDC051EC6F5.pdf",
]


class TestFormatoCadernosReais:
    @pytest.mark.parametrize("arquivo", AMOSTRA_ME_REAL)
    def test_amostra_me_real(self, arquivo):
        caminho = AMOSTRA_DIR_TESTE / arquivo
        if not caminho.is_file():
            pytest.skip(f"{caminho} ausente (amostra gitignored)")
        assert detectar_formato_caderno(caminho) == FORMATO_ME

    def test_42_cadernos_objetivos_do_piloto_sao_ce(self):
        if not PILOTO_DIR.is_dir():
            pytest.skip(SEM_DADOS_PILOTO)
        formatos = {}
        for mf in sorted(PILOTO_DIR.glob("*/provas_texto_link.json")):
            if mf.parent.name not in ORGAOS_PILOTO:
                continue
            textos = json.loads(mf.read_text(encoding="utf-8"))
            for arquivo, texto in textos.items():
                if classificar_link_pdf(texto)["tipo"] == TIPO_CADERNO_OBJETIVO:
                    caminho = mf.parent / "Provas" / arquivo
                    formatos[str(caminho)] = detectar_formato_caderno(caminho)
        assert len(formatos) == 42
        assert set(formatos.values()) == {FORMATO_CE}, formatos


class TestRelatorioInventario:
    """Valida a geração e salvamento do relatório Markdown inventario/RELATORIO.md."""

    @pytest.fixture
    def mock_concursos(self):
        return [
            {
                "slug": "CD_25_NS",
                "orgao": "Câmara dos Deputados",
                "ano": 2025,
                "situacao": "encerrado",
                "no_banco": True,
                "formato_provavel": FORMATO_CE,
                "url": "https://www.cebraspe.org.br/concursos/CD_25_NS",
                "pdfs": [
                    {
                        "url": "http://cdn/edital.pdf",
                        "texto": "EDITAL Nº 1 – ABERTURA",
                        "tipo": TIPO_EDITAL_ABERTURA,
                        "versao": "desconhecida",
                    },
                    {
                        "url": "http://cdn/prova_cb.pdf",
                        "texto": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                        "versao": "desconhecida",
                    },
                    {
                        "url": "http://cdn/gabarito.pdf",
                        "texto": "GABARITO DEFINITIVO",
                        "tipo": TIPO_GABARITO,
                        "versao": "definitivo",
                    },
                    {
                        "url": "http://cdn/padrao.pdf",
                        "texto": "PADRÃO DEFINITIVO DE RESPOSTAS",
                        "tipo": TIPO_PADRAO_RESPOSTA,
                        "versao": "definitivo",
                    },
                ],
            },
            {
                "slug": "MPO_2024_ESP",
                "orgao": "Ministério do Planejamento",
                "ano": 2024,
                "situacao": "encerrado",
                "no_banco": False,
                "formato_provavel": FORMATO_ME,
                "url": "https://www.cebraspe.org.br/concursos/MPO_2024_ESP",
                "pdfs": [
                    {
                        "url": "http://cdn/edital_mpo.pdf",
                        "texto": "EDITAL Nº 1 – ABERTURA",
                        "tipo": TIPO_EDITAL_ABERTURA,
                        "versao": "desconhecida",
                    },
                    {
                        "url": "http://cdn/prova_cb_mpo.pdf",
                        "texto": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                        "versao": "desconhecida",
                    },
                    {
                        "url": "http://cdn/prova_ce_mpo.pdf",
                        "texto": "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                        "versao": "desconhecida",
                    },
                    {
                        "url": "http://cdn/gab_mpo.pdf",
                        "texto": "GABARITO DEFINITIVO",
                        "tipo": TIPO_GABARITO,
                        "versao": "definitivo",
                    },
                    {
                        "url": "http://cdn/comunicado.pdf",
                        "texto": "COMUNICADO ESPECIAL SOBRE HORÁRIOS",
                        "tipo": TIPO_NAO_CLASSIFICADO,
                        "versao": "desconhecida",
                    },
                    {
                        "url": "http://cdn/comunicado2.pdf",
                        "texto": "COMUNICADO ESPECIAL SOBRE HORÁRIOS",
                        "tipo": TIPO_NAO_CLASSIFICADO,
                        "versao": "desconhecida",
                    },
                ],
            },
            {
                "slug": "ANTAQ_25_CF",
                "orgao": "ANTAQ",
                "ano": 2025,
                "situacao": "em-andamento",
                "no_banco": False,
                "formato_provavel": FORMATO_CE,
                "alertas": ["curso_formacao", "sem_edital_abertura"],
                "url": "https://www.cebraspe.org.br/concursos/ANTAQ_25_CF",
                "pdfs": [
                    {
                        "url": "http://cdn/prova_cf.pdf",
                        "texto": "PROVA OBJETIVA – CURSO DE FORMAÇÃO",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                        "curso_formacao": True,
                        "versao": "desconhecida",
                    },
                ],
            },
            {
                "slug": "INSS_2015",
                "orgao": "INSS",
                "ano": 2015,
                "situacao": "encerrado",
                "no_banco": False,
                "formato_provavel": FORMATO_CE,
                "alertas": ["ano_4_digitos", "sem_caderno", "sem_gabarito"],
                "url": "https://www.cebraspe.org.br/concursos/INSS_2015",
                "pdfs": [],
            },
        ]

    def test_gerar_relatorio_md_contem_todas_as_secoes_e_metricas(self, mock_concursos):
        anos_data = {"ano_desconhecido": ["SLUG_SEM_ANO"]}
        md = gerar_relatorio_md(mock_concursos, anos_data)

        # 1. Título e Metadados
        assert "# Relatório Analítico de Inventário de Concursos CEBRASPE" in md
        assert "**Total de concursos mapeados:** 4 (3 com ano ≥ 2020)" in md
        assert "**Total de PDFs identificados:** 11" in md

        # 2. Tabela resumo por ano e situação
        assert "## Tabela Resumo por Ano e Situação" in md
        assert (
            "| Ano | Situação | Concursos | Fora do Site | Cadernos | Gabaritos | Padrões de Resposta | Formato CE | Formato ME | No Banco |"
            in md
        )
        assert "| 2025 | encerrado | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 1 |" in md
        # O caderno de curso de formação não conta (fora do site).
        assert "| 2025 | em-andamento | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |" in md
        assert "| 2024 | encerrado | 1 | 0 | 2 | 1 | 0 | 0 | 1 | 0 |" in md
        assert "| 2015 | encerrado | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |" in md
        assert (
            "| **Total** | - | **4** | **0** | **3** | **2** | **1** | **3** | **1** | **1** |"
            in md
        )

        # 3. Cadernos ME identificados com destaques
        assert "## Cadernos de Múltipla Escolha (ME) Identificados" in md
        assert "| MPO_2024_ESP | 2024 | encerrado |" in md
        assert "## Cadernos ME para Calibrar a Etapa 8.M" in md
        assert "Nenhum caderno ME da amostra disponível em disco." in md
        assert "## Formato na Amostra (CE × ME)" in md
        assert "| `me` | 1 |" in md

        # 4. Alertas e Casos Especiais
        assert "## Alertas e Casos Especiais" in md
        assert "### Concursos sem Edital de Abertura" in md
        assert "ANTAQ_25_CF" in md
        assert "INSS_2015" in md

        assert "### Concursos sem Caderno de Prova ou sem Gabarito" in md
        assert "ANTAQ_25_CF" in md
        assert "INSS_2015" in md

        assert "### Provas de Curso de Formação (fora do site)" in md
        assert "- **ANTAQ_25_CF**: 1" in md

        assert "### Concursos com Ano de 4 Dígitos no Slug" in md
        assert "MPO_2024_ESP" in md
        assert "INSS_2015" in md

        assert "### Concursos com Ano Desconhecido nas Listagens" in md
        assert "SLUG_SEM_ANO" in md

        # 5. Concursos do piloto no banco
        assert "## Concursos do Piloto no Banco" in md
        assert "CD_25_NS" in md
        assert "Confirmado (`True`)" in md

        # 6. Top textos não classificados
        assert "## Top Textos Não Classificados" in md
        assert "COMUNICADO ESPECIAL SOBRE HORÁRIOS" in md
        assert "| 2 |" in md

    def test_fora_do_site_e_aguardando_saem_dos_alertas(self):
        concursos = [
            aplicar_exclusao(
                {
                    "slug": "IBGE_20_AGENTE",
                    "ano": 2020,
                    "situacao": "encerrado",
                    "pdfs": [],
                },
                {"IBGE_20_AGENTE": {"categoria": "cancelado", "motivo": "Cancelado."}},
            ),
            {
                "slug": "PC_PE_26",
                "ano": 2026,
                "situacao": "novos",
                "pdfs": [
                    {"tipo": TIPO_EDITAL_ABERTURA, "texto": "Edital nº 1 – Abertura"}
                ],
            },
        ]
        md = gerar_relatorio_md(concursos)
        fora, resto = md.split("## Aguardando Prova")
        assert (
            "| IBGE_20_AGENTE | 2020 | Concurso cancelado ou suspenso antes da prova | Cancelado. |"
            in fora
        )
        assert "- **PC_PE_26** (2026, novos)" in resto
        alertas = md.split("## Alertas e Casos Especiais")[1]
        assert "IBGE_20_AGENTE" not in alertas
        assert "PC_PE_26" not in alertas
        assert "| 2020 | encerrado | 1 | 1 |" in md

    def test_cobertura_e_calibracao_no_relatorio(self, mock_concursos):
        anos_data = {
            "2025": {
                "encerrado": ["CD_25_NS", "FALTA_25"],
                "em_andamento": ["ANTAQ_25_CF"],
                "outros": ["ANTAQ_25_CF"],
            },
            "2015": {"encerrado": ["INSS_2015"]},
        }
        calibracao = [
            {
                "papel": "com figura",
                "slug": "MPO_2024_ESP",
                "texto": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
                "arquivo": "MPO_2024_ESP_x.pdf",
                "paginas_figura": [5],
            }
        ]
        concursos = [{**c, "data_mapeamento": "2026-10-08"} for c in mock_concursos]
        md = gerar_relatorio_md(concursos, anos_data, calibracao)
        assert "## Cobertura do Mapeamento (2020+)" in md
        assert "| 2025 | 3 | 2 | 0 | 1 |" in md
        assert "- **FALTA_25**: sem estado" in md
        assert "`data/inventario_amostra/MPO_2024_ESP_x.pdf` | 5 |" in md

    def test_cobertura_por_ano_separa_erro(self):
        concursos = [
            {"slug": "A_25", "data_mapeamento": "x"},
            {"slug": "B_25", "data_mapeamento": "x", "erro": "timeout"},
        ]
        anos = {"2025": {"encerrado": ["A_25", "B_25", "C_25"]}, "2019": {}}
        assert cobertura_por_ano(concursos, anos) == [
            {
                "ano": 2025,
                "listados": 3,
                "mapeados": 1,
                "com_erro": ["B_25"],
                "sem_estado": ["C_25"],
            }
        ]

    def test_escolher_cadernos_calibracao_me(self, tmp_path):
        def _pdf(nome, com_figura=False):
            doc = fitz.open()
            doc.new_page()
            pagina = doc.new_page()
            if com_figura:
                pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40), False)
                pagina.insert_image(fitz.Rect(100, 300, 300, 450), pixmap=pix)
            doc.save(str(tmp_path / nome))
            doc.close()

        _pdf("A.pdf", com_figura=True)
        _pdf("B.pdf")
        _pdf("C.pdf")
        concursos = [
            {
                "slug": slug,
                "ano": 2025,
                "formato_provavel": FORMATO_ME,
                "amostra_formato": {"arquivo": arquivo, "texto": texto},
            }
            for slug, arquivo, texto in [
                ("A_25", "A.pdf", "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS"),
                ("B_25", "B.pdf", "PROVA OBJETIVA – CONHECIMENTOS GERAIS"),
                ("C_25", "C.pdf", "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS"),
            ]
        ] + [{"slug": "D_25", "ano": 2025, "formato_provavel": FORMATO_CE}]
        escolhidos = escolher_cadernos_calibracao_me(concursos, tmp_path)
        assert [(e["papel"], e["slug"]) for e in escolhidos] == [
            ("com figura", "A_25"),
            ("conhecimentos básicos", "B_25"),
            ("conhecimentos específicos", "C_25"),
        ]
        assert escolhidos[0]["paginas_figura"] == [2]

    def test_gerar_relatorio_md_lista_vazia(self):
        md = gerar_relatorio_md([])
        assert "# Relatório Analítico de Inventário de Concursos CEBRASPE" in md
        assert "**Total de concursos mapeados:** 0" in md
        assert "Nenhum caderno de Múltipla Escolha (ME) identificado" in md
        assert "Nenhum link com tipo `nao_classificado` encontrado." in md

    def test_salvar_relatorio_md(self, tmp_path):
        caminho = tmp_path / "inventario" / "RELATORIO.md"
        conteudo = "# Teste de Relatório\n\nTexto com acentuação: Gabaritos e Padrões."
        salvar_relatorio_md(conteudo, caminho)

        assert caminho.exists()
        lido = caminho.read_text(encoding="utf-8")
        assert lido == conteudo


class TestExclusoes:
    """Concursos fora do site (ADR-037): `inventario/exclusoes.json`."""

    def _gravar(self, tmp_path, concursos):
        caminho = tmp_path / "exclusoes.json"
        caminho.write_text(json.dumps({"concursos": concursos}), encoding="utf-8")
        return caminho

    def test_carregar_e_aplicar(self, tmp_path):
        caminho = self._gravar(
            tmp_path, [{"slug": "A_20", "categoria": "cancelado", "motivo": "x"}]
        )
        exclusoes = carregar_exclusoes(caminho)
        assert exclusoes == {"A_20": {"categoria": "cancelado", "motivo": "x"}}
        fora = aplicar_exclusao({"slug": "A_20"}, exclusoes)
        assert fora["incluir"] is False
        assert fora["exclusao"]["categoria"] == "cancelado"
        dentro = aplicar_exclusao({"slug": "B_20"}, exclusoes)
        assert dentro["incluir"] is True
        assert dentro["exclusao"] is None

    def test_sem_arquivo_nao_exclui_nada(self, tmp_path):
        assert carregar_exclusoes(tmp_path / "nao_existe.json") == {}

    @pytest.mark.parametrize(
        "concursos",
        [
            [{"slug": "A_20", "categoria": "inventada", "motivo": "x"}],
            [{"slug": "A_20", "categoria": "cancelado", "motivo": " "}],
            [
                {"slug": "A_20", "categoria": "cancelado", "motivo": "x"},
                {"slug": "A_20", "categoria": "sem_prova", "motivo": "y"},
            ],
        ],
    )
    def test_lista_invalida_levanta_erro(self, tmp_path, concursos):
        with pytest.raises(ValueError):
            carregar_exclusoes(self._gravar(tmp_path, concursos))

    def test_reclassificar_inventario_aplica_exclusoes(self, tmp_path):
        caminho = tmp_path / "concursos.jsonl"
        salvar_concursos_jsonl(
            [
                {"slug": "A_20", "situacao": "encerrado", "pdfs": []},
                {"slug": "B_20", "situacao": "encerrado", "pdfs": []},
            ],
            caminho,
        )
        exclusoes = self._gravar(
            tmp_path, [{"slug": "A_20", "categoria": "sem_prova", "motivo": "x"}]
        )
        reclassificar_inventario(caminho, exclusoes)
        por_slug = {c["slug"]: c for c in carregar_concursos_jsonl(caminho)}
        assert por_slug["A_20"]["incluir"] is False
        assert por_slug["B_20"]["incluir"] is True

    def test_arquivo_real_bate_com_o_inventario(self):
        """Todo slug excluído existe no inventário e está com incluir=false."""
        exclusoes = carregar_exclusoes(INVENTARIO_EXCLUSOES_PATH)
        assert exclusoes
        inventario = {c["slug"]: c for c in carregar_concursos_jsonl()}
        for slug, exclusao in exclusoes.items():
            assert slug in inventario, slug
            assert inventario[slug]["incluir"] is False, slug
            assert inventario[slug]["exclusao"] == exclusao, slug
        incluidos = [c for c in inventario.values() if c["slug"] not in exclusoes]
        assert all(c["incluir"] is True for c in incluidos)


class TestEscolherEditalExtracao:
    """Valida a seleção canônica do edital de abertura (C0 / KAN-30)."""

    def test_lista_vazia_retorna_none(self):
        assert escolher_edital_extracao([]) is None

    def test_edital_unico_retorna_ele_mesmo(self):
        edital = {
            "url": "https://cdn.cebraspe.org.br/ed1.pdf",
            "texto": "Edital nº 5 – Abertura",
        }
        assert escolher_edital_extracao([edital]) == edital

    def test_escolhe_atualizado_conforme_retificacoes_banrisul(self):
        editais = [
            {
                "url": "https://cdn.cebraspe.org.br/ed1_atualizado.pdf",
                "texto": "Edital nº 1 – Abertura, atualizado conforme retificações",
            },
            {
                "url": "https://cdn.cebraspe.org.br/ed1_original.pdf",
                "texto": "Edital nº 1 – Abertura",
            },
        ]
        escolhido = escolher_edital_extracao(editais)
        assert escolhido == editais[0]

    def test_escolhe_atualizado_comunicado_sebrae(self):
        editais = [
            {
                "url": "https://cdn.cebraspe.org.br/comunicado1_atualizado.pdf",
                "texto": "Comunicado nº 1 – Abertura – Atualizado conforme retificações",
            },
            {
                "url": "https://cdn.cebraspe.org.br/comunicado1_original.pdf",
                "texto": "Comunicado nº 1 - Abertura",
            },
        ]
        escolhido = escolher_edital_extracao(editais)
        assert escolhido == editais[0]

    def test_desempata_por_maior_numero_de_retificacao(self):
        editais = [
            {
                "url": "https://cdn.cebraspe.org.br/ed1_ret2.pdf",
                "texto": "Edital nº 1 – Abertura – Atualizado conforme retificação nº 2",
            },
            {
                "url": "https://cdn.cebraspe.org.br/ed1_ret5.pdf",
                "texto": "Edital nº 1 – Abertura – Atualizado conforme retificação nº 5",
            },
        ]
        escolhido = escolher_edital_extracao(editais)
        assert escolhido == editais[1]

    def test_empate_sem_desempate_retorna_none_com_log_ambiguo(self, caplog):
        editais = [
            {
                "url": "https://cdn.cebraspe.org.br/ed1_a.pdf",
                "texto": "Edital nº 1 – Abertura – Atualizado conforme retificações",
            },
            {
                "url": "https://cdn.cebraspe.org.br/ed1_b.pdf",
                "texto": "Edital nº 1 – Abertura – Atualizado conforme retificações",
            },
        ]
        with caplog.at_level("WARNING"):
            escolhido = escolher_edital_extracao(editais)
        assert escolhido is None
        assert "[EDITAL_AMBIGUO]" in caplog.text

    def test_multiplos_editais_sem_consolidado_retorna_none_com_log_ambiguo(
        self, caplog
    ):
        editais = [
            {
                "url": "https://cdn.cebraspe.org.br/ed1.pdf",
                "texto": "Edital nº 1 - Abertura",
            },
            {
                "url": "https://cdn.cebraspe.org.br/ed2.pdf",
                "texto": "Edital nº 2 - Abertura",
            },
        ]
        with caplog.at_level("WARNING"):
            escolhido = escolher_edital_extracao(editais)
        assert escolhido is None
        assert "[EDITAL_AMBIGUO]" in caplog.text


class TestCorrecoesClassificador8C:
    """Valida correções mínimas do classificador fino em 8.C/C0."""

    @pytest.mark.parametrize(
        "texto",
        [
            "PROVA PRÁTICA - OPÇÃO 40000002: TÉCNICO – ÁREA: LABORATÓRIO E CAMPOS EXPERIMENTAIS – SUBÁREA: MANEJO ANIMAL",
            "PROVA PRÁTICA - OPÇÃO 40001925: TÉCNICO – ÁREA: LABORATÓRIO E CAMPOS EXPERIMENTAIS – SUBÁREA: MANEJO FLORESTAL",
            "PROVA PRÁTICA - OPÇÃO 40004381: TÉCNICO – ÁREA: MECÂNICA – SUBÁREA: MECÂNICA DE PRECISÃO",
            "PROVA PRÁTICA - OPÇÃO 40000007: ASSISTENTE – ÁREA: LABORATÓRIO E CAMPOS EXPERIENCIAIS – SUBÁREA: MANEJO ANIMAL",
            "PROVA PRÁTICA - OPÇÃO 40000035: ASSISTENTE – ÁREA: SUPRIMENTO, MANUTENÇÃO E SERVIÇOS – SUBÁREA: OPERADOR DE MÁQUINAS AGRÍCOLAS E VEÍCULOS",
        ],
    )
    def test_prova_pratica_opcao_classificada_como_prova_outra(self, texto):
        classif = classificar_link_pdf(texto)
        assert classif["tipo"] == TIPO_PROVA_OUTRA

    def test_prova_pratica_p3_juridica_permanece_caderno_discursivo(self):
        classif = classificar_link_pdf("PROVA PRÁTICA - P3")
        assert classif["tipo"] == TIPO_CADERNO_DISCURSIVO

    def test_caderno_unico_provas_objetivas_e_discursiva_permanece_objetivo(self):
        texto = "PROVAS OBJETIVAS E DISCURSIVA – CARGO 1: ANALISTA EM DESENVOLVIMENTO REGIONAL – ÁREA: ADMINISTRAÇÃO"
        classif = classificar_link_pdf(texto)
        assert classif["tipo"] == TIPO_CADERNO_OBJETIVO
