# ADR-004: Priorização de Cargo Migrada do Texto do Link para o Slug

## Status
Aceito

## Data
2026-09-19

## Contexto
O crawler precisa priorizar determinados órgãos/cargos de interesse imediato (como INSS, PF, PRF). Inicialmente, utilizava-se busca por expressão regular com `\b` no texto do link.

## Decisão
Efetuar a checagem de priorização particionando os segmentos do slug da URL (`slug.split("_")` e `slug.split("-")`) e comparando contra um conjunto (*set*) de palavras-chave, em vez de regex sobre texto.

## Consequências
### Positivas
- Elimina a dependência do texto dos cards HTML (que é sempre "MAIS INFORMAÇÕES").
- Resolve o problema de delimitação de palavras: a meta-sequência `\b` em expressões regulares não cria fronteira de palavra em caracteres de underscore (`_`), pois `\w` inclui underscore. O `split` explícito é 100% confiável.

### Alternativas Descartadas
- **Regex com `\b` direto no slug:** Não funcionou adequadamente por conta de slugs com underscores.
- **Regex no texto do link:** Inoperante pela natureza do HTML do portal.
