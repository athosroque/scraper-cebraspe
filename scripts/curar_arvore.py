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
    python -m scripts.curar_arvore --criar 'assunto:PAI=Nome' --permitir-norma-repetida
    python -m scripts.curar_arvore --renomear 'NO=Novo nome'
    python -m scripts.curar_arvore --rebaixar MATERIA:ASSUNTO_DESTINO [--simular]
    python -m scripts.curar_arvore --lote canonico/lotes/arquivo.json [--simular]
    python -m scripts.curar_arvore --html
"""

import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_arvore import REVISAO_DIR_PADRAO, gerar_relatorio_arvore
from src import arvore, canonico, classificacao


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
        existentes = (
            [] if args.permitir_norma_repetida else arvore.nos_da_mesma_norma(arv, nome)
        )
        if existentes:
            detalhes = "; ".join(
                f"{i} ({arvore._caminho_no(arv, i)})" for i in existentes
            )
            raise arvore.ArvoreInvalida(
                f"[NORMA_JA_EXISTE] {nome!r} já existe como norma em {detalhes}. "
                f"Use --mapear ITEM:{existentes[0]} para apontar o item ao nó "
                "existente, ou --permitir-norma-repetida se for outro conceito"
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
    if args.rebaixar is not None:
        materia, destino = _dividir(args.rebaixar, ":", "MATERIA:DESTINO")
        arvore.rebaixar_materia(arv, _exigir_no(arv, materia), _exigir_no(arv, destino))
        feitas.append(f"rebaixado {materia} → {destino}")
    if args.lote is not None:
        operacoes = json.loads(args.lote.read_text(encoding="utf-8"))["operacoes"]
        feitas.extend(arvore.aplicar_lote(arv, operacoes))
    if args.fundir is not None:
        origem, destino = _dividir(args.fundir, ":", "ORIGEM:DESTINO")
        arvore.fundir_nos(arv, _exigir_no(arv, origem), _exigir_no(arv, destino))
        feitas.append(f"fundido {origem} → {destino}")
    if args.mapear is not None:
        item, nos = _dividir(args.mapear, ":", "ITEM:NO1,NO2")
        ids = [_exigir_no(arv, n.strip()) for n in nos.split(",") if n.strip()]
        arvore.mapear(arv, item, ids, origem="humano", status="aprovado")
        feitas.append(f"mapeado {item!r} → {', '.join(ids)}")
        alvos = {arvore.resolver_no(arv, n) for n in ids}
        for alvo in sorted(alvos):
            no = arv.nos[alvo]
            repetidos = arvore.nos_da_mesma_norma(arv, no.nome, ignorar=alvos)
            if repetidos:
                detalhes = "; ".join(
                    f"{i} ({arvore._caminho_no(arv, i)})" for i in repetidos
                )
                feitas.append(
                    f"[AVISO NORMA_REPETIDA] {no.nome!r} ({alvo}) também existe em "
                    f"{detalhes}: funda com --fundir se for o mesmo conceito"
                )
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


def chaves_por_no(arv: arvore.ArvoreMestre, path: Path) -> dict[str, set[str]]:
    """Chaves das questões por nó efetivo (pelo `fundido_em`), sem as rejeitadas."""
    if not path.exists():
        return {}
    por_no: dict[str, set[str]] = {}
    for chave, reg in classificacao.carregar(path).registros.items():
        for a in reg.apontamentos:
            if a.status != "rejeitado":
                por_no.setdefault(arvore.resolver_no(arv, a.no_id), set()).add(chave)
    return por_no


def _questoes_por_no(arv: arvore.ArvoreMestre, path: Path) -> dict[str, int]:
    return {no_id: len(c) for no_id, c in chaves_por_no(arv, path).items()}


def resumir_efeito(
    antes: arvore.ArvoreMestre, depois: arvore.ArvoreMestre, path_classificacao: Path
) -> list[str]:
    """Prévia do `--simular`: disciplinas que saem/entram e fusões com questão."""

    def materias(arv: arvore.ArvoreMestre) -> dict[str, str]:
        return {
            n.id: n.nome
            for n in arv.nos.values()
            if n.nivel == "materia" and n.status == "ativo"
        }

    m_antes, m_depois = materias(antes), materias(depois)
    linhas = [f"Disciplinas ativas: {len(m_antes)} → {len(m_depois)}"]
    for no_id in sorted(set(m_antes) - set(m_depois), key=m_antes.get):
        destino = arvore.resolver_no(depois, no_id)
        linhas.append(
            f"  sai   {no_id} {m_antes[no_id]} → {arvore._caminho_no(depois, destino)}"
        )
    for no_id in sorted(set(m_depois) - set(m_antes), key=m_depois.get):
        linhas.append(f"  entra {no_id} {m_depois[no_id]}")
    for no_id in sorted(set(m_antes) & set(m_depois)):
        if m_antes[no_id] != m_depois[no_id]:
            linhas.append(f"  nome  {no_id} {m_antes[no_id]} → {m_depois[no_id]}")

    questoes = _questoes_por_no(antes, path_classificacao)
    fundidos = [
        n
        for n in antes.nos.values()
        if n.status == "ativo"
        and n.nivel != "materia"
        and depois.nos[n.id].status == "fundido"
        and questoes.get(n.id)
    ]
    linhas.append(f"Nós com questão que fundem (perdem detalhe): {len(fundidos)}")
    for n in sorted(fundidos, key=lambda n: -questoes[n.id]):
        destino = arvore.resolver_no(depois, n.id)
        linhas.append(
            f"  {n.id} {n.nome!r} ({questoes[n.id]} q) → "
            f"{destino} {arvore._caminho_no(depois, destino)}"
        )
    return linhas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curadoria da árvore mestre (ADR-030)")
    parser.add_argument(
        "--mapear",
        help="ITEM:NO1,NO2 — aponta o item para os nós (aprovado); avisa se o nó "
        "é uma norma que já existe em outro lugar (aviso, não bloqueia)",
    )
    parser.add_argument("--desmapear", help="ITEM:NO — remove o apontamento")
    parser.add_argument("--aprovar", help="ITEM:NO — aprova um apontamento proposto")
    parser.add_argument("--rejeitar", help="ITEM:NO — rejeita um apontamento proposto")
    parser.add_argument(
        "--fundir",
        help="ORIGEM:DESTINO — funde nós (nível diferente só se a origem não tem filhos ativos)",
    )
    parser.add_argument("--mover", help="NO:PAI — troca o pai (nível de cima)")
    parser.add_argument(
        "--criar",
        help="NIVEL:PAI=Nome — cria nó (matéria: 'materia:=Nome'); recusa norma "
        "que já existe em outro nó ([NORMA_JA_EXISTE])",
    )
    parser.add_argument(
        "--permitir-norma-repetida",
        action="store_true",
        help="com --criar: desliga a trava de norma repetida (outro conceito de mesmo nome)",
    )
    parser.add_argument("--renomear", help="NO=Nome — renomeia o nó")
    parser.add_argument(
        "--rebaixar",
        help="MATERIA:ASSUNTO — a matéria entra no assunto; os assuntos dela viram "
        "subassuntos e os subassuntos dela fundem no pai (Etapa 5B.3)",
    )
    parser.add_argument(
        "--lote",
        type=Path,
        help="JSON com {'operacoes': [{'tipo', 'args'}]} aplicado em ordem, tudo ou nada",
    )
    parser.add_argument(
        "--simular",
        action="store_true",
        help="mostra o efeito (disciplinas e nós fundidos com questão) sem gravar",
    )
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
    parser.add_argument(
        "--classificacao",
        type=Path,
        default=classificacao.CLASSIFICACAO_PADRAO,
        help=argparse.SUPPRESS,
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
        "rebaixar",
        "lote",
        "aprovar_proposta",
        "rejeitar_proposta",
    )
    if not any(getattr(args, op) is not None for op in operacoes) and not args.html:
        parser.print_help()
        return 2

    if any(getattr(args, op) is not None for op in operacoes):
        arv = arvore.carregar(args.arvore)
        antes = copy.deepcopy(arv)
        try:
            feitas = aplicar_operacoes(arv, args)
        except arvore.ArvoreInvalida as e:
            # Nada é gravado: as operações da mesma chamada valem juntas ou nenhuma.
            print(f"Erro: {e}", file=sys.stderr)
            return 1
        for linha in feitas:
            print(linha)
        if args.simular:
            for linha in resumir_efeito(antes, arv, args.classificacao):
                print(linha)
            print("Simulação: nada foi gravado.")
            return 0
        arvore.salvar(arv, args.arvore)

    gerar_relatorio_arvore(args.revisao_dir, args.arvore)
    return 0


if __name__ == "__main__":
    sys.exit(main())
