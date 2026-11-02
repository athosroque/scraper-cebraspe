"""Migração das chaves de mapeamento do subtópico em cadeia (KAN-93, M7)."""

import json

import pytest

from scripts import migrar_chaves_cadeia as mig
from src import arvore as arv_mod
from src.arvore import ArvoreMestre, criar_no, mapear
from src.canonico import arvore_apos_passo

CHAVE_ASSUNTO = "gestao de produtos|user experience ux"
CHAVE_ANTIGA = (
    f"{CHAVE_ASSUNTO}|metodologias ageis e experiencia do usuario design thinking"
)
CHAVE_NOVA = f"{CHAVE_ASSUNTO}|design thinking"


def _edital(subtopicos, caminho_origem=None):
    topico = {"nome": "User Experience (UX)", "subtopicos": subtopicos}
    if caminho_origem:
        topico["caminho_origem"] = caminho_origem
    return {
        "edital": "x.pdf",
        "concurso": {"slug": "XX_25", "orgao": "XX", "ano": 2025},
        "cargos": [],
        "resultados": [
            {
                "chunk_index": 0,
                "materia_chunk": "Gestão de Produtos",
                "materia_origem": "cabecalho",
                "taxonomia_extraida": {
                    "materia": "Gestão de Produtos",
                    "topicos": [topico],
                },
            }
        ],
    }


EDITAL_NOVO = _edital(
    ["Metodologias ágeis e experiência do usuário", "Design thinking"],
    {"Design thinking": ["Metodologias ágeis e experiência do usuário"]},
)


@pytest.fixture
def revisao(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps(EDITAL_NOVO), encoding="utf-8")
    return tmp_path


@pytest.fixture
def arvore():
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Gestão de Produtos", None, id_override="M-GP")
    criar_no(arv, "assunto", "User Experience (UX)", "M-GP", id_override="A-UX")
    criar_no(arv, "subassunto", "Design thinking", "A-UX", id_override="S-DT")
    criar_no(arv, "subassunto", "Outro", "A-UX", id_override="S-OUT")
    mapear(arv, "gestao de produtos", ["M-GP"])
    mapear(arv, CHAVE_ASSUNTO, ["A-UX"])
    return arv


def test_pares_de_chaves_recalcula_a_chave_antiga_pela_cadeia(revisao):
    pares, ambiguos, atuais = mig.pares_de_chaves(revisao)
    assert pares == {CHAVE_ANTIGA: CHAVE_NOVA}
    assert ambiguos == {}
    assert CHAVE_NOVA in atuais and CHAVE_ANTIGA not in atuais


def test_json_sem_caminho_origem_nao_gera_par(tmp_path):
    (tmp_path / "x.json").write_text(
        json.dumps(_edital(["Design thinking"])), encoding="utf-8"
    )
    assert mig.pares_de_chaves(tmp_path)[0] == {}


def test_dry_run_nao_altera_a_arvore(revisao, arvore):
    mapear(arvore, CHAVE_ANTIGA, ["S-DT"], origem="humano", status="aprovado")
    antes = {k: list(v) for k, v in arvore.mapeamentos.items()}
    plano = mig.planejar(arvore, revisao)
    assert plano.movidos == [(CHAVE_ANTIGA, CHAVE_NOVA)]
    assert {k: list(v) for k, v in arvore.mapeamentos.items()} == antes


def test_move_o_apontamento_preservando_origem_status_e_no(revisao, arvore):
    mapear(arvore, CHAVE_ANTIGA, ["S-DT"], origem="humano", status="aprovado")
    mig.aplicar_plano(arvore, mig.planejar(arvore, revisao))
    assert CHAVE_ANTIGA not in arvore.mapeamentos
    (m,) = arvore.mapeamentos[CHAVE_NOVA]
    assert (m.no_id, m.origem, m.status) == ("S-DT", "humano", "aprovado")


def test_chave_nova_com_os_mesmos_nos_descarta_a_antiga(revisao, arvore):
    mapear(arvore, CHAVE_ANTIGA, ["S-DT"])
    mapear(arvore, CHAVE_NOVA, ["S-DT"])
    plano = mig.planejar(arvore, revisao)
    assert plano.descartados == [(CHAVE_ANTIGA, CHAVE_NOVA)]
    mig.aplicar_plano(arvore, plano)
    assert CHAVE_ANTIGA not in arvore.mapeamentos and CHAVE_NOVA in arvore.mapeamentos


def test_conflito_de_nos_nao_altera_nada(revisao, arvore):
    mapear(arvore, CHAVE_ANTIGA, ["S-DT"])
    mapear(arvore, CHAVE_NOVA, ["S-OUT"])
    plano = mig.planejar(arvore, revisao)
    assert plano.conflitos == [(CHAVE_ANTIGA, CHAVE_NOVA)]
    mig.aplicar_plano(arvore, plano)
    assert set(arvore.mapeamentos) >= {CHAVE_ANTIGA, CHAVE_NOVA}


def test_antiga_sem_mapeamento_e_so_contada(revisao, arvore):
    plano = mig.planejar(arvore, revisao)
    assert plano.sem_mapeamento == [CHAVE_ANTIGA]
    assert plano.movidos == []


def test_main_dry_run_nao_grava_e_aplicar_grava_por_arvore_py(
    revisao, arvore, tmp_path_factory
):
    caminho = tmp_path_factory.mktemp("arv") / "arvore.json"
    mapear(arvore, CHAVE_ANTIGA, ["S-DT"])
    arv_mod.salvar(arvore, caminho)
    antes = caminho.read_bytes()
    assert mig.main([str(revisao), "--arvore", str(caminho)]) == 0
    assert caminho.read_bytes() == antes
    assert mig.main([str(revisao), "--arvore", str(caminho), "--aplicar"]) == 0
    assert CHAVE_NOVA in arv_mod.carregar(caminho).mapeamentos


def test_design_thinking_so_casa_por_nome_com_o_texto_proprio(arvore, tmp_path):
    """Com o pai mapeado, o nó "Design thinking" é achado pelo nome do filho; na
    forma em cadeia a chave nunca coincidia."""
    mapear(arvore, CHAVE_ASSUNTO, ["A-UX"])
    (tmp_path / "x.json").write_text(json.dumps(EDITAL_NOVO), encoding="utf-8")
    nova, _ = arvore_apos_passo(tmp_path, arvore)
    assert [m.no_id for m in nova.mapeamentos[CHAVE_NOVA]] == ["S-DT"]

    antigo = _edital(
        [
            "Metodologias ágeis e experiência do usuário",
            "Metodologias ágeis e experiência do usuário - Design thinking",
        ]
    )
    (tmp_path / "x.json").write_text(json.dumps(antigo), encoding="utf-8")
    nova, _ = arvore_apos_passo(tmp_path, arvore)
    assert CHAVE_ANTIGA not in nova.mapeamentos
