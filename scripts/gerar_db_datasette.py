"""Constrói o banco SQLite servido via Datasette para revisão humana (Etapa 4).

Lê todos os pares `revisao_piloto/<edital>.json` (+ `<edital>.auditoria.json`
quando existir) e reconstrói `revisao_piloto/revisao.db` do zero — banco de
apoio à revisão (entrada/saída do parser + taxonomia extraída lado a lado),
não o schema de produção da Fase 5 (esse é o Postgres próprio `scraper-cebraspe-db`,
ver ADR-026).

Reconstrução completa a cada execução (não incremental): na escala do
piloto (poucos editais) upsert só adicionaria risco de linha obsoleta sem
ganho nenhum.

Uso:
    python -m scripts.gerar_db_datasette [revisao_piloto_dir]
"""

import json
import sys
from pathlib import Path

import sqlite_utils

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.edital_parser import CAMPOS_CLASSIFICACAO_CHUNK
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
DB_NOME = "revisao.db"


def _classificacao(item: dict) -> dict:
    # `.get` e não `[...]`: JSON anterior ao ADR-020 não tem esses campos.
    return {campo: item.get(campo) for campo in CAMPOS_CLASSIFICACAO_CHUNK}


# sqlite-utils infere o tipo da coluna pela 1ª linha inserida — como os
# chunks básicos vêm primeiro com `cargo_numero=None`, a coluna virava TEXT
# ("15" em vez de 15) e quebrava ordenação/comparação numérica no Datasette.
TIPOS_COLUNAS_CLASSIFICACAO = {
    "cargo_numero": int,
    "apenas_discursiva": int,
    "materia_origem": str,
}


def _concurso(resultado: dict) -> dict:
    concurso = resultado.get("concurso") or {}
    return {
        "concurso_slug": concurso.get("slug"),
        "orgao": concurso.get("orgao"),
        "ano": concurso.get("ano"),
    }


def _carregar_par(
    json_path: Path,
) -> tuple[dict, dict | None, Path | None, dict | None]:
    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    auditoria, origem_auditoria = None, None
    if auditoria_path.exists():
        auditoria, origem_auditoria = (
            json.loads(auditoria_path.read_text(encoding="utf-8")),
            auditoria_path,
        )
    validacao_path = json_path.parent / f"{json_path.stem}.validacao.json"
    validacao = (
        json.loads(validacao_path.read_text(encoding="utf-8"))
        if validacao_path.exists()
        else None
    )
    return resultado, auditoria, origem_auditoria, validacao


def _inserir_edital(
    db: sqlite_utils.Database,
    resultado: dict,
    auditoria: dict | None,
    origem: Path,
    origem_auditoria: Path | None,
    validacao: dict | None,
) -> None:
    secao = (auditoria or {}).get("secao_objetos_avaliacao", {})
    db["editais"].insert(
        {
            "edital": resultado["edital"],
            **_concurso(resultado),
            "total_chunks": resultado["total_chunks"],
            "extraidos_com_sucesso": resultado["extraidos_com_sucesso"],
            "falhas": resultado["falhas"],
            "status_revisao_humana": resultado["status_revisao_humana"],
            "pdf_total_paginas": auditoria.get("pdf_total_paginas")
            if auditoria
            else None,
            "pdf_total_chars": auditoria.get("pdf_total_chars") if auditoria else None,
            "marcador_fim_encontrado": secao.get("marcador_fim_encontrado"),
            "offset_inicio_char": secao.get("offset_inicio_char"),
            "offset_fim_char": secao.get("offset_fim_char"),
            "chars_secao": secao.get("chars_secao"),
            "chars_descartados_do_pdf": secao.get("chars_descartados_do_pdf"),
            "origem_json": str(origem),
            "origem_auditoria_json": str(origem_auditoria)
            if origem_auditoria
            else None,
            "total_alertas": validacao.get("total_alertas") if validacao else None,
            "total_informativos": validacao.get("total_informativos", 0)
            if validacao
            else None,
        },
        pk="edital",
        replace=True,
    )


def _inserir_chunks_com_auditoria(
    db: sqlite_utils.Database, edital: str, auditoria: dict
) -> dict[int, int]:
    chunk_id_by_index: dict[int, int] = {}
    for chunk in auditoria["chunks"]:
        chunk_id = (
            db["chunks"]
            .insert(
                {
                    "edital": edital,
                    "chunk_index": chunk.get("chunk_index"),
                    "cargo": chunk["cargo"],
                    "materia": chunk["materia"],
                    **_classificacao(chunk),
                    "offset_inicio_secao": chunk["offset_inicio_secao"],
                    "offset_fim_secao": chunk["offset_fim_secao"],
                    "chars": chunk["chars"],
                    "texto_enviado_llm": chunk["texto_enviado_llm"],
                    "status": chunk["status"],
                },
                pk="id",
                foreign_keys=[("edital", "editais", "edital")],
                columns=TIPOS_COLUNAS_CLASSIFICACAO,
            )
            .last_pk
        )
        if chunk.get("chunk_index") is not None:
            chunk_id_by_index[chunk["chunk_index"]] = chunk_id
    return chunk_id_by_index


def _inserir_chunks_sem_auditoria(
    db: sqlite_utils.Database, edital: str, resultado: dict
) -> dict[int, int]:
    # Arquivos gerados antes do `chunk_index` (ver revisar_taxonomia_piloto.py)
    # não têm essa chave — a posição do item na lista `resultados` é o único
    # jeito de ligar cada resultado de volta ao seu chunk nesse formato legado.
    chunk_id_by_index: dict[int, int] = {}
    for posicao, item in enumerate(resultado["resultados"]):
        chave = item["chunk_index"] if item.get("chunk_index") is not None else posicao
        chunk_id = (
            db["chunks"]
            .insert(
                {
                    "edital": edital,
                    "chunk_index": item.get("chunk_index"),
                    "cargo": item["cargo"],
                    "materia": item["materia_chunk"],
                    **_classificacao(item),
                    "offset_inicio_secao": None,
                    "offset_fim_secao": None,
                    "chars": None,
                    "texto_enviado_llm": None,
                    "status": "sucesso",
                },
                pk="id",
                foreign_keys=[("edital", "editais", "edital")],
                columns=TIPOS_COLUNAS_CLASSIFICACAO,
            )
            .last_pk
        )
        chunk_id_by_index[chave] = chunk_id
    for item in resultado["chunks_com_falha"]:
        db["chunks"].insert(
            {
                "edital": edital,
                "chunk_index": item.get("chunk_index"),
                "cargo": item["cargo"],
                "materia": item["materia_esperada"],
                **_classificacao(item),
                "offset_inicio_secao": None,
                "offset_fim_secao": None,
                "chars": None,
                "texto_enviado_llm": None,
                "status": "falha",
            },
            pk="id",
            foreign_keys=[("edital", "editais", "edital")],
            columns=TIPOS_COLUNAS_CLASSIFICACAO,
        )
    return chunk_id_by_index


def _inserir_taxonomia(
    db: sqlite_utils.Database,
    edital: str,
    resultado: dict,
    chunk_id_by_index: dict[int, int],
) -> None:
    concurso = _concurso(resultado)
    for posicao, item in enumerate(resultado["resultados"]):
        chave = item["chunk_index"] if item.get("chunk_index") is not None else posicao
        chunk_id = chunk_id_by_index.get(chave)
        taxonomia = item["taxonomia_extraida"]
        for topico_ordem, topico in enumerate(taxonomia.get("topicos", [])):
            topico_id = (
                db["taxonomia_topicos"]
                .insert(
                    {
                        "edital": edital,
                        # Concurso e classificação desnormalizados aqui de
                        # propósito: é a tabela que se filtra no Datasette
                        # (facet por concurso/nível/tipo sem precisar de join).
                        **concurso,
                        "chunk_id": chunk_id,
                        "cargo": item["cargo"],
                        "materia_chunk": item["materia_chunk"],
                        **_classificacao(item),
                        "materia_extraida": taxonomia.get("materia"),
                        "topico_nome": topico["nome"],
                        "topico_ordem": topico_ordem,
                    },
                    pk="id",
                    foreign_keys=[("chunk_id", "chunks", "id")],
                    columns={**TIPOS_COLUNAS_CLASSIFICACAO, "ano": int},
                )
                .last_pk
            )
            for subtopico_ordem, subtopico in enumerate(topico.get("subtopicos", [])):
                db["taxonomia_subtopicos"].insert(
                    {
                        "topico_id": topico_id,
                        "subtopico_nome": subtopico,
                        "subtopico_ordem": subtopico_ordem,
                    },
                    pk="id",
                    foreign_keys=[("topico_id", "taxonomia_topicos", "id")],
                )


def _inserir_cargos(db: sqlite_utils.Database, edital: str, resultado: dict) -> None:
    for cargo in resultado.get("cargos") or []:
        db["cargos"].insert(
            {"edital": edital, **_concurso(resultado), **cargo},
            pk="id",
            foreign_keys=[("edital", "editais", "edital")],
        )


def _inserir_alertas_validacao(
    db: sqlite_utils.Database,
    edital: str,
    validacao: dict,
    chunk_id_by_index: dict[int, int],
) -> None:
    for alerta in validacao.get("alertas", []):
        chunk_index = alerta.get("chunk_index")
        db["alertas_validacao"].insert(
            {
                "edital": edital,
                "chunk_id": chunk_id_by_index.get(chunk_index)
                if chunk_index is not None
                else None,
                "chunk_index": chunk_index,
                "cargo": alerta.get("cargo"),
                "materia": alerta.get("materia"),
                "tipo": alerta["tipo"],
                "severidade": alerta.get("severidade", "bloqueante"),
                "numero_item": alerta.get("numero_item"),
                "texto_item_origem": alerta.get("texto_item_origem"),
                "topico_nome_extraido": alerta.get("topico_nome_extraido"),
            },
            pk="id",
            foreign_keys=[
                ("edital", "editais", "edital"),
                ("chunk_id", "chunks", "id"),
            ],
        )


def gerar_db(revisao_dir: Path = REVISAO_DIR_PADRAO) -> Path:
    db_path = revisao_dir / DB_NOME
    db_path.unlink(missing_ok=True)
    db = sqlite_utils.Database(db_path)

    jsons = sorted(
        p
        for p in revisao_dir.glob("*.json")
        if not p.name.endswith(".auditoria.json")
        and not p.name.endswith(".validacao.json")
    )
    if not jsons:
        logger.warning(
            f"Nenhum <edital>.json encontrado em {revisao_dir} — banco gerado vazio."
        )

    for json_path in jsons:
        resultado, auditoria, auditoria_path, validacao = _carregar_par(json_path)
        edital = resultado["edital"]

        _inserir_edital(db, resultado, auditoria, json_path, auditoria_path, validacao)

        if auditoria is not None:
            chunk_id_by_index = _inserir_chunks_com_auditoria(db, edital, auditoria)
        else:
            chunk_id_by_index = _inserir_chunks_sem_auditoria(db, edital, resultado)

        _inserir_taxonomia(db, edital, resultado, chunk_id_by_index)
        _inserir_cargos(db, edital, resultado)

        if validacao is not None:
            _inserir_alertas_validacao(db, edital, validacao, chunk_id_by_index)

        logger.info(
            f"{edital}: {resultado['total_chunks']} chunks carregados no banco de revisão."
        )

    for tabela, colunas in (
        ("chunks", ["texto_enviado_llm", "materia", "cargo"]),
        ("taxonomia_topicos", ["topico_nome", "materia_extraida", "materia_chunk"]),
        ("taxonomia_subtopicos", ["subtopico_nome"]),
    ):
        if db[tabela].exists():
            db[tabela].enable_fts(colunas, create_triggers=False)

    logger.info(f"Banco de revisão gerado em {db_path} — {len(jsons)} edital(is).")
    return db_path


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    gerar_db(diretorio)
