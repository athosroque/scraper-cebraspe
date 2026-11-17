Template version: 1.2

# Scraper CEBRASPE — Coleta Estruturada de Editais, Provas e Gabaritos

## 1. Identidade

- **ID:** `scraper-cebraspe` (diretório físico: `scraper_cebraspe/`)
- **Nome legível:** Scraper CEBRASPE — Coleta Estruturada de Editais, Provas e Gabaritos
- **Guia de referência:** `task.md` (roteiro de implementação por etapas, neste diretório)
- **Status:** in-progress:phase-6
- **Repositório GitHub:** desenvolvimento no monorepo privado `athosroque/Homelab`;
  publicação em `athosroque/scraper-cebraspe` (público, branch `main`), por
  `git subtree split` (ADR-045). O monorepo é a fonte; a publicação é só de ida.

## 2. Pré-requisitos

- Nenhum projeto do portfólio. O banco da Fase 5 é o Postgres **próprio**
  deste projeto (`scraper-cebraspe-db`, ver §4 e ADR-026). O cruzamento com o
  `study-rag-agent` (`itens_estudo`) é uma etapa futura (Etapa 7 do
  `task.md`), não um pré-requisito.
- `OpenRouter` — Provedor de inferência para o modelo `z-ai/glm-5.3-flash`
  usado na Etapa 4 de extração e no Telegram Bot via requisições REST diretas,
  com observabilidade e telemetria no Langfuse via SDK oficial (OTel, ver ADR-023).

## 3. Arquitetura

Pipeline batch: **Crawler** (Playwright) percorre a listagem de concursos
encerrados do CEBRASPE, filtra por ano via slug da URL e mapeia PDFs de
Edital/Prova/Gabarito → **Downloader** baixa e valida os PDFs, organizando em
`data/<ano>/CEBRASPE/<orgao>/{Editais,Provas,Gabaritos}/` → **Parser**
(PyMuPDF) recorta seções validadas manualmente na fase exploratória →
**Extração LLM** (via OpenRouter direto / `glm-5.3-flash`) produz taxonomia
matéria→tópico→subtópico estruturada, com checkpoint humano → **DB writer**
grava em star schema (dimensões matéria/tópico/órgão/cargo/ano + fatos
concurso/cargo/taxonomia) no Postgres próprio do projeto
(`scraper-cebraspe-db`), sem FK para outros projetos — o cruzamento com
`itens_estudo` do `study-rag-agent` é feito depois por chave natural
normalizada (ADR-026).
Provas e Gabaritos baixados entram na fila `fila_extracao_questoes`. O
consumidor dela (extração de questões, gabarito e discursiva, seguida da
classificação por assunto) passou a ser prioridade do projeto: Etapas 5C/5D do
`task.md`.
Camada canônica (Etapa 5B, ADR-029): `canonico/sinonimos.json` juntou os
nomes de matéria/tópico/subtópico por regra determinística, proposta do LLM
(lista fechada) e aprovação humana. Desde a 5B.1 é só histórico congelado:
os grupos aprovados viraram os nós da árvore mestre (abaixo).
**Objetivo do produto (2026-09-28, ADR-030):** um **site público de
questões** (portfólio, estilo Gran Questões), começando pelo piloto 2025. A
questão é a entidade central, e o subassunto é a unidade de estudo. As
estatísticas, em ordem: o que mais cai na prova; o que o edital cobra;
edital × prova; desempenho pessoal. **Árvore mestre** (Etapas 5B.1/5B.2):
`canonico/arvore.json` guarda nós matéria → assunto → subassunto, com o pai
no próprio nó, semeados com os grupos aprovados da 5B (mesmo ID). Item de
edital e questão apontam para nós (N:N). Toda leitura e escrita do JSON
passa por `src/arvore.py`; a curadoria é `scripts/curar_arvore.py`, e o
pipeline só mapeia item novo por regra. No banco: `no_arvore` + pontes
`materia_no`/`topico_no`/`subtopico_no` e as views `vw_no_caminho`,
`vw_arvore_edital_por_cargo` e `vw_edital_cobra_*`. As views no Postgres (5E)
alimentam o site (5F: API, frontend, contas, histórico, simulado). O
Datasette continua só como ferramenta de revisão do dono.

## 4. Stack fixada

- Python 3.11+
- playwright >=1.42 (chromium)
- pymupdf >=1.23
- pydantic >=2.6
- psycopg2-binary
- python-dotenv
- requests >=2.31 (download de PDFs na Etapa 3, fora do contexto Playwright)
- pytest + ruff (CI universal do portfólio)
- langfuse >=4.7,<5 — SDK oficial de observabilidade (OTel), ver ADR-023
  (v4 desde 2026-09-29: nome do trace via `propagate_attributes` na abertura)
- PostgreSQL 16 (`postgres:16-alpine`) — serviço próprio
  `scraper-cebraspe-db` no `docker-compose.yml` deste projeto, porta
  `127.0.0.1:5435`, banco/usuário `cebraspe`, volume
  `scraper_cebraspe_pgdata` (ADR-026). Sem pgvector por ora
- Site (5F, ADR-033): FastAPI + Jinja2 + HTMX + Alpine.js + Pico.css,
  Authlib (Google OAuth), código em `site/`
- sqlite-utils >=3.36 — só pra construir `revisao_piloto/revisao.db` (banco
  de apoio à revisão humana da Etapa 4); Datasette roda via Docker
  (`datasetteproject/datasette`), não é dependência do venv
- mkdocs-material >=9.6,<10 — site de documentação (Etapa 9/D1, ADR-040):
  `mkdocs.yml` com `site_dir: build/docs` (o padrão `site/` colide com o app
  FastAPI) e `nav` explícito guardado pelo `--strict`; páginas de `docs/tecnico/`
  geradas de `src/registro/` por `scripts/gerar_docs.py` (Etapa 9/D2, ADR-041)


## 5. Progresso

O detalhe de cada etapa (checklist, critérios e números) está no `task.md` (painel de
etapas no topo) e nos planos em `docs/planos/` (índice em `docs/planos/README.md`). Aqui
fica só o estado resumido. Mantenha o título de cada item (o texto antes do ` — `): o
`scripts/jira_sync.py` deduplica os cards pelo id da etapa.

- [x] Fase 1 — Preparação: ambiente, modelos Pydantic (Concurso → Cargo → Taxonomia) e `.env`.
- [x] Fase 2 — Crawler: ano pelo slug, falha isolada por concurso, idempotência por registro local (ADR-008).
- [x] Fase 3 — Download: validação `%PDF-`, dedup por URL (manifesto) e por hash de conteúdo.
- [x] Fase 4 — Extração híbrida de editais com checkpoint humano; base de 2025 aprovada em 2026-09-23 (ADR-019, ADR-025, ADR-028).
- [x] Fase 5 — Banco de estatísticas: star schema no `scraper-cebraspe-db`, carga idempotente e fila de provas (ADR-026, ADR-027, ADR-028).
- [x] Etapa 5C — Extração de questões, gabaritos e discursivas (ADR-031).
- [x] Etapa 5C.1 — Correções da extração (`docs/planos/correcoes-etapa-5c.md`, ADR-031).
- [x] Etapa 5B.1 — Árvore mestre semeada com a 5B (ADR-029, ADR-030).
- [x] Etapa 5B.2 — Curadoria da árvore com propostas do LLM e aprovação do dono (ADR-030).
- [x] Etapa 5D — Classificação das questões na árvore mestre, LLM com lista fechada (ADR-032).
- [x] Etapa 5E — Estatísticas e views de incidência, 100% determinísticas (ADR-032).
- [x] Fase 6 — Piloto de 5 concursos de 2025 validado ponta a ponta (2026-10-06).
- [x] Etapa 5F.0 — Decisões do site público: FastAPI + Jinja2/HTMX/Alpine em 3 camadas (ADR-033).
- [x] Etapa 5F.1 — API de leitura `/api/v1` e contrato `site/openapi.json` (ADR-033).
- [x] Etapa 5F.2 — Frontend de resolução (ADR-033).
- [x] Etapa 5F.3 — Contas Google e histórico (ADR-033).
- [x] Etapa 5F.4 — Páginas de estatística (ADR-033).
- [x] Etapa 5F.5 — Simulado com correção CEBRASPE (ADR-033).
- [x] Etapas 5F.6 a 5F.8 — Documentação da API e endpoints novos (ADR-033).
- [x] Etapa 5G — Fidelidade ao caderno e filtros multisseleção (ADR-034).
- [x] Etapa 5H — Card e filtros no formato Gran, em teal (ADR-035, ADR-030).
- [x] Etapa 8.0 — Inventário 2020+, classificador fino e `inventario/exclusoes.json` (ADR-037).
- [x] Etapa 8.M — Múltipla escolha: tipo, alternativas, gabarito A–E e site por tipo (ADR-038).
- [x] Etapa 8.M.1 Estatísticas: incidência em dois níveis, prova → concurso (fn_prova_cobra) — cada edital pesa 1 (ADR-039, KAN-28).
- [x] Etapa 5B.3 Auditoria da hierarquia da árvore — 74 matérias → 43 disciplinas, um conceito por nó, K22 inalterado (ADR-030, KAN-78, 2026-10-29).
- [ ] Etapa 8.C Coleta dos concursos de múltipla escolha (ME) de 2025 — prioridade do dono
      (2026-10-12), plano em `plano-etapa-8c.md`. **Repartida em 2026-11-13** (decisão do
      dono): só a família fiscal/jurídica/administrativa, 7 concursos (`SEFA_PR_25`,
      `BANRISUL_25`, `SEBRAE_25_PSE_1`, `PGE_ES_25_PROCURADOR`, `PGE_PI_25`,
      `SEFAZ_SE_25_AUDITOR`, `TCE_MG_25`); os outros 4, de domínio novo, foram para a Etapa
      8.D. C0 (KAN-30) e C1a (KAN-56) concluídas — os 2 editais aprovados e as duas
      classificações 5D decididas pelo dono em 2026-11-13, site em 3.409 questões.
      Próximas: C1b → C2 (Dagster, Etapa 9/D5a e D5b) → C3
      (KAN-58), C5 (KAN-60), C6 (KAN-61) → C8. Pronto quando os 7 concursos ME de 2025 da 8.C
      estão `aprovado`, o piloto segue inalterado e `make test-all` está verde.
- [ ] Etapa 8.D Coleta dos concursos ME de 2025 de domínio novo — remanejados da 8.C em
      2026-11-13 (decisão do dono): `SEED_SE_25_PROFESSOR`, `UNIVESP_25_PSS`, `IPAAM_25`,
      `SEMA_AM_25` (licenciatura/pedagogia, ensino superior, meio ambiente). Medição mostrou
      que a árvore mestre hoje resolve só ~0,1% dos itens do edital nesses domínios (contra
      67% no `SEFA_PR_25`), por isso saíram do lote da família madura; exige ampliar a árvore
      mestre antes de começar. Sem plano de sessões ainda; detalhes e pontos em aberto
      (inclusive a proposta de um portão normativo medível em vez de lista nomeada) no
      `task.md`, seção 8.D.
- [ ] Etapa 8.M.2 Estatísticas por recorte: drill-down matéria → assunto → subassunto e filtros banca/ano/órgão/nível — na fila,
      depois da 8.C; detalhes no `task.md`.
- [ ] Etapa 9 Documentação viva (MkDocs executivo + técnico, contexto para agentes) e Dagster como C2 — plano em
      `plano-etapa-9.md` (KAN-67). D1 (KAN-68, ADR-040), D2 (KAN-69, ADR-041) e
      D3 (KAN-70) concluídas; D4 (KAN-71, executivo e PDF) em análise; D5a e D5b (KAN-31 e
      KAN-32, Dagster) entregues e validadas em 2026-10-21, registradas no ADR-042.
- [ ] Etapa 10 Portfólio público — identidade visual dos dois fronts (skill `frontend-design`), seção de
      processos e governança (BPMN da curadoria, matriz RACI, indicadores, riscos, fluxo Jira/ITSM) e
      repositório público só do `scraper_cebraspe`. Pedido do dono em 2026-11-13, plano em
      `plano-etapa-10.md` (sessões P1 a P4). P1 entregue em 2026-11-13 (KAN-103, ADR-043),
      em análise; P3 em andamento (KAN-105, ADR-045): repositório público e GitHub Pages.
- **Deploy público (5F.12): opcional**, por decisão do dono em 2026-10-06 (o site ainda vai mudar muito antes de ir ao ar).

## 6. Patterns

O texto completo das regras está em `src/registro/regras_*.py` e na página gerada
[docs/tecnico/regras.md](docs/tecnico/regras.md). Para saber o que ler em cada tarefa, use
[docs/tecnico/tarefas.md](docs/tecnico/tarefas.md). Regra nova entra só no registro, e só
vai para cá se for do núcleo (`nucleo=True`).

- **P41** Aprovação da revisão humana é o `status_revisao_humana` do `<edital>.json`; o writer relê a cada carga. [regra](docs/tecnico/regras.md#p41)
- **P51** Decisão do dono na árvore só via `scripts/curar_arvore.py` (ou `src/arvore.py`); operação humana sai `aprovado`/`ativo`, e erro de validação não grava nada. [regra](docs/tecnico/regras.md#p51)
- **P67** O que fica fora do site é decidido só em `inventario/exclusoes.json`; alerta do inventário vem do texto do link, e antes de tratar como "sem arquivo" confere-se a página ao vivo (ADR-037). [regra](docs/tecnico/regras.md#p67)
- **P70** Script novo entra em `src/registro/scripts.py`; mudança de argparse, etapa, checagem, regra ou schema pede `make docs-gerar`; regra nova entra só no registro (ADR-041). [regra](docs/tecnico/regras.md#p70)
- **P71** Lote novo, ou qualquer passo que grava no banco, nunca altera o piloto (2.800 itens, 129 anuladas, 3.029 apontamentos, chaves da 5D): K22–K24 rodam antes e depois, e diferença bloqueia o lote. [regra](docs/tecnico/regras.md#p71)
- **P72** Título de bloco de edital fora de `canonico/disciplinas.json` vira assunto, nunca disciplina; proposta automática não cria matéria (ADR-030). [regra](docs/tecnico/regras.md#p72)

## 7. Anti-patterns

- **A06** Nunca gravar tabelas deste projeto no `study-rag-db` nem criar FK para `itens_estudo`; o cruzamento é só por chave natural, na Etapa 7 (ADR-026). [regra](docs/tecnico/regras.md#a06)
- **A07** Nunca hardcodar credenciais de API ou Postgres no código; usar `.env` (ver §8). [regra](docs/tecnico/regras.md#a07)
- **A13** Nunca deixar um passo do pipeline como "rode manualmente depois": o artefato seguinte fica desatualizado sem sinal nenhum (ADR-008, ADR-019). [regra](docs/tecnico/regras.md#a13)
- **A25** Nunca aprovar concurso com `UPDATE` direto no banco: a próxima carga reverte a partir do JSON. [regra](docs/tecnico/regras.md#a25)
- **A27** Nunca aprovar sinônimo ou mapeamento da árvore com `UPDATE` no banco: a fonte é `canonico/arvore.json`, e a próxima carga reverte. [regra](docs/tecnico/regras.md#a27)
- **A28** Nunca ler ou escrever `canonico/arvore.json` com `json.load`/`json.dump` direto; usar `src/arvore.py` (`carregar`, `salvar`, `chave_item`). [regra](docs/tecnico/regras.md#a28)
- **A29** Nunca rodar `scripts/semear_arvore.py --forcar` depois da curadoria: a semente reescreve a árvore e apaga toda decisão do dono. [regra](docs/tecnico/regras.md#a29)
- **A30** Nunca deixar o agente aprovar proposta do LLM em nome do dono; só grupo `regra` é aprovado automaticamente. [regra](docs/tecnico/regras.md#a30)
- **A42** Nunca commitar `questoes/` (JSON de questões extraídas) no git: é local e regenerável (ADR-031). [regra](docs/tecnico/regras.md#a42)
- **A44** Nunca pôr senha de role no SQL versionado nem em teste; a senha vem do `.env`, via `site/scripts/aplicar_schema_app.py`. [regra](docs/tecnico/regras.md#a44)
- **A57** Nunca dar GRANT ao role do site esperando que sobreviva a uma carga: `stats_writer.criar_schema` reaplica os GRANTs, e isso não pode ser removido. [regra](docs/tecnico/regras.md#a57)
- **A59** Nunca remover o `conftest.py` da raiz: sem ele, os erros simulados vão para `logs/scraper_cebraspe.log` e o log de produção deixa de servir para auditoria. [regra](docs/tecnico/regras.md#a59)
- **A62** Nunca editar à mão as páginas de `docs/tecnico/`: são geradas de `src/registro/` por `scripts/gerar_docs.py`, e o teste guarda recusa a diferença (ADR-041). [regra](docs/tecnico/regras.md#a62)

## 8. Segurança

- Credenciais: `POSTGRES_HOST/PORT/DB/USER/PASSWORD` (apontando para o
  banco próprio `scraper-cebraspe-db`; a senha não tem default no compose —
  vazia, o container não sobe) e as chaves `OPENROUTER_KEY_*` por etapa (fallback `OPENROUTER_API_KEY`) — todas
  em `.env` local, nunca hardcoded.
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
3. `cp .env.example .env` e preencher `POSTGRES_PASSWORD` (host `localhost`
   + porta `5435` fora de container; host `scraper-cebraspe-db` + porta
   `5432` dentro da rede `homelab_default`)
3.1. `docker compose up -d scraper-cebraspe-db` — sobe o Postgres próprio
   (a 1ª subida cria banco/usuário a partir do `.env`; trocar a senha depois
   exige `ALTER USER`, o volume já está inicializado)
4. `python -m src.spider` — roda a Etapa 2 isolada para validação
5. `pytest` para validar (spider + downloader)

Documentação (Etapa 9/D1, ADR-040):

- `make docs-serve`: local em `127.0.0.1:8001`, com recarga ao salvar.
- `make docs-build`: `mkdocs build --strict` em `build/docs`, mais o PDF da visão executiva
  (`scripts/exportar_pdf_executivo.py`, Chromium do Playwright) em
  `build/docs/executivo/scraper-cebraspe-executivo.pdf`; também roda no `make check`.
- `make docs-build && docker compose up -d scraper-cebraspe-docs`: nginx em
  `127.0.0.1:8013` e `docs.projetoathos.com.br` via Traefik + Cloudflare Access.
- Publicação pública (Etapa 10/P3, ADR-045): o workflow
  `.github/workflows/publicar-docs.yml` do repositório público roda o mesmo
  `mkdocs build --strict` e publica em
  [athosroque.github.io/scraper-cebraspe](https://athosroque.github.io/scraper-cebraspe/),
  com `requirements-docs.txt` (sem banco, sem LLM) e o PDF gerado no próprio job. O nginx
  interno continua servindo a cópia atrás do Cloudflare Access.
- Página nova em `docs/` entra no `nav` do `mkdocs.yml`, na aba e seção do seu propósito
  (seção nova ganha `index.md` de abertura; ADR-040), senão o `--strict` falha.
- `make hooks-instalar` (uma vez por clone): instala os hooks `post-commit` e `post-merge` em `.git/hooks`
  (encadeando o que já existir). Depois disso, commit ou merge no checkout principal que toca `docs/`,
  `mkdocs.yml`, `scripts/gerar_docs.py`, `scripts/gerar_numeros.py`,
  `scripts/exportar_pdf_executivo.py` ou `src/registro/` roda o `docs-build` sozinho, em segundo
  plano, com log em `logs/publicar_docs.log`. Worktree não publica (ADR-040).
- `make docs-gerar` (Etapa 9/D2, ADR-041): regera `docs/tecnico/` (pipeline, comandos,
  regras, checagens e banco) a partir de `src/registro/`; lê o schema do banco. Sem banco:
  `venv/bin/python -m scripts.gerar_docs --sem-banco`; conferir: `--verificar`. Também regera
  `docs/executivo/numeros.md` (Etapa 9/D4) com `scripts/gerar_numeros.py`, que lê o banco e o
  custo acumulado das chaves no OpenRouter; sem rede, `--sem-custo`.

## 9.2. Revisão via Datasette (Etapa 4 — checkpoint de revisão humana)

Navega a trilha de auditoria (entrada/saída do parser+chunking+LLM) e a
taxonomia extraída lado a lado, sem frontend próprio. Exposto externamente
via rede `homelab_default` com Traefik e Cloudflare Tunnel, acessível em
`https://datasette.projetoathos.com.br`, protegido por Cloudflare Zero Trust
(SSO restrito à conta do dono). **Não é** o banco de produção
da Fase 5 (esse é o Postgres próprio `scraper-cebraspe-db`).

Além das tabelas (`chunks`/`taxonomia_topicos`/`taxonomia_subtopicos`/
`alertas_validacao`), o mesmo container serve em `/relatorio/index.html`
um **relatório HTML de página única por edital** — texto-fonte e taxonomia
extraída lado a lado por chunk, com os alertas de
`scripts/validar_taxonomia.py` destacados — pra não precisar alternar entre
tabelas pra fazer o de-para manualmente (ADR-018).

**Não é preciso rodar nada manualmente depois de uma extração.**
`scripts/revisar_taxonomia_piloto.py` e `scripts/reprocessar_falhas_piloto.py`
chamam `scripts/atualizar_revisao.py` automaticamente ao final — validação
de-para, relatório HTML, banco `revisao.db` e restart do container Datasette
ficam sempre em dia com o `<edital>.json` mais recente, sem passo manual
(ver ADR-019). O restart é best-effort: se o Docker/container não estiver
disponível, só loga aviso, nunca derruba o pipeline de extração.

Setup inicial (subir o container pela primeira vez) ou re-sincronizar os
artefatos depois de editar um `.json` na mão, fora do pipeline de extração:

```bash
cd /home/athos/homelab/scraper_cebraspe
python -m scripts.atualizar_revisao   # roda validação + relatório + banco + restart em sequência
docker compose up -d                  # 1ª vez, ou depois de mudar o `command` do docker-compose.yml
# Acesse: https://datasette.projetoathos.com.br (tabelas)
# e https://datasette.projetoathos.com.br/relatorio/index.html (página única)
```

Mudou o `command` do `docker-compose.yml` (ex.: nova flag `--static`)?
`restart` (automático ou manual) não recarrega — precisa recriar o
container: `docker compose up -d`.

`docker compose down` para derrubar.

## 9.1. Uso do downloader (Etapa 3)

```python
from src.downloader import download_concurso_pdfs

resultado = download_concurso_pdfs(
    orgao="TJ_CE",  # ou contest["orgao"] retornado por get_contest_links
    ano=2025,
    pdf_map=pdfs,  # dict retornado por spider.map_pdf_links
)
# resultado = {"editais_abertura": [...], "provas": [...], "gabaritos": [...]}
# paths dos arquivos efetivamente baixados/reaproveitados
```

## 10. Entregáveis

Os comandos de cada script, com argumentos, estão em
[docs/tecnico/comandos.md](docs/tecnico/comandos.md); as etapas, em
[docs/tecnico/pipeline.md](docs/tecnico/pipeline.md).

- `data/<ano>/CEBRASPE/<orgao>/{Editais,Provas,Gabaritos}/` — PDFs baixados (ignorados pelo git).
- `logs/scraper_cebraspe.log` — log de execução (ignorado pelo git).
- Banco `scraper-cebraspe-db` (Postgres próprio, DDL em `src/sql/schema_estatisticas.sql`), gravado por `src/stats_writer.py`. Sem FK para outros projetos.
- `revisao_piloto/` — `<edital>.json` (taxonomia aprovada) e `<edital>.auditoria.json` e `.validacao.json` (versionados). `revisao.db` e `relatorio/*.html` são derivados, ignorados pelo git, e servidos pelo Datasette (§9.2).
- `canonico/arvore.json` — árvore mestre, fonte da verdade da taxonomia; lida e escrita só por `src/arvore.py`.
- `canonico/classificacao_questoes.json` — classificação das questões na árvore (5D), chave estável `<concurso>|<caderno>|<numero>`.
- `canonico/sinonimos.json` — histórico congelado da 5B; não é mais escrito pelo pipeline.
- `questoes/` — JSONs brutos das questões extraídas: locais, ignorados pelo git, regeneráveis por `scripts/extrair_questoes.py`.
- `inventario/` — inventário 2020+ (`concursos.jsonl`, `RELATORIO.md`) e `exclusoes.json`, que decide o que fica fora do site.
- `site/` — API e páginas do site (5F). Rodar: `cd site && uvicorn app.main:app`; Swagger em `/docs`. Depois de mudar rota ou modelo, rode `python site/scripts/exportar_openapi.py`, senão o teste `test_openapi_versionado_em_dia` falha. `site/openapi.json` é o contrato versionado.
- `task.md` — roteiro de execução por etapas (versionado). `docs/planos/` — planos arquivados.

## 11. Documentação

- Comentário só quando o "porquê" não é óbvio (ex: por que o filtro de ano
  usa o slug e não o texto do link).
- `task.md` é a fonte de verdade para granularidade de passos; este
  `CLAUDE.md` mantém a visão de fase/status.
- Plano de etapa (`plano-etapa-N.md`) fica na raiz só enquanto a etapa está
  em andamento. Ao concluir, levar o que ficou aberto para o `task.md` e
  fazer `git mv` para `docs/planos/` (índice em `docs/planos/README.md`).
  Não apagar: `task.md` e ADRs citam esses arquivos.

## 12. Log de decisões

As decisões ficam em [`docs/adr/`](docs/adr/README.md) (ADR-001 a ADR-045;
o `README.md` de lá é o índice com data e título). Antes de reabrir uma
escolha de stack, banco, parser ou site, ler o ADR correspondente.

- Decisão nova vira ADR novo (ou seção "Atualização" no ADR existente), não
  entrada aqui. Este arquivo só cita o número do ADR em §5–§7.
- O log cronológico que ficava aqui (2026-09-19 a 2026-10-07) foi removido em
  2026-10-08 por duplicar os ADRs; está no histórico do git.

## 13. LESSONS.md (do projeto)

Ver `LESSONS.md` neste diretório — protocolo padrão descrito no `CLAUDE.md`
raiz do portfólio.

