"""Reprocessa chunks com falha e consolida o edital piloto (Etapa 4, task.md).

Lê o resultado e a trilha de auditoria do edital piloto, identifica os chunks
que falharam na extração anterior e reexecuta a chamada ao OpenRouter com os novos
defaults (max_tokens=24576, timeout=240s, retry com backoff).

Também aceita forçar o reprocessamento de `chunk_index` específicos mesmo
com `status="sucesso"` (`--chunks`) — usado para corrigir chunks
estruturalmente válidos mas semanticamente malformados (ex.: `nome` de
tópico puramente numérico, ver ADR-021) que não são pegos pelo filtro
normal de falha.

Cria backup (.bak) antes da primeira alteração e salva incrementalmente
a cada chunk bem-sucedido. Ao final, chama `scripts.atualizar_revisao`
(validação de-para + relatório HTML + banco Datasette + restart do
container — ver ADR-019).

Uso:
    python -m scripts.reprocessar_falhas_piloto [caminho_do_json]
    python -m scripts.reprocessar_falhas_piloto [caminho_do_json] --chunks 17,21
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.atualizar_revisao import atualizar_artefatos_revisao
from src.edital_parser import CAMPOS_CLASSIFICACAO_CHUNK, remover_topicos_excluidos
from src.logger import logger
from src.taxonomia_extractor import extrair_taxonomia_chunk

JSON_PADRAO = (
    Path(__file__).resolve().parent.parent
    / "revisao_piloto"
    / "Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.json"
)


def _criar_backup_se_necessario(json_path: Path, auditoria_path: Path) -> None:
    """Cria cópia .bak dos JSONs se ainda não existirem."""
    bak_json = json_path.with_suffix(".json.bak")
    if json_path.exists() and not bak_json.exists():
        shutil.copy2(json_path, bak_json)
        logger.info(f"Backup criado: {bak_json.name}")

    if auditoria_path.exists():
        bak_auditoria = auditoria_path.parent / f"{auditoria_path.name}.bak"
        if not bak_auditoria.exists():
            shutil.copy2(auditoria_path, bak_auditoria)
            logger.info(f"Backup criado: {bak_auditoria.name}")


def _salvar_incremento(
    json_path: Path, resultado: dict, auditoria_path: Path, auditoria: dict
) -> None:
    """Salva os dois JSONs em disco garantindo consistência imediata."""
    json_path.write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    auditoria_path.write_text(
        json.dumps(auditoria, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def reprocessar_falhas(
    json_path: Path = JSON_PADRAO,
    *,
    chunk_indices_forcados: list[int] | None = None,
) -> dict:
    if not json_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {json_path}")

    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    if not auditoria_path.exists():
        raise FileNotFoundError(
            f"Auditoria correspondente não encontrada: {auditoria_path}"
        )

    _criar_backup_se_necessario(json_path, auditoria_path)

    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria = json.loads(auditoria_path.read_text(encoding="utf-8"))

    # Seleção normal: chunks marcados como falha técnica. Seleção forçada
    # (--chunks): reprocessa por chunk_index independente do status — usada
    # pra corrigir chunks "sucesso" mas semanticamente malformados (ADR-021),
    # que o filtro de falha nunca pegaria sozinho.
    if chunk_indices_forcados:
        indices_forcados = set(chunk_indices_forcados)
        chunks_selecionados = [
            c for c in auditoria["chunks"] if c.get("chunk_index") in indices_forcados
        ]
        indices_encontrados = {c.get("chunk_index") for c in chunks_selecionados}
        indices_nao_encontrados = indices_forcados - indices_encontrados
        if indices_nao_encontrados:
            logger.warning(
                f"chunk_index(es) não encontrado(s) em {json_path.name}: {sorted(indices_nao_encontrados)}"
            )
        motivo = "forçado(s) via --chunks"
    else:
        # Qualquer status que não seja "sucesso" conta como falha aqui —
        # não só o literal "falha" genérico, mas também status específicos
        # como `STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO` (ADR-021). Chunk sem
        # campo "status" (formato legado) fica de fora por segurança: não dá
        # pra saber se teve sucesso ou falha sem essa informação.
        chunks_selecionados = [
            c
            for c in auditoria["chunks"]
            if c.get("status") is not None and c.get("status") != "sucesso"
        ]
        motivo = "com falha"

    if not chunks_selecionados:
        logger.info(
            f"Nenhum chunk {motivo} em {json_path.name}. Totalmente consolidado!"
        )
        return resultado

    logger.info(
        f"Iniciando reprocessamento de {len(chunks_selecionados)} chunk(s) {motivo} em {json_path.name}."
    )

    sucessos_novos = 0
    falhas_persistentes = 0

    for idx, chunk in enumerate(chunks_selecionados, 1):
        chunk_index = chunk["chunk_index"]
        cargo = chunk.get("cargo")
        materia = chunk.get("materia")
        texto = chunk["texto_enviado_llm"]
        # Itens excluídos por retificação saem antes do LLM e o texto limpo fica
        # na auditoria, para bater com o parser (o backfill exige prefixo igual).
        texto_limpo = remover_topicos_excluidos(texto)
        if texto_limpo != texto:
            texto = texto_limpo
            chunk["texto_enviado_llm"] = texto

        logger.info(
            f"[{idx}/{len(chunks_selecionados)}] Reprocessando chunk #{chunk_index} "
            f"({cargo or 'sem cargo'} — {materia}) [{len(texto)} chars]..."
        )

        taxonomia, motivo_falha = extrair_taxonomia_chunk(texto)
        if taxonomia is None:
            status_falha = motivo_falha or "falha"
            logger.error(
                f"  -> Chunk #{chunk_index} não pôde ser reprocessado com sucesso ({status_falha})."
            )
            # Atualiza o status mesmo na falha — necessário pro reprocessamento
            # forçado (--chunks) de um chunk que estava "sucesso" (malformado):
            # sem isso, uma falha na nova tentativa deixava o status antigo
            # "sucesso" mentindo sobre o resultado desta rodada (ver ADR-021).
            for c in auditoria["chunks"]:
                if c.get("chunk_index") == chunk_index:
                    c["status"] = status_falha
                    break
            _salvar_incremento(json_path, resultado, auditoria_path, auditoria)
            falhas_persistentes += 1
            continue

        logger.info(
            f"  -> Chunk #{chunk_index} extraído com sucesso! "
            f"({len(taxonomia.topicos)} tópicos extraídos)"
        )
        sucessos_novos += 1

        # Atualiza resultado
        novo_item = {
            "chunk_index": chunk_index,
            "cargo": cargo,
            "materia_chunk": materia,
            **{
                campo: chunk[campo]
                for campo in CAMPOS_CLASSIFICACAO_CHUNK
                if campo in chunk
            },
            "taxonomia_extraida": taxonomia.model_dump(),
        }
        # Substitui se já existir, senão adiciona
        resultados_atuais = [
            r for r in resultado["resultados"] if r.get("chunk_index") != chunk_index
        ]
        resultados_atuais.append(novo_item)
        resultados_atuais.sort(key=lambda x: x.get("chunk_index", 0))
        resultado["resultados"] = resultados_atuais

        # Remove da lista de chunks_com_falha
        resultado["chunks_com_falha"] = [
            f
            for f in resultado.get("chunks_com_falha", [])
            if f.get("chunk_index") != chunk_index
        ]
        resultado["extraidos_com_sucesso"] = len(resultado["resultados"])
        resultado["falhas"] = len(resultado["chunks_com_falha"])

        # Atualiza auditoria
        for c in auditoria["chunks"]:
            if c.get("chunk_index") == chunk_index:
                c["status"] = "sucesso"
                break

        # Persistência incremental imediata
        _salvar_incremento(json_path, resultado, auditoria_path, auditoria)
        logger.info(
            f"  -> Progresso persistido incrementalmente ({resultado['extraidos_com_sucesso']}/{resultado['total_chunks']})."
        )

    logger.info(
        f"Reprocessamento concluído: {sucessos_novos} novo(s) sucesso(s), "
        f"{falhas_persistentes} falha(s) persistente(s)."
    )

    if sucessos_novos > 0:
        atualizar_artefatos_revisao(json_path.parent)

    return resultado


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "json_path",
        nargs="?",
        type=Path,
        default=JSON_PADRAO,
        help="Caminho do <edital>.json",
    )
    parser.add_argument(
        "--chunks",
        type=str,
        default=None,
        help="chunk_index separados por vírgula a forçar mesmo com status=sucesso (ex.: --chunks 17,21)",
    )
    args = parser.parse_args()

    indices = [int(i) for i in args.chunks.split(",")] if args.chunks else None
    reprocessar_falhas(args.json_path, chunk_indices_forcados=indices)
