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
- `fn_prova_cobra`: percentuais como média por prova (concurso × cargo), com
  peso igual por prova e nunca soma bruta; prova única igual à conta direta.
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
        """pct_medio_por_concurso: média dos % de cada prova (concurso × cargo), peso igual."""
        with conn.cursor() as cur:
            # S-ACENT dentro de Língua Portuguesa, por prova (concurso × cargo):
            # CONC_A cargo 1: LP = q1, q4, q6 (3); S-ACENT = q1, q4 -> 66,67%
            # CONC_A cargo 3: LP = q1 (= q7, canônica), q4 (2); S-ACENT = 2 -> 100%
            # CONC_A cargo 2: LP = q10 (1, nó fundido em A-ORT); S-ACENT = 0 -> 0%
            # CONC_B cargo 1: LP = q8 (1); S-ACENT = 1 -> 100%
            # Média: (66,67 + 100 + 0 + 100) / 4 = 66,67%.
            # (Por concurso seria (50 + 100) / 2 = 75%; bruto, 3 / 5 = 60%.)
            cur.execute(
                """
                SELECT DISTINCT no_id, pct_medio_por_concurso
                FROM vw_prova_cobra_subassunto
                WHERE no_id = 'S-ACENT'
                """
            )
            no_id, pct_medio = cur.fetchone()
            assert no_id == "S-ACENT"
            assert pct_medio == Decimal("66.67")

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

    def test_vw_questoes_figuras_inclui_as_do_texto_base(self, conn, dados):
        """Tabela recortada fica no texto-base do grupo; o card só lê `figuras`."""
        q1_id = dados["questoes"]["q1"]
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE textos_base SET figuras = '[{"arquivo": "tb.png"}]'
                 WHERE id = (SELECT texto_base_id FROM questoes WHERE id = %s)
                """,
                (q1_id,),
            )
            cur.execute(
                """UPDATE questoes SET figuras = '[{"arquivo": "item.png"}]'
                    WHERE id = %s""",
                (q1_id,),
            )
            cur.execute(
                """
                SELECT DISTINCT figuras, tem_figuras FROM vw_questoes
                 WHERE questao_id = %s
                """,
                (q1_id,),
            )
            figuras, tem_figuras = cur.fetchone()
        assert [f["arquivo"] for f in figuras] == ["tb.png", "item.png"]
        assert tem_figuras is True

    def test_canonica_ignora_quebra_de_paragrafo_do_texto_base(self, conn, dados):
        """Mesmo texto, quebrado em parágrafo em lugar diferente: 1 questão."""
        q1_id, q7_id = dados["questoes"]["q1"], dados["questoes"]["q7"]
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE textos_base SET texto = 'Texto de apoio' || chr(10) || chr(10)
                                               || 'da questão 1'
                 WHERE id = (SELECT texto_base_id FROM questoes WHERE id = %s)
                """,
                (q7_id,),
            )
            cur.execute(
                """
                SELECT count(DISTINCT questao_canonica_id) FROM vw_questoes
                 WHERE questao_id IN (%s, %s)
                """,
                (q1_id, q7_id),
            )
            assert cur.fetchone()[0] == 1

    def test_criar_schema_preserva_grants_das_views(self, conn):
        """O schema recria as views (DROP ... CASCADE); o GRANT do site volta."""
        role = f"test_role_{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute(f"CREATE ROLE {role} NOLOGIN")
            cur.execute(f"GRANT SELECT ON vw_questoes TO {role}")
        conn.commit()
        try:
            stats_writer.criar_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT has_table_privilege(%s, 'vw_questoes', 'SELECT')",
                    (role,),
                )
                assert cur.fetchone()[0] is True
        finally:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute(f"DROP OWNED BY {role}")
                cur.execute(f"DROP ROLE {role}")
            conn.commit()

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
        """Com filtro de concurso, a média usa só as provas daquele concurso."""
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
            assert cur.fetchone()[0] == Decimal("66.67")
            # CONC_A: cargos 1, 2 e 3 -> (66,67 + 0 + 100) / 3.
            cur.execute(
                """
                SELECT pct_medio_por_concurso
                FROM fn_prova_cobra('subassunto', p_concurso => 'CONC_A')
                WHERE no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone()[0] == Decimal("55.56")

    def test_fn_prova_cobra_pct_do_universo_e_media_por_prova(self, conn, dados):
        """Entre provas, `pct_do_universo` é a média dos % por concurso × cargo, nunca a soma bruta."""
        with conn.cursor() as cur:
            # % de S-ACENT na prova inteira, por concurso × cargo:
            # CONC_A c1: 2 / 3 (q1, q4, q6) = 66,67%; c3: 2 / 2 = 100%;
            # c2: 0 / 1 (q10) = 0%; CONC_B c1: 1 / 2 (q8, q9) = 50%.
            # Média = 216,67 / 4 = 54,17%. A soma bruta daria 3 / 6 = 50%.
            cur.execute(
                """
                SELECT questoes, total_universo, pct_do_universo
                FROM fn_prova_cobra('subassunto') WHERE no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone() == (3, 6, Decimal("54.17"))
            # Só CONC_A (3 cargos): (66,67 + 0 + 100) / 3; bruto daria 2 / 4.
            cur.execute(
                """
                SELECT questoes, pct_do_universo
                FROM fn_prova_cobra('subassunto', p_concurso => 'CONC_A')
                WHERE no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone() == (2, Decimal("55.56"))
            # Matéria: % da prova e % médio coincidem (o escopo é a prova).
            # LP: c1 3/3, c3 2/2, c2 1/1, CONC_B 1/2 -> 87,50% (bruto: 5/6).
            cur.execute(
                """
                SELECT questoes, pct_do_universo, pct_medio_por_concurso
                FROM fn_prova_cobra('materia') WHERE no_id = 'M-LP'
                """
            )
            assert cur.fetchone() == (5, Decimal("87.50"), Decimal("87.50"))
            # Nó que só uma prova cobra: as outras entram com 0%.
            # S-HIFEN: q4 está em CONC_A c1 (1/3) e c3 (1/2) -> (33,33 + 50) / 4.
            cur.execute(
                """
                SELECT pct_do_universo FROM fn_prova_cobra('subassunto')
                WHERE no_id = 'S-HIFEN'
                """
            )
            assert cur.fetchone()[0] == Decimal("20.83")

    def test_fn_prova_cobra_prova_unica_igual_a_conta_direta(self, conn, dados):
        """Filtro de um só concurso × cargo: média de 1 termo = questões / total."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT concurso, cargo_numero FROM vw_prova_cobra_base"
            )
            provas = cur.fetchall()
            assert len(provas) == 4
            for concurso, cargo in provas:
                for tipo in (None, "basico", "especifico"):
                    cur.execute(
                        """
                        SELECT no_id, questoes, total_universo, pct_do_universo
                        FROM fn_prova_cobra(p_concurso => %s, p_cargo_numero => %s,
                                            p_tipo_conhecimento => %s)
                        """,
                        (concurso, cargo, tipo),
                    )
                    for no_id, questoes, total, pct in cur.fetchall():
                        esperado = round(Decimal(questoes * 100) / total, 2)
                        assert pct == esperado, (concurso, cargo, tipo, no_id)
            # Exemplo: CONC_A cargo 1, S-ACENT = 2 de 3 nas duas medidas.
            cur.execute(
                """
                SELECT questoes, total_universo, pct_do_universo, pct_medio_por_concurso
                FROM fn_prova_cobra('subassunto', p_concurso => 'CONC_A',
                                    p_cargo_numero => 1)
                WHERE no_id = 'S-ACENT'
                """
            )
            assert cur.fetchone() == (2, 3, Decimal("66.67"), Decimal("66.67"))

    def test_vw_peso_materia_cargo(self, conn, dados):
        """vw_peso_materia_cargo calcula proporção por matéria no cargo e formata rótulos."""
        with conn.cursor() as cur:
            # Em CONC_B, cargo 1 tem q8 (M-LP) e q9 (M-DIR)
            cur.execute(
                """
                SELECT materia_id, materia_nome, rotulo_materia, questoes, anuladas, total_cargo, pct_da_prova
                FROM vw_peso_materia_cargo
                WHERE concurso = 'CONC_B' AND cargo_numero = 1
                ORDER BY materia_id
                """
            )
            rows = cur.fetchall()
            assert len(rows) == 2
            row_dir = next(r for r in rows if r[0] == "M-DIR")
            assert row_dir[1] == "Direito Constitucional"
            assert row_dir[2] == "Direito Constitucional"  # nome_de_cargo = False
            assert row_dir[3] == 1  # questoes
            assert row_dir[4] == 0  # anuladas
            assert row_dir[5] == 2  # total_cargo
            assert row_dir[6] == Decimal("50.00")  # pct_da_prova

            row_lp = next(r for r in rows if r[0] == "M-LP")
            assert row_lp[3] == 1
            assert row_lp[5] == 2
            assert row_lp[6] == Decimal("50.00")

    @staticmethod
    def _item_edital(cur, concurso_id, cargo_edital_id, dim_materia_id, nome):
        """Item de edital mínimo: liga a matéria do edital ao concurso."""
        cur.execute(
            "INSERT INTO dim_topico (materia_id, chave, nome) VALUES (%s, %s, %s) RETURNING id",
            (dim_materia_id, f"tema_{dim_materia_id}", nome),
        )
        topico_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO taxonomia_itens (concurso_id, cargo_edital_id, materia_id, topico_id,
                nivel, tipo_conhecimento, chunk_index, topico_ordem, topico_nome)
            VALUES (%s, %s, %s, %s, 'superior', 'especifico', 90, 1, %s)
            """,
            (concurso_id, cargo_edital_id, dim_materia_id, topico_id, nome),
        )

    @staticmethod
    def _questao_no_no(cur, prova_id, numero, no_id):
        cur.execute(
            """
            INSERT INTO questoes (prova_id, numero, enunciado, gabarito, anulada, utilizavel)
            VALUES (%s, %s, %s, 'C', false, true)
            RETURNING id
            """,
            (prova_id, numero, f"Questão Especial {numero}"),
        )
        q_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO questao_no (questao_id, no_id, papel, confianca, origem, status)
            VALUES (%s, %s, 'principal', 'alta', 'humano', 'aprovado')
            """,
            (q_id, no_id),
        )
        return q_id

    def _preparar_no_de_cargo(self, cur, dados):
        """M-ESP: nó com o nome da matéria-cargo 'Especialista' do CONC_A cargo 1."""
        cur.execute(
            """
            INSERT INTO no_arvore (id, nivel, nome, pai_id, origem, status)
            VALUES ('M-ESP', 'materia', 'Especialista', NULL, 'humano', 'ativo')
            """
        )
        cur.execute("SELECT id FROM dim_materia WHERE chave = 'cargo_especial'")
        dm_esp_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO materia_no (materia_id, no_id) VALUES (%s, 'M-ESP')",
            (dm_esp_id,),
        )
        conc_a = dados["concursos"]["CONC_A"]
        self._item_edital(
            cur, conc_a, dados["cargos"][(conc_a, 1)], dm_esp_id, "Tema especial"
        )
        return self._questao_no_no(cur, dados["provas"]["001"], 99, "M-ESP")

    def test_vw_peso_materia_cargo_rotulo_nome_de_cargo(self, conn, dados):
        """Matéria com nome_de_cargo=True é exibida como 'Conhecimentos específicos — <cargo>'."""
        with conn.cursor() as cur:
            q_esp_id = self._preparar_no_de_cargo(cur, dados)
            cur.execute(
                """
                SELECT rotulo_materia, nome_de_cargo
                FROM vw_peso_materia_cargo
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND materia_id = 'M-ESP'
                """
            )
            row = cur.fetchone()
            assert row[0] == "Conhecimentos específicos — ANALISTA JUDICIÁRIO"
            assert row[1] is True
            # O nó ainda tem o nome do cargo: o card usa o mesmo rótulo.
            cur.execute(
                "SELECT rotulo_materia, nome_de_cargo FROM vw_questoes WHERE questao_id = %s",
                (q_esp_id,),
            )
            assert cur.fetchone() == (
                "Conhecimentos específicos — ANALISTA JUDICIÁRIO",
                True,
            )

    def test_no_de_cargo_curado_e_fundido_com_materia_nomeada(self, conn, dados):
        """ADR-030 (2026-10-07): o nó renomeado para a área mostra o próprio nome
        no card; o rótulo do edital segue pelo cargo e é avaliado por concurso,
        então a matéria nomeada de outro concurso no mesmo nó não vira
        'Conhecimentos específicos'."""
        with conn.cursor() as cur:
            q_esp_id = self._preparar_no_de_cargo(cur, dados)
            cur.execute(
                "UPDATE no_arvore SET nome = 'Área Especial' WHERE id = 'M-ESP'"
            )
            # CONC_B tem a matéria nomeada que caiu no mesmo nó.
            cur.execute(
                "INSERT INTO dim_materia (chave, nome) VALUES ('area_especial', 'ÁREA ESPECIAL') RETURNING id"
            )
            dm_area_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO materia_no (materia_id, no_id) VALUES (%s, 'M-ESP')",
                (dm_area_id,),
            )
            conc_b = dados["concursos"]["CONC_B"]
            self._item_edital(
                cur, conc_b, dados["cargos"][(conc_b, 1)], dm_area_id, "Tema da área"
            )
            q_b_id = self._questao_no_no(cur, dados["provas"]["CB_B"], 98, "M-ESP")

            cur.execute(
                """
                SELECT concurso, rotulo_materia, nome_de_cargo FROM vw_peso_materia_cargo
                WHERE materia_id = 'M-ESP' ORDER BY concurso
                """
            )
            assert cur.fetchall() == [
                ("CONC_A", "Conhecimentos específicos — ANALISTA JUDICIÁRIO", True),
                ("CONC_B", "Área Especial", False),
            ]
            cur.execute(
                "SELECT questao_id, rotulo_materia, nome_de_cargo FROM vw_questoes "
                "WHERE questao_id = ANY(%s) ORDER BY questao_id",
                ([q_esp_id, q_b_id],),
            )
            assert cur.fetchall() == [
                (q_esp_id, "Área Especial", False),
                (q_b_id, "Área Especial", False),
            ]

    def test_vw_edital_vs_prova_situacoes_e_cobertura_descendente(self, conn, dados):
        """vw_edital_vs_prova classifica situações e aplica cobertura descendente."""
        with conn.cursor() as cur:
            conc_a_id = dados["concursos"]["CONC_A"]
            cargo_1_id = dados["cargos"][(conc_a_id, 1)]

            cur.execute("SELECT id FROM dim_materia WHERE chave = 'lingua_portuguesa'")
            dm_lp_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO dim_topico (materia_id, chave, nome)
                VALUES (%s, 'ortografia', 'Ortografia')
                RETURNING id
                """,
                (dm_lp_id,),
            )
            top_ort_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO topico_no (topico_id, no_id) VALUES (%s, 'A-ORT')",
                (top_ort_id,),
            )

            cur.execute(
                """
                INSERT INTO dim_subtopico (topico_id, chave, nome)
                VALUES (%s, 'hifen', 'Emprego do hífen'),
                       (%s, 'sem_questao', 'Tópico Nunca Cobrado')
                RETURNING chave, id
                """,
                (top_ort_id, top_ort_id),
            )
            subtopicos = dict(cur.fetchall())
            cur.execute(
                "INSERT INTO subtopico_no (subtopico_id, no_id) VALUES (%s, 'S-HIFEN')",
                (subtopicos["hifen"],),
            )

            # Criar nó nunca cobrado na árvore
            cur.execute(
                """
                INSERT INTO no_arvore (id, nivel, nome, pai_id, origem, status)
                VALUES ('S-NUNC', 'subassunto', 'Tópico Nunca Cobrado', 'A-ORT', 'humano', 'ativo')
                """
            )
            cur.execute(
                "INSERT INTO subtopico_no (subtopico_id, no_id) VALUES (%s, 'S-NUNC')",
                (subtopicos["sem_questao"],),
            )

            # Itens de edital:
            # 1. edital aponta para S-HIFEN (subassunto)
            cur.execute(
                """
                INSERT INTO taxonomia_itens (concurso_id, cargo_edital_id, materia_id, topico_id, nivel, tipo_conhecimento, chunk_index, topico_ordem, topico_nome)
                VALUES (%s, %s, %s, %s, 'superior', 'basico', 0, 1, 'Ortografia')
                RETURNING id
                """,
                (conc_a_id, cargo_1_id, dm_lp_id, top_ort_id),
            )
            ti_1 = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO taxonomia_subitens (taxonomia_item_id, subtopico_id, ordem, nome) VALUES (%s, %s, 1, 'Emprego do hífen')",
                (ti_1, subtopicos["hifen"]),
            )

            # 2. edital aponta para S-NUNC (nunca cobrado)
            cur.execute(
                """
                INSERT INTO taxonomia_itens (concurso_id, cargo_edital_id, materia_id, topico_id, nivel, tipo_conhecimento, chunk_index, topico_ordem, topico_nome)
                VALUES (%s, %s, %s, %s, 'superior', 'basico', 1, 1, 'Ortografia')
                RETURNING id
                """,
                (conc_a_id, cargo_1_id, dm_lp_id, top_ort_id),
            )
            ti_2 = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO taxonomia_subitens (taxonomia_item_id, subtopico_id, ordem, nome) VALUES (%s, %s, 1, 'Tópico Nunca Cobrado')",
                (ti_2, subtopicos["sem_questao"]),
            )

            # Consultar vw_edital_vs_prova para cargo 1:
            # S-HIFEN: previsto e cobrado (q4 está em S-HIFEN) -> 'cobrado_no_edital'
            # S-NUNC: previsto e 0 questões cobradas -> 'no_edital_nunca_cobrado'
            # M-LP: previsto (sobe de S-HIFEN e S-NUNC) e cobrado -> 'cobrado_no_edital'
            cur.execute(
                """
                SELECT no_id, no_nivel, no_edital, previsao, questoes, razao, situacao
                FROM vw_edital_vs_prova
                WHERE concurso = 'CONC_A' AND cargo_numero = 1 AND no_id IN ('S-HIFEN', 'S-NUNC', 'M-LP')
                ORDER BY no_id
                """
            )
            res = {r[0]: r for r in cur.fetchall()}
            assert "S-HIFEN" in res
            assert res["S-HIFEN"][2] is True  # no_edital
            assert res["S-HIFEN"][3] >= 1  # previsao
            assert res["S-HIFEN"][4] >= 1  # questoes
            assert res["S-HIFEN"][6] == "cobrado_no_edital"

            assert "S-NUNC" in res
            assert res["S-NUNC"][2] is True
            assert res["S-NUNC"][3] >= 1
            assert res["S-NUNC"][4] == 0  # questoes
            assert res["S-NUNC"][6] == "no_edital_nunca_cobrado"

            assert "M-LP" in res
            assert res["M-LP"][6] == "cobrado_no_edital"

    def test_vw_discursivas(self, conn, dados):
        """vw_discursivas expõe dados analíticos e não entra nas contagens de questões objetivas."""
        with conn.cursor() as cur:
            # 1. Inserir discursiva aprovada e discursiva pendente
            cur.execute(
                """
                INSERT INTO discursivas (prova_id, numero, titulo, tema, enunciado, quesitos, padrao_resposta)
                VALUES
                (%s, 1, 'Título D1', 'Tema Constitucional', 'Enunciado D1', '["Q1", "Q2"]'::jsonb, 'Padrão D1'),
                (%s, 2, 'Título D2', 'Tema Proposto', 'Enunciado D2', '[]'::jsonb, 'Padrão D2')
                RETURNING id, numero
                """,
                (dados["provas"]["001"], dados["provas"]["001"]),
            )
            d_rows = dict(cur.fetchall())
            d1_id = next(k for k, v in d_rows.items() if v == 1)
            d2_id = next(k for k, v in d_rows.items() if v == 2)

            cur.execute(
                """
                INSERT INTO discursiva_no (discursiva_id, no_id, papel, confianca, origem, status)
                VALUES
                (%s, 'A-CONST', 'principal', 'alta', 'humano', 'aprovado'),
                (%s, 'A-CONST', 'principal', 'alta', 'humano', 'proposto')
                """,
                (d1_id, d2_id),
            )

            # 2. Consultar vw_discursivas: apenas d1 deve aparecer
            cur.execute(
                """
                SELECT discursiva_id, numero, titulo, tema, no_id, no_nome, confianca, status_revisao
                FROM vw_discursivas
                WHERE concurso = 'CONC_A'
                """
            )
            rows = cur.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == d1_id
            assert rows[0][1] == 1
            assert rows[0][2] == "Título D1"
            assert rows[0][3] == "Tema Constitucional"
            assert rows[0][4] == "A-CONST"
            assert rows[0][6] == "alta"
            assert rows[0][7] == "aprovado"

            # 3. Discursiva NÃO pode alterar as contagens de vw_prova_cobra_base nem vw_peso_materia_cargo
            cur.execute(
                "SELECT count(*) FROM vw_prova_cobra_base WHERE alvo_id = 'A-CONST' AND concurso = 'CONC_A'"
            )
            assert cur.fetchone()[0] == 0

    def test_vw_edital_vs_prova_irmao_fora_do_edital_e_consistencia_5d(
        self, conn, dados
    ):
        """Subassunto irmão de um previsto, sem ancestral apontado pelo edital,
        é `cobrado_fora_do_edital` e bate com o `fora_do_edital` da 5D."""
        with conn.cursor() as cur:
            conc_a_id = dados["concursos"]["CONC_A"]
            cargo_1_id = dados["cargos"][(conc_a_id, 1)]
            cur.execute(
                """
                INSERT INTO no_arvore (id, nivel, nome, pai_id, origem, status) VALUES
                ('M-ADM', 'materia', 'Direito Administrativo', NULL, 'humano', 'ativo'),
                ('A-ATOS', 'assunto', 'Atos administrativos', 'M-ADM', 'humano', 'ativo'),
                ('S-ATO1', 'subassunto', 'Conceito', 'A-ATOS', 'humano', 'ativo'),
                ('S-ATO2', 'subassunto', 'Anulação', 'A-ATOS', 'humano', 'ativo')
                """
            )
            # Matéria e tópico sem nó: o edital só aponta para S-ATO1.
            cur.execute(
                "INSERT INTO dim_materia (chave, nome) VALUES ('adm', 'ADM') RETURNING id"
            )
            dm_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO dim_topico (materia_id, chave, nome) VALUES (%s, 'atos', 'Atos') RETURNING id",
                (dm_id,),
            )
            top_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO dim_subtopico (topico_id, chave, nome) VALUES (%s, 'conceito', 'Conceito') RETURNING id",
                (top_id,),
            )
            sub_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO subtopico_no (subtopico_id, no_id) VALUES (%s, 'S-ATO1')",
                (sub_id,),
            )
            cur.execute(
                """
                INSERT INTO taxonomia_itens (concurso_id, cargo_edital_id, materia_id, topico_id,
                    nivel, tipo_conhecimento, chunk_index, topico_ordem, topico_nome)
                VALUES (%s, %s, %s, %s, 'superior', 'especifico', 9, 1, 'Atos')
                RETURNING id
                """,
                (conc_a_id, cargo_1_id, dm_id, top_id),
            )
            ti_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO taxonomia_subitens (taxonomia_item_id, subtopico_id, ordem, nome) VALUES (%s, %s, 1, 'Conceito')",
                (ti_id, sub_id),
            )
            cur.execute(
                """
                INSERT INTO questoes (prova_id, numero, enunciado, gabarito, anulada, utilizavel)
                VALUES (%s, 50, 'Anulação do ato', 'C', false, true) RETURNING id
                """,
                (dados["provas"]["001"],),
            )
            q_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO questao_no (questao_id, no_id, papel, confianca, origem, status, fora_do_edital)
                VALUES (%s, 'S-ATO2', 'principal', 'alta', 'humano', 'aprovado', true)
                """,
                (q_id,),
            )
            cur.execute(
                """
                SELECT no_id, no_edital, previsao, questoes, situacao
                FROM vw_edital_vs_prova
                WHERE cargo_edital_id = %s AND no_id IN ('S-ATO1', 'S-ATO2', 'A-ATOS')
                """,
                (cargo_1_id,),
            )
            res = {r[0]: r[1:] for r in cur.fetchall()}
            assert res["S-ATO2"] == (False, 0, 1, "cobrado_fora_do_edital")
            assert res["S-ATO1"][3] == "no_edital_nunca_cobrado"
            # O assunto-pai agrega o irmão previsto e a questão: aparece como cobrado.
            assert res["A-ATOS"][3] == "cobrado_no_edital"

            # Consistência 5D × 5E no nó da própria questão.
            cur.execute(
                """
                SELECT count(*) FILTER (
                    WHERE (evp.situacao = 'cobrado_fora_do_edital') <> qn.fora_do_edital)
                FROM vw_questao_no qn
                JOIN vw_questoes_contexto ctx ON ctx.questao_id = qn.questao_id
                JOIN vw_edital_vs_prova evp ON evp.cargo_edital_id = ctx.cargo_edital_id
                                           AND evp.no_id = qn.no_id
                WHERE qn.questao_id = %s
                """,
                (q_id,),
            )
            assert cur.fetchone()[0] == 0
