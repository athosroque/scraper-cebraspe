# Decisões (ADRs)

Cada ADR (Architecture Decision Record) registra uma escolha do projeto: o contexto, a decisão, os trade-offs e as alternativas descartadas.

**Para que serve:** saber por que algo é como é antes de mudar. **Quando ler:** antes de reabrir uma escolha de stack, banco, parser ou site, leia a ADR do tema. Se a mudança valer, ela vira uma ADR nova ou uma seção "Atualização" na ADR existente.

!!! tip "Como criar uma ADR"

    1. Copie o formato de uma ADR recente e use o próximo número (`ADR-042-…`).
    2. Acrescente a linha na tabela do tema, abaixo.
    3. Ponha a ADR no `nav` do `mkdocs.yml`, no grupo do tema, com um título curto. Sem isso, o `--strict` falha.

O teste `tests/test_adr_catalogo.py` confere o passo 2 (e o `nav` dentro da aba Decisões), e o `--strict` confere o passo 3.

Status: **Aceito** está em vigor. **Substituído** é histórico: o texto da ADR diz o que vale no lugar.

## Coleta e download

Como o crawler acha os concursos e como o downloader baixa os PDFs sem repetir (Fases 2 e 3).

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-001](ADR-001-filtro-ano-slug-url.md) | 2026-09-19 | Filtro de ano por slug de URL, não por texto do link | Aceito |
| [ADR-002](ADR-002-fonte-primaria-concursos-encerrados.md) | 2026-09-19 | Fonte primária de crawling é `/concursos/encerrado` | Aceito |
| [ADR-004](ADR-004-priorizacao-cargo-slug.md) | 2026-09-19 | Priorização de cargo também migrada do texto do link para o slug | Aceito |
| [ADR-005](ADR-005-idempotencia-registro-json.md) | 2026-09-19 | Idempotência via registro JSON local, não pasta em `data/` | Aceito |
| [ADR-006](ADR-006-extracao-orgao-slug.md) | 2026-09-19 | Nome de órgão também vem do slug, não do texto do link | Aceito |
| [ADR-007](ADR-007-dedup-download-dupla-camada.md) | 2026-09-19 | Dedup de download em duas camadas (URL + hash de conteúdo) | Aceito |
| [ADR-008](ADR-008-resolucao-href-relativo.md) | 2026-09-19 | Resolução de href relativo no crawler de concursos | Aceito |
| [ADR-013](ADR-013-ligacao-spider-downloader.md) | 2026-09-19 | Chamada explícita do Downloader no Spider antes de marcar idempotência | Aceito |

## Extração do edital e revisão

Parser, chunking e extração da taxonomia pelo LLM, com auditoria, validação e revisão humana no Datasette (Fase 4).

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-009](ADR-009-recorte-objetos-avaliacao.md) | 2026-09-19 | Recorte exclusivo da seção "OBJETOS DE AVALIAÇÃO" no parser | Aceito |
| [ADR-010](ADR-010-chunking-cargo-materia.md) | 2026-09-19 | Chunking em dois níveis (cargo + matéria), não só matéria | Aceito |
| [ADR-011](ADR-011-extracao-llm-requests-direto.md) | 2026-09-19 | Extração LLM via requisições HTTP diretas, sem dependência de SDKs | Aceito |
| [ADR-012](ADR-012-virtual-key-litellm.md) | 2026-09-19 | Chaves dedicadas e escopadas por serviço no OpenRouter e Langfuse | Substituído |
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
| [ADR-028](ADR-028-cargos-restritos-e-aprovacao-fase4.md) | 2026-09-23 | Restrição de cargo fora do nome da matéria e registro da aprovação da Fase 4 | Aceito |

## Banco e árvore mestre

Onde os dados ficam, o star schema e a árvore de assuntos que organiza edital e questão (Fase 5, Etapas 5B).

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-003](ADR-003-tabelas-postgres-study-rag.md) | 2026-09-19 | Novas tabelas na mesma instância Postgres do study-rag-agent | Substituído (ADR-026) |
| [ADR-026](ADR-026-banco-postgres-proprio.md) | 2026-09-21 | Banco PostgreSQL próprio, independente do study-rag-agent | Aceito |
| [ADR-027](ADR-027-star-schema-estatisticas.md) | 2026-09-22 | Star schema de estatísticas, gravação idempotente e fila de provas | Aceito |
| [ADR-029](ADR-029-camada-canonica-sinonimos.md) | 2026-09-25 | Camada canônica de sinônimos (matéria → assunto → subassunto) com aprovação humana e reasoning padrão de 3000 tokens | Aceito (aprovado em 2026-09-27; semente da árvore mestre do ADR-030) |
| [ADR-030](ADR-030-arvore-mestre-e-site-de-questoes.md) | 2026-09-28 | Árvore mestre de assuntos semeada com a 5B e site público de questões como objetivo do produto | Aceito (5B.1 implementada; 5B.2–5F a seguir) |

## Questões e estatísticas

Extração das questões dos cadernos, classificação na árvore e cálculo da incidência (Etapas 5C a 5E, 8.M).

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-031](ADR-031-extracao-questoes-cadernos.md) | 2026-09-25 | Extração determinística de questões, gabaritos e discursivas dos cadernos de prova | Aceito |
| [ADR-032](ADR-032-classificacao-questoes-arvore.md) | 2026-09-29 | Classificação das questões na árvore mestre, confiança em 2 camadas e governança humana | Aceito |
| [ADR-038](ADR-038-suporte-multipla-escolha-retrocompativel.md) | 2026-10-09 | Suporte a Múltipla Escolha retrocompatível no pipeline, banco e site (Etapa 8.M); resposta sempre conferida pelo tipo da questão | Aceito |
| [ADR-039](ADR-039-incidencia-em-dois-niveis.md) | 2026-10-10 | Incidência agregada em dois níveis (prova → concurso): cada edital pesa 1 e o caderno básico compartilhado não se multiplica pelos cargos; cargos com a mesma prova contam uma vez | Aceito (implementado na 8.M.1) |

## Site público

Stack, contas, interface e o que entra ou fica fora do site de questões (Etapas 5F a 5H, 8.0).

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-033](ADR-033-site-publico-stack-e-deploy.md) | 2026-09-29 | Site público: FastAPI + Jinja/HTMX (migração futura via /api/v1), Google OAuth, schema `app`, deploy e direitos | Aceito |
| [ADR-034](ADR-034-fidelidade-ao-caderno-e-filtros.md) | 2026-10-06 | Fidelidade ao caderno (parágrafos, comando, figuras vetoriais, item × preâmbulo) e filtros multisseleção; GRANTs preservados na carga e chave canônica sem quebra de parágrafo | Aceito |
| [ADR-035](ADR-035-card-e-filtros-formato-gran.md) | 2026-10-06 | Card da questão e filtros no formato Gran em teal: ID curto, Responder, dropdowns no topo aplicados só no Filtrar, recontagem em `/questoes/facetas`, palavra-chave e "questões com" | Aceito |
| [ADR-037](ADR-037-escopo-do-site-no-inventario.md) | 2026-10-09 | Escopo do site no inventário: `inventario/exclusoes.json` (cancelado, sem prova, página vazia, curso de formação…), `aguardando_prova` e correção do classificador (caderno com gabarito, abertura do SEBRAE) | Aceito |

## Engenharia e documentação

Organização dos testes e deste site de documentação (Etapas 9 e afins).

| ADR | Data | Título | Status |
|---|---|---|---|
| [ADR-036](ADR-036-etapas-testes-e-ruff.md) | 2026-10-07 | Divisão e agrupamento de testes e ruff por etapas: markers semânticos, Makefile e pyproject.toml | Aceito |
| [ADR-040](ADR-040-site-documentacao-mkdocs.md) | 2026-10-13 | Site de documentação em MkDocs Material (executivo e técnico), `nav` explícito guardado pelo `--strict` e publicação por nginx atrás do Traefik e do Cloudflare Access | Aceito |
| [ADR-041](ADR-041-registro-e-paginas-geradas.md) | 2026-10-13 | Registro do pipeline em `src/registro/` (scripts, etapas, checagens e regras) e páginas técnicas geradas em `docs/tecnico/`, com teste guarda (atualização D3: registro é a fonte das regras, `CLAUDE.md` só com o núcleo) | Aceito |
