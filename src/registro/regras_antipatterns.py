"""Anti-patterns do projeto (fonte desde a D3; o CLAUDE.md cita só o núcleo)."""

from src.registro.modelo import Regra

REGRAS_ANTIPATTERNS: tuple[Regra, ...] = (
    Regra(
        id="A01",
        tipo="anti-pattern",
        area="coleta",
        texto=(
            'Nunca comparar `get_attribute("href")` d'
            "ireto contra uma URL absoluta\n"
            "sem resolver primeiro (`urljoin(page.url"
            ", href)`) — os cards da listagem\n"
            "do CEBRASPE usam href relativo (`/concur"
            "sos/PF_25_ADM`), e um\n"
            '`href.startswith("https://...")` sem res'
            "olver descarta 100% dos links\n"
            "silenciosamente (0 resultados, sem exceç"
            "ão). Achado ao vivo em\n"
            "2026-09-19, ver ADR-008."
        ),
        adrs=("ADR-008",),
        testes=(
            "tests/test_spider.py::TestGetContestLinksResolveHref::test_resolve_href_relativo_contra_url_da_pagina",
        ),
    ),
    Regra(
        id="A02",
        tipo="anti-pattern",
        area="coleta",
        texto=(
            "Nunca filtrar ano com regex no texto do "
            "link — o ano está no slug da URL\n"
            "(ex: `TJ_CE_25_NOTARIOS` → 2025), não ap"
            'arece como "2025" no texto visível.'
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A03",
        tipo="anti-pattern",
        area="coleta",
        texto=(
            "Nunca envolver o loop de concursos intei"
            "ro num único `try/except` (mascara\n"
            "falha isolada como falha total do lote)."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A04",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca modelar tópico/subtópico como duas"
            " listas paralelas — perde a\n"
            "hierarquia que a Fase 5 precisa para est"
            "atística."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A05",
        tipo="anti-pattern",
        area="banco",
        texto=(
            "Nunca reabrir a decisão de tecnologia de"
            " banco — PostgreSQL 16 já é o\n"
            "padrão do portfólio."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A06",
        nucleo=True,
        tipo="anti-pattern",
        area="banco",
        texto=(
            "Nunca gravar tabelas deste projeto no `s"
            "tudy-rag-db` nem criar FK para\n"
            "`itens_estudo` — o `study-rag-db` tem ci"
            "clo de vida, credenciais e\n"
            "reconfiguração próprios, e acoplar os do"
            "is quebra um a cada mudança do\n"
            "outro. Cruzamento só por chave natural n"
            "a Etapa 7 (ADR-026)."
        ),
        adrs=("ADR-026",),
        testes=(),
    ),
    Regra(
        id="A07",
        nucleo=True,
        tipo="anti-pattern",
        area="infra",
        texto=(
            "Nunca hardcodar credenciais de API/Postg"
            "res no código — usar `.env`\n"
            "(ver Segurança)."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A08",
        tipo="anti-pattern",
        area="classificacao",
        texto=(
            "Nunca usar `\\b` de regex direto sobre um"
            " slug com underscore para detectar\n"
            "keywords — `_` é `\\w`, então `\\bINSS\\b` "
            "não dispara em `INSS_25`. Dividir\n"
            "o slug em segmentos primeiro."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A09",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca casar cabeçalho de matéria/cargo e"
            "m edital só com letras/espaço/\n"
            "hífen — perde silenciosamente todo cabeç"
            "alho com dígito (`CARGO N:`),\n"
            "vírgula ou parênteses, e o conteúdo corr"
            "espondente é engolido pelo chunk\n"
            "anterior sem erro nenhum. Achado ao vivo"
            " em 2026-09-19 (chunk de 41850\n"
            "chars engolindo ~14 cargos), ver ADR-010"
            " e `LESSONS.md`."
        ),
        adrs=("ADR-010",),
        testes=(
            "tests/test_edital_parser.py::TestPadroes::test_padrao_materia_casa_nomes_com_digito_virgula_parenteses",
        ),
    ),
    Regra(
        id="A10",
        tipo="anti-pattern",
        area="llm",
        texto=(
            "Nunca chamar modelo de raciocínio com `m"
            "ax_tokens` baixo pra `glm-5.3-flash` — o"
            "\n"
            "`content` volta `null` mesmo sem erro de"
            " rede se o orçamento acabar no\n"
            "`reasoning_content`."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A11",
        tipo="anti-pattern",
        area="llm",
        texto=(
            "Nunca usar SDKs pesados de LLM (como lit"
            "ellm ou langchain) na chamada de inferên"
            "cia\n"
            "— chamadas diretas REST via `requests`/`"
            "httpx` mantêm a stack enxuta e confiável"
            ".\n"
            "Isso se refere à chamada de inferência d"
            "o modelo; para observabilidade, usa-se\n"
            "o SDK oficial do Langfuse (OTel, ver ADR"
            "-023)."
        ),
        adrs=("ADR-023",),
        testes=(),
    ),
    Regra(
        id="A12",
        tipo="anti-pattern",
        area="llm",
        texto=(
            "Nunca enviar telemetria via `POST /api/p"
            "ublic/ingestion` (REST manual) —\n"
            "endpoint legado entra em sunset em 2026-"
            "11-16, passando a aceitar apenas scores\n"
            "e rejeitando traces e generations. Usar "
            "o SDK oficial `langfuse` (ADR-023)."
        ),
        adrs=("ADR-023",),
        testes=(),
    ),
    Regra(
        id="A13",
        nucleo=True,
        tipo="anti-pattern",
        area="processo",
        texto=(
            "Nunca deixar um passo do pipeline (extra"
            "ção → artefatos derivados) como\n"
            '"rode manualmente depois" — este projeto'
            " já foi mordido 2x por isso\n"
            "(`run()` nunca chamando `download_concur"
            "so_pdfs`, achado de 2026-09-19;\n"
            "href relativo silenciosamente descartand"
            "o 100% dos links, ADR-008): a\n"
            "falha de esquecer o passo manual não lan"
            "ça erro, só deixa o artefato\n"
            "seguinte desatualizado sem sinal nenhum."
            " Ver ADR-019."
        ),
        adrs=(
            "ADR-008",
            "ADR-019",
        ),
        testes=(),
    ),
    Regra(
        id="A14",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca identificar matéria só pelo nome ("
            "nem por `(cargo, materia)`). O\n"
            "bloco básico repete os mesmos nomes (LÍN"
            "GUA PORTUGUESA, RACIOCÍNIO\n"
            "LÓGICO, ...) em superior e médio com con"
            "teúdo diferente. A chave mínima é\n"
            "`(concurso, tipo_conhecimento, nivel, ca"
            "rgo, materia)`. Ver ADR-020 e\n"
            "`LESSONS.md`."
        ),
        adrs=("ADR-020",),
        testes=(
            "tests/test_edital_parser.py::TestBlocosDeConhecimento::test_mesma_materia_em_niveis_diferentes_fica_distinguivel",
        ),
    ),
    Regra(
        id="A15",
        tipo="anti-pattern",
        area="coleta",
        texto=(
            "Nunca deduzir o concurso pelo path `data"
            "/<ano>/CEBRASPE/<orgao>/`: dois\n"
            "concursos do mesmo órgão no mesmo ano di"
            "videm a pasta. O slug só existe\n"
            "na URL de origem guardada no manifesto."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A16",
        tipo="anti-pattern",
        area="llm",
        texto=(
            "Nunca aceitar `nome` de tópico puramente"
            " numérico como extração válida —\n"
            '`Topico.nome: str` do Pydantic aceita "1'
            '" numa boa (estruturalmente\n'
            "válido), mas é sinal de que o LLM confun"
            "diu o numeral do item da fonte\n"
            "com o texto do tópico, não um tópico leg"
            "ítimo. Achado real: 2 chunks\n"
            'inteiros (Contabilidade) com `status="su'
            'cesso"` e todo `nome` numérico,\n'
            "86 dos 88 alertas de validação de um tes"
            "te completo. Ver ADR-021."
        ),
        adrs=("ADR-021",),
        testes=(
            "tests/test_validar_taxonomia.py::TestCompararChunk::test_topico_nome_numerico_gera_alerta_dedicado",
        ),
    ),
    Regra(
        id="A17",
        tipo="anti-pattern",
        area="llm",
        texto=(
            "Nunca capturar `requests.RequestExceptio"
            "n`/erro de parse de forma\n"
            "genérica e devolver um único `motivo_fal"
            "ha=None` para tudo — timeout,\n"
            "conexão recusada, HTTP 429/5xx, conteúdo"
            " vazio e schema inválido são\n"
            "causas-raiz diferentes com decisões de r"
            "eprocessamento diferentes\n"
            "(transitório vs. precisa de ajuste); col"
            'apsar tudo em `status="falha"`\n'
            "esconde isso do relatório HTML/Datasette"
            " e do Langfuse. Ver ADR-022."
        ),
        adrs=("ADR-022",),
        testes=(
            "tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_content_none_retorna_status_de_conteudo_vazio",
            "tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_json_invalido_retorna_status_de_parse_json",
            "tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_json_fora_do_schema_retorna_status_de_validacao_schema",
            "tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_falha_de_conexao_retorna_status_de_conexao",
        ),
    ),
    Regra(
        id="A18",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca aplicar `[^\\w]` ou normalização NF"
            "KD direta sobre texto bruto extraído de\n"
            "PDF sem antes compor caracteres combinan"
            "tes via `NFC` — caracteres em NFD\n"
            "(como `i` + `\\u0301`) perdem o acento is"
            "olado e geram divergência com a saída do"
            " LLM."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A19",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca validar cobertura de itens do edit"
            "al comparando apenas o campo\n"
            '`topico["nome"]` — o modelo frequentemen'
            "te estrutura itens como `subtopicos`,\n"
            "e ignorá-los gera falsos positivos em ma"
            "ssa de `topico_ausente`."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A20",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca emitir alerta de `topico_extra` ap"
            "enas por ausência de casamento direto\n"
            "com um item numerado individual — se o t"
            "ermo constar no corpo do texto-fonte\n"
            "do chunk, trata-se de um tópico válido d"
            "o texto programático, não alucinação."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A21",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca criar um chunk novo diretamente a "
            "partir de quebra de linha de cabeçalho\n"
            "de cargo sem checar se o bloco intermedi"
            "ário possui itens numerados programático"
            "s."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A22",
        tipo="anti-pattern",
        area="revisao",
        texto=(
            "Nunca silenciar um alerta de validação s"
            "em antes perguntar se o dado está\n"
            "errado. Perda de conteúdo (item omitido)"
            " se corrige no dado; paráfrase\n"
            "explicável se rebaixa para informativo. "
            "Canonicalizar o nome extraído\n"
            "para o texto literal da fonte reintroduz"
            " erro de digitação do PDF. Ver\n"
            "ADR-025."
        ),
        adrs=("ADR-025",),
        testes=(),
    ),
    Regra(
        id="A23",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca usar casamento tolerante contra o "
            "texto-fonte **inteiro** numa\n"
            "checagem por item: um tópico parafrasead"
            'o de um item passa a "cobrir" a\n'
            "omissão de outro item do mesmo chunk."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A24",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca deixar a restrição de cargo no nom"
            "e da matéria (duplica\n"
            "`dim_materia`), nem apagá-la do nome sem"
            " ter extraído os números de cargo\n"
            "(a matéria passa a valer para todos os c"
            "argos sem aviso)."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A25",
        nucleo=True,
        tipo="anti-pattern",
        area="revisao",
        texto=(
            "Nunca aprovar concurso com `UPDATE` dire"
            "to no banco: a próxima carga do\n"
            "writer reverte a partir do JSON."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A26",
        tipo="anti-pattern",
        area="classificacao",
        texto=(
            "Nunca agrupar matéria/assunto/subassunto"
            " por similaridade de texto sem\n"
            "aprovação humana: `atos` × `contratos ad"
            "ministrativos` (0,89), `ativos` ×\n"
            "`passivos` (0,90), `gestão de processos`"
            " × `de pessoas` (0,89). Similaridade\n"
            "só sugere; quem junta é regra determinís"
            "tica ou o dono (ADR-029)."
        ),
        adrs=("ADR-029",),
        testes=(),
    ),
    Regra(
        id="A27",
        nucleo=True,
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca aprovar sinônimo ou mapeamento da "
            "árvore com `UPDATE` no banco nem\n"
            "editando só o banco: a fonte é `canonico"
            "/arvore.json` (antes,\n"
            "`sinonimos.json`), e a próxima carga rev"
            "erte."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A28",
        nucleo=True,
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca ler ou escrever `canonico/arvore.j"
            "son` com `json.load`/`json.dump`\n"
            "direto: o primeiro código da 5B.1 fez is"
            "so, montou a chave com `str(tupla)`\n"
            "e leu o campo `no` em vez de `no_id`. A "
            "regra do pipeline casou 0 de 1259\n"
            "assuntos e o relatório pôs os 4050 itens"
            " sob `None`, sem erro nenhum. Use\n"
            "`src/arvore.py` (`carregar`, `salvar`, `"
            "chave_item`)."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A29",
        nucleo=True,
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca rodar `scripts/semear_arvore.py --"
            "forcar` depois da curadoria: a\n"
            "semente reescreve a árvore do zero e apa"
            "ga toda decisão do dono."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A30",
        nucleo=True,
        tipo="anti-pattern",
        area="revisao",
        texto=(
            "Nunca deixar o agente aprovar proposta d"
            "o LLM em nome do dono; só grupo\n"
            "`regra` é aprovado automaticamente."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A31",
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca juntar um nome composto (`Disposiç"
            "ões gerais, servidores\n"
            "públicos`) a uma de suas partes: isso co"
            "nta uma parte como a outra. Ele\n"
            "aponta para os N nós (ADR-030)."
        ),
        adrs=("ADR-030",),
        testes=(
            "tests/test_arvore_views.py::TestEditalCobra::test_composto_conta_uma_vez_em_cada_no",
        ),
    ),
    Regra(
        id="A32",
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca derivar o pai de um nó da árvore d"
            "o edital de origem: a matéria\n"
            "composta do CD separaria os assuntos de "
            "Constitucional dos outros\n"
            "concursos (ADR-030)."
        ),
        adrs=("ADR-030",),
        testes=(),
    ),
    Regra(
        id="A33",
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca criar nó da árvore automaticamente"
            " a partir de nome novo de edital:\n"
            "o que a regra não mapeia fica pendente p"
            "ara a curadoria."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A34",
        tipo="anti-pattern",
        area="arvore",
        texto=(
            "Nunca deixar dois nós ativos com o mesmo"
            " nome (pela `chave_regra`) sob o mesmo\n"
            "pai, nem duas disciplinas de mesmo nome:"
            " o filtro do site mostra o nome\n"
            "repetido e a incidência se divide. Ao fu"
            "ndir ou renomear disciplina, rode\n"
            "`pytest tests/test_arvore.py`; os testes"
            " `*_sem_irmaos_homonimos` e\n"
            "`*_sem_disciplinas_homonimas` guardam is"
            "so. Cargo não é atributo do nó\n"
            "(ADR-030). Paráfrase (nome diferente) se"
            "gue com o dono."
        ),
        adrs=("ADR-030",),
        testes=(
            "tests/test_arvore.py::test_arvore_curada_sem_irmaos_homonimos",
            "tests/test_arvore.py::test_arvore_curada_sem_disciplinas_homonimas",
        ),
    ),
    Regra(
        id="A35",
        tipo="anti-pattern",
        area="classificacao",
        texto=(
            "Nunca classificar a questão só entre os "
            "nós do edital do caderno: a\n"
            "questão fora do edital ficaria sem nó, e"
            ' o "edital × prova" perderia o\n'
            'lado "cobrado fora do edital".'
        ),
        adrs=(),
        testes=("tests/test_classificacao.py::test_mapear_fora_do_edital_por_no",),
    ),
    Regra(
        id="A36",
        tipo="anti-pattern",
        area="edital",
        texto=(
            "Nunca casar a restrição com `\\([^)]*\\)`:"
            " um parêntese interno\n"
            "(`ANALISTA (TI)`) corta a cláusula no me"
            "io e o resto fica no nome."
        ),
        adrs=(),
        testes=(
            "tests/test_edital_parser.py::TestBlocosDeConhecimento::test_restricao_com_parentese_interno_sai_inteira_do_nome",
        ),
    ),
    Regra(
        id="A37",
        tipo="anti-pattern",
        area="prova",
        texto=(
            "Nunca permitir janela ampla de recuo de "
            "linha de item (> 24 pt, ex.: 8–30 pt) no"
            " parser de provas — captura a primeira l"
            "inha com recuo de parágrafo (~28–29 pt) "
            "do texto-base subsequente após itens de "
            "1 linha física (ADR-031)."
        ),
        adrs=("ADR-031",),
        testes=(),
    ),
    Regra(
        id="A38",
        tipo="anti-pattern",
        area="prova",
        texto=(
            "Nunca confiar na ordem do fluxo interno "
            "de objetos do PDF (PyMuPDF blocks) para "
            "determinar a ordem de leitura em caderno"
            "s sem ordenar visualmente por coordenada"
            "s `(coluna, y0, x0)` (ADR-031)."
        ),
        adrs=("ADR-031",),
        testes=(),
    ),
    Regra(
        id="A39",
        tipo="anti-pattern",
        area="prova",
        texto=(
            'Nunca confiar em `span["flags"] & 16` ou'
            ' "Bold" para segmentar itens de provas ('
            "apenas 9,64% dos cadernos do CEBRASPE us"
            "am fonte com flag negrito; a segmentação"
            " real é por x0 na margem via cluster/mod"
            "a)."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A40",
        tipo="anti-pattern",
        area="prova",
        texto=(
            'Nunca procurar "definitivo" solto no cor'
            "po do padrão de resposta ou gabarito (o "
            'padrão do cargo 2 da PF cita "definitivo'
            '" no texto discursivo; um preliminar com'
            " a mesma redação seria classificado como"
            " definitivo). Avaliar estritamente o cab"
            "eçalho (primeiros 600 caracteres no padr"
            "ão de resposta, 2000 na grade — ver `cla"
            "ssificar_versao`) ou o nome do arquivo."
        ),
        adrs=(),
        testes=(
            "tests/test_gabarito_parser.py::TestClassificarVersao::test_definitivo_solto_apenas_no_corpo_retorna_none",
        ),
    ),
    Regra(
        id="A41",
        tipo="anti-pattern",
        area="prova",
        texto=(
            "Nunca extrair quesitos numerados antes d"
            "o verbo de comando da prova discursiva ("
            'datas como "1 de janeiro..." no enunciad'
            "o viram falso quesito 1)."
        ),
        adrs=(),
        testes=(
            "tests/test_prova_parser.py::TestCadernoDiscursivo::test_quesitos_so_a_partir_do_comando",
        ),
    ),
    Regra(
        id="A42",
        nucleo=True,
        tipo="anti-pattern",
        area="infra",
        texto=(
            "Nunca commitar arquivos JSON de questões"
            " extraídas (`questoes/`) no git — mantid"
            "os localmente e no `.gitignore` por volu"
            "metria, sendo 100% regeneráveis sob dema"
            "nda (ADR-031)."
        ),
        adrs=("ADR-031",),
        testes=(),
    ),
    Regra(
        id="A43",
        tipo="anti-pattern",
        area="banco",
        texto=(
            "Nunca somar linhas de views agregadas po"
            "r cargo (`vw_prova_cobra_*`): cadernos b"
            "ásicos cobrem múltiplos cargos; somar li"
            "nhas de cargos diferentes duplica questõ"
            "es básicas no denominador e no numerador"
            ". Para consultas que cruzam ou agregam m"
            "últiplos cargos/concursos, usar sempre a"
            " função oficial `fn_prova_cobra(...)` ou"
            " filtrar estritamente por um cargo indiv"
            "idual (ADR-032)."
        ),
        adrs=("ADR-032",),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_caderno_basico_multiplos_cargos_conta_uma_vez",
        ),
    ),
    Regra(
        id="A44",
        nucleo=True,
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca pôr senha de role no SQL versionad"
            "o (`site/sql/app_schema.sql`) nem em\n"
            "teste: a primeira versão da 5F.1 fez iss"
            "o e as senhas foram trocadas. Senha\n"
            "vem do `.env` via `site/scripts/aplicar_"
            "schema_app.py`."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A45",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca rodar o site com `python -m site.."
            ".`: o diretório `site` colide com o\n"
            "módulo `site` da stdlib. Use o caminho d"
            "o script ou `uvicorn app.main:app`\n"
            "de dentro de `site/`."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A46",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca dar à role `site_leitura` acesso a"
            "o schema `app` (nem fazer JOIN\n"
            "entre `app.resposta` e as views numa que"
            "ry só): as respostas são lidas pela\n"
            "`site_app` e a lista de chaves entra no "
            "SQL das views por parâmetro."
        ),
        adrs=(),
        testes=("site/tests/test_api_questoes.py::test_permissoes_role_site_leitura",),
    ),
    Regra(
        id="A47",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca aceitar o `voltar` do login sem `a"
            "uth.destino_seguro` (open redirect\n"
            "com `//host` ou `/\\host`)."
        ),
        adrs=(),
        testes=(
            "site/tests/test_contas.py::test_destino_seguro_bloqueia_open_redirect",
        ),
    ),
    Regra(
        id="A48",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca usar a `questao_chave` crua como i"
            "d de elemento HTML: o `|` é\n"
            "separador de namespace em seletor CSS, e"
            ' o `hx-target="#..."` quebra no\n'
            "`querySelector` do HTMX sem aparecer em "
            "teste de rota. Use `dom_id(chave)`\n"
            "(`q-<sha1>`) de `rotas_web.py`."
        ),
        adrs=(),
        testes=(
            "site/tests/test_web.py::test_hx_target_da_correcao_e_seletor_css_valido",
        ),
    ),
    Regra(
        id="A49",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca interpolar valor da query string d"
            "entro de expressão do Alpine\n"
            "(`x-data=\"{ x: '{{ valor }}' }\"`): o nav"
            "egador decodifica `&#39;` de volta\n"
            "para `'` antes de o Alpine avaliar, e vi"
            "ra XSS. Passe por atributo\n"
            "`data-*` e leia com `$el.dataset`."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A50",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca pôr `hx-get` num `<select>` dentro"
            " do form de filtros: em GET o HTMX\n"
            "envia só o valor do próprio elemento e p"
            "erde os outros filtros. O gatilho\n"
            'fica no `<form>` (`hx-trigger="change, s'
            'ubmit"`).'
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A51",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca devolver o fragmento só por `HX-Re"
            "quest`: a restauração de histórico\n"
            "do HTMX também manda esse header e esper"
            "a a página inteira (checar\n"
            "`HX-History-Restore-Request`)."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A52",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca pôr campo pesado (texto-base, figu"
            "ras) em `QuestaoResumo` para\n"
            "servir o HTML: muda o contrato da API e "
            "multiplica o payload da listagem.\n"
            "O card busca em `/q/.../anexos` quando o"
            " usuário abre."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A53",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca declarar `cargo_numero: int` em ro"
            "ta HTML com select de cargo: trocar\n"
            "o concurso limpa o select e manda `cargo"
            "_numero=`, e o FastAPI responde 422\n"
            "(só aparece no navegador, não no teste c"
            "om parâmetro válido)."
        ),
        adrs=(),
        testes=(
            "site/tests/test_web.py::test_cargo_vazio_ao_trocar_concurso_nao_da_422",
        ),
    ),
    Regra(
        id="A54",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca mandar o gabarito na prova do simu"
            "lado (`ItemSimulado` não tem o\n"
            "campo) nem o padrão de resposta antes de"
            " encerrar: a correção é sempre no\n"
            "servidor."
        ),
        adrs=(),
        testes=("site/tests/test_simulado.py::test_prova_em_ordem_e_sem_gabarito",),
    ),
    Regra(
        id="A55",
        tipo="anti-pattern",
        area="site",
        texto=(
            "Nunca apagar o rascunho do simulado no c"
            "lique de enviar: se o POST falhar\n"
            "(CSRF, rede), as marcações de horas de p"
            "rova somem. Só a página de\n"
            "resultado apaga. E nada de `try` em `x-i"
            "nit`: Alpine só avalia expressão."
        ),
        adrs=(),
        testes=("site/tests/test_simulado.py::test_rascunho_so_some_no_resultado",),
    ),
    Regra(
        id="A56",
        tipo="anti-pattern",
        area="testes",
        texto=(
            "Nunca usar dois `TestClient(app)` ao mes"
            "mo tempo nos testes: os pools do\n"
            "banco são globais e o lifespan do primei"
            "ro a sair fecha os do outro."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A57",
        nucleo=True,
        tipo="anti-pattern",
        area="banco",
        texto=(
            "Nunca dar GRANT a role do site esperando"
            " que ele sobreviva a uma carga:\n"
            "`schema_estatisticas.sql` recria as view"
            "s com `DROP ... CASCADE`.\n"
            "`stats_writer.criar_schema` guarda e rea"
            "plica os GRANTs do schema; não\n"
            "remover isso (sem ele, toda reextração d"
            "erruba o site com 500)."
        ),
        adrs=(),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_criar_schema_preserva_grants_das_views",
        ),
    ),
    Regra(
        id="A58",
        tipo="anti-pattern",
        area="prova",
        texto=(
            "Nunca comparar texto-base por hash do te"
            "xto cru: a quebra de parágrafo\n"
            "depende do layout do caderno. A chave ca"
            "nônica normaliza espaços."
        ),
        adrs=(),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_canonica_ignora_quebra_de_paragrafo_do_texto_base",
        ),
    ),
    Regra(
        id="A59",
        nucleo=True,
        tipo="anti-pattern",
        area="testes",
        texto=(
            "Nunca remover o `conftest.py` da raiz: s"
            "em ele o pytest grava os erros\n"
            "simulados (`x.test`, `XX_25`) em `logs/s"
            "craper_cebraspe.log`, e o log de\n"
            "produção deixa de servir para auditar ex"
            "ecução real."
        ),
        adrs=(),
        testes=(),
    ),
    Regra(
        id="A60",
        tipo="anti-pattern",
        area="banco",
        texto=(
            "Nunca computar questões discursivas junt"
            "o com questões objetivas: discursivas po"
            "ssuem grão, tema e dinâmica de pontuação"
            " inteiramente distintos e devem ser cons"
            "umidas estritamente via `vw_discursivas`"
            " (ADR-032)."
        ),
        adrs=("ADR-032",),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_discursivas",
        ),
    ),
    Regra(
        id="A61",
        tipo="anti-pattern",
        area="infra",
        texto=(
            "Nunca usar o `site_dir` padrão do MkDocs"
            " (`site/`): o build apagaria o app FastA"
            "PI em `site/`. O build vai para `build/d"
            "ocs` (ADR-040)."
        ),
        adrs=("ADR-040",),
        testes=(),
    ),
    Regra(
        id="A62",
        nucleo=True,
        tipo="anti-pattern",
        area="processo",
        texto="""Nunca editar à mão as páginas de `docs/tecnico/`: são geradas de `src/registro/`
por `scripts/gerar_docs.py`, e o teste guarda recusa a diferença (ADR-041).""",
        adrs=("ADR-041",),
        testes=("tests/test_registro.py::test_paginas_geradas_batem_com_o_disco",),
    ),
)
