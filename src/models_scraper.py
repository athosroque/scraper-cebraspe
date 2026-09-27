from typing import Literal

from pydantic import BaseModel


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
    nome: str
    subtopicos: list[str] = []


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
