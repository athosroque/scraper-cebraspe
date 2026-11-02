"""Migra as chaves de mapeamento do subtópico em cadeia ("Pai - Filho") para o
texto próprio (KAN-93, M7, Etapa 5B.4).

Depois de `scripts.reconciliar_taxonomia` trocar o nome em cadeia pelo texto próprio
(com a cadeia em `Topico.caminho_origem`), a chave do item muda: de
`materia|topico|pai filho` para `materia|topico|filho`. Os mapeamentos que o
dono (ou o passo determinístico) já gravaram na chave antiga precisam acompanhar,
senão viram órfãos e o item novo volta a ficar pendente.

A chave antiga de cada subtópico é recalculada sem consultar o banco nem backup:
é `normalizar(" - ".join([*caminho_origem, nome]))`, com a mesma `materia|topico` do
writer (`montar_carga_concurso`). A escrita passa só por `src/arvore.py` (A28).

Regras da migração, por chave antiga com mapeamento na árvore:
- chave nova sem mapeamento: os apontamentos mudam de chave, com origem, status e
  nós intactos;
- chave nova com os mesmos nós (ou um superconjunto): a antiga some, a nova fica;
- chave nova com nó diferente: CONFLITO, nada é alterado (a decisão é do dono) e o
  item entra no relatório;
- a chave antiga ainda produzida por algum item atual (outro edital, ou nome que
  coincide) é copiada, não removida.

Uso:
    python -m scripts.migrar_chaves_cadeia [--aplicar] [--arvore CAMINHO] [revisao_dir]

Sem `--aplicar` é dry-run (padrão): imprime o plano e não grava.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import arvore as arv_mod
from src.comparacao_texto import normalizar
from src.stats_writer import listar_jsons_edital, montar_carga_concurso

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"


@dataclass
class PlanoMigracao:
    pares: dict[str, str] = field(default_factory=dict)  # chave antiga -> nova
    ambiguos: dict[str, set[str]] = field(default_factory=dict)
    movidos: list[tuple[str, str]] = field(default_factory=list)
    descartados: list[tuple[str, str]] = field(
        default_factory=list
    )  # antiga redundante
    copiados: list[tuple[str, str]] = field(default_factory=list)  # antiga ainda em uso
    conflitos: list[tuple[str, str]] = field(default_factory=list)
    sem_mapeamento: list[str] = field(default_factory=list)


def _expandir_cadeias(resultado: dict) -> dict:
    """Cópia do `<edital>.json` com os subtópicos de volta à forma em cadeia."""
    copia = copy.deepcopy(resultado)
    for item in copia.get("resultados", []):
        taxonomia = item.get("taxonomia_extraida") or {}
        for topico in taxonomia.get("topicos", []):
            caminhos = topico.get("caminho_origem") or {}
            topico["subtopicos"] = [
                " - ".join([*caminhos.get(s, []), s])
                for s in topico.get("subtopicos", [])
            ]
    return copia


def pares_de_chaves(
    revisao_dir: Path,
) -> tuple[dict[str, str], dict[str, set[str]], set[str]]:
    """`(pares antiga->nova, ambíguos, chaves de subtópico atuais)` de todos os
    `<edital>.json` do diretório."""
    pares: dict[str, str] = {}
    ambiguos: dict[str, set[str]] = {}
    atuais: set[str] = set()
    for json_path in listar_jsons_edital(revisao_dir):
        resultado = json.loads(json_path.read_text(encoding="utf-8"))
        nova = montar_carga_concurso(resultado)["itens"]
        antiga = montar_carga_concurso(_expandir_cadeias(resultado))["itens"]
        if len(nova) != len(antiga):
            raise ValueError(f"{json_path.name}: cargas de tamanhos diferentes")
        for item_n, item_a in zip(nova, antiga):
            m, t = item_n["materia_chave"], item_n["topico_chave"]
            if len(item_n["subtopicos"]) != len(item_a["subtopicos"]):
                raise ValueError(f"{json_path.name}: subtópicos desalinhados")
            for sub_n, sub_a in zip(item_n["subtopicos"], item_a["subtopicos"]):
                s_n, s_a = normalizar(sub_n), normalizar(sub_a)
                if not s_n:
                    continue
                atuais.add(arv_mod.chave_item((m, t, s_n)))
                if s_n == s_a:
                    continue
                k_a, k_n = (
                    arv_mod.chave_item((m, t, s_a)),
                    arv_mod.chave_item((m, t, s_n)),
                )
                if pares.setdefault(k_a, k_n) != k_n:
                    ambiguos.setdefault(k_a, {pares[k_a]}).add(k_n)
    return pares, ambiguos, atuais


def _nos(arv, chave: str) -> set[str]:
    return {arv_mod.resolver_no(arv, m.no_id) for m in arv.mapeamentos.get(chave, [])}


def planejar(arv, revisao_dir: Path) -> PlanoMigracao:
    """Plano da migração; não altera `arv`."""
    pares, ambiguos, atuais = pares_de_chaves(revisao_dir)
    plano = PlanoMigracao(pares=pares, ambiguos=ambiguos)
    for antiga, nova in sorted(pares.items()):
        if antiga not in arv.mapeamentos:
            plano.sem_mapeamento.append(antiga)
            continue
        if antiga in ambiguos:
            plano.conflitos.append((antiga, nova))
            continue
        em_uso = antiga in atuais
        if nova not in arv.mapeamentos:
            (plano.copiados if em_uso else plano.movidos).append((antiga, nova))
        elif _nos(arv, antiga) <= _nos(arv, nova):
            if em_uso:
                plano.copiados.append((antiga, nova))
            else:
                plano.descartados.append((antiga, nova))
        else:
            plano.conflitos.append((antiga, nova))
    return plano


def aplicar_plano(arv, plano: PlanoMigracao) -> None:
    """Aplica o plano em `arv` (em memória): mantém origem, status e nós."""
    for antiga, nova in plano.movidos + plano.copiados:
        if nova in arv.mapeamentos:
            continue
        arv.mapeamentos[nova] = copy.deepcopy(arv.mapeamentos[antiga])
    for antiga, _ in plano.movidos + plano.descartados:
        arv.mapeamentos.pop(antiga, None)


def _imprimir(plano: PlanoMigracao) -> None:
    print(f"Chaves que mudam: {len(plano.pares)} (ambíguas: {len(plano.ambiguos)})")
    print(f"  sem mapeamento na árvore: {len(plano.sem_mapeamento)}")
    print(f"  movidas: {len(plano.movidos)}")
    print(f"  antiga descartada (nova já tem os nós): {len(plano.descartados)}")
    print(f"  copiadas (antiga ainda em uso): {len(plano.copiados)}")
    print(f"  CONFLITOS (nada alterado): {len(plano.conflitos)}")
    for rotulo, lista in (("movida", plano.movidos), ("conflito", plano.conflitos)):
        for antiga, nova in lista:
            print(f"  [{rotulo}] {antiga}  ->  {nova}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("revisao_dir", nargs="?", type=Path, default=REVISAO_DIR_PADRAO)
    parser.add_argument("--arvore", type=Path, default=arv_mod.ARVORE_PADRAO)
    parser.add_argument(
        "--aplicar", action="store_true", help="grava a árvore (padrão: dry-run)"
    )
    args = parser.parse_args(argv)

    arv = arv_mod.carregar(args.arvore)
    plano = planejar(arv, args.revisao_dir)
    _imprimir(plano)
    if not args.aplicar:
        print("Dry-run: nada gravado. Use --aplicar para gravar.")
        return 0
    if plano.conflitos:
        print(
            "Há conflitos: resolva-os com scripts/curar_arvore.py; o resto foi aplicado."
        )
    aplicar_plano(arv, plano)
    arv_mod.salvar(arv, args.arvore)
    print("Árvore gravada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
