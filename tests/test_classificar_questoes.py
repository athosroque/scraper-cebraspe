"""Testes unitários e de integração com LLM mockado para scripts/classificar_questoes.py (Etapa 5D)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts import classificar_questoes as cq_script
from src import arvore, classificacao, llm_openrouter


def _resposta_mock(itens: list[dict], custo: float = 0.001):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [
            {
                "message": {"content": json.dumps({"itens": itens})},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 50,
            "total_tokens": 250,
            "cost": custo,
        },
    }
    return resp


@pytest.fixture(autouse=True)
def _sem_rede_nem_telemetria():
    with (
        patch.object(llm_openrouter, "langfuse_client", return_value=None),
        patch.object(cq_script.time, "sleep"),
    ):
        yield


@pytest.fixture
def arvore_teste() -> arvore.ArvoreMestre:
    arv = arvore.ArvoreMestre()
    arvore.criar_no(arv, "materia", "DIREITO ADMINISTRATIVO", None, id_override="M-ADM")
    arvore.criar_no(
        arv, "assunto", "Atos Administrativos", "M-ADM", id_override="A-ATOS"
    )
    arvore.criar_no(
        arv, "subassunto", "Anulação e revogação", "A-ATOS", id_override="S-ANUL"
    )
    arvore.criar_no(arv, "subassunto", "Competência", "A-ATOS", id_override="S-COMP")
    arvore.criar_no(
        arv, "assunto", "Contratos Administrativos", "M-ADM", id_override="A-CONT"
    )
    arvore.criar_no(
        arv, "subassunto", "Rescisão contratual", "A-CONT", id_override="S-RESC"
    )
    return arv


class TestFormatadorArvoreCandidatos:
    def test_formatar_arvore_candidatos_hierarquia(self):
        candidatos = {
            "M-ADM": {
                "id": "M-ADM",
                "nome": "DIREITO ADMINISTRATIVO",
                "nivel": "materia",
                "pai_id": None,
                "materia_id": "M-ADM",
            },
            "A-ATOS": {
                "id": "A-ATOS",
                "nome": "Atos Administrativos",
                "nivel": "assunto",
                "pai_id": "M-ADM",
                "materia_id": "M-ADM",
            },
            "S-ANUL": {
                "id": "S-ANUL",
                "nome": "Anulação e revogação",
                "nivel": "subassunto",
                "pai_id": "A-ATOS",
                "assunto_id": "A-ATOS",
                "materia_id": "M-ADM",
            },
        }

        texto, local_para_id, id_para_local = cq_script.formatar_arvore_candidatos(
            candidatos
        )

        assert "[C1] DIREITO ADMINISTRATIVO (matéria)" in texto
        assert "  [C2] Atos Administrativos (assunto)" in texto
        assert "    [C3] Anulação e revogação (subassunto)" in texto

        assert local_para_id["C1"] == "M-ADM"
        assert local_para_id["C2"] == "A-ATOS"
        assert local_para_id["C3"] == "S-ANUL"

        assert id_para_local["M-ADM"] == "C1"
        assert id_para_local["A-ATOS"] == "C2"
        assert id_para_local["S-ANUL"] == "C3"


class TestPosValidacao:
    def test_pos_validacao_rejeita_id_desconhecido(self):
        local_para_id = {"C1": "M-ADM", "C2": "A-ATOS"}
        validador = cq_script._pos_validacao_classificacao(local_para_id, [1, 2])

        resp_invalida = cq_script.RespostaClassificacaoLote(
            itens=[
                cq_script.ItemClassificado(numero=1, nos=["C1"], confianca="alta"),
                cq_script.ItemClassificado(numero=2, nos=["C999"], confianca="alta"),
            ]
        )

        desfecho = validador(resp_invalida, "")
        assert desfecho.motivo == cq_script.STATUS_FALHA_ID_DESCONHECIDO
        assert "C999" in str(desfecho.erro)

    def test_pos_validacao_rejeita_divergencia_itens(self):
        local_para_id = {"C1": "M-ADM"}
        validador = cq_script._pos_validacao_classificacao(local_para_id, [1, 2, 3])

        # Faltando item 3 e com item extra 4
        resp_divergente = cq_script.RespostaClassificacaoLote(
            itens=[
                cq_script.ItemClassificado(numero=1, nos=["C1"], confianca="alta"),
                cq_script.ItemClassificado(numero=2, nos=["C1"], confianca="alta"),
                cq_script.ItemClassificado(numero=4, nos=["C1"], confianca="alta"),
            ]
        )

        desfecho = validador(resp_divergente, "")
        assert desfecho.motivo == cq_script.STATUS_FALHA_ITENS_DIVERGENTES
        assert "Faltando: ['3']" in str(desfecho.erro)
        assert "Sobrando: ['4']" in str(desfecho.erro)

    def test_pos_validacao_rejeita_inconsistencias_schema(self):
        local_para_id = {"C1": "M-ADM", "C2": "A-ATOS"}
        validador = cq_script._pos_validacao_classificacao(local_para_id, [1])

        # Caso 1: nenhum_serve=True com nós atribuídos
        resp1 = cq_script.RespostaClassificacaoLote(
            itens=[cq_script.ItemClassificado(numero=1, nos=["C1"], nenhum_serve=True)]
        )
        assert validador(resp1, "").motivo == cq_script.STATUS_FALHA_VALIDACAO_SCHEMA

        # Caso 2: nenhum_serve=False mas sem nós
        resp2 = cq_script.RespostaClassificacaoLote(
            itens=[cq_script.ItemClassificado(numero=1, nos=[], nenhum_serve=False)]
        )
        assert validador(resp2, "").motivo == cq_script.STATUS_FALHA_VALIDACAO_SCHEMA

        # Caso 3: nós duplicados no mesmo item
        resp3 = cq_script.RespostaClassificacaoLote(
            itens=[
                cq_script.ItemClassificado(
                    numero=1, nos=["C1", "C1"], nenhum_serve=False
                )
            ]
        )
        assert validador(resp3, "").motivo == cq_script.STATUS_FALHA_VALIDACAO_SCHEMA


class TestClassificacaoPipeline:
    def test_classificacao_primeira_tentativa_sucesso(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path
    ):
        classif_path = tmp_path / "classificacao.json"
        cq = classificacao.ClassificacaoQuestoes()
        conta = cq_script.Contabilidade()

        itens = [
            {"numero": 1, "enunciado": "Ato nulo deve ser anulado.", "secao": "Atos"},
            {"numero": 2, "enunciado": "Competência é irrenunciável.", "secao": "Atos"},
        ]
        local_para_id = {"C1": "S-ANUL", "C2": "S-COMP"}

        resposta_llm = [
            {"numero": 1, "nos": ["C1"], "confianca": "alta", "nenhum_serve": False},
            {"numero": 2, "nos": ["C2"], "confianca": "media", "nenhum_serve": False},
        ]

        with patch.object(
            llm_openrouter.requests, "post", return_value=_resposta_mock(resposta_llm)
        ) as mock_post:
            resp = cq_script.classificar_lote(
                prompt_usuario="prompt de teste",
                numeros_esperados=[1, 2],
                local_para_id=local_para_id,
                metadata_base={"caderno": "094_PF_CB1_01"},
                conta=conta,
            )

        assert resp is not None
        assert mock_post.call_count == 1
        assert conta.lotes_ok == 1
        assert conta.chamadas == 1

        # Mapeia na classificação
        for it_resp in resp.itens:
            num = it_resp.numero
            it_orig = next(x for x in itens if x["numero"] == num)
            chave = f"PF_25_ADM|094_PF_CB1_01|{num}"
            h = classificacao.calcular_hash_enunciado(it_orig["enunciado"])
            nos_papeis = [
                (local_para_id[lid], "principal", False) for lid in it_resp.nos
            ]
            classificacao.mapear_questao(
                cq,
                arvore_teste,
                chave=chave,
                hash_enunciado=h,
                nos=nos_papeis,
                confianca=it_resp.confianca,
                fora_do_edital=False,
                origem="llm",
                status="proposto",
            )

        classificacao.salvar(cq, classif_path)
        assert classif_path.exists()

        cq_salvo = classificacao.carregar(classif_path)
        assert len(cq_salvo.registros) == 2

        reg1 = cq_salvo.registros["PF_25_ADM|094_PF_CB1_01|1"]
        assert reg1.apontamentos[0].no_id == "S-ANUL"
        assert reg1.apontamentos[0].confianca == "alta"
        assert reg1.apontamentos[0].fora_do_edital is False
        assert reg1.apontamentos[0].status == "proposto"

        reg2 = cq_salvo.registros["PF_25_ADM|094_PF_CB1_01|2"]
        assert reg2.apontamentos[0].no_id == "S-COMP"
        assert reg2.apontamentos[0].confianca == "media"

    def test_recuperacao_segunda_tentativa_apos_id_invalido(self):
        conta = cq_script.Contabilidade()
        local_para_id = {"C1": "S-ANUL"}

        resp_invalida = [
            {"numero": 1, "nos": ["C999"], "confianca": "alta", "nenhum_serve": False}
        ]
        resp_valida = [
            {"numero": 1, "nos": ["C1"], "confianca": "alta", "nenhum_serve": False}
        ]

        with patch.object(
            llm_openrouter.requests,
            "post",
            side_effect=[
                _resposta_mock(resp_invalida),
                _resposta_mock(resp_valida),
            ],
        ) as mock_post:
            resp = cq_script.classificar_lote(
                prompt_usuario="prompt de teste",
                numeros_esperados=[1],
                local_para_id=local_para_id,
                metadata_base={"caderno": "CAD1"},
                conta=conta,
            )

        assert resp is not None
        assert mock_post.call_count == 2
        assert conta.chamadas == 2
        assert conta.lotes_ok == 1
        assert conta.falhas[cq_script.STATUS_FALHA_ID_DESCONHECIDO] == 1

        # Verifica injeção do erro no prompt da segunda tentativa
        msg_segunda = mock_post.call_args_list[1].kwargs["json"]["messages"][1][
            "content"
        ]
        assert "ATENÇÃO: Sua resposta anterior foi rejeitada" in msg_segunda
        assert "falha_id_desconhecido" in msg_segunda
        assert "C999" in msg_segunda

    def test_roteamento_passada_reserva_quando_nenhum_serve(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path
    ):
        classif_path = tmp_path / "classificacao.json"
        cq = classificacao.ClassificacaoQuestoes()
        conta = cq_script.Contabilidade()

        # Item 1 tem nó na preferencial (S-ANUL)
        # Item 2 marca nenhum_serve=True na preferencial, mas encontra S-RESC na reserva!
        itens = [
            {"numero": 1, "enunciado": "Anulação de ato.", "texto_base_id": None},
            {"numero": 2, "enunciado": "Rescisão de contrato.", "texto_base_id": None},
        ]

        cands_pref = {
            "M-ADM": {
                "id": "M-ADM",
                "nome": "DIREITO ADMINISTRATIVO",
                "nivel": "materia",
                "materia_id": "M-ADM",
            },
            "A-ATOS": {
                "id": "A-ATOS",
                "nome": "Atos Administrativos",
                "nivel": "assunto",
                "materia_id": "M-ADM",
            },
            "S-ANUL": {
                "id": "S-ANUL",
                "nome": "Anulação",
                "nivel": "subassunto",
                "materia_id": "M-ADM",
                "assunto_id": "A-ATOS",
            },
        }

        # Simula resposta preferencial (item 2 sem nó)
        resp_pref = [
            {"numero": 1, "nos": ["C3"], "confianca": "alta", "nenhum_serve": False},
            {"numero": 2, "nos": [], "confianca": "alta", "nenhum_serve": True},
        ]
        # Simula resposta na reserva (item 2 encontra S-RESC)
        resp_res = [
            {"numero": 2, "nos": ["C6"], "confianca": "media", "nenhum_serve": False}
        ]

        # Monta mock do banco
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        with (
            patch.object(
                cq_script.candidatos_questao,
                "candidatos_preferenciais",
                return_value=cands_pref,
            ),
            patch.object(
                cq_script,
                "carregar_dados_caderno",
                return_value=(
                    {
                        "prova_id": 1,
                        "nome_caderno": "CAD_TESTE",
                        "concurso_slug": "CONC",
                        "tipo": "objetiva_basica",
                        "orgao": "TESTE",
                    },
                    itens,
                    {},
                ),
            ),
            patch.object(
                llm_openrouter.requests,
                "post",
                side_effect=[_resposta_mock(resp_pref), _resposta_mock(resp_res)],
            ) as mock_post,
        ):
            cq_script.processar_caderno(
                mock_conn,
                prova_id=1,
                arv=arvore_teste,
                cq=cq,
                conta=conta,
                classificacao_path=classif_path,
            )

        assert mock_post.call_count == 2
        assert conta.total_fora_edital == 1

        reg1 = cq.registros["CONC|CAD_TESTE|1"]
        assert reg1.apontamentos[0].no_id == "S-ANUL"
        assert reg1.apontamentos[0].fora_do_edital is False

        reg2 = cq.registros["CONC|CAD_TESTE|2"]
        assert reg2.apontamentos[0].no_id == "S-RESC"
        assert reg2.apontamentos[0].fora_do_edital is True
        assert reg2.apontamentos[0].status == "proposto"

    def test_gravacao_sem_no_quando_ambas_passadas_falham(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path
    ):
        classif_path = tmp_path / "classificacao.json"
        cq = classificacao.ClassificacaoQuestoes()
        conta = cq_script.Contabilidade()

        itens = [
            {
                "numero": 1,
                "enunciado": "Tema totalmente alienígena.",
                "texto_base_id": None,
            }
        ]
        cands_pref = {
            "M-ADM": {
                "id": "M-ADM",
                "nome": "DIREITO ADMINISTRATIVO",
                "nivel": "materia",
                "materia_id": "M-ADM",
            },
            "A-ATOS": {
                "id": "A-ATOS",
                "nome": "Atos Administrativos",
                "nivel": "assunto",
                "materia_id": "M-ADM",
            },
        }

        resp_pref = [
            {"numero": 1, "nos": [], "confianca": "alta", "nenhum_serve": True}
        ]
        resp_res = [{"numero": 1, "nos": [], "confianca": "alta", "nenhum_serve": True}]

        mock_conn = MagicMock()
        with (
            patch.object(
                cq_script.candidatos_questao,
                "candidatos_preferenciais",
                return_value=cands_pref,
            ),
            patch.object(
                cq_script,
                "carregar_dados_caderno",
                return_value=(
                    {
                        "prova_id": 1,
                        "nome_caderno": "CAD_TESTE",
                        "concurso_slug": "CONC",
                        "tipo": "objetiva_basica",
                        "orgao": "TESTE",
                    },
                    itens,
                    {},
                ),
            ),
            patch.object(
                llm_openrouter.requests,
                "post",
                side_effect=[_resposta_mock(resp_pref), _resposta_mock(resp_res)],
            ) as mock_post,
        ):
            cq_script.processar_caderno(
                mock_conn,
                prova_id=1,
                arv=arvore_teste,
                cq=cq,
                conta=conta,
                classificacao_path=classif_path,
            )

        assert mock_post.call_count == 2
        assert conta.total_sem_no == 1

        reg = cq.registros["CONC|CAD_TESTE|1"]
        assert reg.sem_no is True
        assert reg.apontamentos == []

    def test_idempotencia_preserva_registros_com_mesmo_hash(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path
    ):
        classif_path = tmp_path / "classificacao.json"
        cq = classificacao.ClassificacaoQuestoes()
        conta = cq_script.Contabilidade()

        enun = "Enunciado que já foi classificado."
        chave = "CONC|CAD1|1"
        h = classificacao.calcular_hash_enunciado(enun)
        classificacao.mapear_questao(
            cq,
            arvore_teste,
            chave=chave,
            hash_enunciado=h,
            nos=["S-ANUL"],
            confianca="alta",
            origem="llm",
            status="proposto",
        )

        itens = [{"numero": 1, "enunciado": enun, "texto_base_id": None}]
        mock_conn = MagicMock()

        with (
            patch.object(
                cq_script.candidatos_questao,
                "candidatos_preferenciais",
                return_value={
                    "M-ADM": {"id": "M-ADM", "nome": "DIR ADM", "nivel": "materia"}
                },
            ),
            patch.object(
                cq_script,
                "carregar_dados_caderno",
                return_value=(
                    {
                        "prova_id": 1,
                        "nome_caderno": "CAD1",
                        "concurso_slug": "CONC",
                        "tipo": "objetiva_basica",
                    },
                    itens,
                    {},
                ),
            ),
            patch.object(llm_openrouter.requests, "post") as mock_post,
        ):
            # Sem --reclassificar: pula!
            cq_script.processar_caderno(
                mock_conn,
                prova_id=1,
                arv=arvore_teste,
                cq=cq,
                conta=conta,
                reclassificar=False,
                classificacao_path=classif_path,
            )
            assert mock_post.call_count == 0
            assert conta.itens_pulados_idempotencia == 1

            # Com --reclassificar: chama o LLM!
            mock_post.return_value = _resposta_mock(
                [
                    {
                        "numero": 1,
                        "nos": ["C1"],
                        "confianca": "media",
                        "nenhum_serve": False,
                    }
                ]
            )
            cq_script.processar_caderno(
                mock_conn,
                prova_id=1,
                arv=arvore_teste,
                cq=cq,
                conta=conta,
                reclassificar=True,
                classificacao_path=classif_path,
            )
            assert mock_post.call_count == 1
            assert cq.registros[chave].apontamentos[0].confianca == "media"

    @pytest.mark.parametrize("decisao", ["aprovado", "rejeitado", "humano"])
    def test_reclassificar_nao_sobrescreve_decisao_do_dono(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path, decisao: str
    ):
        cq = classificacao.ClassificacaoQuestoes()
        enun = "Enunciado já decidido pelo dono."
        chave = "CONC|CAD1|1"
        classificacao.mapear_questao(
            cq,
            arvore_teste,
            chave=chave,
            hash_enunciado=classificacao.calcular_hash_enunciado(enun),
            nos=["S-ANUL"],
            origem="humano" if decisao == "humano" else "llm",
            status="rejeitado" if decisao == "rejeitado" else "aprovado",
        )
        dados = (
            {
                "prova_id": 1,
                "nome_caderno": "CAD1",
                "concurso_slug": "CONC",
                "tipo": "objetiva_basica",
            },
            [{"numero": 1, "enunciado": enun, "texto_base_id": None}],
            {},
        )
        conta = cq_script.Contabilidade()
        with (
            patch.object(
                cq_script.candidatos_questao,
                "candidatos_preferenciais",
                return_value={
                    "M-ADM": {"id": "M-ADM", "nome": "DIR ADM", "nivel": "materia"}
                },
            ),
            patch.object(cq_script, "carregar_dados_caderno", return_value=dados),
            patch.object(llm_openrouter.requests, "post") as mock_post,
        ):
            cq_script.processar_caderno(
                MagicMock(),
                prova_id=1,
                arv=arvore_teste,
                cq=cq,
                conta=conta,
                reclassificar=True,
                classificacao_path=tmp_path / "c.json",
            )
        assert mock_post.call_count == 0
        assert conta.itens_pulados_idempotencia == 1

    def test_classificacao_discursivas_com_quesitos(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path
    ):
        classif_path = tmp_path / "classificacao.json"
        cq = classificacao.ClassificacaoQuestoes()
        conta = cq_script.Contabilidade()

        itens_disc = [
            {
                "numero": 1,
                "titulo": "Questão Discursiva 1",
                "tema": "Controle de legalidade dos atos",
                "enunciado": "Redija texto dissertativo abordando os atos administrativos.",
                "quesitos": [
                    {"numero": 1, "texto": "Conceitue anulação."},
                    {"numero": 2, "texto": "Diferencie revogação de anulação."},
                ],
            }
        ]

        cands_pref = {
            "M-ADM": {
                "id": "M-ADM",
                "nome": "DIREITO ADMINISTRATIVO",
                "nivel": "materia",
                "materia_id": "M-ADM",
            },
            "A-ATOS": {
                "id": "A-ATOS",
                "nome": "Atos Administrativos",
                "nivel": "assunto",
                "materia_id": "M-ADM",
            },
            "S-ANUL": {
                "id": "S-ANUL",
                "nome": "Anulação e revogação",
                "nivel": "subassunto",
                "materia_id": "M-ADM",
                "assunto_id": "A-ATOS",
            },
        }

        resp_disc = [
            {"numero": "D1", "nos": ["C3"], "confianca": "alta", "nenhum_serve": False}
        ]

        mock_conn = MagicMock()
        with (
            patch.object(
                cq_script.candidatos_questao,
                "candidatos_preferenciais",
                return_value=cands_pref,
            ),
            patch.object(
                cq_script,
                "carregar_dados_caderno",
                return_value=(
                    {
                        "prova_id": 99,
                        "nome_caderno": "094_PF_014_DISC",
                        "concurso_slug": "PF_25_ADM",
                        "tipo": "discursiva",
                    },
                    itens_disc,
                    {},
                ),
            ),
            patch.object(
                llm_openrouter.requests, "post", return_value=_resposta_mock(resp_disc)
            ) as mock_post,
        ):
            cq_script.processar_caderno(
                mock_conn,
                prova_id=99,
                arv=arvore_teste,
                cq=cq,
                conta=conta,
                classificacao_path=classif_path,
            )

        assert mock_post.call_count == 1
        chave_esperada = "PF_25_ADM|094_PF_014_DISC|D1"
        assert chave_esperada in cq.registros
        reg = cq.registros[chave_esperada]
        assert reg.apontamentos[0].no_id == "S-ANUL"
        assert reg.apontamentos[0].confianca == "alta"

    def test_cli_dry_run_nao_chama_api(
        self, arvore_teste: arvore.ArvoreMestre, tmp_path: Path
    ):
        classif_path = tmp_path / "classificacao.json"
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_cur.fetchall.return_value = [
            (1, "094_PF_CB1_01", "arq.pdf", "CB1", "PF_25_ADM")
        ]

        with (
            patch.object(cq_script, "conectar", return_value=mock_conn),
            patch.object(
                cq_script.candidatos_questao,
                "candidatos_preferenciais",
                return_value={
                    "M-ADM": {"id": "M-ADM", "nome": "DIR ADM", "nivel": "materia"}
                },
            ),
            patch.object(
                cq_script,
                "carregar_dados_caderno",
                return_value=(
                    {
                        "prova_id": 1,
                        "nome_caderno": "094_PF_CB1_01",
                        "concurso_slug": "PF_25_ADM",
                        "tipo": "objetiva_basica",
                    },
                    [{"numero": 1, "enunciado": "Item de teste"}],
                    {},
                ),
            ),
            patch.object(llm_openrouter.requests, "post") as mock_post,
        ):
            conta = cq_script.classificar_todas_questoes(
                caderno="094_PF_CB1_01",
                dry_run=True,
                classificacao_path=classif_path,
            )

        assert mock_post.call_count == 0
        assert conta.chamadas == 0
        assert not classif_path.exists()
