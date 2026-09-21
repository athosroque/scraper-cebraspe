# ADR-008: Resolução de Href Relativo no Crawler de Concursos

## Status
Aceito

## Data
2026-09-19

## Contexto
Durante a auditoria pós-Etapa 3, o crawler retornava 0 concursos de 2025 no site real, mesmo após testes unitários bem-sucedidos em ambiente mock.

## Decisão
Em `get_contest_links`, aplicar `urljoin(page.url, href)` para resolver qualquer atributo `href` relativo contra a base da página antes de executar as comparações de prefixo de URL.

## Consequências
### Positivas
- No portal real do CEBRASPE, os 424 cards da listagem de encerrados utilizam caminhos relativos (ex: `/concursos/PF_25_ADM`). O método `get_attribute("href")` do Playwright retorna a string literal do HTML sem resolução do DOM. A comparação `href.startswith("https://...")` descartava 100% dos concursos silenciosamente.
- Após a correção com `urljoin`, 31 concursos de 2025 foram imediatamente identificados e validados para download.

### Alternativas Descartadas
- Nenhuma. Trata-se de correção de bug crítico de integração entre o DOM real e o crawler.
