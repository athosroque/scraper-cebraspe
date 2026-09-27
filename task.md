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

> **⚡ Prioridade atual (2026-09-25):** Etapas **5B/5B.1 → 5D → 5E**
> (sinônimos, divisão de nomes compostos, classificação das questões, estatísticas por nível
> e simulado). A 5A foi concluída em 2026-09-23 (ADR-028), a 5B aguarda aprovação das
> propostas (ADR-029) e a 5C foi concluída em 2026-09-25 (ADR-031). A 5D depende da aprovação
> da 5B/5B.1 e da 5C.

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

# ⚡ PRIORIDADE (2026-09-22): Etapas 5A–5E (5A concluída em 2026-09-23; 5B implementada em 2026-09-25, aguardando aprovação dos sinônimos; 5C e 5C.1 concluídas em 2026-09-27) — questões, sinônimos, estatísticas por nível e simulado

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
>   Telegram não, por ora.
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
  `SL-065b9773e6` (nome composto, vai para a 5B.1) e `ML-badfd45efe` (TI +
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

## Etapa 5B.1: Divisão de nomes compostos (1 nome → N canônicos), com aprovação humana
> **Por que existe (achado na revisão da 5B, 2026-09-25):** alguns editais
> colam dois itens num nome só, e a 5B só permite que cada nome pertença a
> **um** grupo. Exemplo medido: em DIREITO CONSTITUCIONAL → assunto
> "Administração pública" (arts. 37–42 da CF), STM (2×), IBAMA cargo 1 e CD
> cargo 2 listam `Disposições gerais` e `Servidores públicos` como subtópicos
> separados; PF, TCU, IBAMA básico e CD cargo 1 listam um item só,
> `Disposições gerais, servidores públicos`. São 8 **ocorrências**
> (concurso × cargo/bloco; o mesmo concurso pode aparecer mais de uma vez,
> ex.: STM básico e STM cargo 7), e não 8 editais. Hoje a estatística fica
> 4 + 4 + 4 ocorrências em três subassuntos. O certo é 8 + 8 em dois (8 + 7
> se `servidores públicos civis e militares`, do CD cargo 2, não for
> aprovado como sinônimo de `Servidores públicos`). Juntar o
> nome composto a uma das partes (proposta `SL-065b9773e6`) conta
> "servidores públicos" como "disposições gerais": **rejeitar na revisão da
> 5B** e resolver aqui. O mesmo acontece no nível de matéria:
> `DIREITO CONSTITUCIONAL E PROCESSO LEGISLATIVO` e `NOÇÕES DE DIREITO
> CONSTITUCIONAL E DE REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS` (CD_25_NS)
> são matérias separadas de `DIREITO CONSTITUCIONAL`, e os tópicos de
> Constitucional do CD não somam com os dos outros concursos.
>
> **Hierarquia não muda:** matéria → assunto → subassunto. A divisão só
> diz que um nome de origem cobre **mais de um** canônico do mesmo nível e
> do mesmo pai. Nunca divide entre níveis nem entre pais diferentes.

- `[ ]` `canonico/sinonimos.json`: nova operação `divisao` por entrada
  (`partes: [ID canônico, ...]`, `origem`, `status`, ID estável `MD-/AD-/SD-`).
  Uma entrada com divisão `aprovada` mapeia para todas as partes; sem
  divisão aprovada, continua 1:1 como hoje. Nada `proposto` entra na
  estatística.
- `[ ]` Detecção de candidatos, determinística e conservadora
  (`src/canonico.py`): o nome se divide em `,`, ` e ` e `;`, e **cada
  pedaço** tem a mesma chave de regra de uma entrada **irmã já existente**
  (mesmo pai, em outro concurso). Sai como `proposto`, com `origem = regra`.
  Candidato sem todas as partes existentes não é proposto; pedaço solto
  nunca vira canônico novo sozinho.
- `[ ]` Proposta pelo LLM (opcional, via `scripts/propor_sinonimos.py
  --divisoes`), só para o que a regra não achou. A validação de lista
  fechada vale para as partes: ID desconhecido ou de outro pai é falha
  tipada. Reasoning padrão (3000).
- `[ ]` `scripts/aprovar_sinonimos.py`: `--dividir ID:PARTE1,PARTE2` (divisão
  manual), e `--aprovar`/`--rejeitar` também aceitam IDs de divisão. O
  relatório `sinonimos.html` ganha a seção "Nomes compostos", mostrando para
  cada candidato os concursos/cargos/níveis e os irmãos que justificam cada
  parte (o mesmo quadro usado na revisão deste achado).
- `[ ]` Banco: pontes N:N no lugar da FK única quando houver divisão —
  `dim_materia_canonica` (`materia_id`, `materia_canonica_id`),
  `dim_topico_assunto` e `dim_subtopico_subassunto`, com a FK atual mantida
  como "parte principal" ou removida (decidir e registrar no ADR). As views de
  estatística de edital contam cada parte uma vez por ocorrência
  (concurso × cargo/bloco). **Não somar o
  mesmo item duas vezes na mesma parte.** Idempotência por concurso (ADR-027).
- `[ ]` Testes: `Disposições gerais, servidores públicos` → as 2 partes
  (com irmãos presentes); nome composto sem irmão para uma parte → não
  proposto; vírgula interna que não separa itens (ex.: `Lei nº 8.112/1990,
  de 11 de dezembro`) → não proposto; divisão de matéria do CD; contagem da
  view antes/depois (4+4+4 → 8+8).
- `[ ]` Documentação: ADR-030 (divisão de nomes compostos). Os ADRs
  seguintes passam para ADR-031 (extração de questões) e ADR-032
  (classificação, estatísticas e simulado). `CLAUDE.md`: pattern e
  anti-pattern "nunca juntar nome composto a uma de suas partes".
- **Pronto quando:** a divisão de "Administração pública" da CF deixa
  "Disposições gerais" e "Servidores públicos" com as 8 ocorrências cada; a
  matéria Direito Constitucional do CD_25_NS soma com a dos outros
  concursos (se a divisão for aprovada); `pytest` e `ruff` verdes.
- **Checkpoint:** o dono aprova as divisões junto com os sinônimos, antes da
  Etapa 5D.

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

## Etapa 5D: Classificação das questões por matéria/assunto (LLM, lista fechada)
- `[ ]` Pré-requisito: sinônimos aprovados (5B, feito), nomes compostos
  divididos (5B.1) e questões extraídas (5C).
- `[ ]` `scripts/classificar_questoes.py`: para cada caderno, os candidatos
  são **só** os assuntos canônicos do edital aplicáveis àquele caderno (tipo
  básico/específico, nível, cargos via `provas_cargos` e `cargos_restritos`).
  O LLM recebe um lote (um texto-base com seus itens, ou cerca de 10 itens) e
  o rótulo de seção, e devolve
  `{numero: materia_id, assunto_id, subassunto_id | null, confianca}` ou
  `fora_do_edital`. ID fora da lista de candidatos é falha tipada (ADR-022),
  nunca aceito.
- `[ ]` Estimativa: cerca de 3.300 itens, cerca de 350 chamadas.
- `[ ]` Banco: `questoes_classificacao` (`questao_id`,
  `materia_canonica_id`, `assunto_canonico_id`, `subassunto_canonico_id`,
  `confianca`, `origem`, `status`).
- `[ ]` Revisão humana: relatório por caderno, ordenado por menor
  confiança. As views oficiais só usam classificação `aprovada`.
- **Checkpoint:** o dono aprova a classificação (começando pela amostra de
  baixa confiança).

## Etapa 5E: Estatísticas por nível e simulado
- `[ ]` Views, todas filtráveis por `nivel`, `ano`, `orgao`, `banca`,
  `cargo` e `concurso`:
  - `vw_questoes`: linha plana com questão, gabarito, matéria/assunto/
    subassunto canônicos e o contexto de concurso;
  - `vw_assunto_mais_cobrado`: nº de questões e % da prova por assunto ×
    matéria × nível (e ano/órgão), com as anuladas à parte. "Quais questões
    são deste assunto" = filtrar `vw_questoes` pelo assunto;
  - `vw_comparativo_nivel`: a mesma matéria/assunto/subassunto em médio ×
    superior, lado a lado;
  - `vw_edital_vs_prova`: listado no edital × efetivamente cobrado (inclui
    "no edital, nunca cobrado");
  - `vw_certo_errado_por_assunto`: proporção C/E e anulações;
  - `vw_peso_materia_cargo`: questões por matéria em cada prova de cargo;
  - `vw_discursivas`: tema por matéria/cargo/nível.
- `[ ]` Matéria que é o próprio cargo: cargo de especialidade não tem
  cabeçalho de matéria no edital, e o parser usa o nome do cargo como
  matéria (`ESTATÍSTICO`, `ENFERMEIRO`...). Medido em 2026-09-27: 12
  chunks, todos do `PF_25_ADM` (chunks 15 e 22–32); STM, IBAMA e TCU têm
  cabeçalho real. **Não renomear para disciplina:** o edital não faz essa
  classificação, e tudo que é cobrado já está nos assuntos/tópicos
  canonizados (decisão do dono, 2026-09-27). Só marcar a origem:
  `ChunkTaxonomia.materia_origem` (`cabecalho` | `prefixo` | `cargo`) nos
  três ramos de `dividir_por_cargo_e_materia`, em
  `CAMPOS_CLASSIFICACAO_CHUNK`, completado por backfill sem LLM (esperado:
  12 `cargo`, 1 `prefixo` do CD, o resto `cabecalho`), e
  `dim_materia.nome_de_cargo boolean`. Views e simulado mostram essas
  matérias como "Conhecimentos específicos — <cargo>", não como disciplina.
- `[ ]` Simulado (página web): `scripts/gerar_simulado.py <slug> <cargo>` gera
  `revisao_piloto/relatorio/simulados/<slug>_cargo<N>.html`, servido pelo
  Datasette/SSO. Básico + específico na ordem original, texto-base e
  figuras, botões Certo/Errado/Branco, cronômetro e discursiva com os
  quesitos. A correção no fim segue a regra CEBRASPE (certo +1, errado −1,
  branco 0; anulada não conta) e mostra o desempenho por matéria/assunto. O
  `index.html` lista os simulados, gerados automaticamente no pipeline
  (ADR-019).
- `[ ]` Documentação: ADR-029 (camada canônica, já escrito na Etapa 5B),
  ADR-031 (extração de questões), ADR-032 (classificação, estatísticas e
  simulado). O ADR-028 foi usado pela Etapa 5A e o ADR-030 pela 5B.1. No
  `CLAUDE.md`: fases, patterns e o anti-pattern "nunca agrupar por
  similaridade de texto sem aprovação".
- **Pronto quando:** as consultas de exemplo funcionam (top 10 assuntos de
  LÍNGUA PORTUGUESA em superior × médio; questões de um assunto filtradas por
  nível), e o simulado `PF_25_ADM` cargo 1 é aberto no navegador,
  respondido e corrigido, com a pontuação conferida à mão.

---


## Etapa 6: Teste Piloto e Validação
> **Depende das Etapas 5B–5E, incluindo a 5B.1** (prioridade 2026-09-22; a 5A foi concluída em 2026-09-23).

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
