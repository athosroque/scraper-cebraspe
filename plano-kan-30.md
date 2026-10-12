# Plano — KAN-30 (Etapa 8.C / Sessão C0)
## Download guiado pelo inventário (`map_pdf_links` com classificador fino)

> **Jira Card:** [KAN-30](https://athoslobin.atlassian.net/browse/KAN-30) — `[scraper-cebraspe] Etapa 8.1.1 (8.C/C0) Download: map_pdf_links com o classificador fino do inventário`  
> **Etapa Pai:** 8.C Coleta dos concursos de múltipla escolha (ME) de 2025 ([KAN-55](https://athoslobin.atlassian.net/browse/KAN-55))  
> **Base Normativa:** ADR-026, ADR-030, ADR-031, ADR-037 (escopo e exclusões), ADR-038 (ME), ADR-039 (incidência)  
> **Documento de Referência:** [`plano-etapa-8c.md`](plano-etapa-8c.md)

---

## 1. Contexto e Objetivo

A Etapa 8.M preparou os parsers e o banco para cadernos ME, mas **nenhuma questão ME está no
banco de produção**. A Etapa 8.C levará os 11 concursos ME de 2025 encerrados ao banco. A C0
não extrai questão: ela garante que o download desses 11 concursos traga exatamente os PDFs
certos, e que a C1a saiba qual edital mandar ao LLM.

**Foco da sessão: os 11 concursos ME.** As duas correções herdadas da 8.0 ("PROVA PRÁTICA –
OPÇÃO" e caderno único "PROVAS OBJETIVAS E DISCURSIVA") **não aparecem nos 11 alvos**
(conferido no `concursos.jsonl`: só em `EMBRAPA_24` e `CODEVASF_20`, ambos C/E e fora de 2025).
Entram por serem pendência do plano da etapa, com escopo mínimo, sem investigação extra.

Entregas:
1. `map_pdf_links` passa a usar o classificador fino de `src/inventario.py`
   (`classificar_link_pdf`), respeitando `pdf_vai_para_o_site` e `inventario/exclusoes.json`
   (ADR-037).
2. Guarda o texto do link também para `editais_abertura` e `gabaritos` (persistido em
   `provas_texto_link.json` pelo `downloader`).
3. **Edital de abertura canônico:** 10 dos 11 concursos ME têm dois links de abertura (o
   original e o "atualizado conforme retificações"; só o `SEFAZ_SE_25_AUDITOR` tem um). Os dois
   continuam baixados (auditoria), mas uma função escolhe **um** para a extração LLM, evitando
   taxonomia em dobro e custo em dobro na C1a.
4. Testes com os textos reais dos links ME dos 11 concursos.
5. Correções mínimas no classificador fino (pendências da 8.0).
6. Regressão do piloto (70 provas, 145 PDFs na fila, 2.800 itens C/E, chaves 5D inalteradas).
7. Tabela "inventário × download previsto" dos 11 concursos ME sem divergências.

---

## 2. Decisões Técnicas

1. **Estrutura de retorno de `map_pdf_links`:**
   Todas as categorias (`editais_abertura`, `provas`, `gabaritos`, `nao_classificados`)
   retornam lista de dicionários `{"url": href, "texto": text}`. O `downloader.py` já suporta
   essa estrutura via `.get("texto")` e grava em `provas_texto_link.json`.
2. **Exclusões do inventário (ADR-037):**
   Slug listado em `exclusoes.json` → `map_pdf_links`/`process_contest` registram log
   informativo com categoria e motivo e devolvem `pdf_map` vazio, **sem exceção**. Exclusão é
   decisão de escopo, não erro, e o crawler nunca aborta o lote por um concurso. Nenhum dos 11
   alvos está na lista.
3. **Edital de abertura canônico (novo):**
   `inventario.escolher_edital_extracao(editais)` recebe a lista `{"url", "texto"}` e devolve
   o edital consolidado: texto com "atualizado"/"conforme retificações" (normalizado, sem
   acento); sem consolidado, o único edital; mais de um candidato do mesmo tipo → o de maior
   número de retificação no texto, e empate é ambíguo (retorna `None` + log `[EDITAL_AMBIGUO]`,
   o dono decide). Mesma regra que o piloto aplicou à mão: 4 dos 5 `revisao_piloto/<edital>.json`
   vêm do PDF `..._atualizado...` (o `TCU_25_TEFC` só tem o original).
   O `downloader` grava a escolha no manifesto (`edital_extracao`), para a C1a e o orquestrador
   (C2) lerem sem repetir a regra.
4. **Correções herdadas da 8.0 (escopo mínimo):**
   - "PROVA PRÁTICA – OPÇÃO …" → `prova_outra` (afeta só 5 PDFs de `EMBRAPA_24`).
   - Caderno único "PROVAS OBJETIVAS E DISCURSIVA" fica `caderno_objetivo` (afeta só
     `CODEVASF_20`, 15 cadernos; o PDF real já foi conferido: 120 itens C/E nas p. 1–7 e
     discursiva nas p. 8–9). A extração da discursiva desses cadernos fica para quando
     concursos anteriores a 2025 entrarem. Registrar a decisão no `task.md` e seguir.

---

## 3. Tarefas

- [ ] **Tarefa 1: Classificador fino em `src/inventario.py`**
  - Adicionar `\bpratic\w*\s+opca\w*` a `PADRAO_PROVA_OUTRA`.
  - `escolher_edital_extracao` (decisão 3).
  - Testes em `tests/test_inventario.py`, com os textos reais de abertura dos 11 alvos, por
    exemplo:
    - `"Edital nº 1 – Abertura, atualizado conforme retificações"` × `"Edital nº 1 – Abertura"`
      (BANRISUL) → o atualizado;
    - `"Comunicado nº 1 – Abertura – Atualizado conforme retificações"` (SEBRAE, "Comunicado" em
      vez de "Edital") → o atualizado;
    - `"Edital nº 5 – Abertura"` sozinho (SEFAZ_SE) → ele mesmo.
- [ ] **Tarefa 2: Modernizar `map_pdf_links` em `src/spider.py`**
  - Usar `classificar_link_pdf`, `pdf_vai_para_o_site` e `carregar_exclusoes`.
  - Retornar `{"url": href, "texto": text}` para editais e gabaritos.
  - `downloader` grava `edital_extracao` no manifesto.
  - Testes em `tests/test_spider.py` com os textos reais dos links ME (todos já classificados
    certo no inventário; o teste garante que o spider classifica igual):
    - `"PROVA PREAMBULAR (OBJETIVA)"` e `"GABARITO DEFINITIVO - PROVA PREAMBULAR (OBJETIVA)"`
      (PGE_ES) → caderno objetivo / gabarito; `"PROVA ORAL"` → `prova_outra`, fora da fila;
    - `"PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS II – ESPECIALIDADE 1 – TARDE"` e o gabarito
      correspondente (SEFAZ_SE, "MANHÃ"/"TARDE");
    - `"PROVA OBJETIVA – CONHECIMENTOS GERAIS PARA OS PERFIS 1 E 2 – TIPO 2"` e
      `"GABARITO DEFINITIVO – CONHECIMENTOS ESPECÍFICOS – PERFIL 1 – TIPO 4"` (SEBRAE);
    - não classificados reais (`"Demanda de candidatos por vaga"`, `"Ficha de Informações
      Pessoais (FIP)"`, `"Portaria de homologação do concurso"`, `"Modelo de Currículo
      Padrão"`) → fora de provas e gabaritos.
- [ ] **Tarefa 3: Teste e tabela dos 11 concursos ME de 2025**
  - `tests/test_download_inventario_c0.py`: a previsão de download (offline, sobre o
    `concursos.jsonl`) bate com as `contagens` do inventário — 110 cadernos objetivos +
    44 discursivos = **154 provas**, 110 gabaritos + 45 padrões = **155 gabaritos**,
    2 `prova_outra` (PGE_ES, fora) — e `escolher_edital_extracao` devolve exatamente 1 edital
    em cada um dos 11.
  - Tabela por concurso no fechamento (contagem inventário × previsto × edital escolhido).
- [ ] **Tarefa 4: Reclassificação offline do inventário (gravada nesta sessão)**
  - `scripts/inventariar_concursos.py --reclassificar` e `--relatorio`, persistindo
    `concursos.jsonl` e `RELATORIO.md`.
  - Diferença esperada: só os 5 PDFs de `EMBRAPA_24` (`caderno_discursivo` → `prova_outra`).
    Qualquer outra mudança para a sessão.
- [ ] **Tarefa 5: Regressão e fechamento**
  - `tests/test_reconciliacao_inventario.py` (piloto inalterado) e `make test-all` verde.
  - Atualizar `task.md`, `CLAUDE.md` §5 e, se couber, `LESSONS.md`.

---

## 4. Pontos ME anotados para as próximas sessões (fora da C0)

Vistos ao conferir os textos dos 11 alvos; não mudam o download, mas afetam a C1a em diante:

- **SEBRAE "TIPO 1–4":** os 12 cadernos são 3 provas × 4 tipos (a mesma prova com outra ordem).
  Extrair os 4 tipos quadruplica as questões no banco. Decidir na C3 (ou antes, na C1a, se o
  SEBRAE entrar na calibração): extrair só o TIPO 1 ou desduplicar pela chave canônica.
- **"ESPECIALIDADE N" / "PERFIL N" em vez de "CARGO N"** (SEFAZ_SE, SEBRAE): conferir se
  `comparacao_texto.extrair_cargos_do_texto` liga o caderno ao cargo certo no `stats_writer`.
- **"MANHÃ"/"TARDE" (SEFAZ_SE):** o "CONHECIMENTOS ESPECÍFICOS I" aparece nos dois turnos;
  conferir na C1/C5 que não são cadernos duplicados.
