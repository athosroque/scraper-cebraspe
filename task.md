# Tarefas de Implementação: Scraper CEBRASPE

Este documento serve como seu guia definitivo de passos. Como você fará a
implementação dividida em diferentes prompts/sessões, você pode simplesmente
enviar o bloco de uma etapa específica para o agente construir.

> **Revisão 2026-09-19:** este plano foi revisado após checar o código já
> existente (`src/spider.py`, `src/models_scraper.py`, `src/logger.py`) e
> testar o site do CEBRASPE ao vivo com Playwright. Os achados que motivaram
> a revisão estão registrados em `CLAUDE.md` (seção 12, Log de decisões) e
> `LESSONS.md`. Alvo confirmado: **concursos ENCERRADOS de 2025** (edital,
> prova e gabarito já publicados) — não 2026 em andamento.

> **🎯 Objetivo do produto (redefinido em 2026-09-28, ADR-030):** um **site
> público de questões** (item de portfólio), no estilo Gran Questões, com mais
> filtros e estatísticas da base de concursos. Escopo inicial: só o piloto
> 2025 (5 concursos, ~2.800 itens). A **questão** é a entidade central e o
> **subassunto** é a unidade de estudo. Estatísticas, em ordem de
> importância: (1) o que mais cai na prova; (2) o que o edital cobra; (3)
> edital × prova; (4) desempenho pessoal do usuário.

> **⚡ Prioridade atual (2026-09-28):** Etapas **5D → 5E → 5F** (5B.1 e
> 5B.2 concluídas: árvore mestre curada; próximas: classificação das questões,
> estatísticas e site). A 5A (ADR-028), a 5B (ADR-029, sinônimos aprovados em
> 2026-09-27), a 5C e a 5C.1 (ADR-031) estão concluídas. A antiga 5B.1
> ("divisão de nomes compostos") foi **substituída** pela árvore mestre
> (ADR-030): num mapeamento N:N, o nome composto é só um item que aponta
> para dois nós.

## Etapa 1: Preparação do Ambiente e Modelos de Dados
- `[x]` Completar `requirements.txt`: já tem `playwright`, `pymupdf`,
  `pydantic` — adicionar `psycopg2-binary` (Etapa 5) e `python-dotenv`
  (leitura de `.env`). Rodar `pip install -r requirements.txt` e
  `playwright install chromium` sem erro.
- `[x]` Corrigir `src/logger.py`: hoje usa caminho relativo `"logs"`
  (`os.makedirs("logs")` / `FileHandler("logs/scraper_cebraspe.log")`), que
  quebra se o script rodar fora da raiz do projeto. Ancorar em
  `Path(__file__).resolve().parent.parent / "logs"`.
- `[x]` Criar `.env.example` com `POSTGRES_HOST/PORT/DB/USER/PASSWORD`
  (hoje apontando para o banco próprio `scraper-cebraspe-db`, ADR-026) e `OPENROUTER_KEY_*` por etapa (fallback `OPENROUTER_API_KEY`).
  `.gitignore` já criado nesta revisão (cobre `.env`, `venv/`, `logs/`,
  `data/`).
- `[x]` Revisar `src/models_scraper.py` (já existe, mas com 3 problemas a
  corrigir):
  - `ConcursoMetadados` não tem `id`/`slug` — mas `CargoEdital.concurso_id`
    já referencia um ID inexistente. Adicionar `slug: str` derivado do slug
    da URL do concurso (ex: `TJ_CE_25_NOTARIOS`), usado como chave.
  - `link_edital_base: Optional[str]` deve virar `links_editais: List[str]`
    — um concurso pode ter retificação/aditamento, e `spider.py` já mapeia
    `editais_abertura` como lista. Modelo e crawler estão desalinhados hoje.
  - `TaxonomiaEdital.topicos: List[str]` + `.subtopicos: List[str]` (listas
    paralelas) perdem a relação tópico→subtópico. Trocar por estrutura
    aninhada, ex:
    ```python
    class Topico(BaseModel):
        nome: str
        subtopicos: List[str] = []


    class TaxonomiaEdital(BaseModel):
        materia: str
        topicos: List[Topico]
    ```

## Etapa 2: O Spider (Crawler)
- `[x]` **Corrigir o filtro de ano** em `spider.py:51`: hoje faz
  `re.search(r'2025', text)` sobre o **texto do link**, mas o texto de todo
  card é sempre `"MAIS INFORMAÇÕES"` (confirmado ao vivo) — o filtro nunca
  retorna nada. Extrair o ano do **slug da URL** (padrão `_(\d{2})(_|$)`,
  ex: `TJ_CE_25_NOTARIOS` → `25` → 2025). Feito em `extract_year_from_slug`.
- `[x]` Trocar a URL-base de `https://www.cebraspe.org.br/concursos/` (raiz)
  para `https://www.cebraspe.org.br/concursos/encerrado`. A raiz trouxe só
  80 links de concurso; `/encerrado` trouxe 423 — e é onde estão os
  concursos com Prova/Gabarito já publicados.
- `[x]` Envolver **cada concurso individualmente** em `try/except` dentro do
  loop de `run()` — hoje o `try/except` envolve o método inteiro, então uma
  falha num concurso aborta o processamento de todos os outros. Validado com
  simulação de falha isolada (concurso segue processando os demais).
- `[x]` Manter o stealth básico atual (rotação de User-Agent, espera
  aleatória 1.5–3.5s). Teste ao vivo não encontrou CAPTCHA/challenge numa
  navegação simples — não investir em `playwright-stealth` ou spoofing de
  `navigator.webdriver` a menos que apareça bloqueio real em volume.
- `[x]` Adicionar idempotência simples: pular concurso cujo slug já foi
  processado (checar pasta em `data/` ou registro local). Implementado com
  registro JSON local (`data/processed_concursos.json`), já que a hierarquia
  de pastas por órgão só existe a partir da Etapa 3.
- `[x]` Manter a priorização de grandes cargos (INSS, PF, PRF, Receita) para
  o piloto. Também migrada do texto do link (sempre "MAIS INFORMAÇÕES") para
  o slug da URL — mesma causa-raiz do bug do filtro de ano; ver
  `CLAUDE.md` (seção 12).
- `[x]` Manter o mapeamento de PDFs de Edital de Abertura, Provas e
  Gabaritos por concurso (lógica já existe em `map_pdf_links`). Validado ao
  vivo contra um concurso real (`AGSUS_25_CCE`): retornou 3 editais, 10
  provas, 1 gabarito, todos em URLs absolutas (`cdn.cebraspe.org.br`).
- `[x]` **BUG encontrado e corrigido na auditoria de 2026-09-19:**
  `get_contest_links` filtrava `href.startswith("https://www.cebraspe.org.br/concursos/")`,
  mas os cards reais da listagem usam **href relativo**
  (`/concursos/PF_25_ADM`, não absoluto) — `get_attribute("href")` devolve o
  atributo cru do HTML, sem resolver contra a URL da página. Resultado: **0
  concursos encontrados em produção, silenciosamente, sem exceção** — o
  mesmo padrão de falha silenciosa já documentado para o filtro de ano, mas
  desta vez no ponto de entrada do crawler, mascarando que todo o resto da
  Etapa 2 (filtro de ano, priorização, idempotência) nunca chegava a rodar.
  Confirmado ao vivo: rodar `get_contest_links` contra
  `/concursos/encerrado` retornava 0/424 cards antes da correção. Corrigido
  resolvendo o href com `urljoin(page.url, raw_href)` antes de comparar —
  após a correção, 31 concursos de 2025 encontrados, priorização e
  extração de órgão corretas para todos (`PF_25_ADM`, `TCU_25_TEFC`
  priorizados; `AGSUS_25_CCE` → `AGSUS`, etc.). 3 testes de regressão
  adicionados em `tests/test_spider.py`
  (`TestGetContestLinksResolveHref`). Ver `CLAUDE.md`, seção 12.

## Etapa 3: Download e Organização Estruturada
- `[x]` Criar `src/downloader.py` com função de download que valida
  Content-Type/magic bytes do PDF (evita salvar uma página HTML de erro como
  se fosse PDF, algo comum quando um link está quebrado).
- `[x]` Definir função de slugify determinística para nome de órgão
  (acentos/espaços → forma normalizada única) — sem isso, execuções
  diferentes podem gerar nomes de pasta distintos para o mesmo órgão.
- `[x]` Salvar em `data/<ano>/CEBRASPE/<orgao_slug>/{Editais,Provas,Gabaritos}/`.
- `[x]` Dedup por hash de conteúdo entre execuções (não rebaixar PDF já
  presente).
- `[x]` Escopo explícito: nesta fase de construção, a Etapa 3 roda sobre a
  lista já filtrada/priorizada da Etapa 2 (concursos encerrados de 2025,
  ordenados por prioridade) — o corte final para 1–2 concursos do piloto
  acontece na Etapa 6, não aqui.
- `[x]` **Auditoria 2026-09-19 — validado ao vivo, sem falhas:** rodado
  `download_concurso_pdfs` contra PDFs reais do concurso `AGSUS_25_CCE`
  (`cdn.cebraspe.org.br`) — edital e gabarito baixados com sucesso,
  magic bytes `%PDF-1.5` confirmados, gravados em
  `2025/CEBRASPE/AGSUS/{Editais,Gabaritos}/` com `.manifest.json`
  populado corretamente. Nenhuma falha encontrada no downloader em si; o
  bug real da fase estava upstream, no crawler (ver Etapa 2).

## Etapa 4: Análise Exploratória e Extração Híbrida
- `[x]` **Análise Exploratória Manual:** baixado ao vivo (crawler + downloader
  já corrigidos) o edital real `Ed_1_2025_PF_Administrativo_Abertura_
  atualizado_ret_5.pdf` (concurso `PF_25_ADM`, 68 páginas). Decisão: a única
  seção com valor para a taxonomia matéria→tópico→subtópico é "OBJETOS DE
  AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)" — cronograma, critérios de
  desempate e requisitos/atividades por cargo são dados operacionais do
  concurso, não conteúdo programático, e foram descartados. Racional
  completo em `CLAUDE.md`, seção 12.
- `[x]` Criado `src/edital_parser.py` (PyMuPDF). **Achado real, não
  hipotético:** a seção não tem colunas paralelas (confirmado por
  coordenadas de bloco — todo bloco de corpo de texto com x0 ≈ 42.5), mas
  o corte por cabeçalho da primeira versão do parser (só letras/espaço/
  hífen) perdia silenciosamente todo cabeçalho com dígito, vírgula ou
  parênteses (`CARGO 7: MÉDICO CLÍNICO`, `ADMINISTRAÇÃO FINANCEIRA,
  ORÇAMENTÁRIA...`) — o conteúdo de ~14 cargos inteiros foi parar dentro
  de 1 chunk só (41850 chars, ~55% da seção). Corrigido e revalidado
  contra o PDF real: 39 chunks, nenhum > ~7000 chars. Ver `LESSONS.md`.
- `[x]` **Chunking:** `dividir_por_cargo_e_materia` separa por cargo (`CARGO
  N: <nome>`) e por matéria dentro de cada cargo — cobre os dois formatos
  reais do edital (cargo com matérias nomeadas à parte, ex: Administrador;
  e cargo de especialidade cujo próprio nome é a "matéria", ex: Médico
  Clínico).
- `[x]` **Extração LLM:** `src/taxonomia_extractor.py`, POST direto via
  `requests` para OpenRouter (`{OPENROUTER_BASE_URL}/chat/completions`, `z-ai/glm-5.3-flash`) —
  sem adicionar `langchain-openai`/`openai` nem LiteLLM como dependência (stack do
  projeto já tem `requests`). Chaves isoladas salvas só em `.env` local (gitignored).
  **Achado real:** `glm-5.3-flash` é modelo de raciocínio — parte do
  orçamento de tokens vai para `reasoning_content` antes do `content`
  final; com `max_tokens` baixo o `content` vem `null` mesmo sem erro de
  rede. `max_tokens=8192` usado (mesmo padrão do `study-rag-agent`). Saída
  validada contra `TaxonomiaEdital`/`Topico` (`src/models_scraper.py`).
- `[x]` **Revisão Humana Contínua:** `scripts/revisar_taxonomia_piloto.py`
  roda o pipeline completo (parser → chunking → LLM) contra o edital piloto
  real e salva o resultado em `revisao_piloto/<edital>.json` — não escreve
  em banco, não decide sozinho que está "bom", não dispara lote. Rodado de
  verdade contra o edital PF_25_ADM (ver resumo/contagem de sucesso no
  próprio JSON gerado). A revisão humana em si foi feita pelo dono
  e **registrada nos JSONs em 2026-09-23** (Etapa 5A, ADR-028).
- `[x]` **Trilha de auditoria + navegação via Datasette:** além do
  `<edital>.json`, o checkpoint agora salva `<edital>.auditoria.json` (o que
  entrou/saiu de cada etapa local — corte de seção, chunking, texto exato
  enviado ao LLM por chunk — não só contagens agregadas como no log).
  `scripts/gerar_db_datasette.py` constrói `revisao_piloto/revisao.db` a
  partir desses JSONs; `docker-compose.yml` sobe Datasette. A interface
  agora está exposta via Traefik e Cloudflare Tunnel no endereço
  `https://datasette.projetoathos.com.br`, protegida por Zero Trust SSO
  (permissão restrita para `athoslobin@hotmail.com`). Isso é ferramenta
  de apoio à revisão — **não fecha** o item acima (a aprovação foi
  registrada na Etapa 5A). Em caso de erro na geração
  do DB, lembre-se de renomear arquivos corrompidos (ex: `.json` para `.bak`).
- `[x]` **Redução da taxa de falha de extração:** comparados dois runs reais
  completos (39 chunks) — falha majoritariamente não-determinística (só 2
  das 5 falhas coincidem entre os runs). Implementado retry com backoff (3
  tentativas) em `extrair_taxonomia_chunk`, `max_tokens`/`timeout`/
  `reasoning` parametrizáveis, e limpeza de nota de retificação embutida no
  texto (`_limpar_ruido_edital`). Experimento controlado
  (`scripts/experimento_falhas_llm.py`, 20 chamadas reais nos 5 chunks que
  falharam) validou `max_tokens=24576`/`timeout=240s` como fix: 5/5 sucesso,
  contra 2/5 do baseline. `thinking: disabled` testado e descartado como
  mitigação (3/5, mesma assinatura de falha do baseline num caso — indício
  de que o backend ignora o parâmetro). Novo default de produção já
  aplicado em `src/taxonomia_extractor.py`. Racional completo em
  `CLAUDE.md` seção 12 e `LESSONS.md`.
- `[x]` **Validação heurística de-para e relatórios visuais (ADR-017 e ADR-018):**
  `scripts/validar_taxonomia.py` compara itens numerados do texto-fonte contra
  a taxonomia extraída usando correspondência de texto normalizado por substring,
  gerando `<edital>.validacao.json` com alertas (`topico_ausente`, `topico_extra`,
  `chunk_sem_extracao` e, desde o ADR-020, `chunk_sem_classificacao`). `scripts/gerar_relatorio_revisao.py` gera HTMLs
  estáticos de página única lado a lado com destaque `<mark>` nos itens ausentes,
  servidos pelo Datasette via `--static relatorio:/data/relatorio`. Schema
  estendido com `alertas_validacao` e `editais.total_alertas`.
- `[x]` **Pipeline automatizado dos artefatos de revisão (ADR-019):**
  `scripts/atualizar_revisao.py` encapsula a sequência (`validar_taxonomia` →
  `gerar_relatorios` → `gerar_db` → restart best-effort do container Datasette).
  Chamado automaticamente ao final de `revisar_taxonomia_piloto.py` e
  `reprocessar_falhas_piloto.py` (ao obter novos sucessos), eliminando os 4 passos
  manuais após cada extração e mantendo `revisao.db` e `/relatorio/` sempre em dia.
- `[x]` **Classificação por Nível, Tipo de Conhecimento e Concurso (ADR-020):**
  reconhecimento de cabeçalhos de bloco (`PADRAO_BLOCO`) no parser PyMuPDF para
  definir `tipo_conhecimento` (básico/específico) e `nivel` (médio/superior), além
  de `cargo_numero`, `materia_normalizada` e `apenas_discursiva`. Resolução do
  concurso de origem (`slug`, `orgao`, `ano`) via manifesto do downloader. Extensão
  do schema SQLite com tabela `cargos` e desnormalização para facets em `taxonomia_topicos`.
  Backfill determinístico sem LLM implementado em `scripts/backfill_classificacao_chunks.py`,
  completando 39/39 chunks no piloto `PF_25_ADM` com 0 alertas de classificação.
- `[x]` **Reparo local determinístico para nome de tópico numérico (ADR-021):**
  detecção e reparo automático de tópicos com `topico["nome"]` puramente numérico
  ("1", "2", ...), extraindo o texto real diretamente do texto-fonte via
  `extrair_itens_numerados` (`src/edital_parser.py`) dentro de `src/taxonomia_extractor.py`,
  sem nova chamada ao LLM (zero token), com log `[REPARO_NOME_NUMERICO]` e metadados
  no Langfuse. Se houver numeral não mapeado, devolve status específico
  `falha_nome_numerico_nao_mapeado`. Adicionado alerta passivo `topico_nome_numerico`
  em `validar_taxonomia.py` e parâmetro `--chunks` em `reprocessar_falhas_piloto.py`
  para forçar reprocessamento por índice de chunk mesmo com status "sucesso".
- `[x]` **Classificação granular de erros e exceções da chamada LLM (ADR-022):**
  mapeamento explícito de falhas na camada HTTP/OpenRouter (`falha_timeout`,
  `falha_conexao`, `falha_rate_limit`, `falha_http`, `falha_rede`,
  `falha_conteudo_vazio`, `falha_parse_json`, `falha_validacao_schema`), persistido
  no `status` do chunk e no metadata `tipo_erro` do Langfuse via `_falha_chamada`
  com logs greppáveis `[FALHA_*]`, diferenciando falhas transitórias de infraestrutura
  de falhas estruturais de formatação e schema.
- `[x]` **Migração da telemetria Langfuse para SDK oficial OTel (ADR-023):**
  substituição do endpoint REST manual legado (`/api/public/ingestion`, sunset em 2026-11-16)
  pelo SDK oficial `langfuse>=4.7,<5` (era `>=3,<4`; ver nota no ADR-023) em `src/taxonomia_extractor.py` e `src/telegram_bot.py`.
  Observation do tipo generation aberta antes da requisição HTTP para medição real de latência,
  fechamento em `_registrar_langfuse` e flush automático em segundo plano via `atexit`.
- `[x]` **Generalização do Parser e Resiliência a Variações de Editais de 2025:**
  - Substituição determinística de espaços não-separáveis `\xa0` por espaços ASCII no PyMuPDF.
  - Absorção de títulos de cargos multi-linha sem itens intermediários no rótulo do cargo, eliminando chunks espúrios.
  - Reconhecimento de colons parentéticos em cabeçalhos de matérias (`PADRAO_MATERIA` com `(?:\s*\([^)]*\))?:`).
  - Mapeamento de cabeçalhos `CONHECIMENTOS GERAIS` para tipo básico e tolerância a prefixos numéricos em `PADRAO_BLOCO`.
  - Detecção automática de cargo único e nível escolar via páginas preliminares (`detectar_cargo_e_nivel_edital`) para editais como `TCU_25_TEFC`.
- `[x]` **Eliminação de Falsos Positivos na Validação Heurística (`validar_taxonomia.py`):**
  - Normalização preliminar NFC para unir diacríticos combinantes decompostos (NFD) antes da remoção de pontuação.
  - Mapeamento determinístico de ligaduras tipográficas corrompidas de fontes do CEBRASPE (`MAPA_LIGATURAS_FONTES`: `Ɵ`→`ti`, `Ō`→`ft`, `ﬃ`→`ffi`, etc.).
  - Cobertura expandida para tópicos e subtópicos (`todos_extraidos`), reconhecendo itens agrupados pelo LLM.
  - Casamento por fronteira de palavra `\b` e igualdade exata para termos curtos (>= 3 chars).
  - Supressão de falso `topico_extra` via verificação de pertinência no texto integral do chunk (`texto_fonte_norm`).
  - Alertas do IBAMA_25 reduzidos de 1.271 para 1; base consolidada de 2025 fechada com apenas 3 alertas em 135 chunks.
- `[x]` **Expansão da Extração em Lote de 2025 (PF, TCU, IBAMA, STM e Câmara dos Deputados):**
  - Execução validada contra 5 editais representativos: `PF_25_ADM` (39 chunks), `TCU_25_TEFC` (10 chunks), `IBAMA_25` (33 chunks), `STM_25` (53 chunks) e `CD_25_NS` (15 chunks).
  - Total de 150 chunks extraídos com 100% de sucesso na chamada LLM (0 falhas).
  - `CD_25_NS` finalizado com 0 alertas de validação; base total consolidada com apenas 3 alertas em 150 chunks.
  - Sincronização automática de todos os artefatos via `atualizar_revisao.py` (JSONs de resultado, auditoria, validação, relatórios HTML e banco `revisao.db`).
  - Suite com 165 testes unitários e de integração aprovados em `pytest`.
- `[x]` **Tratamento automático dos 3 alertas residuais (ADR-025):**
  - Reinjeção determinística, sem LLM, de item de primeiro nível omitido (`reinjetar_itens_ausentes`): IBAMA_25 #32 `IN Ibama 05/2021`.
  - Severidade `informativo` para paráfrase leve (`topico_divergencia_leve`): PF_25_ADM #31 (qualificador entre parênteses) e STM_25 #31 (erro de digitação da fonte corrigido pelo LLM).
  - Remoção da assinatura do fim da seção (`remover_assinatura_final`), validada nos 5 editais.
  - Backfill `scripts/reconciliar_taxonomia.py`; base de 2025 com **0 alertas bloqueantes** e 2 informativos em 150 chunks; 186 testes aprovados.

## Etapa 5: Modelagem do Banco de Dados Estatístico

> **Revisão 2026-09-21 (ADR-026):** o plano original gravava as tabelas na
> instância `study-rag-db` do `study-rag-agent`, com FK opcional para
> `itens_estudo`. Isso foi revertido: os domínios são distintos (material de
> estudo pessoal × dados públicos de concursos), a FK teria a direção errada e
> ficaria sempre `NULL`, e o `study-rag-db` será reconfigurado. Este projeto
> passa a ter **banco próprio**; o cruzamento entre os dois virou a Etapa 7.

- `[x]` Usar **PostgreSQL 16** (padrão do portfólio, não reabrir) em
  **instância própria**: serviço `scraper-cebraspe-db` (`postgres:16-alpine`)
  no `docker-compose.yml` deste projeto, banco/usuário `cebraspe`, senha só em
  `.env` (sem default no compose), porta publicada só em `127.0.0.1:5435`,
  rede `homelab_default`. Container criado e saudável em 2026-09-21.
- `[x]` Desenhar **star schema**: dimensões (`materias`, `topicos`,
  `orgaos`, `cargos`, `anos`) e fatos (`concursos`, `cargos_editais`,
  `taxonomia_itens`), com colunas `JSONB` para metadados irregulares que não
  justificam dimensão própria ainda.
- `[x]` Modelar cargo↔prova como **N:1 para Conhecimentos Básicos** (um
  caderno pode cobrir vários cargos de mesmo nível — ex: CB1 = cargos 1 a
  14, CB2 = cargo 15) e **1:1 para Conhecimentos Específicos/Discursiva**.
  `nivel` (médio/superior) é atributo do cargo, não da prova. Discursiva
  guarda só o **tema**, nunca o conteúdo completo, e só existe registro pra
  cargo que efetivamente tem discursiva. Ver `ProvaObjetiva`/
  `ProvaDiscursiva` em `models_scraper.py` e a decisão em `CLAUDE.md` (seção
  12). A fonte do texto que identifica tipo/cargo(s)/CB1 vs CB2 é
  `provas_texto_link.json` (gerado pelo downloader a partir do texto do
  link, ver `LESSONS.md`) — não dá pra extrair isso do conteúdo do PDF.
- `[x]` **Nenhuma** FK para tabelas de outro projeto. As dimensões carregam
  **chaves naturais normalizadas** (`slug` do concurso, `materia_normalizada`,
  nome de tópico normalizado, já produzidos pelo parser — ADR-020), que servem
  de ponte para o cruzamento da Etapa 7 sem acoplar os bancos agora.
- `[x]` Criar `src/stats_writer.py` para gravação idempotente
  (`CREATE TABLE IF NOT EXISTS` + upsert por chave natural), lendo a conexão
  de `POSTGRES_*` no `.env`.
- `[x]` Criar tabela/fila `pendente` para os PDFs de Provas e Gabaritos
  baixados. ~~O consumidor dessa fila é fora do escopo~~ → o consumidor
  virou prioridade na **Etapa 5C** (decisão de 2026-09-22).

> **Concluída em 2026-09-22 (ADR-027):** `src/sql/schema_estatisticas.sql` +
> `src/stats_writer.py` (`python -m src.stats_writer`, também automático no
> fim de `scripts/atualizar_revisao.py`). Carga real idempotente: 5
> concursos, 1485 tópicos, 70 provas (ponte `provas_cargos`), 145 PDFs em
> `fila_extracao_questoes`. Concursos entram com `status_revisao =
> 'pendente'`. A aprovação é registrada no `status_revisao_humana` do
> `<edital>.json`, e não por `UPDATE` no banco, porque o writer relê o JSON a
> cada carga (ver Etapa 5A).

---

# ⚡ PRIORIDADE (2026-09-22, revista em 2026-09-29): Etapas 5A–5F (5A, 5B, 5B.1, 5B.2, 5C, 5C.1 e 5D concluídas; próximas: 5E estatísticas → 5F site) — questões, árvore de assuntos, estatísticas e site público

> **Por que existe:** a Etapa 5 entregou o banco com a **taxonomia dos
> editais**, ou seja, o que o edital lista. O objetivo real do projeto é
> saber **o que a prova cobra**: o assunto mais cobrado e quais questões são
> desse assunto, filtrando por nível (médio × superior), cargo, ano, órgão e
> banca. Também é preciso poder **refazer a prova** de um concurso/cargo como
> simulado. Estas etapas vêm **antes** da Etapa 6 e devem ser executadas **em
> ordem, uma por sessão**. Cada uma termina com testes verdes e ADR; B e D
> terminam com checkpoint de aprovação humana.
>
> **Decisões já tomadas pelo dono do projeto (não reabrir):**
> - Sinônimos: regras determinísticas + proposta do LLM + **aprovação
>   humana**. Nada `proposto` entra na estatística.
> - `NOÇÕES DE X` é a **mesma matéria** `X`, com a marca `nocoes = true`.
> - Extrair **todas** as questões dos cadernos, o tema da discursiva e o
>   gabarito, ligados a cargo, ano, nível, banca e órgão.
> - Simulado como **página web** (servida no Datasette com SSO). Bot do
>   Telegram não, por ora. *(Revisto em 2026-09-28: o simulado vai para o
>   site público da Etapa 5F; o Datasette fica só para revisão do dono.)*
> - *(2026-09-28, ADR-030)* A taxonomia é uma **árvore mestre curada**
>   (matéria → assunto → subassunto), semeada com os grupos aprovados da 5B.
>   Item de edital e questão **apontam** para nós da árvore (N:N); eles não
>   definem a árvore.
>
> **Achados medidos nos dados reais (2026-09-22) que moldam o desenho:**
> - Hoje são 106 matérias (102 depois da Etapa 5A, que fundiu as 4 variantes
>   "(APENAS PARA ...)") e 1220 tópicos. Só 76 tópicos têm o mesmo texto em
>   mais de um concurso. Há sinônimos reais: `ADMINISTRAÇÃO FINANCEIRA E
>   ORÇAMENTÁRIA` × `ADMINISTRAÇÃO ORÇAMENTÁRIA E FINANCEIRA`, e `CONTABILIDADE
>   PÚBLICA` × `CONTABILIDADE APLICADA AO SETOR PÚBLICO`.
> - **Semelhança de texto não serve para agrupar sozinha:** `atos
>   administrativos` ≈ `contratos administrativos` (0,89), `mensuração de
>   ativos` ≈ `mensuração de passivos` (0,90), `gestão de processos` ≈
>   `gestão de pessoas` (0,89). Agrupar automaticamente por similaridade
>   corromperia a estatística.
> - O parser deixa a restrição de cargo no nome da matéria (`DIREITO PENAL
>   MILITAR (APENAS PARA O CARGO 1: ...)`), o que gera matéria duplicada.
>   Também há espaço duplo em nomes do IBAMA.
> - A prova é **Certo/Errado**. Os itens estão numerados em linha
>   (`15 Identificando-se...`), com texto-base compartilhado antes de cada
>   grupo. Básicos vão de 1 a 50 (CD: 1 a 90); específicos de 51 a 120 (CD: a
>   partir de 91). A varredura determinística achou a sequência completa em
>   quase todos os cadernos. Exceção: `094_PF_005_01` só achou 58 a 120.
> - O gabarito definitivo é uma grade (20 números, depois 20 letras
>   `C`/`E`/`X`, com `0` de enchimento), e **o código do caderno está no
>   conteúdo do PDF** (`167_CDNS_002_01`, `108_TCUTEFC_001_01`). Isso liga os
>   gabaritos com nome em hash (CD/TCU) que hoje ficam sem `prova_id`.
> - A discursiva é um enunciado com quesitos `[valor: X pontos]`; o padrão de
>   resposta é outro PDF. Há figuras em vários cadernos (ex.:
>   `094_PF_007_01` tem 16 imagens).

## Etapa 5A: Registro da revisão da Fase 4 e correções do parser (sem LLM)
- `[x]` Registrar a revisão humana da Fase 4, **já feita pelo dono do
  projeto**. Nos 5 `revisao_piloto/<edital>.json`, trocar
  `status_revisao_humana` para
  `"APROVADO — revisão humana da Fase 4 concluída (registrada em 2026-09-22)"`.
  O `stats_writer` já converte `APROVADO...` em
  `concursos.status_revisao = 'aprovado'`. **Não** aprovar só com `UPDATE` no
  banco: o writer relê o status dos JSONs a cada carga e reverteria.
- `[x]` `CLAUDE.md`: Fase 4 `[x]` e `Status: in-progress:phase-6`. Corrigir
  a frase "a aprovação é um `UPDATE` no banco" no ADR-027, no `CLAUDE.md` e
  na nota da Etapa 5 acima: a aprovação é feita no JSON.
- `[x]` `src/edital_parser.py`: novo `PADRAO_RESTRICAO_CARGO` para
  `(APENAS PARA O(S) CARGO(S) ...)`. A restrição sai de `materia_normalizada`
  e vira o campo `cargos_restritos: list[int]`, incluído em
  `CAMPOS_CLASSIFICACAO_CHUNK`. Para extrair os números de cargo, usar a
  mesma função de `stats_writer.extrair_cargos_do_texto`, movida para um
  lugar comum (parser ou `comparacao_texto`) para os dois não divergirem.
  Colapsar espaços repetidos no nome.
- `[x]` Backfill sem LLM (`scripts/backfill_classificacao_chunks.py`,
  ADR-020) nos 5 editais. Depois, `python -m scripts.atualizar_revisao`.
- `[x]` `taxonomia_itens.cargos_restritos int[]` no schema, gravado pelo
  writer.
- **Pronto quando:** 5 concursos `aprovado` no banco depois de uma carga
  nova, nenhuma matéria com `APENAS PARA` no nome, e `pytest` verde.

> **Concluída em 2026-09-23 (ADR-028):** revisão humana da Fase 4 registrada
> nos 5 `<edital>.json` (o texto do status mantém "2026-09-22", como pedia a
> spec). `cargos_restritos` sai do nome via `PADRAO_RESTRICAO_CARGO` e é
> gravado como `INTEGER[]` em `taxonomia_itens` (e na view
> `vw_taxonomia_detalhe`). `extrair_cargos_do_texto` agora mora em
> `src/comparacao_texto.py`. Backfill em lote, sem LLM. Resultado no banco: 5
> concursos `aprovado`, `dim_materia` de 106 para 102 matérias, nenhuma com
> `APENAS PARA` ou espaço duplo. A auditoria da entrega achou e corrigiu:
> `ruff` vermelho, restrição sem número apagada do nome, parêntese aninhado,
> várias restrições, e a checagem do backfill sem comparar o texto. Nenhum
> dos 150 chunks mudou de metadado com as correções. `pytest`: 259 testes.
>
> **Logs da Etapa 5A (2026-09-25):** o que a 5A mudou agora aparece em
> `logs/scraper_cebraspe.log`, para conferir sem abrir o banco:
> - `[RESTRICAO_CARGO] chunk #N '<matéria>' → só cargos [..]`, no parser,
>   para cada chunk com `cargos_restritos` (ao lado do `[RESTRICAO_SEM_CARGO]`
>   que já existia, que agora também traz o `chunk #N`);
> - `[BACKFILL] <slug>: N chunks · N cargos · N chunks com cargos_restritos ·
>   campos alterados: ...`, com a contagem por campo do que mudou na
>   auditoria (o diff campo a campo sai em `DEBUG`). "nenhuma" confirma que
>   uma reexecução não mudou nada;
> - `[STATS] <slug> (<status_revisao>): ... N com cargos restritos`, por
>   concurso; `[STATS] Órfãs removidas: N matérias (nomes), N tópicos`; e o
>   total da carga com a contagem por status de revisão (`5 aprovado`).
>
> Conferido ao vivo: 4 chunks restritos no STM, "nenhuma" alteração nos 5
> editais, 0 órfãs e `revisão: 5 aprovado`. A busca do PDF de um edital virou
> `localizar_pdf_edital` (reaproveitada pelo lote).

## Etapa 5B: Camada canônica de sinônimos (matéria → assunto → subassunto), com aprovação humana
- `[x]` **Fonte da verdade versionada:** `canonico/sinonimos.json`, porque o
  banco é regenerável. Ele guarda matérias canônicas → assuntos canônicos →
  subassuntos canônicos, cada um com os nomes de origem mapeados, `origem`
  (`regra` | `llm` | `humano`), `status` (`proposto` | `aprovado` |
  `rejeitado`) e ID estável.
- `[x]` `src/canonico.py`, com regras determinísticas conservadoras (chave de
  regra):
  - remove "noções de/sobre" (vira `nocoes = true`), artigos iniciais e
    qualificadores entre parênteses;
  - forma única de norma: `Lei nº 9.784/1999` e `Lei n o 9.784/1999` →
    `lei 9784 1999`;
  - singular/plural simples.
  - Nomes com a mesma chave de regra são agrupados e **aprovados
    automaticamente** (`origem = regra`).
- `[x]` Extrair o núcleo genérico da chamada ao LLM de
  `_chamar_llm_uma_vez` (`src/taxonomia_extractor.py`) para
  `src/llm_openrouter.py`, com
  `chamar_llm_json(prompt_sistema, prompt_usuario, schema_pydantic, ...)`.
  Manter os status de falha tipados (ADR-022), o Langfuse via SDK (ADR-023) e
  o `max_tokens` generoso. O extrator de taxonomia passa a usar esse núcleo, e
  todos os testes atuais continuam passando.
- `[x]` `scripts/propor_sinonimos.py`: para o que as regras não agruparam, o
  LLM recebe a **lista fechada de nomes com IDs** e devolve grupos com nome
  canônico, em três passos: (1) matérias; (2) assuntos dentro de cada matéria
  canônica; (3) subassuntos dentro de cada assunto. Validação local: cada ID
  de entrada aparece em exatamente um grupo, e ID desconhecido é falha tipada.
  Sai tudo como `proposto`.
- `[x]` Revisão humana: relatório `revisao_piloto/relatorio/sinonimos.html`
  (mesmo Datasette/SSO), com os grupos propostos, os nomes de origem, os
  concursos e níveis de cada nome, e IDs estáveis. Aprovação via
  `scripts/aprovar_sinonimos.py --aprovar ... --rejeitar ... --mover ID:GRUPO`,
  ou o dono passa as decisões na conversa e o agente aplica.
- `[x]` Banco: `materia_canonica`, `assunto_canonico`, `subassunto_canonico`;
  `dim_materia.materia_canonica_id` + `nocoes`,
  `dim_topico.assunto_canonico_id`. O subtópico sai do JSONB para
  `dim_subtopico` + `taxonomia_subitens` (1 linha por subtópico,
  `subassunto_canonico_id`). **Só mapeamento `aprovado` é carregado.**
- `[x]` Testes: pares reais que devem se juntar (nº de lei, plural,
  "noções") **e** falsos positivos reais que devem ficar separados (atos ×
  contratos administrativos, ativos × passivos, gestão de processos × de
  pessoas).
- `[x]` **Checkpoint:** o dono aprova os sinônimos antes da Etapa 5D.
  **Feito em 2026-09-27** (commits `b5b2e77` e `214f2d2`). Rejeitadas
  `SL-065b9773e6` (nome composto, resolvido por mapeamento N:N na árvore mestre, 5B.1/5B.2) e `ML-badfd45efe` (TI +
  Estatística numa matéria só). "Procedimentos Contábeis Patrimoniais
  conforme MCASP" saiu do grupo do manual e virou `AH-20068a5851`. As
  outras 104 propostas foram aprovadas. Resultado: 89 matérias, 1148
  assuntos e 2493 subassuntos canônicos, nenhuma proposta pendente.

> **Implementada em 2026-09-25 (ADR-029). Aprovação humana concluída em 2026-09-27.**
> `canonico/sinonimos.json` (entradas + grupos, IDs estáveis `M-/A-/S-`,
> `MR-/AR-/SR-`, `ML-/AL-/SL-`, `MH-/AH-/SH-`), `src/canonico.py`,
> `src/llm_openrouter.py` (`chamar_llm_json`, reasoning padrão de 3000
> tokens em toda chamada), `scripts/propor_sinonimos.py`,
> `scripts/aprovar_sinonimos.py`, `relatorio/sinonimos.html` (linkado do
> `index.html`). Regras e relatório rodam em `atualizar_revisao.py`; a
> proposta do LLM só roda de forma explícita.
> - **Regras:** 102 nomes de matéria em 93 entradas (9 juntadas, todas
>   "NOÇÕES DE X" × "X"), 1259 tópicos em 1202 entradas (52 juntadas), 2689
>   subtópicos em 2593 entradas (85 juntadas). Aprovado automaticamente.
> - **LLM (execução real):** 20 chamadas, US$ 0,0139, 38,9 mil tokens de
>   entrada e 35,6 mil de saída. Falhas: 2 `falha_validacao_schema` (o mesmo
>   lote; `nome_canonico` omitido em grupo de 1 ID, corrigido no schema e o
>   nível refeito), 1 `falha_grupo_entre_blocos` e 1 `falha_id_ausente`
>   (resolvidas na 2ª tentativa com o erro no prompt). A 1ª execução usou
>   reasoning de 4000; as seguintes, 3000.
> - **106 propostas pendentes:** 3 matérias, 40 assuntos, 63 subassuntos.
>   61 juntam nomes com a mesma chave de regra separados só porque as
>   matérias-pai não foram aprovadas (somem sozinhas ao aprovar a matéria);
>   75 dependem de aprovar antes o grupo do nível de cima. Comece pelas 3
>   matérias.
> - **Banco:** `materia_canonica` 93, `assunto_canonico` 1202,
>   `subassunto_canonico` 2593 (identidade/regra); 102/102 matérias,
>   1259/1259 tópicos e 2689/2689 subtópicos mapeados; `taxonomia_subitens`
>   3127 linhas; 18 matérias com `nocoes`. Carga idempotente.
> - `pytest`: 316 testes.

## Etapa 5B.1: Árvore mestre semeada com a 5B (modelo, semeadura e banco), sem LLM
> **Por que existe (decisão de 2026-09-28, ADR-030):** o objetivo do projeto
> é um site público de questões. A taxonomia da 5B **nasce dos editais**: o
> pai de cada nome é o pai que ele tem no edital, e cada edital novo traz
> nomes novos que precisam de aprovação. Com só 5 concursos, esse modelo já
> criou três problemas:
> - **Nome composto:** `Disposições gerais, servidores públicos` (PF, TCU,
>   IBAMA básico, CD cargo 1) é um item só, mas é o mesmo conteúdo que
>   `Disposições gerais` + `Servidores públicos` (STM 2×, IBAMA cargo 1, CD
>   cargo 2). Hoje dá 4 + 4 + 4 em três subassuntos, e o certo é 8 + 8 em
>   dois (a proposta `SL-065b9773e6`, que juntava o composto a uma das
>   partes, foi rejeitada).
> - **Matéria composta:** o CD põe "Poder Legislativo", "Administração
>   pública" etc. debaixo de `DIREITO CONSTITUCIONAL E PROCESSO LEGISLATIVO`
>   (16 assuntos, 9 com a mesma chave de regra de um assunto de Direito
>   Constitucional) e de `NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO
>   INTERNO…` (11 assuntos: 6 batem com Constitucional e 1 com Regimento).
>   Esses assuntos não somam com os dos outros concursos.
> - **Granularidade diferente:** o mesmo conteúdo é assunto num edital e
>   subassunto em outro.
>
> Sites de questões usam uma **árvore fixa e curada**, e o edital e a questão
> apontam para ela. Com isso, os três casos viram mapeamento: o composto
> aponta para 2 nós, o assunto do CD aponta para o nó de Direito
> Constitucional e o item de outra granularidade aponta para o nó do nível
> certo. **Nada da 5B se perde:** os grupos aprovados (89 matérias, 1148
> assuntos e 2493 subassuntos) viram os nós, e os mapeamentos aprovados viram
> os primeiros apontamentos.

- `[x]` **Fonte da verdade versionada:** `canonico/arvore.json`, com uma
  linha por registro, como o `sinonimos.json`:
  - **nós:** `id`, `nivel` (`materia` | `assunto` | `subassunto`), `nome`,
    `pai` (ID de nó; `null` na matéria), `origem` (`semente` | `humano` |
    `llm`), `status` (`ativo` | `proposto` | `fundido`), `fundido_em` (ID
    do nó de destino, quando fundido). O **pai pertence ao nó**, não ao
    edital.
  - **mapeamentos:** chave natural do item de edital (a mesma do banco:
    `materia`, `(materia, topico)`, `(materia, topico, subtopico)`) → **lista
    de nós**, com `origem` (`semente` | `regra` | `llm` | `humano`) e
    `status` (`proposto` | `aprovado` | `rejeitado`). O item pode apontar
    para um nó de **qualquer nível** (granularidade diferente), e a
    estatística soma subindo a árvore.
- `[x]` **IDs estáveis:** o nó semeado **herda o ID do grupo aprovado da 5B**
  (`M-/MR-/ML-/MH-`, `A-…`, `S-…`), então quem já aponta para esses IDs
  continua válido. Nó criado depois: `NM-/NA-/NS-` + sha1. **Fundir** nunca
  apaga um ID: o nó de origem vira `fundido`, com `fundido_em`, e toda
  leitura resolve o redirecionamento (`resolver_no`).
- `[x]` `scripts/semear_arvore.py`: lê `sinonimos.json` e cria 1 nó por
  grupo aprovado (pai = grupo aprovado do escopo) e 1 mapeamento `semente`
  por nome de origem. É determinístico e idempotente (a 2ª execução não gera
  diff), e roda uma vez. Depois disso, `sinonimos.json` fica congelado como
  histórico da 5B (ADR-029) e o pipeline para de escrevê-lo.
- `[x]` `src/arvore.py`, com as operações de curadoria:
  - `criar_no`, `renomear_no`, `mover_no` (troca o pai, dentro do nível de
    cima), `fundir_nos(origem, destino)`;
  - `mapear(item, [nós])` e `desmapear`;
  - validação: nível do pai = nível do nó − 1; sem ciclo; nó `fundido` não
    recebe mapeamento novo.

  Toda operação humana vira `status = aprovado`/`ativo`. A proposta do LLM
  (5B.2) sai `proposto` e nunca muda a estatística antes da aprovação
  (mesmo invariante da 5B).
- `[x]` **Item novo de edital (pipeline, ADR-019):** mapeamento automático
  por regra quando a `chave_regra` (`src/canonico.py`, reaproveitada) do nome
  bate com um nome já mapeado **no mesmo nó-pai efetivo** (o nó para onde o
  pai do item aponta). O que a regra não resolve fica sem mapeamento e
  aparece no relatório como pendente. Nunca se cria nó novo automaticamente.
- `[x]` `scripts/curar_arvore.py` (CLI das operações: `--mapear
  ITEM:NO1,NO2`, `--fundir ORIGEM:DESTINO`, `--mover NO:PAI`, `--criar
  "NIVEL:PAI=Nome"`, `--renomear NO=Nome`, `--aprovar`/`--rejeitar`) e
  `revisao_piloto/relatorio/arvore.html`: a árvore navegável, com os itens
  de edital (concurso/cargo/nível) em cada nó, os itens sem mapeamento e as
  propostas pendentes. Substitui o `sinonimos.html`.
- `[x]` **Banco:** `no_arvore` (`id`, `nivel`, `nome`, `pai_id`, `status`,
  `fundido_em`), com as pontes `materia_no`, `topico_no` e `subtopico_no`
  (`dim_* id` → `no_id`, N:N), carregadas só com mapeamento `aprovado`. Uma
  view auxiliar `vw_no_caminho` dá o caminho completo de cada nó (matéria ›
  assunto › subassunto) e resolve os fundidos. `materia_canonica`,
  `assunto_canonico`, `subassunto_canonico` e as FKs `*_canonico_id` das
  dimensões **saem** (nada fora da 5B as usa). A carga é idempotente.
- `[x]` **Views de "o que o edital cobra"**, a partir da árvore expandida
  por cargo:
  - `vw_arvore_edital_por_cargo`: 1 linha por (item do edital × cargo ×
    nó), com concurso, órgão, banca, ano, nível, tipo de conhecimento,
    cargo, nomes de origem e o caminho do nó. O chunk básico
    (`cargo_edital_id` NULL) vira 1 linha para cada cargo do nível,
    respeitando `cargos_restritos`. O tópico sem subtópico entra no nó do
    assunto.
  - `vw_edital_cobra_subassunto`, `vw_edital_cobra_assunto` e
    `vw_edital_cobra_materia`: ocorrência = `taxonomia_itens.id` distinto,
    então o composto e as partes no mesmo item nunca contam 2×. A variante
    oficial filtra `status_revisao = 'aprovado'`.
- `[x]` **Testes:** semeadura (contagem de nós = grupos aprovados, 2ª
  execução sem diff); fundir preserva o ID por redirecionamento; mover
  valida nível e ciclo; composto mapeado para 2 nós conta 1× em cada; item
  mapeado para um nó de nível acima soma no assunto; expansão do básico por
  cargo com `cargos_restritos`; item novo mapeado por regra só dentro do
  mesmo nó-pai efetivo.
- `[x]` **Documentação:** ADR-030 (já escrito com a decisão; completar com a
  implementação), `CLAUDE.md` (§3, §5, §6, §7, §10) e o ADR-029 marcado como
  semente do ADR-030.
- **Pronto quando:** a árvore semeada reproduz os números da 5B (89 / 1148 /
  2493 nós, 100% dos nomes mapeados), o banco carrega as pontes, as views de
  "edital cobra" funcionam com filtro por cargo, e `pytest`/`ruff` estão
  verdes. **A curadoria de conteúdo não entra aqui (5B.2).**

> **Resultado (2026-09-28):** árvore com 3730 nós (89 / 1148 / 2493) e 4050
> mapeamentos `semente` (100% dos nomes). Banco: pontes 102 / 1259 / 2689,
> `vw_arvore_edital_por_cargo` com 9569 linhas (os 1485 itens estão
> cobertos), `vw_edital_cobra_*` com 89 / 1148 / 2493 nós e 18 matérias com
> `nocoes`. Ponto de partida da 5B.2: `Disposições gerais` / `Servidores
> públicos` / composto = 3 / 3 / 4. A primeira entrega (`c514f26`/`25de48c`)
> foi revisada. Foram corrigidos: CLI, regra do pipeline, relatório,
> `nocoes`, resolução de fundido e nó proposto no banco, semente que
> sobrescrevia a curadoria e testes ausentes (views no Postgres, CLI e
> regra). `pytest`: 476 testes (+1 xfail); `ruff` verde.

## Etapa 5B.2: Curadoria da árvore do piloto (LLM com lista fechada + aprovação do dono)
> **Detalhes da implementação e da decisão do dono:** ADR-030, seção
> "Implementação (Etapa 5B.2)". O plano das 2 sessões
> (`plano-etapa-5b2.md`) foi removido ao concluir a etapa e fica no
> histórico do git. Aqui fica só o resumo.
>
> **Decisões do dono (2026-09-28, não reabrir):** `A-4529f205f7`
> "Licitações e contratos administrativos" é **dividido** entre
> `A-2261b82645` e `A-91e52e6c2e`. Os assuntos de processo legislativo das
> matérias compostas do CD vão para uma **matéria nova "Processo
> Legislativo"**. O composto que fica sem uso vira o status novo
> `aposentado` (não `fundido`, porque fundir redireciona para um nó só).
- `[x]` **Sessão A (sem LLM):** propostas de operação no `arvore.json`
  (`fundir`, `mover`, `criar`, `remapear`, `aposentar`), validadas numa
  cópia e aprovadas em lote, tudo ou nada; status `aposentado` (JSON +
  CHECK no Postgres); `detectar_compostos` por `chave_regra` (esperado:
  `A-4529f205f7` e `S-7b3b2a86ce`); `arvore.html` com as propostas
  agrupadas por matéria; CLI `--aprovar-proposta`, `--rejeitar-proposta` e
  `--propostas`; testes.
- `[x]` **Sessão B (LLM + checkpoint):** `scripts/propor_arvore.py` (por
  matéria; escopo composto do CD com Constitucional, Regimento e Processo
  Legislativo; destino dos 21 filhos de Licitações), rodada real,
  **decisão do dono** sobre cada `P-…` e ADR-030 atualizado.
- **Pronto quando:** "Disposições gerais" e "Servidores públicos" têm 8
  ocorrências cada em `vw_edital_cobra_subassunto` (7 se `servidores
  públicos civis e militares`, do CD cargo 2, não for fundido);
  "Direito Constitucional" soma os assuntos do CD; `M-841dde7520`,
  `M-d5adcb4de4`, `A-4529f205f7` e `S-7b3b2a86ce` estão `aposentado`; não há
  proposta pendente.
- **Checkpoint:** o dono aprova a árvore antes da Etapa 5D.

> **Resultado (2026-09-28):** rodada real com 83 chamadas (US$ 0,02) e 210
> propostas. O dono rejeitou 29 e aprovou o resto. Na aplicação apareceram
> 50 pares de subassuntos homônimos, que uma regra nova
> (`arvore.detectar_homonimos`) fundiu. Banco: "Disposições gerais" 8 e
> "Servidores públicos" 7 em `vw_edital_cobra_subassunto`, `M-841dde7520`,
> `M-d5adcb4de4`, `A-4529f205f7` e `S-7b3b2a86ce` `aposentado`, nenhuma
> proposta pendente. Árvore: 3577 nós ativos. Ver ADR-030.

## Etapa 5C: Extração determinística de questões, gabaritos e discursivas (sem LLM)
- `[x]` Tirar o "fora do escopo" da fila `fila_extracao_questoes` (Etapa 5,
  `CLAUDE.md` §3): esta etapa é o consumidor dela. O status passa por
  `processando` → `concluido` | `erro`.
- `[x]` `src/gabarito_parser.py`: lê a grade por posição (números e letras,
  descartando o enchimento `0`) → `{numero: 'C' | 'E' | 'X'}`, e extrai o
  código do caderno do **conteúdo** do PDF (liga os gabaritos em hash de
  CD/TCU). Lê também o texto do padrão de resposta da discursiva.
- `[x]` `src/prova_parser.py`, caderno objetivo:
  - a faixa esperada de itens vem do gabarito (verdade de referência);
  - corta o texto nos marcadores `^N ` em ordem, removendo cabeçalho/rodapé
    (`CEBRASPE – <ÓRGÃO> – Edital: 2025`) e normalizando ` `
    (reaproveitar `extrair_texto_paginas` do `edital_parser`);
  - o trecho antes do primeiro item de um grupo vira **texto-base**
    compartilhado;
  - guardar o rótulo de seção (`Julgue os itens relativos a X`) como pista
    para a classificação;
  - figuras extraídas com PyMuPDF para
    `data/<ano>/CEBRASPE/<orgao>/Provas/figuras/<caderno>_<pag>_<n>.png`,
    ligadas ao item ou texto-base pela posição vertical na página.
- `[x]` `src/prova_parser.py`, caderno discursivo: tema/enunciado, quesitos
  (`numero`, `texto`, `valor_pontos` de `[valor: X pontos]`) e ligação com o
  padrão de resposta do mesmo cargo.
- `[x]` Validação: itens extraídos == itens do gabarito. Divergência (ex.:
  `094_PF_005_01`) vira status de falha visível no caderno, **nunca perda
  silenciosa**, no mesmo padrão dos alertas do ADR-017.
- `[x]` Saída gerada `questoes/<caderno>.json` + `<caderno>.auditoria.json`
  (texto bruto por item), no mesmo padrão de `revisao_piloto/`, mantida
  localmente (gitignored por volumetria, 100% regenerável via script).
- `[x]` Banco: `textos_base`, `questoes` (`prova_id`, `numero`, `enunciado`,
  `texto_base_id`, `gabarito`, `anulada`, `figuras jsonb`, `secao`) e
  `discursivas` (`prova_id`, `tema`, `enunciado`, `quesitos jsonb`,
  `padrao_resposta`). `concursos.banca` (`CEBRASPE`, do path/URL). Cargo,
  nível, ano e órgão vêm por join
  (`prova → provas_cargos → cargos_editais → concursos`).
- `[x]` **Pronto quando:** todo caderno tem itens == gabarito ou falha explícita;
  os gabaritos sem prova caem para perto de zero (os 5 restantes são justificativas
  de alteração); 3 cadernos conferidos à mão contra o PDF (um básico, um específico
  com figura, uma discursiva).

> **Concluída em 2026-09-25 (ADR-031):** pipeline determinístico implementado
> com `src/gabarito_parser.py`, `src/prova_parser.py`, `src/questoes_writer.py`
> e `scripts/extrair_questoes.py` (`python -m scripts.extrair_questoes`, também
> chamado automaticamente em `atualizar_revisao.py`).
> - **Execução real:** 70 cadernos processados, 0 falhas, itens == gabarito em
>   todos; 2.800 itens (129 anulados); 34 discursivas / 107 quesitos; 123
>   textos-base; 10 figuras raster; 145 PDFs em `fila_extracao_questoes`
>   concluídos. Gabaritos sem prova: 11 → 5 (os 5 são justificativas de
>   alteração, 1 por concurso; gabarito real sem caderno = 0).
> - **Bug de recuo de item:** em `_recuo_item`, a faixa foi ajustada para
>   `12 < delta < 24` (~18 pt real), eliminando a captura indevida de primeira
>   linha de texto-base (~28–29 pt) nos itens 55 e 62 de `094_PF_007_01`.
> - **Conferência manual:** básico `094_PF_CB2_01` conferido; específico com
>   figura `094_PF_007_01` (figuras ECG OK e itens limpos); discursiva
>   `108_TCUTEFC_002_DISC` (3 questões, quesitos e pontuação 4.8 + 4.8 + 19.0 = 28.6).
> - **Dataset:** 140 JSONs gerados em `questoes/`, mantidos localmente
>   (adicionados ao `.gitignore`) por volume, sendo regeneráveis a qualquer momento.
> - **Testes e CI:** 374 testes aprovados no `pytest`, `ruff` verde.


## Etapa 5C.1: Correções da revisão da 5C (antes da 5D)
- `[x]` Executar as 5 sessões de `correcoes-etapa-5c.md`, uma por conversa
  (posição dos itens, alertas no banco, fila/gabaritos, discursivas,
  documentação). O arquivo é autocontido: não precisa reler este `task.md`.
- **Pronto quando:** as 5 sessões estão marcadas e a verificação padrão do
  arquivo mantém os números da 5C.

## Etapa 5D: Classificação das questões na árvore mestre (LLM, lista fechada)
> **Detalhes da implementação e plano de execução:** [`plano-etapa-5d.md`](file:///home/athos/homelab/scraper_cebraspe/plano-etapa-5d.md).
> O arquivo é autocontido e dividido em 3 sessões independentes (uma por conversa).
> Cada sessão roda seus testes e verificações antes de avançar.
>
> **Decisões fechadas (dono, 2026-09-29):** confiança categórica (`alta`, `media`, `baixa`);
> até 2 nós por questão (`principal` e, se interdisciplinar, `secundario`);
> `fora_do_edital` calculado localmente pelo conjunto do nó (preferencial × reserva);
> fonte da verdade em `canonico/classificacao_questoes.json` (banco Postgres é derivado e recarregável).
- `[x]` **Sessão A (sem LLM):** modelo (`src/classificacao.py`), candidatos preferenciais e de reserva + montagem de lotes (`src/candidatos_questao.py`), tabelas no banco (`questao_no`, `discursiva_no`, `vw_questao_no`), carga idempotente em `stats_writer.py` e testes.
- `[x]` **Sessão B (LLM + rodada real):** `scripts/classificar_questoes.py` (prompt contextualizado, IDs locais `C1..Cn`, validação estrita, reserva para `nenhum_serve`, idempotência), rodada real nos cadernos e testes mockados. (2.834 questões processadas, 450 chamadas, $0.1939 USD, 0 falhas).
- `[x]` **Sessão C (revisão e checkpoint do dono):** relatório HTML (`scripts/gerar_relatorio_classificacao.py`), CLI de curadoria (`scripts/curar_classificacao.py`), decisão/aprovação pelo dono e documentação (ADR-032, `CLAUDE.md`, `task.md`). Concluída em 2026-09-29 com 100% de aprovação pelo dono (3.029 apontamentos aprovados, 0 pendências).
- **Pronto quando:** toda questão utilizável (2.800) e discursiva (34) tem registro canônico; 0 pendências após decisão do dono; `vw_questao_no` cobre os dados aprovados; reextração preserva classificações; pytest e ruff verdes.

## Etapa 5E: Estatísticas (views no banco)
> **Plano de execução em 3 sessões (A `materia_origem`, B base plana + "o que
> mais cai", C edital × prova + fechamento):** `plano-etapa-5e.md` (concluído em 2026-09-29).

- `[x]` Todas as views sobem pela árvore (matéria › assunto › subassunto) e
  são filtráveis por `banca`, `orgao`, `ano`, `concurso`, `cargo`, `nivel` e
  `tipo_conhecimento`. O item básico é expandido por cargo, como na
  `vw_arvore_edital_por_cargo` da 5B.1.
  - `vw_questoes`: linha plana com a questão, o gabarito, o caminho do nó e
    o contexto de concurso (base da busca do site);
  - **(1) o que mais cai:** `vw_prova_cobra_subassunto` /
    `_assunto` / `_materia`: nº e % de questões por nó, com as anuladas à
    parte;
  - **(2) o que o edital cobra:** as views `vw_edital_cobra_*` da 5B.1;
  - **(3) edital × prova:** `vw_edital_vs_prova` (no edital e nunca
    cobrado; cobrado fora do edital; razão cobrança/previsão por nó);
  - `vw_comparativo_nivel` (médio × superior), `vw_certo_errado_por_no`
    (proporção C/E e anulações), `vw_peso_materia_cargo` e
    `vw_discursivas` (tema por matéria/cargo/nível).
- `[x]` Matéria que é o próprio cargo: cargo de especialidade não tem
  cabeçalho de matéria no edital, e o parser usa o nome do cargo como
  matéria (`ESTATÍSTICO`, `ENFERMEIRO`...). Medido em 2026-09-27: 12
  chunks, todos do `PF_25_ADM` (chunks 15 e 22–32); STM, IBAMA e TCU têm
  cabeçalho real. **Não renomear para disciplina:** o edital não faz essa
  classificação, e tudo que é cobrado já está nos assuntos/tópicos
  (decisão do dono, 2026-09-27). Só marcar a origem:
  `ChunkTaxonomia.materia_origem` (`cabecalho` | `prefixo` | `cargo`) nos
  três ramos de `dividir_por_cargo_e_materia`, em
  `CAMPOS_CLASSIFICACAO_CHUNK`, completado por backfill sem LLM (esperado:
  12 `cargo`, 1 `prefixo` do CD, o resto `cabecalho`), e
  `dim_materia.nome_de_cargo boolean`. As views e o site mostram essas
  matérias como "Conhecimentos específicos — <cargo>", não como disciplina.
- `[x]` Documentação: ADR-032 (classificação e estatísticas). `CLAUDE.md`:
  fases e patterns.
- **Pronto quando:** as consultas de exemplo funcionam: top 10 subassuntos
  de LÍNGUA PORTUGUESA em superior × médio; questões de um subassunto
  filtradas por cargo e nível; "no edital, nunca cobrado" do `PF_25_ADM`
  cargo 1. Concluída com 100% de sucesso em 2026-09-29.

## Etapa 5F: Site público de questões (portfólio)
> **Por que existe (2026-09-28):** o produto é um site público no estilo Gran
> Questões, com mais filtros e estatísticas. O Datasette continua só como
> ferramenta de revisão do dono (SSO). **Cada subetapa é uma sessão.** Antes
> da 5F.1, detalhar as subetapas num arquivo autocontido
> (`plano-etapa-5f.md`), no padrão do `correcoes-etapa-5c.md`.

- `[x]` **5F.0 — Decisões (ADR-033):** concluída em 2026-09-29. FastAPI +
  Jinja/HTMX em 3 camadas (migração futura para SvelteKit via `/api/v1`),
  só Google OAuth, schema `app` com roles no mesmo banco (chave estável da
  5D), serviço público sem Zero Trust, postura de crédito à fonte.
  Subetapas detalhadas em `plano-etapa-5f.md`. Itens decididos:
  - stack da API e do frontend;
  - autenticação (provedor próprio × OAuth);
  - hospedagem no Xeon via Traefik + Cloudflare Tunnel, **sem** o Zero
    Trust do Datasette;
  - separação entre o banco de conteúdo (`scraper-cebraspe-db`, somente
    leitura para o site) e os dados de usuário;
  - checagem de direitos de republicação das provas do CEBRASPE (documento
    público; citar a fonte).
- `[x]` **5F.1 — API de leitura:** concluída em 2026-09-29. busca de questões com filtros
  combináveis (banca, órgão, ano, concurso, cargo, nível, tipo, matéria ›
  assunto › subassunto, anuladas, "já resolvidas/erradas" com login),
  paginação e detalhe da questão (texto-base, figuras, gabarito). Lê
  `vw_questoes`.
- `[x]` **5F.2 — Frontend de resolução:** concluída em 2026-10-01. lista filtrável, resolver
  Certo/Errado com a correção imediata, texto-base e figuras, e a árvore de
  filtros navegável.
- `[x]` **5F.3 — Contas e histórico:** concluída em 2026-10-01. cadastro/login, tabela de respostas
  (`usuario`, `questao`, `resposta`, `acertou`, `respondida_em`) e
  **(4) desempenho pessoal** por nó da árvore (onde mais erra), com os
  mesmos filtros.
- `[x]` **5F.4 — Páginas de estatística:** concluída em 2026-10-01. (1) o que mais cai, (2) o que o
  edital cobra e (3) edital × prova, por concurso/cargo/nível, a partir das
  views da 5E.
- `[ ]` **5F.5 — Simulado:** refazer a prova de um concurso/cargo (básico +
  específico na ordem original, cronômetro, discursiva com os quesitos). A
  correção segue a regra CEBRASPE (certo +1, errado −1, branco 0; anulada
  não conta) e mostra o desempenho por nó. Substitui o simulado em HTML
  estático planejado antes para a 5E.
- `[ ]` **5F.6 — Deploy público:** Traefik/Cloudflare, rate limit, headers
  de segurança, backup do banco de usuários, CI (ruff/pytest + testes da
  API).
- **Pronto quando:** o site está no ar com as 2.800 questões do piloto
  filtráveis pela árvore, um usuário cadastrado resolve questões e vê o
  próprio desempenho, e as três estatísticas e o simulado `PF_25_ADM` cargo
  1 funcionam, com a pontuação conferida à mão.

---


## Etapa 6: Teste Piloto e Validação
> **Depende das Etapas 5B.1–5E** (árvore, classificação e estatísticas; a 5A foi concluída em 2026-09-23). O site (5F) pode seguir em paralelo depois da 5E.

- `[ ]` Rodar o fluxo completo ponta a ponta (Crawler → Downloader → Parser
  → LLM → DB) para **1–2 concursos grandes de 2025 já encerrados** (ex:
  INSS, PF).
  > **Nota de Progresso (2026-09-21):** O pipeline de extração e validação
  > (Crawler → Downloader → Parser → LLM → Validação/Datasette) já foi executado
  > e homologado com sucesso absoluto em **5 concursos de 2025** (`PF_25_ADM`,
  > `TCU_25_TEFC`, `IBAMA_25`, `STM_25` e `CD_25_NS`), totalizando 150 chunks com 100% de
  > sucesso e 0 alertas bloqueantes após a reconciliação do ADR-025 (2 informativos: PF e STM). A gravação no Postgres (Etapa 5) já foi feita em
  > 2026-09-22; a conclusão formal da Etapa 6 depende da revisão humana e da
  > aprovação no banco.
- `[ ]` Critério de sucesso explícito: 0 exceções não tratadas no log; 100%
  dos PDFs mapeados efetivamente baixados e validados; taxonomia extraída
  revisada manualmente e aprovada.
- `[ ]` Inspecionar `logs/scraper_cebraspe.log` para checar saúde do
  processo (sem bloqueios, sem timeout).
- `[ ]` Aprovar a base no banco e só então considerar liberar a rotina para
  rodar em lote — agendamento (cron/systemd timer) fica para decisão
  posterior, fora deste piloto.

## Etapa 7 (futura, fora do escopo atual): Cruzamento com o `study-rag-agent`
- `[ ]` Pré-condição: Etapa 6 aprovada e `study-rag-db` já reconfigurado
  (credenciais em `.env`, porta não exposta em `0.0.0.0`).
- `[ ]` Tabela de mapeamento N:N `topico_edital ↔ item_estudo`, casando por
  nome normalizado e, onde não bater, por similaridade de embedding (pgvector).
  Mapeamento é validado por ela, não por FK entre bancos.
- `[ ]` Escolher o mecanismo de leitura cruzada: `postgres_fdw` (um banco lê o
  outro pela rede `homelab_default`) ou camada analítica separada (schema
  `mart`/dbt) que lê os dois. Decisão a registrar em ADR próprio.
- `[ ]` Caso de uso-alvo: "tópicos mais cobrados por matéria/ano que ainda não
  têm item de estudo" → plano de estudo priorizado.

- [x] Etapa 5F.11b — Correções da interface web (antes do deploy 5F.12)
  Plano autocontido em `correcoes-interface-5f.md` (6 sessões: bugs de rota,
  rótulos/formatação, coerência dos números, curadoria da árvore, SEO/UX,
  revalidação ao vivo). Executar uma sessão por conversa.
