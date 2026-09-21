# ADR-016: Retry com Backoff e Expansão de max_tokens/timeout para Mitigar Falhas LLM

## Status
Aceito

## Data
2026-09-20

## Contexto
Durante o processamento piloto de editais com 39 chunks, observaram-se falhas intermitentes de extração (cerca de 5 falhas por execução). Experimentos comprovaram que as falhas eram não determinísticas e causadas por estouro de limite de tokens (decorrente dos tokens de pensamento/reasoning do modelo `glm-5.3-flash` somados ao JSON extenso de resposta).

## Decisão
1. Implementar mecanismo de retry com backoff exponencial (3 tentativas, pausas de 5s e 15s) na função `extrair_taxonomia_chunk` (`src/taxonomia_extractor.py`).
2. Ampliar os parâmetros padrão de produção para `MAX_TOKENS = 24576` (anteriormente 8192) e `REQUEST_TIMEOUT = 240s` (anteriormente 120s).
3. Adicionar filtro `_limpar_ruido_edital` em `src/edital_parser.py` para extirpar notas avulsas de retificação embutidas no meio das disciplinas.

## Consequências
### Positivas
- Em bateria de testes controlada com os chunks mais problemáticos (incluindo disciplinas com mais de 6.900 caracteres), a taxa de sucesso subiu de 2/5 (40%) para 5/5 (100%).
- Elimina erros de `json.JSONDecodeError: Unterminated string` provocados por truncamento prematuro de resposta JSON.

### Alternativas Descartadas
- **Desabilitar reasoning do modelo via `thinking: disabled`:** Testes empíricos demonstraram que o backend ignorava o parâmetro ou mantinha taxa de falha elevada.
- **Trocar de modelo para um menor sem reasoning:** Descartado para manter a alta capacidade semântica de extração do `glm-5.3-flash`.
