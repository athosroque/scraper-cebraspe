"""Aplica as decisões humanas sobre os sinônimos canônicos (Etapa 5B, ADR-029).

As decisões ficam gravadas em `canonico/sinonimos.json` (versionado) e nunca
são desfeitas pelas regras numa reexecução. Ordem de aplicação: `--mover`,
`--renomear`, `--rejeitar`, `--aprovar` (mover uma entrada para uma proposta
e aprovar a proposta cabe numa chamada só).

Depois de aplicar, reaplica as regras (grupos do nível de baixo que passam a
ter o mesmo escopo são juntados), regenera `relatorio/sinonimos.html` e
grava o banco (best-effort, como no ADR-019).

Uso:
    python -m scripts.aprovar_sinonimos --aprovar ML-xxxx,AL-yyyy --rejeitar SL-zzzz
    python -m scripts.aprovar_sinonimos --mover A-entrada:AL-grupo --mover S-entrada:NOVO
    python -m scripts.aprovar_sinonimos --renomear "ML-xxxx=Administração Financeira e Orçamentária"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_sinonimos import gerar_relatorio_sinonimos
from src import canonico
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"


def _ids(valores: list[str] | None) -> list[str]:
    return [i.strip() for v in valores or [] for i in v.split(",") if i.strip()]


def aplicar_decisoes(
    estado: dict,
    *,
    aprovar: list[str] = (),
    rejeitar: list[str] = (),
    mover: list[str] = (),
    renomear: list[str] = (),
) -> list[str]:
    """Aplica as decisões e devolve um resumo legível. Levanta
    `canonico.DecisaoInvalida` na primeira decisão inválida (nada é salvo)."""
    feitas = []
    for par in mover:
        if ":" not in par:
            raise canonico.DecisaoInvalida(
                f"--mover espera ENTRADA:GRUPO, recebeu {par!r}"
            )
        entrada, destino = par.split(":", 1)
        gid = canonico.mover(estado, entrada.strip(), destino.strip())
        feitas.append(f"movida {entrada} → {gid}")
    for par in renomear:
        if "=" not in par:
            raise canonico.DecisaoInvalida(
                f"--renomear espera GRUPO=Nome, recebeu {par!r}"
            )
        gid, nome = par.split("=", 1)
        canonico.renomear(estado, gid.strip(), nome)
        feitas.append(f"renomeado {gid.strip()} → {nome.strip()!r}")
    for gid in rejeitar:
        canonico.rejeitar(estado, gid)
        feitas.append(f"rejeitado {gid}")
    for gid in aprovar:
        canonico.aprovar(estado, gid)
        feitas.append(f"aprovado {gid}")
    return feitas


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--aprovar", action="append", help="IDs de grupo, separados por vírgula"
    )
    parser.add_argument(
        "--rejeitar", action="append", help="IDs de grupo, separados por vírgula"
    )
    parser.add_argument(
        "--mover", action="append", default=[], help="ENTRADA:GRUPO (ou ENTRADA:NOVO)"
    )
    parser.add_argument(
        "--renomear", action="append", default=[], help="GRUPO=Nome canônico"
    )
    parser.add_argument("--revisao-dir", type=Path, default=REVISAO_DIR_PADRAO)
    parser.add_argument(
        "--sem-banco", action="store_true", help="não grava o Postgres ao final"
    )
    args = parser.parse_args(argv)

    path = canonico.caminho_sinonimos(args.revisao_dir)
    estado = canonico.carregar(path)
    try:
        feitas = aplicar_decisoes(
            estado,
            aprovar=_ids(args.aprovar),
            rejeitar=_ids(args.rejeitar),
            mover=args.mover,
            renomear=args.renomear,
        )
    except canonico.DecisaoInvalida as e:
        logger.error(f"[CANONICO] Decisão inválida, nada foi salvo: {e}")
        sys.exit(1)
    canonico.aplicar_regras(estado, canonico.coletar_nomes(args.revisao_dir))
    canonico.salvar(estado, path)
    for linha in feitas:
        logger.info(f"[CANONICO] {linha}")
    gerar_relatorio_sinonimos(args.revisao_dir, path)

    if not args.sem_banco:
        from src.stats_writer import gravar_estatisticas

        try:
            gravar_estatisticas(args.revisao_dir)
        except Exception as e:  # noqa: BLE001 — banco regenerável, ver ADR-019
            logger.warning(
                f"[STATS] Não foi possível gravar no banco de estatísticas: {e}"
            )


if __name__ == "__main__":
    main()
