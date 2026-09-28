import json

import pytest

from scripts.semear_arvore import semear
from src.arvore import ArvoreInvalida, carregar, criar_no, salvar


@pytest.fixture
def sinonimos_json(tmp_path):
    path = tmp_path / "sinonimos.json"
    data = {
        "versao_esquema": 1,
        "materia": {
            "entradas": {
                "M-1": {
                    "chave_regra": "m1",
                    "pai": None,
                    "presente": True,
                    "nomes": [{"chave": "m1", "nome": "Materia 1"}],
                }
            },
            "grupos": {
                "MR-1": {
                    "nome": "Materia 1",
                    "origem": "regra",
                    "status": "aprovado",
                    "membros": ["M-1"],
                    "escopo": None,
                }
            },
        },
        "assunto": {
            "entradas": {
                "A-1": {
                    "chave_regra": "a1",
                    "pai": "M-1",
                    "presente": True,
                    "nomes": [{"materia": "m1", "chave": "a1", "nome": "Assunto 1"}],
                }
            },
            "grupos": {
                "AR-1": {
                    "nome": "Assunto 1",
                    "origem": "regra",
                    "status": "aprovado",
                    "membros": ["A-1"],
                    "escopo": "MR-1",
                }
            },
        },
        "subassunto": {"entradas": {}, "grupos": {}},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_semear_arvore(sinonimos_json, tmp_path):
    arvore_path = tmp_path / "arvore.json"

    # 1ª execução
    semear(sinonimos_json, arvore_path)

    assert arvore_path.exists()

    arvore = carregar(arvore_path)
    assert len(arvore.nos) == 2
    assert "MR-1" in arvore.nos
    assert "AR-1" in arvore.nos

    assert arvore.nos["MR-1"].nivel == "materia"
    assert arvore.nos["MR-1"].nome == "Materia 1"

    assert arvore.nos["AR-1"].nivel == "assunto"
    assert arvore.nos["AR-1"].pai == "MR-1"

    # Mapeamentos
    assert "m1" in arvore.mapeamentos
    assert arvore.mapeamentos["m1"][0].no_id == "MR-1"

    assert "m1|a1" in arvore.mapeamentos
    assert arvore.mapeamentos["m1|a1"][0].no_id == "AR-1"

    # 2ª execução sem diff (idempotência)
    conteudo1 = arvore_path.read_text(encoding="utf-8")
    semear(sinonimos_json, arvore_path)
    conteudo2 = arvore_path.read_text(encoding="utf-8")
    assert conteudo1 == conteudo2


def test_semear_nao_sobrescreve_arvore_curada(sinonimos_json, tmp_path):
    arvore_path = tmp_path / "arvore.json"
    semear(sinonimos_json, arvore_path)
    arvore = carregar(arvore_path)
    criar_no(arvore, "assunto", "Assunto curado", "MR-1")
    salvar(arvore, arvore_path)
    curada = arvore_path.read_text(encoding="utf-8")

    with pytest.raises(ArvoreInvalida, match="--forcar"):
        semear(sinonimos_json, arvore_path)
    assert arvore_path.read_text(encoding="utf-8") == curada

    semear(sinonimos_json, arvore_path, forcar=True)
    assert "Assunto curado" not in arvore_path.read_text(encoding="utf-8")
