"""Testes do exportador do PDF executivo (Etapa 9/D4, KAN-71).

Os unitários não abrem navegador: cobrem a capa, o sumário, a junção dos PDFs e
a checagem das páginas. O teste de integração (marcado `slow`) monta um site
MkDocs mínimo em `tmp_path`, com um diagrama Mermaid, e roda o exportador de
ponta a ponta. Ele é pulado se o Chromium do Playwright não estiver instalado.
"""

import datetime
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from scripts import exportar_pdf_executivo as exp

METADADOS = {
    "title": "Título de teste",
    "author": "Athos Roque",
    "subject": "Assunto de teste",
}


def _pdf_com_paginas(n: int, texto: str = "conteúdo") -> bytes:
    documento = pymupdf.open()
    for indice in range(n):
        pagina = documento.new_page()
        pagina.insert_text((72, 72), f"{texto} {indice + 1}")
    dados = documento.tobytes()
    documento.close()
    return dados


# --- unitários ---------------------------------------------------------------


def test_html_capa_tem_titulo_autor_e_data():
    html = exp.html_capa(datetime.date(2026, 10, 13))

    assert "Scraper CEBRASPE" in html
    assert "Visão executiva" in html
    assert "Athos Roque" in html
    assert "13/10/2026" in html
    assert "docs.projetoathos.com.br" in html


def test_html_capa_escapa_caracteres_especiais(monkeypatch):
    monkeypatch.setattr(exp, "AUTOR", "Ana <script>")

    html = exp.html_capa(datetime.date(2026, 1, 2))

    assert "Ana <script>" not in html
    assert "Ana &lt;script&gt;" in html
    assert "02/01/2026" in html


def test_montar_toc_pula_capa_e_conta_paginas():
    blocos = [(None, 1), ("Visão executiva", 2), ("Arquitetura", 3), ("Roadmap", 1)]

    toc = exp.montar_toc(blocos)

    assert toc == [
        [1, "Visão executiva", 2],
        [1, "Arquitetura", 4],
        [1, "Roadmap", 7],
    ]


def test_juntar_pdfs_com_duas_partes_tem_paginas_metadados_e_sumario():
    capa = _pdf_com_paginas(1, "capa")
    secao = _pdf_com_paginas(2, "secao")

    pdf = exp.juntar_pdfs([capa, secao], [None, "Arquitetura"], METADADOS)

    documento = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        assert documento.page_count == 3
        assert documento.metadata["title"] == "Título de teste"
        assert documento.metadata["author"] == "Athos Roque"
        assert documento.metadata["subject"] == "Assunto de teste"
        assert documento.get_toc() == [[1, "Arquitetura", 2]]
    finally:
        documento.close()


def test_juntar_pdfs_com_tres_partes_tem_sumario_com_cada_titulo():
    capa = _pdf_com_paginas(1, "capa")
    pdfs = [
        capa,
        _pdf_com_paginas(1, "a"),
        _pdf_com_paginas(3, "b"),
        _pdf_com_paginas(2),
    ]

    pdf = exp.juntar_pdfs(
        pdfs, [None, "Visão executiva", "Números", "Roadmap"], METADADOS
    )

    documento = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        assert documento.page_count == 1 + 1 + 3 + 2
        assert documento.get_toc() == [
            [1, "Visão executiva", 2],
            [1, "Números", 3],
            [1, "Roadmap", 6],
        ]
    finally:
        documento.close()


def test_juntar_pdfs_recusa_listas_de_tamanhos_diferentes():
    with pytest.raises(ValueError):
        exp.juntar_pdfs([_pdf_com_paginas(1)], [None, "X"], METADADOS)


def test_numerar_paginas_nao_carimba_a_capa():
    pdf = exp.juntar_pdfs(
        [_pdf_com_paginas(1), _pdf_com_paginas(1), _pdf_com_paginas(1)],
        [None, "A", "B"],
        METADADOS,
    )

    numerado = exp.numerar_paginas(pdf)

    documento = pymupdf.open(stream=numerado, filetype="pdf")
    try:
        assert "página" not in documento[0].get_text()
        assert "página 2 de 3" in documento[1].get_text()
        assert "página 3 de 3" in documento[2].get_text()
    finally:
        documento.close()


def test_verificar_paginas_falha_com_pagina_faltando(tmp_path):
    for caminho in exp.PAGINAS[:-1]:
        pasta = tmp_path / caminho
        pasta.mkdir(parents=True)
        (pasta / "index.html").write_text("<html></html>", encoding="utf-8")

    with pytest.raises(exp.ErroExportacao, match="executivo/roadmap/"):
        exp.verificar_paginas(tmp_path)


def test_verificar_paginas_falha_se_o_site_nao_existe(tmp_path):
    with pytest.raises(exp.ErroExportacao, match="não existe"):
        exp.verificar_paginas(tmp_path / "inexistente")


def test_main_retorna_erro_legivel_sem_build(tmp_path, capsys):
    codigo = exp.main(["--site", str(tmp_path)])

    assert codigo == 1
    assert "páginas ausentes" in capsys.readouterr().err


def test_escrever_atomico_grava_e_nao_deixa_temporario(tmp_path):
    destino = tmp_path / "executivo" / "saida.pdf"

    exp.escrever_atomico(destino, b"%PDF-1.4 teste")

    assert destino.read_bytes() == b"%PDF-1.4 teste"
    assert not destino.with_name(destino.name + ".tmp").exists()


# --- integração (navegador e MkDocs) -----------------------------------------

_CONFIG_MKDOCS = """\
site_name: Teste do executivo
docs_dir: docs
site_dir: site
theme:
  name: material
markdown_extensions:
  - tables
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
"""

_MERMAID = """\
```mermaid
flowchart TD
    A["Início"] --> B["Fim"]
```
"""


def _montar_site_minimo(raiz: Path) -> Path:
    (raiz / "docs").mkdir(parents=True)
    (raiz / "mkdocs.yml").write_text(_CONFIG_MKDOCS, encoding="utf-8")
    for indice, caminho in enumerate(exp.PAGINAS):
        arquivo = raiz / "docs" / caminho / "index.md"
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        corpo = (
            f"# Página {indice + 1}\n\n"
            "Texto de teste. [Ir para números](/executivo/numeros/).\n\n"
            f"{_MERMAID}\n"
        )
        arquivo.write_text(corpo, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "-f", str(raiz / "mkdocs.yml")],
        cwd=raiz,
        check=True,
        capture_output=True,
    )
    return raiz / "site"


def _chromium_instalado() -> bool:
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception:
        return False
    return True


@pytest.mark.slow
def test_exportar_pdf_de_site_minimo_ponta_a_ponta(tmp_path):
    pytest.importorskip("mkdocs")
    pytest.importorskip("playwright.sync_api")
    if not _chromium_instalado():
        pytest.skip(
            "Chromium do Playwright não instalado (venv/bin/playwright install chromium)"
        )

    site = _montar_site_minimo(tmp_path)
    url_base = "https://exemplo.test"

    pdf, total = exp.exportar_pdf(site, url_base)

    documento = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        assert total == documento.page_count
        assert documento.page_count > len(exp.PAGINAS)
        toc = documento.get_toc()
        assert len(toc) == len(exp.PAGINAS)
        assert [entrada[1] for entrada in toc] == [
            f"Página {indice + 1}" for indice in range(len(exp.PAGINAS))
        ]
        assert documento.metadata["author"] == "Athos Roque"
        links = [
            link["uri"]
            for pagina in documento
            for link in pagina.get_links()
            if link.get("uri")
        ]
        assert any(uri.startswith(f"{url_base}/executivo/numeros") for uri in links)
        assert not any("127.0.0.1" in uri for uri in links)
    finally:
        documento.close()
