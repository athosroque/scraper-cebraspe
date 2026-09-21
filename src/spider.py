import json
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright

from src.logger import logger

# Import tardio (dentro de run()) para evitar import circular: downloader.py
# importa USER_AGENTS/stealth_wait deste módulo.

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0"
]

# Concursos já processados ficam registrados aqui, um slug por linha JSON.
# A pasta de download por concurso (Etapa 3) ainda não existe nesta fase,
# então a idempotência usa este registro local em vez de checar `data/`.
PROCESSED_REGISTRY = Path(__file__).resolve().parent.parent / "data" / "processed_concursos.json"

PRIORITY_KEYWORDS = {"INSS", "PF", "PRF", "PC", "PM", "MPU", "STJ", "STF", "TCU", "RECEITA"}


def has_priority_keyword(slug: str) -> bool:
    """Checks slug segments (split on '_'/'-') against known big-job keywords.

    Não usar `\\b` de regex direto no slug: underscore é caractere de
    palavra (\\w), então não cria fronteira entre "INSS" e "_25" — o
    `\\b` nunca dispara em slugs como "INSS_25".
    """
    parts = re.split(r'[_\-]', slug.upper())
    return any(part in PRIORITY_KEYWORDS for part in parts)


def stealth_wait():
    """Organic random wait between actions."""
    time.sleep(random.uniform(1.5, 3.5))


def setup_stealth(page: Page):
    """Applies stealth settings to a Playwright page."""
    user_agent = random.choice(USER_AGENTS)
    page.set_extra_http_headers({"User-Agent": user_agent})
    logger.info(f"Stealth User-Agent set: {user_agent}")


def extract_slug(url: str) -> str:
    """Last path segment of the contest URL, used as its stable identifier."""
    return url.rstrip("/").split("/")[-1]


def extract_year_from_slug(url: str) -> int | None:
    """Extracts the 2-digit year suffix from the contest's URL slug.

    O texto visível de todo card de concurso na listagem é sempre
    "MAIS INFORMAÇÕES" (confirmado ao vivo) — o ano só existe no slug da URL,
    ex: TJ_CE_25_NOTARIOS -> 25 -> 2025.
    """
    slug = extract_slug(url)
    match = re.search(r'_(\d{2})(_|$)', slug)
    if not match:
        return None
    return 2000 + int(match.group(1))


def extract_orgao_from_slug(url: str) -> str:
    """Segmento de órgão do slug: tudo antes do token de ano de 2 dígitos.

    Mesma razão dos outros extractors: o texto do link não carrega o nome do
    órgão (é sempre "MAIS INFORMAÇÕES"), então a Etapa 3 (downloader, que
    organiza PDFs por órgão) também depende do slug. Ex:
    TJ_CE_25_NOTARIOS -> "TJ_CE". Sem match de ano no slug, usa o slug
    inteiro como fallback (não deveria ocorrer para concursos já filtrados
    por target_year).
    """
    slug = extract_slug(url)
    match = re.search(r'_(\d{2})(_|$)', slug)
    if not match:
        return slug
    return slug[:match.start()] or slug


def load_processed_slugs() -> set[str]:
    if not PROCESSED_REGISTRY.exists():
        return set()
    try:
        return set(json.loads(PROCESSED_REGISTRY.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def mark_processed(slug: str, processed_slugs: set[str]):
    processed_slugs.add(slug)
    PROCESSED_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_REGISTRY.write_text(
        json.dumps(sorted(processed_slugs), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class CebraspeSpider:
    def __init__(self, headless: bool = True, target_year: int = 2025):
        self.headless = headless
        self.target_year = target_year
        self.base_url = "https://www.cebraspe.org.br/concursos/encerrado"

    def get_contest_links(self, page: Page) -> list[dict]:
        """Fetch closed contest links for target_year, prioritizing big jobs."""
        logger.info(f"Navigating to {self.base_url}")
        page.goto(self.base_url, timeout=60000)
        stealth_wait()

        contests = []
        links = page.locator("a").element_handles()

        for link in links:
            text = link.inner_text().strip().upper()
            raw_href = link.get_attribute("href")

            if not raw_href:
                continue

            # Os cards da listagem usam href RELATIVO (ex: "/concursos/ABIN_17"),
            # não absoluto — `get_attribute("href")` devolve o atributo cru do
            # HTML, sem resolver contra a base da página. Comparar direto com
            # "https://www.cebraspe.org.br/concursos/" descartava 100% dos
            # cards silenciosamente (0 contests, sem exceção). Resolver contra
            # a URL da página corrige tanto o caso relativo quanto o absoluto.
            href = urljoin(page.url, raw_href)
            if not href.startswith("https://www.cebraspe.org.br/concursos/"):
                continue

            # O ano só está disponível no slug da URL — o texto do link é
            # sempre "MAIS INFORMAÇÕES", não confiar nele para filtrar.
            ano = extract_year_from_slug(href)
            if ano != self.target_year:
                continue

            slug = extract_slug(href)

            # Pela mesma razão, priorização por cargo também usa o slug
            # (o texto do link não carrega o nome do órgão/cargo).
            priority = 1 if has_priority_keyword(slug) else 0

            contests.append({
                "title": text,
                "url": href,
                "slug": slug,
                "orgao": extract_orgao_from_slug(href),
                "ano": ano,
                "priority": priority
            })

        # Remove duplicates while preserving order
        unique_contests = []
        seen = set()
        for c in contests:
            if c["slug"] not in seen:
                seen.add(c["slug"])
                unique_contests.append(c)

        # Sort by priority (descending)
        unique_contests.sort(key=lambda x: x["priority"], reverse=True)
        return unique_contests

    def map_pdf_links(self, page: Page, contest_url: str) -> dict[str, list]:
        """Maps PDF links for Edital de Abertura, Provas, and Gabaritos."""
        logger.info(f"Mapping PDFs for {contest_url}")
        page.goto(contest_url, timeout=60000)
        stealth_wait()

        pdf_map = {
            "editais_abertura": [],
            "provas": [],
            "gabaritos": [],
            "nao_classificados": []
        }

        links = page.locator("a").element_handles()
        for link in links:
            raw_href = link.get_attribute("href")
            text = link.inner_text().strip().upper()

            if not raw_href or not raw_href.lower().endswith(".pdf"):
                continue

            href = urljoin(page.url, raw_href)

            if re.search(r'EDITAL.*?\bABERTURA\b', text):
                pdf_map["editais_abertura"].append(href)
                logger.info(f"[PROVA-PDF] editais_abertura <- '{text}' ({href})")
            elif re.search(r'GABARITO|PADR[ÕOÃA]ES?.*RESPOSTA', text):
                # "PADRÃO DE RESPOSTA (DEFINITIVO)" é o gabarito da prova
                # discursiva — o CEBRASPE não usa a palavra "GABARITO" nesse
                # caso. Deve ser checado antes de "PROVA" porque títulos como
                # "PADRÕES DEFINITIVOS DE RESPOSTAS – PROVAS DISCURSIVAS"
                # contêm a palavra "PROVAS" mas são gabaritos.
                pdf_map["gabaritos"].append(href)
                logger.info(f"[PROVA-PDF] gabaritos <- '{text}' ({href})")
            elif re.search(r'PROVA', text):
                # Editais administrativos que apenas citam prova (ex: resultados, convocações, locais)
                # não são cadernos de questões de prova.
                if re.search(r'EDITAL\s+N[ºO]|RESULTADO|LOCAIS\s+DE\s+APLICA', text):
                    pdf_map["nao_classificados"].append({"url": href, "texto": text})
                    logger.info(f"[PROVA-PDF] nao_classificados (edital administrativo citando prova) <- '{text}' ({href})")
                else:
                    # Guardar o texto do link é essencial: é a única fonte de
                    # tipo (CB/CE/discursiva), nível e cargo(s) cobertos — esse
                    # texto não existe dentro do conteúdo do PDF (ver LESSONS.md).
                    pdf_map["provas"].append({"url": href, "texto": text})
                    logger.info(f"[PROVA-PDF] provas <- '{text}' ({href})")
            else:
                # Nunca descartar em silêncio: qualquer PDF que caia aqui é
                # um tipo de documento que a regex ainda não reconhece.
                pdf_map["nao_classificados"].append({"url": href, "texto": text})
                logger.warning(f"[PROVA-PDF] NÃO CLASSIFICADO: '{text}' ({href})")

        logger.info(
            f"Classificação em {contest_url}: "
            f"{len(pdf_map['editais_abertura'])} editais, "
            f"{len(pdf_map['provas'])} provas, "
            f"{len(pdf_map['gabaritos'])} gabaritos, "
            f"{len(pdf_map['nao_classificados'])} não classificados"
        )
        return pdf_map

    def process_contest(self, page: Page, contest: dict, processed_slugs: set[str]) -> dict:
        """Mapeia, baixa PDFs de um concurso e registra no índice de processados."""
        logger.info(f"Processing: {contest['title']} (Priority: {contest['priority']})")
        pdfs = self.map_pdf_links(page, contest["url"])

        logger.info(f"Found {len(pdfs['editais_abertura'])} Editais de Abertura")
        logger.info(f"Found {len(pdfs['provas'])} Provas")
        logger.info(f"Found {len(pdfs['gabaritos'])} Gabaritos")
        if pdfs['nao_classificados']:
            logger.warning(f"Found {len(pdfs['nao_classificados'])} PDFs NÃO classificados — ver [PROVA-PDF] acima")

        # Import tardio: evita import circular (downloader importa deste módulo no nível de topo).
        from src.downloader import download_concurso_pdfs

        baixados = download_concurso_pdfs(contest["orgao"], contest["ano"], pdfs)
        logger.info(
            f"Baixados para {contest['slug']}: "
            f"{len(baixados['editais_abertura'])} editais, "
            f"{len(baixados['provas'])} provas, "
            f"{len(baixados['gabaritos'])} gabaritos"
        )

        # Só marca como processado depois do download ter efetivamente rodado
        mark_processed(contest["slug"], processed_slugs)
        return baixados

    def run(self, slug_filtro: str | None = None):
        logger.info("Starting Cebraspe Spider")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            setup_stealth(page)

            try:
                processed_slugs = load_processed_slugs()

                if slug_filtro:
                    url = slug_filtro if slug_filtro.startswith("http") else f"https://www.cebraspe.org.br/concursos/{slug_filtro}"
                    slug = extract_slug(url)
                    contest = {
                        "title": slug,
                        "url": url,
                        "slug": slug,
                        "orgao": extract_orgao_from_slug(url),
                        "ano": extract_year_from_slug(url) or self.target_year,
                        "priority": 1 if has_priority_keyword(slug) else 0,
                    }
                    self.process_contest(page, contest, processed_slugs)
                else:
                    contests = self.get_contest_links(page)
                    logger.info(f"Found {len(contests)} contests matching criteria for {self.target_year}.")

                    for contest in contests:
                        if contest["slug"] in processed_slugs:
                            logger.info(f"Skipping already processed contest: {contest['slug']}")
                            continue

                        # Falha isolada de um concurso não pode abortar o lote inteiro.
                        try:
                            self.process_contest(page, contest, processed_slugs)
                        except Exception as e:  # noqa: BLE001 — falha de 1 concurso não aborta o lote
                            logger.error(f"Error processing contest {contest['slug']}: {e}")
                        finally:
                            stealth_wait()
            except Exception as e:  # noqa: BLE001 — garante browser.close() e log final
                logger.error(f"Error during spider run: {e}")
            finally:
                browser.close()
                logger.info("Spider finished")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Crawler de concursos do CEBRASPE")
    parser.add_argument("--slug", type=str, default=None, help="Slug específico de concurso a processar (ex: TCU_25_TEFC)")
    args = parser.parse_args()

    spider = CebraspeSpider(headless=True)
    spider.run(slug_filtro=args.slug)

