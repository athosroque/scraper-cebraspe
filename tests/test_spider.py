from unittest.mock import MagicMock

from src.spider import CebraspeSpider, extract_orgao_from_slug, extract_year_from_slug


def _make_link(text: str, href: str) -> MagicMock:
    link = MagicMock()
    link.inner_text.return_value = text
    link.get_attribute.return_value = href
    return link


class TestGetContestLinksResolveHref:
    """Regressão: a listagem real do CEBRASPE usa href RELATIVO nos cards
    (ex: "/concursos/PF_25_ADM"), não absoluto. `get_attribute("href")`
    devolve o atributo cru do HTML, sem resolver contra a URL da página —
    comparar isso direto com "https://www.cebraspe.org.br/concursos/"
    descartava 100% dos cards em produção (0 contests, sem exceção),
    confirmado ao vivo em 2026-09-19. Ver CLAUDE.md, seção 12.
    """

    def _spider_with_links(self, monkeypatch, links):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        spider = CebraspeSpider(headless=True, target_year=2025)
        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/encerrado"
        page.locator.return_value.element_handles.return_value = links
        return spider, page

    def test_resolve_href_relativo_contra_url_da_pagina(self, monkeypatch):
        spider, page = self._spider_with_links(
            monkeypatch,
            [
                _make_link("MAIS INFORMAÇÕES", "/concursos/PF_25_ADM"),
                _make_link(
                    "MAIS INFORMAÇÕES", "/concursos/ABIN_17"
                ),  # outro ano, deve ser filtrado
            ],
        )
        contests = spider.get_contest_links(page)

        assert len(contests) == 1
        assert contests[0]["url"] == "https://www.cebraspe.org.br/concursos/PF_25_ADM"
        assert contests[0]["slug"] == "PF_25_ADM"

    def test_mantem_href_absoluto_inalterado(self, monkeypatch):
        spider, page = self._spider_with_links(
            monkeypatch,
            [
                _make_link(
                    "MAIS INFORMAÇÕES",
                    "https://www.cebraspe.org.br/concursos/TCU_25_TEFC",
                )
            ],
        )
        contests = spider.get_contest_links(page)

        assert len(contests) == 1
        assert contests[0]["slug"] == "TCU_25_TEFC"

    def test_ignora_link_fora_do_dominio_de_concursos(self, monkeypatch):
        spider, page = self._spider_with_links(
            monkeypatch,
            [_make_link("Institucional", "https://www.cebraspe.org.br/sobre-nos/")],
        )
        contests = spider.get_contest_links(page)

        assert contests == []


class TestExtractOrgaoFromSlug:
    def test_extrai_segmento_antes_do_ano(self):
        url = "https://www.cebraspe.org.br/concursos/TJ_CE_25_NOTARIOS"
        assert extract_orgao_from_slug(url) == "TJ_CE"

    def test_fallback_para_slug_inteiro_sem_ano(self):
        url = "https://www.cebraspe.org.br/concursos/SEM_ANO_AQUI"
        assert extract_orgao_from_slug(url) == "SEM_ANO_AQUI"

    def test_consistente_com_extract_year_from_slug(self):
        url = "https://www.cebraspe.org.br/concursos/INSS_25"
        assert extract_orgao_from_slug(url) == "INSS"
        assert extract_year_from_slug(url) == 2025


class TestMapPdfLinks:
    def _spider_with_page(self, monkeypatch, links):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        spider = CebraspeSpider(headless=True)
        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/TCU_25_TEFC"
        page.locator.return_value.element_handles.return_value = links
        return spider, page

    def test_classifica_padrao_resposta_discursiva_como_gabarito_e_nao_prova(
        self, monkeypatch
    ):
        spider, page = self._spider_with_page(
            monkeypatch,
            [
                _make_link(
                    "PADRÕES DEFINITIVOS DE RESPOSTAS – PROVAS DISCURSIVAS(P3)",
                    "https://cdn.cebraspe.org.br/concursos/TCU_25_TEFC/arquivos/padrao.pdf",
                ),
            ],
        )
        pdf_map = spider.map_pdf_links(page, page.url)
        assert len(pdf_map["gabaritos"]) == 1
        assert len(pdf_map["provas"]) == 0
        assert "padrao.pdf" in pdf_map["gabaritos"][0]

    def test_edital_resultado_de_prova_vai_para_nao_classificados_e_nao_provas(
        self, monkeypatch
    ):
        spider, page = self._spider_with_page(
            monkeypatch,
            [
                _make_link(
                    "EDITAL Nº 3 – RESULTADO FINAL NAS PROVAS OBJETIVAS E O RESULTADO PROVISÓRIO NA PROVA DISCURSIVA",
                    "https://cdn.cebraspe.org.br/concursos/TCU_25_TEFC/arquivos/ed3.pdf",
                ),
            ],
        )
        pdf_map = spider.map_pdf_links(page, page.url)
        assert len(pdf_map["provas"]) == 0
        assert len(pdf_map["nao_classificados"]) == 1

    def test_caderno_de_questoes_vai_para_provas(self, monkeypatch):
        spider, page = self._spider_with_page(
            monkeypatch,
            [
                _make_link(
                    "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
                    "https://cdn.cebraspe.org.br/concursos/TCU_25_TEFC/arquivos/prova_cb.pdf",
                ),
            ],
        )
        pdf_map = spider.map_pdf_links(page, page.url)
        assert len(pdf_map["provas"]) == 1
        assert pdf_map["provas"][0]["texto"] == "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS"

    def test_edital_reabertura_nao_vai_para_editais_abertura(self, monkeypatch):
        spider, page = self._spider_with_page(
            monkeypatch,
            [
                _make_link(
                    "EDITAL Nº 8 - RETIFICAÇÃO E REABERTURA DO PERÍODO DE ACESSO",
                    "https://cdn.cebraspe.org.br/concursos/CD_25_NS/arquivos/ed8.pdf",
                ),
                _make_link(
                    "EDITAL Nº 1 – ABERTURA – ATUALIZADO CONFORME RETIFICAÇÕES",
                    "https://cdn.cebraspe.org.br/concursos/CD_25_NS/arquivos/ed1.pdf",
                ),
            ],
        )
        pdf_map = spider.map_pdf_links(page, page.url)
        assert len(pdf_map["editais_abertura"]) == 1
        assert "ed1.pdf" in pdf_map["editais_abertura"][0]
        assert len(pdf_map["nao_classificados"]) == 1
