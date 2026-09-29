import uuid
from pathlib import Path

import pytest

from src import arvore, classificacao, questoes_writer, stats_writer
from src.candidatos_questao import (
    candidatos_preferenciais,
    candidatos_reserva,
    montar_lotes,
)
from tests.test_stats_writer import _postgres_disponivel


def test_candidatos_reserva_hierarquia():
    arv = arvore.ArvoreMestre()
    arvore.criar_no(arv, "materia", "DIREITO ADMINISTRATIVO", None, id_override="M-ADM")
    arvore.criar_no(
        arv, "assunto", "Atos Administrativos", "M-ADM", id_override="A-ATOS"
    )
    arvore.criar_no(arv, "subassunto", "Anulação", "A-ATOS", id_override="S-ANUL")

    arvore.criar_no(arv, "materia", "INFORMÁTICA", None, id_override="M-INF")
    arvore.criar_no(arv, "assunto", "Redes", "M-INF", id_override="A-REDES")
    arvore.criar_no(arv, "subassunto", "Protocolos", "A-REDES", id_override="S-PROT")

    # Aposentado
    arvore.criar_no(arv, "subassunto", "Obsoleto", "A-ATOS", id_override="S-OBS")
    arvore.aposentar_no(arv, "S-OBS")

    # Filtra apenas DIREITO ADMINISTRATIVO
    res = candidatos_reserva(arv, {"M-ADM"})
    assert "M-ADM" in res
    assert "A-ATOS" in res
    assert "S-ANUL" in res

    # INFORMÁTICA e aposentado não devem entrar
    assert "M-INF" not in res
    assert "A-REDES" not in res
    assert "S-OBS" not in res

    # Valida caminhos e chaves
    assert res["M-ADM"]["caminho"] == "DIREITO ADMINISTRATIVO"
    assert res["M-ADM"]["nivel"] == "materia"
    assert res["M-ADM"]["pai_id"] is None
    assert res["M-ADM"]["assunto_id"] is None

    assert res["A-ATOS"]["caminho"] == "DIREITO ADMINISTRATIVO > Atos Administrativos"
    assert res["A-ATOS"]["nivel"] == "assunto"
    assert res["A-ATOS"]["pai_id"] == "M-ADM"
    assert res["A-ATOS"]["assunto_id"] == "A-ATOS"

    assert (
        res["S-ANUL"]["caminho"]
        == "DIREITO ADMINISTRATIVO > Atos Administrativos > Anulação"
    )
    assert res["S-ANUL"]["nivel"] == "subassunto"
    assert res["S-ANUL"]["pai_id"] == "A-ATOS"
    assert res["S-ANUL"]["assunto_id"] == "A-ATOS"


def test_montar_lotes_vazio():
    assert montar_lotes([]) == []


def test_montar_lotes_texto_base_indiviso():
    # 12 questões com o mesmo texto-base não devem ser fatiadas
    questoes = [
        {
            "numero": i,
            "secao": "Secao 1",
            "texto_base_id": 101,
            "enunciado": f"Item {i}",
        }
        for i in range(1, 13)
    ]
    lotes = montar_lotes(questoes, max_tamanho=10)
    assert len(lotes) == 1
    assert len(lotes[0]) == 12


def test_montar_lotes_fatiamento_sem_texto_base():
    # 25 questões sem texto-base da mesma seção devem ser fatiadas em [10, 10, 5]
    questoes = [
        {
            "numero": i,
            "secao": "Direito Const",
            "texto_base_id": None,
            "enunciado": f"Item {i}",
        }
        for i in range(1, 26)
    ]
    lotes = montar_lotes(questoes, max_tamanho=10)
    assert len(lotes) == 3
    assert [len(l) for l in lotes] == [10, 10, 5]


def test_montar_lotes_juncao_grupos_pequenos_adjacentes():
    # Seção A tem 3 itens, Seção B tem 4 itens -> devem ser agrupados num único lote de 7
    questoes = [
        {"numero": 1, "secao": "Sec A", "texto_base_id": None},
        {"numero": 2, "secao": "Sec A", "texto_base_id": None},
        {"numero": 3, "secao": "Sec A", "texto_base_id": None},
        {"numero": 4, "secao": "Sec B", "texto_base_id": None},
        {"numero": 5, "secao": "Sec B", "texto_base_id": None},
        {"numero": 6, "secao": "Sec B", "texto_base_id": None},
        {"numero": 7, "secao": "Sec B", "texto_base_id": None},
    ]
    lotes = montar_lotes(questoes, max_tamanho=10)
    assert len(lotes) == 1
    assert len(lotes[0]) == 7


def test_montar_lotes_misto_com_e_sem_texto_base():
    questoes = [
        # Bloco sem TB: 3 itens
        {"numero": 1, "secao": "Sec 1", "texto_base_id": None},
        {"numero": 2, "secao": "Sec 1", "texto_base_id": None},
        {"numero": 3, "secao": "Sec 1", "texto_base_id": None},
        # Bloco com TB: 4 itens
        {"numero": 4, "secao": "Sec 2", "texto_base_id": 99},
        {"numero": 5, "secao": "Sec 2", "texto_base_id": 99},
        {"numero": 6, "secao": "Sec 2", "texto_base_id": 99},
        {"numero": 7, "secao": "Sec 2", "texto_base_id": 99},
        # Bloco sem TB: 2 itens
        {"numero": 8, "secao": "Sec 3", "texto_base_ordem": None},
        {"numero": 9, "secao": "Sec 3", "texto_base_ordem": None},
    ]
    lotes = montar_lotes(questoes, max_tamanho=10)
    assert len(lotes) == 3
    assert [len(l) for l in lotes] == [3, 4, 2]
    assert lotes[0][0]["numero"] == 1
    assert lotes[1][0]["numero"] == 4
    assert lotes[2][0]["numero"] == 8


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="PostgreSQL de teste não disponível"
)
class TestCandidatosEIntegracaoPostgres:
    @pytest.fixture
    def conn_banco(self):
        conn = stats_writer.conectar()
        try:
            yield conn
        finally:
            conn.close()

    def test_candidatos_preferenciais_prova_real(self, conn_banco):
        with conn_banco.cursor() as cur:
            # Busca uma prova objetiva básica existente no banco
            cur.execute(
                "SELECT id, tipo FROM provas WHERE tipo = 'objetiva_basica' LIMIT 1"
            )
            row_basica = cur.fetchone()

            # Busca uma prova objetiva específica existente no banco
            cur.execute(
                "SELECT id, tipo FROM provas WHERE tipo = 'objetiva_especifica' LIMIT 1"
            )
            row_especifica = cur.fetchone()

        if not row_basica or not row_especifica:
            pytest.skip("Provas básicas/específicas não encontradas no banco.")

        cands_basica = candidatos_preferenciais(conn_banco, row_basica[0])
        assert len(cands_basica) > 0
        # Todos os nós retornados devem ter id, nome, nivel e caminho preenchidos
        for no_id, info in cands_basica.items():
            assert info["id"] == no_id
            assert info["nome"]
            assert info["nivel"] in ("materia", "assunto", "subassunto")
            assert info["caminho"]

        cands_esp = candidatos_preferenciais(conn_banco, row_especifica[0])
        assert len(cands_esp) > 0

    @pytest.fixture
    def conn_isolada(self):
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

    def _popular_minimo(self, conn) -> int:
        """Concurso, prova e árvore mínimos no schema isolado. Retorna prova_id."""
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dim_ano (ano) VALUES (2025) ON CONFLICT DO NOTHING"
            )
            cur.execute("INSERT INTO dim_orgao (sigla) VALUES ('PF') RETURNING id")
            orgao_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO concursos (slug, ano, orgao_id) VALUES ('PF_25_ADM', 2025, %s) RETURNING id",
                (orgao_id,),
            )
            concurso_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO provas (concurso_id, arquivo, tipo, codigo_caderno)
                VALUES (%s, '094_PF_015_01.pdf', 'objetiva_basica', '094_PF_015_01')
                RETURNING id
                """,
                (concurso_id,),
            )
            prova_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO no_arvore (id, nivel, nome, origem, status, pai_id)
                VALUES
                    ('M-DIR_CONST', 'materia', 'DIREITO CONSTITUCIONAL', 'humano', 'ativo', NULL),
                    ('A-PODER_CONST', 'assunto', 'Poder Constituinte', 'humano', 'ativo', 'M-DIR_CONST')
                """
            )
        conn.commit()
        return prova_id

    def _gravar_questoes(self, conn, prova_id: int, enunciados: dict[int, str]):
        questoes_writer.gravar_caderno_objetivo(
            conn,
            prova_id,
            {
                "textos_base": [],
                "alertas": [],
                "questoes": [
                    {
                        "numero": numero,
                        "enunciado": enunciado,
                        "gabarito": "C",
                        "anulada": False,
                        "figuras": [],
                        "secao": "Conhecimentos Básicos",
                        "alertas": [],
                    }
                    for numero, enunciado in enunciados.items()
                ],
            },
        )

    @staticmethod
    def _registro(chave: str, enunciado: str, no_id: str, status: str):
        return classificacao.RegistroQuestao(
            chave=chave,
            hash_enunciado=classificacao.calcular_hash_enunciado(enunciado),
            sem_no=False,
            apontamentos=[
                classificacao.ApontamentoQuestao(
                    no_id=no_id,
                    papel="principal",
                    confianca="alta",
                    status=status,
                )
            ],
        )

    def test_aplicar_classificacao_idempotente(self, conn_isolada, tmp_path: Path):
        prova_id = self._popular_minimo(conn_isolada)
        enunciados = {1: "Item 1 sobre poder constituinte", 2: "Item 2 sobre limites"}
        self._gravar_questoes(conn_isolada, prova_id, enunciados)

        cq = classificacao.ClassificacaoQuestoes()
        for numero, texto in enunciados.items():
            chave = f"PF_25_ADM|094_PF_015_01|{numero}"
            cq.registros[chave] = self._registro(
                chave,
                texto,
                "A-PODER_CONST" if numero == 1 else "M-DIR_CONST",
                "aprovado" if numero == 1 else "proposto",
            )
        classif_path = tmp_path / "classificacao_questoes.json"
        classificacao.salvar(cq, classif_path)

        totais = stats_writer.aplicar_classificacao(conn_isolada, classif_path)
        assert totais["questao_no"] == 2
        assert totais["desatualizados"] == 0

        with conn_isolada.cursor() as cur:
            cur.execute(
                "SELECT q.numero, qn.no_id, qn.status FROM questao_no qn "
                "JOIN questoes q ON q.id = qn.questao_id ORDER BY q.numero"
            )
            assert cur.fetchall() == [
                (1, "A-PODER_CONST", "aprovado"),
                (2, "M-DIR_CONST", "proposto"),
            ]

        # Reaplicar é idempotente
        assert stats_writer.aplicar_classificacao(conn_isolada, classif_path) == totais

    def test_aplicar_classificacao_pula_enunciado_divergente(
        self, conn_isolada, tmp_path: Path
    ):
        """Reextração que muda o texto da questão não herda a classificação antiga."""
        prova_id = self._popular_minimo(conn_isolada)
        v1 = {1: "Item 1 sobre poder constituinte", 2: "Item 2 sobre limites"}
        self._gravar_questoes(conn_isolada, prova_id, v1)

        cq = classificacao.ClassificacaoQuestoes()
        for numero, texto in v1.items():
            chave = f"PF_25_ADM|094_PF_015_01|{numero}"
            cq.registros[chave] = self._registro(
                chave, texto, "A-PODER_CONST", "aprovado"
            )
        classif_path = tmp_path / "classificacao_questoes.json"
        classificacao.salvar(cq, classif_path)

        # Reextração: a questão 2 mudou de texto, a 1 ficou igual
        v2 = {1: v1[1], 2: "Item 2 completamente diferente"}
        self._gravar_questoes(conn_isolada, prova_id, v2)

        totais = stats_writer.aplicar_classificacao(conn_isolada, classif_path)
        assert totais["questao_no"] == 1
        assert totais["desatualizados"] == 1
        with conn_isolada.cursor() as cur:
            cur.execute(
                "SELECT q.numero FROM questao_no qn "
                "JOIN questoes q ON q.id = qn.questao_id"
            )
            assert cur.fetchall() == [(1,)]

    def test_reextracao_caderno_restaura_classificacao_end_to_end(
        self, conn_isolada, tmp_path: Path
    ):
        """Critério de Pronto (Sessão A):
        Comprova que aplicar_classificacao restaura integralmente os vínculos
        em questao_no e na view vw_questao_no após uma reextração (DELETE + INSERT)
        de caderno realizada por questoes_writer.gravar_caderno_objetivo.
        """
        # 1. Popula dados estruturais mínimos no schema isolado
        with conn_isolada.cursor() as cur:
            cur.execute(
                "INSERT INTO dim_ano (ano) VALUES (2025) ON CONFLICT DO NOTHING"
            )
            cur.execute("INSERT INTO dim_orgao (sigla) VALUES ('PF') RETURNING id")
            orgao_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO concursos (slug, ano, orgao_id) VALUES ('PF_25_ADM', 2025, %s) RETURNING id",
                (orgao_id,),
            )
            concurso_id = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO provas (concurso_id, arquivo, tipo, codigo_caderno)
                VALUES (%s, '094_PF_015_01.pdf', 'objetiva_basica', '094_PF_015_01')
                RETURNING id
                """,
                (concurso_id,),
            )
            prova_id = cur.fetchone()[0]

            # Cria nós na árvore mestre (matéria -> assunto)
            cur.execute(
                """
                INSERT INTO no_arvore (id, nivel, nome, origem, status, pai_id)
                VALUES
                    ('M-DIR_CONST', 'materia', 'DIREITO CONSTITUCIONAL', 'humano', 'ativo', NULL),
                    ('A-PODER_CONST', 'assunto', 'Poder Constituinte', 'humano', 'ativo', 'M-DIR_CONST')
                """
            )
        conn_isolada.commit()

        # 2. Grava primeira extração de questões via questoes_writer
        resultado_v1 = {
            "textos_base": [],
            "alertas": [],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item 1 sobre poder constituinte",
                    "gabarito": "C",
                    "anulada": False,
                    "figuras": [],
                    "secao": "Conhecimentos Básicos",
                    "alertas": [],
                },
                {
                    "numero": 2,
                    "enunciado": "Item 2 sobre limitações ao poder constituinte",
                    "gabarito": "E",
                    "anulada": False,
                    "figuras": [],
                    "secao": "Conhecimentos Básicos",
                    "alertas": [],
                },
            ],
        }
        n_extraidas_v1 = questoes_writer.gravar_caderno_objetivo(
            conn_isolada, prova_id, resultado_v1
        )
        assert n_extraidas_v1 == 2

        with conn_isolada.cursor() as cur:
            cur.execute(
                "SELECT id, numero FROM questoes WHERE prova_id = %s ORDER BY numero",
                (prova_id,),
            )
            questoes_v1 = cur.fetchall()
        id_q1_v1, id_q2_v1 = questoes_v1[0][0], questoes_v1[1][0]

        # 3. Monta e salva o arquivo canônico com apontamentos aprovado e proposto
        path_teste = tmp_path / "classificacao_questoes.json"
        chave_q1 = "PF_25_ADM|094_PF_015_01|1"
        chave_q2 = "PF_25_ADM|094_PF_015_01|2"

        cq = classificacao.ClassificacaoQuestoes()
        cq.registros[chave_q1] = classificacao.RegistroQuestao(
            chave=chave_q1,
            hash_enunciado=classificacao.calcular_hash_enunciado(
                "Item 1 sobre poder constituinte"
            ),
            sem_no=False,
            apontamentos=[
                classificacao.ApontamentoQuestao(
                    no_id="A-PODER_CONST",
                    papel="principal",
                    confianca="alta",
                    fora_do_edital=False,
                    origem="llm",
                    status="aprovado",
                )
            ],
        )
        cq.registros[chave_q2] = classificacao.RegistroQuestao(
            chave=chave_q2,
            hash_enunciado=classificacao.calcular_hash_enunciado(
                "Item 2 sobre limitações ao poder constituinte"
            ),
            sem_no=False,
            apontamentos=[
                classificacao.ApontamentoQuestao(
                    no_id="M-DIR_CONST",
                    papel="principal",
                    confianca="media",
                    fora_do_edital=False,
                    origem="llm",
                    status="proposto",
                )
            ],
        )
        classificacao.salvar(cq, path_teste)

        # 4. Aplica classificação e valida dados em questao_no e na view vw_questao_no
        totais_v1 = stats_writer.aplicar_classificacao(conn_isolada, path_teste)
        assert totais_v1.get("questao_no") == 2

        with conn_isolada.cursor() as cur:
            # questao_no contém ambos os registros (aprovado e proposto)
            cur.execute(
                "SELECT questao_id, no_id, papel, confianca, status FROM questao_no ORDER BY questao_id"
            )
            linhas_qn_v1 = cur.fetchall()
            assert len(linhas_qn_v1) == 2
            assert linhas_qn_v1[0] == (
                id_q1_v1,
                "A-PODER_CONST",
                "principal",
                "alta",
                "aprovado",
            )
            assert linhas_qn_v1[1] == (
                id_q2_v1,
                "M-DIR_CONST",
                "principal",
                "media",
                "proposto",
            )

            # vw_questao_no expõe apenas registros com status = 'aprovado' e nós resolvidos
            cur.execute(
                """
                SELECT questao_id, codigo_caderno, numero, no_id, no_nome, no_caminho, papel, confianca
                FROM vw_questao_no
                ORDER BY questao_id
                """
            )
            linhas_vw_v1 = cur.fetchall()
            assert len(linhas_vw_v1) == 1
            assert linhas_vw_v1[0] == (
                id_q1_v1,
                "094_PF_015_01",
                1,
                "A-PODER_CONST",
                "Poder Constituinte",
                "DIREITO CONSTITUCIONAL > Poder Constituinte",
                "principal",
                "alta",
            )

        # 5. Simula reextração do caderno (DELETE + INSERT via gravar_caderno_objetivo)
        resultado_v2 = {
            "textos_base": [],
            "alertas": [],
            "questoes": [
                {
                    "numero": 1,
                    "enunciado": "Item 1 sobre poder constituinte",
                    "gabarito": "C",
                    "anulada": False,
                    "figuras": [],
                    "secao": "Conhecimentos Básicos",
                    "alertas": [],
                },
                {
                    "numero": 2,
                    "enunciado": "Item 2 sobre limitações ao poder constituinte",
                    "gabarito": "E",
                    "anulada": False,
                    "figuras": [],
                    "secao": "Conhecimentos Básicos",
                    "alertas": [],
                },
            ],
        }
        n_extraidas_v2 = questoes_writer.gravar_caderno_objetivo(
            conn_isolada, prova_id, resultado_v2
        )
        assert n_extraidas_v2 == 2

        with conn_isolada.cursor() as cur:
            cur.execute(
                "SELECT id, numero FROM questoes WHERE prova_id = %s ORDER BY numero",
                (prova_id,),
            )
            questoes_v2 = cur.fetchall()
            id_q1_v2, id_q2_v2 = questoes_v2[0][0], questoes_v2[1][0]
            # Novos IDs foram gerados pela sequência SERIAL do PostgreSQL
            assert id_q1_v2 != id_q1_v1
            assert id_q2_v2 != id_q2_v1

            # CASCADE no banco eliminou os apontamentos órfãos anteriores
            cur.execute("SELECT count(*) FROM questao_no")
            assert cur.fetchone()[0] == 0
            cur.execute("SELECT count(*) FROM vw_questao_no")
            assert cur.fetchone()[0] == 0

        # 6. Chamar stats_writer.aplicar_classificacao e comprovar restauração integral
        totais_v2 = stats_writer.aplicar_classificacao(conn_isolada, path_teste)
        assert totais_v2.get("questao_no") == 2

        with conn_isolada.cursor() as cur:
            cur.execute(
                "SELECT questao_id, no_id, papel, confianca, status FROM questao_no ORDER BY questao_id"
            )
            linhas_qn_v2 = cur.fetchall()
            assert len(linhas_qn_v2) == 2
            # Vínculos agora apontam para os novos IDs de questões gerados na reextração
            assert linhas_qn_v2[0] == (
                id_q1_v2,
                "A-PODER_CONST",
                "principal",
                "alta",
                "aprovado",
            )
            assert linhas_qn_v2[1] == (
                id_q2_v2,
                "M-DIR_CONST",
                "principal",
                "media",
                "proposto",
            )

            # vw_questao_no reflete perfeitamente o caderno reextraído com os novos IDs
            cur.execute(
                """
                SELECT questao_id, codigo_caderno, numero, no_id, no_nome, no_caminho, papel, confianca
                FROM vw_questao_no
                ORDER BY questao_id
                """
            )
            linhas_vw_v2 = cur.fetchall()
            assert len(linhas_vw_v2) == 1
            assert linhas_vw_v2[0] == (
                id_q1_v2,
                "094_PF_015_01",
                1,
                "A-PODER_CONST",
                "Poder Constituinte",
                "DIREITO CONSTITUCIONAL > Poder Constituinte",
                "principal",
                "alta",
            )
