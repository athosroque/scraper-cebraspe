"""Definição de partições dinâmicas para o orquestrador C2 (Dagster).

Partições por concurso vêm do inventário (`inventario/concursos.jsonl`),
permitindo materializações e lotes particionados por certame (KAN-31, D5a).
"""

from dagster import DynamicPartitionsDefinition

from src.inventario import INVENTARIO_CONCURSOS_PATH, carregar_concursos_jsonl

CONCURSOS_PARTITIONS_NAME = "concursos"
concursos_partitions = DynamicPartitionsDefinition(name=CONCURSOS_PARTITIONS_NAME)


def obter_slugs_inventario() -> list[str]:
    """Retorna os slugs de todos os concursos catalogados no inventário."""
    if not INVENTARIO_CONCURSOS_PATH.exists():
        return []
    return [
        c["slug"]
        for c in carregar_concursos_jsonl(INVENTARIO_CONCURSOS_PATH)
        if c.get("slug")
    ]


def sincronizar_particoes_inventario(instance) -> list[str]:
    """Sincroniza os slugs do inventário com as partições dinâmicas do Dagster."""
    slugs = obter_slugs_inventario()
    if not slugs:
        return []
    existentes = set(instance.get_dynamic_partitions(CONCURSOS_PARTITIONS_NAME))
    novos = [s for s in slugs if s not in existentes]
    if novos:
        instance.add_dynamic_partitions(CONCURSOS_PARTITIONS_NAME, novos)
    return slugs
