# Tarefas de Implementação: Scraper CEBRASPE

Este documento serve como seu guia definitivo de passos. Como você fará a
implementação dividida em diferentes prompts/sessões, você pode simplesmente
enviar o bloco de uma etapa específica para o agente construir.

> **Revisão 2026-09-19:** este plano foi revisado após checar o código já
> existente (`src/spider.py`, `src/models_scraper.py`, `src/logger.py`) e
> testar o site do CEBRASPE ao vivo com Playwright. Os achados que motivaram
> a revisão estão registrados nos ADRs (`docs/adr/`, ADR-001 a ADR-008) e
> `LESSONS.md`. Alvo confirmado: **concursos ENCERRADOS de 2025** (edital,
> prova e gabarito já publicados) — não 2026 em andamento.

> **🎯 Objetivo do produto (redefinido em 2026-09-28, ADR-030):** um **site
> público de questões** (item de portfólio), no estilo Gran Questões, com mais
> filtros e estatísticas da base de concursos. Escopo inicial: só o piloto
> 2025 (5 concursos, ~2.800 itens). A **questão** é a entidade central e o
> **subassunto** é a unidade de estudo. Estatísticas, em ordem de
> importância: (1) o que mais cai na prova; (2) o que o edital cobra; (3)
> edital × prova; (4) desempenho pessoal do usuário.

## ⚡ Painel de etapas (atualizado em 2026-10-13)

Ordem de trabalho, uma sessão (conversa) por item. O detalhe de cada sessão está no plano
indicado; o checklist fica na seção da etapa, mais abaixo.

| # | Etapa | Estado | Onde está o detalhe |
|---|---|---|---|
| 1 | **8.C Coleta dos concursos ME de 2025** (prioridade do dono, 2026-10-12) | **próxima** (a C2 é o Dagster, Etapa 9/D5a e D5b) | [`plano-etapa-8c.md`](plano-etapa-8c.md), sessões C0 a C8 |
| 2 | 8.M.2 Estatísticas por recorte (drill-down e filtros, KAN-28/KAN-54) | na fila | seção 8.M.2 abaixo |
| 3 | 8.1 Orquestrador de lotes (o que sobrar depois do Dagster da 8.C/C2) | na fila | [`plano-etapa-8.md`](plano-etapa-8.md), Fase 8.1 |
| 4 | 8.2+ Lotes C/E de 2025 e anos seguintes (2025 → 2026 → 2024 … 2020) | na fila | [`plano-etapa-8.md`](plano-etapa-8.md), Fase 8.2+ |
| 5 | 9 Documentação viva (MkDocs executivo + técnico, registro gerado do código, contexto para agentes) e Dagster como C2 | **em paralelo à 8.C** (docs D1–D4 numa worktree própria; D5a/D5b são a C2 da 8.C), decisões fechadas em 2026-10-13 (KAN-67); D1 (KAN-68) e D2 (KAN-69) concluídas; próxima: D3 (KAN-70) | [`plano-etapa-9.md`](plano-etapa-9.md), sessões D1 a D5b; checklist na seção Etapa 9 |
| — | Pendências sem etapa (KAN-66 busca, KAN-52, KAN-53, recortes lado a lado, 5F.12 deploy) | quando o dono pedir | "Pendências posteriores" e 5F, abaixo |
| — | Etapa 7 (cruzamento com o `study-rag-agent`) | futura | seção Etapa 7 |

Checklist da 8.C (C0 → C1a → C1b → C2 → C3–C7 → C8): seção **8.C** dentro da Etapa 8,
abaixo. Marcar só lá.

Concluídas: Etapas 1 a 6, 5A a 5H, 8.0, 8.M e 8.M.1 (histórico abaixo; planos arquivados em
`docs/planos/`).

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
  ADR-004.
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
  (`TestGetContestLinksResolveHref`). Ver ADR-008.

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
  completo no ADR-009.
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
  ADR-016 e `LESSONS.md`.
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

# Etapas 5A–5H (concluídas; histórico): questões, árvore de assuntos, estatísticas e site público

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
> (`docs/planos/plano-etapa-5b2.md`) está arquivado. Aqui fica só o resumo.
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
- `[x]` Executar as 5 sessões de `docs/planos/correcoes-etapa-5c.md`, uma por conversa
  (posição dos itens, alertas no banco, fila/gabaritos, discursivas,
  documentação). O arquivo é autocontido: não precisa reler este `task.md`.
- **Pronto quando:** as 5 sessões estão marcadas e a verificação padrão do
  arquivo mantém os números da 5C.

## Etapa 5D: Classificação das questões na árvore mestre (LLM, lista fechada)
> **Detalhes da implementação e plano de execução:** [`docs/planos/plano-etapa-5d.md`](docs/planos/plano-etapa-5d.md).
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
> mais cai", C edital × prova + fechamento):** `docs/planos/plano-etapa-5e.md` (concluído em 2026-09-29).

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
> (`docs/planos/plano-etapa-5f.md`), no padrão do `docs/planos/correcoes-etapa-5c.md`.

- `[x]` **5F.0 — Decisões (ADR-033):** concluída em 2026-09-29. FastAPI +
  Jinja/HTMX em 3 camadas (migração futura para SvelteKit via `/api/v1`),
  só Google OAuth, schema `app` com roles no mesmo banco (chave estável da
  5D), serviço público sem Zero Trust, postura de crédito à fonte.
  Subetapas detalhadas em `docs/planos/plano-etapa-5f.md`. Itens decididos:
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
- `[x]` **5F.5 — Simulado:** concluída (ver `CLAUDE.md` §5). refazer a prova de um concurso/cargo (básico +
  específico na ordem original, cronômetro, discursiva com os quesitos). A
  correção segue a regra CEBRASPE (certo +1, errado −1, branco 0; anulada
  não conta) e mostra o desempenho por nó. Substitui o simulado em HTML
  estático planejado antes para a 5E.
- `[ ]` **5F.12 — Deploy público (opcional, decisão do dono em
  2026-10-06; o site ainda vai mudar muito antes de ir ao ar):**
  - `Dockerfile` (python:3.11-slim, uvicorn, usuário não root) e serviço
    `scraper-cebraspe-site` no `docker-compose.yml` (labels Traefik,
    `homelab_default`, figuras montadas `:ro`).
  - Cloudflare Tunnel para o subdomínio público, **sem** Access; middleware
    de rate limit no Traefik; headers (CSP, HSTS, nosniff); `/saude`.
  - Backup `pg_dump -n app` diário (systemd timer do usuário) com retenção
    de 14 dias.
  - CI: ruff + pytest do `site/` no workflow do projeto.
  - **Checklist de direitos:** o dono lê os termos de `cebraspe.org.br`; sem
    proibição expressa → público; com proibição → fica atrás do Access.
- `[x]` **5F.11b — Correções da interface web:** plano em
  `docs/planos/correcoes-interface-5f.md` (6 sessões).
- `[ ]` **Pendências herdadas de `correcoes-interface-5f.md`** (conferir se
  a curadoria da 5H já resolveu antes de abrir sessão):
  - validação da Sessão 6 em navegador real (só houve Chromium headless);
  - "TI + Estatística": qual matéria recebe a parte de Estatística;
  - "Despesa(s) de exercícios anteriores": em 2026-10-08 a árvore ainda tem
    um assunto (`A-25cda6b4f4`) e um subassunto (`SL-0b8742283d`) ativos
    com o mesmo nome;
  - padrão de caixa dos nomes de nó (117 em minúscula): normalizar na
    exibição ou no dado;
  - base dos percentuais exibidos.
- **Ideias opcionais do site** (sem compromisso, vieram do plano da 5F):
  - recuperar as 19 questões ilegíveis (`simbolo_ilegivel`, caderno
    `094_PF_005_01`) recortando o item do PDF como imagem na extração;
  - "% de acerto da comunidade" por questão (agregado anônimo de
    `app.resposta`);
  - filtro rápido "nunca cobrado no edital do meu cargo";
  - sitemap XML das páginas de questão;
  - modo escuro via `prefers-color-scheme`.
- **Pronto quando:** o site está no ar com as 2.800 questões do piloto
  filtráveis pela árvore, um usuário cadastrado resolve questões e vê o
  próprio desempenho, e as três estatísticas e o simulado `PF_25_ADM` cargo
  1 funcionam, com a pontuação conferida à mão.

---

## Etapa 5G: Fidelidade ao caderno e filtros estilo Gran (antes do deploy)
> **Por que existe (2026-10-05):** o dono achou inconsistências entre o site
> e o PDF. Discover feito em 2026-10-05 (números abaixo medidos no banco e
> nos JSONs de `questoes/`). **Cada subetapa é uma sessão.**

**Achados do discover:**
1. **Parágrafos do texto-base perdidos.** `juntar_linhas`
   (`src/prova_parser.py`) junta todas as linhas de prosa com espaço: só 2
   dos 123 textos-base têm quebra de linha. No PDF, o parágrafo é marcado
   pelo recuo da 1ª linha (ex.: `167_CDNS_CG1_01`, x0 56,8 × 28,3 do corpo).
   79 questões citam "primeiro/segundo/… parágrafo" ou "linha N" e ficam
   difíceis de conferir.
2. **Comando do grupo não aparece no site.** O texto "Julgue os itens…,
   considerando que…" é gravado em `questoes.secao`, mas
   `_card_questao.html` não o exibe. 714 itens têm comando com dados de
   contexto. Caso do relato de Raciocínio Lógico: `094_PF_CB2_01` itens
   24–26 ("entrevista com 60 pessoas, 17…, 53…") ficam sem os dados. Ali o
   PDF não tem figura, o dado está só no comando.
3. **Figuras vetoriais não são recortadas.** O parser só recorta imagem
   raster. Há desenho vetorial grande em `072_STM_005_0*`, `072_STM_010_0*`
   e `094_PF_005_0*` (gráficos/tabelas desenhados), que somem.
4. **Assunto no rodapé.** O caminho matéria › assunto › subassunto fica no
   `<footer>` do card; deve ir para o topo.
5. **Filtros de valor único.** A lista só tem `orgao`, `nivel`,
   `historico` e um `no_id`. Falta multisseleção com busca para cargo, ano,
   matéria, assunto e subassunto (estilo Gran: lista pesquisável com
   checkbox e chips do que foi marcado).

- `[x]` **5G.1 — Parágrafos:** `juntar_linhas` quebra parágrafo (`\n\n`)
  quando a linha começa com recuo de 1ª linha em relação à margem do bloco
  (medir por `Linha.x0`, mesma régua de cluster/moda da 5C.1); preservar
  numeração de linha impressa na margem, se houver. Reextrair (determinístico,
  sem LLM), conferir que a chave da 5D não muda (hash do enunciado igual) e
  renderizar `\n\n` como `<p>` no `_anexos.html`. Teste com o texto da CD.
- `[x]` **5G.2 — Comando e assunto no topo:** card mostra o comando
  (`secao`) acima do enunciado (uma vez por grupo, igual ao "mesmo texto"),
  e o caminho matéria › assunto › subassunto no cabeçalho. Contrato da API:
  `secao` já existe no modelo, conferir se sai no JSON.
- `[x]` **5G.3 — Figuras vetoriais:** detectar agrupamentos de
  `page.get_drawings()` acima de um tamanho mínimo e recortar a região como
  PNG (mesmo dono/vínculo das figuras raster). Conferir os 3 cadernos acima.
- `[x]` **5G.4 — Filtros multisseleção:** API aceita listas (`ano`,
  `cargo`, `orgao`, `no_id`, …), facetas devolvem contagem por valor; UI com
  painel pesquisável + checkbox + chips removíveis, URL compartilhável.
  Atualizar `site/openapi.json`.
- `[x]` **5G.5 — Item que engole o preâmbulo do grupo seguinte:** em
  `072_STM_005_01`, o item 64 absorveu o preâmbulo ("Da contabilidade de uma
  entidade hipotética…") e as duas tabelas do grupo 65–68, sem alerta. Único
  caso no piloto, mas é regra do parser e se repete em layout igual.
  (1) Diagnosticar a regra exata; (2) quando o comando muda, o trecho entre o
  fim do item e o novo comando vira texto-base do grupo seguinte;
  (3) alerta bloqueante (`utilizavel=false`) para o padrão residual; (4) teste
  com a página real. Enunciados dos outros itens inalterados.
- **Pronto quando:** as 79 questões que citam parágrafo batem com o PDF, os
  itens 24–26 de `094_PF_CB2_01` mostram os dados, os 3 cadernos com
  desenho vetorial mostram a figura e é possível filtrar por 2 anos + 2
  cargos + 3 assuntos ao mesmo tempo.
- **Validação do "pronto quando" (2026-10-06):** reextração completa
  (`extrair_questoes --reprocessar`, 70/70 cadernos, 2.800 itens). Chaves da
  5D, gabaritos, `secao` e `utilizavel` iguais aos de antes; só o enunciado
  do STM 64 mudou (5G.5), com o hash atualizado em
  `classificacao_questoes.json` (mesmo nó aprovado). As 88 questões que citam
  parágrafo ou linha têm texto-base com parágrafos, e a contagem cobre o
  maior ordinal citado (`072_STM_CG4_01`: 7 parágrafos, igual ao PDF).
  PF_CB2 24–26 mostram o comando com os dados. Figuras vetoriais: STM_005
  0→3, STM_010 0→2, PF_005 1→4. Filtro 2024+2025 × 2 cargos × 3 assuntos: 44
  questões, igual ao SQL, com chips e facetas no Chromium headless. Corrigido
  na validação: (a) `vw_questoes.figuras` não trazia as figuras do
  texto-base (as tabelas não apareciam no site); (b) a reextração recria as
  views e apagava os GRANTs do site (500 em toda a lista): `criar_schema`
  agora guarda e reaplica os GRANTs; (c) o mesmo texto quebrado em
  parágrafos diferentes em dois cadernos virava duas questões canônicas (LP
  139 → 146): a chave canônica ignora espaços/quebras (2.676 grupos, igual a
  antes). Só existe 2025 na base, então o "2 anos" testa a lista na API.

---


## Etapa 5H: Card da questão e filtros no formato Gran (cor teal)
> **Por que existe (2026-10-06):** o dono pediu o card e os filtros do site no
> formato do Gran Questões, com teal no lugar do laranja. Plano completo em
> `docs/planos/plano-etapa-5h.md`. **Cada subetapa é uma sessão.**

- `[x]` **5H.1 — Cor e ID curto:** token `destaque` (teal) em
  `tailwind.config.js`, todos os `*-blue-*` trocados, CSS refeito. Campo
  `codigo` (`Q` + 8 hex do SHA-1 da chave) em `QuestaoResumo`, rota
  `/q/{codigo}` → 301 para a canônica, teste de colisão nas 2.800 chaves,
  `openapi.json` reexportado.
- `[x]` **5H.2 — Card novo:** barra cinza (posição · ID · matéria ▸ assunto),
  linha Ano/Banca/Órgão/Prova com links de filtro, "Texto associado ⊕",
  radios Certo/Errado + Responder (macro `form_resposta`), barra de ações
  (estatísticas, parecidas, PDF, notificar erro) e "Fonte: CEBRASPE".
- `[x]` **5H.3 — Filtros no topo:** dropdowns com busca rápida, aplicação só no
  botão Filtrar, recontagem ao fechar (`/questoes/facetas`), barra
  "Filtrar por:", simples/avançado, linhas "Excluir questões" e "Questões com".
- `[x]` **5H.4 — Filtros novos no backend:** `texto` (palavra-chave com
  `unaccent`) e `com` (texto associado, figuras) na API e nas facetas; termo
  igual a um ID curto leva à questão.
- `[x]` **5H.5 — Validação e documentação:** Chromium headless (1280 e 390 px),
  `docs/guia-teste-navegador.md`, ADR-035, `CLAUDE.md`.
- **Pronto quando:** o card da lista, do detalhe e da revisão do simulado segue
  o layout em teal; toda questão tem ID curto único e `/q/<ID>` abre a
  questão; filtrar por 2 matérias + 1 órgão + "excluir anuladas" +
  palavra-chave só busca ao clicar Filtrar e dá o mesmo total que o SQL;
  nenhum `blue-` sobra nos templates; ruff e pytest verdes.

---


## Etapa 6: Teste Piloto e Validação
> **Depende das Etapas 5B.1–5E** (árvore, classificação e estatísticas; a 5A foi concluída em 2026-09-23). O site (5F) pode seguir em paralelo depois da 5E.

- `[x]` Rodar o fluxo completo ponta a ponta (Crawler → Downloader → Parser
  → LLM → DB) para **1–2 concursos grandes de 2025 já encerrados** (ex:
  INSS, PF).
  > **Nota de Progresso (2026-09-21):** O pipeline de extração e validação
  > (Crawler → Downloader → Parser → LLM → Validação/Datasette) já foi executado
  > e homologado com sucesso absoluto em **5 concursos de 2025** (`PF_25_ADM`,
  > `TCU_25_TEFC`, `IBAMA_25`, `STM_25` e `CD_25_NS`), totalizando 150 chunks com 100% de
  > sucesso e 0 alertas bloqueantes após a reconciliação do ADR-025 (2 informativos: PF e STM). A gravação no Postgres (Etapa 5) já foi feita em
  > 2026-09-22; a conclusão formal da Etapa 6 depende da revisão humana e da
  > aprovação no banco.
- `[x]` Critério de sucesso explícito: 0 exceções não tratadas no log; 100%
  dos PDFs mapeados efetivamente baixados e validados; taxonomia extraída
  revisada manualmente e aprovada.
- `[x]` Inspecionar `logs/scraper_cebraspe.log` para checar saúde do
  processo (sem bloqueios, sem timeout).
- `[x]` Aprovar a base no banco e só então considerar liberar a rotina para
  rodar em lote — agendamento (cron/systemd timer) fica para decisão
  posterior, fora deste piloto.
- **Concluída em 2026-10-06.** PDFs: 158/158 dos manifestos presentes e
  válidos (`%PDF-`) nos 5 concursos. Taxonomia: 150/150 chunks `sucesso`,
  0 alertas bloqueantes e os 5 editais `APROVADO` (ADR-028), com os 5
  concursos `aprovado` no banco. Questões: fila 145/145 `concluido`,
  2.800 itens (2.781 utilizáveis). Log: os testes gravavam no log de
  produção (661 MB, ~8 mil ERROR de cenários simulados como `x.test` e
  `XX_25`). O `conftest.py` da raiz agora tira o arquivo do logger durante o
  pytest, e o log antigo foi arquivado em
  `logs/scraper_cebraspe.ate-2026-10-06.log.gz`. Com o log limpo,
  `atualizar_revisao` + `extrair_questoes --reprocessar` deram 0 ERROR e
  0 Traceback, só 3 WARNING esperados (editais administrativos fora da fila).
  Nenhum ERROR do log antigo cita concurso ou URL real. O agendamento em lote
  continua para decisão posterior.

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

## Etapa 8: Múltipla escolha, inventário 2020→hoje e ingestão em lotes
> **Detalhes e plano de execução:** [`plano-etapa-8.md`](plano-etapa-8.md). O arquivo é
> autocontido; uma sessão (conversa) por subetapa.
>
> **Decisões do dono (2026-10-08):** inventário persistido de **2020 até hoje** com os anos
> disponíveis mapeados pelo crawler; ingestão em **lotes de 2 concursos** com pausa de revisão
> e retomada; ordem dos anos **2025 → 2026 → 2024 → 2023 → 2022 → 2021 → 2020**; suporte a
> **múltipla escolha** antes de qualquer lote novo (hoje tudo é Certo/Errado).
- `[x]` **8.0 Inventário** (concluído e revisado em 2026-10-08): classificador fino de link
  (`src/inventario.py`), `scripts/inventariar_concursos.py`, `inventario/anos.json` (497 concursos
  únicos), `inventario/concursos.jsonl` (346 concursos de 2020+, todos mapeados, 0 com erro,
  18.248 PDFs), tabelas `inv_concurso`/`inv_pdf`, view `vw_inventario_ano` e
  `inventario/RELATORIO.md` (cobertura por ano, formato da amostra e os 3 cadernos ME para a 8.M).
  - `[x]` Revisão: mapeamento completo (era 67 de 337), tipo `prova_outra` (oral, didática,
    tribuna, desempenho), escrita/subjetiva/prática como discursiva, comunicado/relação/edital
    como administrativo, `\bprovas?\b` em vez de substring; `caderno_objetivo` 2.953 → 2.642.
    Reclassificação offline (`--reclassificar`) a partir de `pdfs[].texto`.
  - `[x]` Formato: "julgue" só conta como CE sem alternativas A–D na mesma questão. Amostra
    refeita (todos de 2025/2026 com caderno + 3 por ano de 2020–2024): 83 cadernos, 42 CE e
    41 ME, 0 misto, 0 `?`. Os 42 objetivos do piloto continuam CE.
  - `[x]` Ano de 4 dígitos no slug só `_19YY`/`_20YY`; testes que leem `data/` pulam sem os
    dados.
  - `[ ]` Pendente para a 8.1: `map_pdf_links` (download) ainda usa a classificação antiga;
    "PROVA PRÁTICA – OPÇÃO …" de técnico (prova manual) entra como `caderno_discursivo`;
    caderno único "PROVAS OBJETIVAS E DISCURSIVA" entra como objetivo.
  - `[x]` Pausa 0, parte `incluir` (2026-10-09, ADR-037): os 55 alertas do relatório foram
    validados ao vivo (contagem de PDFs igual nas 55 páginas). O que não entra no site está
    em `inventario/exclusoes.json` (16 concursos: cancelado, só títulos, página vazia,
    discursiva sem caderno, exame de certificação e páginas só de curso de formação), e
    PDF de curso de formação fica fora mesmo em concurso incluído (97 PDFs em 19
    concursos). Classificador corrigido: `caderno_com_gabarito` (158), justificativa e
    recurso como administrativo, abertura do SEBRAE ("Comunicado nº 1"), "QUESTÃO
    DISCURSIVA" como caderno. Prova não aplicada vira `aguardando_prova` (26), e o
    relatório fica com 0 alertas reais. Falta decidir o tamanho do lote e os concursos em
    andamento.
- `[x]` **8.M Múltipla escolha**:
  - `[x]` Layout `caderno_com_gabarito` (questão e gabarito no mesmo PDF; CAESB_24 é ME, ADR-038).
  - `[x]` Schema e persistência (`src/sql/schema_estatisticas.sql`, `src/questoes_writer.py`, `src/stats_writer.py`): `questoes.tipo`, `alternativas jsonb`, check `A-E` e `X`, hash 5D com alternativas para ME e estável para CE.
  - `[x]` Parser de gabaritos (`src/gabarito_parser.py`): `LETRAS_VALIDAS` expandido, cabeçalho `Questão`/`Item`, validação com PDFs reais.
  - `[x]` Parser de cadernos ME (`src/prova_parser.py`): `_eff_y0` em blocos, segmentação de enunciados e alternativas A–E (multilinhas, figuras), calibração 100% verde nos 3 PDFs reais da amostra (`BANRISUL_25`, `SEBRAE_26_PSE_1`, `SEFA_PR_25`).
    - `[x]` Revisão (2026-10-09): rótulo "Texto X" no meio da seção era engolido pela
      alternativa E, e selos "Questão N" criavam texto-base vazio. Corrigido com testes de
      contagem exata nos 3 PDFs; piloto C/E re-parseado com 0 diferenças.
      **Decisão do dono (2026-10-09):** no ME, o texto-base vale para quem cita o rótulo; o
      texto que abre a seção vale para a seção inteira; o texto no meio da seção vale só para
      a questão seguinte e para as que o citam. A herança "até a próxima seção" do C/E daria o
      Texto 1A3 do `SEFA_PR_25` (seção única) a 23 questões sem relação.
  - `[x]` Classificação 5D (`scripts/classificar_questoes.py`, `src/classificacao.py`): alternativas no prompt LLM e hash 5D.
  - `[x]` Site e simulado (`site/`, ADR-038): modelos Pydantic, respostas A–E validadas pelo
    tipo da questão (letra fora do formato é recusada na API e no form e vira branco no
    simulado), pontuação +1/−1 no C/E e +1/0 no ME, radios em teal, gabarito em destaque na
    correção, faceta "Formato" e OpenAPI.
  - `[x]` Revisão de gabarito e schema (2026-10-09): código de caderno com sublinhado na sigla
    (`169_SEBRAE_26_PSE_1_CG1_02`) reconhecido; tipo da grade pelo rótulo (`Item` → C/E,
    `Questão` → ME) com letras validadas por tipo; constraints `questoes_gabarito_tipo_check`
    e `questoes_alternativas_tipo_check`; `vw_comparativo_nivel` com ME e média de percentuais
    por concurso × cargo. 42 grades do piloto e 2.530 questões re-parseadas sem diferença.
  - `[x]` **Ligação prova ME ↔ gabarito** (`stats_writer.py`, 8.M/S1):
    - SEBRAE_26_PSE_1 ligado pelo sufixo `_NN`/TIPO e texto do link;
    - SEFA_PR_25: `discursiva_por_cargo` confere o tipo e evita ligar gabarito objetivo a discursiva;
    - `GradeGabarito.tipos` chega ao `prova_parser`; `PADRAO_CODIGO_CADERNO` aceita `CG` sem dígito.
  - `[x]` `fn_prova_cobra` (8.M/S2): agregação pela média por concurso × cargo. **Revista em
    2026-10-10** (ADR-039): o básico compartilhado entra N vezes na média; ver 8.M.1.
  - `[x]` **Gate aprovado (2026-10-10, S4)**: carga real ME `SEFA_PR_25` no `cebraspe_gate` (380 itens ME), piloto inalterado (2.800 itens, 129 anuladas, 3.029 apontamentos), suíte completa verde (1.276 testes passando, `make check` 100%).
  - `[x]` Sem registro no Gate (achado da arrumação de 2026-10-10, KAN-50): passada no
    Chromium headless com questão ME real do `SEFA_PR_25` (cópia descartável do
    `cebraspe_gate`, apagada no fim). Filtro "Formato", responder/corrigir e simulado do cargo 1
    conferidos, com 0 erro de JS (42 certas, 41 erradas e 41 em branco dão 42 de 124). O edital
    nº 1 (subitem 8.11.2, a e b) dá 0,00 ponto à resposta errada, então o erro no ME não desconta.
    Achados que ficam para depois:
    - `[ ]` Peso por prova no simulado: o edital do SEFA (8.11.2) dá 1,00 ponto por item na P1
      (conhecimentos gerais, 80 questões no cargo 1) e 1,50 na P2 (específicos, 50), máximo
      80 + 75 = 155. O simulado dá peso 1 a tudo (130 − 6 anuladas = 124). O peso vem do edital,
      por prova (P1/P2), e não existe no banco; conferir também os editais C/E do piloto.
      Generalizado no card KAN-53 (regra de pontuação por banca, formato e prova, vinda do
      edital: C/E do CEBRASPE +1/−1; ME do CEBRASPE varia por edital, com desconto em alguns e não no
      SEFA_PR_25; discursiva com quesitos; outras bancas). Tarefa futura (dono, 2026-10-11).
    - `[ ]` Textos do ME: o KPI "Nota CEBRASPE" mostra "certas − erradas", o subtítulo da lista
      diz "padrão certo/errado" no filtro ME, e a introdução do simulado só descreve +1/−1.
  - Plano das sessões arquivado em [`docs/planos/plano-etapa-8m.md`](docs/planos/plano-etapa-8m.md).
- `[x]` **8.M.1 Incidência em dois níveis** (concluída em 2026-10-12, KAN-28, ADR-039; plano arquivado
  em [`docs/planos/plano-etapa-8m1.md`](docs/planos/plano-etapa-8m1.md)). Decisão do dono (2026-10-10): a média por
  prova (concurso × cargo) da S2 conta o mesmo caderno básico uma vez por cargo, e o concurso
  com mais cargos domina (no piloto, PF_25_ADM pesa 48% e TCU_25_TEFC 3%). Passa a ser
  % do nó na prova → média das provas dentro do concurso → média entre concursos (cada edital
  pesa 1).
  - `[x]` `fn_prova_cobra` e `vw_comparativo_nivel` com a regra nova; contagens inalteradas.
    **Prova distinta** (brainstorm do dono, 2026-10-10, KAN-28): cargos com o mesmo conjunto de
    questões canônicas no escopo, sob os filtros, contam como uma prova só (assinatura = `md5`
    dos `questao_canonica_id`; um cargo representante). Casos dos lotes: SEE_PE_22 (um
    específico para os cargos 3 a 47) e IPAAM_25 (um básico para os cargos 1 a 19). A
    `vw_comparativo_nivel` ganhou `concursos_medio`/`concursos_superior`. O banco ainda tinha
    a `fn_prova_cobra` de antes da S2 e foi atualizado.
  - `[x]` Testes: caso 3 cargos com básico compartilhado × 1 cargo (50% cada), 3 cargos de
    prova idêntica + 1, anulada na assinatura, filtro `basico` e filtro `p_nivel`; as 31
    provas filtradas uma a uma sem diferença (são 31 provas distintas no piloto).
  - `[x]` Textos do site (`modelos.py`, rotas, templates) e `site/openapi.json`.
  - Conferido (2026-10-10): ranking sem filtro igual ao ADR-039; PF_25_ADM cargo 1 segue com
    AOF (17,80%); `make test-all` 1252 passados (+31 pulados, 1 xfail). Muda o % dentro da
    matéria do básico (LP › Reescrita de frases: 9,13 → 15,76) e o recorte `basico` (Ética
    16,66 → 11,65; Informática 7,10 → 3,43). Números completos no ADR-039.
  - **Pronto quando:** o ranking de matérias sem filtro bate com o ADR-039 (LP 13,81%;
    Dir. Adm. 10,59%; Ética 4,81%; Adm. Geral 4,20%) e `make test-all` está verde.
- `[ ]` **8.C Coleta dos concursos ME de 2025** (KAN-55; prioridade do dono, 2026-10-12; plano
  autocontido em [`plano-etapa-8c.md`](plano-etapa-8c.md), uma sessão por item). Nenhuma
  questão ME está no banco de produção: o Gate da 8.M carregou o `SEFA_PR_25` só na cópia
  `cebraspe_gate`. Alvo: os 11 concursos ME de 2025 encerrados do inventário. Os ME de 2026 e
  os em andamento ficam para decisão do dono.
  - `[x]` C0 (KAN-30) Download guiado pelo inventário: `map_pdf_links` com o classificador fino,
    `pdf_vai_para_o_site` e `exclusoes.json`; preservação de texto de links para editais/gabaritos;
    seleção de edital canônico (`escolher_edital_extracao`); "PROVA PRÁTICA – OPÇÃO" e o caderno único
    objetivo + discursivo (pendências da 8.0). Reclassificação aplicada (5 PDFs EMBRAPA_24). Piloto inalterado.
  - `[ ]` C1a (KAN-56) Calibração `SEFA_PR_25` + `BANRISUL_25`: download, edital (LLM), questões no
    banco, 3 questões conferidas no PDF e roteiro `docs/runbook-lote.md`. Pausa: editais.
    Feito em 2026-10-12 (falta só a pausa do dono): 18 + 21 PDFs iguais ao inventário; editais
    com 22 e 28 chunks, 0 falhas, 0 alertas, US$ 0,018; 380 + 230 questões ME (5 alternativas,
    gabarito A–E, 18 + 5 anuladas) e 5 discursivas no banco. Correções: sub-matéria em romano e
    nível pela escolaridade (edital), área vira cargo (decisão do dono, ADR-038) e cabeçalho
    de matéria ME pelo layout (23 alternativas E traziam o cabeçalho seguinte). Piloto
    inalterado. Revisão antes da aprovação (2026-10-12): o LLM descartou 128 subitens de 3º/4º
    nível no ECONOMIA do SEFA e 6 no CONTABILIDADE, e manteve um tópico excluído por retificação;
    a validação só olhava o 1º nível (0 alertas). Agora: item "excluído por meio do Edital" sai
    antes do LLM, `subitem_ausente` bloqueante em todos os níveis (ADR-017) e reinjeção
    determinística de subitem (ADR-025); SEFA com 0 alertas. A validação nova acha 22 perdas
    reais no piloto (PF 12, STM 3, IBAMA 7), sem reconciliar: decisão do dono.
    **Pausa do dono:** aprovar os 2 editais (`status_revisao_humana`).
  - `[ ]` C1b.0 (KAN-64, **urgente**, dono em 2026-10-12) Árvore: o mesmo conceito espalhado em
    vários pais. LGPD tem 13 questões em 6 nós de 4 disciplinas; LRF está em 6 disciplinas; o BSC
    está em 4 nós. A incidência e o filtro do site se dividem entre os pedaços.
    `detectar_homonimos` só compara irmãos: há 229 grupos de nome igual sob pais diferentes, muitos
    legítimos ("Conceito", "Disposições gerais"). Fazer: detector de dispersão (regra, com lista de
    nomes genéricos), relatório para o dono, fusões aprovadas por ele, carga e conferência no site.
    Antes da C1b, que liga os itens novos do lote aos nós.
    Fase 2 (dono em 2026-10-12, ADR-030): regra "um conceito com nome próprio, um lugar".
    DIREITO ADMINISTRATIVO › Acesso à informação e proteção de dados › {LAI 8, LGPD 13} (21
    questões; LAI de Arquivologia e TI fundida). Travas: `--criar` recusa norma repetida,
    `--mapear` avisa, `test_normas_consolidadas_em_um_no_so` (LGPD, LAI, LRF) e o P6 do runbook
    (detector depois de cada lote). Falta: as 184 propostas com o dono (ex.: Lei 8.112 em 3 nós).
  - `[ ]` C1b.1 (KAN-65, **prioridade alta**, dono em 2026-10-12) Árvore: gestão estratégica (BSC,
    SWOT, GUT, 5W2H, Canvas, referencial estratégico, indicadores) numa casa só, com um subassunto
    por ferramenta; nomes compostos ("Ferramentas…: SWOT; BSC…") apontam para as partes (ADR-030).
    Antes da C1b: a matéria ESTRATÉGIA do BANRISUL_25 cai nesses nós.
  - `[ ]` C1b (KAN-57) Mesmo lote: árvore (pausa: curadoria), classificação, site no Chromium.
  - `[ ]` C2 (KAN-31, KAN-32) Orquestrador mínimo no **Dagster** (decisão do dono em 2026-10-13,
    KAN-67): sessões D5a e D5b da Etapa 9 (`plano-etapa-9.md`), com o alerta "ME sem texto-base"
    e `--concurso` no `classificar_questoes`. Checklist na seção Etapa 9.
  - `[ ]` C3 (KAN-58) `SEBRAE_25_PSE_1` + `UNIVESP_25_PSS`
  - `[ ]` C4 (KAN-59) `IPAAM_25` + `SEMA_AM_25`
  - `[ ]` C5 (KAN-60) `PGE_ES_25_PROCURADOR` + `PGE_PI_25`
  - `[ ]` C6 (KAN-61) `SEFAZ_SE_25_AUDITOR` + `TCE_MG_25`
  - `[ ]` C7 (KAN-62) `SEED_SE_25_PROFESSOR`
  - `[ ]` C8 (KAN-63) Fechamento: views da 5E com 16 concursos, textos ME do site (pendência da 8.M),
    `CLAUDE.md`/`task.md` e arquivar o plano.
  - **Pronto quando:** os 11 concursos ME de 2025 estão `aprovado`, o piloto segue inalterado
    (2.800 itens, 129 anuladas, 3.029 apontamentos) e `make test-all` está verde.
- `[ ]` **8.M.2 Estatísticas por recorte: drill-down e filtros** (pedido do dono, 2026-10-10,
  KAN-28). Usa a regra de dois níveis da 8.M.1. Usos-alvo: (1) "para Língua Portuguesa, o que a
  banca X cobra no ano X, no assunto X ou subassunto"; (2) "no concurso X, na matéria X, o que
  mais caiu no assunto X e em quais subassuntos", podendo listar as questões. No recorte de
  concurso importam os dois números: % médio (dois níveis) e nº de questões distintas.
  - `[ ]` Filtros de banca, ano e órgão no `FiltroEstatistica`, em `/estatisticas`,
    `/materias/{id}` e na API (a `fn_prova_cobra` já aceita `p_banca`, `p_orgao` e `p_ano`).
  - `[ ]` Nível médio/superior (pedido do dono, 2026-10-10) em todos os recortes e em todos os
    degraus do drill-down, combinável com banca/ano/órgão/concurso. Já existe em
    `/estatisticas` e `/materias/{id}`; falta garantir que o link para a lista de questões e
    cada degrau mantenham o filtro.
  - `[ ]` Drill-down matéria → assunto → subassuntos do assunto → lista de questões
    (`/questoes` com os mesmos filtros). Hoje `/materias/{id}` vai direto da matéria para os
    subassuntos; falta o degrau do assunto. Cada degrau mostra o % (dois níveis, regra da
    8.M.1) e o nº de questões distintas.
  - `[ ]` Separação básico × específico no recorte de concurso (filtro ou colunas).
  - `[ ]` Rótulo "média de N concursos / M provas" ao lado do %. Pede colunas novas na
    `fn_prova_cobra` e muda o contrato da API e o `site/openapi.json`.
  - `[ ]` Recorte visível (pedido do dono, 2026-10-11, card KAN-54): o botão "Estatísticas"
    da questão (`_card_questao.html`) abre `/materias/<id>` sem filtro e perde o contexto.
    Ele passa a levar banca/concurso/ano/nível/tipo da questão, já selecionados. Também entram
    uma faixa de recorte com chips removíveis e "média de N concursos", o % principal dentro
    da disciplina (somando 100% com "Outros") e o "% da prova" como segundo número.
  - **Pronto quando:** os dois usos-alvo acima são respondidos no site, sem SQL à mão, também
    com o filtro de nível, e `make test-all` está verde.
- `[ ]` **8.1 Orquestrador de lotes** (o núcleo sai no Dagster, na 8.C/C2 = Etapa 9/D5a e D5b;
  aqui fica o resto como schedule, sensor e config do Dagster: ordem geral dos anos, próximo
  lote, tamanho do lote e teto de custo). Texto original, antes da decisão pelo Dagster: `scripts/lote_concursos.py` (`--proximo`, `--lote`,
  `--aprovar`, `--status`), estado em `inventario/lotes.json`, checagens automáticas e relatório
  por lote.
  - `[ ]` Checagem automática (pedido do dono, 2026-10-09): alerta para questão ME cujo
    enunciado ou alternativas mencionam "texto", "tabela", "figura", "gráfico" ou "quadro"
    e que ficou sem texto-base e sem figura. Cobre o risco da regra de herança do ME
    (questão que usa um texto sem citar o rótulo e não vem logo depois dele). Excluir o
    caso em que o "texto precedente" está no próprio enunciado (BANRISUL Q22, SEFA_PR Q11
    e Q50). O alerta entra no relatório do lote para revisão na pausa, sem bloquear.
- `[ ]` **8.2+ Lotes**: 2025 → 2026 → 2024 … 2020, 2 concursos por vez; 1º lote de cada ano é
  de calibração.
- **Pronto quando:** todos os concursos marcados `incluir` no inventário estão `aprovado`, as
  views da 5E reconciliam e a suíte completa está verde.

## Etapa 9: Documentação viva e Dagster como C2

Plano autocontido em [`plano-etapa-9.md`](plano-etapa-9.md), uma sessão por item. Card da
etapa: KAN-67. Decisões do dono (2026-10-13): Dagster já como C2 da 8.C; docs em paralelo à
8.C numa worktree própria; site em `docs.projetoathos.com.br` atrás do Cloudflare Access; D3
aprovado com um núcleo de regras no `CLAUDE.md`.

Trilha A, documentação (em paralelo):

- `[x]` D1 (KAN-68) Esqueleto do MkDocs (`site_dir: build/docs`), alvos no `Makefile`,
  `mkdocs build --strict` no `make check` e container `scraper-cebraspe-docs` no domínio.
  **Pronto quando:** o site sobe local e no domínio, os links resolvem e o `--strict` passa.
  Estado: concluída e aprovada (2026-10-13); ADR-040.
- `[x]` D2 (KAN-69) Registro de etapas, checagens e regras (`src/registro/`, também fonte do
  Dagster); páginas e Mermaid gerados; teste guarda. **Pronto quando:** um script novo sem
  entrada no registro quebra o teste e as páginas batem com o código.
  Estado: concluída e aprovada (2026-10-13); ADR-041. `make docs-gerar` regera `docs/tecnico/`.
- `[ ]` D3 (KAN-70) Contexto para agentes: índice por tarefa e `CLAUDE.md` enxuto, com o núcleo
  de regras e links. **Pronto quando:** um agente novo acha a regra e o runbook de uma tarefa a
  partir do `CLAUDE.md`, sem ler o arquivo inteiro.
- `[ ]` D4 (KAN-71) Documentação executiva (visão, C4, números, decisões, roadmap) e PDF.
  **Pronto quando:** o dono envia o PDF a alguém de fora sem explicar o projeto antes.

Trilha B, Dagster (é a C2 da 8.C, depois da C1b):

- `[ ]` D5a (KAN-31) Infra e assets: containers, banco `dagster`, domínio com Access, assets
  por concurso gerados do registro e `--concurso` no `classificar_questoes`. **Pronto
  quando:** o lote da C1 em modo conferência não muda nada e a UI abre no domínio.
- `[ ]` D5b (KAN-32) Asset checks, portões do dono, detector de dispersão e relatório
  `inventario/lotes/lote_NN.md`. **Pronto quando:** o relatório do lote da C1 sai com as
  checagens verdes e um teste mostra o portão travando a etapa seguinte.

## Pendências posteriores (fora de etapa)

- `[ ]` **Busca do site: palavra-chave com classificação, sugestões, cascata sem trava e
  normas num lugar só** (pedido do dono, 2026-10-12; card **KAN-66**). Nada executado ainda.
  1. **Norma consolidada num lugar só, também nas questões.** `STM_25|072_STM_004_01|56`, `57`
     e `58` são de LAI e estão em `S-d1e73b29ac` (COMUNICAÇÃO SOCIAL › Comunicação pública ›
     Legislação): mover para `S-256fbea4b7` (LAI) com `curar_classificacao --mapear` (LAI de 8
     para 11) e conferir a 4ª questão desse nó. Padrão: questão de norma consolidada (LAI,
     LGPD, LRF…) sempre aponta para o nó da norma, venha do caderno que vier. Teste guarda:
     questão cujo enunciado cita a norma (sigla como palavra inteira, número com ou sem
     ponto, nome por extenso) tem o nó da norma entre os apontamentos.
  2. **Palavra-chave = texto + classificação.** Hoje procura só no enunciado e no comando.
     Medido (questões no nó / achadas / do nó que ficam de fora): LGPD 13/11/6; LAI 8/5/8;
     12.527 8/7/6; 12527, 7.724, 7724 8/0/8; LRF 18/4/15. Novo: termo que casa nome ou
     apelido de nó (regra do `/api/v1/busca`) traz também as questões classificadas no nó e
     nos descendentes. Sigla curta como palavra inteira ("LAI" não casa "laicização"); ponto
     de milhar e "nº" fora da comparação, igual à busca rápida.
  3. **Sugestões ao digitar na palavra-chave:** lista de assuntos que casam, com caminho e
     total (ex.: "LGPD → Dir. Administrativo › Acesso à informação e proteção de dados (13)");
     o clique marca o filtro. A lista de questões continua só no Filtrar (ADR-035).
  4. **Tirar a trava da cascata:** Assunto e Subassunto passam a aceitar busca e marcação sem
     disciplina marcada (hoje desabilitados até marcar o pai, 5H.3). Com o pai marcado, a
     lista segue restrita aos filhos. Atualizar ADR-035 e `site/tests/test_filtros_cascata.py`.

  Pronto quando: "LGPD", "LAI", "12527" e "LRF" na palavra-chave trazem todas as questões do
  nó; conferido no Chromium headless; `make check` verde; piloto inalterado (2.800 itens, 129
  anuladas).

- `[ ]` **Incidência de subassunto com vários recortes** (pedido do dono, 2026-10-09).
  A parte de filtros e recortes (banca, ano, órgão, nível, drill-down) passou para a **8.M.2**.
  Aqui fica o que não coube nela: o lado a lado dos recortes, `p_formato` e o gabarito C/E.
  Mostrar lado a lado, para cada nó (matéria › assunto › subassunto):
  - % na **prova** (concurso × cargo) — já existe em `vw_prova_cobra_no`;
  - % **geral da banca** (todos os concursos) — já existe em `fn_prova_cobra(p_banca => ...)`,
    como média de percentuais (em dois níveis depois da 8.M.1); falta expor junto do % da prova no site;
  - % de um **assunto/matéria filtrado por banca** (e órgão, ano, cargo, nível).

  Filtros novos que faltam em `fn_prova_cobra` e no site:
  - `p_formato` (`certo_errado` | `multipla_escolha`): ME e C/E contam igualmente por padrão
    (decisão de 2026-10-09);
  - **gabarito C ou E**. Confirmar com o dono antes de implementar se é (a) incidência só
    entre itens de gabarito C (ou E), ou (b) a proporção C × E dentro do nó (hoje em
    `vw_certo_errado_por_no`, só para C/E).

  Regra: agregar entre concursos sempre em dois níveis (média das provas dentro do concurso,
  depois média entre concursos), nunca pela soma bruta (decisões de 2026-10-09 e 2026-10-10,
  ADR-039).
- `[ ]` **Comparativo de cargo nas estatísticas** (decisão do dono, 2026-10-10: fica para
  depois; card KAN-52 no Jira). Três leituras ainda a escolher com o dono:
  - (a) cargos do mesmo concurso lado a lado (ex.: PF_25_ADM cargo 1 × cargo 5), viável com os
    dados de hoje;
  - (b) o mesmo cargo entre editais (ex.: Agente da PF 2021 × 2025), que pede uma "carreira
    canônica" com regra + curadoria, como a árvore, porque hoje `dim_cargo` tem uma linha por
    nome de edital;
  - (c) nível médio × superior, que já existe na `vw_comparativo_nivel` e falta expor no site.
