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
      resultado do crawler em produção (ver seção 12) — 31 concursos de
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
- [x] Etapa 5C.1 — Correções da extração (Sessões 1 a 5, correcoes-etapa-5c.md): posição dos itens por x0 (cluster/moda); alertas no item no Postgres (alertas text[], utilizavel boolean, view vw_questoes_utilizaveis); fila reprocessada por assinatura_grupo; lock pg_try_advisory_lock (5031001); gabarito definitivo x preliminar no cabeçalho; quesitos discursivos após comando; tema anafórico rejeitado; padrão ligado por chave de título. 435 testes (+1 xfail) no pytest e base inalterada (ADR-031).
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
      `plano-etapa-5f.md`.
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
  2026-09-20 (§12), que ficam só como histórico.
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
- Estatística de prova sobe a árvore e conta questão distinta (`count(DISTINCT questao_canonica_id)`): questão em subassunto soma em subassunto, assunto e matéria; questão em assunto soma em assunto e matéria, nunca descendo. Leitura com filtros agregados no site é feita via `fn_prova_cobra(...)` para garantir cálculo de percentual médio sob os filtros e desduplicação correta de questões básicas aplicadas em múltiplos cargos (ADR-032).
- Cobertura descendente edital × prova (`vw_edital_vs_prova`): item de edital em nó X cobre X e todos os descendentes de X. Na prova, o apontamento sobe; na comparação, checa se há ancestral-ou-igual previsto no edital daquele cargo (`cobrado_no_edital`, `no_edital_nunca_cobrado`, `cobrado_fora_do_edital`).
- Peso por matéria em cargo (`vw_peso_materia_cargo`): proporção de cada matéria dentro do total da prova do cargo (básico + específico); matérias identificadas como nome de cargo (`nome_de_cargo = true`) são formatadas como `"Conhecimentos específicos — <cargo>"`.
- Discursivas analíticas (`vw_discursivas`): isola estritamente os temas e quesitos das 64 discursivas associadas aos nós da árvore mestre, sem interferir nem computar nas contagens das views de questões objetivas.

## 7. Anti-patterns

- Nunca comparar `get_attribute("href")` direto contra uma URL absoluta
  sem resolver primeiro (`urljoin(page.url, href)`) — os cards da listagem
  do CEBRASPE usam href relativo (`/concursos/PF_25_ADM`), e um
  `href.startswith("https://...")` sem resolver descarta 100% dos links
  silenciosamente (0 resultados, sem exceção). Achado ao vivo em
  2026-09-19, ver seção 12.
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
  chars engolindo ~14 cargos), ver seção 12 e `LESSONS.md`.
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
tabelas pra fazer o de-para manualmente (ver §12, decisão de 2026-09-21).

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

## 12. Log de decisões

> 💡 **Nota:** As decisões técnicas e arquiteturais deste projeto foram formalizadas e catalogadas individualmente em [`docs/adr/`](docs/adr/README.md) (ADR-001 a ADR-034). O registro abaixo mantém a memória cronológica das decisões tomadas durante as sessões:

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

> **Substituída em 2026-09-21 pelo ADR-026** (banco próprio) — ver a última
> entrada deste log.
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

### 2026-09-19 — Nome de órgão também vem do slug, não do texto do link
**Decisão:** Adicionar `extract_orgao_from_slug` em `spider.py` (segmento do
slug antes do token de ano `_YY`, ex: `TJ_CE_25_NOTARIOS` → `TJ_CE`) e
incluir a chave `orgao` no dict retornado por `get_contest_links`.
**Motivo:** A Etapa 3 (downloader) precisa de um nome de órgão para montar
`data/<ano>/CEBRASPE/<orgao_slug>/...`, mas nada no crawler produzia isso —
`ConcursoMetadados.orgao` existe no modelo desde a Etapa 1, porém
`get_contest_links` só devolvia `title` (sempre "MAIS INFORMAÇÕES", mesma
causa-raiz do filtro de ano) e nunca populava esse campo. Extrair do slug é
consistente com o padrão já usado para ano e priorização.
**Alternativas descartadas:** Buscar o nome do órgão na página de detalhe do
concurso (H1/breadcrumb) — mais preciso, mas exige nova navegação Playwright
por concurso (custo de rede/tempo) e não foi validado ao vivo nesta sessão;
fica como possível refinamento futuro se o slug abreviado (ex: `TJ_CE`) se
mostrar insuficiente para leitura humana das pastas.

### 2026-09-19 — Dedup de download em duas camadas (URL + hash de conteúdo)
**Decisão:** `downloader.py` mantém um manifesto JSON por concurso
(`.manifest.json` dentro da pasta do órgão) mapeando URL → {hash, path}.
Antes de baixar, verifica se a URL já está no manifesto (pula a requisição
de rede); depois de baixar, verifica se o hash do conteúdo já corresponde a
um arquivo existente (evita gravar duplicata em disco quando dois links
apontam pro mesmo PDF).
**Motivo:** O `task.md` pede dedup "por hash de conteúdo entre execuções",
mas só o hash não evita a requisição de rede repetida (precisa baixar antes
de saber o hash) — o manifesto por URL resolve a reexecução idempotente, e a
checagem de hash resolve duplicata de conteúdo sob URLs diferentes
(retificação de edital que reaponta pro mesmo arquivo, por exemplo).
**Alternativas descartadas:** Dedup só por nome de arquivo — falso-positivo
(nomes iguais, conteúdo diferente) e falso-negativo (nomes diferentes,
mesmo conteúdo) fáceis de ocorrer em PDFs do CEBRASPE.

### 2026-09-19 — Auditoria pós-Etapa 3: href relativo zerava o crawler em produção
**Decisão:** Em `get_contest_links`, resolver todo `href` com
`urljoin(page.url, href)` antes de compará-lo contra
`"https://www.cebraspe.org.br/concursos/"`, em vez de comparar o atributo
cru do HTML direto.
**Motivo:** Auditoria ao vivo (Playwright real contra
`/concursos/encerrado`, não mock) revelou que os 424 cards da listagem
usam **href relativo** (`/concursos/PF_25_ADM`), não absoluto —
`get_attribute("href")` devolve exatamente o que está no atributo HTML, sem
resolver contra a base da página (diferente da propriedade `.href` do DOM,
resolvida pelo browser). O filtro `href.startswith("https://www.cebraspe.org.br/concursos/")`
— presente desde o commit inicial do projeto e mantido sem alteração pela
Etapa 2 — descartava **100% dos cards**, silenciosamente: `get_contest_links`
retornava lista vazia sem lançar exceção, mesmo padrão de falha do bug do
filtro de ano já documentado, mas desta vez no ponto de entrada do crawler,
mascarando que nenhuma das correções da Etapa 2 (filtro de ano,
priorização, idempotência) chegava a ser exercitada em produção — apesar de
`task.md` e este `CLAUDE.md` marcarem a Fase 2 como concluída. Confirmado
antes/depois da correção: 0 → 31 concursos de 2025 encontrados contra o
site real; `download_concurso_pdfs` (Etapa 3) validado ponta a ponta com
PDFs reais de um desses concursos (`AGSUS_25_CCE`).
**Alternativas descartadas:** Nenhuma — é uma correção direta de bug, sem
trade-off. Reforça a lição já registrada em `LESSONS.md` de sempre validar
o crawler contra o DOM real, nunca assumir a forma de um atributo HTML sem
inspecionar ao vivo.

### 2026-09-19 — Etapa 4: só a seção "OBJETOS DE AVALIAÇÃO" vale a pena extrair
**Decisão:** `edital_parser.py` recorta exclusivamente a seção "OBJETOS DE
AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)" do edital (usa o texto do
marcador, não o número do item — varia por concurso).
**Motivo:** Análise manual do edital real `PF_25_ADM` (68 páginas): é a
única seção com estrutura matéria→tópico→subtópico, o dado que a Fase 5
(banco de estatísticas) precisa. Cronograma, critérios de desempate e
requisitos/atividades por cargo (vistos nas páginas 1–3 e 63–64) são dados
operacionais do concurso — não conteúdo de estudo — e não servem ao
objetivo do projeto (cruzar estatísticas de incidência de tópico por
matéria/ano para planos de estudo).
**Alternativas descartadas:** Extrair também requisitos/atividades por
cargo (dá pra montar uma dimensão "cargo" mais rica) — descartado por
agora porque foge do escopo de "conteúdo de estudo" da Etapa 4; pode virar
uma dimensão auxiliar na Fase 5 se fizer falta, sem precisar mudar o parser.

### 2026-09-19 — Chunking em dois níveis (cargo + matéria), não só matéria
**Decisão:** `dividir_por_cargo_e_materia` percorre cabeçalhos de cargo
(`CARGO N: <nome>`) e de matéria juntos, mantendo o cargo corrente; gera 1
chunk por matéria nomeada, e 1 chunk pelo próprio cargo quando ele não tem
matéria nomeada à parte (especialidades médicas: o cabeçalho do cargo já é
o rótulo do conteúdo).
**Motivo:** O `task.md` pede chunking "por cargo, ... disciplinas" — os
dois eixos coexistem de verdade no mesmo edital (ver achado abaixo e em
`LESSONS.md`): cargos administrativos agrupam várias matérias nomeadas;
cargos de especialidade (Médico Clínico, Médico Ortopedista, ...) não têm
matéria própria, só o nome do cargo mesmo. Um chunking só-por-matéria perde
a associação com o cargo (necessária pra Fase 5 relacionar taxonomia →
cargo → concurso); um chunking só-por-cargo perde a granularidade de
matéria nos cargos administrativos.
**Alternativas descartadas:** Chunking só por matéria (primeira versão) —
comprovadamente quebrado: perdeu silenciosamente ~14 cargos inteiros dentro
de 1 chunk de 41850 chars, por o regex de matéria não reconhecer cabeçalhos
com dígito/vírgula/parênteses. Ver `LESSONS.md`.

### 2026-09-19 — Extração LLM via `requests` direto, não LangChain
**Decisão:** `taxonomia_extractor.py` faz POST direto (`requests`) para
`{LITELLM_BASE_URL}/chat/completions`, sem adicionar `langchain-openai`
como dependência nova.
**Motivo:** O `study-rag-agent` usa `langchain_openai.ChatOpenAI` contra o
mesmo LiteLLM, mas ele já depende de LangChain pro grafo inteiro (LangGraph).
O `scraper_cebraspe` tem stack enxuta e já depende de `requests` (Etapa 3).
O LiteLLM expõe um schema compatível com a API de chat da OpenAI — não há
ganho em trazer uma dependência pesada só para 1 chamada de extração.
**Alternativas descartadas:** `langchain-openai` (mesmo padrão do
`study-rag-agent`) — rejeitado por trazer uma dependência nova grande sem
necessidade; SDK oficial `openai` — mesma objeção, `requests` já resolve.

### 2026-09-19 — Chave de API do LiteLLM: virtual key gerada, nunca a master key
**Decisão:** Gerada uma virtual key (`key_alias: scraper-cebraspe`, escopo
`models: ["glm-5.3-flash"]`) via `POST {LITELLM_BASE_URL}/key/generate` com
a master key do `study-rag-agent`, salva só em `.env` local (gitignored).
**Motivo:** A master key do LiteLLM está documentada em texto puro no
`CLAUDE.md`/`docker-compose.yml` do `study-rag-agent` (issue de segurança
conhecida, fora do escopo deste projeto — ver seção 8). Usá-la direto nas
chamadas de extração deste projeto propagaria esse problema; uma virtual
key escopada segue o mesmo padrão já usado lá para o "Hermes Agent".
**Alternativas descartadas:** Usar a master key direto — descartado por
segurança (nenhum motivo técnico pra precisar de uma master key só pra
chamar 1 modelo).

### 2026-09-19 — `run()` nunca chamava o downloader; registro de idempotência mentia
**Decisão:** `CebraspeSpider.run()` agora chama `download_concurso_pdfs`
logo após `map_pdf_links` e só marca o slug como processado
(`mark_processed`) depois do download rodar — nunca antes.
**Motivo:** Auditoria ao vivo (`python -m src.spider` rodado pelo usuário)
mostrou que `run()` mapeava os PDFs, logava as contagens e já marcava o
concurso como "processado" em `data/processed_concursos.json` **sem nunca
chamar `download_concurso_pdfs`** — a Etapa 2 e a Etapa 3 nunca tinham sido
ligadas, apesar de ambas constarem como `[x]` no Progresso. Resultado real
encontrado: 13 slugs no registro, mas só 1 (`PF_25_ADM`) com pasta de
download de verdade; os outros 12 (`AGSUS_25_CCE`, `TCU_25_TEFC`, etc.)
seriam pulados para sempre em execuções futuras sem nunca ter baixado nada.
Registro limpo manualmente para conter só `PF_25_ADM`.
**Efeito colateral corrigido junto:** nessa mesma auditoria, o
`map_pdf_links` também tinha regredido — voltou a descartar o texto do link
de cada prova (guardava só a URL, perdendo a distinção CB1/CB2/DISC descrita
na decisão de 2026-09-19 sobre cargo↔prova) e a logar só contagens
agregadas, sem sinalizar PDFs não classificados. Reaplicado o formato
`{"url": ..., "texto": ...}` e o log `[PROVA-PDF]`/`nao_classificados`.
Como `download_concurso_pdfs` esperava `list[str]` de URLs, ele foi ajustado
para aceitar também `list[dict]` nessa forma e persistir o texto em
`<concurso_dir>/provas_texto_link.json` (chave = nome do arquivo baixado),
para a Etapa 4 consumir depois sem precisar reconstruir a informação a
partir do PDF (que não a contém).
**Risco de processo identificado:** este diretório nunca foi commitado em
nenhuma branch (raiz do `homelab` está com `scraper_cebraspe/` totalmente
untracked); existe uma worktree separada (`worktree-scraper-cebraspe-etapa3`)
com commits próprios da Etapa 2/3 que nunca foi mergeada de volta. É provável
que essa regressão tenha entrado ao sincronizar arquivos entre as duas
cópias sem levar em conta o ajuste de `texto`. Recomendado começar a
commitar este projeto para não perder trabalho de novo (ver aviso ao
usuário na conversa).
**Alternativas descartadas:** Nenhuma — bug de wiring, sem trade-off.

### 2026-09-20 — Trilha de auditoria de entrada/saída do parser+extractor
**Decisão:** `scripts/revisar_taxonomia_piloto.py` agora salva, além do
`<edital>.json` de resultado, um `<edital>.auditoria.json` com os metadados
do corte de seção (páginas/chars totais do PDF, offsets, se achou o
marcador de fim) e, por chunk, cargo/matéria/offsets/tamanho/**o texto
exato enviado ao LLM**/status. `ChunkTaxonomia` ganhou `offset_inicio`/
`offset_fim` e um `chunk_index` estável (posição na lista de chunking) foi
adicionado a `auditoria_chunks`, `resultados` e `chunks_com_falha` pra ligar
os dois arquivos sem depender do par `(cargo, materia)` como string.
**Motivo:** `logs/scraper_cebraspe.log` só registrava contagens agregadas
(quantos chunks, quantas falhas) — não dava pra auditar depois se o corte
da seção "OBJETOS DE AVALIAÇÃO" descartou/reteve o texto certo, nem
inspecionar o texto que efetivamente foi pro LLM em cada chunk que falhou.
**Alternativas descartadas:** Registrar isso só no log (texto de 39 chunks
por edital não cabe legível em log de linha única); casar auditoria↔resultado
só por `(cargo, materia)` — frágil pra cargos com matéria repetida/nula.

### 2026-09-20 — Revisão navegável via Datasette e Traefik/Cloudflare Tunnel
**Decisão:** Novo `scripts/gerar_db_datasette.py` lê todos os pares
`revisao_piloto/<edital>.json`+`<edital>.auditoria.json` (funciona também
com o arquivo legado sem auditoria) e reconstrói do zero
`revisao_piloto/revisao.db` (`sqlite-utils`, tabelas `editais`/`chunks`/
`taxonomia_topicos`/`taxonomia_subtopicos`, FTS5 habilitado em texto de
chunk e nomes de tópico/subtópico). Novo `docker-compose.yml` sobe
`datasetteproject/datasette` servindo esse banco. Antes restrito ao
`127.0.0.1:8011`, a pedido do usuário o serviço foi exposto via Traefik
na rede `homelab_default` e associado ao Cloudflare Tunnel em
`datasette.projetoathos.com.br`, com autenticação restrita via SSO para
o email do usuário.
**Motivo:** Ferramenta de apoio ao checkpoint de revisão humana da Etapa 4
(`status_revisao_humana: PENDENTE`) — precisa navegar/comparar entrada
(chunk enviado ao LLM) e saída (taxonomia extraída) lado a lado sem escrever
frontend. Reconstrução completa (não incremental) porque na escala do
piloto (poucos editais) upsert só adiciona risco de linha obsoleta sem
ganho. A exposição via Cloudflare Tunnel foi necessária para permitir a
revisão fora da rede local. **Isso não é e não substitui** o banco de
produção da Fase 5 (Postgres próprio `scraper-cebraspe-db`, ADR-026) —
é descartável/regenerável a qualquer momento a partir dos JSONs.
**Alternativas descartadas:** Upsert incremental — complexidade sem
benefício na escala atual; Postgres em vez de SQLite pra essa ferramenta —
rejeitado porque duplicaria a decisão já fechada da Fase 5 pra um uso
completamente diferente (revisão descartável vs. estatística de produção).

### 2026-09-20 — Retry + max_tokens/timeout maiores para reduzir falhas de extração; reasoning-off descartado
**Decisão:** `extrair_taxonomia_chunk` (`src/taxonomia_extractor.py`) ganhou
retry com backoff (3 tentativas, 5s/15s) e `max_tokens`/`timeout`/
`reasoning` parametrizáveis (default reproduz produção). Novo default de
produção: `MAX_TOKENS=24576` (era 8192), `REQUEST_TIMEOUT=240` (era 120s).
`edital_parser.py` ganhou `_limpar_ruido_edital` — remove nota de
retificação de edital embutida no meio do texto programático (achado no
chunk `PSICÓLOGO ORGANIZACIONAL`) antes de virar `ChunkTaxonomia.texto`.
**Motivo:** Comparando dois runs reais completos do mesmo edital (39
chunks, 2026-09-19 e 2026-09-20), só 2 das 5 falhas de cada run coincidiam
— a falha é majoritariamente não-determinística, não estrutural por chunk.
Um experimento controlado (`scripts/experimento_falhas_llm.py`, 20 chamadas
reais, 1 tentativa por config pra isolar o efeito) nos 5 chunks que
falharam no run de 20/09 comparou: baseline (8192/120s) 2/5 sucesso;
`max_tokens=24576,timeout=240s` **5/5**; `thinking: disabled` 3/5 (mesmo
chunk falhou com a mesma assinatura ligado e desligado — z-ai/OpenRouter
provavelmente ignora o parâmetro); `thinking:disabled`+texto limpo 4/5.
Achado extra: no chunk maior (6977 chars), a falha não era só reasoning —
o `content` (JSON) em si veio cortado no meio
(`json.JSONDecodeError: Unterminated string`, ~7510 chars) com
`max_tokens=8192`, confirmando que o teto também é insuficiente pro output
final em chunks grandes, não só pro reasoning. `max_tokens`/`timeout`
maiores foi a única config que fechou 5/5 — adotada como default. Fecha o
item `validacao-pendente` registrado em `LESSONS.md`.
**Alternativas descartadas:** Desligar reasoning via `thinking`/
`reasoning_effort` como mitigação de produção — tecnicamente repassado pelo
LiteLLM (`openrouter/chat/transformation.py`, confirmado no pacote
instalado) mas sem evidência de que o backend obedece; resultado do
experimento (3/5, mesma assinatura de falha que o baseline num caso) não
justifica confiar nisso sem verificação mais forte — se algum dia isso for
revisitado, precisa de um teste isolado que prove a diferença de
comportamento, não só taxa de sucesso agregada. Fallback pra modelo sem
reasoning já no gateway (`tencent/hy3:free`, `xiaomi/mimo-v2.5-pro`) —
descartado por agora, qualidade da extração nessa tarefa específica nunca
foi verificada. Generalizar a limpeza de ruído pro cabeçalho de transição
de seção do chunk `TÉCNICO EM COMUNICAÇÃO SOCIAL` (`CONHECIMENTOS
ESPECÍFICOS PARA O CARGO DE NÍVEL MÉDIO` grudado na cauda) — descartado por
enquanto, é um caso só, regex genérico demais arrisca cortar conteúdo
legítimo de outro edital.

### 2026-09-21 — Desacoplamento total do LiteLLM e migração para OpenRouter direto

**Decisão:** Remoção completa do SDK `litellm` do repositório (`requirements.txt`, ambiente virtual e código-fonte). O bot do Telegram (`src/telegram_bot.py`) e o extrator de taxonomia (`src/taxonomia_extractor.py`) agora chamam diretamente o endpoint REST do OpenRouter (`https://openrouter.ai/api/v1/chat/completions`) com chaves dedicadas (`TELEGRAM_OPENROUTER_API_KEY` e `OPENROUTER_API_KEY`) e enviam telemetria assíncrona ao Langfuse diretamente via REST (`/api/public/ingestion`).
**Motivo:** Evita sobrecarga de SDKs intermediários, incompatibilidades com callbacks de OpenTelemetry/Langfuse v3 e conflito de compartilhamento de chaves e métricas entre serviços distintos.
**Alternativas descartadas:** Manter LiteLLM apenas no Telegram Bot — descartado para eliminar complexidade desnecessária e manter padrão arquitetural único e enxuto em todo o repositório.

### 2026-09-21 — Validação heurística de-para + relatório de página única para o checkpoint de revisão humana

**Decisão:** Dois scripts novos, ligados por `chunk_index`: `scripts/validar_taxonomia.py`
compara, por chunk, os itens numerados de primeiro nível do texto-fonte
(`texto_enviado_llm` em `.auditoria.json`) contra `topico["nome"]` extraído
(`.json`), gerando `<edital>.validacao.json` com alertas `topico_ausente`
(item na fonte sem correspondência extraída), `topico_extra` (tópico
extraído sem correspondência literal na fonte) e `chunk_sem_extracao`
(chunk com `status="falha"` e itens na fonte). A comparação é por **texto
normalizado** do item completo (substring), não por número — o LLM não
preserva a numeração original de forma consistente entre chunks do mesmo
edital, então um diff por número sozinho gera falso-positivo maciço (ver
`LESSONS.md`). `scripts/gerar_relatorio_revisao.py` consome o mesmo trio de
JSONs e gera um relatório HTML estático de página única por edital (texto-
fonte e taxonomia lado a lado por chunk, alertas destacados), servido pelo
Datasette via `--static relatorio:/data/relatorio` (`docker-compose.yml`) —
sem plugin novo, reaproveitando Traefik/Cloudflare Tunnel já configurados.
`gerar_db_datasette.py` ganhou a tabela `alertas_validacao` e a coluna
`editais.total_alertas` (carregamento opcional do `.validacao.json`, mesmo
padrão condicional do `.auditoria.json`).
**Motivo:** Usuário relatou dificuldade em fazer o de-para manual entre
texto do edital e taxonomia extraída navegando as tabelas separadas do
Datasette, e pediu uma forma de sinalizar automaticamente tópico que
"ficou de fora" da extração. Validado contra o edital piloto real (39
chunks): a primeira versão (diff por número) gerou 385 alertas; a versão
final gerou 2, ambos achados genuínos (não ruído de heurística) — um caso
onde o LLM consolidou 2 itens duplicados do próprio edital num tópico só, e
um caso de numeração corrompida no texto extraído do PDF-fonte (chunk
`TÉCNICO EM COMUNICAÇÃO SOCIAL`).
**Alternativas descartadas:** Diff por número de item — descartado depois
de comprovar que o LLM não preserva numeração de forma confiável entre
chunks (mesmo edital, mesma extração); validação via segundo LLM como
"juiz" — descartada por ora (mais cara, não-determinística, e a heurística
textual já convergiu pra sinal/ruído aceitável no piloto); view/canned
query dentro do próprio Datasette em vez de relatório HTML separado —
descartada porque o renderizador tabular padrão do Datasette não faz layout
de duas colunas nem destaque de texto, exigiria plugin novo pra um ganho
menor que gerar o HTML estático direto.

### 2026-09-21 — Pipeline automático dos artefatos de revisão a cada extração

**Decisão:** Novo `scripts/atualizar_revisao.py`
(`atualizar_artefatos_revisao`) encapsula a sequência
`validar_taxonomia` → `gerar_relatorio_revisao` → `gerar_db_datasette` →
restart do container Datasette, e passa a ser chamado automaticamente ao
final de `scripts/revisar_taxonomia_piloto.py` (`revisar_edital_piloto`) e
`scripts/reprocessar_falhas_piloto.py` (`reprocessar_falhas`, quando há
sucesso novo) — substitui a lógica de restart que já existia duplicada só
em `reprocessar_falhas_piloto.py`. O restart é best-effort: captura
`OSError`/`returncode != 0` e só loga aviso, nunca lança exceção — o
pipeline de extração (que já pagou a chamada LLM) não pode falhar por causa
do Datasette local estar fora do ar.
**Motivo:** Usuário pediu que o fluxo de validação (ADR-017/ADR-018)
"entre no pipeline, rode automaticamente a cada extração" em vez de exigir
4 comandos manuais depois de cada rodada. Mesma classe de risco já
documentada 2x neste projeto (`run()` nunca chamando o downloader, achado
de 2026-09-19; href relativo do ADR-008): passo manual esquecido não lança
erro, só deixa o artefato seguinte desatualizado silenciosamente.
**Alternativas descartadas:** Hook de `git commit`/pre-commit — descartado
por acoplar controle de versão a infraestrutura local sem necessidade;
cron/systemd timer regenerando periodicamente — descartado por atrasar a
atualização (objetivo é "logo após a extração") e desperdiçar ciclos na
escala atual do piloto; propagar exceção se o restart do Datasette falhar —
descartado por quebrar o retorno da extração por um problema de
infraestrutura não relacionado ao resultado já salvo em disco. Ver
ADR-019 para o detalhamento completo.

### 2026-09-21 — Classificação de chunk por nível, tipo de conhecimento e concurso

**Decisão:** O chunking passa a reconhecer o cabeçalho de bloco
`CONHECIMENTOS BÁSICOS/ESPECÍFICOS PARA ... NÍVEL SUPERIOR/MÉDIO` como um
terceiro tipo de marcador, que define `tipo_conhecimento`/`nivel` dos chunks
seguintes. Cada chunk ganha também `cargo_numero`, `materia_normalizada` e
`apenas_discursiva`. O `<edital>.json` ganha `concurso` (slug/órgão/ano,
resolvido pelo manifesto do downloader) e `cargos` (número/nome/nível).
**Motivo:** O usuário quer filtrar questões por nível, básico/específico e
tópico do edital. No piloto, os básicos de superior e de médio saíam
idênticos (`cargo=None`, mesmo nome de matéria), e o concurso não aparecia
em nenhum artefato. O piloto foi completado por backfill (tudo vem do
parser), e o filtro `PF_25_ADM` × nível × tipo foi validado no banco de
revisão: 39/39 chunks classificados e 0 alertas de classificação.
**Alternativas descartadas:** Distinguir por posição/`chunk_index` (não é
filtro); pedir o nível ao LLM (o dado é determinístico no cabeçalho);
reorganizar `data/` por concurso (fica como follow-up, o manifesto já
resolve). Ver ADR-020.

### 2026-09-21 — Reparo local determinístico para nome de tópico numérico

**Decisão:** Um teste de ponta a ponta do zero contra `PF_25_ADM` achou 88
alertas de validação (vs. 2 históricos, ADR-018) — causa: em 2 dos 39
chunks (CARGO 3: CONTADOR — "CONTABILIDADE APLICADA AO SETOR PÚBLICO" e
"MATEMÁTICA FINANCEIRA"), o LLM preencheu `topico["nome"]` com o numeral do
item da fonte ("1", "2", ...) em vez do texto do tópico — estruturalmente
válido (`status="sucesso"`), semanticamente errado. Em vez de um retry cego
reaproveitando o loop genérico (mesma chamada, mesmo prompt, sem contexto
do erro — desenho inicial, descartado), a correção final é um **reparo
local determinístico, sem chamada nova ao LLM**: o texto-fonte já tem o
item completo pra cada numeral, mapeado pela mesma extração de itens
numerados que `validar_taxonomia.py` já usa (`extrair_itens_numerados`,
movida para `src/edital_parser.py` pra reparo e validação nunca
divergirem). Complementado por reforço do prompt (mitigação na origem, sem
garantia) e um quinto tipo de alerta passivo (`topico_nome_numerico`) como
rede de segurança para dados já persistidos ou casos que o reparo não
cubra. `reprocessar_falhas_piloto.py` ganhou `--chunks 17,21` para forçar
reprocessamento por `chunk_index` mesmo com `status="sucesso"`. Refinamento
adicional na mesma sessão: quando o reparo não mapeia todo numeral,
`extrair_taxonomia_chunk` passa a devolver `tuple[TaxonomiaEdital | None,
str | None]` (antes só `TaxonomiaEdital | None`) — o motivo, quando
identificado, vira o `status` persistido do chunk
(`STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO =
"falha_nome_numerico_nao_mapeado"`), não o `"falha"` genérico de
rede/timeout/parse. A seleção padrão de `reprocessar_falhas_piloto.py`
(sem `--chunks`) e `gerar_relatorio_revisao.py::renderizar_chunk` foram
generalizados de `status == "falha"` para `status not in (None,
"sucesso")`, senão o novo status específico escaparia do reprocessamento
automático e do aviso "sem taxonomia" no relatório HTML.
**Motivo:** O dono do projeto rejeitou o retry cego original por não passar
contexto nenhum ao LLM (repetir a tarefa sem corrigir nada, arriscando
consumir tokens à toa) e pediu uma etapa específica, transparente e
rastreável. O reparo local resolve isso por completo: custo zero de
tokens, determinístico, e rastreável por log com tag própria
(`[REPARO_NOME_NUMERICO]`/`[REPARO_NOME_NUMERICO_FALHOU]`) e por metadata
estruturado (`status: "reparado"|"falhou"`) no Langfuse para os dois
desfechos — sem misturar com retry de falha técnica. Depois, o próprio
dono pediu explicitamente um status diferente de "falha" genérica para
esse caso semântico, já que repetir a chamada pode não resolver (não é
instabilidade transitória). Verificado contra os dados reais do achado
(restaurados do `.bak`): reparo local corrigiu 32 + 11 tópicos sem nenhuma
chamada ao LLM; reprocessamento real via `--chunks 17,21` (LLM de verdade,
prompt reforçado) devolveu `total_alertas` a 2 (os mesmos genuínos do
ADR-018).
**Alternativas descartadas:** Retry cego reaproveitando o loop genérico
(desenho original); uma chamada LLM corretiva dedicada (mais robusta a
casos não cobertos pelo reparo local, mas custa tokens sempre que o bug
ocorre — fica como possível fallback futuro); validator Pydantic em
`Topico.nome` (não tem acesso ao texto-fonte, que o reparo precisa);
persistir só o flag de reparo bem-sucedido sem mudar o contrato de retorno
de `extrair_taxonomia_chunk` (não cobria o desfecho de falha, que era
justamente o que precisava de um status próprio). Ver ADR-021.

### 2026-09-21 — Classificação de erros/exceções na chamada ao OpenRouter

**Decisão:** `_chamar_llm_uma_vez` (`src/taxonomia_extractor.py`) parou de
colapsar toda falha técnica no mesmo `motivo_falha=None` → `status="falha"`
genérico. Cada tipo de exceção/etapa ganhou status próprio: timeout
(`requests.exceptions.Timeout` → `falha_timeout`), conexão recusada
(`ConnectionError` → `falha_conexao`), HTTP 429 (`falha_rate_limit`), outro
HTTP de erro (`falha_http`), qualquer outra `RequestException` não
classificada (`falha_rede`), resposta sem `content`/`finish_reason`
truncado (`falha_conteudo_vazio`), JSON malformado (`falha_parse_json`) e
JSON válido mas fora do schema `TaxonomiaEdital` (`falha_validacao_schema`)
— além do `falha_nome_numerico_nao_mapeado` já existente do ADR-021. Nova
função `_falha_chamada` centraliza log com tag própria por tipo
(`[FALHA_TIMEOUT]`, `[FALHA_CONEXAO]`, `[FALHA_RATE_LIMIT]`, `[FALHA_HTTP]`,
`[FALHA_REDE]`) e registro no Langfuse. Todo caminho de falha (inclusive o
semântico do ADR-021) agora inclui `metadata["tipo_erro"] = <status>` no
Langfuse, filtrável no dashboard sem abrir log.
**Motivo:** Pedido do dono do projeto para rastrear "os diferentes tipos de
erros ou exceções dos scripts de cada chamada ou etapa para o
openrouter/langfuse" — mesma exigência de rastreabilidade do ADR-021,
estendida a todo o espectro de falha técnica (não só o caso semântico).
Timeout/conexão/rate-limit são tipicamente transitórios (retry tende a
resolver); conteúdo vazio/parse/schema tendem a se repetir com os mesmos
parâmetros (retry sozinho não ajuda) — misturar os dois no mesmo "falha"
esconde essa diferença do relatório HTML/Datasette e do Langfuse.
Nenhum consumidor do `status` do chunk precisou mudar: a generalização já
feita no ADR-021 (`status not in (None, "sucesso")`) absorve qualquer novo
status técnico automaticamente.
**Alternativas descartadas:** Manter status técnico único e diferenciar só
via `metadata["tipo_erro"]` no Langfuse — descartado porque o `status` é o
campo que aparece no relatório HTML/Datasette, não só no Langfuse; um
status por código HTTP individual (`falha_http_401`, `falha_http_500`, ...)
— descartado por ora, sem caso de uso concreto que precise da granularidade
completa; classificar por regex na mensagem de exceção em vez de por tipo
de exceção Python — descartado, a hierarquia tipada do `requests` já é mais
robusta que casar texto de mensagem de erro. Ver ADR-022.

### 2026-09-21 — Migração da telemetria Langfuse para SDK oficial (OTel)

**Decisão:** Migração completa da camada de observabilidade em `src/taxonomia_extractor.py` e `src/telegram_bot.py` de requisições manuais REST (`POST /api/public/ingestion`) para o SDK oficial `langfuse.Langfuse` (v3, OTel). As generations passam a ser abertas imediatamente antes da requisição HTTP ao OpenRouter (`_abrir_generation`), fornecendo medição de latência real. O fechamento e envio são centralizados em `_registrar_langfuse` (síncrono e não bloqueante, com exportação em thread em segundo plano e flush via `atexit`).
**Motivo:** A API REST v3 de ingestão do Langfuse entra em sunset em 2026-11-16 (passando a aceitar apenas scores e rejeitando traces/generations). Além disso, requisições REST manuais com `requests.post` sem checagem de resposta silenciavam falhas como HTTP 401 por chave inválida. O SDK oficial já constava nas dependências (`langfuse>=3,<4`), tornando a migração de custo zero de dependências.
**Alternativas descartadas:** Manter o endpoint REST até a data limite (acumularia débito técnico crítico); exportador OTLP cru via requests (reinventaria buffer e retry já validados no SDK). Ver ADR-023.

### 2026-09-21 — Expansão da extração 2025 (IBAMA, STM, TCU) e eliminação de falsos positivos na validação

**Decisão:** Expansão do pipeline de extração e validação para mais 3 grandes editais de 2025: `IBAMA_25` (33 chunks), `STM_25` (53 chunks) e `TCU_25_TEFC` (10 chunks), somando com `PF_25_ADM` (39 chunks) um total de 135 chunks processados com 100% de sucesso na chamada LLM. Para acomodar as peculiaridades dos novos editais, `edital_parser.py` recebeu normalização de espaços `\xa0`, suporte a títulos de cargo multi-linha sem itens, colons parentéticos em matérias (`(?:\s*\([^)]*\))?:`), cabeçalhos `CONHECIMENTOS GERAIS` e detecção de cargo único/nível em páginas preliminares. Em `validar_taxonomia.py`, foram implementadas 5 heurísticas de eliminação de falsos positivos: composição NFC preliminar, substituição de ligaduras corrompidas de fontes do CEBRASPE (`Ɵ`→`ti`, etc.), verificação de cobertura conjunta em tópicos e subtópicos, correspondência exata/fronteira `\b` para termos com >= 3 caracteres e checagem em texto integral do chunk antes de apontar `topico_extra`.
**Motivo:** A primeira execução do validador sobre o edital do IBAMA retornou 1.271 alertas em 33 chunks já auditados como sucesso no LLM. A investigação comprovou que se tratava quase exclusivamente de ruído heurístico (fontes embutidas do CEBRASPE com glifos privados para ligaduras, acentos em NFD e itens alocados pelo modelo em `subtopicos`). Com os ajustes, os alertas no IBAMA caíram para apenas 1 (achado real), e a base consolidada de 135 chunks de 2025 estabilizou com apenas 3 alertas no total (PF: 1, STM: 1, IBAMA: 1, TCU: 0).
**Alternativas descartadas:** Afrouxar a validação para verificar apenas contagem agregada de tópicos (perderia a rastreabilidade item a item); aceitar acentos corrompidos nas saídas sem tratamento determinístico (poluiria o banco de estatísticas final).

### 2026-09-21 — Coleta e extração da Câmara dos Deputados 2025 (CD_25_NS) e refinamentos do parser

**Decisão:** Coleta estruturada completa do concurso `CD_25_NS` (Câmara dos Deputados 2025 - Nível Superior), integrando 2 editais, 7 cadernos de provas (objetivas e discursivas) e 4 gabaritos definitivos ao repositório local. A extração híbrida do edital de abertura atualizado foi concluída com 15/15 chunks com 100% de sucesso na chamada LLM e 0 alertas de validação, elevando a base consolidada de 2025 para 5 concursos e 150 chunks. Para viabilizar a extração limpa das matérias do edital da Câmara, implementou-se em `src/edital_parser.py`: (1) reconhecimento de quebras de linha em cabeçalhos de matéria condicionadas a conectivos (`(?:,\s*|\s+(?:E|OU|DE|DA|DO|DOS|DAS))\s*\n`), permitindo casar títulos multi-linha como "REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM DO CONGRESSO NACIONAL E CÓDIGO DE ÉTICA" sem absorver indevidamente títulos de cargos multi-linha; (2) detecção determinística de prefixos de matéria em caixa alta antes do primeiro item numerado quando o edital omite o delimitador dois-pontos antes do item 1 (caso de "NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS 1 Constituição..."). Em `src/spider.py`, aplicou-se fronteira de palavra `\bABERTURA\b` na regex de editais para evitar falsos positivos com termos administrativos como "reabertura".
**Motivo:** O edital da Câmara dos Deputados possui um formato tipográfico com longos títulos de matérias com quebras de linha conectivas e omissão de dois-pontos no primeiro bloco de matéria do Cargo 2. Sem os ajustes, o Cargo 1 acumulava o título da matéria no rótulo do cargo, e o Cargo 2 era catalogado com a própria matéria repetindo o nome do cargo. Além disso, no crawler, editais administrativos de retificação citando "reabertura de período de acesso à prova" estavam sendo mapeados erroneamente como editais de abertura.
**Alternativas descartadas:** Tratar os nomes das matérias por substituição pontual via hardcoding no parser (quebraria a generalização para futuros editais federais do CEBRASPE); relaxar `PADRAO_MATERIA` para qualquer quebra de linha (regrediu testes de cargos com layout quebrado no IBAMA). Ver ADR-024.

### 2026-09-21 — Tratamento automático dos 3 alertas residuais da validação

**Decisão:** Cada alerta residual tinha uma causa diferente, então o tratamento
também é diferente. (1) IBAMA_25 #32: o LLM omitiu o item `1 IN Ibama 05/2021.`.
Nova etapa `reinjetar_itens_ausentes` (pós-LLM, sem nova chamada) reinjeta item
de primeiro nível omitido, só se for simples. (2) PF_25_ADM #31 (qualificador
entre parênteses para desambiguar item repetido no edital) e (3) STM_25 #31
(erro de digitação `bBiblioteca` corrigido pelo LLM): viram
`topico_divergencia_leve` com severidade `informativo`, fora de
`total_alertas`. A comparação textual foi movida para `src/comparacao_texto.py`,
compartilhada entre reparo e validador. Também entraram a remoção da assinatura
do fim da seção (presente nos 5 editais) e duas regras novas no prompt.
Backfill via `scripts/reconciliar_taxonomia.py`.
**Motivo:** O dono do projeto pediu uma etapa automática no pipeline para os
alertas residuais, com prós e contras de cada alternativa. O diagnóstico
mostrou 1 perda real de dado e 2 falsos positivos. Suprimir tudo esconderia a
perda; forçar o nome literal da fonte reintroduziria o erro de digitação.
Resultado: 3 → 0 alertas bloqueantes, 2 informativos visíveis, e 1 único
tópico alterado na base.
**Alternativas descartadas:** Reprocessar o chunk automaticamente (retry cego,
ADR-021); chamada corretiva ao LLM (tokens, não determinística, sem caso real
que exija); campo `numero` no `Topico` (schema + reextração); lista de alertas
aceitos (não é automática, fica para a revisão humana). Ver ADR-025.

### 2026-09-21 — Banco Postgres próprio, independente do study-rag-agent

**Decisão:** A Fase 5 passa a usar um Postgres 16 próprio
(`scraper-cebraspe-db`, `postgres:16-alpine`, banco/usuário `cebraspe`, porta
`127.0.0.1:5435`, rede `homelab_default`) em vez da instância `study-rag-db`.
Nenhuma FK para `itens_estudo`: as dimensões carregam chave natural
normalizada, e o cruzamento vira a Etapa 7 do `task.md` (tabela de mapeamento
+ `postgres_fdw` ou camada analítica).
**Motivo:** Revisão do plano da Etapa 5 pelo dono do projeto, antes de haver
código de banco. Os domínios são diferentes (material de estudo pessoal ×
dados públicos de concursos). A FK prevista tinha a direção errada e ficaria
sempre `NULL`. O `study-rag-db` precisa ser reconfigurado (`postgres/postgres`,
porta `5434` em `0.0.0.0`), e acoplar os dois quebraria um a cada mudança do
outro. A senha do banco novo não tem default no compose.
**Alternativas descartadas:** Manter a decisão de 2026-09-19; outro database
na mesma instância (mantém a dependência operacional e ainda exige
`postgres_fdw` para JOIN); schema dentro de `study_rag` (maior acoplamento).
Ver ADR-026, que substitui o ADR-003.

### 2026-09-22 — Star schema de estatísticas, gravação idempotente e fila de provas

**Decisão:** DDL em `src/sql/schema_estatisticas.sql`: dimensões
`dim_orgao`/`dim_ano`/`dim_materia`/`dim_topico`/`dim_cargo`, fatos
`concursos`/`cargos_editais`/`taxonomia_itens` (1 tópico de 1 chunk,
subtópicos em `JSONB`), `provas` + ponte `provas_cargos` e
`fila_extracao_questoes`. `src/stats_writer.py` faz upsert das dimensões por
chave natural e substitui os fatos de cada concurso numa transação. A fila
usa upsert por `sha256` sem tocar `status`. O writer roda no fim de
`atualizar_revisao.py` (best-effort). Dado pendente de revisão entra
marcado, e a view de estatística oficial só conta `aprovado`.
**Motivo:** Etapa 5 do `task.md`. A substituição por concurso evita tópico
órfão depois de uma reextração. A fila preserva o estado do consumidor. O
texto do link, a única fonte de tipo e cargos do caderno, tem formatos
variados (intervalo, lista, cargo único, sem cargo, CB/CG) e lixo legado
(editais administrativos e padrões de resposta em `Provas/`). O
classificador trata esses casos e foi testado contra todos os textos reais.
**Alternativas descartadas:** upsert linha a linha nos fatos (deixa órfão);
uma linha por subtópico (sem uso estatístico ainda); não gravar dado
pendente (a aprovação precisa chegar ao banco — via JSON, ADR-028); `nivel` em `provas` (é
atributo do cargo). Ver ADR-027.

### 2026-09-23 — Restrição de cargo fora do nome da matéria e aprovação da Fase 4

**Decisão:** A restrição `(APENAS/SOMENTE PARA O(S) CARGO(S) ...)` sai do nome
da matéria e vira `cargos_restritos`, gravado como `INTEGER[]` em
`taxonomia_itens`. Espaços repetidos são colapsados. `extrair_cargos_do_texto`
foi para `comparacao_texto`, usada pelo parser e pelo writer. A aprovação
da Fase 4 entrou no `status_revisao_humana` dos 5 JSONs. Na auditoria da
entrega, entraram também: restrição sem número fica no nome, parêntese
aninhado, várias restrições e checagem do backfill pelo texto.
**Motivo:** Etapa 5A. A restrição no nome duplicava matérias no STM, e o
espaço duplo duplicava no IBAMA (`dim_materia` de 106 para 102).
**Alternativas descartadas:** restrição no nome; `UPDATE` no banco
(revertido pelo writer); regex própria de cargo no parser (divergiria do
writer). Ver ADR-028.

### 2026-09-25 — Camada canônica de sinônimos e reasoning padrão de 3000 tokens

**Decisão:** Etapa 5B. `canonico/sinonimos.json` guarda entradas (nomes com
a mesma chave de regra no mesmo pai) e grupos canônicos com ID estável,
origem e status. Regras determinísticas juntam e aprovam sozinhas; o LLM
propõe o resto por lista fechada de IDs, em 3 passos (matéria, assunto,
subassunto), e tudo sai `proposto`. O mapeamento só muda com aprovação
(`aprovar_sinonimos.py`); sem decisão, cada nome é o próprio canônico
(identidade). O núcleo de chamada ao OpenRouter virou
`src/llm_openrouter.chamar_llm_json`, e o dono fixou reasoning de 3000
tokens em toda chamada (`REASONING_PADRAO`, fonte única). Os defaults do
extrator continuam 12000/120 (merge `b823c31`), não os 24576/240 da decisão
de 2026-09-20. No banco, tabelas canônicas com o ID do JSON, `nocoes` em
`dim_materia` e subtópico como linha (`dim_subtopico` + `taxonomia_subitens`).
**Motivo:** o dono decidiu regra + LLM + aprovação humana, e a similaridade
de texto tem falsos positivos medidos. Canônico NULL até a revisão tiraria
~4 mil nomes sem sinônimo da estatística; a identidade dá o resultado de
antes sem inventar nada. Execução real: 20 chamadas, US$ 0,0139, 106
propostas pendentes (3 matérias, 40 assuntos, 63 subassuntos).
**Alternativas descartadas:** similaridade de texto; LLM sobre todas as
entradas de uma vez; rodar o LLM no pipeline automático (custa tokens a
cada extração); IDs estáveis no prompt (IDs locais curtos erram menos).
Ver ADR-029.

### 2026-09-25 — Extração determinística de questões, gabaritos e discursivas dos cadernos (Etapa 5C)

**Decisão:** Extração 100% determinística sem LLM para cadernos de provas e
gabaritos dos 5 concursos de 2025. `src/gabarito_parser.py` lê a grade de
respostas (C/E/X), extrai o código do caderno impresso no corpo do PDF
(resolvendo gabaritos com nome em hash do TCU e CD) e lê o padrão de resposta
discursivo. `src/prova_parser.py` segmenta em duas colunas por ordenação
visual, isola itens pelo span próprio em negrito, extrai textos-base
compartilhados, recorta figuras raster para `data/.../figuras/` vinculando
por interseção vertical, extrai quesitos discursivos com `valor_pontos` e
pontuação total conferida, e calibra o recuo de continuação do item na janela
estrita de 12 a 24 pt (~18 pt real), eliminando a captura indevida de
parágrafos de texto-base (~28–29 pt). `src/questoes_writer.py` persiste em
`textos_base`, `questoes` e `discursivas` no Postgres próprio, e
`scripts/extrair_questoes.py` consome a fila. Os arquivos JSON gerados em
`questoes/` são mantidos localmente (`questoes/` no `.gitignore`) por volume,
sendo 100% regeneráveis sob demanda. 70 cadernos processados, 2.800 itens
(129 anulados), 34 discursivas / 107 quesitos, 145 PDFs na fila concluídos,
0 falhas e 374 testes verdes no pytest.
**Motivo:** Etapa 5C do `task.md`. O objetivo real é saber o que a banca cobra
e viabilizar simulados com refazer de prova.
**Alternativas descartadas:** Chamada ao LLM para estruturar questões (custo e
não-determinismo desnecessários quando a grade e a numeração são regulares);
commitar 140 JSONs pesados no git (sobrecarregaria o repositório com dados
geráveis por script); tolerância genérica de recuo 8–30 pt (engolia a 1ª linha
do texto-base após item de 1 linha). Ver ADR-031.

### 2026-09-27 — Correções da extração dos cadernos (Etapa 5C.1, Sessões 1 a 5, ADR-031)

**Decisão:** Consolidação das correções e robustez do pipeline de extração de cadernos e gabaritos em 5 sessões (ADR-031):
1. **Posição dos itens:** Identificação de itens por x0 na margem da coluna via moda/cluster em vez de flag negrito de fonte (apenas 9,64% das fontes do CEBRASPE usavam flag negrito); itens duplicados ou fora de ordem são bloqueantes; trechos sem recuo anexados ao item com alerta informativo `trecho_sem_recuo_anexado_ao_item`. Vinculação de figuras raster à linha logo acima na mesma coluna com sobreposição horizontal (exceção item → preâmbulo).
2. **Alertas no banco:** Persistência de `alertas text[]` e flag `utilizavel boolean` na tabela `questoes` com view `vw_questoes_utilizaveis` para isolar itens que exigem revisão.
3. **Fila e concorrência:** Reprocessamento automático de grupos via hash sha256 (`fila_extracao_questoes.assinatura_grupo`) em qualquer status quando a composição de gabaritos muda; flag `--reprocessar-erros` para tratar falhas e órfãos; advisory lock de sessão (`pg_try_advisory_lock(5_031_001)`) garantindo consumidor de execução única sem concorrência destrutiva na fila.
4. **Versão de gabarito e discursivas:** Classificação de versão (`definitivo` × `preliminar`) estritamente pelo cabeçalho (ou prefixo do arquivo) com preferência determinística pelo definitivo e alertas informativos (`mais_de_um_gabarito`, `gabarito_preliminar`). Quesitos discursivos extraídos estritamente após o primeiro verbo de comando (`redija`, `elabore`, `aborde`, `discorra`), evitando confusão com datas; tema anafórico rejeitado para `None` com alerta `tema_anaforico`; padrão de resposta ligado preferencialmente por chave de título (`_chave_titulo`), caindo na ligação por ordem se alguma chave faltar ou se repetir; número da questão tirado do título (`Questão N`), com repetição ou buraco gerando o alerta informativo `numeracao_discursiva`; alertas `sem_quesitos` e `quesito_sem_valor`; remoção do rodapé repetido e do cabeçalho institucional em caixa alta no fim da seção do padrão.
5. **Documentação e alinhamento:** Remoção do plano obsoleto `concluir-etapa-5c.md`, documentação de gotchas em `LESSONS.md`, alinhamento de contagens (123 textos-base) e ADR-031 atualizado. 435 testes aprovados (+1 xfail) e suite 100% verde.
**Motivo:** Correções identificadas na revisão da Etapa 5C antes do avanço para a Etapa 5D (`correcoes-etapa-5c.md`).
**Alternativas descartadas:** Confiar em flags de fonte para segmentação de itens; buscar "definitivo" no corpo do documento (o padrão do cargo 2 da PF cita a palavra no texto); capturar quesitos antes do comando discursivo (falso positivo em datas); reprocessamento apenas de status pendentes (não pegava gabaritos associados a posteriori). Ver ADR-031.

### 2026-09-28 — Site público de questões como objetivo e árvore mestre semeada com a 5B

**Decisão:** O objetivo do produto passa a ser um site público de questões
(portfólio, estilo Gran Questões), começando pelo piloto 2025, com a questão
como entidade central e o subassunto como unidade de estudo. As
estatísticas, em ordem, são: o que mais cai na prova, o que o edital cobra,
edital × prova e desempenho pessoal. A taxonomia vira uma **árvore mestre
curada** (`canonico/arvore.json`), semeada com os grupos aprovados da 5B
(mesmo ID). Item de edital e questão apontam para nós (N:N). O roteiro passa
a ser 5B.1 (árvore e banco) → 5B.2 (curadoria) → 5D (questão na árvore) →
5E (views) → 5F (site). A antiga 5B.1 ("divisão de nomes compostos") foi
descartada antes de ser implementada.
**Motivo:** Ao planejar a divisão de nomes compostos, o modelo de árvore
emergente dos editais exigiu mecanismos especiais para o composto
(`Disposições gerais, servidores públicos`) e para a matéria composta do CD
(realocação de 16 + 11 assuntos), e mesmo assim não resolvia a granularidade
diferente entre editais. O dono apontou que a arquitetura misturava o
objetivo do produto (site de questões) com estatística de edital. Numa
árvore fixa com mapeamento N:N, os três casos viram mapeamento comum.
**Alternativas descartadas:** divisão 1 → N com realocação de filhos (plano
original); árvore do zero (perderia a revisão da 5B); taxonomia de terceiros
(sem fonte aberta, risco autoral); simulado estático no Datasette (movido
para o site). Ver ADR-030.



### 2026-09-29 — Classificação das questões na árvore mestre (Etapa 5D)

**Decisão:** Ponte semântica entre as 2.800 questões objetivas e 34 discursivas
extraídas e a árvore mestre curada (3.577 nós). Fonte da verdade canônica em
`canonico/classificacao_questoes.json` (chave estável `<slug>|<caderno>|<numero>`,
hash SHA-1 do enunciado), com confiança categórica (`alta`, `media`, `baixa`) e
cardinalidade até 2 nós (`principal` e opcional `secundario`). O cálculo de
`fora_do_edital` é estritamente local (duas passadas: preferencial do edital do
cargo com flag `false`; reserva das matérias do caderno com flag `true`). Se
nenhum nó servir, registra `sem_no = true` (sem criação automática de nós pelo
pipeline). Banco Postgres é derivado (`questao_no`, `discursiva_no` e view
`vw_questao_no`). Relatório HTML em `classificacao.html` com ordenação por
criticidade (`sem_no` → `baixa` → `media` → `alta`) e CLI de curadoria humana
`scripts/curar_classificacao.py` sob governança soberana do dono.
**Motivo:** Etapa 5D do ADR-030 e ADR-032. Rodada real concluída com 450 chamadas
ao LLM ($0.1939 USD, 0 falhas finais): 2.412 nós alta, 613 média, 3 baixa e 1
item sem nó.
**Alternativas descartadas:** Enviar a árvore inteira no prompt (estouro de
contexto); permitir que o LLM crie nós automaticamente (alucinação taxonômica);
amarrar por IDs seriais de banco (incompatível com DELETE+INSERT de cadernos).
Ver ADR-032.

### 2026-09-29 — Stack e deploy do site público (Etapa 5F.0)

**Decisão:** FastAPI + Jinja2/HTMX/Alpine renderizado no servidor, em 3
camadas (`repositorio` → `servicos` → `api/v1` e `web`), com toda tela
espelhada em JSON para migrar o frontend depois (SvelteKit) sem tocar a
regra. Só Google OAuth. Dados de usuário no schema `app` do mesmo banco,
com roles separadas e a chave estável da 5D (nunca `questoes.id`). Serviço
público via Traefik + Tunnel, sem Access. Republicação com crédito à fonte
e canal de remoção; termos do CEBRASPE conferidos pelo dono antes do deploy.
**Motivo:** o dono preferiu começar em Python e migrar depois; a separação
em camadas é o que torna essa migração barata.
**Alternativas descartadas:** SvelteKit/Vue/Astro já agora; senha própria
ou auth gerenciado; Postgres separado para usuários. Ver ADR-033.

### 2026-10-01 — Frontend de resolução (Etapa 5F.2) e texto-base sob demanda

**Decisão:** As páginas usam a mesma camada `servicos` da API, em rotas
HTML fora do OpenAPI. A primeira entrega pôs `texto_base_texto` e `figuras`
em `QuestaoResumo` para o card da lista. O dono decidiu carregar esses
campos sob demanda (`GET /q/.../anexos`, disparado ao abrir o `<details>`),
o que mantém o contrato da 5F.1. A validação da entrega achou e corrigiu
bugs que os testes de rota não pegavam: id com `|` quebrando o `hx-target`,
XSS do `no_id` dentro do `x-data`, `$nextTick` sem `this`, select que
perdia os outros filtros e fragmento devolvido na restauração de histórico.
**Motivo:** a listagem com 50 itens passava de ~14 KB para ~68 KB, e a
maior parte dos cards não tem o texto-base aberto.
**Alternativas descartadas:** manter os campos na listagem (contrato maior,
payload 5×); carregar anexos de todo card no `load` (uma requisição por
card). Ver ADR-033.

### 2026-10-02 — Coerência dos números do painel de matéria (Etapa 5F.12 - Sessão 3)

**Decisão:** A base única para a porcentagem de incidência na home e no painel de matéria passa a ser "válidas desduplicadas" (computadas via `fn_prova_cobra`). Na tela do painel, os 4 KPIs receberam rótulos mais diretos e tooltips de explicação ("Questões da matéria", "Distintas no recorte", "Anuladas", "Universo de comparação"). O ranking "O que mais cai" também foi complementado com uma linha agregadora "Outros / direto no assunto", para que a soma visível feche exatamente com o total do recorte e a explicação de escopo fique clara (adicionado teste de reconciliação para a LP).
**Motivo:** Usuários reportaram inconsistências ou confusão entre o número do ranking, o total sem filtro e o número do recorte, visto que cada query contava itens de maneira ligeiramente diferente.
**Alternativas descartadas:** Mostrar a porcentagem usando a tabela bruta de questões sem desduplicar (causava peso maior do que a matéria realmente tem nos cadernos).

## 13. LESSONS.md (do projeto)

Ver `LESSONS.md` neste diretório — protocolo padrão descrito no `CLAUDE.md`
raiz do portfólio.
