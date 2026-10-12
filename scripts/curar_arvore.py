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
from src import arvore, canonico


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


def _formatar_detalhe_proposta(arv: arvore.ArvoreMestre, p: arvore.Proposta) -> str:
    if p.tipo == "fundir":
        orig = arv.nos.get(p.args["origem"])
        dest = arv.nos.get(p.args["destino"])
        orig_s = f"{orig.nome} ({p.args['origem']})" if orig else p.args["origem"]
        dest_s = f"{dest.nome} ({p.args['destino']})" if dest else p.args["destino"]
        return f"{orig_s} → {dest_s}"
    elif p.tipo == "mover":
        no = arv.nos.get(p.args["no"])
        pai = arv.nos.get(p.args["pai"])
        no_s = f"{no.nome} ({p.args['no']})" if no else p.args["no"]
        pai_s = f"{pai.nome} ({p.args['pai']})" if pai else p.args["pai"]
        return f"{no_s} → pai {pai_s}"
    elif p.tipo == "criar":
        pai = arv.nos.get(p.args.get("pai")) if p.args.get("pai") else None
        pai_s = (
            f"{pai.nome} ({p.args['pai']})" if pai else (p.args.get("pai") or "raiz")
        )
        return f"({p.args['nivel']}) {p.args['nome']!r} sob {pai_s}"
    elif p.tipo == "remapear":
        de_no = arv.nos.get(p.args["de"])
        de_s = f"{de_no.nome} ({p.args['de']})" if de_no else p.args["de"]
        destinos = (
            p.args["para"] if isinstance(p.args["para"], list) else [p.args["para"]]
        )
        para_s = ", ".join(
            f"{arv.nos[d].nome} ({d})" if d in arv.nos else d for d in destinos
        )
        return f"{p.args['item']!r}: {de_s} → {para_s}"
    elif p.tipo == "aposentar":
        no_id = p.args.get("no") or p.args.get("no_id", "")
        no = arv.nos.get(no_id)
        no_s = f"{no.nome} ({no_id})" if no else no_id
        return f"aposentar {no_s}"
    return str(p.args)


ORDEM_TIPOS = {
    "criar": 1,
    "mover": 2,
    "fundir": 3,
    "remapear": 4,
    "aposentar": 5,
}


def _chave_ordem_proposta(p: arvore.Proposta) -> tuple[int, str]:
    return (ORDEM_TIPOS.get(p.tipo, 99), p.id)


def listar_propostas(
    arv: arvore.ArvoreMestre, filtro_materia: str | None = None
) -> list[str]:
    filtro = filtro_materia.strip() if filtro_materia else None
    pendentes = [
        p
        for p in arv.propostas.values()
        if p.status == "proposto"
        and (
            not filtro
            or filtro == p.materia
            or filtro.lower() == getattr(arv.nos.get(p.materia), "nome", "").lower()
            or (
                p.materia in arv.nos
                and canonico.chave_regra(filtro).chave
                == canonico.chave_regra(arv.nos[p.materia].nome).chave
            )
        )
    ]
    if not pendentes:
        return ["Nenhuma proposta pendente."]

    linhas = []
    por_materia: dict[str, list[arvore.Proposta]] = {}
    for p in pendentes:
        por_materia.setdefault(p.materia, []).append(p)

    for m_id, props in sorted(por_materia.items()):
        m_no = arv.nos.get(m_id)
        m_nome = m_no.nome if m_no else (m_id or "Sem matéria")
        props_ordenadas = sorted(props, key=_chave_ordem_proposta)
        linhas.append(f"=== Matéria: {m_nome} ({m_id}) ===")
        if len(props_ordenadas) > 1:
            todos_ids = ",".join(p.id for p in props_ordenadas)
            linhas.append(
                f"  Aprovar todas da matéria: python -m scripts.curar_arvore --aprovar-proposta {todos_ids}"
            )
        for p in props_ordenadas:
            detalhe = _formatar_detalhe_proposta(arv, p)
            linhas.append(f"[{p.id}] {p.tipo.upper()} ({p.origem}): {detalhe}")
            if p.justificativa:
                linhas.append(f"  Justificativa: {p.justificativa}")
            linhas.append(
                f"  Aprovar: python -m scripts.curar_arvore --aprovar-proposta {p.id}"
            )
    return linhas


def aplicar_operacoes(arv: arvore.ArvoreMestre, args: argparse.Namespace) -> list[str]:
    """Aplica as operações pedidas e devolve uma linha de log por operação."""
    feitas = []
    if args.criar is not None:
        nivel_pai, nome = _dividir(args.criar, "=", "NIVEL:PAI=Nome")
        nivel, _, pai = nivel_pai.partition(":")
        if nivel not in arvore.NIVEIS:
            raise arvore.ArvoreInvalida(
                f"Nível {nivel!r} inválido (use {', '.join(arvore.NIVEIS)})"
            )
        no_id = arvore.criar_no(arv, nivel, nome, pai.strip() or None)
        feitas.append(f"criado {no_id} ({nivel}) {nome!r}")
    if args.renomear is not None:
        no_id, nome = _dividir(args.renomear, "=", "NO=Nome")
        arvore.renomear_no(arv, _exigir_no(arv, no_id), nome)
        feitas.append(f"renomeado {no_id} → {nome!r}")
    if args.mover is not None:
        no_id, pai = _dividir(args.mover, ":", "NO:PAI")
        arvore.mover_no(arv, _exigir_no(arv, no_id), _exigir_no(arv, pai))
        feitas.append(f"movido {no_id} → pai {pai}")
    if args.fundir is not None:
        origem, destino = _dividir(args.fundir, ":", "ORIGEM:DESTINO")
        arvore.fundir_nos(arv, _exigir_no(arv, origem), _exigir_no(arv, destino))
        feitas.append(f"fundido {origem} → {destino}")
    if args.mapear is not None:
        item, nos = _dividir(args.mapear, ":", "ITEM:NO1,NO2")
        ids = [_exigir_no(arv, n.strip()) for n in nos.split(",") if n.strip()]
        arvore.mapear(arv, item, ids, origem="humano", status="aprovado")
        feitas.append(f"mapeado {item!r} → {', '.join(ids)}")
    if args.aprovar_proposta is not None:
        ids = [p.strip() for p in args.aprovar_proposta.split(",") if p.strip()]
        if not ids:
            raise arvore.ArvoreInvalida("Nenhuma proposta informada para aprovação")
        ids_aprovados = arvore.aprovar_propostas(arv, ids)
        feitas.append(f"propostas aprovadas: {', '.join(ids_aprovados)}")
    if args.rejeitar_proposta is not None:
        ids = [p.strip() for p in args.rejeitar_proposta.split(",") if p.strip()]
        if not ids:
            raise arvore.ArvoreInvalida("Nenhuma proposta informada para rejeição")
        ids_unicos = list(dict.fromkeys(ids))
        for pid in ids_unicos:
            if pid not in arv.propostas:
                raise arvore.ArvoreInvalida(f"Proposta {pid} não existe")
            if arv.propostas[pid].status == "aprovado":
                raise arvore.ArvoreInvalida(
                    f"Proposta {pid} já foi aprovada e não pode ser rejeitada"
                )
        for pid in ids_unicos:
            arvore.rejeitar_proposta(arv, pid)
        feitas.append(f"propostas rejeitadas: {', '.join(ids_unicos)}")
    for acao, funcao in (
        ("desmapear", arvore.desmapear),
        ("aprovar", arvore.aprovar),
        ("rejeitar", arvore.rejeitar),
    ):
        valor = getattr(args, acao)
        if valor is not None:
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
    parser.add_argument("--fundir", help="ORIGEM:DESTINO — funde nós (nível diferente só se a origem não tem filhos ativos)")
    parser.add_argument("--mover", help="NO:PAI — troca o pai (nível de cima)")
    parser.add_argument(
        "--criar", help="NIVEL:PAI=Nome — cria nó (matéria: 'materia:=Nome')"
    )
    parser.add_argument("--renomear", help="NO=Nome — renomeia o nó")
    parser.add_argument(
        "--aprovar-proposta",
        help="P1,P2... — aprova propostas em lote (tudo ou nada)",
    )
    parser.add_argument(
        "--rejeitar-proposta",
        help="P1,P2... — rejeita propostas",
    )
    parser.add_argument(
        "--propostas",
        nargs="?",
        const="",
        metavar="MATERIA",
        help="Lista propostas pendentes no terminal (opcional: [M-..])",
    )
    parser.add_argument("--html", action="store_true", help="Regenera o arvore.html")
    parser.add_argument(
        "--arvore", type=Path, default=arvore.ARVORE_PADRAO, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--revisao-dir", type=Path, default=REVISAO_DIR_PADRAO, help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)

    if args.propostas is not None:
        arv = arvore.carregar(args.arvore)
        filtro = args.propostas.strip() or None
        for linha in listar_propostas(arv, filtro):
            print(linha)
        return 0

    operacoes = (
        "mapear",
        "desmapear",
        "aprovar",
        "rejeitar",
        "fundir",
        "mover",
        "criar",
        "renomear",
        "aprovar_proposta",
        "rejeitar_proposta",
    )
    if not any(getattr(args, op) is not None for op in operacoes) and not args.html:
        parser.print_help()
        return 2

    if any(getattr(args, op) is not None for op in operacoes):
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
