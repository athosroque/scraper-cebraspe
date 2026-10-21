# Arquitetura do Sistema — Scraper CEBRASPE

Este documento detalha o desenho arquitetural, os componentes e o pipeline de processamento do **Scraper CEBRASPE**, responsável pela coleta, download, extração estruturada de editais e cadernos de provas, governança taxonômica em árvore mestre e disponibilização de um site público de resolução de questões com métricas de incidência.

---

## 1. Visão Geral

O sistema é concebido como um ecossistema desacoplado que une um pipeline batch analítico a uma aplicação web interativa em tempo real. Ele se integra ao ambiente do **Homelab**, estruturado da seguinte forma:

- **Site Público de Questões (Objetivo do Produto):** Plataforma web voltada para estudantes de concursos (estilo Gran Questões), focada no acervo do CEBRASPE. Permite filtragem avançada, resolução de questões fiéis aos cadernos originais, simulados cronometrados com correção clássica da banca (+1 acerto, -1 erro, 0 em branco) e cruzamento de incidência edital × prova ([ADR-030](adr/ADR-030-arvore-mestre-e-site-de-questoes.md), [ADR-033](adr/ADR-033-site-publico-stack-e-deploy.md)).
- **PostgreSQL 16 Próprio (`scraper-cebraspe-db`):** Banco relacional dedicado do projeto, executado em contêiner Docker isolado (`docker-compose.yml`), com volume dedicado `scraper_cebraspe_pgdata` e porta local restrita a `127.0.0.1:5435` (ou rede interna `homelab_default:5432`). É estritamente independente de outros projetos (como o `study-rag-agent`); cruzamentos futuros serão efetuados por chaves naturais normalizadas, sendo vedado acoplamento via chaves estrangeiras externas ou dependências de schemas remotos ([ADR-026](adr/ADR-026-banco-postgres-proprio.md)).
- **Inferência LLM (OpenRouter) & Telemetria (Langfuse):** Chamadas HTTP REST diretas ao endpoint do OpenRouter para o modelo `z-ai/glm-5.3-flash`, centralizadas no módulo `src/llm_openrouter.py` sem proxies locais ou runtimes intermediários ([ADR-011](adr/ADR-011-extracao-llm-requests-direto.md)). Observabilidade e rastreamento de custos ponta a ponta no Langfuse via SDK oficial v4 (OpenTelemetry), compartilhando o mesmo projeto e diferenciando etapas pelo nome do trace ([ADR-023](adr/ADR-023-migracao-langfuse-sdk-oficial.md)).
- **Roteamento Reverso e SSO (Traefik + Cloudflare Tunnel):** O Traefik gerencia o roteamento interno e a terminação HTTPS na rede `homelab_default`, expondo três pontos de acesso:
  1. `datasette.projetoathos.com.br` (porta 8011): revisão humana interna protegida por Cloudflare Access SSO ([ADR-015](adr/ADR-015-revisao-datasette-traefik.md));
  2. `questoes-dev.projetoathos.com.br` (porta 8012): aplicação web pública do site de questões ([ADR-033](adr/ADR-033-site-publico-stack-e-deploy.md));
  3. `docs.projetoathos.com.br` (porta 8013): site de documentação técnica e executiva em MkDocs ([ADR-040](adr/ADR-040-site-documentacao-mkdocs.md)).

---

## 2. Diagramas de Arquitetura e Pipeline

- **Arquitetura de Contêineres e Contexto C4:** A visão sistêmica de contêineres (Pipeline, PostgreSQL, Datasette, Site FastAPI, Bot Telegram, MkDocs, Traefik, OpenRouter e Google OAuth) pode ser consultada no diagrama interativo em [Visão Executiva — Arquitetura](executivo/arquitetura.md).
- **Pipeline e Grafo de Etapas:** O fluxo detalhado de dependências entre comandos, etapas de LLM, artefatos gerados e portões humanos é gerado a partir do registro técnico em Python (`src/registro/`) e pode ser consultado em [Pipeline e etapas](tecnico/pipeline.md) ([ADR-041](adr/ADR-041-registro-e-paginas-geradas.md)).

---

## 3. Componentes Principais

### 3.1. Crawler & Descoberta (`src/spider.py`)
- **Ponto de Entrada e Situações:** Rastreia concorrentemente as listagens `/concursos/encerrado`, `/concursos/em-andamento`, `/concursos/inscricoes-abertas` e `/concursos/novos`, priorizando certames encerrados (`PRIORIDADE_SITUACAO`) e aceitando execução direcionada via CLI `--slug <SLUG>` ([ADR-002](adr/ADR-002-fonte-primaria-concursos-encerrados.md)).
- **Resolução de Hrefs:** URLs relativas extraídas dos cards HTML são resolvidas via `urljoin(page.url, href)` para prevenir descartes silenciosos ([ADR-008](adr/ADR-008-resolucao-href-relativo.md)).
- **Extração por Slug:** O ano (`_YY` ou `_YYYY`) e o prefixo do órgão são extraídos deterministicamente do slug da URL por regex (`PADRAO_ANO_SLUG`), ignorando o texto visível genérico dos botões ([ADR-001](adr/ADR-001-filtro-ano-slug-url.md), [ADR-006](adr/ADR-006-extracao-orgao-slug.md)).
- **Governança de Escopo:** O crawler consulta `inventario/exclusoes.json` para ignorar certames fora de escopo (como vestibulares ou seleções sem edital/prova) e classifica os links de PDF por meio de `src.inventario` ([ADR-037](adr/ADR-037-escopo-do-site-no-inventario.md)).
- **Isolamento de Falhas e Idempotência:** Concursos processados com sucesso são registrados em `data/processed_concursos.json` apenas após a finalização bem-sucedida de todos os downloads, com isolamento de exceções por concurso ([ADR-005](adr/ADR-005-idempotencia-registro-json.md), [ADR-013](adr/ADR-013-ligacao-spider-downloader.md)).

### 3.2. Downloader com Duplo Dedup (`src/downloader.py`)
- **Validação de Integridade:** Valida a presença obrigatória dos magic bytes `%PDF-` nos primeiros 4 bytes do arquivo binário, descartando respostas HTTP 200 com HTML de erro.
- **Desduplicação em 2 Níveis:**
  1. *Camada 1 (Rede):* O manifesto `.manifest.json` mapeia URLs já baixadas para evitar requisições redundantes.
  2. *Camada 2 (Armazenamento):* O hash SHA-256 do binário impede o salvamento de arquivos duplicados no disco ([ADR-007](adr/ADR-007-dedup-download-dupla-camada.md)).
- **Isolamento de Worktrees:** Detecta automaticamente execuções em worktrees isoladas e redireciona o `DATA_DIR` para a raiz do repositório principal, mantendo os arquivos físicos unificados.
- **Estrutura no Disco:**
  ```text
  data/
  └── <ano>/
      └── CEBRASPE/
          └── <orgao_slug>/
              ├── .manifest.json
              ├── Editais/
              ├── Provas/
              ├── Gabaritos/
              └── provas_texto_link.json
  ```

### 3.3. Parser de Editais (`src/edital_parser.py`)
- **Extração Seletiva:** Isola o conteúdo programático a partir do marcador flexível `MARCADOR_INICIO_SECAO = "OBJETOS DE AVALIAÇÃO"` até `MARCADOR_FIM_SECAO = "ANEXO I"` ([ADR-009](adr/ADR-009-recorte-objetos-avaliacao.md), [ADR-024](adr/ADR-024-coleta-camara-deputados-refinamentos-parser.md)).
- **Chunking Hierárquico (Cargo + Matéria):** Suporta certames administrativos com disciplinas segregadas e cargos de especialidade técnica unificados ([ADR-010](adr/ADR-010-chunking-cargo-materia.md)).
- **Classificação por Bloco:** Cabeçalhos de bloco (`CONHECIMENTOS BÁSICOS/ESPECÍFICOS`) definem `tipo_conhecimento` e `nivel`, reconhecendo submatérias romanas e padrões de restrição a subconjuntos de cargos ([ADR-020](adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-028](adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md)).
- **Higienização:** Remove blocos de assinaturas administrativas finais e exclui previamente tópicos revogados por editais de retificação.

### 3.4. Extrator de Taxonomia via LLM (`src/taxonomia_extractor.py` & `src/llm_openrouter.py`)
- **Conexão Direta e Modelo Padronizado:** Requisições REST diretas ao endpoint do OpenRouter utilizando o modelo `z-ai/glm-5.3-flash`, com `MAX_TOKENS = 12000`, `TIMEOUT = 120s`, `TEMPERATURA = 0.1` e teto de reasoning em 3.000 tokens ([ADR-011](adr/ADR-011-extracao-llm-requests-direto.md), [ADR-016](adr/ADR-016-retry-maiores-tokens-llm.md)).
- **Reparos Locais Determinísticos Sem Custo de Tokens:**
  - Reparo de nomes puramente numéricos consultando o texto-fonte original (`extrair_itens_numerados`) ([ADR-021](adr/ADR-021-reparo-local-nome-topico-numerico.md)).
  - Reinjeção de itens e subitens omitidos pelo modelo (`reinjetar_itens_ausentes` e `reinjetar_subitens_ausentes`) ([ADR-025](adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)).
- **Classificação Granular de Falhas e Retry:** Mapeamento explícito de exceções de rede e validação (`falha_timeout`, `falha_rate_limit`, `falha_parse_json`, etc.) com retentativas e backoff exponencial ([ADR-022](adr/ADR-022-classificacao-erros-chamada-openrouter.md)).
- **Trilha de Auditoria:** Gravação em disco do par `<edital>.json` e `<edital>.auditoria.json`, preservando o texto exato submetido ao modelo e seus limites de página ([ADR-014](adr/ADR-014-trilha-auditoria-parser-extractor.md)).

### 3.5. Validação Heurística e Revisão Humana
- **Orquestrador de Artefatos (`scripts/atualizar_revisao.py`):** Executa em cadeia contínua: validação de-para, relatórios HTML, atualização determinística da árvore mestre, classificação visual, reconstrução do SQLite `revisao.db`, reinício do contêiner Datasette, gravação no Postgres analítico via `stats_writer` e consumo da fila de questões ([ADR-019](adr/ADR-019-pipeline-automatico-artefatos-revisao.md), [ADR-027](adr/ADR-027-star-schema-estatisticas.md), [ADR-031](adr/ADR-031-extracao-questoes-cadernos.md)).
- **Validação De-Para (`scripts/validar_taxonomia.py`):** Confronta os tópicos do texto-fonte contra os tópicos extraídos pelo LLM, emitindo alertas estruturados ([ADR-017](adr/ADR-017-validacao-heuristica-de-para-taxonomia.md)).
- **Relatório Estático Comparativo (`scripts/gerar_relatorio_revisao.py`):** Gera páginas HTML em duas colunas (texto-fonte com `<mark>` à esquerda e árvore taxonômica à direita) ([ADR-018](adr/ADR-018-relatorio-html-e-extensao-schema-revisao.md)).
- **Datasette de Auditoria (`scripts/gerar_db_datasette.py`):** SQLite descartável `revisao.db` com busca FTS5, atuando como interface somente-leitura da Etapa 4 protegida por Cloudflare Access SSO ([ADR-015](adr/ADR-015-revisao-datasette-traefik.md)).

### 3.6. Extração de Questões e Gabaritos (`src/questoes_extractor.py`)
- **Consumo de Cadernos:** Processa cadernos de prova e gabaritos oficiais registrados na fila `fila_extracao_questoes` ([ADR-031](adr/ADR-031-extracao-questoes-cadernos.md)).
- **Formatos Suportados:** Extração robusta para questões no formato Certo/Errado e múltipla escolha retrocompatível (4 ou 5 alternativas), identificando anulações, alterações de gabarito e enunciados discursivos ([ADR-038](adr/ADR-038-suporte-multipla-escolha-retrocompativel.md)).
- **Fidelidade ao Caderno:** Preserva a ordem original, blocos de texto-base e vínculos com os cadernos oficiais ([ADR-034](adr/ADR-034-fidelidade-ao-caderno-e-filtros.md)).

### 3.7. Árvore Mestre de Conceitos e Curadoria (`src/arvore.py` & `canonico/arvore.json`)
- **Fonte da Verdade Taxonômica:** O arquivo `canonico/arvore.json` é a única fonte da verdade para a taxonomia do projeto, organizado estritamente em `materia` → `assunto` → `subassunto` com identificadores estáveis derivados de SHA-1 ([ADR-030](adr/ADR-030-arvore-mestre-e-site-de-questoes.md)).
- **Imutabilidade e Fusões:** Nós fundidos preservam histórico através de `fundido_em`, sendo resolvidos de forma encadeada e livre de ciclos via `resolver_no`.
- **Ciclo de Governança:** Semeadura determinística inicial (`semear_arvore.py`), proposição automatizada por regras ou LLM (`propor_arvore.py`) e curadoria transacional via CLI (`scripts/curar_arvore.py`). Acesso ao JSON restrito às funções do módulo `src/arvore.py`.

### 3.8. Classificador de Questões na Árvore (`src/classificador_questoes.py`)
- **Associação com a Árvore Mestre:** Classifica as questões extraídas dos cadernos diretamente nos nós de subassunto da árvore mestre ([ADR-032](adr/ADR-032-classificacao-questoes-arvore.md)).
- **Estratégia Híbrida:** Prioriza regras determinísticas de casamento exato por disciplina e termos de edital; quando inconclusivo, recorre à inferência com LLM utilizando chave escopada (`OPENROUTER_KEY_CLASSIFICACAO_QUESTOES`).

### 3.9. Star Schema e Estatísticas Analíticas (`src/stats_writer.py`)
- **Modelagem Relacional:** Star schema no schema `public` do PostgreSQL composto por dimensões (`dim_materia`, `dim_topico`, `dim_orgao`, `dim_cargo`, `dim_ano`) e tabelas de fatos e pontes (`no_arvore`, `materia_no`, `topico_no`, `subtopico_no`, `questoes`, `questoes_arvore`) ([ADR-027](adr/ADR-027-star-schema-estatisticas.md)).
- **Views Analíticas:** Views recursivas `vw_no_caminho`, mapeamento de conteúdo programático `vw_arvore_edital_por_cargo`, incidência de editais `vw_edital_cobra_*` e cálculo de incidência empírica em dois níveis nas provas via função `fn_prova_cobra` ([ADR-039](adr/ADR-039-incidencia-em-dois-niveis.md)).

### 3.10. Aplicação Web Pública e API (`site/`)
- **Stack:** FastAPI, Jinja2, HTMX, Alpine.js e Tailwind CSS compilado, organizada em três camadas (`repositorio/`, `servicos/`, `api/` e `web/`) ([ADR-033](adr/ADR-033-site-publico-stack-e-deploy.md)).
- **Funcionalidades:** Busca e resolução paginada de questões, filtros por facetas, simulados cronometrados com pontuação CEBRASPE (+1 acerto, -1 erro, 0 branco), exibição no formato Gran e área autenticada do usuário ([ADR-034](adr/ADR-034-fidelidade-ao-caderno-e-filtros.md), [ADR-035](adr/ADR-035-card-e-filtros-formato-gran.md)).
- **Schema `app` no PostgreSQL:** Tabelas transacionais isoladas do pipeline (`usuarios`, `respostas`, `simulado`, `simulado_item`, `cadernos_favoritos`), com autenticação Google OAuth (Authlib) e cookie de sessão assinado com proteção CSRF.

### 3.11. Inventário de Concursos e Escopo (`inventario/`)
- **Controle Central de Certames:** Arquivos `concursos.jsonl`, `anos.json` e relatórios quantitativos que definem os concursos mapeados pelo projeto.
- **Exclusões Homologadas:** O arquivo `inventario/exclusoes.json` documenta explicitamente cada concurso rejeitado ou fora de escopo com sua respectiva categoria técnica e justificativa ([ADR-037](adr/ADR-037-escopo-do-site-no-inventario.md)).

### 3.12. Bot de Notificações e Interações (Telegram — `src/telegram_bot.py`)
- **Assistente Técnico:** Bot assíncrono para alertas do pipeline e consultas operacionais via `httpx`.
- **Inferência e Segurança:** Utiliza chave dedicada `OPENROUTER_KEY_TELEGRAM`, telemetria no Langfuse (`cebraspe-telegram-bot`) e validação de remetente restrita a `TELEGRAM_ALLOWED_USER_ID`.

### 3.13. Documentação Viva e Registro Técnico (`src/registro/` & MkDocs)
- **Documentação Baseada em Código:** Metadados de etapas, regras e comandos registrados em Python (`src/registro/`), gerando páginas técnicas automatizadas via `scripts/gerar_docs.py` ([ADR-041](adr/ADR-041-registro-e-paginas-geradas.md)).
- **Site MkDocs Material:** Servido via contêiner Nginx na porta 8013, validado com `mkdocs build --strict` no pipeline de testes ([ADR-040](adr/ADR-040-site-documentacao-mkdocs.md)).

---

## 4. Segurança e Isolamento

1. **Credenciais e Segregação de Chaves:** Todas as credenciais residem exclusivamente no `.env` (ignorado pelo git). O OpenRouter utiliza chaves separadas por escopo de etapa (`OPENROUTER_KEY_TAXONOMIA_EDITAL`, `_SINONIMOS`, `_CURADORIA_ARVORE`, `_CLASSIFICACAO_QUESTOES`, `_TELEGRAM`).
2. **Segregação de Roles no PostgreSQL:**
   - `cebraspe`: proprietário do banco, utilizado exclusivamente pelas rotas de ingestão e pipeline batch;
   - `site_leitura`: permissão estrita de `SELECT` nas views e tabelas analíticas do schema `public`;
   - `site_app`: leitura no schema `public` e permissões de `SELECT`, `INSERT`, `UPDATE`, `DELETE` nas tabelas do schema transacional `app`.
3. **Exposição de Rede e Proteção da Porta do Banco:** A porta do contêiner `scraper-cebraspe-db` é vinculada exclusivamente ao endereço local `127.0.0.1:5435` (nunca `0.0.0.0`), prevenindo exposição acidental. O contêiner Datasette e os roteadores do site operam isolados na rede virtual do Docker (`homelab_default`), com tráfego externo mediado pelo Traefik e Cloudflare Access SSO.
4. **Proteção Web e Privacidade (LGPD):** A aplicação web adota cookies assinados com `HttpOnly`, `SameSite=Lax`, verificação mandatória de token CSRF para todas as requisições com mutação e suporte a exclusão integral de conta e histórico de respostas em cascata via `/conta/apagar`.
5. **Limitação de Taxa e Stealth no Crawler:** O crawler Playwright aplica intervalos orgânicos de espera (`stealth_wait`) e User-Agents reais para mitigar riscos de bloqueio ou sobrecarga no portal de origem.
