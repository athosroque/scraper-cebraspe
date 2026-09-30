from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.modelos import (
    FacetasResponse,
    FiltroQuestoes,
    NoArvore,
    PaginaQuestoes,
    QuestaoDetalhe,
)
from app.servicos import questoes_servico

router = APIRouter(prefix="/questoes", tags=["Questões"])


@router.get(
    "",
    response_model=PaginaQuestoes,
    summary="Lista questões objetivas com filtros",
    description=(
        "Uma entrada por questão (cargos e nós agregados), ordenada por concurso, "
        "caderno e número. Os filtros combinam com E. Sem filtro, devolve as 2.781 "
        "questões objetivas utilizáveis do piloto 2025 (2.800 com `utilizaveis=todas`)."
    ),
)
def listar_questoes(
    banca: str | None = Query(None, description="Banca (ex.: `CEBRASPE`)."),
    orgao: str | None = Query(
        None, description="Órgão (ex.: `PF`, `STM`). Valores em `/facetas`."
    ),
    ano: int | None = Query(None, description="Ano do concurso (ex.: `2025`)."),
    concurso: str | None = Query(
        None, description="Slug do concurso (ex.: `PF_25_ADM`)."
    ),
    cargo_numero: int | None = Query(
        None, description="Número do cargo no edital. Use junto com `concurso`."
    ),
    nivel: str | None = Query(None, description="`superior` ou `medio`."),
    tipo_conhecimento: str | None = Query(
        None, description="`basico` ou `especifico`."
    ),
    no_id: str | None = Query(
        None,
        description="Nó da árvore (`/arvore`). Matéria ou assunto incluem as questões dos descendentes.",
        examples=["S-c33faee4a4"],
    ),
    anuladas: Literal["incluir", "excluir", "so"] = Query(
        "incluir", description="Tratamento das questões anuladas."
    ),
    fora_do_edital: Literal["todos", "sim", "nao"] = Query(
        "todos",
        description="`sim`: só questões classificadas fora do edital do cargo; `nao`: só dentro.",
    ),
    utilizaveis: Literal["so", "todas"] = Query(
        "so",
        description=(
            "`so` (padrão): esconde as questões com extração ilegível (`utilizavel=false`, "
            "ex.: fórmulas do caderno de Estatística da PF). `todas`: inclui, para revisão."
        ),
    ),
    pagina: int = Query(1, ge=1, description="Página, a partir de 1."),
    tamanho_pagina: int = Query(
        20, ge=1, le=50, description="Itens por página (máx. 50)."
    ),
):
    filtros = FiltroQuestoes(
        banca=banca,
        orgao=orgao,
        ano=ano,
        concurso=concurso,
        cargo_numero=cargo_numero,
        nivel=nivel,
        tipo_conhecimento=tipo_conhecimento,
        no_id=no_id,
        anuladas=anuladas,
        fora_do_edital=fora_do_edital,
        utilizaveis=utilizaveis,
    )
    return questoes_servico.listar_questoes(filtros, pagina, tamanho_pagina)


@router.get(
    "/{chave}",
    response_model=QuestaoDetalhe,
    summary="Detalhe de uma questão",
    description="Busca pela chave estável `concurso|caderno|numero`.",
    responses={404: {"description": "Questão não encontrada"}},
)
def obter_questao(chave: str):
    questao = questoes_servico.obter_questao_por_chave(chave)
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return questao


router_arvore = APIRouter(prefix="/arvore", tags=["Árvore"])


@router_arvore.get(
    "",
    response_model=list[NoArvore],
    summary="Árvore mestre com contagem de questões",
    description="Matéria → assunto → subassunto. A contagem é de questões distintas e sobe a árvore.",
)
def obter_arvore(
    apenas_com_questoes: bool = Query(
        True, description="Omite nós sem nenhuma questão."
    ),
):
    return questoes_servico.obter_arvore(apenas_com_questoes)


router_facetas = APIRouter(prefix="/facetas", tags=["Facetas"])


@router_facetas.get(
    "",
    response_model=FacetasResponse,
    summary="Valores possíveis dos filtros",
    description="Cada valor vem com o total de questões distintas, para montar os filtros da interface.",
)
def obter_facetas():
    return questoes_servico.obter_facetas()
