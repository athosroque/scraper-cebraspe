import re
from pathlib import Path

import pymupdf
import pytest

from src.edital_parser import (
    CAMPOS_CLASSIFICACAO_CHUNK,
    PADRAO_CARGO,
    PADRAO_MATERIA,
    PADRAO_RESTRICAO_CARGO,
    ChunkTaxonomia,
    _limpar_ruido_edital,
    detectar_cargo_e_nivel_edital,
    detectar_nivel_no_texto,
    dividir_por_cargo_e_materia,
    extrair_secao_objetos_avaliacao_detalhada,
    mapear_cargos,
    metadados_chunk,
    remover_assinatura_final,
)

# Reproduz, em miniatura, os padrões reais encontrados no edital
# Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.pdf (PF_25_ADM):
# matéria "solta" (CONHECIMENTOS BÁSICOS, sem cargo), cargo com matérias
# nomeadas à parte (inclusive com vírgula e parênteses no nome), e cargo de
# especialidade cujo conteúdo vem direto embaixo do "CARGO N:" sem matéria
# nomeada.
SECAO_TESTE = """OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)
14.1 HABILIDADES
CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR
LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos. 2 Tipologia textual.
ATUALIDADES (SOMENTE PARA A PROVA DISCURSIVA): 1 Tópicos relevantes e atuais.

CONHECIMENTOS ESPECÍFICOS PARA OS CARGOS DE NÍVEL SUPERIOR

CARGO 1: ADMINISTRADOR
ADMINISTRAÇÃO GERAL E PÚBLICA: 1 Evolução da administração. 1.1 Principais abordagens.
ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO: 1 O papel do Estado.

CARGO 7: MÉDICO CLÍNICO
1 Ética médica e bioética. 2 Doenças cardiovasculares. 2.1 Hipertensão arterial.
"""


class TestPadroes:
    def test_padrao_cargo_captura_numero_e_nome(self):
        matches = list(PADRAO_CARGO.finditer(SECAO_TESTE))
        assert [(m.group(1), m.group(2).strip()) for m in matches] == [
            ("1", "ADMINISTRADOR"),
            ("7", "MÉDICO CLÍNICO"),
        ]

    def test_padrao_materia_nao_casa_linha_de_cargo(self):
        # Regressão: sem o `(?!CARGO \d)`, "CARGO 1: ADMINISTRADOR" também
        # bateria como matéria (falso positivo).
        nomes = [m.group(1).strip() for m in PADRAO_MATERIA.finditer(SECAO_TESTE)]
        assert not any(n.startswith("CARGO ") for n in nomes)

    def test_padrao_materia_casa_nomes_com_digito_virgula_parenteses(self):
        # Regressão: a primeira versão do regex (só letras/espaço/hífen)
        # perdia silenciosamente esses três formatos reais, fazendo o
        # conteúdo deles ser engolido pelo chunk anterior.
        nomes = [m.group(1).strip() for m in PADRAO_MATERIA.finditer(SECAO_TESTE)]
        assert "ATUALIDADES (SOMENTE PARA A PROVA DISCURSIVA)" in nomes
        assert "ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO" in nomes

    def test_padrao_bloco_com_prefixo_numerico(self):
        from src.edital_parser import PADRAO_BLOCO

        texto = "\n15.2.2 CONHECIMENTOS BÁSICOS PARA O CARGO DE ANALISTA\n"
        m = PADRAO_BLOCO.search(texto)
        assert m is not None
        assert m.group(1) == "BÁSICOS"

    def test_padrao_cargo_com_espacos_multiplos(self):
        texto = "\nCARGO  2:  ANALISTA  AMBIENTAL\n"
        m = PADRAO_CARGO.search(texto)
        assert m is not None
        assert m.group(1) == "2"

    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            (
                "(APENAS PARA O CARGO 1: ANALISTA JUDICIÁRIO – ÁREA: ADMINISTRATIVA E PARA O CARGO 8: TÉCNICO JUDICIÁRIO – ÁREA: ADMINISTRATIVA)",
                True,
            ),
            ("(APENAS PARA O CARGO 3: ANALISTA... E PARA O CARGO 6: TÉCNICO...)", True),
            ("(SOMENTE PARA OS CARGOS DE 1 A 14)", True),
            ("(apenas para os cargos 1 e 2)", True),
            ("(HABILIDADES E CONHECIMENTOS)", False),
            ("(SOMENTE PARA A PROVA DISCURSIVA)", False),
        ],
    )
    def test_padrao_restricao_cargo(self, texto, esperado):
        assert bool(PADRAO_RESTRICAO_CARGO.search(texto)) == esperado


class TestDividirPorCargoEMateria:
    def test_materia_sem_cargo_associado(self):
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        lingua_portuguesa = next(c for c in chunks if c.materia == "LÍNGUA PORTUGUESA")
        assert lingua_portuguesa.cargo is None
        assert "Compreensão e interpretação" in lingua_portuguesa.texto

    def test_cargo_com_materias_nomeadas_a_parte(self):
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        do_cargo_1 = [c for c in chunks if c.cargo == "CARGO 1: ADMINISTRADOR"]
        assert {c.materia for c in do_cargo_1} == {
            "ADMINISTRAÇÃO GERAL E PÚBLICA",
            "ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO",
        }

    def test_cargo_de_especialidade_sem_materia_nomeada_vira_o_proprio_chunk(self):
        # Regressão do bug real: "CARGO 7: MÉDICO CLÍNICO" não tem matéria
        # nomeada à parte — o conteúdo vem direto embaixo do cabeçalho de
        # cargo. Antes da correção, esse conteúdo (e o de outros ~14
        # cargos de especialidade) era engolido silenciosamente pelo chunk
        # anterior no texto.
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        medico = next(c for c in chunks if c.cargo == "CARGO 7: MÉDICO CLÍNICO")
        assert medico.materia == "MÉDICO CLÍNICO"
        assert "Doenças cardiovasculares" in medico.texto

    def test_nenhum_chunk_gigante_por_boundary_perdida(self):
        # Regressão direta do bug: nenhum chunk deve conter texto de mais
        # de 1 cargo/matéria — sintoma original era um chunk de 41850
        # chars (~55% da seção) engolindo ~14 cargos inteiros.
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        assert all(len(c.texto) < 300 for c in chunks)

    def test_retorna_lista_de_chunk_taxonomia(self):
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        assert chunks
        assert all(isinstance(c, ChunkTaxonomia) for c in chunks)

    def test_secao_sem_cabecalhos_retorna_lista_vazia(self):
        assert (
            dividir_por_cargo_e_materia("texto sem nenhum cabeçalho reconhecível") == []
        )

    def test_materia_origem_nos_tres_ramos_e_metadados(self):
        assert "materia_origem" in CAMPOS_CLASSIFICACAO_CHUNK
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        lp = next(c for c in chunks if c.materia == "LÍNGUA PORTUGUESA")
        assert lp.materia_origem == "cabecalho"
        assert metadados_chunk(lp)["materia_origem"] == "cabecalho"

        medico = next(c for c in chunks if c.cargo == "CARGO 7: MÉDICO CLÍNICO")
        assert medico.materia_origem == "cargo"
        assert metadados_chunk(medico)["materia_origem"] == "cargo"

    def test_materia_origem_prefixo_antes_do_item_1(self):
        texto = (
            "OBJETOS DE AVALIAÇÃO\n"
            "CONHECIMENTOS ESPECÍFICOS\n"
            "CARGO 2: TÉCNICO LEGISLATIVO – ATRIBUIÇÃO: ASSISTENTE\n"
            "NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO 1 Constituição Federal. 2 Poder Legislativo.\n"
        )
        chunks = dividir_por_cargo_e_materia(texto)
        assert len(chunks) == 1
        assert (
            chunks[0].materia
            == "NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO"
        )
        assert chunks[0].materia_origem == "prefixo"
        assert chunks[0].texto.startswith("1 Constituição Federal.")
        assert metadados_chunk(chunks[0])["materia_origem"] == "prefixo"

    def test_chunks_carregam_offsets_dentro_da_secao(self):
        # Offsets necessários pra trilha de auditoria (revisar_taxonomia_piloto.py):
        # devem apontar de volta pro texto exato que gerou cada chunk.
        chunks = dividir_por_cargo_e_materia(SECAO_TESTE)
        for chunk in chunks:
            assert (
                SECAO_TESTE[chunk.offset_inicio : chunk.offset_fim].strip()
                == chunk.texto
            )

    def test_cargo_multilinha_sem_itens_absorve_titulo_e_nao_gera_chunk_falso(self):
        texto = (
            "OBJETOS DE AVALIAÇÃO\n"
            "CONHECIMENTOS ESPECÍFICOS\n"
            "CARGO  2:  ANALISTA  AMBIENTAL  –  TEMA  1:  PROTEÇÃO\n"
            "QUALIDADE AMBIENTAL\n"
            "LEGISLAÇÃO AMBIENTAL: 1 Leis e normas.\n"
        )
        chunks = dividir_por_cargo_e_materia(texto)
        assert len(chunks) == 1
        assert chunks[0].materia == "LEGISLAÇÃO AMBIENTAL"
        assert "ANALISTA AMBIENTAL" in chunks[0].cargo
        assert "QUALIDADE AMBIENTAL" in chunks[0].cargo


def _criar_pdf_teste(tmp_path, paginas_texto: list[str]):
    doc = pymupdf.open()
    for texto in paginas_texto:
        page = doc.new_page()
        page.insert_text((72, 72), texto)
    pdf_path = tmp_path / "edital_teste.pdf"
    doc.save(pdf_path)
    doc.close()
    return pdf_path


class TestExtrairSecaoObjetosAvaliacaoDetalhada:
    def test_extrair_secao_com_espacos_nao_separaveis(self, tmp_path):
        texto_com_nbsp = "15\xa0DOS\xa0OBJETOS\xa0DE\xa0AVALIAÇÃO\xa0(HABILIDADES)\nConteudo da secao."
        pdf_path = _criar_pdf_teste(tmp_path, [texto_com_nbsp])
        secao = extrair_secao_objetos_avaliacao_detalhada(pdf_path)
        assert secao is not None
        assert "OBJETOS DE AVALIAÇÃO" in secao.texto

    def test_marcador_ausente_retorna_none(self, tmp_path):
        pdf_path = _criar_pdf_teste(tmp_path, ["Edital sem a seção procurada."])
        assert extrair_secao_objetos_avaliacao_detalhada(pdf_path) is None

    def test_metadados_de_corte_sem_marcador_fim(self, tmp_path):
        # Sem "ANEXO I": corta até o fim do PDF, marcador_fim_encontrado=False.
        pdf_path = _criar_pdf_teste(
            tmp_path,
            [
                "Página de rosto, irrelevante.",
                "OBJETOS DE AVALIAÇÃO\nConteudo da secao.",
            ],
        )
        secao = extrair_secao_objetos_avaliacao_detalhada(pdf_path)
        assert secao is not None
        assert secao.paginas_pdf_total == 2
        assert secao.marcador_fim_encontrado is False
        assert secao.texto.startswith("OBJETOS DE AVALIAÇÃO")
        assert secao.offset_fim == secao.chars_pdf_total

    def test_metadados_de_corte_com_marcador_fim(self, tmp_path):
        pdf_path = _criar_pdf_teste(
            tmp_path,
            [
                "OBJETOS DE AVALIAÇÃO\nConteudo da secao.\nANEXO I\nTexto de anexo, fora da secao."
            ],
        )
        secao = extrair_secao_objetos_avaliacao_detalhada(pdf_path)
        assert secao is not None
        assert secao.marcador_fim_encontrado is True
        assert "ANEXO I" not in secao.texto
        assert "Texto de anexo" not in secao.texto


NOTA_RETIFICACAO = (
    "(Retificado por meio do Edital nº 5 – PF – Administrativo, de 13 de junho de 2025, "
    "divulgado no endereço eletrônico http://www.cebraspe.org.br/concursos/pf_25_adm)"
)

# Regressão do achado ao vivo 2026-09-20 (chunk 30, PSICÓLOGO ORGANIZACIONAL,
# ver ADR-016): nota de retificação embutida no meio do texto
# programático — ruído administrativo, não conteúdo de estudo.
SECAO_COM_RETIFICACAO = f"""OBJETOS DE AVALIAÇÃO
CARGO 12: PSICÓLOGO ORGANIZACIONAL
1 Psicologia organizacional. 2 Clima e cultura organizacional, assédio sexual e discriminação.
{NOTA_RETIFICACAO}

CARGO 13: TÉCNICO EM ASSUNTOS EDUCACIONAIS
1 Pedagogia.
"""


class TestLimparRuidoEdital:
    def test_remove_nota_de_retificacao(self):
        texto = f"1 Psicologia organizacional.\n{NOTA_RETIFICACAO}"
        limpo = _limpar_ruido_edital(texto)
        assert "Retificado" not in limpo
        assert limpo == "1 Psicologia organizacional."

    def test_texto_sem_ruido_fica_intacto(self):
        texto = "1 Compreensão e interpretação de textos. 2 Tipologia textual."
        assert _limpar_ruido_edital(texto) == texto


class TestRemoverAssinaturaFinal:
    """Os 5 editais de 2025 do piloto terminam com assinatura colada no último item."""

    @pytest.mark.parametrize(
        "assinatura",
        [
            " \n \nRODRIGO AGOSTINHO \nPresidente do Ibama",
            " \n\n \n \nTen Brig Ar Francisco Joseli Parente Camelo \nMinistro-Presidente",
            (
                " \n \nMAURO LIMEIRA MENA BARRETO \nPresidente da Comissão Organizadora de Governança  \n"
                "do Concurso Público da Câmara dos Deputados"
            ),
            (
                " \n \nANA CRISTINA SIQUEIRA NOVAES \nDiretora-Geral do Instituto Serzedello Corrêa \n"
                "Presidente do Concurso"
            ),
        ],
    )
    def test_remove_assinatura_em_linhas_proprias(self, assinatura):
        texto = (
            "12 Anatomia. 13 Proteção da Fauna. 13.1 Lei nº 5.197/1967." + assinatura
        )
        assert (
            remover_assinatura_final(texto)
            == "12 Anatomia. 13 Proteção da Fauna. 13.1 Lei nº 5.197/1967."
        )

    def test_remove_nome_colado_na_mesma_linha_do_ultimo_item(self):
        # Formato real do PF_25_ADM.
        texto = (
            "5 Lei nº 12.830/2013: dispõe sobre a \ninvestigação criminal conduzida pelo delegado de polícia. "
            "GUILHERME MONSEFF DE BIAGI \nDelegado de Polícia Federal \nDiretor de Gestão de Pessoas"
        )
        assert remover_assinatura_final(texto) == (
            "5 Lei nº 12.830/2013: dispõe sobre a \ninvestigação criminal conduzida pelo delegado de polícia."
        )

    def test_presidente_no_meio_do_conteudo_nao_e_removido(self):
        texto = (
            "7.3 Poder Executivo. 7.3.1 \nPresidente da República. 7.3.1.1 Atribuições."
        )
        assert remover_assinatura_final(texto) == texto

    def test_linha_de_cargo_sem_nome_antes_nao_e_removida(self):
        texto = "7 Poder Executivo. 7.3.1 \nPresidente da República"
        assert remover_assinatura_final(texto) == texto

    def test_limpar_ruido_tambem_remove_assinatura(self):
        assert (
            _limpar_ruido_edital(
                "1 Epidemiologia.\nRODRIGO AGOSTINHO\nPresidente do Ibama"
            )
            == "1 Epidemiologia."
        )


class TestChunkingRemoveRuido:
    def test_nota_de_retificacao_nao_aparece_no_texto_do_chunk(self):
        chunks = dividir_por_cargo_e_materia(SECAO_COM_RETIFICACAO)
        psicologo = next(c for c in chunks if c.materia == "PSICÓLOGO ORGANIZACIONAL")
        assert "Retificado" not in psicologo.texto
        assert psicologo.texto == (
            "1 Psicologia organizacional. 2 Clima e cultura organizacional, "
            "assédio sexual e discriminação."
        )

    def test_offsets_continuam_apontando_para_o_trecho_bruto_com_ruido(self):
        # offset_inicio/offset_fim descrevem o span bruto consumido da seção
        # (incluindo o ruído removido) — só `texto` é limpo. A auditoria usa
        # os offsets pra apontar de volta pro PDF, não pra reconstruir texto.
        chunks = dividir_por_cargo_e_materia(SECAO_COM_RETIFICACAO)
        psicologo = next(c for c in chunks if c.materia == "PSICÓLOGO ORGANIZACIONAL")
        bruto = SECAO_COM_RETIFICACAO[psicologo.offset_inicio : psicologo.offset_fim]
        assert "Retificado" in bruto


# Estrutura dos 4 blocos do PF_25_ADM (ADR-020): as matérias básicas se
# repetem com o mesmo nome em superior e médio, com conteúdo diferente.
SECAO_BLOCOS = """OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)
14.2 CONHECIMENTOS
CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR
(Retificado por meio do Edital nº 4 – PF – Administrativo, de 4 de junho de 2025)
LÍNGUA PORTUGUESA: 1 Conteúdo superior.
NOÇÕES DE DIREITO ADMINISTRATIVO: 1 Organização administrativa.

CONHECIMENTOS BÁSICOS PARA O CARGO DE NÍVEL MÉDIO
LÍNGUA PORTUGUESA: 1 Conteúdo médio.
ATUALIDADES (SOMENTE PARA A PROVA DISCURSIVA): 1 Tópicos atuais.

CONHECIMENTOS ESPECÍFICOS PARA OS CARGOS DE NÍVEL SUPERIOR
CARGO 1: ADMINISTRADOR
GESTÃO DE PESSOAS: 1 Conceitos.
CARGO 7: MÉDICO CLÍNICO
1 Ética médica.

CONHECIMENTOS ESPECÍFICOS PARA O CARGO DE NÍVEL MÉDIO
CARGO 15: AGENTE ADMINISTRATIVO
NOÇÕES DE GOVERNANÇA PÚBLICA: 1 Teorias da administração.
"""


class TestBlocosDeConhecimento:
    def _classificacoes(self, secao):
        return [
            (c.materia_normalizada, c.tipo_conhecimento, c.nivel, c.cargo_numero)
            for c in dividir_por_cargo_e_materia(secao)
        ]

    def test_cada_chunk_herda_tipo_e_nivel_do_bloco(self):
        assert self._classificacoes(SECAO_BLOCOS) == [
            ("LÍNGUA PORTUGUESA", "basico", "superior", None),
            ("NOÇÕES DE DIREITO ADMINISTRATIVO", "basico", "superior", None),
            ("LÍNGUA PORTUGUESA", "basico", "medio", None),
            ("ATUALIDADES", "basico", "medio", None),
            ("GESTÃO DE PESSOAS", "especifico", "superior", 1),
            ("MÉDICO CLÍNICO", "especifico", "superior", 7),
            ("NOÇÕES DE GOVERNANÇA PÚBLICA", "especifico", "medio", 15),
        ]

    def test_mesma_materia_em_niveis_diferentes_fica_distinguivel(self):
        # Regressão do problema original: os dois chunks de LÍNGUA
        # PORTUGUESA saíam idênticos (cargo=None, mesmo nome).
        portugues = [
            c
            for c in dividir_por_cargo_e_materia(SECAO_BLOCOS)
            if c.materia == "LÍNGUA PORTUGUESA"
        ]
        assert {(c.nivel, c.texto) for c in portugues} == {
            ("superior", "1 Conteúdo superior."),
            ("medio", "1 Conteúdo médio."),
        }

    def test_cabecalho_de_bloco_nao_gruda_na_cauda_do_chunk_anterior(self):
        for chunk in dividir_por_cargo_e_materia(SECAO_BLOCOS):
            assert "CONHECIMENTOS" not in chunk.texto

    def test_materia_somente_discursiva_vira_flag_e_sai_do_nome_normalizado(self):
        atualidades = next(
            c for c in dividir_por_cargo_e_materia(SECAO_BLOCOS) if c.apenas_discursiva
        )
        assert atualidades.materia == "ATUALIDADES (SOMENTE PARA A PROVA DISCURSIVA)"
        assert atualidades.materia_normalizada == "ATUALIDADES"
        assert metadados_chunk(atualidades) == {
            "tipo_conhecimento": "basico",
            "nivel": "medio",
            "cargo_numero": None,
            "materia_normalizada": "ATUALIDADES",
            "apenas_discursiva": True,
            "cargos_restritos": None,
            "materia_origem": "cabecalho",
        }

    def test_chunk_com_restricao_de_cargo_extrai_cargos_restritos_e_limpa_materia(self):
        chunk = ChunkTaxonomia(
            cargo=None,
            materia="DIREITO PENAL MILITAR (APENAS PARA O CARGO 1: ANALISTA JUDICIÁRIO – ÁREA: ADMINISTRATIVA E PARA O CARGO 8: TÉCNICO JUDICIÁRIO – ÁREA: ADMINISTRATIVA)",
            texto="1 Crime militar.",
            tipo_conhecimento="especifico",
            nivel="superior",
        )
        assert chunk.cargos_restritos == [1, 8]
        assert chunk.materia_normalizada == "DIREITO PENAL MILITAR"
        assert chunk.apenas_discursiva is False
        assert metadados_chunk(chunk)["cargos_restritos"] == [1, 8]

    def test_chunk_com_restricao_multilinha_stm(self):
        materia_stm = (
            "LÍNGUA INGLESA (APENAS PARA O CARGO 3: ANALISTA JUDICIÁRIO – ÁREA: APOIO ESPECIALIZADO – \n"
            "ESPECIALIDADE: ANÁLISE DE SISTEMAS E PARA O CARGO 6: ANALISTA JUDICIÁRIO – ÁREA: APOIO \n"
            "ESPECIALIZADO – ESPECIALIDADE: SUPORTE EM TECNOLOGIA DA INFORMAÇÃO)"
        )
        chunk = ChunkTaxonomia(
            cargo=None,
            materia=materia_stm,
            texto="1 Compreensão de texto em língua inglesa.",
        )
        assert chunk.cargos_restritos == [3, 6]
        assert chunk.materia_normalizada == "LÍNGUA INGLESA"

    def test_chunk_sem_restricao_tem_cargos_restritos_none(self):
        chunk = ChunkTaxonomia(
            cargo=None, materia="DIREITO CONSTITUCIONAL", texto="1 CF/88."
        )
        assert chunk.cargos_restritos is None
        assert chunk.materia_normalizada == "DIREITO CONSTITUCIONAL"

    def test_colapso_espacos_multiplos_em_materia_normalizada(self):
        chunk = ChunkTaxonomia(
            cargo=None, materia="LÍNGUA   PORTUGUESA", texto="1 Texto."
        )
        assert chunk.cargos_restritos is None
        assert chunk.materia_normalizada == "LÍNGUA PORTUGUESA"

    def test_restricao_com_parentese_interno_sai_inteira_do_nome(self):
        chunk = ChunkTaxonomia(
            cargo=None,
            materia="LÍNGUA INGLESA (APENAS PARA O CARGO 3: ANALISTA (TI) E PARA O CARGO 6: TÉCNICO)",
            texto="1 Texto.",
        )
        assert chunk.cargos_restritos == [3, 6]
        assert chunk.materia_normalizada == "LÍNGUA INGLESA"

    def test_varias_restricoes_somam_os_cargos(self):
        chunk = ChunkTaxonomia(
            cargo=None,
            materia="X (APENAS PARA O CARGO 1) (APENAS PARA O CARGO 2)",
            texto="1 Texto.",
        )
        assert chunk.cargos_restritos == [1, 2]
        assert chunk.materia_normalizada == "X"

    @pytest.mark.parametrize(
        "materia",
        [
            "ÉTICA (SOMENTE PARA OS CARGOS DE NÍVEL SUPERIOR)",
            "ÉTICA (APENAS PARA O CARGO DE ANALISTA)",
        ],
    )
    def test_restricao_sem_numero_de_cargo_fica_no_nome(self, materia):
        # Tirar do nome sem guardar os cargos faria a matéria valer para todos.
        chunk = ChunkTaxonomia(cargo=None, materia=materia, texto="1 Texto.")
        assert chunk.cargos_restritos is None
        assert chunk.materia_normalizada == materia

    def test_dividir_avisa_restricao_sem_numero(self, caplog):
        secao = (
            "\nCONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            "ÉTICA (SOMENTE PARA OS CARGOS DE NÍVEL SUPERIOR): 1 Texto.\n"
        )
        with caplog.at_level("WARNING"):
            dividir_por_cargo_e_materia(secao)
        assert "[RESTRICAO_SEM_CARGO]" in caplog.text

    def test_dividir_loga_cargos_restritos(self, caplog):
        secao = (
            "\nCONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            "LÍNGUA INGLESA (APENAS PARA OS CARGOS 3 E 6): 1 Texto.\n"
        )
        with caplog.at_level("INFO"):
            dividir_por_cargo_e_materia(secao)
        assert "[RESTRICAO_CARGO]" in caplog.text
        assert "'LÍNGUA INGLESA' → só cargos [3, 6]" in caplog.text

    def test_campos_classificacao_chunk_inclui_cargos_restritos(self):
        assert "cargos_restritos" in CAMPOS_CLASSIFICACAO_CHUNK

    def test_dividir_por_cargo_e_materia_com_restricao_e_espacos_duplos(self):
        secao = (
            "\nCONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            "LÍNGUA  PORTUGUESA: 1 Texto.\n"
            "DIREITO PENAL MILITAR (APENAS PARA O CARGO 1: ANALISTA E PARA O CARGO 8: TÉCNICO): 1 Crime.\n"
        )
        chunks = dividir_por_cargo_e_materia(secao)
        assert len(chunks) == 2
        assert chunks[0].materia == "LÍNGUA PORTUGUESA"
        assert chunks[0].materia_normalizada == "LÍNGUA PORTUGUESA"
        assert chunks[0].cargos_restritos is None
        assert (
            chunks[1].materia
            == "DIREITO PENAL MILITAR (APENAS PARA O CARGO 1: ANALISTA E PARA O CARGO 8: TÉCNICO)"
        )
        assert chunks[1].materia_normalizada == "DIREITO PENAL MILITAR"
        assert chunks[1].cargos_restritos == [1, 8]

    def test_novo_bloco_zera_o_cargo_corrente(self):
        secao = (
            "\nCONHECIMENTOS ESPECÍFICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            "CARGO 1: ADMINISTRADOR\nGESTÃO DE PESSOAS: 1 Conceitos.\n"
            "CONHECIMENTOS BÁSICOS PARA O CARGO DE NÍVEL MÉDIO\n"
            "LÍNGUA PORTUGUESA: 1 Texto.\n"
        )
        portugues = next(
            c
            for c in dividir_por_cargo_e_materia(secao)
            if c.materia == "LÍNGUA PORTUGUESA"
        )
        assert (
            portugues.cargo,
            portugues.cargo_numero,
            portugues.tipo_conhecimento,
        ) == (None, None, "basico")

    def test_bloco_sem_nivel_unico_deixa_nivel_none(self):
        secao = (
            "\nCONHECIMENTOS BÁSICOS PARA TODOS OS CARGOS\nLÍNGUA PORTUGUESA: 1 Texto.\n"
            "\nCONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR E DE NÍVEL MÉDIO\nRACIOCÍNIO LÓGICO: 1 Lógica.\n"
        )
        assert self._classificacoes(secao) == [
            ("LÍNGUA PORTUGUESA", "basico", None, None),
            ("RACIOCÍNIO LÓGICO", "basico", None, None),
        ]

    def test_conhecimentos_especificos_com_dois_pontos_continua_sendo_materia(self):
        secao = "\nCONHECIMENTOS ESPECÍFICOS: 1 Conteúdo na mesma linha.\n"
        chunks = dividir_por_cargo_e_materia(secao)
        assert [(c.materia, c.tipo_conhecimento) for c in chunks] == [
            ("CONHECIMENTOS ESPECÍFICOS", None)
        ]

    def test_mapear_cargos_herda_nivel_do_bloco_especifico(self):
        assert mapear_cargos(dividir_por_cargo_e_materia(SECAO_BLOCOS)) == [
            {"numero": 1, "nome": "ADMINISTRADOR", "nivel": "superior"},
            {"numero": 7, "nome": "MÉDICO CLÍNICO", "nivel": "superior"},
            {"numero": 15, "nome": "AGENTE ADMINISTRATIVO", "nivel": "medio"},
        ]

    def test_cargo_padrao_e_nivel_padrao_em_bloco_sem_declaracao_explicita(self):
        secao = (
            "\nCONHECIMENTOS BÁSICOS\nLÍNGUA PORTUGUESA: 1 Texto.\n"
            "\nCONHECIMENTOS ESPECÍFICOS\nDIREITO ADMINISTRATIVO: 1 Atos.\n"
        )
        chunks = dividir_por_cargo_e_materia(
            secao,
            cargo_padrao="TÉCNICO FEDERAL DE CONTROLE EXTERNO",
            nivel_padrao="medio",
        )
        assert len(chunks) == 2
        assert chunks[0].materia == "LÍNGUA PORTUGUESA"
        assert chunks[0].cargo is None
        assert chunks[0].tipo_conhecimento == "basico"
        assert chunks[0].nivel == "medio"

        assert chunks[1].materia == "DIREITO ADMINISTRATIVO"
        assert chunks[1].cargo == "CARGO 1: TÉCNICO FEDERAL DE CONTROLE EXTERNO"
        assert chunks[1].tipo_conhecimento == "especifico"
        assert chunks[1].nivel == "medio"

    def test_mapear_cargos_com_cargo_padrao_e_nivel_padrao(self):
        chunks = [
            ChunkTaxonomia(
                cargo=None,
                materia="LÍNGUA PORTUGUESA",
                texto="...",
                offset_inicio=0,
                offset_fim=10,
                tipo_conhecimento="basico",
                nivel="medio",
            )
        ]
        cargos = mapear_cargos(
            chunks,
            cargo_padrao="TÉCNICO FEDERAL DE CONTROLE EXTERNO",
            nivel_padrao="medio",
        )
        assert cargos == [
            {
                "numero": 1,
                "nome": "TÉCNICO FEDERAL DE CONTROLE EXTERNO",
                "nivel": "medio",
            }
        ]

    def test_materia_multilinha_com_conectivo_reconhecida(self):
        texto = (
            "\nCONHECIMENTOS ESPECÍFICOS\n"
            "CARGO 1: ANALISTA LEGISLATIVO – ATRIBUIÇÃO: GESTÃO\n"
            "REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM DO CONGRESSO NACIONAL E\n"
            "CÓDIGO DE ÉTICA: 1 Regimento Interno.\n"
        )
        chunks = dividir_por_cargo_e_materia(texto)
        assert len(chunks) == 1
        assert chunks[0].cargo == "CARGO 1: ANALISTA LEGISLATIVO – ATRIBUIÇÃO: GESTÃO"
        assert (
            chunks[0].materia
            == "REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM DO CONGRESSO NACIONAL E CÓDIGO DE ÉTICA"
        )
        assert chunks[0].texto == "1 Regimento Interno."

    def test_materia_sem_dois_pontos_sob_cargo_reconhecida_antes_do_item_1(self):
        texto = (
            "\nCONHECIMENTOS ESPECÍFICOS\n"
            "CARGO 2: TÉCNICO LEGISLATIVO – ATRIBUIÇÃO: ASSISTENTE\n"
            "NOÇÕES DE DIREITO CONSTITUCIONAL E REGIMENTO INTERNO 1\n"
            "Constituição Federal de 1988.\n"
        )
        chunks = dividir_por_cargo_e_materia(texto)
        assert len(chunks) == 1
        assert (
            chunks[0].cargo == "CARGO 2: TÉCNICO LEGISLATIVO – ATRIBUIÇÃO: ASSISTENTE"
        )
        assert (
            chunks[0].materia == "NOÇÕES DE DIREITO CONSTITUCIONAL E REGIMENTO INTERNO"
        )
        assert chunks[0].texto.startswith("1\nConstituição Federal")


# Trecho real do SEFA_PR_25 (página de Objetos de Avaliação): matéria composta
# guarda-chuva seguida de sub-matérias numeradas em romano, algumas coladas no
# meio da linha de um item anterior.
SECAO_SUBMATERIAS_ROMANAS = """
CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR
LÍNGUA PORTUGUESA: 1 Compreensão de textos.
DIREITO CONSTITUCIONAL, DIREITO ADMINISTRATIVO E ESTATUTO DA CRIANÇA E DO ADOLESCENTE: I 
DIREITO CONSTITUCIONAL: 1 Constituição. 1.1 Conceito, objeto, elementos e classificações. 17 
Direitos das comunidades remanescentes de quilombos. II DIREITO ADMINISTRATIVO: 1 Conceito e fontes 
do direito administrativo. 17 Improbidade administrativa. III ESTATUTO DA CRIANÇA E DO ADOLESCENTE: 
1 Lei nº 8.069/1990.  
DIREITO TRIBUTÁRIO: 1 Sistema Tributário Nacional.
"""

SECAO_SUBMATERIAS_ECONOMIA = """
CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR
ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA: 1 Orçamento público.
NOÇÕES DE ECONOMIA E NOÇÕES DE FINANÇAS PÚBLICAS: I NOÇÕES DE ECONOMIA: 1 Economia do setor 
público. 2.11 Taxas de juros. II NOÇÕES DE 
FINANÇAS PÚBLICAS: 1 Finanças públicas: receitas e despesas. 2 Orçamento.
"""


class TestSubmateriasRomanas:
    def test_guarda_chuva_e_romanos_viram_um_chunk_por_submateria(self):
        chunks = dividir_por_cargo_e_materia(SECAO_SUBMATERIAS_ROMANAS)
        assert [c.materia for c in chunks] == [
            "LÍNGUA PORTUGUESA",
            "DIREITO CONSTITUCIONAL",
            "DIREITO ADMINISTRATIVO",
            "ESTATUTO DA CRIANÇA E DO ADOLESCENTE",
            "DIREITO TRIBUTÁRIO",
        ]
        assert all(
            c.tipo_conhecimento == "basico" and c.nivel == "superior" for c in chunks
        )

    def test_romano_e_guarda_chuva_nao_vazam_para_o_texto(self):
        chunks = dividir_por_cargo_e_materia(SECAO_SUBMATERIAS_ROMANAS)
        _, constitucional, administrativo, eca, _ = chunks
        assert constitucional.texto.startswith("1 Constituição.")
        assert "DIREITO ADMINISTRATIVO" not in constitucional.texto
        assert administrativo.texto.startswith("1 Conceito e fontes")
        assert "ESTATUTO" not in administrativo.texto
        assert eca.texto == "1 Lei nº 8.069/1990."
        assert all(c.texto.strip() not in {"I", "II", "III"} for c in chunks)
        assert not any(re.search(r"\b(I|II|III)\b\s+[A-ZÀ-Ú]", c.texto) for c in chunks)

    def test_submateria_com_nome_quebrado_em_duas_linhas(self):
        chunks = dividir_por_cargo_e_materia(SECAO_SUBMATERIAS_ECONOMIA)
        assert [c.materia for c in chunks] == [
            "ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA",
            "NOÇÕES DE ECONOMIA",
            "NOÇÕES DE FINANÇAS PÚBLICAS",
        ]
        assert chunks[1].texto.startswith("1 Economia do setor")
        assert chunks[2].texto.startswith("1 Finanças públicas: receitas")
        assert not any("NOÇÕES DE" in c.texto for c in chunks)

    def test_guarda_chuva_nao_vaza_para_o_fim_do_chunk_anterior(self):
        chunks = dividir_por_cargo_e_materia(SECAO_SUBMATERIAS_ROMANAS)
        assert chunks[0].materia == "LÍNGUA PORTUGUESA"
        assert chunks[0].texto == "1 Compreensão de textos."
        assert "DIREITO CONSTITUCIONAL, DIREITO" not in chunks[0].texto
        assert "ESTATUTO" not in chunks[0].texto

    def test_guarda_chuva_nao_vaza_quando_o_anterior_e_outra_materia(self):
        chunks = dividir_por_cargo_e_materia(SECAO_SUBMATERIAS_ECONOMIA)
        anterior = chunks[0]
        assert anterior.materia == "ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA"
        assert anterior.texto == "1 Orçamento público."
        assert "NOÇÕES DE ECONOMIA E" not in anterior.texto

    def test_romano_no_corpo_de_item_nao_vira_materia(self):
        texto = (
            "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            "LEGISLAÇÃO: 1 Lei nº 8.112/1990, conforme o inciso II do art. 5º. "
            "2 Estatuto, item V da lista. 3 Regime disciplinar.\n"
        )
        chunks = dividir_por_cargo_e_materia(texto)
        assert [c.materia for c in chunks] == ["LEGISLAÇÃO"]
        assert "inciso II do art. 5º" in chunks[0].texto


class TestNivelPelaEscolaridade:
    # Trecho real do BANRISUL_25 (2.2 ESCOLARIDADE EXIGIDA): não há bloco de
    # REQUISITOS, então o nível sai da escolaridade exigida.
    PRELIMINARES_BANRISUL = (
        "2.1 As atribuições do cargo estão descritas no Anexo I.\n"
        "2.2 ESCOLARIDADE EXIGIDA PARA O CARGO: diploma, devidamente registrado, de "
        "conclusão de curso \nde graduação na área de Tecnologia da Informação, reconhecido "
        "e concluído em instituição de nível \nsuperior credenciada pelo MEC, acrescido de "
        "curso de pós-graduação.\n"
        "2.3 As provas poderão ser aplicadas.\n"
    )

    def test_escolaridade_de_graduacao_define_superior(self):
        assert detectar_nivel_no_texto(self.PRELIMINARES_BANRISUL) == "superior"

    def test_escolaridade_de_nivel_medio(self):
        texto = "2.2 ESCOLARIDADE EXIGIDA PARA O CARGO: certificado de conclusão do ensino médio.\n"
        assert detectar_nivel_no_texto(texto) == "medio"

    def test_requisitos_continuam_com_prioridade(self):
        texto = (
            "REQUISITOS: ensino médio completo.\n"
            "Ser brasileiro nato.\n"
            "Ter 18 anos completos.\n"
            "Ter aptidão física.\n"
            "2.2 ESCOLARIDADE EXIGIDA PARA O CARGO: graduação em direito.\n"
        )
        assert detectar_nivel_no_texto(texto) == "medio"

    def test_escolaridade_mista_nao_define_nivel(self):
        texto = (
            "2.2 ESCOLARIDADE EXIGIDA PARA O CARGO: graduação em direito.\n"
            "2.3 ESCOLARIDADE EXIGIDA PARA O CARGO: ensino médio completo.\n"
        )
        assert detectar_nivel_no_texto(texto) is None

    def test_sem_escolaridade_nem_requisitos_fica_none(self):
        assert detectar_nivel_no_texto("Edital sem qualquer requisito.") is None


PDF_PILOTO = (
    Path(__file__).resolve().parent.parent
    / "data/2025/CEBRASPE/PF/Editais/Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.pdf"
)
PDF_TCU = (
    Path(__file__).resolve().parent.parent
    / "data/2025/CEBRASPE/TCU/Editais/Ed_1_TCU_25_TEFC_Abertura.pdf"
)


@pytest.mark.skipif(
    not PDF_PILOTO.exists(), reason="PDF piloto não baixado (data/ é gitignored)"
)
def test_edital_piloto_real_classifica_os_4_blocos():
    chunks = dividir_por_cargo_e_materia(
        extrair_secao_objetos_avaliacao_detalhada(PDF_PILOTO).texto
    )
    assert len(chunks) == 39
    faixas = {
        range(6): ("basico", "superior"),
        range(6, 11): ("basico", "medio"),
        range(11, 33): ("especifico", "superior"),
        range(33, 39): ("especifico", "medio"),
    }
    for faixa, esperado in faixas.items():
        assert {(chunks[i].tipo_conhecimento, chunks[i].nivel) for i in faixa} == {
            esperado
        }
    assert [c.materia_normalizada for c in chunks if c.apenas_discursiva] == [
        "ATUALIDADES"
    ]
    assert {c["nivel"] for c in mapear_cargos(chunks) if c["numero"] <= 14} == {
        "superior"
    }
    assert mapear_cargos(chunks)[-1] == {
        "numero": 15,
        "nome": "AGENTE ADMINISTRATIVO",
        "nivel": "medio",
    }


@pytest.mark.skipif(
    not PDF_TCU.exists(), reason="PDF TCU não baixado (data/ é gitignored)"
)
def test_edital_tcu_real_cargo_unico_e_nivel_medio():
    info = detectar_cargo_e_nivel_edital(PDF_TCU)
    assert info["cargo"] == "TÉCNICO FEDERAL DE CONTROLE EXTERNO"
    assert info["nivel"] == "medio"

    secao = extrair_secao_objetos_avaliacao_detalhada(PDF_TCU)
    assert secao.cargo_detectado == "TÉCNICO FEDERAL DE CONTROLE EXTERNO"
    assert secao.nivel_detectado == "medio"

    chunks = dividir_por_cargo_e_materia(
        secao.texto,
        cargo_padrao=secao.cargo_detectado,
        nivel_padrao=secao.nivel_detectado,
    )
    assert len(chunks) == 10
    assert all(c.nivel == "medio" for c in chunks)
    assert all(chunks[i].cargo is None for i in range(5))
    assert all(chunks[i].tipo_conhecimento == "basico" for i in range(5))
    assert all(
        chunks[i].cargo == "CARGO 1: TÉCNICO FEDERAL DE CONTROLE EXTERNO"
        for i in range(5, 10)
    )
    assert all(chunks[i].tipo_conhecimento == "especifico" for i in range(5, 10))

    cargos = mapear_cargos(
        chunks, cargo_padrao=secao.cargo_detectado, nivel_padrao=secao.nivel_detectado
    )
    assert cargos == [
        {"numero": 1, "nome": "TÉCNICO FEDERAL DE CONTROLE EXTERNO", "nivel": "medio"}
    ]


# Reproduz, em miniatura, o BANRISUL_25: um cargo único com 4 áreas, cada uma
# com prova específica própria. "ÁREA N: <nome>" em linha inteira vira cargo;
# a área nunca vira matéria, e o ":" dentro do nome da área fica no nome.
SECAO_AREAS = """OBJETOS DE AVALIAÇÃO
2.1.1 CONHECIMENTOS BÁSICOS
LÍNGUA PORTUGUESA: 1 Compreensão de texto.
2.1.2 CONHECIMENTOS ESPECÍFICOS
ÁREA 1: ADMINISTRAÇÃO DE BANCO DE DADOS
CONCEITOS BÁSICOS: 1 Modelagem.
ÁREA 2: DESENVOLVIMENTO DE SOFTWARE
ENGENHARIA DE SOFTWARE: 1 Requisitos.
ÁREA 3: TECNOLOGIA: SEGURANÇA, INFRA E OPERAÇÃO
SEGURANÇA DA INFORMAÇÃO: 1 Criptografia.
ÁREA 4: TRANSFORMAÇÃO DIGITAL E GESTÃO DE TI
ESTRATÉGIA: 1 Planejamento das áreas de conhecimento da organização.
"""
CARGO_AREAS = "TÉCNICO EM TECNOLOGIA DA INFORMAÇÃO II"


class TestAreaComoCargo:
    def test_cada_area_vira_cargo_com_numero_e_rotulo(self):
        chunks = dividir_por_cargo_e_materia(
            SECAO_AREAS, cargo_padrao=CARGO_AREAS, nivel_padrao="superior"
        )
        especificos = [c for c in chunks if c.tipo_conhecimento == "especifico"]
        assert [(c.cargo_numero, c.materia) for c in especificos] == [
            (1, "CONCEITOS BÁSICOS"),
            (2, "ENGENHARIA DE SOFTWARE"),
            (3, "SEGURANÇA DA INFORMAÇÃO"),
            (4, "ESTRATÉGIA"),
        ]
        assert especificos[0].cargo == (
            f"CARGO 1: {CARGO_AREAS} – ÁREA 1: ADMINISTRAÇÃO DE BANCO DE DADOS"
        )
        assert especificos[2].cargo == (
            f"CARGO 3: {CARGO_AREAS} – ÁREA 3: TECNOLOGIA: SEGURANÇA, INFRA E OPERAÇÃO"
        )

    def test_area_nao_vira_materia(self):
        chunks = dividir_por_cargo_e_materia(
            SECAO_AREAS, cargo_padrao=CARGO_AREAS, nivel_padrao="superior"
        )
        assert not [c for c in chunks if c.materia.startswith("ÁREA")]
        assert len(chunks) == 5

    def test_basicos_continuam_sem_cargo(self):
        chunks = dividir_por_cargo_e_materia(
            SECAO_AREAS, cargo_padrao=CARGO_AREAS, nivel_padrao="superior"
        )
        basico = chunks[0]
        assert basico.materia == "LÍNGUA PORTUGUESA"
        assert basico.cargo is None and basico.cargo_numero is None
        assert basico.tipo_conhecimento == "basico"

    def test_mapear_cargos_devolve_as_quatro_areas(self):
        chunks = dividir_por_cargo_e_materia(
            SECAO_AREAS, cargo_padrao=CARGO_AREAS, nivel_padrao="superior"
        )
        assert mapear_cargos(chunks, CARGO_AREAS, "superior") == [
            {
                "numero": 1,
                "nome": f"{CARGO_AREAS} – ÁREA 1: ADMINISTRAÇÃO DE BANCO DE DADOS",
                "nivel": "superior",
            },
            {
                "numero": 2,
                "nome": f"{CARGO_AREAS} – ÁREA 2: DESENVOLVIMENTO DE SOFTWARE",
                "nivel": "superior",
            },
            {
                "numero": 3,
                "nome": f"{CARGO_AREAS} – ÁREA 3: TECNOLOGIA: SEGURANÇA, INFRA E OPERAÇÃO",
                "nivel": "superior",
            },
            {
                "numero": 4,
                "nome": f"{CARGO_AREAS} – ÁREA 4: TRANSFORMAÇÃO DIGITAL E GESTÃO DE TI",
                "nivel": "superior",
            },
        ]

    def test_sem_cargo_padrao_o_rotulo_fica_so_com_a_area(self):
        chunks = dividir_por_cargo_e_materia(SECAO_AREAS, nivel_padrao="superior")
        especifico = next(c for c in chunks if c.cargo_numero == 2)
        assert especifico.cargo == "CARGO 2: ÁREA 2: DESENVOLVIMENTO DE SOFTWARE"
        assert especifico.materia == "ENGENHARIA DE SOFTWARE"

    def test_area_minuscula_no_corpo_nao_casa(self):
        secao = "2.1.2 CONHECIMENTOS ESPECÍFICOS\nÁREA 1: ADMIN\nTEMA: 1 texto\nárea 9: não é cabeçalho\n"
        chunks = dividir_por_cargo_e_materia(secao, nivel_padrao="superior")
        assert [c.cargo_numero for c in chunks] == [1]
        assert "área 9" in chunks[0].texto


@pytest.mark.skipif(
    not (
        Path(__file__).resolve().parent.parent
        / "data/2025/CEBRASPE/BANRISUL/Editais/Ed_1_2025_Banrisul_Abertura_atualizado_ate_ret_4.pdf"
    ).exists(),
    reason="PDF BANRISUL não baixado (data/ é gitignored)",
)
def test_edital_banrisul_real_tem_quatro_areas_como_cargos():
    pdf = (
        Path(__file__).resolve().parent.parent
        / "data/2025/CEBRASPE/BANRISUL/Editais/Ed_1_2025_Banrisul_Abertura_atualizado_ate_ret_4.pdf"
    )
    secao = extrair_secao_objetos_avaliacao_detalhada(pdf)
    chunks = dividir_por_cargo_e_materia(
        secao.texto,
        cargo_padrao=secao.cargo_detectado,
        nivel_padrao=secao.nivel_detectado,
    )
    cargos = mapear_cargos(chunks, secao.cargo_detectado, secao.nivel_detectado)
    assert [c["numero"] for c in cargos] == [1, 2, 3, 4]
    assert [c["nome"].split(" – ")[1] for c in cargos] == [
        "ÁREA 1: ADMINISTRAÇÃO DE BANCO DE DADOS",
        "ÁREA 2: DESENVOLVIMENTO DE SOFTWARE",
        "ÁREA 3: TECNOLOGIA: SEGURANÇA, INFRA E OPERAÇÃO",
        "ÁREA 4: TRANSFORMAÇÃO DIGITAL E GESTÃO DE TI",
    ]
    assert all(c["nivel"] == "superior" for c in cargos)
    assert not [c for c in chunks if c.materia.startswith("ÁREA")]
