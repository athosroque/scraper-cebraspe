Template version: 1.2

# Scraper CEBRASPE — Coleta Estruturada de Editais, Provas e Gabaritos

## 1. Identidade

- **ID:** `scraper-cebraspe` (diretório físico: `scraper_cebraspe/`)
- **Nome legível:** Scraper CEBRASPE — Coleta Estruturada de Editais, Provas e Gabaritos
- **Guia de referência:** `task.md` (roteiro de implementação por etapas, neste diretório)
- **Status:** in-progress:phase-3
- **Repositório GitHub:** homelab local / a versionar

## 2. Pré-requisitos

- `study-rag-agent` — `completed`. Fornece a instância PostgreSQL + pgvector
  (`study-rag-db`, rede Docker `homelab_default`, porta publicada `5434`,
  banco `study_rag`) e a tabela `itens_estudo`, à qual as novas tabelas deste
  projeto se referenciam por FK opcional. Verifique com
  `./agents/list-status.sh study-rag-agent`.
- `llm-gateway` — `completed`. Fornece o LiteLLM (`:4000`, modelo
  `glm-5.3-flash`) usado na Etapa 4 de extração — reaproveitar essa infra,
  nunca instanciar client para outro provedor. Verifique com
  `./agents/list-status.sh llm-gateway`.

## 3. Arquitetura

Pipeline batch: **Crawler** (Playwright) percorre a listagem de concursos
encerrados do CEBRASPE, filtra por ano via slug da URL e mapeia PDFs de
Edital/Prova/Gabarito → **Downloader** baixa e valida os PDFs, organizando em
`data/<ano>/CEBRASPE/<orgao>/{Editais,Provas,Gabaritos}/` → **Parser**
(PyMuPDF) recorta seções validadas manualmente na fase exploratória →
**Extração LLM** (via `llm-gateway`/`glm-5.3-flash`) produz taxonomia
matéria→tópico→subtópico estruturada, com checkpoint humano → **DB writer**
grava em tabelas novas (star schema: dimensões matéria/tópico/órgão/cargo/ano
+ fatos concurso/cargo/taxonomia) na mesma instância Postgres do
`study-rag-agent`, referenciando `itens_estudo` por FK opcional sem alterá-la.
Provas e Gabaritos baixados entram numa fila `pendente` para um pipeline de
extração de questões futuro (fora do escopo deste projeto).

## 4. Stack fixada

- Python 3.11+
- playwright >=1.42 (chromium)
- pymupdf >=1.23
- pydantic >=2.6
- psycopg2-binary (a adicionar ao `requirements.txt`)
- python-dotenv (a adicionar ao `requirements.txt`)
- pytest + ruff (CI universal do portfólio)
- PostgreSQL 16 + pgvector — reaproveitado de `study-rag-agent`, não é
  serviço próprio deste projeto

## 5. Progresso

- [x] Fase 1 — Preparação: `requirements.txt` completo instala sem erro;
      `models_scraper.py` com hierarquia Concurso→Cargo→Taxonomia aninhada
      (sem listas paralelas); `.env.example` e `.gitignore` presentes
- [x] Fase 2 — Crawler: `spider.py` filtra ano pelo slug da URL (não pelo
      texto do link), percorre `/concursos/encerrado`, falha de um concurso
      não aborta o lote, idempotência por registro local
      (`data/processed_concursos.json`)
- [ ] Fase 3 — Download: `downloader.py` valida PDFs (Content-Type/magic
      bytes) e grava em hierarquia determinística e testada
- [ ] Fase 4 — Extração híbrida: seções validadas documentadas; parser +
      chunking; extração LLM com checkpoint humano aprovado em ≥1 edital
      piloto
- [ ] Fase 5 — Banco de estatísticas: tabelas novas criadas em `study-rag-db`
      com FK para `itens_estudo`; `stats_writer.py` grava sem alterar
      `itens_estudo`; fila `pendente` populada
- [ ] Fase 6 — Piloto: fluxo ponta a ponta em 1–2 concursos grandes de 2025
      encerrados, log sem bloqueios/timeouts, base aprovada manualmente

## 6. Patterns

- Filtro de ano sempre pelo slug da URL (`_25`, `_26`, ...) — nunca pelo
  texto visível do link (o texto do card é sempre "MAIS INFORMAÇÕES",
  confirmado ao vivo).
- Falha de rede/parsing por concurso individual é logada e o crawler segue
  para o próximo — nunca aborta o lote inteiro.
- Slugify determinístico (acentos/espaços → forma normalizada única) para
  nomes de órgão usados em paths de disco.
- Toda chamada LLM passa pelo `llm-gateway` (`:4000`, `glm-5.3-flash`).
- Toda tabela nova referencia `itens_estudo` por FK opcional, nunca duplica
  ou altera suas colunas.
- Priorização de cargo grande (INSS, PF, PRF, ...) também é feita pelo slug
  da URL, dividido em segmentos por `_`/`-` e comparado contra um set de
  keywords — nunca com `\b` de regex direto no slug (underscore é `\w`, não
  cria fronteira de palavra).
- Idempotência do crawler: registro local em JSON
  (`data/processed_concursos.json`, um array de slugs) checado/atualizado a
  cada concurso processado com sucesso — não depende da estrutura de pastas
  da Etapa 3 (ainda não implementada).

## 7. Anti-patterns

- Nunca filtrar ano com regex no texto do link — o ano está no slug da URL
  (ex: `TJ_CE_25_NOTARIOS` → 2025), não aparece como "2025" no texto visível.
- Nunca envolver o loop de concursos inteiro num único `try/except` (mascara
  falha isolada como falha total do lote).
- Nunca modelar tópico/subtópico como duas listas paralelas — perde a
  hierarquia que a Fase 5 precisa para estatística.
- Nunca reabrir a decisão de tecnologia de banco — PostgreSQL 16 já é o
  padrão do portfólio e a instância do `study-rag-agent` já está disponível.
- Nunca hardcodar credenciais do LiteLLM/Postgres no código — usar `.env`
  (ver Segurança).
- Nunca usar `\b` de regex direto sobre um slug com underscore para detectar
  keywords — `_` é `\w`, então `\bINSS\b` não dispara em `INSS_25`. Dividir
  o slug em segmentos primeiro.

## 8. Segurança

- Credenciais: `POSTGRES_HOST/PORT/DB/USER/PASSWORD` (apontando para
  `study-rag-db`) e `LITELLM_BASE_URL`/`LITELLM_API_KEY` — todas em `.env`
  local, nunca hardcoded.
- `.env` está no `.gitignore` deste projeto.
- Nunca commitar PDFs baixados (`data/`) nem logs (`logs/`) — ambos no
  `.gitignore`.
- Nota fora do escopo deste projeto: `study-rag-agent/CLAUDE.md` e seu
  `docker-compose.yml` têm a master key do LiteLLM em texto puro, versionada
  — vale rotacionar e mover para `.env` quando for conveniente tratar aquele
  projeto.

## 9. Deploy

1. `python3 -m venv venv && source venv/bin/activate`
2. `pip install -r requirements.txt && playwright install chromium`
3. `cp .env.example .env` e preencher com as credenciais do `study-rag-db`
   (host `localhost` + porta `5434` se rodando fora de container; host
   `study-rag-db` + porta `5432` se este projeto vier a rodar dentro da rede
   `homelab_default`)
4. `python -m src.spider` — roda a Etapa 2 isolada para validação
5. `pytest` para validar

## 10. Entregáveis

- `data/<ano>/CEBRASPE/<orgao>/{Editais,Provas,Gabaritos}/` — PDFs baixados
  (ignorado pelo git, volume grande demais)
- `logs/scraper_cebraspe.log` — log de execução (ignorado)
- Tabelas novas em `study-rag-db` (star schema de estatísticas de concursos)
- `task.md` — roteiro de execução por etapas (versionado)

## 11. Documentação

- Comentário só quando o "porquê" não é óbvio (ex: por que o filtro de ano
  usa o slug e não o texto do link).
- `task.md` é a fonte de verdade para granularidade de passos; este
  `CLAUDE.md` mantém a visão de fase/status.

## 12. Log de decisões

### 2026-09-19 — Filtro de ano por slug de URL, não por texto do link
**Decisão:** Extrair o ano do sufixo `_YY` no slug da URL do concurso (ex:
`_25` → 2025), em vez de regex `2025` no texto do link.
**Motivo:** Teste ao vivo no site confirmou que o texto de cada card é sempre
"MAIS INFORMAÇÕES" — a regex original (`re.search(r'2025', text)` sobre o
texto do link, em `spider.py`) nunca teria retornado resultado nenhum.
**Alternativas descartadas:** Regex no texto visível (implementação
original) — comprovadamente quebrada, falha silenciosa (sem erro, só
retorna lista vazia).

### 2026-09-19 — Fonte primária de crawling é `/concursos/encerrado`
**Decisão:** Priorizar a aba "Encerrados" como fonte dos concursos 2025, não
a raiz `/concursos/`.
**Motivo:** A raiz retornou 80 links de concurso vs. 423 em `/encerrado`;
Prova e Gabarito só existem para concursos já realizados.
**Alternativas descartadas:** Crawlear só a raiz — insuficiente para o
objetivo de PDFs de prova/gabarito.

### 2026-09-19 — Novas tabelas na mesma instância Postgres do study-rag-agent
**Decisão:** Tabelas de estatísticas deste projeto vivem em `study-rag-db`
(mesma instância, rede `homelab_default`), desenhadas como star schema, com
FK opcional para `itens_estudo`.
**Motivo:** Reaproveita infra já provisionada, permite FK real (em vez de
ETL externo) e o objetivo final (cruzar estatísticas por matéria/tema/ano
para ML e planos de estudo) é exatamente o forte de um modelo relacional com
colunas `JSONB` para campos irregulares.
**Alternativas descartadas:** Instância Postgres própria; banco não
relacional (Mongo) — descartado porque agregação/estatística/ML sobre
matéria×tema×ano é o caso de uso central de um schema relacional, não de um
document store.

### 2026-09-19 — Priorização de cargo também migrada do texto do link para o slug
**Decisão:** Ao implementar a Etapa 2, a checagem de keywords (INSS, PF,
PRF, ...) foi movida de `re.search` sobre o texto do link para uma
comparação por segmentos do slug da URL (`slug.split("_"/"-")` contra um
set de keywords).
**Motivo:** Mesma causa-raiz documentada no filtro de ano — o texto de todo
card é sempre "MAIS INFORMAÇÕES", então a priorização original também nunca
teria disparado (achado não listado explicitamente no `task.md`, mas
decorre diretamente do mesmo teste ao vivo). Além disso, `\b` de regex não
funciona bem sobre slug com underscore (`\w` inclui `_`), então a primeira
tentativa de correção (regex com `\b` direto no slug) também falhou
silenciosamente — corrigido comparando segmentos pós-`split`, não regex com
fronteira de palavra.
**Alternativas descartadas:** Manter checagem apenas no texto do link
(mantém o bug); regex `\b` direto no slug (não cria fronteira em
underscore, mesmo problema).

### 2026-09-19 — Idempotência via registro JSON local, não pasta em `data/`
**Decisão:** A Etapa 2 registra slugs processados com sucesso em
`data/processed_concursos.json` (array JSON), checado no início do loop e
atualizado após cada concurso bem-sucedido.
**Motivo:** A estrutura de pastas `data/<ano>/CEBRASPE/<orgao>/...` só passa
a existir na Etapa 3 (downloader); checar pasta em disco não é viável antes
disso. Um registro JSON simples é suficiente para o piloto e pode ser
substituído/complementado por uma checagem de pasta quando o downloader
existir.
**Alternativas descartadas:** Adiar idempotência para a Etapa 3 — rejeitado
porque o `task.md` pede idempotência já na Etapa 2, e o crawler sozinho já
é caro o suficiente (network + stealth wait) para justificar não reprocessar
concursos.

## 13. LESSONS.md (do projeto)

Ver `LESSONS.md` neste diretório — protocolo padrão descrito no `CLAUDE.md`
raiz do portfólio.
