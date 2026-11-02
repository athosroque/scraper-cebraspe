"""De onde veio cada mapeamento de item de edital para nó da árvore (revisão).

Função pura, sem LLM e sem gravar: classifica todo item (disciplina, assunto,
subassunto) de um `<edital>.json` em uma de quatro categorias, para o relatório
de revisão e para a tabela `mapeamento_itens` do `revisao.db` (Datasette).

Não há critério de equivalência próprio (M1, Etapa 5B.4): só vale mapeamento
aprovado na árvore recebida. Quem chama passa a árvore já com o passo
determinístico aplicado (`canonico.arvore_apos_passo`), então o que o passo
mapeia aparece como `auto`/`dono` e o resto como `proposta` ou `sem_equivalente`,
exatamente o que `mapear_novos_itens` deixa pendente (P72, ADR-030).

Categorias (`categoria`):
- `auto`: mapeamento aprovado de `origem="regra"`. A memória das decisões do
  dono grava com a mesma origem, então regra de nome gravada e memória não se
  distinguem na proveniência: o rótulo é "automático (regra/memória)".
- `dono`: aprovado por decisão humana ou pela semente (grupos aprovados da 5B).
- `proposta`: proposto pela IA (`origem="llm"`, status `proposto`), a conferir;
  confiança e justificativa vêm do cache de `src/mapeamento_llm.py`, se houver.
- `sem_equivalente`: nada aprovado nem proposto; o dono precisa decidir.
"""

import json
from pathlib import Path

from src import arvore as arv_mod
from src.canonico import normalizar
from src.logger import logger
from src.novidades_edital import _caminho, _nos_aprovados, _proposto
from src.stats_writer import montar_carga_concurso

CACHE_PADRAO = arv_mod.PROJETO_DIR / "canonico" / ".mapear_itens_novos_cache.json"

ROTULOS = {
    "auto": "automático (regra/memória)",
    "dono": "decisão sua / semente",
    "proposta": "proposto pela IA (a conferir)",
    "sem_equivalente": "sem equivalente (a decidir)",
}
CATEGORIAS = tuple(ROTULOS)


def carregar_cache_propostos(path: Path = CACHE_PADRAO) -> dict[str, dict]:
    """`propostos` do cache do mapeamento por LLM; vazio se ausente/corrompido."""
    try:
        dados = json.loads(Path(path).read_text(encoding="utf-8"))
        propostos = dados.get("propostos") or {}
        return {k: v for k, v in propostos.items() if isinstance(v, dict)}
    except (OSError, ValueError, AttributeError):
        return {}


def _categoria_aprovada(origem: str) -> str:
    return "auto" if origem == "regra" else "dono"


def classificar_itens(
    resultado: dict,
    arvore: arv_mod.ArvoreMestre | None = None,
    propostos: dict[str, dict] | None = None,
    disciplinas_conhecidas: list[str] | None = None,  # compatibilidade; sem efeito
) -> list[dict]:
    """Uma linha por item distinto do edital (ordem de aparição).

    Campos: `edital`, `nivel`, `item`, `disciplina`, `assunto`, `chave`,
    `no_id`, `no_caminho`, `origem`, `status`, `categoria`, `confianca`,
    `justificativa`. Para `sem_equivalente`, `status` é `sem_equivalente`.
    """
    if arvore is None:
        arvore = arv_mod.carregar()
    if propostos is None:
        propostos = carregar_cache_propostos()

    def resolver(chave: str):
        """(nós, categoria, origem, status, mapeamento)."""
        aprovados = [
            m
            for m in arvore.mapeamentos.get(chave, [])
            if m.status == "aprovado"
            and arv_mod.resolver_no(arvore, m.no_id) in arvore.nos
        ]
        if aprovados:
            nos = _nos_aprovados(arvore, chave)
            m = aprovados[0]
            return nos, _categoria_aprovada(m.origem), m.origem, "aprovado", m
        m = _proposto(arvore, chave)
        if m is not None:
            return (
                {arv_mod.resolver_no(arvore, m.no_id)},
                "proposta",
                m.origem,
                "proposto",
                m,
            )
        return set(), "sem_equivalente", None, "sem_equivalente", None

    edital = resultado.get("edital")
    linhas: dict[str, dict] = {}

    def registrar(chave, nivel, nome, disc, ass, nos, cat, origem, status, m):
        if chave in linhas:
            return
        no_id = sorted(nos)[0] if nos else None
        info = (propostos.get(chave) or {}) if cat == "proposta" else {}
        confianca = info.get("confianca") or getattr(m, "confianca", None)
        linhas[chave] = {
            "edital": edital,
            "nivel": nivel,
            "item": nome,
            "disciplina": disc,
            "assunto": ass,
            "chave": chave,
            "no_id": no_id,
            "no_caminho": _caminho(arvore, no_id) if no_id else None,
            "origem": origem,
            "status": status,
            "categoria": cat,
            "confianca": confianca,
            "justificativa": info.get("justificativa"),
        }

    for item in montar_carga_concurso(resultado)["itens"]:
        m_chave, m_nome = item["materia_chave"], item["materia_nome"]
        chave_m = arv_mod.chave_item(m_chave)
        nos_m, *res_m = resolver(chave_m)
        registrar(chave_m, "disciplina", m_nome, m_nome, None, nos_m, *res_m)

        t_chave = item["topico_chave"]
        chave_t = arv_mod.chave_item((m_chave, t_chave))
        nos_t, *res_t = resolver(chave_t)
        registrar(chave_t, "assunto", item["topico_nome"], m_nome, None, nos_t, *res_t)

        for sub in item["subtopicos"]:
            s_chave = normalizar(sub)
            if not s_chave:
                continue
            chave_s = arv_mod.chave_item((m_chave, t_chave, s_chave))
            nos_s, *res_s = resolver(chave_s)
            registrar(
                chave_s,
                "subassunto",
                sub,
                m_nome,
                item["topico_nome"],
                nos_s,
                *res_s,
            )
    return list(linhas.values())


def classificar_seguro(resultado: dict, **kwargs) -> list[dict]:
    """Como `classificar_itens`, mas nunca levanta: falha vira lista vazia."""
    try:
        return classificar_itens(resultado, **kwargs)
    except Exception as erro:  # noqa: BLE001
        logger.warning(
            f"{resultado.get('edital')}: mapeamento não classificado: {erro}"
        )
        return []


def contar_por_categoria(linhas: list[dict]) -> dict[str, int]:
    contagem = dict.fromkeys(CATEGORIAS, 0)
    for linha in linhas:
        contagem[linha["categoria"]] += 1
    return contagem


COLUNAS_TABELA = (
    "edital",
    "nivel",
    "item",
    "no_id",
    "no_caminho",
    "origem",
    "status",
    "confianca",
    "justificativa",
)


def inserir_mapeamento_itens(db, linhas: list[dict]) -> None:
    """Acrescenta `linhas` à tabela `mapeamento_itens` do `revisao.db`."""
    if not linhas:
        return
    db["mapeamento_itens"].insert_all(
        [
            {
                **{c: linha.get(c) for c in COLUNAS_TABELA},
                "disciplina": linha["disciplina"],
            }
            for linha in linhas
        ],
        columns={"confianca": str, "justificativa": str, "no_id": str},
    )


def criar_tabela_vazia(db) -> None:
    """Garante a tabela mesmo sem linhas, para o Datasette não dar 404."""
    if not db["mapeamento_itens"].exists():
        db["mapeamento_itens"].create(
            {
                "edital": str,
                "nivel": str,
                "item": str,
                "no_id": str,
                "no_caminho": str,
                "origem": str,
                "status": str,
                "confianca": str,
                "justificativa": str,
                "disciplina": str,
            }
        )


__all__ = [
    "CACHE_PADRAO",
    "CATEGORIAS",
    "ROTULOS",
    "carregar_cache_propostos",
    "classificar_itens",
    "classificar_seguro",
    "contar_por_categoria",
    "criar_tabela_vazia",
    "inserir_mapeamento_itens",
]
