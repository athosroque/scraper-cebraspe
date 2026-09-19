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


class Topico(BaseModel):
    nome: str
    subtopicos: list[str] = []


class TaxonomiaEdital(BaseModel):
    materia: str
    topicos: list[Topico]
