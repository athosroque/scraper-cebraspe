# Plano — Etapa 8.C: coleta dos concursos de múltipla escolha (ME)

> **Documento autocontido, uma sessão (conversa) por item C0, C1a, C1b...** Prioridade do dono
> em 2026-10-12: a coleta dos cadernos ME vem antes da 8.M.2 (estatísticas por recorte).
> Base normativa: ADR-026 (banco próprio), ADR-030 (árvore), ADR-031 (cadernos), ADR-032
> (classificação), ADR-037 (inventário e exclusões), ADR-038 (ME), ADR-039 (incidência).
> Jira: KAN-55 (etapa); C0 = KAN-30, C1a = KAN-56, C1b = KAN-57, C2 = KAN-31 + KAN-32,
> C3–C7 = KAN-58 a KAN-62, C8 = KAN-63.
> Ao abrir uma sessão, ler só este arquivo e a seção dela. O `task.md` tem o resumo e o
> checklist.

## Por que existe

A 8.M deixou o código pronto para ME (parser, gabarito A–E, banco, site e simulado), mas
**nenhuma questão ME está no banco de produção**: o `scraper-cebraspe-db` tem só as 2.800
C/E do piloto. O Gate da 8.M carregou o `SEFA_PR_25` (380 itens ME) numa cópia descartável
(`cebraspe_gate`), fora do caminho normal: não há `data/2025/CEBRASPE/SEFA_PR/` nem o edital em
`revisao_piloto/`. Esta etapa leva os concursos ME para o banco de verdade pelo pipeline
inteiro (download → edital → questões → árvore → classificação → site), com revisão do dono.

## Fatos de partida (2026-10-12)

- **Alvo da 8.C: os 11 concursos ME de 2025 encerrados** (formato da amostra do inventário,
  `inventario/RELATORIO.md`; o formato real é por questão e sai no parse):

  | Concurso | Cadernos obj. | Cadernos disc. | Observação |
  |---|---:|---:|---|
  | `SEFA_PR_25` | 7 | 1 | já passou no Gate (cópia); P1 peso 1,00 e P2 peso 1,50 (KAN-53) |
  | `BANRISUL_25` | 5 | 4 | caderno de calibração com figura |
  | `SEBRAE_25_PSE_1` | 12 | 2 | "TIPO 1–4" e "perfis", como o `SEBRAE_26_PSE_1` da calibração |
  | `UNIVESP_25_PSS` | 12 | 1 | |
  | `IPAAM_25` | 22 | 0 | um básico para os cargos 1 a 19 (prova distinta, ADR-039) |
  | `SEMA_AM_25` | 14 | 0 | |
  | `PGE_ES_25_PROCURADOR` | 1 | 1 | "PROVA PREAMBULAR (OBJETIVA)" + 2 `prova_outra` |
  | `PGE_PI_25` | 1 | 2 | |
  | `SEFAZ_SE_25_AUDITOR` | 6 | 6 | "MANHÃ"/"TARDE" no texto do link |
  | `TCE_MG_25` | 11 | 10 | |
  | `SEED_SE_25_PROFESSOR` | 19 | 17 | o maior; lote sozinho |

- **Fora da 8.C (decisão do dono depois):** ME de 2026 encerrados (`SEBRAE_26_PSE_1`,
  `SEBRAE_26_PSE_2`) e os ME em andamento (13 de 2025 e 7 de 2026), que dependem de gabarito
  definitivo publicado (ponto em aberto da 8.1).
- **Pipeline existente, por concurso** (sem orquestrador):
  1. Download: `python -m src.spider --slug <SLUG>` → `data/<ano>/CEBRASPE/<orgao>/{Editais,
     Provas,Gabaritos}/` + `.manifest.json` (o slug só existe na URL do manifesto; dois
     concursos do mesmo órgão no mesmo ano dividem a pasta). Pula slugs de
     `data/processed_concursos.json`.
  2. Edital (LLM, `OPENROUTER_KEY_TAXONOMIA_EDITAL`): `python -m scripts.revisar_taxonomia_piloto
     <pdf_edital>` → `revisao_piloto/<edital>.json` + auditoria; chama `atualizar_revisao`
     (validação de-para, relatório, Datasette, `stats_writer`, regra da árvore).
  3. Revisão humana do edital: `status_revisao_humana = "APROVADO..."` no `<edital>.json`
     (ADR-028). Sem isso, nada entra na estatística oficial.
  4. Banco: `python -m src.stats_writer` grava concurso, cargos, taxonomia, provas e a fila
     `fila_extracao_questoes` (o concurso nasce do `<edital>.json`; as provas, do manifesto).
  5. Questões: `python -m scripts.extrair_questoes` consome a fila (lock 5031001).
  6. Árvore: itens novos de edital mapeados por regra; o resto fica pendente no
     `arvore.html`. Matéria nova (ex.: conhecimentos bancários, legislação tributária
     estadual) precisa de nó criado pelo dono (`scripts/curar_arvore.py`) ou proposta do LLM
     (`scripts/propor_arvore.py`, custa tokens).
  7. Classificação (LLM): `python -m scripts.classificar_questoes --caderno <X>` (não tem
     `--concurso`) → `canonico/classificacao_questoes.json`; curadoria em
     `scripts/curar_classificacao.py` (`--aprovar-lote --confianca alta`, `--pendentes`,
     `--aplicar-banco`).
- **Pendências da 8.0 que afetam o download** (`task.md`, 8.0): `map_pdf_links` ainda usa a
  classificação antiga (o singular "PADRÃO DEFINITIVO DE RESPOSTAS" cai em `provas`; não
  conhece `pdf_vai_para_o_site` nem `exclusoes.json`); "PROVA PRÁTICA – OPÇÃO …" de técnico
  entra como discursivo; caderno único "PROVAS OBJETIVAS E DISCURSIVA" entra como objetivo.
- **Riscos conhecidos:** o `edital_parser` foi calibrado em 5 editais C/E; editais com P1/P2
  (SEFA_PR), "áreas" (BANRISUL) ou "perfis" (SEBRAE) podem quebrar o chunking por
  cargo/matéria. A regra de herança do texto-base ME (decisão de 2026-10-09) pode deixar
  questão sem texto-base quando ela usa o texto sem citar o rótulo.

## Regras de toda sessão

- Antes de gravar no banco de produção: `pg_dump` do `scraper-cebraspe-db` para
  `scratch/backup_<data>_<sessao>.dump` (rollback do lote).
- Piloto intocado: 2.800 itens C/E, 129 anuladas, 3.029 apontamentos, chaves 5D iguais.
  Conferir no fim de toda sessão que grava no banco.
- Nada `proposto` é aprovado pelo agente: edital, árvore e classificação média/baixa são
  aprovados pelo dono (anti-padrões do `CLAUDE.md`).
- Custo LLM registrado por sessão (Langfuse + saída dos scripts). Teto: avisar o dono antes de
  passar de US$ 2 numa sessão.
- `make test-all` verde no fim; `task.md` e `CLAUDE.md` §5 atualizados; lição nova no
  `LESSONS.md` se custou mais de 30 min.

## Sessões

### C0 — Download guiado pelo inventário (sem LLM)

Fecha as pendências da 8.0 que afetam o download, para o lote não baixar lixo nem perder PDF.

1. `map_pdf_links` (ou uma função nova usada pelo `process_contest`) classifica com o
   classificador fino de `src/inventario.py` e respeita `pdf_vai_para_o_site` e
   `inventario/exclusoes.json`. Guarda o `texto` do link também para edital e gabarito.
2. Corrigir no classificador: "PROVA PRÁTICA – OPÇÃO …" (prova manual de técnico, vira
   `prova_outra`) e caderno único "PROVAS OBJETIVAS E DISCURSIVA" (decidir o tipo com um PDF
   real; registrar).
3. Regressão: reextração do piloto com 70 provas, 145 PDFs na fila e chaves 5D iguais;
   `--reclassificar` do inventário sem mudança fora dos casos corrigidos.
4. Comparar, para os 11 concursos do alvo, a contagem que o download baixaria com a do
   inventário (`contagens`, só PDFs que vão para o site). Sem rede: usar o `concursos.jsonl`.

**Pronto quando:** testes novos com os textos reais, piloto inalterado e a tabela
"inventário × download previsto" dos 11 concursos sem diferença.

### C1a — Lote de calibração, parte 1: `SEFA_PR_25` + `BANRISUL_25` até as questões no banco

Feito à mão, comando a comando, para virar o roteiro do orquestrador (C2).

1. Backup; download dos 2 concursos; conferir PDFs (`%PDF-`) e contagem × inventário.
2. Edital pelo LLM; validação de-para com 0 alertas bloqueantes; corrigir o `edital_parser`
   se o chunking quebrar (P1/P2, "áreas"), com teste e sem mudar os 5 editais do piloto.
3. `stats_writer` + `extrair_questoes`: fila `concluido`; itens == gabarito; ME com 4–5
   alternativas por questão; gabarito A–E; discursivas com quesitos.
4. Conferir 3 questões contra o PDF (1 básica, 1 específica, 1 com figura do BANRISUL).
5. Escrever o **roteiro** (`docs/runbook-lote.md`): cada comando, o que conferir e onde
   parou. Anotar o tempo e o custo de cada passo.

**Pausa do dono:** revisar os 2 editais no relatório/Datasette e gravar
`status_revisao_humana`.

**Pronto quando:** os 2 concursos com questões no banco (sem classificação ainda), piloto
inalterado e roteiro escrito.

### C1b — Lote de calibração, parte 2: árvore, classificação e site

1. Árvore: itens novos dos 2 editais mapeados por regra; o resto vai para o `arvore.html`.
   Rodar `propor_arvore.py` só nas matérias novas, se o dono quiser (custa tokens).
   **Pausa do dono:** criar/mapear nós e aprovar propostas (`curar_arvore.py`).
2. Classificação por caderno (`classificar_questoes --caderno`), aprovação em lote só da
   confiança `alta` (com ordem do dono) e média/baixa no `classificacao.html` para o dono.
   `--aplicar-banco`.
3. Site: as questões ME aparecem com filtro "Formato", assunto e concurso; responder,
   corrigir e simulado de 1 cargo no Chromium headless, 0 erro de JS.
4. Estatística: `fn_prova_cobra` sem filtro com 7 concursos (o ranking do ADR-039 muda, e
   isso é esperado; registrar os números novos).

**Pronto quando:** os 2 concursos `aprovado`, classificação aplicada, site conferido no
Chromium, piloto inalterado e roteiro completo até o site.

### C2 — Orquestrador mínimo (núcleo da 8.1)

`scripts/lote_concursos.py` automatiza o roteiro da C1, com estado em `inventario/lotes.json`
(por concurso: `mapeado → baixado → edital_extraido → aguardando_revisao_edital →
questoes_extraidas → aguardando_curadoria → classificado → aprovado`), idempotente e
retomável: `--lote N --concursos A,B`, `--continuar N`, `--status`, `--aprovar N`. Para em
toda pausa do dono e em falha bloqueante.

- Checagens automáticas que entram no relatório `inventario/lotes/lote_NN.md` (tabela
  "Checagens automáticas por lote" do `plano-etapa-8.md`), incluindo o alerta pedido pelo
  dono em 2026-10-09: questão ME que cita "texto", "tabela", "figura", "gráfico" ou "quadro"
  e ficou sem texto-base e sem figura (excluir o "texto precedente" no próprio enunciado:
  BANRISUL Q22, SEFA_PR Q11 e Q50). O alerta não bloqueia.
- `--concurso` no `classificar_questoes` (hoje só `--caderno`).
- Testes com etapas mockadas: retomada, parada na pausa, `--aprovar`.
- Passo fixo: detector de dispersão da árvore (`detectar_dispersao_arvore --propor`) depois da
  carga de cada lote; as propostas vão para o dono (KAN-64).

**Pronto quando:** rodar o orquestrador sobre o lote da C1 em modo conferência não muda nada
(idempotente) e o relatório do lote sai com as checagens verdes.

### C3 a C7 — Lotes ME de 2025 (uma sessão por lote, pausa do dono no meio)

Pares por afinidade (a árvore cresce por área, e a curadoria fica mais curta):

| Sessão | Lote | Concursos |
|---|---|---|
| C3 | 2 | `SEBRAE_25_PSE_1` + `UNIVESP_25_PSS` |
| C4 | 3 | `IPAAM_25` + `SEMA_AM_25` (ambiental, Amazonas) |
| C5 | 4 | `PGE_ES_25_PROCURADOR` + `PGE_PI_25` (procuradorias) |
| C6 | 5 | `SEFAZ_SE_25_AUDITOR` + `TCE_MG_25` (fiscal e controle) |
| C7 | 6 | `SEED_SE_25_PROFESSOR` (sozinho: 19 objetivos + 17 discursivos) |

Cada lote: `lote_concursos.py` até a pausa do edital → dono aprova → até a pausa da
curadoria → dono decide → classificação aplicada → relatório do lote → `--aprovar`. Correção
de parser no meio exige reextrair os lotes anteriores e conferir chaves 5D e contagens.

### C8 — Fechamento da coleta ME de 2025

1. Reconciliação das views da 5E com 16 concursos (5 C/E + 11 ME); desempenho da
   `fn_prova_cobra` com o volume novo.
2. Textos ME no site (pendência da 8.M): o KPI "Nota CEBRASPE" mostra "certas − erradas", o
   subtítulo da lista diz "padrão certo/errado" no filtro ME, e a introdução do simulado só
   descreve +1/−1.
3. `CLAUDE.md` §5, `task.md`, ADR novo só se houver decisão nova (ex.: regra do caderno único
   objetivo + discursivo); `git mv plano-etapa-8c.md docs/planos/`.

**Pronto quando:** os 11 concursos ME de 2025 `aprovado`, views reconciliadas, textos ME
corrigidos e `make test-all` verde.

## Pontos em aberto (dono)

- Ordem: ME de 2025 primeiro e só depois os C/E de 2025 que faltam (premissa deste plano).
- Concursos ME em andamento com gabarito definitivo (`PC_CE_25_DELEGADO`, `SEFAZ_RJ_25_*`,
  `TJ_*_25_NOTARIOS`...): entram na 8.C ou esperam o encerramento?
- Classificação média/baixa: revisar por lote (premissa) ou acumular para o fim?
- Pontuação do simulado ME por edital (KAN-53) continua fora; o simulado ME usa +1/0.
