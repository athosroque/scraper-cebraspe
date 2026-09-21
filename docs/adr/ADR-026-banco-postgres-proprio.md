# ADR-026: Banco PostgreSQL Próprio, Independente do study-rag-agent

## Status
Aceito (substitui o [ADR-003](ADR-003-tabelas-postgres-study-rag.md))

## Data
2026-09-21

## Contexto

O [ADR-003](ADR-003-tabelas-postgres-study-rag.md) decidiu gravar as tabelas de
estatísticas da Fase 5 na instância `study-rag-db` do `study-rag-agent`, com FK
opcional de cada tabela nova para `itens_estudo`. Na revisão do plano da
Etapa 5, antes de qualquer código de banco existir, apareceram quatro problemas:

1. **Os domínios são diferentes.** `study_rag` guarda o material de estudo
   pessoal (`itens_estudo` com embeddings, `revisoes`, `videos_processados`).
   Este projeto guarda dados públicos de concursos (edital, cargo, matéria,
   tópico, prova, gabarito). Os dois mudam em ritmos diferentes e por motivos
   diferentes.
2. **A direção da FK estava errada.** Um tópico de edital não pertence a um item
   de estudo. A relação natural é N:N, numa tabela de ligação criada quando o
   cruzamento existir. A FK prevista seria uma coluna sempre `NULL` no piloto.
3. **Uma FK entre projetos prende os dois.** O `study-rag-db` deve ser
   reconfigurado. Com FKs apontando para ele, cada mudança de schema em
   `itens_estudo` quebraria o scraper, ou o scraper congelaria o schema do outro
   projeto.
4. **A instância atual tem problemas de segurança conhecidos.** Ela usa
   `postgres/postgres`, publica a porta `5434` em `0.0.0.0` e tem a master key
   do LiteLLM versionada no compose (ver §8 do `CLAUDE.md`). O scraper
   herdaria esses problemas e ficaria fora do ar a cada manutenção do outro
   projeto.

## Decisão

- Novo serviço `scraper-cebraspe-db` (`postgres:16-alpine`) no
  `docker-compose.yml` deste projeto, com volume próprio
  (`scraper_cebraspe_pgdata`), porta publicada só em `127.0.0.1:5435` e
  conectado à rede `homelab_default`.
- Banco `cebraspe` e usuário `cebraspe`. A senha fica só em `.env` e não tem
  default no compose: com senha vazia, o container recusa subir.
- Nenhuma tabela deste projeto referencia `itens_estudo`. O star schema da
  Fase 5 carrega **chaves naturais normalizadas** (`materia_normalizada`, nome
  de tópico normalizado, `slug` do concurso), que já vêm do parser (ADR-020).
- O cruzamento com o `study-rag-agent` vira uma etapa futura e separada
  (Etapa 7 do `task.md`): uma tabela de mapeamento
  `topico_edital ↔ item_estudo` (por nome normalizado ou similaridade de
  embedding) consultada via `postgres_fdw` ou por uma camada analítica
  (schema `mart`/dbt) que lê os dois bancos.
- `pgvector` fica fora da imagem por ora. Nenhuma tabela da Fase 5 precisa
  de embedding. Se a Etapa 7 precisar, troca-se a imagem por
  `pgvector/pgvector:pg16`, que continua compatível com o volume.

## Consequências

### Positivas
- Ciclo de vida, credenciais e schema independentes. O `study-rag-db` pode ser
  reconfigurado ou recriado sem afetar este projeto, e vice-versa.
- Não herda as credenciais fracas nem a porta exposta do `study-rag-db`.
- O schema da Fase 5 é desenhado só para estatística de concursos, sem colunas
  mortas de FK.
- A rede compartilhada `homelab_default` deixa o `postgres_fdw` viável depois
  sem abrir porta nova.

### Negativas
- Mais um container Postgres no host (custo de memória baixo com
  `postgres:16-alpine` ocioso).
- Sem integridade referencial entre projetos. O vínculo com `itens_estudo` só
  existe quando a tabela de mapeamento da Etapa 7 for construída, e é validado
  por ela, não por constraint.
- Backup do volume novo precisa ser incluído na rotina do homelab.

### Alternativas Descartadas
- **Manter o ADR-003 (mesma instância, FK para `itens_estudo`):** motivos acima.
- **Outro database na mesma instância `study-rag-db`:** resolve o schema, mas
  mantém a dependência operacional (mesmas credenciais fracas, mesmo container,
  mesma janela de manutenção) sem ganho relevante sobre um container próprio.
  Também não permite JOIN direto, pois bancos distintos no Postgres exigem
  `postgres_fdw`/`dblink` de qualquer forma.
- **Schema separado dentro de `study_rag`:** permite JOIN direto, mas é o maior
  acoplamento de todos. Um `DROP`/restore do banco do outro projeto leva os
  dados deste junto.
