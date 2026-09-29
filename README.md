# Scraper CEBRASPE

> Pipeline automatizado de rastreamento, download, extração de conteúdo programático e estruturação taxonômica de editais, provas e gabaritos de concursos públicos do CEBRASPE.

---

## ⚡ Início Rápido (< 5 minutos)

### Pré-requisitos
- Python 3.11+
- Docker e Docker Compose (para visualização no Datasette)
- Rede Docker `homelab_default` (PostgreSQL próprio `scraper-cebraspe-db`, sobe com `docker compose up -d`)

### Instalação

```bash
# 1. Clonar ou acessar o repositório
cd /home/athos/homelab/scraper_cebraspe

# 2. Criar e ativar o ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependências Python
pip install -r requirements.txt

# 4. Instalar os navegadores do Playwright (Chromium)
playwright install chromium

# 5. Configurar variáveis de ambiente
cp .env.example .env
# Edite o .env preenchendo as chaves necessárias
```

### Execução Básica (Pipeline Automatizado)

```bash
# 1. Executar o crawler e download dos PDFs (concursos de 2025)
python -m src.spider

# 2. Subir a interface do Datasette para inspeção (uma única vez)
docker compose up -d

# 3. Extrair taxonomia via LLM (piloto)
# O script executa a extração E dispara automaticamente scripts.atualizar_revisao
# (validação de-para -> relatórios HTML -> banco SQLite -> restart do Datasette):
python -m scripts.revisar_taxonomia_piloto

# 4. (Opcional) Reprocessar falhas com context window ampliado
# Também aciona scripts.atualizar_revisao automaticamente ao obter novos sucessos:
python -m scripts.reprocessar_falhas_piloto
# Ou forçar chunk_index específicos mesmo com status=sucesso (ex.: achado
# semântico que o reparo automático não cobriu, ver ADR-021):
python -m scripts.reprocessar_falhas_piloto --chunks 17,21

# 5. (Opcional) Sincronizar manualmente todos os artefatos de revisão
# Útil caso arquivos JSON em revisao_piloto/ sejam editados diretamente:
python -m scripts.atualizar_revisao

# 6. (Opcional) Executar backfill determinístico de classificação e concurso
# Enriquece extrações legadas sem custo de inferência LLM (ADR-020):
python -m scripts.backfill_classificacao_chunks

# Acesse o banco tabular em http://127.0.0.1:8011 ou https://datasette.projetoathos.com.br
# Acesse os relatórios visuais em https://datasette.projetoathos.com.br/relatorio/index.html
```

---

## ✨ Funcionalidades

- **Rastreamento Resiliente:** Coleta automatizada a partir de `/concursos/encerrado`, com resolução de links relativos e extração de ano e órgão diretamente pelo slug da URL.
- **Download com Desduplicação Dupla:**
  - *Camada de Rede:* Manifesto `.manifest.json` por concurso para ignorar URLs já baixadas.
  - *Camada de Armazenamento:* Verificação de hash SHA256 para evitar arquivos idênticos duplicados em disco.
- **Validação Rigorosa de PDFs:** Checagem de integridade binária através de magic bytes `%PDF-` e Content-Type, descartando falsos 200 com HTML de erro.
- **Parser Inteligente de Editais:** Recorte focado exclusivamente na seção `"OBJETOS DE AVALIAÇÃO"`, com suporte a layouts multicolunas via PyMuPDF e limpeza de notas de retificação.
- **Chunking em Dois Níveis:** Associação estrita de conteúdo programático por cargo e disciplina, atendendo tanto a cargos administrativos quanto a especialidades médicas e técnicas.
- **Extração Taxonômica via LLM:** Extração hierárquica (matéria → tópico → subtópico) validada por modelos Pydantic, utilizando o modelo `glm-5.3-flash` via OpenRouter com retry exponencial e trilha de auditoria completa (`.auditoria.json`).
- **Reparo Local Determinístico (ADR-021):** Resolução automática para tópicos cujo nome veio preenchido apenas pelo numeral do item ("1", "2", etc.). O extrator busca o texto do tópico diretamente no texto-fonte sem novas chamadas de LLM (zero token), registrando a correção com tag `[REPARO_NOME_NUMERICO]` e metadados no Langfuse.
- **Classificação Granular de Erros de Inferência (ADR-022):** Mapeamento explícito de exceções e desfechos técnicos (`falha_timeout`, `falha_conexao`, `falha_rate_limit`, `falha_http`, `falha_rede`, `falha_conteudo_vazio`, `falha_parse_json`, `falha_validacao_schema`, `falha_nome_numerico_nao_mapeado`), persistido no `status` do chunk e no metadata `tipo_erro` do Langfuse, permitindo distinguir instabilidades transitórias de problemas de schema ou prompt.
- **Validação Heurística De-Para:** Comparação determinística por texto normalizado entre o edital e os tópicos retornados pelo LLM, sinalizando 5 tipos de alertas (`topico_ausente`, `topico_extra`, `chunk_sem_extracao`, `chunk_sem_classificacao` e `topico_nome_numerico`) em `.validacao.json` sem custo adicional de API.
- **Relatórios Estáticos Lado a Lado:** Geração de página única HTML por edital com layout em duas colunas (texto-fonte com `<mark>` para tópicos ausentes vs. taxonomia extraída).
- **Pipeline Automático de Artefatos (ADR-019):** Orquestração automática da sequência de validação, relatórios HTML, reconstrução de banco e restart do Datasette a cada extração ou reprocessamento, eliminando passos manuais.
- **Classificação por Nível e Tipo de Conhecimento (ADR-020):** Cada chunk do edital sai com concurso, nível (médio/superior), básico/específico, cargo e marcação "só discursiva", para filtrar tópicos (e, depois, questões) por esses eixos.
- **Interface de Revisão Humana:** Geração de banco `revisao.db` com busca Full-Text Search (FTS5), tabela `alertas_validacao`, tabela `cargos` e facets de classificação em `taxonomia_topicos` servido via Datasette, expondo também os relatórios estáticos e protegido por Cloudflare Access SSO.

---

## ⚙️ Configuração (.env)

Copie o arquivo `.env.example` para `.env` e configure as variáveis conforme seu ambiente:

| Variável | Descrição | Padrão / Exemplo |
|---|---|---|
| `POSTGRES_HOST` | Host do PostgreSQL próprio (`scraper-cebraspe-db`, ADR-026) | `localhost` (fora de container) ou `scraper-cebraspe-db` |
| `POSTGRES_PORT` | Porta de acesso ao banco PostgreSQL | `5435` (local, só `127.0.0.1`) ou `5432` (Docker) |
| `POSTGRES_DB` | Nome do banco de dados relacional | `cebraspe` |
| `POSTGRES_USER` | Usuário de autenticação no banco | `cebraspe` |
| `POSTGRES_PASSWORD` | Senha do banco; obrigatória (sem ela o container não sobe) | *(gerar com `secrets.token_urlsafe`)* |
| `TELEGRAM_BOT_TOKEN` | Token do bot de notificações do Telegram | *(opcional)* |
| `TELEGRAM_ALLOWED_USER_ID` | ID do usuário autorizado no bot | *(opcional)* |
| `OPENROUTER_KEY_TELEGRAM` | Chave dedicada do OpenRouter para o Telegram Bot | `sk-or-v1-...` |
| `OPENROUTER_API_KEY` | Chave do OpenRouter para extração de taxonomia | `sk-or-v1-...` |
| `LANGFUSE_PUBLIC_KEY` | Chave pública do Langfuse para observabilidade (SDK oficial OTel, ver ADR-023) | *(opcional)* |
| `LANGFUSE_SECRET_KEY` | Chave secreta do Langfuse (SDK oficial OTel, ver ADR-023) | *(opcional)* |
| `LANGFUSE_HOST` | Endpoint do servidor Langfuse | `https://cloud.langfuse.com` |

---

## 📂 Estrutura de Diretórios

```text
scraper_cebraspe/
├── data/                       # Armazenamento físico de PDFs e metadados
│   ├── <ano>/CEBRASPE/<orgao>/ # Editais, Provas e Gabaritos baixados
│   └── processed_concursos.json # Registro de idempotência do crawler
├── docs/                       # Documentação técnica do projeto
│   ├── architecture.md         # Desenho arquitetural e diagramas Mermaid
│   └── adr/                    # Registros de Decisões de Arquitetura (ADRs)
├── revisao_piloto/             # Artefatos da Etapa 4 de revisão humana
│   ├── <edital>.json           # Taxonomia extraída pelo LLM
│   ├── <edital>.auditoria.json # Trilha de auditoria (offsets e texto bruto)
│   ├── <edital>.validacao.json # Alertas de tópicos ausentes ou divergentes
│   ├── relatorio/              # Relatórios HTML estáticos lado a lado
│   └── revisao.db              # Banco SQLite FTS5 para o Datasette
├── scripts/                    # Utilitários de migração, testes e auditoria
│   ├── atualizar_revisao.py    # Pipeline automatizado de validação, relatórios e restart
│   ├── backfill_classificacao_chunks.py # Backfill de classificação e concurso sem LLM (ADR-020)
│   ├── experimento_falhas_llm.py # Teste controlado de parâmetros de inferência
│   ├── gerar_db_datasette.py   # Constrói revisao.db a partir dos JSONs
│   ├── gerar_relatorio_revisao.py # Gera relatórios HTML de revisão humana
│   ├── reprocessar_falhas_piloto.py # Reprocessador com contexto estendido
│   ├── revisar_taxonomia_piloto.py # Orquestrador de extração do piloto
│   └── validar_taxonomia.py    # Validação heurística de-para edital vs taxonomia
├── src/                        # Código-fonte principal
│   ├── spider.py               # Crawler Playwright para CEBRASPE
│   ├── downloader.py           # Downloader com duplo dedup e validação
│   ├── edital_parser.py        # Parser PyMuPDF e fatiamento de seções
│   ├── taxonomia_extractor.py  # Integração com OpenRouter e schemas Pydantic
│   ├── telegram_bot.py         # Bot de notificações e consultas via Telegram
│   ├── models_scraper.py       # Modelos de dados e validação de entidades
│   └── logger.py               # Configuração centralizada de logs
├── tests/                      # Bateria de testes automatizados (pytest)
├── docker-compose.yml          # Serviço Datasette para revisão local/web
├── requirements.txt            # Dependências Python do projeto
├── CLAUDE.md                   # Diretrizes operacionais para assistentes de IA
├── LESSONS.md                  # Registro de post-mortems e lições aprendidas
├── llms.txt                    # Manifesto resumido para ferramentas de IA
└── task.md                     # Roteiro mestre de tarefas e etapas
```

---

## 🧪 Testes e Validação

Para rodar a suíte completa de testes unitários e de integração:

```bash
# Executar todos os testes
pytest

# Executar com saída detalhada
pytest -v

# Executar testes específicos do spider
pytest tests/test_spider.py
```

---

## 📚 Documentação Técnica

- [Arquitetura do Sistema](docs/architecture.md): Visão aprofundada dos pipelines, diagramas Mermaid e fluxo de dados.
- [Catálogo de ADRs](docs/adr/README.md): Histórico completo das decisões de arquitetura e trade-offs técnicos (ADR-001 a ADR-022).
- [Lições Aprendidas](LESSONS.md): Post-mortems detalhados de bugs reais de web scraping e comportamento de modelos de linguagem.
- [Diretrizes de IA](CLAUDE.md): Padrões de engenharia e contexto operacional do repositório.
- [Manifesto llms.txt](llms.txt): Visão rápida e indexada para ferramentas e assistentes de IA.

---

## 📄 Licença

Uso interno no ecossistema Homelab / Athos Roque. Todos os direitos reservados.
