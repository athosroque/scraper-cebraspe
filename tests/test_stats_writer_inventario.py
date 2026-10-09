"""Testes para gravação do inventário no banco de dados (Etapa 8.0).

Valida:
- Estrutura das tabelas `inv_concurso`, `inv_pdf` e view `vw_inventario_ano`.
- Gravação transacional via `gravar_inventario`.
- Inserção em lote de PDFs associados a concursos.
- Idempotência da função (gravar 2 vezes seguidas resulta no mesmo estado final).
- Cascade delete de `inv_pdf` ao remover concurso.
- Métricas e agrupamentos agregados da view `vw_inventario_ano`.
"""

import uuid
from datetime import UTC, datetime

import pytest

from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)
class TestStatsWriterInventario:
    @pytest.fixture
    def conn(self):
        schema = f"test_{uuid.uuid4().hex[:12]}"
        admin = stats_writer.conectar()
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema}")
        conn = stats_writer.conectar(options=f"-c search_path={schema}")
        try:
            stats_writer.criar_schema(conn)
            yield conn
        finally:
            conn.close()
            with admin.cursor() as cur:
                cur.execute(f"DROP SCHEMA {schema} CASCADE")
            admin.close()

    def test_estrutura_tabelas_e_view(self, conn):
        with conn.cursor() as cur:
            # Verifica se as tabelas e a view existem
            cur.execute(
                """
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name IN ('inv_concurso', 'inv_pdf', 'vw_inventario_ano')
                ORDER BY table_name;
                """
            )
            tabelas = dict(cur.fetchall())
            assert "inv_concurso" in tabelas
            assert tabelas["inv_concurso"] == "BASE TABLE"
            assert "inv_pdf" in tabelas
            assert tabelas["inv_pdf"] == "BASE TABLE"
            assert "vw_inventario_ano" in tabelas
            assert tabelas["vw_inventario_ano"] == "VIEW"

            # Verifica colunas principais de inv_concurso
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = current_schema() AND table_name = 'inv_concurso'
                ORDER BY ordinal_position;
                """
            )
            colunas_concurso = [r[0] for r in cur.fetchall()]
            esperadas = [
                "slug",
                "orgao",
                "ano",
                "situacao",
                "url",
                "data_mapeamento",
                "qtd_editais",
                "qtd_cadernos",
                "qtd_gabaritos",
                "qtd_padroes",
                "qtd_administrativos",
                "qtd_nao_classificados",
                "formato_provavel",
                "alertas",
                "incluir",
                "no_banco",
                "erro",
            ]
            for col in esperadas:
                assert col in colunas_concurso

    def test_gravar_inventario_basico(self, conn):
        agora = datetime.now(UTC)
        concursos = [
            {
                "slug": "PF_2025",
                "orgao": "PF",
                "ano": 2025,
                "situacao": "Encerrado",
                "url": "https://www.cebraspe.org.br/concursos/PF_2025",
                "data_mapeamento": agora,
                "qtd_editais": 2,
                "qtd_cadernos": 4,
                "qtd_gabaritos": 4,
                "qtd_padroes": 1,
                "qtd_administrativos": 3,
                "qtd_nao_classificados": 0,
                "formato_provavel": "ce",
                "alertas": ["alerta1", "alerta2"],
                "incluir": True,
                "no_banco": True,
                "erro": None,
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/pf/edital1.pdf",
                        "texto": "Edital de Abertura",
                        "tipo": "edital",
                        "versao": "v1",
                    },
                    {
                        "url": "https://cdn.cebraspe.org.br/pf/caderno1.pdf",
                        "texto": "Caderno de Prova 01",
                        "tipo": "caderno",
                        "versao": None,
                    },
                ],
            }
        ]

        stats_writer.gravar_inventario(conn, concursos)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, orgao, ano, situacao, formato_provavel, alertas, no_banco FROM inv_concurso"
            )
            row = cur.fetchone()
            assert row[0] == "PF_2025"
            assert row[1] == "PF"
            assert row[2] == 2025
            assert row[3] == "Encerrado"
            assert row[4] == "ce"
            assert row[5] == ["alerta1", "alerta2"]
            assert row[6] is True

            cur.execute(
                "SELECT concurso_slug, url, texto, tipo, versao FROM inv_pdf ORDER BY url"
            )
            pdfs = cur.fetchall()
            assert len(pdfs) == 2
            assert pdfs[0] == (
                "PF_2025",
                "https://cdn.cebraspe.org.br/pf/caderno1.pdf",
                "Caderno de Prova 01",
                "caderno",
                None,
            )
            assert pdfs[1] == (
                "PF_2025",
                "https://cdn.cebraspe.org.br/pf/edital1.pdf",
                "Edital de Abertura",
                "edital",
                "v1",
            )

    def test_idempotencia_e_substituicao_completa(self, conn):
        concursos_v1 = [
            {
                "slug": "CONC_1",
                "orgao": "ORG1",
                "ano": 2024,
                "situacao": "Encerrado",
                "url": "https://cebraspe.org.br/conc1",
                "qtd_cadernos": 2,
                "qtd_gabaritos": 2,
                "formato_provavel": "me",
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/p1.pdf",
                        "texto": "P1",
                        "tipo": "caderno",
                    },
                    {
                        "url": "https://cdn.cebraspe.org.br/g1.pdf",
                        "texto": "G1",
                        "tipo": "gabarito",
                    },
                ],
            },
            {
                "slug": "CONC_2",
                "orgao": "ORG2",
                "ano": 2024,
                "situacao": "Em andamento",
                "url": "https://cebraspe.org.br/conc2",
                "qtd_cadernos": 1,
                "formato_provavel": "ce",
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/p2.pdf",
                        "texto": "P2",
                        "tipo": "caderno",
                    },
                ],
            },
        ]

        # 1ª Gravação
        stats_writer.gravar_inventario(conn, concursos_v1)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM inv_concurso")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT count(*) FROM inv_pdf")
            assert cur.fetchone()[0] == 3

        # 2ª Gravação idêntica (idempotência)
        stats_writer.gravar_inventario(conn, concursos_v1)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM inv_concurso")
            assert cur.fetchone()[0] == 2
            cur.execute("SELECT count(*) FROM inv_pdf")
            assert cur.fetchone()[0] == 3

        # 3ª Gravação com remoção de CONC_2 e adição de CONC_3
        concursos_v2 = [
            {
                "slug": "CONC_1",
                "orgao": "ORG1",
                "ano": 2024,
                "situacao": "Encerrado",
                "url": "https://cebraspe.org.br/conc1",
                "qtd_cadernos": 5,
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/p1_novo.pdf",
                        "texto": "P1 Novo",
                        "tipo": "caderno",
                    },
                ],
            },
            {
                "slug": "CONC_3",
                "orgao": "ORG3",
                "ano": 2025,
                "situacao": "Em andamento",
                "url": "https://cebraspe.org.br/conc3",
                "pdfs": [],
            },
        ]
        stats_writer.gravar_inventario(conn, concursos_v2)
        with conn.cursor() as cur:
            cur.execute("SELECT slug, qtd_cadernos FROM inv_concurso ORDER BY slug")
            rows = cur.fetchall()
            assert rows == [("CONC_1", 5), ("CONC_3", 0)]

            # PDFs antigos de CONC_1 e CONC_2 foram substituídos
            cur.execute("SELECT concurso_slug, url FROM inv_pdf")
            pdf_rows = cur.fetchall()
            assert pdf_rows == [("CONC_1", "https://cdn.cebraspe.org.br/p1_novo.pdf")]

    def test_cascade_delete(self, conn):
        concursos = [
            {
                "slug": "CONC_DEL",
                "orgao": "DEL",
                "ano": 2023,
                "situacao": "Encerrado",
                "url": "https://cebraspe.org.br/del",
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/del1.pdf",
                        "texto": "Del 1",
                        "tipo": "edital",
                    },
                ],
            }
        ]
        stats_writer.gravar_inventario(conn, concursos)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM inv_pdf")
            assert cur.fetchone()[0] == 1
            cur.execute("DELETE FROM inv_concurso WHERE slug = 'CONC_DEL'")
            cur.execute("SELECT count(*) FROM inv_pdf")
            assert cur.fetchone()[0] == 0

    def test_fora_do_site_e_curso_de_formacao(self, conn):
        """ADR-037: exclusão do concurso e PDF de curso de formação no banco."""
        concursos = [
            {
                "slug": "IBGE_20_AGENTE",
                "orgao": "IBGE",
                "ano": 2020,
                "situacao": "encerrado",
                "url": "https://cebraspe.org.br/ibge",
                "incluir": False,
                "exclusao": {"categoria": "cancelado", "motivo": "Cancelado."},
                "pdfs": [],
            },
            {
                "slug": "PRF_21",
                "orgao": "PRF",
                "ano": 2021,
                "situacao": "encerrado",
                "url": "https://cebraspe.org.br/prf",
                "incluir": True,
                "exclusao": None,
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/cf.pdf",
                        "texto": "PROVA OBJETIVA - CURSO DE FORMAÇÃO",
                        "tipo": "caderno_objetivo",
                        "curso_formacao": True,
                    },
                ],
            },
        ]
        stats_writer.gravar_inventario(conn, concursos)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, incluir, categoria_exclusao, motivo_exclusao "
                "FROM inv_concurso ORDER BY slug"
            )
            assert cur.fetchall() == [
                ("IBGE_20_AGENTE", False, "cancelado", "Cancelado."),
                ("PRF_21", True, None, None),
            ]
            cur.execute("SELECT curso_formacao FROM inv_pdf")
            assert cur.fetchall() == [(True,)]
            cur.execute(
                "SELECT ano, concursos_fora_do_site FROM vw_inventario_ano ORDER BY ano"
            )
            assert cur.fetchall() == [(2020, 1), (2021, 0)]

    def test_desduplicacao_pdf_mesmo_concurso(self, conn):
        concursos = [
            {
                "slug": "CONC_DUP",
                "orgao": "DUP",
                "ano": 2025,
                "situacao": "Encerrado",
                "url": "https://cebraspe.org.br/dup",
                "pdfs": [
                    {
                        "url": "https://cdn.cebraspe.org.br/rep.pdf",
                        "texto": "Repetido 1",
                        "tipo": "caderno",
                    },
                    {
                        "url": "https://cdn.cebraspe.org.br/rep.pdf",
                        "texto": "Repetido 2",
                        "tipo": "caderno",
                    },
                ],
            }
        ]
        stats_writer.gravar_inventario(conn, concursos)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM inv_pdf WHERE concurso_slug = 'CONC_DUP'")
            assert cur.fetchone()[0] == 1

    def test_view_inventario_ano(self, conn):
        concursos = [
            {
                "slug": "C1_2025",
                "orgao": "O1",
                "ano": 2025,
                "situacao": "Em andamento",
                "url": "https://c1",
                "qtd_cadernos": 10,
                "qtd_gabaritos": 8,
                "qtd_padroes": 2,
                "formato_provavel": "ce",
                "no_banco": True,
            },
            {
                "slug": "C2_2025",
                "orgao": "O2",
                "ano": 2025,
                "situacao": "Em andamento",
                "url": "https://c2",
                "qtd_cadernos": 5,
                "qtd_gabaritos": 5,
                "qtd_padroes": 0,
                "formato_provavel": "me",
                "no_banco": False,
            },
            {
                "slug": "C3_2025",
                "orgao": "O3",
                "ano": 2025,
                "situacao": "Encerrado",
                "url": "https://c3",
                "qtd_cadernos": 2,
                "qtd_gabaritos": 2,
                "qtd_padroes": 1,
                "formato_provavel": "ce",
                "no_banco": True,
            },
            {
                "slug": "C4_2024",
                "orgao": "O4",
                "ano": 2024,
                "situacao": "Encerrado",
                "url": "https://c4",
                "qtd_cadernos": 20,
                "qtd_gabaritos": 20,
                "qtd_padroes": 5,
                "formato_provavel": "me",
                "no_banco": True,
            },
            {
                "slug": "C5_SANO",
                "orgao": "O5",
                "ano": None,
                "situacao": "Encerrado",
                "url": "https://c5",
                "qtd_cadernos": 1,
                "qtd_gabaritos": 1,
                "qtd_padroes": 0,
                "formato_provavel": "ce",
                "no_banco": False,
            },
        ]

        stats_writer.gravar_inventario(conn, concursos)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ano,
                    situacao,
                    total_concursos,
                    total_cadernos,
                    total_gabaritos,
                    total_padroes,
                    concursos_me,
                    concursos_ce,
                    concursos_no_banco
                FROM vw_inventario_ano;
                """
            )
            linhas = cur.fetchall()

            # Ordenação esperada: ano DESC NULLS LAST, situacao
            # 2025 'Em andamento'
            # 2025 'Encerrado'
            # 2024 'Encerrado'
            # None 'Encerrado'
            assert len(linhas) == 4

            # 2025, 'Em andamento'
            assert linhas[0] == (2025, "Em andamento", 2, 15, 13, 2, 1, 1, 1)

            # 2025, 'Encerrado'
            assert linhas[1] == (2025, "Encerrado", 1, 2, 2, 1, 0, 1, 1)

            # 2024, 'Encerrado'
            assert linhas[2] == (2024, "Encerrado", 1, 20, 20, 5, 1, 0, 1)

            # None, 'Encerrado'
            assert linhas[3] == (None, "Encerrado", 1, 1, 1, 0, 0, 1, 0)
