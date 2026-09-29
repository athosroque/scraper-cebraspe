# Plano — Etapa 5E: Estatísticas (views no banco)

> **Documento autocontido para execução em 3 sessões (uma por conversa).**
> Não requer reler `task.md` nem ADRs anteriores. Base normativa: ADR-030
> (árvore mestre, estatística sobe a árvore), ADR-031 (questões), ADR-032
> (classificação). Tudo aqui é **SQL + Python determinístico, sem LLM**.

---

## 1. Contexto e objetivo

A 5D deixou **2.800 questões objetivas e 34 discursivas** ligadas a nós da
árvore mestre, todas `aprovado` (`questao_no` 2.965 linhas, `discursiva_no`
64). A 5E transforma isso nas estatísticas do produto, em ordem de prioridade
(ADR-030): **(1) o que mais cai na prova**, **(2) o que o edital cobra**,
**(3) edital × prova**; a (4) desempenho pessoal é da 5F.3. As views são a
única interface de leitura do site (5F.1 lê `vw_questoes`).

**Pronto quando** (critério do `task.md`), com as consultas rodando no banco:
1. top 10 subassuntos de LÍNGUA PORTUGUESA em superior × médio;
2. questões de um subassunto filtradas por cargo e nível;
3. "no edital, nunca cobrado" do `PF_25_ADM` cargo 1.

---

## 2. Estado atual do banco (o que já existe e será reutilizado)

- `vw_no_caminho`: `id`, `no_efetivo` (resolve fundido), `nivel`, `nome`,
  `caminho` (`Matéria > Assunto > Subassunto`), `materia_id`, `assunto_id`.
  Só expõe a cadeia `ativa`.
- `vw_questao_no`: 1 linha por (questão × nó aprovado), com `papel`
  (`principal`/`secundario`), `confianca`, `fora_do_edital`, `anulada`,
  `utilizavel`. **Não tem** cargo, nível, concurso, órgão nem ano.
- `vw_arvore_edital_por_cargo`: 1 linha por (item de edital × cargo × nó),
  com concurso, órgão, banca, ano, nível, tipo, cargo, `no_id`,
  `no_materia_id`, `no_assunto_id`, `status_revisao`. Já expande o básico
  por cargo respeitando `cargos_restritos`.
- `vw_edital_cobra_base` + `vw_edital_cobra_{subassunto,assunto,materia}`
  (+ `_todas`): ocorrência = `taxonomia_itens.id` distinto, subindo a árvore,
  só `aprovado` na variante oficial. **Cobre o item (2); não muda.**
- Contexto da prova: `questoes.prova_id → provas → provas_cargos →
  cargos_editais → concursos → dim_orgao`. `provas.tipo` é
  `objetiva_basica` | `objetiva_especifica` | `discursiva`. Nível vem de
  `cargos_editais.nivel`. Um caderno **básico cobre N cargos** (CB1 = cargos
  1–14); o específico é 1:1.
- Sem `materia_origem` ainda: cargo de especialidade usa o nome do cargo como
  matéria (12 chunks, todos `PF_25_ADM`, chunks 15 e 22–32).

---

## 3. Decisões de desenho (propostas; confirmar com o dono no início da Sessão B)

1. **Grão base = (questão × cargo).** O caderno básico vale para vários
   cargos, então a linha plana é expandida por `provas_cargos`. Toda
   contagem usa `count(DISTINCT questao_id)`; a mesma questão nunca conta 2×
   no mesmo nó, mesmo aparecendo em vários cargos ou com 2 nós na mesma
   subárvore. Filtrar por cargo/nível/tipo reduz o universo sem duplicar.
2. **Subida na árvore**, como em `vw_edital_cobra_base`: questão em
   subassunto soma no subassunto, no assunto e na matéria; questão em
   assunto soma no assunto e na matéria, nunca abaixo.
3. **Nó `principal` × `secundario`:** as contagens oficiais usam **todos** os
   nós aprovados (a questão interdisciplinar cobra os dois assuntos), mas a
   view expõe `so_principal` (contagem apenas com `papel = 'principal'`)
   para o site poder alternar. Percentual = questões distintas no nó ÷
   questões distintas do universo filtrado (denominador **não** soma nós,
   então a soma dos percentuais pode passar de 100%; documentar na view).
4. **Universo oficial:** `q.utilizavel` **e** concurso `aprovado`. Anuladas
   ficam **fora do total e viram coluna à parte** (`anuladas`). As 19 questões
   não utilizáveis (`simbolo_ilegivel`) continuam classificadas, mas não
   entram em estatística.
5. **Edital × prova compara por cobertura descendente:** o item do edital em
   nó X cobre X e todos os descendentes de X. "Cobrado fora do edital" =
   nó da questão sem ancestral-ou-igual mapeado no edital daquele cargo.
   "No edital e nunca cobrado" = nó mapeado pelo edital do cargo sem
   nenhuma questão nele **nem em descendente**. O flag `fora_do_edital` da 5D
   (calculado por candidatos no LLM) vira **checagem cruzada**: a view
   recalcula a partir do edital e um teste compara as duas (divergência =
   investigar, não corrigir em silêncio).
6. **Só concurso `aprovado`** nas views oficiais; sufixo `_todas` só onde já
   existe o padrão (edital cobra). Views novas nascem oficiais.
7. **Peso por concurso:** somar questões de todos os concursos faz o
   concurso com básico grande (CD: 90 questões) pesar mais. As views de
   "o que mais cai" expõem **duas visões**: `questoes` (contagem bruta) e
   `pct_medio_por_concurso` (média dos % de cada concurso no nó, cada
   concurso com peso igual). O site escolhe qual mostrar; a bruta é o padrão.
8. **Enunciado repetido entre cadernos:** antes de fechar a contagem, medir
   (Sessão B) se o mesmo `hash_enunciado` (SHA-1, já guardado na 5D) aparece
   em mais de um caderno do mesmo concurso (versões do mesmo caderno). Se
   aparecer, definir a regra com o dono (contar 1× por concurso × enunciado)
   antes de publicar as views; se não aparecer, registrar "0 repetições" no
   ADR-032.
9. **Ano = ano do concurso** (`concursos.ano`, vindo do slug `_YY`), não o
   da aplicação da prova. O filtro existe, mas o piloto só tem 2025;
   tendência entre anos só faz sentido depois de coletar outros anos
   (o crawler filtra só `_25`).
10. **Matéria = nome do cargo** (`ESTATÍSTICO`…) **não é renomeada** para
   disciplina (decisão do dono, 2026-09-27): só marcada, e as views/site a
   exibem como "Conhecimentos específicos — <cargo>".

---

## 4. Sessões

### Sessão A — `materia_origem` (parser, backfill, banco), sem LLM

**Objetivo:** marcar de onde veio cada matéria, para as views distinguirem
disciplina real de "matéria que é o cargo". Vem primeiro porque as views da
Sessão B exibem essa marca.

- `[x]` `src/edital_parser.py`: novo campo `ChunkTaxonomia.materia_origem`
  (`cabecalho` | `prefixo` | `cargo`), definido nos **três ramos** de
  `dividir_por_cargo_e_materia` (matéria de cabeçalho `PADRAO_MATERIA`;
  prefixo em caixa alta antes do item 1, caso do CD; cargo sem matéria
  nomeada). Incluir em `CAMPOS_CLASSIFICACAO_CHUNK`
  (`src/edital_parser.py:163`), que é a lista única propagada para
  `.json`, `.auditoria.json` e `revisao.db`
  (`scripts/gerar_db_datasette.py` também lê essa lista; conferir
  `TIPOS_COLUNAS_CLASSIFICACAO`).
- `[x]` Backfill sem LLM em `scripts/backfill_classificacao_chunks.py` nos 5
  editais. **Esperado:** 12 `cargo` (todos `PF_25_ADM`), 1 `prefixo` (CD), o
  resto `cabecalho`. Conferir a contagem antes de gravar; qualquer outro
  número é bug do parser, não do dado.
- `[x]` `src/stats_writer.py` (`montar_carga_concurso`, ~linha 258): levar
  `materia_origem` para o item; `src/sql/schema_estatisticas.sql`:
  `taxonomia_itens.materia_origem TEXT CHECK (...)` (migração idempotente com
  `ADD COLUMN IF NOT EXISTS`) e `dim_materia.nome_de_cargo boolean`.
  - **Armadilha:** `dim_materia` é única por chave normalizada entre
    concursos; um nome pode ser cargo num edital e disciplina em outro. Por
    isso a verdade fica em `taxonomia_itens.materia_origem` (grão do chunk) e
    `dim_materia.nome_de_cargo` é **derivado** (`bool_and(materia_origem =
    'cargo')` sobre os itens da matéria) na carga, nunca gravado à mão.
- `[x]` Testes: os três ramos do parser (fixtures reais curtas, incluindo o
  caso CD de prefixo e um cargo de especialidade da PF); backfill alinha 12/1/
  resto; carga grava a coluna e o derivado; reexecução idempotente.
- **Aceite:** `pytest` + `ruff` verdes; no banco,
  `select materia_origem, count(distinct chunk_index) ...` = 12 / 1 / demais;
  `python -m scripts.atualizar_revisao` sem diff extra na segunda execução.

### Sessão B — Base plana e "o que mais cai" (itens 1 do produto)

**Objetivo:** views `vw_questoes_contexto`, `vw_questoes` e
`vw_prova_cobra_*`. Todo o SQL em `src/sql/schema_estatisticas.sql`, com
`CREATE OR REPLACE VIEW` e ordem de dependência respeitada (as views novas
vão **depois** de `vw_questao_no`; o bloco de `DROP VIEW ... CASCADE` no topo
da seção de views deve listar as novas, senão mudar coluna de uma view
existente quebra a reaplicação).

- `[x]` **Decidir com o dono** os pontos da §3 (grão, principal×secundário,
  denominador, tratamento de anuladas). Registrar a decisão final no ADR-032.
- `[x]` `vw_questoes_contexto`: 1 linha por (questão × cargo) com `questao_id`,
  `numero`, `codigo_caderno`, `prova_tipo`, `tipo_conhecimento` (derivado de
  `provas.tipo`: `objetiva_basica` → `basico`, `objetiva_especifica` →
  `especifico`), `concurso`, `orgao`, `banca`, `ano`, `cargo_numero`, `cargo`,
  `nivel`, `gabarito`, `anulada`, `utilizavel`, `status_revisao`.
- `[x]` `vw_questoes` (base da busca do site, 5F.1): junta o contexto ao caminho
  do nó (`vw_questao_no`): enunciado, `secao`, texto-base (`textos_base`),
  `figuras`, `no_id`, `no_caminho`, `papel`, `confianca`, `fora_do_edital`,
  flag de matéria-cargo (`nome_de_cargo`, rótulo "Conhecimentos específicos
  — <cargo>"). Uma linha por (questão × cargo × nó); o site agrupa por
  `questao_id`. Documentar no comentário SQL o grão e o `DISTINCT` esperado.
- `[x]` **Checagem de enunciado repetido (decisão 8):** consulta única sobre
  `canonico/classificacao_questoes.json` (ou `questoes`) agrupando por
  `hash_enunciado` dentro do concurso; registrar o resultado no ADR-032.
- `[x]` **Filtros suportados** (colunas obrigatórias em `vw_questoes`, para o
  site filtrar sem nova view): banca, órgão, ano, concurso, cargo, nível,
  tipo_conhecimento, matéria/assunto/subassunto (via `no_caminho`, `materia_id`,
  `assunto_id`), `gabarito` (C/E), `anulada`, `confianca`, `fora_do_edital`,
  `papel`, `nocoes`, `nome_de_cargo`, `codigo_caderno`, `secao`, presença de
  texto-base (`texto_base_id IS NOT NULL`) e de figuras
  (`jsonb_array_length(figuras) > 0`, da questão ou do texto-base). Os filtros
  "já resolvidas/erradas/nunca vi" são da 5F.3 (dependem de login) e ficam
  fora das views. Discursivas filtram em `vw_discursivas` por concurso,
  cargo, nível e matéria.
- `[x]` `vw_prova_cobra_base` (análoga a `vw_edital_cobra_base`): 
  (`questao_id`, `cargo_edital_id`, `nivel_alvo`, `alvo_id`) subindo a
  árvore, só `papel` conforme decisão 3; filtros de universo (§3.4) aplicados
  aqui uma vez.
- `[x]` `vw_prova_cobra_{subassunto,assunto,materia}`: por nó **e** com as
  dimensões de filtro (`banca`, `orgao`, `ano`, `concurso`, `cargo`, `nivel`,
  `tipo_conhecimento`) como colunas — o site filtra com `WHERE`, então a
  view precisa ser agregada **no grão máximo** (concurso × cargo × nível ×
  tipo × nó) e o front/API reagrega. Colunas: `questoes`, `anuladas`,
  `so_principal`, `pct_do_universo` e `pct_medio_por_concurso` (decisão 7).
  Conferir custo com `EXPLAIN ANALYZE`
  (universo é pequeno, 2.800 questões; se passar de ~100 ms, indexar
  `questao_no(no_id)` já existe, avaliar índice em `provas_cargos`).
- `[x]` `vw_certo_errado_por_no`: proporção C/E e anulações por nó
  (`gabarito` em `C`/`E`/`X`; `X` = anulada, ver `questoes.anulada`).
- `[x]` `vw_comparativo_nivel`: médio × superior por nó, lado a lado
  (`questoes_medio`, `questoes_superior`, e a diferença de % — só nós com
  ocorrência em ao menos um nível).
- `[x]` Testes em `tests/test_estatisticas_views.py` (padrão de
  `tests/test_arvore_views.py`, Postgres real com fixtures mínimas): questão
  de caderno básico em 3 cargos conta 1× no nó ao filtrar 1 cargo e 1× (não
  3×) sem filtro de cargo; questão com 2 nós na mesma subárvore conta 1× no
  assunto-pai; questão em nó de assunto não soma em subassunto; anulada
  fora do total; questão não utilizável e concurso `pendente` fora; nó
  fundido soma no `no_efetivo`; `pct_medio_por_concurso` com 2 concursos de
  tamanhos diferentes (peso igual por concurso, não por questão); matérias
  básicas de mesmo nome em cadernos de concursos distintos somam como
  questões distintas, mas o mesmo caderno em 14 cargos conta 1×.
- `[x]` **Correção pós-revisão:** as views por cargo não se somam; a leitura com
  filtros é `fn_prova_cobra(...)` (conta distinto depois de filtrar, média
  por concurso sob os filtros). A Sessão C e a API da 5F leem por ela. Ver ADR-032.
- **Aceite:** consultas 1 e 2 do "Pronto quando" rodam; conferir a mão o
  top 3 de LÍNGUA PORTUGUESA superior contra `classificacao.html`;
  reconciliar os totais e escrever a conta no ADR-032: 2.781 questões
  `utilizavel` = (não anuladas, que entram no total) + (anuladas, que ficam
  só na coluna `anuladas`); as 19 não utilizáveis ficam fora de tudo.
  `pytest` + `ruff` verdes.

### Sessão C — Edital × prova, discursivas, peso e fechamento

**Objetivo:** item (3) do produto e as views restantes; documentação e
aceite final.

- `[x]` `vw_edital_vs_prova`: por (concurso × cargo × nó) com `no_edital`
  (cobertura descendente, decisão 5), `questoes` cobradas, `razao =
  questoes / previsao` (previsão = ocorrências do edital no nó) e
  `situacao` ∈ `cobrado_no_edital` | `no_edital_nunca_cobrado` |
  `cobrado_fora_do_edital`. Usar o nível em que o edital aponta para
  evitar "nunca cobrado" falso quando o edital está em assunto e a questão
  em subassunto (regra da descendência).
- `[x]` Teste de consistência 5D × 5E: para todo par (questão, nó) aprovado,
  `fora_do_edital` da 5D **==** `situacao = 'cobrado_fora_do_edital'` da
  view. Divergências são listadas e analisadas uma a uma; **não** sobrescrever
  o dado da 5D sem o dono (é canônico, ADR-032).
- `[x]` `vw_peso_materia_cargo`: % de questões por matéria em cada cargo
  (a prova do cargo = básico + específico), para o "peso de cada matéria".
  Matéria-cargo (`nome_de_cargo`) aparece como "Conhecimentos específicos —
  <cargo>", não como disciplina.
- `[x]` `vw_discursivas`: tema por matéria/cargo/nível a partir de
  `discursivas` + `discursiva_no` (64 linhas), com `titulo`, `tema`, nós e
  `fora_do_edital`. Discursiva **não** entra nas contagens de questão.
- `[x]` Aplicar tudo no banco real (`python -m src.stats_writer`) e rodar as
  **três consultas de aceite** do §1; registrar as saídas resumidas no ADR-032.
- `[x]` Documentação: ADR-032 (seção "Estatísticas 5E": decisões finais,
  contas de reconciliação, custo das views); `CLAUDE.md` (§5 marcar 5E
  `[x]`, §3 arquitetura, §6 pattern "estatística sobe a árvore e conta
  questão distinta", §7 anti-patterns encontrados); `task.md` (5E `[x]`,
  próxima prioridade = 5F.0); `LESSONS.md` se houver gotcha.
- `[x]` Atualizar §5 do `CLAUDE.md`: "Prioridade atual" passa para 5F.
- **Aceite final:** `pytest` e `ruff` 100% verdes no repositório; as 3
  consultas do §1 funcionam; nenhuma view nova ignora `status_revisao =
  'aprovado'`, `utilizavel` ou a resolução de nó fundido.

---

## 5. Mapeamento de arquivos

**Alterados:** `src/edital_parser.py`, `scripts/backfill_classificacao_chunks.py`,
`scripts/gerar_db_datasette.py` (se a lista de campos exigir),
`src/stats_writer.py`, `src/sql/schema_estatisticas.sql`,
`docs/adr/ADR-032-classificacao-questoes-arvore.md`, `CLAUDE.md`, `task.md`,
`revisao_piloto/*.json` (backfill; versionados).

**Novos:** `tests/test_estatisticas_views.py`, `plano-etapa-5e.md` (este;
remover ao concluir a etapa, como o `plano-etapa-5b2.md`).

## 6. Riscos e armadilhas conhecidas

- **Contar questão 2×:** básico expande por cargo e a questão pode ter 2 nós.
  Sempre `count(DISTINCT questao_id)` sobre o nó de destino.
- **Nunca `UPDATE` direto no banco** para "corrigir" contagem: a fonte é o
  canônico (`arvore.json`, `classificacao_questoes.json`) e o JSON dos
  editais; o banco é derivado.
- **Reaplicação do schema:** mudar colunas de view exige `DROP VIEW ... CASCADE`
  no bloco de topo; testar reaplicar o schema duas vezes seguidas.
- **`vw_no_caminho` só expõe cadeia ativa:** nó `proposto`/`aposentado` some
  do JOIN silenciosamente; se algum total não fechar, compare com
  `questao_no` sem a view.
- **Não renomear matéria-cargo para disciplina** (decisão do dono).
- **Não rodar** `scripts/semear_arvore.py --forcar` nem reclassificar questões
  (custa tokens e apaga decisão do dono).
