from unittest.mock import MagicMock, patch

import pytest

from src import taxonomia_extractor as te

CHUNK_TESTE = (
    "LÍNGUA PORTUGUESA: 1 Compreensão e interpretação de textos. 2 Tipologia textual."
)


def fake_response(payload: dict, finish_reason: str = "stop"):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": payload}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    return resp


@pytest.fixture(autouse=True)
def sem_pausa_real_no_retry():
    # Os testes deste módulo não devem esperar o backoff real (5s/15s) —
    # só o comportamento de retry importa aqui, não o tempo de espera.
    with patch.object(te.time, "sleep"):
        yield


@pytest.fixture(autouse=True)
def desativar_langfuse_durante_testes_de_unidade(request):
    # Evita que chamadas ao Langfuse interfiram nas contagens de mock_post
    # dos testes específicos do extrator OpenRouter, mas permite que TestLangfuseSdk rode.
    if "TestLangfuseSdk" in request.node.nodeid:
        yield
        return
    with patch.object(te, "_registrar_langfuse"):
        yield


class TestStripMarkdownFence:
    def test_remove_bloco_json(self):
        texto = '```json\n{"a": 1}\n```'
        assert te._strip_markdown_fence(texto) == '{"a": 1}'

    def test_texto_sem_fence_passa_direto(self):
        texto = '{"a": 1}'
        assert te._strip_markdown_fence(texto) == '{"a": 1}'


class TestExtrairTaxonomiaChunk:
    def test_extrai_e_valida_com_sucesso(self):
        conteudo = (
            '{"materia": "LÍNGUA PORTUGUESA", "topicos": '
            '[{"nome": "Compreensão e interpretação de textos", "subtopicos": []}]}'
        )
        with patch.object(te.requests, "post", return_value=fake_response(conteudo)):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)

        assert resultado is not None
        assert motivo_falha is None
        assert resultado.materia == "LÍNGUA PORTUGUESA"
        assert resultado.topicos[0].nome == "Compreensão e interpretação de textos"

    def test_content_none_retorna_status_de_conteudo_vazio(self):
        with patch.object(
            te.requests,
            "post",
            return_value=fake_response(None, finish_reason="length"),
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_CONTEUDO_VAZIO

    def test_json_invalido_retorna_status_de_parse_json(self):
        with patch.object(
            te.requests, "post", return_value=fake_response("isso não é json")
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_PARSE_JSON

    def test_json_fora_do_schema_retorna_status_de_validacao_schema(self):
        with patch.object(
            te.requests, "post", return_value=fake_response('{"campo_errado": 1}')
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_VALIDACAO_SCHEMA

    def test_falha_de_conexao_retorna_status_de_conexao(self):
        with patch.object(
            te.requests, "post", side_effect=te.requests.ConnectionError("timeout")
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_CONEXAO

    def test_remove_fence_markdown_antes_de_validar(self):
        conteudo = '```json\n{"materia": "X", "topicos": []}\n```'
        with patch.object(te.requests, "post", return_value=fake_response(conteudo)):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)
        assert resultado is not None
        assert motivo_falha is None
        assert resultado.materia == "X"


class TestRetry:
    def test_sucesso_na_segunda_tentativa_nao_precisa_de_terceira(self):
        conteudo_ok = '{"materia": "X", "topicos": []}'
        with patch.object(
            te.requests,
            "post",
            side_effect=[
                fake_response(None, finish_reason="length"),
                fake_response(conteudo_ok),
            ],
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)

        assert resultado is not None
        assert motivo_falha is None
        assert resultado.materia == "X"
        assert mock_post.call_count == 2

    def test_falha_em_todas_as_tentativas_retorna_status_da_ultima(self):
        with patch.object(
            te.requests,
            "post",
            return_value=fake_response(None, finish_reason="length"),
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=3
            )

        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_CONTEUDO_VAZIO
        assert mock_post.call_count == 3

    def test_nao_retenta_alem_do_numero_de_tentativas_configurado(self):
        with patch.object(
            te.requests, "post", side_effect=te.requests.ConnectionError("timeout")
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=1
            )

        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_CONEXAO
        assert mock_post.call_count == 1

    def test_pausa_entre_tentativas_usa_backoff_configurado(self):
        with (
            patch.object(
                te.requests,
                "post",
                return_value=fake_response(None, finish_reason="length"),
            ),
            patch.object(te.time, "sleep") as mock_sleep,
        ):
            te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=3, backoff_segundos=(1, 2)
            )

        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)


class TestClassificacaoDeErros:
    """Cada tipo de exceção/etapa da chamada ao OpenRouter tem um status
    próprio — não colapsa tudo em "falha" genérico (ADR-022). Necessário pra
    rastrear no status persistido do chunk e no Langfuse (`tipo_erro`) se o
    problema foi rede, HTTP, conteúdo vazio ou parse/schema."""

    def _http_error(self, status_code: int) -> "te.requests.exceptions.HTTPError":
        resp = MagicMock()
        resp.status_code = status_code
        return te.requests.exceptions.HTTPError(
            f"{status_code} Client Error", response=resp
        )

    def test_timeout_retorna_status_proprio(self):
        with patch.object(
            te.requests, "post", side_effect=te.requests.exceptions.Timeout("demorou")
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=1
            )
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_TIMEOUT

    def test_http_429_retorna_status_de_rate_limit(self):
        with patch.object(te.requests, "post", side_effect=self._http_error(429)):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=1
            )
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_RATE_LIMIT

    def test_http_500_retorna_status_http_generico(self):
        with patch.object(te.requests, "post", side_effect=self._http_error(500)):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=1
            )
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_HTTP

    def test_excecao_de_rede_nao_classificada_cai_no_fallback_generico(self):
        with patch.object(
            te.requests,
            "post",
            side_effect=te.requests.exceptions.TooManyRedirects("loop"),
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=1
            )
        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_REDE

    def test_cada_tipo_de_falha_fica_rastreavel_no_metadata_langfuse_como_tipo_erro(
        self,
    ):
        with patch.object(
            te.requests, "post", side_effect=te.requests.exceptions.Timeout("demorou")
        ):
            te.extrair_taxonomia_chunk(CHUNK_TESTE, tentativas=1)

        metadata = te._registrar_langfuse.call_args.kwargs["metadata"]
        assert metadata["tipo_erro"] == te.STATUS_FALHA_TIMEOUT

    def test_falha_de_conteudo_vazio_fica_rastreavel_no_metadata_langfuse(self):
        with patch.object(
            te.requests,
            "post",
            return_value=fake_response(None, finish_reason="length"),
        ):
            te.extrair_taxonomia_chunk(CHUNK_TESTE, tentativas=1)

        metadata = te._registrar_langfuse.call_args.kwargs["metadata"]
        assert metadata["tipo_erro"] == te.STATUS_FALHA_CONTEUDO_VAZIO

    def test_falha_de_parse_json_fica_rastreavel_no_metadata_langfuse(self):
        with patch.object(
            te.requests, "post", return_value=fake_response("isso não é json")
        ):
            te.extrair_taxonomia_chunk(CHUNK_TESTE, tentativas=1)

        metadata = te._registrar_langfuse.call_args.kwargs["metadata"]
        assert metadata["tipo_erro"] == te.STATUS_FALHA_PARSE_JSON

    def test_falha_de_validacao_schema_fica_rastreavel_no_metadata_langfuse(self):
        with patch.object(
            te.requests, "post", return_value=fake_response('{"campo_errado": 1}')
        ):
            te.extrair_taxonomia_chunk(CHUNK_TESTE, tentativas=1)

        metadata = te._registrar_langfuse.call_args.kwargs["metadata"]
        assert metadata["tipo_erro"] == te.STATUS_FALHA_VALIDACAO_SCHEMA

    def test_todos_os_status_de_falha_sao_distintos_entre_si(self):
        status = {
            te.STATUS_FALHA_TIMEOUT,
            te.STATUS_FALHA_CONEXAO,
            te.STATUS_FALHA_RATE_LIMIT,
            te.STATUS_FALHA_HTTP,
            te.STATUS_FALHA_REDE,
            te.STATUS_FALHA_CONTEUDO_VAZIO,
            te.STATUS_FALHA_PARSE_JSON,
            te.STATUS_FALHA_VALIDACAO_SCHEMA,
            te.STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO,
        }
        assert len(status) == 9
        assert "falha" not in status


class TestReparoNomeTopicoNumerico:
    """`nome` puramente numérico (ex.: "1") é reparado localmente a partir do
    texto-fonte, sem nova chamada ao LLM (ver ADR-021 — descartou repetir a
    mesma chamada às cegas, sem contexto do erro e sem rastro próprio)."""

    def test_nome_numerico_e_reparado_com_texto_do_item_fonte_sem_nova_chamada(self):
        conteudo_ruim = (
            '{"materia": "CONTABILIDADE", "topicos": [{"nome": "1", "subtopicos": []}]}'
        )
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                "1 Conceito. 2 Campo de aplicação."
            )

        assert resultado is not None
        assert motivo_falha is None
        assert resultado.topicos[0].nome == "Conceito."
        assert mock_post.call_count == 1

    def test_numero_sem_correspondencia_na_fonte_retorna_none(self):
        conteudo_ruim = '{"materia": "CONTABILIDADE", "topicos": [{"nome": "99", "subtopicos": []}]}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ) as mock_post:
            resultado, _motivo_falha = te.extrair_taxonomia_chunk(
                "1 Conceito.", tentativas=1
            )

        assert resultado is None
        assert mock_post.call_count == 1

    def test_numero_sem_correspondencia_devolve_status_especifico_nao_falha_generica(
        self,
    ):
        # Pedido explícito na revisão: distinguir, no status persistido, uma
        # falha semântica identificada (reparo não mapeou o numeral) de uma
        # falha técnica genérica (rede/timeout/parse) — repetir a chamada
        # pode não resolver, então não deveria ser tratado igual (ADR-021).
        conteudo_ruim = '{"materia": "CONTABILIDADE", "topicos": [{"nome": "99", "subtopicos": []}]}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                "1 Conceito.", tentativas=1
            )

        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO
        assert motivo_falha != "falha"

    def test_falha_tecnica_de_rede_tem_motivo_proprio_distinto_do_semantico(self):
        # ADR-022: falha técnica (conexão, timeout, HTTP, parse) também ganha
        # status específico — mas continua distinto do motivo semântico
        # deste bloco (numeral sem correspondência), que precisa de reparo
        # local, não de retry de rede.
        with patch.object(
            te.requests, "post", side_effect=te.requests.ConnectionError("timeout")
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                CHUNK_TESTE, tentativas=1
            )

        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_CONEXAO
        assert motivo_falha != te.STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO

    def test_motivo_falha_devolvido_e_o_da_ultima_tentativa(self):
        # 1ª tentativa: falha técnica de conexão (STATUS_FALHA_CONEXAO). 2ª
        # tentativa: falha semântica (numeral sem correspondência) — o
        # motivo final deve refletir a última tentativa, não a primeira.
        conteudo_ruim = (
            '{"materia": "X", "topicos": [{"nome": "99", "subtopicos": []}]}'
        )
        with patch.object(
            te.requests,
            "post",
            side_effect=[
                te.requests.ConnectionError("timeout"),
                fake_response(conteudo_ruim),
            ],
        ):
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                "1 Conceito.", tentativas=2
            )

        assert resultado is None
        assert motivo_falha == te.STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO

    def test_reparo_bem_sucedido_fica_rastreavel_no_metadata_langfuse(self):
        # Rastreabilidade pedida na revisão: os dois desfechos (reparou /
        # não reparou) precisam ser igualmente filtráveis no Langfuse, não
        # só o de sucesso (ver ADR-021).
        conteudo_ruim = '{"materia": "X", "topicos": [{"nome": "1", "subtopicos": []}]}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ):
            te.extrair_taxonomia_chunk("1 Conceito.")

        metadata = te._registrar_langfuse.call_args.kwargs["metadata"]
        assert metadata["reparo_nome_numerico"] == {
            "numerais_detectados": ["1"],
            "numerais_nao_mapeados": [],
            "status": "reparado",
        }

    def test_reparo_sem_correspondencia_fica_rastreavel_no_metadata_langfuse(self):
        conteudo_ruim = (
            '{"materia": "X", "topicos": [{"nome": "99", "subtopicos": []}]}'
        )
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ):
            te.extrair_taxonomia_chunk("1 Conceito.", tentativas=1)

        metadata = te._registrar_langfuse.call_args.kwargs["metadata"]
        assert metadata["reparo_nome_numerico"] == {
            "numerais_detectados": ["99"],
            "numerais_nao_mapeados": ["99"],
            "status": "falhou",
        }

    def test_um_topico_numerico_entre_varios_e_reparado_mantendo_os_demais(self):
        conteudo_ruim = (
            '{"materia": "X", "topicos": ['
            '{"nome": "Direitos fundamentais", "subtopicos": []}, '
            '{"nome": "2", "subtopicos": []}'
            "]}"
        )
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk(
                "1 Direitos fundamentais. 2 Campo de aplicação."
            )

        assert resultado is not None
        assert motivo_falha is None
        assert resultado.topicos[0].nome == "Direitos fundamentais"
        assert resultado.topicos[1].nome == "Campo de aplicação."
        assert mock_post.call_count == 1

    def test_nome_com_espacos_ao_redor_de_digito_tambem_e_reparado(self):
        conteudo_ruim = (
            '{"materia": "X", "topicos": [{"nome": " 1 ", "subtopicos": []}]}'
        )
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ruim)
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk("1 Conceito.")

        assert resultado is not None
        assert motivo_falha is None
        assert resultado.topicos[0].nome == "Conceito."
        assert mock_post.call_count == 1

    def test_nome_alfanumerico_nao_e_tratado_como_numerico(self):
        conteudo_ok = '{"materia": "X", "topicos": [{"nome": "3. Direitos fundamentais", "subtopicos": []}]}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ok)
        ) as mock_post:
            resultado, motivo_falha = te.extrair_taxonomia_chunk(CHUNK_TESTE)

        assert resultado is not None
        assert motivo_falha is None
        assert resultado.topicos[0].nome == "3. Direitos fundamentais"
        assert mock_post.call_count == 1


class TestParametrosConfiguraveis:
    def test_max_tokens_e_timeout_customizados_vao_na_requisicao(self):
        conteudo_ok = '{"materia": "X", "topicos": []}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ok)
        ) as mock_post:
            te.extrair_taxonomia_chunk(CHUNK_TESTE, max_tokens=24576, timeout=240)

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["max_tokens"] == 24576
        assert kwargs["timeout"] == 240

    def test_reasoning_customizado_vai_no_payload(self):
        conteudo_ok = '{"materia": "X", "topicos": []}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ok)
        ) as mock_post:
            te.extrair_taxonomia_chunk(
                CHUNK_TESTE, reasoning={"thinking": {"type": "disabled"}}
            )

        _, kwargs = mock_post.call_args
        assert kwargs["json"]["thinking"] == {"type": "disabled"}

    def test_sem_reasoning_nao_adiciona_chave_no_payload(self):
        conteudo_ok = '{"materia": "X", "topicos": []}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ok)
        ) as mock_post:
            te.extrair_taxonomia_chunk(CHUNK_TESTE, reasoning=None)

        assert "reasoning" not in mock_post.call_args.kwargs["json"]
        assert "thinking" not in mock_post.call_args.kwargs["json"]

    def test_reasoning_padrao_e_max_tokens_12000(self):
        conteudo_ok = '{"materia": "X", "topicos": []}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ok)
        ) as mock_post:
            te.extrair_taxonomia_chunk(CHUNK_TESTE)

        assert mock_post.call_args.kwargs["json"]["reasoning"] == {"max_tokens": 3000}
        assert mock_post.call_args.kwargs["json"]["max_tokens"] == 12000


class TestOpenRouterDirect:
    def test_requisicao_vai_para_openrouter(self):
        conteudo_ok = '{"materia": "X", "topicos": []}'
        with patch.object(
            te.requests, "post", return_value=fake_response(conteudo_ok)
        ) as mock_post:
            te.extrair_taxonomia_chunk(CHUNK_TESTE)

        args, kwargs = mock_post.call_args
        assert "openrouter.ai/api/v1/chat/completions" in args[0]
        assert "Bearer " in kwargs["headers"]["Authorization"]


class TestLangfuseSdk:
    def test_sem_chaves_retorna_none_e_registrar_nao_faz_nada(self):
        te._langfuse_client.cache_clear()
        with (
            patch.object(te, "LANGFUSE_PUBLIC_KEY", ""),
            patch.object(te, "LANGFUSE_SECRET_KEY", ""),
        ):
            assert te._langfuse_client() is None
            assert te._abrir_generation("chunk teste", 12000, 120) is None
            # Chamar com gen=None não lança exceção
            te._registrar_langfuse(
                None,
                resposta=None,
                usage=None,
                sucesso=False,
                erro="erro teste",
                metadata={"tipo_erro": "falha_timeout"},
            )

    def test_registra_falha_na_generation_e_trace(self):
        mock_gen = MagicMock()
        te._registrar_langfuse(
            mock_gen,
            resposta=None,
            usage=None,
            sucesso=False,
            erro="erro teste",
            metadata={"tipo_erro": "falha_timeout"},
        )

        mock_gen.update.assert_called_once_with(
            output=None,
            usage_details={"input": 0, "output": 0, "total": 0},
            level="ERROR",
            status_message="erro teste",
            metadata={"tipo_erro": "falha_timeout"},
        )
        mock_gen.update_trace.assert_not_called()
        mock_gen.end.assert_called_once()

    def test_registra_sucesso_na_generation_e_trace(self):
        mock_gen = MagicMock()
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        te._registrar_langfuse(
            mock_gen,
            resposta='{"materia": "X"}',
            usage=usage,
            sucesso=True,
            metadata={"reparo_nome_numerico": {"status": "reparado"}},
        )

        mock_gen.update.assert_called_once_with(
            output='{"materia": "X"}',
            usage_details={"input": 10, "output": 20, "total": 30},
            level="DEFAULT",
            status_message=None,
            metadata={"reparo_nome_numerico": {"status": "reparado"}},
        )
        mock_gen.update_trace.assert_not_called()
        mock_gen.end.assert_called_once()

    def test_excecao_no_sdk_nao_propaga_e_gera_warning(self):
        mock_gen = MagicMock()
        mock_gen.update.side_effect = RuntimeError("Falha de conexão OTel")
        with patch.object(te.logger, "warning") as mock_warning:
            te._registrar_langfuse(
                mock_gen,
                resposta=None,
                usage=None,
                sucesso=False,
                erro="erro teste",
            )

        mock_warning.assert_called_once()
        assert (
            "Falha ao registrar generation no Langfuse" in mock_warning.call_args[0][0]
        )


class TestReinjetarItensAusentes:
    """ADR-025: item de primeiro nível omitido pelo LLM é reinjetado a partir
    do texto-fonte, sem nova chamada."""

    FONTE_IBAMA = (
        "1  IN  Ibama  05/2021.  2  Ecossistemas \nbrasileiros. 3 Corredores ecológicos. "
        "4 Manejo de fauna. 4.1 Nutrição de animais silvestres. \n \nRODRIGO AGOSTINHO \nPresidente do Ibama"
    )

    def _taxonomia(self, topicos):
        return te.TaxonomiaEdital(
            materia="Fauna",
            topicos=[te.Topico(nome=n, subtopicos=s) for n, s in topicos],
        )

    def test_item_omitido_e_reinjetado_na_posicao_da_fonte(self):
        # Caso real IBAMA_25 chunk 32.
        tax = self._taxonomia(
            [
                ("Ecossistemas brasileiros", []),
                ("Corredores ecológicos", []),
                ("Manejo de fauna", ["Nutrição de animais silvestres"]),
            ]
        )
        assert te.reinjetar_itens_ausentes(tax, self.FONTE_IBAMA) == ["1"]
        assert [t.nome for t in tax.topicos][:2] == [
            "IN Ibama 05/2021",
            "Ecossistemas brasileiros",
        ]
        assert len(tax.topicos) == 4

    def test_dois_itens_seguidos_omitidos_saem_na_ordem(self):
        tax = self._taxonomia([("Manejo de fauna", ["Nutrição de animais silvestres"])])
        te.reinjetar_itens_ausentes(tax, self.FONTE_IBAMA)
        assert [t.nome for t in tax.topicos] == [
            "IN Ibama 05/2021",
            "Ecossistemas brasileiros",
            "Corredores ecológicos",
            "Manejo de fauna",
        ]

    def test_item_com_subitens_nao_e_reinjetado(self):
        tax = self._taxonomia(
            [
                ("IN Ibama 05/2021", []),
                ("Ecossistemas brasileiros", []),
                ("Corredores ecológicos", []),
            ]
        )
        assert te.reinjetar_itens_ausentes(tax, self.FONTE_IBAMA) == []
        assert len(tax.topicos) == 3

    def test_assinatura_final_nao_vira_topico(self):
        tax = self._taxonomia(
            [
                ("IN Ibama 05/2021", []),
                ("Ecossistemas brasileiros", []),
                ("Corredores ecológicos", []),
            ]
        )
        te.reinjetar_itens_ausentes(
            tax,
            "1 IN Ibama 05/2021. 2 Ecossistemas brasileiros. 3 Corredores ecológicos. "
            "4 Manejo de fauna.\nRODRIGO AGOSTINHO\nPresidente do Ibama",
        )
        assert tax.topicos[-1].nome == "Manejo de fauna"

    def test_item_so_parafraseado_nao_e_duplicado(self):
        tax = self._taxonomia(
            [("Persistência; Hibernate Envers; Biblioteca Flyway", [])]
        )
        fonte = "1 Persistência; Hibernate Envers; bBiblioteca Flyway."
        assert te.reinjetar_itens_ausentes(tax, fonte) == []
        assert len(tax.topicos) == 1

    def test_extracao_completa_fica_intacta(self):
        tax = self._taxonomia(
            [("Compreensão e interpretação de textos", []), ("Tipologia textual", [])]
        )
        assert te.reinjetar_itens_ausentes(tax, CHUNK_TESTE) == []
        assert len(tax.topicos) == 2

    def test_reparo_roda_no_fluxo_da_chamada_e_fica_rastreavel_no_langfuse(self):
        conteudo = '{"materia": "Fauna", "topicos": [{"nome": "Ecossistemas brasileiros", "subtopicos": []}]}'
        fonte = "1 IN Ibama 05/2021. 2 Ecossistemas brasileiros."
        with (
            patch.object(
                te.requests, "post", return_value=fake_response(conteudo)
            ) as mock_post,
            patch.object(te, "_registrar_langfuse") as mock_lf,
        ):
            resultado, motivo = te.extrair_taxonomia_chunk(fonte)
        assert motivo is None
        assert [t.nome for t in resultado.topicos] == [
            "IN Ibama 05/2021",
            "Ecossistemas brasileiros",
        ]
        assert mock_post.call_count == 1
        metadata = mock_lf.call_args.kwargs["metadata"]
        assert metadata["reparo_item_ausente"] == {"itens": ["1"], "status": "reparado"}


class TestReasoningPadraoUnico:
    """Toda chamada LLM com reasoning limitado a 3000 tokens (decisão do dono,
    2026-09-25), com fonte única em `llm_openrouter.REASONING_PADRAO`."""

    def test_nucleo_envia_reasoning_3000_por_padrao(self):
        from pydantic import BaseModel

        from src import llm_openrouter

        class Qualquer(BaseModel):
            ok: bool

        with (
            patch.object(
                llm_openrouter.requests,
                "post",
                return_value=fake_response('{"ok": true}'),
            ) as mock_post,
            patch.object(llm_openrouter, "langfuse_client", return_value=None),
        ):
            resultado = llm_openrouter.chamar_llm_json("sistema", "usuário", Qualquer)
        assert resultado.motivo is None
        assert mock_post.call_args.kwargs["json"]["reasoning"] == {"max_tokens": 3000}

    def test_extrator_usa_a_constante_do_nucleo(self):
        from src import llm_openrouter

        assert te.REASONING_PADRAO is llm_openrouter.REASONING_PADRAO


class TestReinjetarSubitensAusentes:
    """Reinjeção determinística de subitens (ADR-025, atualização C1a)."""

    # Trecho real do SEFA_PR_25 (ECONOMIA, chunk 19), cortado no item 1.3.
    FONTE = (
        "1 Microeconomia. 1.1 Conceitos fundamentais. 1.1.1 Formas de organização da atividade \n"
        "econômica: laissez-faire, intervencionismo, economia planificada. 1.1.2 Fatores de produção. "
        "1.2 Teoria da demanda. 1.2.1 Preferências e função \nutilidade. 1.2.5 \nCurva de demanda. "
        "1.2.6 Curva de Engel. 1.2.7 Bens substitutos e bens complementares. 1.2.10 Elasticidades. "
        "1.2.10.1 Elasticidade-preço da demanda e seus \ndeterminantes. 1.2.10.2 Efeito da mudança "
        "no preço de um bem sobre a receita total. 1.3 Teoria da oferta. "
        "2 Macroeconomia. 2.1 Contas nacionais."
    )

    def _tax(self, subs_micro, subs_macro=("Contas nacionais",)):
        return te.TaxonomiaEdital(
            materia="ECONOMIA",
            topicos=[
                te.Topico(nome="Microeconomia", subtopicos=list(subs_micro)),
                te.Topico(nome="Macroeconomia", subtopicos=list(subs_macro)),
            ],
        )

    def test_subitens_entram_em_cadeia_e_na_ordem_da_fonte(self):
        tax = self._tax(
            [
                "Conceitos fundamentais",
                "Teoria da demanda",
                "Teoria da oferta",
            ]
        )
        reinjetados = te.reinjetar_subitens_ausentes(tax, self.FONTE)
        assert reinjetados == [
            "1.1.1",
            "1.1.2",
            "1.2.1",
            "1.2.5",
            "1.2.6",
            "1.2.7",
            "1.2.10",
            "1.2.10.1",
            "1.2.10.2",
        ]
        subs = tax.topicos[0].subtopicos
        assert subs == [
            "Conceitos fundamentais",
            "Conceitos fundamentais - Formas de organização da atividade econômica: "
            "laissez-faire, intervencionismo, economia planificada",
            "Conceitos fundamentais - Fatores de produção",
            "Teoria da demanda",
            "Teoria da demanda - Preferências e função utilidade",
            "Teoria da demanda - Curva de demanda",
            "Teoria da demanda - Curva de Engel",
            "Teoria da demanda - Bens substitutos e bens complementares",
            "Teoria da demanda - Elasticidades",
            "Teoria da demanda - Elasticidades - Elasticidade-preço da demanda e seus determinantes",
            "Teoria da demanda - Elasticidades - Efeito da mudança no preço de um bem "
            "sobre a receita total",
            "Teoria da oferta",
        ]
        assert tax.topicos[1].subtopicos == ["Contas nacionais"]

    def test_subitem_ja_coberto_nao_duplica(self):
        tax = self._tax(["Curva de Engel", "Conceitos fundamentais"])
        te.reinjetar_subitens_ausentes(tax, self.FONTE)
        assert sum("Curva de Engel" in s for s in tax.topicos[0].subtopicos) == 1
        assert te.reinjetar_subitens_ausentes(tax, self.FONTE) == []

    def test_idempotente(self):
        tax = self._tax(["Teoria da demanda"])
        assert te.reinjetar_subitens_ausentes(tax, self.FONTE)
        assert te.reinjetar_subitens_ausentes(tax, self.FONTE) == []

    def test_sem_topico_destino_nao_reinjeta(self):
        tax = te.TaxonomiaEdital(
            materia="ECONOMIA", topicos=[te.Topico(nome="Assunto sem relação")]
        )
        assert te.reinjetar_subitens_ausentes(tax, self.FONTE) == []
        assert tax.topicos[0].subtopicos == []

    def test_nome_longo_demais_nao_reinjeta(self):
        longo = "palavra " * 40
        fonte = f"1 Microeconomia. 1.1 Conceitos. 1.1.1 {longo.strip()}."
        tax = te.TaxonomiaEdital(
            materia="E", topicos=[te.Topico(nome="Microeconomia", subtopicos=[])]
        )
        assert te.reinjetar_subitens_ausentes(tax, fonte) == ["1.1"]
        assert tax.topicos[0].subtopicos == ["Conceitos"]

    def test_validador_nao_acusa_subitem_ausente_apos_reinjecao(self):
        from scripts.validar_taxonomia import comparar_chunk

        tax = self._tax(["Conceitos fundamentais", "Teoria da demanda"])
        te.reinjetar_subitens_ausentes(tax, self.FONTE)
        alertas = comparar_chunk(
            {"chunk_index": 19, "texto_enviado_llm": self.FONTE},
            {"taxonomia_extraida": tax.model_dump()},
        )
        assert [a for a in alertas if a["tipo"] == "subitem_ausente"] == []

    def test_reinjecao_de_primeiro_nivel_continua_igual(self):
        tax = te.TaxonomiaEdital(
            materia="X", topicos=[te.Topico(nome="Ecossistemas brasileiros")]
        )
        fonte = "1 IN Ibama 05/2021. 2 Ecossistemas brasileiros."
        assert te.reinjetar_itens_ausentes(tax, fonte) == ["1"]
        assert te.reinjetar_subitens_ausentes(tax, fonte) == []

    def test_texto_repetido_em_ramos_diferentes_nao_embaralha_a_ordem(self):
        # Caso real SEFA: "Fatores de produção" é 1.1.2 e 1.3.1.1.
        fonte = (
            "1 Microeconomia. 1.1 Conceitos fundamentais. 1.1.1 Formas de organização. "
            "1.1.2 Fatores de produção. 1.1.3 Papel dos preços. "
            "1.3 Teoria da oferta. 1.3.1 Função de produção. 1.3.1.1 Fatores de produção. "
            "1.3.1.2 Isoquantas. 1.3.1.3 Rendimentos de escala. 1.3.2 Minimização de custos."
        )
        tax = te.TaxonomiaEdital(
            materia="E",
            topicos=[
                te.Topico(
                    nome="Microeconomia",
                    subtopicos=["Conceitos fundamentais", "Teoria da oferta"],
                )
            ],
        )
        te.reinjetar_subitens_ausentes(tax, fonte)
        assert tax.topicos[0].subtopicos == [
            "Conceitos fundamentais",
            "Conceitos fundamentais - Formas de organização",
            "Conceitos fundamentais - Fatores de produção",
            "Conceitos fundamentais - Papel dos preços",
            "Teoria da oferta",
            "Teoria da oferta - Função de produção",
            "Teoria da oferta - Função de produção - Isoquantas",
            "Teoria da oferta - Função de produção - Rendimentos de escala",
            "Teoria da oferta - Minimização de custos",
        ]

    def test_destino_pelo_texto_proprio_do_item_e_nao_pelo_item_inteiro(self):
        # Caso real SEFA chunk 18: 21.1.6 cita "Mensuração de ativos", e existe
        # um tópico com esse nome (item 5) antes do tópico do item 21.
        fonte = (
            "5 Mensuração de ativos. "
            "21 Normas Brasileiras de Contabilidade. 21.1 NBC TSP Estrutura Conceitual. "
            "21.1.1 Objetivos e usuários da informação contábil. 21.1.2 Características qualitativas. "
            "21.1.6 Mensuração de ativos e passivos nas demonstrações contábeis. "
            "21.2 NBC TSP 03 – provisões. 22 Análise das demonstrações contábeis."
        )
        tax = te.TaxonomiaEdital(
            materia="CONTABILIDADE",
            topicos=[
                te.Topico(nome="Mensuração de ativos"),
                te.Topico(
                    nome="Normas Brasileiras de Contabilidade",
                    subtopicos=[
                        "NBC TSP Estrutura Conceitual",
                        "NBC TSP 03 – provisões",
                    ],
                ),
                te.Topico(nome="Análise das demonstrações contábeis"),
            ],
        )
        te.reinjetar_subitens_ausentes(tax, fonte)
        assert tax.topicos[0].subtopicos == []
        assert tax.topicos[1].subtopicos == [
            "NBC TSP Estrutura Conceitual",
            "NBC TSP Estrutura Conceitual - Objetivos e usuários da informação contábil",
            "NBC TSP Estrutura Conceitual - Características qualitativas",
            "NBC TSP Estrutura Conceitual - Mensuração de ativos e passivos nas demonstrações contábeis",
            "NBC TSP 03 – provisões",
        ]


class TestReparosDeForma:
    """Matéria inutilizável e hífen de quebra de linha (KAN-56, C1a)."""

    def test_materia_vazia_vira_o_cabecalho(self):
        tax = te.TaxonomiaEdital(
            materia="", topicos=[te.Topico(nome="Lei nº 8.069/1990")]
        )
        assert te.reparar_materia_extraida(tax, "ESTATUTO DA CRIANÇA") == "vazia"
        assert tax.materia == "ESTATUTO DA CRIANÇA"

    def test_materia_que_copia_a_lista_de_topicos(self):
        tax = te.TaxonomiaEdital(
            materia="Concorrência (sincronização). Redes Locais. Web Services, APIs REST.",
            topicos=[
                te.Topico(nome="Concorrência (sincronização)"),
                te.Topico(nome="Redes Locais"),
                te.Topico(nome="Web Services, APIs REST"),
            ],
        )
        assert (
            te.reparar_materia_extraida(tax, "CONCEITOS BÁSICOS") == "lista_de_topicos"
        )
        assert tax.materia == "CONCEITOS BÁSICOS"

    def test_materia_normal_ou_sem_cabecalho_nao_muda(self):
        tax = te.TaxonomiaEdital(
            materia="Programação estruturada",
            topicos=[te.Topico(nome="Programação estruturada")],
        )
        assert te.reparar_materia_extraida(tax, "TÉCNICAS") is None
        assert tax.materia == "Programação estruturada"
        vazia = te.TaxonomiaEdital(materia="", topicos=[te.Topico(nome="A")])
        assert te.reparar_materia_extraida(vazia, None) is None
        assert vazia.materia == ""

    def test_hifen_de_quebra_de_linha_sem_espaco(self):
        fonte = "1.2.10.3 Elasticidade-\nrenda da demanda. 1.2.10.4 Outra"
        tax = te.TaxonomiaEdital(
            materia="Economia",
            topicos=[
                te.Topico(
                    nome="Demanda",
                    subtopicos=[
                        "Demanda - Elasticidades - Elasticidade- renda da demanda",
                        "A - B",
                    ],
                )
            ],
        )
        corrigidos = te.corrigir_hifen_quebra_de_linha(tax, fonte)
        assert corrigidos == ["Demanda - Elasticidades - Elasticidade-renda da demanda"]
        assert tax.topicos[0].subtopicos[1] == "A - B"

    def test_hifen_com_espaco_que_a_fonte_nao_confirma_fica(self):
        tax = te.TaxonomiaEdital(
            materia="X", topicos=[te.Topico(nome="T", subtopicos=["médio- marginal"])]
        )
        assert te.corrigir_hifen_quebra_de_linha(tax, "médio e marginal") == []
        assert tax.topicos[0].subtopicos == ["médio- marginal"]

    def test_nome_em_cadeia_junta_hifen_de_fim_de_linha(self):
        assert te._limpar_nome_subitem("Elasticidade-\nrenda da demanda.") == (
            "Elasticidade-renda da demanda"
        )

    def test_materia_composta_que_so_cita_topicos_nao_e_trocada(self):
        tax = te.TaxonomiaEdital(
            materia="Ciclos de vida e Metodologias ágeis",
            topicos=[
                te.Topico(nome="Ciclos de vida"),
                te.Topico(nome="Metodologias ágeis"),
                te.Topico(nome="Kanban"),
            ],
        )
        assert te.reparar_materia_extraida(tax, "PROCESSO") is None
        assert tax.materia == "Ciclos de vida e Metodologias ágeis"
