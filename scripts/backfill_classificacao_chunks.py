"""Backfill de concurso/nível/tipo de conhecimento em extrações já feitas (ADR-020).

Os campos de classificação do chunk (`tipo_conhecimento`, `nivel`,
`cargo_numero`, `materia_normalizada`, `apenas_discursiva`), o concurso de
origem e a lista de cargos vêm só do parser e do manifesto do downloader,
nunca do LLM. Então dá pra completar um `<edital>.json`/`.auditoria.json`
antigo sem gastar chamada nenhuma no OpenRouter: re-roda o chunking no PDF e
casa com o resultado existente por `chunk_index`.

Aborta sem gravar nada se o chunking novo não bater 1:1 com o antigo
(mesma quantidade de chunks, mesma matéria/cargo por índice) — nesse caso a
extração precisa ser refeita, não completada. `texto_enviado_llm` NÃO é
reescrito: é o registro do que o LLM efetivamente recebeu.

Uso:
    python -m scripts.backfill_classificacao_chunks <caminho_do_pdf> [caminho_do_json]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atualizar_revisao import atualizar_artefatos_revisao
from src.downloader import resolver_concurso_do_pdf
from src.edital_parser import (
    dividir_por_cargo_e_materia,
    extrair_secao_objetos_avaliacao_detalhada,
    mapear_cargos,
    metadados_chunk,
)
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"


def backfill(pdf_path: Path, json_path: Path, atualizar_artefatos: bool = True) -> dict:
    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria = json.loads(auditoria_path.read_text(encoding="utf-8"))

    secao = extrair_secao_objetos_avaliacao_detalhada(pdf_path)
    if secao is None:
        raise ValueError(f"Seção 'OBJETOS DE AVALIAÇÃO' não encontrada em {pdf_path}")
    chunks = dividir_por_cargo_e_materia(
        secao.texto,
        cargo_padrao=secao.cargo_detectado,
        nivel_padrao=secao.nivel_detectado,
    )

    if len(chunks) != len(auditoria["chunks"]):
        raise ValueError(
            f"Chunking atual gera {len(chunks)} chunks, extração salva tem "
            f"{len(auditoria['chunks'])} — refazer a extração, não completar."
        )
    for chunk_auditoria in auditoria["chunks"]:
        chunk = chunks[chunk_auditoria["chunk_index"]]
        if chunk.materia != chunk_auditoria["materia"] or (
            chunk_auditoria["cargo"] is not None and chunk.cargo != chunk_auditoria["cargo"]
        ):
            raise ValueError(
                f"Chunk #{chunk_auditoria['chunk_index']} divergente: salvo "
                f"({chunk_auditoria['cargo']}, {chunk_auditoria['materia']}) vs atual "
                f"({chunk.cargo}, {chunk.materia}) — refazer a extração, não completar."
            )

    for chunk_auditoria in auditoria["chunks"]:
        chunk = chunks[chunk_auditoria["chunk_index"]]
        chunk_auditoria.update(metadados_chunk(chunk))
        chunk_auditoria["cargo"] = chunk.cargo
    for item in resultado["resultados"] + resultado["chunks_com_falha"]:
        chunk = chunks[item["chunk_index"]]
        item.update(metadados_chunk(chunk))
        item["cargo"] = chunk.cargo

    resultado["concurso"] = resolver_concurso_do_pdf(pdf_path)
    resultado["cargos"] = mapear_cargos(
        chunks,
        cargo_padrao=secao.cargo_detectado,
        nivel_padrao=secao.nivel_detectado,
    )

    json_path.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    auditoria_path.write_text(json.dumps(auditoria, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        f"Backfill de classificação em {json_path.name}: {len(chunks)} chunks, "
        f"concurso={resultado['concurso']}, {len(resultado['cargos'])} cargos."
    )

    if atualizar_artefatos:
        atualizar_artefatos_revisao(json_path.parent)
    return resultado


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.backfill_classificacao_chunks <caminho_do_pdf> [caminho_do_json]")
        sys.exit(1)

    pdf_arg = Path(sys.argv[1])
    json_arg = Path(sys.argv[2]) if len(sys.argv) > 2 else REVISAO_DIR_PADRAO / f"{pdf_arg.stem}.json"
    backfill(pdf_arg, json_arg)
