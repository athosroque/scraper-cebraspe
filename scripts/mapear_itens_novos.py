"""Mapeia item novo de edital para a árvore mestre pelo LLM (lista fechada).

Uso:
    python -m scripts.mapear_itens_novos [--concurso SLUG] [--dry-run]
        [--reavaliar] [--limite N] [--arvore caminho] [revisao_dir]

Item de edital (matéria, tópico, subtópico) sem entrada em `arvore.mapeamentos`,
que `canonico.mapear_novos_itens_por_regra` não resolveu, recebe do modelo uma
proposta de nó EXISTENTE da disciplina dele ou "nenhum". O resultado é gravado
como `origem="llm"`, `status="proposto"` (A30): o dono aprova com
`scripts/curar_arvore.py`. O modelo nunca cria nó nem disciplina (P72).

A memória das decisões do dono (`src/memoria_mapeamento.py`, P73) já faz parte do passo
determinístico: este script só garante que ele rodou (idempotente) e trata o que sobrar.
O prompt leva o contexto dos subitens, exemplos aprovados e os pares rejeitados; o resumo
(`por_origem`) mostra de onde saiu o nó de cada item: cada ramo do passo determinístico,
o LLM, sem candidato ou cache do "nenhum".

`--dry-run` não chama o LLM nem grava: mostra quantos itens estão pendentes e uma
estimativa de custo. Simula a cascata entre níveis (M13, KAN-90): a sugestão top-1 do
ranking entra só em memória e serve de pai ao nível seguinte, como a proposta do LLM no
modo real. Chamada via `chamar_llm_json` com `REASONING_PADRAO`
(P16) e `nome_trace="mapear_itens_novos"`. A lógica fica em `src/mapeamento_llm.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import mapeamento_llm

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
ARVORE_PATH_PADRAO = Path(__file__).resolve().parent.parent / "canonico" / "arvore.json"

# Estimativa do dry-run: ~3,3 caracteres por token em português e saída curta por item.
CARACTERES_POR_TOKEN = 3.3
TOKENS_SAIDA_POR_ITEM = 60
# Reasoning ocupa até REASONING_PADRAO.max_tokens (3000) por chamada, no pior caso.
TOKENS_REASONING_POR_CHAMADA = 3000


def estimar(conta: mapeamento_llm.Contabilidade, itens: int) -> dict:
    tokens_entrada = int(conta.caracteres_previstos / CARACTERES_POR_TOKEN)
    tokens_saida = (
        itens * TOKENS_SAIDA_POR_ITEM
        + conta.chamadas_previstas * TOKENS_REASONING_POR_CHAMADA
    )
    return {
        "chamadas_previstas": conta.chamadas_previstas,
        "tokens_entrada_estimados": tokens_entrada,
        "tokens_saida_estimados_pior_caso": tokens_saida,
    }


def por_origem(conta: mapeamento_llm.Contabilidade, dry_run: bool) -> dict:
    """De onde sai (ou sairia) o nó de cada item (M13, KAN-90). Os ramos do passo
    determinístico contam o que ele resolveu nesta execução; os pendentes depois
    dele vão ao LLM, ficam sem candidato ou já estão no cache do "nenhum"."""
    origem = {
        "regra_de_nome": conta.resolvidos_regra,
        "memoria_do_dono": conta.resolvidos_memoria,
        "filho_unico": conta.resolvidos_filho_unico,
        "heranca": conta.resolvidos_heranca,
        "casamento_global": conta.resolvidos_global,
        "proposto_por_regra": conta.propostos_regra,
    }
    if dry_run:
        origem["llm_previstos"] = conta.itens_previstos
    else:
        origem["llm_propostos"] = conta.propostos
        origem["llm_nenhum"] = conta.nenhum
    origem["sem_candidatos"] = conta.sem_candidatos
    origem["cache_nenhum"] = conta.pulados_cache
    return origem


def main(args_list: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("revisao_dir", nargs="?", type=Path, default=REVISAO_DIR_PADRAO)
    parser.add_argument(
        "--concurso", help="Só itens que aparecem neste concurso (ex: SEFA_PR_25)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sem chamada ao LLM e sem gravar: conta pendentes e estima o custo",
    )
    parser.add_argument(
        "--reavaliar",
        action="store_true",
        help='Pergunta de novo os itens que o modelo já respondeu "nenhum"',
    )
    parser.add_argument("--limite", type=int, help="Máximo de lotes (chamadas) a rodar")
    parser.add_argument("--arvore", type=Path, default=ARVORE_PATH_PADRAO)
    args = parser.parse_args(args_list)

    conta = mapeamento_llm.mapear_itens_novos(
        args.revisao_dir,
        args.arvore,
        concurso=args.concurso,
        dry_run=args.dry_run,
        reavaliar=args.reavaliar,
        limite=args.limite,
    )
    saida = {
        "pendentes": conta.pendentes,
        "pulados_cache_nenhum": conta.pulados_cache,
        "por_origem": por_origem(conta, args.dry_run),
        "lotes_sem_disciplina": conta.lotes_sem_disciplina,
    }
    if args.dry_run:
        saida["simulados_top1_cascata"] = conta.simulados_top1
        saida.update(estimar(conta, conta.itens_previstos))
    else:
        saida.update(
            {
                "propostos_por_llm": conta.propostos,
                "sem_no": conta.pendentes - conta.propostos,
                "nenhum": conta.nenhum,
                "descartados_par_rejeitado": conta.descartados_rejeitados,
                "recusados_na_gravacao": conta.rejeitados_gravacao,
                "chamadas": conta.chamadas,
                "lotes_ok": conta.lotes_ok,
                "lotes_falhos": conta.lotes_falhos,
                "tokens_entrada": conta.tokens_entrada,
                "tokens_saida": conta.tokens_saida,
                "custo_usd": conta.custo_usd,
                "confianca": dict(conta.confianca),
                "falhas": dict(conta.falhas),
            }
        )
    print(json.dumps(saida, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
