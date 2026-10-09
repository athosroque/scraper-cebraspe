# Plano — Etapa 5F: Site público de questões

> **Documento autocontido, uma sessão (conversa) por subetapa (5F.1 a 5F.6).**
> Base normativa: ADR-030 (produto e árvore), ADR-032 (chave estável da
> questão), ADR-033 (stack, auth, dados de usuário, deploy e direitos). Não é
> preciso reler o `task.md`.

---

## 1. Contexto e objetivo

A 5E deixou o banco pronto para leitura. O site mostra as **2.800 questões
objetivas** do piloto 2025 (5 concursos), com filtros pela árvore mestre,
resolução Certo/Errado, contas Google, desempenho pessoal, as três
estatísticas e o simulado.

**Pronto quando** (critério do `task.md`): o site está no ar com as 2.800
questões filtráveis pela árvore, um usuário cadastrado resolve questões e vê
o próprio desempenho, e as três estatísticas e o simulado `PF_25_ADM` cargo 1
funcionam, com a pontuação conferida à mão.

---

## 2. O que já existe no banco (reutilizar, não recriar)

- `vw_questoes`: 1 linha por (questão × nó aprovado). Colunas: `questao_id`,
  `questao_canonica_id`, `numero`, `codigo_caderno`, `prova_tipo`,
  `tipo_conhecimento`, `concurso`, `orgao`, `banca`, `ano`,
  `cargo_edital_id`, `cargo_numero`, `cargo`, `nivel`, `gabarito`,
  `anulada`, `utilizavel`, `status_revisao`, `enunciado`, `secao`,
  `figuras`, `texto_base_id`, `texto_base_texto`, `tem_texto_base`,
  `tem_figuras`, `no_id`, `no_caminho`, `no_nivel`, `no_nome`, `materia_id`,
  `assunto_id`, `papel`, `confianca`, `fora_do_edital`, `nocoes`,
  `nome_de_cargo`, `rotulo_materia`. **Vem expandida por nó e por cargo**:
  a listagem precisa de `DISTINCT` por questão.
- `vw_no_caminho` (árvore ativa, `no_efetivo`), `vw_questao_no`.
- `fn_prova_cobra(p_nivel_alvo, p_banca, p_orgao, p_ano, p_concurso,
  p_cargo_numero, p_nivel, p_tipo_conhecimento)`: leitura oficial do "o que
  mais cai". **Nunca somar linhas de `vw_prova_cobra_*` entre cargos**.
- `vw_edital_cobra_{materia,assunto,subassunto}`, `vw_edital_vs_prova`,
  `vw_peso_materia_cargo`, `vw_certo_errado_por_no`, `vw_comparativo_nivel`,
  `vw_discursivas` (discursiva nunca se mistura com objetiva).
- Figuras em `data/2025/CEBRASPE/<orgao>/Provas/figuras/` (o caminho está no
  JSONB `figuras`).

---

## 3. Estrutura proposta

```
scraper_cebraspe/site/
  app/
    main.py            # FastAPI, monta api + web + static
    config.py          # pydantic-settings, lê .env (SITE_DB_*, GOOGLE_*, SESSION_SECRET)
    db.py              # pool psycopg (dois DSNs: leitura e app)
    modelos.py         # Pydantic: Questao, FiltroQuestoes, Pagina, NoArvore...
    repositorio/       # SQL puro sobre as views e o schema app
    servicos/          # regras: filtros, correção CEBRASPE, desempenho
    api/v1/            # JSON
    web/               # rotas HTML
    templates/         # Jinja2 + HTMX + Alpine
    static/            # pico.css, htmx.min.js, alpine.min.js (vendorizados)
  sql/app_schema.sql   # schema app + roles (idempotente)
  tests/
  Dockerfile
```

Regra do ADR-033: **template e rota não têm SQL nem regra.** Toda rota HTML
tem o endpoint JSON equivalente e teste.

DDL do schema `app` (5F.3 aplica; aqui como referência):

```sql
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE app.usuario (
  id bigserial PRIMARY KEY, google_sub text UNIQUE NOT NULL,
  email text NOT NULL, nome text, criado_em timestamptz DEFAULT now());
CREATE TABLE app.resposta (
  id bigserial PRIMARY KEY,
  usuario_id bigint REFERENCES app.usuario ON DELETE CASCADE,
  questao_chave text NOT NULL,          -- <concurso>|<caderno>|<numero> (ADR-032)
  resposta char(1) CHECK (resposta IN ('C','E')),
  acertou boolean NOT NULL, simulado_id bigint NULL,
  respondida_em timestamptz DEFAULT now());
CREATE TABLE app.simulado (...);          -- usuario, concurso, cargo, início, fim, nota
-- roles: site_leitura (SELECT nas views, EXECUTE fn_prova_cobra), site_app (CRUD em app)
```

---

## 4. Sessões

### 5F.1 — API de leitura ✅ (2026-09-29)
- `vw_questoes` ganha a coluna `questao_chave` (`concurso|codigo_caderno|numero`,
  a mesma de `canonico/classificacao_questoes.json`) — conferir que casa
  1:1 com os 2.834 registros da 5D.
- Roles `site_leitura`/`site_app` em `site/sql/app_schema.sql` (idempotente,
  senhas do `.env`).
- `GET /api/v1/questoes`: filtros combináveis `banca, orgao, ano, concurso,
  cargo_numero, nivel, tipo_conhecimento, no_id` (inclui descendentes via
  `materia_id/assunto_id`), `anuladas` (incluir/excluir/só),
  `fora_do_edital`; paginação por cursor ou `limit/offset` (máx. 50);
  1 item por questão (agregando os nós).
- `GET /api/v1/questoes/{chave}`: texto-base, figuras (URL), gabarito,
  caminhos na árvore, fonte (concurso, caderno, link ao PDF).
- `GET /api/v1/arvore` (matéria → assunto → subassunto com contagem de
  questões) e `GET /api/v1/facetas` (valores de cada filtro).
- Testes com banco real (fixture que pula se o Postgres não estiver no ar,
  no padrão de `tests/test_estatisticas_views.py`).
- **Pronto quando:** a soma das questões distintas sem filtro = 2.800; o
  filtro por subassunto de Língua Portuguesa + nível superior bate com
  uma consulta SQL feita à mão.

### 5F.2 — Frontend de resolução ✅ (2026-09-30)
- Layout base (Pico.css), lista filtrável com HTMX (`hx-get` no formulário
  de filtros, `hx-push-url` para URL compartilhável), árvore de filtros
  expansível (Alpine).
- Card de questão: enunciado, texto-base recolhível, figuras, botões C/E →
  `POST` devolve o fragmento com a correção imediata (anônimo: sem gravar).
- Página canônica por questão `/q/<concurso>/<caderno>/<numero>` com
  `<title>`/meta description, crédito "Fonte: CEBRASPE" e link ao PDF.
- Página "Sobre e fontes" + canal de remoção (ADR-033 §5).
- **Pronto quando:** navegar da matéria ao subassunto, resolver 10 questões
  e ver a correção, com HTML válido e testes das rotas.
- **Entregue (2026-10-01):** `site/app/web/rotas_web.py` (fora do OpenAPI),
  templates em `site/app/templates/`, Pico/HTMX/Alpine locais em
  `site/app/static/` e figuras em `/figuras`. Texto-base e figuras do card
  da lista vêm de `GET /q/<concurso>/<caderno>/<numero>/anexos`, aberto sob
  demanda: o contrato da API da 5F.1 não mudou. Canal de remoção:
  `athosroque@hotmail.com`. Validado no Chromium headless.
- **Fica para depois:** as contagens da árvore são globais e não mudam com
  os outros filtros (um subassunto pode mostrar N e devolver 0 combinado com
  órgão/nível). Exige contagem por faceta.

### 5F.3 — Contas e histórico (estatística 4: desempenho pessoal) ✅ (2026-10-01)
- Google OAuth (Authlib), sessão em cookie assinado, CSRF nos POST.
- Aplicar o schema `app`; resposta logada grava em `app.resposta`.
- Filtros "já resolvidas" / "erradas" (JOIN por `questao_chave`).
- Desempenho por nó (acertos/erros subindo a árvore, mesma regra da 5E:
  questão distinta, nunca conta 2× no mesmo nó), com os mesmos filtros.
- "Apagar minha conta" (cascata).
- **Pronto quando:** login real com a conta do dono, 20 respostas gravadas,
  o desempenho por matéria bate com a contagem manual.

### 5F.4 — Páginas de estatística ✅ (2026-10-01)
- (1) O que mais cai: `fn_prova_cobra` com filtros (concurso/cargo/nível),
  ranking de subassuntos e barras (SVG no servidor ou Chart.js).
- (2) O que o edital cobra: `vw_edital_cobra_*`.
- (3) Edital × prova: `vw_edital_vs_prova` (cobrado, nunca cobrado, fora
  do edital) + `vw_peso_materia_cargo`.
- Cada ranking linka para a lista de questões já filtrada.
- **Pronto quando:** os três exemplos do "pronto quando" da 5E aparecem nas
  páginas com os mesmos números.

### 5F.5 — Simulado ✅ (2026-10-01)
- Montar a prova de um concurso/cargo: básico + específico na ordem
  original (`codigo_caderno`, `numero`), cronômetro (Alpine), respostas em
  branco permitidas.
- Correção CEBRASPE em `servicos/` (certo +1, errado −1, branco 0, anulada
  não conta), com teste unitário de casos-limite; desempenho por nó.
- Discursiva: mostra tema e quesitos (`vw_discursivas`) e o padrão de
  resposta depois de encerrar; sem nota automática.
- **Pronto quando:** simulado `PF_25_ADM` cargo 1 respondido com um padrão
  conhecido e a nota conferida à mão.

### Redesenho (2026-10-02)
Protótipo aprovado pelo dono: https://claude.ai/artifact/323qGK9cuTRHdJjRSS9DUE
(6 telas: Início "escolha sua matéria", Painel da matéria, Resolver questões,
Meu concurso, Meu desempenho com caderno de erros, Resultado do simulado).
Decisões: entrada pela matéria; "Meu concurso" com login; Tailwind; "mais cai"
em cor discreta. A documentação vem antes dos endpoints para que o teste guarda
obrigue toda rota nova a nascer documentada.

### 5F.6 — Documentação da API (Swagger/ReDoc) ✅ (2026-10-02)
- `openapi_tags` com descrição (Questões, Árvore, Facetas, Matérias, Conta,
  Estatísticas, Simulado, Autenticação, Infra) e `description` geral: como
  autenticar (cookie `sessao` + `X-CSRFToken`), chave `concurso|caderno|numero`,
  crédito à fonte, rotas HTML fora do contrato.
- `securitySchemes`: `APIKeyCookie("sessao")` e `APIKeyHeader("X-CSRFToken")`
  com `auto_error=False` em `auth.py` (comportamento igual, mantém o fallback do
  campo `csrf_token`).
- Modelo `Erro {detail}` e respostas 401/403/404/409 compartilhadas em
  `app/api/v1/respostas_comuns.py`.
- `description` nas rotas que faltam (`GET`/`DELETE /eu`, `GET`/`POST /simulados`,
  `GET /simulados/{id}`, `/saude` com 503).
- `Field(description=...)` em todos os campos (hoje 169 de 194 sem), docstring
  em todo schema, exemplos reais (PF_25_ADM item 1) nos modelos principais.
- `/entrar`, `/auth/google` e `/sair` no contrato (tag "Autenticação",
  redirecionamentos 303); as demais rotas HTML continuam fora.
- Teste guarda `site/tests/test_openapi_documentado.py`: toda operação com
  `summary` e `description`; 401/403/404 declarados conforme dependência e
  parâmetro de caminho; todo schema e campo próprio com descrição.
- **Pronto quando:** teste guarda verde, `openapi.json` regenerado e `/docs`
  mostra tags descritas e o "Authorize" com cookie e CSRF.

- **Junto com esta sessão (decisão do dono, 2026-10-02):** ligar no frontend
  os blocos que ficaram com `{# TODO 5F.7 #}`/`{# TODO 5F.8 #}` nas 5F.9–5F.11
  (questões parecidas, selo de incidência, plano de estudo, concurso-alvo,
  dias seguidos, "revisar as que errei", duração e nota anterior do simulado)
  à medida que os endpoints da 5F.7/5F.8 nascem documentados.

### 5F.7 — Endpoints públicos novos ✅ (2026-10-02)
- `GET /api/v1/materias`: matérias da árvore ativa com total de questões
  (distinta, sobe a árvore, utilizável) e `nome_de_cargo`.
- `GET /api/v1/materias/{materia_id}`: resumo + top subassuntos por
  `fn_prova_cobra` (via `estatisticas_servico.prova_cobra`), com recorte de
  concurso/cargo/nível; 404 se não for matéria ativa.
- `GET /api/v1/busca?q=`: nós da árvore por nome, sem acento e sem caixa,
  máx. 20 (não busca enunciado).
- `GET /api/v1/questoes/{chave}/parecidas`: mesmo nó principal, sem a própria
  e sem enunciado canônico repetido (`listar_questoes` + `chaves_excluir`).
- Campo aditivo `incidencia` em `QuestaoResumo`/`QuestaoDetalhe`: posição do
  subassunto principal no ranking da matéria (cache por processo).
- **Pronto quando:** LP com 178 questões em `/materias`; top 1 de LP =
  "Substituição de palavras…" (15; a base atual dá 14, divergência em aberto); testes de 404.

### 5F.8 — Endpoints pessoais novos ✅ (2026-10-02)
- `GET /api/v1/eu/resumo`: resolvidas, acerto, nota líquida, erradas pendentes,
  dias seguidos (fuso `America/Sao_Paulo`).
- `GET /api/v1/eu/prioridades`: subassuntos com ≥ 2 respostas, por
  incidência × taxa de erro (cruzamento no serviço, sem JOIN `app` × views).
- `GET /api/v1/eu/plano?concurso&cargo_numero`: peso da matéria
  (`vw_peso_materia_cargo`) × (1 − acerto).
- `GET`/`PUT /api/v1/eu/concurso-alvo` + colunas `concurso_alvo`/`cargo_alvo`
  em `app.usuario` (`ALTER ... ADD COLUMN IF NOT EXISTS` em `app_schema.sql`);
  `GET /eu` passa a devolver o alvo.
- `ResultadoSimulado` ganha `duracao_segundos` e `nota_anterior`;
  `GET /api/v1/simulados/{id}/questoes?situacao=errado|branco` reusa
  `listar_questoes(chaves_incluir=...)`.
- **Pronto quando:** plano de PF_25_ADM cargo 1 sem respostas começa por AOF
  (17,80%); prioridades e resumo batem com um usuário de teste de respostas
  conhecidas; 401/403/404 cobertos.

### 5F.9 — Tailwind: base, Início e Painel da matéria ✅ (2026-10-02, visual; blocos de 5F.7/5F.8 com `TODO`)
- Tailwind pelo binário standalone (sem Node); `site/scripts/gerar_css.sh`
  gera `static/tailwind.css` (versionado, teste de divergência); Pico sai.
- Tokens do protótipo: `slate-50`/`slate-900`/`slate-600`, destaque `blue-700`,
  "mais cai" discreto (`slate-100`/`blue-300`), fonte Public Sans.
- Macros Jinja em `templates/_componentes.html` (cabeçalho, card, chip de
  filtro, barra de ranking, KPI). Menu: Questões · Matérias · Meu concurso ·
  Simulados · Meu desempenho.
- **Pronto quando:** Início e Painel iguais ao protótipo em 1280 e 390 px, sem
  erro de JS no Chromium headless.

### 5F.10 — Tailwind: Resolver questões e Meu concurso ✅ (2026-10-02, visual; blocos de 5F.7/5F.8 com `TODO`)
- Barra de filtros em chips (modal da árvore com busca), card limpo com selo de
  incidência, "questões parecidas", painel Meu concurso (peso, edital × prova,
  plano).
- **Pronto quando:** fluxo matéria → painel → questões → correção funcionando,
  com os anti-patterns de HTMX/Alpine do CLAUDE.md respeitados.

### 5F.11 — Tailwind: Meu desempenho, Simulado e páginas restantes ✅ (2026-10-02, visual; blocos de 5F.7/5F.8 com `TODO`)
- Desempenho (KPIs, "o que estudar agora", caderno de erros), simulado (início,
  prova, resultado com "revisar as que errei"), página da questão, sobre, 404.
- **Pronto quando:** todas as telas no novo visual; nenhum template usa Pico.

### 5F.12 — Deploy público (opcional)
> Opcional por decisão do dono (2026-10-06): o site ainda vai mudar muito
> antes de ir ao público.
- `Dockerfile` (python:3.11-slim, uvicorn, usuário não root) e serviço
  `scraper-cebraspe-site` no `docker-compose.yml` (labels Traefik,
  `homelab_default`, figuras montadas `:ro`).
- Cloudflare Tunnel para o subdomínio público, **sem** Access; middleware de
  rate limit no Traefik; headers (CSP, HSTS, nosniff); `/saude`.
- Backup `pg_dump -n app` diário (systemd timer do usuário) com retenção de 14 dias.
- CI: ruff + pytest do `site/` no workflow do projeto.
- **Checklist de direitos:** o dono leu os termos de `cebraspe.org.br`; sem
  proibição expressa → público; com proibição → fica atrás do Access.
- **Pronto quando:** o "pronto quando" da seção 1, acessando pelo domínio
  público de fora da rede.

---

## 5. Ideias opcionais (fazer só se sobrar tempo na sessão)

- **Recuperar as 19 questões ilegíveis** (`simbolo_ilegivel`, caderno
  `094_PF_005_01`, Estatística da PF): recortar a região do item no PDF como
  imagem na extração e exibi-la no lugar do texto. Hoje a API as esconde por
  padrão (`utilizaveis=so`, decisão do dono em 2026-09-30).
- "% de acerto da comunidade" por questão (agregado anônimo de `app.resposta`).
- Filtro rápido "nunca cobrado no edital do meu cargo".
- Sitemap XML das páginas de questão.
- Modo escuro via `prefers-color-scheme` (Pico já suporta).

## 6. Anti-patterns desta etapa
- SQL ou regra de negócio em template/rota (quebra a migração da Fase 2).
- Referenciar `questoes.id` fora do banco de conteúdo (muda a cada reextração).
- Somar `vw_prova_cobra_*` entre cargos (usar `fn_prova_cobra`).
- Misturar discursiva com objetiva nas contagens.
- Usar o usuário `cebraspe` no site ou expor `data/` inteiro.
- `questao_chave` crua como id HTML (o `|` quebra o seletor do `hx-target`).
- Valor da query string dentro de expressão do Alpine (XSS); usar `data-*`.
- `hx-get` em campo dentro do form de filtros (GET envia só o próprio campo).
