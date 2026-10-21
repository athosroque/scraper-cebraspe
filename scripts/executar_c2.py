"""CLI de execução do pipeline via Dagster (C2, D5a e D5b, KAN-31 e KAN-32).

Permite disparar a execução de lotes particionados por concurso diretamente
da linha de comando em modo conferência ou produção, com checagem obrigatória
do invariante do piloto (K22) antes e depois do lote e geração do relatório
em `inventario/lotes/lote_NN.md`.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dagster import DagsterInstance

from src.c2.assets import aprovacao_efetiva
from src.c2.checks import (
    ViolacaoInvariantePiloto,
    consultar_custo_openrouter,
    executar_consultas_runbook,
    obter_contagens_lote,
    obter_status_classificacao_lote,
    verificar_download_lote,
    verificar_invariante_piloto,
    verificar_portao_arvore,
    verificar_portao_classificacao,
    verificar_portao_edital,
    verificar_site_lote,
)
from src.c2.definitions import defs
from src.c2.partitions import (
    CONCURSOS_PARTITIONS_NAME,
    sincronizar_particoes_inventario,
)
from src.c2.relatorio import gerar_relatorio_lote
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
    numero_lote: int = 1,
    instance: DagsterInstance | None = None,
) -> bool:
    """Executa o lote de concursos selecionados via Dagster com guardas e relatório."""
    inst = instance or obter_instancia()
    alvos = concursos or CONCURSOS_PADRAO_C1

    logger.info(
        f"[C2] Iniciando execução do lote {numero_lote}: {alvos} "
        f"(modo conferência={conferencia}, exigir_aprovacao={exigir_aprovacao})"
    )

    # 1. Invariante do piloto antes do lote (K22)
    logger.info("[C2] Checando invariante do piloto antes da execução...")
    inv_antes = verificar_invariante_piloto(lancar_excecao=not conferencia)
    if not inv_antes.get("valido", True) and inv_antes.get("status") != "sem_banco":
        msg = f"[C2] Invariante do piloto violado antes do lote: {inv_antes.get('divergencias')}"
        if not conferencia:
            raise ViolacaoInvariantePiloto(detalhes=inv_antes, mensagem=msg)
        logger.warning(msg)

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
                        "exigir_aprovacao": aprovacao_efetiva(
                            conferencia, exigir_aprovacao
                        ),
                        "numero_lote": numero_lote,
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

    # 2. Invariante do piloto depois do lote (K22)
    logger.info("[C2] Checando invariante do piloto depois da execução...")
    inv_depois = verificar_invariante_piloto(lancar_excecao=not conferencia)
    if not inv_depois.get("valido", True) and inv_depois.get("status") != "sem_banco":
        msg = f"[C2] Invariante do piloto violado após o lote: {inv_depois.get('divergencias')}"
        if not conferencia:
            raise ViolacaoInvariantePiloto(detalhes=inv_depois, mensagem=msg)
        logger.warning(msg)

    # 3. Consolidação e geração do relatório do lote
    try:
        download_res = verificar_download_lote(alvos)
        portao_edital = {s: verificar_portao_edital(s) for s in alvos}
        consultas = executar_consultas_runbook(alvos)
        contagens_banco = obter_contagens_lote(alvos)
        classif_status = obter_status_classificacao_lote(alvos)
        portao_classif = verificar_portao_classificacao(alvos)
        portao_arvore = verificar_portao_arvore()
        site_res = verificar_site_lote(alvos)
        custo = consultar_custo_openrouter()

        banco_valido = bool(
            inv_depois.get("valido", True) and contagens_banco.get("valido", True)
        )
        checks_resultado: dict[str, Any] = {
            "download": download_res,
            "edital": {
                "status": "ok"
                if all(res[0] for res in portao_edital.values())
                else "pendente",
                "mensagem": "; ".join(
                    f"{s}: {res[1][:40]}" for s, res in portao_edital.items()
                ),
                "detalhes": portao_edital,
            },
            "portao_edital": portao_edital,
            "prova": {
                "status": consultas.get("status", "ok"),
                "mensagem": (
                    f"{len(consultas.get('consulta_a', []))} provas validadas, "
                    f"gabaritos na grade e {len(consultas.get('consulta_c', []))} discursivas com padrão"
                ),
                "detalhes": consultas,
            },
            "consultas_runbook": consultas,
            "banco": {
                "status": "ok" if banco_valido else "falha",
                "mensagem": contagens_banco.get("mensagem", "Contagens do lote"),
                "detalhes": contagens_banco,
            },
            "classificacao": {
                "status": "ok" if portao_classif[0] else "pendente",
                "mensagem": classif_status.get(
                    "mensagem", "Classificação das questões"
                ),
                "detalhes": classif_status,
            },
            "portao_classificacao": portao_classif,
            "portao_arvore": portao_arvore,
            "site": site_res,
            "invariante_piloto_antes": inv_antes,
            "invariante_piloto_depois": inv_depois,
        }
        relatorio_path = gerar_relatorio_lote(
            numero_lote=numero_lote,
            slugs=alvos,
            checks_resultado=checks_resultado,
            custo_info=custo,
            propostas_dispersao=portao_arvore[1],
        )
        logger.info(f"[C2] Relatório do Lote {numero_lote} gerado em: {relatorio_path}")
    except Exception as exc:
        logger.warning(f"[C2] Não foi possível consolidar relatório do lote: {exc}")

    return todos_ok


def main(args_list: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Executa o lote de concursos no Dagster (C2, D5b)",
        epilog=(
            "Guarda K22 ativa: o invariante do piloto (2.800 itens, 129 anuladas, "
            "hash 3257ba6b...) é verificado antes e depois do lote. Diferenças "
            "bloqueiam a execução."
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
        help="Executa em modo conferência (somente leitura/idempotente, sem chamadas externas)",
    )
    parser.add_argument(
        "--exigir-aprovacao",
        action="store_true",
        default=False,
        help=(
            "Bloqueia nos portões humanos (P3, P7, P9) se não houver aprovação formal. "
            "Fora do modo conferência (--no-conferencia) é sempre ativo"
        ),
    )
    parser.add_argument(
        "--lote",
        type=int,
        default=1,
        help="Número do lote (padrão: 1)",
    )
    parser.add_argument(
        "--sincronizar-apenas",
        action="store_true",
        help="Apenas sincroniza as partições do inventário com o banco do Dagster",
    )
    args = parser.parse_args(args_list)

    try:
        inst = obter_instancia()
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
        numero_lote=args.lote,
        instance=inst,
    )
    if not sucesso:
        sys.exit(1)


if __name__ == "__main__":
    main()
