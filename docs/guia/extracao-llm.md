# Extração por LLM e Observabilidade

Pipeline de extração estruturada de conteúdo programático e taxonomia de editais via modelos de linguagem (OpenRouter/GLM), enriquecido por reparos locais determinísticos e observabilidade ponta a ponta no Langfuse.

**Para que serve:** Descrever a arquitetura de recorte de texto de editais, divisão em chunks, chamadas HTTP diretas ao OpenRouter, tolerância a falhas com retentativas, trilha de auditoria e telemetria no Langfuse. **Quando ler:** Antes de alterar rotinas do parser de editais, prompts de extração, parâmetros de inferência, regras de classificação de erros ou integração de observabilidade.

## Recorte e Pré-Processamento de Editais

A extração de taxonomia programática inicia-se pelo isolamento estrito da seção de conteúdo relevante do edital em PDF. Em vez de submeter o documento integral à inferência (o que geraria alto custo e risco de alucinações), o sistema localiza a seção iniciada pelo marcador textual `OBJETOS DE AVALIAÇÃO` e encerra a captura no início de `ANEXO I` ou no fim do arquivo, retornando a estrutura detalhada `SecaoExtraida` com os metadados de corte.
Fonte: src/edital_parser.py:20-21, 313-331, 338-372; docs/adr/ADR-009-recorte-objetos-avaliacao.md:12-20

As seções administrativas anteriores (requisitos de posse, atribuições de cargos, modelos de declaração e cronograma) e posteriores ao anexo programático são sumariamente descartadas. Essa estratégia reduz o volume textual submetido ao modelo e previne que ruídos de regras operacionais de certames interfiram na extração da matriz de disciplinas.
Fonte: src/edital_parser.py:10-19, 348-359; docs/adr/ADR-009-recorte-objetos-avaliacao.md:16-23

O texto recortado passa por rotinas de higienização pré-processamento. A função `_limpar_ruido_edital` remove notas avulsas de retificação embutidas no meio das disciplinas e aciona `remover_assinatura_final`, que detecta e extirpa o bloco final contendo nomes e cargos de signatários administrativos (como dirigentes e ministros-presidentes) que frequentemente colam na cauda do último item programático.
Fonte: src/edital_parser.py:386-434; docs/adr/ADR-016-retry-maiores-tokens-llm.md:13-15

Itens programáticos que tenham sido explicitamente revogados ou excluídos por editais de retificação são eliminados previamente pela função `remover_topicos_excluidos`. Ao analisar notas textuais que indicam a exclusão de determinados tópicos e subtópicos numerados, o parser remove a anotação e o intervalo textual do item correspondente antes da formação dos chunks, impedindo que conteúdo revogado seja enviado ao modelo.
Fonte: src/edital_parser.py:583-610, 839-842

## Estratégia de Chunking em Dois Níveis

O texto da seção de objetos de avaliação é particionado em unidades autônomas por meio da função `dividir_por_cargo_e_materia`. O particionamento em dois níveis vincula conjuntamente cabeçalhos de cargo (`CARGO N: <nome>`) e cabeçalhos de disciplina (`NOME DA MATÉRIA:`), mantendo o cargo corrente para garantir que cada bloco caiba na janela de contexto do modelo sem romper a hierarquia de relações das disciplinas.
Fonte: src/edital_parser.py:660-680; docs/adr/ADR-010-chunking-cargo-materia.md:12-19

O algoritmo suporta dois formatos estruturais coexistentes em editais de concurso: certames administrativos com disciplinas segregadas (gerando um chunk para cada matéria sob o mesmo cargo) e certames com cargos de especialidade técnica ou médica cujo conteúdo programático é disposto diretamente sob o título do cargo (gerando um único chunk em que o próprio nome do cargo é atribuído ao campo de matéria). Disciplinas gerais desprovidas de vinculação específica a um cargo único recebem a indicação de `cargo=None`.
Fonte: src/edital_parser.py:671-678, 779-824; docs/adr/ADR-010-chunking-cargo-materia.md:10-21

A delimitação de fronteiras entre chunks também reconhece cabeçalhos institucionais de bloco (`CONHECIMENTOS BÁSICOS` ou `CONHECIMENTOS ESPECÍFICOS` combinados com `NÍVEL SUPERIOR` ou `NÍVEL MÉDIO`). Esses cabeçalhos não geram chunks próprios, mas definem as propriedades `tipo_conhecimento` e `nivel` dos chunks subsequentes, resetam o cargo corrente para evitar contaminação entre blocos distintos e atuam como barreira para que o texto do cabeçalho seguinte não se misture à cauda do anterior.
Fonte: src/edital_parser.py:681-697, 754-774; docs/adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md:12-25

Submatérias numeradas em algarismos romanos no corpo de disciplinas compostas (como divisões internas de direito constitucional e administrativo) são identificadas por expressões regulares dedicadas e convertidas em chunks individuais, evitando que matérias guarda-chuva vazem texto não estruturado. Adicionalmente, restrições expressas de aplicação de matérias a subconjuntos de cargos são registradas e validadas nos metadados do chunk.
Fonte: src/edital_parser.py:51-59, 711-733, 853-863; docs/adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md:10-22

## Chamadas Diretas ao OpenRouter e Parâmetros de Inferência

A submissão dos chunks ao modelo de linguagem é realizada via requisições HTTP REST diretas contra o endpoint `/chat/completions` do OpenRouter, utilizando a biblioteca `requests` no processamento em lote e `httpx` no bot do Telegram. A arquitetura dispensa proxies locais, runtimes pesados ou frameworks intermediários (como LiteLLM ou LangChain), garantindo estabilidade, baixa pegada de dependências e controle absoluto sobre o payload e os cabeçalhos de rede.
Fonte: src/llm_openrouter.py:8-15, 313-318; docs/adr/ADR-011-extracao-llm-requests-direto.md:12-25

O modelo de linguagem padronizado para as rotinas de extração taxonômica e classificação é o `z-ai/glm-5.3-flash`. Por se tratar de um modelo de raciocínio avançado, parte considerável de sua geração inicial é dedicada a tokens de pensamento interno (`reasoning_content`) antes da emissão do conteúdo final em JSON, exigindo dimensionamento adequado de limites para evitar respostas truncadas.
Fonte: src/llm_openrouter.py:13-15, 41-42, 278-286; docs/adr/ADR-016-retry-maiores-tokens-llm.md:10-15

Os parâmetros padrão das requisições são calibrados para maximizar determinismo e tolerância à extensão de matérias volumosas: temperatura baixa de 0.1 (`TEMPERATURA_PADRAO`), limite máximo de 12.000 tokens (`MAX_TOKENS_PADRAO`) e tempo limite de resposta de 120 segundos (`TIMEOUT_PADRAO`). Para mitigar o consumo desproporcional do orçamento por etapas de raciocínio, aplica-se uma restrição explícita de reasoning configurada em 3.000 tokens (`REASONING_PADRAO`).
Fonte: src/llm_openrouter.py:82-90, 248-253, 284-288; docs/adr/ADR-016-retry-maiores-tokens-llm.md:14

As requisições transmitem cabeçalhos HTTP adicionais de identificação (`HTTP-Referer` e `X-Title`) e utilizam autenticação Bearer com a chave de API resolvida para a etapa. O payload enviado combina uma mensagem de sistema estrita (`PROMPT_SISTEMA`) com o texto bruto do chunk como mensagem de usuário. A resposta recebida tem possíveis cercas de código Markdown removidas por `strip_markdown_fence` e é validada estruturalmente contra o schema Pydantic `TaxonomiaEdital`, garantindo a tipagem de tópicos e subtópicos.
Fonte: src/llm_openrouter.py:104-107, 136-147, 278-297, 378-380; src/taxonomia_extractor.py:92-108; src/models_scraper.py:21-28

## Resiliência, Retentativas e Reparos Locais Determinísticos

O núcleo de chamadas classifica minuciosamente qualquer anomalia ocorrida durante a comunicação com a API do OpenRouter em oito status técnicos padronizados: `falha_timeout`, `falha_conexao`, `falha_rate_limit` (HTTP 429), `falha_http` (outros status 4xx/5xx), `falha_rede` (outras exceções de rede), `falha_conteudo_vazio` (resposta sem conteúdo textual útil, tipicamente por esgotamento de tokens), `falha_parse_json` (JSON corrompido ou malformado) e `falha_validacao_schema` (JSON válido que descumpre o contrato do Pydantic). Essa taxonomia de erros distingue falhas transitórias de infraestrutura de inconsistências estruturais persistentes.
Fonte: src/llm_openrouter.py:92-103, 320-405; docs/adr/ADR-022-classificacao-erros-chamada-openrouter.md:39-96

Para mitigar intermitências de rede e limites momentâneos de requisições, a função `extrair_taxonomia_chunk` adota política de retentativa com backoff exponencial. O fluxo padrão executa até duas tentativas, intercalando pausas de espera (5 e 15 segundos) entre os disparos. Caso o processamento obtenha êxito em qualquer rodada, a falha anterior é desconsiderada; persistindo o insucesso após o esgotamento do ciclo, o status da última tentativa é retornado para registro no relatório e reprocessamento posterior.
Fonte: src/taxonomia_extractor.py:73-74, 540-576; src/llm_openrouter.py:433-464; docs/adr/ADR-016-retry-maiores-tokens-llm.md:12-20

Falhas semânticas identificadas na resposta do modelo (quando o JSON gerado é sintaticamente válido mas viola regras lógicas de conteúdo) são tratadas por meio do gancho `pos_validacao`. Em vez de reexecutar chamadas cegas ao modelo sem contexto adicional de erro, o pipeline aciona rotinas determinísticas de reparo local que utilizam o próprio texto-fonte do edital como verdade factual, poupando tokens e assegurando previsibilidade.
Fonte: src/taxonomia_extractor.py:160-174, 454-504; docs/adr/ADR-021-reparo-local-nome-topico-numerico.md:12-35

O reparo local de nomes numéricos (`_reparar_nomes_numericos`) atua quando o modelo preenche o campo `nome` do tópico apenas com o numeral do item (ex.: `"1"`, `"2"`). A rotina cruza o número com os itens extraídos da fonte por `extrair_itens_numerados` e substitui o valor in-place pelo texto integral da ementa. Caso algum numeral não encontre correspondência factual no texto de origem, o chunk é marcado com o status específico `falha_nome_numerico_nao_mapeado`, direcionando-o para inspeção humana.
Fonte: src/taxonomia_extractor.py:84, 160-193, 470-489; docs/adr/ADR-021-reparo-local-nome-topico-numerico.md:37-60

De forma complementar, as rotinas `reinjetar_itens_ausentes` e `reinjetar_subitens_ausentes` reconstituem itens de primeiro nível simples (de até 150 caracteres) e subitens hierárquicos que tenham sido indevidamente omitidos pelo modelo. As inserções são realizadas in-place na árvore taxonômica na posição correta de leitura da fonte, utilizando critérios de normalização idênticos aos do validador de-para, prevenindo divergências e apontamentos de ausência na validação heurística.
Fonte: src/taxonomia_extractor.py:86-90, 195-263, 268-270, 355-451, 490-502; docs/adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md:10-30

## Trilha de Auditoria e Reprodutibilidade

Todo processamento de edital gera um par indissociável de arquivos na pasta `revisao_piloto/`: o arquivo de dados `<edital>.json` (contendo o catálogo de cargos e a taxonomia final extraída) e o arquivo de auditoria `<edital>.auditoria.json`. A persistência desses dois artefatos viabiliza a rastreabilidade ponta a ponta do ciclo de vida da extração e a reprodução exata das inferências realizadas.
Fonte: scripts/revisar_taxonomia_piloto.py:130-160; docs/adr/ADR-014-trilha-auditoria-parser-extractor.md:12-22

O arquivo de auditoria armazena metadados globais da extração física do documento (total de páginas, contagem de caracteres do PDF, caracteres descartados fora do anexo e offsets absolutos de início e fim da seção recortada). Cada chunk particionado recebe uma entrada correspondente no array `chunks`, contendo os limites de caracteres na seção, o status da extração e a cópia exata do texto bruto submetido ao modelo de linguagem (`texto_enviado_llm`).
Fonte: scripts/revisar_taxonomia_piloto.py:79-91, 139-153; docs/adr/ADR-014-trilha-auditoria-parser-extractor.md:13-17

A amarração relacional entre a taxonomia consolidada, a trilha de auditoria e os diagnósticos de divergência textual é estabelecida pela chave inteira `chunk_index`. Esse identificador imutável permite que interfaces de revisão humana (como o Datasette e relatórios HTML) cruzem lado a lado o texto bruto do edital com os tópicos gerados pelo modelo e os alertas apontados pelo validador heurístico.
Fonte: scripts/revisar_taxonomia_piloto.py:81, 104; docs/adr/ADR-014-trilha-auditoria-parser-extractor.md:16; docs/adr/ADR-017-validacao-heuristica-de-para-taxonomia.md:183

## Observabilidade e Telemetria com Langfuse

A observabilidade de todas as chamadas a modelos de linguagem é realizada por meio do SDK oficial do Langfuse na versão 4 (`langfuse>=4.7,<5`), estruturado sobre a especificação OpenTelemetry (OTel). A instrumentação oficial substituiu o modelo legado de envio via requisições REST manuais ao endpoint `/api/public/ingestion`, que entrou em processo de descontinuação na infraestrutura do Langfuse Cloud.
Fonte: src/llm_openrouter.py:32; docs/adr/ADR-023-migracao-langfuse-sdk-oficial.md:24-27, 61-72

A instância do cliente Langfuse é gerenciada de maneira singleton e preguiçosa pela função `langfuse_client` com `@lru_cache(maxsize=1)`. Caso as credenciais `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY` não estejam configuradas no ambiente, o cliente retorna `None`, permitindo que testes unitários e execuções locais ocorram sem bloqueios, latência de rede ou mocks invasivos.
Fonte: src/llm_openrouter.py:150-159; docs/adr/ADR-023-migracao-langfuse-sdk-oficial.md:28-30

A telemetria organiza as chamadas segundo a convenção padronizada de nomenclatura de traces `cebraspe-<etapa>-<função>`. No processamento de editais, o trace é identificado como `cebraspe-4-taxonomia-edital`, espelhando a chave dedicada de faturamento `OPENROUTER_KEY_TAXONOMIA_EDITAL` (com fallback para `OPENROUTER_API_KEY`). A nomenclatura e o identificador de usuário são injetados no contexto via context manager `propagate_attributes` durante a abertura da observação.
Fonte: src/llm_openrouter.py:46-73, 175-188; docs/adr/ADR-023-migracao-langfuse-sdk-oficial.md:66-70

A observação de inferência (`as_type="generation"`) é iniciada antecipadamente por `abrir_generation` imediatamente antes do disparo da requisição HTTP ao OpenRouter. Esse mecanismo assegura que a métrica de latência computada pelo Langfuse reflita com precisão o tempo real despendido no transporte de rede e no processamento do modelo, sem desvios de estimativas manuais posteriores.
Fonte: src/llm_openrouter.py:162-192, 302-311; docs/adr/ADR-023-migracao-langfuse-sdk-oficial.md:31-33

Ao término da inferência, a função `registrar_generation` consolida os dados da observação. Ela registra a saída emitida, o status de execução (`level="DEFAULT"` para sucesso ou `level="ERROR"` em falhas), o consumo discriminado de tokens em `usage_details` (prompt, completion e total obtidos do payload do OpenRouter) e dicionário de metadados contendo o `tipo_erro` (nas falhas do ADR-022) ou registros de reparos locais efetuados. As rotinas de registro operam sob captura ampla de exceções, impedindo que falhas de telemetria afetem o fluxo operacional da extração.
Fonte: src/llm_openrouter.py:194-221, 233-241, 412-429; docs/adr/ADR-022-classificacao-erros-chamada-openrouter.md:91-96; docs/adr/ADR-023-migracao-langfuse-sdk-oficial.md:34-40

O envio de métricas pelo SDK v4 ocorre em segundo plano via thread dedicada com buffer local, eliminando sobrecarga no loop principal de execução. O flush definitivo dos lotes residuais é assegurado nativamente pelo registro do gancho `atexit.register(self.shutdown)` no ciclo de vida da biblioteca, viabilizando o encerramento seguro e gracioso de scripts batch sem necessidade de invocações manuais dispersas de flush.
Fonte: src/taxonomia_extractor.py:115-116; src/llm_openrouter.py:150-159; docs/adr/ADR-023-migracao-langfuse-sdk-oficial.md:41-43

## Referências e Regras Relacionadas

- Regras de negócio relacionadas no registro:
  - [P04 — Chamada Direta ao OpenRouter pelo Núcleo](../tecnico/regras.md#p04)
  - [P17 — Chaves Dedicadas por Etapa no OpenRouter e Langfuse](../tecnico/regras.md#p17)
  - [P19 — Classificação de Chunks por Tipo de Conhecimento e Nível](../tecnico/regras.md#p19)
  - [P20 — Reparo Local Determinístico de Falhas Semânticas](../tecnico/regras.md#p20)
  - [P21 — Status Específico por Tipo de Falha na Chamada ao OpenRouter](../tecnico/regras.md#p21)
  - [A11 — Proibição de SDKs Pesados de LLM em Inferência](../tecnico/regras.md#a11)
  - [A12 — Proibição de Ingestão REST Manual no Langfuse](../tecnico/regras.md#a12)
  - [A14 — Chave Mínima de Matéria com Concurso, Bloco e Nível](../tecnico/regras.md#a14)
  - [A16 — Proibição de Tópicos Puramente Numéricos sem Reparo](../tecnico/regras.md#a16)
  - [A17 — Proibição de Falha Genérica sem Tipagem Técnica](../tecnico/regras.md#a17)
- Decisões de arquitetura fundamentais:
  - [ADR-009 — Recorte Exclusivo da Seção "OBJETOS DE AVALIAÇÃO" no Parser](../adr/ADR-009-recorte-objetos-avaliacao.md)
  - [ADR-010 — Chunking em Dois Níveis (Cargo + Matéria)](../adr/ADR-010-chunking-cargo-materia.md)
  - [ADR-011 — Extração LLM via Requisições HTTP Diretas, sem Dependência de SDKs](../adr/ADR-011-extracao-llm-requests-direto.md)
  - [ADR-014 — Trilha de Auditoria de Entrada/Saída do Parser+Extractor (.auditoria.json)](../adr/ADR-014-trilha-auditoria-parser-extractor.md)
  - [ADR-016 — Retry com Backoff e Expansão de max_tokens/timeout para Mitigar Falhas LLM](../adr/ADR-016-retry-maiores-tokens-llm.md)
  - [ADR-021 — Reparo Local de Nome de Tópico Numérico](../adr/ADR-021-reparo-local-nome-topico-numerico.md)
  - [ADR-022 — Classificação de Erros/Exceções na Chamada ao OpenRouter](../adr/ADR-022-classificacao-erros-chamada-openrouter.md)
  - [ADR-023 — Migração da Telemetria Langfuse de REST Manual para SDK Oficial (OTel)](../adr/ADR-023-migracao-langfuse-sdk-oficial.md)
  - [ADR-025 — Reconciliação Determinística e Severidade de Alertas](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)
  - [ADR-029 — Camada Canônica de Sinônimos de Matérias e Assuntos](../adr/ADR-029-camada-canonica-sinonimos.md)
- Estatísticas e indicadores globais:
  - Quantitativos consolidados de concursos, cargos, cadernos e questões: consultar [docs/executivo/numeros.md](../executivo/numeros.md).

---
_Verificado em 2026-10-21 contra commit 6a9e448._
