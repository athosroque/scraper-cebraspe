"""Decisões humanas sobre sinônimos (Etapa 5B)."""

import pytest

from scripts.aprovar_sinonimos import aplicar_decisoes
from src import canonico
from tests.test_canonico import _nomes


@pytest.fixture
def estado():
    estado = canonico.estado_vazio()
    canonico.aplicar_regras(
        estado, _nomes(materias={"X": ["A"], "Y": ["B"], "Z": ["C"]})
    )
    return estado


def test_mover_e_aprovar_na_mesma_chamada(estado):
    ex, ey, ez = sorted(
        estado["materia"]["entradas"],
        key=lambda e: estado["materia"]["entradas"][e]["chave_regra"],
    )
    gid = canonico.registrar_proposta(estado, "materia", [ex, ey], "XY", None, None)
    feitas = aplicar_decisoes(
        estado, mover=[f"{ez}:{gid}"], aprovar=[gid], renomear=[f"{gid}=Nome final"]
    )
    assert feitas[0].startswith("movida")
    grupo = estado["materia"]["grupos"][gid]
    assert (grupo["status"], grupo["nome"], len(grupo["membros"])) == (
        "aprovado",
        "Nome final",
        3,
    )


def test_formato_invalido_levanta_erro(estado):
    with pytest.raises(canonico.DecisaoInvalida):
        aplicar_decisoes(estado, mover=["sem-dois-pontos"])
    with pytest.raises(canonico.DecisaoInvalida):
        aplicar_decisoes(estado, aprovar=["ML-inexistente"])


def test_grupo_por_regra_nao_e_rejeitavel(estado):
    gid = next(iter(estado["materia"]["grupos"]))
    with pytest.raises(canonico.DecisaoInvalida):
        aplicar_decisoes(estado, rejeitar=[gid])
