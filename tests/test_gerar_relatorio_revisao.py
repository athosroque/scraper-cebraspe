import json

from scripts.gerar_relatorio_revisao import gerar_relatorios


def _escrever_json(path, dados):
    path.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _fixture_basica():
    resultado = {
        "edital": "Edital_A.pdf",
        "total_chunks": 2,
        "extraidos_com_sucesso": 1,
        "falhas": 1,
        "status_revisao_humana": "PENDENTE — teste.",
        "chunks_com_falha": [{"chunk_index": 1, "cargo": None, "materia_esperada": "MATERIA B"}],
        "resultados": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia_chunk": "MATERIA A",
                "taxonomia_extraida": {
                    "materia": "Matéria A",
                    "topicos": [{"nome": "1 Tópico um", "subtopicos": ["1.1 Subtópico"]}],
                },
            }
        ],
    }
    auditoria = {
        "chunks": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia": "MATERIA A",
                "texto_enviado_llm": "1 Tópico um. 2 Tópico dois não extraído.",
                "status": "sucesso",
            },
            {
                "chunk_index": 1,
                "cargo": None,
                "materia": "MATERIA B",
                "texto_enviado_llm": "1 Conteúdo não processado.",
                "status": "falha",
            },
        ]
    }
    validacao = {
        "edital": "Edital_A.pdf",
        "total_chunks_analisados": 2,
        "total_alertas": 1,
        "alertas": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia": "MATERIA A",
                "tipo": "topico_ausente",
                "numero_item": "2",
                "posicao_item": 1,
                "texto_item_origem": "Tópico dois não extraído.",
                "topico_nome_extraido": None,
            }
        ],
    }
    return resultado, auditoria, validacao


class TestGerarRelatorios:
    def test_gera_html_do_edital_e_index(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)

        assert (saida_dir / "Edital_A.html").exists()
        assert (saida_dir / "index.html").exists()

    def test_html_do_edital_contem_texto_fonte_e_taxonomia_lado_a_lado(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "Tópico um" in html
        assert "1.1 Subtópico" in html
        assert "class='col fonte'" in html
        assert "class='col taxonomia'" in html

    def test_alerta_topico_ausente_aparece_destacado_no_html(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "topico_ausente" in html
        assert "<mark>2 Tópico dois não extraído.</mark>" in html

    def test_chunk_com_falha_mostra_aviso_sem_taxonomia(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "falha na extração" in html

    def test_chunk_com_status_especifico_tambem_mostra_aviso_sem_taxonomia(self, tmp_path):
        # Não só o "falha" genérico — um status específico de falha semântica
        # (ex.: STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO, ver ADR-021) também
        # precisa ser reconhecido como "sem taxonomia", não renderizado como
        # se tivesse tido sucesso.
        resultado, auditoria, validacao = _fixture_basica()
        auditoria["chunks"][1]["status"] = "falha_nome_numerico_nao_mapeado"
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "falha na extração" in html
        assert "falha_nome_numerico_nao_mapeado" in html

    def test_edital_sem_validacao_json_gera_relatorio_sem_alertas(self, tmp_path):
        resultado, auditoria, _ = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")
        assert (saida_dir / "Edital_A.html").exists()
        assert "topico_ausente" not in html

    def test_edital_sem_auditoria_e_pulado_sem_erro(self, tmp_path):
        resultado, _, _ = _fixture_basica()
        _escrever_json(tmp_path / "Edital_Legado.json", resultado)

        saida_dir = gerar_relatorios(tmp_path)
        assert not (saida_dir / "Edital_Legado.html").exists()
        assert (saida_dir / "index.html").exists()

    def test_index_lista_edital_com_contagem_de_alertas(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        index_html = (saida_dir / "index.html").read_text(encoding="utf-8")

        assert "Edital_A.pdf" in index_html
        assert "Edital_A.html" in index_html
