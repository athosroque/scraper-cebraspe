# ADR-003: Novas Tabelas na Mesma Instância Postgres do study-rag-agent

## Status
Substituído pelo [ADR-026](ADR-026-banco-postgres-proprio.md) em 2026-09-21

## Data
2026-09-19

## Contexto
A Fase 5 do projeto exige a persistência estruturada dos metadados de concursos, cargos, provas e taxonomias extraídas para cruzamentos analíticos e planos de estudo.

## Decisão
Criar as novas tabelas de estatísticas na mesma instância PostgreSQL + pgvector do projeto `study-rag-agent` (`study-rag-db`, porta 5434 ou rede `homelab_default:5432`), organizadas em Star Schema, com Foreign Key opcional referenciando a tabela `itens_estudo`.

## Consequências
### Positivas
- Reaproveita a infraestrutura já provisionada e monitorada no Homelab.
- Viabiliza integridade referencial real com as matérias e itens de estudo do sistema de RAG.
- Favorece consultas analíticas relacionais de agregação por matéria × tema × ano, mantendo flexibilidade com colunas `JSONB` quando necessário.

### Alternativas Descartadas
- **Subir uma nova instância de Postgres dedicada:** Desperdício de recursos de memória e CPU no host homelab.
- **Banco orientado a documentos (MongoDB):** Descartado pois agregações e estatísticas de incidência relacional são anti-pattern em document stores puros.
