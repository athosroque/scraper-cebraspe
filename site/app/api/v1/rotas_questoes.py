from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request

from app.api.v1.respostas_comuns import R401, r404
from app.auth import usuario_id_atual
from app.modelos import (
    FacetasResponse,
    FiltroQuestoes,
    NoArvore,
    PaginaQuestoes,
    QuestaoDetalhe,
    QuestaoResumo,
)
from app.servicos import questoes_servico
from app.servicos.contas_servico import LoginNecessario

router = APIRouter(prefix="/questoes", tags=["Questões"])


@router.get(
    "",
    response_model=PaginaQuestoes,
    summary="Lista questões objetivas com filtros",
    responses=R401,
    description=(
        "Uma entrada por questão (cargos e nós agregados), ordenada por concurso, "
        "caderno e número. Cada filtro aceita vários valores (parâmetro repetido, "
        "ex.: `?ano=2025&ano=2024`), que combinam com OU; filtros diferentes "
        "combinam com E. Sem filtro, devolve as 2.781 "
        "questões objetivas utilizáveis do piloto 2025 (2.800 com `utilizaveis=todas`)."
    ),
)
def listar_questoes(
    request: Request,
    banca: Annotated[
        list[str] | None,
        Query(description="Banca (ex.: `CEBRASPE`). Repita para várias (OU)."),
    ] = None,
    orgao: Annotated[
        list[str] | None,
        Query(
            description="Órgão (ex.: `PF`, `STM`). Repita para vários (OU). Valores em `/facetas`.",
        ),
    ] = None,
    ano: Annotated[
        list[int] | None,
        Query(description="Ano do concurso (ex.: `2025`). Repita para vários (OU)."),
    ] = None,
    concurso: Annotated[
        list[str] | None,
        Query(
            description="Slug do concurso (ex.: `PF_25_ADM`). Repita para vários (OU)."
        ),
    ] = None,
    cargo: Annotated[
        list[str] | None,
        Query(
            description=(
                "Cargo como `CONCURSO:NUMERO` (ex.: `PF_25_ADM:1`). Repita para vários "
                "(OU), inclusive de concursos diferentes. Valores em `/facetas` (`cargos[].valor`)."
            ),
        ),
    ] = None,
    cargo_numero: Annotated[
        list[int] | None,
        Query(
            description="Número do cargo no edital, junto com `concurso` (forma antiga; prefira `cargo`).",
        ),
    ] = None,
    nivel: Annotated[
        list[str] | None,
        Query(description="`superior` ou `medio`. Repita para os dois (OU)."),
    ] = None,
    tipo_conhecimento: Annotated[
        list[str] | None,
        Query(description="`basico` ou `especifico`. Repita para os dois (OU)."),
    ] = None,
    no_id: Annotated[
        list[str] | None,
        Query(
            description=(
                "Nó da árvore (`/arvore`), em qualquer nível. Matéria ou assunto incluem as "
                "questões dos descendentes. Repita para vários (OU)."
            ),
            examples=["S-c33faee4a4"],
        ),
    ] = None,
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
    historico: Literal[
        "todas", "resolvidas", "nao_resolvidas", "certas", "erradas"
    ] = Query(
        "todas",
        description=(
            "Filtra pelo histórico do usuário logado (resposta mais recente de cada "
            "questão). Diferente de `todas` sem login: 401."
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
        cargo=cargo,
        cargo_numero=cargo_numero,
        nivel=nivel,
        tipo_conhecimento=tipo_conhecimento,
        no_id=no_id,
        anuladas=anuladas,
        fora_do_edital=fora_do_edital,
        utilizaveis=utilizaveis,
        historico=historico,
    )
    try:
        return questoes_servico.listar_questoes(
            filtros, pagina, tamanho_pagina, usuario_id_atual(request)
        )
    except LoginNecessario:
        raise HTTPException(status_code=401, detail="Login necessário") from None


@router.get(
    "/{chave}",
    response_model=QuestaoDetalhe,
    summary="Detalhe de uma questão",
    description="Busca pela chave estável `concurso|caderno|numero`.",
    responses=r404("Questão não encontrada."),
)
def obter_questao(
    chave: str = Path(
        description="Chave estável `concurso|caderno|numero` (codifique `|` como `%7C`).",
        examples=["PF_25_ADM|094_PF_CB1_01|1"],
    ),
):
    questao = questoes_servico.obter_questao_por_chave(chave)
    if not questao:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return questao


@router.get(
    "/{chave}/parecidas",
    response_model=list[QuestaoResumo],
    summary="Questões parecidas",
    description=(
        "Questões do mesmo nó principal da árvore, sem a própria e sem repetir "
        "enunciado canônico (o mesmo item aplicado em outro caderno aparece uma "
        "vez só, e o da própria questão não aparece). Só utilizáveis, na ordem "
        "da listagem. Lista vazia se a questão não foi classificada."
    ),
    responses={
        404: {
            "description": "Questão não encontrada",
            "content": {
                "application/json": {"example": {"detail": "Questão não encontrada"}}
            },
        }
    },
)
def obter_parecidas(
    chave: str = Path(
        description="Chave estável `concurso|caderno|numero`.",
        examples=["PF_25_ADM|094_PF_CB1_01|13"],
    ),
    limite: int = Query(5, ge=1, le=20, description="Máximo de questões (até 20)."),
):
    """Questões do mesmo nó principal, para continuar estudando o assunto."""
    parecidas = questoes_servico.parecidas(chave, limite)
    if parecidas is None:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return parecidas


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
    description=(
        "Cada valor vem com o total de questões distintas, para montar os filtros da "
        "interface. Aceita os mesmos filtros da listagem: o total de cada valor "
        "considera os outros filtros (não o próprio), e um valor marcado aparece "
        "mesmo com total 0. Sem filtro, conta as questões utilizáveis."
    ),
    responses=R401,
)
def obter_facetas(
    request: Request,
    banca: Annotated[list[str] | None, Query(description="Bancas marcadas.")] = None,
    orgao: Annotated[list[str] | None, Query(description="Órgãos marcados.")] = None,
    ano: Annotated[list[int] | None, Query(description="Anos marcados.")] = None,
    concurso: Annotated[
        list[str] | None, Query(description="Concursos marcados (slug).")
    ] = None,
    cargo: Annotated[
        list[str] | None, Query(description="Cargos marcados (`CONCURSO:NUMERO`).")
    ] = None,
    nivel: Annotated[list[str] | None, Query(description="Níveis marcados.")] = None,
    tipo_conhecimento: Annotated[
        list[str] | None, Query(description="Tipos de conhecimento marcados.")
    ] = None,
    no_id: Annotated[
        list[str] | None, Query(description="Nós da árvore marcados.")
    ] = None,
    anuladas: Literal["incluir", "excluir", "so"] = Query(
        "incluir", description="Tratamento das questões anuladas."
    ),
    utilizaveis: Literal["so", "todas"] = Query(
        "so", description="`so` (padrão) conta só as questões utilizáveis."
    ),
    historico: Literal[
        "todas", "resolvidas", "nao_resolvidas", "certas", "erradas"
    ] = Query(
        "todas",
        description="Histórico do usuário logado. Diferente de `todas` sem login: 401.",
    ),
):
    filtros = FiltroQuestoes(
        banca=banca,
        orgao=orgao,
        ano=ano,
        concurso=concurso,
        cargo=cargo,
        nivel=nivel,
        tipo_conhecimento=tipo_conhecimento,
        no_id=no_id,
        anuladas=anuladas,
        utilizaveis=utilizaveis,
        historico=historico,
    )
    try:
        return questoes_servico.obter_facetas(filtros, usuario_id_atual(request))
    except LoginNecessario:
        raise HTTPException(status_code=401, detail="Login necessário") from None
