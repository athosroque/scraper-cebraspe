"""Aplica os reparos locais (item/subitem ausente, hífen de quebra de linha e
matéria do LLM inutilizável e subtópico em cadeia "Pai - Filho" que volta a
texto próprio, KAN-93; ADR-025) a extrações já salvas,
sem chamar o LLM.

`reinjetar_itens_ausentes` roda automaticamente dentro de
`taxonomia_extractor._chamar_llm_uma_vez` pra toda extração nova. Este script
cobre o que foi extraído antes dele existir: pra cada chunk com taxonomia em
`<edital>.json`, reaplica o reparo sobre o `texto_enviado_llm` registrado em
`<edital>.auditoria.json` (o texto exato que o LLM recebeu), grava o `.json`
se algo mudou e atualiza os artefatos de revisão (ADR-019).

Backup em `<edital>.json.pre_reconciliacao.bak` antes da primeira gravação —
nome próprio pra não sobrescrever o `.json.bak` do `reprocessar_falhas_piloto`.
`.auditoria.json` não é tocado: é o registro do que o LLM recebeu.

Uso:
    python -m scripts.reconciliar_taxonomia [--sem-atualizar] [<edital>.json ...]
    --sem-atualizar: grava só o <edital>.json (não chama atualizar_revisao).
    (sem argumento: todos os <edital>.json de revisao_piloto/)
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atualizar_revisao import atualizar_artefatos_revisao
from src.logger import logger
from src.models_scraper import TaxonomiaEdital
from src.taxonomia_extractor import (
    corrigir_hifen_quebra_de_linha,
    migrar_cadeias_para_texto_proprio,
    reinjetar_itens_ausentes,
    reinjetar_subitens_ausentes,
    reparar_materia_extraida,
)

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"


def reconciliar(json_path: Path) -> dict[int, list[str]]:
    """Reconcilia um `<edital>.json` in-place. Retorna `{chunk_index: [itens
    reinjetados]}` só dos chunks alterados (vazio == nada a fazer, nada gravado)."""
    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    if not auditoria_path.exists():
        logger.warning(
            f"{json_path.name}: sem .auditoria.json — sem texto-fonte pra reconciliar, pulando."
        )
        return {}

    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria = json.loads(auditoria_path.read_text(encoding="utf-8"))
    texto_por_index = {
        c["chunk_index"]: c.get("texto_enviado_llm") or "" for c in auditoria["chunks"]
    }

    alterados: dict[int, list[str]] = {}
    for item in resultado["resultados"]:
        taxonomia_salva = item.get("taxonomia_extraida")
        texto = texto_por_index.get(item.get("chunk_index"))
        if not taxonomia_salva or not texto:
            continue
        taxonomia = TaxonomiaEdital.model_validate(taxonomia_salva)
        # Primeiro a forma antiga "Pai - Filho" vira texto próprio (KAN-93),
        # para a cobertura dos reparos seguintes ver os nomes novos.
        reinjetados = [
            f"cadeia:{n}" for n in migrar_cadeias_para_texto_proprio(taxonomia, texto)
        ]
        reinjetados += reinjetar_itens_ausentes(taxonomia, texto)
        reinjetados += reinjetar_subitens_ausentes(taxonomia, texto)
        # Reparos de forma (sem mudar o conjunto de itens): hífen de quebra de
        # linha e matéria vazia/lista de tópicos.
        reinjetados += [
            f"hifen:{n}" for n in corrigir_hifen_quebra_de_linha(taxonomia, texto)
        ]
        # De novo: o conserto do hífen pode ter feito um nome em cadeia casar com a fonte.
        reinjetados += [
            f"cadeia:{n}" for n in migrar_cadeias_para_texto_proprio(taxonomia, texto)
        ]
        motivo = reparar_materia_extraida(
            taxonomia, item.get("materia_normalizada") or item.get("materia_chunk")
        )
        if motivo:
            reinjetados.append(f"materia:{motivo}")
        if reinjetados:
            item["taxonomia_extraida"] = taxonomia.model_dump()
            alterados[item["chunk_index"]] = reinjetados

    if alterados:
        bak = json_path.parent / f"{json_path.name}.pre_reconciliacao.bak"
        if not bak.exists():
            shutil.copy2(json_path, bak)
            logger.info(f"Backup criado: {bak.name}")
        json_path.write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(f"{json_path.name}: itens reinjetados por chunk {alterados}.")
    else:
        logger.info(f"{json_path.name}: nada a reconciliar.")
    return alterados


def main(
    json_paths: list[Path], atualizar_artefatos: bool = True
) -> dict[str, dict[int, list[str]]]:
    resumo = {p.name: reconciliar(p) for p in json_paths}
    if atualizar_artefatos and any(resumo.values()):
        atualizar_artefatos_revisao(json_paths[0].parent)
    return resumo


if __name__ == "__main__":
    argumentos = [a for a in sys.argv[1:] if a != "--sem-atualizar"]
    caminhos = [Path(a) for a in argumentos] or sorted(
        p
        for p in REVISAO_DIR_PADRAO.glob("*.json")
        if not p.name.endswith((".auditoria.json", ".validacao.json"))
    )
    main(caminhos, atualizar_artefatos="--sem-atualizar" not in sys.argv[1:])
