"""Testes das views de estatísticas e incidência (Etapa 5E, ADR-032).

Roda contra o Postgres real em schema temporário isolado por teste.
Cobre:
- Desduplicação canônica (enunciados idênticos em cadernos do mesmo concurso).
- Subida na árvore (subassunto -> assunto -> matéria).
- Regra de não descida (questão em assunto nunca desce para subassunto).
- Caderno básico expandido para múltiplos cargos contando 1×.
- Interdisciplinaridade na mesma subárvore contando 1× no pai.
- Exclusão de anuladas do total/denominadores e presença na coluna `anuladas`.
- Exclusão de não utilizáveis e concursos pendentes de revisão.
- Resolução de nós fundidos para o nó efetivo.
- Cálculo de `pct_medio_por_concurso` com pesos iguais por concurso.
- Proporção Certo/Errado e comparativo Médio × Superior.
"""

import uuid
from decimal import Decimal

import pytest

from src import stats_writer
from tests.test_stats_writer import _postgres_disponivel


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)
class TestEstatisticasViews:
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

    @pytest.fixture
    def dados(self, conn):
        """Popula o schema com concursos, provas, questões e nós para os testes."""
        with conn.cursor() as cur:
            # 1. Órgão e Concursos
            cur.execute("INSERT INTO dim_orgao (sigla) VALUES ('ST') RETURNING id")
            orgao_id = cur.fetchone()[0]
            cur.execute("INSERT INTO dim_ano (ano) VALUES (2025)")

            cur.execute(
                """
                INSERT INTO concursos (slug, orgao_id, ano, banca, status_revisao) VALUES
                ('CONC_A', %s, 2025, 'CEBRASPE', 'aprovado'),
                ('CONC_B', %s, 2025, 'CEBRASPE', 'aprovado'),
                ('CONC_PEND', %s, 2025, 'CEBRASPE', 'pendente')
                RETURNING slug, id
                """,
                (orgao_id, orgao_id, orgao_id),
            )
            concursos = dict(cur.fetchall())

            # 2. Cargos
            cur.execute(
                """
                INSERT INTO dim_cargo (chave, nome) VALUES
                ('analista_judiciario', 'ANALISTA JUDICIÁRIO'),
                ('tecnico_judiciario', 'TÉCNICO JUDICIÁRIO'),
                ('oficial_justica', 'OFICIAL DE JUSTIÇA'),
                ('analista', 'ANALISTA')
                RETURNING chave, id
                """
            )
            dc = dict(cur.fetchall())

            # CONC_A: cargo 1 (superior), cargo 2 (medio), cargo 3 (superior)
            cur.execute(
                """
                INSERT INTO cargos_editais (concurso_id, cargo_id, numero, nome, nivel) VALUES
                (%s, %s, 1, 'ANALISTA JUDICIÁRIO', 'superior'),
                (%s, %s, 2, 'TÉCNICO JUDICIÁRIO', 'medio'),
                (%s, %s, 3, 'OFICIAL DE JUSTIÇA', 'superior'),
                (%s, %s, 1, 'ANALISTA', 'superior')
                RETURNING id, concurso_id, numero
                """,
                (
                    concursos["CONC_A"],
                    dc["analista_judiciario"],
                    concursos["CONC_A"],
                    dc["tecnico_judiciario"],
                    concursos["CONC_A"],
                    dc["oficial_justica"],
                    concursos["CONC_B"],
                    dc["analista"],
                ),
            )
            cargos_raw = cur.fetchall()
            cargos = {(c_id, num): row_id for row_id, c_id, num in cargos_raw}

            # 3. Provas e Provas_Cargos
            # p1: básico em CONC_A cobre cargo 1 e cargo 3
            # p2: específico em CONC_A cobre cargo 1
            # p3: básico em CONC_A para cargo 2 (médio)
            # p4: específico 2 em CONC_A (para testar caderno duplicado) cobre cargo 3
            # p5: em CONC_B cobre cargo 1
            # p_pend: em CONC_PEND
            cur.execute(
                """
                INSERT INTO provas (concurso_id, arquivo, identificador, tipo, codigo_caderno) VALUES
                (%s, 'prova_cb1.pdf', 'CB1', 'objetiva_basica', '001_CB1'),
                (%s, 'prova_esp1.pdf', '001', 'objetiva_especifica', '001_ESP1'),
                (%s, 'prova_cb2.pdf', 'CB2', 'objetiva_basica', '001_CB2'),
                (%s, 'prova_esp2.pdf', '002', 'objetiva_especifica', '001_ESP2'),
                (%s, 'prova_b.pdf', 'CB_B', 'objetiva_basica', '002_CB'),
                (%s, 'prova_pend.pdf', 'CB_PEND', 'objetiva_basica', '003_CB')
                RETURNING identificador, id
                """,
                (
                    concursos["CONC_A"],
                    concursos["CONC_A"],
                    concursos["CONC_A"],
                    concursos["CONC_A"],
                    concursos["CONC_B"],
                    concursos["CONC_PEND"],
                ),
            )
            provas = dict(cur.fetchall())

            cur.execute(
                """
                INSERT INTO provas_cargos (prova_id, cargo_edital_id) VALUES
                (%s, %s), -- p1 -> cargo 1 (sup)
                (%s, %s), -- p1 -> cargo 3 (sup)
                (%s, %s), -- p2 -> cargo 1 (sup)
                (%s, %s), -- p3 -> cargo 2 (med)
                (%s, %s), -- p4 -> cargo 3 (sup)
                (%s, %s)  -- p5 -> CONC_B cargo 1 (sup)
                """,
                (
                    provas["CB1"],
                    cargos[(concursos["CONC_A"], 1)],
                    provas["CB1"],
                    cargos[(concursos["CONC_A"], 3)],
                    provas["001"],
                    cargos[(concursos["CONC_A"], 1)],
                    provas["CB2"],
                    cargos[(concursos["CONC_A"], 2)],
                    provas["002"],
                    cargos[(concursos["CONC_A"], 3)],
                    provas["CB_B"],
                    cargos[(concursos["CONC_B"], 1)],
                ),
            )

            # 4. Árvore de nós
            # Matéria LP -> Assunto Ortografia -> Subassuntos Acentuação e Hífen
            # Assunto A-OLD fundido em A-ORT
            # Matéria DIR -> Assunto Constitucional
            cur.execute(
                """
                INSERT INTO no_arvore (id, nivel, nome, pai_id, origem, status, fundido_em) VALUES
                ('M-LP', 'materia', 'Língua Portuguesa', NULL, 'humano', 'ativo', NULL),
                ('A-ORT', 'assunto', 'Ortografia', 'M-LP', 'humano', 'ativo', NULL),
                ('A-OLD', 'assunto', 'Ortografia Antiga', 'M-LP', 'humano', 'fundido', 'A-ORT'),
                ('S-ACENT', 'subassunto', 'Acentuação gráfica', 'A-ORT', 'humano', 'ativo', NULL),
                ('S-HIFEN', 'subassunto', 'Emprego do hífen', 'A-ORT', 'humano', 'ativo', NULL),
                ('M-DIR', 'materia', 'Direito Constitucional', NULL, 'humano', 'ativo', NULL),
                ('A-CONST', 'assunto', 'Direitos Fundamentais', 'M-DIR', 'humano', 'ativo', NULL)
                """
            )

            # Dim_materia e mapeamento materia_no
            cur.execute(
                """
                INSERT INTO dim_materia (chave, nome, nocoes, nome_de_cargo) VALUES
                ('lingua_portuguesa', 'Língua Portuguesa', false, false),
                ('direito_constitucional', 'Direito Constitucional', false, false),
                ('cargo_especial', 'Especialista', false, true)
                RETURNING chave, id
                """
            )
            dm = dict(cur.fetchall())
            cur.execute(
                """
                INSERT INTO materia_no (materia_id, no_id) VALUES
                (%s, 'M-LP'),
                (%s, 'M-DIR')
                """,
                (dm["lingua_portuguesa"], dm["direito_constitucional"]),
            )

            # 5. Textos-base
            cur.execute(
                """
                INSERT INTO textos_base (prova_id, ordem, texto) VALUES
                (%s, 1, 'Texto de apoio da questão 1')
                RETURNING id
                """,
                (provas["CB1"],),
            )
            tb1_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO textos_base (prova_id, ordem, texto) VALUES
                (%s, 1, 'Texto de apoio da questão 1')
                RETURNING id
                """,
                (provas["002"],),
            )
            tb2_id = cur.fetchone()[0]

            # 6. Questões
            # q1: prova CB1, número 1, C, válida, aponta para S-ACENT (principal)
            # q2: prova CB1, número 2, X, anulada=True, gabarito='X', aponta para S-ACENT
            # q3: prova CB1, número 3, C, utilizavel=False (ilegível), aponta para S-ACENT
            # q4: prova CB1, número 4, E, válida, interdisciplinar: S-ACENT (secundário) + S-HIFEN (principal)
            # q5: prova CB_PEND, número 1, C, válida, concurso pendente
            # q6: prova 001, número 1, C, válida, aponta direto em A-ORT (assunto)
            # q7: prova 002 (caderno esp2), número 1, C, MESMO enunciado e tb de q1 (duplicata entre cadernos!)
            # q8: prova CB_B (CONC_B), número 1, C, válida, aponta para S-ACENT
            # q9: prova CB_B (CONC_B), número 2, E, válida, aponta para A-CONST (M-DIR)
            # q10: prova CB2 (médio), número 1, C, válida, aponta para nó fundido A-OLD
            cur.execute(
                """
                INSERT INTO questoes (prova_id, numero, enunciado, texto_base_id, gabarito, anulada, utilizavel) VALUES
                (%s, 1, 'Enunciado Acentuacao 1', %s, 'C', false, true),
                (%s, 2, 'Enunciado Anulado 2', NULL, 'X', true, true),
                (%s, 3, 'Enunciado Ilegivel 3', NULL, 'C', false, false),
                (%s, 4, 'Enunciado Interdisciplinar 4', NULL, 'E', false, true),
                (%s, 1, 'Enunciado Pendente 5', NULL, 'C', false, true),
                (%s, 1, 'Enunciado Assunto Direto 6', NULL, 'C', false, true),
                (%s, 1, 'Enunciado Acentuacao 1', %s, 'C', false, true), -- q7: duplicata canônica de q1
                (%s, 1, 'Enunciado CONC_B 8', NULL, 'C', false, true),
                (%s, 2, 'Enunciado Constitucional 9', NULL, 'E', false, true),
                (%s, 1, 'Enunciado Fundido 10', NULL, 'C', false, true)
                RETURNING numero, id, prova_id
                """,
                (
                    provas["CB1"],
                    tb1_id,
                    provas["CB1"],
                    provas["CB1"],
                    provas["CB1"],
                    provas["CB_PEND"],
                    provas["001"],
                    provas["002"],
                    tb2_id,
                    provas["CB_B"],
                    provas["CB_B"],
                    provas["CB2"],
                ),
            )
            questoes_raw = cur.fetchall()
            # Mapear para facilitar
            q_map = {}
            for num, q_id, p_id in questoes_raw:
                q_map[(p_id, num)] = q_id

            q1 = q_map[(provas["CB1"], 1)]
            q2 = q_map[(provas["CB1"], 2)]
            q3 = q_map[(provas["CB1"], 3)]
            q4 = q_map[(provas["CB1"], 4)]
            q5 = q_map[(provas["CB_PEND"], 1)]
            q6 = q_map[(provas["001"], 1)]
            q7 = q_map[(provas["002"], 1)]
            q8 = q_map[(provas["CB_B"], 1)]
            q9 = q_map[(provas["CB_B"], 2)]
            q10 = q_map[(provas["CB2"], 1)]

            # 7. Apontamentos questao_no
            cur.execute(
                """
                INSERT INTO questao_no (questao_id, no_id, papel, confianca, origem, status) VALUES
                (%s, 'S-ACENT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'S-ACENT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'S-ACENT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'S-ACENT', 'secundario', 'alta', 'humano', 'aprovado'),
                (%s, 'S-HIFEN', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'S-ACENT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'A-ORT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'S-ACENT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'S-ACENT', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'A-CONST', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'A-OLD', 'principal', 'alta', 'humano', 'aprovado')
                """,
                (
                    q1,
                    q2,
                    q3,
                    q4,
                    q4,  # q4 tem 2 nós na mesma subárvore!
                    q5,
                    q6,
                    q7,
                    q8,
                    q9,
                    q10,
                ),
            )
            conn.commit()

        return {
            "concursos": concursos,
            "provas": provas,
            "cargos": cargos,
            "questoes": {
                "q1": q1,
                "q2": q2,
                "q3": q3,
                "q4": q4,
                "q5": q5,
                "q6": q6,
                "q7": q7,
                "q8": q8,
                "q9": q9,
                "q10": q10,
            },
        }

    def test_caderno_basico_multiplos_cargos_conta_uma_vez(self, conn, dados):
        """Questão em caderno básico (que cobre N cargos) conta 1× sem filtro de cargo e 1× com filtro."""
        with conn.cursor() as cur:
            # Sem filtro de cargo na vw_prova_cobra_base:
            # Na base plana por cargo, a questão básica aparece expandida para cargo 1 e cargo 3.
            # Mas o count(DISTINCT questao_canonica_id) conta apenas as questões distintas!
            cur.execute(
                """
                SELECT count(*), count(DISTINCT questao_canonica_id)
                FROM vw_prova_cobra_base
                WHERE concurso = 'CONC_A' AND alvo_id = 'S-ACENT' AND NOT anulada
                """
            )
            linhas_totais, canonicas_distintas = cur.fetchone()
            # q1 e q4 estão em CONC_A para S-ACENT e aparecem para múltiplos cargos
            assert linhas_totais > canonicas_distintas
            assert canonicas_distintas == 2

            # Com filtro de cargo: cargo 1 (Analista)
            cur.execute(
                """
                SELECT questoes
                FROM vw_prova_cobra_subassunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND no_id = 'S-ACENT'
                """
            )
            # Cargo 1 tem q1 e q4 -> 2 questões
            assert cur.fetchone()[0] == 2

            # Com filtro de cargo: cargo 3 (Oficial)
            cur.execute(
                """
                SELECT questoes
                FROM vw_prova_cobra_subassunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 3 AND no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone()[0] == 2

    def test_desduplicacao_canonica_cadernos_mesmo_concurso(self, conn, dados):
        """Dois cadernos do mesmo concurso com enunciado, texto-base e gabarito idênticos compartilham questao_canonica_id."""
        with conn.cursor() as cur:
            q1_id = dados["questoes"]["q1"]
            q7_id = dados["questoes"]["q7"]
            cur.execute(
                """
                SELECT questao_id, questao_canonica_id
                FROM vw_questoes_contexto
                WHERE questao_id IN (%s, %s)
                """,
                (q1_id, q7_id),
            )
            rows = dict(cur.fetchall())
            assert rows[q1_id] == rows[q7_id]
            assert rows[q1_id] == min(q1_id, q7_id)

    def test_interdisciplinar_mesma_subarvore_conta_uma_vez_no_pai(self, conn, dados):
        """Questão com 2 apontamentos na mesma subárvore soma 1× no assunto pai."""
        with conn.cursor() as cur:
            # q4 aponta para S-ACENT e S-HIFEN (ambos sob A-ORT)
            # No subassunto: q4 aparece em S-ACENT e em S-HIFEN
            cur.execute(
                """
                SELECT no_id, questoes
                FROM vw_prova_cobra_subassunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND no_id IN ('S-ACENT', 'S-HIFEN')
                ORDER BY no_id
                """
            )
            sub = dict(cur.fetchall())
            assert sub["S-HIFEN"] == 1  # só q4
            assert sub["S-ACENT"] == 2  # q1 e q4

            # No assunto pai A-ORT para o caderno básico: q1 e q4 estão no básico.
            # q4 NUNCA deve somar 2×! Total esperado em A-ORT no básico: 2 (q1 e q4).
            cur.execute(
                """
                SELECT questoes, so_principal
                FROM vw_prova_cobra_assunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND no_id = 'A-ORT' AND tipo_conhecimento = 'basico'
                """
            )
            row = cur.fetchone()
            assert row[0] == 2
            # q4 tinha papel secundário em S-ACENT mas principal em S-HIFEN -> no pai vira principal!
            assert row[1] == 2

            # Somando todas as provas do cargo 1 (básico + específico com q6):
            cur.execute(
                """
                SELECT sum(questoes)
                FROM vw_prova_cobra_assunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND no_id = 'A-ORT'
                """
            )
            assert cur.fetchone()[0] == 3  # q1, q4 (básico) + q6 (específico)

    def test_questao_em_assunto_nao_desce_para_subassunto(self, conn, dados):
        """Questão classificada direto no nó de assunto não soma em subassunto."""
        with conn.cursor() as cur:
            # q6 foi classificada em A-ORT
            cur.execute(
                """
                SELECT count(*)
                FROM vw_prova_cobra_base
                WHERE questao_id = %s AND nivel_alvo = 'subassunto'
                """,
                (dados["questoes"]["q6"],),
            )
            assert cur.fetchone()[0] == 0

            # Mas soma em assunto e matéria
            cur.execute(
                """
                SELECT nivel_alvo, alvo_id
                FROM vw_prova_cobra_base
                WHERE questao_id = %s
                ORDER BY nivel_alvo
                """,
                (dados["questoes"]["q6"],),
            )
            niveis = cur.fetchall()
            assert ("assunto", "A-ORT") in niveis
            assert ("materia", "M-LP") in niveis

    def test_anulada_fora_do_total_e_presente_em_anuladas(self, conn, dados):
        """Anuladas ficam fora do total de questoes e do denominador de percentuais."""
        with conn.cursor() as cur:
            # q2 é anulada em S-ACENT (prova CB1, cargos 1 e 3)
            cur.execute(
                """
                SELECT questoes, anuladas
                FROM vw_prova_cobra_subassunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND no_id = 'S-ACENT'
                """
            )
            questoes, anuladas = cur.fetchone()
            assert questoes == 2  # q1 e q4 (q2 NÃO entra aqui)
            assert anuladas == 1  # q2 entra aqui

    def test_nao_utilizavel_e_concurso_pendente_excluidos(self, conn, dados):
        """Questão com utilizavel=false e questões de concurso pendente ficam 100% fora das views oficiais."""
        with conn.cursor() as cur:
            # q3 é utilizavel=False
            # q5 é do concurso CONC_PEND
            cur.execute(
                """
                SELECT count(*)
                FROM vw_prova_cobra_base
                WHERE questao_id IN (%s, %s)
                """,
                (dados["questoes"]["q3"], dados["questoes"]["q5"]),
            )
            assert cur.fetchone()[0] == 0

    def test_no_fundido_soma_no_efetivo(self, conn, dados):
        """Apontamento para nó fundido soma no nó de destino (no_efetivo)."""
        with conn.cursor() as cur:
            # q10 apontou para A-OLD (fundido em A-ORT)
            cur.execute(
                """
                SELECT no_id, questoes
                FROM vw_prova_cobra_assunto
                WHERE concurso = 'CONC_A' AND cargo_numero = 2
                """
            )
            res = dict(cur.fetchall())
            assert "A-OLD" not in res
            assert res.get("A-ORT") == 1

    def test_pct_medio_por_concurso_pesos_iguais(self, conn, dados):
        """pct_medio_por_concurso calcula a média dos percentuais de cada concurso com peso igual."""
        with conn.cursor() as cur:
            # S-ACENT em Língua Portuguesa:
            # Em CONC_A: válidas em LP = q1(1), q4(1), q6(1), q10(1) = 4 canônicas válidas.
            # q1 e q4 estão em S-ACENT -> 2 / 4 = 50.00%
            # Em CONC_B: válidas em LP = q8(1).
            # q8 está em S-ACENT -> 1 / 1 = 100.00%
            # Média esperada entre os 2 concursos: (50.00% + 100.00%) / 2 = 75.00%
            # (Em contagem bruta seria 3 / 5 = 60.00%; pct_medio_por_concurso iguala o peso dos concursos)
            cur.execute(
                """
                SELECT DISTINCT no_id, pct_medio_por_concurso
                FROM vw_prova_cobra_subassunto
                WHERE no_id = 'S-ACENT'
                """
            )
            no_id, pct_medio = cur.fetchone()
            assert no_id == "S-ACENT"
            assert pct_medio == Decimal("75.00")

    def test_certo_errado_por_no(self, conn, dados):
        """vw_certo_errado_por_no computa proporção C/E sobre válidas e anulações sobre total."""
        with conn.cursor() as cur:
            # No nó S-ACENT global:
            # q1 (C), q4 (E), q8 (C) válidas = 2 certos, 1 errado.
            # q2 (X) anulada = 1 anulada.
            # Total itens = 4 (3 válidas + 1 anulada).
            # pct_certos = 2 / 3 = 66.67%
            # pct_errados = 1 / 3 = 33.33%
            # pct_anuladas = 1 / 4 = 25.00%
            cur.execute(
                """
                SELECT total_itens, certos, errados, anuladas, pct_certos, pct_errados, pct_anuladas
                FROM vw_certo_errado_por_no
                WHERE no_id = 'S-ACENT'
                """
            )
            (
                total,
                certos,
                errados,
                anuladas,
                pct_c,
                pct_e,
                pct_a,
            ) = cur.fetchone()
            assert total == 4
            assert certos == 2
            assert errados == 1
            assert anuladas == 1
            assert pct_c == Decimal("66.67")
            assert pct_e == Decimal("33.33")
            assert pct_a == Decimal("25.00")

    def test_comparativo_nivel(self, conn, dados):
        """vw_comparativo_nivel compara incidência em nível superior vs médio."""
        with conn.cursor() as cur:
            # Para S-ACENT:
            # superior: q1, q4 (CONC_A), q8 (CONC_B) -> 3 questões
            # medio: 0 questões em S-ACENT (q10 em médio foi direto para A-ORT)
            cur.execute(
                """
                SELECT questoes_superior, questoes_medio
                FROM vw_comparativo_nivel
                WHERE no_id = 'S-ACENT'
                """
            )
            sup, med = cur.fetchone()
            assert sup == 3
            assert med == 0

    def test_vw_questoes_filtros_e_rotulo_materia(self, conn, dados):
        """vw_questoes expõe colunas de filtro para o site, flag tem_texto_base e rótulo de matéria."""
        with conn.cursor() as cur:
            q1_id = dados["questoes"]["q1"]
            cur.execute(
                """
                SELECT
                    questao_id,
                    tem_texto_base,
                    rotulo_materia,
                    nome_de_cargo,
                    no_caminho,
                    gabarito
                FROM vw_questoes
                WHERE questao_id = %s AND cargo_numero = 1
                """,
                (q1_id,),
            )
            row = cur.fetchone()
            assert row[0] == q1_id
            assert row[1] is True  # tem_texto_base
            assert row[2] == "Língua Portuguesa"
            assert row[3] is False  # nome_de_cargo
            assert "Língua Portuguesa > Ortografia > Acentuação gráfica" in row[4]
            assert row[5] == "C"

    def test_fn_prova_cobra_conta_distinto_com_filtro_de_varios_cargos(
        self, conn, dados
    ):
        """Somar a view por cargo duplica a questão básica; a função conta 1×."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sum(questoes) FROM vw_prova_cobra_subassunto
                WHERE concurso = 'CONC_A' AND no_id = 'S-ACENT'
                """
            )
            soma_ingenua = cur.fetchone()[0]
            cur.execute(
                """
                SELECT questoes, total_universo
                FROM fn_prova_cobra('subassunto', p_concurso => 'CONC_A')
                WHERE no_id = 'S-ACENT'
                """
            )
            questoes, total = cur.fetchone()
            assert questoes == 2  # q1 e q4, em qualquer número de cargos
            assert soma_ingenua > questoes
            assert total > 0

    def test_fn_prova_cobra_pct_medio_respeita_filtro(self, conn, dados):
        """Com filtro de concurso, a média usa só aquele concurso."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pct_medio_por_concurso
                FROM fn_prova_cobra('subassunto', p_concurso => 'CONC_B')
                WHERE no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone()[0] == Decimal("100.00")
            cur.execute(
                """
                SELECT pct_medio_por_concurso
                FROM fn_prova_cobra('subassunto')
                WHERE no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone()[0] == Decimal("75.00")
