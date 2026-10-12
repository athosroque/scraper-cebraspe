"""Testes de validação da previsão de download guiada pelo inventário (Etapa 8.C / C0 / KAN-30).

Valida para os 11 concursos de múltipla escolha (ME) de 2025 encerrados:
1. A contagem de cadernos prevista bate 100% com as contagens do inventário (154 provas: 110 obj + 44 disc).
2. A contagem de gabaritos prevista bate 100% com as contagens do inventário (155 gabaritos: 110 gab + 45 padrões).
3. Documentos de prova_outra (como a prova oral da PGE_ES) ficam fora da fila de provas e gabaritos.
4. Exatamente 1 edital canônico de abertura é selecionado por concurso para extração LLM via escolher_edital_extracao.
"""

from typing import Any

import pytest

from src.inventario import (
    TIPO_CADERNO_DISCURSIVO,
    TIPO_EDITAL_ABERTURA,
    TIPO_GABARITO,
    TIPO_PADRAO_RESPOSTA,
    TIPO_PROVA_OUTRA,
    TIPOS_CADERNO_OBJETIVO,
    carregar_concursos_jsonl,
    classificar_link_pdf,
    escolher_edital_extracao,
    pdf_vai_para_o_site,
)

ALVO_11_ME_2025 = [
    "SEFA_PR_25",
    "BANRISUL_25",
    "SEBRAE_25_PSE_1",
    "UNIVESP_25_PSS",
    "IPAAM_25",
    "SEMA_AM_25",
    "PGE_ES_25_PROCURADOR",
    "PGE_PI_25",
    "SEFAZ_SE_25_AUDITOR",
    "TCE_MG_25",
    "SEED_SE_25_PROFESSOR",
]

# Metadados esperados pelo inventário:
# (slug, cadernos_obj, cadernos_disc, gabaritos, padroes_resposta, prova_outra, total_editais)
METADADOS_ESPERADOS = {
    "SEFA_PR_25": (7, 1, 7, 1, 0, 2),
    "BANRISUL_25": (5, 4, 5, 5, 0, 2),
    "SEBRAE_25_PSE_1": (12, 2, 12, 2, 0, 2),
    "UNIVESP_25_PSS": (12, 1, 12, 1, 0, 2),
    "IPAAM_25": (22, 0, 22, 0, 0, 2),
    "SEMA_AM_25": (14, 0, 14, 0, 0, 2),
    "PGE_ES_25_PROCURADOR": (1, 1, 1, 1, 2, 2),
    "PGE_PI_25": (1, 2, 1, 2, 0, 2),
    "SEFAZ_SE_25_AUDITOR": (6, 6, 6, 6, 0, 1),
    "TCE_MG_25": (11, 10, 11, 10, 0, 2),
    "SEED_SE_25_PROFESSOR": (19, 17, 19, 17, 0, 2),
}


def _simular_map_pdf_links_offline(
    pdfs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Simula a classificação do map_pdf_links sem rede."""
    pdf_map = {
        "editais_abertura": [],
        "provas": [],
        "gabaritos": [],
        "nao_classificados": [],
    }
    for p in pdfs:
        text = p.get("texto", "")
        href = p.get("url", "")
        classif = classificar_link_pdf(text)
        tipo = classif["tipo"]
        entry = {"url": href, "texto": text}
        if tipo == TIPO_EDITAL_ABERTURA:
            pdf_map["editais_abertura"].append(entry)
        elif pdf_vai_para_o_site(classif):
            if tipo in (*TIPOS_CADERNO_OBJETIVO, TIPO_CADERNO_DISCURSIVO):
                pdf_map["provas"].append(entry)
            elif tipo in (TIPO_GABARITO, TIPO_PADRAO_RESPOSTA):
                pdf_map["gabaritos"].append(entry)
            else:
                pdf_map["nao_classificados"].append(entry)
        else:
            pdf_map["nao_classificados"].append(entry)
    return pdf_map


@pytest.fixture(scope="module")
def concursos_me():
    todos = carregar_concursos_jsonl()
    por_slug = {c["slug"]: c for c in todos if c["slug"] in ALVO_11_ME_2025}
    assert len(por_slug) == 11, (
        f"Faltam concursos no jsonl: {set(ALVO_11_ME_2025) - set(por_slug)}"
    )
    return por_slug


@pytest.mark.parametrize("slug", ALVO_11_ME_2025)
def test_concurso_me_previsao_bate_com_inventario(slug, concursos_me):
    concurso = concursos_me[slug]
    contagens = concurso["contagens"]
    mapa = _simular_map_pdf_links_offline(concurso["pdfs"])

    esperado = METADADOS_ESPERADOS[slug]
    exp_obj, exp_disc, exp_gab, exp_pad, exp_outra, exp_editais = esperado

    # 1. Contagens do inventário conferidas
    assert contagens["caderno_objetivo"] == exp_obj
    assert contagens["caderno_discursivo"] == exp_disc
    assert contagens["gabarito"] == exp_gab
    assert contagens["padrao_resposta"] == exp_pad
    assert contagens[TIPO_PROVA_OUTRA] == exp_outra
    assert contagens["edital_abertura"] == exp_editais

    # 2. Previsão de download do spider bate 100% com o inventário
    assert len(mapa["provas"]) == exp_obj + exp_disc
    assert len(mapa["gabaritos"]) == exp_gab + exp_pad
    assert len(mapa["editais_abertura"]) == exp_editais

    # 3. Exatamente 1 edital canônico escolhido por concurso
    escolhido = escolher_edital_extracao(mapa["editais_abertura"])
    assert escolhido is not None
    assert escolhido["url"].startswith("http")
    assert escolhido["texto"]
    # Se havia versão consolidada/atualizada, deve ter escolhido ela
    if exp_editais > 1:
        assert (
            "atualizado" in escolhido["texto"].lower()
            or "conforme retifica" in escolhido["texto"].lower()
        )


def test_totais_consolidados_dos_11_concursos_me(concursos_me):
    total_provas = 0
    total_gabaritos = 0
    total_editais_escolhidos = 0

    for slug in ALVO_11_ME_2025:
        concurso = concursos_me[slug]
        mapa = _simular_map_pdf_links_offline(concurso["pdfs"])
        total_provas += len(mapa["provas"])
        total_gabaritos += len(mapa["gabaritos"])
        escolhido = escolher_edital_extracao(mapa["editais_abertura"])
        if escolhido is not None:
            total_editais_escolhidos += 1

    # 110 objetivos + 44 discursivos = 154 provas
    assert total_provas == 154
    # 110 gabaritos + 45 padrões = 155 gabaritos
    assert total_gabaritos == 155
    # Exatamente 1 edital por concurso
    assert total_editais_escolhidos == 11
