# ADR-020: Classificação de Chunk por Nível, Tipo de Conhecimento e Concurso

## Status
Aceito

## Data
2026-09-21

## Contexto

O objetivo final do projeto é filtrar questões por órgão/ano/concurso,
**nível** (médio/superior), **tipo de conhecimento** (básico/específico),
cargo, matéria e tópico do edital. A taxonomia extraída na Etapa 4 não
carregava nenhum desses eixos além de cargo/matéria:

- O edital piloto (`PF_25_ADM`) tem 4 blocos em "OBJETOS DE AVALIAÇÃO":
  `CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR`, `... BÁSICOS
  PARA O CARGO DE NÍVEL MÉDIO`, `... ESPECÍFICOS PARA OS CARGOS DE NÍVEL
  SUPERIOR` e `... ESPECÍFICOS PARA O CARGO DE NÍVEL MÉDIO`. O parser
  (ADR-010) ignorava esses cabeçalhos.
- Resultado: os chunks 0 (LÍNGUA PORTUGUESA, básico superior) e 6 (LÍNGUA
  PORTUGUESA, básico médio) saíam **idênticos** (`cargo=None`, mesmo nome
  de matéria), com conteúdo programático diferente. O mesmo vale para
  RACIOCÍNIO LÓGICO, ÉTICA e INFORMÁTICA. "Básico × específico" só era
  inferível pela convenção frágil `cargo=None`.
- O próprio cabeçalho do bloco seguinte grudava na cauda do chunk anterior
  (ex: chunk 32 terminava em `CONHECIMENTOS ESPECÍFICOS PARA O CARGO DE
  NÍVEL MÉDIO`, já notado no ADR-016 como ruído sem generalização).
- O `<edital>.json` só tinha o nome do arquivo PDF, não o concurso. O path
  em disco (`data/<ano>/CEBRASPE/<orgao>/`) é por **órgão**, não por
  concurso — dois concursos do mesmo órgão no mesmo ano dividem a pasta.

## Decisão

1. **Cabeçalho de bloco como terceiro tipo de marcador** no chunking
   (`PADRAO_BLOCO` em `src/edital_parser.py`). Ele não gera chunk: define
   `tipo_conhecimento` (`basico`/`especifico`/`complementar`) e `nivel`
   (`medio`/`superior`) de todo chunk até o próximo bloco, zera o cargo
   corrente e serve de fronteira. Bloco sem nível único ("PARA TODOS OS
   CARGOS", "SUPERIOR E MÉDIO") fica com `nivel=None`, com log de aviso e
   alerta `chunk_sem_classificacao` em `validar_taxonomia.py`. Nunca é
   descartado em silêncio.
2. **Campos novos por chunk** (`CAMPOS_CLASSIFICACAO_CHUNK`):
   `tipo_conhecimento`, `nivel`, `cargo_numero`, `materia_normalizada`
   (sem "(SOMENTE PARA A PROVA DISCURSIVA)") e `apenas_discursiva`.
   Propagados para `.json`, `.auditoria.json`, banco de revisão e
   relatório HTML.
3. **Nível do cargo** herdado do bloco de específicos onde `CARGO N:`
   aparece (`mapear_cargos`): no piloto, cargos 1–14 são superior e o 15 é
   médio. Isso liga os blocos básicos aos cadernos CB1/CB2 na Fase 5.
4. **Concurso de origem** (`slug`, `orgao`, `ano`) resolvido pelo manifesto
   do downloader (`resolver_concurso_do_pdf`): a URL de origem
   (`/concursos/PF_25_ADM/arquivos/...`) é o único lugar onde o slug
   existe. O casamento é pelo nome do arquivo, porque o `path` gravado no
   manifesto pode apontar para outra cópia do repo (achado: worktree
   antiga). Se o nome for ambíguo entre concursos, fica `None` com aviso.
5. **Backfill sem LLM** (`scripts/backfill_classificacao_chunks.py`): todos
   os campos novos vêm do parser e do manifesto, nunca do LLM. Extrações já
   feitas são completadas re-rodando o chunking e casando por
   `chunk_index`, com abort se contagem ou `(cargo, materia)` divergirem.
   `texto_enviado_llm` não é reescrito (é o registro do que o LLM recebeu).

## Consequências

- Piloto `PF_25_ADM` completado por backfill, sem custo de OpenRouter:
  39/39 chunks classificados (6 básico superior, 5 básico médio,
  22 específico superior, 6 específico médio), 0 alertas de classificação
  e os mesmos 2 alertas genuínos de antes.
- No banco de revisão, `taxonomia_topicos` ganhou `concurso_slug`/`orgao`/
  `ano` e os campos de classificação, desnormalizados de propósito para
  facet no Datasette sem join. Há também a tabela nova `cargos`.
- Os chunks re-rodados perdem ruído em relação ao texto que foi pro LLM no
  piloto (cabeçalho de bloco na cauda e notas de retificação), sem mudar
  conteúdo programático. Verificado por diff chunk a chunk.
- Fase 5: o fato de conteúdo programático usa a chave
  `(concurso, tipo_conhecimento, nivel, cargo nullable, materia)`, e
  `dim_materia` usa `materia_normalizada`, para "Língua Portuguesa" ser
  comparável entre níveis e concursos.

## Alternativas descartadas

- **Distinguir pelo `chunk_index`/posição**: não é filtro, só funciona
  dentro de um edital e quebra em qualquer edital com ordem diferente.
- **Pedir o nível ao LLM**: o dado está em um cabeçalho determinístico. LLM
  adiciona custo e não-determinismo sem ganho.
- **Reorganizar `data/` por concurso** (`<orgao>/<slug>/`) em vez de
  resolver pelo manifesto: mais correto a longo prazo, mas muda o layout de
  disco da Fase 3 e o manifesto já tem a informação. Fica como follow-up
  se aparecer colisão real de nome de arquivo entre concursos do mesmo
  órgão.
