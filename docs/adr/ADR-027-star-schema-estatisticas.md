# ADR-027: Star Schema de Estatísticas, Gravação Idempotente e Fila de Provas

## Status
Aceito

## Data
2026-09-22

## Contexto

A Fase 4 terminou com 5 concursos de 2025 extraídos (`PF_25_ADM`, `STM_25`,
`IBAMA_25`, `CD_25_NS`, `TCU_25_TEFC`; 150 chunks, 1485 tópicos) em
`revisao_piloto/<edital>.json`. O Postgres próprio `scraper-cebraspe-db`
(ADR-026) já estava no ar, mas vazio. A Etapa 5 do `task.md` pede um star
schema, gravação idempotente por chave natural, modelagem cargo↔prova (N:1 nos
básicos, 1:1 em específica/discursiva) e uma fila `pendente` com os PDFs de
provas e gabaritos.

Achados nos dados reais que moldaram o desenho:

- O tipo e os cargos de cada caderno só existem no texto do link
  (`provas_texto_link.json`), em formatos variados: `CARGOS DE 1 A 14`,
  `CARGOS 2, 4, 5 E 7`, `CARGO 15`, ou nenhum cargo (TCU, cargo único). O
  básico aparece como `CONHECIMENTOS BÁSICOS` (CB) e como `CONHECIMENTOS
  GERAIS` (CG, no STM e na CD).
- O arquivo tem lixo legado de antes da correção do spider: 3 editais
  administrativos do PF (`EDITAL Nº 7 – RESULTADO...`) e padrões de resposta
  da discursiva (gabaritos) gravados em `Provas/`.
- Gabarito não tem texto de link salvo. Só dá para ligar gabarito a prova pelo
  nome (`Gab_Definitivo_<stem-da-prova>`) ou, no padrão de resposta, pelo
  cargo da discursiva. Arquivos com nome em hash (CD, TCU) ficam sem ligação.
- Todos os resultados estão com revisão humana `PENDENTE`.

## Decisão

**Schema** (`src/sql/schema_estatisticas.sql`, aplicado a cada carga com
`CREATE ... IF NOT EXISTS`):

- Dimensões: `dim_orgao`, `dim_ano`, `dim_materia`, `dim_topico` (única por
  matéria + chave) e `dim_cargo`. A chave natural é
  `comparacao_texto.normalizar()`, a mesma função do reparo e da validação.
  Assim `LÍNGUA PORTUGUESA` casa entre concursos e serve de ponte para a
  Etapa 7.
- Fatos: `concursos` (com `status_revisao`), `cargos_editais`,
  `taxonomia_itens` (grão: 1 tópico de 1 chunk; subtópicos em `JSONB`;
  `cargo_edital_id` NULL no básico, que é compartilhado), `provas` +
  `provas_cargos` (ponte que expressa tanto o N:1 quanto o 1:1, sem `nivel`,
  porque o nível é do cargo), e `fila_extracao_questoes`.
- Views: `vw_taxonomia_detalhe`, `vw_incidencia_topico_todas` e
  `vw_incidencia_topico`, esta última só com concursos `aprovado`.

**Gravação** (`src/stats_writer.py`):

- Dimensões por upsert em chave natural. Cargos por upsert em
  `(concurso, numero)`, porque a ponte `provas_cargos` aponta para eles.
- Taxonomia e provas de um concurso são **substituídas numa transação**. Um
  upsert linha a linha deixaria tópico órfão quando uma reextração muda a
  taxonomia. Dimensões de tópico/matéria que ficam sem fato são removidas no
  fim da carga.
- A fila usa upsert por `sha256` e **nunca altera `status`**, que pertence ao
  consumidor futuro.
- Dados pendentes entram marcados (`status_revisao = 'pendente'`). A
  aprovação da revisão humana é registrada no `status_revisao_humana` dos
  arquivos JSON de revisão e ingerida pelo `stats_writer` como
  `concursos.status_revisao = 'aprovado'` a cada carga idempotente (não por
  comando `UPDATE` manual no banco, ver ADR-028).
- O writer roda automaticamente como último passo de
  `scripts/atualizar_revisao.py` (ADR-019). É best-effort: banco fora do ar só
  gera aviso.
- Edital administrativo em `Provas/` é logado e fica fora da fila. Padrão de
  resposta vai para a fila como `gabarito`.

## Consequências

### Positivas
- A carga real é idempotente: duas execuções seguidas dão contagens
  idênticas, e um item da fila marcado `processando` continua assim.
- Resultado da carga: 5 concursos, 31 cargos, 1485 tópicos, 70 provas, 145
  PDFs na fila, 3 pulados. PF CB1 → cargos 1..14, STM CG1 → 2, 4, 5, 7.
- A estatística "oficial" só conta dado aprovado, e o piloto pendente
  continua inspecionável pela view `_todas`. (Desde o ADR-028 o piloto está
  aprovado, via JSON.)

### Negativas
- A chave normalizada não resolve sinônimos: `NOÇÕES DE DIREITO
  ADMINISTRATIVO` e `DIREITO ADMINISTRATIVO` são matérias diferentes. Uma
  tabela de sinônimos fica para quando a estatística exigir.
- 13 gabaritos ficam sem `prova_id` (nome em hash, ou "justificativas de
  alteração de gabarito").
- A substituição por concurso reescreve os IDs de `taxonomia_itens` a cada
  carga. Nada externo deve guardar esses IDs.

### Alternativas Descartadas
- **Upsert linha a linha nos fatos:** deixa órfão quando a taxonomia muda.
- **Uma linha por subtópico:** a estatística é por tópico; subtópico não
  justifica dimensão ainda.
- **Não gravar dado pendente:** a aprovação precisa chegar ao banco (via
  JSON, ADR-028), e a view filtrada já protege a estatística.
- **`nivel` em `provas`:** duplicaria atributo do cargo e divergiria em
  caderno compartilhado.
