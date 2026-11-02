import json

from scripts.gerar_relatorio_revisao import gerar_relatorios, renderizar_index


def _escrever_json(path, dados):
    path.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")


def _fixture_basica():
    resultado = {
        "edital": "Edital_A.pdf",
        "total_chunks": 2,
        "extraidos_com_sucesso": 1,
        "falhas": 1,
        "status_revisao_humana": "PENDENTE — teste.",
        "chunks_com_falha": [
            {"chunk_index": 1, "cargo": None, "materia_esperada": "MATERIA B"}
        ],
        "resultados": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia_chunk": "MATERIA A",
                "taxonomia_extraida": {
                    "materia": "Matéria A",
                    "topicos": [
                        {"nome": "1 Tópico um", "subtopicos": ["1.1 Subtópico"]}
                    ],
                },
            }
        ],
    }
    auditoria = {
        "chunks": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia": "MATERIA A",
                "texto_enviado_llm": "1 Tópico um. 2 Tópico dois não extraído.",
                "status": "sucesso",
            },
            {
                "chunk_index": 1,
                "cargo": None,
                "materia": "MATERIA B",
                "texto_enviado_llm": "1 Conteúdo não processado.",
                "status": "falha",
            },
        ]
    }
    validacao = {
        "edital": "Edital_A.pdf",
        "total_chunks_analisados": 2,
        "total_alertas": 1,
        "alertas": [
            {
                "chunk_index": 0,
                "cargo": "CARGO 1: ADMINISTRADOR",
                "materia": "MATERIA A",
                "tipo": "topico_ausente",
                "numero_item": "2",
                "posicao_item": 1,
                "texto_item_origem": "Tópico dois não extraído.",
                "topico_nome_extraido": None,
            }
        ],
    }
    return resultado, auditoria, validacao


class TestGerarRelatorios:
    def test_gera_html_do_edital_e_index(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)

        assert (saida_dir / "Edital_A.html").exists()
        assert (saida_dir / "index.html").exists()

    def test_html_do_edital_contem_texto_fonte_e_taxonomia_lado_a_lado(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "Tópico um" in html
        assert "1.1 Subtópico" in html
        assert "class='col fonte'" in html
        assert "class='col taxonomia'" in html

    def test_subtopico_com_caminho_origem_mostra_o_contexto(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        topico = resultado["resultados"][0]["taxonomia_extraida"]["topicos"][0]
        topico["subtopicos"] = ["Pai", "Filho"]
        topico["caminho_origem"] = {"Filho": ["Pai", "Avô <b>"]}
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        html = (gerar_relatorios(tmp_path) / "Edital_A.html").read_text(
            encoding="utf-8"
        )

        assert "<li class='subtopico'>Filho <small class='caminho'>" in html
        assert "(em: Pai › Avô &lt;b&gt;)" in html
        assert "<li class='subtopico'>Pai</li>" in html

    def test_alerta_topico_ausente_aparece_destacado_no_html(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "topico_ausente" in html
        assert "<mark>2 Tópico dois não extraído.</mark>" in html

    def test_chunk_com_falha_mostra_aviso_sem_taxonomia(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "falha na extração" in html

    def test_chunk_com_status_especifico_tambem_mostra_aviso_sem_taxonomia(
        self, tmp_path
    ):
        # Não só o "falha" genérico — um status específico de falha semântica
        # (ex.: STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO, ver ADR-021) também
        # precisa ser reconhecido como "sem taxonomia", não renderizado como
        # se tivesse tido sucesso.
        resultado, auditoria, validacao = _fixture_basica()
        auditoria["chunks"][1]["status"] = "falha_nome_numerico_nao_mapeado"
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")

        assert "falha na extração" in html
        assert "falha_nome_numerico_nao_mapeado" in html

    def test_edital_sem_validacao_json_gera_relatorio_sem_alertas(self, tmp_path):
        resultado, auditoria, _ = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)

        saida_dir = gerar_relatorios(tmp_path)
        html = (saida_dir / "Edital_A.html").read_text(encoding="utf-8")
        assert (saida_dir / "Edital_A.html").exists()
        assert "topico_ausente" not in html

    def test_edital_sem_auditoria_e_pulado_sem_erro(self, tmp_path):
        resultado, _, _ = _fixture_basica()
        _escrever_json(tmp_path / "Edital_Legado.json", resultado)

        saida_dir = gerar_relatorios(tmp_path)
        assert not (saida_dir / "Edital_Legado.html").exists()
        assert (saida_dir / "index.html").exists()

    def test_index_lista_edital_com_contagem_de_alertas(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        saida_dir = gerar_relatorios(tmp_path)
        index_html = (saida_dir / "index.html").read_text(encoding="utf-8")

        assert "Edital_A.pdf" in index_html
        assert "Edital_A.html" in index_html

    def test_cargos_restritos_aparecem_na_classificacao_do_chunk(self, tmp_path):
        resultado, auditoria, validacao = _fixture_basica()
        auditoria["chunks"][0].update(
            {
                "tipo_conhecimento": "especifico",
                "nivel": "superior",
                "cargos_restritos": [1, 8],
            }
        )
        _escrever_json(tmp_path / "Edital_A.json", resultado)
        _escrever_json(tmp_path / "Edital_A.auditoria.json", auditoria)
        _escrever_json(tmp_path / "Edital_A.validacao.json", validacao)

        html = (gerar_relatorios(tmp_path) / "Edital_A.html").read_text(
            encoding="utf-8"
        )

        assert "só cargos 1, 8" in html


def _novidades_fake(resultado):
    return {
        "disciplinas_novas": ["Matéria A"],
        "titulos_sem_destino": [
            {"titulo": "Matéria A", "chunks": [0], "itens_travados": 2}
        ],
        "total_titulos_sem_destino": 1,
        "total_itens_travados": 2,
        "assuntos_novos": [
            {
                "disciplina": "Matéria A",
                "assunto": "1 Tópico um",
                "subassuntos": ["1.1 Subtópico"],
            }
        ],
        "total_disciplinas": 1,
        "total_assuntos": 1,
        "total_itens_novos": 2,
        "propostas": [
            {
                "nivel": "assunto",
                "item": "2 Tópico dois",
                "disciplina": "Matéria A",
                "no_id": "NA-X",
                "no_caminho": "Matéria B › Assunto <X>",
                "confianca": 0.9,
            }
        ],
        "total_propostas": 1,
    }


def _gravar(tmp_path, nome, status, alertas=True):
    resultado, auditoria, validacao = _fixture_basica()
    resultado["edital"] = f"{nome}.pdf"
    resultado["status_revisao_humana"] = status
    if not alertas:
        validacao.update(total_alertas=0, alertas=[])
        resultado["falhas"] = 0
    _escrever_json(tmp_path / f"{nome}.json", resultado)
    _escrever_json(tmp_path / f"{nome}.auditoria.json", auditoria)
    _escrever_json(tmp_path / f"{nome}.validacao.json", validacao)


class TestIndexSecoes:
    def test_pendentes_e_aprovados_em_secoes_separadas(self, tmp_path):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")
        _gravar(tmp_path, "Aprov", "APROVADO — revisão concluída.", alertas=False)

        index = (
            gerar_relatorios(tmp_path, novidades_fn=_novidades_fake) / "index.html"
        ).read_text(encoding="utf-8")

        pend = index.index("Aguardando aprovação (1)")
        aprov = index.index("Aprovados (1)")
        assert pend < aprov
        assert pend < index.index("Pend.pdf") < aprov
        assert aprov < index.index("Aprov.pdf")
        assert '<details class="secao">' in index
        assert '<details class="secao" open' not in index

    def test_badges_de_problema_e_novidade(self, tmp_path):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")

        index = (
            gerar_relatorios(tmp_path, novidades_fn=_novidades_fake) / "index.html"
        ).read_text(encoding="utf-8")

        assert "1 alertas bloqueantes" in index
        assert "1 falhas" in index
        assert "2 novos sem equivalente (2 itens)" in index
        assert (
            "1 títulos de bloco sem destino (viram assunto) · destravam 2 itens"
            in index
        )
        assert "1 propostas a conferir" in index
        assert "data-proposta='1'" in index
        assert "1 disciplinas · 1 assuntos" in index
        assert "data-problema='1'" in index
        assert "data-novidade='1'" in index
        assert "data-filtro='problema'" in index

    def test_pendentes_com_problema_ou_novidade_vem_primeiro(self):
        base = {
            "arquivo_html": "x.html",
            "situacao": "pendente",
            "total_chunks": 1,
            "falhas": 0,
            "total_alertas": 0,
        }
        limpo = {**base, "edital": "A_limpo"}
        problema = {**base, "edital": "Z_problema", "total_alertas": 2}
        novo = {**base, "edital": "M_novo", "assuntos_novos": 1}

        prop = {**base, "edital": "B_proposta", "propostas": 3}

        html = renderizar_index([limpo, prop, novo, problema])

        assert (
            html.index("Z_problema")
            < html.index("M_novo")
            < html.index("B_proposta")
            < html.index("A_limpo")
        )

    def test_index_escapa_html_do_nome(self):
        e = {
            "edital": "<script>alert(1)</script>",
            "arquivo_html": "x.html",
            "situacao": "pendente",
            "total_chunks": 1,
        }

        html = renderizar_index([e])

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

    def test_situacao_desconhecida_vai_para_outros(self):
        e = {
            "edital": "Estranho",
            "arquivo_html": "x.html",
            "situacao": "outro",
            "total_chunks": 1,
        }

        assert "Outros (1)" in renderizar_index([e])


class TestPaginaEdital:
    def test_bloco_o_que_revisar_com_ancoras_e_badge_novo(self, tmp_path):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")

        html = (
            gerar_relatorios(tmp_path, novidades_fn=_novidades_fake) / "Pend.html"
        ).read_text(encoding="utf-8")

        assert "O que revisar" in html
        assert html.index("O que revisar") < html.index("class='chunk'")
        assert "Alertas bloqueantes e falhas (2)" in html
        assert "Realmente novos — sem nó equivalente (2 entradas; 2 itens)" in html
        assert "Propostas da IA a conferir (1)" in html
        assert "Matéria B › Assunto &lt;X&gt;" in html
        assert "aprovar via curar_arvore" in html
        assert (
            html.index("Alertas bloqueantes")
            < html.index("Realmente novos")
            < html.index("Propostas da IA")
        )
        assert "href='#chunk-0'" in html
        assert "id='chunk-0'" in html
        assert "novo-tag'>NOVO" in html

    def test_sem_novidades_mostra_mensagem_vazia(self, tmp_path):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")

        html = (
            gerar_relatorios(tmp_path, novidades_fn=lambda r: {}) / "Pend.html"
        ).read_text(encoding="utf-8")

        assert "Nenhum item novo sem equivalente." in html
        assert "Nenhuma proposta pendente." in html
        assert "<span class='novo-tag'>" not in html

    def test_falha_na_funcao_de_novidades_nao_derruba_o_relatorio(self, tmp_path):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")

        def quebrada(resultado):
            raise RuntimeError("boom")

        saida = gerar_relatorios(tmp_path, novidades_fn=quebrada)

        assert (saida / "Pend.html").exists()

    def test_novidades_sao_escapadas(self, tmp_path):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")

        def hostil(resultado):
            return {
                "disciplinas_novas": ["<b>x</b>"],
                "assuntos_novos": [
                    {"disciplina": "<i>d</i>", "assunto": "<u>a</u>", "subassuntos": []}
                ],
            }

        html = (
            gerar_relatorios(tmp_path, novidades_fn=hostil) / "Pend.html"
        ).read_text(encoding="utf-8")

        assert "<b>x</b>" not in html
        assert "&lt;b&gt;x&lt;/b&gt;" in html
        assert "<u>a</u>" not in html


class TestTituloSemDestino:
    def _html(self, tmp_path, fn):
        _gravar(tmp_path, "Pend", "PENDENTE — teste.")
        return (gerar_relatorios(tmp_path, novidades_fn=fn) / "Pend.html").read_text(
            encoding="utf-8"
        )

    def test_rotulo_novo_e_sem_disciplina_nova(self, tmp_path):
        html = self._html(tmp_path, _novidades_fake)
        assert "Título de bloco sem destino (vira assunto)" in html
        assert "Não é disciplina nova" in html
        assert "destrava 2 itens" in html
        assert "DISCIPLINA nova" not in html
        assert "novo-tag'>DISCIPLINA<" not in html

    def test_ordena_por_itens_travados(self, tmp_path):
        def fn(resultado):
            return {
                "titulos_sem_destino": [
                    {"titulo": "Pequeno", "chunks": [], "itens_travados": 1},
                    {"titulo": "Grande", "chunks": [], "itens_travados": 9},
                ],
                "total_itens_travados": 10,
            }

        html = self._html(tmp_path, fn)
        assert html.index("Grande") < html.index("Pequeno")
        assert "os 10 itens abaixo" in html

    def test_titulo_hostil_e_escapado(self, tmp_path):
        def fn(resultado):
            return {
                "titulos_sem_destino": [
                    {"titulo": "<b>x</b>", "chunks": [], "itens_travados": 1}
                ]
            }

        html = self._html(tmp_path, fn)
        assert "<b>x</b>" not in html
        assert "&lt;b&gt;x&lt;/b&gt;" in html
        assert "destrava 1 item" in html

    def test_chave_antiga_continua_funcionando(self, tmp_path):
        html = self._html(tmp_path, lambda r: {"disciplinas_novas": ["Velha"]})
        assert "Velha" in html
        assert "Título de bloco sem destino (vira assunto)" in html
