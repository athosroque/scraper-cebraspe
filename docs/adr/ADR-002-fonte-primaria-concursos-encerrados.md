# ADR-002: Fonte Primária de Crawling é `/concursos/encerrado`

## Status
Aceito

## Data
2026-09-19

## Contexto
O objetivo do projeto compreende a coleta estruturada não apenas de editais de abertura, mas também de cadernos de prova e gabaritos definitivos para alimentar a base de questões e estatísticas.

## Decisão
Definir a URL `/concursos/encerrado` do CEBRASPE como a fonte primária de navegação do crawler, em vez da raiz `/concursos/`.

## Consequências
### Positivas
- Na raiz `/concursos/`, apenas 80 links eram encontrados, muitos de concursos com inscrições abertas ou em andamento onde provas e gabaritos ainda não existem.
- Em `/concursos/encerrado`, mais de 420 certames históricos estão disponíveis com o ciclo completo de documentos (Edital, Provas e Gabaritos).

### Alternativas Descartadas
- **Crawlear apenas a raiz `/concursos/`:** Insuficiente para coletar provas e gabaritos realizados.
