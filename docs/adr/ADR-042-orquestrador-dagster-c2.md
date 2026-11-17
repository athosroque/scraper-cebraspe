# ADR-042: Orquestrador mínimo do pipeline em Dagster (C2 da Etapa 8.C)

- **Status:** Aceito
- **Data da decisão e entrega:** 2026-10-21 — **registro escrito em 2026-11-17** (dívida de
  27 dias; o `CLAUDE.md` §5 e o `task.md` diziam "falta ADR-042" desde a entrega)
- **Etapa:** 9, sessões D5a (KAN-31) e D5b (KAN-32); é também a C2 da Etapa 8.C
  (`plano-etapa-8c.md`)
- **Decisores:** Dono do produto (decisão tomada em 2026-10-13, KAN-67)
- **Relaciona-se com:** ADR-041 (registro do pipeline em `src/registro/`, fonte dos assets),
  ADR-026 (banco Postgres próprio do projeto), ADR-040 (site de documentação, mesmo padrão
  de domínio + Cloudflare Access), ADR-044 (o portão do site é a classificação aprovada, não
  a aprovação do edital — ver §4)

---

## 1. Contexto

Até a Etapa 9, o pipeline não tinha orquestrador: era uma sequência de CLIs `python -m ...`
rodada à mão pelo dono, concurso por concurso (`plano-etapa-8c.md`, "Pipeline existente, por
concurso (sem orquestrador)"). O grafo de etapas só existia implícito nos imports e nos
arquivos que uma etapa gravava e a seguinte lia. A Etapa 8.1 previa resolver isso com um
script próprio, `scripts/lote_concursos.py` (`--proximo`, `--lote`, `--aprovar`, `--status`,
estado em `inventario/lotes.json`) — esse script **nunca foi escrito**; ficou só como
roteiro no `task.md`.

Em paralelo, a Etapa 9 (documentação viva) criou um **registro em Python** das etapas do
pipeline (`src/registro/etapas.py`, ADR-041), pensado desde o início como fonte única "para
o pipeline documentado e o executado" — ou seja, o registro já nasceu com a intenção de
alimentar um orquestrador real, não só a documentação.

Em 2026-10-13 (KAN-67) o dono decidiu (`plano-etapa-9.md`, seção "Decisões do dono"):

> **Dagster já como C2.** A C2 da 8.C deixa de ser o script `scripts/lote_concursos.py`: o
> orquestrador mínimo nasce no Dagster (sessões D5a e D5b, cards KAN-31 e KAN-32), e os
> lotes C3 a C7 já rodam nele.

As sessões D5a e D5b entregaram esse orquestrador e foram validadas em 2026-10-21 contra o
lote da C1 (`SEFA_PR_25` + `BANRISUL_25`), em modo conferência (commits `c3a6eb9`, `c2d7719`
e `3a6120c`; relatório `inventario/lotes/lote_01.md`). O que faltou desde então foi só este
registro.

## 2. Decisão

**O orquestrador mínimo do pipeline nasce no Dagster**, com o desenho abaixo.

### 2.1 Um asset por etapa do registro, chamando as funções existentes

Cada etapa `P0`–`P11` do registro (`src/registro/etapas.py`) virou um `@asset` em
`src/c2/assets.py`, com a mesma chave em minúsculas (`p0` … `p11`) e as mesmas dependências
(`depois_de` do registro → `deps=` do asset). O teste
`test_dagster_definitions_batem_com_o_registro` (`tests/test_registro.py`) é o guarda dessa
correspondência: `asset_keys` tem que ser exatamente igual a `{e.id.lower() for e in ETAPAS}`,
e as dependências de cada asset têm que bater com `etapa.depois_de`. Registro e orquestrador
são a mesma fonte — exatamente a intenção declarada na ADR-041.

Os assets **não reescrevem** a lógica do pipeline: chamam as funções que já existiam
(`CebraspeSpider.process_contest`, `avaliar_chunking_edital`, `processar_fila`/
`atualizar_artefatos_revisao`, `classificar_todas_questoes`, etc.), import tardio dentro do
corpo do asset. A única mudança funcional fora do Dagster foi o parâmetro `--concurso` novo
em `scripts/classificar_questoes.py` (hoje só tinha `--caderno`), necessário para o asset
`p8_classificacao_questoes` rodar por partição.

### 2.2 Partição = concurso; lote = uma execução com N partições

`src/c2/partitions.py` define `concursos_partitions`, uma `DynamicPartitionsDefinition`
sincronizada com os slugs de `inventario/concursos.jsonl`
(`sincronizar_particoes_inventario`). Materializar um lote é executar o job
`lote_concursos` (todos os assets, `define_asset_job` em `src/c2/definitions.py`) para cada
slug do lote. O estado vivo vem das materializações do Dagster e do banco
(`status_revisao_humana`, apontamentos da árvore) — `inventario/lotes.json`, previsto no
texto original da 8.1, deixou de ser necessário.

O lote de validação (C1) tem 2 partições: `CONCURSOS_PADRAO_C1 = ["SEFA_PR_25",
"BANRISUL_25"]`, padrão de `--concursos` em `scripts/executar_c2.py`.

### 2.3 Modo conferência por padrão, com guarda K22 antes e depois

`PipelineConfig` (`conferencia: bool = True`, `exigir_aprovacao: bool = False`,
`numero_lote: int = 1`) controla o comportamento de cada asset. Em modo conferência os
assets de efeito (download, carga no banco, classificação) ficam só-leitura ou em dry-run;
fora dele, cada execução do lote chama `verificar_invariante_piloto` (K22) antes e depois,
e diferença levanta `ViolacaoInvariantePiloto` — a regra P71/A13 do piloto inalterado
(2.800 itens, 129 anuladas, 3.029 apontamentos) se aplica também ao Dagster, sem exceção.

### 2.4 Portões humanos como exceção bloqueante na própria etapa, não só como asset check

A regra única está em `aprovacao_efetiva()` (`src/c2/assets.py`): fora do modo conferência,
a aprovação humana é **sempre** exigida; dentro dele, só se `--exigir-aprovacao` for
passado. Os três portões do pipeline — P3 (edital), P7 (árvore), P9 (classificação) — leem
o estado real (`verificar_portao_edital`, `verificar_portao_arvore`,
`verificar_portao_classificacao`, em `src/c2/checks.py`) e, quando a aprovação é exigida e
não existe, o próprio asset levanta `PortaoHumanoBloqueado`, interrompendo a cadeia da
partição ali.

Isso é diferente dos **asset checks** de D5b (`TODOS_ASSET_CHECKS`,
`@asset_check(blocking=...)`): `check_k22_piloto_p0` e `check_consultas_runbook_p5` são
`blocking=True` (violação de dado, sempre para); já `check_download_p1`,
`check_portao_edital_p3`, `check_portao_arvore_p7` e `check_portao_classificacao_p9` são
`blocking=False` — servem para mostrar o status do portão na UI do Dagster mesmo quando a
etapa não para (por exemplo, em conferência sem `--exigir-aprovacao`). O bloqueio de fato
dos portões humanos vem da exceção dentro do asset, não do `blocking=` do check.

### 2.5 Checagens automáticas e relatório por lote (D5b)

`src/c2/checks.py` também reúne as consultas a–e do `docs/runbook-lote.md`, o alerta K19
("ME sem texto-base", não bloqueante, com as exceções documentadas de `BANRISUL_25` Q22 e
`SEFA_PR_25` Q11/Q50) e a consulta de custo acumulado no OpenRouter
(`consultar_custo_openrouter`). `src/c2/relatorio.py` consolida tudo num
`inventario/lotes/lote_NN.md` com veredito em 3 estados — o relatório do lote da C1
(`lote_01.md`) foi gerado em modo conferência e serviu de prova do "pronto quando" da D5b.

### 2.6 Infraestrutura

`Dockerfile.dagster` (base `python:3.12-slim`, `requirements.txt` do projeto + Chromium do
Playwright) sustenta dois serviços novos no `docker-compose.yml`: `scraper-cebraspe-dagster-
webserver` (porta `127.0.0.1:8014:3000`, roteado por Traefik em
`dagster.projetoathos.com.br`) e `scraper-cebraspe-dagster-daemon` (`dagster-daemon run -m
src.c2.definitions`), ambos com o código montado por bind mount (como o bot do Telegram) e
dependendo de `scraper-cebraspe-db` saudável. O storage do Dagster fica num banco **`dagster`
separado**, dentro do mesmo serviço Postgres `scraper-cebraspe-db` — nunca no banco `cebraspe`
da aplicação (`dagster_home/dagster.yaml`, que já cita este ADR-042 no comentário de
cabeçalho desde a entrega). O domínio segue o mesmo padrão de exposição do Datasette (ADR-015)
e do site de documentação (ADR-040): Traefik + Cloudflare Access, aplicação criada à mão pelo
dono — não encontrei no repositório confirmação de que essa aplicação no Cloudflare Access já
foi criada para `dagster.projetoathos.com.br` (ver §6).

## 3. Por que um orquestrador, e por que Dagster

**Por que um orquestrador.** A alternativa real — a única com texto escrito no repositório
antes desta decisão — era o script encadeado `scripts/lote_concursos.py` previsto na Etapa
8.1 original: `--proximo`/`--lote`/`--aprovar`/`--status` com estado num `inventario/
lotes.json` próprio. Essa rota reimplementaria, só para o lote, bem perto do que o registro
da ADR-041 já descrevia (dependência entre etapas, portão humano por etapa) — duas fontes da
mesma informação, risco já identificado e evitado pela própria ADR-041 ("evitar que o texto
das regras exista em dois lugares" é o mesmo princípio aplicado aqui ao grafo do pipeline).

**Por que Dagster, e não outra ferramenta.** Aqui o repositório é mais fraco do que eu
gostaria de admitir sem ressalva: não encontrei, nem no `plano-etapa-9.md`, nem no
`plano-etapa-8c.md`, nem em nenhum ADR, uma comparação explícita e escrita do Dagster contra
Airflow ou Prefect. A linha do `plano-etapa-9.md` ("Execução e acompanhamento do pipeline |
Dagster, no papel da C2 da 8.C (**decisão aberta**, ver abaixo)") mostra que a escolha da
ferramenta foi uma pergunta em aberto até 2026-10-13, decidida numa conversa com o dono
(KAN-67) cujo raciocínio **não ficou registrado por escrito** — só o resultado. O que o
repositório comprova é:

- O cron já tinha sido descartado nesta mesma Etapa 9, para um problema vizinho (publicar a
  documentação): ADR-040 lista "Cron: publica com atraso, roda sem mudança e esconde o erro
  longe do commit", e a ADR-019 já tinha descartado "Cron/systemd timer regenerando tudo
  periodicamente" para os artefatos de revisão, no mesmo projeto. Não há um texto equivalente
  rejeitando cron especificamente para o C2, mas o padrão de raciocínio do projeto contra cron
  — falta de granularidade por etapa, sem backfill, erro silencioso — é o mesmo que o desenho
  por asset do Dagster resolve (materialização por etapa e por partição, histórico de runs,
  asset checks visíveis).
- O "script simples" (`lote_concursos.py`) foi a alternativa de fato descartada, com texto
  (§3 acima).
- Nada no repositório cita Airflow ou Prefect, nem como considerados nem como descartados.
  **Não afirmo que foram avaliados e perderam** — não há evidência disso. O que a decisão do
  dono registra é só a escolha final (Dagster) e a data (2026-10-13).

## 4. O portão do edital no fluxo, e a relação com a ADR-044

O asset `p3_taxonomia_edital` chama `verificar_portao_edital(slug)`, que lê o
`<edital>.json` do concurso em `revisao_piloto/` e devolve `(aprovado, status_humana)` a
partir do campo `status_revisao_humana` (a mesma leitura que a P41/A25 já descreviam para o
`stats_writer`). Fora do modo conferência (ou com `--exigir-aprovacao`), edital sem
`APROVADO` faz o asset levantar `PortaoHumanoBloqueado` e parar a partição ali — a cadeia
`p4`…`p11` não roda para esse concurso.

Separadamente, o asset `p9_curadoria_classificacao` chama `verificar_portao_classificacao`,
que consulta o banco por apontamentos `proposto` em `questao_no`/`discursiva_no` e por
questões utilizáveis sem nenhum apontamento `aprovado`. Esse é outro portão, com outra
exceção (`PortaoHumanoBloqueado` também, mas disparada por pendência de **classificação**,
não de **edital**).

Essas duas checagens já existiam como portões **separados** desde a entrega de D5a/D5b em
2026-10-21 — o desenho do Dagster já tratava "edital aprovado" (P3) e "classificação
aprovada" (P9) como dois estados independentes, cada um travando um trecho diferente da
cadeia. A ADR-044 (escrita quase um mês depois, em 2026-11-13) nomeou explicitamente o que
cada um desses portões decide: o edital aprovado libera a **estatística de cobertura**
(`fn_prova_cobra`, `vw_edital_cobra_*`), e é a classificação aprovada que libera a
**publicação da questão no site** (`vw_questoes`). O orquestrador não precisou de nenhuma
mudança para ficar consistente com a ADR-044 — a estrutura de dois portões paralelos já
estava no código desde D5a/D5b; a ADR-044 só documentou, por escrito e depois de um
incidente real (`BANRISUL_25` × `SEFA_PR_25`), o que cada portão já fazia de fato dentro do
pipeline (incluindo dentro do Dagster).

## 5. O que o orquestrador mínimo não faz

- **Não decide o próximo lote.** `--proximo` na ordem geral dos anos, tamanho do lote e teto
  de custo — o que sobrou do texto original da Etapa 8.1 — não foi implementado. O lote é
  sempre uma lista explícita de slugs (`--concursos`, padrão `CONCURSOS_PADRAO_C1`). Isso
  está escrito como pendência no `task.md`: "entra depois como schedule, sensor e config do
  Dagster" (Etapa 8.1, "o núcleo sai no Dagster… aqui fica o resto").
- **Não tem schedule nem sensor.** `src/c2/definitions.py` só exporta `assets`,
  `asset_checks` e um `job` (`lote_concursos`); não há `ScheduleDefinition` nem
  `SensorDefinition` no código lido. A execução é sempre disparada à mão
  (`python -m scripts.executar_c2` ou a UI do Dagster).
- **Não aprova nada em nome do dono.** Os três portões humanos (P3, P7, P9) só leem estado
  já aprovado por um ato humano fora do Dagster (edição do `<edital>.json`,
  `scripts/curar_arvore.py`, `scripts/curar_classificacao.py`) — a A30 ("nunca deixar o
  agente aprovar proposta do LLM em nome do dono") vale igual dentro do orquestrador.
- **Não substitui as checagens do runbook como fonte**, só as executa: as consultas a–e e o
  alerta K19 continuam definidos em `docs/runbook-lote.md` e no código de
  `src/c2/checks.py`, que o orquestrador chama.
- **Não está no `make check` nem no `make test-all`.** Não encontrei alvo de Makefile que
  rode uma materialização real do Dagster contra serviços externos; a suíte
  (`tests/test_c2_dagster.py`) testa os assets com as funções mockadas e uma
  `DagsterInstance` efêmera, e o guarda de sincronia (`test_dagster_definitions_batem_com_o_
  registro`) roda sem banco. Rodar um lote de verdade continua sendo um comando manual.

## 6. Consequências operacionais

**Passou a ser automático:**

- Rodar a cadeia inteira `P0`…`P11` para um concurso com um comando
  (`python -m scripts.executar_c2 --concursos <slug>…`), em vez de uma sequência de `python
  -m` separados.
- A guarda do invariante do piloto (K22) antes e depois de cada lote, sem depender de o
  operador lembrar de rodar a checagem.
- O relatório por lote (`inventario/lotes/lote_NN.md`), com os checks automáticos
  consolidados.
- A visibilidade do estado de cada etapa e de cada portão (materializações, asset checks) na
  UI do Dagster, em vez de só no log.

**Continua sendo pausa humana** (o orquestrador para e espera, não decide por conta própria):

- Aprovar a taxonomia do edital (`status_revisao_humana`, portão P3).
- Curar a árvore mestre (`scripts/curar_arvore.py`, portão P7).
- Curar a classificação das questões (`scripts/curar_classificacao.py`, portão P9) — que,
  pela ADR-044, é também o que decide se a questão vai ao ar.
- Decidir o próximo lote e seu tamanho (sem schedule/sensor, §5).
- Criar a aplicação no Cloudflare Access para `dagster.projetoathos.com.br` — passo manual
  do dono, pelo mesmo padrão do Datasette e do site de documentação; não encontrei no
  repositório confirmação de que esse passo já foi feito.

**Dívida que esta entrega deixou, além do próprio ADR:**

- `docs/tecnico/comandos.md` (gerado) ainda cita só a ADR-041 na entrada de
  `scripts.executar_c2`; o `make docs-gerar` deveria passar a citar também esta ADR-042, mas
  regerar essa página fica fora do escopo deste registro (A62: página gerada, não é para
  editar à mão aqui).
- A página do Dagster no guia técnico e a movimentação dos cards no Jira (KAN-31/KAN-32 para
  o status final) seguem pendentes — citadas no `task.md` e fora do escopo deste ADR.

### 6.1 Alternativas consideradas (resumo da §3)

- **Script encadeado `scripts/lote_concursos.py` (Etapa 8.1 original):** descartado por
  duplicar o grafo de dependências que o registro da ADR-041 já ia manter como fonte única.
- **Cron/systemd timer:** sem texto específico para o C2, mas descartado pelo mesmo padrão
  já usado nesta etapa contra cron (ADR-019, ADR-040): sem granularidade por etapa, sem
  histórico de execução, erro silencioso.
- **Airflow, Prefect:** não há registro escrito de avaliação nem de descarte. Ausência
  anotada aqui para não ficar implícita.
