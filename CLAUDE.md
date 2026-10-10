Template version: 1.2

# Scraper CEBRASPE — Coleta Estruturada de Editais, Provas e Gabaritos

## 1. Identidade

- **ID:** `scraper-cebraspe` (diretório físico: `scraper_cebraspe/`)
- **Nome legível:** Scraper CEBRASPE — Coleta Estruturada de Editais, Provas e Gabaritos
- **Guia de referência:** `task.md` (roteiro de implementação por etapas, neste diretório)
- **Status:** in-progress:phase-6
- **Repositório GitHub:** homelab local / a versionar

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

## 5. Progresso

- [x] Fase 1 — Preparação: `requirements.txt` completo instala sem erro;
      `models_scraper.py` com hierarquia Concurso→Cargo→Taxonomia aninhada
      (sem listas paralelas); `.env.example` e `.gitignore` presentes
- [x] Fase 2 — Crawler: `spider.py` filtra ano pelo slug da URL (não pelo
      texto do link), percorre `/concursos/encerrado`, falha de um concurso
      não aborta o lote, idempotência por registro local
      (`data/processed_concursos.json`). Auditado ao vivo em 2026-09-19:
      encontrado e corrigido um bug crítico de href relativo que zerava o
      resultado do crawler em produção (ADR-008) — 31 concursos de
      2025 confirmados após a correção.
- [x] Fase 3 — Download: `downloader.py` valida PDFs (magic bytes `%PDF-` +
      Content-Type) e grava em `data/<ano>/CEBRASPE/<orgao_slug>/{Editais,
      Provas,Gabaritos}/` com dedup por URL (manifesto) e por hash de
      conteúdo; `spider.py` ganhou `extract_orgao_from_slug` (o nome do
      órgão também só existe no slug, mesma causa-raiz da Fase 2); 21 testes
      cobrindo slugify, validação de PDF, dedup e resolução de href.
      Auditado ao vivo em 2026-09-19 contra PDFs reais do CEBRASPE — sem
      falhas encontradas no downloader em si.
- [x] Fase 4 — Extração híbrida: `edital_parser.py` (seção "OBJETOS DE
      AVALIAÇÃO" + chunking por cargo/matéria) e `taxonomia_extractor.py`
      (LLM via OpenRouter direto, validado contra `TaxonomiaEdital`) implementados
      e validados ao vivo contra editais reais de 2025: `PF_25_ADM` (39 chunks),
      `TCU_25_TEFC` (10 chunks), `IBAMA_25` (33 chunks), `STM_25` (53 chunks)
      e `CD_25_NS` (15 chunks), totalizando 150 chunks processados com 100% de sucesso.
      Checkpoint `scripts/revisar_taxonomia_piloto.py` e `scripts/reprocessar_falhas_piloto.py`
      consolidados em `revisao_piloto/`, com trilha de auditoria completa
      (`<edital>.auditoria.json`) e navegável via Datasette local e público
      (`https://datasette.projetoathos.com.br`).
      Parser robustecido contra quebras reais do Cebraspe: normalização `\xa0`,
      absorção de títulos multi-linha de cargo, suporte a `CONHECIMENTOS GERAIS`,
      cabeçalhos de matérias multi-linha com conectivos e prefixos de matéria sem dois-pontos.
      Validação heurística de-para (`scripts/validar_taxonomia.py`) refinada para
      eliminar falsos positivos: normalização Unicode NFC (acentos combinantes NFD),
      mapeamento de ligaduras de fonte (`Ɵ` -> `ti`, `Ō` -> `ft`, `ﬃ` -> `ffi`),
      cobertura uniforme de tópicos + subtópicos e match por fronteira de palavra `\b`.
      Relatórios HTML e banco `revisao.db` gerados automaticamente via
      `scripts/atualizar_revisao.py` (ADR-019). Os 3 alertas residuais foram
      tratados no pipeline (ADR-025): reinjeção determinística de item omitido
      pelo LLM e severidade `informativo` para paráfrase leve. A base de 2025
      fica com 0 alertas bloqueantes e 2 informativos. **Revisão humana feita
      pelo dono e registrada em 2026-09-23** nos 5 `<edital>.json`
      (`status_revisao_humana`; o texto do status mantém "2026-09-22", como
      pedia a spec), ingerida como `status_revisao = 'aprovado'` (ADR-028).
- [x] Fase 5 — Banco de estatísticas: star schema criado no Postgres próprio
      (`scraper-cebraspe-db`, ADR-026) com chaves naturais normalizadas
      (`src/sql/schema_estatisticas.sql`); `src/stats_writer.py` grava de
      forma idempotente (reexecução com contagens idênticas, validado ao vivo
      em 2026-09-22) e roda no fim de `scripts/atualizar_revisao.py`; fila
      `fila_extracao_questoes` populada. Carga real: 5 concursos, 31 cargos,
      1485 tópicos, 70 provas, 145 PDFs na fila e 3 editais administrativos
      pulados. Depois da Etapa 5A: os 5 concursos estão `aprovado` e
      `dim_materia` tem 102 matérias (as 4 variantes "(APENAS PARA ...)"
      viraram a matéria base + `cargos_restritos`). Ver ADR-027 e ADR-028.
- [x] Etapa 5C — Extração de questões, gabaritos e discursivas: `src/gabarito_parser.py`,
      `src/prova_parser.py`, `src/questoes_writer.py` e consumidor `scripts/extrair_questoes.py`.
      70 cadernos processados (2.800 itens, 129 anulados, 34 discursivas / 107 quesitos, 145 PDFs na fila).
      Gabaritos em hash (TCU/CD) ligados pelo código impresso no PDF. Bug de recuo em `_recuo_item`
      corrigido para a faixa estrita de 12 a 24 pt. JSONs gerados em `questoes/` mantidos localmente
      (`questoes/` no `.gitignore`). 374 testes no pytest e ruff verde (ADR-031).
- [x] Etapa 5C.1 — Correções da extração (Sessões 1 a 5, `docs/planos/correcoes-etapa-5c.md`): posição dos itens por x0 (cluster/moda); alertas no item no Postgres (alertas text[], utilizavel boolean, view vw_questoes_utilizaveis); fila reprocessada por assinatura_grupo; lock pg_try_advisory_lock (5031001); gabarito definitivo x preliminar no cabeçalho; quesitos discursivos após comando; tema anafórico rejeitado; padrão ligado por chave de título. 435 testes (+1 xfail) no pytest e base inalterada (ADR-031).
- [x] Etapa 5B.1 — Árvore mestre semeada com a 5B (ADR-030): `canonico/arvore.json`
      (3730 nós: 89/1148/2493, 4050 mapeamentos `semente`, 100% dos nomes),
      `src/arvore.py`, `scripts/semear_arvore.py` (recusa sobrescrever árvore
      curada), `scripts/curar_arvore.py`, regra do pipeline
      (`canonico.mapear_novos_itens_por_regra`) e `arvore.html`. Banco:
      `no_arvore` + pontes (102/1259/2689), `vw_no_caminho` (resolve fundido,
      só cadeia ativa), `vw_arvore_edital_por_cargo` (9569 linhas, 1485/1485
      itens) e `vw_edital_cobra_{materia,assunto,subassunto}` (+ `_todas`).
      Tabelas `*_canonico` removidas. 476 testes (+1 xfail), ruff verde.
- [x] Etapa 5B.2 — Curadoria da árvore (ADR-030): propostas de operação no
      `arvore.json` (`fundir`/`mover`/`criar`/`remapear`/`aposentar`,
      aprovação em lote tudo ou nada), status `aposentado`,
      `detectar_compostos` e `detectar_homonimos` (regra) e
      `scripts/propor_arvore.py` (LLM por matéria). Rodada real de 83
      chamadas e 210 propostas: o dono rejeitou 29 e aprovou o resto. Árvore:
      3577 nós ativos, 148 fundidos e 6 aposentados; matéria nova "Processo
      Legislativo" para os assuntos de processo legislativo das matérias
      compostas do CD; "Disposições gerais" e "Servidores públicos" com 8 e 7
      ocorrências no edital (ADR-030).
- [x] Etapa 5D — Classificação das questões na árvore mestre (ADR-032): fonte canônica
      `canonico/classificacao_questoes.json` (2.834 registros, chave estável
      `<concurso>|<caderno>|<numero>`, hash SHA-1 do enunciado), `src/classificacao.py`,
      `src/candidatos_questao.py` (preferencial × reserva), `scripts/classificar_questoes.py`
      (450 chamadas LLM, $0.1939 USD, 0 falhas finais), `scripts/gerar_relatorio_classificacao.py`
      (`classificacao.html`), `scripts/curar_classificacao.py` (`--mapear`, `--aprovar`,
      `--rejeitar`, `--aprovar-lote`, `--pendentes`). Banco derivado: `questao_no`,
      `discursiva_no` e view `vw_questao_no`. Testes no pytest e ruff verde.
- [x] Etapa 5E — Estatísticas e Views de Incidência (ADR-032): Sessões A, B e C
      concluídas ($0.00 USD, 100% determinístico). Backfill de `materia_origem` (150 chunks)
      e colunas `dim_materia.nome_de_cargo` e `taxonomia_itens.materia_origem`.
      Views analíticas em `src/sql/schema_estatisticas.sql`: `vw_questoes_contexto`,
      `vw_questoes`, `vw_prova_cobra_base`, `vw_prova_cobra_no` (+ atalhos `_subassunto`,
      `_assunto`, `_materia`), função `fn_prova_cobra` (leitura oficial com desduplicação
      canônica de enunciados repetidos e média com peso igual por concurso),
      `vw_certo_errado_por_no`, `vw_comparativo_nivel`, `vw_edital_vs_prova` (cobertura
      descendente), `vw_peso_materia_cargo` e `vw_discursivas` (64 linhas analíticas).
      Reconciliação total: 2.781 questões utilizáveis (2.652 válidas + 129 anuladas),
      19 ilegíveis descartadas. 4.055 pares expandidos na consistência 5D × 5E com 0
      divergências. 609 testes (+1 xfail) no pytest e ruff 100% verde.
- [x] Fase 6 — Piloto (concluída em 2026-10-06, ver `task.md`): fluxo ponta a ponta validado no crawler, downloader,
      parser e extração LLM para 5 concursos de 2025 (`PF_25_ADM`, `TCU_25_TEFC`,
      `IBAMA_25`, `STM_25` e `CD_25_NS`), acumulando 150 chunks sem bloqueios nem falhas
      de inferência (0 alertas de validação no `CD_25_NS`). Gravados com aprovação no
      Postgres (`status_revisao = 'aprovado'`). A revisão humana da Fase 4 foi
      registrada e homologada no banco (Etapa 5A concluída, ADR-028). Critérios
      conferidos: 158/158 PDFs válidos, fila 145/145, 0 ERROR no log de uma
      execução real (log isolado dos testes pelo `conftest.py` da raiz).
- [x] Etapa 5F.0 — Decisões do site público (ADR-033): FastAPI + Jinja2/HTMX/Alpine
      em 3 camadas (`repositorio` → `servicos` → `api/v1` JSON e `web` HTML) para
      migrar o frontend depois (SvelteKit) sem tocar a regra; só Google OAuth;
      schema `app` no `scraper-cebraspe-db` com roles `site_leitura`/`site_app`
      e chave estável da 5D; deploy via Traefik + Tunnel sem Access. Plano em
      `docs/planos/plano-etapa-5f.md`.
- [x] Etapa 5F.1 — API de leitura (ADR-033): `questao_chave` em `vw_questoes`
      (2.800 chaves, 1:1 com a 5D; as 34 restantes da 5D são discursivas);
      `site/app` em 3 camadas com `GET /api/v1/questoes` (filtros + paginação,
      máx. 50), `/questoes/{chave}`, `/arvore`, `/facetas` e `/saude` (503 se o
      banco cair). Roles `site_leitura`/`site_app` com senha só no `.env`,
      aplicadas por `site/scripts/aplicar_schema_app.py`. Contrato em
      `site/openapi.json` (versionado, teste de divergência) e Swagger em `/docs`.
      Listagem, árvore e facetas escondem por padrão as 19 questões com
      `utilizavel=false` (fórmulas ilegíveis do caderno `094_PF_005_01`):
      2.781 no padrão, 2.800 com `utilizaveis=todas`; o detalhe por chave segue
      acessível.
      619 testes (+1 xfail), ruff verde.
- [x] Etapa 5F.2 — Frontend de resolução (ADR-033): rotas HTML em
      `site/app/web/rotas_web.py` (fora do OpenAPI) e templates Jinja2 com
      Pico.css/HTMX/Alpine servidos de `site/app/static/` (figuras em
      `/figuras`). Lista filtrável (form inteiro a cada `change`, URL
      compartilhável, página volta a 1), árvore matéria → assunto →
      subassunto, correção C/E por fragmento (anônimo, sem gravar), página
      canônica `/q/<concurso>/<caderno>/<numero>` com meta description e
      crédito "Fonte: CEBRASPE", `/sobre` com canal de remoção
      (`athosroque@hotmail.com`) e 404 com layout. Texto-base e figuras
      carregam sob demanda (`/q/.../anexos`), e o contrato da API da 5F.1
      ficou inalterado. Validado no Chromium headless (10 questões
      corrigidas, filtros combinados, árvore, voltar do navegador, sem erro
      de JS). 25 testes no `site/`, ruff verde.
- [x] Etapa 5F.3 — Contas e histórico (ADR-033): Google OAuth (Authlib),
      sessão em cookie assinado, CSRF em todo POST/DELETE; `app.resposta`
      gravada com login (anulada não grava); filtro `historico`
      (resolvidas/não resolvidas/certas/erradas, pela resposta mais recente);
      desempenho por nó em `/conta` e `/api/v1/eu/desempenho` (regra da 5E);
      "apagar minha conta" em cascata. Login real com a conta do dono em
      2026-10-01 (via túnel SSH para `localhost:8000`): 30 respostas, e o
      desempenho das 13 matérias bateu com a contagem manual no banco.
      641 testes (+1 xfail), ruff verde.
- [x] Etapa 5F.4 — Páginas de estatística (ADR-033): `/estatisticas` (o que
      mais cai, `fn_prova_cobra`), `/estatisticas/edital` (itens de edital
      distintos sobre `vw_arvore_edital_por_cargo`, com filtro de
      concurso/cargo/nível) e `/estatisticas/edital-vs-prova` (situações +
      `vw_peso_materia_cargo`), espelhadas em `/api/v1/estatisticas/*`. Os 3
      exemplos da 5E batem: top 10 de LP superior × médio, link para a lista
      filtrada por subassunto/cargo/nível e PF_25_ADM cargo 1 (139 nós
      cobrados, 125 nunca cobrados, 0 fora). Validado no Chromium headless.
      653 testes (+1 xfail), ruff verde.
- [x] Etapa 5F.5 — Simulado (ADR-033): `/simulado` escolhe concurso/cargo e
      monta a prova na ordem original (básico, depois específico; caderno e
      número), com cronômetro e rascunho no `localStorage` (Alpine). Correção
      CEBRASPE em `servicos/simulados_servico.py` (certo +1, errado −1,
      branco 0, anulada fora da nota e do máximo), com placar por matéria do
      nó principal. Sem login corrige sem gravar; com login, `app.simulado`
      nasce no início e encerra uma vez só (reenvio cai no resultado, API dá
      409), e as respostas ficam com `simulado_id` (fora do histórico
      avulso). Discursiva mostra tema e quesitos e o padrão de resposta só no
      resultado. API em `/api/v1/simulados/*`. Conferido: PF_25_ADM cargo 1,
      padrão "tudo C" dá 58 − 60 = −2 de 118 (2 anuladas), igual à contagem
      no banco. Revisão: rascunho só some no resultado, login caído volta pelo
      `/entrar`, aviso de itens ilegíveis (`itens_omitidos`, PF cargo 5) e
      início pela API via body. Validado no Chromium headless. 670 testes
      (+1 xfail), ruff verde.
- [x] Etapas 5F.6 a 5F.8 — Documentação e endpoints novos (ADR-033): Swagger
      com tags descritas, `securitySchemes` (cookie `sessao` + `X-CSRFToken`),
      `respostas_comuns.py` e teste guarda `test_openapi_documentado.py` (toda
      operação, schema, campo e parâmetro descritos; 401/403/404 conforme a
      dependência). 5F.7: `/materias`, `/materias/{id}`, `/busca`,
      `/questoes/{chave}/parecidas` e `incidencia` na questão. 5F.8:
      `/eu/resumo`, `/eu/prioridades`, `/eu/plano`, `/eu/concurso-alvo`
      (colunas em `app.usuario`), duração e nota anterior do simulado e
      `/simulados/{id}/questoes`. Os TODOs do frontend Tailwind foram ligados.
      LP com 178 questões; plano de PF_25_ADM cargo 1 começa por AOF (17,80%).
      97 testes no `site/`, ruff verde.
- [x] Etapa 5G — Fidelidade ao caderno e filtros (task.md): parágrafos do
      texto-base pelo recuo da 1ª linha, comando do grupo e assunto no topo
      do card, figuras vetoriais recortadas (tabelas desenhadas), filtros
      multisseleção com facetas e chips, e o item que engolia o preâmbulo do
      grupo seguinte (STM 64). Validada em 2026-10-06 com reextração
      completa: chaves da 5D inalteradas, 88/88 questões que citam parágrafo
      com parágrafos, filtro múltiplo igual ao SQL. A validação corrigiu as
      figuras do texto-base fora da `vw_questoes`, os GRANTs do site apagados
      a cada carga e a chave canônica sensível a quebra de parágrafo.
      763 testes (+1 xfail), ruff verde. Ver ADR-034.
- [x] Etapa 5H — Card da questão e filtros no formato Gran, em teal
      (ADR-035, `docs/planos/plano-etapa-5h.md`): token `destaque` (teal), ID curto `Q` +
      8 hex (`/q/<ID>` → 301), card com barra cinza, radios + Responder e
      barra de ações; painel no topo com dropdowns de busca rápida,
      palavra-chave (`texto`, `unaccent`), "Excluir questões" e "Questões
      com" (`com`), aplicado só no botão Filtrar; recontagem em
      `/questoes/facetas` (só OOB); ID curto na palavra-chave abre a questão.
      Chips no "Filtrar por:" do painel (Alpine; `<noscript>` sem JS), fora do
      fragmento da lista. Validada no Chromium headless em 1280 e 390 px
      (2026-10-06). Cascata disciplina → assunto → subassunto (5H.3) igual
      no site e na API (`no_id`, 2026-10-07). Curadoria das 12 disciplinas
      com nome de cargo da PF_25_ADM concluída (Opção A aprovada no ADR-030,
      renomeando 10 para área de conhecimento e fundindo Psicologia e
      Comunicação Social; assuntos e subassuntos homônimos fundidos, com teste guarda; 2026-10-07). 631 testes (+1 xfail) em `tests/`
      e 209 em `site/tests/`, ruff verde.
- [x] Etapa 8.0 — Inventário 2020+ e classificador fino (`plano-etapa-8.md`,
      revisada em 2026-10-08): `src/inventario.py` (classificador de link,
      `resumir_pdfs`, `reclassificar_inventario`, `detectar_formato_caderno`,
      `cobertura_por_ano`, `escolher_cadernos_calibracao_me`), `spider.py`
      (`listar_todas_listagens`, `mapear_links_pdf`, ano `_19YY/_20YY` além de
      `_YY`), `scripts/inventariar_concursos.py` (`--listagens`, `--mapear`,
      `--reclassificar` offline, `--amostra-formato`, `--gravar-banco`,
      `--relatorio`), `inv_concurso`/`inv_pdf`/`vw_inventario_ano`. 497 concursos
      nas 4 listagens; os 346 de 2020+ (337 encerrados/em andamento + 9 com
      inscrição aberta ou novos) mapeados, 0 com erro, 0 sem estado; 18.248 PDFs.
      Classificador: tipo novo `prova_outra` (oral, didática, tribuna,
      desempenho), escrita/subjetiva/prática como discursiva e comunicado/
      relação/edital como administrativo; `caderno_objetivo` caiu de 2.953 para
      2.642 no mesmo corpus. Formato: "julgue" só conta como CE sem alternativas
      A–D na mesma questão; amostra de 83 cadernos (42 CE, 41 ME, 0 misto,
      0 `?`); os 42 objetivos do piloto seguem CE. Cadernos ME para a 8.M no
      `inventario/RELATORIO.md` (`BANRISUL_25` com figura, `SEBRAE_26_PSE_1`
      básico, `SEFA_PR_25` específico). Piloto inalterado (70 provas, 145 na
      fila, 2.800 questões). 809 testes (+1 xfail) em `tests/`, ruff verde.
      Pausa 0, parte `incluir` (2026-10-09, ADR-037): os 55 alertas foram validados ao
      vivo, e o que fica fora do site está em `inventario/exclusoes.json` (16 concursos
      + PDF de curso de formação). Também entraram `caderno_com_gabarito`, a abertura do
      SEBRAE e `aguardando_prova` (26). Relatório com 0 alertas reais.
- [x] Etapa 8.M — Múltipla escolha (concluída em 2026-10-10, `docs/planos/plano-etapa-8m.md`,
      ADR-038): `questoes.tipo` + `alternativas`, gabarito A–E, parser ME calibrado com os cadernos
      reais do inventário, site e simulado por tipo (resposta sempre conferida pelo tipo da
      questão), ligação prova ME ↔ gabarito (S1), `caderno_com_gabarito` (S3). Gate (S4): carga
      real do `SEFA_PR_25` (380 itens ME) no `cebraspe_gate`, piloto inalterado (2.800 itens, 129
      anuladas, 3.029 apontamentos), 1.276 testes verdes. Sem registro no Gate: Chromium headless
      com ME real e conferência do desconto no edital (no `task.md`, junto da 8.M.1).
- [ ] Etapa 8.M.1 Estatísticas: incidência em dois níveis, prova → concurso (fn_prova_cobra) — cada edital pesa 1 e o básico compartilhado não se multiplica pelos cargos (**próxima**, antes da 8.1; `plano-etapa-8m1.md`,
      ADR-039): a média por prova da 8.M/S2 conta o básico compartilhado uma vez por cargo (PF_25_ADM
      pesa 48% da média do piloto). Passa a ser prova → média no concurso → média entre concursos.
- [ ] Etapa 8.M.2 Estatísticas por recorte: drill-down matéria → assunto → subassunto e filtros banca/ano/órgão/nível — os dois usos-alvo do dono
      (banca × ano × assunto; concurso × matéria × assunto) respondidos no site, com % de dois
      níveis e nº de questões distintas; detalhes no `task.md`.
- **Deploy público (5F.12): opcional**, por decisão do dono em 2026-10-06
  (o site ainda vai mudar muito antes de ir ao ar).

## 6. Patterns

- Filtro de ano sempre pelo slug da URL (`_25`, `_26`, ...) — nunca pelo
  texto visível do link (o texto do card é sempre "MAIS INFORMAÇÕES",
  confirmado ao vivo).
- Falha de rede/parsing por concurso individual é logada e o crawler segue
  para o próximo — nunca aborta o lote inteiro.
- Slugify determinístico (acentos/espaços → forma normalizada única) para
  nomes de órgão usados em paths de disco.
- Toda chamada LLM é feita diretamente à API REST do OpenRouter (`z-ai/glm-5.3-flash`),
  pelo núcleo `src/llm_openrouter.chamar_llm_json` (status tipados, Langfuse,
  gancho `pos_validacao`). Uso novo não monta payload próprio.
- Banco próprio, sem FK entre projetos: dimensões carregam chave natural
  normalizada (`slug`, `materia_normalizada`, tópico normalizado) para o
  cruzamento futuro com `itens_estudo` via tabela de mapeamento (ADR-026).
- Priorização de cargo grande (INSS, PF, PRF, ...) também é feita pelo slug
  da URL, dividido em segmentos por `_`/`-` e comparado contra um set de
  keywords — nunca com `\b` de regex direto no slug (underscore é `\w`, não
  cria fronteira de palavra).
- Idempotência do crawler: registro local em JSON
  (`data/processed_concursos.json`, um array de slugs) checado/atualizado a
  cada concurso processado com sucesso — não depende da estrutura de pastas
  da Etapa 3.
- Nome de órgão também extraído do slug (`extract_orgao_from_slug` em
  `spider.py`: segmento antes do token de ano `_YY`) — o texto do link
  nunca carrega o nome do órgão, mesma causa-raiz do filtro de ano.
- Validação de PDF baixado sempre por magic bytes (`content.startswith(b"%PDF-")`)
  no conteúdo em si, nunca só pelo header `Content-Type` — um link quebrado
  pode responder 200 com uma página HTML de erro.
- Dedup de download em duas camadas: por URL (manifesto `.manifest.json` por
  concurso, evita nova requisição de rede numa reexecução) e por hash de
  conteúdo (evita gravar o mesmo PDF duas vezes quando dois links diferentes
  apontam para o mesmo arquivo).
- Todo `href` de `get_attribute("href")` é resolvido com
  `urljoin(page.url, href)` antes de comparar contra a URL base — o atributo
  cru do HTML pode vir relativo, e o `.href` (propriedade JS resolvida) não
  é o que `get_attribute` devolve.
- Cabeçalho de matéria/cargo em edital sempre casado com um padrão que
  aceita dígitos, vírgula e parênteses no meio (`[A-ZÀ-Ú0-9 /,()\-]`), não
  só letras/espaço/hífen — títulos reais como `CARGO 7: MÉDICO CLÍNICO` e
  `ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO:` têm esses
  caracteres.
- Chunking de edital sempre nos dois níveis (cargo E matéria), nunca só um —
  cargos de especialidade (ex: áreas médicas) não têm matéria nomeada à
  parte, o conteúdo vem direto embaixo do cabeçalho `CARGO N: <nome>`.
- Checagem de layout multi-coluna (`checar_ordem_confiavel`) só considera
  blocos de texto com tamanho mínimo (`TAMANHO_MINIMO_BLOCO_COLUNA`) — um
  bloco curto isolado (título, assinatura) tem x0 diferente da margem do
  corpo sem indicar colunas paralelas de conteúdo.
- Chamada ao modelo de raciocínio (`glm-5.3-flash`) sempre com
  `max_tokens` generoso — um orçamento baixo é consumido pelo `reasoning_content`
  antes do `content` final, que volta `null` mesmo sem erro de rede.
- Toda chamada LLM com reasoning limitado a 3000 tokens via `REASONING_PADRAO`
  do `src/llm_openrouter.py` (fonte única: default de `chamar_llm_json`,
  reexportado pelo extrator de taxonomia e usado no payload do bot do
  Telegram). Decisão do dono em 2026-09-25. Defaults atuais do extrator:
  `MAX_TOKENS=12000`, `REQUEST_TIMEOUT=120`, reasoning 3000 — vieram do merge
  `b823c31` e substituíram os `24576`/`240` registrados na decisão de
  2026-09-20 (ADR-016), que ficam só como histórico.
- Chaves do OpenRouter são dedicadas por etapa (`llm_openrouter.ETAPA_*` +
  `chave_openrouter`): `OPENROUTER_KEY_TAXONOMIA_EDITAL`, `_SINONIMOS`,
  `_CURADORIA_ARVORE`, `_CLASSIFICACAO_QUESTOES` e `_TELEGRAM`. O nome da chave
  no OpenRouter é igual ao nome do trace no Langfuse
  (`cebraspe-<etapa>-<função>`). Chave vazia cai na `OPENROUTER_API_KEY`
  com aviso `[CHAVE_FALLBACK]` no log.
- Todo passo derivado do checkpoint de revisão (validação de-para, relatório
  HTML, banco Datasette, restart do container) é acionado automaticamente
  ao final do pipeline de extração/reprocessamento
  (`scripts/atualizar_revisao.py`, chamado por `revisar_taxonomia_piloto.py`
  e `reprocessar_falhas_piloto.py`) — nunca deixado como passo manual
  separado. O restart do Datasette é best-effort (loga aviso, nunca lança
  exceção) pra não derrubar o pipeline de extração por causa de
  infraestrutura local indisponível.
- Todo chunk carrega `tipo_conhecimento`/`nivel` herdados do cabeçalho de
  bloco `CONHECIMENTOS BÁSICOS/ESPECÍFICOS PARA ... NÍVEL SUPERIOR/MÉDIO`
  (`PADRAO_BLOCO`), além de `cargo_numero`, `materia_normalizada` e
  `apenas_discursiva` (lista única em `CAMPOS_CLASSIFICACAO_CHUNK`). O
  concurso (`slug`/`orgao`/`ano`) vem do manifesto do downloader
  (`resolver_concurso_do_pdf`), não do path em disco (a pasta é por órgão).
  Esses campos vêm só do parser/manifesto, então extração antiga é
  completada com `scripts/backfill_classificacao_chunks.py` sem chamar o
  LLM (ADR-020).
- Falha *semântica* do LLM (resposta estruturalmente válida mas com
  conteúdo errado — ex: `nome` de tópico igual ao numeral do item da
  fonte) é corrigida por reparo local determinístico quando o dado pra
  corrigir já está disponível (texto-fonte), nunca por repetir a mesma
  chamada ao LLM torcendo por sorte — sem contexto do erro, uma repetição
  não tem garantia de corrigir e não deixa rastro distinto de um retry por
  falha de rede. Ver ADR-021.
- Toda falha na chamada ao OpenRouter (`_chamar_llm_uma_vez`) devolve um
  status técnico específico (`falha_timeout`, `falha_conexao`,
  `falha_rate_limit`, `falha_http`, `falha_rede`, `falha_conteudo_vazio`,
  `falha_parse_json`, `falha_validacao_schema`), nunca um `motivo_falha`
  genérico — persistido no `status` do chunk e replicado em
  `metadata["tipo_erro"]` no Langfuse, pra distinguir falha transitória
  (timeout/conexão/rate-limit, retry tende a resolver) de falha que se
  repete com os mesmos parâmetros (conteúdo vazio/parse/schema, retry
  sozinho não ajuda). Ver ADR-022.
- Telemetria de observabilidade exclusivamente via SDK oficial `langfuse` (OTel),
  com observation (`generation`) aberta imediatamente antes da chamada HTTP para
  medição precisa da latência real de rede/inferência. Ver ADR-023.
- Normalização de whitespace no PyMuPDF: substituir sempre espaços não-separáveis
  (`\xa0`) por espaço ASCII (`" "`) logo na extração de texto das páginas (`extrair_texto_paginas`
  e detecção de cargo preliminar). PDFs do CEBRASPE contêm `\xa0` nos cabeçalhos
  de seções e blocos, o que faz buscas literais e regexes falharem silenciosamente.
- Títulos de cargos multi-linha sem itens no parser: quando um cabeçalho de cargo
  quebra linhas no layout do PDF e o bloco subsequente não contém itens
  numerados (`extrair_itens_numerados`), o texto deve ser acumulado ao rótulo do
  cargo (`f"{cargo_atual} {texto_bloco}"`), evitando criar chunks vazios sem matéria.
- Variações de blocos de matérias: mapear `CONHECIMENTOS GERAIS` para tipo básico
  (`"basico"`) e aceitar prefixação numérica de itens no edital (`PADRAO_BLOCO`
  com `(?:\d+(?:\.\d+)*\s+)?`).
- Colons parentéticos em matérias: cabeçalhos com restrição entre parênteses
  (ex.: `LÍNGUA INGLESA (APENAS PARA O CARGO 3: ...):`) exigem regex que capture
  o parêntese fechado antes do colon delimitador (`(?:\s*\([^)]*\))?:`), impedindo
  que o colon interno trunque o nome da matéria.
- Detecção determinística de cargo e nível único: editais com cargo único (ex.:
  `TCU_25_TEFC`) não repetem cargos nem declaração de nível na seção de Objetos
  de Avaliação; inspecionar as páginas preliminares (`DO CARGO DE...` e `REQUISITOS:`)
  para injetar `cargo_padrao` e `nivel_padrao` automaticamente no chunking.
- Resiliência na validação de taxonomia contra PDFs:
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
- Cabeçalhos de matérias multi-linha em editais: `PADRAO_MATERIA` só aceita quebras
  de linha se a linha anterior terminar com conectivos (`E|OU|DE|DA|DO|DOS|DAS` ou vírgula),
  evitando incorporar indevidamente títulos de cargo em layouts multi-linha como matérias falsas.
- Matérias sem dois-pontos delimitadores antes do item 1: quando um bloco sob cabeçalho
  de cargo contém itens numerados imediatos mas possui um prefixo em caixa alta antes do primeiro
  item (ex: `NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO ... 1`), o prefixo é
  extraído como nome da matéria e o corpo do chunk inicia a partir do item 1, evitando que a
  matéria receba o nome do cargo ou perca seu conteúdo.
- Filtro de editais de abertura no crawler: casar sempre com fronteira de palavra
  `\bABERTURA\b` (`re.search(r'EDITAL.*?\bABERTURA\b', text)`), impedindo que editais
  administrativos de retificação com palavras como "reabertura" sejam classificados
  como editais de abertura.

- Item de primeiro nível omitido pelo LLM é reinjetado localmente a partir
  do texto-fonte (`reinjetar_itens_ausentes`, logo depois do reparo de nome
  numérico), sem nova chamada ao LLM, e só quando o item é simples (sem
  subitens `N.1`, ≤ 150 chars). Item complexo continua `topico_ausente`
  para revisão humana. Ver ADR-025.
- Alerta de validação tem severidade: paráfrase leve (qualificador entre
  parênteses, erro de digitação da fonte corrigido pelo LLM, similaridade
  ≥ 0,92) vira `topico_divergencia_leve` `informativo`, visível mas fora de
  `total_alertas`. Reparo e validador usam a mesma comparação textual
  (`src/comparacao_texto.py`).
- Assinatura do fim da seção (nome + cargo do signatário) é removida em
  `_limpar_ruido_edital` ancorando no **cargo** (`PADRAO_CARGO_ASSINATURA`)
  no fim do texto, nunca no nome em caixa alta.

- Fatos de um concurso (`taxonomia_itens`, `provas`) são substituídos
  numa transação a cada carga; dimensões usam upsert por chave natural
  (`comparacao_texto.normalizar`). Cargos usam upsert em `(concurso, numero)`
  porque `provas_cargos` aponta para eles. Ver ADR-027.
- A fila `fila_extracao_questoes` usa upsert por `sha256` e o writer nunca
  altera `status`, que pertence ao consumidor.
- Tipo/cargos de caderno vêm de `classificar_prova_por_texto` sobre o texto
  do link já normalizado. Aceita `CONHECIMENTOS GERAIS` (CG) como básico, e
  texto sem cargo significa "todos os cargos do concurso" (TCU). Edital
  administrativo em `Provas/` fica fora da fila, com log.
- Estatística "oficial" só em view que filtra `status_revisao = 'aprovado'`
  (`vw_incidencia_topico`, `vw_edital_cobra_*`); a variante `_todas` é para
  inspeção.
- Restrição de cargo no nome da matéria (`(APENAS/SOMENTE PARA O(S)
  CARGO(S) ...)`, `PADRAO_RESTRICAO_CARGO`) sai de `materia_normalizada` e
  vira `cargos_restritos: list[int] | None`. Só sai do nome quando tem número
  de cargo; sem número (`PARA OS CARGOS DE NÍVEL SUPERIOR`), fica no nome e
  loga `[RESTRICAO_SEM_CARGO]`. Espaços repetidos são colapsados. Ver ADR-028.
- Número de cargo em texto (link de caderno ou restrição de matéria) vem só
  de `comparacao_texto.extrair_cargos_do_texto`, usada pelo parser e pelo
  writer.
- Aprovação da revisão humana é o `status_revisao_humana` do `<edital>.json`
  (`APROVADO...`). O writer relê o JSON a cada carga.
- O backfill confere o alinhamento pelo texto: o texto atual do chunk tem de
  ser prefixo do `texto_enviado_llm` salvo (a assinatura final foi removida
  depois, ADR-025), além de matéria/cargo.

- Sinônimo (Etapa 5B, ADR-029): regra determinística conservadora
  (`canonico.chave_regra`: "noções de" → `nocoes`, artigo inicial, parêntese,
  forma única de norma `lei 9784 1999`, plural simples) junta e aprova
  sozinha; o resto vai ao LLM por lista fechada de IDs e escopo (matéria →
  assunto dentro da matéria → subassunto dentro do assunto) e sai
  `proposto`. Proposta nunca muda o mapeamento: até a aprovação, cada nome
  fica no grupo aprovado de antes (identidade).
- Decisão humana de sinônimo (5B, histórico) foi via
  `scripts/aprovar_sinonimos.py`. Desde a 5B.1 o `sinonimos.json` está
  congelado, e o pipeline não o escreve mais.
- `scripts/propor_sinonimos.py` custa tokens e **não** roda no pipeline
  automático. Blocos já avaliados ficam em `avaliados_llm` e não são
  reenviados.
- Resposta de LLM sobre lista fechada é validada localmente (cada ID em
  exatamente um grupo, nada inventado, nada entre blocos) com falha tipada; a
  segunda tentativa leva o erro no prompt.
- Subtópico é linha (`dim_subtopico` + `taxonomia_subitens`), não JSONB.
- Árvore mestre (ADR-030): o pai pertence ao **nó**, não ao edital. Item de
  edital e questão **apontam** para nós (N:N, qualquer nível), e a
  estatística soma subindo a árvore. O nome composto aponta para N nós, e o
  item de uma matéria composta aponta para o nó da matéria certa.
- O ID de nó é estável. O nó semeado herda o ID do grupo aprovado da 5B.
  Fundir marca `fundido` + `fundido_em` e nunca apaga ID; toda leitura
  resolve o redirecionamento.
- `canonico/arvore.json` só é lido e escrito por `src/arvore.py`
  (`carregar`/`salvar`, uma linha por registro, ordenado por ID). A chave do
  item é a chave natural do banco unida por `|` (`arvore.chave_item`), e o
  apontamento é `{no_id, origem, status}`.
- Decisão do dono na árvore só via `scripts/curar_arvore.py` (ou as funções
  de `src/arvore.py`): `--mapear`, `--desmapear`, `--aprovar`, `--rejeitar`,
  `--fundir`, `--mover`, `--criar`, `--renomear`. Operação humana sai
  `aprovado`/`ativo`; mapear de novo um apontamento proposto o aprova. Erro de
  validação não grava nada.
- Item novo de edital (pipeline, `atualizar_revisao.atualizar_arvore`):
  `canonico.mapear_novos_itens_por_regra` copia os nós de um item aprovado com
  a mesma `chave_regra` **no mesmo nó-pai efetivo**. Regra ambígua ou pai sem
  nó fica pendente no `arvore.html`.
- A carga (`stats_writer.aplicar_arvore`) grava **todos** os nós com o status
  (as pontes nunca ficam sem FK) e as pontes só com apontamento `aprovado`,
  já resolvido. `vw_no_caminho` só expõe a cadeia `ativa` (nó proposto não
  conta antes da aprovação) e dá o `no_efetivo` do fundido. `dim_materia.nocoes`
  vem de `chave_regra(nome).nocoes`, com ou sem mapeamento.
- Estatística "edital cobra": ocorrência = `taxonomia_itens.id` distinto,
  com o item básico expandido por cargo (`cargos_restritos` respeitado).
  "Prova cobra": questão distinta. O mesmo item nunca conta 2× no mesmo nó.
- Segmentação de cadernos de prova: número do item distinguido por x0 na margem da coluna (cluster/moda); duplicado/fora de ordem é bloqueante; recuo de continuação de item medido na faixa estrita de 12 a 24 pt (~18 pt real); gabaritos definitivos em hash (TCU/Câmara) ligados aos cadernos pelo código impresso no corpo do PDF (ADR-031).
- Assinatura de grupo por hash na fila (`fila_extracao_questoes.assinatura_grupo`) garante reprocessamento automático quando os gabaritos ligados mudam, em qualquer status; `--reprocessar-erros` cobre órfãos e falhas.
- Advisory lock de sessão (`pg_try_advisory_lock(5_031_001)`) garante consumidor de execução única sem concorrência destrutiva na fila.
- Versão do gabarito (`definitivo` × `preliminar`) classificada exclusivamente pelo cabeçalho (ou prefixo do nome de arquivo), com preferência determinística pelo definitivo e alertas informativos (`mais_de_um_gabarito` / `gabarito_preliminar`).
- Caderno discursivo: quesitos extraídos estritamente a partir do comando (`redija`, `elabore`, `aborde`, `discorra`), evitando confusão com datas; tema anafórico rejeitado para `None` com alerta `tema_anaforico`.
- Padrão de resposta ligado preferencialmente por chave de título (`_chave_titulo`), garantindo ordem semântica correta mesmo com seções fora de ordem no PDF (chave ausente ou repetida cai na ligação por ordem); alertas `sem_quesitos` e `quesito_sem_valor`.
- Figuras: vinculadas à linha logo acima na mesma coluna com sobreposição horizontal (exceção item → preâmbulo).
- JSONs brutos de questões (`questoes/`) mantidos localmente e no `.gitignore` por volumetria, sendo regeneráveis de forma determinística por `scripts/extrair_questoes.py` (ADR-031).
- Estatística de prova sobe a árvore e conta questão distinta (`count(DISTINCT questao_canonica_id)`): questão em subassunto soma em subassunto, assunto e matéria; questão em assunto soma em assunto e matéria, nunca descendo. Leitura com filtros agregados no site é feita via `fn_prova_cobra(...)` para garantir cálculo de percentual médio sob os filtros e desduplicação correta de questões básicas aplicadas em múltiplos cargos (ADR-032). Percentual entre provas é média em dois níveis: % do nó na prova distinta → média das provas distintas do concurso → média entre concursos, cada edital com peso 1. Prova distinta: cargos com o mesmo conjunto de questões canônicas no escopo, sob os filtros, contam 1× (assinatura `md5` + cargo representante). Nunca soma bruta nem média direta por cargo, que multiplica o básico (ou o específico) compartilhado pelo número de cargos (ADR-039, 8.M.1).
- Cobertura descendente edital × prova (`vw_edital_vs_prova`): item de edital em nó X cobre X e todos os descendentes de X. Na prova, o apontamento sobe; na comparação, checa se há ancestral-ou-igual previsto no edital daquele cargo (`cobrado_no_edital`, `no_edital_nunca_cobrado`, `cobrado_fora_do_edital`).
- Peso por matéria em cargo (`vw_peso_materia_cargo`): proporção de cada matéria dentro do total da prova do cargo (básico + específico); matérias identificadas como nome de cargo (`nome_de_cargo = true`) são formatadas como `"Conhecimentos específicos — <cargo>"`.
- Discursivas analíticas (`vw_discursivas`): isola estritamente os temas e quesitos das 64 discursivas associadas aos nós da árvore mestre, sem interferir nem computar nas contagens das views de questões objetivas.
- O que fica fora do site é decidido só em `inventario/exclusoes.json` (slug, categoria
  de `CATEGORIAS_EXCLUSAO`, motivo), lido por `inventario.carregar_exclusoes`. Concurso da
  lista não é remapeado, não entra em amostra nem em lote e sai dos alertas. PDF de curso
  de formação fica fora por `pdf_vai_para_o_site`. Alerta do inventário vem do texto do
  link: antes de tratar como "sem arquivo", conferir a página ao vivo (ADR-037).
- Testes e Ruff por etapas (`Makefile` e marcadores do `pytest.ini`):
  - Etapa 1 (`make test-fast` / `pytest -m "unit and not db"`): executa `ruff check .` e testes unitários em memória (~18s, sem I/O nem banco).
  - Etapa 2A (`make test-pipeline` / `pytest tests/`): suíte do scraper, parsers, taxonomia e árvore (~1m15s).
  - Etapa 2B (`make test-site` / `pytest site/tests/`): suíte da web, rotas, API e simulados (~3m20s). Para pular testes lentos (>3s), usar `make test-site-fast` (`-m "not slow"`).
  - Etapa 3 (`make test-all` / `make check`): suíte completa de 840 testes e verificação de formatação.
  - Marcadores registrados no `pytest.ini`: `unit`, `db`, `pipeline`, `site`, `slow`.
  - Configuração central do Ruff em `pyproject.toml` (targets, ignores e exclusões de `scratch/`, `data/`, etc.).

## 7. Anti-patterns

- Nunca comparar `get_attribute("href")` direto contra uma URL absoluta
  sem resolver primeiro (`urljoin(page.url, href)`) — os cards da listagem
  do CEBRASPE usam href relativo (`/concursos/PF_25_ADM`), e um
  `href.startswith("https://...")` sem resolver descarta 100% dos links
  silenciosamente (0 resultados, sem exceção). Achado ao vivo em
  2026-09-19, ver ADR-008.
- Nunca filtrar ano com regex no texto do link — o ano está no slug da URL
  (ex: `TJ_CE_25_NOTARIOS` → 2025), não aparece como "2025" no texto visível.
- Nunca envolver o loop de concursos inteiro num único `try/except` (mascara
  falha isolada como falha total do lote).
- Nunca modelar tópico/subtópico como duas listas paralelas — perde a
  hierarquia que a Fase 5 precisa para estatística.
- Nunca reabrir a decisão de tecnologia de banco — PostgreSQL 16 já é o
  padrão do portfólio.
- Nunca gravar tabelas deste projeto no `study-rag-db` nem criar FK para
  `itens_estudo` — o `study-rag-db` tem ciclo de vida, credenciais e
  reconfiguração próprios, e acoplar os dois quebra um a cada mudança do
  outro. Cruzamento só por chave natural na Etapa 7 (ADR-026).
- Nunca hardcodar credenciais de API/Postgres no código — usar `.env`
  (ver Segurança).
- Nunca usar `\b` de regex direto sobre um slug com underscore para detectar
  keywords — `_` é `\w`, então `\bINSS\b` não dispara em `INSS_25`. Dividir
  o slug em segmentos primeiro.
- Nunca casar cabeçalho de matéria/cargo em edital só com letras/espaço/
  hífen — perde silenciosamente todo cabeçalho com dígito (`CARGO N:`),
  vírgula ou parênteses, e o conteúdo correspondente é engolido pelo chunk
  anterior sem erro nenhum. Achado ao vivo em 2026-09-19 (chunk de 41850
  chars engolindo ~14 cargos), ver ADR-010 e `LESSONS.md`.
- Nunca chamar modelo de raciocínio com `max_tokens` baixo pra `glm-5.3-flash` — o
  `content` volta `null` mesmo sem erro de rede se o orçamento acabar no
  `reasoning_content`.
- Nunca usar SDKs pesados de LLM (como litellm ou langchain) na chamada de inferência
  — chamadas diretas REST via `requests`/`httpx` mantêm a stack enxuta e confiável.
  Isso se refere à chamada de inferência do modelo; para observabilidade, usa-se
  o SDK oficial do Langfuse (OTel, ver ADR-023).
- Nunca enviar telemetria via `POST /api/public/ingestion` (REST manual) —
  endpoint legado entra em sunset em 2026-11-16, passando a aceitar apenas scores
  e rejeitando traces e generations. Usar o SDK oficial `langfuse` (ADR-023).
- Nunca deixar um passo do pipeline (extração → artefatos derivados) como
  "rode manualmente depois" — este projeto já foi mordido 2x por isso
  (`run()` nunca chamando `download_concurso_pdfs`, achado de 2026-09-19;
  href relativo silenciosamente descartando 100% dos links, ADR-008): a
  falha de esquecer o passo manual não lança erro, só deixa o artefato
  seguinte desatualizado sem sinal nenhum. Ver ADR-019.
- Nunca identificar matéria só pelo nome (nem por `(cargo, materia)`). O
  bloco básico repete os mesmos nomes (LÍNGUA PORTUGUESA, RACIOCÍNIO
  LÓGICO, ...) em superior e médio com conteúdo diferente. A chave mínima é
  `(concurso, tipo_conhecimento, nivel, cargo, materia)`. Ver ADR-020 e
  `LESSONS.md`.
- Nunca deduzir o concurso pelo path `data/<ano>/CEBRASPE/<orgao>/`: dois
  concursos do mesmo órgão no mesmo ano dividem a pasta. O slug só existe
  na URL de origem guardada no manifesto.
- Nunca aceitar `nome` de tópico puramente numérico como extração válida —
  `Topico.nome: str` do Pydantic aceita "1" numa boa (estruturalmente
  válido), mas é sinal de que o LLM confundiu o numeral do item da fonte
  com o texto do tópico, não um tópico legítimo. Achado real: 2 chunks
  inteiros (Contabilidade) com `status="sucesso"` e todo `nome` numérico,
  86 dos 88 alertas de validação de um teste completo. Ver ADR-021.
- Nunca capturar `requests.RequestException`/erro de parse de forma
  genérica e devolver um único `motivo_falha=None` para tudo — timeout,
  conexão recusada, HTTP 429/5xx, conteúdo vazio e schema inválido são
  causas-raiz diferentes com decisões de reprocessamento diferentes
  (transitório vs. precisa de ajuste); colapsar tudo em `status="falha"`
  esconde isso do relatório HTML/Datasette e do Langfuse. Ver ADR-022.
- Nunca aplicar `[^\w]` ou normalização NFKD direta sobre texto bruto extraído de
  PDF sem antes compor caracteres combinantes via `NFC` — caracteres em NFD
  (como `i` + `\u0301`) perdem o acento isolado e geram divergência com a saída do LLM.
- Nunca validar cobertura de itens do edital comparando apenas o campo
  `topico["nome"]` — o modelo frequentemente estrutura itens como `subtopicos`,
  e ignorá-los gera falsos positivos em massa de `topico_ausente`.
- Nunca emitir alerta de `topico_extra` apenas por ausência de casamento direto
  com um item numerado individual — se o termo constar no corpo do texto-fonte
  do chunk, trata-se de um tópico válido do texto programático, não alucinação.
- Nunca criar um chunk novo diretamente a partir de quebra de linha de cabeçalho
  de cargo sem checar se o bloco intermediário possui itens numerados programáticos.

- Nunca silenciar um alerta de validação sem antes perguntar se o dado está
  errado. Perda de conteúdo (item omitido) se corrige no dado; paráfrase
  explicável se rebaixa para informativo. Canonicalizar o nome extraído
  para o texto literal da fonte reintroduz erro de digitação do PDF. Ver
  ADR-025.
- Nunca usar casamento tolerante contra o texto-fonte **inteiro** numa
  checagem por item: um tópico parafraseado de um item passa a "cobrir" a
  omissão de outro item do mesmo chunk.
- Nunca deixar a restrição de cargo no nome da matéria (duplica
  `dim_materia`), nem apagá-la do nome sem ter extraído os números de cargo
  (a matéria passa a valer para todos os cargos sem aviso).
- Nunca aprovar concurso com `UPDATE` direto no banco: a próxima carga do
  writer reverte a partir do JSON.
- Nunca agrupar matéria/assunto/subassunto por similaridade de texto sem
  aprovação humana: `atos` × `contratos administrativos` (0,89), `ativos` ×
  `passivos` (0,90), `gestão de processos` × `de pessoas` (0,89). Similaridade
  só sugere; quem junta é regra determinística ou o dono (ADR-029).
- Nunca aprovar sinônimo ou mapeamento da árvore com `UPDATE` no banco nem
  editando só o banco: a fonte é `canonico/arvore.json` (antes,
  `sinonimos.json`), e a próxima carga reverte.
- Nunca ler ou escrever `canonico/arvore.json` com `json.load`/`json.dump`
  direto: o primeiro código da 5B.1 fez isso, montou a chave com `str(tupla)`
  e leu o campo `no` em vez de `no_id`. A regra do pipeline casou 0 de 1259
  assuntos e o relatório pôs os 4050 itens sob `None`, sem erro nenhum. Use
  `src/arvore.py` (`carregar`, `salvar`, `chave_item`).
- Nunca rodar `scripts/semear_arvore.py --forcar` depois da curadoria: a
  semente reescreve a árvore do zero e apaga toda decisão do dono.
- Nunca deixar o agente aprovar proposta do LLM em nome do dono; só grupo
  `regra` é aprovado automaticamente.
- Nunca juntar um nome composto (`Disposições gerais, servidores
  públicos`) a uma de suas partes: isso conta uma parte como a outra. Ele
  aponta para os N nós (ADR-030).
- Nunca derivar o pai de um nó da árvore do edital de origem: a matéria
  composta do CD separaria os assuntos de Constitucional dos outros
  concursos (ADR-030).
- Nunca criar nó da árvore automaticamente a partir de nome novo de edital:
  o que a regra não mapeia fica pendente para a curadoria.
- Nunca deixar dois nós ativos com o mesmo nome (pela `chave_regra`) sob o mesmo
  pai, nem duas disciplinas de mesmo nome: o filtro do site mostra o nome
  repetido e a incidência se divide. Ao fundir ou renomear disciplina, rode
  `pytest tests/test_arvore.py`; os testes `*_sem_irmaos_homonimos` e
  `*_sem_disciplinas_homonimas` guardam isso. Cargo não é atributo do nó
  (ADR-030). Paráfrase (nome diferente) segue com o dono.
- Nunca classificar a questão só entre os nós do edital do caderno: a
  questão fora do edital ficaria sem nó, e o "edital × prova" perderia o
  lado "cobrado fora do edital".
- Nunca casar a restrição com `\([^)]*\)`: um parêntese interno
  (`ANALISTA (TI)`) corta a cláusula no meio e o resto fica no nome.
- Nunca permitir janela ampla de recuo de linha de item (> 24 pt, ex.: 8–30 pt) no parser de provas — captura a primeira linha com recuo de parágrafo (~28–29 pt) do texto-base subsequente após itens de 1 linha física (ADR-031).
- Nunca confiar na ordem do fluxo interno de objetos do PDF (PyMuPDF blocks) para determinar a ordem de leitura em cadernos sem ordenar visualmente por coordenadas `(coluna, y0, x0)` (ADR-031).
- Nunca confiar em `span["flags"] & 16` ou "Bold" para segmentar itens de provas (apenas 9,64% dos cadernos do CEBRASPE usam fonte com flag negrito; a segmentação real é por x0 na margem via cluster/moda).
- Nunca procurar "definitivo" solto no corpo do padrão de resposta ou gabarito (o padrão do cargo 2 da PF cita "definitivo" no texto discursivo; um preliminar com a mesma redação seria classificado como definitivo). Avaliar estritamente o cabeçalho (primeiros 600 caracteres no padrão de resposta, 2000 na grade — ver `classificar_versao`) ou o nome do arquivo.
- Nunca extrair quesitos numerados antes do verbo de comando da prova discursiva (datas como "1 de janeiro..." no enunciado viram falso quesito 1).
- Nunca commitar arquivos JSON de questões extraídas (`questoes/`) no git — mantidos localmente e no `.gitignore` por volumetria, sendo 100% regeneráveis sob demanda (ADR-031).
- Nunca somar linhas de views agregadas por cargo (`vw_prova_cobra_*`): cadernos básicos cobrem múltiplos cargos; somar linhas de cargos diferentes duplica questões básicas no denominador e no numerador. Para consultas que cruzam ou agregam múltiplos cargos/concursos, usar sempre a função oficial `fn_prova_cobra(...)` ou filtrar estritamente por um cargo individual (ADR-032).
- Nunca pôr senha de role no SQL versionado (`site/sql/app_schema.sql`) nem em
  teste: a primeira versão da 5F.1 fez isso e as senhas foram trocadas. Senha
  vem do `.env` via `site/scripts/aplicar_schema_app.py`.
- Nunca rodar o site com `python -m site...`: o diretório `site` colide com o
  módulo `site` da stdlib. Use o caminho do script ou `uvicorn app.main:app`
  de dentro de `site/`.
- Nunca dar à role `site_leitura` acesso ao schema `app` (nem fazer JOIN
  entre `app.resposta` e as views numa query só): as respostas são lidas pela
  `site_app` e a lista de chaves entra no SQL das views por parâmetro.
- Nunca aceitar o `voltar` do login sem `auth.destino_seguro` (open redirect
  com `//host` ou `/\host`).
- Nunca usar a `questao_chave` crua como id de elemento HTML: o `|` é
  separador de namespace em seletor CSS, e o `hx-target="#..."` quebra no
  `querySelector` do HTMX sem aparecer em teste de rota. Use `dom_id(chave)`
  (`q-<sha1>`) de `rotas_web.py`.
- Nunca interpolar valor da query string dentro de expressão do Alpine
  (`x-data="{ x: '{{ valor }}' }"`): o navegador decodifica `&#39;` de volta
  para `'` antes de o Alpine avaliar, e vira XSS. Passe por atributo
  `data-*` e leia com `$el.dataset`.
- Nunca pôr `hx-get` num `<select>` dentro do form de filtros: em GET o HTMX
  envia só o valor do próprio elemento e perde os outros filtros. O gatilho
  fica no `<form>` (`hx-trigger="change, submit"`).
- Nunca devolver o fragmento só por `HX-Request`: a restauração de histórico
  do HTMX também manda esse header e espera a página inteira (checar
  `HX-History-Restore-Request`).
- Nunca pôr campo pesado (texto-base, figuras) em `QuestaoResumo` para
  servir o HTML: muda o contrato da API e multiplica o payload da listagem.
  O card busca em `/q/.../anexos` quando o usuário abre.
- Nunca declarar `cargo_numero: int` em rota HTML com select de cargo: trocar
  o concurso limpa o select e manda `cargo_numero=`, e o FastAPI responde 422
  (só aparece no navegador, não no teste com parâmetro válido).
- Nunca mandar o gabarito na prova do simulado (`ItemSimulado` não tem o
  campo) nem o padrão de resposta antes de encerrar: a correção é sempre no
  servidor.
- Nunca apagar o rascunho do simulado no clique de enviar: se o POST falhar
  (CSRF, rede), as marcações de horas de prova somem. Só a página de
  resultado apaga. E nada de `try` em `x-init`: Alpine só avalia expressão.
- Nunca usar dois `TestClient(app)` ao mesmo tempo nos testes: os pools do
  banco são globais e o lifespan do primeiro a sair fecha os do outro.
- Nunca dar GRANT a role do site esperando que ele sobreviva a uma carga:
  `schema_estatisticas.sql` recria as views com `DROP ... CASCADE`.
  `stats_writer.criar_schema` guarda e reaplica os GRANTs do schema; não
  remover isso (sem ele, toda reextração derruba o site com 500).
- Nunca comparar texto-base por hash do texto cru: a quebra de parágrafo
  depende do layout do caderno. A chave canônica normaliza espaços.
- Nunca remover o `conftest.py` da raiz: sem ele o pytest grava os erros
  simulados (`x.test`, `XX_25`) em `logs/scraper_cebraspe.log`, e o log de
  produção deixa de servir para auditar execução real.
- Nunca computar questões discursivas junto com questões objetivas: discursivas possuem grão, tema e dinâmica de pontuação inteiramente distintos e devem ser consumidas estritamente via `vw_discursivas` (ADR-032).

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

## 9.2. Revisão via Datasette (Etapa 4 — checkpoint de revisão humana)

Navega a trilha de auditoria (entrada/saída do parser+chunking+LLM) e a
taxonomia extraída lado a lado, sem frontend próprio. Exposto externamente
via rede `homelab_default` com Traefik e Cloudflare Tunnel, acessível em
`https://datasette.projetoathos.com.br`, protegido por Cloudflare Zero Trust
(SSO restrito a `athoslobin@hotmail.com`). **Não é** o banco de produção
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

- `data/<ano>/CEBRASPE/<orgao>/{Editais,Provas,Gabaritos}/` — PDFs baixados
  (ignorado pelo git, volume grande demais)
- `logs/scraper_cebraspe.log` — log de execução (ignorado)
- Tabelas em `scraper-cebraspe-db` (Postgres próprio, star schema de
  estatísticas de concursos, DDL em `src/sql/schema_estatisticas.sql`),
  gravadas por `python -m src.stats_writer` (também automático no fim de
  `scripts/atualizar_revisao.py`, ADR-027)
- `task.md` — roteiro de execução por etapas (versionado)
- `revisao_piloto/<edital>.json` + `<edital>.auditoria.json` — resultado da
  extração e trilha de auditoria de entrada/saída por edital (versionado,
  conteúdo público de edital)
- `revisao_piloto/<edital>.validacao.json` — alertas heurísticos de
  `scripts/validar_taxonomia.py` (candidatos a tópico ausente/extra por
  chunk; versionado, sempre regenerável)
- `revisao_piloto/revisao.db` — banco SQLite derivado dos JSONs acima, servido
  via Datasette (ignorado pelo git, sempre regenerável por
  `scripts/gerar_db_datasette.py`)
- `revisao_piloto/relatorio/*.html` — relatório de revisão de página única
  por edital + índice (ignorado pelo git, sempre regenerável por
  `scripts/gerar_relatorio_revisao.py`), servido como estático pelo
  Datasette (ver §9.2)
- `docker-compose.yml` — serviço Datasette local para revisão (ver §9.2)
- `scripts/reconciliar_taxonomia.py [json ...]` — aplica a reinjeção de
  item ausente (ADR-025) a extrações já salvas, sem LLM, com backup
  `.pre_reconciliacao.bak`
- `canonico/arvore.json` — árvore mestre (versionado, fonte da verdade da
  taxonomia desde a 5B.1; um registro por linha): nós e mapeamentos
  item de edital → nós. Semeada uma vez por `scripts/semear_arvore.py`
- `scripts/curar_arvore.py` (`--mapear ITEM:NO1,NO2`, `--desmapear/--aprovar/
  --rejeitar ITEM:NO`, `--fundir ORIGEM:DESTINO`, `--mover NO:PAI`,
  `--criar NIVEL:PAI=Nome`, `--renomear NO=Nome`, `--html`) e
  `revisao_piloto/relatorio/arvore.html` (regenerável, linkado do
  `index.html`, em `https://datasette.projetoathos.com.br/relatorio/arvore.html`):
  árvore navegável com os itens de edital de cada nó (concurso · cargo ·
  nível), os itens sem mapeamento e as propostas pendentes
- `canonico/sinonimos.json` — camada canônica da 5B (ADR-029), **congelada**
  como histórico desde a 5B.1. `scripts/propor_sinonimos.py`,
  `scripts/aprovar_sinonimos.py` e `sinonimos.html` ficam só como histórico
- `canonico/classificacao_questoes.json` — base canônica da Etapa 5D (ADR-032, versionado,
  um registro por linha): amarração estável `<concurso>|<caderno>|<numero>` a até 2 nós
  da árvore mestre, com hash SHA-1 do enunciado e confiança categórica (`alta`, `media`, `baixa`)
- `scripts/curar_classificacao.py` (`--mapear CHAVE:NO1[,NO2]`, `--aprovar/--rejeitar CHAVE:NO`,
  `--aprovar-lote --confianca alta [--caderno X]`, `--pendentes`, `--html`, `--aplicar-banco`) e
  `revisao_piloto/relatorio/classificacao.html` (regenerável, linkado do `index.html` e servido
  em `https://datasette.projetoathos.com.br/relatorio/classificacao.html`): auditoria visual com
  texto-base expansível, gabarito e comandos CLI copiáveis
- `scripts/classificar_questoes.py` — inferência em 2 passadas (preferencial × reserva) via LLM
  com OpenRouter e Langfuse (não roda no pipeline padrão para isolar custos)
- `site/` — API e páginas do site (5F). Rodar: `cd site && uvicorn app.main:app`
  (páginas em `/`, `/sobre`, `/q/<concurso>/<caderno>/<numero>`);
  documentação interativa em `/docs` (Swagger) e `/redoc`. `site/openapi.json`
  é o contrato versionado (fonte para os MCPs): depois de mudar rota ou
  modelo, rodar `python site/scripts/exportar_openapi.py`, senão o teste
  `test_openapi_versionado_em_dia` falha. Roles do banco:
  `python site/scripts/aplicar_schema_app.py` (senhas `SITE_DB_*` do `.env`)
- `scripts/backfill_classificacao_chunks.py [<pdf> [json]]` — sem argumentos,
  roda em todos os editais de `revisao_piloto/` (`backfill_lote`); completa
  concurso/nível/tipo de conhecimento em extração já feita, sem LLM
  (ADR-020)

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

As decisões ficam em [`docs/adr/`](docs/adr/README.md) (ADR-001 a ADR-039;
o `README.md` de lá é o índice com data e título). Antes de reabrir uma
escolha de stack, banco, parser ou site, ler o ADR correspondente.

- Decisão nova vira ADR novo (ou seção "Atualização" no ADR existente), não
  entrada aqui. Este arquivo só cita o número do ADR em §5–§7.
- O log cronológico que ficava aqui (2026-09-19 a 2026-10-07) foi removido em
  2026-10-08 por duplicar os ADRs; está no histórico do git.

## 13. LESSONS.md (do projeto)

Ver `LESSONS.md` neste diretório — protocolo padrão descrito no `CLAUDE.md`
raiz do portfólio.
