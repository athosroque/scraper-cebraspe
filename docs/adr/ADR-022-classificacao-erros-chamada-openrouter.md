# ADR-022: Classificação de Erros/Exceções na Chamada ao OpenRouter

## Status
Aceito

## Data
2026-09-21

## Contexto

O [ADR-021](ADR-021-reparo-local-nome-topico-numerico.md) introduziu um
status persistido específico (`STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO`)
para uma falha *semântica* identificada, distinguindo-a de um "falha"
genérico de rede/timeout/parse. Mas o lado técnico continuava não
diferenciado: qualquer `requests.RequestException` (timeout, conexão
recusada, HTTP 4xx/5xx), qualquer resposta sem `content` (`finish_reason`
truncado) e qualquer erro de parse da resposta (`json.JSONDecodeError`,
`pydantic.ValidationError`) colapsavam todos no mesmo `motivo_falha = None`
→ `status = "falha"`.

Isso esconde do dashboard do Langfuse e do `<edital>.auditoria.json` *por
que* um chunk falhou — timeout e rate-limit (HTTP 429) são tipicamente
transitórios (retry tende a resolver sozinho), enquanto conteúdo vazio por
`max_tokens` insuficiente ou uma resposta que não bate com `TaxonomiaEdital`
tendem a se repetir com os mesmos parâmetros (retry sozinho não ajuda, é
sinal de ajuste de configuração ou de instabilidade do modelo). Sem essa
distinção, não dá pra responder "quantas falhas foram rate-limit hoje?" nem
"esse chunk falhou por timeout ou por schema?" sem abrir o log linha a
linha.

Pedido do dono do projeto: "precisamos rastrear os diferentes tipos de
erros ou exceções dos scripts de cada chamada ou etapa para o
openrouter/langfuse" — a mesma exigência de rastreabilidade do ADR-021,
agora estendida para todo o espectro de falha técnica, não só o caso
semântico.

## Decisão

Cada etapa de `_chamar_llm_uma_vez` (`src/taxonomia_extractor.py`) passa a
devolver um status técnico próprio em vez do genérico `None`, seguindo o
mesmo padrão de status persistido do ADR-021 (nunca a string `"falha"`
solta — sempre um valor específico, exceto o fallback já documentado em
`extrair_taxonomia_chunk` para uma cadeia de tentativas vazia):

```python
STATUS_FALHA_TIMEOUT = "falha_timeout"                    # requests.exceptions.Timeout
STATUS_FALHA_CONEXAO = "falha_conexao"                    # requests.exceptions.ConnectionError
STATUS_FALHA_RATE_LIMIT = "falha_rate_limit"              # HTTPError, status_code == 429
STATUS_FALHA_HTTP = "falha_http"                          # HTTPError, qualquer outro status_code
STATUS_FALHA_REDE = "falha_rede"                          # RequestException não classificada acima
STATUS_FALHA_CONTEUDO_VAZIO = "falha_conteudo_vazio"      # content vazio (finish_reason truncado)
STATUS_FALHA_PARSE_JSON = "falha_parse_json"              # json.JSONDecodeError
STATUS_FALHA_VALIDACAO_SCHEMA = "falha_validacao_schema"  # pydantic.ValidationError
STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO = "falha_nome_numerico_nao_mapeado"  # ADR-021
```

Os `except` da chamada de rede passam de um único `except
requests.RequestException` genérico para uma cadeia do mais específico ao
mais genérico (ordem importa: `Timeout`/`ConnectionError`/`HTTPError` são
subclasses de `RequestException`, testadas antes do fallback):

```python
except requests.exceptions.Timeout as e:
    return _falha_chamada("[FALHA_TIMEOUT]", ..., STATUS_FALHA_TIMEOUT, ...)
except requests.exceptions.ConnectionError as e:
    return _falha_chamada("[FALHA_CONEXAO]", ..., STATUS_FALHA_CONEXAO, ...)
except requests.exceptions.HTTPError as e:
    status_code = e.response.status_code if e.response is not None else None
    motivo = STATUS_FALHA_RATE_LIMIT if status_code == 429 else STATUS_FALHA_HTTP
    ...
except requests.RequestException as e:
    return _falha_chamada("[FALHA_REDE]", ..., STATUS_FALHA_REDE, ...)
```

Nova função `_falha_chamada` centraliza o log com tag própria (mesmo
padrão greppável do `[REPARO_NOME_NUMERICO]` do ADR-021,
ex.: `[FALHA_TIMEOUT]`, `[FALHA_CONEXAO]`, `[FALHA_RATE_LIMIT]`,
`[FALHA_HTTP]`, `[FALHA_REDE]`) e o registro no Langfuse — evitando repetir
os mesmos argumentos de telemetria (`_registrar_langfuse`, atualizado no ADR-023) em cada `except`.

Os dois erros de parse da resposta (antes um único `except
(json.JSONDecodeError, ValidationError)`) foram separados em dois `except`
distintos, cada um com sua tag (`[FALHA_PARSE_JSON]`,
`[FALHA_VALIDACAO_SCHEMA]`) — um JSON malformado e um JSON válido mas fora
do schema são causas-raiz diferentes (o primeiro é o LLM não obedecendo o
formato pedido; o segundo é a estrutura vir certa mas com campos/tipos
errados).

**Rastreabilidade no Langfuse:** todo caminho de falha (inclusive o
semântico do ADR-021) agora inclui `metadata["tipo_erro"] = <status>` na
chamada a `_registrar_langfuse` (contrato mantido idêntico na migração para o SDK oficial no ADR-023) — filtrável no dashboard sem precisar
abrir o log, mesmo padrão de "campo estruturado, não só texto livre em
`erro`" já estabelecido pelo `metadata["reparo_nome_numerico"]` do
ADR-021.

Os consumidores do `status` do chunk (`reprocessar_falhas_piloto.py`,
`gerar_relatorio_revisao.py`, `gerar_db_datasette.py`,
`validar_taxonomia.py`) **não precisaram de nenhuma mudança**: já foram
generalizados no ADR-021 para tratar qualquer `status not in (None,
"sucesso")` como falha, sem depender da string literal `"falha"` — a
granularidade nova dos status técnicos é absorvida de graça pelo mesmo
código.

## Consequências

### Positivas
- Cada falha registra no status persistido e no Langfuse *por que* falhou,
  sem abrir o log — responde "quantos timeouts hoje" / "esse chunk foi
  rate-limit ou schema" direto no dashboard/`.auditoria.json`.
- Falhas tipicamente transitórias (timeout, conexão, rate-limit) ficam
  visualmente distintas de falhas que tendem a se repetir com os mesmos
  parâmetros (conteúdo vazio, parse, schema) — informação útil para decidir
  se vale a pena só reprocessar ou se precisa ajustar `max_tokens`/prompt.
- Nenhum consumidor de `status` precisou mudar — a generalização já feita
  no ADR-021 (`status not in (None, "sucesso")`) absorve qualquer novo
  status técnico automaticamente.
- Testado com todos os 8 tipos de exceção reais (`Timeout`,
  `ConnectionError`, `HTTPError` 429, `HTTPError` 500,
  `RequestException` não classificada, conteúdo vazio, JSON inválido,
  schema inválido) — `tests/test_taxonomia_extractor.py::TestClassificacaoDeErros`.

### Limitações conhecidas
- HTTP 4xx/5xx fora de 429 caem todos em `STATUS_FALHA_HTTP` (não separa
  401/403/500/503 individualmente) — granularidade suficiente para decidir
  "foi HTTP" vs. "foi rede/parse"; separar por código específico fica como
  extensão futura se algum código particular precisar de tratamento
  diferente (ex.: 401 nunca deveria ser retentado, ao contrário de 503).
- `STATUS_FALHA_REDE` é um fallback deliberadamente genérico para qualquer
  `RequestException` não coberta pelas três subclasses tratadas — não há
  como enumerar todas as subclasses de `requests.exceptions` de antemão sem
  acoplar o código a detalhes internos da biblioteca.

### Alternativas Descartadas
- **Manter um único status técnico genérico e usar só `metadata["tipo_erro"]`
  para diferenciar** (sem mudar o `status` persistido): descartado porque o
  `status` é o campo que aparece no relatório HTML e no Datasette — quem
  revisa o edital veria "falha" sem saber se vale a pena só reprocessar
  (timeout) ou se precisa investigar (schema); o Langfuse não é a única
  superfície de rastreabilidade que importa aqui.
- **Um status por código HTTP individual** (`falha_http_401`,
  `falha_http_500`, ...): descartado por enquanto — explode o espaço de
  status sem um caso de uso concreto que precise da granularidade completa;
  o par (`STATUS_FALHA_HTTP`, `status_code` na mensagem de log) já permite
  grep pelo código específico quando necessário.
- **Classificar por regex na mensagem de exceção** em vez de por tipo de
  exceção Python: descartado — `requests` já expõe uma hierarquia de
  exceções tipada (`Timeout`, `ConnectionError`, `HTTPError`), usá-la é mais
  robusto que casar texto de mensagem de erro (que pode variar por versão
  da lib).
