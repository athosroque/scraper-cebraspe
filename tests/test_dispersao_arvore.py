"""Conceitos dispersos em pais diferentes (KAN-64, Fase 1)."""

import copy

import pytest

from scripts import detectar_dispersao_arvore as script
from src import arvore
from src.arvore import ArvoreMestre, criar_no, detectar_dispersos

pytestmark = pytest.mark.unit


def _arv(estrutura):
    """estrutura: {matéria: {assunto: [subassuntos]}} -> (árvore, ids por nome)."""
    arv = ArvoreMestre()
    ids = {}
    for m, assuntos in estrutura.items():
        mid = criar_no(arv, "materia", m, None)
        ids[m] = mid
        for a, subs in assuntos.items():
            aid = criar_no(arv, "assunto", a, mid)
            ids[(m, a)] = aid
            for s in subs:
                ids[(m, a, s)] = criar_no(arv, "subassunto", s, aid)
    return arv, ids


def _grupos(arv, **kw):
    return detectar_dispersos(arv, kw.get("questoes"))


def test_mesma_norma_escrita_de_tres_jeitos_agrupa():
    arv, ids = _arv(
        {
            "Orçamento": {
                "Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000)": [],
            },
            "Contabilidade": {
                "Lei Complementar nº 101/2000 e suas alterações": [],
            },
            "Auditoria": {"LC 101": []},
        }
    )
    grupos = [g for g in _grupos(arv) if g["motivo"] == "mesma_norma"]
    alta = [g for g in grupos if g["confianca"] == "alta"]
    assert len(alta) == 1
    assert len(alta[0]["nos"]) == 3


def test_conceito_generico_sob_dois_assuntos_nao_agrupa():
    arv, _ = _arv(
        {
            "Direito Administrativo": {
                "Atos": ["Conceito", "Disposições gerais"],
                "Contratos": ["Conceito", "Disposições gerais"],
            }
        }
    )
    assert _grupos(arv) == []


def test_nome_curto_de_uma_palavra_e_generico():
    arv, _ = _arv(
        {
            "Penal": {"Crimes": ["Prescrição"], "Penas": ["Prescrição"]},
        }
    )
    assert _grupos(arv) == []


def test_mesmo_nome_especifico_agrupa_com_alta():
    arv, _ = _arv(
        {
            "Gestão de Pessoas": {
                "Desempenho": ["Gestão por competências"],
                "Pessoas": ["Gestão por competências"],
            }
        }
    )
    (g,) = _grupos(arv)
    assert (g["motivo"], g["confianca"]) == ("mesmo_nome", "alta")


def test_ramos_diferentes_viram_media():
    arv, _ = _arv(
        {
            "Direito Penal": {"Penas": ["Livramento condicional"]},
            "Direito Penal Militar": {"Penas": ["Livramento condicional"]},
        }
    )
    (g,) = _grupos(arv)
    assert g["confianca"] == "media"


def test_nome_contido_e_media_e_nao_e_proposto():
    arv, ids = _arv(
        {
            "Administração Geral": {
                "Balanced scorecard": [],
                "Estratégia": ["Balanced Scorecard (BSC): principais conceitos"],
            }
        }
    )
    (g,) = _grupos(arv)
    assert (g["motivo"], g["confianca"]) == ("nome_contido", "media")
    copia = copy.deepcopy(arv)
    propostas, erros = script.propor_grupos(copia, [g])
    assert propostas == {} and erros == [] and copia.propostas == {}


def test_destino_pelo_numero_de_questoes_e_depois_nivel():
    arv, ids = _arv(
        {
            "Gestão": {"Desempenho": ["Gestão por competências"]},
            "Psicologia": {"Gestão por competências": []},
        }
    )
    sub = ids[("Gestão", "Desempenho", "Gestão por competências")]
    ass = ids[("Psicologia", "Gestão por competências")]
    (g,) = _grupos(arv, questoes={sub: 5, ass: 2})
    assert g["destino"] == sub
    assert g["operacoes"] == [{"origem": ass, "destino": sub}]  # entre níveis
    assert g["sem_operacao"] == []
    (g,) = _grupos(arv, questoes={sub: 2, ass: 2})
    assert g["destino"] == ass  # empate: assunto > subassunto
    assert g["operacoes"] == [{"origem": sub, "destino": ass}]


def test_no_de_nivel_diferente_com_filhos_fica_sem_operacao():
    arv, ids = _arv(
        {
            "Gestão": {"Desempenho": ["Gestão por competências"]},
            "Psicologia": {"Gestão por competências": ["Mapeamento"]},
        }
    )
    sub = ids[("Gestão", "Desempenho", "Gestão por competências")]
    ass = ids[("Psicologia", "Gestão por competências")]
    (g,) = _grupos(arv, questoes={sub: 5, ass: 2})
    assert g["destino"] == sub
    assert g["operacoes"] == []
    assert g["sem_operacao"] == [ass]


def test_destino_conta_questoes_do_no_fundido_no_destino():
    arv, ids = _arv(
        {
            "A": {"Plano plurianual": []},
            "B": {"Plano plurianual": []},
            "C": {"Plano plurianual": []},
        }
    )
    a, b, c = (ids[(m, "Plano plurianual")] for m in "ABC")
    arvore.fundir_nos(arv, c, b)  # c passa a contar como b
    (g,) = _grupos(arv, questoes={a: 3, b: 2, c: 2})
    assert g["destino"] == b
    assert c not in g["nos"]


def test_propostas_gravadas_como_proposto_sem_mudar_nos():
    arv, ids = _arv(
        {
            "Gestão": {"Desempenho": ["Gestão por competências"]},
            "Psicologia": {"Pessoas": ["Gestão por competências"]},
        }
    )
    antes = {i: (n.status, n.fundido_em, n.pai) for i, n in arv.nos.items()}
    (g,) = _grupos(arv)
    propostas, erros = script.propor_grupos(arv, [g])
    assert erros == [] and len(propostas) == 1
    (prop,) = arv.propostas.values()
    assert prop.status == "proposto" and prop.tipo == "fundir"
    assert prop.origem == "regra"
    assert {i: (n.status, n.fundido_em, n.pai) for i, n in arv.nos.items()} == antes
    # idempotente
    again, _ = script.propor_grupos(arv, [g])
    assert again == propostas and len(arv.propostas) == 1


def test_relatorio_lista_grupo_e_proposta():
    arv, _ = _arv(
        {
            "Gestão": {"Desempenho": ["Gestão por competências"]},
            "Psicologia": {"Pessoas": ["Gestão por competências"]},
        }
    )
    grupos = _grupos(arv)
    propostas, erros = script.propor_grupos(arv, grupos)
    texto = script.gerar_relatorio(arv, grupos, propostas, erros, gravou=True)
    assert "Gestão por competências" in texto
    assert next(iter(propostas.values())) in texto


def test_nos_da_mesma_norma_acha_a_lei_escrita_de_dois_jeitos():
    """ADR-030, KAN-64: a mesma norma em matérias diferentes é um só conceito."""
    arv, ids = _arv(
        {
            "Orçamento": {
                "Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000)": [],
            },
            "Contabilidade": {"Lei Complementar nº 101/2000": []},
        }
    )
    achados = arvore.nos_da_mesma_norma(arv, "Lei Complementar nº 101/2000")
    assert achados == sorted(
        [
            ids[
                (
                    "Orçamento",
                    "Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000)",
                )
            ],
            ids[("Contabilidade", "Lei Complementar nº 101/2000")],
        ]
    )


def test_nos_da_mesma_norma_ignora_recorte_do_tema():
    arv, ids = _arv(
        {
            "Direito Penal": {"Crimes previstos na Lei nº 9.605/1998": []},
            "Direito Ambiental": {"Lei nº 9.605/1998": []},
        }
    )
    assert arvore.nos_da_mesma_norma(arv, "Lei nº 9.605/1998") == [
        ids[("Direito Ambiental", "Lei nº 9.605/1998")]
    ]
    assert arvore.nos_da_mesma_norma(arv, "Crimes previstos na Lei nº 9.605/1998") == []


def test_nos_da_mesma_norma_ignora_fundido_e_aposentado():
    arv, ids = _arv(
        {
            "Orçamento": {"Lei nº 4.320/1964": []},
            "Contabilidade": {"Lei nº 4.320/1964": []},
            "Auditoria": {"Lei nº 4.320/1964": []},
        }
    )
    fundido = ids[("Orçamento", "Lei nº 4.320/1964")]
    aposentado = ids[("Contabilidade", "Lei nº 4.320/1964")]
    ativo = ids[("Auditoria", "Lei nº 4.320/1964")]
    arv.nos[fundido].status = "fundido"
    arv.nos[fundido].fundido_em = ativo
    arv.nos[aposentado].status = "aposentado"
    assert arvore.nos_da_mesma_norma(arv, "Lei nº 4.320/1964") == [ativo]


def test_nos_da_mesma_norma_respeita_ignorar():
    arv, ids = _arv(
        {
            "Orçamento": {"Lei nº 4.320/1964": []},
            "Contabilidade": {"Lei nº 4.320/1964": []},
        }
    )
    um = ids[("Orçamento", "Lei nº 4.320/1964")]
    outro = ids[("Contabilidade", "Lei nº 4.320/1964")]
    assert arvore.nos_da_mesma_norma(arv, "Lei nº 4.320/1964", ignorar={um}) == [outro]


def test_nos_da_mesma_norma_vazio_para_nome_sem_norma():
    arv, _ = _arv(
        {
            "Orçamento": {"Balanced Scorecard": []},
            "Administração": {"Balanced Scorecard": []},
        }
    )
    assert arvore.nos_da_mesma_norma(arv, "Balanced Scorecard") == []
