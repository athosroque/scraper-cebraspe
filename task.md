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
  (hoje apontando para o banco próprio `scraper-cebraspe-db`, ADR-026) e `OPENROUTER_API_KEY`/`TELEGRAM_OPENROUTER_API_KEY`.
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
  próprio JSON gerado). **A revisão humana em si (aprovar/reprovar a
  qualidade da extração) ainda está PENDENTE** — o JSON existe para você
  revisar; não marque esse checkpoint como aprovado sem olhar o conteúdo.
- `[x]` **Trilha de auditoria + navegação via Datasette:** além do
  `<edital>.json`, o checkpoint agora salva `<edital>.auditoria.json` (o que
  entrou/saiu de cada etapa local — corte de seção, chunking, texto exato
  enviado ao LLM por chunk — não só contagens agregadas como no log).
  `scripts/gerar_db_datasette.py` constrói `revisao_piloto/revisao.db` a
  partir desses JSONs; `docker-compose.yml` sobe Datasette. A interface
  agora está exposta via Traefik e Cloudflare Tunnel no endereço
  `https://datasette.projetoathos.com.br`, protegida por Zero Trust SSO
  (permissão restrita para `athoslobin@hotmail.com`). Isso é ferramenta
  de apoio à revisão — **não fecha** o item acima; a aprovação humana da
  qualidade da extração continua PENDENTE. Em caso de erro na geração
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
  pelo SDK oficial `langfuse>=3,<4` em `src/taxonomia_extractor.py` e `src/telegram_bot.py`.
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
- `[ ]` Desenhar **star schema**: dimensões (`materias`, `topicos`,
  `orgaos`, `cargos`, `anos`) e fatos (`concursos`, `cargos_editais`,
  `taxonomia_itens`), com colunas `JSONB` para metadados irregulares que não
  justificam dimensão própria ainda.
- `[ ]` Modelar cargo↔prova como **N:1 para Conhecimentos Básicos** (um
  caderno pode cobrir vários cargos de mesmo nível — ex: CB1 = cargos 1 a
  14, CB2 = cargo 15) e **1:1 para Conhecimentos Específicos/Discursiva**.
  `nivel` (médio/superior) é atributo do cargo, não da prova. Discursiva
  guarda só o **tema**, nunca o conteúdo completo, e só existe registro pra
  cargo que efetivamente tem discursiva. Ver `ProvaObjetiva`/
  `ProvaDiscursiva` em `models_scraper.py` e a decisão em `CLAUDE.md` (seção
  12). A fonte do texto que identifica tipo/cargo(s)/CB1 vs CB2 é
  `provas_texto_link.json` (gerado pelo downloader a partir do texto do
  link, ver `LESSONS.md`) — não dá pra extrair isso do conteúdo do PDF.
- `[ ]` **Nenhuma** FK para tabelas de outro projeto. As dimensões carregam
  **chaves naturais normalizadas** (`slug` do concurso, `materia_normalizada`,
  nome de tópico normalizado, já produzidos pelo parser — ADR-020), que servem
  de ponte para o cruzamento da Etapa 7 sem acoplar os bancos agora.
- `[ ]` Criar `src/stats_writer.py` para gravação idempotente
  (`CREATE TABLE IF NOT EXISTS` + upsert por chave natural), lendo a conexão
  de `POSTGRES_*` no `.env`.
- `[ ]` Criar tabela/fila `pendente` para os PDFs de Provas e Gabaritos
  baixados. O consumidor dessa fila (pipeline de extração de questões) é
  **fora do escopo deste projeto** por enquanto — só deixar a fila pronta e
  populada.

## Etapa 6: Teste Piloto e Validação
- `[ ]` Rodar o fluxo completo ponta a ponta (Crawler → Downloader → Parser
  → LLM → DB) para **1–2 concursos grandes de 2025 já encerrados** (ex:
  INSS, PF).
  > **Nota de Progresso (2026-09-21):** O pipeline de extração e validação
  > (Crawler → Downloader → Parser → LLM → Validação/Datasette) já foi executado
  > e homologado com sucesso absoluto em **5 concursos de 2025** (`PF_25_ADM`,
  > `TCU_25_TEFC`, `IBAMA_25`, `STM_25` e `CD_25_NS`), totalizando 150 chunks com 100% de
  > sucesso e 0 alertas bloqueantes após a reconciliação do ADR-025 (2 informativos: PF e STM). A conclusão formal da Etapa 6 depende apenas
  > da implementação do DB Writer Postgres (Etapa 5).
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
