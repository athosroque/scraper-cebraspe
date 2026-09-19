from pydantic import BaseModel
from typing import List


class ConcursoMetadados(BaseModel):
    slug: str
    orgao: str
    ano: int
    link_pagina: str
    links_editais: List[str] = []


class CargoEdital(BaseModel):
    concurso_id: str
    nome_cargo: str


class Topico(BaseModel):
    nome: str
    subtopicos: List[str] = []


class TaxonomiaEdital(BaseModel):
    materia: str
    topicos: List[Topico]
