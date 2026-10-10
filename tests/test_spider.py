from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import MagicMock

from src.inventario import (
    SLUGS_NAVEGACAO,
    TIPO_ADMINISTRATIVO,
    TIPO_CADERNO_OBJETIVO,
    TIPO_EDITAL_ABERTURA,
    TIPO_GABARITO,
    TIPO_PADRAO_RESPOSTA,
)
from src.spider import (
    CebraspeSpider,
    extract_orgao_from_slug,
    extract_year_from_slug,
    listar_concursos,
    listar_todas_listagens,
    mapear_links_pdf,
)


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
    confirmado ao vivo em 2026-09-19. Ver ADR-008.
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

    def test_caderno_com_gabarito_vai_para_provas_com_texto(self, monkeypatch):
        # "PROVA ... E GABARITO ..." é caderno (8.M/S3): antes caía em
        # gabaritos, sem texto do link, e ficava fora da fila.
        spider, page = self._spider_with_page(
            monkeypatch,
            [
                _make_link(
                    "PROVA OBJETIVA (P1) E GABARITO PRELIMINAR COM JUSTIFICATIVAS - "
                    "CARGOS 1 AO 18 (ATUALIZADO)",
                    "https://cdn.cebraspe.org.br/concursos/CAESB_24/arquivos/cg1.pdf",
                ),
                _make_link(
                    "PROVA E GABARITO DEFINITIVO – CONHECIMENTOS BÁSICOS",
                    "https://cdn.cebraspe.org.br/concursos/AGSUS_26_RD/arquivos/cb.pdf",
                ),
                _make_link(
                    "GABARITO DEFINITIVO – CONHECIMENTOS GERAIS PARA OS CARGOS 1 A 18",
                    "https://cdn.cebraspe.org.br/concursos/CAESB_24/arquivos/gab.pdf",
                ),
            ],
        )
        pdf_map = spider.map_pdf_links(page, page.url)
        assert [p["url"].rsplit("/", 1)[1] for p in pdf_map["provas"]] == [
            "cg1.pdf",
            "cb.pdf",
        ]
        assert pdf_map["provas"][0]["texto"].startswith(
            "PROVA OBJETIVA (P1) E GABARITO"
        )
        assert [u.rsplit("/", 1)[1] for u in pdf_map["gabaritos"]] == ["gab.pdf"]

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


class FixtureLinkParser(HTMLParser):
    """Helper simples para extrair links de fixtures HTML sem dependência externa."""

    def __init__(self):
        super().__init__()
        self.links: list[MagicMock] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            self._current_href = attrs_dict.get("href")
            self._current_text = []

    def handle_data(self, data):
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._current_href is not None:
            text = "".join(self._current_text).strip()
            self.links.append(_make_link(text, self._current_href))
            self._current_href = None


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "inventario"


class TestExtractYearFromSlug4Digitos:
    def test_extrai_ano_4_digitos(self):
        assert (
            extract_year_from_slug("https://www.cebraspe.org.br/concursos/INSS_2015")
            == 2015
        )
        assert extract_year_from_slug("INSS_2015") == 2015
        assert (
            extract_year_from_slug(
                "https://www.cebraspe.org.br/concursos/CAIXA_2014_REGIONAL"
            )
            == 2014
        )

    def test_codigo_de_4_digitos_implausivel_nao_vira_ano(self):
        # Só 19YY/20YY valem como ano de 4 dígitos; senão vale o sufixo _YY.
        assert extract_year_from_slug("PREF_5678") is None
        assert extract_year_from_slug("PREF_1234_25") == 2025
        assert extract_orgao_from_slug("PREF_1234_25") == "PREF_1234"
        assert extract_year_from_slug("TJ_2099_X") == 2099

    def test_extrai_ano_2_digitos(self):
        assert (
            extract_year_from_slug("https://www.cebraspe.org.br/concursos/PF_25")
            == 2025
        )
        assert (
            extract_year_from_slug(
                "https://www.cebraspe.org.br/concursos/TJ_CE_25_NOTARIOS"
            )
            == 2025
        )
        assert extract_year_from_slug("ABIN_17") == 2017

    def test_slug_sem_ano_retorna_none(self):
        assert (
            extract_year_from_slug("https://www.cebraspe.org.br/concursos/SEM_ANO_AQUI")
            is None
        )
        assert extract_year_from_slug("encerrado") is None
        assert extract_year_from_slug("em-andamento") is None
        assert extract_year_from_slug("#main") is None


class TestListarConcursos:
    def test_descarta_slugs_navegacao_e_extrai_campos(self, monkeypatch):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/encerrado"
        page.locator.return_value.element_handles.return_value = [
            _make_link("MAIS INFORMAÇÕES", "/concursos/PF_25_ADM"),
            _make_link("MAIS INFORMAÇÕES", "/concursos/INSS_2015"),
            _make_link("MAIS INFORMAÇÕES", "/concursos/ABIN_17"),
            _make_link("Em Andamento", "/concursos/em-andamento"),
            _make_link("Inscrições Abertas", "/concursos/inscricoes-abertas"),
            _make_link("Novos", "/concursos/novos"),
            _make_link("Encerrados", "/concursos/encerrado"),
            _make_link("Pular Conteúdo", "#main"),
            _make_link("Sobre", "https://www.cebraspe.org.br/sobre-nos/"),
        ]

        contests = listar_concursos(page, page.url, "encerrado")
        assert len(contests) == 3

        slugs = [c["slug"] for c in contests]
        assert slugs == ["PF_25_ADM", "INSS_2015", "ABIN_17"]

        # Verifica descarte explícito de todos os SLUGS_NAVEGACAO
        for slug_nav in SLUGS_NAVEGACAO:
            assert slug_nav not in slugs

        # Verifica campos extraídos
        c_pf = contests[0]
        assert c_pf["slug"] == "PF_25_ADM"
        assert c_pf["orgao"] == "PF"
        assert c_pf["ano"] == 2025
        assert c_pf["situacao"] == "encerrado"
        assert c_pf["url"] == "https://www.cebraspe.org.br/concursos/PF_25_ADM"
        assert c_pf["title"] == "MAIS INFORMAÇÕES"

        c_inss = contests[1]
        assert c_inss["slug"] == "INSS_2015"
        assert c_inss["orgao"] == "INSS"
        assert c_inss["ano"] == 2015

        c_abin = contests[2]
        assert c_abin["slug"] == "ABIN_17"
        assert c_abin["orgao"] == "ABIN"
        assert c_abin["ano"] == 2017

    def test_com_fixture_html_listagem(self, monkeypatch):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        fixture_path = FIXTURES_DIR / "listagem_encerrado_amostra.html"
        assert fixture_path.exists(), f"Fixture não encontrada: {fixture_path}"

        parser = FixtureLinkParser()
        parser.feed(fixture_path.read_text(encoding="utf-8"))

        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/encerrado"
        page.locator.return_value.element_handles.return_value = parser.links

        contests = listar_concursos(page, page.url, "encerrado")
        assert len(contests) == 3
        assert [c["slug"] for c in contests] == ["PF_25_ADM", "INSS_2015", "ABIN_17"]


class TestListarTodasListagens:
    def test_deduplicacao_e_prioridade_situacao(self, monkeypatch):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/encerrado"

        def fake_listar(p, url, situacao):
            if situacao == "encerrado":
                return [
                    {
                        "slug": "PF_25",
                        "situacao": "encerrado",
                        "ano": 2025,
                        "orgao": "PF",
                        "url": "https://.../PF_25",
                        "title": "PF",
                    },
                    {
                        "slug": "STJ_24",
                        "situacao": "encerrado",
                        "ano": 2024,
                        "orgao": "STJ",
                        "url": "https://.../STJ_24",
                        "title": "STJ",
                    },
                ]
            elif situacao == "em_andamento":
                return [
                    # PF_25 também em andamento -> deve prevalecer encerrado
                    {
                        "slug": "PF_25",
                        "situacao": "em_andamento",
                        "ano": 2025,
                        "orgao": "PF",
                        "url": "https://.../PF_25",
                        "title": "PF",
                    },
                    {
                        "slug": "TCU_25",
                        "situacao": "em_andamento",
                        "ano": 2025,
                        "orgao": "TCU",
                        "url": "https://.../TCU_25",
                        "title": "TCU",
                    },
                ]
            elif situacao == "inscricoes_abertas":
                return [
                    # TCU_25 também aqui -> em_andamento vence inscricoes_abertas
                    {
                        "slug": "TCU_25",
                        "situacao": "inscricoes_abertas",
                        "ano": 2025,
                        "orgao": "TCU",
                        "url": "https://.../TCU_25",
                        "title": "TCU",
                    },
                    {
                        "slug": "NOVO_26",
                        "situacao": "inscricoes_abertas",
                        "ano": 2026,
                        "orgao": "NOVO",
                        "url": "https://.../NOVO_26",
                        "title": "NOVO",
                    },
                ]
            elif situacao == "novos":
                return [
                    # NOVO_26 também em novos -> inscricoes_abertas vence novos
                    {
                        "slug": "NOVO_26",
                        "situacao": "novos",
                        "ano": 2026,
                        "orgao": "NOVO",
                        "url": "https://.../NOVO_26",
                        "title": "NOVO",
                    },
                ]
            return []

        monkeypatch.setattr("src.spider.listar_concursos", fake_listar)

        # Testa standalone
        res = listar_todas_listagens(page)
        assert len(res) == 4
        # Ordenado por slug: NOVO_26, PF_25, STJ_24, TCU_25
        assert [c["slug"] for c in res] == ["NOVO_26", "PF_25", "STJ_24", "TCU_25"]

        res_dict = {c["slug"]: c["situacao"] for c in res}
        assert res_dict["PF_25"] == "encerrado"  # encerrado > em_andamento
        assert res_dict["STJ_24"] == "encerrado"
        assert res_dict["TCU_25"] == "em_andamento"  # em_andamento > inscricoes_abertas
        assert res_dict["NOVO_26"] == "inscricoes_abertas"  # inscricoes_abertas > novos

        # Testa também através do método no spider
        spider = CebraspeSpider()
        res_spider = spider.listar_todas_listagens(page)
        assert res_spider == res


class TestMapearLinksPdf:
    def test_classifica_com_classificar_link_pdf(self, monkeypatch):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/PF_25_ADM"
        page.locator.return_value.element_handles.return_value = [
            _make_link("EDITAL Nº 1 – ABERTURA", "arquivos/ed1.pdf"),
            _make_link(
                "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS",
                "/concursos/PF_25_ADM/arquivos/prova.pdf",
            ),
            _make_link(
                "GABARITO DEFINITIVO – CARGO 1",
                "https://cdn.cebraspe.org.br/.../gab_def.pdf",
            ),
            _make_link("PADRÃO DEFINITIVO DE RESPOSTAS", "arquivos/padrao.pdf"),
            _make_link(
                "COMUNICADO – LOCAL DE REALIZAÇÃO DA PROVA OBJETIVA",
                "arquivos/comunicado.pdf",
            ),
            _make_link("Perguntas Frequentes", "https://www.cebraspe.org.br/duvidas"),
        ]

        pdfs = mapear_links_pdf(page, page.url)
        assert len(pdfs) == 5

        assert pdfs[0]["tipo"] == TIPO_EDITAL_ABERTURA
        assert (
            pdfs[0]["url"] == "https://www.cebraspe.org.br/concursos/arquivos/ed1.pdf"
        )
        assert pdfs[0]["curso_formacao"] is False

        assert pdfs[1]["tipo"] == TIPO_CADERNO_OBJETIVO
        assert (
            pdfs[1]["url"]
            == "https://www.cebraspe.org.br/concursos/PF_25_ADM/arquivos/prova.pdf"
        )

        assert pdfs[2]["tipo"] == TIPO_GABARITO
        assert pdfs[2]["versao"] == "definitivo"

        assert pdfs[3]["tipo"] == TIPO_PADRAO_RESPOSTA
        assert pdfs[3]["versao"] == "definitivo"

        assert pdfs[4]["tipo"] == TIPO_ADMINISTRATIVO

    def test_com_fixture_html_pagina_concurso(self, monkeypatch):
        monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
        fixture_path = FIXTURES_DIR / "pagina_concurso_amostra.html"
        assert fixture_path.exists()

        parser = FixtureLinkParser()
        parser.feed(fixture_path.read_text(encoding="utf-8"))

        page = MagicMock()
        page.url = "https://www.cebraspe.org.br/concursos/PF_25_ADM"
        page.locator.return_value.element_handles.return_value = parser.links

        spider = CebraspeSpider()
        pdfs = spider.mapear_links_pdf(page, page.url)

        # 6 PDFs no HTML (1 edital abertura, 1 caderno objetivo, 1 gabarito, 1 padrão resposta, 2 administrativos)
        assert len(pdfs) == 6
        tipos = [p["tipo"] for p in pdfs]
        assert tipos == [
            TIPO_EDITAL_ABERTURA,
            TIPO_CADERNO_OBJETIVO,
            TIPO_GABARITO,
            TIPO_PADRAO_RESPOSTA,
            TIPO_ADMINISTRATIVO,
            TIPO_ADMINISTRATIVO,
        ]
