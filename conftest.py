"""Configuração comum do pytest (tests/ e site/tests/).

Os testes exercitam caminhos de erro de propósito (timeout, PDF quebrado,
ID inventado). Sem isto, gravavam em `logs/scraper_cebraspe.log` e enchiam o
log de produção (661 MB, ~8 mil ERROR falsos), o que impedia conferir o
critério "0 exceções no log" da Etapa 6.
"""

from src.logger import file_handler, logger

logger.removeHandler(file_handler)
file_handler.close()

import pytest

TESTES_COM_BANCO_RAIZ = {
    "test_stats_writer",
    "test_arvore_views",
    "test_questoes_writer",
    "test_estatisticas_views",
    "test_registro_banco",
}

TESTES_SLOW = {
    "test_site_e_api_dao_o_mesmo_total",
    "test_fora_do_edital_saiu_do_painel",
    "test_rotulo_disciplina_no_painel_e_no_site",
    "test_combinacao_2_anos_2_cargos_3_assuntos",
    "test_resumo_e_prioridades_conhecidas",
    "test_historico_e_desempenho",
    "test_assunto_orfao_sai_no_servidor",
    "test_duracao_nota_anterior_e_revisar_erradas",
    "test_fila_ponta_a_ponta_e_idempotente",
    "test_facetas_respeitam_texto_e_com",
    "test_historico_com_login",
    "test_top10_lingua_portuguesa_por_nivel",
    "test_tailwind_css_versionado_em_dia",
    "test_detectar_compostos_dados_reais",
}

SITE_TESTES_UNITARIOS = {
    "test_formatacao.py",
    "test_tailwind.py",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        fspath_str = str(item.fspath)
        nome_arquivo = item.fspath.basename

        if item.name.split("[")[0] in TESTES_SLOW:
            item.add_marker(pytest.mark.slow)

        if "site/tests" in fspath_str:
            item.add_marker(pytest.mark.site)
            if nome_arquivo in SITE_TESTES_UNITARIOS:
                item.add_marker(pytest.mark.unit)
            else:
                item.add_marker(pytest.mark.db)
        else:
            item.add_marker(pytest.mark.pipeline)
            nome_modulo = nome_arquivo.replace(".py", "")
            if nome_modulo in TESTES_COM_BANCO_RAIZ:
                item.add_marker(pytest.mark.db)
            elif "TestConsumidorPostgres" in getattr(
                item.parent, "name", ""
            ) or "TestBancoCandidatos" in getattr(item.parent, "name", ""):
                item.add_marker(pytest.mark.db)
            else:
                item.add_marker(pytest.mark.unit)
