import json
import re
from functools import cache
from pathlib import Path

import pymupdf
import pytest

from src.gabarito_parser import ler_grade
from src.prova_parser import (
    PADRAO_COMANDO_REFERE_TEXTO,
    PADRAO_TEXTO_ROTULO_ME,
    STATUS_FALHA_ITENS_DIVERGENTES,
    STATUS_FALHA_SEM_GABARITO,
    STATUS_SUCESSO,
    Linha,
    ResultadoSegmentacao,
    _chave_titulo,
    _eh_cabecalho_layout_me,
    _eh_codigo_ou_tabela,
    _eh_multipla_escolha,
    _extrair_quesitos,
    _linha_monoespacada,
    _marcar_borda_direita,
    _processar_preambulo_me,
    _recuo_item,
    _remover_texto_das_tabelas,
    _segmentar_me,
    _tema,
    _texto_spans,
    _unir_tiras,
    dono_da_figura,
    extrair_caderno_discursivo,
    extrair_caderno_objetivo,
    extrair_linhas,
    figuras_vetoriais_da_pagina,
    juntar_linhas,
    ligar_padrao_resposta,
    localizar_itens,
    localizar_questoes_me,
    marcadores_fora_do_gabarito_me,
    ordenar_blocos,
    remover_ruido,
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


# Parágrafos do texto-base (5G.1) ---------------------------------------------


def _prosa(texto: str, x0: float, y0: float, pagina: int = 0, **kw) -> Linha:
    return Linha(
        pagina=pagina,
        bloco=1,
        texto=texto,
        x0=kw.pop("x0_linha", x0),
        y0=y0,
        x1=280.0,
        y1=y0 + 10,
        inicio_bloco=False,
        x0_texto=x0,
        **kw,
    )


class TestParagrafosTextoBase:
    def _texto(self) -> list[Linha]:
        return [
            _prosa("Primeiro parágrafo começa", 56.8, 50),
            _prosa("e continua aqui.", 28.3, 62),
            _prosa("Segundo parágrafo vem", 56.8, 74),
            _prosa("com mais texto", 28.3, 86),
            _prosa("e termina.", 28.3, 98),
        ]

    def test_recuo_da_primeira_linha_abre_paragrafo(self):
        assert juntar_linhas(self._texto(), paragrafos=True) == (
            "Primeiro parágrafo começa e continua aqui.\n\n"
            "Segundo parágrafo vem com mais texto e termina."
        )

    def test_sem_flag_continua_juntando_com_espaco(self):
        # Enunciado de item: a chave/hash da 5D depende do texto.
        assert "\n" not in juntar_linhas(self._texto())

    def test_span_vazio_na_margem_nao_esconde_o_recuo(self):
        # O x0 da linha fica na margem (spans " " em 28,3 e 42,5); vale o
        # x0 do primeiro span com texto.
        linhas = self._texto()
        linhas[2] = _prosa("Segundo parágrafo vem", 56.8, 74, x0_linha=28.3)
        assert "\n\nSegundo" in juntar_linhas(linhas, paragrafos=True)

    def test_recuo_sem_fim_de_frase_nao_quebra(self):
        linhas = self._texto()
        linhas[1] = _prosa("e continua aqui", 28.3, 62)
        assert "\n" not in juntar_linhas(linhas, paragrafos=True)

    def test_linha_muito_deslocada_nao_e_recuo(self):
        # Fonte centralizada/à direita ("Internet: <...>") não é parágrafo.
        linhas = self._texto() + [_prosa("Internet: <site>.", 171.3, 120)]
        assert "\n\nInternet" not in juntar_linhas(linhas, paragrafos=True)

    def test_moda_por_coluna(self):
        # Parágrafo que continua na coluna da direita (margem 303,4).
        linhas = self._texto() + [
            _prosa("Terceiro na direita", 331.9, 50),
            _prosa("segue aqui", 303.4, 62),
            _prosa("e acaba.", 303.4, 74),
        ]
        partes = juntar_linhas(linhas, paragrafos=True).split("\n\n")
        assert [p.split()[0] for p in partes] == ["Primeiro", "Segundo", "Terceiro"]

    def test_texto_de_uma_linha_sem_regua(self):
        linhas = [_prosa("Só uma.", 56.8, 50)]
        assert juntar_linhas(linhas, paragrafos=True) == "Só uma."

    def test_strings_sem_posicao_nao_quebram(self):
        assert juntar_linhas(["Fim.", "Outra."], paragrafos=True) == "Fim. Outra."


class TestParagrafosReal:
    def test_texto_base_com_paragrafos(self):
        gabarito = {
            14: "E", 15: "C", 16: "E", 17: "E", 18: "C", 19: "C", 20: "C",
            21: "C", 22: "C", 23: "E", 24: "E", 25: "X", 26: "E",
        }  # fmt: skip
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "167_CDNS_CG1_01_pag2.pdf", gabarito, "167_CDNS_CG1_01"
        )
        assert resultado["status"] == STATUS_SUCESSO
        bases = [tb["texto"] for tb in resultado["textos_base"]]
        uip = next(t for t in bases if t.startswith("Novos dados da União"))
        partes = uip.split("\n\n")
        assert len(partes) == 5
        assert partes[1].startswith("Globalmente, a presença feminina")
        assert partes[4].startswith("Ainda, o mapa de 2025")
        # Enunciado continua numa linha só.
        assert all("\n" not in q["enunciado"] for q in resultado["questoes"])


class TestFigurasVetoriais:
    """5G.3: tabelas e gráficos desenhados com vetores viram figura; o layout
    do caderno (separadores, molduras, fundos brancos) não."""

    @staticmethod
    def _pagina():
        doc = pymupdf.open()
        return doc, doc.new_page(width=595, height=842)

    @staticmethod
    def _tabela(page, x0, y0, x1, y1, linhas=4):
        passo = (y1 - y0) / linhas
        for i in range(linhas + 1):
            page.draw_line((x0, y0 + i * passo), (x1, y0 + i * passo))
        for x in (x0, (x0 + x1) / 2, x1):
            page.draw_line((x, y0), (x, y1))

    def test_tabela_com_grade_vira_uma_figura(self):
        _doc, page = self._pagina()
        self._tabela(page, 310, 380, 560, 460)
        regioes = figuras_vetoriais_da_pagina(page)
        assert len(regioes) == 1
        assert regioes[0].contains(pymupdf.Rect(310, 380, 560, 460))

    def test_layout_do_caderno_e_ignorado(self):
        _doc, page = self._pagina()
        # Separador duplo entre grupos (2 linhas finas, ~4 pt de altura).
        page.draw_line((27, 250), (293, 250))
        page.draw_line((27, 254), (293, 254))
        # Separador vertical de colunas (quase a página inteira).
        page.draw_line((297, 63), (297, 805))
        # Moldura em volta de um bloco de texto, sem traço interno.
        page.draw_rect(pymupdf.Rect(40, 400, 280, 600))
        # Fundo branco sem traço.
        page.draw_rect(pymupdf.Rect(40, 620, 280, 700), color=None, fill=(1, 1, 1))
        # Cabeçalho.
        page.draw_rect(pymupdf.Rect(27, 46, 568, 63), color=None, fill=(0.85,) * 3)
        assert figuras_vetoriais_da_pagina(page) == []

    def test_separador_curto_da_primeira_pagina_nao_engole_a_tabela(self):
        # Faixa "PROVA OBJETIVA" encurta o separador (~79% da altura, abaixo
        # do corte de 80%); o filete do título encostado nele unia a coluna
        # esquerda inteira numa caixa só e a tabela sumia.
        _doc, page = self._pagina()
        page.draw_line((297, 137), (297, 803))
        page.draw_line((27, 150), (296, 150))
        page.draw_line((27, 152), (296, 152))
        self._tabela(page, 105, 189, 214, 292)
        regioes = figuras_vetoriais_da_pagina(page)
        assert len(regioes) == 1
        assert regioes[0].contains(pymupdf.Rect(105, 189, 214, 292))
        assert regioes[0].x1 < 230 and regioes[0].y1 < 310

    def test_regiao_sobre_figura_raster_nao_duplica(self):
        _doc, page = self._pagina()
        self._tabela(page, 310, 380, 560, 460)
        raster = [pymupdf.Rect(300, 370, 570, 470)]
        assert figuras_vetoriais_da_pagina(page, raster) == []

    def test_texto_dentro_da_tabela_nao_e_vizinho(self):
        # Duas tabelas empilhadas depois de um item, comando do grupo
        # seguinte abaixo: as duas são do grupo seguinte (STM_005, itens 65-68).
        linhas = [
            Linha(0, 0, "64 Item anterior.", 310, 360, 560, 370, True),
            Linha(0, 1, "célula da tabela 1", 315, 390, 400, 398, True),
            Linha(0, 2, "célula da tabela 2", 315, 480, 400, 488, True),
            Linha(
                0, 3, "Com base nessas informações, julgue.", 310, 545, 560, 555, True
            ),
        ]
        dono_linha = {
            0: ("item", 64),
            1: ("item", 64),
            2: ("item", 64),
            3: ("preambulo", 7),
        }
        t1 = pymupdf.Rect(309, 382, 561, 462)
        t2 = pymupdf.Rect(309, 469, 561, 538)
        assert dono_da_figura(t1, 0, linhas, dono_linha) == ("item", 64)
        for tabela in (t1, t2):
            dono = dono_da_figura(tabela, 0, linhas, dono_linha, ignorar=[t1, t2])
            assert dono == ("preambulo", 7)

    def test_figura_vetorial_nao_corta_legenda_acima(self):
        # KAN-75: a folga superior (-2 pt) não pode invadir a linha de texto
        # logo acima da tabela (ex.: legenda "Clientes" em BANRISUL Q36).
        _doc, page = self._pagina()
        page.insert_text((350, 242), "Clientes", fontsize=10)
        self._tabela(page, 310, 243.35, 560, 320)
        regioes = figuras_vetoriais_da_pagina(page)
        assert len(regioes) == 1
        words = page.get_text("words")
        clientes_w = [w for w in words if w[4] == "Clientes"][0]
        assert regioes[0].y0 >= clientes_w[3]

    def test_remover_texto_das_tabelas_no_enunciado(self):
        # KAN-75: texto achatado de tabela vetorial vai para texto_tabela
        linhas = [
            Linha(0, 0, "1", 30, 100, 40, 112, True),
            Linha(0, 1, "célula 1 célula 2", 35, 125, 200, 135, True),
            Linha(0, 2, "célula 3 célula 4", 35, 140, 200, 150, True),
            Linha(
                0,
                3,
                "Com base na tabela, julgue o item a seguir.",
                30,
                170,
                280,
                182,
                True,
            ),
        ]
        seg = ResultadoSegmentacao()
        seg.itens[1] = {
            "numero": 1,
            "enunciado": "célula 1 célula 2 célula 3 célula 4 Com base na tabela, julgue o item a seguir.",
            "tipo": "certo_errado",
            "figuras": [
                {
                    "arquivo": "tabela.png",
                    "pagina": 1,
                    "bbox": [30, 120, 210, 155],
                    "origem": "vetorial",
                }
            ],
            "texto_tabela": None,
        }
        for k in range(len(linhas)):
            seg.dono_linha[k] = ("item", 1)

        _remover_texto_das_tabelas(seg, linhas)
        assert seg.itens[1]["texto_tabela"] == "célula 1 célula 2 célula 3 célula 4"
        assert (
            seg.itens[1]["enunciado"] == "Com base na tabela, julgue o item a seguir."
        )

    def test_figura_vetorial_com_legenda_engloba_titulo_e_subtitulo(self):
        # KAN-76: tabela com legenda ("Tabela I" + "Clientes") logo acima:
        # o recorte estende para cima englobando a legenda.
        _doc, page = self._pagina()
        page.insert_text((350, 220), "Tabela I", fontsize=10)
        page.insert_text((350, 235), "Clientes", fontsize=10)
        self._tabela(page, 310, 243.35, 560, 320)
        regioes = figuras_vetoriais_da_pagina(page)
        assert len(regioes) == 1
        words = page.get_text("words")
        tabela_w = [w for w in words if w[4] == "Tabela"][0]
        clientes_w = [w for w in words if w[4] == "Clientes"][0]
        assert regioes[0].y0 <= tabela_w[1]
        assert regioes[0].contains(
            pymupdf.Point(
                (tabela_w[0] + tabela_w[2]) / 2, (tabela_w[1] + tabela_w[3]) / 2
            )
        )
        assert regioes[0].contains(
            pymupdf.Point(
                (clientes_w[0] + clientes_w[2]) / 2, (clientes_w[1] + clientes_w[3]) / 2
            )
        )

        linhas = [
            Linha(0, 0, "1", 30, 100, 40, 112, True),
            Linha(0, 1, "Tabela I", 350, 210, 400, 222, True),
            Linha(0, 2, "Clientes", 350, 225, 400, 237, True),
            Linha(0, 3, "célula 1 célula 2", 320, 250, 450, 260, True),
            Linha(
                0,
                4,
                "Com base na tabela, julgue o item a seguir.",
                30,
                340,
                280,
                352,
                True,
            ),
        ]
        seg = ResultadoSegmentacao()
        seg.itens[1] = {
            "numero": 1,
            "enunciado": "Tabela I Clientes célula 1 célula 2 Com base na tabela, julgue o item a seguir.",
            "tipo": "certo_errado",
            "figuras": [
                {
                    "arquivo": "tabela.png",
                    "pagina": 1,
                    "bbox": [round(v, 1) for v in regioes[0]],
                    "origem": "vetorial",
                }
            ],
            "texto_tabela": None,
        }
        for k in range(len(linhas)):
            seg.dono_linha[k] = ("item", 1)
        _remover_texto_das_tabelas(seg, linhas)
        assert seg.itens[1]["texto_tabela"] == "Tabela I Clientes célula 1 célula 2"
        assert (
            seg.itens[1]["enunciado"] == "Com base na tabela, julgue o item a seguir."
        )

    def test_figura_vetorial_com_paragrafo_acima_nao_engloba(self):
        # KAN-76: texto acima que não começa com palavra-chave (Tabela, Figura...)
        # não pode ser englobado no recorte e deve permanecer no enunciado.
        _doc, page = self._pagina()
        page.insert_text(
            (310, 238),
            "Considerando as informações precedentes, responda:",
            fontsize=10,
        )
        self._tabela(page, 310, 245.0, 560, 320)
        regioes = figuras_vetoriais_da_pagina(page)
        assert len(regioes) == 1
        words = page.get_text("words")
        texto_w = [w for w in words if w[4] == "Considerando"][0]
        assert regioes[0].y0 >= texto_w[3]

    def test_extrair_banrisul_q36_tabelas_e_legendas(self):
        # KAN-76: caso real do BANRISUL (077_BANRISUL_002_01.pdf, Q36).
        # Três tabelas desenhadas com vetores, cada uma com sua legenda acima:
        # Tabela I / Clientes, Tabela II / Pedidos, Tabela III / Resultado.
        # As legendas devem ir para o recorte da imagem e para texto_tabela,
        # deixando o enunciado limpo.
        pdf_path = Path("data/2025/CEBRASPE/BANRISUL/Provas/077_BANRISUL_002_01.pdf")
        if not pdf_path.exists():
            pytest.skip("PDF do BANRISUL não encontrado no ambiente local")
        with open("questoes/077_BANRISUL_002_01.json") as f:
            data = json.load(f)
        gabarito = {q["numero"]: q["gabarito"] for q in data["questoes"]}
        resultado, _auditoria = extrair_caderno_objetivo(
            pdf_path, gabarito, "077_BANRISUL_002_01"
        )
        q36 = next(q for q in resultado["questoes"] if q["numero"] == 36)
        assert q36["enunciado"] == (
            "Com base nas informações nas tabelas I e II, precedentes, "
            "assinale a opção em que são apresentados comandos SQL que permitem "
            "a obtenção do resultado demonstrado na tabela III."
        )
        assert "Tabela I Clientes" in q36["texto_tabela"]
        assert "Tabela II Pedidos" in q36["texto_tabela"]
        assert "Tabela III Resultado" in q36["texto_tabela"]
        assert len(q36["figuras"]) == 3
        # Cada figura teve o topo estendido para englobar a respectiva legenda
        # (originalmente sem legenda: y0 era ~243.2, ~347.9, ~454.1)
        assert q36["figuras"][0]["bbox"][1] < 225.0
        assert q36["figuras"][1]["bbox"][1] < 330.0
        assert q36["figuras"][2]["bbox"][1] < 435.0


GABARITO_STM_005_PAG1 = {
    51: "E", 52: "C", 53: "E", 54: "C", 55: "C", 56: "E", 57: "X", 58: "C",
    59: "E", 60: "C", 61: "C", 62: "E", 63: "C", 64: "E", 65: "C", 66: "E",
    67: "E", 68: "C", 69: "C", 70: "E",
}  # fmt: skip


class TestPreambuloDepoisDoItem:
    """`072_STM_005_01`, item 64: as células da tabela do grupo 65–68 ficam a
    ~17 pt da margem, no recuo de continuação do item (5G.5)."""

    def _extrair(self):
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "072_STM_005_01_pag1.pdf", GABARITO_STM_005_PAG1, "STM5"
        )
        return resultado, {q["numero"]: q for q in resultado["questoes"]}

    def test_preambulo_e_tabela_viram_texto_base_do_grupo_seguinte(self):
        resultado, q = self._extrair()
        assert resultado["status"] == STATUS_SUCESSO
        assert q[64]["enunciado"] == (
            "Pelo custeio variável, cada unidade produzida pela entidade custa "
            "R$ 27 a menos do que pelo custeio por absorção."
        )
        ordem = q[65]["texto_base_ordem"]
        base = resultado["textos_base"][ordem]["texto"]
        assert base.startswith("Da contabilidade de uma entidade hipotética")
        # As duas tabelas viram figura vetorial; o texto das células sai.
        assert "lucro operacional líquido" not in base
        figuras = resultado["textos_base"][ordem]["figuras"]
        assert [f.get("origem") for f in figuras] == ["vetorial", "vetorial"]
        assert all(q[n]["texto_base_ordem"] == ordem for n in (66, 67, 68))
        assert q[65]["secao"].startswith("Com base nessas informações")
        assert "possivel_preambulo_no_item" not in q[64]["alertas"]

    def test_residuo_sem_ruptura_gera_alerta_que_inutiliza_o_item(self, monkeypatch):
        import src.prova_parser as pp

        monkeypatch.setattr(pp, "_ruptura_do_item", lambda *a, **k: None)
        _, q = self._extrair()
        assert "Da contabilidade" in q[64]["enunciado"]
        assert "possivel_preambulo_no_item" in q[64]["alertas"]
        assert not pp.ALERTAS_ITEM_INUTILIZAVEL.isdisjoint(q[64]["alertas"])


class TestTipoDaGrade:
    """O tipo da grade (`GradeGabarito.tipos`) decide C/E × ME; as letras e a
    contagem de "Questão N" só valem sem tipo ou com grade mista."""

    LINHAS_ME = (
        _l("Questão 1"),
        _l("Enunciado.", inicio=False),
        _l("Questão 2"),
        _l("Enunciado.", inicio=False),
    )
    CE, ME = "certo_errado", "multipla_escolha"

    def test_grade_me_so_com_c_e_e_continua_me(self):
        # Prova ME cujas respostas são só C e E: pelas letras seria C/E.
        gabarito = {1: "C", 2: "E"}
        assert _eh_multipla_escolha([], [1, 2], gabarito, {1: self.ME, 2: self.ME})

    def test_grade_ce_nunca_vira_me(self):
        # Caderno C/E com "Questão N" no texto e letra espúria: o rótulo `Item`
        # da grade manda.
        tipos = {1: self.CE, 2: self.CE}
        assert not _eh_multipla_escolha(list(self.LINHAS_ME), [1, 2], {1: "A"}, tipos)

    def test_sem_tipo_ou_mista_cai_nas_letras(self):
        assert _eh_multipla_escolha([], [1, 2], {1: "A", 2: "C"}, None)
        assert not _eh_multipla_escolha([], [1, 2], {1: "C", 2: "E"}, {})
        mista = {1: self.CE, 2: self.ME}
        assert not _eh_multipla_escolha([], [1, 2], {1: "C", 2: "E"}, mista)
        assert _eh_multipla_escolha(list(self.LINHAS_ME), [1, 2], {1: "C"}, mista)
        # Tipo só de parte dos números também não decide.
        assert _eh_multipla_escolha([], [1, 2], {1: "B", 2: "C"}, {1: self.CE})


class TestMultiplaEscolhaSintetico:
    """Testes unitários para cadernos de múltipla escolha sintéticos."""

    def test_localizacao_e_segmentacao_basica_5_alternativas(self):
        linhas = [
            _l("Questão 1"),
            _l("Qual é a capital do Brasil?", inicio=False),
            _l("A ", primeiro_span="A"),
            _l("Brasília.", inicio=False),
            _l("B ", primeiro_span="B"),
            _l("Rio de Janeiro.", inicio=False),
            _l("C ", primeiro_span="C"),
            _l("São Paulo.", inicio=False),
            _l("D ", primeiro_span="D"),
            _l("Salvador.", inicio=False),
            _l("E ", primeiro_span="E"),
            _l("Belo Horizonte.", inicio=False),
        ]
        gabarito = {1: "A"}
        assert _eh_multipla_escolha(linhas, [1], gabarito)
        achados = localizar_questoes_me(linhas, [1])
        assert achados == {1: (0, True)}
        seg = _segmentar_me(linhas, achados)
        assert len(seg.itens) == 1
        item = seg.itens[1]
        assert item["enunciado"] == "Qual é a capital do Brasil?"
        assert item["tipo"] == "multipla_escolha"
        assert len(item["alternativas"]) == 5
        assert [a["letra"] for a in item["alternativas"]] == ["A", "B", "C", "D", "E"]
        assert item["alternativas"][0]["texto"] == "Brasília."
        assert item["alternativas"][4]["texto"] == "Belo Horizonte."

    def test_enunciado_que_comeca_com_artigo_a_nao_e_alternativa(self):
        # SEFA_PR_25, Q24 do cargo 4: a 1ª linha justificada sai com "A " num
        # span próprio, no recuo do parágrafo (56,7 pt); as letras das
        # alternativas ficam na margem (28,3 pt).
        linhas = [
            _l("Questão 24", x0=70.8),
            _l(
                "A atuação do Estado na esfera econômica é", primeiro_span="A ", x0=56.7
            ),
            _l("operacionalizada por políticas econômicas.", x0=28.3, inicio=False),
            _l("Acerca desse assunto, é um exemplo de política comercial", x0=28.3),
            _l("A a redução do IOF", primeiro_span="A", x0=28.3, inicio=False),
            _l("B a fixação da taxa SELIC", primeiro_span="B", x0=28.3, inicio=False),
            _l("C o aumento do subsídio", primeiro_span="C", x0=28.3, inicio=False),
            _l("D a redução do IPI", primeiro_span="D", x0=28.3, inicio=False),
            _l("E cotas de importação", primeiro_span="E", x0=28.3, inicio=False),
        ]
        achados = localizar_questoes_me(linhas, [24])
        item = _segmentar_me(linhas, achados).itens[24]
        assert item["enunciado"].startswith("A atuação do Estado")
        assert item["enunciado"].endswith("política comercial")
        assert [a["texto"] for a in item["alternativas"]] == [
            "a redução do IOF",
            "a fixação da taxa SELIC",
            "o aumento do subsídio",
            "a redução do IPI",
            "cotas de importação",
        ]

    def test_letra_da_alternativa_depois_de_span_em_branco(self):
        # SEFA_PR_25, CG1 Q65: a linha "A $A1." vem com um span " " antes da
        # letra; o primeiro span da linha é o primeiro com texto.
        doc = pymupdf.open()
        page = doc.new_page()
        escritor = pymupdf.TextWriter(page.rect)
        escritor.append((28, 100), " ", font=pymupdf.Font("helv"), fontsize=11)
        escritor.append((31, 100), "A", font=pymupdf.Font("tiro"), fontsize=11)
        escritor.append((42, 100), " $A1.", font=pymupdf.Font("helv"), fontsize=11)
        escritor.write_text(page)
        (linha,) = extrair_linhas(doc)
        assert linha.primeiro_span == "A"
        assert linha.texto.strip() == "A $A1."

    def test_4_alternativas_estilo_parenteses_e_ponto(self):
        linhas = [
            _l("Questão 1"),
            _l("Acerca do tema, assinale a opção correta.", inicio=False),
            _l("A) Opção A.", primeiro_span="A)"),
            _l("B) Opção B.", primeiro_span="B)"),
            _l("C) Opção C.", primeiro_span="C)"),
            _l("D) Opção D.", primeiro_span="D)"),
        ]
        achados = localizar_questoes_me(linhas, [1])
        seg = _segmentar_me(linhas, achados)
        item = seg.itens[1]
        assert len(item["alternativas"]) == 4
        assert [a["letra"] for a in item["alternativas"]] == ["A", "B", "C", "D"]
        assert item["alternativas"][0]["texto"] == "Opção A."

    def test_alternativa_multilinha(self):
        linhas = [
            _l("Questão 1"),
            _l("Enunciado da questão.", inicio=False),
            _l("A Primeira linha da alternativa A,", primeiro_span="A"),
            _l("segunda linha da alternativa A,", inicio=False),
            _l("e terceira linha da alternativa A.", inicio=False),
            _l("B Linha única de B.", primeiro_span="B"),
            _l("C Linha única de C.", primeiro_span="C"),
            _l("D Linha única de D.", primeiro_span="D"),
        ]
        achados = localizar_questoes_me(linhas, [1])
        seg = _segmentar_me(linhas, achados)
        item = seg.itens[1]
        assert (
            item["alternativas"][0]["texto"]
            == "Primeira linha da alternativa A, segunda linha da alternativa A, e terceira linha da alternativa A."
        )

    def test_alternativa_faltando_gera_alerta_bloqueante(self):
        # Questão com apenas 3 alternativas (falta D)
        linhas = [
            _l("Questão 1"),
            _l("Enunciado.", inicio=False),
            _l("A Opção A.", primeiro_span="A"),
            _l("B Opção B.", primeiro_span="B"),
            _l("C Opção C.", primeiro_span="C"),
        ]
        achados = localizar_questoes_me(linhas, [1])
        seg = _segmentar_me(linhas, achados)
        assert any(
            a["tipo"] == "alternativas_invalidas" and a["severidade"] == "bloqueante"
            for a in seg.alertas
        )

    def test_alternativas_nao_consecutivas_gera_alerta_bloqueante(self):
        # Pula a letra C (tem A, B, D, E)
        linhas = [
            _l("Questão 1"),
            _l("Enunciado.", inicio=False),
            _l("A Opção A.", primeiro_span="A"),
            _l("B Opção B.", primeiro_span="B"),
            _l("D Opção D.", primeiro_span="D"),
            _l("E Opção E.", primeiro_span="E"),
        ]
        achados = localizar_questoes_me(linhas, [1])
        seg = _segmentar_me(linhas, achados)
        assert any(
            a["tipo"] == "alternativas_invalidas" and a["severidade"] == "bloqueante"
            for a in seg.alertas
        )

    def test_marcador_duplicado_gera_alerta_bloqueante(self):
        linhas = [
            _l("Questão 1"),
            _l("Enunciado 1.", inicio=False),
            _l("Questão 1"),
            _l("Enunciado duplicado.", inicio=False),
        ]
        alertas: list[dict] = []
        achados = localizar_questoes_me(linhas, [1], alertas=alertas)
        assert 1 not in achados
        assert any(
            a["tipo"] == "marcador_duplicado" and a["severidade"] == "bloqueante"
            for a in alertas
        )

    def test_marcador_fora_de_ordem_gera_alerta_bloqueante(self):
        linhas = [
            _l("Questão 2"),
            _l("Questão 1"),
        ]
        alertas: list[dict] = []
        localizar_questoes_me(linhas, [1, 2], alertas=alertas)
        assert any(
            a["tipo"] == "marcador_fora_de_ordem" and a["severidade"] == "bloqueante"
            for a in alertas
        )

    def test_marcadores_fora_do_gabarito_me(self):
        linhas = [
            _l("Questão 1"),
            _l("Questão 2"),
            _l("Questão 3"),
        ]
        # Gabarito só espera 1 e 2
        extras = marcadores_fora_do_gabarito_me(linhas, [1, 2])
        assert extras == [3]

    @staticmethod
    def _questao(numero, enunciado, letras="ABCDE"):
        linhas = [_l(f"Questão {numero}"), _l(enunciado, inicio=False)]
        for letra in letras:
            linhas.append(_l(f"{letra} Opção {letra}{numero}.", primeiro_span=letra))
        return linhas

    @pytest.mark.parametrize(
        "texto",
        [
            "Texto CB1A1",
            "Texto CB1A3-II",
            "Texto 1A3",
            "Text CB1A2",
            "Textos CG1A1-I e CG1A1-II",
        ],
    )
    def test_rotulo_de_texto_real_casa(self, texto):
        assert PADRAO_TEXTO_ROTULO_ME.match(texto)

    @pytest.mark.parametrize(
        "texto", ["text CB1A2.", "Texto de apoio", "Texto CB1A1 Podemos atribuir"]
    )
    def test_linha_que_nao_e_rotulo_de_texto(self, texto):
        assert not PADRAO_TEXTO_ROTULO_ME.match(texto)

    def test_rotulo_texto_no_meio_da_secao_vira_texto_base(self):
        # BANRISUL Q19-Q24: "Texto CB1A3-I" depois da alternativa E de Q19.
        linhas = (
            [_l("RACIOCÍNIO LÓGICO")]
            + self._questao(1, "Questão sem texto.")
            + [
                _l("Texto XY1A3-I"),
                _l("Em determinado setor, trabalham 80 pessoas.", inicio=False),
            ]
            + self._questao(2, "Considere o texto XY1A3-I e assinale.")
            + self._questao(3, "Outra questão, sem texto.")
            + [
                _l("Texto XY1A3-II"),
                _l("Uma tabela com 5 colunas.", inicio=False),
            ]
            + self._questao(4, "Com base no texto XY1A3-I, assinale.")
            + self._questao(5, "Questão com enunciado próprio.")
        )
        achados = localizar_questoes_me(linhas, [1, 2, 3, 4, 5])
        seg = _segmentar_me(linhas, achados)
        assert [tb["texto"] for tb in seg.textos_base] == [
            "Texto XY1A3-I Em determinado setor, trabalham 80 pessoas.",
            "Texto XY1A3-II Uma tabela com 5 colunas.",
        ]
        assert seg.itens[1]["alternativas"][4]["texto"] == "Opção E1."
        assert seg.itens[3]["alternativas"][4]["texto"] == "Opção E3."
        assert {n: i["texto_base_ordem"] for n, i in seg.itens.items()} == {
            1: None,
            2: 0,  # logo depois do texto
            3: None,  # não cita: o texto do meio da seção não vale para ela
            4: 0,  # cita XY1A3-I, mesmo depois do XY1A3-II
            5: None,
        }
        assert all(i["secao"] == "RACIOCÍNIO LÓGICO" for i in seg.itens.values())

    def test_texto_que_abre_a_secao_vale_ate_a_proxima_secao(self):
        linhas = (
            [
                _l("LÍNGUA PORTUGUESA"),
                _l("Texto CG1A1"),
                _l("Onde não houver alimento, não haverá paz.", inicio=False),
            ]
            + self._questao(1, "Infere-se do texto CG1A1 que")
            + self._questao(2, "Com base no Manual de Redação, assinale.")
            + [_l("LEGISLAÇÃO")]
            + self._questao(3, "À luz da lei, assinale.")
        )
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [1, 2, 3]))
        assert len(seg.textos_base) == 1
        assert [seg.itens[n]["texto_base_ordem"] for n in (1, 2, 3)] == [0, 0, None]
        assert seg.itens[2]["alternativas"][4]["texto"] == "Opção E2."
        assert seg.itens[3]["secao"] == "LEGISLAÇÃO"

    def test_cabecalho_de_secao_quebrado_depois_de_conectivo(self):
        # SEFA_PR_25 CG1: a 2ª linha do cabeçalho virava texto-base.
        assert _processar_preambulo_me(
            [_l("NOÇÕES DE CONTABILIDADE APLICADA AO"), _l("SETOR PÚBLICO (CASP)")]
        ) == ("NOÇÕES DE CONTABILIDADE APLICADA AO SETOR PÚBLICO (CASP)", None)
        # Sem conectivo no fim, a linha de baixo não é continuação.
        secao, base = _processar_preambulo_me(
            [_l("LEGISLAÇÃO"), _l("TEXTO EM CAIXA ALTA")]
        )
        assert secao == "LEGISLAÇÃO"
        assert [l.texto for l in base] == ["TEXTO EM CAIXA ALTA"]

    def test_area_do_caderno_especifico_e_secao_nao_texto_base(self):
        # SEFA_PR_25 P2: "CONTABILIDADE" sozinha antes da 1ª questão virava o
        # texto-base das 50 questões do caderno.
        assert _processar_preambulo_me([_l("CONTABILIDADE"), _l(" ")]) == (
            "CONTABILIDADE",
            None,
        )
        # Linha com minúscula ou rótulo de texto continua texto-base.
        for texto in ("Texto 1A3", "O secretário afirmou que"):
            secao, base = _processar_preambulo_me([_l(texto)])
            assert secao is None
            assert [l.texto for l in base] == [texto]

    def test_preambulo_so_com_linha_vazia_nao_cria_texto_base(self):
        assert _processar_preambulo_me([_l("LEGISLAÇÃO"), _l("  ")]) == (
            "LEGISLAÇÃO",
            None,
        )
        assert _processar_preambulo_me([_l(" ")]) == (None, None)

    def test_artigo_a_no_enunciado_nao_e_alternativa(self):
        # Reserva (letra no span do texto): "A respeito ..." não é a
        # alternativa A, mesmo abrindo bloco na margem da coluna.
        linhas = [
            _l("Questão 1"),
            _l("A respeito do tema, assinale a opção correta."),
            _l("A) Opção A."),
            _l("B) Opção B."),
            _l("C) Opção C."),
            _l("D) Opção D."),
        ]
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [1]))
        item = seg.itens[1]
        assert item["enunciado"] == "A respeito do tema, assinale a opção correta."
        assert [a["texto"] for a in item["alternativas"]] == [
            "Opção A.",
            "Opção B.",
            "Opção C.",
            "Opção D.",
        ]
        assert not seg.alertas

    def test_linha_quebrada_em_minuscula_nao_e_cabecalho_de_secao(self):
        linhas = (
            [_l("LEGISLAÇÃO")]
            + self._questao(1, "Assinale a opção correta.", letras="ABCD")
            + [
                _l("E Os atos administrativos devem observar a", primeiro_span="E"),
                _l("legislação vigente.", inicio=False, x0=42),
            ]
            + self._questao(2, "Assinale a opção correta.", letras="ABC")
            + [
                _l("D O cargo exige", primeiro_span="D"),
                _l("conhecimentos técnicos específicos.", inicio=False, x0=42),
            ]
        )
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [1, 2]))
        assert seg.itens[1]["alternativas"][4]["texto"] == (
            "Os atos administrativos devem observar a legislação vigente."
        )
        assert seg.itens[2]["alternativas"][3]["texto"] == (
            "O cargo exige conhecimentos técnicos específicos."
        )
        assert seg.itens[2]["secao"] == "LEGISLAÇÃO"
        assert not seg.textos_base

    def test_ruido_tira_codigo_de_controle_me_e_mantem_tag_html(self):
        linhas = [
            _l("-- CONHECIMENTOS ESPECÍFICOS --"),
            _l("<html>"),
            _l("<SEFAPR177001A01E2977>"),
            _l("<DIV>"),
            _l("<SEBRAE_26_PSE_1169CG1A01E1035>"),
            _l("<sefapr177001a01e2977>"),
        ]
        restantes, _ = remover_ruido(linhas)
        assert [linha.texto for linha in restantes] == [
            "<html>",
            "<DIV>",
            "<sefapr177001a01e2977>",
        ]

    def test_ce_mantem_retrocompatibilidade_com_tipo_e_alternativas_none(
        self, grade_pf_cb1
    ):
        # Testa se caderno CE mantém tipo='certo_errado' e alternativas=None
        gabarito = _gabarito(grade_pf_cb1, range(15, 28))
        resultado, _ = extrair_caderno_objetivo(
            FIXTURES / "094_PF_CB1_01_pag2.pdf", gabarito, "CE_TEST"
        )
        assert resultado["status"] == STATUS_SUCESSO
        for q in resultado["questoes"]:
            assert q["tipo"] == "certo_errado"
            assert q["alternativas"] is None


DATA_AMOSTRA = Path(__file__).parent.parent / "data" / "inventario_amostra"


def _linha_caderno(texto, x0, x1, negrito=False, primeiro_span=None, inicio=True):
    """Linha com as coordenadas reais dos cadernos ME (x0/x1 medidos nos PDFs)."""
    return Linha(
        pagina=0,
        bloco=1,
        texto=texto,
        x0=x0,
        y0=0,
        x1=x1,
        y1=10,
        inicio_bloco=inicio,
        primeiro_span=primeiro_span if primeiro_span is not None else texto,
        negrito=negrito,
    )


def _questao_coluna_direita(numero, letras="ABCDE"):
    """Questão na coluna da direita (margem 304.3, como o BANRISUL_002)."""
    linhas = [
        _linha_caderno(f"Questão {numero}", 304.3, 500.0),
        _linha_caderno(f"Enunciado da questão {numero}.", 304.3, 569.5, inicio=False),
    ]
    for letra in letras:
        linhas.append(
            _linha_caderno(
                f"{letra} Opção {letra}{numero}.",
                304.3,
                420.0,
                primeiro_span=letra,
            )
        )
    return linhas


class TestCabecalhoDeLayoutME:
    """Cabeçalho de matéria centralizado no meio do caderno ME (8.C, C1a H4c).
    Coordenadas de linhas reais: BANRISUL_002 (coluna direita, margem 304.3) e
    SEFA_PR CG1 (coluna esquerda, margem 28.4)."""

    def test_banco_de_dados_no_topo_da_coluna_fecha_a_alternativa_e(self):
        # BANRISUL_002, Q34 -> Q35: "BANCO DE DADOS" centralizado (391.4-483.9)
        # sem palavra-chave; antes ficava colado no fim da alternativa E de Q34.
        linhas = (
            [_linha_caderno("LÍNGUA PORTUGUESA", 304.3, 480.0, negrito=True)]
            + _questao_coluna_direita(34)
            + [_linha_caderno("BANCO DE DADOS", 391.4, 483.9, inicio=True)]
            + _questao_coluna_direita(35)
        )
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [34, 35]))
        assert seg.itens[34]["alternativas"][4]["texto"] == "Opção E34."
        assert seg.itens[35]["secao"] == "BANCO DE DADOS"
        assert seg.itens[34]["secao"] == "LÍNGUA PORTUGUESA"
        assert not seg.textos_base
        assert not seg.alertas

    def test_materia_em_negrito_na_coluna_esquerda_vira_secao(self):
        # SEFA_PR CG1, Q30 -> Q31: "MATEMÁTICA FINANCEIRA" (91.8-230.5, negrito).
        linhas = [
            _linha_caderno("RACIOCÍNIO LÓGICO E MATEMÁTICO", 340.4, 531.9, negrito=True)
        ]
        for n, letras in ((30, "ABCDE"), (31, "ABCDE")):
            linhas.append(_linha_caderno(f"Questão {n}", 28.4, 290.0))
            linhas.append(_linha_caderno(f"Enunciado {n}.", 28.4, 293.6, inicio=False))
            for letra in letras:
                linhas.append(
                    _linha_caderno(
                        f"{letra} Opção {letra}{n}.",
                        28.4,
                        200.0,
                        primeiro_span=letra,
                    )
                )
            if n == 30:
                linhas.append(
                    _linha_caderno("MATEMÁTICA FINANCEIRA", 91.8, 230.5, negrito=True)
                )
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [30, 31]))
        assert seg.itens[30]["alternativas"][4]["texto"] == "Opção E30."
        assert seg.itens[31]["secao"] == "MATEMÁTICA FINANCEIRA"

    def test_cabecalho_de_duas_linhas_com_sigla_vira_uma_secao(self):
        # SEFA_PR CG1, Q40: "ADMINISTRAÇÃO FINANCEIRA E" + "ORÇAMENTÁRIA (AFO)".
        linhas = [
            _linha_caderno("ADMINISTRAÇÃO FINANCEIRA E", 354.2, 522.6, negrito=True),
            _linha_caderno("ORÇAMENTÁRIA (AFO)", 378.2, 494.1, negrito=True),
            _linha_caderno("Questão 40", 304.3, 500.0),
            _linha_caderno("Enunciado da questão 40.", 304.3, 569.5, inicio=False),
        ]
        linhas += _questao_coluna_direita(40)[2:]
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [40]))
        assert seg.itens[40]["secao"] == "ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA (AFO)"
        assert not seg.textos_base

    def test_titulo_que_atravessa_as_colunas_vira_secao(self):
        # BANRISUL_004, Q76 -> Q77: "INOVAÇÃO EM TI NO SISTEMA FINANCEIRO" fica
        # centralizado na largura do texto (190.2-411.9), não numa coluna.
        linhas = [_linha_caderno("GESTÃO E GOVERNANÇA", 340.0, 530.0, negrito=True)]
        linhas += _questao_coluna_direita(76)
        linhas.append(
            _linha_caderno("INOVAÇÃO EM TI NO SISTEMA FINANCEIRO", 190.2, 411.9)
        )
        linhas += _questao_coluna_direita(77)
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [76, 77]))
        assert seg.itens[76]["alternativas"][4]["texto"] == "Opção E76."
        assert seg.itens[77]["secao"] == "INOVAÇÃO EM TI NO SISTEMA FINANCEIRO"

    def test_processar_preambulo_aceita_cabecalho_de_layout(self):
        assert _processar_preambulo_me(
            [
                _linha_caderno(
                    "ADMINISTRAÇÃO FINANCEIRA E", 354.2, 522.6, negrito=True
                ),
                _linha_caderno("ORÇAMENTÁRIA (AFO)", 378.2, 494.1, negrito=True),
            ]
        ) == ("ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA (AFO)", None)

    def test_cabecalho_de_layout_precisa_de_centro_ou_negrito_e_afastamento(self):
        # Centralizada e em caixa alta: vale.
        assert _eh_cabecalho_layout_me(_linha_caderno("BANCO DE DADOS", 391.4, 483.9))
        assert (
            _eh_cabecalho_layout_me(_linha_caderno("CASP (AFO)", 300.0, 340.0)) is False
        )
        # Caixa alta na margem, sem negrito, não é cabeçalho.
        assert not _eh_cabecalho_layout_me(
            _linha_caderno("SELECT NOME FROM TABELA", 304.3, 480.0)
        )
        # Ocupa a coluna inteira (centro na coluna, mas colada na margem).
        assert not _eh_cabecalho_layout_me(
            _linha_caderno("ORDER BY NOME, IDADE, CODIGO", 304.3, 569.5)
        )
        # Dígito, código ou aspas nunca: nem centralizada nem em negrito.
        for texto in ("CB1A3 BANCO", "SUM() COUNT()", "SELECT * FROM", "X = Y CASO"):
            assert not _eh_cabecalho_layout_me(
                _linha_caderno(texto, 391.4, 483.9, negrito=True)
            ), texto

    def test_continuacao_de_alternativa_em_caixa_alta_na_margem_nao_corta(self):
        # Alternativa E com código SQL em caixa alta na margem, ainda antes da
        # questão seguinte: fica na alternativa E (não vira seção).
        linhas = (
            [_linha_caderno("CONHECIMENTOS DE INFORMÁTICA", 304.3, 480.0, negrito=True)]
            + [_linha_caderno("Questão 1", 304.3, 500.0)]
            + [_linha_caderno("Enunciado da questão 1.", 304.3, 569.5, inicio=False)]
            + [
                _linha_caderno("A SUM()", 304.3, 348.0, primeiro_span="A"),
                _linha_caderno("B AVG()", 304.3, 348.0, primeiro_span="B"),
                _linha_caderno("C MIN()", 304.3, 348.0, primeiro_span="C"),
                _linha_caderno("D MAX()", 304.3, 348.0, primeiro_span="D"),
                _linha_caderno("E COUNT()", 304.3, 358.8, primeiro_span="E"),
                _linha_caderno("ORDER BY NOME", 304.3, 380.0, inicio=False),
                _linha_caderno("SELECT NOME FROM TABELA", 304.3, 480.0, inicio=False),
            ]
            + [_linha_caderno("Questão 2", 304.3, 500.0)]
            + [_linha_caderno("Enunciado da questão 2.", 304.3, 569.5, inicio=False)]
            + [
                _linha_caderno(
                    f"{letra} Opção {letra}2.", 304.3, 420.0, primeiro_span=letra
                )
                for letra in "ABCDE"
            ]
        )
        seg = _segmentar_me(linhas, localizar_questoes_me(linhas, [1, 2]))
        assert seg.itens[1]["alternativas"][4]["texto"] == (
            "COUNT() ORDER BY NOME\nSELECT NOME FROM TABELA"
        )
        assert seg.itens[2]["secao"] == "CONHECIMENTOS DE INFORMÁTICA"
        assert not seg.alertas


class TestCadernosMEReais:
    """Validação com os 3 PDFs reais de inventario_amostra (Etapa 8.M — Task 3)."""

    def test_banrisul_30_itens_5_alternativas(self):
        pdf = DATA_AMOSTRA / "BANRISUL_25_077_BANRISUL_CB1_01.pdf"
        gab = DATA_AMOSTRA / "Gab_BANRISUL_25_CB1.pdf"
        if not pdf.exists() or not gab.exists():
            pytest.skip("PDF de amostra BANRISUL não encontrado")

        lida = ler_grade(gab)
        grade = lida.respostas
        resultado, auditoria = extrair_caderno_objetivo(
            pdf, grade, "BANRISUL", tipos=lida.tipos
        )

        assert resultado["status"] == STATUS_SUCESSO
        assert resultado["itens_esperados"] == 30
        assert resultado["itens_extraidos"] == 30
        assert resultado["itens_faltando"] == []
        assert resultado["itens_fora_do_gabarito"] == []
        assert len(resultado["questoes"]) == 30
        assert len(resultado["textos_base"]) >= 3

        for q in resultado["questoes"]:
            assert q["tipo"] == "multipla_escolha"
            assert len(q["alternativas"]) == 5
            assert [a["letra"] for a in q["alternativas"]] == ["A", "B", "C", "D", "E"]
            assert q["enunciado"].strip()
            assert not q["enunciado"].startswith("Questão")
            assert q["gabarito"] == grade[q["numero"]]
            assert q["anulada"] == (grade[q["numero"]] == "X")

    def test_sebrae_15_itens_4_alternativas(self):
        pdf = (
            DATA_AMOSTRA
            / "SEBRAE_26_PSE_1_2F270C9D0984DBDB129163E0C92DDE43057DFC1637D6342D91B41790C26EAB2E.pdf"
        )
        gab = DATA_AMOSTRA / "Gab_SEBRAE_26_TIPO2.pdf"
        if not pdf.exists() or not gab.exists():
            pytest.skip("PDF de amostra SEBRAE não encontrado")

        lida = ler_grade(gab)
        grade = lida.respostas
        resultado, auditoria = extrair_caderno_objetivo(
            pdf, grade, "SEBRAE", tipos=lida.tipos
        )

        assert resultado["status"] == STATUS_SUCESSO
        assert resultado["itens_esperados"] == 15
        assert resultado["itens_extraidos"] == 15
        assert resultado["itens_faltando"] == []
        assert resultado["itens_fora_do_gabarito"] == []
        assert len(resultado["questoes"]) == 15
        assert len(resultado["textos_base"]) >= 1

        for q in resultado["questoes"]:
            assert q["tipo"] == "multipla_escolha"
            assert len(q["alternativas"]) == 4
            assert [a["letra"] for a in q["alternativas"]] == ["A", "B", "C", "D"]
            assert q["enunciado"].strip()
            assert not q["enunciado"].startswith("Questão")
            assert q["gabarito"] == grade[q["numero"]]
            assert q["anulada"] == (grade[q["numero"]] == "X")

    def test_sefa_pr_50_itens_5_alternativas(self):
        pdf = (
            DATA_AMOSTRA
            / "SEFA_PR_25_90ECB71259732E8F2E4407EDA63B6754CADD1809D7F1A2741FB1422320521691.pdf"
        )
        gab = DATA_AMOSTRA / "Gab_SEFA_PR_25_CARGO1.pdf"
        if not pdf.exists() or not gab.exists():
            pytest.skip("PDF de amostra SEFA_PR não encontrado")

        lida = ler_grade(gab)
        grade = lida.respostas
        resultado, auditoria = extrair_caderno_objetivo(
            pdf, grade, "SEFA_PR", tipos=lida.tipos
        )

        assert resultado["status"] == STATUS_SUCESSO
        assert resultado["itens_esperados"] == 50
        assert resultado["itens_extraidos"] == 50
        assert resultado["itens_faltando"] == []
        assert resultado["itens_fora_do_gabarito"] == []
        assert len(resultado["questoes"]) == 50
        assert len(resultado["textos_base"]) >= 1

        # Item 4 é anulado (gabarito X)
        assert grade[4] == "X"
        q4 = next(q for q in resultado["questoes"] if q["numero"] == 4)
        assert q4["gabarito"] == "X"
        assert q4["anulada"] is True

        for q in resultado["questoes"]:
            assert q["tipo"] == "multipla_escolha"
            assert len(q["alternativas"]) == 5
            assert [a["letra"] for a in q["alternativas"]] == ["A", "B", "C", "D", "E"]
            assert q["enunciado"].strip()
            assert not q["enunciado"].startswith("Questão")
            assert q["gabarito"] == grade[q["numero"]]
            assert q["anulada"] == (grade[q["numero"]] == "X")

    # Conferido no PDF: rótulos "Texto ..."/"Text ..." de cada caderno, quais
    # questões os usam (todas citam o rótulo, salvo BANRISUL Q10, que fica
    # com o texto que abre a seção de Língua Portuguesa) e as figuras reais
    # (sem os selos "Questão N" nem a faixa da prova).
    ESPERADO_ME = {
        "BANRISUL": {
            "pdf": "BANRISUL_25_077_BANRISUL_CB1_01.pdf",
            "gabarito": "Gab_BANRISUL_25_CB1.pdf",
            "textos": {
                "CB1A1": set(range(1, 11)),
                "CB1A2": set(range(11, 16)),
                "CB1A3-I": {20, 21},
                "CB1A3-II": {23, 24},
            },
            "figuras_por_questao": {16: 1, 26: 1},
            "figuras_por_texto": {"CB1A3-II": 1},
        },
        "SEBRAE": {
            "pdf": "SEBRAE_26_PSE_1_2F270C9D0984DBDB129163E0C92DDE43057DFC1637D6342D91B41790C26EAB2E.pdf",
            "gabarito": "Gab_SEBRAE_26_TIPO2.pdf",
            "textos": {"CG1A1": set(range(1, 11))},
            "figuras_por_questao": {},
            "figuras_por_texto": {},
        },
        "SEFA_PR": {
            "pdf": "SEFA_PR_25_90ECB71259732E8F2E4407EDA63B6754CADD1809D7F1A2741FB1422320521691.pdf",
            "gabarito": "Gab_SEFA_PR_25_CARGO1.pdf",
            "textos": {"1A3": {26, 27}},
            "figuras_por_questao": {},
            "figuras_por_texto": {},
        },
    }
    ROTULO_NO_TEXTO_BASE = re.compile(r"Text(?:os?|s)? (\S+)")
    CITA_ROTULO = re.compile(
        r"\b[Tt]ext(?:os?|s)?\s+([A-Z0-9]*\d[A-Z0-9]*(?:-[IVX]+)?)\b"
    )
    PROIBIDO_NA_ALTERNATIVA = re.compile(
        r"(?:^|\s)Text(?:os?|s)?\s+[A-Z0-9]*\d|\bQuest[ãa]o\s+\d+|Espaço livre"
    )

    @staticmethod
    @cache
    def _extrair(nome):
        esperado = TestCadernosMEReais.ESPERADO_ME[nome]
        pdf = DATA_AMOSTRA / esperado["pdf"]
        gab = DATA_AMOSTRA / esperado["gabarito"]
        if not pdf.exists() or not gab.exists():
            pytest.skip(f"PDF de amostra {nome} não encontrado")
        resultado, _ = extrair_caderno_objetivo(pdf, ler_grade(gab).respostas, nome)
        return resultado

    @pytest.mark.parametrize("nome", sorted(ESPERADO_ME))
    def test_textos_base_nao_vazios_e_contagem_exata(self, nome):
        resultado = self._extrair(nome)
        textos = resultado["textos_base"]
        assert all(tb["texto"].strip() for tb in textos)
        rotulos = [self.ROTULO_NO_TEXTO_BASE.match(tb["texto"]) for tb in textos]
        assert all(rotulos), [tb["texto"][:40] for tb in textos]
        assert [m.group(1) for m in rotulos] == list(self.ESPERADO_ME[nome]["textos"])

    @pytest.mark.parametrize("nome", sorted(ESPERADO_ME))
    def test_alternativa_sem_rotulo_de_texto_nem_marcador(self, nome):
        for q in self._extrair(nome)["questoes"]:
            for alt in q["alternativas"]:
                assert not self.PROIBIDO_NA_ALTERNATIVA.search(alt["texto"]), (
                    q["numero"],
                    alt["letra"],
                    alt["texto"][:120],
                )

    @pytest.mark.parametrize("nome", sorted(ESPERADO_ME))
    def test_questao_que_cita_texto_aponta_para_ele(self, nome):
        resultado = self._extrair(nome)
        rotulo_de = {
            tb["ordem"]: self.ROTULO_NO_TEXTO_BASE.match(tb["texto"]).group(1)
            for tb in resultado["textos_base"]
        }
        citacoes = 0
        for q in resultado["questoes"]:
            citados = self.CITA_ROTULO.findall(q["enunciado"])
            if not citados:
                continue
            citacoes += 1
            assert q["texto_base_ordem"] is not None, q["numero"]
            assert rotulo_de[q["texto_base_ordem"]] == citados[0], q["numero"]
        assert citacoes > 0
        # Mapa completo: quem não está em nenhum texto fica sem texto-base.
        usa = {
            q["numero"]: rotulo_de.get(q["texto_base_ordem"])
            for q in resultado["questoes"]
        }
        esperado = {
            n: rotulo
            for rotulo, numeros in self.ESPERADO_ME[nome]["textos"].items()
            for n in numeros
        }
        assert usa == {n: esperado.get(n) for n in usa}

    @pytest.mark.parametrize("nome", sorted(ESPERADO_ME))
    def test_selo_da_questao_nao_vira_figura(self, nome):
        resultado = self._extrair(nome)
        esperado = self.ESPERADO_ME[nome]
        assert {
            q["numero"]: len(q["figuras"])
            for q in resultado["questoes"]
            if q["figuras"]
        } == esperado["figuras_por_questao"]
        assert {
            self.ROTULO_NO_TEXTO_BASE.match(tb["texto"]).group(1): len(tb["figuras"])
            for tb in resultado["textos_base"]
            if tb["figuras"]
        } == esperado["figuras_por_texto"]


class TestFormulaPerdida:
    """`135_SEFAPR_005_01` (SEFA_PR_25, seção ESTATÍSTICA): o `ToUnicode`
    embutido no PDF mapeia a maioria dos glifos da equação (fonte Cambria
    Math) para espaço (`U+0020`) — confirmado com `get_text("rawdict")`, o
    char já chega como `" "` antes de qualquer processamento nosso. O texto
    sai como `( )`/`( ) ( )` vazio, sem `simbolo_ilegivel` (não é `�`) e
    sem figura (não é imagem). `formula_perdida` cobre esse buraco."""

    TEXTOS_PERDIDOS_REAIS = [
        # Enunciados reais de 135_SEFAPR_005_01 (questões 4, 5, 9, 10, 12, 15).
        "Caso uma variável aleatória contínua cuja função de densidade de "
        "probabilidade seja dada pela expressão ( ) { ( ) ( ) em que A é "
        "uma constante positiva, então a probabilidade P(Y < 0,5) é igual a",
        "Se for uma variável aleatória contínua tal que ( ) ( √ ), para , "
        "e ( ) , para , então a função de densidade de probabilidade de "
        "para será dada pela expressão",
        "Em uma entidade pública, em que o número de processos instruídos "
        "para determinada finalidade segue uma distribuição condicional na "
        "forma ( ) . / ( ) na qual * + e segue uma distribuição uniforme",
        "Se , - , em que segue uma distribuição exponencial, então a "
        "probabilidade condicional ( ) será igual a",
        "Com base nas informações do texto 5A1, é correto afirmar que a "
        "( )√ razão tem variância",
        "Se ( ), então ( ) ( ) ( ) ( ) é igual a",
        # Questão 13: a fórmula inteira sumiu sem deixar parênteses.
        "No texto 5A1, o valor esperado de é igual a",
    ]

    # Falsos-positivos medidos na base inteira (3.449 questões): código com
    # parênteses vazios grudados no identificador, sem espaço dentro.
    TEXTOS_CODIGO_REAIS = [
        "if(s.length() == 0 || s.length() == 1) return true;",  # 072_STM_003_01 #86
        "HttpRequest.newBuilder()",  # 072_STM_003_01 #87
        "RANK() OVER (...) AS rank, DENSE_RANK() OVER (...), ROW_NUMBER()",  # 077_BANRISUL_001_01 #59
        "SUM(), AVG(), MIN(), MAX(), COUNT()",  # 077_BANRISUL_002_01 #35
        'public virtual void GetInfo(){ Console.WriteLine($"Nome"); }',  # 077_BANRISUL_002_01 #45
        "public String getNome() { return nome; }",  # 077_BANRISUL_002_01 #46
        "consultarSaldo() {}",  # 077_BANRISUL_002_01 #69
        "for pessoa, dados in prisao.items():",  # 094_PF_005_01 #113
    ]

    def test_detector_pega_formula_apagada_sem_pegar_codigo(self):
        import src.prova_parser as pp

        for texto in self.TEXTOS_PERDIDOS_REAIS:
            assert pp.PADRAO_FORMULA_PERDIDA.search(texto), texto
        for texto in self.TEXTOS_CODIGO_REAIS:
            assert not pp.PADRAO_FORMULA_PERDIDA.search(texto), texto

    def test_alerta_formula_perdida_e_item_inutilizavel(self, tmp_path, monkeypatch):
        import src.prova_parser as pp

        assert "formula_perdida" in pp.ALERTAS_ITEM_INUTILIZAVEL

        linhas = [
            _linha_caderno("ESTATÍSTICA", 304.3, 500.0),
            _linha_caderno("Questão 1", 304.3, 500.0),
            _linha_caderno(
                "Se ( ), então ( ) ( ) ( ) ( ) é igual a",
                304.3,
                569.5,
                inicio=False,
            ),
        ]
        for letra, texto in zip("ABCDE", ["4.", "3.", "2.", "1.", "0."]):
            linhas.append(
                _linha_caderno(f"{letra} {texto}", 304.3, 420.0, primeiro_span=letra)
            )
        monkeypatch.setattr(pp, "extrair_linhas", lambda doc: linhas)

        doc = pymupdf.open()
        doc.new_page()
        pdf_path = tmp_path / "caderno.pdf"
        doc.save(pdf_path)
        doc.close()

        resultado, _ = extrair_caderno_objetivo(pdf_path, {1: "A"}, "TESTE")
        assert resultado["status"] == STATUS_SUCESSO
        q1 = resultado["questoes"][0]
        assert "formula_perdida" in q1["alertas"]
        assert not pp.ALERTAS_ITEM_INUTILIZAVEL.isdisjoint(q1["alertas"])
