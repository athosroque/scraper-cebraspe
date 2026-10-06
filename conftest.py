"""Configuração comum do pytest (tests/ e site/tests/).

Os testes exercitam caminhos de erro de propósito (timeout, PDF quebrado,
ID inventado). Sem isto, gravavam em `logs/scraper_cebraspe.log` e enchiam o
log de produção (661 MB, ~8 mil ERROR falsos), o que impedia conferir o
critério "0 exceções no log" da Etapa 6.
"""

from src.logger import file_handler, logger

logger.removeHandler(file_handler)
file_handler.close()
