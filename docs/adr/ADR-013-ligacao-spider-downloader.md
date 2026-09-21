# ADR-013: Chamada Explícita do Downloader no Spider Antes de Marcar Idempotência

## Status
Aceito

## Data
2026-09-19

## Contexto
Durante auditoria ao vivo da execução do spider, constatou-se que o método `CebraspeSpider.run()` mapeava os links de PDF, exibia os contadores no log e gravava o slug como processado em `data/processed_concursos.json` sem jamais invocar a função `download_concurso_pdfs`.

## Decisão
1. Modificar `CebraspeSpider.run()` para acionar explicitamente `download_concurso_pdfs` imediatamente após o mapeamento dos links de cada concurso.
2. Só registrar o slug do certame no manifesto de idempotência (`mark_processed`) após a finalização bem-sucedida do download de todos os seus arquivos.
3. Preservar o texto do link das provas (`CB1`, `CB2`, `DISC`) em `<concurso_dir>/provas_texto_link.json` para consumo das etapas posteriores.

## Consequências
### Positivas
- Elimina o descompasso crítico entre o crawler (Etapa 2) e o downloader (Etapa 3), garantindo que os PDFs existam fisicamente no disco antes de considerar o concurso finalizado.
- Evita que execuções subsequentes pulem concursos cujos arquivos nunca foram baixados.

### Alternativas Descartadas
- Nenhuma. Correção direta de falha de orquestração no fluxo principal.
