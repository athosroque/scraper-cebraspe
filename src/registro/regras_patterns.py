"""Patterns do CLAUDE.md §6, bullets 1 a 35, texto literal (Etapa 9/D2)."""

from src.registro.modelo import Regra

REGRAS_PATTERNS_1: tuple[Regra, ...] = (
    Regra(
        id="P01",
        tipo="pattern",
        area="coleta",
        texto=(
            "Filtro de ano sempre pelo slug da URL (`_25`, `_26`, ...) — nunca pelo\n"
            'texto visível do link (o texto do card é sempre "MAIS INFORMAÇÕES",\n'
            "confirmado ao vivo)."
        ),
    ),
    Regra(
        id="P02",
        tipo="pattern",
        area="coleta",
        texto=(
            "Falha de rede/parsing por concurso individual é logada e o crawler segue\n"
            "para o próximo — nunca aborta o lote inteiro."
        ),
    ),
    Regra(
        id="P03",
        tipo="pattern",
        area="coleta",
        texto=(
            "Slugify determinístico (acentos/espaços → forma normalizada única) para\n"
            "nomes de órgão usados em paths de disco."
        ),
        testes=(
            "tests/test_downloader.py::TestSlugify::test_normaliza_acentos_e_espacos",
        ),
    ),
    Regra(
        id="P04",
        tipo="pattern",
        area="llm",
        texto=(
            "Toda chamada LLM é feita diretamente à API REST do OpenRouter (`z-ai/glm-5.3-flash`),\n"
            "pelo núcleo `src/llm_openrouter.chamar_llm_json` (status tipados, Langfuse,\n"
            "gancho `pos_validacao`). Uso novo não monta payload próprio."
        ),
        testes=(
            "tests/test_taxonomia_extractor.py::TestOpenRouterDirect::test_requisicao_vai_para_openrouter",
        ),
    ),
    Regra(
        id="P05",
        tipo="pattern",
        area="banco",
        texto=(
            "Banco próprio, sem FK entre projetos: dimensões carregam chave natural\n"
            "normalizada (`slug`, `materia_normalizada`, tópico normalizado) para o\n"
            "cruzamento futuro com `itens_estudo` via tabela de mapeamento (ADR-026)."
        ),
        adrs=("ADR-026",),
    ),
    Regra(
        id="P06",
        tipo="pattern",
        area="coleta",
        texto=(
            "Priorização de cargo grande (INSS, PF, PRF, ...) também é feita pelo slug\n"
            "da URL, dividido em segmentos por `_`/`-` e comparado contra um set de\n"
            "keywords — nunca com `\\b` de regex direto no slug (underscore é `\\w`, não\n"
            "cria fronteira de palavra)."
        ),
    ),
    Regra(
        id="P07",
        tipo="pattern",
        area="coleta",
        texto=(
            "Idempotência do crawler: registro local em JSON\n"
            "(`data/processed_concursos.json`, um array de slugs) checado/atualizado a\n"
            "cada concurso processado com sucesso — não depende da estrutura de pastas\n"
            "da Etapa 3."
        ),
    ),
    Regra(
        id="P08",
        tipo="pattern",
        area="coleta",
        texto=(
            "Nome de órgão também extraído do slug (`extract_orgao_from_slug` em\n"
            "`spider.py`: segmento antes do token de ano `_YY`) — o texto do link\n"
            "nunca carrega o nome do órgão, mesma causa-raiz do filtro de ano."
        ),
        testes=(
            "tests/test_spider.py::TestExtractOrgaoFromSlug::test_extrai_segmento_antes_do_ano",
        ),
    ),
    Regra(
        id="P09",
        tipo="pattern",
        area="coleta",
        texto=(
            'Validação de PDF baixado sempre por magic bytes (`content.startswith(b"%PDF-")`)\n'
            "no conteúdo em si, nunca só pelo header `Content-Type` — um link quebrado\n"
            "pode responder 200 com uma página HTML de erro."
        ),
        testes=(
            "tests/test_downloader.py::TestIsValidPdf::test_rejeita_conteudo_html",
            "tests/test_downloader.py::TestIsValidPdf::test_rejeita_mesmo_com_content_type_pdf_se_magic_bytes_nao_batem",
        ),
    ),
    Regra(
        id="P10",
        tipo="pattern",
        area="coleta",
        texto=(
            "Dedup de download em duas camadas: por URL (manifesto `.manifest.json` por\n"
            "concurso, evita nova requisição de rede numa reexecução) e por hash de\n"
            "conteúdo (evita gravar o mesmo PDF duas vezes quando dois links diferentes\n"
            "apontam para o mesmo arquivo)."
        ),
        testes=(
            "tests/test_downloader.py::TestDownloadPdf::test_pula_download_se_ja_no_manifesto",
            "tests/test_downloader.py::TestDownloadPdf::test_dedup_por_hash_reaproveita_arquivo_existente",
        ),
    ),
    Regra(
        id="P11",
        tipo="pattern",
        area="coleta",
        texto=(
            'Todo `href` de `get_attribute("href")` é resolvido com\n'
            "`urljoin(page.url, href)` antes de comparar contra a URL base — o atributo\n"
            "cru do HTML pode vir relativo, e o `.href` (propriedade JS resolvida) não\n"
            "é o que `get_attribute` devolve."
        ),
    ),
    Regra(
        id="P12",
        tipo="pattern",
        area="edital",
        texto=(
            "Cabeçalho de matéria/cargo em edital sempre casado com um padrão que\n"
            "aceita dígitos, vírgula e parênteses no meio (`[A-ZÀ-Ú0-9 /,()\\-]`), não\n"
            "só letras/espaço/hífen — títulos reais como `CARGO 7: MÉDICO CLÍNICO` e\n"
            "`ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO:` têm esses\n"
            "caracteres."
        ),
        testes=(
            "tests/test_edital_parser.py::TestPadroes::test_padrao_materia_casa_nomes_com_digito_virgula_parenteses",
        ),
    ),
    Regra(
        id="P13",
        tipo="pattern",
        area="edital",
        texto=(
            "Chunking de edital sempre nos dois níveis (cargo E matéria), nunca só um —\n"
            "cargos de especialidade (ex: áreas médicas) não têm matéria nomeada à\n"
            "parte, o conteúdo vem direto embaixo do cabeçalho `CARGO N: <nome>`."
        ),
    ),
    Regra(
        id="P14",
        tipo="pattern",
        area="edital",
        texto=(
            "Checagem de layout multi-coluna (`checar_ordem_confiavel`) só considera\n"
            "blocos de texto com tamanho mínimo (`TAMANHO_MINIMO_BLOCO_COLUNA`) — um\n"
            "bloco curto isolado (título, assinatura) tem x0 diferente da margem do\n"
            "corpo sem indicar colunas paralelas de conteúdo."
        ),
    ),
    Regra(
        id="P15",
        tipo="pattern",
        area="llm",
        texto=(
            "Chamada ao modelo de raciocínio (`glm-5.3-flash`) sempre com\n"
            "`max_tokens` generoso — um orçamento baixo é consumido pelo `reasoning_content`\n"
            "antes do `content` final, que volta `null` mesmo sem erro de rede."
        ),
        testes=(
            "tests/test_taxonomia_extractor.py::TestParametrosConfiguraveis::test_reasoning_padrao_e_max_tokens_12000",
        ),
    ),
    Regra(
        id="P16",
        tipo="pattern",
        area="llm",
        texto=(
            "Toda chamada LLM com reasoning limitado a 3000 tokens via `REASONING_PADRAO`\n"
            "do `src/llm_openrouter.py` (fonte única: default de `chamar_llm_json`,\n"
            "reexportado pelo extrator de taxonomia e usado no payload do bot do\n"
            "Telegram). Decisão do dono em 2026-09-25. Defaults atuais do extrator:\n"
            "`MAX_TOKENS=12000`, `REQUEST_TIMEOUT=120`, reasoning 3000 — vieram do merge\n"
            "`b823c31` e substituíram os `24576`/`240` registrados na decisão de\n"
            "2026-09-20 (ADR-016), que ficam só como histórico."
        ),
        adrs=("ADR-016",),
        testes=(
            "tests/test_taxonomia_extractor.py::TestReasoningPadraoUnico::test_nucleo_envia_reasoning_3000_por_padrao",
            "tests/test_taxonomia_extractor.py::TestReasoningPadraoUnico::test_extrator_usa_a_constante_do_nucleo",
        ),
    ),
    Regra(
        id="P17",
        tipo="pattern",
        area="llm",
        texto=(
            "Chaves do OpenRouter são dedicadas por etapa (`llm_openrouter.ETAPA_*` +\n"
            "`chave_openrouter`): `OPENROUTER_KEY_TAXONOMIA_EDITAL`, `_SINONIMOS`,\n"
            "`_CURADORIA_ARVORE`, `_CLASSIFICACAO_QUESTOES` e `_TELEGRAM`. O nome da chave\n"
            "no OpenRouter é igual ao nome do trace no Langfuse\n"
            "(`cebraspe-<etapa>-<função>`). Chave vazia cai na `OPENROUTER_API_KEY`\n"
            "com aviso `[CHAVE_FALLBACK]` no log."
        ),
    ),
    Regra(
        id="P18",
        tipo="pattern",
        area="revisao",
        texto=(
            "Todo passo derivado do checkpoint de revisão (validação de-para, relatório\n"
            "HTML, banco Datasette, restart do container) é acionado automaticamente\n"
            "ao final do pipeline de extração/reprocessamento\n"
            "(`scripts/atualizar_revisao.py`, chamado por `revisar_taxonomia_piloto.py`\n"
            "e `reprocessar_falhas_piloto.py`) — nunca deixado como passo manual\n"
            "separado. O restart do Datasette é best-effort (loga aviso, nunca lança\n"
            "exceção) pra não derrubar o pipeline de extração por causa de\n"
            "infraestrutura local indisponível."
        ),
    ),
    Regra(
        id="P19",
        tipo="pattern",
        area="edital",
        texto=(
            "Todo chunk carrega `tipo_conhecimento`/`nivel` herdados do cabeçalho de\n"
            "bloco `CONHECIMENTOS BÁSICOS/ESPECÍFICOS PARA ... NÍVEL SUPERIOR/MÉDIO`\n"
            "(`PADRAO_BLOCO`), além de `cargo_numero`, `materia_normalizada` e\n"
            "`apenas_discursiva` (lista única em `CAMPOS_CLASSIFICACAO_CHUNK`). O\n"
            "concurso (`slug`/`orgao`/`ano`) vem do manifesto do downloader\n"
            "(`resolver_concurso_do_pdf`), não do path em disco (a pasta é por órgão).\n"
            "Esses campos vêm só do parser/manifesto, então extração antiga é\n"
            "completada com `scripts/backfill_classificacao_chunks.py` sem chamar o\n"
            "LLM (ADR-020)."
        ),
        adrs=("ADR-020",),
    ),
    Regra(
        id="P20",
        tipo="pattern",
        area="llm",
        texto=(
            "Falha *semântica* do LLM (resposta estruturalmente válida mas com\n"
            "conteúdo errado — ex: `nome` de tópico igual ao numeral do item da\n"
            "fonte) é corrigida por reparo local determinístico quando o dado pra\n"
            "corrigir já está disponível (texto-fonte), nunca por repetir a mesma\n"
            "chamada ao LLM torcendo por sorte — sem contexto do erro, uma repetição\n"
            "não tem garantia de corrigir e não deixa rastro distinto de um retry por\n"
            "falha de rede. Ver ADR-021."
        ),
        adrs=("ADR-021",),
        testes=(
            "tests/test_taxonomia_extractor.py::TestReparoNomeTopicoNumerico::test_nome_numerico_e_reparado_com_texto_do_item_fonte_sem_nova_chamada",
        ),
    ),
    Regra(
        id="P21",
        tipo="pattern",
        area="llm",
        texto=(
            "Toda falha na chamada ao OpenRouter (`_chamar_llm_uma_vez`) devolve um\n"
            "status técnico específico (`falha_timeout`, `falha_conexao`,\n"
            "`falha_rate_limit`, `falha_http`, `falha_rede`, `falha_conteudo_vazio`,\n"
            "`falha_parse_json`, `falha_validacao_schema`), nunca um `motivo_falha`\n"
            "genérico — persistido no `status` do chunk e replicado em\n"
            '`metadata["tipo_erro"]` no Langfuse, pra distinguir falha transitória\n'
            "(timeout/conexão/rate-limit, retry tende a resolver) de falha que se\n"
            "repete com os mesmos parâmetros (conteúdo vazio/parse/schema, retry\n"
            "sozinho não ajuda). Ver ADR-022."
        ),
        adrs=("ADR-022",),
        testes=(
            "tests/test_taxonomia_extractor.py::TestClassificacaoDeErros::test_cada_tipo_de_falha_fica_rastreavel_no_metadata_langfuse_como_tipo_erro",
            "tests/test_taxonomia_extractor.py::TestClassificacaoDeErros::test_todos_os_status_de_falha_sao_distintos_entre_si",
        ),
    ),
    Regra(
        id="P22",
        tipo="pattern",
        area="llm",
        texto=(
            "Telemetria de observabilidade exclusivamente via SDK oficial `langfuse` (OTel),\n"
            "com observation (`generation`) aberta imediatamente antes da chamada HTTP para\n"
            "medição precisa da latência real de rede/inferência. Ver ADR-023."
        ),
        adrs=("ADR-023",),
        testes=(
            "tests/test_taxonomia_extractor.py::TestLangfuseSdk::test_registra_falha_na_generation_e_trace",
        ),
    ),
    Regra(
        id="P23",
        tipo="pattern",
        area="edital",
        texto=(
            "Normalização de whitespace no PyMuPDF: substituir sempre espaços não-separáveis\n"
            '(`\\xa0`) por espaço ASCII (`" "`) logo na extração de texto das páginas (`extrair_texto_paginas`\n'
            "e detecção de cargo preliminar). PDFs do CEBRASPE contêm `\\xa0` nos cabeçalhos\n"
            "de seções e blocos, o que faz buscas literais e regexes falharem silenciosamente."
        ),
        testes=(
            "tests/test_edital_parser.py::TestExtrairSecaoObjetosAvaliacaoDetalhada::test_extrair_secao_com_espacos_nao_separaveis",
        ),
    ),
    Regra(
        id="P24",
        tipo="pattern",
        area="edital",
        texto=(
            "Títulos de cargos multi-linha sem itens no parser: quando um cabeçalho de cargo\n"
            "quebra linhas no layout do PDF e o bloco subsequente não contém itens\n"
            "numerados (`extrair_itens_numerados`), o texto deve ser acumulado ao rótulo do\n"
            'cargo (`f"{cargo_atual} {texto_bloco}"`), evitando criar chunks vazios sem matéria.'
        ),
    ),
    Regra(
        id="P25",
        tipo="pattern",
        area="edital",
        texto=(
            "Variações de blocos de matérias: mapear `CONHECIMENTOS GERAIS` para tipo básico\n"
            '(`"basico"`) e aceitar prefixação numérica de itens no edital (`PADRAO_BLOCO`\n'
            "com `(?:\\d+(?:\\.\\d+)*\\s+)?`)."
        ),
        testes=(
            "tests/test_edital_parser.py::TestPadroes::test_padrao_bloco_com_prefixo_numerico",
        ),
    ),
    Regra(
        id="P26",
        tipo="pattern",
        area="edital",
        texto=(
            "Colons parentéticos em matérias: cabeçalhos com restrição entre parênteses\n"
            "(ex.: `LÍNGUA INGLESA (APENAS PARA O CARGO 3: ...):`) exigem regex que capture\n"
            "o parêntese fechado antes do colon delimitador (`(?:\\s*\\([^)]*\\))?:`), impedindo\n"
            "que o colon interno trunque o nome da matéria."
        ),
    ),
    Regra(
        id="P27",
        tipo="pattern",
        area="edital",
        texto=(
            "Detecção determinística de cargo e nível único: editais com cargo único (ex.:\n"
            "`TCU_25_TEFC`) não repetem cargos nem declaração de nível na seção de Objetos\n"
            "de Avaliação; inspecionar as páginas preliminares (`DO CARGO DE...` e `REQUISITOS:`)\n"
            "para injetar `cargo_padrao` e `nivel_padrao` automaticamente no chunking."
        ),
        testes=(
            "tests/test_edital_parser.py::TestBlocosDeConhecimento::test_cargo_padrao_e_nivel_padrao_em_bloco_sem_declaracao_explicita",
        ),
    ),
    Regra(
        id="P28",
        tipo="pattern",
        area="classificacao",
        texto=(
            "Resiliência na validação de taxonomia contra PDFs:\n"
            '1. Compor caracteres Unicode via `unicodedata.normalize("NFC", texto)` antes\n'
            "   de remover pontuação (`[^\\w]`), evitando que acentos combinantes decompostos\n"
            "   (NFD) sejam descartados.\n"
            "2. Substituir ligaduras tipográficas corrompidas de fontes do CEBRASPE\n"
            "   (`MAPA_LIGATURAS_FONTES`: `Ɵ`→`ti`, `Ō`→`ft`, `ﬃ`→`ffi`, `ﬁ`→`fi`, etc.).\n"
            "3. Validar cobertura de itens numerados contra tópicos OU subtópicos\n"
            "   (`todos_extraidos`), reconhecendo quando o LLM subordina itens como subtópicos.\n"
            "4. Permitir casamento por fronteira de palavras (`\\b`) e igualdade exata para\n"
            '   termos com 3 ou mais caracteres (ex.: "Crime", "Atos"), reservando o piso\n'
            "   de 6 caracteres apenas para match de substring livre.\n"
            "5. Só classificar tópico como `topico_extra` se ele não tiver correspondência\n"
            "   nem estiver contido no texto integral normalizado do chunk (`texto_fonte_norm`)."
        ),
        testes=(
            "tests/test_validar_taxonomia.py::TestNormalizar::test_acento_combinante_decomposto_normaliza_igual_ao_precomposto",
        ),
    ),
    Regra(
        id="P29",
        tipo="pattern",
        area="edital",
        texto=(
            "Cabeçalhos de matérias multi-linha em editais: `PADRAO_MATERIA` só aceita quebras\n"
            "de linha se a linha anterior terminar com conectivos (`E|OU|DE|DA|DO|DOS|DAS` ou vírgula),\n"
            "evitando incorporar indevidamente títulos de cargo em layouts multi-linha como matérias falsas."
        ),
        testes=(
            "tests/test_edital_parser.py::TestPadroes::test_padrao_materia_nao_casa_linha_de_cargo",
        ),
    ),
    Regra(
        id="P30",
        tipo="pattern",
        area="edital",
        texto=(
            "Matérias sem dois-pontos delimitadores antes do item 1: quando um bloco sob cabeçalho\n"
            "de cargo contém itens numerados imediatos mas possui um prefixo em caixa alta antes do primeiro\n"
            "item (ex: `NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO ... 1`), o prefixo é\n"
            "extraído como nome da matéria e o corpo do chunk inicia a partir do item 1, evitando que a\n"
            "matéria receba o nome do cargo ou perca seu conteúdo."
        ),
    ),
    Regra(
        id="P31",
        tipo="pattern",
        area="coleta",
        texto=(
            "Filtro de editais de abertura no crawler: casar sempre com fronteira de palavra\n"
            "`\\bABERTURA\\b` (`re.search(r'EDITAL.*?\\bABERTURA\\b', text)`), impedindo que editais\n"
            'administrativos de retificação com palavras como "reabertura" sejam classificados\n'
            "como editais de abertura."
        ),
    ),
    Regra(
        id="P32",
        tipo="pattern",
        area="llm",
        texto=(
            "Item de primeiro nível omitido pelo LLM é reinjetado localmente a partir\n"
            "do texto-fonte (`reinjetar_itens_ausentes`, logo depois do reparo de nome\n"
            "numérico), sem nova chamada ao LLM, e só quando o item é simples (sem\n"
            "subitens `N.1`, ≤ 150 chars). Item complexo continua `topico_ausente`\n"
            "para revisão humana. Ver ADR-025."
        ),
        adrs=("ADR-025",),
        testes=(
            "tests/test_taxonomia_extractor.py::TestReinjetarItensAusentes::test_item_omitido_e_reinjetado_na_posicao_da_fonte",
            "tests/test_taxonomia_extractor.py::TestReinjetarItensAusentes::test_item_com_subitens_nao_e_reinjetado",
        ),
    ),
    Regra(
        id="P33",
        tipo="pattern",
        area="classificacao",
        texto=(
            "Alerta de validação tem severidade: paráfrase leve (qualificador entre\n"
            "parênteses, erro de digitação da fonte corrigido pelo LLM, similaridade\n"
            "≥ 0,92) vira `topico_divergencia_leve` `informativo`, visível mas fora de\n"
            "`total_alertas`. Reparo e validador usam a mesma comparação textual\n"
            "(`src/comparacao_texto.py`)."
        ),
        testes=(
            "tests/test_validar_taxonomia.py::TestSeveridadeDivergenciaLeve::test_qualificador_entre_parenteses_e_informativo",
            "tests/test_validar_taxonomia.py::TestSeveridadeDivergenciaLeve::test_erro_de_digitacao_da_fonte_corrigido_pelo_llm_e_informativo",
        ),
    ),
    Regra(
        id="P34",
        tipo="pattern",
        area="edital",
        texto=(
            "Assinatura do fim da seção (nome + cargo do signatário) é removida em\n"
            "`_limpar_ruido_edital` ancorando no **cargo** (`PADRAO_CARGO_ASSINATURA`)\n"
            "no fim do texto, nunca no nome em caixa alta."
        ),
        testes=(
            "tests/test_edital_parser.py::TestRemoverAssinaturaFinal::test_limpar_ruido_tambem_remove_assinatura",
        ),
    ),
    Regra(
        id="P35",
        tipo="pattern",
        area="banco",
        texto=(
            "Fatos de um concurso (`taxonomia_itens`, `provas`) são substituídos\n"
            "numa transação a cada carga; dimensões usam upsert por chave natural\n"
            "(`comparacao_texto.normalizar`). Cargos usam upsert em `(concurso, numero)`\n"
            "porque `provas_cargos` aponta para eles. Ver ADR-027."
        ),
        adrs=("ADR-027",),
    ),
)
