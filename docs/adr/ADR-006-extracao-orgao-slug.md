# ADR-006: Nome de Órgão Também Vem do Slug, Não do Texto do Link

## Status
Aceito

## Data
2026-09-19

## Contexto
O Downloader organiza os arquivos em diretórios do tipo `data/<ano>/CEBRASPE/<orgao_slug>/...`. Para isso, a função `get_contest_links` precisa informar o órgão correspondente a cada certame mapeado.

## Decisão
Criar a função `extract_orgao_from_slug` no módulo `src/spider.py`, extraindo o segmento do slug anterior ao token de ano `_YY` (ex: `TJ_CE_25_NOTARIOS` → `TJ_CE`), injetando a chave `orgao` no dicionário retornado.

## Consequências
### Positivas
- Permite nomear pastas e associar metadados sem introduzir requisições adicionais de rede para raspar o título interno (H1/breadcrumb) da página do concurso.
- Mantém coerência arquitetural com a estratégia de resolução de ano e priorização.

### Alternativas Descartadas
- **Navegar até a página interna de cada concurso para extrair o nome extenso do órgão:** Descartado pelo custo excessivo de rede/tempo na fase de listagem de concursos.
