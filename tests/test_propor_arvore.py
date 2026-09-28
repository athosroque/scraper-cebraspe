"""Testes para scripts/propor_arvore.py com LLM mockado (Etapa 5B.2, ADR-030)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts import propor_arvore as pa
from src import arvore, llm_openrouter


def _resposta(propostas: list[dict]):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [
            {
                "message": {"content": json.dumps({"propostas": propostas})},
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
        patch.object(pa.time, "sleep"),
    ):
        yield


@pytest.fixture
def arvore_teste(tmp_path: Path):
    arv = arvore.ArvoreMestre()
    # Matéria padrão com 3 assuntos e subassuntos
    arvore.criar_no(
        arv, "materia", "DIREITO CONSTITUCIONAL TESTE", None, id_override="M-test1"
    )
    arvore.criar_no(
        arv, "assunto", "Direitos Fundamentais", "M-test1", id_override="A-1"
    )
    arvore.criar_no(arv, "subassunto", "Direito à vida", "A-1", id_override="S-1")
    arvore.criar_no(
        arv,
        "subassunto",
        "Direito à vida e integridade",
        "A-1",
        id_override="S-2",
    )

    arvore.criar_no(arv, "assunto", "Poder Judiciário", "M-test1", id_override="A-2")
    arvore.criar_no(
        arv, "subassunto", "Estrutura do Judiciário", "A-2", id_override="S-3"
    )

    arvore.criar_no(arv, "assunto", "Poder Executivo", "M-test1", id_override="A-3")

    # Matéria pequena com < 2 assuntos (deve ser pulada)
    arvore.criar_no(arv, "materia", "MATÉRIA PEQUENA", None, id_override="M-pequena")
    arvore.criar_no(
        arv, "assunto", "Assunto Único", "M-pequena", id_override="A-sozinho"
    )

    caminho = tmp_path / "arvore.json"
    arvore.salvar(arv, caminho)
    return arv, caminho


@pytest.fixture
def arvore_cd(tmp_path: Path):
    arv = arvore.ArvoreMestre()
    # M-841dde7520 (Composta CD 1)
    arvore.criar_no(
        arv,
        "materia",
        "DIREITO CONSTITUCIONAL E PROCESSO LEGISLATIVO",
        None,
        id_override="M-841dde7520",
    )
    arvore.criar_no(
        arv, "assunto", "Poder Legislativo", "M-841dde7520", id_override="A-cd1"
    )
    arvore.criar_no(
        arv,
        "assunto",
        "Processo Legislativo Ordinário",
        "M-841dde7520",
        id_override="A-cd2",
    )

    # M-d5adcb4de4 (Composta CD 2)
    arvore.criar_no(
        arv,
        "materia",
        "DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS",
        None,
        id_override="M-d5adcb4de4",
    )
    arvore.criar_no(
        arv,
        "assunto",
        "Regimento da Câmara",
        "M-d5adcb4de4",
        id_override="A-cd3",
    )

    # Destinos
    arvore.criar_no(
        arv, "materia", "DIREITO CONSTITUCIONAL", None, id_override="M-5edb4898a0"
    )
    arvore.criar_no(
        arv, "assunto", "Poder Legislativo", "M-5edb4898a0", id_override="A-const1"
    )

    arvore.criar_no(
        arv,
        "materia",
        "REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM E CÓDIGO DE ÉTICA",
        None,
        id_override="M-e96f4dbbb5",
    )
    arvore.criar_no(
        arv, "assunto", "Regimento Interno", "M-e96f4dbbb5", id_override="A-reg1"
    )

    # Mapeamentos dos 2 itens de matéria
    arvore.mapear(
        arv,
        "direito constitucional e processo legislativo",
        ["M-841dde7520"],
        origem="semente",
        status="aprovado",
    )
    arvore.mapear(
        arv,
        "nocoes de direito constitucional e de regimento interno da camara dos deputados",
        ["M-d5adcb4de4"],
        origem="semente",
        status="aprovado",
    )

    caminho = tmp_path / "arvore_cd.json"
    arvore.salvar(arv, caminho)
    return arv, caminho


@pytest.fixture
def arvore_licitacoes(tmp_path: Path):
    arv = arvore.ArvoreMestre()
    arvore.criar_no(
        arv, "materia", "DIREITO ADMINISTRATIVO", None, id_override="M-6f50f4f1dd"
    )
    # Composto
    arvore.criar_no(
        arv,
        "assunto",
        "Licitações e contratos administrativos",
        "M-6f50f4f1dd",
        id_override="A-4529f205f7",
    )
    arvore.criar_no(
        arv, "subassunto", "Pregão eletrônico", "A-4529f205f7", id_override="S-lic1"
    )
    arvore.criar_no(
        arv,
        "subassunto",
        "Execução de contratos administrativos",
        "A-4529f205f7",
        id_override="S-lic2",
    )

    # Destinos irmãos
    arvore.criar_no(
        arv, "assunto", "Licitação", "M-6f50f4f1dd", id_override="A-2261b82645"
    )
    arvore.criar_no(
        arv,
        "assunto",
        "Contratos administrativos",
        "M-6f50f4f1dd",
        id_override="A-91e52e6c2e",
    )

    # Remapeamento do edital já proposto
    arv.mapeamentos["direito administrativo|licitacoes e contratos administrativos"] = [
        arvore.Mapeamento(no_id="A-4529f205f7", origem="semente", status="aprovado")
    ]
    arvore.propor(
        arv,
        tipo="remapear",
        args={
            "item": "direito administrativo|licitacoes e contratos administrativos",
            "de": "A-4529f205f7",
            "para": ["A-2261b82645", "A-91e52e6c2e"],
        },
        origem="regra",
        justificativa="Remapeamento para irmãos",
        materia="M-6f50f4f1dd",
    )

    caminho = tmp_path / "arvore_licitacoes.json"
    arvore.salvar(arv, caminho)
    return arv, caminho


class TestValidacaoELoopTentativas:
    def test_resposta_valida_grava_proposta_llm(self, arvore_teste):
        arv, _ = arvore_teste
        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")

        # Inverte ids_locais para encontrar os nomes locais de S-1, S-2, S-3 e A-1
        global_para_local = {gid: lid for lid, gid in ids_locais.items()}
        s1_local = global_para_local["S-1"]
        s2_local = global_para_local["S-2"]
        s3_local = global_para_local["S-3"]
        a1_local = global_para_local["A-1"]

        propostas_llm = [
            {
                "tipo": "fundir",
                "ids": [s2_local, s1_local],
                "justificativa": "Mesmo tema de direito à vida",
            },
            {
                "tipo": "mover",
                "ids": [s3_local, a1_local],
                "justificativa": "Mover para novo pai",
            },
        ]

        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta(propostas_llm)
        ) as mock_post:
            gravadas = pa.propor_lote(
                arv, prompt, ids_locais, "M-test1", conta, dry_run=False
            )

        assert gravadas == 2
        assert mock_post.call_count == 1
        payload = mock_post.call_args.kwargs["json"]
        assert payload["reasoning"] == pa.REASONING_PADRAO["reasoning"]
        assert payload["usage"] == {"include": True}

        # Verifica propostas gravadas
        assert len(arv.propostas) == 2
        props = list(arv.propostas.values())
        assert all(p.status == "proposto" and p.origem == "llm" for p in props)

        # Propostas não alteram a árvore ativa antes da aprovação
        assert arv.nos["S-1"].status == "ativo"
        assert arv.nos["S-2"].status == "ativo"
        assert arv.nos["S-3"].pai == "A-2"

        # Métricas
        assert conta.lotes_ok == 1
        assert conta.lotes_falhos == 0
        assert conta.custo_usd == pytest.approx(0.001)
        assert conta.propostas["fundir"] == 1
        assert conta.propostas["mover"] == 1

    def test_id_inventado_gera_falha_tipada_e_segunda_tentativa_corrige(
        self, arvore_teste
    ):
        arv, _ = arvore_teste
        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")
        global_para_local = {gid: lid for lid, gid in ids_locais.items()}

        invalida = [
            {
                "tipo": "fundir",
                "ids": [global_para_local["S-1"], "n999"],
                "justificativa": "id inventado",
            }
        ]
        valida = [
            {
                "tipo": "fundir",
                "ids": [global_para_local["S-2"], global_para_local["S-1"]],
                "justificativa": "correto",
            }
        ]

        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(valida)],
        ) as mock_post:
            gravadas = pa.propor_lote(
                arv, prompt, ids_locais, "M-test1", conta, dry_run=False
            )

        assert gravadas == 1
        assert conta.chamadas == 2
        assert conta.lotes_ok == 1
        assert conta.falhas[pa.STATUS_FALHA_ID_DESCONHECIDO] == 1

        # Verifica que a 2ª tentativa levou o erro no prompt
        segunda_chamada = mock_post.call_args_list[1].kwargs["json"]["messages"][1][
            "content"
        ]
        assert "ATENÇÃO: uma resposta anterior foi rejeitada" in segunda_chamada
        assert pa.STATUS_FALHA_ID_DESCONHECIDO in segunda_chamada

    def test_nivel_errado_gera_falha_operacao_invalida(self, arvore_teste):
        arv, _ = arvore_teste
        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")
        global_para_local = {gid: lid for lid, gid in ids_locais.items()}

        # Fusão entre assunto (A-1) e subassunto (S-1): proibida!
        invalida = [
            {
                "tipo": "fundir",
                "ids": [global_para_local["A-1"], global_para_local["S-1"]],
                "justificativa": "fusao de niveis diferentes",
            }
        ]
        valida = []

        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(valida)],
        ) as mock_post:
            pa.propor_lote(arv, prompt, ids_locais, "M-test1", conta, dry_run=False)

        assert conta.chamadas == 2
        assert conta.falhas[pa.STATUS_FALHA_OPERACAO_INVALIDA] == 1
        segunda = mock_post.call_args_list[1].kwargs["json"]["messages"][1]["content"]
        assert "ATENÇÃO" in segunda
        assert pa.STATUS_FALHA_OPERACAO_INVALIDA in segunda

    def test_verificacao_prompt_segunda_tentativa_contem_feedback(self, arvore_teste):
        arv, _ = arvore_teste
        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")

        invalida = [
            {
                "tipo": "fundir",
                "ids": ["n_inexistente_1", "n_inexistente_2"],
                "justificativa": "IDs falsos",
            }
        ]
        valida = []

        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(valida)],
        ) as mock_post:
            pa.propor_lote(arv, prompt, ids_locais, "M-test1", conta, dry_run=False)

        assert mock_post.call_count == 2
        segunda_chamada_msg = mock_post.call_args_list[1].kwargs["json"]["messages"][1][
            "content"
        ]
        assert (
            "ATENÇÃO: uma resposta anterior foi rejeitada (falha_id_desconhecido)"
            in segunda_chamada_msg
        )
        assert "IDs locais desconhecidos ou inventados" in segunda_chamada_msg
        assert "n_inexistente_1" in segunda_chamada_msg

    def test_movimento_nivel_errado_gera_falha_operacao_invalida(self, arvore_teste):
        arv, _ = arvore_teste
        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")
        global_para_local = {gid: lid for lid, gid in ids_locais.items()}

        # Mover assunto A-2 para subassunto S-1: nível do pai é inválido!
        invalida = [
            {
                "tipo": "mover",
                "ids": [global_para_local["A-2"], global_para_local["S-1"]],
                "justificativa": "pai com nivel invalido",
            }
        ]
        valida = []

        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(valida)],
        ):
            pa.propor_lote(arv, prompt, ids_locais, "M-test1", conta, dry_run=False)

        assert conta.falhas[pa.STATUS_FALHA_OPERACAO_INVALIDA] == 1

    def test_ciclo_gera_falha_operacao_invalida(self, arvore_teste):
        arv, _ = arvore_teste
        # Cria ciclo estrutural: M-test1 aponta para S-1 (que aponta para A-1)
        arv.nos["M-test1"].pai = "S-1"

        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")
        ids_locais["n_materia"] = "M-test1"
        global_para_local = {gid: lid for lid, gid in ids_locais.items()}

        invalida = [
            {
                "tipo": "mover",
                "ids": [global_para_local["A-1"], "n_materia"],
                "justificativa": "mover criando ciclo",
            }
        ]
        valida = []

        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(valida)],
        ):
            pa.propor_lote(arv, prompt, ids_locais, "M-test1", conta, dry_run=False)

        assert conta.falhas[pa.STATUS_FALHA_OPERACAO_INVALIDA] == 1

    def test_falha_persistente_nas_duas_tentativas_nao_grava_nada(self, arvore_teste):
        arv, _ = arvore_teste
        prompt, ids_locais = pa.montar_prompt_materia(arv, "M-test1")

        invalida = [
            {
                "tipo": "fundir",
                "ids": ["n998", "n999"],
                "justificativa": "ids inventados",
            }
        ]
        conta = pa.Contabilidade()
        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[_resposta(invalida), _resposta(invalida)],
        ):
            gravadas = pa.propor_lote(
                arv, prompt, ids_locais, "M-test1", conta, dry_run=False
            )

        assert gravadas == 0
        assert conta.chamadas == 2
        assert conta.lotes_falhos == 1
        assert conta.falhas[pa.STATUS_FALHA_ID_DESCONHECIDO] == 2
        assert len(arv.propostas) == 0


class TestRegrasEscopoEIdempotencia:
    def test_materia_menos_de_dois_assuntos_e_pulada(self, arvore_teste, tmp_path):
        _, caminho = arvore_teste
        revisao_dir = tmp_path / "revisao"
        revisao_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(llm_openrouter.requests, "post") as mock_post:
            conta = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-pequena",
                dry_run=False,
            )

        assert mock_post.call_count == 0
        assert conta.chamadas == 0

    def test_idempotencia_hash_subarvore(self, arvore_teste, tmp_path):
        _, caminho = arvore_teste
        revisao_dir = tmp_path / "revisao"
        revisao_dir.mkdir(parents=True, exist_ok=True)

        # 1ª execução avalia a matéria
        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta([])
        ) as mock_post:
            conta1 = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-test1",
            )
        assert mock_post.call_count == 1
        assert conta1.lotes_ok == 1

        # 2ª execução sobre a mesma árvore sem mudanças: pula!
        with patch.object(llm_openrouter.requests, "post") as mock_post:
            conta2 = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-test1",
            )
        assert mock_post.call_count == 0
        assert conta2.chamadas == 0

        # 3ª execução com --reavaliar: força reavaliação!
        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta([])
        ) as mock_post:
            conta3 = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-test1",
                reavaliar=True,
            )
        assert mock_post.call_count == 1
        assert conta3.lotes_ok == 1

    def test_dry_run_nao_grava_nem_chama_llm(self, arvore_teste, tmp_path):
        _, caminho = arvore_teste
        revisao_dir = tmp_path / "revisao"
        conteudo_antes = caminho.read_text(encoding="utf-8")

        with patch.object(llm_openrouter.requests, "post") as mock_post:
            conta = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-test1",
                dry_run=True,
            )

        assert mock_post.call_count == 0
        assert conta.chamadas == 0
        assert caminho.read_text(encoding="utf-8") == conteudo_antes

    def test_so_regras_apenas_deteccao_deterministica(
        self, arvore_licitacoes, tmp_path
    ):
        _, caminho = arvore_licitacoes
        revisao_dir = tmp_path / "revisao"

        with patch.object(llm_openrouter.requests, "post") as mock_post:
            conta = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                so_regras=True,
            )

        assert mock_post.call_count == 0
        assert conta.chamadas == 0


class TestEscoposEspeciais:
    def test_escopo_composto_cd_e_processo_legislativo(self, arvore_cd, tmp_path):
        _, caminho = arvore_cd
        revisao_dir = tmp_path / "revisao"

        # Simula resposta do LLM redistribuindo os 3 assuntos das compostas:
        # A-cd1 funde em A-const1 (Constitucional)
        # A-cd2 move para Processo Legislativo
        # A-cd3 move para Regimento Interno (M-e96f4dbbb5)
        def _fake_post(*args, **kwargs):
            messages = kwargs["json"]["messages"]
            prompt_usuario = messages[1]["content"]

            # Extrair os IDs locais do prompt
            mapa_prompt = {}
            for linha in prompt_usuario.splitlines():
                if linha.startswith("- n"):
                    partes = linha.split(":")
                    lid = partes[0].replace("-", "").strip()
                    rotulo = partes[1].strip()
                    mapa_prompt[rotulo] = lid

            # Localizar IDs das matérias e assuntos no prompt
            lid_const1 = next(
                lid
                for r, lid in mapa_prompt.items()
                if "Poder Legislativo" in r and "DIREITO CONSTITUCIONAL" in r
            )
            lid_proc_leg = next(
                lid
                for r, lid in mapa_prompt.items()
                if "[matéria] Processo Legislativo" in r
            )
            lid_reg_materia = next(
                lid
                for r, lid in mapa_prompt.items()
                if "REGIMENTO INTERNO DA CÂMARA" in r and "[matéria]" in r
            )
            lid_cd1 = next(
                lid
                for r, lid in mapa_prompt.items()
                if "Poder Legislativo" in r and "a redistribuir" in r
            )
            lid_cd2 = next(
                lid
                for r, lid in mapa_prompt.items()
                if "Processo Legislativo Ordinário" in r
            )
            lid_cd3 = next(
                lid for r, lid in mapa_prompt.items() if "Regimento da Câmara" in r
            )

            propostas = [
                {
                    "tipo": "fundir",
                    "ids": [lid_cd1, lid_const1],
                    "justificativa": "Mesmo tema",
                },
                {
                    "tipo": "mover",
                    "ids": [lid_cd2, lid_proc_leg],
                    "justificativa": "Materia especifica",
                },
                {
                    "tipo": "mover",
                    "ids": [lid_cd3, lid_reg_materia],
                    "justificativa": "Regimento",
                },
            ]
            return _resposta(propostas)

        with patch.object(
            llm_openrouter.requests, "post", side_effect=_fake_post
        ) as mock_post:
            conta = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-841dde7520,M-d5adcb4de4",
            )

        assert mock_post.call_count == 1
        assert conta.lotes_ok == 1

        arv_resultado = arvore.carregar(caminho)

        # 1. Proposta humano de criação de "Processo Legislativo"
        props_criar = [
            p
            for p in arv_resultado.propostas.values()
            if p.tipo == "criar" and p.args.get("nome") == "Processo Legislativo"
        ]
        assert len(props_criar) == 1
        assert props_criar[0].origem == "humano"
        assert "2026-09-28" in props_criar[0].justificativa

        # 2. Propostas do LLM
        props_llm = [p for p in arv_resultado.propostas.values() if p.origem == "llm"]
        assert len(props_llm) == 3

        # 3. Propostas de remapeamento dos 2 itens
        props_remap = [
            p for p in arv_resultado.propostas.values() if p.tipo == "remapear"
        ]
        assert len(props_remap) == 2
        assert all(p.origem == "regra" for p in props_remap)

        # 4. Propostas de aposentadoria das compostas
        props_ap = [
            p for p in arv_resultado.propostas.values() if p.tipo == "aposentar"
        ]
        assert len(props_ap) == 2
        nos_aposentados = {p.args["no"] for p in props_ap}
        assert "M-841dde7520" in nos_aposentados
        assert "M-d5adcb4de4" in nos_aposentados

    def test_escopo_licitacoes_redistribuicao_e_aposentadoria(
        self, arvore_licitacoes, tmp_path
    ):
        _, caminho = arvore_licitacoes
        revisao_dir = tmp_path / "revisao"

        def _fake_post(*args, **kwargs):
            messages = kwargs["json"]["messages"]
            prompt_usuario = messages[1]["content"]

            # Extrair os IDs locais
            mapa_prompt = {}
            for linha in prompt_usuario.splitlines():
                if linha.strip().startswith("- n"):
                    partes = linha.split(":")
                    lid = partes[0].replace("-", "").strip()
                    rotulo = partes[1].strip()
                    mapa_prompt[rotulo] = lid

            lid_lic1 = next(
                lid for r, lid in mapa_prompt.items() if "Pregão eletrônico" in r
            )
            lid_lic2 = next(
                lid for r, lid in mapa_prompt.items() if "Execução de contratos" in r
            )
            lid_lic_pai = next(
                lid for r, lid in mapa_prompt.items() if "[assunto] Licitação" in r
            )
            lid_cont_pai = next(
                lid
                for r, lid in mapa_prompt.items()
                if "[assunto] Contratos administrativos" in r
            )

            # Mover S-lic1 para Licitação e S-lic2 para Contratos
            propostas = [
                {
                    "tipo": "mover",
                    "ids": [lid_lic1, lid_lic_pai],
                    "justificativa": "Licitação",
                },
                {
                    "tipo": "mover",
                    "ids": [lid_lic2, lid_cont_pai],
                    "justificativa": "Contratos",
                },
            ]
            return _resposta(propostas)

        with patch.object(
            llm_openrouter.requests, "post", side_effect=_fake_post
        ) as mock_post:
            conta = pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-6f50f4f1dd",
            )

        assert mock_post.call_count == 1
        assert conta.lotes_ok == 1

        arv_resultado = arvore.carregar(caminho)

        # Aposentadoria de A-4529f205f7 deve ter sido gerada com sucesso!
        props_ap = [
            p
            for p in arv_resultado.propostas.values()
            if p.tipo == "aposentar" and p.args.get("no") == "A-4529f205f7"
        ]
        assert len(props_ap) == 1
        assert props_ap[0].origem == "regra"

    def test_escopo_licitacoes_sem_redistribuicao_completa_posterga_aposentadoria(
        self, arvore_licitacoes, tmp_path
    ):
        _, caminho = arvore_licitacoes
        revisao_dir = tmp_path / "revisao"

        def _fake_post(*args, **kwargs):
            messages = kwargs["json"]["messages"]
            prompt_usuario = messages[1]["content"]
            mapa_prompt = {}
            for linha in prompt_usuario.splitlines():
                if linha.strip().startswith("- n"):
                    partes = linha.split(":")
                    lid = partes[0].replace("-", "").strip()
                    rotulo = partes[1].strip()
                    mapa_prompt[rotulo] = lid

            lid_lic1 = next(
                lid for r, lid in mapa_prompt.items() if "Pregão eletrônico" in r
            )
            lid_lic_pai = next(
                lid for r, lid in mapa_prompt.items() if "[assunto] Licitação" in r
            )

            # Move só 1 dos 2 subassuntos: A-4529f205f7 ainda possui filhos ativos!
            propostas = [
                {
                    "tipo": "mover",
                    "ids": [lid_lic1, lid_lic_pai],
                    "justificativa": "Licitação",
                },
            ]
            return _resposta(propostas)

        with patch.object(llm_openrouter.requests, "post", side_effect=_fake_post):
            pa.propor_arvore(
                revisao_dir=revisao_dir,
                arvore_path=caminho,
                materias="M-6f50f4f1dd",
            )

        arv_resultado = arvore.carregar(caminho)

        # Não deve haver proposta de aposentadoria para A-4529f205f7
        props_ap = [
            p
            for p in arv_resultado.propostas.values()
            if p.tipo == "aposentar" and p.args.get("no") == "A-4529f205f7"
        ]
        assert len(props_ap) == 0


class TestMainCLI:
    def test_main_cli_output_json(self, arvore_teste, capsys):
        _, caminho = arvore_teste
        pa.main(["--dry-run", "--materias", "M-test1", "--arvore", str(caminho)])
        captured = capsys.readouterr()
        res = json.loads(captured.out)
        assert res["chamadas"] == 0
        assert res["lotes_ok"] == 0
        assert "falhas" in res
        assert "propostas" in res
