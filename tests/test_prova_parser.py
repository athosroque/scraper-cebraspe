from pathlib import Path

import pymupdf
import pytest

from src.gabarito_parser import ler_grade
from src.prova_parser import (
    PADRAO_COMANDO_REFERE_TEXTO,
    STATUS_FALHA_ITENS_DIVERGENTES,
    STATUS_FALHA_SEM_GABARITO,
    STATUS_SUCESSO,
    Linha,
    _chave_titulo,
    _eh_codigo_ou_tabela,
    _extrair_quesitos,
    _linha_monoespacada,
    _marcar_borda_direita,
    _recuo_item,
    _tema,
    _texto_spans,
    _unir_tiras,
    extrair_caderno_discursivo,
    extrair_caderno_objetivo,
    juntar_linhas,
    ligar_padrao_resposta,
    localizar_itens,
    ordenar_blocos,
    segmentar,
)

FIXTURES = Path(__file__).parent / "fixtures" / "questoes"


@pytest.fixture(scope="module")
def grade_pf_cb1():
    return ler_grade(FIXTURES / "Gab_Definitivo_094_PF_CB1_01.pdf").respostas


def _gabarito(grade, numeros):
    return {n: grade[n] for n in numeros}


def _l(texto, primeiro_span=None, x0=28, y0=0, bloco=1, inicio=True, negrito=False):
    return Linha(
        pagina=0,
        bloco=bloco,
        texto=texto,
        x0=x0,
        y0=y0,
        x1=290,
        y1=y0 + 10,
        inicio_bloco=inicio,
        primeiro_span=primeiro_span if primeiro_span is not None else texto,
        negrito=negrito,
    )


class TestMarcadorDeItem:
    def test_numero_em_linha_de_texto_nao_e_item(self):
        # "55 metros." no meio do texto-base (achado real no 072_STM_006_01)
        # vem antes do item 55 de verdade, que tem o número num span próprio.
        linhas = [
            _l("54 ", primeiro_span="54 "),
            _l("Um prédio tem altura de", inicio=False),
            _l("55 metros.", inicio=False),
            _l("55 ", primeiro_span="55 "),
            _l("texto do item 55", x0=46, inicio=False),
        ]
        assert localizar_itens(linhas, [54, 55]) == {54: (0, True), 55: (3, True)}

    def test_fallback_sem_fonte_propria_entre_vizinhos(self):
        linhas = [
            _l("1 ", primeiro_span="1 "),
            _l("texto do item um.", x0=46, inicio=False),
            _l("2 Texto do item dois", primeiro_span="2 Texto do item dois", bloco=2),
            _l("3 ", primeiro_span="3 ", bloco=3),
        ]
        assert localizar_itens(linhas, [1, 2, 3]) == {
            1: (0, True),
            2: (2, False),
            3: (3, True),
        }

    def test_numero_em_tabela_dentro_da_faixa_ignorado(self):
        # Tabela com células "2", "3" antes dos itens reais 2 e 3.
        # As células da tabela têm x0 fora da margem da coluna e não são negrito.
        # O parser deve ignorar a tabela e localizar os itens reais na margem.
        linhas = [
            _l(
                "Julgue os itens a seguir com base na tabela.",
                primeiro_span="Julgue",
                x0=28,
            ),
            _l("2", primeiro_span="2", x0=100),
            _l("12,5", primeiro_span="12,5", x0=150),
            _l("3", primeiro_span="3", x0=100),
            _l("14,0", primeiro_span="14,0", x0=150),
            _l("1 Primeiro item real.", primeiro_span="1", x0=28),
            _l("2 Segundo item real.", primeiro_span="2", x0=28),
            _l("3 Terceiro item real.", primeiro_span="3", x0=28),
        ]
        achados = localizar_itens(linhas, [1, 2, 3])
        assert achados == {1: (5, True), 2: (6, True), 3: (7, True)}

    def test_numero_duplicado_gera_alerta_bloqueante(self):
        # Dois candidatos a marcador para o item 2 na margem da coluna.
        linhas = [
            _l("1 Primeiro item.", primeiro_span="1", x0=28),
            _l("2 Candidato falso na margem.", primeiro_span="2", x0=28),
            _l("2 Candidato verdadeiro na margem.", primeiro_span="2", x0=28),
            _l("3 Terceiro item.", primeiro_span="3", x0=28),
        ]
        alertas = []
        achados = localizar_itens(linhas, [1, 2, 3], alertas=alertas)
        # O item 2 não pode ser escolhido silenciosamente
        assert 2 not in achados
        assert len(alertas) == 1
        assert alertas[0]["tipo"] == "marcador_duplicado"
        assert alertas[0]["severidade"] == "bloqueante"
        assert alertas[0]["item"] == 2
        assert alertas[0]["indices"] == [1, 2]

    def test_marcador_fora_de_ordem_gera_alerta_bloqueante(self):
        # Item 3 aparece antes do item 2 nas linhas
        linhas = [
            _l("1 Primeiro item.", primeiro_span="1", x0=28),
            _l("3 Terceiro item fora de ordem.", primeiro_span="3", x0=28),
            _l("2 Segundo item atrasado.", primeiro_span="2", x0=28),
        ]
        alertas = []
        achados = localizar_itens(linhas, [1, 2, 3], alertas=alertas)
        # O item 3 apareceu antes de 2 (linha 1 vs linha 2)
        # Ao iterar na ordem [1, 2, 3], o item 3 é rejeitado por aparecer antes da linha de 2
        assert 3 not in achados
        assert any(
            a["tipo"] == "marcador_fora_de_ordem"
            and a["severidade"] == "bloqueante"
            and a["item"] == 3
            for a in alertas
        )


class TestCadernoObjetivoReal:
    def test_pagina_com_textos_base_e_comandos(self, grade_pf_cb1):
        gabarito = _gabarito(grade_pf_cb1, range(15, 28))
        resultado, auditoria = extrair_caderno_objetivo(
            FIXTURES / "094_PF_CB1_01_pag2.pdf", gabarito, "094_PF_CB1_01"
        )
        assert resultado["status"] == STATUS_SUCESSO
        assert [q["numero"] for q in resultado["questoes"]] == list(range(15, 28))
        q = {q["numero"]: q for q in resultado["questoes"]}

        # Proposição P é o texto-base dos itens 15-17; o comando é a seção.
        base_p = resultado["textos_base"][q[15]["texto_base_ordem"]]
        assert base_p["texto"].startswith("P: Se o condenado não for reincidente")
        assert q[17]["texto_base_ordem"] == q[15]["texto_base_ordem"]
        assert q[15]["secao"].startswith("Com base na proposição P precedente, julgue")
        assert (
            q[16]["enunciado"]
            == "A tabela-verdade associada à proposição P possui mais de 15 linhas."
        )

        # "220 condenados ..." é lista do texto-base, não item.
        base_levantamento = resultado["textos_base"][q[18]["texto_base_ordem"]]
        assert "220 condenados não são reincidentes" in base_levantamento["texto"]
        assert (
            q[18]["secao"] == "Com base nessas informações, julgue os itens seguintes."
        )

        # Grupo sem texto-base: só comando.
        assert q[20]["texto_base_ordem"] is None
        assert "Lei n.º 12.813/2013" in q[20]["secao"]
        assert q[20]["gabarito"] == gabarito[20]
        assert auditoria["itens"]["16"]["linhas_brutas"][0].startswith(
            "16 A tabela-verdade"
        )

    def test_figura_do_item_e_extraida(self, grade_pf_cb1, tmp_path):
        gabarito = _gabarito(grade_pf_cb1, range(28, 51))
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "094_PF_CB1_01_pag3.pdf", gabarito, "cad", tmp_path
        )
        assert resultado["status"] == STATUS_SUCESSO
        assert resultado["alertas"] == []
        q = {q["numero"]: q for q in resultado["questoes"]}
        assert [f["arquivo"] for f in q[31]["figuras"]] == ["cad_1_1.png"]
        assert (tmp_path / "cad_1_1.png").exists()
        assert resultado["total_figuras"] == 1
        assert q[37]["gabarito"] == "X" and q[37]["anulada"]

    def test_item_do_caderno_fora_do_gabarito_e_falha_visivel(self, grade_pf_cb1):
        # Gabarito truncado em 39: os itens 40-50 do caderno não podem ser
        # engolidos pelo item 39 em silêncio.
        gabarito = _gabarito(grade_pf_cb1, range(28, 40))
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "094_PF_CB1_01_pag3.pdf", gabarito, "cad"
        )
        assert resultado["status"] == STATUS_FALHA_ITENS_DIVERGENTES
        assert resultado["itens_fora_do_gabarito"] == list(range(40, 51))

    def test_item_do_gabarito_ausente_no_caderno_e_falha_visivel(self, grade_pf_cb1):
        gabarito = _gabarito(grade_pf_cb1, range(15, 29))  # 28 está na pág. 3
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "094_PF_CB1_01_pag2.pdf", gabarito, "cad"
        )
        assert resultado["status"] == STATUS_FALHA_ITENS_DIVERGENTES
        assert resultado["itens_faltando"] == [28]
        assert resultado["itens_extraidos"] == 13
        bloqueante = [
            a for a in resultado["alertas"] if a["severidade"] == "bloqueante"
        ]
        assert bloqueante[0]["faltando"] == [28]

    def test_sem_gabarito_nao_chuta_faixa(self):
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "094_PF_CB1_01_pag2.pdf", None, "cad"
        )
        assert resultado["status"] == STATUS_FALHA_SEM_GABARITO
        assert resultado["questoes"] == []


class TestAuxiliares:
    def test_juntar_linhas_hifen_e_espacos(self):
        assert (
            juntar_linhas(["executá-", "los  no", "  prazo. "])
            == "executá-los no prazo."
        )
        assert (
            juntar_linhas(["Lei n.º 8.112/1990 ―", "e da Lei"])
            == "Lei n.º 8.112/1990 ― e da Lei"
        )

    def test_juntar_linhas_preserva_codigo_java_com_indentacao(self):
        trecho_stm = [
            "A execução do código a seguir, escrito em Java, retornará o ",
            "resultado True. ",
            "package com.mcnz.recursion; ",
            "public class checkpgm { ",
            "  public static void main(String[] args) { ",
            '    boolean flag = Check("STM"); ',
            "    System.out.println(flag); ",
            "  } ",
            "  public static boolean Check(String s){ ",
            "    if(s.length() == 0 || s.length() == 1) { ",
            "      return true; ",
            "    } ",
            "    return false; ",
            "  } ",
            "} ",
        ]
        resultado = juntar_linhas(trecho_stm)
        esperado = (
            "A execução do código a seguir, escrito em Java, retornará o resultado True.\n"
            "package com.mcnz.recursion;\n"
            "public class checkpgm {\n"
            "  public static void main(String[] args) {\n"
            '    boolean flag = Check("STM");\n'
            "    System.out.println(flag);\n"
            "  }\n"
            "  public static boolean Check(String s){\n"
            "    if(s.length() == 0 || s.length() == 1) {\n"
            "      return true;\n"
            "    }\n"
            "    return false;\n"
            "  }\n"
            "}"
        )
        assert resultado == esperado

    def test_juntar_linhas_preserva_yaml(self):
        trecho_yaml = [
            "Considere que o seguinte arquivo YAML tenha sido ",
            "utilizado para criar um deployment no Kubernetes: ",
            "apiVersion: apps/v1 ",
            "kind: Deployment ",
            "metadata: ",
            "  name: nginx-deployment ",
            "spec: ",
            "  replicas: 2 ",
        ]
        resultado = juntar_linhas(trecho_yaml)
        esperado = (
            "Considere que o seguinte arquivo YAML tenha sido utilizado para criar um deployment no Kubernetes:\n"
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: nginx-deployment\n"
            "spec:\n"
            "  replicas: 2"
        )
        assert resultado == esperado

    def test_juntar_linhas_preserva_tabela_e_json(self):
        trecho_tabela = [
            "Nesse caso, apresentará o seguinte resultado: ",
            " id |   nome  ",
            "----+----------- ",
            "  1 | Bicicleta ",
        ]
        assert juntar_linhas(trecho_tabela) == (
            "Nesse caso, apresentará o seguinte resultado:\n"
            " id |   nome\n"
            "----+-----------\n"
            "  1 | Bicicleta"
        )

        trecho_json = [
            "O código a seguir é um exemplo de uma notação JSON com ",
            "formato válido. ",
            '{"Nome":[{"letra":"S","nome":"Supremo"}, ',
            '{"letra":"T","nome":"Tribunal"}, ',
            '{"letra":"M","nome":"Militar"}]} ',
        ]
        assert juntar_linhas(trecho_json) == (
            "O código a seguir é um exemplo de uma notação JSON com formato válido.\n"
            '{"Nome":[{"letra":"S","nome":"Supremo"},\n'
            '{"letra":"T","nome":"Tribunal"},\n'
            '{"letra":"M","nome":"Militar"}]}'
        )

    def test_juntar_linhas_com_linha_monoespacada(self):
        l1 = Linha(0, 1, "Prose text line 1 ", 28.3, 100, 200, 110, True)
        l2 = Linha(0, 1, "prose text line 2 ", 28.3, 112, 200, 122, False)
        l3 = Linha(0, 2, "  def foo(): ", 28.3, 130, 200, 140, True, monoespacada=True)
        l4 = Linha(
            0, 2, "    return 42 ", 28.3, 142, 200, 152, False, monoespacada=True
        )
        assert juntar_linhas([l1, l2, l3, l4]) == (
            "Prose text line 1 prose text line 2\n  def foo():\n    return 42"
        )

    def test_juntar_linhas_preserva_indentacao_python_por_x0(self):
        # Na prova 094_PF_005_01 (itens 110 a 115), o código Python não traz
        # espaços ASCII no início de cada linha, mas desloca a posição horizontal x0.
        linhas = [
            Linha(
                0,
                1,
                "def calculo(lista):",
                46.26,
                100,
                200,
                110,
                True,
                monoespacada=True,
            ),
            Linha(
                0, 1, "for n in lista:", 70.98, 112, 200, 122, False, monoespacada=True
            ),
            Linha(
                0,
                1,
                "for x in range(2, n):",
                85.20,
                124,
                200,
                134,
                False,
                monoespacada=True,
            ),
            Linha(
                0, 1, "if n % x == 0:", 99.36, 136, 200, 146, False, monoespacada=True
            ),
            Linha(0, 1, "n=n//x", 113.57, 148, 200, 158, False, monoespacada=True),
            Linha(0, 1, "break", 113.57, 160, 200, 170, False, monoespacada=True),
            Linha(0, 1, "else:", 85.20, 172, 200, 182, False, monoespacada=True),
            Linha(
                0,
                1,
                'print(f"O Resultado é: {n}")',
                99.36,
                184,
                200,
                194,
                False,
                monoespacada=True,
            ),
            Linha(
                0,
                1,
                "lista = [2, 4, 6]",
                46.26,
                196,
                200,
                206,
                False,
                monoespacada=True,
            ),
            Linha(
                0, 1, "calculo(lista)", 46.26, 208, 200, 218, False, monoespacada=True
            ),
        ]
        esperado = (
            "def calculo(lista):\n"
            "    for n in lista:\n"
            "        for x in range(2, n):\n"
            "            if n % x == 0:\n"
            "                n=n//x\n"
            "                break\n"
            "        else:\n"
            '            print(f"O Resultado é: {n}")\n'
            "lista = [2, 4, 6]\n"
            "calculo(lista)"
        )
        assert juntar_linhas(linhas) == esperado

    def test_termo_monoespacado_no_inicio_da_linha_nao_quebra_prosa(self):
        # Linha em que o primeiro span é termo técnico monoespaçado, mas o restante
        # da linha é texto corrido em fonte proporcional. Não deve quebrar com \n.
        l1 = Linha(
            0,
            1,
            "só será criada a pipeline se as três regras de ativação do",
            28.3,
            100,
            290,
            110,
            True,
            monoespacada=False,
        )
        l2 = Linha(
            0,
            1,
            "workflow.rules forem verdadeiras.",
            28.3,
            112,
            290,
            122,
            False,
            monoespacada=False,
        )
        assert juntar_linhas([l1, l2]) == (
            "só será criada a pipeline se as três regras de ativação do "
            "workflow.rules forem verdadeiras."
        )

        # Checa _linha_monoespacada diretamente:
        spans_misto = [
            {"text": "workflow.rules", "font": "Courier", "flags": 8},
            {"text": " forem verdadeiras.", "font": "Times-Roman", "flags": 0},
        ]
        assert not _linha_monoespacada(spans_misto, {"Courier"})

    def test_formula_com_pipe_isolado_nao_vira_tabela(self):
        # Barra vertical isolada em fórmula matemática/estatística (ex: Poisson em PF_005)
        # não deve ser classificada como tabela.
        linha_formula = "Var(X | Y) = 5."
        assert not _eh_codigo_ou_tabela("texto", linha_formula)
        # Tabela com múltiplos pipes ou divisor ainda é detectada
        assert _eh_codigo_ou_tabela("texto", "col1 | col2 | col3")
        assert _eh_codigo_ou_tabela("texto", "----+----")

    def test_tiras_empilhadas_viram_uma_figura(self):
        tiras = [pymupdf.Rect(89, 276 + 35 * i, 506, 311 + 35 * i) for i in range(7)]
        separada = pymupdf.Rect(300, 600, 400, 700)
        unidas = _unir_tiras(tiras + [separada])
        assert len(unidas) == 2
        assert unidas[0] == pymupdf.Rect(89, 276, 506, 521)

    @pytest.mark.parametrize(
        ("enunciado", "esperado"),
        [
            (
                (
                    "Considerando que ..., redija um texto dissertativo a respeito do seguinte tema.\n"
                    "A IMPORTÂNCIA DA LEITURA NA ERA DIGITAL"
                ),
                ("A IMPORTÂNCIA DA LEITURA NA ERA DIGITAL", None),
            ),
            (
                "Considerando a lei, elabore um texto dissertativo acerca de licitações. Em seu texto, atenda.",
                ("licitações", None),
            ),
            (
                "Redija um texto dissertativo em atendimento ao que se pede a seguir.",
                (None, None),
            ),
            (
                "Considerando o caso concreto, redija um texto dissertativo acerca dessa contratação.",
                (None, "dessa contratação"),
            ),
            (
                "Considerando a matéria, elabore um texto sobre a implantação do referido sistema de alerta.",
                (None, "a implantação do referido sistema de alerta"),
            ),
        ],
    )
    def test_tema(self, enunciado, esperado):
        assert _tema(enunciado) == esperado


class TestCadernoDiscursivo:
    def test_varias_questoes_e_peca(self):
        resultado, auditoria = extrair_caderno_discursivo(
            FIXTURES / "108_TCUTEFC_002_DISC.pdf", "108_TCUTEFC_002_DISC"
        )
        assert resultado["status"] == STATUS_SUCESSO
        titulos = [q["titulo"] for q in resultado["questoes"]]
        assert titulos == ["Questão 1", "Questão 2", "Peça de natureza técnica"]
        valores = [
            [qq["valor_pontos"] for qq in q["quesitos"]] for q in resultado["questoes"]
        ]
        assert valores == [[1.2] * 4, [2.4, 2.4], [3.0, 4.0, 4.0, 4.0, 4.0]]
        # Soma dos quesitos confere com a capa (5 - 0,2 por questão; 20 - 1
        # na peça): nenhum alerta de soma.
        assert not [
            a for a in resultado["alertas"] if a["tipo"] == "soma_quesitos_divergente"
        ]
        assert [q.get("pontos_conteudo") for q in resultado["questoes"]] == [
            4.8,
            4.8,
            19.0,
        ]
        # A grade de rascunho não vaza para o enunciado.
        assert "RASCUNHO" not in resultado["questoes"][0]["enunciado"]
        assert len(auditoria["questoes"]) == 3

    def test_questao_unica_com_quesitos_numerados(self):
        resultado, _ = extrair_caderno_discursivo(
            FIXTURES / "PF_DISC_CARGO_1.pdf", "PF_25_ADM_DISC_001"
        )
        [questao] = resultado["questoes"]
        assert questao["titulo"] is None
        assert questao["tema"] == "licitações"
        assert [q["valor_pontos"] for q in questao["quesitos"]] == [6.0, 3.0, 7.5, 2.5]
        assert (
            questao["quesitos"][0]["texto"]
            == "Discorra sobre os objetivos do processo licitatório."
        )
        assert questao["pontos_conteudo"] == 19.0

    def test_quesitos_so_a_partir_do_comando(self):
        bloco = (
            "No dia 1 de janeiro de 2020 ocorreu a reunião preliminar.\n"
            "Considerando o caso, redija um texto dissertativo atendendo ao que se pede:\n"
            "1 apresente as regras vigentes;\n"
            "2 discorra sobre as sanções cabíveis."
        )
        quesitos, offset = _extrair_quesitos(bloco)
        assert len(quesitos) == 2
        assert quesitos[0]["numero"] == 1
        assert "apresente as regras vigentes" in quesitos[0]["texto"]
        assert quesitos[1]["numero"] == 2
        assert "discorra sobre as sanções" in quesitos[1]["texto"]
        assert bloco[offset:].startswith("1 apresente")

    def test_chave_titulo(self):
        assert _chave_titulo("Questão 1") == ("questao", 1)
        assert _chave_titulo("Questão 2 – Conhecimentos Básicos") == ("questao", 2)
        assert _chave_titulo("Peça de natureza técnica") == ("peca", None)
        assert _chave_titulo(None) is None
        assert _chave_titulo("Texto livre") is None

    def test_quesitos_sem_comando_gera_alerta(self):
        bloco = "Texto sem verbos de comando.\n1 primeiro quesito;\n2 segundo quesito."
        alertas = []
        quesitos, _ = _extrair_quesitos(bloco, alertas)
        assert len(quesitos) == 2
        assert any(a["tipo"] == "comando_nao_identificado" for a in alertas)

    def test_tema_anaforico_gera_alerta(self, monkeypatch, tmp_path):
        corpo = (
            "-- PROVA DISCURSIVA --\n"
            "Redija um texto dissertativo acerca dessa contratação.\n"
            "1 quesito um [valor: 10 pontos]\n"
        )
        monkeypatch.setattr("src.prova_parser.extrair_texto_paginas", lambda _: [corpo])
        resultado, _ = extrair_caderno_discursivo(
            tmp_path / "fake.pdf", "CADERNO_TESTE"
        )
        assert resultado["questoes"][0]["tema"] is None
        alerta = next(
            (a for a in resultado["alertas"] if a["tipo"] == "tema_anaforico"), None
        )
        assert alerta is not None
        assert alerta["candidato"] == "dessa contratação"

    def test_ligar_padrao_resposta_por_chave_fora_de_ordem(self):
        resultado = {
            "questoes": [
                {"numero": 1, "titulo": "Questão 1"},
                {"numero": 2, "titulo": "Questão 2"},
                {"numero": 3, "titulo": "Peça de natureza técnica"},
            ],
            "alertas": [],
        }
        secoes = [
            {"titulo": "Prova Discursiva – Questão 2", "texto": "texto da questao 2"},
            {
                "titulo": "Prova Discursiva – Peça de natureza técnica",
                "texto": "texto da peca",
            },
            {"titulo": "Prova Discursiva – Questão 1", "texto": "texto da questao 1"},
        ]
        ligar_padrao_resposta(resultado, secoes, "padrao.pdf")
        assert [q["padrao_resposta"] for q in resultado["questoes"]] == [
            "texto da questao 1",
            "texto da questao 2",
            "texto da peca",
        ]
        assert resultado["alertas"] == []

    def test_ligar_padrao_resposta_secao_com_chave_repetida_nao_liga_por_chave(
        self,
    ):
        # Duas seções "Questão 1": a ligação por chave pegaria só a última em
        # silêncio; o certo é cair no passo 3 (texto inteiro, com alerta).
        resultado = {
            "questoes": [
                {"numero": 1, "titulo": "Questão 1"},
                {"numero": 2, "titulo": "Questão 2"},
            ],
            "alertas": [],
        }
        secoes = [
            {"titulo": "Prova Discursiva – Questão 1", "texto": "primeira"},
            {"titulo": "Prova Discursiva – Questão 2", "texto": "segunda"},
            {"titulo": "Prova Discursiva – Questão 1", "texto": "repetida"},
        ]
        ligar_padrao_resposta(resultado, secoes, "padrao.pdf")
        assert [q["padrao_resposta"] for q in resultado["questoes"]] == [
            "primeira\n\nsegunda\n\nrepetida",
            "primeira\n\nsegunda\n\nrepetida",
        ]
        assert resultado["alertas"][0]["tipo"] == "padrao_resposta_nao_dividido"

    def test_ligar_padrao_resposta_questao_com_chave_repetida_liga_por_ordem(self):
        resultado = {
            "questoes": [
                {"numero": 1, "titulo": "Questão 1"},
                {"numero": 2, "titulo": "Questão 1"},
            ],
            "alertas": [],
        }
        secoes = [
            {"titulo": "Prova Discursiva – Questão 1", "texto": "um"},
            {"titulo": "Prova Discursiva – Questão 2", "texto": "dois"},
        ]
        ligar_padrao_resposta(resultado, secoes, "padrao.pdf")
        assert [q["padrao_resposta"] for q in resultado["questoes"]] == ["um", "dois"]
        assert any(a["tipo"] == "padrao_ligado_por_ordem" for a in resultado["alertas"])

    def test_ligar_padrao_resposta_por_ordem_alerta(self):
        resultado = {"questoes": [{"numero": 1}, {"numero": 2}], "alertas": []}
        ligar_padrao_resposta(
            resultado, [{"texto": "um"}, {"texto": "dois"}], "padrao.pdf"
        )
        assert [q["padrao_resposta"] for q in resultado["questoes"]] == ["um", "dois"]
        assert any(a["tipo"] == "padrao_ligado_por_ordem" for a in resultado["alertas"])

    def test_ligar_padrao_resposta_questao_unica_sem_titulo_sem_alerta(self):
        resultado = {
            "questoes": [{"numero": 1, "titulo": None}],
            "alertas": [],
        }
        ligar_padrao_resposta(resultado, [{"texto": "padrao unico"}], "padrao.pdf")
        assert resultado["questoes"][0]["padrao_resposta"] == "padrao unico"
        assert resultado["alertas"] == []

    def test_ligar_padrao_resposta_nao_dividido(self):
        resultado = {"questoes": [{"numero": 1}, {"numero": 2}], "alertas": []}
        ligar_padrao_resposta(resultado, [{"texto": "tudo"}], "padrao.pdf")
        assert [q["padrao_resposta"] for q in resultado["questoes"]] == ["tudo", "tudo"]
        assert resultado["alertas"][0]["tipo"] == "padrao_resposta_nao_dividido"

    def test_bloco_vazio_no_meio_nao_cria_buraco(self, monkeypatch, tmp_path):
        corpo = (
            "-- PROVA DISCURSIVA --\n"
            "Questão 1\n"
            "Redija um texto sobre A.\n"
            "1 quesito um [valor: 5 pontos]\n"
            "Questão 2\n\n"
            "Peça de natureza técnica\n"
            "Elabore uma peça técnica sobre B.\n"
            "1 quesito da peça [valor: 10 pontos]\n"
        )
        monkeypatch.setattr("src.prova_parser.extrair_texto_paginas", lambda _: [corpo])
        resultado, _ = extrair_caderno_discursivo(
            tmp_path / "fake.pdf", "CADERNO_TESTE"
        )
        numeros = [q["numero"] for q in resultado["questoes"]]
        assert numeros == [1, 2]
        assert not any(
            a["tipo"] == "numeracao_discursiva" for a in resultado["alertas"]
        )

    def test_alertas_sem_quesitos_e_quesito_sem_valor(self, monkeypatch, tmp_path):
        corpo = (
            "-- PROVA DISCURSIVA --\n"
            "Questão 1\n"
            "Redija um texto sem quesitos.\n\n"
            "Questão 2\n"
            "Redija um texto.\n"
            "1 quesito sem valor definido\n"
            "2 outro quesito [valor: 5 pontos]\n"
        )
        monkeypatch.setattr("src.prova_parser.extrair_texto_paginas", lambda _: [corpo])
        resultado, _ = extrair_caderno_discursivo(
            tmp_path / "fake.pdf", "CADERNO_TESTE"
        )
        assert any(
            a["tipo"] == "sem_quesitos" and a["questao"] == 1
            for a in resultado["alertas"]
        )
        alerta_val = next(
            (
                a
                for a in resultado["alertas"]
                if a["tipo"] == "quesito_sem_valor" and a["questao"] == 2
            ),
            None,
        )
        assert alerta_val is not None
        assert alerta_val["quesitos"] == [1]


class TestOrdemEReferencias:
    def test_tabela_no_fim_do_fluxo_volta_para_a_posicao_visual(self):
        # 072_STM_010_01: a tabela dos itens 115-116 vem no fim do fluxo do PDF.
        def bloco(x0, y0, x1, texto):
            return {"type": 0, "bbox": (x0, y0, x1, y0 + 10), "texto": texto}

        blocos = [
            bloco(28, 50, 294, "esq topo"),
            bloco(303, 50, 569, "dir topo"),
            bloco(303, 400, 569, "dir baixo"),
            bloco(40, 300, 200, "tabela da esquerda"),
        ]
        ordem = [b["texto"] for b in ordenar_blocos(blocos, 595)]
        assert ordem == ["esq topo", "tabela da esquerda", "dir topo", "dir baixo"]

    def test_pagina_de_uma_coluna_com_celula_a_direita(self):
        blocos = [
            {"type": 0, "bbox": (28, 50, 569, 60)},
            {"type": 0, "bbox": (400, 70, 450, 80)},  # célula estreita
            {"type": 0, "bbox": (28, 90, 569, 100)},
        ]
        assert [b["bbox"][1] for b in ordenar_blocos(blocos, 595)] == [50, 70, 90]

    @pytest.mark.xfail(
        reason="Limitação conhecida: layout de 2 colunas com bloco largo central inverte ordem (dir topo vem após esq baixo). Hoje 0 blocos desse tipo nos 42 cadernos reais."
    )
    def test_duas_colunas_com_bloco_largo_no_meio_ordem(self):
        # Página de duas colunas com bloco de largura total no meio.
        # A ordem humana esperada é: esq topo, dir topo, bloco largo, esq baixo, dir baixo.
        # No algoritmo atual simples (coluna_direita, y0, x0), o bloco largo (x0=28)
        # cai na coluna esquerda e o topo direito vem após o bloco largo e esq baixo.
        def bloco(x0, y0, x1, texto):
            return {"type": 0, "bbox": (x0, y0, x1, y0 + 10), "texto": texto}

        blocos = [
            bloco(28, 50, 294, "esq topo"),
            bloco(28, 200, 569, "bloco largo meio"),
            bloco(28, 350, 294, "esq baixo"),
            bloco(303, 50, 569, "dir topo"),
            bloco(303, 350, 569, "dir baixo"),
        ]
        ordem = [b["texto"] for b in ordenar_blocos(blocos, 595)]
        assert ordem == [
            "esq topo",
            "dir topo",
            "bloco largo meio",
            "esq baixo",
            "dir baixo",
        ]

    def test_ordenar_blocos_desempate_x0(self):
        def bloco(x0, y0, x1, texto):
            return {"type": 0, "bbox": (x0, y0, x1, y0 + 10), "texto": texto}

        # Dois blocos na mesma coluna e mesma altura y0: x0 desempata da esquerda para a direita
        blocos = [
            bloco(150, 50, 250, "segundo"),
            bloco(28, 50, 100, "primeiro"),
        ]
        ordem = [b["texto"] for b in ordenar_blocos(blocos, 595)]
        assert ordem == ["primeiro", "segundo"]

    @pytest.mark.parametrize(
        ("comando", "refere"),
        [
            (
                "Considerando as informações precedentes, julgue os próximos itens.",
                True,
            ),
            ("Julgue os itens que se seguem, referentes ao texto CG4A1.", True),
            ("Com base nos dados da tabela precedente, julgue o item.", True),
            (
                (
                    "Em cada um dos itens que se seguem, é apresentada uma situação "
                    "hipotética seguida de uma assertiva a ser julgada."
                ),
                False,
            ),
            (
                "Acerca da ética no serviço público, julgue os itens que se seguem.",
                False,
            ),
        ],
    )
    def test_comando_que_se_refere_ao_material_anterior(self, comando, refere):
        assert bool(PADRAO_COMANDO_REFERE_TEXTO.search(comando)) is refere

    def test_simbolo_de_formula_sem_unicode_fica_visivel(self):
        assert juntar_linhas(["O primeiro quartil de \x02 é igual a zero."]) == (
            "O primeiro quartil de � é igual a zero."
        )


class TestSegmentacao:
    def test_recuo_item_ignora_paragrafo_texto_base(self):
        # Item de 1 linha física sucedido por texto-base indentado (~28.3 pt).
        # _recuo_item não deve capturar o recuo do texto-base (deve retornar 18.0 padrão).
        linhas = [
            _l(
                "55 A paciente apresenta indícios de lesão.",
                primeiro_span="55",
                x0=28.44,
            ),
            _l("Um paciente de 66 anos de idade...", primeiro_span="Um", x0=56.76),
            _l("dispneia aos esforços moderados.", primeiro_span="dispneia", x0=28.44),
        ]
        assert _recuo_item(linhas, 0) == 18.0

    def test_recuo_item_mede_continuacao_legitima(self):
        # Item com continuação real com recuo de ~17.9 pt.
        linhas = [
            _l(
                "59 O modelo clínico-hemodinâmico de descompensação",
                primeiro_span="59",
                x0=28.44,
            ),
            _l(
                "apresentado sugere pior prognóstico.",
                primeiro_span="apresentado",
                x0=46.32,
            ),
        ]
        assert abs(_recuo_item(linhas, 0) - 17.88) < 0.01

    def test_segmentacao_item_uma_linha_nao_engole_texto_base(self):
        # Cenário real (094_PF_007_01): item 55 de 1 linha física seguido por
        # texto-base com parágrafo indentado (~28.3 pt) e comando subsequente.
        linhas = [
            _l(
                "Julgue o item a seguir a respeito de medicina.",
                primeiro_span="Julgue",
                x0=28.44,
                bloco=13,
            ),
            _l(
                "55 A paciente apresenta indícios de lesão em órgão alvo.",
                primeiro_span="55",
                x0=28.44,
                bloco=14,
            ),
            _l(
                "Um paciente de 66 anos de idade, com antecedente de HAS, compareceu.",
                primeiro_span="Um",
                x0=56.76,
                bloco=15,
            ),
            _l(
                "dispneia aos esforços moderados e tosse seca.",
                primeiro_span="dispneia",
                x0=28.44,
                bloco=15,
            ),
            _l(
                "Com base no caso clínico apresentado, julgue os itens a seguir.",
                primeiro_span="Com",
                x0=28.44,
                bloco=16,
            ),
            _l(
                "56 Nesse caso, é recomendável conduta conservadora.",
                primeiro_span="56",
                x0=28.44,
                bloco=17,
            ),
        ]
        achados = {55: (1, True), 56: (5, True)}
        res = segmentar(linhas, achados)

        # O item 55 deve conter estritamente seu enunciado, sem o texto-base subsequente.
        assert (
            res.itens[55]["enunciado"]
            == "A paciente apresenta indícios de lesão em órgão alvo."
        )
        # Nenhum trecho indevido anexado ao item 55.
        alertas_55 = [a for a in res.alertas if a.get("item") == 55]
        assert not alertas_55

        # O texto-base deve começar pela sua primeira linha com recuo de parágrafo.
        tb_ordem = res.itens[56]["texto_base_ordem"]
        assert tb_ordem is not None
        assert res.textos_base[tb_ordem]["texto"].startswith(
            "Um paciente de 66 anos de idade"
        )

    def test_item_que_cruza_coluna(self):
        # Item 1 começa na coluna esquerda (x0=28.3) e continua na coluna direita (x0=321.3)
        linhas = [
            _l("Julgue o item.", primeiro_span="Julgue", x0=28.3, y0=50),
            _l(
                "1 Início do enunciado no fim da",
                primeiro_span="1",
                x0=28.3,
                y0=700,
            ),
            _l(
                "coluna esquerda e continuando na",
                primeiro_span="coluna",
                x0=46.3,
                y0=715,
            ),
            _l(
                "coluna direita com o mesmo recuo.",
                primeiro_span="coluna",
                x0=321.3,
                y0=50,
            ),
            _l(
                "2 Próximo item na coluna direita.",
                primeiro_span="2",
                x0=303.3,
                y0=70,
            ),
        ]
        achados = {1: (1, True), 2: (4, True)}
        res = segmentar(linhas, achados)
        assert res.itens[1]["enunciado"] == (
            "Início do enunciado no fim da coluna esquerda e continuando na "
            "coluna direita com o mesmo recuo."
        )
        assert res.itens[2]["enunciado"] == "Próximo item na coluna direita."

    def test_item_que_cruza_pagina(self):
        # Item começa na página 0 e continua na página 1
        l_p0_1 = _l("Julgue o item.", primeiro_span="Julgue", x0=28.3, y0=50)
        l_p0_2 = _l(
            "1 Enunciado do item que começa na",
            primeiro_span="1",
            x0=28.3,
            y0=750,
        )
        l_p1_1 = Linha(
            pagina=1,
            bloco=1,
            texto="página seguinte e conclui aqui.",
            x0=46.3,
            y0=50,
            x1=290,
            y1=60,
            inicio_bloco=True,
            primeiro_span="página",
            negrito=False,
        )
        l_p1_2 = Linha(
            pagina=1,
            bloco=2,
            texto="2 Segundo item na nova página.",
            x0=28.3,
            y0=70,
            x1=290,
            y1=80,
            inicio_bloco=True,
            primeiro_span="2",
            negrito=False,
        )
        linhas = [l_p0_1, l_p0_2, l_p1_1, l_p1_2]
        achados = {1: (1, True), 2: (3, True)}
        res = segmentar(linhas, achados)
        assert res.itens[1]["enunciado"] == (
            "Enunciado do item que começa na página seguinte e conclui aqui."
        )
        assert res.itens[2]["enunciado"] == "Segundo item na nova página."


def _cod(texto: str, x0: float, y: float, x1: float, borda: float = 297.3) -> Linha:
    """Linha de código monoespaçada na coluna da esquerda (borda em 297,3 pt,
    como em `072_STM_003_01`)."""
    return Linha(
        0, 1, texto, x0, y, x1, y + 9, False, monoespacada=True, borda_direita=borda
    )


class TestCodigoQuebradoESimbolos:
    def test_recuo_por_posicao_do_x0_nao_depende_da_fonte(self):
        # Degraus de 10 pt (outra fonte): o nível é a posição do x0 entre os
        # x0 distintos do bloco, não uma conta em pontos calibrada na PF_005.
        linhas = [
            _cod("def f(xs):", 40.0, 100, 120),
            _cod("for x in xs:", 50.0, 110, 130),
            _cod("if x:", 60.0, 120, 100),
            _cod("return x", 70.0, 130, 120),
            _cod("return None", 50.0, 140, 130),
        ]
        assert juntar_linhas(linhas) == (
            "def f(xs):\n"
            "    for x in xs:\n"
            "        if x:\n"
            "            return x\n"
            "    return None"
        )

    def test_linha_quebrada_na_borda_volta_para_a_de_cima(self):
        # 072_STM_003_01, item 72: a sobra desce sem o recuo da original.
        linhas = [
            _cod("    - if: $ CI_PIPELINE_SOURCE ==", 46.2, 100, 297.3),
            _cod("'merge_request_event' ", 46.2, 110, 165.0),
            _cod("    - if: $ CI_COMMIT_TAG ", 46.2, 120, 186.6),
        ]
        assert juntar_linhas(linhas) == (
            "    - if: $CI_PIPELINE_SOURCE == 'merge_request_event'\n"
            "    - if: $CI_COMMIT_TAG"
        )

    def test_quebra_perto_da_borda_com_recuo_menor(self):
        # 072_STM_003_01, item 86: termina 5,3 pt antes da borda.
        linhas = [
            _cod("      return Check(s.substring(1, s.length()-", 46.2, 100, 292.0),
            _cod("1)); ", 46.2, 110, 73.2),
            _cod("    } ", 46.2, 120, 78.6),
        ]
        assert juntar_linhas(linhas) == (
            "      return Check(s.substring(1, s.length()-1));\n    }"
        )

    def test_mesmo_recuo_so_junta_com_delimitador_aberto(self):
        # 094_PF_005_01: item 113 (parêntese aberto) junta; item 114
        # (`// 2`, linha completa a 2,7 pt da borda) não junta.
        quebrada = [
            _cod('resultado = sum(dados["anos_prisao"] for', 321.2, 100, 572.2, 572.3),
            _cod("dados in prisao.values()) ", 321.2, 110, 461.6, 572.3),
        ]
        assert juntar_linhas(quebrada) == (
            'resultado = sum(dados["anos_prisao"] for dados in prisao.values())'
        )
        completa = [
            _cod(
                "resultado = (numeros[0] + numeros[1]) // 2 ", 345.9, 100, 569.6, 572.3
            ),
            _cod("x += 1 ", 345.9, 110, 383.7, 572.3),
        ]
        assert juntar_linhas(completa) == (
            "resultado = (numeros[0] + numeros[1]) // 2\nx += 1"
        )

    def test_linha_terminada_em_chave_nao_e_quebra(self):
        linhas = [
            _cod("    if(s.charAt(0) == s.charAt(s.length()-1)) { ", 46.2, 100, 296.0),
            _cod("} ", 46.2, 110, 57.0),
        ]
        assert juntar_linhas(linhas) == (
            "    if(s.charAt(0) == s.charAt(s.length()-1)) {\n}"
        )

    def test_sem_borda_conhecida_nao_junta(self):
        linhas = [
            Linha(0, 1, "a = (1,", 46.2, 100, 297.3, 109, False, monoespacada=True),
            Linha(0, 1, "2)", 46.2, 110, 60.0, 119, False, monoespacada=True),
        ]
        assert juntar_linhas(linhas) == "a = (1,\n2)"

    def test_variavel_com_espaco_so_em_codigo_e_maiuscula(self):
        # Prompt de shell (`$ ls`) fica intacto.
        assert juntar_linhas([_cod("echo $ HOME_DIR; $ ls", 46.2, 100, 150)]) == (
            "echo $HOME_DIR; $ ls"
        )
        # Em prosa fica como veio.
        assert juntar_linhas(["custa $ CEM reais"]) == "custa $ CEM reais"

    def test_simbolo_da_fonte_symbol_vira_unicode(self):
        # 094_PF_005_01, item 110 (menos) e 094_PF_007_01 (vezes); código
        # fora da tabela fica como veio.
        spans = [
            {"text": "while x < len(lista) "},
            {"text": "\uf02d"},
            {"text": " 1: 185 mmHg \uf0b4 146 mmHg \uf0ff"},
        ]
        assert _texto_spans(spans) == (
            "while x < len(lista) - 1: 185 mmHg × 146 mmHg \uf0ff"
        )

    def test_borda_direita_ignora_cabecalho_de_largura_total(self):
        cabecalho = Linha(0, 1, "CABEÇALHO", 28.3, 40, 431.0, 50, True)
        esquerda = Linha(0, 2, "texto", 28.3, 60, 294.5, 70, True)
        direita = Linha(0, 3, "texto", 303.3, 60, 569.4, 70, True)
        _marcar_borda_direita([cabecalho, esquerda, direita], 595.2, True)
        assert esquerda.borda_direita == 294.5
        assert cabecalho.borda_direita == 294.5
        assert direita.borda_direita == 569.4

        unica = Linha(1, 4, "texto", 28.3, 60, 569.4, 70, True)
        rodape = Linha(1, 5, "Espaço livre", 400.0, 800, 460.0, 810, True)
        _marcar_borda_direita([unica, rodape], 595.2, False)
        assert unica.borda_direita == rodape.borda_direita == 569.4
