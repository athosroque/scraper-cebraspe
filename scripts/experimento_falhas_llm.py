"""Experimento controlado sobre os chunks que falharam na extração real.

**Custa tokens reais — nunca rodar sem confirmação explícita do usuário.**
Ver CLAUDE.md seção 12 / task.md Etapa 4.

Carrega os textos reais dos chunks que falharam a partir do
`<edital>.auditoria.json` já em disco (não reprocessa os 39 chunks) e roda
cada um contra configurações candidatas, isolando o efeito de cada uma:

- `baseline`: configuração de produção atual (max_tokens=8192, timeout=120,
  sem override de reasoning).
- `max_tokens_e_timeout_maiores`: max_tokens=24576, timeout=240.
- `reasoning_desligado`: `thinking: {"type": "disabled"}` no payload —
  requer validação ao vivo se o z-ai (via OpenRouter) realmente obedece;
  ver CLAUDE.md seção 12.
- `reasoning_desligado_texto_limpo`: reasoning desligado + texto passado
  por `_limpar_ruido_edital` (só muda o resultado pro chunk que tem nota de
  retificação embutida).

Cada chamada usa `tentativas=1` (sem retry) de propósito: o objetivo aqui é
isolar o efeito de cada mitigação isoladamente. Retry já está ligado por
padrão em produção (`extrair_taxonomia_chunk`) e foi validado separadamente
comparando dois runs reais completos — não precisa ser reprovado aqui. Isso
mantém o teto em exatamente 5 chunks x 4 configs = 20 chamadas reais.

Uso:
    python -m scripts.experimento_falhas_llm [caminho_auditoria.json]
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.edital_parser import _limpar_ruido_edital
from src.logger import logger
from src.taxonomia_extractor import extrair_taxonomia_chunk

AUDITORIA_PADRAO = (
    Path(__file__).resolve().parent.parent
    / "revisao_piloto"
    / "Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.auditoria.json"
)
SAIDA_PADRAO = (
    Path(__file__).resolve().parent.parent
    / "revisao_piloto"
    / "experimento_falhas.json"
)

CONFIGURACOES: dict[str, dict] = {
    "baseline": {},
    "max_tokens_e_timeout_maiores": {"max_tokens": 24576, "timeout": 240},
    "reasoning_desligado": {"reasoning": {"thinking": {"type": "disabled"}}},
    "reasoning_desligado_texto_limpo": {
        "reasoning": {"thinking": {"type": "disabled"}},
        "limpar_texto": True,
    },
}


def carregar_chunks_com_falha(auditoria_path: Path) -> list[dict]:
    auditoria = json.loads(auditoria_path.read_text(encoding="utf-8"))
    falhas = [c for c in auditoria["chunks"] if c["status"] == "falha"]
    if not falhas:
        logger.warning(
            f"Nenhum chunk com status=falha encontrado em {auditoria_path.name}."
        )
    return falhas


def rodar_experimento(
    auditoria_path: Path = AUDITORIA_PADRAO, saida_path: Path = SAIDA_PADRAO
) -> dict:
    chunks_falhos = carregar_chunks_com_falha(auditoria_path)
    total_chamadas = len(chunks_falhos) * len(CONFIGURACOES)
    logger.info(
        f"{len(chunks_falhos)} chunks com falha x {len(CONFIGURACOES)} configs "
        f"= {total_chamadas} chamadas reais ao LLM."
    )

    resultados = []
    for chunk in chunks_falhos:
        for nome_config, params_config in CONFIGURACOES.items():
            params = dict(params_config)
            limpar = params.pop("limpar_texto", False)
            texto = (
                _limpar_ruido_edital(chunk["texto_enviado_llm"])
                if limpar
                else chunk["texto_enviado_llm"]
            )

            logger.info(
                f"[{chunk['cargo'] or 'sem cargo'} / {chunk['materia']}] config={nome_config}"
            )
            taxonomia = extrair_taxonomia_chunk(texto, tentativas=1, **params)
            status = "sucesso" if taxonomia is not None else "falha"
            logger.info(f"  -> {status}")

            resultados.append(
                {
                    "chunk_index": chunk["chunk_index"],
                    "cargo": chunk["cargo"],
                    "materia": chunk["materia"],
                    "configuracao": nome_config,
                    "status": status,
                    "topicos_extraidos": len(taxonomia.topicos) if taxonomia else None,
                }
            )

    saida = {"auditoria_origem": str(auditoria_path), "resultados": resultados}
    saida_path.write_text(
        json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Resultado do experimento salvo em {saida_path}")

    _imprimir_resumo(resultados)
    return saida


def _imprimir_resumo(resultados: list[dict]) -> None:
    total_por_config: Counter = Counter()
    sucesso_por_config: Counter = Counter()
    for r in resultados:
        total_por_config[r["configuracao"]] += 1
        if r["status"] == "sucesso":
            sucesso_por_config[r["configuracao"]] += 1

    print("\nResumo por configuração:")
    for config in CONFIGURACOES:
        total = total_por_config[config]
        sucesso = sucesso_por_config[config]
        print(f"  {config}: {sucesso}/{total} sucesso")


if __name__ == "__main__":
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else AUDITORIA_PADRAO
    rodar_experimento(caminho)
