# ADR-018: Relatório HTML de Página Única e Extensão do Schema de Revisão (`alertas_validacao`)

## Status
Aceito (schema estendido pelo [ADR-020](ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md): concurso, classificação por chunk e tabela `cargos`)

## Data
2026-09-21

## Contexto

O ADR-015 resolveu a navegação/busca do checkpoint de revisão via Datasette,
mas deixou uma lacuna: comparar o texto do edital com a taxonomia extraída
exige alternar entre a tabela `chunks` (texto-fonte) e a tabela
`taxonomia_topicos` (extração), filtrando manualmente por `chunk_id` a cada
vez — o usuário relatou que esse de-para manual é trabalhoso. O renderizador
tabular padrão do Datasette não faz layout de duas colunas nem destaque de
texto; resolver isso dentro do próprio Datasette exigiria um plugin de
template customizado.

Em paralelo, o ADR-017 passou a produzir `<edital>.validacao.json` com
alertas heurísticos — que também precisavam de um lugar consultável (tanto
via SQL/Datasette quanto visualmente).

Esta decisão registra **duas mudanças relacionadas**: (1) um relatório HTML
estático de página única por edital, e (2) a extensão do schema SQLite do
ADR-015 para incluir os alertas do ADR-017. As duas são documentadas juntas
porque a extensão de schema existe para alimentar a leitura tabular/SQL dos
mesmos alertas que o relatório destaca visualmente.

> **Nota para migração futura de banco:** este ADR documenta o schema
> completo (DDL, chaves, nulidade) porque o SQLite atual (`revisao.db`) é
> **descartável e inteiramente derivado dos arquivos JSON em
> `revisao_piloto/`** (`<edital>.json` + `<edital>.auditoria.json` +
> `<edital>.validacao.json`) — nunca a fonte de verdade. Ao trocar de banco,
> a migração real é **reescrever `scripts/gerar_db_datasette.py`** para
> gravar no novo destino a partir dos mesmos JSONs (mesmas chaves de junção,
> mesmas colunas); não existe estado em `revisao.db` que precise ser
> "migrado" no sentido de preservado — o script já reconstrói tudo do zero a
> cada execução (ver ADR-015, "Reconstrução completa"). Ver seção
> **Guia para troca de banco** no fim deste documento.

## Decisão

### 1. `scripts/gerar_relatorio_revisao.py` (novo)

Lê o mesmo trio de JSONs por edital (`<edital>.json`, `<edital>.auditoria.json`,
`<edital>.validacao.json` — este último opcional) e gera HTML estático puro
(stdlib `html.escape` + f-strings, **sem Jinja2** — mesma filosofia de stack
enxuta do resto do projeto, ver ADR-011):

- `revisao_piloto/relatorio/<edital-stem>.html` — um arquivo por edital.
  Cabeçalho com totais (`total_chunks`, `extraidos_com_sucesso`, `falhas`,
  `total_alertas`); um card por chunk (ordenado por `chunk_index`) em
  **duas colunas**: esquerda = `texto_enviado_llm` com os itens sinalizados
  como `topico_ausente` destacados via `<mark>` (usando `posicao_item` do
  ADR-017 para apontar a ocorrência exata, não o número); direita = árvore
  matéria → tópico → subtópicos extraída. Alertas do chunk aparecem como
  banner no topo do card antes das duas colunas.
- `revisao_piloto/relatorio/index.html` — lista todos os editais com
  contagem de chunks/alertas e link para o relatório individual.
- Chunk com `status == "falha"` renderiza aviso "sem taxonomia" em vez das
  duas colunas (não há `taxonomia_extraida` pra mostrar).
- Edital sem `.auditoria.json` (formato legado) é pulado com log de aviso —
  sem `texto_enviado_llm` não há texto-fonte pra exibir.

CLI: `python -m scripts.gerar_relatorio_revisao [revisao_piloto_dir]`.

### 2. Exposição via Datasette (`docker-compose.yml`)

```yaml
command:
  - datasette
  - serve
  - /data/revisao.db
  - --host
  - "0.0.0.0"
  - --port
  - "8001"
  - --setting
  - sql_time_limit_ms
  - "5000"
  - --static
  - relatorio:/data/relatorio
```

`/data` já era o mount `./revisao_piloto:/data:ro` (ADR-015); como
`relatorio/` é gerado **dentro de** `revisao_piloto/`, nenhum volume novo
foi necessário — só a flag nativa `--static` do próprio Datasette, sem
plugin. Como a montagem é `:ro` (somente-leitura), os relatórios HTML
são sempre gerados externamente no host via script e apenas lidos pelo
contêiner. URL final: `https://datasette.projetoathos.com.br/relatorio/index.html`,
reaproveitando Traefik + Cloudflare Tunnel + SSO já configurados (ADR-015).
Mudança de `command` exige **recriar** o container (`docker compose up -d`),
não só `restart` — documentado no topo do `docker-compose.yml` e em
CLAUDE.md §9.2.

### 3. Extensão do schema (`scripts/gerar_db_datasette.py`)

`_carregar_par` passou a também carregar `<edital>.validacao.json`
(opcional, mesmo padrão condicional já usado para `.auditoria.json`).

**Nova tabela `alertas_validacao`** (DDL real gerada por `sqlite_utils`,
capturada de `revisao.db`):

```sql
CREATE TABLE "alertas_validacao" (
   "id" INTEGER PRIMARY KEY,
   "edital" TEXT REFERENCES "editais"("edital"),
   "chunk_id" INTEGER REFERENCES "chunks"("id"),
   "chunk_index" INTEGER,
   "cargo" TEXT,
   "materia" TEXT,
   "tipo" TEXT,
   "numero_item" TEXT,
   "texto_item_origem" TEXT,
   "topico_nome_extraido" TEXT
)
```

- Uma linha por objeto em `validacao["alertas"]` (ver ADR-017 para o schema
  do JSON de origem). `posicao_item` do JSON **não** é persistido nesta
  tabela — é só um detalhe de implementação do destaque no HTML (item 1),
  sem valor de consulta SQL.
- `chunk_id` é resolvido via `chunk_id_by_index[chunk_index]` (o mesmo dict
  retornado por `_inserir_chunks_com_auditoria`/`_inserir_chunks_sem_auditoria`
  — chave de junção herdada do ADR-014); fica `NULL` se `chunk_index` for
  `None` (alerta sem chunk associável — não ocorre na prática atual, mas o
  schema permite).
- Só é populada quando `<edital>.validacao.json` existe para o edital
  (mesmo padrão condicional de `auditoria`) — edital sem validação rodada
  simplesmente não aparece nesta tabela, sem erro.

**Coluna nova em `editais`:**

```sql
ALTER TABLE editais ADD COLUMN total_alertas INTEGER;
-- (não é literalmente um ALTER — a tabela é recriada do zero a cada run,
--  ver "Reconstrução completa" no ADR-015)
```

Populada de `validacao["total_alertas"]` quando o arquivo existe, `NULL`
caso contrário — permite ver de cara, na tabela `editais`, quais editais
têm pendência de revisão sem abrir mais nada.

> [!NOTE]
> O bloco DDL abaixo registra o schema no momento da aprovação do ADR-018. Para as colunas de classificação (`concurso_slug`, `nivel`, `tipo_conhecimento`, etc.) e a tabela `cargos` incorporadas posteriormente, consulte a [Atualização — ADR-020](#atualização--adr-020-2026-09-21) ao final deste documento.

**Schema completo atualizado de `revisao.db`** (todas as tabelas, para
referência única):

```sql
CREATE TABLE "editais" (
   "edital" TEXT PRIMARY KEY,
   "total_chunks" INTEGER,
   "extraidos_com_sucesso" INTEGER,
   "falhas" INTEGER,
   "status_revisao_humana" TEXT,
   "pdf_total_paginas" INTEGER,
   "pdf_total_chars" INTEGER,
   "marcador_fim_encontrado" INTEGER,
   "offset_inicio_char" INTEGER,
   "offset_fim_char" INTEGER,
   "chars_secao" INTEGER,
   "chars_descartados_do_pdf" INTEGER,
   "origem_json" TEXT,
   "origem_auditoria_json" TEXT,
   "total_alertas" INTEGER
);

CREATE TABLE "chunks" (
   "id" INTEGER PRIMARY KEY,
   "edital" TEXT REFERENCES "editais"("edital"),
   "chunk_index" INTEGER,
   "cargo" TEXT,
   "materia" TEXT,
   "offset_inicio_secao" INTEGER,
   "offset_fim_secao" INTEGER,
   "chars" INTEGER,
   "texto_enviado_llm" TEXT,
   "status" TEXT
);

CREATE TABLE "taxonomia_topicos" (
   "id" INTEGER PRIMARY KEY,
   "edital" TEXT,                              -- sem FK declarada (ver nota abaixo)
   "chunk_id" INTEGER REFERENCES "chunks"("id"),
   "cargo" TEXT,
   "materia_chunk" TEXT,
   "materia_extraida" TEXT,
   "topico_nome" TEXT,
   "topico_ordem" INTEGER
);

CREATE TABLE "taxonomia_subtopicos" (
   "id" INTEGER PRIMARY KEY,
   "topico_id" INTEGER REFERENCES "taxonomia_topicos"("id"),
   "subtopico_nome" TEXT,
   "subtopico_ordem" INTEGER
);

CREATE TABLE "alertas_validacao" (
   "id" INTEGER PRIMARY KEY,
   "edital" TEXT REFERENCES "editais"("edital"),
   "chunk_id" INTEGER REFERENCES "chunks"("id"),
   "chunk_index" INTEGER,
   "cargo" TEXT,
   "materia" TEXT,
   "tipo" TEXT,
   "numero_item" TEXT,
   "texto_item_origem" TEXT,
   "topico_nome_extraido" TEXT
);
```

**FTS5** (via `sqlite_utils.enable_fts`, `create_triggers=False` — populado
só na criação, aceitável porque o banco é sempre reconstruído do zero):
`chunks_fts` sobre `(texto_enviado_llm, materia, cargo)`;
`taxonomia_topicos_fts` sobre `(topico_nome, materia_extraida, materia_chunk)`;
`taxonomia_subtopicos_fts` sobre `(subtopico_nome)`. `alertas_validacao` **não**
tem FTS habilitado (volume baixo, campos já curtos o bastante pra `LIKE`).

**Nota de consistência conhecida:** `taxonomia_topicos.edital` é gravado
como coluna solta sem `REFERENCES` declarado (decisão original do ADR-015,
mantida sem alteração aqui) — inconsistente com `chunks.edital` e
`alertas_validacao.edital`, que têm FK declarada. Não corrigido nesta
decisão por ser comportamento pré-existente fora do escopo desta mudança;
registrado aqui para não ser reintroduzido por engano numa migração futura
achando que é itencional em todo o schema.

**Ordem de inserção por edital** (relevante para qualquer reimplementação
em outro banco): `editais` → `chunks` (retorna `chunk_id_by_index`) →
`taxonomia_topicos`/`taxonomia_subtopicos` → `alertas_validacao` (usa o
mesmo `chunk_id_by_index` dos `chunks`). `alertas_validacao` depende de
`chunks` já estarem inseridos, não pode ser paralelizada antes deles.

## Guia para troca de banco (SQLite → outro motor)

Documentado explicitamente a pedido do time, para quando o SQLite via
Datasette for substituído:

1. **Fonte de verdade nunca é o banco.** É sempre
   `revisao_piloto/<edital>.json` + `<edital>.auditoria.json` +
   `<edital>.validacao.json`. Qualquer banco novo deve ser populado a partir
   desses três arquivos, replicando a lógica hoje em
   `scripts/gerar_db_datasette.py` (`_carregar_par`, `_inserir_edital`,
   `_inserir_chunks_com_auditoria`/`_inserir_chunks_sem_auditoria`,
   `_inserir_taxonomia`, `_inserir_alertas_validacao`) — não existe
   ferramenta de "exportar do SQLite", porque o SQLite é ele mesmo uma
   exportação.
2. **Chave de junção estável entre os três JSONs é `chunk_index`** (inteiro,
   posição do chunk dentro do edital) — presente em
   `auditoria.chunks[i].chunk_index`, `resultado.resultados[i].chunk_index`
   e `validacao.alertas[i].chunk_index`. Arquivos legados sem
   `.auditoria.json` não têm `chunk_index` confiável (usam posição na lista
   como substituto, ver `_inserir_chunks_sem_auditoria`) — um banco novo
   pode optar por não suportar mais esse caso legado, já que só existe 1
   edital no piloto e ele já tem `.auditoria.json`.
3. **Esta tabela/schema é disposable por design** (ADR-015: "banco de apoio
   à revisão, não o schema de produção da Fase 5") — ao trocar de motor,
   não há necessidade de preservar dados históricos do `revisao.db` atual;
   basta rodar o novo `gerar_db_<motor>.py` contra os JSONs existentes.
4. **O schema de produção real (Fase 5, Postgres próprio `scraper-cebraspe-db`, ADR-026)
   é um schema diferente e não relacionado** — não confundir uma eventual
   troca do SQLite de revisão com a Fase 5, que já é Postgres.
5. Se o motor novo continuar sendo servido pelo Datasette (ele suporta
   qualquer banco com plugin de conector, incluindo Postgres via
   `datasette-postgres`), a flag `--static relatorio:/data/relatorio` deste
   ADR-018 independe do motor do banco — o relatório HTML é gerado à parte,
   a partir dos mesmos JSONs, e não precisa de nenhuma mudança.

## Consequências

### Positivas
- Resolve o de-para manual: uma página por edital, sem alternar entre
  tabelas ou escrever SQL.
- Reaproveita 100% da infraestrutura já paga (Traefik, Cloudflare Tunnel,
  SSO, container Datasette) — zero serviço novo, zero porta nova, zero
  plugin.
- `alertas_validacao` torna os achados do ADR-017 consultáveis via SQL/FTS
  do próprio Datasette, além de visíveis no relatório — mesma fonte
  (`.validacao.json`), duas formas de consumo.
- Schema documentado de ponta a ponta neste ADR reduz o custo de uma futura
  migração de banco a "reescrever um script de carga", não a "redescobrir o
  formato".

### Alternativas Descartadas
- **Canned query / template customizado dentro do próprio Datasette:**
  descartado porque o renderizador tabular padrão não faz layout de duas
  colunas nem destaque de texto — exigiria plugin de template Jinja2 custom
  do Datasette pra um ganho menor que gerar HTML estático direto.
- **Framework de templating (Jinja2) para o relatório:** descartado por
  manter a mesma filosofia de stack enxuta do ADR-011 (chamadas diretas em
  vez de SDK) — o relatório é gerado uma vez por regeneração do piloto, não
  em runtime, então o ganho de um motor de template não compensa a
  dependência nova.
- **Servir o relatório fora do Datasette (nginx dedicado, novo serviço):**
  descartado porque a flag `--static` nativa do Datasette já resolve sem
  infraestrutura adicional.

## Atualização — [ADR-020](ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md) (2026-09-21)

O schema acima continua valendo, com estas extensões:

```sql
-- editais: concurso de origem (resolvido pelo manifesto do downloader)
ALTER TABLE editais ADD COLUMN concurso_slug TEXT;   -- ex: "PF_25_ADM"
ALTER TABLE editais ADD COLUMN orgao TEXT;           -- ex: "PF"
ALTER TABLE editais ADD COLUMN ano INTEGER;          -- ex: 2025

-- chunks: classificação vinda do parser
ALTER TABLE chunks ADD COLUMN tipo_conhecimento TEXT;    -- basico | especifico | complementar
ALTER TABLE chunks ADD COLUMN nivel TEXT;                -- medio | superior
ALTER TABLE chunks ADD COLUMN cargo_numero INTEGER;
ALTER TABLE chunks ADD COLUMN materia_normalizada TEXT;  -- sem "(SOMENTE PARA A PROVA DISCURSIVA)"
ALTER TABLE chunks ADD COLUMN apenas_discursiva INTEGER;

-- taxonomia_topicos: concurso + mesma classificação, desnormalizados de
-- propósito para facet no Datasette sem join
--   concurso_slug, orgao, ano, tipo_conhecimento, nivel, cargo_numero,
--   materia_normalizada, apenas_discursiva

CREATE TABLE "cargos" (
   "id" INTEGER PRIMARY KEY,
   "edital" TEXT REFERENCES "editais"("edital"),
   "concurso_slug" TEXT,
   "orgao" TEXT,
   "ano" INTEGER,
   "numero" INTEGER,
   "nome" TEXT,
   "nivel" TEXT                                -- herdado do bloco de específicos
);
```

`cargo_numero`, `apenas_discursiva` e `ano` são tipados explicitamente
(`columns=` no `sqlite_utils`). Sem isso, a primeira linha com
`cargo_numero=None` fazia a coluna virar TEXT. JSON anterior ao ADR-020
gera essas colunas nulas, sem erro. O relatório HTML ganhou um selo por
chunk ("Básico · Médio", "Específico · Superior", "só discursiva") e o slug
do concurso no título e no índice.
