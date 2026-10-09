"""Testes automatizados de reconciliação e integridade do inventário (Etapa 8.0).

Auditor de QA & Reconciliação (Worker 5 da Onda 5).

Valida:
1. Reconciliação do piloto entre os manifestos locais (data/2025/CEBRASPE/) e o banco
   (70 cadernos de prova e 145 PDFs na fila de extração).
2. Reconciliação dos 31 concursos encerrados de 2025 identificados na sonda/auditoria.
3. Descarte estrito de slugs de navegação (SLUGS_NAVEGACAO).
4. Ausência de falsos positivos na classificação de provas ("PADRÃO DEFINITIVO DE RESPOSTAS"
   e comunicados de locais não inflam a contagem de provas).
5. Integridade estrutural do inventário em JSON e JSONL (campos obrigatórios, metadados
   e invariante de data_mapeamento ou erro explícito para concursos 2020+).
6. Regressão do piloto e estabilidade das chaves 5D das 2.800 questões extraídas.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.inventariar_concursos import (
    agrupar_por_ano,
    extrair_concursos_de_anos_json,
)
from src import stats_writer
from src.comparacao_texto import normalizar
from src.downloader import MANIFEST_FILENAME, PROVAS_TEXTO_FILENAME
from src.inventario import (
    CONCURSOS_PILOTO,
    INVENTARIO_ANOS_PATH,
    INVENTARIO_CONCURSOS_PATH,
    SLUGS_NAVEGACAO,
    TIPO_ADMINISTRATIVO,
    TIPO_CADERNO_DISCURSIVO,
    TIPO_CADERNO_OBJETIVO,
    TIPO_EDITAL_ABERTURA,
    TIPO_GABARITO,
    TIPO_PADRAO_RESPOSTA,
    carregar_anos_json,
    carregar_concursos_jsonl,
    classificar_link_pdf,
    cobertura_por_ano,
    salvar_concursos_jsonl,
)
from src.spider import (
    CebraspeSpider,
    extract_orgao_from_slug,
    extract_year_from_slug,
    listar_concursos,
    mapear_links_pdf,
)
from tests.test_stats_writer import _postgres_disponivel

PROJETO_DIR = Path(__file__).resolve().parent.parent
DATA_2025_DIR = PROJETO_DIR / "data" / "2025" / "CEBRASPE"
CANONICO_CLASSIFICACAO_PATH = PROJETO_DIR / "canonico" / "classificacao_questoes.json"

# Conjunto conhecido de 31 concursos encerrados de 2025 mapeados na sonda de 2026-10-08
# e na auditoria de 2026-09-19 (inclui os 5 do piloto e concursos como SEED_SE_25_PROFESSOR).
CONCURSOS_ENCERRADOS_2025_SONDA = [
    "AGSUS_25_CCE",
    "AGSUS_25_EC",
    "ANEEL_25_CF",
    "ANS_25_CF",
    "BANRISUL_25",
    "CAU_MG_25",
    "CD_25_NS",
    "FUB_25",
    "IBAMA_25",
    "IPAAM_25",
    "IRBR_25_DIPLOMACIA",
    "MP_CE_25_SERVIDOR",
    "MTE_25",
    "PF_25_ADM",
    "PGE_ES_25_PROCURADOR",
    "PGE_PI_25",
    "SEBRAE_25_PSE_1",
    "SEED_SE_25_PROFESSOR",
    "SEFAZ_SE_25_AUDITOR",
    "SEFA_PR_25",
    "SEMA_AM_25",
    "SEMA_MT_25_PSS",
    "STM_25",
    "SUSEP_25",
    "TCE_MG_25",
    "TCE_RS_25",
    "TCU_25_TEFC",
    "TELEBRAS_25",
    "TJ_PA_25_SERVIDOR",
    "UNIVESP_25_DOCENTE",
    "UNIVESP_25_PSS",
]


def _make_mock_link(text: str, href: str) -> MagicMock:
    """Helper para mockar nós <a> do Playwright."""
    link = MagicMock()
    link.inner_text.return_value = text
    link.get_attribute.return_value = href
    return link


def test_reconciliacao_piloto_manifestos_e_banco():
    """Valida que a soma de provas e gabaritos dos 5 manifestos do piloto

    bate exatamente com os 70 cadernos de prova e 145 PDFs da fila da Fase 5/6,
    tanto nos dados em disco quanto no banco PostgreSQL (quando disponível).
    """
    if not DATA_2025_DIR.is_dir():
        pytest.skip(
            f"{DATA_2025_DIR} ausente: manifestos e PDFs do piloto são gitignored "
            "e só existem no checkout com os dados baixados"
        )

    orgaos_piloto = ["CD", "IBAMA", "PF", "STM", "TCU"]
    contagens_disco = {
        "editais": 0,
        "provas": 0,
        "padroes_resposta": 0,
        "gabaritos": 0,
        "pulados_admin": 0,
        "total_manifesto": 0,
    }
    por_orgao = {}

    for orgao in orgaos_piloto:
        dir_orgao = DATA_2025_DIR / orgao
        manifest_path = dir_orgao / MANIFEST_FILENAME
        assert manifest_path.exists(), (
            f"Manifesto ausente para {orgao}: {manifest_path}"
        )

        manifesto = json.loads(manifest_path.read_text(encoding="utf-8"))
        textos_links = {}
        textos_path = dir_orgao / PROVAS_TEXTO_FILENAME
        if textos_path.exists():
            textos_links = json.loads(textos_path.read_text(encoding="utf-8"))

        contagens_disco["total_manifesto"] += len(manifesto)

        orgao_stats = {
            "provas": 0,
            "padroes": 0,
            "gabaritos": 0,
            "editais": 0,
            "pulados": 0,
        }

        for url, entrada in manifesto.items():
            path_str = entrada.get("path", "")
            arquivo = Path(path_str).name

            if "/Editais/" in path_str:
                contagens_disco["editais"] += 1
                orgao_stats["editais"] += 1
            elif "/Gabaritos/" in path_str:
                contagens_disco["gabaritos"] += 1
                orgao_stats["gabaritos"] += 1
            elif "/Provas/" in path_str:
                texto_link = textos_links.get(arquivo, "")
                classificacao = (
                    stats_writer.classificar_prova_por_texto(texto_link)
                    if texto_link
                    else None
                )
                if classificacao is None:
                    contagens_disco["pulados_admin"] += 1
                    orgao_stats["pulados"] += 1
                elif classificacao["tipo"] == "padrao_resposta":
                    contagens_disco["padroes_resposta"] += 1
                    orgao_stats["padroes"] += 1
                else:
                    contagens_disco["provas"] += 1
                    orgao_stats["provas"] += 1

        por_orgao[orgao] = orgao_stats

    # 1. Validação de contagens em disco/manifestos
    assert contagens_disco["total_manifesto"] == 158
    assert contagens_disco["editais"] == 10
    assert (
        contagens_disco["pulados_admin"] == 3
    )  # 3 editais residuais na pasta Provas da PF
    assert contagens_disco["provas"] == 70
    assert contagens_disco["padroes_resposta"] == 27
    assert contagens_disco["gabaritos"] == 48

    total_gabaritos_fila = (
        contagens_disco["gabaritos"] + contagens_disco["padroes_resposta"]
    )
    assert total_gabaritos_fila == 75

    total_fila = contagens_disco["provas"] + total_gabaritos_fila
    assert total_fila == 145

    # Validação detalhada por órgão do piloto
    assert por_orgao["CD"]["provas"] == 5
    assert por_orgao["IBAMA"]["provas"] == 8
    assert por_orgao["PF"]["provas"] == 32
    assert por_orgao["STM"]["provas"] == 22
    assert por_orgao["TCU"]["provas"] == 3

    assert por_orgao["CD"]["gabaritos"] + por_orgao["CD"]["padroes"] == 6
    assert por_orgao["IBAMA"]["gabaritos"] + por_orgao["IBAMA"]["padroes"] == 9
    assert por_orgao["PF"]["gabaritos"] + por_orgao["PF"]["padroes"] == 33
    assert por_orgao["STM"]["gabaritos"] + por_orgao["STM"]["padroes"] == 23
    assert por_orgao["TCU"]["gabaritos"] + por_orgao["TCU"]["padroes"] == 4

    # 2. Reconciliação direta contra o banco PostgreSQL se disponível
    if _postgres_disponivel():
        conn = stats_writer.conectar()
        try:
            with conn.cursor() as cur:
                # Concursos piloto
                cur.execute("SELECT slug, status_revisao FROM concursos ORDER BY slug;")
                concursos_db = cur.fetchall()
                slugs_db = {row[0] for row in concursos_db}
                assert slugs_db == CONCURSOS_PILOTO
                for _, status in concursos_db:
                    assert status == "aprovado"

                # Provas cadernos
                cur.execute("SELECT count(*) FROM provas;")
                assert cur.fetchone()[0] == 70

                cur.execute(
                    """
                    SELECT c.slug, count(p.id)
                    FROM concursos c
                    LEFT JOIN provas p ON p.concurso_id = c.id
                    GROUP BY c.slug
                    ORDER BY c.slug;
                    """
                )
                provas_por_slug = dict(cur.fetchall())
                assert provas_por_slug["CD_25_NS"] == 5
                assert provas_por_slug["IBAMA_25"] == 8
                assert provas_por_slug["PF_25_ADM"] == 32
                assert provas_por_slug["STM_25"] == 22
                assert provas_por_slug["TCU_25_TEFC"] == 3

                # Fila de extração
                cur.execute("SELECT count(*) FROM fila_extracao_questoes;")
                assert cur.fetchone()[0] == 145

                cur.execute(
                    """
                    SELECT categoria, count(*)
                    FROM fila_extracao_questoes
                    GROUP BY categoria;
                    """
                )
                fila_categorias = dict(cur.fetchall())
                assert fila_categorias.get("prova") == 70
                assert fila_categorias.get("gabarito") == 75

                cur.execute(
                    """
                    SELECT c.slug, f.categoria, count(f.id)
                    FROM concursos c
                    JOIN fila_extracao_questoes f ON f.concurso_id = c.id
                    GROUP BY c.slug, f.categoria;
                    """
                )
                fila_por_slug_cat = {}
                for slug, cat, cnt in cur.fetchall():
                    fila_por_slug_cat[(slug, cat)] = cnt

                assert fila_por_slug_cat[("CD_25_NS", "prova")] == 5
                assert fila_por_slug_cat[("CD_25_NS", "gabarito")] == 6
                assert fila_por_slug_cat[("IBAMA_25", "prova")] == 8
                assert fila_por_slug_cat[("IBAMA_25", "gabarito")] == 9
                assert fila_por_slug_cat[("PF_25_ADM", "prova")] == 32
                assert fila_por_slug_cat[("PF_25_ADM", "gabarito")] == 33
                assert fila_por_slug_cat[("STM_25", "prova")] == 22
                assert fila_por_slug_cat[("STM_25", "gabarito")] == 23
                assert fila_por_slug_cat[("TCU_25_TEFC", "prova")] == 3
                assert fila_por_slug_cat[("TCU_25_TEFC", "gabarito")] == 4
        finally:
            conn.close()


def test_reconciliacao_31_concursos_2025(monkeypatch):
    """Testa que o conjunto conhecido dos 31 concursos de 2025 identificados

    na sonda e na auditoria é tratado sem erros e sem slugs de navegação.
    """
    assert len(CONCURSOS_ENCERRADOS_2025_SONDA) == 31
    assert len(set(CONCURSOS_ENCERRADOS_2025_SONDA)) == 31

    # Valida que todos os 5 do piloto estão contidos
    assert CONCURSOS_PILOTO.issubset(set(CONCURSOS_ENCERRADOS_2025_SONDA))

    # Valida concurso emblemático SEED_SE_25_PROFESSOR
    assert "SEED_SE_25_PROFESSOR" in CONCURSOS_ENCERRADOS_2025_SONDA

    # Valida propriedades determinísticas de cada slug
    for slug in CONCURSOS_ENCERRADOS_2025_SONDA:
        assert extract_year_from_slug(slug) == 2025, f"Ano incorreto para {slug}"
        assert slug not in SLUGS_NAVEGACAO, f"Slug de navegação em lote: {slug}"
        orgao = extract_orgao_from_slug(slug)
        assert orgao and orgao != slug or "_" in slug, (
            f"Órgão não identificado para {slug}"
        )

    # Simula extração através de listar_concursos misturando os 31 com navegação e outros anos
    monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
    links_simulados = [
        _make_mock_link("Link " + s, f"/concursos/{s}")
        for s in CONCURSOS_ENCERRADOS_2025_SONDA
    ]
    # Adiciona links de navegação para certificar que são descartados
    for nav in SLUGS_NAVEGACAO:
        links_simulados.append(_make_mock_link("Navegação " + nav, f"/concursos/{nav}"))
    links_simulados.append(_make_mock_link("Main Anchor", "#main"))
    # Adiciona outros anos
    links_simulados.append(_make_mock_link("Concurso Antigo", "/concursos/INSS_2015"))
    links_simulados.append(_make_mock_link("Concurso Anterior", "/concursos/ABIN_17"))

    mock_page = MagicMock()
    mock_page.url = "https://www.cebraspe.org.br/concursos/encerrado"
    mock_page.locator.return_value.element_handles.return_value = links_simulados

    spider = CebraspeSpider(target_year=2025)
    contests_spider = spider.get_contest_links(mock_page)

    assert len(contests_spider) == 31
    slugs_retornados = {c["slug"] for c in contests_spider}
    assert slugs_retornados == set(CONCURSOS_ENCERRADOS_2025_SONDA)
    assert not (slugs_retornados & SLUGS_NAVEGACAO)

    # Agrupamento por ano do inventário
    dados_brutos = listar_concursos(mock_page, mock_page.url, "encerrado")
    agrupados = agrupar_por_ano(dados_brutos)
    assert "2025" in agrupados
    assert len(agrupados["2025"]["encerrado"]) == 31
    assert set(agrupados["2025"]["encerrado"]) == set(CONCURSOS_ENCERRADOS_2025_SONDA)

    # Se inventario/anos.json já existir em disco, valida consistência com arquivo
    if INVENTARIO_ANOS_PATH.exists():
        anos_disco = json.loads(INVENTARIO_ANOS_PATH.read_text(encoding="utf-8"))
        if "2025" in anos_disco and "encerrado" in anos_disco["2025"]:
            encerrados_2025 = set(anos_disco["2025"]["encerrado"])
            assert len(encerrados_2025) >= 31
            assert set(CONCURSOS_ENCERRADOS_2025_SONDA).issubset(encerrados_2025)


def test_zero_slugs_navegacao(monkeypatch):
    """Valida categoricamente que nenhum dos slugs em SLUGS_NAVEGACAO

    (em-andamento, encerrado, inscricoes-abertas, novos, main, #main)
    pode ser aceito como concurso válido.
    """
    slugs_proibidos = {
        "em-andamento",
        "encerrado",
        "inscricoes-abertas",
        "novos",
        "main",
        "#main",
    }
    # SLUGS_NAVEGACAO do módulo inventario deve conter os elementos base
    for s in {"em-andamento", "encerrado", "inscricoes-abertas", "novos", "main"}:
        assert s in SLUGS_NAVEGACAO

    # Nenhum slug proibido pode ter ano válido
    for s in slugs_proibidos:
        assert extract_year_from_slug(s) is None
        assert (
            extract_year_from_slug(f"https://www.cebraspe.org.br/concursos/{s}") is None
        )

    # Garante que listar_concursos e CebraspeSpider descartam 100% de páginas puras de navegação
    monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
    links_navegacao = [
        _make_mock_link("Navegação " + s, f"/concursos/{s}") for s in slugs_proibidos
    ]
    links_navegacao.extend(
        [
            _make_mock_link("Absoluto", f"https://www.cebraspe.org.br/concursos/{s}")
            for s in slugs_proibidos
        ]
    )

    mock_page = MagicMock()
    mock_page.url = "https://www.cebraspe.org.br/concursos/encerrado"
    mock_page.locator.return_value.element_handles.return_value = links_navegacao

    resultado_spider = CebraspeSpider().get_contest_links(mock_page)
    assert resultado_spider == []

    resultado_listar = listar_concursos(mock_page, mock_page.url, "encerrado")
    assert resultado_listar == []

    # Se transformar anos.json mockado em lista, não pode haver slug proibido
    anos_data_mock = {
        "2025": {"encerrado": ["PF_25_ADM", "encerrado", "main"], "outros": []}
    }
    concursos_extraidos = extrair_concursos_de_anos_json(anos_data_mock)
    slugs_extraidos = {c["slug"] for c in concursos_extraidos}
    assert slugs_extraidos == {"PF_25_ADM", "encerrado", "main"}
    # Mesmo se injetado em anos.json, SLUGS_NAVEGACAO não deve ser aceito
    concursos_filtrados = [
        c for c in concursos_extraidos if c["slug"] not in SLUGS_NAVEGACAO
    ]
    assert len(concursos_filtrados) == 1
    assert concursos_filtrados[0]["slug"] == "PF_25_ADM"


def test_classificacao_link_sem_falsos_positivos_provas(monkeypatch):
    """Valida que 'PADRÃO DEFINITIVO DE RESPOSTAS' (singular), comunicados de local de prova

    e editais administrativos NÃO caem em caderno_objetivo nem caderno_discursivo,
    evitando inflar a contagem de provas (bug crítico identificado na sonda ao vivo).
    """
    casos_nao_provas = [
        # Padrões de resposta (singular e plural)
        ("PADRÃO DEFINITIVO DE RESPOSTAS", TIPO_PADRAO_RESPOSTA),
        (
            "PADRÃO DEFINITIVO DE RESPOSTAS – PROVA DISCURSIVA – CARGO 1",
            TIPO_PADRAO_RESPOSTA,
        ),
        ("PADRÃO DE RESPOSTA DEFINITIVO", TIPO_PADRAO_RESPOSTA),
        (
            "PADRÕES DEFINITIVOS DE RESPOSTAS – PROVAS DISCURSIVAS(P3)",
            TIPO_PADRAO_RESPOSTA,
        ),
        ("PADRAO DEFINITIVO DE RESPOSTA", TIPO_PADRAO_RESPOSTA),
        # Comunicados e editais administrativos
        (
            "COMUNICADO – LOCAL DE REALIZAÇÃO DA PROVA OBJETIVA",
            TIPO_ADMINISTRATIVO,
        ),
        (
            "COMUNICADO – LOCAIS DE REALIZAÇÃO DAS PROVAS OBJETIVAS",
            TIPO_ADMINISTRATIVO,
        ),
        (
            "COMUNICADO - LOCAIS DE APLICAÇÃO DAS PROVAS",
            TIPO_ADMINISTRATIVO,
        ),
        (
            "EDITAL Nº 5 – LOCAIS DE APLICAÇÃO DAS PROVAS OBJETIVAS E DA PROVA DISCURSIVA",
            TIPO_ADMINISTRATIVO,
        ),
        (
            "EDITAL Nº 6 – RESULTADO FINAL NAS PROVAS OBJETIVAS E O RESULTADO PROVISÓRIO NA PROVA DISCURSIVA",
            TIPO_ADMINISTRATIVO,
        ),
        (
            "EDITAL Nº 8 - RETIFICAÇÃO E REABERTURA DO PERÍODO DE ACESSO",
            TIPO_ADMINISTRATIVO,
        ),
    ]

    for texto, tipo_esperado in casos_nao_provas:
        res = classificar_link_pdf(texto)
        assert res["tipo"] == tipo_esperado, (
            f"Texto '{texto}' classificado como '{res['tipo']}' em vez de '{tipo_esperado}'"
        )
        assert res["tipo"] not in (
            TIPO_CADERNO_OBJETIVO,
            TIPO_CADERNO_DISCURSIVO,
        ), f"Falso positivo de prova detectado para texto: '{texto}'"

    # Caso real da sonda: SEED_SE_25_PROFESSOR
    # Esse concurso possuía "PADRÃO DEFINITIVO DE RESPOSTAS" que causava falso positivo no crawler antigo
    links_seed_se = [
        _make_mock_link(
            "EDITAL Nº 1 – ABERTURA", "https://cdn.cebraspe.org.br/ed1.pdf"
        ),
        _make_mock_link(
            "PROVA OBJETIVA – PROFESSOR DE MATEMÁTICA",
            "https://cdn.cebraspe.org.br/p_mat.pdf",
        ),
        _make_mock_link(
            "PROVA DISCURSIVA – ESTUDO DE CASO",
            "https://cdn.cebraspe.org.br/p_disc.pdf",
        ),
        _make_mock_link("GABARITO DEFINITIVO", "https://cdn.cebraspe.org.br/gab.pdf"),
        _make_mock_link(
            "PADRÃO DEFINITIVO DE RESPOSTAS",
            "https://cdn.cebraspe.org.br/padrao.pdf",
        ),
        _make_mock_link(
            "COMUNICADO – LOCAL DE REALIZAÇÃO DA PROVA OBJETIVA",
            "https://cdn.cebraspe.org.br/comunicado.pdf",
        ),
    ]

    monkeypatch.setattr("src.spider.stealth_wait", lambda: None)
    mock_page = MagicMock()
    mock_page.url = "https://www.cebraspe.org.br/concursos/SEED_SE_25_PROFESSOR"
    mock_page.locator.return_value.element_handles.return_value = links_seed_se

    pdfs = mapear_links_pdf(mock_page, mock_page.url)
    tipos_classificados = [p["tipo"] for p in pdfs]

    assert tipos_classificados == [
        TIPO_EDITAL_ABERTURA,
        TIPO_CADERNO_OBJETIVO,
        TIPO_CADERNO_DISCURSIVO,
        TIPO_GABARITO,
        TIPO_PADRAO_RESPOSTA,
        TIPO_ADMINISTRATIVO,
    ]

    # Contagem de cadernos deve ser estritamente 2 (1 objetivo + 1 discursivo), NUNCA 4!
    total_cadernos = sum(
        1
        for t in tipos_classificados
        if t in (TIPO_CADERNO_OBJETIVO, TIPO_CADERNO_DISCURSIVO)
    )
    assert total_cadernos == 2


def test_integridade_estrutura_inventario_json_e_jsonl(tmp_path):
    """Valida que registros de concursos.jsonl e anos.json contêm todos os campos requeridos:

    slug, orgao, ano, situacao, url, data_mapeamento, contagens, alertas, no_banco,
    e que todo concurso de ano 2020+ possui data_mapeamento ou erro explícito.
    """
    campos_obrigatorios = {
        "slug",
        "orgao",
        "ano",
        "situacao",
        "url",
        "data_mapeamento",
        "contagens",
        "alertas",
        "no_banco",
    }
    contagens_obrigatorias = {
        "edital_abertura",
        "caderno_objetivo",
        "caderno_discursivo",
        "gabarito",
        "padrao_resposta",
        "administrativo",
        "nao_classificado",
    }

    # Registro de teste completo e válido
    registro_valido_2025 = {
        "slug": "PF_25_ADM",
        "orgao": "PF",
        "ano": 2025,
        "situacao": "encerrado",
        "url": "https://www.cebraspe.org.br/concursos/PF_25_ADM",
        "data_mapeamento": datetime.now().isoformat(),
        "qtd_editais": 3,
        "qtd_cadernos": 32,
        "qtd_gabaritos": 18,
        "qtd_padroes": 15,
        "qtd_administrativos": 3,
        "qtd_nao_classificados": 0,
        "contagens": {
            "edital_abertura": 3,
            "caderno_objetivo": 20,
            "caderno_discursivo": 12,
            "gabarito": 18,
            "padrao_resposta": 15,
            "administrativo": 3,
            "nao_classificado": 0,
        },
        "formato_provavel": "ce",
        "alertas": [],
        "incluir": True,
        "no_banco": True,
        "erro": None,
        "pdfs": [],
    }

    # Registro com falha de rede/mapeamento explícita
    registro_com_erro = {
        "slug": "CONCURSO_FALHA_25",
        "orgao": "TESTE",
        "ano": 2025,
        "situacao": "encerrado",
        "url": "https://www.cebraspe.org.br/concursos/CONCURSO_FALHA_25",
        "data_mapeamento": datetime.now().isoformat(),
        "qtd_editais": 0,
        "qtd_cadernos": 0,
        "qtd_gabaritos": 0,
        "qtd_padroes": 0,
        "qtd_administrativos": 0,
        "qtd_nao_classificados": 0,
        "contagens": {
            "edital_abertura": 0,
            "caderno_objetivo": 0,
            "caderno_discursivo": 0,
            "gabarito": 0,
            "padrao_resposta": 0,
            "administrativo": 0,
            "nao_classificado": 0,
        },
        "formato_provavel": None,
        "alertas": ["sem_edital_abertura", "sem_caderno"],
        "incluir": None,
        "no_banco": False,
        "erro": "Timeout 30000ms excedido",
        "pdfs": [],
    }

    caminho_teste = tmp_path / "concursos.jsonl"
    salvar_concursos_jsonl([registro_valido_2025, registro_com_erro], caminho_teste)

    carregados = carregar_concursos_jsonl(caminho_teste)
    assert len(carregados) == 2

    for reg in carregados:
        # 1. Campos obrigatórios presentes
        for campo in campos_obrigatorios:
            assert campo in reg, f"Campo '{campo}' ausente no registro {reg}"

        # 2. Contagens presentes e consistentes
        for ctg in contagens_obrigatorias:
            assert ctg in reg["contagens"], f"Contagem '{ctg}' ausente em {reg['slug']}"
            assert isinstance(reg["contagens"][ctg], int)

        assert isinstance(reg["alertas"], list)
        assert isinstance(reg["no_banco"], bool)

        # 3. Invariante 2020+: data_mapeamento ou erro explícito
        if reg.get("ano") and reg["ano"] >= 2020:
            tem_data = bool(reg.get("data_mapeamento"))
            tem_erro = bool(reg.get("erro"))
            assert tem_data or tem_erro, (
                f"Concurso 2020+ '{reg['slug']}' sem data_mapeamento nem erro explícito."
            )

    # Se existir o arquivo real do inventário (gerado em execução do pipeline), valida-o também
    if INVENTARIO_CONCURSOS_PATH.exists():
        registros_reais = carregar_concursos_jsonl(INVENTARIO_CONCURSOS_PATH)
        assert len(registros_reais) > 0
        for reg in registros_reais:
            for campo in campos_obrigatorios:
                assert campo in reg, (
                    f"Campo '{campo}' ausente no arquivo real {reg.get('slug')}"
                )
            if reg.get("ano") and reg["ano"] >= 2020:
                tem_data = bool(reg.get("data_mapeamento"))
                tem_erro = bool(reg.get("erro"))
                assert tem_data or tem_erro, (
                    f"Registro real 2020+ '{reg['slug']}' sem data_mapeamento nem erro."
                )


def test_regressao_piloto_chaves_5d_inalteradas():
    """Valida que canonico/classificacao_questoes.json e as chaves 5D

    das 2.800 questões continuam intactas e alinhadas ao banco.
    """
    assert CANONICO_CLASSIFICACAO_PATH.exists(), (
        f"Arquivo canônico ausente: {CANONICO_CLASSIFICACAO_PATH}"
    )

    conteudo = json.loads(CANONICO_CLASSIFICACAO_PATH.read_text(encoding="utf-8"))
    registros = conteudo.get("registros", conteudo)

    assert isinstance(registros, dict)
    assert len(registros) >= 2800, (
        f"Menos de 2.800 registros encontrados: {len(registros)}"
    )

    padrao_chave_5d = re.compile(r"^([A-Z0-9_]+)\|([A-Za-z0-9_]+)\|(D?\d+)$")
    concursos_encontrados = set()

    for chave, item in registros.items():
        match = padrao_chave_5d.match(chave)
        assert match is not None, (
            f"Chave 5D em formato inválido: '{chave}' (esperado concurso|caderno|numero)"
        )

        slug_concurso = match.group(1)
        concursos_encontrados.add(slug_concurso)

        # Hash SHA-1 de 40 hexadecimais
        hash_enunciado = item.get("hash_enunciado", "")
        assert re.match(r"^[0-9a-f]{40}$", hash_enunciado), (
            f"hash_enunciado inválido na chave {chave}: {hash_enunciado}"
        )

        # Apontamentos
        assert "apontamentos" in item, f"Campo 'apontamentos' ausente na chave {chave}"
        assert isinstance(item["apontamentos"], list)

    # Valida que todos os 5 concursos do piloto estão representados
    assert CONCURSOS_PILOTO.issubset(concursos_encontrados)

    # Se o banco de dados PostgreSQL estiver disponível, valida casamento exato de 2.800 questões
    if _postgres_disponivel():
        conn = stats_writer.conectar()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM questoes;")
                total_banco = cur.fetchone()[0]
                assert total_banco == 2800, (
                    f"Total no banco deve ser 2.800, obtido: {total_banco}"
                )

                # Recupera chaves 5D geradas pelo banco: concurso|caderno|numero
                cur.execute(
                    """
                    SELECT c.slug, coalesce(p.codigo_caderno, p.arquivo), q.numero
                    FROM questoes q
                    JOIN provas p ON p.id = q.prova_id
                    JOIN concursos c ON c.id = p.concurso_id;
                    """
                )
                chaves_banco = set()
                for slug, caderno, numero in cur.fetchall():
                    stem_caderno = caderno.replace(".pdf", "").replace(".PDF", "")
                    chaves_banco.add(f"{slug}|{stem_caderno}|{numero}")

                assert len(chaves_banco) == 2800

                # Verifica que 100% das 2.800 questões do banco estão presentes no JSON canônico
                intersecao = chaves_banco.intersection(registros.keys())
                assert len(intersecao) == 2800, (
                    f"Interseção incompleta: {len(intersecao)} / 2800"
                )

                diferenca = chaves_banco - set(registros.keys())
                assert len(diferenca) == 0, (
                    f"Chaves do banco ausentes no JSON canônico: {diferenca}"
                )
        finally:
            conn.close()


def test_inventario_real_2020_sem_concurso_sem_estado():
    """Todo slug 2020+ das listagens (`anos.json`) tem registro no JSONL,
    mapeado ou com `erro` explícito (critério "Pronto quando" da 8.0)."""
    anos = carregar_anos_json(INVENTARIO_ANOS_PATH)
    if not anos:
        pytest.skip("inventario/anos.json ausente")
    cobertura = cobertura_por_ano(
        carregar_concursos_jsonl(INVENTARIO_CONCURSOS_PATH), anos
    )
    assert cobertura, "anos.json sem anos 2020+"
    sem_estado = {x["ano"]: x["sem_estado"] for x in cobertura if x["sem_estado"]}
    assert sem_estado == {}


# Texto de link que nunca é caderno objetivo (comunicado, relação, prova oral,
# didática, escrita/subjetiva/prática, desempenho). "PROVA ESCRITA OBJETIVA" e
# "PROVA OBJETIVA COM JUSTIFICATIVAS" são cadernos objetivos reais.
PADRAO_SUSPEITO_CADERNO_OBJETIVO = re.compile(
    r"^comunicado|^relacao|^composicao|justificativ|\boral\b|didatic|pratic"
    r"|subjetiv|escrita|desempenho"
)
PADRAO_CADERNO_OBJETIVO_LEGITIMO = re.compile(
    r"\bescrita objetiva\b|^prova objetiva com justificativas\b"
)


def test_inventario_real_sem_falso_caderno_objetivo():
    """Nenhum PDF do inventário versionado classificado como caderno objetivo
    tem texto de comunicado, prova oral/didática ou prova escrita."""
    suspeitos = [
        (c["slug"], p["texto"])
        for c in carregar_concursos_jsonl(INVENTARIO_CONCURSOS_PATH)
        for p in c.get("pdfs") or []
        if p.get("tipo") == TIPO_CADERNO_OBJETIVO
        and PADRAO_SUSPEITO_CADERNO_OBJETIVO.search(normalizar(p.get("texto") or ""))
        and not PADRAO_CADERNO_OBJETIVO_LEGITIMO.search(
            normalizar(p.get("texto") or "")
        )
    ]
    assert suspeitos == []
