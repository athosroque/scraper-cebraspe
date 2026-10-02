"""5F.8: `/api/v1/eu/resumo` e `/api/v1/eu/prioridades`."""

from datetime import date

import pytest
from tests.test_stats_writer import _postgres_disponivel

from app.servicos.contas_servico import contar_dias_seguidos

banco = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)


def _errada(gabarito):
    return "E" if gabarito == "C" else "C"


def test_dias_seguidos():
    hoje = date(2026, 10, 2)
    assert contar_dias_seguidos([], hoje) == 0
    assert contar_dias_seguidos([hoje], hoje) == 1
    # Hoje ainda sem resposta não quebra a sequência de ontem.
    assert contar_dias_seguidos([date(2026, 10, 1), date(2026, 9, 30)], hoje) == 2
    assert contar_dias_seguidos([hoje, date(2026, 9, 30)], hoje) == 1
    assert contar_dias_seguidos([date(2026, 9, 30)], hoje) == 0


@banco
def test_sem_login_401(cliente):
    assert cliente.get("/api/v1/eu/resumo").status_code == 401
    assert cliente.get("/api/v1/eu/prioridades").status_code == 401


@banco
def test_resumo_e_prioridades_conhecidas(cliente_logado):
    c, _ = cliente_logado
    vazio = c.get("/api/v1/eu/resumo").json()
    assert vazio == {
        "resolvidas": 0,
        "certas": 0,
        "erradas": 0,
        "percentual": None,
        "nota_liquida": 0,
        "erradas_pendentes": 0,
        "dias_seguidos": 0,
    }
    assert c.get("/api/v1/eu/prioridades").json() == []

    # Um subassunto com pelo menos 3 questões válidas.
    base = c.get(
        "/api/v1/questoes",
        params={"concurso": "PF_25_ADM", "anuladas": "excluir", "tamanho_pagina": 50},
    ).json()["itens"]
    alvo = None
    for q in base:
        for n in q["nos"]:
            if n["papel"] == "principal" and n["no_nivel"] == "subassunto":
                qs = c.get(
                    "/api/v1/questoes",
                    params={"no_id": n["no_id"], "anuladas": "excluir"},
                ).json()["itens"]
                if len(qs) >= 3:
                    alvo, qs = n["no_id"], qs[:3]
                    break
        if alvo:
            break
    assert alvo

    # 1 certa e 2 erradas; a 1ª errada antes, para valer a mais recente.
    certa, *erradas = qs
    c.post(
        "/api/v1/respostas",
        json={
            "questao_chave": certa["questao_chave"],
            "resposta": _errada(certa["gabarito"]),
        },
    )
    c.post(
        "/api/v1/respostas",
        json={"questao_chave": certa["questao_chave"], "resposta": certa["gabarito"]},
    )
    for q in erradas:
        c.post(
            "/api/v1/respostas",
            json={
                "questao_chave": q["questao_chave"],
                "resposta": _errada(q["gabarito"]),
            },
        )

    resumo = c.get("/api/v1/eu/resumo").json()
    assert resumo == {
        "resolvidas": 3,
        "certas": 1,
        "erradas": 2,
        "percentual": 33.3,
        "nota_liquida": -1,
        "erradas_pendentes": 2,
        "dias_seguidos": 1,
    }

    prioridades = c.get("/api/v1/eu/prioridades").json()
    nosso = next(p for p in prioridades if p["no_id"] == alvo)
    assert (nosso["respondidas"], nosso["acertos"], nosso["taxa_erro"]) == (3, 1, 66.7)
    assert nosso["incidencia"] > 0
    assert nosso["prioridade"] == pytest.approx(
        nosso["incidencia"] * 66.7 / 100, abs=0.01
    )
    assert all(p["respondidas"] >= 2 for p in prioridades)
    ordem = [p["prioridade"] for p in prioridades]
    assert ordem == sorted(ordem, reverse=True)
    assert len(c.get("/api/v1/eu/prioridades?limite=1").json()) == 1
    assert c.get("/api/v1/eu/prioridades?limite=0").status_code == 422

    pagina = c.get("/conta").text
    assert "O que estudar agora" in pagina
    assert "Nota líquida" in pagina
    assert "Dias seguidos" in pagina
    assert "/questoes?no_id=" + alvo.replace(":", "%3A") in pagina or alvo in pagina
