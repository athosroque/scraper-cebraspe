"""Proposta de sinônimos pelo LLM com lista fechada (Etapa 5B), resposta mockada."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts import propor_sinonimos as ps
from src import canonico, llm_openrouter
from tests.test_canonico import _nomes


def _resposta(grupos: list[dict]):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [
            {
                "message": {"content": json.dumps({"grupos": grupos})},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": 0.001,
        },
    }
    return resp


@pytest.fixture(autouse=True)
def _sem_rede_nem_telemetria():
    with (
        patch.object(llm_openrouter, "langfuse_client", return_value=None),
        patch.object(ps.time, "sleep"),
    ):
        yield


@pytest.fixture
def estado_lote():
    estado = canonico.estado_vazio()
    nomes = _nomes(
        materias={
            "ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA": ["PF_25"],
            "ADMINISTRAÇÃO ORÇAMENTÁRIA E FINANCEIRA": ["STM_25"],
            "LÍNGUA PORTUGUESA": ["PF_25", "STM_25"],
        }
    )
    canonico.aplicar_regras(estado, nomes)
    escopos = canonico.montar_escopos(estado, "materia", nomes)
    lotes = ps.montar_lotes(escopos)
    assert len(lotes) == 1
    return estado, lotes[0]


def _ids_locais_por_nome(estado, lote):
    ps.montar_prompt(estado, lote)
    return {
        estado["materia"]["grupos"][gid]["nome"]: local
        for local, gid in lote.ids_locais.items()
    }


class TestProporLote:
    def test_resposta_valida_vira_proposta(self, estado_lote):
        estado, lote = estado_lote
        ids = _ids_locais_por_nome(estado, lote)
        afo = [
            ids["ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA"],
            ids["ADMINISTRAÇÃO ORÇAMENTÁRIA E FINANCEIRA"],
        ]
        grupos = [
            {
                "ids": afo,
                "nome_canonico": "Administração Financeira e Orçamentária",
                "justificativa": "ordem",
            },
            {"ids": [ids["LÍNGUA PORTUGUESA"]], "nome_canonico": "Língua Portuguesa"},
        ]
        lote.ids_locais.clear()
        conta = ps.Contabilidade()
        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta(grupos)
        ) as post:
            assert ps.propor_lote(estado, lote, conta) == 1
        assert post.call_count == 1
        payload = post.call_args.kwargs["json"]
        assert payload["usage"] == {"include": True}
        assert payload["max_tokens"] == ps.MAX_TOKENS

        propostas = [
            g for g in estado["materia"]["grupos"].values() if g["status"] == "proposto"
        ]
        assert len(propostas) == 1
        assert propostas[0]["origem"] == "llm"
        assert len(propostas[0]["membros"]) == 2
        assert conta.custo_usd == pytest.approx(0.001)
        # Proposta não muda o mapeamento aprovado.
        assert len(set(canonico.indice_aprovado(estado).materia.values())) == 3

    def test_id_desconhecido_e_falha_tipada_e_segunda_tentativa_leva_o_erro(
        self, estado_lote
    ):
        estado, lote = estado_lote
        ids = _ids_locais_por_nome(estado, lote)
        lote.ids_locais.clear()
        invalida = [{"ids": [*ids.values(), "i99"], "nome_canonico": "x"}]
        valida = [{"ids": [i], "nome_canonico": n} for n, i in ids.items()]
        conta = ps.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(valida)],
        ) as post:
            assert (
                ps.propor_lote(estado, lote, conta) == 0
            )  # só singletons: nada a propor
        assert conta.falhas == {canonico.STATUS_FALHA_ID_DESCONHECIDO: 1}
        assert conta.chamadas == 2 and conta.lotes_ok == 1
        segunda = post.call_args_list[1].kwargs["json"]["messages"][1]["content"]
        assert "ATENÇÃO" in segunda and canonico.STATUS_FALHA_ID_DESCONHECIDO in segunda

    def test_id_faltante_nas_duas_tentativas_nao_grava_nada(self, estado_lote):
        estado, lote = estado_lote
        ids = _ids_locais_por_nome(estado, lote)
        lote.ids_locais.clear()
        incompleta = [{"ids": list(ids.values())[:2], "nome_canonico": "x"}]
        conta = ps.Contabilidade()
        antes = json.dumps(estado, sort_keys=True)
        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta(incompleta)
        ):
            assert ps.propor_lote(estado, lote, conta) == 0
        assert conta.falhas == {canonico.STATUS_FALHA_ID_AUSENTE: 2}
        assert conta.lotes_falhos == 1
        assert json.dumps(estado, sort_keys=True) == antes

    def test_falha_de_rede_fica_tipada(self, estado_lote):
        estado, lote = estado_lote
        conta = ps.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=llm_openrouter.requests.Timeout("lento"),
        ):
            assert ps.propor_lote(estado, lote, conta) == 0
        assert conta.falhas == {llm_openrouter.STATUS_FALHA_TIMEOUT: 2}


class TestMontarLotes:
    def test_escopos_pequenos_dividem_lote_sem_quebrar_escopo(self):
        escopos = [
            canonico.Escopo(
                "assunto", f"M{i}", f"m{i}", [f"g{i}_{j}" for j in range(30)]
            )
            for i in range(4)
        ]
        lotes = ps.montar_lotes(escopos, limite=60)
        assert [sum(len(b[1]) for b in lote.blocos) for lote in lotes] == [60, 60]

    def test_escopo_grande_so_divide_acima_do_limite_de_escopo(self):
        escopo = canonico.Escopo("materia", None, "todas", [f"g{j}" for j in range(93)])
        assert len(ps.montar_lotes([escopo], limite=90)) == 1
        assert len(ps.montar_lotes([escopo], limite=90, limite_escopo=50)) == 2


class TestRobustez:
    def test_grupo_sem_nome_canonico_recebe_nome_da_regra(self, estado_lote):
        estado, lote = estado_lote
        ids = _ids_locais_por_nome(estado, lote)
        lote.ids_locais.clear()
        afo = [
            ids["ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA"],
            ids["ADMINISTRAÇÃO ORÇAMENTÁRIA E FINANCEIRA"],
        ]
        grupos = [{"ids": afo}, {"ids": [ids["LÍNGUA PORTUGUESA"]]}]
        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta(grupos)
        ):
            assert ps.propor_lote(estado, lote, ps.Contabilidade()) == 1
        proposta = next(
            g for g in estado["materia"]["grupos"].values() if g["status"] == "proposto"
        )
        assert proposta["nome"].startswith("ADMINISTRAÇÃO")

    def test_bloco_ja_avaliado_nao_volta_ao_llm(self):
        estado = canonico.estado_vazio()
        nomes = _nomes(materias={"X": ["A"], "Y": ["B"]})
        canonico.aplicar_regras(estado, nomes)
        escopos = canonico.montar_escopos(estado, "materia", nomes)
        assert len(escopos) == 1
        canonico.marcar_avaliados(estado, "materia", escopos[0].itens, None)
        assert canonico.montar_escopos(estado, "materia", nomes) == []
        assert (
            len(canonico.montar_escopos(estado, "materia", nomes, reavaliar=True)) == 1
        )
        # Nome novo: o bloco volta inteiro.
        nomes2 = _nomes(materias={"X": ["A"], "Y": ["B"], "Z": ["C"]})
        canonico.aplicar_regras(estado, nomes2)
        assert len(canonico.montar_escopos(estado, "materia", nomes2)[0].itens) == 3
