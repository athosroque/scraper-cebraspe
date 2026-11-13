"""Exporta a aba "Visão executiva" do site de documentação para um PDF (Etapa 9/D4, KAN-71).

O site fica atrás do Cloudflare Access, então quem é de fora recebe este PDF. O
script serve o build do MkDocs por HTTP local (o Mermaid e os assets precisam de
HTTP), imprime cada página com Chromium pelo Playwright, junta tudo com PyMuPDF e
grava um sumário (bookmarks) com o título de cada página. Os links absolutos do
site local são reescritos para a URL pública, para que o PDF leve ao site real.

Uso:
    python -m scripts.exportar_pdf_executivo
    python -m scripts.exportar_pdf_executivo --site build/docs.novo
    python -m scripts.exportar_pdf_executivo --saida /tmp/executivo.pdf --url-base https://docs.projetoathos.com.br

O padrão de `--saida` é `<site>/executivo/scraper-cebraspe-executivo.pdf`, para o
nginx servir o arquivo e o botão "Baixar PDF" da página `executivo/` apontar para ele.
Antes de imprimir, o script confere que todas as páginas de `PAGINAS` existem no
build e falha com mensagem clara se alguma faltar.
"""

import argparse
import datetime
import functools
import html
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymupdf
from playwright.sync_api import Error as ErroPlaywright
from playwright.sync_api import TimeoutError as TimeoutPlaywright
from playwright.sync_api import sync_playwright

PROJETO_DIR = Path(__file__).resolve().parent.parent
SITE_PADRAO = PROJETO_DIR / "build" / "docs"
URL_BASE_PADRAO = "https://docs.projetoathos.com.br"
NOME_PDF = "scraper-cebraspe-executivo.pdf"

PAGINAS = (
    "executivo/",
    "executivo/arquitetura/",
    "executivo/numeros/",
    "executivo/decisoes/",
    "executivo/roadmap/",
)
AUTOR = "Athos Roque"
TITULO_PDF = "Scraper CEBRASPE — Visão executiva"
ASSUNTO_PDF = (
    "Coleta estruturada de editais, provas e gabaritos para um site de questões"
)
ENDERECO_SITE = "docs.projetoathos.com.br"
RODAPE = "Scraper CEBRASPE, visão executiva"
TIMEOUT_MERMAID_MS = 10_000
MARCADOR_MERMAID = '<pre class="mermaid">'


class ErroExportacao(RuntimeError):
    """Falha esperada do exportador, com mensagem pronta para o operador."""


def html_capa(data_geracao: datetime.date) -> str:
    """HTML da capa. Impressa sem cabeçalho nem rodapé, ocupa a folha inteira."""
    data = data_geracao.strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>{html.escape(TITULO_PDF)}</title>
<style>
  /* Capa na mesma identidade do site (ADR-043): Spectral, preto real, um
     acento ocre. As marcas de registro nos cantos vêm da folha de leitura
     ótica e são o único enfeite da página. */
  @import url("https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&display=swap");
  html, body {{ margin: 0; height: 100%; }}
  body {{
    font-family: "Spectral", Georgia, "Times New Roman", serif;
    color: #000000;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 0 22mm;
    box-sizing: border-box;
    height: 297mm;
    position: relative;
  }}
  .registro {{
    position: absolute;
    width: 4mm;
    height: 4mm;
    background: #000000;
  }}
  .registro--se {{ top: 12mm; left: 12mm; }}
  .registro--sd {{ top: 12mm; right: 12mm; }}
  .registro--ie {{ bottom: 12mm; left: 12mm; }}
  .registro--id {{ bottom: 12mm; right: 12mm; }}
  .rotulo {{
    font-size: 11pt;
    color: #5a5a5e;
    margin: 0 0 10mm 0;
  }}
  h1 {{
    font-size: 34pt;
    line-height: 1.1;
    margin: 0 0 6mm 0;
    font-weight: 600;
    letter-spacing: -0.012em;
  }}
  .subtitulo {{
    font-size: 15pt;
    line-height: 1.45;
    color: #5a5a5e;
    margin: 0 0 22mm 0;
    max-width: 150mm;
  }}
  .faixa {{
    border-top: 2px solid #92670a;
    padding-top: 6mm;
    font-size: 11pt;
    line-height: 1.7;
    color: #5a5a5e;
  }}
  .faixa strong {{ color: #000000; font-weight: 600; }}
</style>
</head>
<body>
  <span class="registro registro--se"></span>
  <span class="registro registro--sd"></span>
  <span class="registro registro--ie"></span>
  <span class="registro registro--id"></span>
  <p class="rotulo">Visão executiva</p>
  <h1>{html.escape("Scraper CEBRASPE")}</h1>
  <p class="subtitulo">{html.escape(ASSUNTO_PDF)}</p>
  <div class="faixa">
    <div><strong>Autor:</strong> {html.escape(AUTOR)}</div>
    <div><strong>Gerado em:</strong> {data}</div>
    <div><strong>Site:</strong> {html.escape(ENDERECO_SITE)} (exige login)</div>
  </div>
</body>
</html>
"""


def montar_toc(blocos: list[tuple[str | None, int]]) -> list[list]:
    """Sumário no formato do PyMuPDF (`[nivel, titulo, pagina]`, pagina a partir de 1).

    Cada bloco é `(titulo, numero_de_paginas)`, na ordem do PDF. Bloco sem título
    (a capa) ocupa páginas mas não entra no sumário.
    """
    toc: list[list] = []
    pagina = 1
    for titulo, paginas in blocos:
        if titulo:
            toc.append([1, titulo, pagina])
        pagina += paginas
    return toc


def juntar_pdfs(
    pdfs: list[bytes], titulos: list[str | None], metadados: dict[str, str]
) -> bytes:
    """Junta PDFs num só, com metadados e sumário.

    `titulos[i]` é o título do bookmark de `pdfs[i]`, ou None para não criar entrada
    (a capa). `metadados` aceita as chaves `title`, `author` e `subject`.
    """
    if len(pdfs) != len(titulos):
        raise ValueError("pdfs e titulos têm tamanhos diferentes")
    destino = pymupdf.open()
    blocos: list[tuple[str | None, int]] = []
    for pdf, titulo in zip(pdfs, titulos):
        origem = pymupdf.open(stream=pdf, filetype="pdf")
        try:
            blocos.append((titulo, origem.page_count))
            destino.insert_pdf(origem)
        finally:
            origem.close()
    destino.set_metadata(
        {
            "title": metadados.get("title", ""),
            "author": metadados.get("author", AUTOR),
            "subject": metadados.get("subject", ""),
            "creator": "scripts/exportar_pdf_executivo.py",
        }
    )
    destino.set_toc(montar_toc(blocos))
    return destino.tobytes(garbage=3, deflate=True)


def numerar_paginas(pdf: bytes) -> bytes:
    """Carimba "página X de N" no rodapé direito, da segunda página em diante.

    O Chromium numera cada página isoladamente (cada página do site é um PDF
    próprio), então a numeração certa só existe depois da junção.
    """
    documento = pymupdf.open(stream=pdf, filetype="pdf")
    total = documento.page_count
    for indice in range(1, total):
        pagina = documento[indice]
        largura = pagina.rect.width
        altura = pagina.rect.height
        texto = f"página {indice + 1} de {total}"
        comprimento = pymupdf.get_text_length(texto, fontname="helv", fontsize=8)
        pagina.insert_text(
            pymupdf.Point(largura - 16 * 2.835 - comprimento, altura - 17.5),
            texto,
            fontname="helv",
            fontsize=8,
            color=(0.32, 0.32, 0.36),
        )
    return documento.tobytes(garbage=3, deflate=True)


def verificar_paginas(site: Path) -> None:
    """Falha cedo se alguma página do executivo não existe no build."""
    if not site.is_dir():
        raise ErroExportacao(f"diretório do site não existe: {site}")
    faltando = [p for p in PAGINAS if not (site / p / "index.html").is_file()]
    if faltando:
        raise ErroExportacao(
            "páginas ausentes no build "
            f"({site}): {', '.join(faltando)}. Rode `make docs-build` antes."
        )


class _ServidorSilencioso(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - assinatura da base
        pass


def _iniciar_servidor(site: Path) -> ThreadingHTTPServer:
    handler = functools.partial(_ServidorSilencioso, directory=str(site))
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    servidor.daemon_threads = True
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


def _contar_mermaid(site: Path, caminho: str) -> int:
    texto = (site / caminho / "index.html").read_text(encoding="utf-8")
    return texto.count(MARCADOR_MERMAID)


def _esperar_mermaid(page, caminho: str, n_diagramas: int) -> None:
    """Espera o Material trocar cada `pre.mermaid` por um `div.mermaid`.

    O SVG vai para um shadow root fechado, então não dá para consultá-lo; o
    contador de `div.mermaid` só sobe depois do `replaceWith`, ou seja, com o
    diagrama já renderizado. Não se usa `pre.mermaid` como sinal: o Material tira
    a classe do `pre` enquanto o Mermaid carrega, e a contagem passaria cedo.
    """
    if n_diagramas == 0:
        return
    try:
        page.wait_for_function(
            "(n) => document.querySelectorAll('div.mermaid').length >= n",
            arg=n_diagramas,
            timeout=TIMEOUT_MERMAID_MS,
        )
    except TimeoutPlaywright as erro:
        raise ErroExportacao(
            f"o Mermaid não renderizou os {n_diagramas} diagrama(s) em "
            f"{TIMEOUT_MERMAID_MS // 1000} s na página {caminho}"
        ) from erro


_JS_TITULO = """() => {
    const h1 = document.querySelector('article h1') || document.querySelector('h1');
    if (!h1) return '';
    const copia = h1.cloneNode(true);
    copia.querySelectorAll('.headerlink').forEach((e) => e.remove());
    return copia.textContent.trim();
}"""

_JS_REESCREVER_LINKS = """([base, origem]) => {
    for (const a of document.querySelectorAll('a[href]')) {
        if (a.href.startsWith(origem)) {
            a.href = base + a.href.slice(origem.length);
        }
    }
}"""

_RODAPE_CHROMIUM = (
    '<div style="font-family: sans-serif; font-size: 8px; color: #71717a; '
    'width: 100%; padding: 0 16mm; box-sizing: border-box;">'
    f"{html.escape(RODAPE)}</div>"
)


def _imprimir_pagina(
    page, site: Path, caminho: str, url_base: str, origem: str
) -> tuple[str, bytes]:
    """Imprime uma página do executivo. Devolve (título, PDF)."""
    try:
        page.goto(f"{origem}/{caminho}", wait_until="networkidle", timeout=30_000)
    except ErroPlaywright as erro:
        raise ErroExportacao(f"falha ao carregar a página {caminho}: {erro}") from erro
    _esperar_mermaid(page, caminho, _contar_mermaid(site, caminho))
    titulo = page.evaluate(_JS_TITULO)
    if not titulo:
        raise ErroExportacao(f"a página {caminho} não tem <h1>")
    page.evaluate(_JS_REESCREVER_LINKS, [url_base.rstrip("/"), origem])
    pdf = page.pdf(
        format="A4",
        print_background=True,
        margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"},
        display_header_footer=True,
        header_template="<span></span>",
        footer_template=_RODAPE_CHROMIUM,
    )
    return titulo, pdf


def exportar_pdf(site: Path, url_base: str = URL_BASE_PADRAO) -> tuple[bytes, int]:
    """Gera o PDF do executivo a partir do build em `site`. Devolve (bytes, nº de páginas)."""
    verificar_paginas(site)
    servidor = _iniciar_servidor(site)
    origem = f"http://127.0.0.1:{servidor.server_address[1]}"
    pdfs: list[bytes] = []
    titulos: list[str | None] = []
    try:
        with sync_playwright() as p:
            try:
                navegador = p.chromium.launch()
            except ErroPlaywright as erro:
                raise ErroExportacao(
                    "Chromium do Playwright indisponível; rode "
                    "`venv/bin/playwright install chromium`"
                ) from erro
            try:
                page = navegador.new_page()
                page.emulate_media(media="print", color_scheme="light")
                pdfs.append(_gerar_capa(page))
                titulos.append(None)
                for caminho in PAGINAS:
                    titulo, pdf = _imprimir_pagina(
                        page, site, caminho, url_base, origem
                    )
                    pdfs.append(pdf)
                    titulos.append(titulo)
            finally:
                navegador.close()
    finally:
        servidor.shutdown()
        servidor.server_close()

    metadados = {"title": TITULO_PDF, "author": AUTOR, "subject": ASSUNTO_PDF}
    pdf_final = juntar_pdfs(pdfs, titulos, metadados)
    pdf_final = numerar_paginas(pdf_final)
    total = pymupdf.open(stream=pdf_final, filetype="pdf").page_count
    return pdf_final, total


def _gerar_capa(page) -> bytes:
    page.set_content(html_capa(datetime.date.today()), wait_until="load")
    return page.pdf(
        format="A4",
        print_background=True,
        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        display_header_footer=False,
    )


def escrever_atomico(caminho: Path, conteudo: bytes) -> None:
    """Grava em arquivo temporário e renomeia no fim, para não deixar PDF pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    temporario.write_bytes(conteudo)
    os.replace(temporario, caminho)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exporta a visão executiva do site de documentação para PDF."
    )
    parser.add_argument(
        "--site",
        type=Path,
        default=SITE_PADRAO,
        help="diretório de um build do MkDocs (padrão: build/docs)",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=None,
        help="arquivo PDF de saída (padrão: <site>/executivo/" + NOME_PDF + ")",
    )
    parser.add_argument(
        "--url-base",
        default=URL_BASE_PADRAO,
        help="endereço público que substitui o servidor local nos links do PDF",
    )
    args = parser.parse_args(argv)
    site = args.site.resolve()
    saida = args.saida or site / "executivo" / NOME_PDF
    try:
        pdf, total = exportar_pdf(site, args.url_base)
    except ErroExportacao as erro:
        print(f"erro: {erro}", file=sys.stderr)
        return 1
    escrever_atomico(saida, pdf)
    print(f"PDF gravado em {saida} ({total} páginas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
