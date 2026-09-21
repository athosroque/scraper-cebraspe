# ADR-023: Migração da Telemetria Langfuse de REST Manual para SDK Oficial (OTel)

## Status
Aceito

## Data
2026-09-21

## Contexto

A telemetria de observabilidade no Langfuse era realizada manualmente via requisições HTTP REST diretas ao endpoint `/api/public/ingestion` (HTTP Basic Auth, payload com batch de `trace-create` e `generation-create` montado manualmente com base64, uuid e datetime), em dois pontos:
1. `src/taxonomia_extractor.py::_registrar_langfuse_rest` (sync, via `requests`)
2. `src/telegram_bot.py::_registrar_langfuse_async` (async, via `httpx`)

Em 2026-09-21, a validação das chamadas revelou um aviso explícito da API do Langfuse:
> A partir de **2026-11-16**, o endpoint legado `/api/public/ingestion` aceitará exclusivamente eventos de score, recusando eventos de `trace` e `generation`.

Além disso, a implementação anterior de `requests.post` sem tratamento e sem validação estrita de status code silenciava erros de autenticação (como HTTP 401 decorrente de credenciais desatualizadas).

A objeção histórica a SDKs registrada no [ADR-011](ADR-011-extracao-llm-requests-direto.md) referia-se especificamente aos callbacks intermediários e proxies do LiteLLM (que causavam conflitos com o Langfuse v3). Com o LiteLLM removido da stack, essa restrição não se aplica ao SDK oficial de observabilidade do Langfuse.

O pacote `langfuse>=3,<4` já se encontrava listado em `requirements.txt` e instalado no ambiente virtual junto com as dependências `opentelemetry-*`, porém não vinha sendo importado.

## Decisão

Migrar a camada de telemetria de ambos os componentes (`taxonomia_extractor.py` e `telegram_bot.py`) para o SDK oficial `Langfuse` (v3, baseado em OpenTelemetry):

1. **Cliente Preguiçoso por Processo**:
   Implementação de `_langfuse_client()` com `@lru_cache(maxsize=1)`. Se as credenciais `LANGFUSE_PUBLIC_KEY` e `LANGFUSE_SECRET_KEY` (ou correspondentes `TELEGRAM_LANGFUSE_*`) não estiverem preenchidas, retorna `None`. Isso preserva o comportamento de telemetria opcional e garante que testes unitários continuem executando sem tráfego de rede ou mocks externos pesados.

2. **Abertura Antecipada da Generation (`_abrir_generation`)**:
   A observation (`as_type="generation"`) é iniciada via `client.start_observation(...)` imediatamente antes do disparo da requisição HTTP de inferência ao OpenRouter. Isso garante medição fidedigna da latência real de rede e inferência pelo próprio SDK, eliminando a estimativa retroativa manual a partir de `time.perf_counter()`.

3. **Helper de Fechamento (`_registrar_langfuse`)**:
   Substitui as funções manuais legadas (`_registrar_langfuse_rest` e `_registrar_langfuse_async`). Executa:
   - `gen.update(...)` com `output`, `usage_details` (input, output, total), `level` (`DEFAULT` ou `ERROR`) e `status_message`.
   - `gen.update_trace(...)` com o nome do trace (`taxonomia_extractor` ou `telegram_chat`), `metadata` (preservando `tipo_erro` do ADR-022 e `reparo_nome_numerico` do ADR-021) e `user_id` (no bot).
   - `gen.end()`.
   - Tratamento de exceções com captura ampla e log em nível `warning`, assegurando que problemas na telemetria jamais interrompam o pipeline de extração ou o atendimento do bot.

4. **Operação Não Bloqueante e Flush via atexit**:
   O SDK do Langfuse v3 opera com exportação em thread em segundo plano e registra nativamente `atexit.register(self.shutdown)`. Desta forma, o envio em lote é completado automaticamente no encerramento normal dos scripts batch, sem necessidade de chamadas manuais dispersas a `flush()`, e opera de maneira transparente em handlers síncronos e assíncronos.

## Alternativas Descartadas

- **Permanecer na API REST v3 até o prazo limite (2026-11-16):** Descartado pois manteria débito técnico crítico com quebra programada em produção.
- **Implementar OTLP manual via requests/httpx:** Descartado pois reinventaria mecanismos complexos de buffer, retry, background export e compatibilidade OTel já maduros e validados dentro do SDK oficial.

## Consequências

### Positivas
- Resolução antecipada e definitiva do sunset do endpoint `/api/public/ingestion`.
- Medição exata da latência da inferência calculada diretamente pela observação.
- Manutenção integral dos contratos semânticos de rastreabilidade (`tipo_erro`, `reparo_nome_numerico`, `user_id`).
- Remoção de código artesanal de montagem de lote, codificação base64 e cabeçalhos manuais.
- Zero dependências adicionadas (o pacote já constava no ambiente).

### Cuidados
- Processos que encerrem via terminação abrupta (`SIGKILL`, `os._exit`) podem não descarregar os últimos eventos bufferizados caso o hook de `atexit` não seja invocado.
