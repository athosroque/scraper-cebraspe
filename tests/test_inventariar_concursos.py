"""Testes unitários e de integração do script scripts/inventariar_concursos.py."""

import json
from unittest.mock import MagicMock

import pymupdf as fitz
import pytest

from scripts.inventariar_concursos import (
    agrupar_por_ano,
    conectar_banco,
    executar_amostra_formato,
    executar_gravar_banco,
    executar_listagens,
    executar_mapear,
    executar_relatorio,
    extrair_concursos_de_anos_json,
    main,
)
from src.inventario import (
    FORMATO_CE,
    FORMATO_ME,
    TIPO_ADMINISTRATIVO,
    TIPO_CADERNO_OBJETIVO,
    TIPO_EDITAL_ABERTURA,
    TIPO_GABARITO,
    TIPO_PADRAO_RESPOSTA,
    carregar_anos_json,
    carregar_concursos_jsonl,
)


def _criar_pdf_sintetico(texto: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), texto)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestAgruparPorAno:
    def test_agrupamento_anos_e_situacoes(self):
        concursos = [
            {"slug": "PF_25_ADM", "ano": 2025, "situacao": "encerrado"},
            {"slug": "IBAMA_25", "ano": 2025, "situacao": "em_andamento"},
            {"slug": "MPO_24", "ano": 2024, "situacao": "inscricoes_abertas"},
            {"slug": "NOVO_26", "ano": 2026, "situacao": "novos"},
            {"slug": "DESCONHECIDO_SLUG", "ano": None, "situacao": "encerrado"},
        ]

        dados = agrupar_por_ano(concursos)

        assert "2026" in dados
        assert "2025" in dados
        assert "2024" in dados
        assert dados["ano_desconhecido"] == ["DESCONHECIDO_SLUG"]

        assert dados["2025"]["encerrado"] == ["PF_25_ADM"]
        assert dados["2025"]["em_andamento"] == ["IBAMA_25"]
        assert dados["2024"]["inscricoes_abertas"] == ["MPO_24"]
        assert dados["2024"]["outros"] == ["MPO_24"]
        assert dados["2026"]["novos"] == ["NOVO_26"]
        assert dados["2026"]["outros"] == ["NOVO_26"]

        # Anos em ordem decrescente
        anos = [k for k in dados if k != "ano_desconhecido"]
        assert anos == ["2026", "2025", "2024"]

    def test_extrair_concursos_de_anos_json(self):
        anos_data = {
            "2025": {
                "encerrado": ["PF_25_ADM"],
                "em_andamento": ["IBAMA_25"],
                "outros": [],
            },
            "ano_desconhecido": ["SLUG_SEM_ANO"],
        }
        concursos = extrair_concursos_de_anos_json(anos_data)
        assert len(concursos) == 3
        mapa = {c["slug"]: c for c in concursos}

        assert mapa["PF_25_ADM"]["ano"] == 2025
        assert mapa["PF_25_ADM"]["situacao"] == "encerrado"
        assert (
            mapa["PF_25_ADM"]["url"]
            == "https://www.cebraspe.org.br/concursos/PF_25_ADM"
        )

        assert mapa["IBAMA_25"]["ano"] == 2025
        assert mapa["IBAMA_25"]["situacao"] == "em_andamento"

        assert mapa["SLUG_SEM_ANO"]["ano"] is None
        assert mapa["SLUG_SEM_ANO"]["situacao"] == "desconhecida"


class TestExecutarListagens:
    def test_executa_e_salva_anos_json(self, tmp_path, monkeypatch):
        caminho_anos = tmp_path / "inventario" / "anos.json"
        mock_page = MagicMock()

        concursos_mock = [
            {"slug": "PF_25_ADM", "ano": 2025, "situacao": "encerrado"},
            {"slug": "TCU_25_TEFC", "ano": 2025, "situacao": "encerrado"},
            {"slug": "ANTAQ_25_CF", "ano": 2025, "situacao": "em_andamento"},
        ]

        monkeypatch.setattr(
            "src.spider.listar_todas_listagens",
            lambda p: concursos_mock,
        )

        res = executar_listagens(mock_page, caminho_anos=caminho_anos)

        assert caminho_anos.exists()
        salvo = carregar_anos_json(caminho_anos)
        assert salvo == res
        assert "2025" in salvo
        assert salvo["2025"]["encerrado"] == ["PF_25_ADM", "TCU_25_TEFC"]
        assert salvo["2025"]["em_andamento"] == ["ANTAQ_25_CF"]


class TestExecutarMapear:
    @pytest.fixture
    def base_concursos(self):
        return [
            {
                "slug": "PF_25_ADM",
                "ano": 2025,
                "situacao": "encerrado",
                "orgao": "PF",
                "url": "https://www.cebraspe.org.br/concursos/PF_25_ADM",
            },
            {
                "slug": "TCU_25_TEFC",
                "ano": 2025,
                "situacao": "em_andamento",
                "orgao": "TCU",
                "url": "https://www.cebraspe.org.br/concursos/TCU_25_TEFC",
            },
            {
                "slug": "INSS_2015",
                "ano": 2015,
                "situacao": "encerrado",
                "orgao": "INSS",
                "url": "https://www.cebraspe.org.br/concursos/INSS_2015",
            },
        ]

    def test_mapeamento_incremental_e_campos(
        self, tmp_path, monkeypatch, base_concursos
    ):
        caminho_concursos = tmp_path / "concursos.jsonl"
        mock_page = MagicMock()

        def mock_mapear_links(page, url):
            if "PF_25_ADM" in url:
                return [
                    {
                        "url": "https://cdn/ed1.pdf",
                        "texto": "EDITAL Nº 1 – ABERTURA",
                        "tipo": TIPO_EDITAL_ABERTURA,
                        "versao": "desconhecida",
                        "curso_formacao": False,
                    },
                    {
                        "url": "https://cdn/prova.pdf",
                        "texto": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                        "versao": "desconhecida",
                        "curso_formacao": False,
                    },
                    {
                        "url": "https://cdn/gab.pdf",
                        "texto": "GABARITO DEFINITIVO",
                        "tipo": TIPO_GABARITO,
                        "versao": "definitivo",
                        "curso_formacao": False,
                    },
                    {
                        "url": "https://cdn/padrao.pdf",
                        "texto": "PADRÃO DEFINITIVO DE RESPOSTAS",
                        "tipo": TIPO_PADRAO_RESPOSTA,
                        "versao": "definitivo",
                        "curso_formacao": False,
                    },
                    {
                        "url": "https://cdn/comunicado.pdf",
                        "texto": "COMUNICADO LOCAL DE PROVA",
                        "tipo": TIPO_ADMINISTRATIVO,
                        "versao": "desconhecida",
                        "curso_formacao": False,
                    },
                ]
            return []

        monkeypatch.setattr("src.spider.mapear_links_pdf", mock_mapear_links)

        # Executa sem ano específico: deve processar 2020+ (PF_25_ADM e TCU_25_TEFC), ignorando INSS_2015
        processados = executar_mapear(
            page=mock_page,
            caminho_concursos=caminho_concursos,
            concursos_base=base_concursos,
            caminho_exclusoes=tmp_path / "sem_exclusoes.json",
        )

        assert processados == 2
        registros = carregar_concursos_jsonl(caminho_concursos)
        assert len(registros) == 2
        assert all(r["incluir"] is True and r["exclusao"] is None for r in registros)

        pf = next(r for r in registros if r["slug"] == "PF_25_ADM")
        assert pf["ano"] == 2025
        assert pf["orgao"] == "PF"
        assert pf["qtd_editais"] == 1
        assert pf["qtd_cadernos"] == 1
        assert pf["qtd_gabaritos"] == 1
        assert pf["qtd_padroes"] == 1
        assert pf["qtd_administrativos"] == 1
        assert pf["qtd_nao_classificados"] == 0
        assert pf["no_banco"] is True  # Está no piloto
        assert pf["erro"] is None
        assert "data_mapeamento" in pf
        assert pf["alertas"] == []

        # Em andamento sem nenhuma prova publicada: aguarda, não é pendência.
        tcu = next(r for r in registros if r["slug"] == "TCU_25_TEFC")
        assert tcu["no_banco"] is True
        assert tcu["alertas"] == ["sem_edital_abertura", "aguardando_prova"]

    def test_concurso_excluido_nao_e_buscado_de_novo(
        self, tmp_path, monkeypatch, base_concursos
    ):
        caminho_concursos = tmp_path / "concursos.jsonl"
        caminho_exclusoes = tmp_path / "exclusoes.json"
        caminho_exclusoes.write_text(
            json.dumps(
                {
                    "concursos": [
                        {
                            "slug": "TCU_25_TEFC",
                            "categoria": "cancelado",
                            "motivo": "Teste",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        visitados = []

        def mock_mapear_links(page, url):
            visitados.append(url)
            return []

        monkeypatch.setattr("src.spider.mapear_links_pdf", mock_mapear_links)
        argumentos = dict(
            page=MagicMock(),
            caminho_concursos=caminho_concursos,
            concursos_base=base_concursos,
            caminho_exclusoes=caminho_exclusoes,
        )
        executar_mapear(**argumentos)
        tcu = next(
            r
            for r in carregar_concursos_jsonl(caminho_concursos)
            if r["slug"] == "TCU_25_TEFC"
        )
        assert tcu["incluir"] is False
        assert tcu["exclusao"] == {"categoria": "cancelado", "motivo": "Teste"}

        visitados.clear()
        executar_mapear(**argumentos, refazer=True)
        assert not any("TCU_25_TEFC" in url for url in visitados)
        assert any("PF_25_ADM" in url for url in visitados)

    def test_tratamento_de_erro_isolado_nao_aborta(
        self, tmp_path, monkeypatch, base_concursos
    ):
        caminho_concursos = tmp_path / "concursos.jsonl"
        mock_page = MagicMock()

        def mock_mapear_com_falha(page, url):
            if "PF_25_ADM" in url:
                raise RuntimeError("Timeout simulado de conexão")
            return [
                {
                    "url": "https://cdn/ed_tcu.pdf",
                    "texto": "EDITAL Nº 1 – ABERTURA",
                    "tipo": TIPO_EDITAL_ABERTURA,
                    "versao": "desconhecida",
                    "curso_formacao": False,
                }
            ]

        monkeypatch.setattr("src.spider.mapear_links_pdf", mock_mapear_com_falha)

        processados = executar_mapear(
            page=mock_page,
            caminho_concursos=caminho_concursos,
            concursos_base=base_concursos,
        )

        assert processados == 2
        registros = carregar_concursos_jsonl(caminho_concursos)
        pf = next(r for r in registros if r["slug"] == "PF_25_ADM")
        assert pf["erro"] == "Timeout simulado de conexão"
        assert pf["qtd_editais"] == 0
        assert pf["pdfs"] == []

        tcu = next(r for r in registros if r["slug"] == "TCU_25_TEFC")
        assert tcu["erro"] is None
        assert tcu["qtd_editais"] == 1

    def test_filtros_ano_situacao_limite_e_refazer(
        self, tmp_path, monkeypatch, base_concursos
    ):
        caminho_concursos = tmp_path / "concursos.jsonl"
        mock_page = MagicMock()
        monkeypatch.setattr("src.spider.mapear_links_pdf", lambda p, u: [])

        # 1. Filtro com limite = 1
        proc1 = executar_mapear(
            page=mock_page,
            limite=1,
            caminho_concursos=caminho_concursos,
            concursos_base=base_concursos,
        )
        assert proc1 == 1
        assert len(carregar_concursos_jsonl(caminho_concursos)) == 1

        # 2. Executa novamente sem refazer: o primeiro concurso é pulado
        proc2 = executar_mapear(
            page=mock_page,
            limite=1,
            caminho_concursos=caminho_concursos,
            concursos_base=base_concursos,
        )
        assert proc2 == 1
        assert len(carregar_concursos_jsonl(caminho_concursos)) == 2

        # 3. Executa com refazer = True e situacao = "encerrado"
        proc3 = executar_mapear(
            page=mock_page,
            situacao="encerrado",
            refazer=True,
            caminho_concursos=caminho_concursos,
            concursos_base=base_concursos,
        )
        assert proc3 == 1  # Apenas PF_25_ADM é 2020+ e encerrado
        assert len(carregar_concursos_jsonl(caminho_concursos)) == 2


class TestExecutarAmostraFormato:
    def test_amostragem_e_deteccao_formato(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        caminho_concursos = tmp_path / "concursos.jsonl"
        dir_amostra = tmp_path / "amostras"
        dir_amostra.mkdir()
        # PDF que não é caderno objetivo do inventário sai da pasta de amostra.
        (dir_amostra / "PF_25_ADM_comunicado.pdf").write_bytes(b"%PDF-1.4")

        pdf_ce = _criar_pdf_sintetico("Julgue os itens a seguir C E\nItem 1.")
        pdf_me = _criar_pdf_sintetico(
            "Questão 1. Assinale...\n(A) 1\n(B) 2\n(C) 3\n(D) 4\n(E) 5"
        )

        concursos = [
            {
                "slug": "PF_25_ADM",
                "ano": 2025,
                "pdfs": [
                    {
                        "url": "https://cdn/prova_ce.pdf",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                    }
                ],
            },
            {
                "slug": "MPO_24",
                "ano": 2024,
                "pdfs": [
                    {
                        "url": "https://cdn/prova_me.pdf",
                        "tipo": TIPO_CADERNO_OBJETIVO,
                    }
                ],
            },
            {
                "slug": "SEM_CADERNO_25",
                "ano": 2025,
                "pdfs": [],
            },
        ]
        from src.inventario import salvar_concursos_jsonl

        salvar_concursos_jsonl(concursos, caminho_concursos)

        mock_session = MagicMock()

        def mock_get(url, **kwargs):
            resp = MagicMock()
            if "prova_ce" in url:
                resp.content = pdf_ce
            elif "prova_me" in url:
                resp.content = pdf_me
            else:
                resp.content = b"INVALID NOT PDF"
            resp.raise_for_status = MagicMock()
            return resp

        mock_session.get.side_effect = mock_get

        atualizados = executar_amostra_formato(
            caminho_concursos=caminho_concursos,
            diretorio_amostra=dir_amostra,
            session_requests=mock_session,
        )

        assert atualizados == 2
        carregados = carregar_concursos_jsonl(caminho_concursos)
        mapa = {c["slug"]: c for c in carregados}

        assert mapa["PF_25_ADM"]["formato_provavel"] == FORMATO_CE
        assert mapa["MPO_24"]["formato_provavel"] == FORMATO_ME
        assert mapa["SEM_CADERNO_25"].get("formato_provavel") is None
        assert mapa["MPO_24"]["amostra_formato"] == {
            "arquivo": "MPO_24_prova_me.pdf",
            "url": "https://cdn/prova_me.pdf",
            "texto": "",
        }
        assert sorted(p.name for p in dir_amostra.iterdir()) == [
            "MPO_24_prova_me.pdf",
            "PF_25_ADM_prova_ce.pdf",
        ]


class TestExecutarGravarBanco:
    def test_gravar_banco_chama_stats_writer(self, tmp_path, monkeypatch):
        caminho_concursos = tmp_path / "concursos.jsonl"
        registros = [{"slug": "PF_25_ADM", "ano": 2025}]
        from src.inventario import salvar_concursos_jsonl

        salvar_concursos_jsonl(registros, caminho_concursos)

        mock_conn = MagicMock()
        mock_gravar = MagicMock()
        monkeypatch.setattr("src.stats_writer.gravar_inventario", mock_gravar)

        total = executar_gravar_banco(
            caminho_concursos=caminho_concursos, conn=mock_conn
        )

        assert total == 1
        mock_gravar.assert_called_once_with(mock_conn, registros)

    def test_conectar_banco_com_database_url(self, monkeypatch):
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:pass@localhost:5432/testdb"
        )
        mock_connect = MagicMock()
        monkeypatch.setattr("psycopg2.connect", mock_connect)

        conectar_banco()
        mock_connect.assert_called_once_with(
            "postgresql://user:pass@localhost:5432/testdb"
        )


class TestExecutarRelatorio:
    def test_gerar_e_salvar_relatorio(self, tmp_path):
        caminho_concursos = tmp_path / "concursos.jsonl"
        caminho_anos = tmp_path / "anos.json"
        caminho_relatorio = tmp_path / "RELATORIO.md"

        from src.inventario import salvar_anos_json, salvar_concursos_jsonl

        salvar_concursos_jsonl(
            [
                {
                    "slug": "PF_25_ADM",
                    "ano": 2025,
                    "situacao": "encerrado",
                    "qtd_cadernos": 2,
                    "qtd_gabaritos": 2,
                    "qtd_padroes": 1,
                    "qtd_editais": 1,
                    "qtd_administrativos": 1,
                    "qtd_nao_classificados": 0,
                    "formato_provavel": "ce",
                    "no_banco": True,
                    "pdfs": [],
                }
            ],
            caminho_concursos,
        )
        salvar_anos_json({"ano_desconhecido": ["SLUG_X"]}, caminho_anos)

        conteudo = executar_relatorio(
            caminho_concursos=caminho_concursos,
            caminho_anos=caminho_anos,
            caminho_relatorio=caminho_relatorio,
        )

        assert caminho_relatorio.exists()
        assert "# Relatório Analítico de Inventário de Concursos CEBRASPE" in conteudo
        assert "PF_25_ADM" in conteudo
        assert "SLUG_X" in conteudo


class TestMainCLI:
    def test_main_sem_argumentos_imprime_ajuda(self, capsys):
        status = main([])
        assert status == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_main_subcomando_posicional_e_flags(self, tmp_path, monkeypatch):
        caminho_anos = tmp_path / "anos.json"
        caminho_concursos = tmp_path / "concursos.jsonl"
        caminho_relatorio = tmp_path / "RELATORIO.md"

        mock_page = MagicMock()
        mock_conn = MagicMock()

        monkeypatch.setattr(
            "src.spider.listar_todas_listagens",
            lambda p: [{"slug": "PF_25_ADM", "ano": 2025, "situacao": "encerrado"}],
        )
        monkeypatch.setattr("src.spider.mapear_links_pdf", lambda p, u: [])
        mock_gravar = MagicMock()
        monkeypatch.setattr("src.stats_writer.gravar_inventario", mock_gravar)

        # Testa o pipeline completo via --tudo com injeção de dependências
        argv = [
            "--tudo",
            "--anos-json",
            str(caminho_anos),
            "--concursos-jsonl",
            str(caminho_concursos),
            "--relatorio-md",
            str(caminho_relatorio),
            "--amostra-dir",
            str(tmp_path / "amostras"),
        ]

        status = main(
            argv=argv,
            page_override=mock_page,
            conn_override=mock_conn,
        )

        assert status == 0
        assert caminho_anos.exists()
        assert caminho_concursos.exists()
        assert caminho_relatorio.exists()
        assert mock_gravar.called
