import json

from scripts.validar_taxonomia import (
    comparar_chunk,
    extrair_itens_numerados,
    main,
    normalizar,
    validar_edital,
)

TEXTO_CHUNK_0_REAL = (
    "1 Compreensão e interpretação de textos. 2 Tipologia textual. 3 Domínio da \n"
    "ortografia oficial. 3.1 Emprego da acentuação gráfica. 4 Emprego das classes de palavras. 5 Domínio dos \n"
    "mecanismos de coesão textual. 5.1 Emprego de elementos de referenciação, substituição e repetição, de \n"
    "conectores e outros elementos de sequenciação textual. 5.2 Emprego/correlação de tempos e modos \n"
    "verbais. 6 Domínio da estrutura morfossintática do período. 6.1 Relações de coordenação entre orações \n"
    "e entre termos da oração. 6.2 Relações de subordinação entre orações e entre termos da oração. 6.3 \n"
    "Emprego dos sinais de pontuação. 6.4 Concordância verbal e nominal. 6.5 Emprego do sinal indicativo de \n"
    "crase. 6.6 Colocação dos pronomes átonos. 7 Regência nominal e verbal. 8 Correspondência oficial \n"
    "(conforme Manual de Redação da Presidência da República). 8.1 Adequação da linguagem ao tipo de \n"
    "documento. 8.2 Adequação do formato do texto ao gênero."
)


class TestExtrairItensNumerados:
    def test_extrai_exatamente_os_8_itens_de_primeiro_nivel_do_texto_real(self):
        itens = extrair_itens_numerados(TEXTO_CHUNK_0_REAL)
        assert [numero for numero, _ in itens] == [str(n) for n in range(1, 9)]

    def test_nao_casa_numero_dentro_de_citacao_legal(self):
        texto = "conforme Lei 8.112, de 11 de dezembro de 1990"
        assert extrair_itens_numerados(texto) == []

    def test_casa_item_colado_ao_ponto_final_do_item_anterior_sem_espaco(self):
        texto = "3.5 Diagramas lógicos.4 Lógica de primeira ordem."
        itens = extrair_itens_numerados(texto)
        assert [numero for numero, _ in itens] == ["4"]
        assert itens[0][1] == "Lógica de primeira ordem."

    def test_texto_sem_numeracao_nao_gera_itens(self):
        assert extrair_itens_numerados("Conteúdo em prosa livre, sem marcação numérica nenhuma.") == []


class TestNormalizar:
    def test_remove_numero_de_prefixo_com_espaco_ou_ponto(self):
        assert normalizar("1 Compreensão e interpretação") == normalizar("1. Compreensão e interpretação")

    def test_hifen_unicode_nao_gruda_palavras(self):
        # U+2010 (hífen tipográfico) usado no PDF-fonte vs "-" ASCII usado pelo LLM
        assert normalizar("ético‐político") == normalizar("ético-político")

    def test_acento_combinante_decomposto_normaliza_igual_ao_precomposto(self):
        # Domi\u0301nio (decomposto NFD) vs Domínio (precomposto NFC)
        assert normalizar("Domi\u0301nio da ortografia oficial.") == normalizar("Domínio da ortografia oficial")

    def test_ligaturas_e_caracteres_corrompidos_sao_normalizados(self):
        assert normalizar("ÉƟca no serviço público") == normalizar("Ética no serviço público")
        assert normalizar("MicrosoŌ Oﬃce 365") == normalizar("Microsoft Office 365")


class TestCompararChunk:
    def _chunk_auditoria(self, texto, status="sucesso", chunk_index=0):
        return {
            "chunk_index": chunk_index,
            "cargo": None,
            "materia": "MATERIA X",
            "texto_enviado_llm": texto,
            "status": status,
        }

    def _resultado_chunk(self, nomes_topicos):
        return {
            "cargo": None,
            "materia_chunk": "MATERIA X",
            "taxonomia_extraida": {"materia": "Matéria X", "topicos": [{"nome": n, "subtopicos": []} for n in nomes_topicos]},
        }

    def test_conjuntos_iguais_nao_gera_alerta(self):
        chunk = self._chunk_auditoria("1 Fundamentos da matéria. 2 Aplicações práticas.")
        resultado = self._resultado_chunk(["Fundamentos da matéria", "Aplicações práticas"])
        assert comparar_chunk(chunk, resultado) == []

    def test_item_presente_na_fonte_e_ausente_na_extracao_gera_alerta_ausente(self):
        chunk = self._chunk_auditoria("1 Fundamentos da matéria. 2 Aplicações práticas avançadas.")
        resultado = self._resultado_chunk(["Fundamentos da matéria"])
        alertas = comparar_chunk(chunk, resultado)
        assert len(alertas) == 1
        assert alertas[0]["tipo"] == "topico_ausente"
        assert alertas[0]["numero_item"] == "2"

    def test_topico_extraido_sem_correspondencia_na_fonte_gera_alerta_extra(self):
        chunk = self._chunk_auditoria("1 Fundamentos da matéria.")
        resultado = self._resultado_chunk(["Fundamentos da matéria", "Tópico inventado que não está no texto"])
        alertas = comparar_chunk(chunk, resultado)
        assert len(alertas) == 1
        assert alertas[0]["tipo"] == "topico_extra"
        assert alertas[0]["topico_nome_extraido"] == "Tópico inventado que não está no texto"

    def test_extracao_sem_numero_de_prefixo_ainda_casa_pelo_texto(self):
        chunk = self._chunk_auditoria("1 Estruturas lógicas. 2 Lógica de argumentação.")
        resultado = self._resultado_chunk(["Estruturas lógicas", "Lógica de argumentação"])
        assert comparar_chunk(chunk, resultado) == []

    def test_item_classificado_como_subtopico_e_marcado_como_incluido(self):
        chunk = self._chunk_auditoria("1 Funções administrativas. 2 Planejamento.")
        resultado = {
            "cargo": None,
            "materia_chunk": "MATERIA X",
            "taxonomia_extraida": {
                "materia": "Matéria X",
                "topicos": [
                    {
                        "nome": "Funções administrativas",
                        "subtopicos": ["Planejamento"],
                    }
                ],
            },
        }
        alertas = comparar_chunk(chunk, resultado)
        assert alertas == []

    def test_palavra_curta_como_crime_casa_exatamente(self):
        chunk = self._chunk_auditoria("1 Crime.")
        resultado = self._resultado_chunk(["Crime"])
        assert comparar_chunk(chunk, resultado) == []

    def test_chunk_com_falha_e_itens_na_fonte_gera_alerta_chunk_sem_extracao(self):
        chunk = self._chunk_auditoria("1 Fundamentos da matéria.", status="falha")
        alertas = comparar_chunk(chunk, None)
        assert len(alertas) == 1
        assert alertas[0]["tipo"] == "chunk_sem_extracao"

    def test_chunk_com_falha_sem_itens_na_fonte_nao_gera_alerta(self):
        chunk = self._chunk_auditoria("Texto de matéria sem numeração.", status="falha")
        assert comparar_chunk(chunk, None) == []

    def test_materia_sem_numeracao_nao_gera_alerta(self):
        chunk = self._chunk_auditoria("Texto corrido sem nenhuma marcação numérica de tópico.")
        resultado = self._resultado_chunk(["Texto corrido sem nenhuma marcação numérica de tópico"])
        assert comparar_chunk(chunk, resultado) == []

    def test_numero_repetido_na_fonte_flag_so_a_ocorrencia_sem_match_com_posicao_correta(self):
        # Simula o achado real do edital piloto (chunk 32): numeração
        # duplicada por corrupção do texto do PDF-fonte.
        chunk = self._chunk_auditoria("1 Comunicação pública. 2 Área X. 1 Fundamentos e finalidades.")
        resultado = self._resultado_chunk(["Comunicação pública", "Área X"])
        alertas = comparar_chunk(chunk, resultado)
        assert len(alertas) == 1
        assert alertas[0]["tipo"] == "topico_ausente"
        assert alertas[0]["numero_item"] == "1"
        assert alertas[0]["posicao_item"] == 2

    def test_chunk_classificado_nao_gera_alerta_de_classificacao(self):
        chunk = {**self._chunk_auditoria("1 Fundamentos."), "tipo_conhecimento": "basico", "nivel": "medio"}
        assert comparar_chunk(chunk, self._resultado_chunk(["Fundamentos"])) == []

    def test_chunk_sem_nivel_gera_alerta_chunk_sem_classificacao(self):
        # ADR-020: bloco "PARA TODOS OS CARGOS" (ou chunk fora de bloco)
        # sai sem nível — some dos filtros por nível, então tem que alertar.
        chunk = {**self._chunk_auditoria("1 Fundamentos."), "tipo_conhecimento": "basico", "nivel": None}
        alertas = comparar_chunk(chunk, self._resultado_chunk(["Fundamentos"]))
        assert [a["tipo"] for a in alertas] == ["chunk_sem_classificacao"]

    def test_chunk_sem_classificacao_e_com_falha_gera_os_dois_alertas(self):
        chunk = {
            **self._chunk_auditoria("1 Fundamentos.", status="falha"),
            "tipo_conhecimento": None,
            "nivel": None,
        }
        tipos = [a["tipo"] for a in comparar_chunk(chunk, None)]
        assert tipos == ["chunk_sem_classificacao", "chunk_sem_extracao"]

    def test_auditoria_legada_sem_campos_de_classificacao_nao_gera_alerta(self):
        chunk = self._chunk_auditoria("1 Fundamentos.")
        assert comparar_chunk(chunk, self._resultado_chunk(["Fundamentos"])) == []

    def test_topico_nome_numerico_gera_alerta_dedicado(self):
        # Achado real (PF_25_ADM, chunks 17/21): LLM preencheu "nome" com o
        # numeral do item da fonte em vez do texto do tópico (ver ADR-021).
        chunk = self._chunk_auditoria("1 Conceito. 2 Campo de aplicação.")
        resultado = self._resultado_chunk(["1", "2"])
        alertas = comparar_chunk(chunk, resultado)
        numericos = [a for a in alertas if a["tipo"] == "topico_nome_numerico"]
        assert {a["topico_nome_extraido"] for a in numericos} == {"1", "2"}

    def test_topico_nome_numerico_tambem_gera_ausente_e_extra(self):
        # O alerta novo é aditivo — não substitui os dois já existentes,
        # que continuam disparando pro mesmo caso ("1" nunca casa por
        # substring com o item de origem).
        chunk = self._chunk_auditoria("1 Conceito.")
        resultado = self._resultado_chunk(["1"])
        tipos = sorted(a["tipo"] for a in comparar_chunk(chunk, resultado))
        assert tipos == ["topico_ausente", "topico_extra", "topico_nome_numerico"]

    def test_topico_com_nome_textual_nao_gera_alerta_numerico(self):
        chunk = self._chunk_auditoria("1 Fundamentos da matéria.")
        resultado = self._resultado_chunk(["Fundamentos da matéria"])
        alertas = comparar_chunk(chunk, resultado)
        assert all(a["tipo"] != "topico_nome_numerico" for a in alertas)

    def test_topico_nome_numerico_com_espacos_conta(self):
        chunk = self._chunk_auditoria("1 Conceito.")
        resultado = self._resultado_chunk([" 1 "])
        alertas = comparar_chunk(chunk, resultado)
        assert any(a["tipo"] == "topico_nome_numerico" for a in alertas)


class TestSeveridadeDivergenciaLeve:
    """ADR-025: paráfrase leve vira informativo, não alerta bloqueante."""

    _chunk = TestCompararChunk._chunk_auditoria
    _resultado = TestCompararChunk._resultado_chunk

    def test_qualificador_entre_parenteses_e_informativo(self):
        # Caso real PF_25_ADM chunk 31: item repetido no edital, LLM desambiguou o nome.
        chunk = self._chunk(
            "7 Educação corporativa. 7.1 Escolas de governo. 11 Educação corporativa. "
            "11.1 Atuação do pedagogo no âmbito corporativo."
        )
        resultado = self._resultado(["Educação corporativa", "Educação corporativa (atuação do pedagogo)"])
        alertas = comparar_chunk(chunk, resultado)
        assert [a["tipo"] for a in alertas] == ["topico_divergencia_leve"]
        assert alertas[0]["severidade"] == "informativo"

    def test_erro_de_digitacao_da_fonte_corrigido_pelo_llm_e_informativo(self):
        # Caso real STM_25 chunk 31: PDF traz "bBiblioteca Flyway".
        chunk = self._chunk(
            "3 Persistência; JPA 2.0; Hibernate 4.3 ou superior; Hibernate Envers; bBiblioteca Flyway. "
            "4 Banco de dados; PostgreSQL."
        )
        resultado = self._resultado(
            [
                "Persistência; JPA 2.0; Hibernate 4.3 ou superior; Hibernate Envers; Biblioteca Flyway",
                "Banco de dados; PostgreSQL",
            ]
        )
        alertas = comparar_chunk(chunk, resultado)
        assert [a["tipo"] for a in alertas] == ["topico_divergencia_leve"]

    def test_nome_parecido_mas_diferente_continua_extra(self):
        chunk = self._chunk("1 Gestão de pessoas. 2 Gamificação.")
        resultado = self._resultado(["Gestão de pessoas", "Gamificação", "Gestão de projetos"])
        alertas = comparar_chunk(chunk, resultado)
        assert [a["tipo"] for a in alertas] == ["topico_extra"]
        assert "severidade" not in alertas[0]

    def test_topico_inventado_de_outro_dominio_continua_extra(self):
        chunk = self._chunk("1 Gamificação. 2 Mídias para educação.")
        resultado = self._resultado(["Gamificação", "Mídias para educação", "Kubernetes avançado"])
        assert [a["tipo"] for a in comparar_chunk(chunk, resultado)] == ["topico_extra"]

    def test_parafrase_de_um_item_nao_esconde_omissao_de_outro(self):
        # O parêntese de um tópico não pode servir de "casamento tolerante"
        # pra um item diferente que o LLM realmente omitiu.
        chunk = self._chunk("1 Educação corporativa. 2 Gamificação. 3 Lei nº 8.112/1990.")
        resultado = self._resultado(["Educação corporativa (atuação do pedagogo)", "Gamificação"])
        tipos = [a["tipo"] for a in comparar_chunk(chunk, resultado)]
        assert "topico_ausente" in tipos

    def test_validar_edital_separa_bloqueantes_de_informativos(self):
        resultado = {
            "edital": "x.pdf",
            "resultados": [
                {
                    "chunk_index": 0,
                    **self._resultado(["Fundamentos (visão geral)", "Aplicações", "Tópico inventado qualquer"]),
                }
            ],
        }
        auditoria = {"chunks": [self._chunk("1 Fundamentos. 1.1 Histórico. 2 Aplicações.")]}
        validacao = validar_edital(resultado, auditoria)
        assert [a["tipo"] for a in validacao["alertas"]] == ["topico_divergencia_leve", "topico_extra"]
        assert validacao["total_informativos"] == 1
        assert validacao["total_alertas"] == 1


class TestValidarEdital:
    def test_fim_a_fim_com_par_resultado_auditoria(self):
        resultado = {
            "edital": "Edital_Teste.pdf",
            "resultados": [
                {
                    "chunk_index": 0,
                    "cargo": None,
                    "materia_chunk": "MATERIA A",
                    "taxonomia_extraida": {
                        "materia": "Matéria A",
                        "topicos": [{"nome": "1 Tópico um", "subtopicos": []}],
                    },
                },
                {
                    "chunk_index": 1,
                    "cargo": None,
                    "materia_chunk": "MATERIA B",
                    "taxonomia_extraida": {"materia": "Matéria B", "topicos": []},
                },
            ],
        }
        auditoria = {
            "chunks": [
                {
                    "chunk_index": 0,
                    "cargo": None,
                    "materia": "MATERIA A",
                    "texto_enviado_llm": "1 Tópico um. 2 Tópico dois que não foi extraído.",
                    "status": "sucesso",
                },
                {
                    "chunk_index": 1,
                    "cargo": None,
                    "materia": "MATERIA B",
                    "texto_enviado_llm": "",
                    "status": "sucesso",
                },
            ]
        }
        validacao = validar_edital(resultado, auditoria)
        assert validacao["edital"] == "Edital_Teste.pdf"
        assert validacao["total_chunks_analisados"] == 2
        assert validacao["total_alertas"] == 1
        assert validacao["alertas"][0]["tipo"] == "topico_ausente"


class TestMain:
    def test_edital_sem_auditoria_e_pulado_sem_erro(self, tmp_path, caplog):
        (tmp_path / "Edital_Legado.json").write_text(
            json.dumps({"edital": "Edital_Legado.pdf", "resultados": []}), encoding="utf-8"
        )
        main(tmp_path)
        assert not (tmp_path / "Edital_Legado.validacao.json").exists()

    def test_gera_validacao_json_para_edital_com_auditoria(self, tmp_path):
        resultado = {
            "edital": "Edital_A.pdf",
            "resultados": [
                {
                    "chunk_index": 0,
                    "cargo": None,
                    "materia_chunk": "MATERIA A",
                    "taxonomia_extraida": {"materia": "Matéria A", "topicos": [{"nome": "1 Único tópico", "subtopicos": []}]},
                }
            ],
        }
        auditoria = {
            "chunks": [
                {
                    "chunk_index": 0,
                    "cargo": None,
                    "materia": "MATERIA A",
                    "texto_enviado_llm": "1 Único tópico.",
                    "status": "sucesso",
                }
            ]
        }
        (tmp_path / "Edital_A.json").write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
        (tmp_path / "Edital_A.auditoria.json").write_text(json.dumps(auditoria, ensure_ascii=False), encoding="utf-8")

        main(tmp_path)

        saida = json.loads((tmp_path / "Edital_A.validacao.json").read_text(encoding="utf-8"))
        assert saida["total_alertas"] == 0


class TestValidarArquivosConcurso:
    def test_sem_concurso_nao_gera_alertas(self):
        from scripts.validar_taxonomia import validar_arquivos_concurso

        alertas = validar_arquivos_concurso({})
        assert alertas == []

    def test_alerta_ausencia_provas_e_gabaritos(self, tmp_path, monkeypatch):
        from scripts.validar_taxonomia import validar_arquivos_concurso

        monkeypatch.setattr("src.spider.load_processed_slugs", lambda: {"TESTE_25"})
        resultado = {
            "edital": "Edital_Teste.pdf",
            "concurso": {"slug": "TESTE_25", "orgao": "TESTE", "ano": 2025},
        }
        concurso_dir = tmp_path / "2025" / "CEBRASPE" / "TESTE"
        concurso_dir.mkdir(parents=True)

        alertas = validar_arquivos_concurso(resultado, data_dir=tmp_path)
        tipos = [a["tipo"] for a in alertas]
        assert "alerta_ausencia_provas" in tipos
        assert "alerta_ausencia_gabaritos" in tipos
        assert "alerta_ausencia_provas_texto_link" in tipos
        assert "concurso_nao_registrado_processed" not in tipos

    def test_alerta_concurso_nao_registrado_processed(self, tmp_path, monkeypatch):
        from scripts.validar_taxonomia import validar_arquivos_concurso

        monkeypatch.setattr("src.spider.load_processed_slugs", lambda: {"OUTRO_25"})
        resultado = {
            "edital": "Edital_Teste.pdf",
            "concurso": {"slug": "TESTE_25", "orgao": "TESTE", "ano": 2025},
        }
        concurso_dir = tmp_path / "2025" / "CEBRASPE" / "TESTE"
        (concurso_dir / "Provas").mkdir(parents=True)
        (concurso_dir / "Provas" / "prova.pdf").write_bytes(b"%PDF-1.4")
        (concurso_dir / "Gabaritos").mkdir(parents=True)
        (concurso_dir / "Gabaritos" / "gabarito.pdf").write_bytes(b"%PDF-1.4")
        (concurso_dir / "provas_texto_link.json").write_text("{}", encoding="utf-8")

        alertas = validar_arquivos_concurso(resultado, data_dir=tmp_path)
        tipos = [a["tipo"] for a in alertas]
        assert tipos == ["concurso_nao_registrado_processed"]

    def test_tudo_presente_sem_alertas(self, tmp_path, monkeypatch):
        from scripts.validar_taxonomia import validar_arquivos_concurso

        monkeypatch.setattr("src.spider.load_processed_slugs", lambda: {"TESTE_25"})
        resultado = {
            "edital": "Edital_Teste.pdf",
            "concurso": {"slug": "TESTE_25", "orgao": "TESTE", "ano": 2025},
        }
        concurso_dir = tmp_path / "2025" / "CEBRASPE" / "TESTE"
        (concurso_dir / "Provas").mkdir(parents=True)
        (concurso_dir / "Provas" / "prova.pdf").write_bytes(b"%PDF-1.4")
        (concurso_dir / "Gabaritos").mkdir(parents=True)
        (concurso_dir / "Gabaritos" / "gabarito.pdf").write_bytes(b"%PDF-1.4")
        (concurso_dir / "provas_texto_link.json").write_text("{}", encoding="utf-8")

        alertas = validar_arquivos_concurso(resultado, data_dir=tmp_path)
        assert alertas == []

