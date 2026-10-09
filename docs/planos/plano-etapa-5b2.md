# Plano da Etapa 5B.2: curadoria da árvore do piloto

Arquivo autocontido: cada sessão abaixo roda numa conversa própria, sem
precisar reler o `task.md` inteiro nem os ADRs. Ordem obrigatória: **A → B**.
Ao fim de cada sessão: testes verdes (`pytest`, `ruff`), commit
(Conventional Commits, pt-BR) e o checkbox marcado aqui e no `task.md`.

## Contexto (medido em 2026-09-28)

A 5B.1 criou a árvore mestre (`canonico/arvore.json`, 3730 nós, todos
`semente`/`ativo`) e as operações de curadoria (`src/arvore.py`,
`scripts/curar_arvore.py`, ADR-030). A árvore ainda herda três defeitos da 5B:

1. **Subassunto composto:** `S-7b3b2a86ce` "Disposições gerais, servidores
   públicos" (pai `A-09437b84fb`) deveria contar nos irmãos `S-10973fad79`
   "Disposições gerais" e `S-de2a8684f9` "Servidores públicos". Hoje a
   contagem é 3/3/4 em `vw_edital_cobra_subassunto`, e o certo é 8/8.
2. **Assunto composto:** `A-4529f205f7` "Licitações e contratos
   administrativos" (21 subassuntos, pai `M-6f50f4f1dd`) convive com os irmãos
   `A-2261b82645` "Licitação" e `A-91e52e6c2e` "Contratos administrativos".
3. **Matérias compostas do CD:** `M-841dde7520` "DIREITO CONSTITUCIONAL E
   PROCESSO LEGISLATIVO" (16 assuntos) e `M-d5adcb4de4` "DIREITO
   CONSTITUCIONAL E DE REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS" (11
   assuntos) duplicam assuntos de `M-5edb4898a0` "DIREITO CONSTITUCIONAL" e
   de `M-e96f4dbbb5` (Regimento Interno/Regimento Comum/Código de Ética).
   Itens de nível matéria afetados: `direito constitucional e processo
   legislativo` e `nocoes de direito constitucional e de regimento interno da
   camara dos deputados`.

**Decisões do dono (2026-09-28, não reabrir):**
- **Dividir** `A-4529f205f7`. O item do edital aponta para Licitação +
  Contratos, e cada subassunto do composto vai para o assunto certo (fusão
  num irmão equivalente ou movimento).
- **Criar a matéria "Processo Legislativo"** para os assuntos de processo
  legislativo do CD: Procedimento Legislativo (`A-7b775fb1f0`), Matérias
  Legislativas (`A-c6f11b5397`), Processo Legislativo Orçamentário
  (`A-fcd9499dfd`), Lei Complementar nº 95/1998 (`A-238930ee22`) e Processo
  Legislativo (`A-de2fd9af0b`).

**Lacuna do modelo atual:** só mapeamento (`Mapeamento.status`) e nó novo
(`NoArvore.status = proposto`) podem ficar pendentes. Não existe fusão,
movimento ou remapeamento *proposto*, nem destino para um composto que ficou
sem uso: `fundido` redireciona para **um** nó só, e esse é justamente o erro
do `SL-065b9773e6`, rejeitado na 5B.

**Invariantes (ADR-029/030):** o LLM só propõe, com lista fechada e
validação local tipada (ADR-022). Nada `proposto` entra na estatística. **O
agente nunca aprova em nome do dono.** Item novo de edital só é mapeado
automaticamente por regra. Nunca se cria nó novo automaticamente.

---

## Sessão A: propostas de operação, status `aposentado`, detecção de composto, relatório e CLI (sem LLM)

- `[x]` **Propostas no `arvore.json`** (`src/arvore.py`):
  - nova seção `propostas`, com uma linha por proposta e ordenada por ID.
    `carregar`/`salvar` leem e gravam a seção, e o JSON antigo, sem ela,
    continua sendo lido;
  - `@dataclass Proposta`: `id`, `tipo`, `args: dict`, `origem`
    (`regra`/`llm`/`humano`), `justificativa`, `status`
    (`proposto`/`aprovado`/`rejeitado`), `materia` (agrupamento no
    relatório);
  - tipos, aplicados pelas operações que já existem: `fundir`
    {origem, destino} → `fundir_nos`; `mover` {no, pai} → `mover_no`;
    `criar` {nivel, pai, nome} cria o nó já `proposto` (a aprovação muda para
    `ativo`, e a rejeição remove o nó se nada o referencia); `remapear`
    {item, de, para} → `desmapear` + `mapear`; `aposentar` {no};
  - `propor(arv, tipo, args, origem, justificativa, materia)`: o ID é
    `P-` + sha1(tipo + args canônicos), então propor de novo não duplica.
    Antes de gravar, a proposta é validada **aplicando-se numa cópia**
    (`copy.deepcopy`), e a inválida levanta `ArvoreInvalida` sem gravar;
  - `aprovar_propostas(arv, ids)` aplica na ordem, tudo ou nada (pode usar
    um nó `criar` aprovado no mesmo lote). `rejeitar_proposta(arv, id)`.
- `[x]` **Status de nó `aposentado`:** para composto sem uso. Exige nenhum
  filho ativo e nenhum mapeamento aprovado. Não redireciona: `mapear`,
  `mover_no` e `fundir_nos` recusam o aposentado como alvo. O `arvore.html`
  não o mostra na árvore.
- `[x]` **Banco:** em `src/sql/schema_estatisticas.sql` (CHECK de
  `no_arvore.status`, hoje `('ativo','proposto','fundido')`), incluir
  `'aposentado'` de forma idempotente (DROP/ADD CONSTRAINT), no padrão em
  que o schema já é reaplicado. `vw_no_caminho` já filtra `status = 'ativo'`.
  Conferir `stats_writer.py` (carga de `no_arvore` e das pontes só com
  `aprovado`). As propostas **não** vão para o banco.
- `[x]` **Detecção determinística de composto:**
  `arvore.detectar_compostos(arv)` divide o nome de cada nó ativo em `,`,
  `;` e ` e `. Se **cada** pedaço tem a `canonico.chave_regra` de um irmão
  ativo (mesmo pai efetivo), gera `remapear` (item do composto → irmãos) +
  `aposentar` (composto), com origem `regra`. Esperado nos dados reais:
  0 matérias, `A-4529f205f7` e `S-7b3b2a86ce`. O `aposentar` de
  `A-4529f205f7` só valida depois que os 21 filhos tiverem destino
  (Sessão B).
- `[x]` **Relatório** (`scripts/gerar_relatorio_arvore.py`): "Propostas
  pendentes" **agrupadas por matéria**. Cada proposta mostra o ID `P-…`, o
  tipo, o antes → depois (nomes + IDs), a justificativa, a origem e o comando
  pronto. O topo mostra os indicadores do critério de pronto: ocorrências de
  "Disposições gerais" e "Servidores públicos" calculadas do JSON +
  `coletar_ocorrencias`, sem banco.
- `[x]` **CLI** (`scripts/curar_arvore.py`): `--aprovar-proposta P1,P2`
  (lote, tudo ou nada), `--rejeitar-proposta P1,...` e `--propostas [M-..]`
  (lista no terminal). As operações diretas continuam iguais.
- `[x]` **Testes:** em `tests/test_arvore.py`, propor/aprovar/rejeitar cada
  tipo, proposta inválida não gravada, lote tudo ou nada, `criar` + `mover`
  no mesmo lote, `aposentar` recusado com filho/mapeamento, mapear para
  aposentado falha e ida e volta do JSON (com e sem `propostas`). Em
  `tests/test_curar_arvore.py`, as flags novas de ponta a ponta. Em
  `tests/test_arvore_views.py`, o aposentado some das views e o composto
  remapeado conta 1× em cada irmão. Novo: `detectar_compostos` num fixture
  com os 2 casos reais.
- **Pronto quando:** testes verdes; `detectar_compostos` sobre o
  `arvore.json` real devolve exatamente os 2 compostos; o `arvore.html`
  lista as propostas `regra` agrupadas por matéria.

## Sessão B: `scripts/propor_arvore.py` (LLM), rodada real e checkpoint do dono

- `[x]` **Script** no molde de `scripts/propor_sinonimos.py`:
  `chamar_llm_json` (`src/llm_openrouter.py`, com `REASONING_PADRAO`),
  `Contabilidade`, checkpoint por lote, Langfuse
  `nome_trace="propor_arvore"` e segunda tentativa com o erro no prompt
  (não é retry cego).
  - **Escopo = uma matéria:** a subárvore (assuntos e subassuntos) vai com
    IDs locais curtos (`n1`, `n2`...). O LLM propõe (a) fusões de nós irmãos,
    (b) movimentos de granularidade e (c) destino de composto. Matérias com
    menos de 2 assuntos são puladas.
  - **Escopo composto do CD:** `M-841dde7520` + `M-d5adcb4de4` +
    `M-5edb4898a0` + `M-e96f4dbbb5` + a matéria "Processo Legislativo" (uma
    proposta `criar` com origem `humano`, registrando a decisão do dono de
    2026-09-28). Para cada assunto das compostas, o LLM propõe `fundir` num
    equivalente ou `mover` de matéria. Depois disso, o script gera
    `remapear` dos 2 itens de nível matéria e `aposentar` das compostas.
  - **Licitações:** o escopo de Direito Administrativo recebe a instrução de
    dar destino aos 21 filhos de `A-4529f205f7` (Licitação ou Contratos).
  - Resposta Pydantic: lista `{tipo, ids, justificativa}`. Validação
    local: ID desconhecido → `falha_id_desconhecido`; nível errado, ciclo ou
    fusão entre níveis → `falha_operacao_invalida` (via `propor` na cópia).
    Tudo sai `proposto` com origem `llm`.
  - O prompt tem as regras conservadoras do `PROMPT_SISTEMA` dos sinônimos
    (nunca juntar vizinhos; na dúvida, separado).
  - Flags: `--materias M-..,M-..`, `--so-regras` (só a detecção da Sessão
    A), `--dry-run` e `--reavaliar`. A matéria avaliada fica marcada por hash
    da subárvore, e a reexecução só paga pelo que mudou.
- `[x]` **Testes** (`tests/test_propor_arvore.py`, LLM mockado como em
  `test_propor_sinonimos.py`): ID inventado, nível errado e ciclo viram falha
  tipada; segunda tentativa com o erro no prompt; propostas gravadas como
  `proposto`/`llm`; idempotência por hash.
- `[x]` **Rodada real:** `--so-regras` → `--dry-run` (revisar os prompts) →
  rodada real (~60–90 chamadas, custo no log final). Gerar o `arvore.html`.
- `[x]` **Checkpoint do dono:** o dono decide pela CLI ou diz na conversa
  quais `P-…` aprovar ou rejeitar. O agente só executa o que o dono
  disser. Depois, recarregar o banco (`python -m src.stats_writer`).
- `[x]` **Documentação:** ADR-030, seção "Implementação (Etapa 5B.2)"
  (propostas de operação, `aposentado`, `propor_arvore.py`, números da
  rodada e decisões do dono). `task.md` com a 5B.2 `[x]`. `LESSONS.md`, se
  houver gotcha.
- **Pronto quando:** `vw_edital_cobra_subassunto` dá 8 ocorrências para
  "Disposições gerais" e para "Servidores públicos" (7 se `servidores
  públicos civis e militares`, do CD cargo 2, não for fundido); "Direito
  Constitucional" soma os assuntos do CD; `M-841dde7520`, `M-d5adcb4de4`,
  `A-4529f205f7` e `S-7b3b2a86ce` estão `aposentado`; não há proposta
  pendente.
- **Checkpoint:** o dono aprova a árvore antes da Etapa 5D.

> **Resultado (2026-09-28):** 210 propostas revisadas; o dono rejeitou 29 e
> aprovou 181, mais 2 propostas `humano` (LC 95/1998 → Processo Legislativo;
> regime dos parlamentares → Direito Constitucional) e 54 de regra (50
> fusões de irmãos homônimos, `arvore.detectar_homonimos`, e 2 compostos
> novos). Banco recarregado: "Disposições gerais" 8, "Servidores públicos" 7,
> os 4 compostos `aposentado`, nenhuma proposta pendente. Detalhes no
> ADR-030.
