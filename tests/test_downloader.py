import json
from unittest.mock import MagicMock, patch

import pytest

from src import downloader

PDF_BYTES = b"%PDF-1.4\n%mock pdf content\n"
HTML_BYTES = b"<html><body>404 not found</body></html>"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(downloader, "stealth_wait", lambda: None)


def fake_response(content: bytes, content_type: str = "application/pdf"):
    resp = MagicMock()
    resp.content = content
    resp.headers = {"Content-Type": content_type}
    resp.raise_for_status.return_value = None
    return resp


class TestSlugify:
    def test_normaliza_acentos_e_espacos(self):
        assert (
            downloader.slugify("Tribunal de Justiça do Ceará")
            == "TRIBUNAL_DE_JUSTICA_DO_CEARA"
        )

    def test_string_vazia_usa_fallback(self):
        assert downloader.slugify("") == "ORGAO_DESCONHECIDO"

    def test_determinismo_case_insensitive(self):
        assert downloader.slugify("INSS") == downloader.slugify("inss")


class TestIsValidPdf:
    def test_aceita_magic_bytes_com_content_type_pdf(self):
        assert downloader._is_valid_pdf(PDF_BYTES, "application/pdf") is True

    def test_aceita_magic_bytes_com_octet_stream(self):
        assert downloader._is_valid_pdf(PDF_BYTES, "application/octet-stream") is True

    def test_rejeita_conteudo_html(self):
        assert downloader._is_valid_pdf(HTML_BYTES, "text/html") is False

    def test_rejeita_mesmo_com_content_type_pdf_se_magic_bytes_nao_batem(self):
        assert downloader._is_valid_pdf(HTML_BYTES, "application/pdf") is False


class TestDownloadPdf:
    def test_baixa_e_grava_arquivo_novo(self, tmp_path):
        manifest = {}
        with patch.object(
            downloader.requests, "get", return_value=fake_response(PDF_BYTES)
        ) as mock_get:
            path = downloader.download_pdf(
                "https://x.test/edital.pdf", tmp_path, manifest
            )

        assert path is not None
        assert path.exists()
        assert path.read_bytes() == PDF_BYTES
        assert mock_get.call_count == 1
        assert "https://x.test/edital.pdf" in manifest

    def test_pula_download_se_ja_no_manifesto(self, tmp_path):
        existing = tmp_path / "edital.pdf"
        existing.write_bytes(PDF_BYTES)
        manifest = {"https://x.test/edital.pdf": {"hash": "x", "path": str(existing)}}

        with patch.object(downloader.requests, "get") as mock_get:
            path = downloader.download_pdf(
                "https://x.test/edital.pdf", tmp_path, manifest
            )

        assert path == existing
        mock_get.assert_not_called()

    def test_rejeita_conteudo_invalido_e_nao_grava(self, tmp_path):
        manifest = {}
        with patch.object(
            downloader.requests,
            "get",
            return_value=fake_response(HTML_BYTES, "text/html"),
        ):
            path = downloader.download_pdf(
                "https://x.test/quebrado.pdf", tmp_path, manifest
            )

        assert path is None
        assert list(tmp_path.iterdir()) == []
        assert manifest == {}

    def test_dedup_por_hash_reaproveita_arquivo_existente(self, tmp_path):
        manifest = {}
        with patch.object(
            downloader.requests, "get", return_value=fake_response(PDF_BYTES)
        ):
            path_a = downloader.download_pdf("https://x.test/a.pdf", tmp_path, manifest)
            path_b = downloader.download_pdf("https://x.test/b.pdf", tmp_path, manifest)

        assert path_a == path_b
        assert len(list(tmp_path.glob("*.pdf"))) == 1

    def test_falha_de_rede_retorna_none(self, tmp_path):
        manifest = {}
        with patch.object(
            downloader.requests,
            "get",
            side_effect=downloader.requests.ConnectionError("timeout"),
        ):
            path = downloader.download_pdf(
                "https://x.test/edital.pdf", tmp_path, manifest
            )

        assert path is None
        assert manifest == {}


class TestDownloadConcursoPdfs:
    def test_organiza_por_categoria_em_hierarquia_ano_orgao(self, tmp_path):
        pdf_map = {
            "editais_abertura": ["https://x.test/edital.pdf"],
            "provas": ["https://x.test/prova.pdf"],
            "gabaritos": ["https://x.test/gabarito.pdf"],
        }
        # Conteúdo distinto por URL — bytes idênticos disparariam o dedup por
        # hash (testado à parte) e mascarariam a organização por categoria.
        respostas = {
            "https://x.test/edital.pdf": fake_response(PDF_BYTES + b"1"),
            "https://x.test/prova.pdf": fake_response(PDF_BYTES + b"2"),
            "https://x.test/gabarito.pdf": fake_response(PDF_BYTES + b"3"),
        }
        with patch.object(
            downloader.requests, "get", side_effect=lambda url, **kw: respostas[url]
        ):
            resultado = downloader.download_concurso_pdfs(
                "Tribunal de Justiça do Ceará", 2025, pdf_map, data_dir=tmp_path
            )

        base = tmp_path / "2025" / "CEBRASPE" / "TRIBUNAL_DE_JUSTICA_DO_CEARA"
        assert (base / "Editais" / "edital.pdf").exists()
        assert (base / "Provas" / "prova.pdf").exists()
        assert (base / "Gabaritos" / "gabarito.pdf").exists()
        assert resultado["editais_abertura"] == [str(base / "Editais" / "edital.pdf")]

    def test_falha_de_um_pdf_nao_aborta_os_demais(self, tmp_path):
        pdf_map = {
            "editais_abertura": ["https://x.test/edital.pdf"],
            "provas": [],
            "gabaritos": [],
        }
        with patch.object(
            downloader.requests,
            "get",
            side_effect=downloader.requests.ConnectionError("timeout"),
        ):
            resultado = downloader.download_concurso_pdfs(
                "Qualquer Orgao", 2025, pdf_map, data_dir=tmp_path
            )

        assert resultado == {"editais_abertura": [], "provas": [], "gabaritos": []}

    def test_reexecucao_nao_rebaixa_pdf_ja_presente(self, tmp_path):
        pdf_map = {
            "editais_abertura": ["https://x.test/edital.pdf"],
            "provas": [],
            "gabaritos": [],
        }

        with patch.object(
            downloader.requests, "get", return_value=fake_response(PDF_BYTES)
        ) as mock_get:
            downloader.download_concurso_pdfs(
                "Qualquer Orgao", 2025, pdf_map, data_dir=tmp_path
            )
            assert mock_get.call_count == 1

            downloader.download_concurso_pdfs(
                "Qualquer Orgao", 2025, pdf_map, data_dir=tmp_path
            )
            assert mock_get.call_count == 1


class TestResolverConcursoDoPdf:
    def _preparar(self, tmp_path, urls: list[str]):
        orgao_dir = tmp_path / "2025" / "CEBRASPE" / "PF"
        (orgao_dir / "Editais").mkdir(parents=True)
        manifest = {
            url: {"hash": "x", "path": f"/outra/copia/{url.rsplit('/', 1)[-1]}"}
            for url in urls
        }
        (orgao_dir / downloader.MANIFEST_FILENAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        return orgao_dir / "Editais"

    def test_resolve_slug_orgao_e_ano_pela_url_do_manifesto(self, tmp_path):
        # O path gravado no manifesto aponta pra outra cópia do repo (achado
        # real: worktree antiga) — o casamento tem que ser pelo nome do arquivo.
        editais = self._preparar(
            tmp_path,
            ["https://cdn.cebraspe.org.br/concursos/PF_25_ADM/arquivos/Ed_1.pdf"],
        )
        assert downloader.resolver_concurso_do_pdf(editais / "Ed_1.pdf") == {
            "slug": "PF_25_ADM",
            "orgao": "PF",
            "ano": 2025,
        }

    def test_mesmo_nome_de_arquivo_em_dois_concursos_do_orgao_e_ambiguo(self, tmp_path):
        editais = self._preparar(
            tmp_path,
            [
                "https://cdn.cebraspe.org.br/concursos/PF_25_ADM/arquivos/Ed_1.pdf",
                "https://cdn.cebraspe.org.br/concursos/PF_25_AGENTE/arquivos/Ed_1.pdf",
            ],
        )
        assert downloader.resolver_concurso_do_pdf(editais / "Ed_1.pdf") is None

    def test_pdf_fora_do_manifesto_retorna_none(self, tmp_path):
        editais = self._preparar(tmp_path, [])
        assert downloader.resolver_concurso_do_pdf(editais / "Ed_1.pdf") is None
