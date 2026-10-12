#!/usr/bin/env python3
"""Detecta conceitos espalhados em pais diferentes da árvore mestre (KAN-64, Fase 1).

`arvore.detectar_homonimos` só compara irmãos. Aqui o mesmo conceito sob pais
diferentes (LGPD, LRF, Balanced Scorecard, suprimento de fundos...) divide a
incidência e o filtro do site. A detecção é por regra, sem LLM
(`arvore.detectar_dispersos`).

Uso:
    python -m scripts.detectar_dispersao_arvore --dry-run   # padrão: só relatório
    python -m scripts.detectar_dispersao_arvore --propor    # grava as propostas

Só os grupos de confiança ALTA viram proposta (`fundir`, origem "regra",
status proposto); os de confiança média ficam só no relatório. Quem aprova é o
dono (`curar_arvore`/`arvore.aprovar_propostas`), em lote. Este script nunca
aprova nem muda o status de nó ou apontamento.

O destino é o nó com mais questões (`questao_no`, aprovadas, por nó resolvido),
depois mais itens de edital aprovados, depois o nível mais alto
(assunto > subassunto) e o menor ID. Todo membro funde no destino: nó de nível
diferente só quando não tem filhos ativos (regra de `fundir_nos`, KAN-64 e
ADR-030). Nó de nível diferente com filhos não recebe proposta (`sem_operacao`,
decisão do dono).
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import arvore, stats_writer  # noqa: E402

logger = logging.getLogger(__name__)

PROJETO_DIR = Path(__file__).resolve().parent.parent
RELATORIO_PADRAO = (
    PROJETO_DIR / "docs" / "relatorios" / "dispersao_arvore_2026-10-12.md"
)
# Propostas NOVAS por execução; mais que isso indica critério frouxo: o script recusa gravar.
LIMITE_PROPOSTAS = 150

MOTIVOS = {
    "mesma_norma": "cita a mesma norma",
    "mesmo_nome": "mesmo nome sob pais diferentes",
    "nome_contido": "nome contido no de outro nó",
}


def questoes_por_no(conn) -> dict[str, int]:
    """Questões distintas aprovadas por `no_id` (somente leitura)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT no_id, count(DISTINCT questao_id) FROM questao_no "
            "WHERE status = 'aprovado' GROUP BY no_id"
        )
        return {no_id: int(n) for no_id, n in cur.fetchall()}


def _justificativa(grupo: dict, arv: arvore.ArvoreMestre, op: dict) -> str:
    origem, destino = arv.nos[op["origem"]], arv.nos[op["destino"]]
    return (
        f"Conceito disperso ({MOTIVOS[grupo['motivo']]}, confiança "
        f"{grupo['confianca']}, chave {grupo['chave']!r}): "
        f"{origem.nome!r} ({origem.id}) junto de {destino.nome!r} ({destino.id}), "
        f"{grupo['questoes'][destino.id]} questão(ões) no destino e "
        f"{grupo['questoes'][origem.id]} na origem"
    )


def propor_grupos(
    arv: arvore.ArvoreMestre, grupos: list[dict]
) -> tuple[dict[tuple[str, str], str], list[str]]:
    """Grava `fundir` para cada operação dos grupos de confiança alta.

    Devolve ({(origem, destino): id da proposta}, erros). Um nó entra uma vez
    só como origem; operação inválida na simulação do `propor` vira erro
    no relatório e nada é gravado para ela.
    """
    ids: dict[tuple[str, str], str] = {}
    erros: list[str] = []
    origens: set[str] = set()
    for grupo in grupos:
        if grupo["confianca"] != "alta":
            continue
        for op in grupo["operacoes"]:
            if op["origem"] in origens:
                continue
            try:
                ids[(op["origem"], op["destino"])] = arvore.propor(
                    arv,
                    tipo="fundir",
                    args=op,
                    origem="regra",
                    justificativa=_justificativa(grupo, arv, op),
                )
                origens.add(op["origem"])
            except arvore.ArvoreInvalida as e:
                erros.append(f"{op['origem']} → {op['destino']}: {e}")
    return ids, erros


def _linha_no(grupo: dict, arv: arvore.ArvoreMestre, no_id: str) -> str:
    marca = " **(destino)**" if no_id == grupo["destino"] else ""
    return (
        f"  - `{no_id}` [{arv.nos[no_id].nivel}] {grupo['caminhos'][no_id]} "
        f"— {grupo['questoes'][no_id]} questão(ões), "
        f"{grupo['itens'][no_id]} item(ns) de edital{marca}"
    )


def gerar_relatorio(
    arv: arvore.ArvoreMestre,
    grupos: list[dict],
    propostas: dict[tuple[str, str], str],
    erros: list[str],
    gravou: bool,
) -> str:
    cont: dict[tuple[str, str], int] = {}
    for g in grupos:
        chave = (g["motivo"], g["confianca"])
        cont[chave] = cont.get(chave, 0) + 1
    linhas = [
        f"# Conceitos dispersos na árvore mestre — {date.today().isoformat()}",
        "",
        "KAN-64, Fase 1. Detecção por regra (`arvore.detectar_dispersos`), sem LLM. "
        + (
            "As propostas abaixo foram GRAVADAS como `proposto` na árvore mestre."
            if gravou
            else "Execução em `--dry-run`: nada foi gravado; os IDs de proposta são os que "
            "`--propor` gravaria."
        )
        + " Aprovação é do dono, em lote.",
        "",
        "## Resumo",
        "",
        "| Motivo | Confiança | Grupos |",
        "|---|---|---|",
    ]
    for (motivo, conf), n in sorted(cont.items()):
        linhas.append(f"| `{motivo}` | {conf} | {n} |")
    sem_op = sum(1 for g in grupos if g["confianca"] == "alta" and not g["operacoes"])
    linhas += [
        "",
        f"- Propostas `fundir` {'gravadas' if gravou else 'previstas'}: {len(propostas)} "
        f"(só confiança alta). Grupos de confiança alta sem operação possível: {sem_op}.",
        f"- Erros ao propor: {len(erros)}.",
        "",
        "## Critérios",
        "",
        "- **Operação.** Todo membro funde no destino do grupo. `fundir_nos` aceita nó de "
        "nível diferente (assunto/subassunto) quando a origem não tem filhos ativos "
        "(ADR-030, atualização de 2026-10-12). O nó de nível diferente que tem filhos fica "
        "como *sem operação*: o dono decide (mover os filhos ou fundi-los antes).",
        "- **Destino.** Mais questões (`questao_no` aprovadas, por nó resolvido), depois mais "
        "itens de edital aprovados, depois nível mais alto (assunto > subassunto) e menor ID.",
        '- **`mesma_norma`.** Lei/LC/decreto/EC/MP + número (ano ignorado; "LC 101" = '
        '"Lei Complementar nº 101/2000 e suas alterações"; apelidos LRF, LGPD e LAI). Alta só '
        "quando o nó é essencialmente a norma (uma norma só, sem recorte do tema, sem lista "
        '":"/";"/"," fora do parêntese); o resto do grupo vai para média.',
        "- **`mesmo_nome`.** Mesma `chave_regra` sob pais diferentes, fora os nomes genéricos "
        "(`NOMES_GENERICOS_DISPERSAO`, nomes só de palavras genéricas e nome curto de uma "
        "palavra). Vira média se as matérias são de ramos diferentes (Penal × Penal Militar × "
        "Processual).",
        '- **`nome_contido`.** O termo antes de ":" ou "(" de um nó é o início do nome de '
        "outro em outro pai. Sempre média, nunca proposto.",
        "",
        "## Ajustes feitos após a primeira medição",
        "",
        "- Primeira versão dava 171 grupos `mesmo_nome` alta e 149 fusões: falso positivo em "
        'Direito Penal × Penal Militar × Processual ("Ação penal", "Livramento condicional"), '
        'e nomes como "Conceito e objetivos" ou "Jurisprudência aplicada dos tribunais '
        'superiores". Entraram `RAMOS_DISPERSAO` (ramo diferente vira média) e '
        "`TOKENS_GENERICOS_DISPERSAO` (nome só de palavras genéricas).",
        '- `mesma_norma` alta aceitava "Tipos de penalidades previstas na Lei nº 14.133", '
        '"Crimes tipificados no Estatuto do Desarmamento (Lei nº 10.826)" e nomes com '
        'duas normas ("Decreto ... e Portaria Conjunta ..."). Entrou a lista de palavras de '
        "recorte e a recusa de outro tipo de norma no nome.",
        "- `nome_contido` repetia o mesmo conjunto por âncoras diferentes e usava como "
        'âncora termos genéricos ("Classificação: ..."): agora o genérico é testado no '
        "termo principal e o conjunto contido em outro grupo é descartado.",
        "- Depois da regra de fusão entre níveis (KAN-64, 2026-10-12) o detector passou a "
        "propor `fundir` também para nó de nível diferente sem filhos. Os grupos de LGPD, "
        "LRF e suprimento de fundos foram consolidados pelo dono na mesma data e não "
        "aparecem mais.",
        "",
        "## Grupos de confiança alta (ordenados por questões)",
        "",
    ]

    def total(g):
        return sum(g["questoes"].values())

    for conf, titulo in (
        ("alta", None),
        ("media", "## Grupos de confiança média (só relatório)"),
    ):
        if titulo:
            linhas += ["", titulo, ""]
        for g in (x for x in grupos if x["confianca"] == conf):
            linhas.append(
                f"### {arv.nos[g['destino']].nome[:90]} — `{g['motivo']}`, "
                f"{total(g)} questão(ões)"
            )
            linhas.append("")
            linhas.append(f"- Chave: `{g['chave']}`")
            linhas.append("- Nós:")
            linhas += [_linha_no(g, arv, i) for i in g["nos"]]
            linhas.append(f"- Destino sugerido: `{g['destino']}`")
            if conf == "alta":
                if g["operacoes"]:
                    linhas.append("- Operações propostas (`fundir`):")
                    for op in g["operacoes"]:
                        pid = propostas.get(
                            (op["origem"], op["destino"]), "não proposta"
                        )
                        linhas.append(
                            f"  - `{op['origem']}` → `{op['destino']}` — {pid}"
                        )
                else:
                    linhas.append(
                        "- Operações propostas: nenhuma (nós de nível diferente "
                        "com filhos ativos)."
                    )
            elif g["operacoes"]:
                linhas.append(
                    "- Fusões possíveis se o dono decidir: "
                    + ", ".join(
                        f"`{o['origem']}`→`{o['destino']}`" for o in g["operacoes"]
                    )
                )
            if g["sem_operacao"]:
                linhas.append(
                    "- Sem operação (nível diferente com filhos, decisão do dono): "
                    + ", ".join(f"`{i}`" for i in g["sem_operacao"])
                )
            linhas.append("")
    if erros:
        linhas += ["## Erros ao propor", ""] + [f"- {e}" for e in erros] + [""]
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    modo = ap.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true", help="só relatório (padrão)")
    modo.add_argument("--propor", action="store_true", help="grava as propostas")
    ap.add_argument("--relatorio", type=Path, default=RELATORIO_PADRAO)
    ap.add_argument("--arvore", type=Path, default=arvore.ARVORE_PADRAO)
    ap.add_argument(
        "--sem-banco",
        action="store_true",
        help="não consulta questao_no (só itens de edital desempatam)",
    )
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    arv = arvore.carregar(args.arvore)
    contagem: dict[str, int] = {}
    if not args.sem_banco:
        conn = stats_writer.conectar()
        try:
            contagem = questoes_por_no(conn)
        finally:
            conn.close()
    grupos = arvore.detectar_dispersos(arv, contagem)

    alvo = arv if args.propor else copy.deepcopy(arv)
    n_antes = len(alvo.propostas)
    ids, erros = propor_grupos(alvo, grupos)
    novas = len(alvo.propostas) - n_antes
    if args.propor and novas > LIMITE_PROPOSTAS:
        logger.error(
            "%d propostas novas passam do limite de %d (critério frouxo); nada gravado.",
            novas,
            LIMITE_PROPOSTAS,
        )
        return 1
    if args.propor:
        arvore.salvar(arv, args.arvore)
    args.relatorio.parent.mkdir(parents=True, exist_ok=True)
    args.relatorio.write_text(
        gerar_relatorio(arv, grupos, ids, erros, gravou=args.propor),
        encoding="utf-8",
    )
    logger.info(
        "%d grupos (%d alta); %d propostas %s (%d novas); %d erros; relatório em %s",
        len(grupos),
        sum(1 for g in grupos if g["confianca"] == "alta"),
        len(ids),
        "gravadas" if args.propor else "previstas",
        novas,
        len(erros),
        args.relatorio,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
