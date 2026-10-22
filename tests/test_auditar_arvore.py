"""Auditoria da hierarquia da árvore contra a lista fechada (Etapa 5B.3)."""

import json

import pytest

from scripts import auditar_arvore
from src.arvore import ArvoreMestre, carregar, criar_no, salvar


@pytest.fixture
def ambiente(tmp_path):
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-1")
    criar_no(arv, "assunto", "Agentes públicos", "M-1", id_override="A-1")
    criar_no(arv, "subassunto", "Lei nº 8.112/1990", "A-1", id_override="S-1")
    criar_no(arv, "materia", "Ética", None, id_override="M-2")
    criar_no(arv, "assunto", "Lei nº 8.112/1990", "M-2", id_override="A-2")
    path = tmp_path / "arvore.json"
    salvar(arv, path)
    disciplinas = tmp_path / "disciplinas.json"

    def rodar(lista, *args):
        disciplinas.write_text(
            json.dumps({"disciplinas": [{"id": i, "nome": n} for i, n in lista]}),
            encoding="utf-8",
        )
        return auditar_arvore.main(
            [
                *args,
                "--arvore",
                str(path),
                "--disciplinas",
                str(disciplinas),
                "--classificacao",
                str(tmp_path / "nao_existe.json"),
            ]
        )

    return path, rodar


def test_verde_com_a_lista_fechada_e_avisa_norma_repetida(ambiente, capsys):
    _, rodar = ambiente
    assert rodar([("M-1", "Direito Administrativo"), ("M-2", "Ética")], "--normas") == 0
    saida = capsys.readouterr().out
    assert "| Direito Administrativo | M-1 | 0 | 1/1 |" in saida
    assert "Aviso: 1 normas em mais de um nó ativo" in saida
    assert "A-2 (Ética › Lei nº 8.112/1990); S-1" in saida


def test_falha_com_materia_fora_da_lista_ou_nome_diferente(ambiente, capsys):
    _, rodar = ambiente
    assert rodar([("M-1", "Direito Administrativo")]) == 1
    assert "matéria fora da lista fechada: M-2 'Ética'" in capsys.readouterr().err
    assert rodar([("M-1", "Dir. Adm."), ("M-2", "Ética"), ("M-3", "TI")]) == 1
    erro = capsys.readouterr().err
    assert "nome difere da lista: M-1" in erro
    assert "disciplina da lista não está ativa: M-3 'TI'" in erro


def test_falha_com_nivel_errado(ambiente, capsys):
    path, rodar = ambiente
    arv = carregar(path)
    arv.nos["S-1"].pai = "M-2"
    salvar(arv, path)
    assert rodar([("M-1", "Direito Administrativo"), ("M-2", "Ética")]) == 1
    assert "S-1 (subassunto) com pai inválido: M-2 (materia, ativo)" in (
        capsys.readouterr().err
    )
