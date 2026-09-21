# ADR-014: Trilha de Auditoria de Entrada/Saída do Parser+Extractor (.auditoria.json)

## Status
Aceito

## Data
2026-09-20

## Contexto
O log textual `logs/scraper_cebraspe.log` apenas contabilizava totais agregados (número de chunks processados e quantidade de falhas). Em casos de erro ou anomalia taxonômica, era impossível auditar se o corte da seção descartou trechos essenciais ou inspecionar o prompt exato submetido ao modelo de linguagem.

## Decisão
Gerar para cada edital processado em `revisao_piloto/`, além do arquivo de dados `<edital>.json`, um arquivo complementar `<edital>.auditoria.json`. Esse arquivo armazena:
- Metadados do corte (páginas, contagem de caracteres, offsets no PDF, flags de fechamento de seção).
- Detalhes de cada chunk: cargo, matéria, offsets, tamanho em caracteres, status e o **texto bruto exato enviado ao LLM**.
- Chave de indexação estável (`chunk_index`) para vincular os dois artefatos.

## Consequências
### Positivas
- Rastreabilidade ponta a ponta: viabiliza comparar entrada e saída lado a lado na interface de revisão.
- Facilita reprodução e análise de falhas não determinísticas de modelos de linguagem.

### Alternativas Descartadas
- **Inserir o texto bruto dos chunks nos logs do sistema:** Tornaria os logs ilegíveis e excessivamente extensos (39+ chunks de milhares de caracteres por edital).
- **Vincular auditoria e resultado apenas por string `(cargo, materia)`:** Frágil diante de cargos com matérias homônimas ou vazias.
