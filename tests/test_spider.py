from src.spider import extract_orgao_from_slug, extract_year_from_slug


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
