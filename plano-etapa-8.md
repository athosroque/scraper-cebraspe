# Plano — Etapa 8: múltipla escolha, inventário 2020→hoje e ingestão em lotes de 2 concursos

> **Documento autocontido, uma sessão por subetapa (8.0, 8.M, 8.1, 8.2+).**
> Base normativa: ADR-026 (banco próprio), ADR-031 (extração de cadernos), ADR-032
> (classificação e estatísticas), ADR-033 (site). Aprovado pelo dono em 2026-10-08.

## Contexto

Hoje o site tem só o piloto 2025 (5 de ~31 concursos) e **tudo assume Certo/Errado**
(`C`/`E`/`X`). O dono quer expandir para todas as provas do CEBRASPE de **2020 até hoje**,
com um **inventário persistido** (provas por ano + anos disponíveis, via crawler) e ingestão
em **lotes de 2 concursos**, com pausa de revisão, retomada e máxima automação com checagens.
Como provas anteriores/outras usam **múltipla escolha (A–E)**, isso entra **antes** da ingestão.

Ordem: **8.0 inventário** → **8.M múltipla escolha** → **8.1 orquestrador** → **8.2+ lotes**
(ordem definida pelo dono: **2025 → 2026 → 2024 → 2023 → 2022 → 2021 → 2020**). O inventário
vem antes da ME porque é ele que revela quais concursos/cadernos são ME e fornece PDFs reais
para calibrar o parser.

Premissas (ajustáveis): "2 provas" = 2 **concursos** por lote; escopo = ano do slug (`_YY`).

## Fatos que moldam o plano

- `/concursos/encerrado` é JS; a auditoria de 2026-09-19 viu 424 cards de todos os anos
  numa só página → o inventário sai de **uma** passada Playwright, sem filtro de ano na UI.
- `CebraspeSpider.get_contest_links` filtra por `target_year`; `map_pdf_links` já classifica
  edital/prova/gabarito/não-classificado e guarda o `texto` do link (única fonte de tipo/cargo).
- **C/E espalhado em ~35 arquivos**, núcleo em: `src/gabarito_parser.py` (`LETRAS_VALIDAS =
  {C,E,X}`, grade `Item/Gabarito`), `src/prova_parser.py` (`extrair_caderno_objetivo`,
  segmentação por item, `anulada = gabarito == "X"`), `questoes.gabarito CHECK IN ('C','E','X')`
  em `schema_estatisticas.sql:264`, views `vw_certo_errado_por_no` (certos/errados por
  `gabarito = 'C'/'E'`), `app.resposta.resposta CHECK IN ('C','E')` (`site/sql/app_schema.sql`),
  `site/app/modelos.py` (`Literal["C","E"]`, ~34 pontos), `contas_servico`, `simulados_servico`
  (certo +1 / errado −1 / anulada fora), templates `_correcao.html`, card `_card_questao.html`,
  `simulado_*.html`, e o contrato `site/openapi.json` (teste de divergência).
- Nenhum JSON atual de `questoes/` tem alternativas (0/2.800) → não há exemplo local de ME.
- Chave estável 5D (`concurso|caderno|numero`) e hash SHA-1 do enunciado **não podem mudar**
  para as 2.800 questões existentes.

## Fase 8.0 — Inventário (sem LLM; download só da amostra de formato)

> **Sessão única.** Detalhada em 2026-10-08 depois de uma sonda ao vivo (só leitura) das
> listagens do CEBRASPE. Os números abaixo são dessa sonda e servem de referência para os
> testes de reconciliação, mas o site muda: o inventário grava a data de cada mapeamento.

### Fatos da sonda ao vivo (2026-10-08)

| Listagem | Slugs | De 2020+ | Observação |
|---|---|---|---|
| `/concursos/encerrado` | 423 | **272** | 2020: 26 · 2021: 60 · 2022: 47 · 2023: 54 · 2024: 49 · 2025: **31** · 2026: 5 |
| `/concursos/em-andamento` | 66 | 65 | **tem provas e gabaritos publicados**: `PF_25`, `TCU_25_AUFC`, `CAESB_24` (56 provas, 68 gabaritos), `SEFAZ_RJ_25_*`... |
| `/concursos/inscricoes-abertas` + `/novos` | 11 | 9 | ainda sem prova; entram no inventário só como `situacao`, nunca em lote |
| `/concursos` (geral) | 74 | 74 | é a união das três de cima (sem interseção com `encerrado`) |

- Uma só página por listagem, sem paginação nem "carregar mais" (0 botões).
- Os links de navegação (`em-andamento`, `encerrado`, `inscricoes-abertas`, `novos`, `#main`)
  também casam `https://www.cebraspe.org.br/concursos/…`. Hoje só somem porque não têm ano no
  slug. **O inventário tem de excluí-los explicitamente**, e não por acaso.
- Há slug com ano de 4 dígitos (`INSS_2015`). Para `extract_year_from_slug` ele não tem ano.
  É anterior a 2020, mas o inventário trata `_20YY` com alerta para não perder um caso 2020+.
- **Bug de classificação no `map_pdf_links`**: `PADR[ÕOÃA]ES?.*RESPOSTA` não casa o singular
  "PADRÃO DEFINITIVO DE RESPOSTAS" (o padrão exige o `E` de "PADRÕES"), e o padrão de resposta
  cai em `provas`. No piloto isso não apareceu porque `stats_writer.PADRAO_PADRAO_RESPOSTA`
  reclassifica depois. Mas a contagem de provas do inventário sairia inflada (ex.:
  `SEED_SE_25_PROFESSOR`).
- "COMUNICADO – LOCAL DE REALIZAÇÃO DA PROVA…" também cai em `provas`, porque o filtro
  administrativo só conhece "LOCAIS DE APLICA".
- `editais_abertura` e `gabaritos` guardam só a URL, sem o `texto` do link. O inventário
  precisa do texto (definitivo × preliminar, cargo).
- Curso de formação (`ANTAQ_25_CF`): 0 edital de abertura (ele fica no concurso-mãe),
  "PROVA OBJETIVA – CURSO DE FORMAÇÃO" e 15 não classificados (resultados e retificações).
- Ordem de grandeza: **272 encerrados + ~65 em andamento ≈ 337 concursos de 2020+**, ou seja,
  ~170 lotes de 2. Ver "Pontos em aberto".

### Passos

1. **Classificador fino de link** (`src/inventario.py`, função pura e testável, sem
   Playwright): recebe o `texto` do link e devolve `edital_abertura`, `caderno` (objetivo ou
   discursivo), `gabarito`, `padrao_resposta`, `administrativo` ou `nao_classificado`.
   - Normalização igual à do `stats_writer` (sem acento, minúscula) e reuso de
     `PADRAO_PADRAO_RESPOSTA` e `PADRAO_EDITAL_ADMINISTRATIVO` (fonte única; mover para
     `comparacao_texto` se o import ficar circular). Versão (`definitivo`/`preliminar`) pelo
     texto do link.
   - **Não mexer no `map_pdf_links` nesta sessão**: ele decide a pasta de download do piloto
     (`Provas/` × `Gabaritos/`), e `extrair_questoes` depende disso. A correção do spider fica
     registrada para a 8.1, com reextração do piloto confirmando chaves 5D iguais.
   - Testes com os textos reais da sonda (singular e plural de padrão de resposta, comunicado
     de local, curso de formação, retificação, "reabertura"), mais os textos de link do piloto
     (os 5 manifestos em `data/2025/`). Regressão: o piloto continua com 70 provas e 145 PDFs
     na fila.
2. **Coleta** (`src/spider.py`, sem mudar o comportamento atual):
   - `listar_concursos(page, url) -> list[dict]` sem filtro de ano, a partir das 4 listagens
     (`encerrado`, `em-andamento`, `inscricoes-abertas`, `novos`). Grava `situacao`, exclui o
     conjunto `SLUGS_NAVEGACAO` e deduplica por slug. Se um slug aparece em duas listagens,
     vence a mais avançada, com alerta. `get_contest_links` passa a filtrar o resultado dela,
     e os testes atuais do spider continuam verdes.
   - `extract_year_from_slug` aceita `_YYYY` além de `_YY` (teste com `INSS_2015`).
   - `mapear_links_pdf(page, url) -> list[dict]` com **todos** os PDFs (`url`, `texto`,
     `tipo` do classificador fino). `map_pdf_links` continua igual para o downloader.
3. **`scripts/inventariar_concursos.py`** (idempotente e retomável):
   - `--listagens`: passada 1 → `inventario/anos.json` (`ano → {encerrado, em_andamento,
     outros}`) e `ano_desconhecido` com os slugs (nunca descartar em silêncio).
   - `--mapear [--ano 2025] [--situacao encerrado,em_andamento] [--refazer]`: passada 2,
     concurso a concurso, com `stealth_wait`. Pula o que já foi mapeado (salvo `--refazer`).
     Falha isolada vira `erro` no registro e não aborta o lote; grava a cada concurso.
     Estimativa de ~337 páginas × ~5 s ≈ 30 min, que dá para rodar em background.
   - Saída `inventario/concursos.jsonl`, uma linha por concurso, ordenada por slug: `slug`,
     `orgao`, `ano`, `situacao`, `url`, `data_mapeamento`, `contagens` por tipo, `pdfs`
     (`url`, `texto`, `tipo`, `versao`), `alertas` (`sem_edital_abertura`, `sem_caderno`,
     `sem_gabarito`, `curso_formacao`, `muitos_nao_classificados`, `ano_4_digitos`),
     `formato_provavel` e `incluir` (default `null`, que o dono decide). `no_banco: true` para
     os 5 do piloto. A leitura e a escrita passam só por funções de `src/inventario.py`,
     nunca por `json.load` solto (lição da 5B.1).
   - `--relatorio` → `inventario/RELATORIO.md`: ano × situação × concursos/cadernos/
     gabaritos; concursos sem caderno ou gabarito; top textos `nao_classificado` por ano;
     curso de formação; o que está no banco.
4. **Amostra de formato (CE × ME)**: em vez de 1 prova por concurso (~300 PDFs), amostrar
   **todos os concursos de 2025 e 2026** (os próximos lotes) e **3 por ano** de 2020–2024.
   Baixar o primeiro caderno objetivo de cada um para `data/inventario_amostra/`, sem tocar no
   manifesto do downloader e validando `%PDF-`. Detectar no texto do caderno se tem
   alternativas `(A)…(E)` / "Julgue os itens" e gravar `formato_provavel` (`ce`/`me`/`misto`/`?`).
   O formato dos demais é preenchido no download do lote (8.1). **Saída que destrava a 8.M:**
   lista de 2–3 cadernos ME reais (1 básico, 1 específico, 1 com figura) no `RELATORIO.md`.
5. **Banco (derivado)**: tabelas `inv_concurso` e `inv_pdf` em `schema_estatisticas.sql`,
   carregadas por `stats_writer.gravar_inventario` (substitui tudo numa transação, é
   idempotente e preserva os GRANTs pelo `criar_schema`). View `vw_inventario_ano`. Sem FK
   para `concursos` (o inventário é maior que o banco); o cruzamento é pelo `slug`.
6. **Checagens (teste + script)**: 31 encerrados de 2025 com os mesmos slugs da auditoria;
   os 5 do banco presentes e com contagens compatíveis com `provas`/fila; nenhum slug de
   navegação; todo concurso 2020+ com `data_mapeamento` ou `erro` explícito; `ruff` e
   `make test-pipeline` verdes. Testes do Playwright com HTML fixture em
   `tests/fixtures/inventario/` (listagem + página de concurso), sem rede.
7. **Pausa 0 (dono)**: lê o `RELATORIO.md`, marca `incluir` (curso de formação? concurso só
   com discursiva? cadastro reserva?) e responde aos "Pontos em aberto" de tamanho de lote e
   concursos em andamento. Só então começa a 8.M.
   - **Feito em 2026-10-09 (ADR-037):** o `incluir` sai de `inventario/exclusoes.json` (fonte
     única; quem não está lá entra). Curso de formação **não entra** (páginas `_CF`/MTE_25
     na lista e `pdf_vai_para_o_site` para o PDF de CF em concurso incluído); concurso só
     discursivo **entra**. A 8.1 seleciona só `incluir=true` e só PDFs de
     `pdf_vai_para_o_site`; concurso com `aguardando_prova` espera o remapeamento.

### Pronto quando

`inventario/{anos.json,concursos.jsonl,RELATORIO.md}` versionados, com 2020+ mapeado (zero
concurso sem estado), `formato_provavel` na amostra, 2–3 cadernos ME reais identificados,
`inv_*` no banco, `ruff` e `make test-pipeline` verdes, e `task.md`/`CLAUDE.md` §5
atualizados.

## Fase 8.M — Múltipla escolha (antes de qualquer lote novo)

Princípio: **tipo por questão**, não por concurso (há cadernos mistos). Retrocompatível.

1. **Modelo/banco** (`schema_estatisticas.sql`, `questoes_writer.py`, `stats_writer.py`):
   - `questoes.tipo` (`certo_errado` default | `multipla_escolha`) e `alternativas jsonb`
     (`[{letra, texto}]`); `gabarito` passa a aceitar `A`–`E` além de `C`/`E`/`X` — atenção à
     **colisão das letras `C` e `E`** (Certo/Errado × alternativas C/E): `gabarito` só é
     interpretado junto com `tipo`, que passa a ser obrigatório em todo `JOIN`/`FILTER`.
     (Alternativa a avaliar na sessão: gravar CE como `C`/`E` e ME como `A`..`E`, ou prefixar.)
   - `vw_questoes` expõe `tipo`/`alternativas`; `vw_certo_errado_por_no` e `vw_comparativo_nivel`
     filtram `tipo = 'certo_errado'` (números do piloto inalterados); view nova de gabarito
     por nó só se houver uso real (YAGNI).
   - Hash 5D: CE continua SHA-1 do enunciado; ME = SHA-1 de enunciado + alternativas
     normalizadas (detecta mudança). Chaves 5D das 2.800 existentes **inalteradas** (teste).
2. **Gabarito** (`gabarito_parser.py`): `LETRAS_VALIDAS` por tipo (grade ME com A–E e
   anulada `X`); a grade `Item N / Gabarito L` pode ser idêntica — validar com PDF real; letras
   inválidas continuam alerta bloqueante. Detectar o tipo do caderno (alternativas no corpo ×
   "Julgue os itens"), nunca pela letra do gabarito.
3. **Prova** (`prova_parser.py`): segmentar alternativas `(A)`/`A)`/`A.` dentro do item
   (enunciado ≠ alternativas), com continuação multilinha, alternativas com figura/tabela;
   validação: ME tem 4–5 alternativas consecutivas A..; falha = alerta bloqueante visível
   (padrão ADR-017/031). Calibrar com 2–3 cadernos ME **reais** achados no 8.0 (1 básico, 1
   específico, 1 com figura); testes com trechos fixos e `xfail` documentado se aparecer caso.
4. **Classificação 5D** (`candidatos_questao.py`, prompt de `classificar_questoes.py`,
   `gerar_relatorio_classificacao.py`): incluir alternativas no prompt de questão ME.
5. **Site** (`site/app/...`): `Resposta` aceita `C|E|A..E` conforme o `tipo`; card renderiza
   radios por alternativa (reuso do card Certo/Errado, 5H); `_correcao.html` mostra a
   alternativa correta; `app.resposta.resposta` ajustado (migration idempotente em
   `aplicar_schema_app.py`, sem senha no SQL); filtros ganham `tipo` (faceta "Formato");
   simulado: pontuação **por tipo** (CE +1/−1; ME +1/0 — confirmar com edital do concurso ME
   real e registrar em ADR); anulada continua fora da nota. Reexportar `site/openapi.json`
   (`python site/scripts/exportar_openapi.py`) e manter `test_openapi_documentado`.
6. **Gate da 8.M:** pytest/ruff verdes (`make test-all`); piloto idêntico (2.800 itens, 129
   anuladas, 3.029 apontamentos); 1 concurso ME de ponta a ponta no site validado no Chromium
   (responder, corrigir, simulado, filtro); ADR-038.

## Fase 8.1 — Orquestrador de lotes

`scripts/lote_concursos.py`, estado em `inventario/lotes.json` (por concurso: `mapeado →
baixado → edital_extraido → questoes_extraidas → classificado → aguardando_revisao →
aprovado`), idempotente e retomável: `--proximo` (2 concursos, na ordem 2025 → 2026 →
2024…2020 definida em `inventario/concursos.jsonl`, só `incluir=true` e sem
`aguardando_prova`; baixa só os PDFs de `pdf_vai_para_o_site`, ADR-037), `--lote N`,
`--aprovar N`, `--status`.
Chama as funções existentes (`process_contest`, `revisar_edital_piloto`,
`atualizar_artefatos_revisao`/`processar_fila`, `classificar_todas_questoes`); adiciona
`--concurso` ao `classificar_questoes`. Para em falha bloqueante, sempre ao fim do lote, e
gera `inventario/lotes/lote_NN.md`. Teto de custo LLM por lote.

### Checagens automáticas por lote (gate antes da revisão humana)

| Camada | Checagem |
|---|---|
| Download | PDFs válidos (`%PDF-`), contagem == PDFs do inventário que vão para o site (`pdf_vai_para_o_site`), nenhum `nao_classificado` novo sem decisão |
| Edital | 0 alertas bloqueantes (`validar_taxonomia`), chunks sem falha, cargos/níveis detectados |
| Prova | fila `concluido`; itens == gabarito; sem numeração duplicada; **ME: 4–5 alternativas por item**; gabaritos em hash ligados; discursivas com quesitos |
| Banco | inventário × `provas` × `questoes` batem; chaves 5D antigas inalteradas |
| Classificação | 0 `sem_no` sem explicação; distribuição de confiança; nós novos listados |
| Site | amostra: 3 questões abrem em `/q/<ID>`, contagem por concurso == SQL; `make test-pipeline` verde |

**Revisão humana (a pausa):** taxonomia do edital (`status_revisao_humana`), pendências em
`arvore.html`, classificação média/baixa em `classificacao.html` (alta em lote), 3 questões
conferidas no PDF (1 básica, 1 específica, 1 discursiva/ME). `--aprovar N` libera o próximo.

## Fase 8.2+ — Lotes e calibração por ano

1º lote de cada ano = calibração (sem LLM de classificação até o parser fechar); correção de
parser exige reextração dos lotes anteriores confirmando que chaves 5D e contagens não mudam.
Ao fim de cada ano: recontar views (5E), `make test-all`, atualizar `CLAUDE.md`/`task.md`,
`LESSONS.md` se custou >30 min; checar desempenho de `fn_prova_cobra` com o volume maior.

## Arquivos críticos

- Modificar: `src/spider.py`, `src/gabarito_parser.py`, `src/prova_parser.py`,
  `src/questoes_writer.py`, `src/stats_writer.py`, `src/sql/schema_estatisticas.sql`,
  `src/candidatos_questao.py`, `scripts/classificar_questoes.py`, `site/app/modelos.py`,
  `site/app/servicos/{contas,simulados}_servico.py`, `site/app/repositorio/*`, templates
  (`_card_questao.html`, `_correcao.html`, `simulado_*.html`), `site/sql/app_schema.sql`,
  `site/openapi.json`, `task.md`, `CLAUDE.md`.
- Novos: `scripts/inventariar_concursos.py`, `scripts/lote_concursos.py`, `inventario/`,
  testes em `tests/` e `site/tests/`.

## Verificação

1. 8.0: inventário reconcilia com os 31 encerrados de 2025 e os 5 do banco; classificador fino
   testado com textos reais (incl. "PADRÃO DEFINITIVO DE RESPOSTAS"); HTML fixture sem rede.
2. 8.M: testes unitários do parser ME (PDF real + fixtures), regressão do piloto (contagens e
   chaves 5D idênticas), `make test-all`, validação no Chromium de 1 concurso ME.
3. 8.1: orquestrador com etapas mockadas (retomada, parada no gate, `--aprovar`).
4. Lote real 1 (2 concursos de 2025): tabela de checagens verde, 3 questões conferidas.

## Pontos em aberto

- Lote = 2 concursos (premissa) ou 2 cadernos? (2026 já definido: logo após 2025.)
- **Tamanho do lote × volume (sonda 2026-10-08):** ~337 concursos de 2020+ dão ~170 lotes de
  2, cada um com uma pausa de revisão. Proposta: manter 2 no lote de calibração de cada ano e
  liberar `--tamanho N` (ex.: 5–10) quando o gate do ano estiver estável. Quem decide é o dono,
  na Pausa 0.
- **Concursos em andamento:** a premissa "só encerrados" deixa de fora `PF_25`, `TCU_25_AUFC`
  e `CAESB_24`, que já têm provas e gabaritos definitivos. Proposta: entram quando o
  inventário mostrar gabarito definitivo, com remapeamento antes do lote (PDF novo vira
  alerta).
- Pontuação do simulado ME (+1/0 assumido) — confirmar pelo edital do 1º concurso ME.
- Classificação revisada por lote (recomendado) ou rodada única no final?
