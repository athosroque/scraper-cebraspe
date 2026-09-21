# ADR-011: Extração LLM via Requisições HTTP Diretas, sem Dependência de SDKs

## Status
Aceito (Atualizado em 2026-09-21 com descontinuação do LiteLLM)

## Data
2026-09-19

## Contexto
O pipeline de extração de taxonomia programática na Etapa 4 e o bot do Telegram precisam submeter prompts ao modelo `glm-5.3-flash` de forma confiável e performática.

## Decisão
Implementar chamadas HTTP REST diretas (`requests` em scripts batch e `httpx` assíncrono no bot) diretamente contra o endpoint oficial do OpenRouter (`https://openrouter.ai/api/v1/chat/completions`), sem adicionar `litellm`, `langchain-openai` ou SDKs proprietários.

## Consequências
### Positivas
- Mantém a stack do repositório enxuta, estável e completamente desacoplada.
- Elimina intermediários, problemas de proxy local e incompatibilidades de telemetria (ex: callbacks legados do LiteLLM vs Langfuse v3).
- Compatibilidade nativa com a especificação de chat da OpenAI.
- *Nota (2026-09-21, ver [ADR-023](ADR-023-migracao-langfuse-sdk-oficial.md)):* A inferência com o LLM continua em requisições REST diretas (`requests`/`httpx`). Apenas a camada de observabilidade/telemetria foi migrada para o SDK oficial do Langfuse (OTel), eliminando o endpoint de ingestão manual REST que entrará em sunset. A objeção original a SDK tratava dos callbacks intermediários do LiteLLM, já removidos.

### Alternativas Descartadas
- **`litellm` SDK/Gateway:** Utilizado inicialmente, mas descontinuado por adicionar camada de proxy desnecessária e causar conflitos de roteamento de chaves e métricas.
- **`langchain-openai`:** Dependência adicional pesada desnecessária para scripts focados.
- **SDK oficial `openai`:** Dispensável frente a chamadas diretas com `requests`/`httpx`.
