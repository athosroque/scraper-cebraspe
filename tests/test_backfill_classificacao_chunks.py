import json
from unittest.mock import MagicMock

import pytest

from scripts import backfill_classificacao_chunks
from src.edital_parser import ChunkTaxonomia


class TestBackfillClassificacaoChunks:
    def test_backfill_tolera_diferencas_de_espacos_e_quebras_de_linha(
        self, monkeypatch, tmp_path, caplog
    ):
        json_file = tmp_path / "edital_teste.json"
        auditoria_file = tmp_path / "edital_teste.auditoria.json"

        auditoria_data = {
            "chunks": [
                {
                    "chunk_index": 0,
                    "materia": "LÍNGUA INGLESA (APENAS PARA O CARGO 3:\nANALISTA E PARA O CARGO 6: TÉCNICO)",
                    "cargo": None,
                }
            ]
        }
        json_data = {
            "status_revisao_humana": "APROVADO",
            "resultados": [
                {
                    "chunk_index": 0,
                    "materia_chunk": "LÍNGUA INGLESA (APENAS PARA O CARGO 3: ANALISTA E PARA O CARGO 6: TÉCNICO)",
                    "taxonomia_extraida": {"topicos": []},
                }
            ],
            "chunks_com_falha": [],
        }

        auditoria_file.write_text(json.dumps(auditoria_data), encoding="utf-8")
        json_file.write_text(json.dumps(json_data), encoding="utf-8")

        mock_secao = MagicMock()
        mock_secao.texto = "texto da secao"
        mock_secao.cargo_detectado = None
        mock_secao.nivel_detectado = "superior"
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "extrair_secao_objetos_avaliacao_detalhada",
            lambda p: mock_secao,
        )

        chunk = ChunkTaxonomia(
            cargo=None,
            materia="LÍNGUA INGLESA (APENAS PARA O CARGO 3:  ANALISTA E PARA O CARGO 6: TÉCNICO)",
            texto="texto 1",
            tipo_conhecimento="basico",
            nivel="superior",
        )
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "dividir_por_cargo_e_materia",
            lambda *args, **kwargs: [chunk],
        )
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "resolver_concurso_do_pdf",
            lambda p: {"slug": "TESTE_25", "orgao": "TESTE", "ano": 2025},
        )
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "mapear_cargos",
            lambda *args, **kwargs: [],
        )

        with caplog.at_level("INFO"):
            res = backfill_classificacao_chunks.backfill(
                tmp_path / "dummy.pdf", json_file, atualizar_artefatos=False
            )
        assert res["resultados"][0]["cargos_restritos"] == [3, 6]
        assert res["resultados"][0]["materia_normalizada"] == "LÍNGUA INGLESA"
        # Resumo do backfill conta os campos que mudaram na auditoria.
        assert "[BACKFILL] TESTE_25: 1 chunks" in caplog.text
        assert "1 chunks com cargos_restritos" in caplog.text
        assert "1 cargos_restritos" in caplog.text

    def test_backfill_lote_processa_arquivos_e_chama_atualizar(
        self, monkeypatch, tmp_path
    ):
        revisao_dir = tmp_path / "revisao"
        data_dir = tmp_path / "data"
        revisao_dir.mkdir()
        (data_dir / "Editais").mkdir(parents=True)

        json_file = revisao_dir / "Ed_1_TESTE.json"
        json_file.write_text("{}", encoding="utf-8")
        pdf_file = data_dir / "Editais" / "Ed_1_TESTE.pdf"
        pdf_file.write_text("%PDF-1.4", encoding="utf-8")

        chamadas_backfill = []
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "backfill",
            lambda pdf, jsn, atualizar_artefatos: chamadas_backfill.append(
                (pdf, jsn, atualizar_artefatos)
            ),
        )
        chamadas_atualizar = []
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "atualizar_artefatos_revisao",
            lambda d: chamadas_atualizar.append(d),
        )

        backfill_classificacao_chunks.backfill_lote(
            revisao_dir=revisao_dir,
            data_dir=data_dir,
            atualizar_artefatos=True,
        )

        assert len(chamadas_backfill) == 1
        assert chamadas_backfill[0] == (pdf_file, json_file, False)
        assert chamadas_atualizar == [revisao_dir]


def _preparar_backfill(monkeypatch, tmp_path, chunks_atuais, chunks_auditoria):
    json_file = tmp_path / "edital_teste.json"
    resultados = [
        {
            "chunk_index": c["chunk_index"],
            "materia_chunk": c["materia"],
            "taxonomia_extraida": {"topicos": []},
        }
        for c in chunks_auditoria
    ]
    json_file.write_text(
        json.dumps({"resultados": resultados, "chunks_com_falha": []}), encoding="utf-8"
    )
    (tmp_path / "edital_teste.auditoria.json").write_text(
        json.dumps({"chunks": chunks_auditoria}), encoding="utf-8"
    )

    secao = MagicMock(texto="secao", cargo_detectado=None, nivel_detectado=None)
    monkeypatch.setattr(
        backfill_classificacao_chunks,
        "extrair_secao_objetos_avaliacao_detalhada",
        lambda p: secao,
    )
    monkeypatch.setattr(
        backfill_classificacao_chunks,
        "dividir_por_cargo_e_materia",
        lambda *a, **k: chunks_atuais,
    )
    monkeypatch.setattr(
        backfill_classificacao_chunks, "resolver_concurso_do_pdf", lambda p: None
    )
    monkeypatch.setattr(
        backfill_classificacao_chunks, "mapear_cargos", lambda *a, **k: []
    )
    return json_file


class TestBackfillAlinhamento:
    def test_chunks_de_mesmo_nome_trocados_abortam_sem_gravar(
        self, monkeypatch, tmp_path
    ):
        # Básico superior e médio com o mesmo nome: só o texto distingue.
        auditoria = [
            {
                "chunk_index": 0,
                "materia": "LÍNGUA PORTUGUESA",
                "cargo": None,
                "texto_enviado_llm": "1 Superior.",
            },
            {
                "chunk_index": 1,
                "materia": "LÍNGUA PORTUGUESA",
                "cargo": None,
                "texto_enviado_llm": "1 Médio.",
            },
        ]
        atuais = [
            ChunkTaxonomia(cargo=None, materia="LÍNGUA PORTUGUESA", texto="1 Médio."),
            ChunkTaxonomia(
                cargo=None, materia="LÍNGUA PORTUGUESA", texto="1 Superior."
            ),
        ]
        json_file = _preparar_backfill(monkeypatch, tmp_path, atuais, auditoria)
        antes = json_file.read_text(encoding="utf-8")

        with pytest.raises(ValueError, match="divergente"):
            backfill_classificacao_chunks.backfill(
                tmp_path / "x.pdf", json_file, atualizar_artefatos=False
            )
        assert json_file.read_text(encoding="utf-8") == antes

    def test_texto_atual_sem_assinatura_final_e_aceito(self, monkeypatch, tmp_path):
        # A assinatura do fim da seção passou a ser removida depois da extração (ADR-025).
        auditoria = [
            {
                "chunk_index": 0,
                "materia": "X",
                "cargo": None,
                "texto_enviado_llm": "1 Item. FULANO\nDiretor",
            },
        ]
        atuais = [ChunkTaxonomia(cargo=None, materia="X", texto="1 Item.")]
        json_file = _preparar_backfill(monkeypatch, tmp_path, atuais, auditoria)

        res = backfill_classificacao_chunks.backfill(
            tmp_path / "x.pdf", json_file, atualizar_artefatos=False
        )
        assert res["resultados"][0]["materia_normalizada"] == "X"


class TestBackfillLote:
    def test_pdf_ausente_aborta_antes_de_gravar_qualquer_edital(
        self, monkeypatch, tmp_path
    ):
        revisao_dir, data_dir = tmp_path / "revisao", tmp_path / "data"
        (data_dir / "Editais").mkdir(parents=True)
        revisao_dir.mkdir()
        (revisao_dir / "Ed_A.json").write_text("{}", encoding="utf-8")
        (revisao_dir / "Ed_B.json").write_text("{}", encoding="utf-8")
        (data_dir / "Editais" / "Ed_A.pdf").write_text("%PDF-1.4", encoding="utf-8")

        chamadas = []
        monkeypatch.setattr(
            backfill_classificacao_chunks,
            "backfill",
            lambda *a, **k: chamadas.append(a),
        )

        with pytest.raises(FileNotFoundError, match="Ed_B"):
            backfill_classificacao_chunks.backfill_lote(
                revisao_dir, data_dir, atualizar_artefatos=False
            )
        assert chamadas == []

    def test_pdf_ambiguo_aborta(self, monkeypatch, tmp_path):
        revisao_dir, data_dir = tmp_path / "revisao", tmp_path / "data"
        for orgao in ("A", "B"):
            (data_dir / orgao / "Editais").mkdir(parents=True)
            (data_dir / orgao / "Editais" / "Ed_A.pdf").write_text(
                "%PDF-1.4", encoding="utf-8"
            )
        revisao_dir.mkdir()
        (revisao_dir / "Ed_A.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(
            backfill_classificacao_chunks, "backfill", lambda *a, **k: None
        )

        with pytest.raises(FileNotFoundError, match="achados 2"):
            backfill_classificacao_chunks.backfill_lote(
                revisao_dir, data_dir, atualizar_artefatos=False
            )
