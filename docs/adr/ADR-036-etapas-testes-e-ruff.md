# ADR-036: Divisão e Agrupamento de Testes e Ruff por Etapas

## Status
Aceito (implementado e validado em 2026-10-07)

## Data
2026-10-07

## Contexto

Com a expansão do projeto após a conclusão das etapas 5H e 6, a suíte de testes automatizados atingiu a marca de **840 testes** (839 aprovados, 1 xfailed), e o tempo total de execução pelo `pytest` chegou a **4 minutos e 45 segundos** (283.5s).

Uma análise de duração (`pytest --durations=20`) revelou a seguinte distribuição:
1. **`site/tests/` (209 testes):** consome **~3m23s (~72% do tempo total)** por executar consultas SQL pesadas, joins analíticos e agregações de facetas (`vw_questoes`, `vw_prova_cobra_base`) contra a instância local do PostgreSQL (`scraper-cebraspe-db`). Desses testes, ~14 consultas mais lentas levam entre 3s e 15s individualmente.
2. **`tests/` (631 testes):** consome **~1m15s (~28% do tempo)**. Destes, a grande maioria (~545 testes) são testes unitários puros em memória (parsers de PDF, expressões regulares, árvore JSON, sinonimos e lógica canônica), que executam em **menos de 20 segundos** e não necessitam de banco de dados ativo.
3. **Ruff:** não possuía arquivo central de configuração (`pyproject.toml` ou `ruff.toml`), fazendo com que o `ruff check .` falhasse em arquivos e pastas de rascunho como `scratch/` e sem ignores oficiais alinhados ao estilo do portfólio homelab.

Esse cenário gerava alto atrito no ciclo de desenvolvimento diário (TDD, correções rápidas em templates, parsers e regras de árvore), forçando o desenvolvedor ou agente de IA a esperar quase 5 minutos para validar edições simples.

## Decisão

1. **Configuração centralizada do Ruff (`pyproject.toml`)**:
   - Padronizado conforme a convenção dos demais projetos do homelab (`target-version = "py311"`, `line-length = 88`).
   - Regras habilitadas: `select = ["E", "F", "I", "UP"]`.
   - Exclusões explícitas adicionadas para diretórios e arquivos de trabalho/temporários: `scratch/`, `scratch.py`, `data/`, `venv/`, `revisao_piloto/`, `questoes/`.
   - Ignores cosméticos alinhados: `E501` (comprimento gerenciado pelo formatter), `E402` (import tardio de dependências de lifespan/templates em `site/app/main.py`) e `E741` (variáveis locais de uma letra em loops de lotes).
   - `.gitignore` atualizado para conter `scratch/` e `scratch.py`.

2. **Registro de marcadores semânticos no Pytest (`pytest.ini`)**:
   - `unit`: testes rápidos e isolados (sem rede nem banco de dados).
   - `db`: testes de integração dependentes do container PostgreSQL `scraper-cebraspe-db`.
   - `pipeline`: testes do ecossistema de scraping, extração, parsers e árvore (`tests/`).
   - `site`: testes da aplicação web FastAPI, rotas, simulados e estatísticas (`site/tests/`).
   - `slow`: testes com tempo individual de execução elevado (> 3s).

3. **Classificação dinâmica no Pytest via hook (`conftest.py`)**:
   - Implementado o hook padrão `pytest_collection_modifyitems` na raiz (`conftest.py`).
   - Todos os testes sob `site/tests/` são automaticamente categorizados como `site` e `db` (com exceção de formatadores puros marcados como `unit`).
   - Testes sob `tests/` são marcados como `pipeline`, distinguindo automaticamente os que gravam no star schema (`db`) dos que são puro processamento de dados (`unit`).
   - As 14 consultas analíticas mais lentas são dinamicamente marcadas como `slow`.
   - Isso eliminou a necessidade de alterar manualmente mais de 40 arquivos de teste, mantendo zero risco de regressão.

4. **Interface de execução por etapas (`Makefile`)**:
   - **Etapa 1 (Dev / Fast Feedback):** `make test-fast` executa `ruff check .` e 545 testes unitários em **~18 segundos** (sem conexão ao Postgres).
   - **Etapa 2A (Pipeline):** `make test-pipeline` executa os 631 testes de `tests/` em **~1m15s**.
   - **Etapa 2B (Site & API):** `make test-site` executa os 209 testes de `site/tests/` em **~3m20s**.
   - **Etapa 2C (Site Fast):** `make test-site-fast` executa os 196 testes do site pulando os 13 mais lentos em **~2m15s**.
   - **Etapa 3 (Full CI / Pré-push):** `make test-all` executa rigorosamente todos os 840 testes (~4m45s).
   - **Check Geral:** `make check` roda `lint` + `format-check` + `test-all`.

## Consequências

- **Redução drástica no tempo de ciclo de desenvolvimento:** o feedback para testes unitários caiu de **4m45s para 18 segundos (~15x mais rápido)**.
- **Desenvolvimento offline viabilizado:** a Etapa 1 (`make test-fast` ou `pytest -m "unit and not db"`) roda com 100% de sucesso mesmo sem o container PostgreSQL inicializado.
- **100% de compatibilidade retroativa:** o comando original `pytest` sem argumentos continua executando integralmente os 840 testes (839 passados, 1 xfailed), sem nenhum teste sendo ocultado ou ignorado por padrão.
- **Ruff estável:** 0 erros de linting e formatação em 163 arquivos válidos, sem interferência de rascunhos em `scratch/`.

## Alternativas Descartadas

1. **Paralelização forçada via `pytest-xdist` (`-n auto`) em toda a suíte:**
   - Descartada por ora para os testes de `site/tests/`, pois a execução paralela de testes que realizam transações e leituras simultâneas no banco `scraper-cebraspe-db` introduziria risco de deadlocks e flakiness intermitente. A separação por etapas solucionou o gargalo de tempo sem adicionar dependências ou fragilidades de infraestrutura.
2. **Dividir a suíte movendo arquivos de pastas físicas:**
   - Descartada para não quebrar a arquitetura existente nem caminhos de importação consolidados. O uso de marcadores dinâmicos no `conftest.py` preservou toda a estrutura física intacta.
