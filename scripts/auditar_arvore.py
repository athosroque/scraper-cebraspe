#!/usr/bin/env python3
"""Auditoria da hierarquia da árvore mestre (Etapa 5B.3, KAN-78).

Mostra cada disciplina (nó matéria ativo) com questões e assuntos/subassuntos e
confere a árvore contra a lista fechada `canonico/disciplinas.json`.

Erro (sai com 1): matéria ativa fora da lista, disciplina da lista que não está
ativa, nome diferente do da lista, ou nó ativo com pai de nível errado.
Aviso (não falha): a mesma norma em mais de um nó ativo.

Uso:
    python -m scripts.auditar_arvore
    python -m scripts.auditar_arvore --normas   # lista os grupos de norma repetida
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.curar_arvore import chaves_por_no
from src import arvore, classificacao

DISCIPLINAS_PADRAO = arvore.PROJETO_DIR / "canonico" / "disciplinas.json"


def carregar_disciplinas(path: Path = DISCIPLINAS_PADRAO) -> dict[str, str]:
    dados = json.loads(path.read_text(encoding="utf-8"))
    return {d["id"]: d["nome"] for d in dados["disciplinas"]}


def _ativos(arv: arvore.ArvoreMestre) -> list[arvore.NoArvore]:
    return [n for n in arv.nos.values() if n.status == "ativo"]


def tabela_disciplinas(
    arv: arvore.ArvoreMestre, chaves: dict[str, set[str]]
) -> list[tuple[str, str, int, int, int]]:
    """(id, nome, questões distintas, assuntos, subassuntos) por matéria ativa."""
    linhas = {n.id: [n.nome, 0, 0, 0] for n in _ativos(arv) if n.nivel == "materia"}
    por_materia: dict[str, set[str]] = {}
    for no_id, c in chaves.items():
        por_materia.setdefault(arvore.materia_do_no(arv, no_id), set()).update(c)
    for materia, c in por_materia.items():
        if materia in linhas:
            linhas[materia][1] = len(c)
    for n in _ativos(arv):
        if n.nivel == "materia":
            continue
        materia = arvore.materia_do_no(arv, n.id)
        if materia in linhas:
            linhas[materia][2 if n.nivel == "assunto" else 3] += 1
    return sorted(((i, *v) for i, v in linhas.items()), key=lambda t: t[1].lower())


def erros_hierarquia(
    arv: arvore.ArvoreMestre, disciplinas: dict[str, str]
) -> list[str]:
    erros = []
    materias = {n.id: n.nome for n in _ativos(arv) if n.nivel == "materia"}
    for no_id in sorted(set(materias) - set(disciplinas)):
        erros.append(f"matéria fora da lista fechada: {no_id} {materias[no_id]!r}")
    for no_id in sorted(set(disciplinas) - set(materias)):
        erros.append(
            f"disciplina da lista não está ativa: {no_id} {disciplinas[no_id]!r}"
        )
    for no_id in sorted(set(disciplinas) & set(materias)):
        if materias[no_id] != disciplinas[no_id]:
            erros.append(
                f"nome difere da lista: {no_id} {materias[no_id]!r} "
                f"(lista: {disciplinas[no_id]!r})"
            )
    for n in sorted(_ativos(arv), key=lambda n: n.id):
        if n.nivel == "materia":
            continue
        pai = arv.nos.get(arvore.resolver_no(arv, n.pai)) if n.pai else None
        if not pai or pai.status != "ativo" or pai.nivel != arvore.NIVEL_PAI[n.nivel]:
            erros.append(
                f"{n.id} ({n.nivel}) com pai inválido: "
                f"{pai.id + ' (' + pai.nivel + ', ' + pai.status + ')' if pai else n.pai}"
            )
    return erros


def normas_repetidas(arv: arvore.ArvoreMestre) -> list[list[str]]:
    """Grupos de nós ativos cujo nome é a mesma norma (8.112, 9.784...)."""
    grupos: dict[tuple, list[str]] = {}
    for n in _ativos(arv):
        if n.nivel != "materia" and arvore._nome_e_a_norma(n.nome):
            chave = tuple(sorted(arvore._normas_do_nome(n.nome)))
            grupos.setdefault(chave, []).append(n.id)
    return sorted(sorted(ids) for ids in grupos.values() if len(ids) > 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auditoria da hierarquia da árvore")
    parser.add_argument(
        "--normas", action="store_true", help="lista os grupos de norma repetida"
    )
    parser.add_argument(
        "--arvore", type=Path, default=arvore.ARVORE_PADRAO, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--disciplinas", type=Path, default=DISCIPLINAS_PADRAO, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--classificacao",
        type=Path,
        default=classificacao.CLASSIFICACAO_PADRAO,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    arv = arvore.carregar(args.arvore)
    disciplinas = carregar_disciplinas(args.disciplinas)
    chaves = chaves_por_no(arv, args.classificacao)

    print("| Disciplina | id | q | A/S |")
    print("|---|---|---|---|")
    for no_id, nome, q, a, s in tabela_disciplinas(arv, chaves):
        print(f"| {nome} | {no_id} | {q} | {a}/{s} |")

    repetidas = normas_repetidas(arv)
    print(f"\nAviso: {len(repetidas)} normas em mais de um nó ativo")
    if args.normas:
        for ids in repetidas:
            print("  " + "; ".join(f"{i} ({arvore._caminho_no(arv, i)})" for i in ids))

    erros = erros_hierarquia(arv, disciplinas)
    for erro in erros:
        print(f"ERRO: {erro}", file=sys.stderr)
    print(f"\n{len(erros)} erro(s) de hierarquia")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
