# ADR-028: Restrição de Cargo Fora do Nome da Matéria e Registro da Aprovação da Fase 4

## Status
Aceito

## Data
2026-09-23

## Contexto

A Etapa 5 (ADR-027) gravou os 5 concursos de 2025 no Postgres próprio, com
chave natural da matéria vinda de `materia_normalizada`. Nos dados reais
isso gerava matérias duplicadas em `dim_materia` (106):

- No STM, a restrição de cargo vinha dentro do nome:
  `DIREITO PENAL MILITAR (APENAS PARA O CARGO 1: ... E PARA O CARGO 8: ...)`.
  Quatro matérias assim viravam chaves diferentes da matéria base.
- No IBAMA, o PDF tinha espaço duplo no cabeçalho (`LÍNGUA  PORTUGUESA`).

Além disso, a revisão humana da Fase 4 já tinha sido feita pelo dono, mas os
5 `<edital>.json` ainda diziam `PENDENTE`. Como o writer relê o
`status_revisao_humana` a cada carga, um `UPDATE` no banco seria revertido.

O `stats_writer` já tinha uma regex de número de cargo para o texto dos links
de caderno. O parser precisava da mesma coisa para a restrição.

## Decisão

1. **Uma só função de número de cargo.** `extrair_cargos_do_texto` foi para
   `src/comparacao_texto.py`, usada pelo parser e pelo writer. Ela lê todas as
   menções (`finditer`), não só a primeira: intervalo (`cargos de 1 a 14`,
   com "de" obrigatório), lista (`cargos 2, 4, 5 e 7`) e menções separadas
   por texto (`CARGO 1: ... E PARA O CARGO 8: ...`). Mantém a ordem e tira
   repetidos.
2. **Restrição sai do nome e vira dado.** `PADRAO_RESTRICAO_CARGO` casa
   `(APENAS|SOMENTE PARA O(S)/A(S) CARGO(S) ...)` com um nível de parêntese
   interno (`ANALISTA (TI)`). `ChunkTaxonomia.cargos_restritos` junta os
   cargos de todas as restrições do nome (`None` = matéria comum). A
   restrição só sai de `materia_normalizada` quando tem número de cargo. Sem
   número (`PARA OS CARGOS DE NÍVEL SUPERIOR`), fica no nome e o parser loga
   `[RESTRICAO_SEM_CARGO]`. Espaços repetidos são colapsados.
   `cargos_restritos` entrou em `CAMPOS_CLASSIFICACAO_CHUNK`.
3. **Banco.** `taxonomia_itens.cargos_restritos INTEGER[]` (com `ADD COLUMN
   IF NOT EXISTS` para o banco já criado), exposto em `vw_taxonomia_detalhe`.
   `dim_materia` passa a atualizar o nome no upsert (`EXCLUDED.nome`).
4. **Aprovação no JSON.** `status_revisao_humana` dos 5 editais virou
   `"APROVADO — revisão humana da Fase 4 concluída (registrada em
   2026-09-22)"` (texto da spec; o registro foi feito em 2026-09-23).
5. **Backfill sem LLM, em lote.** `backfill_classificacao_chunks.py` sem
   argumentos roda em todos os editais de `revisao_piloto/`. Ele resolve os
   PDFs de todos antes de gravar (PDF ausente ou ambíguo aborta o lote
   inteiro). A checagem de alinhamento compara matéria e cargo com espaços
   colapsados e exige que o texto atual do chunk seja prefixo do
   `texto_enviado_llm` salvo. É prefixo, e não igual, porque a assinatura
   do fim da seção passou a ser removida depois da extração (ADR-025).

## Consequências

### Positivas
- `dim_materia` caiu de 106 para 102: as 4 variantes do STM se fundiram na
  matéria base, com `cargos_restritos` `[3, 6]` (LÍNGUA INGLESA) e `[1, 8]`
  (as 3 de Direito). Nenhuma matéria com `APENAS PARA` ou espaço duplo, e
  nenhuma dimensão órfã (`_limpar_dimensoes_orfas`).
- Os 5 concursos estão `aprovado`, e `vw_incidencia_topico` passou a
  retornar dados. A aprovação sobrevive a qualquer recarga ou recriação do
  banco.
- A taxonomia extraída e o `texto_enviado_llm` não mudaram. Nenhuma chamada
  ao LLM.
- A função única não mudou a classificação de nenhum dos 100 textos reais de
  link de caderno (a única diferença de números, no Edital nº 5 da PF, é de
  um edital administrativo que já fica fora da fila).

### Negativas
- `EXCLUDED.nome` faz o nome exibido de uma matéria compartilhada ser o do
  último concurso carregado. É determinístico pela ordem dos arquivos, mas
  depende dela.
- `extrair_cargos_do_texto` ainda aceita número solto depois de uma lista
  (`cargo 15 2025` → `[15, 2025]`), como a versão anterior.
- Uma restrição com formato novo (ex.: `EXCETO PARA`) não é reconhecida e
  fica no nome, o que aparece como matéria duplicada em `dim_materia`.

## Alternativas Consideradas

- **Deixar a restrição no nome:** mantém a duplicação em `dim_materia` e
  esconde a informação de cargo num texto livre.
- **Tirar a restrição do nome mesmo sem número de cargo:** a matéria passaria
  a valer para todos os cargos sem aviso. Preferimos manter no nome e logar.
- **Aprovar com `UPDATE` no banco:** revertido na próxima carga do writer.
- **Regex própria de cargo no parser:** divergiria da do writer.
- **Checagem do backfill só por matéria/cargo:** dois chunks de mesmo nome
  (básico superior e médio) trocados passariam. O texto resolve.
