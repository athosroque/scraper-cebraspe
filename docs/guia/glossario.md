# Glossário

Vocabulário canônico e definições dos principais conceitos do projeto Scraper CEBRASPE.

**Para que serve:** Alinhar o significado exato de termos técnicos e de negócio utilizados no sistema, banco e documentação. **Quando ler:** Sempre que encontrar um conceito ou termo com sentido técnico específico no projeto.

## Índice Alfabético de Termos

- [Apontamento (Questão → Nó)](#apontamento-questão--nó)
- [Árvore Mestre](#árvore-mestre)
- [Caderno](#caderno)
- [Datasette de Revisão](#datasette-de-revisão)
- [De-Para e Reconciliação](#de-para-e-reconciliação)
- [Discursiva](#discursiva)
- [Fila de Extração de Questões](#fila-de-extração-de-questões)
- [Matéria, Assunto e Subassunto](#matéria-assunto-e-subassunto)
- [ME (Múltipla Escolha)](#me-múltipla-escolha)
- [Partição / Chunk](#partição--chunk)
- [Piloto (2025)](#piloto-2025)
- [Portão Humano (Gate)](#portão-humano-gate)
- [Simulado e Pontuação Líquida CEBRASPE](#simulado-e-pontuação-líquida-cebraspe)
- [Star Schema e Dimensões](#star-schema-e-dimensões)
- [Texto-Base](#texto-base)

---

## Apontamento (Questão → Nó)

Associação taxonômica formal entre uma questão extraída de caderno de prova e um nó da [Árvore Mestre](#árvore-mestre). Cada questão pode receber até dois apontamentos, sendo um categorizado com papel `'principal'` e, opcionalmente, outro com papel `'secundario'`, acompanhados pelo grau de aderência textual inferido (`confianca` em `'alta'`, `'media'` ou `'baixa'`), indicador de conteúdo não previsto no edital (`fora_do_edital`), origem (`'llm'` ou `'humano'`) e estado de curadoria (`'proposto'`, `'aprovado'` ou `'rejeitado'`).
Fonte: src/classificacao.py:34-42, src/sql/schema_estatisticas.sql:411-422

A fonte primária da verdade versionada para essas relações reside no arquivo `canonico/classificacao_questoes.json`, estruturado pela classe `RegistroQuestao` sob chaves estáveis compostas (`<concurso>|<codigo_caderno>|<numero>` para objetivas e prefixo `D` para discursivas). O volume consolidado de apontamentos ativos no acervo é documentado em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: src/classificacao.py:4-12, 44-50, docs/executivo/numeros.md:53

## Árvore Mestre

Repositório taxonômico canônico do projeto, estruturado de forma estritamente desacoplada da redação heterogênea e volátil dos editais de abertura das bancas examinadoras. Sua finalidade é catalogar e organizar os ramos do conhecimento cobrados em concursos públicos em três níveis hierárquicos, garantindo persistência estável para agregação estatística, filtros do site público e cruzamentos analíticos entre editais e provas.
Fonte: docs/adr/ADR-030-arvore-mestre-e-site-de-questoes.md:55-70

A única fonte primária da verdade da taxonomia é o arquivo versionado `canonico/arvore.json`, mantido em memória pela classe `ArvoreMestre`. O arquivo reúne o dicionário de nós (`nos`, composto por instâncias de `NoArvore`), a lista de mapeamentos N:N ligando chaves de texto de edital aos nós canônicos (`mapeamentos`), e a fila de sugestões estruturais geradas por regras determinísticas ou modelos de linguagem (`propostas`).
Fonte: src/arvore.py:22-56

A integridade referencial dos nós segue o princípio da imutabilidade: nós obsoletos ou redundantes nunca são excluídos do grafo, recebendo `status = "fundido"` e gravando o identificador do nó sucessor ativo no campo `fundido_em`. A função `resolver_no` percorre recursivamente essa cadeia até encontrar o nó ativo efetivo, detectando e abortando ativamente qualquer possibilidade de ciclo estrutural. Detalhes completos de curadoria constam em [Árvore Mestre e Curadoria](arvore.md).
Fonte: src/arvore.py:58-70, docs/guia/arvore.md:18-20

## Caderno

Caderno oficial de prova em formato PDF aplicado pelo CEBRASPE em determinada data e turno, agrupando dezenas de itens de conhecimentos básicos e específicos. No inventário de documentos do projeto, os cadernos são catalogados nas categorias `caderno_objetivo`, `caderno_discursivo` e `caderno_com_gabarito` (quando o documento oficial compila simultaneamente enunciado e respostas definitivas).
Fonte: src/inventario.py:37-42, 231-233

Os arquivos físicos são armazenados sob o caminho padrão `data/<ano>/CEBRASPE/<orgao_slug>/Provas/`. Cada prova é vinculada a um ou mais cargos do certame na tabela relacional `provas_cargos`, representando fielmente tanto relações de compartilhamento N:1 (caderno de conhecimentos básicos comum a múltiplos cargos de mesmo nível) quanto relações 1:1 (cadernos de conhecimentos específicos restritos a uma carreira).
Fonte: src/sql/schema_estatisticas.sql:204-212, src/downloader.py:221-232

Cada caderno possui um identificador unívoco de aplicação (`codigo_caderno`, ex.: `094_PF_CB1_01`), extraído do próprio cabeçalho do exame ou da grade do gabarito definitivo. Essa chave viabiliza a amarração exata entre o PDF de questões e o respectivo PDF de gabarito mesmo em concursos cujos arquivos públicos tenham sido publicados com identificadores criptográficos ou hashes aleatórios. As regras de fidelidade ao caderno são detalhadas em [ADR-034](../adr/ADR-034-fidelidade-ao-caderno-e-filtros.md).
Fonte: src/sql/schema_estatisticas.sql:200-202, docs/adr/ADR-031-extracao-questoes-cadernos.md:15-35, docs/adr/ADR-034-fidelidade-ao-caderno-e-filtros.md:45-85

## Datasette de Revisão

Interface web interna e somente-leitura baseada na biblioteca Datasette, concebida para auditoria visual e conferência dos dados extraídos na Etapa 4 antes de sua promoção ao banco analítico. Ele consome o banco SQLite descartável `revisao_piloto/revisao.db`, reconstruído do zero a cada ciclo por `scripts/gerar_db_datasette.py` a partir dos arquivos `<edital>.json`, `<edital>.auditoria.json` e `<edital>.validacao.json`.
Fonte: scripts/gerar_db_datasette.py:1-15, docs/adr/ADR-015-revisao-datasette-traefik.md:9-25

O Datasette opera isolado em contêiner Docker dedicado (`scraper-cebraspe-datasette`) na porta local `8011`, com tabelas virtuais indexadas via SQLite FTS5 para busca textual ultra-rápida em chunks e tópicos. Ele é roteado externamente pelo Traefik com proteção de camada Zero Trust via Cloudflare Access SSO, garantindo que o banco de dados analítico de produção (`scraper-cebraspe-db`) permaneça inacessível diretamente pela internet. Procedimentos operacionais constam em [Revisão humana e portões](revisao-humana.md).
Fonte: docker-compose.yml:83-111, docs/guia/revisao-humana.md:8-21

## De-Para e Reconciliação

Mecanismo automatizado de auditoria heurística e reparo sintático que confronta, chunk por chunk, os tópicos numerados existentes no texto-fonte original do edital contra a taxonomia extraída pelo modelo de linguagem. O script `scripts/validar_taxonomia.py` compara os itens identificados em `texto_enviado_llm` com os nomes presentes em `topico["nome"]` usando texto normalizado (`comparacao_texto.normalizar`), desconsiderando numerações de prefixo para casar itens mesmo quando o modelo omite numerais originais.
Fonte: scripts/validar_taxonomia.py:1-35, docs/adr/ADR-017-validacao-heuristica-de-para-taxonomia.md:10-30

A validação emite quatro diagnósticos principais: `topico_ausente` (item da fonte omitido pelo modelo), `topico_extra` (tópico extraído sem correspondente na fonte), `topico_nome_numerico` (quando o modelo inseriu apenas numerais isolados na ementa) e `topico_divergencia_leve` (paráfrases suaves com qualificadores acrescidos, tratadas com severidade informativa que não impede a aprovação do certame).
Fonte: scripts/validar_taxonomia.py:22-38, docs/adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md:10-25

Para reduzir custos de inferência e mitigar retrabalho, o módulo `src/taxonomia_extractor.py` aplica rotinas determinísticas locais de reconciliação antes da etapa de validação humana. A função `_reparar_nomes_numericos` resgata o texto factual da fonte para corrigir tópicos nomeados apenas com dígitos, enquanto `reinjetar_itens_ausentes` e `reinjetar_subitens_ausentes` reconstituem itens e subitens simples omitidos diretamente na árvore JSON, restabelecendo a fidelidade sem consumo adicional de tokens.
Fonte: src/taxonomia_extractor.py:160-263, docs/adr/ADR-021-reparo-local-nome-topico-numerico.md:12-35, docs/adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md:20-30

## Discursiva

Questão dissertativa, estudo de caso, redação ou peça técnica exigida em certames públicos, extraída dos cadernos de prova pela rotina de extração e gravada na tabela `discursivas`. Cada discursiva é indexada por concurso, caderno e número sequencial interno (prefixado com `D`, ex.: `D1`), mantendo enunciados integrais e propostas temáticas.
Fonte: src/sql/schema_estatisticas.sql:395-407, src/classificacao.py:65-68

As discursivas não participam do cômputo de pontuação líquida dos simulados objetivos nem integram a contagem de itens de Certo/Errado ou Múltipla Escolha. Elas são catalogadas na tabela de ligação `discursiva_no` para associação taxonômica à [Árvore Mestre](#árvore-mestre) e disponibilizadas em área própria de consulta e treino no site público. Quantitativos consolidados de discursivas constam em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: src/sql/schema_estatisticas.sql:427-435, docs/executivo/numeros.md:40

## Fila de Extração de Questões

Mecanismo relacional de controle assíncrono e rastreamento de pipeline gerenciado pela tabela `fila_extracao_questoes` no PostgreSQL. A tabela armazena a lista de PDFs de cadernos de prova e gabaritos baixados pelo downloader que aguardam extração de enunciados, alternativas e marcações definitivas pelo módulo `scripts/extrair_questoes.py`.
Fonte: src/sql/schema_estatisticas.sql:216-239, docs/adr/ADR-027-star-schema-estatisticas.md:15-33

O estado de cada documento é acompanhado pelas transições da coluna `status` (`'pendente'`, `'processando'`, `'concluido'` ou `'erro'`). O preenchimento da fila é idempotente, utilizando o hash SHA-256 do arquivo binário como chave natural única; o processo de carga (`src/stats_writer.py`) insere novos documentos mas nunca regride o status de itens já manipulados ou concluídos pelo consumidor de extração.
Fonte: src/stats_writer.py:320-370, docs/adr/ADR-027-star-schema-estatisticas.md:60-66

## Matéria, Assunto e Subassunto

Níveis taxonômicos estritos que formam a espinha dorsal hierárquica da [Árvore Mestre](#árvore-mestre), definidos pela tupla `NIVEIS = ("materia", "assunto", "subassunto")`. Cada nível cumpre uma função estrutural invariante no modelo de dados do projeto:

- **Matéria:** Raiz da hierarquia conceitual (`pai = None`), representando uma disciplina autônoma cobrada em concursos (como *Direito Constitucional* ou *Língua Portuguesa*). Nós de matéria recebem o prefixo `NM-`.
- **Assunto:** Nível intermediário temático subordinado diretamente a uma matéria obrigatória (`NIVEL_PAI["assunto"] = "materia"`), agrupando tópicos correlatos (como *Direitos Fundamentais* ou *Morfologia*). Nós de assunto recebem o prefixo `NA-`.
- **Subassunto:** Nível folha e unidade atômica de estudo do sistema, obrigatoriamente vinculado a um assunto pai (`NIVEL_PAI["subassunto"] = "assunto"`). Exemplos incluem *Habeas Corpus* ou *Classes de Palavras*. Nós de subassunto recebem o prefixo `NS-`.
Fonte: src/arvore.py:14-16, 73-76

Os identificadores estáveis de todos os nós são computados deterministicamente pela função `_gerar_id`, que concatena o prefixo textual do nível aos 10 primeiros dígitos hexadecimais do hash SHA-1 calculado sobre a chave unificada do identificador do pai com o nome do nó. Essa convenção impede colisões e garante que o mesmo ramo conceitual mantenha o mesmo identificador estável em qualquer reconstrução.
Fonte: src/arvore.py:73-76

O **Subassunto** opera como a menor fração indivisível de conhecimento do produto. É no subassunto que os itens de editais são mapeados (`mapeamentos`), que os apontamentos de questões convergem prioritariamente (`questao_no`) e que os motores de recomendação de estudo e cálculo de proficiência do usuário estruturam seus diagnósticos no site público. Para estatísticas detalhadas de nós ativos em cada nível, consulte [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: docs/adr/ADR-030-arvore-mestre-e-site-de-questoes.md:55-70, docs/executivo/numeros.md:46-50

## ME (Múltipla Escolha)

Formato de questão de concurso composto por enunciado seguido por 4 ou 5 alternativas consecutivas de resposta (letras de A a D ou de A a E), em contraste com o tradicional modelo de itens isolados para julgamento Certo/Errado (C/E) adotado majoritariamente pelo CEBRASPE.
Fonte: docs/adr/ADR-038-suporte-multipla-escolha-retrocompativel.md:10-25

No modelo relacional, o formato é estabelecido por item na tabela `questoes` por meio da coluna `tipo` (`'multipla_escolha'` versus `'certo_errado'`). As alternativas textuais de questões ME são persistidas em formato estruturado na coluna `alternativas` (`JSONB`), acompanhadas pela ampliação da checagem de gabarito para `CHECK (gabarito IN ('A', 'B', 'C', 'D', 'E', 'X'))` e pela regra de integridade `CHECK ((tipo = 'certo_errado') = (alternativas IS NULL))`.
Fonte: src/sql/schema_estatisticas.sql:265-281, 334-384

Para assegurar total estabilidade e retrocompatibilidade com o [Piloto (2025)](#piloto-2025), a função `calcular_hash_5d` adota estratégias distintas: para itens Certo/Errado calcula o SHA-1 estritamente sobre o enunciado normalizado; para questões de Múltipla Escolha, concatena o enunciado às alternativas serializadas em JSON determinístico (`sort_keys=True`). Na apuração de simulados, o formato ME confere +1 ponto por acerto e 0 pontos por erro (sem abatimento de pontos), preservando a regra de que questões anuladas são neutralizadas.
Fonte: src/questoes_writer.py:23-38, site/app/servicos/simulados_servico.py:64-100, docs/adr/ADR-038-suporte-multipla-escolha-retrocompativel.md:33-70

## Partição / Chunk

Unidade textual autônoma de conteúdo programático delimitada a partir do recorte da seção de `OBJETOS DE AVALIAÇÃO` do edital de abertura, dimensionada e estruturada para servir como unidade atômica de entrada (prompt) ao modelo de linguagem na Etapa 4 de extração.
Fonte: src/edital_parser.py:660-680, docs/adr/ADR-010-chunking-cargo-materia.md:10-21

O particionamento é processado pela função `dividir_por_cargo_e_materia` em `src/edital_parser.py`, suportando simultaneamente dois padrões de edital da banca: certames com matérias expressamente nomeadas para determinado cargo (gerando um chunk por disciplina sob o mesmo cargo) e certames com cargos de especialidade técnica ou médica cujo conteúdo é disposto diretamente sob a titulação do cargo (gerando um único chunk cuja matéria herda o nome do cargo). Matérias gerais sem cargo específico recebem `cargo = None`.
Fonte: src/edital_parser.py:669-680, 779-824

Marcadores institucionais de bloco (`CONHECIMENTOS BÁSICOS` ou `CONHECIMENTOS ESPECÍFICOS` combinados com nível de escolaridade) não formam chunks individuais, mas cumprem três papéis essenciais: atribuem `tipo_conhecimento` e `nivel` aos chunks subsequentes, resetam o cargo corrente para prevenir contaminações indevidas de escopo e delimitam fronteiras físicas contra aderências residuais de texto entre seções consecutivas.
Fonte: src/edital_parser.py:681-697, docs/adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md:12-25

## Piloto (2025)

Base de dados histórica de referência congelada, originada na Etapa 6 a partir de 5 concursos emblemáticos realizados pelo CEBRASPE no ano de 2025: `PF_25_ADM` (Polícia Federal — Administrativo), `TCU_25_TEFC` (Tribunal de Contas da União), `IBAMA_25` (Instituto Brasileiro do Meio Ambiente), `STM_25` (Superior Tribunal Militar) e `CD_25_NS` (Câmara dos Deputados — Nível Superior).
Fonte: src/inventario.py:35, tests/test_reconciliacao_inventario.py:119-122

O piloto atua como a âncora imutável de calibração de todo o pipeline de extração, inferência e modelagem. Ele possui invariantes numéricos estritos e congelados: a contagem de itens, de questões anuladas e de apontamentos da Etapa 5D, fixada na regra [P71](../tecnico/regras.md#p71) e conferida pelas checagens K22 a K24; os totais atuais estão em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: docs/tecnico/regras.md:810-816, docs/executivo/numeros.md:36, tests/test_reconciliacao_inventario.py:14, 814-830

Conforme estipulado na [Regra P71](../tecnico/regras.md#p71), qualquer modificação de código, ingestão de novos lotes históricos (2020 a 2026), refatoração de parsers ou reprocessamento do banco relacional é expressamente proibida de alterar as chaves compostas 5D, hashes ou apontamentos do piloto. Baterias automatizadas de auditoria (checagens K22 a K24) são executadas compulsoriamente antes e depois de qualquer gravação em banco, abortando qualquer operação caso seja detectado delta não planejado nos certames do piloto.
Fonte: docs/tecnico/regras.md:810-822, tests/test_reconciliacao_inventario.py:107-135

## Portão Humano (Gate)

Pontos de parada e homologação obrigatórios distribuídos ao longo do pipeline batch, estruturados para impor conferência humana mandatória antes que dados brutos, itens alucinados ou classificações incertas alcancem o banco relacional de produção (`scraper-cebraspe-db`) ou fiquem acessíveis aos usuários do site público.
Fonte: docs/guia/revisao-humana.md:50-60, docs/tecnico/pipeline.md:137-356

Por diretriz arquitetural central, agentes autônomos e rotinas de extração nunca realizam a aprovação final de conteúdos ([Regra P51](../tecnico/regras.md#p51), [ADR-028](../adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md)). Os marcos operacionais do pipeline definem os seguintes portões canônicos:

- **P3 (Aprovação de Taxonomia de Edital):** O operador humano analisa os relatórios visuais estáticos e o banco [Datasette de Revisão](#datasette-de-revisão). A homologação ocorre gravando explicitamente `status_revisao_humana = 'APROVADO...'` no arquivo JSON em `revisao_piloto/`. Até que esse registro exista, o concurso é mantido com `status_revisao = 'pendente'` no PostgreSQL e permanece invisível nas views analíticas públicas.
- **P5 (Conferência de Carga e Integridade de Questões):** Conferência manual após a ingestão de cadernos de questões, executando baterias de consultas SQL de integridade (consultas a-e) e cotejando uma amostra de itens diretamente contra os PDFs de aplicação para checar comandos de grupo, textos-base e preservação das invariantes do piloto.
- **P6 / P7 (Curadoria Estrutural da Árvore Mestre):** Avaliação de propostas estruturais emitidas pelo detector de dispersão e pelo módulo LLM. O operador analisa relatórios HTML de divergência e aprova ou rejeita pontualmente novos nós ou fusões taxonômicas via CLI (`scripts/curar_arvore.py`), sendo vedada qualquer aplicação em bloco por agente.
- **P8 / P9 (Curadoria da Classificação de Questões na Árvore):** Revisão humana de questões classificadas com grau de confiança média ou baixa, ou que tenham ficado sem nó aderente na árvore mestre, homologadas caso a caso pelo comando `scripts/curar_classificacao.py`.
Fonte: docs/tecnico/pipeline.md:137-140, 220-234, 263-266, 294-297, 341-356, docs/adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md:20-25, src/stats_writer.py:190-196

## Simulado e Pontuação Líquida CEBRASPE

Módulo interativo de treinamento do site público concebido para reproduzir integralmente a experiência real de resolução de um concurso público sob as regras da banca CEBRASPE. O simulado monta a prova na ordem fidedigna de aplicação do caderno oficial, agrupando primeiro as questões de conhecimentos básicos seguidas pelas questões de conhecimentos específicos.
Fonte: site/app/servicos/simulados_servico.py:36-54, site/app/repositorio/simulados_repo.py:9-14

A apuração de desempenho segue a fórmula clássica de pontuação líquida estabelecida nos editais do CEBRASPE para exames no formato Certo/Errado (C/E):
- Cada item respondido em concordância com o gabarito oficial soma **+1 ponto** líquido;
- Cada item respondido em discordância com o gabarito oficial subtrai **-1 ponto** líquido (um item incorreto anula um item correto);
- Itens deixados em branco (não respondidos) atribuem **0 pontos**;
- Para itens eventuais no formato Múltipla Escolha (ME), o acerto atribui **+1 ponto** e o erro atribui **0 pontos** (sem penalidade de decréscimo).
Fonte: site/app/servicos/simulados_servico.py:64-100, docs/adr/ADR-038-suporte-multipla-escolha-retrocompativel.md:64-67

Itens oficialmente anulados pela banca examinadora são neutralizados no cálculo da nota líquida: não pontuam, não sofrem desconto e são subtraídos da nota máxima possível da prova (`nota_maxima = total_itens - anuladas`). Ao consultar simulados finalizados, a pontuação é recalculada dinamicamente contra o gabarito corrente do banco de dados, garantindo que retificações posteriores de gabaritos reflitam de forma imediata e justa no histórico do estudante.
Fonte: site/app/servicos/simulados_servico.py:87-99, 201-218

## Star Schema e Dimensões

Modelo dimensional relacional implementado no banco dedicado PostgreSQL (`scraper-cebraspe-db`), otimizado para análises OLAP de incidência de conteúdo programático e suporte de alta performance às consultas com filtros facetados da aplicação web. O modelo separa estritamente tabelas de fatos volumosos de dimensões descritivas desnormalizadas com chaves naturais estáveis.
Fonte: src/sql/schema_estatisticas.sql:1-10, docs/adr/ADR-027-star-schema-estatisticas.md:34-51

O esquema organiza os dados nas seguintes entidades fundamentais:
- **Dimensões:** `dim_orgao` (órgãos públicos contratantes), `dim_ano` (ano cronológico do concurso), `dim_cargo` (cargos previstos nos editais), `dim_materia` (disciplinas normalizadas, acompanhadas pelas flags booleanas `nocoes` e `nome_de_cargo`), `dim_topico` e `dim_subtopico` (tópicos e subtópicos unificados por matéria via `comparacao_texto.normalizar()`).
- **Tabelas de Fatos:** `concursos` (registro do certame e metadados de carga), `cargos_editais` (cargos específicos ofertados no edital), `taxonomia_itens` (grão atômico de 1 tópico por chunk de edital), `provas` (metadados dos cadernos), `questoes` (itens de prova objetivos C/E e ME) e `discursivas`.
- **Pontes Relacionais:** `provas_cargos` (associação N:1 ou 1:1 entre cadernos e cargos), `materia_no`, `topico_no`, `subtopico_no` (associação N:N entre os itens do edital e a árvore mestre) e `questao_no` (amarração entre itens de prova e nós da árvore mestre).
Fonte: src/sql/schema_estatisticas.sql:22-160, 204-281, 411-426

A ingestão de dados realizada pelo módulo `src/stats_writer.py` opera de forma estritamente idempotente. As dimensões são atualizadas por upsert baseado em suas chaves naturais. Por sua vez, todos os fatos e pontes taxonômicas de um certame são substituídos de maneira atômica dentro de uma única transação de banco de dados (`DELETE` seguido de `INSERT`), eliminando qualquer risco de tópicos ou apontamentos órfãos quando uma reextração taxonômica for processada.
Fonte: src/stats_writer.py:10-45, 997-1088, docs/adr/ADR-027-star-schema-estatisticas.md:52-66

## Texto-Base

Fragmento textual, crônica, artigo de lei, excerto doutrinário, tabela informativa ou diagrama esquemático publicado no caderno de prova antes de uma sequência de itens objetivos que compartilham a mesma fundamentação de leitura.
Fonte: src/sql/schema_estatisticas.sql:249-256, docs/adr/ADR-034-fidelidade-ao-caderno-e-filtros.md:45-60

Os textos-base são catalogados na tabela `textos_base` e vinculados às questões correspondentes pela chave estrangeira `questoes.texto_base_id`. Para manter fidelidade tipográfica ao caderno original da banca, os parágrafos são reconstituídos através da medição de recuo horizontal da primeira linha em relação à margem da coluna de texto, enquanto ilustrações, fórmulas e tabelas complexas são capturadas como recortes vetoriais gráficos em formato PNG, referenciadas pelo campo estruturado `figuras`.
Fonte: src/sql/schema_estatisticas.sql:249-256, 263, docs/adr/ADR-034-fidelidade-ao-caderno-e-filtros.md:65-85

---

## Referências e Regras Relacionadas

- Regra de aprovação exclusivamente humana: [P51 - Decisão Humana na Árvore](../tecnico/regras.md#p51)
- Regra de imutabilidade da base piloto: [P71 - Imutabilidade do Piloto de 2025](../tecnico/regras.md#p71)
- Decisão sobre arquitetura taxonômica: [ADR-030 - Árvore Mestre e Site de Questões](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)
- Decisão sobre extração de cadernos e gabaritos: [ADR-031 - Extração de Questões dos Cadernos](../adr/ADR-031-extracao-questoes-cadernos.md)
- Decisão sobre classificação de questões na árvore: [ADR-032 - Classificação de Questões na Árvore Mestre](../adr/ADR-032-classificacao-questoes-arvore.md)
- Decisão sobre fidelidade ao caderno de prova: [ADR-034 - Fidelidade ao Caderno e Filtros](../adr/ADR-034-fidelidade-ao-caderno-e-filtros.md)
- Decisão sobre suporte a múltipla escolha: [ADR-038 - Suporte a Múltipla Escolha Retrocompatível](../adr/ADR-038-suporte-multipla-escolha-retrocompativel.md)
- Indicadores quantitativos consolidados: [docs/executivo/numeros.md](../executivo/numeros.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
