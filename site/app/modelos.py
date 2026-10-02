from typing import Any, Literal

from pydantic import BaseModel, Field


# -- Filtros --
class FiltroQuestoes(BaseModel):
    banca: str | None = None
    orgao: str | None = None
    ano: int | None = None
    concurso: str | None = None
    cargo_numero: int | None = None
    nivel: str | None = None
    tipo_conhecimento: str | None = None
    no_id: str | None = None
    anuladas: Literal["incluir", "excluir", "so"] = "incluir"
    fora_do_edital: Literal["todos", "sim", "nao"] = "todos"
    utilizaveis: Literal["so", "todas"] = "so"
    # 5F.3: só vale com login (pela resposta mais recente de cada questão)
    historico: Literal["todas", "resolvidas", "nao_resolvidas", "certas", "erradas"] = (
        "todas"
    )


# -- Respostas da API --
class CargoInfo(BaseModel):
    """Cargo do edital para o qual o caderno da questão foi aplicado."""

    cargo_edital_id: int
    cargo_numero: int
    cargo: str
    nivel: str


class NoInfo(BaseModel):
    """Nó da árvore mestre (matéria → assunto → subassunto) em que a questão foi classificada (Etapa 5D)."""

    no_id: str
    no_nome: str
    no_nivel: str
    no_caminho: str
    materia_id: str | None = None
    assunto_id: str | None = None
    papel: str | None = Field(None, description="`principal` ou `secundario`.")
    confianca: str | None = None
    fora_do_edital: bool | None = Field(
        None, description="`true` quando o nó não está previsto no edital do cargo."
    )
    rotulo_materia: str | None = None


class QuestaoResumo(BaseModel):
    """Questão objetiva (certo/errado) na listagem. Uma entrada por questão, com cargos e nós agregados."""

    questao_id: int
    questao_chave: str = Field(
        description="Chave estável `concurso|caderno|numero` (mesma da 5D). Use no detalhe e para guardar respostas.",
        examples=["PF_25_ADM|094_PF_CB1_01|13"],
    )
    numero: int
    codigo_caderno: str
    concurso: str
    orgao: str
    banca: str
    ano: int
    gabarito: str = Field(
        description="Gabarito definitivo: `C` (certo), `E` (errado) ou `X` (anulada)."
    )
    anulada: bool
    utilizavel: bool = Field(
        description="`false` quando a extração do PDF ficou ilegível ou com alerta bloqueante."
    )
    enunciado: str
    secao: str | None
    tem_texto_base: bool
    tem_figuras: bool
    cargos: list[CargoInfo]
    nos: list[NoInfo]


class QuestaoDetalhe(QuestaoResumo):
    """Questão completa: texto-base, figuras e link para o PDF original do CEBRASPE."""

    texto_base_texto: str | None
    figuras: list[dict[str, Any]]  # Incluir URL resolvida
    link_pdf: str | None = Field(
        None,
        description="URL do caderno original no site do CEBRASPE (crédito da fonte).",
    )


class PaginaQuestoes(BaseModel):
    """Página de resultados de `GET /api/v1/questoes`."""

    total: int
    pagina: int
    tamanho_pagina: int
    total_paginas: int
    itens: list[QuestaoResumo]


class NoArvore(BaseModel):
    """Nó da árvore mestre com a contagem de questões distintas (a contagem sobe a árvore)."""

    id: str
    nome: str
    nivel: str
    total_questoes: int
    filhos: list["NoArvore"] = []


class FacetaValor(BaseModel):
    valor: Any
    rotulo: str
    total: int


class FacetaCargo(BaseModel):
    cargo_numero: int
    cargo: str
    concurso: str
    nivel: str
    total: int


class FacetasResponse(BaseModel):
    """Valores possíveis de cada filtro da listagem, com o total de questões distintas."""

    bancas: list[FacetaValor]
    orgaos: list[FacetaValor]
    anos: list[FacetaValor]
    concursos: list[FacetaValor]
    niveis: list[FacetaValor]
    tipos_conhecimento: list[FacetaValor]
    cargos: list[FacetaCargo]


# -- Contas e histórico (5F.3) --
class Usuario(BaseModel):
    """Usuário logado (Google OAuth)."""

    id: int
    email: str
    nome: str | None = None


class RespostaEntrada(BaseModel):
    questao_chave: str = Field(examples=["PF_25_ADM|094_PF_CB1_01|13"])
    resposta: Literal["C", "E"]


class RespostaResultado(BaseModel):
    """Correção de uma resposta. `gravada` é `false` sem login ou em questão anulada."""

    questao_chave: str
    resposta: Literal["C", "E"]
    gabarito: str
    anulada: bool
    acertou: bool
    gravada: bool


class NoDesempenho(BaseModel):
    """Acertos do usuário num nó da árvore: questão distinta, subindo a árvore (regra da 5E)."""

    id: str
    nome: str
    nivel: str
    total: int
    acertos: int
    percentual: float = Field(description="Acertos / total × 100, com 1 casa.")
    filhos: list["NoDesempenho"] = []


# -- Estatísticas (5F.4) --
NivelAlvo = Literal["materia", "assunto", "subassunto"]


class FiltroEstatistica(BaseModel):
    concurso: str | None = None
    cargo_numero: int | None = None
    nivel: str | None = None
    tipo_conhecimento: str | None = None


class LinhaProvaCobra(BaseModel):
    """Nó no ranking "o que mais cai" (`fn_prova_cobra`): questão distinta, subindo a árvore."""

    no_id: str
    no_nome: str
    caminho: str
    materia_id: str | None
    questoes: int = Field(
        description="Questões válidas distintas no nó (anuladas fora)."
    )
    anuladas: int
    total_universo: int = Field(
        description="Questões válidas distintas sob os filtros."
    )
    pct_do_universo: float
    pct_medio_por_concurso: float = Field(
        description=(
            "Média entre concursos do % do nó dentro da matéria (subassunto/assunto) "
            "ou da prova (matéria), com peso igual por concurso."
        )
    )


class LinhaEditalCobra(BaseModel):
    """Nó no ranking "o que o edital cobra": itens de edital distintos, subindo a árvore."""

    no_id: str
    no_nome: str
    caminho: str
    materia_id: str | None
    ocorrencias: int


class LinhaEditalVsProva(BaseModel):
    no_id: str
    no_nome: str
    no_nivel: str
    caminho: str
    materia_id: str | None
    previsao: int = Field(description="Itens do edital do cargo no nó.")
    questoes: int
    situacao: Literal[
        "cobrado_no_edital", "no_edital_nunca_cobrado", "cobrado_fora_do_edital"
    ]


class PesoMateria(BaseModel):
    materia_id: str
    rotulo_materia: str
    questoes: int
    anuladas: int
    total_cargo: int
    pct_da_prova: float


class EditalVsProva(BaseModel):
    """Edital × prova de um cargo (`vw_edital_vs_prova` + `vw_peso_materia_cargo`)."""

    concurso: str
    cargo_numero: int
    resumo: dict[str, int] = Field(description="Total de nós por situação.")
    nos: list[LinhaEditalVsProva]
    peso_materias: list[PesoMateria]


# -- Simulado (5F.5) --
class ItemSimulado(BaseModel):
    """Item da prova no simulado, sem gabarito (só aparece na correção)."""

    questao_chave: str
    numero: int
    codigo_caderno: str
    tipo_conhecimento: str
    enunciado: str
    texto_base_texto: str | None = None
    figuras: list[dict[str, Any]] = []


class DiscursivaSimulado(BaseModel):
    numero: int | None
    titulo: str | None
    tema: str | None
    enunciado: str | None
    quesitos: list[dict[str, Any]] = []
    padrao_resposta: str | None = Field(
        None, description="Só vem na correção, depois de encerrar o simulado."
    )


class ProvaSimulado(BaseModel):
    """Prova de um cargo na ordem original: básico, depois específico (caderno, número)."""

    concurso: str
    cargo_numero: int
    cargo: str
    nivel: str
    itens_omitidos: int = Field(
        0,
        description="Itens do cargo fora da prova por `utilizavel=false` (ilegíveis).",
    )
    itens: list[ItemSimulado]
    discursivas: list[DiscursivaSimulado]


class RespostasSimulado(BaseModel):
    respostas: dict[str, Literal["C", "E"]] = Field(
        default_factory=dict,
        description="Chave da questão → `C`/`E`. Item ausente conta como em branco.",
    )


class SimuladoInicio(BaseModel):
    concurso: str
    cargo_numero: int


class SimuladoEntrada(SimuladoInicio, RespostasSimulado):
    pass


class ItemCorrigido(BaseModel):
    questao_chave: str
    numero: int
    codigo_caderno: str
    resposta: Literal["C", "E"] | None
    gabarito: str
    situacao: Literal["certo", "errado", "branco", "anulada"]


class PlacarSimulado(BaseModel):
    """Correção CEBRASPE: certo +1, errado −1, branco 0; anulada não conta."""

    certas: int = 0
    erradas: int = 0
    brancos: int = 0
    anuladas: int = 0
    nota: int = Field(0, description="Certas − erradas.")
    nota_maxima: int = Field(0, description="Itens não anulados.")


class MateriaSimulado(PlacarSimulado):
    materia_id: str
    nome: str


class ResultadoSimulado(BaseModel):
    simulado_id: int | None = Field(
        None, description="Preenchido quando o simulado foi gravado (com login)."
    )
    concurso: str
    cargo_numero: int
    cargo: str
    itens_omitidos: int = Field(
        0, description="Itens ilegíveis fora da prova, da nota e do máximo."
    )
    placar: PlacarSimulado
    por_materia: list[MateriaSimulado]
    itens: list[ItemCorrigido]
    discursivas: list[DiscursivaSimulado]
    duracao_segundos: int | None = Field(
        None,
        description=(
            "Tempo entre o início e o encerramento do simulado gravado, em "
            "segundos. Null sem login."
        ),
    )
    nota_anterior: float | None = Field(
        None,
        description=(
            "Nota do simulado encerrado anterior do mesmo usuário, no mesmo "
            "concurso e cargo. Null se não houver ou sem login."
        ),
    )


class SimuladoResumo(BaseModel):
    id: int
    concurso: str
    cargo_numero: int | None
    inicio: Any
    fim: Any
    nota: float | None
