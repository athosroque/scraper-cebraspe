# ADR-012: Chaves Dedicadas e Escopadas por Serviço no OpenRouter e Langfuse
 
## Status
Substituído (pelo desacoplamento do LiteLLM em 2026-09-21)

## Data
2026-09-19 (Atualizado em 2026-09-21)

## Contexto
Originalmente, era utilizada uma Virtual Key escopada no LiteLLM para isolar as chamadas contra a master key do gateway. Com a migração para a API direta do OpenRouter, cada serviço do repositório (extração de editais e bot do Telegram) necessita de isolamento de cotas, faturamento e rastreabilidade de telemetria no Langfuse.

## Decisão
Substituir o modelo de Virtual Key do LiteLLM por chaves de API independentes geradas diretamente no OpenRouter (`OPENROUTER_API_KEY` para extração taxonômica e `TELEGRAM_OPENROUTER_API_KEY` para o bot), associadas a projetos distintos no Langfuse (`LANGFUSE_*` e `TELEGRAM_LANGFUSE_*`).

## Consequências
### Positivas
- Total isolamento de saldo, taxa limite (rate limit) e custos entre a extração pesada de editais e as mensagens do bot.
- Dashboards do Langfuse limpos e categorizados por aplicação sem interferência mútua.
- Respeito estrito ao princípio do menor privilégio sem depender de proxy local do LiteLLM.

### Alternativas Descartadas
- **Compartilhar uma única chave do OpenRouter entre bot e extrator:** Causa concorrência de cotas e mistura traces e métricas no Langfuse.
- **Manter Virtual Keys via LiteLLM Gateway:** Rejeitado pela descontinuação do LiteLLM no projeto.
