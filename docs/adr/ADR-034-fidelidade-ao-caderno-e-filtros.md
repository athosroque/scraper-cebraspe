# ADR-034: Fidelidade ao Caderno e Filtros Multisseleção (Etapa 5G)

## Status
Aceito (Etapa 5G concluída e validada em 2026-10-06)

## Data
2026-10-06

## Contexto

Com o site funcionando (5F.1–5F.8, ADR-033), o dono comparou as questões no
site com os PDFs e achou inconsistências. A investigação de 2026-10-05, com
números medidos no banco e nos JSONs de `questoes/`, encontrou cinco
problemas:

1. **Parágrafos perdidos.** `juntar_linhas` (`src/prova_parser.py`) juntava
   todas as linhas de prosa com espaço: só 2 dos 123 textos-base tinham
   quebra. 79 questões citam "primeiro/segundo… parágrafo" ou "linha N" e
   ficavam difíceis de conferir.
2. **Comando do grupo invisível.** "Julgue os itens…, considerando que…"
   ficava gravado em `questoes.secao`, mas o card não o mostrava. 714 itens
   têm dados de contexto no comando. Em `094_PF_CB2_01`, itens 24–26, o
   dado da questão ("60 pessoas, 17…, 53…") está **só** no comando.
3. **Figuras vetoriais perdidas.** O parser só recortava imagem raster. As
   tabelas desenhadas de `072_STM_005`, `072_STM_010` e `094_PF_005` sumiam,
   e o texto das células ficava solto e ilegível no texto-base.
4. **Assunto no rodapé.** O caminho matéria › assunto › subassunto ficava no
   fim do card.
5. **Filtros de valor único.** Não havia como marcar 2 anos + 2 cargos + 3
   assuntos de uma vez, como faz o Gran Questões.

Durante a implementação apareceu um sexto problema: em `072_STM_005_01`, o
item 64 absorveu o preâmbulo e as duas tabelas do grupo 65–68, sem gerar
nenhum alerta.

Restrições:
- A chave da 5D (`<concurso>|<caderno>|<numero>`) e o **hash do enunciado**
  (ADR-032) não podem mudar sem motivo: um hash diferente tira a questão da
  classificação aprovada.
- A extração continua determinística e sem LLM (ADR-031).
- O contrato `/api/v1` é a base da migração futura do frontend (ADR-033).

## Decisão

### 1. Parágrafo pelo recuo da 1ª linha, só no texto-base

`juntar_linhas(..., paragrafos=True)` abre parágrafo (`\n\n`) quando duas
condições valem ao mesmo tempo:
- a linha tem recuo de 8 a 45 pt sobre a margem da coluna (o recuo real no
  CEBRASPE é de cerca de 28 pt);
- a linha anterior fecha frase.

A margem é a **moda** do x0 das linhas da coluna (página × lado), a mesma
régua de cluster/moda da 5C.1. A 1ª linha de cada parágrafo é minoria e por
isso não desloca a moda. O x0 vem do primeiro span com texto
(`Linha.x0_texto`), porque o PDF põe spans vazios na margem. Uma moda
contada uma vez só não serve de régua, então texto de 1–2 linhas sai sem
parágrafo.

O **enunciado não usa** essa regra, para manter o hash da 5D. O site
renderiza o texto-base com `whitespace-pre-wrap`.

### 2. Comando e caminho no topo do card

O card mostra `secao` acima do enunciado na lista, na página canônica, na
revisão e na prova do simulado. Na lista, um comando repetido no mesmo
caderno fica recolhido ("Mesmo comando da questão anterior"), como já
acontecia com o texto-base. Os selos matéria › assunto › subassunto passam
para o cabeçalho. `ItemSimulado` ganha `secao`, ainda sem gabarito.

### 3. Figuras vetoriais recortadas como PNG

Os traços visíveis próximos (`page.get_drawings()`) são unidos numa região e
recortados com o mesmo DPI e o mesmo vínculo de dono das figuras raster
(`origem: "vetorial"` no JSON). Ficam de fora:
- cabeçalho e rodapé;
- o separador de colunas;
- os separadores duplos entre grupos;
- molduras sem traço interno;
- fundos brancos;
- regiões sobre figura raster.

O texto das células da tabela recortada **sai do texto-base**, porque
repetia a tabela de forma ilegível. Na validação em memória dos 42 cadernos
objetivos saíram 12 tabelas novas em 7 cadernos, sem nenhum falso positivo.

### 4. Filtros multisseleção (OU dentro do filtro, E entre filtros)

`FiltroQuestoes` aceita listas em `ano`, `orgao`, `concurso`, `cargo`,
`nivel`, `tipo_conhecimento` e `no_id`, e continua aceitando valor único ou
vazio (parâmetro vazio não gera 422). O repositório filtra com
`= ANY(%s)` parametrizado.

- **Cargo** passa a ser identificado por `CONCURSO:NUMERO`, porque o número
  do cargo se repete entre concursos. O link antigo (`concurso` +
  `cargo_numero`) continua funcionando.
- **`no_id`** aceita nós de qualquer nível: casa com `no_id`, `assunto_id` ou
  `materia_id`.
- **Facetas** saem numa query só (CTE da view + `FILTER` por faceta). A
  contagem de cada valor considera os outros filtros, e um valor marcado
  aparece mesmo com contagem zero. `/api/v1/facetas` aceita os mesmos
  filtros.
- **UI:** painel lateral com busca, checkbox e contagem (Alpine lendo JSON,
  contagens atualizadas por `hx-swap-oob`), chips removíveis, "Limpar tudo",
  URL compartilhável e painel recolhível no celular. `site/openapi.json` foi
  atualizado.

### 5. Item termina antes do texto-base do grupo seguinte

As células da tabela do grupo 65–68 ficam a cerca de 17 pt da margem, dentro
do recuo de continuação de item (12–24 pt, ADR-031). Por isso a continuação
do item 64 avançava sobre elas.

Agora, quando há comando novo depois do item, o item termina na 1ª linha
fora do recuo depois de um fim de frase (`_ruptura_do_item`). A exceção é o
item que anuncia material ("a seguir" ou terminado em ":"). Um caso residual, com
comando anafórico sem texto-base próprio e item de várias frases, gera o
alerta `possivel_preambulo_no_item`, que está em `ALERTAS_ITEM_INUTILIZAVEL`
e tira a questão do site até a revisão. Fica bloqueado em vez de aparecer
errado.

### 6. Correções da validação (reextração completa, 2026-10-06)

A validação do "pronto quando" reextraiu os 70 cadernos e encontrou três
falhas silenciosas fora do parser:

- **`vw_questoes.figuras` trazia só as figuras do item.** As tabelas ficam no
  texto-base, então não apareciam, embora `tem_figuras` já considerasse as
  duas. Agora a coluna é `COALESCE(tb.figuras, '[]') || q.figuras`, com as
  figuras do texto-base primeiro.
- **A carga apagava os GRANTs do site.** `schema_estatisticas.sql` recria as
  views com `DROP VIEW ... CASCADE`, e o DROP leva junto os GRANTs que
  `site/sql/app_schema.sql` deu a `site_leitura` e `site_app`: depois de
  cada reextração, a lista dava 500. Agora `stats_writer.criar_schema` lê os
  GRANTs do schema corrente (`aclexplode` sobre `pg_class` e `pg_proc`)
  antes do SQL e os reaplica depois. Um objeto que deixou de existir loga
  `[GRANT_PERDIDO]` em vez de abortar a carga.
- **A chave canônica era sensível ao layout.** O mesmo texto em
  `072_STM_CG1_01` e `CG2_01` separa a linha da fonte num caderno e não no
  outro. Com `md5(tb.texto)`, as duplicatas se separaram e LP foi de 139
  para 146 questões distintas. A chave canônica agora usa
  `md5(regexp_replace(tb.texto, '\s+', ' ', 'g'))`.

O único enunciado alterado (STM 64, pela regra do item 5) teve o hash
atualizado em `canonico/classificacao_questoes.json` e continua no mesmo nó
aprovado. Como o sentido da questão não mudou, não foi preciso reclassificar
com LLM.

## Resultado medido

| Critério | Antes | Depois |
|---|---|---|
| Textos-base com parágrafos | 2 de 123 | 22 de 124 |
| Questões que citam parágrafo/linha com parágrafos | — | 88 de 88; cada texto cobre o maior ordinal citado |
| `072_STM_CG4_01`, texto CG4A1 | 1 bloco | 7 parágrafos, igual ao PDF |
| Figuras em STM_005 / STM_010 / PF_005 | 0 / 0 / 1 | 3 / 2 / 4 |
| Chaves da 5D, gabarito, `secao`, `utilizavel` | — | inalterados nas 2.800 |
| Grupos canônicos (`questao_canonica_id`) | 2.676 | 2.676 |
| Filtro 2024+2025 × 2 cargos × 3 assuntos | impossível | 44, igual ao SQL |
| Testes | 760 (+1 xfail) | 763 (+1 xfail), ruff verde |

## Alternativas descartadas

- **Parágrafo por linha em branco ou espaçamento vertical:** o CEBRASPE não
  deixa espaço entre parágrafos; o único sinal é o recuo.
- **Parágrafos também no enunciado:** mudaria o hash da 5D em massa sem
  ganho; enunciado de item é uma frase.
- **OCR ou LLM para reconstruir tabelas como HTML:** não determinístico e
  caro. O PNG é fiel ao caderno, e a tabela como dado estruturado pode vir
  depois, se fizer falta.
- **Rasterizar a página inteira quando houver desenho:** perderia o vínculo
  da figura com o grupo de itens.
- **`ALTER DEFAULT PRIVILEGES ... ON TABLES TO site_leitura` em vez de
  reaplicar os GRANTs:** daria à role de leitura todas as tabelas futuras do
  `public`, não só as views escolhidas em `app_schema.sql`.
- **Chamar `site/scripts/aplicar_schema_app.py` no fim da carga:** acoplaria
  o scraper ao site e exigiria as senhas das roles no pipeline.
- **Desduplicar por similaridade de texto:** a regra é igualdade de
  conteúdo; similaridade tem falsos positivos medidos (ADR-029).

## Consequências

- Toda mudança futura em `juntar_linhas` ou no corte do texto-base precisa
  conferir duas coisas antes e depois: o hash do enunciado (chave da 5D) e
  o total de `questao_canonica_id`.
- Reextrair não exige mais reaplicar as roles do site. Isso só é preciso
  quando muda `app_schema.sql` ou uma senha.
- Uma questão com `possivel_preambulo_no_item` fica fora do site até ser
  revisada.
- Os parâmetros de lista entram no contrato `/api/v1`, e o frontend futuro
  (ADR-033) os herda.
- O deploy público (5F.12) passou a ser **opcional** por decisão do dono:
  o site ainda vai mudar antes de ir ao ar.

## Referências

- `task.md`, Etapa 5G (achados e validação)
- ADR-031 (extração dos cadernos, recuo 12–24 pt), ADR-032 (chave e hash da
  5D, chave canônica), ADR-033 (site, roles, contrato `/api/v1`)
- `LESSONS.md`: tags `postgres, grants, views` e `paragrafos,
  deduplicacao`
- Commits: `ecb5659` (5G.1), `2f7e432` (5G.2), `d2564b2` e `653e78e`
  (5G.3), `227809d` (5G.4), `fa8635f` (5G.5), `a9d3cac` (validação)
