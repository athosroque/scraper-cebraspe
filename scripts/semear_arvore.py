"""Semeia `canonico/arvore.json` com os grupos aprovados da 5B (ADR-030).

Cada grupo aprovado de `sinonimos.json` vira um nó com o **mesmo ID** (pai =
grupo aprovado do escopo), e cada nome de origem vira um mapeamento
`semente`. Determinístico: rodar de novo sobre o mesmo `sinonimos.json` não
gera diff. Roda uma vez; depois a árvore é curada e o `sinonimos.json` fica
congelado. Se a árvore em disco já diverge da semente (curadoria feita), o
script se recusa a sobrescrever sem `--forcar`.

Uso:
    python -m scripts.semear_arvore [--forcar]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.arvore import (
    ARVORE_PADRAO,
    NIVEIS,
    ArvoreInvalida,
    ArvoreMestre,
    carregar,
    chave_item,
    criar_no,
    mapear,
    salvar,
)
from src.canonico import SINONIMOS_PADRAO, indice_aprovado
from src.canonico import carregar as carregar_sinonimos
from src.logger import logger


def arvore_semente(sinonimos_path: Path = SINONIMOS_PADRAO) -> ArvoreMestre:
    indice = indice_aprovado(carregar_sinonimos(sinonimos_path))
    arvore = ArvoreMestre()
    for nivel in NIVEIS:
        for gid, info in indice.grupos.get(nivel, {}).items():
            criar_no(
                arvore,
                nivel,
                info["nome"],
                info["pai"],
                origem="semente",
                status="ativo",
                id_override=gid,
            )
    for nivel in NIVEIS:
        for chave, gid in getattr(indice, nivel).items():
            mapear(
                arvore, chave_item(chave), [gid], origem="semente", status="aprovado"
            )
    return arvore


def semear(
    sinonimos_path: Path = SINONIMOS_PADRAO,
    arvore_path: Path = ARVORE_PADRAO,
    forcar: bool = False,
) -> ArvoreMestre:
    arvore = arvore_semente(sinonimos_path)
    if arvore_path.exists() and not forcar and carregar(arvore_path) != arvore:
        raise ArvoreInvalida(
            f"{arvore_path} já foi curado e diverge da semente; "
            "use --forcar para descartar a curadoria"
        )
    salvar(arvore, arvore_path)
    contagem = {n: sum(no.nivel == n for no in arvore.nos.values()) for n in NIVEIS}
    logger.info(
        f"[ARVORE] semeada: {contagem} nós, {len(arvore.mapeamentos)} mapeamentos"
    )
    return arvore


if __name__ == "__main__":
    try:
        semear(forcar="--forcar" in sys.argv[1:])
    except ArvoreInvalida as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
