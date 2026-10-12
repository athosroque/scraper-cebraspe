from src.comparacao_texto import item_coberto


class TestItemCoberto:
    def test_igual_ao_extraido(self):
        assert item_coberto("1.1 Conceitos fundamentais.", ["Conceitos fundamentais"])

    def test_dentro_de_subtopico_agregado(self):
        extraidos = [
            "Mecanismos de segurança: criptografia (simétrica e assimétrica), "
            "assinatura digital, certificação digital"
        ]
        assert item_coberto("Assinatura digital.", extraidos)

    def test_pai_curto_nao_cobre_filho(self):
        # "Ativo" está contido em "Ativo imobilizado", mas isso não cobre o filho.
        assert not item_coberto("Ativo imobilizado.", ["Ativo", "Passivo"])
        assert not item_coberto("Inflação de custos.", ["Inflação"])

    def test_paráfrase_leve_com_parenteses(self):
        assert item_coberto(
            "Educação corporativa.", ["Educação corporativa (atuação do pedagogo)"]
        )

    def test_erro_de_digitacao_corrigido_dentro_de_subtopico_maior(self):
        assert item_coberto(
            "Média, moda, mediada e quartis.",
            ["Medidas de posição: média, moda, mediana e quartis"],
        )

    def test_sigla_no_lugar_do_nome_por_extenso_em_item_longo(self):
        item = (
            "CTG 2001 (R3): procedimentos técnicos e demais formalidades a serem "
            "observados na escrituração contábil em forma digital para fins de "
            "atendimento ao Sistema Público de Escrituração Digital (SPED)."
        )
        extraido = (
            "Sistema Público de Escrituração Digital (SPED): CTG 2001 (R3): "
            "procedimentos técnicos e demais formalidades a serem observados na "
            "escrituração contábil em forma digital para fins de atendimento ao SPED"
        )
        assert item_coberto(item, [extraido])

    def test_item_diferente_nao_e_coberto(self):
        assert not item_coberto(
            "Equilíbrio de mercado sob monopólio.",
            ["Equilíbrio de mercado", "Estruturas de mercado"],
        )

    def test_lista_vazia(self):
        assert not item_coberto("Qualquer coisa.", [])
