"""Definições do Dagster para o projeto Scraper CEBRASPE (C2, D5a).

Exporta o objeto `defs` consumido pelo `dagster-webserver`, `dagster-daemon`
e pela suíte de testes.
"""

from dagster import AssetSelection, Definitions, define_asset_job

from src.c2.assets import TODOS_ASSETS

lote_concursos_job = define_asset_job(
    name="lote_concursos",
    selection=AssetSelection.all(),
    description="Orquestrador do lote de concursos CEBRASPE (C2, D5a)",
)

defs = Definitions(
    assets=TODOS_ASSETS,
    jobs=[lote_concursos_job],
)
