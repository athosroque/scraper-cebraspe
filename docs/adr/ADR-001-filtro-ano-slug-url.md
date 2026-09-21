# ADR-001: Filtro de Ano por Slug de URL, Não por Texto do Link

## Status
Aceito

## Data
2026-09-19

## Contexto
O crawler (`spider.py`) precisa filtrar e processar apenas os concursos de determinado ano de interesse (ex: 2025). A implementação inicial utilizava uma expressão regular `re.search(r'2025', text)` inspecionando o texto visível das tags de link dos cards.

## Decisão
Extrair o ano de interesse diretamente do sufixo `_YY` presente no slug da URL do concurso (exemplo: `_25` para indicar o ano de 2025), ignorando o texto do link.

## Consequências
### Positivas
- Testes ao vivo no portal do CEBRASPE confirmaram que o texto dos cards HTML é invariavelmente "MAIS INFORMAÇÕES", o que fazia a regex anterior falhar silenciosamente (retornando lista vazia).
- A verificação por slug é determinística e imune a variações visuais no texto dos botões do portal.

### Alternativas Descartadas
- **Regex no texto visível:** Comprovadamente ineficaz na listagem real do CEBRASPE, causando falsos-negativos totais.
