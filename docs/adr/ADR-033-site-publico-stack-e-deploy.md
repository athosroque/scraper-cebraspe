# ADR-033: Site Público de Questões — Stack, Autenticação, Dados de Usuário, Deploy e Direitos

## Status
Aceito (Etapa 5F.0 concluída em 2026-09-29; implementação nas Etapas 5F.1–5F.6)

## Data
2026-09-29

## Contexto

O ADR-030 definiu o produto: um **site público de questões** (estilo Gran
Questões), com a questão como entidade central e o subassunto como unidade
de estudo. A Etapa 5E entregou a camada de leitura no Postgres próprio
(`scraper-cebraspe-db`): `vw_questoes` (4.075 linhas = questão × nó, com
concurso, órgão, ano, cargo, nível, gabarito, texto-base, figuras e o
caminho na árvore), `fn_prova_cobra(...)`, `vw_edital_cobra_*`,
`vw_edital_vs_prova`, `vw_peso_materia_cargo` e `vw_discursivas`.

Faltava decidir como o site é construído e publicado: stack da API e do
frontend, autenticação, onde vivem os dados de usuário, como expor no Xeon
e se as provas podem ser republicadas.

Restrições:
- Projeto de portfólio, um desenvolvedor, servidor próprio (Xeon, Ubuntu
  24.04, Traefik + Cloudflare Tunnel, sem porta aberta no firewall).
- O backend do projeto é Python (pydantic, psycopg2), e o portfólio já tem
  FastAPI (`racao-tracker`, `genesys-manager-api`).
- O conteúdo tem de ser indexável (a página de questão é a porta de entrada
  pelo Google).
- A chave serial `questoes.id` **não é estável**: a extração (5C) faz
  DELETE + INSERT por caderno. A chave estável é a da 5D
  (`<concurso>|<caderno>|<numero>`, ADR-032).

## Decisão

### 1. Stack em duas fases, com a migração garantida pela arquitetura

**Fase 1 (5F.1–5F.6):** FastAPI + Jinja2 renderizado no servidor, **HTMX**
para as trocas parciais (aplicar filtro, responder Certo/Errado, paginar) e
**Alpine.js** para estado só do navegador (cronômetro do simulado, abrir e
fechar o texto-base). CSS com Pico.css (sem etapa de build JS). A escolha é
do dono: começar simples, em Python, e migrar para um frontend moderno
depois.

**Regra que deixa a migração barata (obrigatória desde a 5F.1):** três
camadas.

```
repositorio/  SQL só sobre as views da 5E e o schema app  → dicts/rows
servicos/     regras (filtros, paginação, correção CEBRASPE, desempenho)
              → modelos Pydantic
api/          /api/v1/*  JSON   ┐ adaptadores finos,
web/          rotas HTML Jinja  ┘ sem SQL e sem regra
```

- Template nunca consulta o banco nem calcula nada.
- Toda tela HTML tem o endpoint JSON equivalente em `/api/v1`, com teste.
- Os modelos Pydantic de resposta são o contrato (OpenAPI gerado pelo
  FastAPI).

**Fase 2 (fora da 5F):** frontend em SvelteKit (SSR, mantém o SEO)
consumindo `/api/v1`, sem mudar `repositorio`/`servicos`. **Gatilho:** site
no ar com o piloto 2025 **e** alguma tela (simulado, árvore de filtros) cuja
UX fique limitada pelo HTMX. Até lá, migrar é custo sem ganho.

### 2. Autenticação: só Google OAuth

- Authlib (OIDC do Google), sessão em cookie assinado (`HttpOnly`,
  `Secure`, `SameSite=Lax`), token CSRF nos POST.
- Sem senha e sem SMTP: nada de hash, reset ou e-mail transacional.
- Ler e resolver questões é **anônimo**. O login só serve para gravar
  histórico, ver o desempenho pessoal e salvar simulado.
- Guardamos só `sub` do Google, e-mail e nome. Botão "apagar minha conta"
  (LGPD) remove o usuário e as respostas em cascata.

### 3. Dados de usuário: mesmo container, schema `app`, roles separadas

- Schema `app` no `scraper-cebraspe-db`: `usuario`, `resposta`, `simulado`,
  `simulado_resposta`.
- A questão é referenciada pela **chave estável** da 5D
  (`questao_chave text`, `<concurso>|<caderno>|<numero>`), sem FK para
  `questoes.id`. Nova coluna/expressão `chave` exposta em `vw_questoes`
  (5F.1) para o JOIN.
- Roles:
  - `site_leitura`: `SELECT` só nas views de conteúdo (`vw_questoes`,
    `vw_discursivas`, `vw_no_caminho`, `vw_edital_*`, `vw_prova_cobra_*`,
    `vw_peso_materia_cargo`) e `EXECUTE` em `fn_prova_cobra`.
  - `site_app`: CRUD só no schema `app`.
  - O site **nunca** usa o usuário `cebraspe` (dono do pipeline).
- Backup: `pg_dump -n app` diário com retenção (5F.6). O conteúdo é
  regenerável pelo pipeline e não entra nesse backup.

### 4. Hospedagem

- Serviço novo `scraper-cebraspe-site` no `docker-compose.yml` deste
  projeto, rede `homelab_default`, labels do Traefik no mesmo padrão do
  Datasette, subdomínio público (proposta: `questoes.projetoathos.com.br`)
  via Cloudflare Tunnel, **sem Cloudflare Access**. O Datasette continua
  atrás do SSO.
- O banco continua só em `127.0.0.1:5435` e na rede interna.
- As figuras (`data/<ano>/CEBRASPE/<orgao>/Provas/figuras/`) são
  montadas **somente leitura** e servidas numa rota estática própria com
  cache longo. `data/` inteiro nunca é exposto.
- Rate limit no middleware do Traefik; headers de segurança (CSP, HSTS,
  `X-Content-Type-Options`); `/saude` checa o banco (para o Grafana).

### 5. Direitos de republicação

- As provas são documentos publicados abertamente pelo CEBRASPE. A Lei
  9.610/98 (art. 8º) exclui da proteção autoral os atos oficiais e os
  textos de leis, mas prova de concurso **não** está listada
  expressamente, e a banca é uma associação privada. Não há, nesta
  análise, parecer jurídico que resolva a questão. Sites comerciais
  grandes (QConcursos, Gran Questões) republicam essas provas há anos.
- Postura adotada (uso não comercial, portfólio):
  1. crédito "Fonte: CEBRASPE, <concurso>, <caderno>" e link para o PDF
     original em toda questão;
  2. página "Sobre e fontes" explicando a origem dos dados e que o site
     não tem vínculo com a banca;
  3. canal de remoção (e-mail) com compromisso de retirar o conteúdo
     questionado;
  4. sem cobrança e sem anúncio;
  5. texto-base de terceiros (reportagem, trecho de livro) mantém a
     citação que já vem na própria prova.
- **Pendente antes do deploy público (checklist da 5F.6):** o dono lê os
  termos de uso de `cebraspe.org.br` e, se houver proibição expressa de
  reprodução, o site fica atrás do Cloudflare Access até resolver.

## Alternativas descartadas

- **SvelteKit desde já:** melhor UX e SEO, mas junta duas curvas novas (Node
  + framework) ao trabalho de produto. Fica para a Fase 2, com o contrato
  `/api/v1` pronto.
- **Vue 3 SPA (stack do `racao-tracker`):** reaproveita conhecimento, mas
  a SPA pura não indexa bem as páginas de questão.
- **Astro (stack do `site-portfolio`):** ótimo para páginas estáticas, mas
  o resolver e o simulado são interativos e o conteúdo muda com filtros.
- **E-mail + senha próprios:** mais código e mais superfície de ataque
  (hash, reset, SMTP) sem ganho para um piloto.
- **Auth gerenciado (Supabase/Clerk):** tira os dados de usuário do Xeon e
  adiciona dependência externa.
- **Postgres separado para usuários:** isolamento total, mas o desempenho
  por nó precisa de JOIN com `vw_questao_no` (daria `postgres_fdw` ou cópia).
  Schema separado + roles já isola permissão e backup.
- **FK de `app.resposta` para `questoes.id`:** quebra a cada reextração de
  caderno (DELETE + INSERT, ADR-031).

## Consequências

- **Positivas:** tudo em Python na Fase 1; SEO grátis com SSR; a migração
  do frontend não toca a regra de negócio; um único banco com permissões
  separadas; nenhum segredo de senha guardado.
- **Negativas:** HTMX limita UX muito rica (drag, gráficos interativos
  complexos) até a Fase 2; quem não tem conta Google não salva histórico;
  risco jurídico residual de republicação, mitigado pela postura acima e
  não eliminado.
- **Operacionais:** novo serviço público no Xeon exige rate limit, headers,
  backup do schema `app` e CI da API (5F.6).

## Notas de implementação

- **5F.2 (2026-10-01):** as rotas HTML ficam em `site/app/web/` com
  `include_in_schema=False` e chamam a mesma camada `servicos` da API. O
  card da lista não recebe texto-base nem figuras: abre
  `GET /q/<concurso>/<caderno>/<numero>/anexos` sob demanda, para não
  aumentar `QuestaoResumo` (o contrato da 5F.1 é o mesmo). Id de elemento
  derivado da chave por hash (`q-<sha1>`), porque o `|` não vale em
  seletor CSS. Canal de remoção: `athosroque@hotmail.com`.
- **5F.3 (2026-10-01):** sessão em cookie assinado (`SessionMiddleware`,
  cookie `sessao`, `SameSite=Lax`, 30 dias) com só o id do usuário, o nome e
  o token CSRF; a sessão é recriada no login. CSRF em todo POST/DELETE, pelo
  header `X-CSRFToken` (HTMX via `hx-headers` do `<body>`, API) ou pelo campo
  `csrf_token` (forms comuns). Google OAuth via Authlib (`/entrar`,
  `/auth/google`), só e-mail verificado; `voltar` aceita só caminho local.
  Login fica desligado sem `GOOGLE_CLIENT_ID`. Histórico e desempenho usam a
  **resposta mais recente** de cada questão; anulada não é gravada; resposta
  de simulado (`simulado_id`) fica fora. A role de leitura não lê `app`:
  o serviço busca as chaves respondidas pela `site_app` e passa a lista ao
  SQL das views (`questao_chave = ANY(...)`). Desempenho por nó segue a 5E
  (sobe a árvore, uma vez por nó). API: `POST /api/v1/respostas`,
  `GET/DELETE /api/v1/eu`, `GET /api/v1/eu/desempenho`, `historico=` na
  listagem (401 sem login). Em produção (5F.6): `SESSION_HTTPS_ONLY=true` e
  uvicorn com `--proxy-headers`, senão o `redirect_uri` sai `http://`.
- **5F.4 (2026-10-01):** páginas `/estatisticas` (o que mais cai),
  `/estatisticas/edital` e `/estatisticas/edital-vs-prova`, espelhadas em
  `GET /api/v1/estatisticas/{prova-cobra,edital-cobra,edital-vs-prova}`.
  "O que mais cai" vem só de `fn_prova_cobra` (nunca soma de
  `vw_prova_cobra_*`). As `vw_edital_cobra_*` não têm filtro de concurso ou
  cargo, então o "edital cobra" repete a regra da `vw_edital_cobra_base`
  sobre `vw_arvore_edital_por_cargo` (item distinto, sobe a árvore, só
  `aprovado`), com `SELECT` novo para a `site_leitura`; sem filtro, bate com
  as views. Barras em CSS no servidor (sem Chart.js). Cada linha linka para
  a lista com `no_id`, os mesmos filtros e `anuladas=excluir`. A lista pode
  ter mais questões que o ranking, porque mostra o enunciado repetido em
  cadernos diferentes e a estatística conta a questão canônica uma vez.
  `cargo_numero` chega como texto nas rotas HTML: trocar o concurso manda
  o campo vazio, que como `int` dava 422.

## Referências
- ADR-026 (banco próprio), ADR-030 (árvore mestre e objetivo do site),
  ADR-031 (extração, DELETE + INSERT por caderno), ADR-032 (chave estável
  da questão, 5E).
- `plano-etapa-5f.md` (execução por sessão).
