"""Testes unitários do orquestrador Dagster C2 (D5a, KAN-31).

Cobre:
- Carregamento de Definitions e AssetGraph
- Sincronização de partições dinâmicas
- Execução com funções mockadas (process_contest, revisar_edital_piloto, processar_fila, classificar_todas_questoes)
- Portão humano: parada no portão (pendente), aprovação (aprovado) e retomada
- Execução do lote da C1 em modo conferência
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from dagster import AssetKey, DagsterInstance

from src.c2 import assets as assets_c2
from src.c2.assets import _buscar_edital
from src.c2.definitions import defs
from src.c2.partitions import (
    CONCURSOS_PARTITIONS_NAME,
    sincronizar_particoes_inventario,
)


def _gravar_edital(pasta, nome, slug, status):
    """JSON de edital no formato real (slug dentro de `concurso`, nome de PDF)."""
    (pasta / nome).write_text(
        json.dumps(
            {"concurso": {"slug": slug}, "status_revisao_humana": status},
        ),
        encoding="utf-8",
    )


@pytest.fixture
def revisao_tmp(tmp_path, monkeypatch):
    pasta = tmp_path / "revisao"
    pasta.mkdir()
    monkeypatch.setattr(assets_c2, "REVISAO_DIR", pasta)
    return pasta


@pytest.fixture
def instance():
    inst = DagsterInstance.ephemeral()
    inst.add_dynamic_partitions(
        CONCURSOS_PARTITIONS_NAME, ["SEFA_PR_25", "BANRISUL_25", "CONCURSO_TESTE"]
    )
    return inst


def test_definitions_carrega_e_valida_estrutura():
    """Definitions carrega sem erros e expõe o job lote_concursos."""
    assert defs is not None
    job = defs.get_job_def("lote_concursos")
    assert job.name == "lote_concursos"

    graph = defs.get_asset_graph()
    asset_keys = (
        graph.get_all_asset_keys()
        if hasattr(graph, "get_all_asset_keys")
        else graph.all_asset_keys
    )
    assert len(asset_keys) == 13
    assert AssetKey("p0") in asset_keys
    assert AssetKey("p1") in asset_keys
    assert AssetKey("p4") in asset_keys
    assert AssetKey("p8") in asset_keys


def test_sincronizacao_particoes_inventario(instance):
    """Sincroniza partições dinâmicas a partir do inventário."""
    adicionados = sincronizar_particoes_inventario(instance)
    assert len(adicionados) > 0
    partitions = instance.get_dynamic_partitions(CONCURSOS_PARTITIONS_NAME)
    assert "SEFA_PR_25" in partitions
    assert "BANRISUL_25" in partitions


def test_assets_funcoes_mockadas(instance, revisao_tmp):
    """Executa o pipeline com as funções mockadas verificando chamadas."""
    job = defs.get_job_def("lote_concursos")

    with (
        patch(
            "src.spider.CebraspeSpider.process_contest", return_value={"provas": []}
        ) as mock_spider,
        patch(
            "scripts.revisar_taxonomia_piloto.revisar_edital_piloto", return_value={}
        ),
        patch("src.stats_writer.gravar_estatisticas"),
        patch("scripts.extrair_questoes.processar_fila", return_value=0) as mock_fila,
        patch("scripts.atualizar_revisao.atualizar_artefatos_revisao") as mock_revisao,
        patch(
            "scripts.classificar_questoes.classificar_todas_questoes",
            return_value=MagicMock(chamadas=0, itens_classificados=0),
        ) as mock_classif,
        patch("playwright.sync_api.sync_playwright") as mock_pw,
    ):
        _gravar_edital(revisao_tmp, "Ed_1_Teste.json", "CONCURSO_TESTE", "APROVADO")
        mock_pw.return_value.__enter__.return_value.chromium.launch.return_value.new_page.return_value = MagicMock()
        res = job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_TESTE",
            run_config={
                "ops": {
                    "p1": {"config": {"conferencia": False}},
                    "p3": {"config": {"conferencia": False, "exigir_aprovacao": False}},
                    "p4": {"config": {"conferencia": False}},
                    "p8": {"config": {"conferencia": False}},
                    "p10": {"config": {"conferencia": False}},
                }
            },
            asset_selection=[
                AssetKey("p0"),
                AssetKey("p1"),
                AssetKey("p2"),
                AssetKey("p3"),
                AssetKey("p4"),
                AssetKey("p8"),
                AssetKey("p10"),
            ],
        )

        assert res.success
        assert mock_spider.call_count == 1
        assert mock_classif.call_count == 1
        assert mock_fila.call_count == 1
        assert mock_revisao.call_count >= 1


def test_portao_humano_parada_quando_pendente(instance, revisao_tmp):
    """O portão bloqueia a execução quando o edital está pendente e exigir_aprovacao=True."""
    _gravar_edital(
        revisao_tmp,
        "hash123.json",
        "CONCURSO_TESTE",
        "PENDENTE — aguardando revisão do dono",
    )
    job = defs.get_job_def("lote_concursos")
    with pytest.raises(Exception) as exc_info:
        job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_TESTE",
            run_config={
                "ops": {
                    "p3": {"config": {"exigir_aprovacao": True, "conferencia": True}},
                }
            },
            asset_selection=[AssetKey(f"p{i}") for i in range(4)],
        )
    assert "PortaoHumanoBloqueado" in type(exc_info.value).__name__ or (
        "PortaoHumanoBloqueado" in str(exc_info.value)
    )


def test_portao_humano_sem_edital_bloqueia(instance, revisao_tmp):
    """Sem edital, exigir_aprovacao=True bloqueia (não é mais 'ok')."""
    job = defs.get_job_def("lote_concursos")
    with pytest.raises(Exception) as exc_info:
        job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_TESTE",
            run_config={
                "ops": {
                    "p3": {"config": {"exigir_aprovacao": True, "conferencia": True}},
                }
            },
            asset_selection=[AssetKey(f"p{i}") for i in range(4)],
        )
    assert "PortaoHumanoBloqueado" in str(exc_info.value) or (
        "PortaoHumanoBloqueado" in type(exc_info.value).__name__
    )


def test_p3_sem_edital_status_sem_edital(instance, revisao_tmp):
    """Em conferência sem exigir aprovação, o P3 devolve status sem_edital."""
    job = defs.get_job_def("lote_concursos")
    res = job.execute_in_process(
        instance=instance,
        partition_key="CONCURSO_TESTE",
        run_config={"ops": {"p3": {"config": {"conferencia": True}}}},
        asset_selection=[AssetKey(f"p{i}") for i in range(4)],
    )
    assert res.success
    assert res.output_for_node("p3")["status"] == "sem_edital"


def test_p3_producao_sem_edital_para_sem_chamar_llm(instance, revisao_tmp):
    """Produção sem edital para com erro claro e nunca chama o LLM."""
    job = defs.get_job_def("lote_concursos")
    with patch("scripts.revisar_taxonomia_piloto.revisar_edital_piloto") as llm:
        with pytest.raises(Exception):
            job.execute_in_process(
                instance=instance,
                partition_key="CONCURSO_TESTE",
                run_config={
                    "ops": {
                        "p1": {"config": {"conferencia": True}},
                        "p3": {"config": {"conferencia": False}},
                    }
                },
                asset_selection=[AssetKey(f"p{i}") for i in range(4)],
            )
        assert llm.call_count == 0


def test_buscar_edital_formato_real(revisao_tmp):
    """Aprovado, pendente e sem edital, com JSONs no formato real e sem patch."""
    _gravar_edital(revisao_tmp, "Ed_1_A.json", "CONC_A", "APROVADO — dono em 2026")
    _gravar_edital(revisao_tmp, "hash_b.json", "CONC_B", "PENDENTE")
    (revisao_tmp / "Ed_1_A.auditoria.json").write_text("{}", encoding="utf-8")

    from src.stats_writer import STATUS_REVISAO_APROVADO, status_revisao

    achado_a = _buscar_edital("CONC_A")
    achado_b = _buscar_edital("CONC_B")
    assert achado_a is not None and achado_b is not None
    assert status_revisao(achado_a[1]) == STATUS_REVISAO_APROVADO
    assert status_revisao(achado_b[1]) != STATUS_REVISAO_APROVADO
    assert _buscar_edital("CONC_C") is None


@pytest.mark.db
def test_contrato_buscar_edital_contra_revisao_piloto_real():
    """Contrato: os editais reais do piloto são achados e os aprovados, aprovados."""
    from src.stats_writer import STATUS_REVISAO_APROVADO, status_revisao

    esperado = {"PF_25_ADM": True, "STM_25": True, "SEFA_PR_25": False}
    for slug, aprovado in esperado.items():
        achado = _buscar_edital(slug, assets_c2.RAIZ / "revisao_piloto")
        assert achado is not None, slug
        assert (status_revisao(achado[1]) == STATUS_REVISAO_APROVADO) is aprovado, slug
    assert _buscar_edital("BANRISUL_25", assets_c2.RAIZ / "revisao_piloto") is not None


def test_portao_humano_aprovacao_e_retomada(instance, revisao_tmp):
    """Quando aprovado pelo dono (APROVADO...), o portão permite prosseguir para P4."""
    _gravar_edital(
        revisao_tmp,
        "edital.json",
        "CONCURSO_TESTE",
        "APROVADO — pelo dono em 2026-10-21",
    )
    job = defs.get_job_def("lote_concursos")
    with (
        patch("scripts.extrair_questoes.processar_fila", return_value=0),
        patch("scripts.atualizar_revisao.atualizar_artefatos_revisao"),
        patch("src.stats_writer.gravar_estatisticas"),
    ):
        res = job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_TESTE",
            run_config={
                "ops": {
                    "p3": {"config": {"exigir_aprovacao": True, "conferencia": True}},
                    "p4": {"config": {"conferencia": False}},
                }
            },
            asset_selection=[AssetKey(f"p{i}") for i in range(4)] + [AssetKey("p4")],
        )
        assert res.success
        assert res.output_for_node("p3")["aprovado"] is True


def test_p1_conferencia_sem_arquivos_falha_se_exigir(instance, revisao_tmp, tmp_path):
    """P1 em conferência sem arquivos devolve status honesto e falha com exigir."""
    job = defs.get_job_def("lote_concursos")
    with patch.object(assets_c2, "DATA_DIR", tmp_path / "vazio"):
        res = job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_TESTE",
            run_config={"ops": {"p1": {"config": {"conferencia": True}}}},
            asset_selection=[AssetKey("p0"), AssetKey("p1")],
        )
        assert res.output_for_node("p1")["status"] == "conferencia_sem_arquivos"
        with pytest.raises(Exception):
            job.execute_in_process(
                instance=instance,
                partition_key="CONCURSO_TESTE",
                run_config={
                    "ops": {
                        "p1": {
                            "config": {"conferencia": True, "exigir_aprovacao": True}
                        }
                    }
                },
                asset_selection=[AssetKey("p0"), AssetKey("p1")],
            )


def test_banco_dagster_fora_sai_com_codigo_1(monkeypatch):
    """Sem o banco do Dagster, executar_c2 sai com código 1 (sem instância efêmera)."""
    from scripts import executar_c2

    monkeypatch.setenv("DAGSTER_PG_HOST", "127.0.0.1")
    monkeypatch.setenv("DAGSTER_PG_PORT", "1")
    monkeypatch.setenv(
        "DAGSTER_HOME", str(executar_c2.Path(__file__).parent.parent / "dagster_home")
    )
    with pytest.raises(SystemExit) as exc:
        executar_c2.main(["--concursos", "SEFA_PR_25"])
    assert exc.value.code == 1


def test_lote_c1_modo_conferencia_status_honestos(instance):
    """Lote da C1 em conferência: o sucesso do job não prova nada sozinho, então
    os status por etapa dizem o que rodou. A prova de 'não muda nada' são as
    contagens do banco antes e depois (relatório da rodada)."""
    job = defs.get_job_def("lote_concursos")

    for slug in ["SEFA_PR_25", "BANRISUL_25"]:
        res = job.execute_in_process(
            instance=instance,
            partition_key=slug,
            run_config={
                "ops": {
                    f"p{i}": {
                        "config": {"conferencia": True, "exigir_aprovacao": False}
                    }
                    for i in [
                        "0",
                        "1",
                        "2",
                        "3",
                        "4",
                        "4b",
                        "5",
                        "6",
                        "7",
                        "8",
                        "9",
                        "10",
                        "11",
                    ]
                }
            },
        )
        assert res.success
        saidas = {n: res.output_for_node(n) for n in ["p0", "p2", "p3", "p4", "p8"]}
        assert saidas["p0"]["status"] == "ok"
        assert saidas["p2"]["status"] == "ok"
        assert saidas["p3"]["status"] == "ok"
        assert saidas["p3"]["aprovado"] is False
        assert saidas["p4"]["status"] == "conferencia_sem_acao"
        assert saidas["p8"]["status"] == "conferencia_dry_run"
        for n in ["p5", "p6", "p7", "p9", "p10", "p11"]:
            assert res.output_for_node(n)["status"] == "ok"


def test_portao_p3_bloqueia_etapa_seguinte_quando_pendente(instance, revisao_tmp):
    """Portão P3 bloqueia execução de etapas seguintes quando o concurso está pendente."""
    _gravar_edital(revisao_tmp, "edital_pendente.json", "CONCURSO_PENDENTE", "PENDENTE")
    job = defs.get_job_def("lote_concursos")
    with pytest.raises(Exception):
        job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_PENDENTE",
            run_config={
                "ops": {
                    "p3": {"config": {"exigir_aprovacao": True, "conferencia": True}},
                    "p4": {"config": {"conferencia": True}},
                }
            },
            asset_selection=[
                AssetKey("p0"),
                AssetKey("p1"),
                AssetKey("p2"),
                AssetKey("p3"),
                AssetKey("p4"),
            ],
        )


def test_portao_p7_bloqueia_quando_propostas_pendentes(instance):
    """Portão P7 bloqueia execução quando há propostas de árvore pendentes."""
    job = defs.get_job_def("lote_concursos")
    with patch(
        "src.c2.assets.verificar_portao_arvore",
        return_value=(False, [{"id": "P-1"}]),
    ):
        with pytest.raises(Exception):
            job.execute_in_process(
                instance=instance,
                partition_key="CONCURSO_TESTE",
                run_config={
                    "ops": {
                        "p7": {
                            "config": {"exigir_aprovacao": True, "conferencia": True}
                        },
                    }
                },
                asset_selection=[AssetKey("p7")],
            )


def test_invariante_piloto_k22_bloqueia_quando_divergente(instance):
    """P0 ou P4 bloqueia quando a invariante do piloto K22 diverge."""
    from src.c2.checks import ViolacaoInvariantePiloto

    divergencia = {
        "status": "divergente",
        "valido": False,
        "divergencias": {"itens": {"esperado": 2800, "obtido": 2799}},
    }
    with patch(
        "src.c2.assets.verificar_invariante_piloto",
        side_effect=ViolacaoInvariantePiloto(divergencia),
    ):
        job = defs.get_job_def("lote_concursos")
        with pytest.raises(Exception):
            job.execute_in_process(
                instance=instance,
                partition_key="CONCURSO_TESTE",
                run_config={
                    "ops": {
                        "p0": {"config": {"conferencia": False}},
                    }
                },
                asset_selection=[AssetKey("p0")],
            )


def _rodar_p3_p4(instance, partition_key, ops):
    job = defs.get_job_def("lote_concursos")
    return job.execute_in_process(
        instance=instance,
        partition_key=partition_key,
        run_config={"ops": ops},
        asset_selection=[AssetKey("p3"), AssetKey("p4")],
        raise_on_error=False,
    )


def test_fora_de_conferencia_edital_pendente_bloqueia_p3_por_padrao(
    instance, revisao_tmp
):
    """conferencia=False sem exigir_aprovacao explícito: o portão P3 é exigido e o P4 não roda."""
    _gravar_edital(revisao_tmp, "ed.json", "CONCURSO_TESTE", "PENDENTE")
    res = _rodar_p3_p4(
        instance,
        "CONCURSO_TESTE",
        {"p3": {"config": {"conferencia": False}}},
    )
    assert not res.success
    assert "PortaoHumanoBloqueado" in str(
        [e.event_specific_data for e in res.get_step_failure_events()]
    )
    assert not [e for e in res.get_step_success_events() if e.step_key.startswith("p4")]


def test_fora_de_conferencia_edital_aprovado_passa_p3(instance, revisao_tmp):
    _gravar_edital(revisao_tmp, "ed.json", "CONCURSO_TESTE", "APROVADO")
    job = defs.get_job_def("lote_concursos")
    res = job.execute_in_process(
        instance=instance,
        partition_key="CONCURSO_TESTE",
        run_config={"ops": {"p3": {"config": {"conferencia": False}}}},
        asset_selection=[AssetKey("p3")],
    )
    assert res.success
    assert res.output_for_node("p3")["status"] == "ok"


def test_conferencia_edital_pendente_nao_bloqueia_por_padrao(instance, revisao_tmp):
    _gravar_edital(revisao_tmp, "ed.json", "CONCURSO_TESTE", "PENDENTE")
    job = defs.get_job_def("lote_concursos")
    res = job.execute_in_process(
        instance=instance,
        partition_key="CONCURSO_TESTE",
        run_config={"ops": {"p3": {"config": {"conferencia": True}}}},
        asset_selection=[AssetKey("p3")],
    )
    assert res.success


def test_fora_de_conferencia_p7_bloqueia_por_padrao(instance):
    job = defs.get_job_def("lote_concursos")
    with patch(
        "src.c2.assets.verificar_portao_arvore",
        return_value=(False, [{"id": "P-1"}]),
    ):
        res = job.execute_in_process(
            instance=instance,
            partition_key="CONCURSO_TESTE",
            run_config={"ops": {"p7": {"config": {"conferencia": False}}}},
            asset_selection=[AssetKey("p7")],
            raise_on_error=False,
        )
    assert not res.success
    assert "PortaoHumanoBloqueado" in str(
        [e.event_specific_data for e in res.get_step_failure_events()]
    )


def test_aprovacao_efetiva_regra_central():
    assert assets_c2.aprovacao_efetiva(False, False) is True
    assert assets_c2.aprovacao_efetiva(True, False) is False
    assert assets_c2.aprovacao_efetiva(True, True) is True
