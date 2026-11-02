import json

import sqlite_utils

from scripts.gerar_db_datasette import gerar_db


def _escrever_json(path, dados):
    path.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _resultado_com_auditoria():
    resultado = {
        "edital": "Edital_A.pdf",
        "total_chunks": 3,
        "extraidos_com_sucesso": 2,
        "falhas": 1,
        "chunks_com_falha": [
            {"chunk_index": 2, "cargo": None, "materia_esperada": "MATERIA C"}
        ],
        "resultados": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia_chunk": "MATERIA A",
                "taxonomia_extraida": {
                    "materia": "Matéria A",
                    "topicos": [
                        {"nome": "Tópico 1", "subtopicos": ["Sub 1.1", "Sub 1.2"]},
                        {"nome": "Tópico 2", "subtopicos": []},
                    ],
                },
            },
            {
                "chunk_index": 1,
                "cargo": None,
                "materia_chunk": "MATERIA B",
                "taxonomia_extraida": {
                    "materia": "Matéria B",
                    "topicos": [{"nome": "Tópico 3", "subtopicos": ["Sub 3.1"]}],
                },
            },
        ],
        "status_revisao_humana": "PENDENTE — teste.",
    }
    auditoria = {
        "edital": "Edital_A.pdf",
        "pdf_total_paginas": 10,
        "pdf_total_chars": 5000,
        "secao_objetos_avaliacao": {
            "marcador_inicio": "OBJETOS DE AVALIAÇÃO",
            "marcador_fim": "ANEXO I",
            "marcador_fim_encontrado": True,
            "offset_inicio_char": 1000,
            "offset_fim_char": 3000,
            "chars_secao": 2000,
            "chars_descartados_do_pdf": 3000,
        },
        "chunks": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia": "MATERIA A",
                "offset_inicio_secao": 0,
                "offset_fim_secao": 100,
                "chars": 100,
                "texto_enviado_llm": "texto da materia A",
                "status": "sucesso",
            },
            {
                "chunk_index": 1,
                "cargo": None,
                "materia": "MATERIA B",
                "offset_inicio_secao": 100,
                "offset_fim_secao": 200,
                "chars": 100,
                "texto_enviado_llm": "texto da materia B",
                "status": "sucesso",
            },
            {
                "chunk_index": 2,
                "cargo": None,
                "materia": "MATERIA C",
                "offset_inicio_secao": 200,
                "offset_fim_secao": 250,
                "chars": 50,
                "texto_enviado_llm": "texto da materia C",
                "status": "falha",
            },
        ],
    }
    return resultado, auditoria


def _resultado_legado_sem_auditoria():
    return {
        "edital": "Edital_Legado.pdf",
        "total_chunks": 1,
        "extraidos_com_sucesso": 1,
        "falhas": 0,
        "chunks_com_falha": [],
        "resultados": [
            {
                "cargo": None,
                "materia_chunk": "MATERIA LEGADA",
                "taxonomia_extraida": {
                    "materia": "Matéria Legada",
                    "topicos": [{"nome": "Tópico Legado", "subtopicos": []}],
                },
            }
        ],
        "status_revisao_humana": "PENDENTE — teste.",
    }


class TestGerarDb:
    def test_gera_banco_com_dados_de_edital_com_auditoria_e_sem_auditoria(
        self, tmp_path
    ):
        resultado_a, auditoria_a = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)
        _escrever_json(
            tmp_path / "Edital_Legado.json", _resultado_legado_sem_auditoria()
        )

        db_path = gerar_db(tmp_path)
        db = sqlite_utils.Database(db_path)

        assert db["editais"].count == 2
        assert db["chunks"].count == 4  # 3 do edital A + 1 do legado
        assert db["taxonomia_topicos"].count == 4  # 2 + 1 + 1(legado)
        assert db["taxonomia_subtopicos"].count == 3  # Sub 1.1, Sub 1.2, Sub 3.1

    def test_chunk_com_auditoria_carrega_offsets_e_texto(self, tmp_path):
        resultado_a, auditoria_a = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        chunk = next(db["chunks"].rows_where("materia = ?", ["MATERIA A"]))
        assert chunk["texto_enviado_llm"] == "texto da materia A"
        assert chunk["offset_inicio_secao"] == 0
        assert chunk["status"] == "sucesso"

        chunk_falho = next(db["chunks"].rows_where("status = 'falha'"))
        assert chunk_falho["materia"] == "MATERIA C"

    def test_chunk_legado_sem_auditoria_tem_chunk_index_nulo_mas_liga_topico(
        self, tmp_path
    ):
        _escrever_json(
            tmp_path / "Edital_Legado.json", _resultado_legado_sem_auditoria()
        )

        db = sqlite_utils.Database(gerar_db(tmp_path))
        chunk = next(db["chunks"].rows_where("edital = ?", ["Edital_Legado.pdf"]))
        assert chunk["chunk_index"] is None
        assert chunk["texto_enviado_llm"] is None

        topico = next(db["taxonomia_topicos"].rows_where("chunk_id = ?", [chunk["id"]]))
        assert topico["topico_nome"] == "Tópico Legado"

    def test_integridade_referencial_chunk_id_existe_em_chunks(self, tmp_path):
        resultado_a, auditoria_a = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        ids_chunks = {row["id"] for row in db["chunks"].rows}
        for topico in db["taxonomia_topicos"].rows:
            assert topico["chunk_id"] in ids_chunks
        ids_topicos = {row["id"] for row in db["taxonomia_topicos"].rows}
        for subtopico in db["taxonomia_subtopicos"].rows:
            assert subtopico["topico_id"] in ids_topicos

    def test_subtopico_guarda_o_caminho_origem_como_contexto(self, tmp_path):
        resultado_a, auditoria_a = _resultado_com_auditoria()
        topico = resultado_a["resultados"][0]["taxonomia_extraida"]["topicos"][0]
        nome = topico["subtopicos"][0]
        topico["caminho_origem"] = {nome: ["Avô", "Pai"]}
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        por_nome = {
            r["subtopico_nome"]: r["caminho_origem"]
            for r in db["taxonomia_subtopicos"].rows
        }

        assert por_nome[nome] == "Avô › Pai"
        assert None in por_nome.values()

    def test_tabelas_fts_sao_criadas(self, tmp_path):
        # Usa a fixture com subtópicos — a legada ("Tópico Legado") não tem
        # nenhum, então a tabela taxonomia_subtopicos nem chega a existir.
        resultado_a, auditoria_a = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        tabelas = set(db.table_names())
        assert "chunks_fts" in tabelas
        assert "taxonomia_topicos_fts" in tabelas
        assert "taxonomia_subtopicos_fts" in tabelas

    def test_busca_fts_encontra_texto_do_chunk(self, tmp_path):
        resultado_a, auditoria_a = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        achados = list(db["chunks"].search("materia B"))
        assert any(row["materia"] == "MATERIA B" for row in achados)

    def test_diretorio_sem_jsons_gera_banco_vazio_sem_erro(self, tmp_path):
        db = sqlite_utils.Database(gerar_db(tmp_path))
        assert not db["editais"].exists()

    def test_rebuild_apaga_estado_anterior(self, tmp_path):
        _escrever_json(
            tmp_path / "Edital_Legado.json", _resultado_legado_sem_auditoria()
        )
        db_path = gerar_db(tmp_path)
        assert sqlite_utils.Database(db_path)["editais"].count == 1

        (tmp_path / "Edital_Legado.json").unlink()
        db_path = gerar_db(tmp_path)
        db = sqlite_utils.Database(db_path)
        assert (db["editais"].count if db["editais"].exists() else 0) == 0

    def test_com_validacao_json_popula_alertas_e_total_alertas(self, tmp_path):
        resultado_a, auditoria_a = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado_a)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria_a)
        validacao = {
            "edital": "Edital_A.pdf",
            "total_chunks_analisados": 3,
            "total_alertas": 1,
            "alertas": [
                {
                    "chunk_index": 0,
                    "cargo": "CARGO 1: ADMINISTRADOR",
                    "materia": "MATERIA A",
                    "tipo": "topico_ausente",
                    "numero_item": "9",
                    "texto_item_origem": "Item não extraído.",
                    "topico_nome_extraido": None,
                }
            ],
        }
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        edital = next(db["editais"].rows_where("edital = ?", ["Edital_A.pdf"]))
        assert edital["total_alertas"] == 1

        alerta = next(db["alertas_validacao"].rows)
        assert alerta["tipo"] == "topico_ausente"
        assert alerta["numero_item"] == "9"
        chunk_a = next(db["chunks"].rows_where("materia = ?", ["MATERIA A"]))
        assert alerta["chunk_id"] == chunk_a["id"]

    def test_sem_validacao_json_total_alertas_fica_nulo_sem_erro(self, tmp_path):
        _escrever_json(
            tmp_path / "Edital_Legado.json", _resultado_legado_sem_auditoria()
        )

        db = sqlite_utils.Database(gerar_db(tmp_path))
        edital = next(db["editais"].rows)
        assert edital["total_alertas"] is None
        assert not db["alertas_validacao"].exists()

    def test_validacao_json_nao_e_tratado_como_json_de_edital(self, tmp_path):
        _escrever_json(
            tmp_path / "Edital_Legado.json", _resultado_legado_sem_auditoria()
        )
        _escrever_json(
            tmp_path / "Edital_Legado.validacao.json",
            {
                "edital": "Edital_Legado.pdf",
                "total_chunks_analisados": 1,
                "total_alertas": 0,
                "alertas": [],
            },
        )

        db = sqlite_utils.Database(gerar_db(tmp_path))
        assert db["editais"].count == 1

    def test_concurso_e_classificacao_permitem_filtrar_por_nivel_e_tipo(self, tmp_path):
        # ADR-020: mesma matéria em básico superior e básico médio tem que
        # sair distinguível na tabela filtrável (taxonomia_topicos).
        resultado, auditoria = _resultado_com_auditoria()
        classificacao = {
            0: {
                "tipo_conhecimento": "basico",
                "nivel": "superior",
                "cargo_numero": None,
            },
            1: {"tipo_conhecimento": "basico", "nivel": "medio", "cargo_numero": None},
            2: {
                "tipo_conhecimento": "especifico",
                "nivel": "medio",
                "cargo_numero": 15,
            },
        }
        for item in (
            auditoria["chunks"]
            + resultado["resultados"]
            + resultado["chunks_com_falha"]
        ):
            item.update(
                classificacao[item["chunk_index"]],
                materia_normalizada="LÍNGUA PORTUGUESA",
                apenas_discursiva=False,
            )
        resultado["concurso"] = {"slug": "PF_25_ADM", "orgao": "PF", "ano": 2025}
        resultado["cargos"] = [
            {"numero": 15, "nome": "AGENTE ADMINISTRATIVO", "nivel": "medio"}
        ]
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)

        db = sqlite_utils.Database(gerar_db(tmp_path))

        linhas = db.execute(
            "select nivel, count(*) from taxonomia_topicos "
            "where concurso_slug = 'PF_25_ADM' and tipo_conhecimento = 'basico' group by nivel order by nivel"
        ).fetchall()
        assert linhas == [("medio", 1), ("superior", 2)]
        # Regressão: 1ª linha com cargo_numero=None fazia a coluna virar TEXT.
        assert db["chunks"].columns_dict["cargo_numero"] is int
        assert db.execute("select max(cargo_numero) from chunks").fetchone() == (15,)
        assert list(db["cargos"].rows_where(select="concurso_slug, numero, nivel")) == [
            {"concurso_slug": "PF_25_ADM", "numero": 15, "nivel": "medio"}
        ]

    def test_json_anterior_ao_adr_020_gera_colunas_nulas_sem_erro(self, tmp_path):
        resultado, auditoria = _resultado_com_auditoria()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)

        db = sqlite_utils.Database(gerar_db(tmp_path))
        assert {r["nivel"] for r in db["taxonomia_topicos"].rows} == {None}
        assert next(db["editais"].rows)["concurso_slug"] is None
        assert not db["cargos"].exists()
