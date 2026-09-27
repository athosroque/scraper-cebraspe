"""Checkpoint de Revisão Humana Contínua (Etapa 4, task.md).

Roda o pipeline completo (parser -> chunking -> extração LLM) para 1
edital piloto e SALVA o resultado estruturado em JSON para revisão manual.
Esse script é o gate explícito pedido no task.md: ele NÃO escreve em banco,
não decide sozinho que a extração está "boa" e não dispara processamento em
lote — só produz o material para um humano aprovar (ou não) antes de
qualquer automação maior.

Além do resultado (`<edital>.json`), também salva uma trilha de auditoria
de entrada/saída do filtro (`<edital>.auditoria.json`) com o que entrou e
o que saiu de cada etapa local (corte de seção, chunking) — necessária pra
validar depois se o filtro descartou/reteve o texto certo, já que o
`logs/scraper_cebraspe.log` só registra contagens agregadas, não o
conteúdo em si. Ver CLAUDE.md, seção 12.

Ao final, chama `scripts.atualizar_revisao` automaticamente — validação
heurística de-para, relatório HTML e banco Datasette ficam sempre em dia
com o resultado mais recente, sem passo manual (ver ADR-019).

Uso:
    python -m scripts.revisar_taxonomia_piloto <caminho_do_pdf> [saida.json]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atualizar_revisao import atualizar_artefatos_revisao
from src.downloader import resolver_concurso_do_pdf
from src.edital_parser import (
    MARCADOR_FIM_SECAO,
    MARCADOR_INICIO_SECAO,
    dividir_por_cargo_e_materia,
    extrair_secao_objetos_avaliacao_detalhada,
    mapear_cargos,
    metadados_chunk,
)
from src.logger import logger
from src.taxonomia_extractor import extrair_taxonomia_chunk

STATUS_REVISAO_PENDENTE = (
    "PENDENTE — este resultado ainda NÃO foi revisado por um humano. "
    "Não usar em lote/produção até aprovação explícita (ver task.md, Etapa 4)."
)


def revisar_edital_piloto(pdf_path: Path, saida_path: Path) -> dict:
    secao = extrair_secao_objetos_avaliacao_detalhada(pdf_path)
    if secao is None:
        raise ValueError(f"Seção 'OBJETOS DE AVALIAÇÃO' não encontrada em {pdf_path}")

    chunks = dividir_por_cargo_e_materia(
        secao.texto,
        cargo_padrao=secao.cargo_detectado,
        nivel_padrao=secao.nivel_detectado,
    )
    logger.info(f"{len(chunks)} chunks identificados em {pdf_path.name}")

    resultados = []
    falhas = []
    auditoria_chunks = []
    total = len(chunks)
    for chunk_index, chunk in enumerate(chunks):
        logger.info(
            f"[{chunk_index + 1}/{total}] enviando ao LLM: "
            f"{chunk.cargo or 'sem cargo'} — {chunk.materia}"
        )
        taxonomia, motivo_falha = extrair_taxonomia_chunk(chunk.texto)
        # `motivo_falha` distingue falha semântica identificada (ex.: nome de
        # tópico numérico sem correspondência na fonte, ver ADR-021) de falha
        # técnica genérica (rede/timeout/parse) — só a última vira "falha".
        status = "sucesso" if taxonomia is not None else (motivo_falha or "falha")
        logger.info(
            f"[{chunk_index + 1}/{total}] {status} — faltam {total - chunk_index - 1}"
        )
        auditoria_chunks.append(
            {
                "chunk_index": chunk_index,
                "cargo": chunk.cargo,
                "materia": chunk.materia,
                **metadados_chunk(chunk),
                "offset_inicio_secao": chunk.offset_inicio,
                "offset_fim_secao": chunk.offset_fim,
                "chars": len(chunk.texto),
                "texto_enviado_llm": chunk.texto,
                "status": status,
            }
        )
        if taxonomia is None:
            falhas.append(
                {
                    "chunk_index": chunk_index,
                    "cargo": chunk.cargo,
                    "materia_esperada": chunk.materia,
                    **metadados_chunk(chunk),
                }
            )
            continue
        resultados.append(
            {
                "chunk_index": chunk_index,
                "cargo": chunk.cargo,
                "materia_chunk": chunk.materia,
                **metadados_chunk(chunk),
                "taxonomia_extraida": taxonomia.model_dump(),
            }
        )

    saida = {
        "edital": pdf_path.name,
        # Concurso de origem (slug/órgão/ano) e cargos com nível — base dos
        # filtros por concurso e por nível; ver ADR-020.
        "concurso": resolver_concurso_do_pdf(pdf_path),
        "cargos": mapear_cargos(
            chunks,
            cargo_padrao=secao.cargo_detectado,
            nivel_padrao=secao.nivel_detectado,
        ),
        "total_chunks": len(chunks),
        "extraidos_com_sucesso": len(resultados),
        "falhas": len(falhas),
        "chunks_com_falha": falhas,
        "resultados": resultados,
        "status_revisao_humana": STATUS_REVISAO_PENDENTE,
    }

    saida_path.parent.mkdir(parents=True, exist_ok=True)
    saida_path.write_text(
        json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        f"Resultado salvo em {saida_path} — "
        f"{len(resultados)}/{len(chunks)} chunks extraídos, {len(falhas)} falhas"
    )

    auditoria = {
        "edital": pdf_path.name,
        "pdf_total_paginas": secao.paginas_pdf_total,
        "pdf_total_chars": secao.chars_pdf_total,
        "secao_objetos_avaliacao": {
            "marcador_inicio": MARCADOR_INICIO_SECAO,
            "marcador_fim": MARCADOR_FIM_SECAO,
            "marcador_fim_encontrado": secao.marcador_fim_encontrado,
            "offset_inicio_char": secao.offset_inicio,
            "offset_fim_char": secao.offset_fim,
            "chars_secao": len(secao.texto),
            "chars_descartados_do_pdf": secao.chars_pdf_total - len(secao.texto),
        },
        "chunks": auditoria_chunks,
    }
    auditoria_path = saida_path.parent / f"{pdf_path.stem}.auditoria.json"
    auditoria_path.write_text(
        json.dumps(auditoria, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        f"Auditoria de entrada/saída (parser+extractor) salva em {auditoria_path}"
    )

    atualizar_artefatos_revisao(saida_path.parent)

    return saida


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Uso: python -m scripts.revisar_taxonomia_piloto <caminho_do_pdf> [saida.json]"
        )
        sys.exit(1)

    pdf_arg = Path(sys.argv[1])
    if len(sys.argv) > 2:
        saida_arg = Path(sys.argv[2])
    else:
        saida_arg = (
            Path(__file__).resolve().parent.parent
            / "revisao_piloto"
            / f"{pdf_arg.stem}.json"
        )

    revisar_edital_piloto(pdf_arg, saida_arg)
