"""Testes da CLI de curadoria e relatório visual de classificação (Etapa 5D)."""

from pathlib import Path

import pytest

from scripts import curar_classificacao, gerar_relatorio_classificacao
from src import arvore as arv_mod
from src import classificacao as classif_mod


@pytest.fixture
def ambiente_classificacao(tmp_path: Path):
    """Monta um ambiente isolado com árvore, arquivo canônico de classificação e pasta de revisão."""
    # 1. Árvore mestre
    arv = arv_mod.ArvoreMestre()
    arv_mod.criar_no(
        arv, "materia", "DIREITO CONSTITUCIONAL", None, id_override="M-CONST"
    )
    arv_mod.criar_no(
        arv, "assunto", "Poder Legislativo", "M-CONST", id_override="A-LEG"
    )
    arv_mod.criar_no(
        arv, "subassunto", "Processo Legislativo", "A-LEG", id_override="S-PROC"
    )
    arv_mod.criar_no(
        arv, "subassunto", "Comissões Parlamentares", "A-LEG", id_override="S-CPI"
    )

    arv_path = tmp_path / "arvore.json"
    arv_mod.salvar(arv, arv_path)

    # 2. Classificação canônica
    cq = classif_mod.ClassificacaoQuestoes()
    # Q1: Alta confiança (caderno 001)
    classif_mod.mapear_questao(
        cq,
        arv,
        chave="PF_25_ADM|001_PF_01|1",
        hash_enunciado="hash_q1",
        nos=["S-PROC"],
        confianca="alta",
        origem="llm",
        status="proposto",
    )
    # Q2: Média confiança (caderno 001)
    classif_mod.mapear_questao(
        cq,
        arv,
        chave="PF_25_ADM|001_PF_01|2",
        hash_enunciado="hash_q2",
        nos=["A-LEG"],
        confianca="media",
        origem="llm",
        status="proposto",
    )
    # Q3: Baixa confiança (caderno 002)
    classif_mod.mapear_questao(
        cq,
        arv,
        chave="PF_25_ADM|002_PF_02|3",
        hash_enunciado="hash_q3",
        nos=["S-CPI"],
        confianca="baixa",
        origem="llm",
        status="proposto",
    )
    # Q4: Sem nó (caderno 002)
    classif_mod.mapear_questao(
        cq,
        arv,
        chave="PF_25_ADM|002_PF_02|4",
        hash_enunciado="hash_q4",
        nos=[],
        origem="llm",
        status="proposto",
    )

    classif_path = tmp_path / "classificacao_questoes.json"
    classif_mod.salvar(cq, classif_path)

    # 3. Diretório de revisão
    revisao_dir = tmp_path / "revisao_piloto"
    revisao_dir.mkdir(parents=True, exist_ok=True)

    def rodar(*args):
        return curar_classificacao.main(
            [
                *args,
                "--classificacao",
                str(classif_path),
                "--arvore",
                str(arv_path),
                "--revisao-dir",
                str(revisao_dir),
            ]
        )

    return arv_path, classif_path, revisao_dir, rodar


def test_mapear_questao_manual(ambiente_classificacao):
    _, classif_path, revisao_dir, rodar = ambiente_classificacao

    # Mapear a Q4 (que era sem_no) para S-PROC
    assert rodar("--mapear", "PF_25_ADM|002_PF_02|4:S-PROC") == 0

    cq = classif_mod.carregar(classif_path)
    reg = cq.registros["PF_25_ADM|002_PF_02|4"]
    assert not reg.sem_no
    assert len(reg.apontamentos) == 1
    assert reg.apontamentos[0].no_id == "S-PROC"
    assert reg.apontamentos[0].origem == "humano"
    assert reg.apontamentos[0].status == "aprovado"

    # Relatório HTML gerado automaticamente
    assert (revisao_dir / "relatorio" / "classificacao.html").exists()


def test_aprovar_e_rejeitar_apontamento(ambiente_classificacao):
    _, classif_path, _, rodar = ambiente_classificacao

    # Aprovar Q1
    assert rodar("--aprovar", "PF_25_ADM|001_PF_01|1:S-PROC") == 0
    cq = classif_mod.carregar(classif_path)
    assert cq.registros["PF_25_ADM|001_PF_01|1"].apontamentos[0].status == "aprovado"

    # Rejeitar Q3
    assert rodar("--rejeitar", "PF_25_ADM|002_PF_02|3:S-CPI") == 0
    cq = classif_mod.carregar(classif_path)
    assert cq.registros["PF_25_ADM|002_PF_02|3"].apontamentos[0].status == "rejeitado"


def test_aprovar_lote_confianca_alta(ambiente_classificacao):
    _, classif_path, _, rodar = ambiente_classificacao

    assert rodar("--aprovar-lote", "--confianca", "alta") == 0

    cq = classif_mod.carregar(classif_path)
    # Q1 (alta) foi aprovada
    assert cq.registros["PF_25_ADM|001_PF_01|1"].apontamentos[0].status == "aprovado"
    # Q2 (media) e Q3 (baixa) continuam propostos
    assert cq.registros["PF_25_ADM|001_PF_01|2"].apontamentos[0].status == "proposto"
    assert cq.registros["PF_25_ADM|002_PF_02|3"].apontamentos[0].status == "proposto"


def test_aprovar_lote_com_filtro_caderno(ambiente_classificacao):
    _, classif_path, _, rodar = ambiente_classificacao

    # Aprovar lote apenas no caderno 002
    assert (
        rodar("--aprovar-lote", "--confianca", "baixa", "--caderno", "002_PF_02") == 0
    )

    cq = classif_mod.carregar(classif_path)
    assert cq.registros["PF_25_ADM|002_PF_02|3"].apontamentos[0].status == "aprovado"
    assert cq.registros["PF_25_ADM|001_PF_01|1"].apontamentos[0].status == "proposto"


def test_listar_pendentes_terminal(ambiente_classificacao, capsys):
    _, _, _, rodar = ambiente_classificacao

    assert rodar("--pendentes") == 0
    out = capsys.readouterr().out
    assert "PAINEL DE PENDÊNCIAS" in out
    assert "PF_25_ADM|002_PF_02|4" in out  # sem_no
    assert "PF_25_ADM|002_PF_02|3" in out  # baixa confiança


@pytest.mark.parametrize(
    "args, msg_erro",
    [
        (("--mapear", "PF_25_ADM|001_PF_01|1:NAO_EXISTE"), "não existe"),
        (("--mapear", "SEM_DOIS_PONTOS"), "Formato esperado"),
        (("--aprovar", "SEM_DOIS_PONTOS"), "Formato esperado"),
        (("--aprovar", "PF_25_ADM|001_PF_01|1:NAO_APONTA"), "não encontrado"),
        (("--rejeitar", "CHAVE_INEXISTENTE:NO"), "não encontrada"),
    ],
)
def test_erros_de_validacao_rejeitados(ambiente_classificacao, capsys, args, msg_erro):
    _, classif_path, _, rodar = ambiente_classificacao
    conteudo_antes = classif_path.read_text(encoding="utf-8")

    assert rodar(*args) == 1
    err = capsys.readouterr().err
    assert msg_erro in err
    # Garante que nada foi alterado no arquivo canônico
    assert classif_path.read_text(encoding="utf-8") == conteudo_antes


def test_geracao_relatorio_html(ambiente_classificacao):
    _, _, revisao_dir, rodar = ambiente_classificacao

    # Testa regeneração com flag --html
    assert rodar("--html") == 0

    html_file = revisao_dir / "relatorio" / "classificacao.html"
    assert html_file.exists()

    conteudo = html_file.read_text(encoding="utf-8")
    assert "Classificação de Questões na Árvore Mestre" in conteudo
    assert "001_PF_01" in conteudo
    assert "002_PF_02" in conteudo
    assert "SEM NÓ NA ÁRVORE" in conteudo
    assert "Processo Legislativo" in conteudo
    assert "badge-conf alta" in conteudo
    assert "badge-conf baixa" in conteudo


def test_renderizar_relatorio_com_contexto_mock(tmp_path: Path):
    arv = arv_mod.ArvoreMestre()
    arv_mod.criar_no(arv, "materia", "DIREITO PENAL", None, id_override="M-PEN")
    arv_mod.criar_no(
        arv, "assunto", "Crimes contra a pessoa", "M-PEN", id_override="A-PES"
    )

    cq = classif_mod.ClassificacaoQuestoes()
    classif_mod.mapear_questao(
        cq,
        arv,
        chave="PF_25|CAD1|10",
        hash_enunciado="hash10",
        nos=["A-PES"],
        confianca="alta",
        fora_do_edital=True,
        origem="llm",
        status="proposto",
    )

    contexto = {
        "PF_25|CAD1|10": {
            "tipo": "objetiva",
            "concurso": "PF_25",
            "caderno": "CAD1",
            "numero": 10,
            "enunciado": "O homicídio doloso admite tentativa.",
            "gabarito": "C",
            "anulada": False,
            "secao": "Acerca de crimes contra a pessoa",
            "texto_base": "Texto sobre o direito penal.",
            "orgao": "PF",
            "cargos": ["Agente de Polícia"],
        }
    }

    html = gerar_relatorio_classificacao.renderizar_relatorio(
        cq, arv, contexto=contexto
    )
    assert "O homicídio doloso admite tentativa." in html
    assert "Gabarito: C" in html
    assert "FORA DO EDITAL" in html
    assert "Agente de Polícia" in html
    assert "Texto sobre o direito penal." in html
