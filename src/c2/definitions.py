"""Definições do Dagster para o projeto Scraper CEBRASPE (C2, D5a).

Exporta o objeto `defs` consumido pelo `dagster-webserver`, `dagster-daemon`
e pela suíte de testes.
"""

from dagster import AssetSelection, Definitions, define_asset_job

from src.c2.assets import TODOS_ASSETS
from src.c2.checks import TODOS_ASSET_CHECKS

lote_concursos_job = define_asset_job(
    name="lote_concursos",
    selection=AssetSelection.all(),
    description="Orquestrador do lote de concursos CEBRASPE (C2, D5a e D5b)",
)

defs = Definitions(
    assets=TODOS_ASSETS,
    asset_checks=TODOS_ASSET_CHECKS,
    jobs=[lote_concursos_job],
)
