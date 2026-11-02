"""Migra as chaves de mapeamento do subtópico em cadeia ("Pai - Filho") para o
texto próprio (KAN-93, M7, Etapa 5B.4) e as do que a forma de lista/faceta
mudou (KAN-94, M8; ver "M8" mais abaixo).

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

M8 (KAN-94): `scripts.reconciliar_taxonomia` deixa o rastro no `<edital>.json`
(`Topico.nome_origem`, `Topico.subtopicos_absorvidos`), de onde as chaves antigas
são recalculadas. Tópico-lista cuja cabeça virou o nome entra no mesmo plano dos
pares antiga -> nova (move, descarta ou conflito). Faceta devolvida ao pai tem a
chave `materia|topico|faceta` fora do JSON: o apontamento só é removido se TODOS
os seus mapeamentos são `origem=regra` (herança do passo determinístico, KAN-85) e
os nós já estão no tópico pai; qualquer outro (humano, LLM, nó diferente) fica na
árvore e vai para o relatório como órfão, para o dono decidir. Nada some sem aviso.

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
    # M8: facetas devolvidas ao pai, (chave da faceta, chave do tópico pai).
    absorvidas_descartadas: list[tuple[str, str]] = field(default_factory=list)
    absorvidas_em_uso: list[tuple[str, str]] = field(default_factory=list)
    absorvidas_orfas: list[tuple[str, str]] = field(default_factory=list)
    absorvidas_sem_mapeamento: list[str] = field(default_factory=list)


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


def _topicos_brutos(resultado: dict) -> dict[tuple[int, int], dict]:
    """`(chunk_index, ordem do tópico)` -> tópico como está no JSON (com o rastro
    da M8, que a carga do banco não leva)."""
    return {
        (item.get("chunk_index"), ordem): topico
        for item in resultado.get("resultados", [])
        for ordem, topico in enumerate(
            (item.get("taxonomia_extraida") or {}).get("topicos", [])
        )
    }


def facetas_absorvidas(revisao_dir: Path) -> dict[str, set[str]]:
    """Chave da faceta devolvida ao pai (M8) -> chaves dos tópicos pai."""
    saida: dict[str, set[str]] = {}
    for json_path in listar_jsons_edital(revisao_dir):
        resultado = json.loads(json_path.read_text(encoding="utf-8"))
        brutos = _topicos_brutos(resultado)
        for item in montar_carga_concurso(resultado)["itens"]:
            bruto = brutos.get((item["chunk_index"], item["topico_ordem"]), {})
            topico = arv_mod.chave_item((item["materia_chave"], item["topico_chave"]))
            for faceta in bruto.get("subtopicos_absorvidos") or []:
                if normalizar(faceta):
                    chave = arv_mod.chave_item((topico, normalizar(faceta)))
                    saida.setdefault(chave, set()).add(topico)
    return saida


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
        brutos = _topicos_brutos(resultado)
        nova = montar_carga_concurso(resultado)["itens"]
        antiga = montar_carga_concurso(_expandir_cadeias(resultado))["itens"]
        if len(nova) != len(antiga):
            raise ValueError(f"{json_path.name}: cargas de tamanhos diferentes")
        for item_n, item_a in zip(nova, antiga):
            m, t = item_n["materia_chave"], item_n["topico_chave"]
            atuais.add(arv_mod.chave_item((m, t)))
            bruto = brutos.get((item_n["chunk_index"], item_n["topico_ordem"]), {})
            origem = bruto.get("nome_origem")
            if origem and normalizar(origem) != t:  # M8: a cabeça virou o nome
                k_a = arv_mod.chave_item((m, normalizar(origem)))
                k_n = arv_mod.chave_item((m, t))
                if pares.setdefault(k_a, k_n) != k_n:
                    ambiguos.setdefault(k_a, {pares[k_a]}).add(k_n)
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


def _planejar_facetas(arv, revisao_dir: Path, atuais: set[str], plano) -> None:
    """M8: o que fazer com o apontamento de uma faceta devolvida ao pai."""
    for faceta, topicos in sorted(facetas_absorvidas(revisao_dir).items()):
        pai = sorted(topicos)[0]
        if faceta not in arv.mapeamentos:
            plano.absorvidas_sem_mapeamento.append(faceta)
        elif faceta in atuais:
            plano.absorvidas_em_uso.append((faceta, pai))
        elif (
            all(m.origem == "regra" for m in arv.mapeamentos[faceta])
            and pai in arv.mapeamentos
            and _nos(arv, faceta) <= _nos(arv, pai)
        ):
            plano.absorvidas_descartadas.append((faceta, pai))
        else:
            plano.absorvidas_orfas.append((faceta, pai))


def planejar(arv, revisao_dir: Path) -> PlanoMigracao:
    """Plano da migração; não altera `arv`."""
    pares, ambiguos, atuais = pares_de_chaves(revisao_dir)
    plano = PlanoMigracao(pares=pares, ambiguos=ambiguos)
    _planejar_facetas(arv, revisao_dir, atuais, plano)
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
    for faceta, _ in plano.absorvidas_descartadas:
        arv.mapeamentos.pop(faceta, None)


def _imprimir(plano: PlanoMigracao) -> None:
    print(f"Chaves que mudam: {len(plano.pares)} (ambíguas: {len(plano.ambiguos)})")
    print(f"  sem mapeamento na árvore: {len(plano.sem_mapeamento)}")
    print(f"  movidas: {len(plano.movidos)}")
    print(f"  antiga descartada (nova já tem os nós): {len(plano.descartados)}")
    print(f"  copiadas (antiga ainda em uso): {len(plano.copiados)}")
    print(f"  CONFLITOS (nada alterado): {len(plano.conflitos)}")
    print(
        "Facetas devolvidas ao pai (M8): "
        f"{len(plano.absorvidas_descartadas) + len(plano.absorvidas_em_uso) + len(plano.absorvidas_orfas) + len(plano.absorvidas_sem_mapeamento)}"
    )
    print(f"  sem mapeamento na árvore: {len(plano.absorvidas_sem_mapeamento)}")
    print(
        f"  herança redundante (regra, nós já no pai), removida: {len(plano.absorvidas_descartadas)}"
    )
    print(f"  ainda em uso por outro item, mantida: {len(plano.absorvidas_em_uso)}")
    print(f"  ÓRFÃS mantidas (decisão do dono): {len(plano.absorvidas_orfas)}")
    for rotulo, lista in (
        ("movida", plano.movidos),
        ("conflito", plano.conflitos),
        ("órfã", plano.absorvidas_orfas),
    ):
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
