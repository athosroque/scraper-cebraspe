"""Backfill de concurso/nível/tipo de conhecimento em extrações já feitas (ADR-020).

Os campos de classificação do chunk (`tipo_conhecimento`, `nivel`,
`cargo_numero`, `materia_normalizada`, `apenas_discursiva`), o concurso de
origem e a lista de cargos vêm só do parser e do manifesto do downloader,
nunca do LLM. Então dá pra completar um `<edital>.json`/`.auditoria.json`
antigo sem gastar chamada nenhuma no OpenRouter: re-roda o chunking no PDF e
casa com o resultado existente por `chunk_index`.

Aborta sem gravar nada se o chunking novo não bater 1:1 com o antigo
(mesma quantidade de chunks e, por índice, mesma matéria/cargo e texto) —
nesse caso a extração precisa ser refeita, não completada. `texto_enviado_llm`
NÃO é reescrito: é o registro do que o LLM efetivamente recebeu.

Uso:
    python -m scripts.backfill_classificacao_chunks                  # todos os editais de revisao_piloto/
    python -m scripts.backfill_classificacao_chunks <pdf> [json]     # um edital
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atualizar_revisao import atualizar_artefatos_revisao
from src.downloader import DATA_DIR, resolver_concurso_do_pdf
from src.edital_parser import (
    dividir_por_cargo_e_materia,
    extrair_secao_objetos_avaliacao_detalhada,
    mapear_cargos,
    metadados_chunk,
)
from src.logger import logger
from src.stats_writer import listar_jsons_edital

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"


def _sem_espacos_repetidos(texto: str | None) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


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
        # Espaços são comparados colapsados porque o parser passou a colapsá-los
        # no nome (ADR-028). O texto é o que prova o alinhamento: dois chunks
        # "LÍNGUA PORTUGUESA" (superior e médio) trocados passariam só pelo nome.
        # O atual é prefixo do salvo, e não igual, porque a assinatura do fim da
        # seção passou a ser removida depois da extração (ADR-025).
        texto_salvo = chunk_auditoria.get("texto_enviado_llm")
        if (
            _sem_espacos_repetidos(chunk.materia)
            != _sem_espacos_repetidos(chunk_auditoria["materia"])
            or (
                chunk_auditoria["cargo"] is not None
                and _sem_espacos_repetidos(chunk.cargo)
                != _sem_espacos_repetidos(chunk_auditoria["cargo"])
            )
            or (
                texto_salvo is not None
                and not (chunk.texto and texto_salvo.startswith(chunk.texto))
            )
        ):
            raise ValueError(
                f"Chunk #{chunk_auditoria['chunk_index']} divergente: salvo "
                f"({chunk_auditoria['cargo']}, {chunk_auditoria['materia']}) vs atual "
                f"({chunk.cargo}, {chunk.materia}) — refazer a extração, não completar."
            )

    alterados_por_campo: dict[str, int] = {}
    for chunk_auditoria in auditoria["chunks"]:
        chunk = chunks[chunk_auditoria["chunk_index"]]
        novos = metadados_chunk(chunk)
        for campo, valor in novos.items():
            if chunk_auditoria.get(campo) != valor:
                alterados_por_campo[campo] = alterados_por_campo.get(campo, 0) + 1
                logger.debug(
                    f"[BACKFILL] {json_path.stem} chunk #{chunk_auditoria['chunk_index']} {campo}: "
                    f"{chunk_auditoria.get(campo)!r} → {valor!r}"
                )
        chunk_auditoria.update(novos)
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

    json_path.write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    auditoria_path.write_text(
        json.dumps(auditoria, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    slug = (resultado["concurso"] or {}).get("slug") or json_path.stem
    restritos = sum(1 for c in chunks if c.cargos_restritos)
    mudancas = (
        ", ".join(f"{n} {campo}" for campo, n in sorted(alterados_por_campo.items()))
        or "nenhuma"
    )
    logger.info(
        f"[BACKFILL] {slug}: {len(chunks)} chunks · {len(resultado['cargos'])} cargos · "
        f"{restritos} chunks com cargos_restritos · campos alterados: {mudancas}"
    )

    if atualizar_artefatos:
        atualizar_artefatos_revisao(json_path.parent)
    return resultado


def localizar_pdf_edital(json_path: Path, data_dir: Path = DATA_DIR) -> Path:
    """PDF de origem de um `<edital>.json` (mesmo nome, em alguma pasta `Editais/`).
    Ausente ou ambíguo levanta `FileNotFoundError` — escolher um ao acaso
    poderia casar o JSON com o edital errado."""
    pdfs = sorted(data_dir.glob(f"**/Editais/{json_path.stem}.pdf"))
    if len(pdfs) != 1:
        raise FileNotFoundError(
            f"Esperado 1 PDF para {json_path.name} em {data_dir}, achados {len(pdfs)}: {pdfs}"
        )
    return pdfs[0]


def backfill_lote(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    data_dir: Path = DATA_DIR,
    atualizar_artefatos: bool = True,
) -> list[dict]:
    """Backfill em todos os editais de `revisao_dir`.

    Resolve e confere todos os PDFs antes de gravar qualquer JSON: um edital
    sem PDF (ou com PDF ambíguo) não deixa o lote gravado pela metade.
    """
    pares = [
        (localizar_pdf_edital(json_path, data_dir), json_path)
        for json_path in listar_jsons_edital(revisao_dir)
    ]

    resultados = [
        backfill(pdf_path, json_path, atualizar_artefatos=False)
        for pdf_path, json_path in pares
    ]
    if atualizar_artefatos:
        atualizar_artefatos_revisao(revisao_dir)
    return resultados


if __name__ == "__main__":
    if len(sys.argv) < 2:
        backfill_lote()
    else:
        pdf_arg = Path(sys.argv[1])
        json_arg = (
            Path(sys.argv[2])
            if len(sys.argv) > 2
            else REVISAO_DIR_PADRAO / f"{pdf_arg.stem}.json"
        )
        backfill(pdf_arg, json_arg)
