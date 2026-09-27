import uuid

import psycopg2
import pytest

from src import questoes_writer, stats_writer
from tests.test_stats_writer import _postgres_disponivel


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="PostgreSQL local não disponível"
)
class TestQuestoesWriter:
    @pytest.fixture
    def conn(self):
        schema = f"test_{uuid.uuid4().hex[:12]}"
        admin = stats_writer.conectar()
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema}")
        conn = stats_writer.conectar(options=f"-c search_path={schema}")
        stats_writer.criar_schema(conn)
        try:
            yield conn
        finally:
            conn.close()
            with admin.cursor() as cur:
                cur.execute(f"DROP SCHEMA {schema} CASCADE")
            admin.close()

    def _criar_prova(self, conn, arquivo: str = "prova.pdf") -> int:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dim_ano (ano) VALUES (2025) ON CONFLICT DO NOTHING"
            )
            cur.execute(
                "INSERT INTO dim_orgao (sigla) VALUES (%s) RETURNING id",
                (f"ORG_{uuid.uuid4().hex[:6]}",),
            )
            orgao_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO concursos (slug, ano, orgao_id) VALUES (%s, 2025, %s) RETURNING id",
                (f"c_{uuid.uuid4().hex[:8]}", orgao_id),
            )
            concurso_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO provas (concurso_id, arquivo, tipo) "
                "VALUES (%s, %s, 'objetiva_basica') RETURNING id",
                (concurso_id, arquivo),
            )
            return cur.fetchone()[0]

    def test_gravar_alertas_e_flag_utilizavel(self, conn):
        prova_id = self._criar_prova(conn)
        resultado = {
            "textos_base": [{"ordem": 0, "texto": "Texto base 1", "figuras": []}],
            "alertas": [
                {"tipo": "simbolo_ilegivel", "item": 2},
                {"tipo": "trecho_sem_recuo_anexado_ao_item", "item": 3},
            ],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item perfeito sem alertas.",
                    "gabarito": "C",
                    "anulada": False,
                    "texto_base_ordem": 0,
                    "figuras": [],
                    "secao": "Comando",
                    "alertas": [],
                },
                {
                    "numero": 2,
                    "enunciado": "Item com símbolo \ufffd ilegível.",
                    "gabarito": "E",
                    "anulada": False,
                    "texto_base_ordem": None,
                    "figuras": [],
                    "secao": None,
                    "alertas": ["simbolo_ilegivel"],
                },
                {
                    "numero": 3,
                    "enunciado": "Item com anexo sem recuo.",
                    "gabarito": "C",
                    "anulada": False,
                    "texto_base_ordem": 0,
                    "figuras": [],
                    "secao": "Comando",
                },
            ],
        }

        qtd = questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)
        assert qtd == 3

        with conn.cursor() as cur:
            cur.execute(
                "SELECT numero, alertas, utilizavel FROM questoes ORDER BY numero"
            )
            linhas = cur.fetchall()
            assert linhas == [
                (1, [], True),
                (2, ["simbolo_ilegivel"], False),
                (3, ["trecho_sem_recuo_anexado_ao_item"], True),
            ]

            # View filtra simbolo_ilegivel (utilizavel = true)
            cur.execute("SELECT numero FROM vw_questoes_utilizaveis ORDER BY numero")
            assert [r[0] for r in cur.fetchall()] == [1, 3]

    def test_valida_texto_base_ordem_inexistente(self, conn):
        prova_id = self._criar_prova(conn)
        resultado = {
            "textos_base": [],
            "alertas": [],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item apontando para TB inexistente.",
                    "gabarito": "C",
                    "anulada": False,
                    "texto_base_ordem": 99,
                    "figuras": [],
                    "secao": None,
                }
            ],
        }
        with pytest.raises(ValueError, match="inexistente nesta prova"):
            questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)

    def test_constraint_impede_texto_base_de_outra_prova(self, conn):
        prova1 = self._criar_prova(conn, "prova1.pdf")
        prova2 = self._criar_prova(conn, "prova2.pdf")

        # Grava texto-base na prova 1
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO textos_base (prova_id, ordem, texto) VALUES (%s, 0, 'TB Prova 1') RETURNING id",
                (prova1,),
            )
            tb1_id = cur.fetchone()[0]

        # Tentar inserir questão na prova 2 apontando para tb1_id deve violar a constraint
        with (
            pytest.raises(
                psycopg2.IntegrityError, match="fk_questoes_texto_base_mesma_prova"
            ),
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO questoes
                    (prova_id, numero, enunciado, texto_base_id, gabarito)
                VALUES (%s, 1, 'Tentativa cruzada', %s, 'C')
                """,
                (prova2, tb1_id),
            )

    def test_on_delete_set_null_texto_base(self, conn):
        prova_id = self._criar_prova(conn)
        resultado = {
            "textos_base": [{"ordem": 0, "texto": "TB 0", "figuras": []}],
            "alertas": [],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item 1",
                    "gabarito": "C",
                    "anulada": False,
                    "texto_base_ordem": 0,
                    "figuras": [],
                    "secao": None,
                }
            ],
        }
        questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)
        with conn.cursor() as cur:
            # Apagar o texto-base não deve violar NOT NULL em prova_id:
            # apenas texto_base_id deve ser anulado pelo ON DELETE SET NULL (texto_base_id).
            cur.execute("DELETE FROM textos_base WHERE prova_id = %s", (prova_id,))
            cur.execute(
                "SELECT id, prova_id, texto_base_id FROM questoes WHERE prova_id = %s",
                (prova_id,),
            )
            row = cur.fetchone()
            assert row[1] == prova_id
            assert row[2] is None

    def test_schema_so_recria_fk_texto_base_quando_falta_a_regra(self, conn):
        consulta = (
            "SELECT oid, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'questoes'::regclass "
            "AND conname = 'fk_questoes_texto_base_mesma_prova'"
        )
        with conn.cursor() as cur:
            cur.execute(consulta)
            oid_antes, _ = cur.fetchone()
        # Já certa: reaplicar o schema não recria (nem revalida) a FK.
        stats_writer.criar_schema(conn)
        with conn.cursor() as cur:
            cur.execute(consulta)
            assert cur.fetchone()[0] == oid_antes
            # Versão antiga (SET NULL sem lista de colunas): é trocada.
            cur.execute(
                "ALTER TABLE questoes DROP CONSTRAINT fk_questoes_texto_base_mesma_prova"
            )
            cur.execute(
                "ALTER TABLE questoes ADD CONSTRAINT fk_questoes_texto_base_mesma_prova "
                "FOREIGN KEY (texto_base_id, prova_id) "
                "REFERENCES textos_base (id, prova_id) ON DELETE SET NULL"
            )
        conn.commit()
        stats_writer.criar_schema(conn)
        with conn.cursor() as cur:
            cur.execute(consulta)
            assert cur.fetchone()[1].endswith("ON DELETE SET NULL (texto_base_id)")
