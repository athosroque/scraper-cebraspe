<!-- Gerado por scripts/gerar_docs.py a partir de src/registro/. Não editar à mão: rode `make docs-gerar`. -->

# Regras

Patterns (o que fazer) e anti-patterns (o que nunca fazer) do projeto, por área. Use antes de mexer numa área: a [tarefa](tarefas.md) diz quais regras valem nela.

Fonte: `src/registro/regras_*.py`. O `CLAUDE.md` cita só o núcleo, as regras que quebram dados se forem esquecidas. Cada regra mostra as ADRs que a motivam e o teste que a guarda, quando houver.

## Núcleo

- [P41](#p41) Aprovação da revisão humana é o `status_revisao_humana` do `<edital>.json` (`APROVADO...`). O writer relê o …
- [P51](#p51) Decisão do dono na árvore só via `scripts/curar_arvore.py` (ou as funções de `src/arvore.py`): `--mapear` …
- [P67](#p67) O que fica fora do site é decidido só em `inventario/exclusoes.json` (slug, categoria de …
- [P70](#p70) Script novo em `scripts/` (ou módulo de `src/` com `__main__`) entra em `src/registro/scripts.py`, e mudança …
- [P71](#p71) Lote novo (ou qualquer passo que grava no banco) nunca altera o piloto (PF_25_ADM, TCU_25_TEFC, IBAMA_25 …
- [P72](#p72) O nível matéria da árvore é a disciplina e só aceita os nomes de `canonico/disciplinas.json`. Título de bloco …
- [A06](#a06) Nunca gravar tabelas deste projeto no `study-rag-db` nem criar FK para `itens_estudo` — o `study-rag-db` tem …
- [A07](#a07) Nunca hardcodar credenciais de API/Postgres no código — usar `.env` (ver Segurança).
- [A13](#a13) Nunca deixar um passo do pipeline (extração → artefatos derivados) como "rode manualmente depois" — este …
- [A25](#a25) Nunca aprovar concurso com `UPDATE` direto no banco: a próxima carga do writer reverte a partir do JSON.
- [A27](#a27) Nunca aprovar sinônimo ou mapeamento da árvore com `UPDATE` no banco nem editando só o banco: a fonte é …
- [A28](#a28) Nunca ler ou escrever `canonico/arvore.json` com `json.load`/`json.dump` direto: o primeiro código da 5B.1 …
- [A29](#a29) Nunca rodar `scripts/semear_arvore.py --forcar` depois da curadoria: a semente reescreve a árvore do zero e …
- [A30](#a30) Nunca deixar o agente aprovar proposta do LLM em nome do dono; só grupo `regra` é aprovado automaticamente.
- [A42](#a42) Nunca commitar arquivos JSON de questões extraídas (`questoes/`) no git — mantidos localmente e no …
- [A44](#a44) Nunca pôr senha de role no SQL versionado (`site/sql/app_schema.sql`) nem em teste: a primeira versão da 5F.1 …
- [A57](#a57) Nunca dar GRANT a role do site esperando que ele sobreviva a uma carga: `schema_estatisticas.sql` recria as …
- [A59](#a59) Nunca remover o `conftest.py` da raiz: sem ele o pytest grava os erros simulados (`x.test`, `XX_25`) em …
- [A62](#a62) Nunca editar à mão as páginas de `docs/tecnico/`: são geradas de `src/registro/` por `scripts/gerar_docs.py` …

## Patterns

### coleta

#### P01

Filtro de ano sempre pelo slug da URL (`_25`, `_26`, ...) — nunca pelo
texto visível do link (o texto do card é sempre "MAIS INFORMAÇÕES",
confirmado ao vivo).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P02

Falha de rede/parsing por concurso individual é logada e o crawler segue
para o próximo — nunca aborta o lote inteiro.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P03

Slugify determinístico (acentos/espaços → forma normalizada única) para
nomes de órgão usados em paths de disco.

ADRs: nenhuma

Teste guarda: `tests/test_downloader.py::TestSlugify::test_normaliza_acentos_e_espacos`

#### P06

Priorização de cargo grande (INSS, PF, PRF, ...) também é feita pelo slug
da URL, dividido em segmentos por `_`/`-` e comparado contra um set de
keywords — nunca com `\b` de regex direto no slug (underscore é `\w`, não
cria fronteira de palavra).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P07

Idempotência do crawler: registro local em JSON
(`data/processed_concursos.json`, um array de slugs) checado/atualizado a
cada concurso processado com sucesso — não depende da estrutura de pastas
da Etapa 3.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P08

Nome de órgão também extraído do slug (`extract_orgao_from_slug` em
`spider.py`: segmento antes do token de ano `_YY`) — o texto do link
nunca carrega o nome do órgão, mesma causa-raiz do filtro de ano.

ADRs: nenhuma

Teste guarda: `tests/test_spider.py::TestExtractOrgaoFromSlug::test_extrai_segmento_antes_do_ano`

#### P09

Validação de PDF baixado sempre por magic bytes (`content.startswith(b"%PDF-")`)
no conteúdo em si, nunca só pelo header `Content-Type` — um link quebrado
pode responder 200 com uma página HTML de erro.

ADRs: nenhuma

Teste guarda: `tests/test_downloader.py::TestIsValidPdf::test_rejeita_conteudo_html`, `tests/test_downloader.py::TestIsValidPdf::test_rejeita_mesmo_com_content_type_pdf_se_magic_bytes_nao_batem`

#### P10

Dedup de download em duas camadas: por URL (manifesto `.manifest.json` por
concurso, evita nova requisição de rede numa reexecução) e por hash de
conteúdo (evita gravar o mesmo PDF duas vezes quando dois links diferentes
apontam para o mesmo arquivo).

ADRs: nenhuma

Teste guarda: `tests/test_downloader.py::TestDownloadPdf::test_pula_download_se_ja_no_manifesto`, `tests/test_downloader.py::TestDownloadPdf::test_dedup_por_hash_reaproveita_arquivo_existente`

#### P11

Todo `href` de `get_attribute("href")` é resolvido com
`urljoin(page.url, href)` antes de comparar contra a URL base — o atributo
cru do HTML pode vir relativo, e o `.href` (propriedade JS resolvida) não
é o que `get_attribute` devolve.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P31

Filtro de editais de abertura no crawler: casar sempre com fronteira de palavra
`\bABERTURA\b` (`re.search(r'EDITAL.*?\bABERTURA\b', text)`), impedindo que editais
administrativos de retificação com palavras como "reabertura" sejam classificados
como editais de abertura.

ADRs: nenhuma

Teste guarda: sem teste guarda

### edital

#### P12

Cabeçalho de matéria/cargo em edital sempre casado com um padrão que
aceita dígitos, vírgula e parênteses no meio (`[A-ZÀ-Ú0-9 /,()\-]`), não
só letras/espaço/hífen — títulos reais como `CARGO 7: MÉDICO CLÍNICO` e
`ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO:` têm esses
caracteres.

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestPadroes::test_padrao_materia_casa_nomes_com_digito_virgula_parenteses`

#### P13

Chunking de edital sempre nos dois níveis (cargo E matéria), nunca só um —
cargos de especialidade (ex: áreas médicas) não têm matéria nomeada à
parte, o conteúdo vem direto embaixo do cabeçalho `CARGO N: <nome>`.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P14

Checagem de layout multi-coluna (`checar_ordem_confiavel`) só considera
blocos de texto com tamanho mínimo (`TAMANHO_MINIMO_BLOCO_COLUNA`) — um
bloco curto isolado (título, assinatura) tem x0 diferente da margem do
corpo sem indicar colunas paralelas de conteúdo.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P19

Todo chunk carrega `tipo_conhecimento`/`nivel` herdados do cabeçalho de
bloco `CONHECIMENTOS BÁSICOS/ESPECÍFICOS PARA ... NÍVEL SUPERIOR/MÉDIO`
(`PADRAO_BLOCO`), além de `cargo_numero`, `materia_normalizada` e
`apenas_discursiva` (lista única em `CAMPOS_CLASSIFICACAO_CHUNK`). O
concurso (`slug`/`orgao`/`ano`) vem do manifesto do downloader
(`resolver_concurso_do_pdf`), não do path em disco (a pasta é por órgão).
Esses campos vêm só do parser/manifesto, então extração antiga é
completada com `scripts/backfill_classificacao_chunks.py` sem chamar o
LLM (ADR-020).

ADRs: [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md)

Teste guarda: sem teste guarda

#### P23

Normalização de whitespace no PyMuPDF: substituir sempre espaços não-separáveis
(`\xa0`) por espaço ASCII (`" "`) logo na extração de texto das páginas (`extrair_texto_paginas`
e detecção de cargo preliminar). PDFs do CEBRASPE contêm `\xa0` nos cabeçalhos
de seções e blocos, o que faz buscas literais e regexes falharem silenciosamente.

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestExtrairSecaoObjetosAvaliacaoDetalhada::test_extrair_secao_com_espacos_nao_separaveis`

#### P24

Títulos de cargos multi-linha sem itens no parser: quando um cabeçalho de cargo
quebra linhas no layout do PDF e o bloco subsequente não contém itens
numerados (`extrair_itens_numerados`), o texto deve ser acumulado ao rótulo do
cargo (`f"{cargo_atual} {texto_bloco}"`), evitando criar chunks vazios sem matéria.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P25

Variações de blocos de matérias: mapear `CONHECIMENTOS GERAIS` para tipo básico
(`"basico"`) e aceitar prefixação numérica de itens no edital (`PADRAO_BLOCO`
com `(?:\d+(?:\.\d+)*\s+)?`).

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestPadroes::test_padrao_bloco_com_prefixo_numerico`

#### P26

Colons parentéticos em matérias: cabeçalhos com restrição entre parênteses
(ex.: `LÍNGUA INGLESA (APENAS PARA O CARGO 3: ...):`) exigem regex que capture
o parêntese fechado antes do colon delimitador (`(?:\s*\([^)]*\))?:`), impedindo
que o colon interno trunque o nome da matéria.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P27

Detecção determinística de cargo e nível único: editais com cargo único (ex.:
`TCU_25_TEFC`) não repetem cargos nem declaração de nível na seção de Objetos
de Avaliação; inspecionar as páginas preliminares (`DO CARGO DE...` e `REQUISITOS:`)
para injetar `cargo_padrao` e `nivel_padrao` automaticamente no chunking.

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestBlocosDeConhecimento::test_cargo_padrao_e_nivel_padrao_em_bloco_sem_declaracao_explicita`

#### P29

Cabeçalhos de matérias multi-linha em editais: `PADRAO_MATERIA` só aceita quebras
de linha se a linha anterior terminar com conectivos (`E|OU|DE|DA|DO|DOS|DAS` ou vírgula),
evitando incorporar indevidamente títulos de cargo em layouts multi-linha como matérias falsas.

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestPadroes::test_padrao_materia_nao_casa_linha_de_cargo`

#### P30

Matérias sem dois-pontos delimitadores antes do item 1: quando um bloco sob cabeçalho
de cargo contém itens numerados imediatos mas possui um prefixo em caixa alta antes do primeiro
item (ex: `NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO ... 1`), o prefixo é
extraído como nome da matéria e o corpo do chunk inicia a partir do item 1, evitando que a
matéria receba o nome do cargo ou perca seu conteúdo.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P34

Assinatura do fim da seção (nome + cargo do signatário) é removida em
`_limpar_ruido_edital` ancorando no **cargo** (`PADRAO_CARGO_ASSINATURA`)
no fim do texto, nunca no nome em caixa alta.

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestRemoverAssinaturaFinal::test_limpar_ruido_tambem_remove_assinatura`

#### P39

Restrição de cargo no nome da matéria (`(APENAS/SOMENTE PARA O(S)
CARGO(S) ...)`, `PADRAO_RESTRICAO_CARGO`) sai de `materia_normalizada` e
vira `cargos_restritos: list[int] | None`. Só sai do nome quando tem número
de cargo; sem número (`PARA OS CARGOS DE NÍVEL SUPERIOR`), fica no nome e
loga `[RESTRICAO_SEM_CARGO]`. Espaços repetidos são colapsados. Ver ADR-028.

ADRs: [ADR-028](../adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md)

Teste guarda: `tests/test_edital_parser.py::TestPadroes::test_padrao_restricao_cargo`, `tests/test_edital_parser.py::TestBlocosDeConhecimento::test_dividir_avisa_restricao_sem_numero`

#### P64

Cobertura descendente edital × prova (`vw_edital_vs_prova`): item de edital em nó X cobre X e todos os descendentes de X. Na prova, o apontamento sobe; na comparação, checa se há ancestral-ou-igual previsto no edital daquele cargo (`cobrado_no_edital`, `no_edital_nunca_cobrado`, `cobrado_fora_do_edital`).

ADRs: nenhuma

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_edital_vs_prova_situacoes_e_cobertura_descendente`

#### P75

O subtópico reinjetado de um subitem de 3º nível em diante grava o **texto próprio** como
nome (`Topico.subtopicos`) e os ancestrais de 2º nível para baixo em `Topico.caminho_origem`
(`{"Design thinking": ["Metodologias ágeis..."]}`), nunca a cadeia "Pai - Filho" (KAN-93).
`caminho_origem` é só contexto: fica fora de `chave_item`, do banco e do casamento; o
relatório e o Datasette o mostram. É opcional e omitido do JSON quando vazio, então o
JSON antigo carrega sem mudança. Nome que já é irmão no tópico não colide em silêncio: a
reinjeção grava a cadeia (única) sem `caminho_origem`, e a migração deixa o nome em cadeia.
`migrar_cadeias_para_texto_proprio` só converte o que é, palavra por palavra, a cadeia de um
subitem numerado do texto-fonte (um " - " do próprio nome nunca casa) e roda dentro de
`scripts.reconciliar_taxonomia`. Depois de reconciliar, `scripts.migrar_chaves_cadeia`
(dry-run por padrão) leva os mapeamentos da chave antiga à nova por `src/arvore.py`; conflito
de nós nunca é decidido pelo script.

ADRs: [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md), [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestCadeiaVirandoTextoProprio`, `tests/test_migrar_chaves_cadeia.py`

#### P76

A forma das listas é consertada por `normalizar_listas_e_facetas` (KAN-94, M8), sem LLM,
dentro do pós-LLM do extrator e de `scripts.reconciliar_taxonomia`: (1) tópico com ";" fora de
parênteses e **sem subtópicos** vira subtópicos, um por elemento, sem ponto final; se o 1º
elemento é "Cabeça: resto" a cabeça vira o nome do tópico; senão o **1º elemento vira o nome** e
os demais subtópicos (a chave muda, e o nome antigo vai em `Topico.nome_origem`), salvo quando todos
os elementos abrem com a mesma palavra ("Lei nº…; Lei nº…") ou o 1º passa de `TAMANHO_FRASE_LONGA`,
casos em que o nome fica inteiro e todos viram subtópicos; elemento que abre com "e"/"ou"/"com" ou
sem palavra de 3+ letras ("70 a 75"), elementos repetidos ou cabeça que colide com outro tópico do
chunk impedem a divisão (";" final e pedaço vazio são descartados antes de validar); vírgula e
"e" nunca dividem; (2) facetas voltam ao pai (`Topico.subtopicos_absorvidos`) só em dois casos:
todos os subtópicos são uma palavra minúscula que está no nome do pai ("Modelagem de dados:
físico, lógico e conceitual"), ou o pai tem sigla entre parênteses e pelo menos 3 subtópicos
são `FACETAS_GENERICAS` (BSC); **nunca** por contar palavras: "jQuery", "keycloak", "estados" e
"Backup" são assuntos, e subitem numerado da fonte também nunca é absorvido; (3) o ponto final sai
(a chave já ignora pontuação). O validador só avisa (informativo): `topico_lista_nao_dividida`,
`subtopico_faceta_solta` e `topico_frase_longa` (> `TAMANHO_FRASE_LONGA`). Depois de reconciliar,
`scripts.migrar_chaves_cadeia` leva a chave do tópico que mudou e remove só a herança
`regra` redundante da faceta; o que for humano ou de nó diferente fica e é relatado como órfão.

ADRs: [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md), [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestFormaDeListasEFacetas`, `tests/test_validar_taxonomia.py::TestAlertasDeForma`, `tests/test_migrar_chaves_cadeia.py`, `tests/test_reconciliar_taxonomia.py`

### prova

#### P36

A fila `fila_extracao_questoes` usa upsert por `sha256` e o writer nunca
altera `status`, que pertence ao consumidor.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P37

Tipo/cargos de caderno vêm de `classificar_prova_por_texto` sobre o texto
do link já normalizado. Aceita `CONHECIMENTOS GERAIS` (CG) como básico, e
texto sem cargo significa "todos os cargos do concurso" (TCU). Edital
administrativo em `Provas/` fica fora da fila, com log.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P40

Número de cargo em texto (link de caderno ou restrição de matéria) vem só
de `comparacao_texto.extrair_cargos_do_texto`, usada pelo parser e pelo
writer.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P55

Segmentação de cadernos de prova: número do item distinguido por x0 na margem da coluna (cluster/moda); duplicado/fora de ordem é bloqueante; recuo de continuação de item medido na faixa estrita de 12 a 24 pt (~18 pt real); gabaritos definitivos em hash (TCU/Câmara) ligados aos cadernos pelo código impresso no corpo do PDF (ADR-031).

ADRs: [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

Teste guarda: sem teste guarda

#### P56

Assinatura de grupo por hash na fila (`fila_extracao_questoes.assinatura_grupo`) garante reprocessamento automático quando os gabaritos ligados mudam, em qualquer status; `--reprocessar-erros` cobre órfãos e falhas.

ADRs: nenhuma

Teste guarda: `tests/test_extrair_questoes.py::TestConsumidorPostgres::test_caderno_concluido_com_gabarito_alterado_e_reprocessado`

#### P58

Versão do gabarito (`definitivo` × `preliminar`) classificada exclusivamente pelo cabeçalho (ou prefixo do nome de arquivo), com preferência determinística pelo definitivo e alertas informativos (`mais_de_um_gabarito` / `gabarito_preliminar`).

ADRs: nenhuma

Teste guarda: `tests/test_extrair_questoes.py::TestConsumidorPostgres::test_dois_gabaritos_preliminar_e_definitivo`

#### P59

Caderno discursivo: quesitos extraídos estritamente a partir do comando (`redija`, `elabore`, `aborde`, `discorra`), evitando confusão com datas; tema anafórico rejeitado para `None` com alerta `tema_anaforico`.

ADRs: nenhuma

Teste guarda: `tests/test_prova_parser.py::TestCadernoDiscursivo::test_tema_anaforico_gera_alerta`

#### P60

Padrão de resposta ligado preferencialmente por chave de título (`_chave_titulo`), garantindo ordem semântica correta mesmo com seções fora de ordem no PDF (chave ausente ou repetida cai na ligação por ordem); alertas `sem_quesitos` e `quesito_sem_valor`.

ADRs: nenhuma

Teste guarda: `tests/test_prova_parser.py::TestCadernoDiscursivo::test_chave_titulo`

#### P61

Figuras: vinculadas à linha logo acima na mesma coluna com sobreposição horizontal (exceção item → preâmbulo).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P62

JSONs brutos de questões (`questoes/`) mantidos localmente e no `.gitignore` por volumetria, sendo regeneráveis de forma determinística por `scripts/extrair_questoes.py` (ADR-031).

ADRs: [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

Teste guarda: sem teste guarda

### llm

#### P04

Toda chamada LLM é feita diretamente à API REST do OpenRouter (`z-ai/glm-5.3-flash`),
pelo núcleo `src/llm_openrouter.chamar_llm_json` (status tipados, Langfuse,
gancho `pos_validacao`). Uso novo não monta payload próprio.

ADRs: nenhuma

Teste guarda: `tests/test_taxonomia_extractor.py::TestOpenRouterDirect::test_requisicao_vai_para_openrouter`

#### P15

Chamada ao modelo de raciocínio (`glm-5.3-flash`) sempre com
`max_tokens` generoso — um orçamento baixo é consumido pelo `reasoning_content`
antes do `content` final, que volta `null` mesmo sem erro de rede.

ADRs: nenhuma

Teste guarda: `tests/test_taxonomia_extractor.py::TestParametrosConfiguraveis::test_reasoning_padrao_e_max_tokens_12000`

#### P16

Toda chamada LLM com reasoning limitado a 3000 tokens via `REASONING_PADRAO`
do `src/llm_openrouter.py` (fonte única: default de `chamar_llm_json`,
reexportado pelo extrator de taxonomia e usado no payload do bot do
Telegram). Decisão do dono em 2026-09-25. Defaults atuais do extrator:
`MAX_TOKENS=12000`, `REQUEST_TIMEOUT=120`, reasoning 3000 — vieram do merge
`b823c31` e substituíram os `24576`/`240` registrados na decisão de
2026-09-20 (ADR-016), que ficam só como histórico.

ADRs: [ADR-016](../adr/ADR-016-retry-maiores-tokens-llm.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestReasoningPadraoUnico::test_nucleo_envia_reasoning_3000_por_padrao`, `tests/test_taxonomia_extractor.py::TestReasoningPadraoUnico::test_extrator_usa_a_constante_do_nucleo`

#### P17

Chaves do OpenRouter são dedicadas por etapa (`llm_openrouter.ETAPA_*` +
`chave_openrouter`): `OPENROUTER_KEY_TAXONOMIA_EDITAL`, `_SINONIMOS`,
`_CURADORIA_ARVORE`, `_MAPEAMENTO_ITENS` (cai na da curadoria),
`_CLASSIFICACAO_QUESTOES` e `_TELEGRAM`. O nome da chave
no OpenRouter é igual ao nome do trace no Langfuse
(`cebraspe-<etapa>-<função>`). Chave vazia cai na `OPENROUTER_API_KEY`
com aviso `[CHAVE_FALLBACK]` no log.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P20

Falha *semântica* do LLM (resposta estruturalmente válida mas com
conteúdo errado — ex: `nome` de tópico igual ao numeral do item da
fonte) é corrigida por reparo local determinístico quando o dado pra
corrigir já está disponível (texto-fonte), nunca por repetir a mesma
chamada ao LLM torcendo por sorte — sem contexto do erro, uma repetição
não tem garantia de corrigir e não deixa rastro distinto de um retry por
falha de rede. Ver ADR-021.

ADRs: [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestReparoNomeTopicoNumerico::test_nome_numerico_e_reparado_com_texto_do_item_fonte_sem_nova_chamada`

#### P21

Toda falha na chamada ao OpenRouter (`_chamar_llm_uma_vez`) devolve um
status técnico específico (`falha_timeout`, `falha_conexao`,
`falha_rate_limit`, `falha_http`, `falha_rede`, `falha_conteudo_vazio`,
`falha_parse_json`, `falha_validacao_schema`), nunca um `motivo_falha`
genérico — persistido no `status` do chunk e replicado em
`metadata["tipo_erro"]` no Langfuse, pra distinguir falha transitória
(timeout/conexão/rate-limit, retry tende a resolver) de falha que se
repete com os mesmos parâmetros (conteúdo vazio/parse/schema, retry
sozinho não ajuda). Ver ADR-022.

ADRs: [ADR-022](../adr/ADR-022-classificacao-erros-chamada-openrouter.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestClassificacaoDeErros::test_cada_tipo_de_falha_fica_rastreavel_no_metadata_langfuse_como_tipo_erro`, `tests/test_taxonomia_extractor.py::TestClassificacaoDeErros::test_todos_os_status_de_falha_sao_distintos_entre_si`

#### P22

Telemetria de observabilidade exclusivamente via SDK oficial `langfuse` (OTel),
com observation (`generation`) aberta imediatamente antes da chamada HTTP para
medição precisa da latência real de rede/inferência. Ver ADR-023.

ADRs: [ADR-023](../adr/ADR-023-migracao-langfuse-sdk-oficial.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestLangfuseSdk::test_registra_falha_na_generation_e_trace`

#### P32

Item de primeiro nível omitido pelo LLM é reinjetado localmente a partir
do texto-fonte (`reinjetar_itens_ausentes`, logo depois do reparo de nome
numérico), sem nova chamada ao LLM, e só quando o item é simples (sem
subitens `N.1`, ≤ 150 chars). Item complexo continua `topico_ausente`
para revisão humana. Ver ADR-025.

ADRs: [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestReinjetarItensAusentes::test_item_omitido_e_reinjetado_na_posicao_da_fonte`, `tests/test_taxonomia_extractor.py::TestReinjetarItensAusentes::test_item_com_subitens_nao_e_reinjetado`

#### P42

O backfill confere o alinhamento pelo texto: o texto atual do chunk tem de
ser prefixo do `texto_enviado_llm` salvo (a assinatura final foi removida
depois, ADR-025), além de matéria/cargo.

ADRs: [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)

Teste guarda: sem teste guarda

#### P45

`scripts/propor_sinonimos.py` custa tokens e **não** roda no pipeline
automático. Blocos já avaliados ficam em `avaliados_llm` e não são
reenviados.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P46

Resposta de LLM sobre lista fechada é validada localmente (cada ID em
exatamente um grupo, nada inventado, nada entre blocos) com falha tipada; a
segunda tentativa leva o erro no prompt.

ADRs: nenhuma

Teste guarda: sem teste guarda

### banco

#### P05

Banco próprio, sem FK entre projetos: dimensões carregam chave natural
normalizada (`slug`, `materia_normalizada`, tópico normalizado) para o
cruzamento futuro com `itens_estudo` via tabela de mapeamento (ADR-026).

ADRs: [ADR-026](../adr/ADR-026-banco-postgres-proprio.md)

Teste guarda: sem teste guarda

#### P35

Fatos de um concurso (`taxonomia_itens`, `provas`) são substituídos
numa transação a cada carga; dimensões usam upsert por chave natural
(`comparacao_texto.normalizar`). Cargos usam upsert em `(concurso, numero)`
porque `provas_cargos` aponta para eles. Ver ADR-027.

ADRs: [ADR-027](../adr/ADR-027-star-schema-estatisticas.md)

Teste guarda: sem teste guarda

#### P38

Estatística "oficial" só em view que filtra `status_revisao = 'aprovado'`
(`vw_incidencia_topico`, `vw_edital_cobra_*`); a variante `_todas` é para
inspeção.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P47

Subtópico é linha (`dim_subtopico` + `taxonomia_subitens`), não JSONB.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P53

A carga (`stats_writer.aplicar_arvore`) grava **todos** os nós com o status
(as pontes nunca ficam sem FK) e as pontes só com apontamento `aprovado`,
já resolvido. `vw_no_caminho` só expõe a cadeia `ativa` (nó proposto não
conta antes da aprovação) e dá o `no_efetivo` do fundido. `dim_materia.nocoes`
vem de `chave_regra(nome).nocoes`, com ou sem mapeamento.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P54

Estatística "edital cobra": ocorrência = `taxonomia_itens.id` distinto,
com o item básico expandido por cargo (`cargos_restritos` respeitado).
"Prova cobra": questão distinta. O mesmo item nunca conta 2× no mesmo nó.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P57

Advisory lock de sessão (`pg_try_advisory_lock(5_031_001)`) garante consumidor de execução única sem concorrência destrutiva na fila.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P63

Estatística de prova sobe a árvore e conta questão distinta (`count(DISTINCT questao_canonica_id)`): questão em subassunto soma em subassunto, assunto e matéria; questão em assunto soma em assunto e matéria, nunca descendo. Leitura com filtros agregados no site é feita via `fn_prova_cobra(...)` para garantir cálculo de percentual médio sob os filtros e desduplicação correta de questões básicas aplicadas em múltiplos cargos (ADR-032). Percentual entre provas é média em dois níveis: % do nó na prova distinta → média das provas distintas do concurso → média entre concursos, cada edital com peso 1. Prova distinta: cargos com o mesmo conjunto de questões canônicas no escopo, sob os filtros, contam 1× (assinatura `md5` + cargo representante). Nunca soma bruta nem média direta por cargo, que multiplica o básico (ou o específico) compartilhado pelo número de cargos (ADR-039, 8.M.1).

ADRs: [ADR-032](../adr/ADR-032-classificacao-questoes-arvore.md), [ADR-039](../adr/ADR-039-incidencia-em-dois-niveis.md)

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_fn_prova_cobra_conta_distinto_com_filtro_de_varios_cargos`, `tests/test_estatisticas_views.py::TestEstatisticasViews::test_fn_prova_cobra_pct_do_universo_e_media_por_prova`

#### P65

Peso por matéria em cargo (`vw_peso_materia_cargo`): proporção de cada matéria dentro do total da prova do cargo (básico + específico); matérias identificadas como nome de cargo (`nome_de_cargo = true`) são formatadas como `"Conhecimentos específicos — <cargo>"`.

ADRs: nenhuma

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_peso_materia_cargo`, `tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_peso_materia_cargo_rotulo_nome_de_cargo`

#### P66

Discursivas analíticas (`vw_discursivas`): isola estritamente os temas e quesitos das 64 discursivas associadas aos nós da árvore mestre, sem interferir nem computar nas contagens das views de questões objetivas.

ADRs: nenhuma

Teste guarda: `tests/test_estatisticas_views.py`

### arvore

#### P48

Árvore mestre (ADR-030): o pai pertence ao **nó**, não ao edital. Item de
edital e questão **apontam** para nós (N:N, qualquer nível), e a
estatística soma subindo a árvore. O nome composto aponta para N nós, e o
item de uma matéria composta aponta para o nó da matéria certa.

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: sem teste guarda

#### P49

O ID de nó é estável. O nó semeado herda o ID do grupo aprovado da 5B.
Fundir marca `fundido` + `fundido_em` e nunca apaga ID; toda leitura
resolve o redirecionamento.

ADRs: nenhuma

Teste guarda: `tests/test_curar_arvore.py::test_criar_renomear_mover_fundir_desmapear`

#### P50

`canonico/arvore.json` só é lido e escrito por `src/arvore.py`
(`carregar`/`salvar`, uma linha por registro, ordenado por ID). A chave do
item é a chave natural do banco unida por `|` (`arvore.chave_item`), e o
apontamento é `{no_id, origem, status}`.

ADRs: nenhuma

Teste guarda: `tests/test_arvore.py::test_chave_item`

#### P51

Decisão do dono na árvore só via `scripts/curar_arvore.py` (ou as funções
de `src/arvore.py`): `--mapear`, `--desmapear`, `--aprovar`, `--rejeitar`,
`--fundir`, `--mover`, `--criar`, `--renomear`. Operação humana sai
`aprovado`/`ativo`; mapear de novo um apontamento proposto o aprova. Erro de
validação não grava nada.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: `tests/test_curar_arvore.py::test_criar_renomear_mover_fundir_desmapear`

#### P52

Item novo de edital (pipeline, `atualizar_revisao.atualizar_arvore`):
`canonico.mapear_novos_itens_por_regra` copia os nós de um item aprovado com
a mesma `chave_regra` **no mesmo nó-pai efetivo** (título genérico só do mesmo edital, P78); sem candidato, tenta a memória das
decisões do dono (P73); sem candidato, assunto ou subassunto com pai mapeado vai para o
**filho único** (KAN-97): entre os filhos ativos (não propostos) dos nós do pai, juntos,
exatamente 1 tem a mesma `chave_regra` e nível compatível (assunto: assunto ou subassunto;
subassunto: subassunto); dois filhos iguais, mesmo sob pais diferentes do conjunto, são
ambíguos. Entra como `regra`/`aprovado` e conta em `por_filho`; título genérico e par
vetado pelo dono nunca casam, e o item de matéria (sem pai) não passa por aqui. Sem
candidato ainda, o subtópico herda o nó do tópico-pai quando ele é
folha (KAN-85): o pai tem exatamente 1 nó aprovado, ativo, de nível subassunto e sem
filho ativo, o nome não é título genérico e o par (chave de regra, nó) não foi vetado
pelo dono; entra como `regra`/`aprovado` e conta em `por_heranca`. Regra ambígua ou pai
sem nó fica pendente no `arvore.html`. **Pai provisório (KAN-86)**: assunto ou subassunto
cujo título de bloco não tem nó usa como pai a disciplina que o **cargo** do chunk nomeia
(`canonico.disciplina_do_cargo`: todas as palavras relevantes da disciplina de
`canonico/disciplinas.json` estão no nome do cargo, e exatamente 1 casa), só em chunk
`especifico` de cargo; chunk básico, cargo sem disciplina, 2 disciplinas ou cargos que
inferem disciplinas diferentes não inferem nada, e o bloco recua se já tem item aprovado em
outra disciplina. O título continua sem mapeamento. O que o pai provisório resolve (regra de
nome, decisão aprovada da memória, ou o único nó ativo de mesma `chave_regra` e nível
compatível na **subárvore** da disciplina) entra como `regra`/`aprovado` com as travas de
`canonico.no_do_pai_provisorio`: candidato único, par não vetado pelo dono, nome fora de
`TITULOS_GENERICOS`; o apelido de nó fundido não vale aqui, porque sem o pai real o nome solto
perde o contexto da fusão. `ResultadoRegra` traz `comparados`, `com_pai_provisorio` e
`por_pai_provisorio`. Depois do filho único e da herança (e do pai provisório), o último ramo
é o **casamento global por nome** (KAN-87, P77), que conta em `por_global`.
O log traz a contagem por regra de nome, por memória, por filho único, por herança de folha e pendentes. A `chave_regra` ignora os
prefixos "noções de", "fundamentos de" e "conceitos (básicos|gerais) de" (só "noções" liga
`nocoes`) e unifica gestão e gerenciamento; administração não entra, e a sigla entre
parênteses é só o campo `ChaveRegra.sigla`, nunca a chave (KAN-84). O mapeamento
`regra`/`aprovado` só atravessa disciplina com disciplina compatível ou nome específico:
título genérico (`canonico.TITULOS_GENERICOS`) nunca casa sozinho por nome (KAN-82).

ADRs: nenhuma

Teste guarda: `tests/test_regra_arvore.py::test_mapeia_dentro_do_mesmo_pai_efetivo`, `tests/test_regra_arvore.py::test_nao_mapeia_sob_outro_pai`, `tests/test_regra_arvore.py::test_regra_ambigua_fica_pendente`, `tests/test_canonico.py::TestChaveRegraPrefixosESinonimos`, `tests/test_regra_arvore.py::test_filho_unico_resolve_os_casos_do_sefa`, `tests/test_regra_arvore.py::test_filho_resolve_pela_disciplina_inferida_sem_gravar_o_titulo`, `tests/test_regra_arvore.py::test_cargo_de_ti_infere_ti`, `tests/test_regra_arvore.py::test_chunk_basico_ou_sem_cargo_nao_infere`, `tests/test_regra_arvore.py::test_banrisul_ganha_mais_de_100_itens_comparados`, `tests/test_regra_arvore.py::test_contratos_de_ti_casam_em_direito_administrativo`

#### P72

O nível matéria da árvore é a disciplina e só aceita os nomes de
`canonico/disciplinas.json`. Título de bloco de edital fora da lista vira **assunto**:
`mapear_novos_itens_por_regra` aponta o item para o único nó de disciplina ou assunto de mesmo
nome, e sem equivalente ele fica pendente para a curadoria. Esse casamento por nome só vale se
o nó é a própria disciplina, está numa disciplina inferida dos itens do bloco já aprovados,
ou o nome tem 2+ palavras relevantes e não é título genérico (`canonico.titulo_generico_global`:
`TITULOS_GENERICOS` mais os genéricos de subitem do KAN-87, como "Aplicações", "Definição", "Tipos",
"Procedimento" e "Instalação, configuração e administração", e o rótulo feito só de
`PALAVRAS_GENERICAS`, como "Conceitos básicos e aplicações"; ver P77);
par vetado pelo dono (por `chave_regra`) nunca é regravado, e fora disso o item fica pendente,
nunca `aprovado` (KAN-82). Proposta de LLM ou de regra
nunca cria disciplina (`propor` recusa `criar` de matéria); disciplina nova só por decisão
do dono. O ramo do filho único (KAN-97, P52) é só de assunto e subassunto, que têm pai: o
título de bloco (matéria) continua neste ramo de nome e nunca passa por lá. A disciplina
inferida pelo **cargo** (P52, KAN-86) é só pai provisório dos filhos: nunca é gravada para o
título, que continua sem mapeamento, e jamais cria disciplina.
`scripts/auditar_arvore.py` fica verde antes de cada carga.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_regra_arvore.py::test_titulo_de_bloco_fora_da_lista_vira_assunto`, `tests/test_regra_arvore.py::test_proposta_automatica_nao_cria_disciplina`, `tests/test_regra_arvore.py::test_titulo_generico_nao_casa_com_assunto_de_outra_disciplina`, `tests/test_regra_arvore.py::test_ramo_de_titulo_respeita_veto_de_outra_chave_com_mesma_chave_regra`

#### P73

O mapeamento de item novo aprende com o dono (`src/memoria_mapeamento.py`,
funções puras sobre a árvore) e a memória é parte do **passo determinístico**
(`canonico.mapear_novos_itens_por_regra`, rodado a cada extração, sem LLM). Ordem, nível a
nível (o assunto mapeado agora serve de pai do subassunto): (1) regra de nome; (2) memória:
item de mesma `chave_regra` e mesmo pai efetivo de uma decisão **aprovada**, ou apelido
exato de nó **fundido** (só nó fundido gera apelido, apontando ao destino ativo; nó ativo
nunca) na disciplina do pai, com candidato único, vira `regra`/`aprovado`; ambiguidade
fica pendente; (3) filho único (KAN-97), só assunto e subassunto com pai mapeado: o item vai
para o único filho ativo de mesma `chave_regra` e nível compatível entre os filhos dos nós do
pai (`por_filho`, `regra`/`aprovado`), salvo ambiguidade, título genérico ou par vetado;
(3b) sem nó no título de bloco, o filho usa a disciplina inferida pelo cargo como pai
provisório (P52, KAN-86), com candidato único na subárvore, sem veto e fora dos títulos
genéricos, e sem apelido de nó fundido; (4) herança de folha, só para subtópico: aponta para o nó único do
tópico-pai se ele é subassunto ativo sem filhos, salvo título genérico ou par vetado
(KAN-85, `regra`/`aprovado`); (5) casamento global por nome (KAN-87, P77); nunca cria nó (P72).
Nos passos (1) e (2), título genérico só herda decisão do mesmo edital (KAN-88, P78). Só então o LLM (`mapear_itens_novos`, que antes
reexecuta o passo determinístico, P80) recebe contexto de subitens extraído do `<edital>.json`
(entra no hash do cache), exemplos aprovados do dono e os pares rejeitados. Proposta
`proposto` nunca é fonte da memória (só vira fonte depois que o dono a aprova), par
rejeitado nunca é devolvido nem reproposto, e a memória não muda status existente (A30).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md), [ADR-032](../adr/ADR-032-classificacao-questoes-arvore.md)

Teste guarda: `tests/test_memoria_mapeamento.py::test_proposta_nao_aprovada_nao_e_fonte`, `tests/test_mapeamento_llm.py::test_par_rejeitado_nao_e_reproposto_e_vai_no_prompt`, `tests/test_mapeamento_llm.py::test_memoria_resolve_item_repetido_entre_dois_editais`, `tests/test_regra_arvore.py::test_memoria_no_passo_deterministico`

#### P74

O relatório de revisão e a tabela `mapeamento_itens` do `revisao.db` leem a árvore já
passada pelo passo determinístico (`canonico.arvore_apos_passo`) e não têm critério de
equivalência próprio: só reportam como resolvido o que `mapear_novos_itens` mapeia (nome,
memória, filho único, herança de folha, pai provisório pelo cargo ou casamento global), e os pendentes do relatório são exatamente os do passo. `atualizar_revisao` roda `atualizar_arvore`
antes de `gerar_relatorios` e `gerar_db` (KAN-81). Seções, sugestão e agrupamento por cima disso são
só apresentação (P79).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_mapeamento_revisao.py::test_pendentes_do_relatorio_igual_aos_do_passo_nos_editais_reais`

#### P77

**Casamento global por nome** (KAN-87, M6, `canonico.no_global_por_nome`): último ramo do passo
determinístico (P52, P73), depois do filho único, da herança de folha e do pai provisório, e
antes de marcar pendente. Só para assunto e subassunto; com pai mapeado (ou disciplina inferida
pelo cargo), o item de nome idêntico (`chave_regra`) a um nó ativo de nível compatível em **qualquer**
parte da árvore vai para ele como `regra`/`aprovado` (`por_global`; `chaves_global_fora_disciplina`
guarda os que atravessaram disciplina). Segue D3: um conceito, um nó, então o subitem jurídico de
um bloco de TI vai para o nó que já existe em Direito Administrativo. Travas: (1) o candidato é
único (dois nós iguais, inclusive norma repetida, deixam o item pendente); (2) **exceção de TI**:
se há nó equivalente na disciplina do pai (ou inferida pelo cargo), ele vale e os de fora são
ignorados, e dois equivalentes ali são ambíguos; (3) para atravessar disciplina o nome precisa
de 3+ palavras relevantes (`PALAVRAS_MIN_ENTRE_DISCIPLINAS`) ou ser **norma** (lei, decreto,
"Lei nº X/ano", `nos_da_mesma_norma`, KAN-64: a norma vive em um nó só); nome curto só casa
dentro da disciplina; (4) título genérico nunca casa (`titulo_generico_global`). **Duas listas**
(decisão D3 do dono, 2026-11-06): onde o pai direto não dá contexto (este ramo, os candidatos globais
do LLM, o título de bloco de P72 e a subárvore da disciplina inferida de P52) vale a lista ampliada,
`TITULOS_GENERICOS_GLOBAL` mais rótulo feito só de `PALAVRAS_GENERICAS`; nos ramos que olham o pai
direto (filho único, herança, regra de nome e memória, P78) vale só `TITULOS_GENERICOS`, e
"Licitação › Tipos" casa com o filho "Tipos" do nó de Licitação; (5) par vetado pelo dono não casa; (6) apelido de nó fundido entra como candidato,
exceto com pai provisório (P52); (7) nunca cria nó nem disciplina (D5, P72). Item composto ("A e B")
não é dividido aqui: se a `chave_regra` do nome inteiro não é a de um nó, o item fica para o LLM ou
o dono, que podem apontar até 3 nós (a árvore é N:N, P80). **Subtópico e assunto de mesmo nome**
(KAN-102, M16, `canonico.nivel_aceito_por_nome`): o subtópico só aponta para subassunto, salvo o
assunto cuja `chave_regra` é igual à dele (o mesmo conceito guardado um nível acima), com as mesmas
travas; o subassunto de mesmo nome, se houver, vale primeiro, e o resultado fica o de antes do M16.
Vale só aqui e na subárvore da disciplina inferida (P52); filho único e herança não mudam. **Pai sem nó** (decisão D2 do dono,
2026-11-06): o item cujo pai não tem nó aprovado nem disciplina inferida passa só por este ramo, sem
disciplina de contexto (valem as travas 1, 3 a 6) e grava `regra`/**`proposto`**, nunca `aprovado`
(`propostos_sem_pai`, fora de `total`): sem o pai, o nome solto pode casar errado (o "Normas
Brasileiras de Contabilidade" de um bloco de setor público ia, por apelido, para a Estrutura
Conceitual). O dono confere na revisão guiada; proposta rejeitada fica na chave e não volta. Lote
novo roda K22 a K24 antes e depois (P71).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_regra_arvore.py::test_contratos_de_ti_casam_em_direito_administrativo`, `tests/test_regra_arvore.py::test_lgpd_casa_global_por_norma`, `tests/test_regra_arvore.py::test_nome_curto_nao_atravessa_disciplina`, `tests/test_regra_arvore.py::test_generico_nunca_casa_global`, `tests/test_regra_arvore.py::test_m16_subtopico_casa_com_assunto_de_mesmo_nome`, `tests/test_regra_arvore.py::test_m16_subassunto_de_mesmo_nome_vale_mais_que_o_assunto`, `tests/test_regra_arvore.py::test_candidato_duplicado_nao_casa`, `tests/test_regra_arvore.py::test_excecao_ti_prefere_o_equivalente_da_disciplina_do_pai`, `tests/test_regra_arvore.py::test_veto_do_dono_barra_o_global`, `tests/test_regra_arvore.py::test_economia_nao_casa_com_atualidades`, `tests/test_regra_arvore.py::test_pai_sem_no_casa_global_como_proposta`, `tests/test_regra_arvore.py::test_pai_sem_no_proposta_rejeitada_nao_volta`, `tests/test_regra_arvore.py::test_genericos_do_global_nao_travam_os_ramos_com_pai`, `tests/test_regra_arvore.py::test_tipos_casa_pelo_filho_unico_dentro_do_pai`

#### P78

**Título genérico não herda decisão de outro edital** (KAN-88, M11, D4 do dono): no passo
determinístico (P52, P73), o item cujo nome é `canonico.titulo_generico` (`TITULOS_GENERICOS`, a
lista dos ramos que olham o pai direto, em qualquer nível; ver P77) só herda, pelo ramo da regra de
nome e pelo da memória, a decisão de um item **do mesmo edital** (mesmo `slug` nas ocorrências de
`coletar_nomes`). Decisão de item de outro edital, ou de item que nenhum edital em disco traz
(origem desconhecida), e apelido de nó fundido não valem para ele
(`memoria_mapeamento.resolver_por_memoria(..., chaves_permitidas=...)`), nunca como `aprovado`. Se
nenhum outro ramo mapeia o item e a decisão de outro edital é única, ela é gravada como
`regra`/**`proposto`** (decisão D5 do dono, 2026-11-06; `propostos_generico`), que a revisão guiada
mostra como "proposto pela IA ou por regra" para o dono confirmar; o item sai da fila do LLM. Decisão
ambígua (dois nós) deixa o item pendente. Proposta rejeitada fica na chave e não volta.
`ResultadoRegra.barrados_generico` e `chaves_barradas_generico` contam todo item barrado. Filho único, herança de folha, pai
provisório e casamento global já barravam o genérico (P52, P77). Limite: a chave do item de
matéria é só `normalizar(título)`, então um título genérico igual em dois editais é **a mesma
chave** e o mesmo mapeamento (ex.: `legislacao`); isso não passa pelo passo e só se desfaz na
curadoria (`scripts/curar_arvore.py`) ou com título diferente no edital.

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_regra_arvore.py::test_titulo_generico_nao_herda_de_outro_edital`, `tests/test_regra_arvore.py::test_titulo_generico_herda_dentro_do_mesmo_edital`, `tests/test_regra_arvore.py::test_titulo_especifico_continua_herdando_de_outro_edital`, `tests/test_regra_arvore.py::test_titulo_generico_sem_origem_conhecida_nao_herda_pela_memoria`, `tests/test_regra_arvore.py::test_titulo_generico_barrado_e_idempotente`, `tests/test_regra_arvore.py::test_titulo_generico_proposta_rejeitada_nao_volta`, `tests/test_memoria_mapeamento.py::test_chaves_permitidas_filtra_a_decisao_pelo_item_de_origem`, `tests/test_memoria_mapeamento.py::test_chaves_permitidas_respeita_par_vetado`

#### P80

**Desenho do LLM de mapeamento** (`src/mapeamento_llm.py`, KAN-91, M9), sobre o resto que o passo
determinístico (P73, P77) não resolveu. Candidatos, sempre uma **lista fechada** de nós ativos:
(1) os nós da disciplina do pai, ou da inferida pelo cargo (P52, M4), que vem primeiro no prompt;
no título de bloco, as disciplinas, os assuntos dela e os subassuntos mais parecidos com o título e
os subitens; (2) a eles somam-se, por item, os até 4 melhores nós de **outras** disciplinas por
similaridade (palavras da `chave_regra`, peso idf, cobertura mínima do nome do nó), sem título
genérico (M6) e sem repetir conceito que a disciplina já tem (um conceito, um nó; D3); sem
disciplina, o ranking usa o nome, os subitens e os pais. **Alvo de título:** o título de bloco aceita
também subassunto (o nó natural de "Sistemas operacionais" é subassunto), sempre `proposto`, e
continua sem poder criar disciplina nem aprovar (P72, A30); o subtópico recebe também o nó de
assunto do tópico-pai como candidato, para a herança "sem nó mais específico, o subtópico aponta
para o nó do tópico" (M5, ensinada no prompt), e o assunto único de mesmo nome
(`assunto_de_mesmo_nome`, KAN-102, M16). Num lote de subtópicos, assunto fora desses dois
(`assuntos_permitidos`) recusa a resposta. **Até 3 nós** por item composto (`nos`; `no` único
continua aceito): o 4º, um nó e o descendente dele ou ID fora da lista recusam a resposta inteira
(`falha_validacao_schema`), e a gravação passa por `arvore.mapear` como `llm`/`proposto`. O hash do
cache do "nenhum" inclui o desenho (`DESENHO`) e a disciplina provisória quando é ela que restringe,
então mudar candidatos ou prompt reavalia o item. `REASONING_PADRAO` (P16) não muda. **Dry-run
com cascata** (KAN-90, M13): como no modo real a proposta de um nível é o pai do seguinte, o
`--dry-run` põe a sugestão top-1 do ranking (`sugestao_top1`, fora dos pares rejeitados) só na
árvore em memória, nunca salva; assim lotes, candidatos e custo previstos batem com a execução. O
resumo (`por_origem`) separa os ramos do passo determinístico, o LLM, sem candidato e o cache.

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md), [ADR-032](../adr/ADR-032-classificacao-questoes-arvore.md)

Teste guarda: `tests/test_mapeamento_llm.py::test_ranking_do_titulo_inclui_no_pelos_subitens`, `tests/test_mapeamento_llm.py::test_m16_assunto_de_mesmo_nome_entra_como_candidato`, `tests/test_mapeamento_llm.py::test_m16_pos_validacao_aceita_so_o_assunto_permitido`, `tests/test_mapeamento_llm.py::test_subassunto_e_alvo_valido_de_titulo_e_nunca_vira_aprovado`, `tests/test_mapeamento_llm.py::test_candidatos_globais_somados_sem_quebrar_a_lista_fechada`, `tests/test_mapeamento_llm.py::test_ate_3_nos_em_item_composto_e_o_4_e_recusado`, `tests/test_mapeamento_llm.py::test_validacao_de_nos_multiplos`, `tests/test_mapeamento_llm.py::test_prompt_ensina_heranca_e_varios_nos`, `tests/test_mapeamento_llm.py::test_cache_do_nenhum_invalida_com_a_disciplina_provisoria`, `tests/test_mapeamento_llm.py::test_reasoning_padrao_inalterado`, `tests/test_mapeamento_llm.py::test_dry_run_simula_a_cascata_sem_gravar`, `tests/test_mapeamento_llm.py::test_dry_run_preve_as_mesmas_chamadas_do_modo_real`

#### P79

A revisão do mapeamento é guiada por seções e sugestão, e **só apresenta** (KAN-89, M10):
`mapeamento_revisao.montar_revisao` agrupa os pendentes do passo (P74) em decisão de bloco (título sem
nó, com quantos itens destrava), com sugestão (score ≥ `LIMIAR_SUGESTAO`), realmente novo, travado pelo
pai (pai sem nó e sem disciplina inferida pelo cargo, M4) e herda do tópico (subitem sob nó-folha).
A sugestão é o top-3 por similaridade de palavras (IDF, sem LLM), restrito à subárvore do pai ou da
disciplina provisória; nó de outra disciplina só entra com o mesmo `chave_regra` ou sendo a mesma norma
(`nos_da_mesma_norma`); título genérico não recebe sugestão. Mesmo item em blocos ou cargos
diferentes vira um grupo (uma linha, lista de cargos). Cada sugestão traz a linha
`curar_arvore --mapear` para o dono copiar: o relatório e o `revisao.db` nunca aprovam nem
gravam (A27, A30), e a sugestão não decide equivalência, que continua só do passo. O Datasette
ganha as colunas `bloco`, `secao`, `sugestao_*`, `score`, `cargos`, `grupo`, `representante`,
`curar_arvore`, as visões `revisao_*` e `revisao_piloto/datasette/metadata.json` (consultas salvas,
fora do glob `*.json` dos editais).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_revisao_guiada.py::test_apresentacao_nao_muda_categoria_nem_pendentes_nem_arvore`, `tests/test_revisao_guiada.py::test_nome_parecido_de_outra_disciplina_nao_atravessa`, `tests/test_revisao_guiada.py::test_mesmo_item_em_dois_blocos_vira_um_grupo_com_os_dois_cargos`, `tests/test_revisao_guiada.py::test_gerar_db_acrescenta_colunas_visoes_e_metadata`

### classificacao

#### P28

Resiliência na validação de taxonomia contra PDFs:
1. Compor caracteres Unicode via `unicodedata.normalize("NFC", texto)` antes
   de remover pontuação (`[^\w]`), evitando que acentos combinantes decompostos
   (NFD) sejam descartados.
2. Substituir ligaduras tipográficas corrompidas de fontes do CEBRASPE
   (`MAPA_LIGATURAS_FONTES`: `Ɵ`→`ti`, `Ō`→`ft`, `ﬃ`→`ffi`, `ﬁ`→`fi`, etc.).
3. Validar cobertura de itens numerados contra tópicos OU subtópicos
   (`todos_extraidos`), reconhecendo quando o LLM subordina itens como subtópicos.
4. Permitir casamento por fronteira de palavras (`\b`) e igualdade exata para
   termos com 3 ou mais caracteres (ex.: "Crime", "Atos"), reservando o piso
   de 6 caracteres apenas para match de substring livre.
5. Só classificar tópico como `topico_extra` se ele não tiver correspondência
   nem estiver contido no texto integral normalizado do chunk (`texto_fonte_norm`).

ADRs: nenhuma

Teste guarda: `tests/test_validar_taxonomia.py::TestNormalizar::test_acento_combinante_decomposto_normaliza_igual_ao_precomposto`

#### P33

Alerta de validação tem severidade: paráfrase leve (qualificador entre
parênteses, erro de digitação da fonte corrigido pelo LLM, similaridade
≥ 0,92) vira `topico_divergencia_leve` `informativo`, visível mas fora de
`total_alertas`. Reparo e validador usam a mesma comparação textual
(`src/comparacao_texto.py`).

ADRs: nenhuma

Teste guarda: `tests/test_validar_taxonomia.py::TestSeveridadeDivergenciaLeve::test_qualificador_entre_parenteses_e_informativo`, `tests/test_validar_taxonomia.py::TestSeveridadeDivergenciaLeve::test_erro_de_digitacao_da_fonte_corrigido_pelo_llm_e_informativo`

#### P43

Sinônimo (Etapa 5B, ADR-029): regra determinística conservadora
(`canonico.chave_regra`: "noções de" → `nocoes`, artigo inicial, parêntese,
forma única de norma `lei 9784 1999`, plural simples) junta e aprova
sozinha; o resto vai ao LLM por lista fechada de IDs e escopo (matéria →
assunto dentro da matéria → subassunto dentro do assunto) e sai
`proposto`. Proposta nunca muda o mapeamento: até a aprovação, cada nome
fica no grupo aprovado de antes (identidade).

ADRs: [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md)

Teste guarda: `tests/test_canonico.py::TestChaveRegraJunta::test_mesma_chave`, `tests/test_canonico.py::TestChaveRegraJunta::test_forma_unica_de_norma`

### site

#### P67

O que fica fora do site é decidido só em `inventario/exclusoes.json` (slug, categoria
de `CATEGORIAS_EXCLUSAO`, motivo), lido por `inventario.carregar_exclusoes`. Concurso da
lista não é remapeado, não entra em amostra nem em lote e sai dos alertas. PDF de curso
de formação fica fora por `pdf_vai_para_o_site`. Alerta do inventário vem do texto do
link: antes de tratar como "sem arquivo", conferir a página ao vivo (ADR-037).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

Teste guarda: `tests/test_inventario.py::TestExclusoes::test_carregar_e_aplicar`

#### P69

Página nova em `docs/` entra no `nav` do `mkdocs.yml`; o `mkdocs build --strict` (no `make check`) recusa página fora do nav, link quebrado e âncora inexistente (ADR-040).

ADRs: [ADR-040](../adr/ADR-040-site-documentacao-mkdocs.md)

Teste guarda: sem teste guarda

### revisao

#### P18

Todo passo derivado do checkpoint de revisão (validação de-para, relatório
HTML, banco Datasette, restart do container) é acionado automaticamente
ao final do pipeline de extração/reprocessamento
(`scripts/atualizar_revisao.py`, chamado por `revisar_taxonomia_piloto.py`
e `reprocessar_falhas_piloto.py`) — nunca deixado como passo manual
separado. O restart do Datasette é best-effort (loga aviso, nunca lança
exceção) pra não derrubar o pipeline de extração por causa de
infraestrutura local indisponível.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P41

Aprovação da revisão humana é o `status_revisao_humana` do `<edital>.json`
(`APROVADO...`). O writer relê o JSON a cada carga.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### P44

Decisão humana de sinônimo (5B, histórico) foi via
`scripts/aprovar_sinonimos.py`. Desde a 5B.1 o `sinonimos.json` está
congelado, e o pipeline não o escreve mais.

ADRs: nenhuma

Teste guarda: sem teste guarda

### testes

#### P68

Testes e Ruff por etapas (`Makefile` e marcadores do `pytest.ini`):
- Etapa 1 (`make test-fast` / `pytest -m "unit and not db"`): executa `ruff check .` e testes unitários em memória (~18s, sem I/O nem banco).
- Etapa 2A (`make test-pipeline` / `pytest tests/`): suíte do scraper, parsers, taxonomia e árvore (~1m15s).
- Etapa 2B (`make test-site` / `pytest site/tests/`): suíte da web, rotas, API e simulados (~3m20s). Para pular testes lentos (>3s), usar `make test-site-fast` (`-m "not slow"`).
- Etapa 3 (`make test-all` / `make check`): suíte completa de 840 testes e verificação de formatação.
- Marcadores registrados no `pytest.ini`: `unit`, `db`, `pipeline`, `site`, `slow`.
- Configuração central do Ruff em `pyproject.toml` (targets, ignores e exclusões de `scratch/`, `data/`, etc.).

ADRs: nenhuma

Teste guarda: sem teste guarda

### processo

#### P70

Script novo em `scripts/` (ou módulo de `src/` com `__main__`) entra em
`src/registro/scripts.py`, e mudança de argparse, etapa, checagem, regra ou schema pede
`make docs-gerar`: o `tests/test_registro.py` recusa script fora do registro e página
gerada diferente do código (ADR-041). Regra nova entra só em `src/registro/regras_*.py`
(próximo id, área, ADR e teste guarda), cai numa tarefa de `src/registro/tarefas.py` pela
área, e só vai para o §6/§7 do `CLAUDE.md` se for do núcleo (`nucleo=True`, com link).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-041](../adr/ADR-041-registro-e-paginas-geradas.md)

Teste guarda: `tests/test_registro.py::test_todo_script_esta_no_registro`

#### P71

Lote novo (ou qualquer passo que grava no banco) nunca altera o piloto
(PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, CD_25_NS: 2.800 itens, 129 anuladas,
3.029 apontamentos, chaves da 5D): as checagens K22–K24 rodam antes e depois, e
diferença bloqueia o lote.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: `tests/test_reconciliacao_inventario.py::test_regressao_piloto_chaves_5d_inalteradas`

## Anti-patterns

### coleta

#### A01

Nunca comparar `get_attribute("href")` direto contra uma URL absoluta
sem resolver primeiro (`urljoin(page.url, href)`) — os cards da listagem
do CEBRASPE usam href relativo (`/concursos/PF_25_ADM`), e um
`href.startswith("https://...")` sem resolver descarta 100% dos links
silenciosamente (0 resultados, sem exceção). Achado ao vivo em
2026-09-19, ver ADR-008.

ADRs: [ADR-008](../adr/ADR-008-resolucao-href-relativo.md)

Teste guarda: `tests/test_spider.py::TestGetContestLinksResolveHref::test_resolve_href_relativo_contra_url_da_pagina`

#### A02

Nunca filtrar ano com regex no texto do link — o ano está no slug da URL
(ex: `TJ_CE_25_NOTARIOS` → 2025), não aparece como "2025" no texto visível.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A03

Nunca envolver o loop de concursos inteiro num único `try/except` (mascara
falha isolada como falha total do lote).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A15

Nunca deduzir o concurso pelo path `data/<ano>/CEBRASPE/<orgao>/`: dois
concursos do mesmo órgão no mesmo ano dividem a pasta. O slug só existe
na URL de origem guardada no manifesto.

ADRs: nenhuma

Teste guarda: sem teste guarda

### edital

#### A04

Nunca modelar tópico/subtópico como duas listas paralelas — perde a
hierarquia que a Fase 5 precisa para estatística.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A09

Nunca casar cabeçalho de matéria/cargo em edital só com letras/espaço/
hífen — perde silenciosamente todo cabeçalho com dígito (`CARGO N:`),
vírgula ou parênteses, e o conteúdo correspondente é engolido pelo chunk
anterior sem erro nenhum. Achado ao vivo em 2026-09-19 (chunk de 41850
chars engolindo ~14 cargos), ver ADR-010 e `LESSONS.md`.

ADRs: [ADR-010](../adr/ADR-010-chunking-cargo-materia.md)

Teste guarda: `tests/test_edital_parser.py::TestPadroes::test_padrao_materia_casa_nomes_com_digito_virgula_parenteses`

#### A14

Nunca identificar matéria só pelo nome (nem por `(cargo, materia)`). O
bloco básico repete os mesmos nomes (LÍNGUA PORTUGUESA, RACIOCÍNIO
LÓGICO, ...) em superior e médio com conteúdo diferente. A chave mínima é
`(concurso, tipo_conhecimento, nivel, cargo, materia)`. Ver ADR-020 e
`LESSONS.md`.

ADRs: [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md)

Teste guarda: `tests/test_edital_parser.py::TestBlocosDeConhecimento::test_mesma_materia_em_niveis_diferentes_fica_distinguivel`

#### A18

Nunca aplicar `[^\w]` ou normalização NFKD direta sobre texto bruto extraído de
PDF sem antes compor caracteres combinantes via `NFC` — caracteres em NFD
(como `i` + `\u0301`) perdem o acento isolado e geram divergência com a saída do LLM.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A19

Nunca validar cobertura de itens do edital comparando apenas o campo
`topico["nome"]` — o modelo frequentemente estrutura itens como `subtopicos`,
e ignorá-los gera falsos positivos em massa de `topico_ausente`.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A20

Nunca emitir alerta de `topico_extra` apenas por ausência de casamento direto
com um item numerado individual — se o termo constar no corpo do texto-fonte
do chunk, trata-se de um tópico válido do texto programático, não alucinação.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A21

Nunca criar um chunk novo diretamente a partir de quebra de linha de cabeçalho
de cargo sem checar se o bloco intermediário possui itens numerados programáticos.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A23

Nunca usar casamento tolerante contra o texto-fonte **inteiro** numa
checagem por item: um tópico parafraseado de um item passa a "cobrir" a
omissão de outro item do mesmo chunk.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A24

Nunca deixar a restrição de cargo no nome da matéria (duplica
`dim_materia`), nem apagá-la do nome sem ter extraído os números de cargo
(a matéria passa a valer para todos os cargos sem aviso).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A36

Nunca casar a restrição com `\([^)]*\)`: um parêntese interno
(`ANALISTA (TI)`) corta a cláusula no meio e o resto fica no nome.

ADRs: nenhuma

Teste guarda: `tests/test_edital_parser.py::TestBlocosDeConhecimento::test_restricao_com_parentese_interno_sai_inteira_do_nome`

### prova

#### A37

Nunca permitir janela ampla de recuo de linha de item (> 24 pt, ex.: 8–30 pt) no parser de provas — captura a primeira linha com recuo de parágrafo (~28–29 pt) do texto-base subsequente após itens de 1 linha física (ADR-031).

ADRs: [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

Teste guarda: sem teste guarda

#### A38

Nunca confiar na ordem do fluxo interno de objetos do PDF (PyMuPDF blocks) para determinar a ordem de leitura em cadernos sem ordenar visualmente por coordenadas `(coluna, y0, x0)` (ADR-031).

ADRs: [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

Teste guarda: sem teste guarda

#### A39

Nunca confiar em `span["flags"] & 16` ou "Bold" para segmentar itens de provas (apenas 9,64% dos cadernos do CEBRASPE usam fonte com flag negrito; a segmentação real é por x0 na margem via cluster/moda).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A40

Nunca procurar "definitivo" solto no corpo do padrão de resposta ou gabarito (o padrão do cargo 2 da PF cita "definitivo" no texto discursivo; um preliminar com a mesma redação seria classificado como definitivo). Avaliar estritamente o cabeçalho (primeiros 600 caracteres no padrão de resposta, 2000 na grade — ver `classificar_versao`) ou o nome do arquivo.

ADRs: nenhuma

Teste guarda: `tests/test_gabarito_parser.py::TestClassificarVersao::test_definitivo_solto_apenas_no_corpo_retorna_none`

#### A41

Nunca extrair quesitos numerados antes do verbo de comando da prova discursiva (datas como "1 de janeiro..." no enunciado viram falso quesito 1).

ADRs: nenhuma

Teste guarda: `tests/test_prova_parser.py::TestCadernoDiscursivo::test_quesitos_so_a_partir_do_comando`

#### A58

Nunca comparar texto-base por hash do texto cru: a quebra de parágrafo
depende do layout do caderno. A chave canônica normaliza espaços.

ADRs: nenhuma

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_canonica_ignora_quebra_de_paragrafo_do_texto_base`

### llm

#### A10

Nunca chamar modelo de raciocínio com `max_tokens` baixo pra `glm-5.3-flash` — o
`content` volta `null` mesmo sem erro de rede se o orçamento acabar no
`reasoning_content`.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A11

Nunca usar SDKs pesados de LLM (como litellm ou langchain) na chamada de inferência
— chamadas diretas REST via `requests`/`httpx` mantêm a stack enxuta e confiável.
Isso se refere à chamada de inferência do modelo; para observabilidade, usa-se
o SDK oficial do Langfuse (OTel, ver ADR-023).

ADRs: [ADR-023](../adr/ADR-023-migracao-langfuse-sdk-oficial.md)

Teste guarda: sem teste guarda

#### A12

Nunca enviar telemetria via `POST /api/public/ingestion` (REST manual) —
endpoint legado entra em sunset em 2026-11-16, passando a aceitar apenas scores
e rejeitando traces e generations. Usar o SDK oficial `langfuse` (ADR-023).

ADRs: [ADR-023](../adr/ADR-023-migracao-langfuse-sdk-oficial.md)

Teste guarda: sem teste guarda

#### A16

Nunca aceitar `nome` de tópico puramente numérico como extração válida —
`Topico.nome: str` do Pydantic aceita "1" numa boa (estruturalmente
válido), mas é sinal de que o LLM confundiu o numeral do item da fonte
com o texto do tópico, não um tópico legítimo. Achado real: 2 chunks
inteiros (Contabilidade) com `status="sucesso"` e todo `nome` numérico,
86 dos 88 alertas de validação de um teste completo. Ver ADR-021.

ADRs: [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md)

Teste guarda: `tests/test_validar_taxonomia.py::TestCompararChunk::test_topico_nome_numerico_gera_alerta_dedicado`

#### A17

Nunca capturar `requests.RequestException`/erro de parse de forma
genérica e devolver um único `motivo_falha=None` para tudo — timeout,
conexão recusada, HTTP 429/5xx, conteúdo vazio e schema inválido são
causas-raiz diferentes com decisões de reprocessamento diferentes
(transitório vs. precisa de ajuste); colapsar tudo em `status="falha"`
esconde isso do relatório HTML/Datasette e do Langfuse. Ver ADR-022.

ADRs: [ADR-022](../adr/ADR-022-classificacao-erros-chamada-openrouter.md)

Teste guarda: `tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_content_none_retorna_status_de_conteudo_vazio`, `tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_json_invalido_retorna_status_de_parse_json`, `tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_json_fora_do_schema_retorna_status_de_validacao_schema`, `tests/test_taxonomia_extractor.py::TestExtrairTaxonomiaChunk::test_falha_de_conexao_retorna_status_de_conexao`

### banco

#### A05

Nunca reabrir a decisão de tecnologia de banco — PostgreSQL 16 já é o
padrão do portfólio.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A06

Nunca gravar tabelas deste projeto no `study-rag-db` nem criar FK para
`itens_estudo` — o `study-rag-db` tem ciclo de vida, credenciais e
reconfiguração próprios, e acoplar os dois quebra um a cada mudança do
outro. Cruzamento só por chave natural na Etapa 7 (ADR-026).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-026](../adr/ADR-026-banco-postgres-proprio.md)

Teste guarda: sem teste guarda

#### A43

Nunca somar linhas de views agregadas por cargo (`vw_prova_cobra_*`): cadernos básicos cobrem múltiplos cargos; somar linhas de cargos diferentes duplica questões básicas no denominador e no numerador. Para consultas que cruzam ou agregam múltiplos cargos/concursos, usar sempre a função oficial `fn_prova_cobra(...)` ou filtrar estritamente por um cargo individual (ADR-032).

ADRs: [ADR-032](../adr/ADR-032-classificacao-questoes-arvore.md)

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_caderno_basico_multiplos_cargos_conta_uma_vez`

#### A57

Nunca dar GRANT a role do site esperando que ele sobreviva a uma carga:
`schema_estatisticas.sql` recria as views com `DROP ... CASCADE`.
`stats_writer.criar_schema` guarda e reaplica os GRANTs do schema; não
remover isso (sem ele, toda reextração derruba o site com 500).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_criar_schema_preserva_grants_das_views`

#### A60

Nunca computar questões discursivas junto com questões objetivas: discursivas possuem grão, tema e dinâmica de pontuação inteiramente distintos e devem ser consumidas estritamente via `vw_discursivas` (ADR-032).

ADRs: [ADR-032](../adr/ADR-032-classificacao-questoes-arvore.md)

Teste guarda: `tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_discursivas`

### arvore

#### A27

Nunca aprovar sinônimo ou mapeamento da árvore com `UPDATE` no banco nem
editando só o banco: a fonte é `canonico/arvore.json` (antes,
`sinonimos.json`), e a próxima carga reverte.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A28

Nunca ler ou escrever `canonico/arvore.json` com `json.load`/`json.dump`
direto: o primeiro código da 5B.1 fez isso, montou a chave com `str(tupla)`
e leu o campo `no` em vez de `no_id`. A regra do pipeline casou 0 de 1259
assuntos e o relatório pôs os 4050 itens sob `None`, sem erro nenhum. Use
`src/arvore.py` (`carregar`, `salvar`, `chave_item`).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A29

Nunca rodar `scripts/semear_arvore.py --forcar` depois da curadoria: a
semente reescreve a árvore do zero e apaga toda decisão do dono.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A31

Nunca juntar um nome composto (`Disposições gerais, servidores
públicos`) a uma de suas partes: isso conta uma parte como a outra. Ele
aponta para os N nós (ADR-030).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_arvore_views.py::TestEditalCobra::test_composto_conta_uma_vez_em_cada_no`

#### A32

Nunca derivar o pai de um nó da árvore do edital de origem: a matéria
composta do CD separaria os assuntos de Constitucional dos outros
concursos (ADR-030).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: sem teste guarda

#### A33

Nunca criar nó da árvore automaticamente a partir de nome novo de edital:
o que a regra não mapeia fica pendente para a curadoria.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A34

Nunca deixar dois nós ativos com o mesmo nome (pela `chave_regra`) sob o mesmo
pai, nem duas disciplinas de mesmo nome: o filtro do site mostra o nome
repetido e a incidência se divide. Ao fundir ou renomear disciplina, rode
`pytest tests/test_arvore.py`; os testes `*_sem_irmaos_homonimos` e
`*_sem_disciplinas_homonimas` guardam isso. Cargo não é atributo do nó
(ADR-030). Paráfrase (nome diferente) segue com o dono.

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_arvore.py::test_arvore_curada_sem_irmaos_homonimos`, `tests/test_arvore.py::test_arvore_curada_sem_disciplinas_homonimas`

#### A63

Nunca reimplementar a equivalência de nome no relatório de revisão ou no Datasette: usar
`canonico.arvore_apos_passo`. Divergência faz o relatório prometer "resolvido" o que a carga
não grava (SEFA_PR_25, 8 itens) e esconde ou infla os pendentes (KAN-81).

ADRs: [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

Teste guarda: `tests/test_mapeamento_revisao.py::test_pendentes_do_relatorio_igual_aos_do_passo_nos_editais_reais`

### classificacao

#### A08

Nunca usar `\b` de regex direto sobre um slug com underscore para detectar
keywords — `_` é `\w`, então `\bINSS\b` não dispara em `INSS_25`. Dividir
o slug em segmentos primeiro.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A26

Nunca agrupar matéria/assunto/subassunto por similaridade de texto sem
aprovação humana: `atos` × `contratos administrativos` (0,89), `ativos` ×
`passivos` (0,90), `gestão de processos` × `de pessoas` (0,89). Similaridade
só sugere; quem junta é regra determinística ou o dono (ADR-029).

ADRs: [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md)

Teste guarda: sem teste guarda

#### A35

Nunca classificar a questão só entre os nós do edital do caderno: a
questão fora do edital ficaria sem nó, e o "edital × prova" perderia o
lado "cobrado fora do edital".

ADRs: nenhuma

Teste guarda: `tests/test_classificacao.py::test_mapear_fora_do_edital_por_no`

### site

#### A44

Nunca pôr senha de role no SQL versionado (`site/sql/app_schema.sql`) nem em
teste: a primeira versão da 5F.1 fez isso e as senhas foram trocadas. Senha
vem do `.env` via `site/scripts/aplicar_schema_app.py`.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A45

Nunca rodar o site com `python -m site...`: o diretório `site` colide com o
módulo `site` da stdlib. Use o caminho do script ou `uvicorn app.main:app`
de dentro de `site/`.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A46

Nunca dar à role `site_leitura` acesso ao schema `app` (nem fazer JOIN
entre `app.resposta` e as views numa query só): as respostas são lidas pela
`site_app` e a lista de chaves entra no SQL das views por parâmetro.

ADRs: nenhuma

Teste guarda: `site/tests/test_api_questoes.py::test_permissoes_role_site_leitura`

#### A47

Nunca aceitar o `voltar` do login sem `auth.destino_seguro` (open redirect
com `//host` ou `/\host`).

ADRs: nenhuma

Teste guarda: `site/tests/test_contas.py::test_destino_seguro_bloqueia_open_redirect`

#### A48

Nunca usar a `questao_chave` crua como id de elemento HTML: o `|` é
separador de namespace em seletor CSS, e o `hx-target="#..."` quebra no
`querySelector` do HTMX sem aparecer em teste de rota. Use `dom_id(chave)`
(`q-<sha1>`) de `rotas_web.py`.

ADRs: nenhuma

Teste guarda: `site/tests/test_web.py::test_hx_target_da_correcao_e_seletor_css_valido`

#### A49

Nunca interpolar valor da query string dentro de expressão do Alpine
(`x-data="{ x: '{{ valor }}' }"`): o navegador decodifica `&#39;` de volta
para `'` antes de o Alpine avaliar, e vira XSS. Passe por atributo
`data-*` e leia com `$el.dataset`.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A50

Nunca pôr `hx-get` num `<select>` dentro do form de filtros: em GET o HTMX
envia só o valor do próprio elemento e perde os outros filtros. O gatilho
fica no `<form>` (`hx-trigger="change, submit"`).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A51

Nunca devolver o fragmento só por `HX-Request`: a restauração de histórico
do HTMX também manda esse header e espera a página inteira (checar
`HX-History-Restore-Request`).

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A52

Nunca pôr campo pesado (texto-base, figuras) em `QuestaoResumo` para
servir o HTML: muda o contrato da API e multiplica o payload da listagem.
O card busca em `/q/.../anexos` quando o usuário abre.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A53

Nunca declarar `cargo_numero: int` em rota HTML com select de cargo: trocar
o concurso limpa o select e manda `cargo_numero=`, e o FastAPI responde 422
(só aparece no navegador, não no teste com parâmetro válido).

ADRs: nenhuma

Teste guarda: `site/tests/test_web.py::test_cargo_vazio_ao_trocar_concurso_nao_da_422`

#### A54

Nunca mandar o gabarito na prova do simulado (`ItemSimulado` não tem o
campo) nem o padrão de resposta antes de encerrar: a correção é sempre no
servidor.

ADRs: nenhuma

Teste guarda: `site/tests/test_simulado.py::test_prova_em_ordem_e_sem_gabarito`

#### A55

Nunca apagar o rascunho do simulado no clique de enviar: se o POST falhar
(CSRF, rede), as marcações de horas de prova somem. Só a página de
resultado apaga. E nada de `try` em `x-init`: Alpine só avalia expressão.

ADRs: nenhuma

Teste guarda: `site/tests/test_simulado.py::test_rascunho_so_some_no_resultado`

### revisao

#### A22

Nunca silenciar um alerta de validação sem antes perguntar se o dado está
errado. Perda de conteúdo (item omitido) se corrige no dado; paráfrase
explicável se rebaixa para informativo. Canonicalizar o nome extraído
para o texto literal da fonte reintroduz erro de digitação do PDF. Ver
ADR-025.

ADRs: [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)

Teste guarda: sem teste guarda

#### A25

Nunca aprovar concurso com `UPDATE` direto no banco: a próxima carga do
writer reverte a partir do JSON.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A30

Nunca deixar o agente aprovar proposta do LLM em nome do dono; só grupo
`regra` é aprovado automaticamente.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

### testes

#### A56

Nunca usar dois `TestClient(app)` ao mesmo tempo nos testes: os pools do
banco são globais e o lifespan do primeiro a sair fecha os do outro.

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A59

Nunca remover o `conftest.py` da raiz: sem ele o pytest grava os erros
simulados (`x.test`, `XX_25`) em `logs/scraper_cebraspe.log`, e o log de
produção deixa de servir para auditar execução real.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

### infra

#### A07

Nunca hardcodar credenciais de API/Postgres no código — usar `.env`
(ver Segurança).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: nenhuma

Teste guarda: sem teste guarda

#### A42

Nunca commitar arquivos JSON de questões extraídas (`questoes/`) no git — mantidos localmente e no `.gitignore` por volumetria, sendo 100% regeneráveis sob demanda (ADR-031).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

Teste guarda: sem teste guarda

#### A61

Nunca usar o `site_dir` padrão do MkDocs (`site/`): o build apagaria o app FastAPI em `site/`. O build vai para `build/docs` (ADR-040).

ADRs: [ADR-040](../adr/ADR-040-site-documentacao-mkdocs.md)

Teste guarda: sem teste guarda

### processo

#### A13

Nunca deixar um passo do pipeline (extração → artefatos derivados) como
"rode manualmente depois" — este projeto já foi mordido 2x por isso
(`run()` nunca chamando `download_concurso_pdfs`, achado de 2026-09-19;
href relativo silenciosamente descartando 100% dos links, ADR-008): a
falha de esquecer o passo manual não lança erro, só deixa o artefato
seguinte desatualizado sem sinal nenhum. Ver ADR-019.

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-008](../adr/ADR-008-resolucao-href-relativo.md), [ADR-019](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md)

Teste guarda: sem teste guarda

#### A62

Nunca editar à mão as páginas de `docs/tecnico/`: são geradas de `src/registro/`
por `scripts/gerar_docs.py`, e o teste guarda recusa a diferença (ADR-041).

Núcleo: sim (citada no `CLAUDE.md`)

ADRs: [ADR-041](../adr/ADR-041-registro-e-paginas-geradas.md)

Teste guarda: `tests/test_registro.py::test_paginas_geradas_batem_com_o_disco`
