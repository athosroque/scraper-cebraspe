"""Aplica o reparo local de item ausente (ADR-025) a extrações já salvas,
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
    python -m scripts.reconciliar_taxonomia [<edital>.json ...]
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
from src.taxonomia_extractor import reinjetar_itens_ausentes

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
        reinjetados = reinjetar_itens_ausentes(taxonomia, texto)
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
    caminhos = [Path(a) for a in sys.argv[1:]] or sorted(
        p
        for p in REVISAO_DIR_PADRAO.glob("*.json")
        if not p.name.endswith((".auditoria.json", ".validacao.json"))
    )
    main(caminhos)
