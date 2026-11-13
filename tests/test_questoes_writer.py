import hashlib
import uuid
from decimal import Decimal

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

    def test_gravar_caderno_objetivo_grava_parser_versao_em_provas(self, conn):
        prova_id = self._criar_prova(conn)
        resultado = {
            "parser_versao": 1,
            "textos_base": [],
            "alertas": [],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item qualquer.",
                    "gabarito": "C",
                    "anulada": False,
                    "texto_base_ordem": None,
                    "figuras": [],
                    "secao": None,
                    "alertas": [],
                }
            ],
        }
        questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)

        with conn.cursor() as cur:
            cur.execute("SELECT parser_versao FROM provas WHERE id = %s", (prova_id,))
            assert cur.fetchone() == (1,)

        # Caderno extraído sem a chave (resultado antigo/sem versão): a
        # coluna fica NULL, não é inventada uma versão retroativa.
        del resultado["parser_versao"]
        questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)
        with conn.cursor() as cur:
            cur.execute("SELECT parser_versao FROM provas WHERE id = %s", (prova_id,))
            assert cur.fetchone() == (None,)

    def test_gravar_caderno_discursivo_grava_parser_versao_em_provas(self, conn):
        prova_id = self._criar_prova(conn)
        resultado = {
            "parser_versao": 1,
            "questoes": [
                {
                    "numero": 1,
                    "titulo": "Questão 1",
                    "tema": "Tema qualquer",
                    "enunciado": "Enunciado.",
                    "quesitos": [],
                    "padrao_resposta": None,
                }
            ],
        }
        questoes_writer.gravar_caderno_discursivo(conn, prova_id, resultado)

        with conn.cursor() as cur:
            cur.execute("SELECT parser_versao FROM provas WHERE id = %s", (prova_id,))
            assert cur.fetchone() == (1,)

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

    def test_gravar_multipla_escolha_com_alternativas_e_gabaritos_a_e(self, conn):
        prova_id = self._criar_prova(conn)
        alts = [
            {"letra": "A", "texto": "Alternativa A"},
            {"letra": "B", "texto": "Alternativa B"},
            {"letra": "C", "texto": "Alternativa C"},
            {"letra": "D", "texto": "Alternativa D"},
            {"letra": "E", "texto": "Alternativa E"},
        ]
        resultado = {
            "textos_base": [],
            "alertas": [],
            "questoes": [
                {
                    "numero": i,
                    "enunciado": f"Questão ME {i}",
                    "gabarito": gab,
                    "tipo": "multipla_escolha",
                    "alternativas": alts,
                    "anulada": gab == "X",
                    "figuras": [],
                    "secao": None,
                }
                for i, gab in enumerate(["A", "B", "C", "D", "E", "X"], start=1)
            ],
        }

        qtd = questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)
        assert qtd == 6

        with conn.cursor() as cur:
            cur.execute(
                "SELECT numero, gabarito, tipo, alternativas, anulada FROM questoes ORDER BY numero"
            )
            linhas = cur.fetchall()
            assert len(linhas) == 6
            for idx, gab in enumerate(["A", "B", "C", "D", "E", "X"], start=1):
                num, row_gab, tipo, row_alts, anulada = linhas[idx - 1]
                assert num == idx
                assert row_gab == gab
                assert tipo == "multipla_escolha"
                assert row_alts == alts
                assert anulada == (gab == "X")

    def test_gravar_certo_errado_default_e_retrocompatibilidade(self, conn):
        prova_id = self._criar_prova(conn)
        resultado = {
            "textos_base": [],
            "alertas": [],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item C/E sem especificar tipo.",
                    "gabarito": "C",
                    "anulada": False,
                    "figuras": [],
                    "secao": None,
                }
            ],
        }
        questoes_writer.gravar_caderno_objetivo(conn, prova_id, resultado)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT numero, gabarito, tipo, alternativas FROM questoes WHERE prova_id = %s",
                (prova_id,),
            )
            num, gab, tipo, alts = cur.fetchone()
            assert num == 1
            assert gab == "C"
            assert tipo == "certo_errado"
            assert alts is None

    def test_constraint_gabarito_e_tipo_invalido(self, conn):
        prova_id = self._criar_prova(conn)
        # Gabarito inválido 'Z' deve falhar
        with (
            pytest.raises(psycopg2.IntegrityError, match="questoes_gabarito_check"),
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO questoes (prova_id, numero, enunciado, gabarito, tipo)
                VALUES (%s, 1, 'Invalido', 'Z', 'certo_errado')
                """,
                (prova_id,),
            )
        conn.rollback()

        # Tipo inválido deve falhar (gabarito C e alternativas não nulas para
        # que só a regra de tipo seja violada, não as regras cruzadas)
        with (
            pytest.raises(psycopg2.IntegrityError, match="questoes_tipo_check"),
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO questoes
                    (prova_id, numero, enunciado, gabarito, tipo, alternativas)
                VALUES (%s, 2, 'Invalido', 'C', 'invalido', '[]'::jsonb)
                """,
                (prova_id,),
            )
        conn.rollback()

    def test_calcular_hash_5d(self):
        enun = "  Enunciado da questão teste.  "
        # Certo/Errado: SHA-1 apenas do enunciado limpo (chave estável da 5D)
        h_ce = questoes_writer.calcular_hash_5d(enun, tipo="certo_errado")
        assert h_ce == hashlib.sha1(enun.strip().encode("utf-8")).hexdigest()
        # Alternativas não entram no hash de C/E
        assert (
            questoes_writer.calcular_hash_5d(
                enun, tipo="certo_errado", alternativas=[{"letra": "A"}]
            )
            == h_ce
        )
        # Estabilidade: idêntico sem passar tipo (default certo_errado)
        assert questoes_writer.calcular_hash_5d(enun) == h_ce
        # Sem espaços no começo/fim é o mesmo hash
        assert questoes_writer.calcular_hash_5d(enun.strip()) == h_ce

        # Múltipla escolha: inclui alternativas normalizadas
        alts1 = [
            {"letra": "A", "texto": "Opção 1"},
            {"letra": "B", "texto": "Opção 2"},
        ]
        h_me1 = questoes_writer.calcular_hash_5d(
            enun, tipo="multipla_escolha", alternativas=alts1
        )
        assert len(h_me1) == 40
        assert h_me1 != h_ce

        # Alternativas diferentes geram hashes diferentes
        alts2 = [
            {"letra": "A", "texto": "Opção 1"},
            {"letra": "B", "texto": "Opção Modificada"},
        ]
        h_me2 = questoes_writer.calcular_hash_5d(
            enun, tipo="multipla_escolha", alternativas=alts2
        )
        assert h_me2 != h_me1

        # Ordenação de chaves é estável (sort_keys=True)
        alts3 = [
            {"texto": "Opção 1", "letra": "A"},
            {"texto": "Opção 2", "letra": "B"},
        ]
        h_me3 = questoes_writer.calcular_hash_5d(
            enun, tipo="multipla_escolha", alternativas=alts3
        )
        assert h_me3 == h_me1

        # Os apelidos sem uso foram removidos (o de `classificacao` é outro).
        assert not hasattr(questoes_writer, "calcular_hash_questao")
        assert not hasattr(questoes_writer, "calcular_hash_enunciado")

    @pytest.mark.parametrize(
        ("gabarito", "tipo", "alternativas", "constraint"),
        [
            # C/E com letra de ME
            ("A", "certo_errado", None, "questoes_gabarito_tipo_check"),
            ("D", "certo_errado", None, "questoes_gabarito_tipo_check"),
            # ME sem alternativas
            ("A", "multipla_escolha", None, "questoes_alternativas_tipo_check"),
            # C/E com alternativas
            ("C", "certo_errado", "[]", "questoes_alternativas_tipo_check"),
            (
                "E",
                "certo_errado",
                '[{"letra": "A", "texto": "x"}]',
                "questoes_alternativas_tipo_check",
            ),
        ],
    )
    def test_constraints_cruzadas_tipo_gabarito_alternativas(
        self, conn, gabarito, tipo, alternativas, constraint
    ):
        prova_id = self._criar_prova(conn)
        with (
            pytest.raises(psycopg2.IntegrityError, match=constraint),
            conn.cursor() as cur,
        ):
            cur.execute(
                """
                INSERT INTO questoes
                    (prova_id, numero, enunciado, gabarito, tipo, alternativas)
                VALUES (%s, 1, 'Inválida', %s, %s, %s::jsonb)
                """,
                (prova_id, gabarito, tipo, alternativas),
            )
        conn.rollback()

    def test_constraints_cruzadas_aceitam_linhas_validas(self, conn):
        prova_id = self._criar_prova(conn)
        with conn.cursor() as cur:
            # Formato do piloto: sem tipo nem alternativas (default C/E, NULL).
            for numero, gabarito in enumerate(["C", "E", "X"], start=1):
                cur.execute(
                    "INSERT INTO questoes (prova_id, numero, enunciado, gabarito) "
                    "VALUES (%s, %s, 'Item', %s)",
                    (prova_id, numero, gabarito),
                )
            # ME com C/E/X e com lista de alternativas vazia também vale.
            for numero, gabarito in enumerate(["C", "X", "B"], start=4):
                cur.execute(
                    "INSERT INTO questoes "
                    "(prova_id, numero, enunciado, gabarito, tipo, alternativas) "
                    "VALUES (%s, %s, 'Questão', %s, 'multipla_escolha', '[]'::jsonb)",
                    (prova_id, numero, gabarito),
                )
            cur.execute(
                "SELECT count(*) FROM questoes WHERE prova_id = %s", (prova_id,)
            )
            assert cur.fetchone()[0] == 6

    def test_schema_cria_constraints_cruzadas_em_banco_antigo(self, conn):
        # Banco de antes da 8.M: sem as regras cruzadas. Reaplicar o schema
        # as recria (bloco idempotente), e reaplicar de novo não duplica.
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE questoes DROP CONSTRAINT questoes_gabarito_tipo_check, "
                "DROP CONSTRAINT questoes_alternativas_tipo_check"
            )
        conn.commit()
        stats_writer.criar_schema(conn)
        stats_writer.criar_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'questoes'::regclass AND contype = 'c' ORDER BY conname"
            )
            assert [r[0] for r in cur.fetchall()] == [
                "questoes_alternativas_tipo_check",
                "questoes_gabarito_check",
                "questoes_gabarito_tipo_check",
                "questoes_tipo_check",
            ]

    def _criar_nos(self, conn) -> None:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO no_arvore (id, nivel, nome, pai_id, origem, status) VALUES
                ('M-NO', 'materia', 'Matéria do nó', NULL, 'humano', 'ativo'),
                ('M-OUTRO', 'materia', 'Outra matéria', NULL, 'humano', 'ativo')
                """
            )

    def _criar_concurso_classificado(
        self, conn, nivel: str, tipo: str, no_por_questao: list[str]
    ) -> None:
        """Concurso aprovado com 1 cargo, 1 caderno e uma questão por nó da
        lista (classificação aprovada). ME leva alternativas e gabarito B."""
        sufixo = uuid.uuid4().hex[:8]
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dim_ano (ano) VALUES (2025) ON CONFLICT DO NOTHING"
            )
            cur.execute(
                "INSERT INTO dim_orgao (sigla) VALUES (%s) RETURNING id",
                (f"ORG_{sufixo}",),
            )
            orgao_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO concursos (slug, orgao_id, ano, banca, status_revisao) "
                "VALUES (%s, %s, 2025, 'CEBRASPE', 'aprovado') RETURNING id",
                (f"C_{sufixo}", orgao_id),
            )
            concurso_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO dim_cargo (chave, nome) VALUES (%s, 'CARGO') RETURNING id",
                (f"cargo_{sufixo}",),
            )
            cargo_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO cargos_editais (concurso_id, cargo_id, numero, nome, nivel) "
                "VALUES (%s, %s, 1, 'CARGO', %s) RETURNING id",
                (concurso_id, cargo_id, nivel),
            )
            cargo_edital_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO provas (concurso_id, arquivo, tipo, codigo_caderno) "
                "VALUES (%s, 'p.pdf', 'objetiva_basica', %s) RETURNING id",
                (concurso_id, f"001_{sufixo}_CB1_01"),
            )
            prova_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO provas_cargos (prova_id, cargo_edital_id) VALUES (%s, %s)",
                (prova_id, cargo_edital_id),
            )
            eh_me = tipo == "multipla_escolha"
            for numero, no_id in enumerate(no_por_questao, start=1):
                cur.execute(
                    "INSERT INTO questoes "
                    "(prova_id, numero, enunciado, gabarito, tipo, alternativas) "
                    "VALUES (%s, %s, %s, %s, %s, %s::jsonb) RETURNING id",
                    (
                        prova_id,
                        numero,
                        f"Questão {numero}",
                        "B" if eh_me else "C",
                        tipo,
                        '[{"letra": "A", "texto": "a"}, {"letra": "B", "texto": "b"}]'
                        if eh_me
                        else None,
                    ),
                )
                questao_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO questao_no "
                    "(questao_id, no_id, papel, confianca, origem, status) "
                    "VALUES (%s, %s, 'principal', 'alta', 'humano', 'aprovado')",
                    (questao_id, no_id),
                )
        conn.commit()

    def _comparativo(self, conn, no_id: str) -> dict:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM vw_comparativo_nivel WHERE no_id = %s", (no_id,))
            colunas = [d[0] for d in cur.description]
            linha = cur.fetchone()
        return dict(zip(colunas, linha)) if linha else {}

    def test_questao_me_conta_na_incidencia_e_fica_fora_do_certo_errado(self, conn):
        self._criar_nos(conn)
        self._criar_concurso_classificado(
            conn, "superior", "multipla_escolha", ["M-NO", "M-OUTRO"]
        )
        linha = self._comparativo(conn, "M-NO")
        assert linha["questoes_superior"] == 1
        assert linha["pct_superior"] == Decimal("50.00")
        assert linha["cargos_superior"] == 1
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM vw_certo_errado_por_no")
            assert cur.fetchone()[0] == 0

    def test_comparativo_nivel_e_media_de_percentuais_por_concurso_cargo(self, conn):
        self._criar_nos(conn)
        # Concurso ME pequeno: 5 de 10 no nó (50%).
        self._criar_concurso_classificado(
            conn, "superior", "multipla_escolha", ["M-NO"] * 5 + ["M-OUTRO"] * 5
        )
        # Concurso C/E grande: 10 de 100 no nó (10%).
        self._criar_concurso_classificado(
            conn, "superior", "certo_errado", ["M-NO"] * 10 + ["M-OUTRO"] * 90
        )
        linha = self._comparativo(conn, "M-NO")
        # Média de 50% e 10% = 30%, não 15/110 = 13,64% (soma bruta).
        assert linha["pct_superior"] == Decimal("30.00")
        assert linha["questoes_superior"] == 15
        assert linha["cargos_superior"] == 2
        # Sem cargo de nível médio: % médio indefinido, diferença contra 0.
        assert linha["pct_medio"] is None
        assert linha["cargos_medio"] == 0
        assert linha["diferenca_pct"] == Decimal("30.00")

        # Concurso×cargo do nível sem questão no nó entra na média com 0%.
        self._criar_concurso_classificado(
            conn, "superior", "certo_errado", ["M-OUTRO"] * 4
        )
        linha = self._comparativo(conn, "M-NO")
        assert linha["pct_superior"] == Decimal("20.00")
        assert linha["cargos_superior"] == 3

        # Nível médio com o nó: 1 de 4 (25%); a diferença usa as duas médias.
        self._criar_concurso_classificado(
            conn, "medio", "certo_errado", ["M-NO"] + ["M-OUTRO"] * 3
        )
        linha = self._comparativo(conn, "M-NO")
        assert linha["pct_medio"] == Decimal("25.00")
        assert linha["questoes_medio"] == 1
        assert linha["cargos_medio"] == 1
        assert linha["diferenca_pct"] == Decimal("-5.00")

    def test_views_colunas_e_filtros(self, conn):
        with conn.cursor() as cur:
            # Garante que vw_questoes expõe tipo, alternativas e texto_tabela
            cur.execute(
                "SELECT tipo, alternativas, texto_tabela FROM vw_questoes LIMIT 0"
            )
            col_names = [desc[0] for desc in cur.description]
            assert "tipo" in col_names
            assert "alternativas" in col_names
            assert "texto_tabela" in col_names

            # Garante que as views de estatística compilam e executam sem erro
            cur.execute("SELECT * FROM vw_certo_errado_por_no LIMIT 0")
            cur.execute("SELECT * FROM vw_comparativo_nivel LIMIT 0")
