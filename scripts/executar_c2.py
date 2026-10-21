"""CLI de execução do pipeline via Dagster (C2, D5a, KAN-31).

Permite disparar a execução de lotes particionados por concurso diretamente
da linha de comando em modo conferência ou produção.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dagster import DagsterInstance

from src.c2.definitions import defs
from src.c2.partitions import (
    CONCURSOS_PARTITIONS_NAME,
    sincronizar_particoes_inventario,
)
from src.logger import logger

CONCURSOS_PADRAO_C1 = ["SEFA_PR_25", "BANRISUL_25"]


def obter_instancia() -> DagsterInstance:
    """Obtém a instância persistida do Dagster; sem o banco, levanta RuntimeError.

    Sem fallback efêmero: um lote sem registro não pode terminar com código 0.
    Instância efêmera só nos testes, passando `instance=` explicitamente.
    """
    from dotenv import load_dotenv

    raiz = Path(__file__).resolve().parent.parent
    load_dotenv(raiz / ".env")

    if "DAGSTER_HOME" not in os.environ:
        padrao = raiz / "dagster_home"
        if padrao.exists():
            os.environ["DAGSTER_HOME"] = str(padrao)

    if "DAGSTER_PG_HOST" not in os.environ:
        os.environ["DAGSTER_PG_HOST"] = os.environ.get("POSTGRES_HOST", "localhost")
    if "DAGSTER_PG_PORT" not in os.environ:
        os.environ["DAGSTER_PG_PORT"] = str(os.environ.get("POSTGRES_PORT", "5435"))
    if "DAGSTER_PG_DB" not in os.environ:
        os.environ["DAGSTER_PG_DB"] = os.environ.get("DAGSTER_PG_DB", "dagster")
    try:
        return DagsterInstance.get()
    except Exception as e:
        raise RuntimeError(
            f"Não foi possível abrir a instância persistida do Dagster ({e})"
        ) from e


def executar_lote(
    concursos: list[str] | None = None,
    conferencia: bool = True,
    exigir_aprovacao: bool = False,
    instance: DagsterInstance | None = None,
) -> bool:
    """Executa o lote de concursos selecionados via Dagster."""
    inst = instance or obter_instancia()
    alvos = concursos or CONCURSOS_PADRAO_C1

    logger.info(
        f"[C2] Iniciando execução do lote: {alvos} (modo conferência={conferencia}, exigir_aprovacao={exigir_aprovacao})"
    )
    sincronizar_particoes_inventario(inst)

    job_def = defs.get_job_def("lote_concursos")
    todos_ok = True

    for slug in alvos:
        logger.info(f"[C2] Executando pipeline para concurso partição: {slug}")
        run_config = {
            "ops": {
                f"p{i}": {
                    "config": {
                        "conferencia": conferencia,
                        "exigir_aprovacao": exigir_aprovacao,
                    }
                }
                for i in [
                    "0",
                    "1",
                    "2",
                    "3",
                    "4",
                    "4b",
                    "5",
                    "6",
                    "7",
                    "8",
                    "9",
                    "10",
                    "11",
                ]
            }
        }
        resultado = job_def.execute_in_process(
            instance=inst,
            partition_key=slug,
            run_config=run_config,
        )
        if not resultado.success:
            logger.error(f"[C2] Falha na execução da partição {slug}")
            todos_ok = False
        else:
            logger.info(f"[C2] Concurso {slug} processado com sucesso.")

    return todos_ok


def main(args_list: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Executa o lote de concursos no Dagster (C2)",
        epilog=(
            "AVISO: --no-conferencia não deve ser usado antes da D5b: os assets P4 e "
            "P10 chamam funções globais (gravar_estatisticas, processar_fila, "
            "atualizar_artefatos_revisao). Rode K22–K24 antes e depois do lote."
        ),
    )
    parser.add_argument(
        "--concursos",
        nargs="+",
        default=CONCURSOS_PADRAO_C1,
        help="Slugs dos concursos a executar no lote (padrão: lote da C1)",
    )
    parser.add_argument(
        "--conferencia",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Executa em modo conferência (somente leitura/idempotente, sem chamadas externas). NÃO use --no-conferencia antes da D5b",
    )
    parser.add_argument(
        "--exigir-aprovacao",
        action="store_true",
        default=False,
        help="Bloqueia no portão humano se o concurso não tiver aprovação formal no edital",
    )
    parser.add_argument(
        "--sincronizar-apenas",
        action="store_true",
        help="Apenas sincroniza as partições do inventário com o banco do Dagster",
    )
    args = parser.parse_args(args_list)

    try:
        inst = obter_instancia()
        # força a conexão agora: DagsterInstance.get() é preguiçosa com o banco
        inst.get_dynamic_partitions(CONCURSOS_PARTITIONS_NAME)
    except Exception as e:
        logger.error(f"[C2] Banco do Dagster inacessível, nada foi executado: {e}")
        sys.exit(1)
    if args.sincronizar_apenas:
        adicionados = sincronizar_particoes_inventario(inst)
        print(f"Partições sincronizadas: {len(adicionados)}")
        return

    sucesso = executar_lote(
        concursos=args.concursos,
        conferencia=args.conferencia,
        exigir_aprovacao=args.exigir_aprovacao,
        instance=inst,
    )
    if not sucesso:
        sys.exit(1)


if __name__ == "__main__":
    main()
