import json
from pathlib import Path
from unittest.mock import patch

import pymupdf
import pytest

from scripts.revisar_taxonomia_piloto import (
    avaliar_chunking_edital,
    main,
)
from src.edital_parser import avaliar_chunking_edital as parser_avaliar_chunking_edital


def _criar_pdf_teste(caminho: Path, texto: str) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=1000, height=40000)
    page.insert_text((72, 72), texto)
    doc.save(caminho)
    doc.close()
    return caminho


@pytest.fixture
def pdf_edital_valido(tmp_path):
    texto = (
        "EDITAL Nº 1 – CONCURSO PÚBLICO\n"
        "2 DO CARGO DE ANALISTA\n"
        "REQUISITOS: Diploma de nível superior.\n"
        "14 DOS OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)\n"
        "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
        "LÍNGUA PORTUGUESA:\n"
        "1 Compreensão e interpretação de textos. 2 Ortografia oficial.\n"
        "CONHECIMENTOS ESPECÍFICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
        "CARGO 1: ANALISTA DE SISTEMAS\n"
        "ENGENHARIA DE SOFTWARE:\n"
        "1 Ciclo de vida do software. 2 Metodologias ágeis. 3 Testes automatizados.\n"
        "ANEXO I\n"
        "CRONOGRAMA DO CONCURSO\n"
    )
    return _criar_pdf_teste(tmp_path / "Edital_Valido.pdf", texto)


class TestAvaliarChunkingEdital:
    def test_import_duplo(self):
        """Função exportada tanto em scripts.revisar_taxonomia_piloto quanto em src.edital_parser."""
        assert avaliar_chunking_edital is parser_avaliar_chunking_edital

    def test_secao_inexistente_levanta_value_error(self, tmp_path):
        pdf = _criar_pdf_teste(
            tmp_path / "Sem_Secao.pdf", "Texto simples sem marcador de avaliacao."
        )
        with pytest.raises(ValueError, match="não encontrada"):
            avaliar_chunking_edital(pdf)

    def test_chunking_valido_sem_alertas(self, pdf_edital_valido):
        res = avaliar_chunking_edital(pdf_edital_valido)
        assert res["edital"] == "Edital_Valido.pdf"
        assert res["total_chunks"] == 2
        assert len(res["alertas"]) == 0

        # Verifica metadados dos chunks
        c0 = res["chunks"][0]
        assert c0["materia"] == "LÍNGUA PORTUGUESA"
        assert c0["nivel"] == "superior"
        assert c0["tipo_conhecimento"] == "basico"
        assert c0["total_itens"] == 2
        assert c0["itens_count"] == 2
        assert c0["chars"] > 40

        c1 = res["chunks"][1]
        assert c1["materia"] == "ENGENHARIA DE SOFTWARE"
        assert c1["nivel"] == "superior"
        assert c1["tipo_conhecimento"] == "especifico"
        assert c1["cargo_numero"] == 1
        assert c1["total_itens"] == 3

        # Verifica detecção de cargos
        cargos = res["cargos"]
        assert len(cargos) == 1
        assert cargos[0]["numero"] == 1
        assert "ANALISTA DE SISTEMAS" in cargos[0]["nome"]

    def test_alerta_chunk_muito_curto(self, tmp_path):
        texto = (
            "14 DOS OBJETOS DE AVALIAÇÃO\n"
            "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            "MATÉRIA CURTA:\n"
            "1 Curto.\n"
            "ANEXO I\n"
        )
        pdf = _criar_pdf_teste(tmp_path / "Edital_Curto.pdf", texto)
        res = avaliar_chunking_edital(pdf)
        tipos = [a["tipo"] for a in res["alertas"]]
        assert "chunk_vazio_ou_curto" in tipos
        assert any("muito curto" in a["mensagem"] for a in res["alertas"])

    def test_alerta_chunk_gigantesco(self, tmp_path):
        texto_longo = "1 Tópico detalhado.\n" + ("linha de conteudo relevante.\n" * 700)
        texto = (
            "14 DOS OBJETOS DE AVALIAÇÃO\n"
            "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR\n"
            f"MATÉRIA LONGA:\n{texto_longo}\n"
            "ANEXO I\n"
        )
        pdf = _criar_pdf_teste(tmp_path / "Edital_Longo.pdf", texto)
        res = avaliar_chunking_edital(pdf)
        tipos = [a["tipo"] for a in res["alertas"]]
        assert "chunk_gigantesco" in tipos

    def test_alerta_chunk_sem_nivel(self, tmp_path):
        texto = (
            "14 DOS OBJETOS DE AVALIAÇÃO\n"
            "CONHECIMENTOS GERAIS PARA TODOS OS CARGOS\n"
            "MATÉRIA SEM NÍVEL:\n"
            "1 Tópico da matéria com tamanho razoável para teste.\n"
            "ANEXO I\n"
        )
        pdf = _criar_pdf_teste(tmp_path / "Edital_SemNivel.pdf", texto)
        res = avaliar_chunking_edital(pdf)
        tipos = [a["tipo"] for a in res["alertas"]]
        assert "chunk_sem_nivel" in tipos

    def test_alerta_materia_cargo_ou_area(self, tmp_path):
        # Simula caso onde matéria foi capturada com nome de cargo/área
        texto = (
            "14 DOS OBJETOS DE AVALIAÇÃO\n"
            "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL MÉDIO\n"
            "ADMINISTRAÇÃO PARA O CARGO 1:\n"
            "1 Tópico do cargo que virou matéria indevidamente.\n"
            "ANEXO I\n"
        )
        pdf = _criar_pdf_teste(tmp_path / "Edital_CargoMateria.pdf", texto)
        res = avaliar_chunking_edital(pdf)
        tipos = [a["tipo"] for a in res["alertas"]]
        assert "materia_eh_cargo_ou_area" in tipos

    def test_salva_auditoria_corretamente(self, pdf_edital_valido, tmp_path):
        auditoria_path = tmp_path / "auditoria" / "teste.auditoria.json"
        res = avaliar_chunking_edital(pdf_edital_valido, auditoria_path=auditoria_path)

        assert auditoria_path.exists()
        conteudo = json.loads(auditoria_path.read_text(encoding="utf-8"))
        assert conteudo["edital"] == "Edital_Valido.pdf"
        assert len(conteudo["chunks"]) == 2
        for chunk in conteudo["chunks"]:
            assert chunk["status"] == "so_chunking"
            assert "texto_enviado_llm" in chunk
        assert res["auditoria"] == conteudo

    def test_nao_chama_llm(self, pdf_edital_valido):
        with patch("src.taxonomia_extractor.extrair_taxonomia_chunk") as mock_extractor:
            avaliar_chunking_edital(pdf_edital_valido)
            mock_extractor.assert_not_called()


class TestSoChunkingCLI:
    def test_main_com_so_chunking(self, pdf_edital_valido, tmp_path, capsys):
        saida_json = tmp_path / "saida" / "Edital_Valido.json"
        auditoria_json = tmp_path / "saida" / "Edital_Valido.auditoria.json"

        with (
            patch("scripts.revisar_taxonomia_piloto.revisar_edital_piloto") as mock_rev,
            patch("src.taxonomia_extractor.extrair_taxonomia_chunk") as mock_extractor,
        ):
            codigo = main([str(pdf_edital_valido), str(saida_json), "--so-chunking"])

            assert codigo == 0
            mock_rev.assert_not_called()
            mock_extractor.assert_not_called()

        assert auditoria_json.exists()
        assert not saida_json.exists()  # Não deve salvar o JSON de extração do LLM

        captured = capsys.readouterr()
        assert "=== Chunking: Edital_Valido.pdf (2 chunks) ===" in captured.out
        assert "LÍNGUA PORTUGUESA" in captured.out
        assert "ENGENHARIA DE SOFTWARE" in captured.out
        assert "Nenhum alerta encontrado" in captured.out
        assert str(auditoria_json) in captured.out

    def test_main_com_so_chunking_ordem_inversa(self, pdf_edital_valido, capsys):
        with patch(
            "scripts.revisar_taxonomia_piloto.avaliar_chunking_edital"
        ) as mock_eval:
            mock_eval.return_value = {
                "edital": "Edital_Valido.pdf",
                "total_chunks": 1,
                "cargos": [],
                "alertas": [],
                "chunks": [
                    {
                        "chunk_index": 0,
                        "tipo_conhecimento": "basico",
                        "nivel": "medio",
                        "cargo_numero": None,
                        "materia": "PORTUGUÊS",
                        "total_itens": 2,
                        "chars": 100,
                    }
                ],
            }
            codigo = main(["--so-chunking", str(pdf_edital_valido)])
            assert codigo == 0
            mock_eval.assert_called_once()

    def test_main_sem_args_retorna_1(self, capsys):
        codigo = main([])
        assert codigo == 1
        captured = capsys.readouterr()
        assert "Uso: python -m scripts.revisar_taxonomia_piloto" in captured.out

    def test_main_sem_flag_chama_revisar_edital_piloto(
        self, pdf_edital_valido, tmp_path
    ):
        saida_json = tmp_path / "saida.json"
        with patch(
            "scripts.revisar_taxonomia_piloto.revisar_edital_piloto"
        ) as mock_rev:
            codigo = main([str(pdf_edital_valido), str(saida_json)])
            assert codigo == 0
            mock_rev.assert_called_once_with(pdf_edital_valido, saida_json)
