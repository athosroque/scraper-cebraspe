"""Testes unitários para src/c2/checks.py e src/c2/relatorio.py (KAN-32, D5b)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.c2.checks import (
    INVARIANTE_PILOTO_ESPERADA,
    ViolacaoInvariantePiloto,
    consultar_custo_openrouter,
    executar_consultas_runbook,
    verificar_invariante_piloto,
    verificar_portao_arvore,
    verificar_portao_classificacao,
    verificar_portao_edital,
)
from src.c2.relatorio import gerar_relatorio_lote

# ----------------------------------------------------------------------
# Testes de Invariante do Piloto (K22)
# ----------------------------------------------------------------------


def test_verificar_invariante_piloto_sucesso():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (
        2800,
        129,
        3029,
        "3257ba6ba525fdd6b4492733b50882f2",
    )

    res = verificar_invariante_piloto(conn=mock_conn)
    assert res["status"] == "ok"
    assert res["valido"] is True
    assert res["divergencias"] == {}
    assert res["obtido"]["itens"] == 2800
    assert res["obtido"]["hash_chaves"] == "3257ba6ba525fdd6b4492733b50882f2"


def test_verificar_invariante_piloto_divergencia_sem_excecao():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (
        2790,
        129,
        3035,
        "hash_diferente",
    )

    res = verificar_invariante_piloto(conn=mock_conn, lancar_excecao=False)
    assert res["status"] == "divergencia"
    assert res["valido"] is False
    assert "itens" in res["divergencias"]
    assert "apontamentos" in res["divergencias"]
    assert "hash_chaves" in res["divergencias"]
    assert res["divergencias"]["itens"]["obtido"] == 2790


def test_verificar_invariante_piloto_divergencia_com_excecao():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchone.return_value = (
        2800,
        130,  # divergência de anuladas
        3029,
        "3257ba6ba525fdd6b4492733b50882f2",
    )

    with pytest.raises(ViolacaoInvariantePiloto) as exc_info:
        verificar_invariante_piloto(conn=mock_conn, lancar_excecao=True)
    assert "anuladas" in str(exc_info.value.detalhes.get("divergencias", {}))


def test_verificar_invariante_piloto_sem_banco():
    with patch("src.c2.checks.conectar", side_effect=Exception("Sem conexão")):
        res = verificar_invariante_piloto(conn=None, lancar_excecao=False)
        assert res["status"] == "sem_banco"
        assert res["valido"] is False
        assert "não disponível" in res["mensagem"]


# ----------------------------------------------------------------------
# Testes de Consultas do Runbook §4.5
# ----------------------------------------------------------------------


def test_executar_consultas_runbook_slugs_vazio():
    res = executar_consultas_runbook([])
    assert res["status"] == "ok"
    assert res["valido"] is True
    assert res["consulta_a"] == []


def test_executar_consultas_runbook_sem_banco():
    with patch("src.c2.checks.conectar", side_effect=Exception("Timeout")):
        res = executar_consultas_runbook(["SEFA_PR_25"])
        assert res["status"] == "sem_banco"
        assert res["valido"] is False
        assert len(res["falhas"]) > 0


def test_executar_consultas_runbook_com_dados_mockados():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Simula retornos para sql_a, sql_b, sql_c, sql_d_secoes, sql_d_caixa_alta, sql_k19
    mock_cur.fetchall.side_effect = [
        # a) Provas: 1 regular, 1 com fila com erro e sem gabarito
        [
            (
                "TESTE_25",
                "prova1.pdf",
                "objetiva_basica",
                "001",
                "1,2",
                "concluido",
                50,
                0,
                1,
                5,
                5,
                0,
                0,
            ),
            (
                "TESTE_25",
                "prova2.pdf",
                "objetiva_especifica",
                "002",
                "1",
                "falha",
                50,
                2,
                0,
                5,
                5,
                0,
                0,
            ),
        ],
        # b) Gabaritos: 1 válido, 1 inválido ('Z')
        [
            ("TESTE_25", "multipla_escolha", "A", 40),
            ("TESTE_25", "multipla_escolha", "Z", 1),
        ],
        # c) Discursivas: 1 válida, 1 sem padrão
        [
            ("TESTE_25", "disc1.pdf", 1, "Tema A", 3, True),
            ("TESTE_25", "disc2.pdf", 2, "Tema B", 2, False),
        ],
        # d) Seções
        [
            ("prova1.pdf", "DIREITO", 1, 50, 50),
        ],
        # d2) Alternativas terminando em caixa alta (K15)
        [
            ("TESTE_25", "prova1.pdf", 10, "fim de ciclo BANCO DE DADOS"),
        ],
        # K19: ME sem texto-base
        [
            ("TESTE_25", "prova1.pdf", 25),
        ],
    ]

    res = executar_consultas_runbook(["TESTE_25"], conn=mock_conn)
    assert res["valido"] is False
    assert len(res["falhas"]) >= 4  # fila, sem_gab, gabarito 'Z', disc sem padrão, K15
    assert len(res["alertas"]) == 1  # K19


# ----------------------------------------------------------------------
# Testes de Telemetria OpenRouter (A07)
# ----------------------------------------------------------------------


def test_consultar_custo_openrouter_sucesso(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TAXONOMIA_EDITAL", "fake-token-edital")
    monkeypatch.setenv("OPENROUTER_KEY_SINONIMOS", "fake-token-sinonimos")
    # Zera as demais
    monkeypatch.setenv("OPENROUTER_KEY_CURADORIA_ARVORE", "")
    monkeypatch.setenv("OPENROUTER_KEY_CLASSIFICACAO_QUESTOES", "")
    monkeypatch.setenv("OPENROUTER_KEY_TELEGRAM", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    class MockResp:
        status_code = 200

        def json(self):
            return {
                "data": {
                    "label": "Minha Chave",
                    "usage": 0.05,
                    "usage_daily": 0.01,
                    "limit": 100,
                }
            }

    with patch("requests.get", return_value=MockResp()):
        custo = consultar_custo_openrouter()
        assert custo["disponivel"] is True
        assert custo["total_acumulado_usd"] == 0.10
        assert custo["total_diario_usd"] == 0.02
        assert len(custo["etapas"]) == 2
        # Verifica conformidade com regra A07 (nenhum token no resultado)
        assert "fake-token-edital" not in str(custo)
        assert "fake-token-sinonimos" not in str(custo)


def test_consultar_custo_openrouter_sanitiza_label_com_token(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TAXONOMIA_EDITAL", "token-secreto")
    monkeypatch.setenv("OPENROUTER_KEY_SINONIMOS", "")
    monkeypatch.setenv("OPENROUTER_KEY_CURADORIA_ARVORE", "")
    monkeypatch.setenv("OPENROUTER_KEY_CLASSIFICACAO_QUESTOES", "")
    monkeypatch.setenv("OPENROUTER_KEY_TELEGRAM", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    class MockResp:
        status_code = 200

        def json(self):
            return {
                "data": {
                    "label": "sk-or-v1-abcdef123456",  # label que imita chave
                    "usage": 0.02,
                    "usage_daily": 0.0,
                }
            }

    with patch("requests.get", return_value=MockResp()):
        custo = consultar_custo_openrouter()
        # O label deve ter sido sanitizado para o nome da etapa
        etapa = custo["etapas"][0]
        assert "sk-or" not in etapa["label"]
        assert etapa["label"] == "Taxonomia do edital"


def test_consultar_custo_openrouter_offline(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_TAXONOMIA_EDITAL", "token-teste")
    monkeypatch.setenv("OPENROUTER_KEY_SINONIMOS", "")
    monkeypatch.setenv("OPENROUTER_KEY_CURADORIA_ARVORE", "")
    monkeypatch.setenv("OPENROUTER_KEY_CLASSIFICACAO_QUESTOES", "")
    monkeypatch.setenv("OPENROUTER_KEY_TELEGRAM", "")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    with patch("requests.get", side_effect=ConnectionError("Offline")):
        custo = consultar_custo_openrouter()
        assert custo["disponivel"] is True
        assert custo["total_acumulado_usd"] == 0.0
        assert custo["etapas"][0]["label"] == "Indisponível"


# ----------------------------------------------------------------------
# Testes dos Portões (Edital, Árvore, Classificação)
# ----------------------------------------------------------------------


def test_verificar_portao_edital(tmp_path):
    pasta = tmp_path / "revisao"
    pasta.mkdir()

    # Edital Aprovado
    (pasta / "edital1.json").write_text(
        json.dumps(
            {
                "concurso": {"slug": "CONCURSO_APROVADO"},
                "status_revisao_humana": "APROVADO pelo revisor",
            }
        ),
        encoding="utf-8",
    )
    # Edital Pendente
    (pasta / "edital2.json").write_text(
        json.dumps(
            {
                "concurso": {"slug": "CONCURSO_PENDENTE"},
                "status_revisao_humana": "PENDENTE de revisão",
            }
        ),
        encoding="utf-8",
    )

    ap1, st1 = verificar_portao_edital("CONCURSO_APROVADO", revisao_dir=pasta)
    assert ap1 is True
    assert "APROVADO" in st1

    ap2, st2 = verificar_portao_edital("CONCURSO_PENDENTE", revisao_dir=pasta)
    assert ap2 is False
    assert "PENDENTE" in st2

    ap3, st3 = verificar_portao_edital("INEXISTENTE", revisao_dir=pasta)
    assert ap3 is False
    assert st3 == "NAO_ENCONTRADO"


def test_verificar_portao_arvore():
    mock_arv = MagicMock()

    # Com propostas pendentes
    p1 = MagicMock(status="proposto", id="P1", tipo="fundir", justificativa="Teste")
    p2 = MagicMock(status="aprovado", id="P2", tipo="mover", justificativa="Teste")
    mock_arv.propostas = {"P1": p1, "P2": p2}

    aprovado, pendentes = verificar_portao_arvore(mock_arv)
    assert aprovado is False
    assert len(pendentes) == 1

    # Sem propostas pendentes
    mock_arv.propostas = {"P2": p2}
    aprovado_ok, pendentes_ok = verificar_portao_arvore(mock_arv)
    assert aprovado_ok is True
    assert len(pendentes_ok) == 0


def test_verificar_portao_classificacao():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Caso com 0 pendências (propostas=0, sem_classificacao=0)
    mock_cur.fetchone.return_value = (0, 0)
    ap1, pend1 = verificar_portao_classificacao(["SLUG_TESTE"], conn=mock_conn)
    assert ap1 is True
    assert pend1 == 0
    assert pend1.propostas == 0
    assert pend1.sem_classificacao == 0

    # Caso com pendências separadas
    mock_cur.fetchone.return_value = (10, 32)
    ap2, pend2 = verificar_portao_classificacao(["SLUG_TESTE"], conn=mock_conn)
    assert ap2 is False
    assert pend2 == 42
    assert pend2.propostas == 10
    assert pend2.sem_classificacao == 32
    assert pend2["propostas"] == 10
    assert pend2["sem_classificacao"] == 32


def test_portao_classificacao_bloqueia_concurso_sem_apontamentos():
    """Concurso com questões utilizáveis e 0 apontamentos aprovados bloqueia o portão P9."""
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # 0 propostas, mas 610 questões sem classificação
    mock_cur.fetchone.return_value = (0, 610)
    ap, pend = verificar_portao_classificacao(["C1_SEM_CLASSIFICACAO"], conn=mock_conn)
    assert ap is False
    assert pend == 610
    assert pend.sem_classificacao == 610
    assert pend.propostas == 0


# ----------------------------------------------------------------------
# Testes do Gerador de Relatório de Lote
# ----------------------------------------------------------------------


def test_gerar_relatorio_lote_aguardando_portoes(tmp_path):
    slugs = ["TESTE_25_A", "TESTE_25_B"]
    checks_resultado = {
        "modo": "Conferência",
        "invariante_piloto": {
            "status": "ok",
            "valido": True,
            "esperado": INVARIANTE_PILOTO_ESPERADA,
            "obtido": INVARIANTE_PILOTO_ESPERADA,
            "divergencias": {},
        },
        "consultas_runbook": {
            "status": "ok",
            "valido": True,
            "consulta_a": [
                {
                    "slug": "TESTE_25_A",
                    "arquivo": "prova1.pdf",
                    "tipo": "objetiva_basica",
                    "cargos": "1",
                    "fila": "concluido",
                    "itens": 50,
                    "sem_gab": 0,
                    "anul": 1,
                    "alt_min": 5,
                    "alt_max": 5,
                    "inutil": 0,
                    "disc": 0,
                }
            ],
            "consulta_b": [
                {
                    "slug": "TESTE_25_A",
                    "tipo": "multipla_escolha",
                    "gabarito": "A",
                    "total": 10,
                }
            ],
            "consulta_c": [],
            "consulta_d_secoes": [],
            "consulta_d_caixa_alta": [],
            "checagem_k19": [],
            "alertas": ["Alerta K19 suave"],
            "falhas": [],
        },
        "portao_edital": {
            "TESTE_25_A": (False, "PENDENTE"),
            "TESTE_25_B": (False, "PENDENTE"),
        },
        "portao_arvore": (True, []),
        "portao_classificacao": (False, 50),
    }

    custo_info = {
        "disponivel": True,
        "total_acumulado_usd": 0.15,
        "total_diario_usd": 0.02,
        "etapas": [
            {
                "nome": "Taxonomia do edital",
                "label": "Taxonomia do edital",
                "usage_acumulado": 0.15,
                "usage_daily": 0.02,
                "limit": 50.0,
            }
        ],
    }

    propostas_dispersao = [
        {
            "id": "P-123",
            "tipo": "fundir",
            "args": {"origem": "S-01", "destino": "A-01"},
            "justificativa": "Mesma norma",
        }
    ]

    caminho = gerar_relatorio_lote(
        numero_lote=2,
        slugs=slugs,
        checks_resultado=checks_resultado,
        custo_info=custo_info,
        propostas_dispersao=propostas_dispersao,
        raiz=tmp_path,
    )

    assert caminho.exists()
    assert caminho.name == "lote_02.md"

    conteudo = caminho.read_text(encoding="utf-8")
    assert "# Relatório de Lote 02: TESTE_25_A, TESTE_25_B" in conteudo
    assert "AGUARDANDO PORTÕES HUMANOS" in conteudo
    assert "US$ 0,15" in conteudo
    assert "prova1.pdf" in conteudo
    assert "P-123" in conteudo
    assert "Alerta K19 suave" in conteudo


def test_gerar_relatorio_lote_pronto_para_o_site(tmp_path):
    slugs = ["TESTE_25_A"]
    checks_resultado = {
        "modo": "Produção",
        "download": {"status": "ok", "valido": True, "mensagem": "PDFs íntegros"},
        "prova": {
            "status": "ok",
            "valido": True,
            "mensagem": "Gabaritos e itens validados",
        },
        "banco": {"status": "ok", "valido": True, "mensagem": "Banco íntegro"},
        "site": {
            "status": "ok",
            "valido": True,
            "mensagem": "Todas visíveis em vw_questoes",
        },
        "invariante_piloto": {
            "status": "ok",
            "valido": True,
            "esperado": INVARIANTE_PILOTO_ESPERADA,
            "obtido": INVARIANTE_PILOTO_ESPERADA,
            "divergencias": {},
        },
        "consultas_runbook": {
            "status": "ok",
            "valido": True,
            "consulta_a": [],
            "consulta_b": [],
            "consulta_c": [],
            "consulta_d_secoes": [],
            "consulta_d_caixa_alta": [],
            "checagem_k19": [],
            "alertas": [],
            "falhas": [],
        },
        "portao_edital": {
            "TESTE_25_A": (True, "APROVADO"),
        },
        "portao_arvore": (True, []),
        "portao_classificacao": (True, 0),
    }

    caminho = gerar_relatorio_lote(
        numero_lote=3,
        slugs=slugs,
        checks_resultado=checks_resultado,
        custo_info={
            "disponivel": False,
            "total_acumulado_usd": 0.0,
            "total_diario_usd": 0.0,
            "etapas": [],
        },
        propostas_dispersao=[],
        raiz=tmp_path,
    )

    assert caminho.exists()
    conteudo = caminho.read_text(encoding="utf-8")
    assert "PRONTO PARA O SITE" in conteudo
    assert "APROVADO PARA REVISÃO HUMANA" not in conteudo


def test_gerar_relatorio_lote_bloqueado(tmp_path):
    slugs = ["FALHA_25"]
    checks_resultado = {
        "modo": "Produção",
        "invariante_piloto": {
            "status": "divergencia",
            "valido": False,
            "esperado": INVARIANTE_PILOTO_ESPERADA,
            "obtido": {
                "itens": 2700,
                "anuladas": 129,
                "apontamentos": 3029,
                "hash_chaves": "diff",
            },
            "divergencias": {"itens": {"esperado": 2800, "obtido": 2700}},
        },
        "consultas_runbook": {
            "status": "falha",
            "valido": False,
            "falhas": ["Fila travada em pendente na prova X"],
            "alertas": [],
        },
    }

    caminho = gerar_relatorio_lote(
        numero_lote=99,
        slugs=slugs,
        checks_resultado=checks_resultado,
        custo_info={
            "disponivel": False,
            "total_acumulado_usd": 0.0,
            "total_diario_usd": 0.0,
            "etapas": [],
        },
        propostas_dispersao=[],
        raiz=tmp_path,
    )

    assert caminho.exists()
    conteudo = caminho.read_text(encoding="utf-8")
    assert "BLOQUEADO" in conteudo
    assert "Violação na checagem K22" in conteudo
    assert "Fila travada em pendente na prova X" in conteudo
