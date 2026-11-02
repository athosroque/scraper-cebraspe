from typing import Literal

from pydantic import BaseModel, model_serializer


class ConcursoMetadados(BaseModel):
    slug: str
    orgao: str
    ano: int
    link_pagina: str
    links_editais: list[str] = []


class CargoEdital(BaseModel):
    concurso_id: str
    nome_cargo: str
    numero_cargo: int | None = None
    nivel: Literal["medio", "superior"] | None = None


class Topico(BaseModel):
    """Tópico da taxonomia. `subtopicos` guarda o TEXTO PRÓPRIO de cada subitem.

    `caminho_origem` (KAN-93, M7) é contexto, não identidade: para o subtópico
    reinjetado a partir de um subitem de 3º nível em diante, guarda os textos
    próprios dos ancestrais de 2º nível para baixo (`{"Design thinking":
    ["Metodologias ágeis e experiência do usuário"]}`). Nenhum consumidor usa
    isso para chave: a chave do item é o texto próprio. Opcional e omitido do
    JSON quando vazio, então o JSON antigo carrega sem mudança.

    Rastro da M8 (KAN-94), também opcional e omitido quando vazio: `nome_origem`
    é o nome do tópico antes de a lista com ";" ser dividida e a cabeça antes do
    ":" virar o nome (a chave do tópico mudou); `subtopicos_absorvidos` são as
    facetas devolvidas ao pai. Servem só para `scripts.migrar_chaves_cadeia`
    recalcular as chaves antigas dos mapeamentos; nenhum consumidor os usa como
    identidade.
    """

    nome: str
    subtopicos: list[str] = []
    caminho_origem: dict[str, list[str]] | None = None
    nome_origem: str | None = None
    subtopicos_absorvidos: list[str] | None = None

    @model_serializer(mode="wrap")
    def _omitir_campos_vazios(self, handler):
        dados = handler(self)
        for campo in ("caminho_origem", "nome_origem", "subtopicos_absorvidos"):
            if not dados.get(campo):
                dados.pop(campo, None)
        return dados


class TaxonomiaEdital(BaseModel):
    materia: str
    topicos: list[Topico]


class ProvaObjetiva(BaseModel):
    """Um caderno de prova objetiva. Pode cobrir mais de um cargo — o
    CEBRASPE agrupa Conhecimentos Básicos por cargos de mesmo nível
    (ex: CB1 = cargos 1 a 14, CB2 = cargo 15), enquanto Conhecimentos
    Específicos normalmente é individual por cargo. Ver decisão em
    CLAUDE.md (seção 12, 2026-09-19). No banco: tabelas `provas` +
    `provas_cargos` (ADR-027). Sem `nivel`: nível é atributo do cargo."""

    concurso_id: str
    tipo: Literal["conhecimentos_basicos", "conhecimentos_especificos"]
    identificador: str  # ex: "CB1", "CB2", "015" — vem do nome do arquivo
    cargos_numeros: list[int]  # todos os cargos cobertos por este caderno
    arquivo: str


class ProvaDiscursiva(BaseModel):
    """Caderno de prova discursiva de um cargo. Nem todo cargo tem — só
    criar registro para cargo que efetivamente tem discursiva (não usar
    tema=None para representar ausência)."""

    concurso_id: str
    cargo_numero: int
    tema: str | None = None  # preenchido na Etapa 4 (extração LLM)
    arquivo: str
