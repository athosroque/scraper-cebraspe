"""Modelos Pydantic da API (contrato em `site/openapi.json`).

Todo campo leva `description` e os modelos principais trazem exemplo real
(PF_25_ADM, caderno 094_PF_CB1_01, item 1): o Swagger é a documentação.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_CHAVE = "Chave estável `concurso|caderno|numero` da questão (mesma da 5D)."
_EX_CHAVE = "PF_25_ADM|094_PF_CB1_01|1"
_EX_ENUNCIADO = (
    "Dada a relação de contraste estabelecida entre as duas primeiras orações do "
    "último período do texto, seria coerente e gramaticalmente correto inserir, "
    "entre vírgulas, a expressão não obstante logo após “pobres”."
)
_EX_SECAO = (
    "Acerca das ideias e de aspectos linguísticos do texto precedente, julgue os "
    "itens a seguir."
)
_EX_CARGO = {
    "cargo_edital_id": 1,
    "cargo_numero": 1,
    "cargo": "ADMINISTRADOR",
    "nivel": "superior",
}
_EX_NO = {
    "no_id": "SL-f514698ce9",
    "no_nome": (
        "Emprego de elementos de referenciação, substituição e repetição, de "
        "conectores e de outros elementos de sequenciação textual"
    ),
    "no_nivel": "subassunto",
    "no_caminho": (
        "LÍNGUA PORTUGUESA > Domínio dos mecanismos de coesão textual > Emprego de "
        "elementos de referenciação, substituição e repetição, de conectores e de "
        "outros elementos de sequenciação textual"
    ),
    "materia_id": "M-0f9a364d06",
    "assunto_id": "A-56b9b718fa",
    "papel": "principal",
    "confianca": "alta",
    "fora_do_edital": False,
    "rotulo_materia": "LÍNGUA PORTUGUESA",
}
_EX_QUESTAO = {
    "questao_id": 63231,
    "questao_chave": _EX_CHAVE,
    "numero": 1,
    "codigo_caderno": "094_PF_CB1_01",
    "concurso": "PF_25_ADM",
    "orgao": "PF",
    "banca": "CEBRASPE",
    "ano": 2025,
    "gabarito": "C",
    "anulada": False,
    "utilizavel": True,
    "enunciado": _EX_ENUNCIADO,
    "secao": _EX_SECAO,
    "tem_texto_base": True,
    "tem_figuras": False,
    "cargos": [_EX_CARGO],
    "nos": [_EX_NO],
}

_D_CONCURSO = "Slug do concurso (ex.: `PF_25_ADM`)."
_D_CARGO_NUMERO = "Número do cargo no edital do concurso."
_D_NIVEL = "Nível do cargo: `superior` ou `medio`."
_D_TIPO = "Tipo de conhecimento: `basico` ou `especifico`."
_D_NO_ID = "Id estável do nó da árvore mestre (prefixo `M-`, `A-` ou `S`)."
_D_NO_NOME = "Nome do nó na árvore mestre."
_D_NO_NIVEL = "Nível do nó: `materia`, `assunto` ou `subassunto`."
_D_CAMINHO = "Caminho do nó na árvore, separado por ` > `."
_D_MATERIA_ID = "Id do nó de matéria ao qual o nó pertence."
_D_CADERNO = "Código do caderno de prova (ex.: `094_PF_CB1_01`)."
_D_NUMERO = "Número do item no caderno."
_D_FIGURAS = "Figuras recortadas do PDF, com caminho e URL para exibir."
_D_QUESITOS = "Quesitos da discursiva (número, texto e valor em pontos)."


# -- Filtros (internos; os parâmetros de consulta são documentados nas rotas) --
class FiltroQuestoes(BaseModel):
    """Filtros da listagem de questões, montados a partir da query string."""

    banca: str | None = Field(None, description="Banca (ex.: `CEBRASPE`).")
    orgao: str | None = Field(None, description="Órgão (ex.: `PF`).")
    ano: int | None = Field(None, description="Ano do concurso.")
    concurso: str | None = Field(None, description=_D_CONCURSO)
    cargo_numero: int | None = Field(None, description=_D_CARGO_NUMERO)
    nivel: str | None = Field(None, description=_D_NIVEL)
    tipo_conhecimento: str | None = Field(None, description=_D_TIPO)
    no_id: str | None = Field(None, description=_D_NO_ID)
    anuladas: Literal["incluir", "excluir", "so"] = Field(
        "incluir", description="Tratamento das questões anuladas."
    )
    fora_do_edital: Literal["todos", "sim", "nao"] = Field(
        "todos", description="Recorte por questão fora do edital do cargo."
    )
    utilizaveis: Literal["so", "todas"] = Field(
        "so", description="`so` esconde as questões com extração ilegível."
    )
    # 5F.3: só vale com login (pela resposta mais recente de cada questão)
    historico: Literal["todas", "resolvidas", "nao_resolvidas", "certas", "erradas"] = (
        Field("todas", description="Recorte pelo histórico do usuário logado.")
    )


# -- Respostas da API --
class CargoInfo(BaseModel):
    """Cargo do edital para o qual o caderno da questão foi aplicado."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EX_CARGO]})

    cargo_edital_id: int = Field(description="Id interno do cargo no banco.")
    cargo_numero: int = Field(description=_D_CARGO_NUMERO)
    cargo: str = Field(description="Nome do cargo como no edital.")
    nivel: str = Field(description=_D_NIVEL)


class NoInfo(BaseModel):
    """Nó da árvore mestre (matéria → assunto → subassunto) em que a questão foi classificada (Etapa 5D)."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EX_NO]})

    no_id: str = Field(description=_D_NO_ID)
    no_nome: str = Field(description=_D_NO_NOME)
    no_nivel: str = Field(description=_D_NO_NIVEL)
    no_caminho: str = Field(description=_D_CAMINHO)
    materia_id: str | None = Field(None, description=_D_MATERIA_ID)
    assunto_id: str | None = Field(
        None, description="Id do nó de assunto (vazio quando o nó é matéria)."
    )
    papel: str | None = Field(None, description="`principal` ou `secundario`.")
    confianca: str | None = Field(
        None, description="Confiança da classificação: `alta`, `media` ou `baixa`."
    )
    fora_do_edital: bool | None = Field(
        None, description="`true` quando o nó não está previsto no edital do cargo."
    )
    rotulo_materia: str | None = Field(
        None,
        description=(
            "Nome da matéria para exibição (matéria com nome de cargo vira "
            "“Conhecimentos específicos — <cargo>”)."
        ),
    )


class QuestaoResumo(BaseModel):
    """Questão objetiva (certo/errado) na listagem. Uma entrada por questão, com cargos e nós agregados."""

    model_config = ConfigDict(json_schema_extra={"examples": [_EX_QUESTAO]})

    questao_id: int = Field(
        description="Id interno (muda a cada recarga). Para referência, use `questao_chave`."
    )
    questao_chave: str = Field(
        description="Chave estável `concurso|caderno|numero` (mesma da 5D). Use no detalhe e para guardar respostas.",
        examples=[_EX_CHAVE],
    )
    numero: int = Field(description=_D_NUMERO)
    codigo_caderno: str = Field(description=_D_CADERNO)
    concurso: str = Field(description=_D_CONCURSO)
    orgao: str = Field(description="Órgão do concurso (ex.: `PF`).")
    banca: str = Field(description="Banca organizadora (`CEBRASPE`).")
    ano: int = Field(description="Ano do concurso.")
    gabarito: str = Field(
        description="Gabarito definitivo: `C` (certo), `E` (errado) ou `X` (anulada)."
    )
    anulada: bool = Field(description="`true` quando a banca anulou o item.")
    utilizavel: bool = Field(
        description="`false` quando a extração do PDF ficou ilegível ou com alerta bloqueante."
    )
    enunciado: str = Field(description="Texto do item a julgar.")
    secao: str | None = Field(
        description="Comando da seção do caderno que agrupa o item (“julgue os itens…”)."
    )
    tem_texto_base: bool = Field(
        description="`true` quando há texto-base (buscar no detalhe ou em `/q/.../anexos`)."
    )
    tem_figuras: bool = Field(description="`true` quando o item tem figuras.")
    cargos: list[CargoInfo] = Field(
        description="Cargos para os quais o caderno foi aplicado."
    )
    nos: list[NoInfo] = Field(
        description="Nós da árvore em que a questão foi classificada (principal e secundário)."
    )


class QuestaoDetalhe(QuestaoResumo):
    """Questão completa: texto-base, figuras e link para o PDF original do CEBRASPE."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    **_EX_QUESTAO,
                    "texto_base_texto": "“A liberdade medieval”, disse o historiador…",
                    "figuras": [],
                    "link_pdf": None,
                }
            ]
        }
    )

    texto_base_texto: str | None = Field(
        description="Texto-base compartilhado pelos itens, quando houver."
    )
    figuras: list[dict[str, Any]] = Field(description=_D_FIGURAS)
    link_pdf: str | None = Field(
        None,
        description="URL do caderno original no site do CEBRASPE (crédito da fonte).",
    )


class PaginaQuestoes(BaseModel):
    """Página de resultados de `GET /api/v1/questoes`."""

    total: int = Field(description="Total de questões que atendem aos filtros.")
    pagina: int = Field(description="Página atual, a partir de 1.")
    tamanho_pagina: int = Field(description="Itens por página.")
    total_paginas: int = Field(description="Número de páginas.")
    itens: list[QuestaoResumo] = Field(description="Questões da página.")


class NoArvore(BaseModel):
    """Nó da árvore mestre com a contagem de questões distintas (a contagem sobe a árvore)."""

    id: str = Field(description=_D_NO_ID)
    nome: str = Field(description=_D_NO_NOME)
    nivel: str = Field(description=_D_NO_NIVEL)
    total_questoes: int = Field(
        description="Questões distintas no nó e nos descendentes."
    )
    filhos: list["NoArvore"] = Field([], description="Nós filhos.")


class FacetaValor(BaseModel):
    """Um valor possível de filtro, com o total de questões."""

    valor: Any = Field(description="Valor a enviar no parâmetro do filtro.")
    rotulo: str = Field(description="Texto para exibir.")
    total: int = Field(description="Questões distintas com esse valor.")


class FacetaCargo(BaseModel):
    """Cargo possível no filtro, com o total de questões."""

    cargo_numero: int = Field(description=_D_CARGO_NUMERO)
    cargo: str = Field(description="Nome do cargo.")
    concurso: str = Field(description=_D_CONCURSO)
    nivel: str = Field(description=_D_NIVEL)
    total: int = Field(description="Questões distintas do cargo.")


class FacetasResponse(BaseModel):
    """Valores possíveis de cada filtro da listagem, com o total de questões distintas."""

    bancas: list[FacetaValor] = Field(description="Bancas.")
    orgaos: list[FacetaValor] = Field(description="Órgãos.")
    anos: list[FacetaValor] = Field(description="Anos.")
    concursos: list[FacetaValor] = Field(description="Concursos (slug).")
    niveis: list[FacetaValor] = Field(description="Níveis de cargo.")
    tipos_conhecimento: list[FacetaValor] = Field(
        description="Tipos de conhecimento (básico/específico)."
    )
    cargos: list[FacetaCargo] = Field(description="Cargos por concurso.")


# -- Contas e histórico (5F.3) --
class Usuario(BaseModel):
    """Usuário logado (Google OAuth)."""

    id: int = Field(description="Id interno do usuário.")
    email: str = Field(description="E-mail da conta Google.")
    nome: str | None = Field(None, description="Nome da conta Google.")


class RespostaEntrada(BaseModel):
    """Resposta a uma questão para corrigir (e gravar, com login)."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"questao_chave": _EX_CHAVE, "resposta": "C"}]}
    )

    questao_chave: str = Field(description=_CHAVE, examples=[_EX_CHAVE])
    resposta: Literal["C", "E"] = Field(description="`C` (certo) ou `E` (errado).")


class RespostaResultado(BaseModel):
    """Correção de uma resposta. `gravada` é `false` sem login ou em questão anulada."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "questao_chave": _EX_CHAVE,
                    "resposta": "C",
                    "gabarito": "C",
                    "anulada": False,
                    "acertou": True,
                    "gravada": True,
                }
            ]
        }
    )

    questao_chave: str = Field(description=_CHAVE)
    resposta: Literal["C", "E"] = Field(description="Resposta enviada.")
    gabarito: str = Field(description="Gabarito definitivo (`C`, `E` ou `X`).")
    anulada: bool = Field(description="`true` quando a questão foi anulada.")
    acertou: bool = Field(description="`true` quando a resposta bate com o gabarito.")
    gravada: bool = Field(description="`true` quando entrou no histórico do usuário.")


class NoDesempenho(BaseModel):
    """Acertos do usuário num nó da árvore: questão distinta, subindo a árvore (regra da 5E)."""

    id: str = Field(description=_D_NO_ID)
    nome: str = Field(description=_D_NO_NOME)
    nivel: str = Field(description=_D_NO_NIVEL)
    total: int = Field(
        description="Questões respondidas no nó (resposta mais recente)."
    )
    acertos: int = Field(description="Questões acertadas no nó.")
    percentual: float = Field(description="Acertos / total × 100, com 1 casa.")
    filhos: list["NoDesempenho"] = Field([], description="Nós filhos.")


# -- Estatísticas (5F.4) --
NivelAlvo = Literal["materia", "assunto", "subassunto"]


class FiltroEstatistica(BaseModel):
    """Recorte das estatísticas (interno; os parâmetros são documentados nas rotas)."""

    concurso: str | None = Field(None, description=_D_CONCURSO)
    cargo_numero: int | None = Field(None, description=_D_CARGO_NUMERO)
    nivel: str | None = Field(None, description=_D_NIVEL)
    tipo_conhecimento: str | None = Field(None, description=_D_TIPO)


class LinhaProvaCobra(BaseModel):
    """Nó no ranking "o que mais cai" (`fn_prova_cobra`): questão distinta, subindo a árvore."""

    no_id: str = Field(description=_D_NO_ID)
    no_nome: str = Field(description=_D_NO_NOME)
    caminho: str = Field(description=_D_CAMINHO)
    materia_id: str | None = Field(description=_D_MATERIA_ID)
    questoes: int = Field(
        description="Questões válidas distintas no nó (anuladas fora)."
    )
    anuladas: int = Field(description="Questões anuladas no nó.")
    total_universo: int = Field(
        description="Questões válidas distintas sob os filtros."
    )
    pct_do_universo: float = Field(description="`questoes` / `total_universo` × 100.")
    pct_medio_por_concurso: float = Field(
        description=(
            "Média entre concursos do % do nó dentro da matéria (subassunto/assunto) "
            "ou da prova (matéria), com peso igual por concurso."
        )
    )


class LinhaEditalCobra(BaseModel):
    """Nó no ranking "o que o edital cobra": itens de edital distintos, subindo a árvore."""

    no_id: str = Field(description=_D_NO_ID)
    no_nome: str = Field(description=_D_NO_NOME)
    caminho: str = Field(description=_D_CAMINHO)
    materia_id: str | None = Field(description=_D_MATERIA_ID)
    ocorrencias: int = Field(
        description="Itens de edital distintos no nó (básico conta por cargo)."
    )


class LinhaEditalVsProva(BaseModel):
    """Nó do edital ou da prova de um cargo, com a situação da cobrança."""

    no_id: str = Field(description=_D_NO_ID)
    no_nome: str = Field(description=_D_NO_NOME)
    no_nivel: str = Field(description=_D_NO_NIVEL)
    caminho: str = Field(description=_D_CAMINHO)
    materia_id: str | None = Field(description=_D_MATERIA_ID)
    previsao: int = Field(description="Itens do edital do cargo no nó.")
    questoes: int = Field(description="Questões distintas da prova do cargo no nó.")
    situacao: Literal[
        "cobrado_no_edital", "no_edital_nunca_cobrado", "cobrado_fora_do_edital"
    ] = Field(description="Situação do nó no edital × prova.")


class PesoMateria(BaseModel):
    """Peso de uma matéria na prova do cargo (`vw_peso_materia_cargo`)."""

    materia_id: str = Field(description="Id do nó de matéria.")
    rotulo_materia: str = Field(description="Nome da matéria para exibição.")
    questoes: int = Field(description="Questões válidas da matéria na prova.")
    anuladas: int = Field(description="Questões anuladas da matéria.")
    total_cargo: int = Field(description="Questões válidas da prova do cargo.")
    pct_da_prova: float = Field(description="`questoes` / `total_cargo` × 100.")


class EditalVsProva(BaseModel):
    """Edital × prova de um cargo (`vw_edital_vs_prova` + `vw_peso_materia_cargo`)."""

    concurso: str = Field(description=_D_CONCURSO)
    cargo_numero: int = Field(description=_D_CARGO_NUMERO)
    resumo: dict[str, int] = Field(description="Total de nós por situação.")
    nos: list[LinhaEditalVsProva] = Field(description="Nós com a situação de cada um.")
    peso_materias: list[PesoMateria] = Field(
        description="Peso de cada matéria na prova."
    )


# -- Simulado (5F.5) --
class ItemSimulado(BaseModel):
    """Item da prova no simulado, sem gabarito (só aparece na correção)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "questao_chave": _EX_CHAVE,
                    "numero": 1,
                    "codigo_caderno": "094_PF_CB1_01",
                    "tipo_conhecimento": "basico",
                    "enunciado": _EX_ENUNCIADO,
                    "texto_base_texto": "“A liberdade medieval”, disse o historiador…",
                    "figuras": [],
                }
            ]
        }
    )

    questao_chave: str = Field(description=_CHAVE)
    numero: int = Field(description=_D_NUMERO)
    codigo_caderno: str = Field(description=_D_CADERNO)
    tipo_conhecimento: str = Field(description=_D_TIPO)
    enunciado: str = Field(description="Texto do item a julgar.")
    texto_base_texto: str | None = Field(
        None, description="Texto-base compartilhado, quando houver."
    )
    figuras: list[dict[str, Any]] = Field([], description=_D_FIGURAS)


class DiscursivaSimulado(BaseModel):
    """Questão discursiva da prova do cargo (sem nota: não entra no placar)."""

    numero: int | None = Field(description="Número da questão discursiva.")
    titulo: str | None = Field(description="Título impresso no caderno.")
    tema: str | None = Field(description="Tema proposto (vazio se anafórico).")
    enunciado: str | None = Field(description="Texto completo da proposta.")
    quesitos: list[dict[str, Any]] = Field([], description=_D_QUESITOS)
    padrao_resposta: str | None = Field(
        None, description="Só vem na correção, depois de encerrar o simulado."
    )


class ProvaSimulado(BaseModel):
    """Prova de um cargo na ordem original: básico, depois específico (caderno, número)."""

    concurso: str = Field(description=_D_CONCURSO)
    cargo_numero: int = Field(description=_D_CARGO_NUMERO)
    cargo: str = Field(description="Nome do cargo.")
    nivel: str = Field(description=_D_NIVEL)
    itens_omitidos: int = Field(
        0,
        description="Itens do cargo fora da prova por `utilizavel=false` (ilegíveis).",
    )
    itens: list[ItemSimulado] = Field(description="Itens objetivos, sem gabarito.")
    discursivas: list[DiscursivaSimulado] = Field(
        description="Discursivas do cargo, sem padrão de resposta."
    )


class RespostasSimulado(BaseModel):
    """Marcações do simulado."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"respostas": {_EX_CHAVE: "C"}}]}
    )

    respostas: dict[str, Literal["C", "E"]] = Field(
        default_factory=dict,
        description="Chave da questão → `C`/`E`. Item ausente conta como em branco.",
    )


class SimuladoInicio(BaseModel):
    """Cargo do simulado a iniciar."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"concurso": "PF_25_ADM", "cargo_numero": 1}]}
    )

    concurso: str = Field(description=_D_CONCURSO)
    cargo_numero: int = Field(description=_D_CARGO_NUMERO)


class SimuladoEntrada(SimuladoInicio, RespostasSimulado):
    """Cargo e marcações para corrigir um simulado sem gravar."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "concurso": "PF_25_ADM",
                    "cargo_numero": 1,
                    "respostas": {_EX_CHAVE: "C"},
                }
            ]
        }
    )


class ItemCorrigido(BaseModel):
    """Item do simulado com a resposta, o gabarito e a situação."""

    questao_chave: str = Field(description=_CHAVE)
    numero: int = Field(description=_D_NUMERO)
    codigo_caderno: str = Field(description=_D_CADERNO)
    resposta: Literal["C", "E"] | None = Field(
        description="Resposta marcada (vazio = em branco)."
    )
    gabarito: str = Field(description="Gabarito definitivo (`C`, `E` ou `X`).")
    situacao: Literal["certo", "errado", "branco", "anulada"] = Field(
        description="Resultado do item."
    )


class PlacarSimulado(BaseModel):
    """Correção CEBRASPE: certo +1, errado −1, branco 0; anulada não conta."""

    certas: int = Field(0, description="Itens certos.")
    erradas: int = Field(0, description="Itens errados.")
    brancos: int = Field(0, description="Itens em branco.")
    anuladas: int = Field(0, description="Itens anulados (fora da nota).")
    nota: int = Field(0, description="Certas − erradas.")
    nota_maxima: int = Field(0, description="Itens não anulados.")


class MateriaSimulado(PlacarSimulado):
    """Placar do simulado numa matéria (pelo nó principal de cada item)."""

    materia_id: str = Field(description="Id do nó de matéria.")
    nome: str = Field(description="Nome da matéria para exibição.")


class ResultadoSimulado(BaseModel):
    """Resultado de um simulado: placar geral, por matéria e por item."""

    simulado_id: int | None = Field(
        None, description="Preenchido quando o simulado foi gravado (com login)."
    )
    concurso: str = Field(description=_D_CONCURSO)
    cargo_numero: int = Field(description=_D_CARGO_NUMERO)
    cargo: str = Field(description="Nome do cargo.")
    itens_omitidos: int = Field(
        0, description="Itens ilegíveis fora da prova, da nota e do máximo."
    )
    placar: PlacarSimulado = Field(description="Placar geral.")
    por_materia: list[MateriaSimulado] = Field(description="Placar por matéria.")
    itens: list[ItemCorrigido] = Field(description="Correção item a item.")
    discursivas: list[DiscursivaSimulado] = Field(
        description="Discursivas com o padrão de resposta."
    )


class SimuladoResumo(BaseModel):
    """Simulado gravado do usuário."""

    id: int = Field(description="Id do simulado.")
    concurso: str = Field(description=_D_CONCURSO)
    cargo_numero: int | None = Field(description=_D_CARGO_NUMERO)
    inicio: Any = Field(description="Data e hora do início (ISO 8601).")
    fim: Any = Field(description="Data e hora do encerramento (vazio se aberto).")
    nota: float | None = Field(description="Nota líquida (vazio se aberto).")
