# Próximos passos: figuras da C1 e painel de revisão dos portões

Criado em 2026-10-21, ao fim da sessão que fechou a D5a e a D5b. Para abrir uma sessão nova sem
depender da conversa anterior.

> Ao abrir a sessão, ler só este arquivo. O contexto do Dagster está em
> `proximos-passos-dagster.md` (D5a/D5b já entregues; o arquivo ainda cita a D5b como "a seguir").

## 1. Estado de partida (commitado em `master`)

- **D5a (KAN-31):** `c3a6eb9`. Dagster como C2, infra e assets. `dagster==1.9.13` fixado de
  propósito (a 1.8.13 não resolve com o `langfuse`).
- **D5b (KAN-32):** `c2d7719` (código) e `3a6120c` (relatório e prompt). Checagens calculadas
  (download, prova, banco/K22, classificação, site), portões P3/P7/P9 e relatório
  `inventario/lotes/lote_NN.md` com veredito em 3 estados. Fora de conferência os portões são
  sempre exigidos (regra única `aprovacao_efetiva` em `src/c2/assets.py`).
- **Ainda não feito:** ADR-042 (Dagster como C2, a reescrever sem prometer "retomada granular"
  nem "linhagem" que não existem), página do Dagster no guia (onda 4 do
  `plano-documentacao.md`), comentário e movimentação dos cards KAN-31 e KAN-32 no Jira (o MCP do
  Atlassian falhou ao conectar na sessão), e o KAN-66 parte 1 (mover as questões 56 a 58 de
  `STM_25` para a LAI; grava no banco do piloto).
- **Ambiente:** o `venv/` local ainda tem `protobuf` 4.25.9 e `pip check` quebrado; rodar
  `venv/bin/pip install -r requirements.txt` antes de trabalhar.
- **C1 hoje (relatório `inventario/lotes/lote_01.md`):** veredito `AGUARDANDO PORTÕES HUMANOS`.
  Download, Prova e Banco verdes. Edital `PENDENTE` nos dois concursos. Classificação `0 de 610`.
  Site `NÃO VERIFICADO` (0 de 610 na `vw_questoes`, porque as questões só entram na view depois
  de classificadas). 183 propostas de árvore pendentes (a árvore inteira, não só a C1).
  Piloto inalterado: 2.800 itens, 129 anuladas, 3.029 apontamentos, hash
  `3257ba6ba525fdd6b4492733b50882f2`.

## 2. Pedido do dono (2026-10-21)

1. As provas de `BANRISUL_25` e `SEFA_PR_25` são de **múltipla escolha**, mas nos documentos
   aparecem como "objetiva". Algumas figuras foram extraídas: **conferir se foram todas** e,
   quando necessário, **subir ao site vinculadas à questão específica**. Corrigir a causa para
   não se repetir nos próximos lotes.
2. Os **portões e a execução do fluxo**: o dono acompanha pelo Dagster? Como valida o que precisa
   ser validado? Quer tudo **exibido já tratado**, como no Datasette, sem trabalho manual,
   preferencialmente numa interface que já existe (ajustada) ou numa nova.

## 3. Tema A: figuras (investigação e correção)

### 3.1 O que já se sabe

- **"Objetiva" não é erro de dado.** `provas.tipo` é a categoria do caderno (`objetiva_basica`,
  `objetiva_especifica`, `discursiva`); o formato fica em `questoes.tipo` e é `multipla_escolha`
  nas 610 questões da C1. O que confunde é o relatório do lote (consulta (a)), que mostra só o
  tipo do caderno. Ação pequena: acrescentar a coluna **Formato** à tabela.
- **Figuras no banco (C1):** `BANRISUL_25`: 5 figuras em questões (2 na básica, 3 na específica) e 1
  em texto-base. `SEFA_PR_25`: 5 em questões e 3 em textos-base. Comparação: `PF_25_ADM` (C/E)
  tem 1 figura em 1.150 questões.
- **Sinal de perda possível (não é prova):** o alerta K19 (ME que cita texto, tabela, figura,
  gráfico ou quadro sem texto-base nem figura vinculados) tem **61 questões** na C1, com as
  exceções já conhecidas (`BANRISUL_25` Q22, `SEFA_PR_25` Q11 e Q50). Pela contagem bruta de
  imagens por PDF, `077_BANRISUL_001_01.pdf` tem 9 páginas com imagem e 0 figura extraída, e
  `077_BANRISUL_003_01.pdf` tem 7 páginas e 0. A contagem é ruidosa (o BANRISUL tem 100 "imagens"
  por caderno, provavelmente tiras ou marca-d'água), então **só uma conferência visual das
  páginas decide**.
- **Como funciona hoje:** o parser (`src/prova_parser.py`) recorta figuras raster (tiras vizinhas
  unidas) e vetoriais (traços próximos viram uma região), com "vínculo de dono" para o item ou o
  texto-base; `scripts/extrair_questoes.py` grava os PNG em `data/<ano>/CEBRASPE/<órgão>/Provas/figuras/`.
  No banco, `questoes.figuras` e `textos_base.figuras` (JSONB). A view entrega
  `vw_questoes.figuras = textos_base.figuras || questoes.figuras`; o site carrega sob demanda em
  `/q/{concurso}/{caderno}/{numero}/anexos` (ADR-034, 5G.3).
- **Hipóteses a testar** (nenhuma confirmada): (a) figuras vetoriais ou tabelas desenhadas no
  enunciado não recortadas; (b) alternativas que são imagens (típico de ME); (c) figura que ocupa
  a página inteira ou fica entre colunas e é atribuída ao item errado; (d) tabela do enunciado
  extraída como texto e perdida.

### 3.2 Plano (uma sessão por item)

- **F1, auditoria visual (sem alterar nada).** Para cada caderno da C1, renderizar em PNG as
  páginas que têm imagem raster ou desenho vetorial e cruzá-las com as figuras gravadas e com as
  questões do intervalo da página. Entregar uma tabela por caderno: página, figura extraída
  (sim/não), questão vinculada, questão que cita figura sem figura. Priorizar as 61 do K19.
  Exemplos para abrir à mão: `BANRISUL_25` caderno 001 e 003.
- **F2, correção no parser** (`src/prova_parser.py`), com testes e **sem mudar o piloto**: o
  reprocessamento da C1 não pode alterar os 5 concursos do piloto (P71; K22–K24 antes e depois).
  Reprocessar só a C1 (fila `fila_extracao_questoes`, `--reprocessar` do `extrair_questoes`).
- **F3, vínculo no site.** Garantir que toda questão que cita figura, tabela, gráfico ou quadro
  tenha a figura (ou o texto-base) vinculada e visível em `/q/.../anexos`; conferir no Chromium
  headless, 1280 e 390 px, 0 erro de JavaScript.
- **F4, evitar recorrência.** Transformar a conferência em checagem automática do lote, em
  `src/registro/checagens.py` (P70: registrar e rodar `make docs-gerar`): por caderno, páginas
  com imagem ou desenho sem figura extraída → alerta; K19 residual > 0 fora das exceções →
  **bloqueante**. A coluna "Figuras" entra no relatório do lote (`src/c2/relatorio.py`) e na
  galeria do painel (tema B).
- **Pronto quando:** F1 mostra 0 questão que cita figura sem figura (exceções documentadas), o
  piloto está inalterado, o site exibe a figura na questão certa, e a checagem nova está no
  registro e no relatório.

### 3.3 Resultado da F1 (2026-10-21, só leitura)

**Método.** Os 12 cadernos objetivos da C1 (610 questões, 125 páginas) foram renderizados com
sobreposição (imagem bruta, traço vetorial bruto, candidata raster e vetorial do parser, figura
gravada no banco) e conferidos com três varreduras automáticas, mais conferência visual das
páginas suspeitas:

1. **Tinta fora do texto:** página em 72 dpi, apaga os spans de texto, o cabeçalho, o rodapé e as
   imagens decorativas, e procura regiões escuras que sobram. Pega figura raster e desenho grosso.
2. **Tabela de filete:** grupos de traços horizontais finos com a mesma faixa horizontal,
   empilhados.
3. **Traços soltos:** traços vetoriais agrupados com folga de 15 pt que nenhuma figura cobre.
   Pega gráfico e tabela de linha fina que a varredura 1 apaga.

Os scripts ficaram no scratchpad da sessão (não versionados). A lógica das varreduras 1 e 3 é a
base da checagem da F4.

**Resultado: 1 perda em 610 questões.** Todas as 14 figuras gravadas (9 em questões e 5 em
textos-base) estão no dono certo, e nenhuma alternativa é imagem.

| Caderno | Págs. | Figuras gravadas (página → dono) | Perda |
|---|---|---|---|
| `077_BANRISUL_001_01` | 9 | nenhuma (o caderno não tem figura) | — |
| `077_BANRISUL_002_01` | 8 | p1 → Q36 (3 tabelas vetoriais) | — |
| `077_BANRISUL_003_01` | 7 | nenhuma (o caderno não tem figura) | — |
| `077_BANRISUL_004_01` | 7 | nenhuma (o caderno não tem figura) | — |
| `077_BANRISUL_CB1_01` | 6 | p4 → Q16 (tabela-verdade); p5 → texto CB1A3-II (grade); p5 → Q26 (diagrama de conjuntos) | — |
| `135_SEFAPR_002_01` | 12 | nenhuma (o caderno não tem figura) | — |
| `135_SEFAPR_004_01` | 10 | p2 → texto 4A1-I (gráfico); p2 → Q10 (tabela); p6 → Q27 (imagem IVA/OCDE); p8 → Q38 (tabela) | — |
| `135_SEFAPR_005_01` | 11 | p3 → texto 5A2-I (tabela); p4 → Q27 (tabela) | **p1, Q1: tabela de frequências não recortada** |
| `135_SEFAPR_006_01` | 12 | p5 → Q13 (imagem); p7 → textos 6A4 (captura de tela) | — |
| `135_SEFAPR_CG1_01` | 16 | p13 → texto CG1A11-I (infográfico OCDE) | — |
| `177_SEFAPR_001_01` | 12 | nenhuma (o caderno não tem figura) | — |
| `177_SEFAPR_003_01` | 12 | nenhuma (o caderno não tem figura) | — |

- **"9 páginas com imagem e 0 figura" no BANRISUL 001 e 003 não indica perda.** As "imagens" são
  os selos de cada questão (ícone e tarja, duas por questão), que o `_figura_decorativa_me` já
  descarta. As tabelas do caderno 001 (Q40, Q43, Q76 a Q78) e do SEFA 006 Q5 existem no PDF só
  como texto monoespaçado, e o enunciado as preserva linha a linha. Não há figura a recortar.
- **K19: 61 alertas, 1 verdadeiro (SEFA_PR 005 Q1).** Os outros 60 são ruído da regex:
  "contexto" casa `texto`, "tabela" aparece no sentido de tabela de banco/SQL, "quadro" no
  sentido de situação ou de quadro funcional, e há o texto citado dentro do próprio enunciado
  ("Internet: <…>. Tendo o texto anterior…") e o gráfico só mencionado (005 Q39, "ao examinar o
  gráfico de resíduos", sem gráfico na página).
- **Hipóteses do §3.1:** (a) **confirmada, com outra causa** (abaixo); (b) não ocorre na C1;
  (c) não ocorre (14 de 14 no dono certo); (d) só no SEFA 005 Q1, como efeito de (a). O texto da
  tabela entrou achatado no enunciado: "X frequência absoluta 0 10 1 7 2 7 3 10 total 34".

**Causa da perda (verificada).** Em `figuras_vetoriais_da_pagina`, o separador vertical de
colunas só sai se tiver mais de 80% da altura da página. Na 1ª página do caderno, a faixa
"PROVA OBJETIVA" encurta o separador (629 a 671 pt, contra o limite de 673,5 pt), e ele fica. O
filete do título de seção e as tarjas dos selos encostam nele (a menos de 3 pt), e o
`_agrupar_proximos` une pela **caixa do grupo**, não pelos membros. A caixa vira a coluna
esquerda inteira, `[26, 135, 301, 806]`, e engole a tabela. Depois a região inteira é descartada
porque cruza os selos raster. Experimento: descartando os traços verticais com menos de 2 pt de
largura e mais de 60% da altura, a tabela volta (`[105, 189, 214, 292]`) e as outras 7 primeiras
páginas com separador curto não ganham nenhum falso positivo. **Risco para o piloto:** a regra
vale também para C/E. Qualquer figura na coluna esquerda de uma página com separador curto pode
estar perdida lá, e a F2 tem de medir isso antes e depois (P71).

**Achados menores (para F2 e F3):**

- `077_BANRISUL_002_01_1_1.png` corta ao meio a legenda "Clientes" no topo (a caixa vetorial
  começa na linha da legenda). Ou inclui a legenda inteira, ou começa abaixo dela.
- Quando há figura vetorial (tabela), o texto da tabela também fica achatado no enunciado
  (BANRISUL 002 Q36: "Tabela I Clientes IdCliente Nome…"). É de propósito (comentário em `src/prova_parser.py:2608`),
  mas no site isso duplica a tabela como texto ilegível. Decidir na F3 se o site esconde esse
  trecho.
- **F4:** com a regex atual, o K19 como bloqueante travaria todo lote (60 de 61 são falsos). A
  checagem tem de ser geométrica (varreduras 1 e 3 acima: tinta ou traço sem figura gravada), e
  o K19 fica informativo ou passa a usar uma regex dêitica ("tabela/figura/gráfico" seguido de
  "a seguir", "precedente" ou "apresentad…", com limite de palavra).

## 4. Tema B: como o dono acompanha e valida os portões

### 4.1 O que existe hoje

- **Dagster** (`dagster.projetoathos.com.br`, atrás do Cloudflare Access): mostra as execuções, os
  13 assets por concurso e os 6 asset checks (K22, download, portão P3, consultas do runbook, portão
  P7, portão P9). **Não mostra os dados** que o dono precisa avaliar e **não aprova nada**.
- **Datasette** (`datasette.projetoathos.com.br`): tabelas de `revisao_piloto/` e, em `/relatorio/`,
  `index.html`, um HTML por edital (texto-fonte e taxonomia lado a lado, com alertas),
  `arvore.html` e `classificacao.html`. É onde o dono decide hoje, mas **a aprovação é manual**:
  editar `status_revisao_humana` no JSON do edital, e `curar_arvore.py` / `curar_classificacao.py`
  no terminal (`--aprovar-proposta`, `--rejeitar-proposta`, `--aprovar ITEM:NO`).
- **Relatório do lote** (`inventario/lotes/lote_NN.md`): só Markdown, sem links para as páginas de
  revisão e sem o comando de aprovação.

### 4.2 Opções (recomendação: 1 agora, 2 depois)

1. **Painel de lote em HTML dentro do Datasette** (menor esforço). O D5b passa a gerar também
   `revisao_piloto/relatorio/lotes/lote_NN.html`, servido em `/relatorio/lotes/`. Para cada portão
   (P3, P7, P9 e figuras): o que falta, os números já tratados, **link direto** para a página de
   revisão certa e o **comando de aprovação pronto para copiar**. Reaproveita o que existe e já
   fica atrás do Cloudflare Access. Não elimina o terminal, mas elimina a caça.
2. **Painel de revisão com botões** (resolve o trabalho manual). Serviço admin separado do site
   público (`scraper-cebraspe-painel`, mesma stack do site: FastAPI + Jinja2 + HTMX, atrás do
   Cloudflare Access). Mostra tudo tratado: edital × taxonomia, propostas da árvore agrupadas e com
   impacto, classificações de confiança média e baixa ao lado do enunciado, galeria de figuras. O
   botão **chama as funções existentes** (`src/arvore.py`, o gravador de `status_revisao_humana`),
   nunca `UPDATE` no banco (A25, A27, A28, P51), e só o dono clica (A30). O site público não
   hospeda admin.
3. **Dagster como interface de aprovação** (não recomendado). O Dagster é bom para execução e
   checks, ruim para ver dados e decidir.

**Complemento opcional:** um sensor do Dagster que avise no Telegram (o `scraper-cebraspe-bot` já
existe) quando um lote parar num portão.

### 4.3 O que cada portão precisa mostrar "já tratado"

- **P3, edital:** os dois editais da C1 (`SEFA_PR_25`, `BANRISUL_25`) com alertas da validação
  de-para, itens sem correspondência e a taxonomia por cargo; aprovar ou devolver.
- **P7, árvore:** hoje 183 propostas pendentes, de toda a árvore. **Decidir com o dono** se o
  portão do lote deve olhar só as propostas dos concursos do lote (hoje todo lote sai
  `AGUARDANDO` até a curadoria global zerar). Mostrar agrupadas por tipo e confiança, com as
  questões afetadas.
- **P9, classificação:** por concurso, `N de M` classificadas; as de confiança média e baixa ao
  lado do enunciado e da alternativa correta; aprovação em lote só da confiança `alta`, com ordem
  explícita do dono.
- **Figuras:** a galeria do tema A (página × figura extraída × questão).

### 4.4 Passos

- **B1:** painel em HTML por lote (opção 1) e coluna "Formato" no relatório. Registrar no
  registro (P70) e em `docs/tecnico/`.
- **B2:** decisão do dono sobre o escopo do P7.
- **B3:** painel com botões (opção 2), com ADR novo (admin separado, autenticação, o que ele pode
  gravar e por quê).

## 5. Ordem sugerida

1. ~~**F1**~~ (auditoria visual das figuras da C1; só leitura): **feita em 2026-10-21**, ver §3.3.
2. **F2 e F3** (correção, reprocessamento da C1 e site), com K22–K24 antes e depois. **F2 feita
   em 2026-10-22:** `FRACAO_SEPARADOR_COLUNAS = 0.6` em `figuras_vetoriais_da_pagina`, teste
   `TestFigurasVetoriais::test_separador_curto_da_primeira_pagina_nao_engole_a_tabela`, C1
   reprocessada sozinha (as funções `carregar_fila`, `processar_caderno` e `aplicar_classificacao`
   filtradas pelos 2 concursos, porque o `--reprocessar` não filtra concurso e refaria o piloto).
   Resultado: 15 figuras na C1 (a nova é a da Q1 de `135_SEFAPR_005_01`), as 14 antigas iguais, K19
   de 61 para 60, K22 igual. Os riscos da F1 ficaram no **KAN-75** (piloto C/E, legenda cortada,
   tabela duplicada no enunciado). Falta a F3.
3. **B1** (painel em HTML por lote, já com a galeria de figuras da F1).
4. **C1a / C1b** (dono): aprovar os dois editais, curar a árvore, classificar e conferir o site.
   Fazer **depois** das figuras, para a revisão do dono partir de dados finais.
5. **F4** e **B3** (prevenção e painel com botões).
6. Pendências: ADR-042, página do Dagster no guia, Jira (KAN-31 e KAN-32), KAN-66 parte 1.
7. Lotes C3 a C7 no Dagster, e C8 (`plano-etapa-8c.md`).

## 6. Regras que valem em tudo

- Piloto inalterado (P71): K22–K24 antes e depois de qualquer passo que grava; teste só com a C1.
- Sem credencial no código (A07); nada de `UPDATE` de aprovação no banco (A25, A27); decisão do
  dono na árvore só via `curar_arvore.py` ou `src/arvore.py` (P51, A28).
- Script ou checagem nova entra em `src/registro/` e pede `make docs-gerar` (P70); não editar à
  mão `docs/tecnico/` (A62).
- Não commitar `questoes/` (A42) nem PDFs de `data/`.
- Dagster em conferência por padrão; `--no-conferencia` exige portões aprovados e só com ordem
  explícita do dono.

## 7. O que não foi verificado

- ~~A causa real das figuras ausentes~~: verificada na F1 (§3.3). Falta medir o efeito da
  correção no piloto C/E (F2).
- Se os asset checks aparecem na interface do Dagster (só se sabe que estão em `Definitions`).
- O modo produção (`--no-conferencia`) nunca foi executado, por segurança.
- O fluxo do Cloudflare Access depois do login no Dagster (WebSocket da interface).
