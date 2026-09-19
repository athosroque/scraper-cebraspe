import json
import re
import time
import random
from pathlib import Path
from typing import List, Dict, Optional, Set
from playwright.sync_api import sync_playwright, Page
from src.logger import logger


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


def extract_year_from_slug(url: str) -> Optional[int]:
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


def load_processed_slugs() -> Set[str]:
    if not PROCESSED_REGISTRY.exists():
        return set()
    try:
        return set(json.loads(PROCESSED_REGISTRY.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def mark_processed(slug: str, processed_slugs: Set[str]):
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

    def get_contest_links(self, page: Page) -> List[Dict]:
        """Fetch closed contest links for target_year, prioritizing big jobs."""
        logger.info(f"Navigating to {self.base_url}")
        page.goto(self.base_url, timeout=60000)
        stealth_wait()

        contests = []
        links = page.locator("a").element_handles()

        for link in links:
            text = link.inner_text().strip().upper()
            href = link.get_attribute("href")

            if not href or not href.startswith("https://www.cebraspe.org.br/concursos/"):
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

    def map_pdf_links(self, page: Page, contest_url: str) -> Dict[str, List[str]]:
        """Maps PDF links for Edital de Abertura, Provas, and Gabaritos."""
        logger.info(f"Mapping PDFs for {contest_url}")
        page.goto(contest_url, timeout=60000)
        stealth_wait()

        pdf_map = {
            "editais_abertura": [],
            "provas": [],
            "gabaritos": []
        }

        links = page.locator("a").element_handles()
        for link in links:
            href = link.get_attribute("href")
            text = link.inner_text().strip().upper()

            if not href or not href.lower().endswith(".pdf"):
                continue

            if re.search(r'EDITAL.*?ABERTURA', text):
                pdf_map["editais_abertura"].append(href)
            elif re.search(r'PROVA', text):
                pdf_map["provas"].append(href)
            elif re.search(r'GABARITO', text):
                pdf_map["gabaritos"].append(href)

        return pdf_map

    def run(self):
        logger.info("Starting Cebraspe Spider")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            setup_stealth(page)

            try:
                contests = self.get_contest_links(page)
                logger.info(f"Found {len(contests)} contests matching criteria for {self.target_year}.")

                processed_slugs = load_processed_slugs()

                for contest in contests:
                    if contest["slug"] in processed_slugs:
                        logger.info(f"Skipping already processed contest: {contest['slug']}")
                        continue

                    # Falha isolada de um concurso não pode abortar o lote inteiro.
                    try:
                        logger.info(f"Processing: {contest['title']} (Priority: {contest['priority']})")
                        pdfs = self.map_pdf_links(page, contest["url"])

                        logger.info(f"Found {len(pdfs['editais_abertura'])} Editais de Abertura")
                        logger.info(f"Found {len(pdfs['provas'])} Provas")
                        logger.info(f"Found {len(pdfs['gabaritos'])} Gabaritos")

                        mark_processed(contest["slug"], processed_slugs)
                    except Exception as e:
                        logger.error(f"Error processing contest {contest['slug']}: {e}")
                    finally:
                        stealth_wait()
            except Exception as e:
                logger.error(f"Error during spider run: {e}")
            finally:
                browser.close()
                logger.info("Spider finished")


if __name__ == "__main__":
    spider = CebraspeSpider(headless=True)
    spider.run()
