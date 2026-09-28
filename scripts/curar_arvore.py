#!/usr/bin/env python3
"""CLI de curadoria da árvore mestre (Etapa 5B.1, ADR-030).

Toda decisão do dono passa por aqui (ou por `src.arvore`) e fica gravada em
`canonico/arvore.json`; o banco é recarregado a partir dele. Operação humana
sai `aprovado`/`ativo`. O item de edital é a chave natural unida por `|`
(`materia`, `materia|topico`, `materia|topico|subtopico`), como aparece no
`arvore.html`.

Uso:
    python -m scripts.curar_arvore --mapear 'materia|topico:NO1,NO2'
    python -m scripts.curar_arvore --desmapear 'materia|topico:NO1'
    python -m scripts.curar_arvore --aprovar 'materia|topico:NO1'
    python -m scripts.curar_arvore --rejeitar 'materia|topico:NO1'
    python -m scripts.curar_arvore --fundir ORIGEM:DESTINO
    python -m scripts.curar_arvore --mover NO:NOVO_PAI
    python -m scripts.curar_arvore --criar 'assunto:PAI=Nome'   # matéria: 'materia:=Nome'
    python -m scripts.curar_arvore --renomear 'NO=Novo nome'
    python -m scripts.curar_arvore --html
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_arvore import REVISAO_DIR_PADRAO, gerar_relatorio_arvore
from src import arvore


def _dividir(valor: str, separador: str, formato: str) -> tuple[str, str]:
    esquerda, sep, direita = (
        valor.rpartition(separador) if separador == ":" else valor.partition(separador)
    )
    if not sep or not esquerda.strip() or not direita.strip():
        raise arvore.ArvoreInvalida(f"Formato esperado: {formato} (recebido {valor!r})")
    return esquerda.strip(), direita.strip()


def _exigir_no(arv: arvore.ArvoreMestre, no_id: str) -> str:
    if no_id not in arv.nos:
        raise arvore.ArvoreInvalida(f"Nó {no_id} não existe")
    return no_id


def aplicar_operacoes(arv: arvore.ArvoreMestre, args: argparse.Namespace) -> list[str]:
    """Aplica as operações pedidas e devolve uma linha de log por operação."""
    feitas = []
    if args.criar:
        nivel_pai, nome = _dividir(args.criar, "=", "NIVEL:PAI=Nome")
        nivel, _, pai = nivel_pai.partition(":")
        if nivel not in arvore.NIVEIS:
            raise arvore.ArvoreInvalida(
                f"Nível {nivel!r} inválido (use {', '.join(arvore.NIVEIS)})"
            )
        no_id = arvore.criar_no(arv, nivel, nome, pai.strip() or None)
        feitas.append(f"criado {no_id} ({nivel}) {nome!r}")
    if args.renomear:
        no_id, nome = _dividir(args.renomear, "=", "NO=Nome")
        arvore.renomear_no(arv, _exigir_no(arv, no_id), nome)
        feitas.append(f"renomeado {no_id} → {nome!r}")
    if args.mover:
        no_id, pai = _dividir(args.mover, ":", "NO:PAI")
        arvore.mover_no(arv, _exigir_no(arv, no_id), _exigir_no(arv, pai))
        feitas.append(f"movido {no_id} → pai {pai}")
    if args.fundir:
        origem, destino = _dividir(args.fundir, ":", "ORIGEM:DESTINO")
        arvore.fundir_nos(arv, _exigir_no(arv, origem), _exigir_no(arv, destino))
        feitas.append(f"fundido {origem} → {destino}")
    if args.mapear:
        item, nos = _dividir(args.mapear, ":", "ITEM:NO1,NO2")
        ids = [_exigir_no(arv, n.strip()) for n in nos.split(",") if n.strip()]
        arvore.mapear(arv, item, ids, origem="humano", status="aprovado")
        feitas.append(f"mapeado {item!r} → {', '.join(ids)}")
    for acao, funcao in (
        ("desmapear", arvore.desmapear),
        ("aprovar", arvore.aprovar),
        ("rejeitar", arvore.rejeitar),
    ):
        valor = getattr(args, acao)
        if valor:
            item, no_id = _dividir(valor, ":", "ITEM:NO")
            funcao(arv, item, no_id)
            feitas.append(f"{acao} {item!r} × {no_id}")
    return feitas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curadoria da árvore mestre (ADR-030)")
    parser.add_argument(
        "--mapear", help="ITEM:NO1,NO2 — aponta o item para os nós (aprovado)"
    )
    parser.add_argument("--desmapear", help="ITEM:NO — remove o apontamento")
    parser.add_argument("--aprovar", help="ITEM:NO — aprova um apontamento proposto")
    parser.add_argument("--rejeitar", help="ITEM:NO — rejeita um apontamento proposto")
    parser.add_argument("--fundir", help="ORIGEM:DESTINO — funde nós do mesmo nível")
    parser.add_argument("--mover", help="NO:PAI — troca o pai (nível de cima)")
    parser.add_argument(
        "--criar", help="NIVEL:PAI=Nome — cria nó (matéria: 'materia:=Nome')"
    )
    parser.add_argument("--renomear", help="NO=Nome — renomeia o nó")
    parser.add_argument("--html", action="store_true", help="Regenera o arvore.html")
    parser.add_argument(
        "--arvore", type=Path, default=arvore.ARVORE_PADRAO, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--revisao-dir", type=Path, default=REVISAO_DIR_PADRAO, help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)

    operacoes = (
        "mapear",
        "desmapear",
        "aprovar",
        "rejeitar",
        "fundir",
        "mover",
        "criar",
        "renomear",
    )
    if not any(getattr(args, op) for op in operacoes) and not args.html:
        parser.print_help()
        return 2

    if any(getattr(args, op) for op in operacoes):
        arv = arvore.carregar(args.arvore)
        try:
            feitas = aplicar_operacoes(arv, args)
        except arvore.ArvoreInvalida as e:
            # Nada é gravado: as operações da mesma chamada valem juntas ou nenhuma.
            print(f"Erro: {e}", file=sys.stderr)
            return 1
        arvore.salvar(arv, args.arvore)
        for linha in feitas:
            print(linha)

    gerar_relatorio_arvore(args.revisao_dir, args.arvore)
    return 0


if __name__ == "__main__":
    sys.exit(main())
