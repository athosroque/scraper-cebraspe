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
  (apontando para `study-rag-db`) e `LITELLM_BASE_URL`/`LITELLM_API_KEY`.
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
- `[ ]` **Análise Exploratória Manual:** baixar amostras de editais brutos
  (via crawler) e decidir quais seções extrair além de
  "Conhecimentos/Objetos de Avaliação" — registrar a decisão (mesmo que
  informalmente, em notas) antes de codificar o parser.
- `[ ]` Criar `src/edital_parser.py` (PyMuPDF) para recortar as seções
  validadas. Atenção: quadros matéria×cargo costumam ser multi-coluna, e
  extração de texto simples do PyMuPDF pode embaralhar a ordem — validar
  visualmente antes de confiar no output em lote.
- `[ ]` **Chunking:** separar blocos por cargo, regras de pontuação,
  disciplinas etc.
- `[ ]` **Extração LLM:** enviar os chunks ao LLM reaproveitando o
  `llm-gateway` já existente (`LITELLM_BASE_URL`, modelo `glm-5.3-flash`) —
  não instanciar client para outro provedor.
- `[ ]` **Revisão Humana Contínua:** checkpoint onde a saída do LLM é
  revisada manualmente em pelo menos 1 edital piloto antes de automatizar em
  lote.

## Etapa 5: Modelagem do Banco de Dados Estatístico
- `[ ]` Usar **PostgreSQL 16** — já é o padrão do portfólio (não reabrir
  essa avaliação) — na mesma instância `study-rag-db` do `study-rag-agent`
  (rede Docker `homelab_default`, porta publicada `5434`, banco
  `study_rag`).
- `[ ]` Desenhar **star schema**: dimensões (`materias`, `topicos`,
  `orgaos`, `cargos`, `anos`) e fatos (`concursos`, `cargos_editais`,
  `taxonomia_itens`), com colunas `JSONB` para metadados irregulares que não
  justificam dimensão própria ainda.
- `[ ]` Cada tabela nova referencia **`itens_estudo`** (nome real da tabela
  — atenção, não é `items_estudo`) por **FK opcional**, sem alterar suas
  colunas existentes.
- `[ ]` Criar `src/stats_writer.py` para gravação idempotente
  (`CREATE TABLE IF NOT EXISTS`, seguindo o padrão já usado em
  `study-rag-agent/src/db.py`).
- `[ ]` Criar tabela/fila `pendente` para os PDFs de Provas e Gabaritos
  baixados. O consumidor dessa fila (pipeline de extração de questões) é
  **fora do escopo deste projeto** por enquanto — só deixar a fila pronta e
  populada.

## Etapa 6: Teste Piloto e Validação
- `[ ]` Rodar o fluxo completo ponta a ponta (Crawler → Downloader → Parser
  → LLM → DB) para **1–2 concursos grandes de 2025 já encerrados** (ex:
  INSS, PF).
- `[ ]` Critério de sucesso explícito: 0 exceções não tratadas no log; 100%
  dos PDFs mapeados efetivamente baixados e validados; taxonomia extraída
  revisada manualmente e aprovada.
- `[ ]` Inspecionar `logs/scraper_cebraspe.log` para checar saúde do
  processo (sem bloqueios, sem timeout).
- `[ ]` Aprovar a base no banco e só então considerar liberar a rotina para
  rodar em lote — agendamento (cron/systemd timer) fica para decisão
  posterior, fora deste piloto.
