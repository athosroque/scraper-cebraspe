# Registros de Decisões de Arquitetura (ADRs)

Este diretório armazena os Registros de Decisões de Arquitetura (**Architecture Decision Records — ADRs**) do projeto **Scraper CEBRASPE**, documentando o contexto, decisões técnicas fundamentadas, trade-offs e alternativas descartadas ao longo das fases de desenvolvimento.

---

## Catálogo de Decisões

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-001](ADR-001-filtro-ano-slug-url.md) | 2026-09-19 | Filtro de ano por slug de URL, não por texto do link | Aceito |
| [ADR-002](ADR-002-fonte-primaria-concursos-encerrados.md) | 2026-09-19 | Fonte primária de crawling é `/concursos/encerrado` | Aceito |
| [ADR-003](ADR-003-tabelas-postgres-study-rag.md) | 2026-09-19 | Novas tabelas na mesma instância Postgres do study-rag-agent | Substituído (ADR-026) |
| [ADR-004](ADR-004-priorizacao-cargo-slug.md) | 2026-09-19 | Priorização de cargo também migrada do texto do link para o slug | Aceito |
| [ADR-005](ADR-005-idempotencia-registro-json.md) | 2026-09-19 | Idempotência via registro JSON local, não pasta em `data/` | Aceito |
| [ADR-006](ADR-006-extracao-orgao-slug.md) | 2026-09-19 | Nome de órgão também vem do slug, não do texto do link | Aceito |
| [ADR-007](ADR-007-dedup-download-dupla-camada.md) | 2026-09-19 | Dedup de download em duas camadas (URL + hash de conteúdo) | Aceito |
| [ADR-008](ADR-008-resolucao-href-relativo.md) | 2026-09-19 | Resolução de href relativo no crawler de concursos | Aceito |
| [ADR-009](ADR-009-recorte-objetos-avaliacao.md) | 2026-09-19 | Recorte exclusivo da seção "OBJETOS DE AVALIAÇÃO" no parser | Aceito |
| [ADR-010](ADR-010-chunking-cargo-materia.md) | 2026-09-19 | Chunking em dois níveis (cargo + matéria), não só matéria | Aceito |
| [ADR-011](ADR-011-extracao-llm-requests-direto.md) | 2026-09-19 | Extração LLM via requisições HTTP diretas, sem dependência de SDKs | Aceito |
| [ADR-012](ADR-012-virtual-key-litellm.md) | 2026-09-19 | Chaves dedicadas e escopadas por serviço no OpenRouter e Langfuse | Substituído |
| [ADR-013](ADR-013-ligacao-spider-downloader.md) | 2026-09-19 | Chamada explícita do Downloader no Spider antes de marcar idempotência | Aceito |
| [ADR-014](ADR-014-trilha-auditoria-parser-extractor.md) | 2026-09-20 | Trilha de auditoria de entrada/saída do parser+extractor (`.auditoria.json`) | Aceito |
| [ADR-015](ADR-015-revisao-datasette-traefik.md) | 2026-09-20 | Revisão navegável via Datasette, Traefik e Cloudflare Tunnel | Aceito |
| [ADR-016](ADR-016-retry-maiores-tokens-llm.md) | 2026-09-20 | Retry com backoff e expansão de max_tokens/timeout para mitigar falhas LLM | Aceito |
| [ADR-017](ADR-017-validacao-heuristica-de-para-taxonomia.md) | 2026-09-21 | Validação heurística "de-para" entre texto-fonte e taxonomia extraída | Aceito |
| [ADR-018](ADR-018-relatorio-html-e-extensao-schema-revisao.md) | 2026-09-21 | Relatório HTML de página única e extensão do schema de revisão (`alertas_validacao`) | Aceito |
| [ADR-019](ADR-019-pipeline-automatico-artefatos-revisao.md) | 2026-09-21 | Pipeline automático dos artefatos de revisão a cada extração | Aceito |
| [ADR-020](ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md) | 2026-09-21 | Classificação de chunk por nível, tipo de conhecimento e concurso | Aceito |
| [ADR-021](ADR-021-reparo-local-nome-topico-numerico.md) | 2026-09-21 | Reparo local determinístico para nome de tópico numérico | Aceito |
| [ADR-022](ADR-022-classificacao-erros-chamada-openrouter.md) | 2026-09-21 | Classificação de erros/exceções na chamada ao OpenRouter | Aceito |
| [ADR-023](ADR-023-migracao-langfuse-sdk-oficial.md) | 2026-09-21 | Migração da telemetria Langfuse de REST manual para SDK oficial (OTel) | Aceito |
| [ADR-024](ADR-024-coleta-camara-deputados-refinamentos-parser.md) | 2026-09-21 | Coleta da Câmara dos Deputados 2025 e refinamentos do parser de editais | Aceito |
| [ADR-025](ADR-025-reconciliacao-deterministica-severidade-alertas.md) | 2026-09-21 | Reconciliação determinística de item ausente e severidade de alertas | Aceito |
| [ADR-026](ADR-026-banco-postgres-proprio.md) | 2026-09-21 | Banco PostgreSQL próprio, independente do study-rag-agent | Aceito |
