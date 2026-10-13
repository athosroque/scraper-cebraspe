# Runbook — levar um lote de concursos ME para o banco

> **C1a, 2026-10-12.** Base do orquestrador da C2, que será o Dagster
> (decisão do dono em 2026-10-13, sessões D5a e D5b de `plano-etapa-9.md`).
> Os números são medidos no lote de calibração `SEFA_PR_25` + `BANRISUL_25`. Onde um passo
> ainda é manual ou não foi validado, a seção diz isso. Plano: `plano-etapa-8c.md`.

## 1. Objetivo e quando usar

Este roteiro leva um lote de concursos de múltipla escolha (ME) do site do CEBRASPE até o
banco `scraper-cebraspe-db`, passo a passo: download, chunking do edital, extração do edital
pelo LLM, questões, conferência. Use quando for carregar concursos novos, ou para repetir o
lote de calibração e ver se nada quebrou. Ele não cobre a árvore, a classificação nem o site
(C1b). O piloto de 5 concursos C/E não deve mudar em nenhum passo.

## 2. Pré-requisitos

- **Venv** do projeto: `venv/bin/python` (Python 3.11+, `pip install -r requirements.txt`).
  Os comandos abaixo usam `venv/bin/python` direto, sem ativar o venv.
- **Playwright**: `venv/bin/playwright install chromium` (o spider abre o site do CEBRASPE).
- **`.env`** com:
  - `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5435`, `POSTGRES_DB=cebraspe`,
    `POSTGRES_USER=cebraspe`, `POSTGRES_PASSWORD` preenchido;
  - `OPENROUTER_KEY_TAXONOMIA_EDITAL` (chave da etapa do edital; sem ela cai na
    `OPENROUTER_API_KEY` com aviso `[CHAVE_FALLBACK]`).
- **Container de pé**: `docker compose up -d scraper-cebraspe-db`. Conferir com
  `docker ps --filter name=scraper-cebraspe-db`.

Os passos de banco abaixo usam `docker exec scraper-cebraspe-db psql -U cebraspe -d cebraspe`
(ou um cliente com o mesmo acesso).

## 3. Tabela-resumo

Concursos de exemplo: `SEFA_PR_25` e `BANRISUL_25`. Tempos medidos em 2026-10-12.

| Passo | Comando | O que conferir | Tempo medido | Custo LLM |
|---|---|---|---|---|
| P0 Backup | `docker exec scraper-cebraspe-db pg_dump ... > scratch/backup_<data>_<sessao>.dump` | Dump > 0 bytes; `pg_restore -l` com 95 "TABLE DATA" | 0,9 s (1,9 MB) | 0 |
| P1 Download | `venv/bin/python -m src.spider --slug <SLUG>` (um por concurso) | `%PDF-` em todo PDF; contagens = inventário | 59 s (SEFA), 66 s (BANRISUL) | 0 |
| P2 Chunking | script avulso sobre `extrair_secao_objetos_avaliacao_detalhada` + `dividir_por_cargo_e_materia` | Sem chunk de 1–40 caracteres, sem nível `None`, sem matéria que seja nome de cargo | < 1 s | 0 |
| P3 Edital | `venv/bin/python -m scripts.revisar_taxonomia_piloto <pdf do edital_extracao>` | `falhas: 0`; `total_alertas: 0`; sem tópico numérico | 554 s (SEFA, 22 chunks), 358 s (BANRISUL, 28 chunks) | US$ 0,018 (os 2, 50 chamadas) |
| P4 Questões | feito pelo P3; repetir com `stats_writer` e `extrair_questoes` | Fila `concluido`; 380 + 230 itens ME | incluído no P3 | incluído no P3 |
| P4b Correção | `venv/bin/python -m scripts.extrair_questoes --reprocessar` (só se o parser mudar) | snapshot antes/depois: piloto idêntico, só a mudança esperada | 16 s (87 cadernos) | 0 |
| P5 Conferência | consultas a–e e PDF | Consultas a–e (seção 4.5); 3 questões iguais ao PDF | manual | 0 |
| P6 Dispersão da árvore | `venv/bin/python -m scripts.detectar_dispersao_arvore --dry-run`, depois `--propor` | Grupos novos com nós do lote; norma em dois lugares vira proposta para o dono | não medido | 0 |

Tempo de P3 e P4 juntos: 912 s para os 2 concursos (sem contar P0 a P2). Custo LLM total do
lote de calibração: US$ 0,018.

## 4. Passos

### 4.1 P0 — Backup do banco

Antes de gravar qualquer coisa de produção:

```bash
cd /home/athos/homelab/scraper_cebraspe
docker exec scraper-cebraspe-db pg_dump -U cebraspe -d cebraspe -Fc \
  > scratch/backup_2026-10-12_c1a.dump
```

**Conferir:**

```bash
test -s scratch/backup_2026-10-12_c1a.dump && echo "tamanho ok"
docker exec -i scraper-cebraspe-db pg_restore -l < scratch/backup_2026-10-12_c1a.dump \
  | grep -c "TABLE DATA"
```

O segundo comando deu 95 nesta sessão. Zero ou erro = não siga.

**Se falhar:** container fora do ar ou senha errada. Suba o container e confira o `.env`.
Não grave nada sem backup válido.

**Rollback:** `pg_restore` desse dump sobre o banco (com cuidado: apaga o que foi gravado
depois do backup).

### 4.2 P1 — Download

Um comando por concurso:

```bash
venv/bin/python -m src.spider --slug SEFA_PR_25
venv/bin/python -m src.spider --slug BANRISUL_25
```

Gravam em `data/2025/CEBRASPE/<ORGAO>/{Editais,Provas,Gabaritos}/`, mais `.manifest.json`
(com `edital_extracao`, o edital canônico, o "atualizado conforme retificações") e
`provas_texto_link.json`.

**Conferir:**

1. Todo PDF começa com `%PDF-`:
   ```bash
   find data/2025/CEBRASPE/SEFA_PR data/2025/CEBRASPE/BANRISUL -name '*.pdf' \
     -exec sh -c 'head -c 5 "$1" | grep -q "%PDF-" || echo "NAO PDF: $1"' _ {} \;
   ```
   Nada deve aparecer.
2. Contagem por subpasta = `inventario/concursos.jsonl`, campo `contagens`. Regra:
   Provas = `caderno_objetivo` + `caderno_discursivo`; Gabaritos = `gabarito` +
   `padrao_resposta`; Editais = `edital_abertura`.

   | Concurso | Editais | Provas | Gabaritos |
   |---|---:|---:|---:|
   | SEFA_PR_25 | 2 | 8 | 8 |
   | BANRISUL_25 | 2 | 9 | 10 |

3. O log avisa `Found N PDFs NÃO classificados`. É normal se N = `administrativo` +
   `nao_classificado` do inventário (SEFA: 23 = 22 + 1; BANRISUL: 16 = 15 + 1).

**Se falhar:**
- PDF sem `%PDF-`: o link devolveu HTML de erro. Rode o concurso de novo; se persistir,
  confira o link na página ao vivo (ADR-037).
- Contagem diferente do inventário: não siga. Compare o `.manifest.json` com a página do
  concurso. O inventário pode estar velho.

### 4.3 P2 — Chunking do edital (sem LLM, custo zero)

Gate de custo zero: se o chunking estiver errado, não gaste no LLM.

Ainda não há comando no projeto (pendência da C2). A chamada é a mesma de
`scripts/revisar_taxonomia_piloto.py:50-60`, sem o LLM:

```bash
venv/bin/python - <pdf do edital_extracao> <<'PY'
import sys
from pathlib import Path
from src.edital_parser import (dividir_por_cargo_e_materia, extrair_itens_numerados,
                               extrair_secao_objetos_avaliacao_detalhada)
s = extrair_secao_objetos_avaliacao_detalhada(Path(sys.argv[1]))
print(f"cargo={s.cargo_detectado!r} nivel={s.nivel_detectado!r} fim={s.marcador_fim_encontrado}")
for i, c in enumerate(dividir_por_cargo_e_materia(
        s.texto, cargo_padrao=s.cargo_detectado, nivel_padrao=s.nivel_detectado)):
    print(i, c.tipo_conhecimento, c.nivel, c.cargo_numero, c.materia,
          len(extrair_itens_numerados(c.texto)), len(c.texto), sep=" | ")
PY
```

Imprime tipo × nível × cargo × matéria × nº de itens × tamanho. Tempo < 1 s.

**Conferir** (sinais de chunking quebrado):
- chunk com 1 a 40 caracteres;
- matéria com nome de cargo, de área ou de prova;
- nível `None`;
- chunk com mais de 15.000 caracteres;
- matéria engolindo outra (número de itens alto demais).

Resultado desta sessão, depois da correção: SEFA_PR_25 com 22 chunks, BANRISUL_25 com 28.

**Regressão obrigatória ao mudar o parser:** tirar o chunking dos 5 editais do piloto antes
e depois da mudança. Tem que ficar idêntico. Nesta sessão o chunking quebrou em 3 pontos,
todos corrigidos no commit `79a87f5`:
- sub-matérias em romano no meio da linha (SEFA: `I DIREITO CONSTITUCIONAL: ... II DIREITO
  ADMINISTRATIVO:`);
- nível só aparecia em `ESCOLARIDADE EXIGIDA PARA O CARGO` (BANRISUL);
- `ÁREA N` (BANRISUL). Decisão do dono: `ÁREA N` vira cargo N, também no texto do link do
  caderno.

**Se falhar:** não rode o P3. Corrija o parser com teste e rode a regressão dos 5 editais
do piloto.

### 4.4 P3 — Edital pelo LLM (e questões, P4)

```bash
venv/bin/python -m scripts.revisar_taxonomia_piloto \
  data/2025/CEBRASPE/SEFA_PR/Editais/<edital_extracao do SEFA>.pdf
venv/bin/python -m scripts.revisar_taxonomia_piloto \
  data/2025/CEBRASPE/BANRISUL/Editais/<edital_extracao do BANRISUL>.pdf
```

Use o arquivo indicado em `edital_extracao` no `.manifest.json`, não o primeiro PDF da pasta.

Gera `revisao_piloto/<stem>.json`, `.auditoria.json` e `.validacao.json`.

**Atenção:** no fim o script chama `atualizar_revisao`. Isso roda validação, relatório HTML,
Datasette, `stats_writer` (carga do banco de **todos** os concursos com edital) e
`extrair_questoes` (consome a fila de **todos** os PDFs baixados). Também aplica a regra da
árvore. Nesta sessão, a regra criou 94 apontamentos `origem: regra`, já aprovados em
`canonico/arvore.json`. Por isso o P3 já faz o P4.

**Conferir:**
- todos os chunks `sucesso`: campo de topo `falhas: 0`;
- `.validacao.json` com `total_alertas: 0` (nos dois deu 0, e 0 informativos);
- nenhum tópico com nome só numérico;
- nenhum chunk sem tópico.

Custo dos 2 editais juntos: US$ 0,018 (50 chamadas; 33.835 tokens de entrada e 17.716 de
saída). O OpenRouter não mostra o custo em US$ no Langfuse (o modelo não tem preço lá e vem
0). Meça pelo OpenRouter:

```bash
curl -s -H "Authorization: Bearer $OPENROUTER_KEY_TAXONOMIA_EDITAL" \
  https://openrouter.ai/api/v1/key
```

Use o campo `usage_daily`. Para tokens por chamada, o Langfuse API v2 é
`/api/public/v2/observations` (a v1 responde 410).

**Se falhar:**
- `falhas > 0`: rode `scripts/reprocessar_falhas_piloto.py` para o edital. Não aprove.
- `total_alertas > 0`: leia o `.validacao.json`. Item omitido se corrige no dado (ADR-025).
  Não silencie alerta sem olhar.
- Chunking ruim: volte ao P2.

#### P4 — Questões no banco (sai do P3)

Se precisar repetir só a carga:

```bash
venv/bin/python -m src.stats_writer
venv/bin/python -m scripts.extrair_questoes
venv/bin/python -m scripts.extrair_questoes --reprocessar-erros   # só falhas
```

O consumidor usa o lock `pg_try_advisory_lock(5031001)`. Se outro processo estiver rodando,
ele sai sem fazer nada.

Resultado desta sessão:
- 17 cadernos `concluido`;
- SEFA_PR_25: 380 itens ME, 18 anuladas, gabarito X nas anuladas;
- BANRISUL_25: 230 itens ME, 5 anuladas;
- 5 alternativas em toda questão ME; gabarito só A–E (e X nas anuladas);
- 5 discursivas (SEFA 1 caderno, BANRISUL 4), com 3 a 4 quesitos e padrão de resposta;
- básico do BANRISUL ligado aos cargos 1 a 4, e cada `ÁREA N` ligada ao cargo N.

### 4.5 P5 — Conferência

Rode as consultas abaixo depois de P3/P4. Substitua `<slugs>` por `'SEFA_PR_25','BANRISUL_25'`.

**a) Por prova** (cargos, fila, itens, gabarito, alternativas, discursivas):

```sql
SELECT c.slug, p.arquivo, p.tipo, p.codigo_caderno,
       (SELECT string_agg(ce.numero::text, ',' ORDER BY ce.numero)
          FROM provas_cargos pc JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id
         WHERE pc.prova_id = p.id) AS cargos,
       f.status AS fila,
       count(q.id) AS itens,
       count(q.id) FILTER (WHERE q.gabarito IS NULL AND NOT q.anulada) AS sem_gab,
       count(q.id) FILTER (WHERE q.anulada) AS anul,
       min(jsonb_array_length(q.alternativas)) AS alt_min,
       max(jsonb_array_length(q.alternativas)) AS alt_max,
       count(q.id) FILTER (WHERE NOT q.utilizavel) AS inutil,
       (SELECT count(*) FROM discursivas d WHERE d.prova_id = p.id) AS disc
FROM provas p
JOIN concursos c ON c.id = p.concurso_id
LEFT JOIN fila_extracao_questoes f ON f.prova_id = p.id AND f.categoria <> 'gabarito'
LEFT JOIN questoes q ON q.prova_id = p.id
WHERE c.slug IN (<slugs>)
GROUP BY c.slug, p.id, p.arquivo, p.tipo, p.codigo_caderno, f.status
ORDER BY c.slug, p.tipo, p.arquivo;
```

Esperado: nenhuma linha com `fila` diferente de `concluido`; `sem_gab = 0`; `alt_min = alt_max = 5`
nas questões ME; `inutil` só onde o caderno tem fórmula ilegível.

**b) Gabaritos:**

```sql
SELECT c.slug, q.tipo, q.gabarito, count(*)
FROM questoes q
JOIN provas p ON p.id = q.prova_id
JOIN concursos c ON c.id = p.concurso_id
WHERE c.slug IN (<slugs>)
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3;
```

Esperado: só `A`–`E` e `X` (das anuladas). Qualquer outra letra é erro de parser.

**c) Discursivas:**

```sql
SELECT c.slug, p.arquivo, d.numero, left(d.tema, 70) AS tema,
       jsonb_array_length(d.quesitos) AS quesitos, d.padrao_resposta IS NOT NULL AS tem_padrao
FROM discursivas d
JOIN provas p ON p.id = d.prova_id
JOIN concursos c ON c.id = p.concurso_id
WHERE c.slug IN (<slugs>)
ORDER BY 1, 2;
```

Esperado: 5 linhas (SEFA 1, BANRISUL 4); 3 a 4 quesitos cada; `tem_padrao` verdadeiro. Tema
vazio é aceito (tema anafórico vira `None` com alerta, ADR-031): saiu vazio em 2 das 5.

**d) Seções por caderno** (obrigatória):

```sql
SELECT p.arquivo, q.secao, min(q.numero), max(q.numero), count(*)
FROM questoes q
JOIN provas p ON p.id = q.prova_id
JOIN concursos c ON c.id = p.concurso_id
WHERE c.slug IN (<slugs>)
GROUP BY 1, 2
ORDER BY 1, 3;
```

O que conferir: cada caderno com uma seção por cabeçalho de matéria impresso. Na C1a a
seção ME vinha incompleta, e o cabeçalho que faltava ia parar no **fim da alternativa E** da
questão anterior (BANRISUL 002, Q34: "...ao final de cada ciclo. BANCO DE DADOS"): 23 casos.
Corrigido no `src/prova_parser.py` (`_eh_cabecalho_layout_me`: caixa alta, sem dígito nem
código, centralizado na coluna ou em negrito). Depois da correção: BANRISUL 001/002/003/004
com 7/6/6/5 seções, CB1 com 4, SEFA CG1 com 10. Os específicos do SEFA trazem só o nome da
função ("ANALISTA FAZENDÁRIO") antes da questão 1, e esse nome vira a seção do caderno inteiro.

Sinal de defeito: caderno com uma seção só e várias matérias no edital do cargo, ou
alternativa terminando em palavras em caixa alta:

```sql
SELECT p.arquivo, q.numero, right(q.alternativas->-1->>'texto', 60) AS fim_ultima
FROM questoes q JOIN provas p ON p.id = q.prova_id JOIN concursos c ON c.id = p.concurso_id
WHERE c.slug IN (<slugs>)
  AND q.alternativas->-1->>'texto' ~ '[.?!:;)]\s+[A-ZÀ-Ú][A-ZÀ-Ú ,()–-]{3,}$';
```

Nos dados de antes da correção ela achou 20 dos 23 casos (os outros 3 terminam sem
pontuação, ex.: "confidencialidade ARQUITETURA"); por isso a contagem de seções também
entra na conferência.

As colunas da página estão fixas em pt (`COLUNAS_ME`, medidas no SEFA e no BANRISUL). Um
layout diferente perde o cabeçalho de novo, sem cortar nada a mais: esta consulta pega isso.

**e) Invariante do piloto** (rodar depois de todo passo que grava no banco). Filtra pelos 5
slugs do piloto, porque os totais globais sobem com o lote:

```sql
WITH pil AS (
  SELECT p.id FROM provas p JOIN concursos c ON c.id = p.concurso_id
  WHERE c.slug IN ('PF_25_ADM','TCU_25_TEFC','IBAMA_25','STM_25','CD_25_NS'))
SELECT
  (SELECT count(*) FROM questoes WHERE prova_id IN (SELECT id FROM pil)) AS itens,
  (SELECT count(*) FROM questoes WHERE prova_id IN (SELECT id FROM pil) AND anulada) AS anuladas,
  (SELECT count(*) FROM questao_no qn JOIN questoes q ON q.id = qn.questao_id
    WHERE q.prova_id IN (SELECT id FROM pil))
  + (SELECT count(*) FROM discursiva_no dn JOIN discursivas d ON d.id = dn.discursiva_id
    WHERE d.prova_id IN (SELECT id FROM pil)) AS apontamentos,
  (SELECT md5(string_agg(questao_chave, ',' ORDER BY questao_chave)) FROM vw_questoes
    WHERE split_part(questao_chave, '|', 1)
      IN ('PF_25_ADM','TCU_25_TEFC','IBAMA_25','STM_25','CD_25_NS')) AS hash_chaves;
```

Esperado (2026-10-12, antes e depois do lote): `2800 | 129 | 3029 | 3257ba6ba525fdd6b4492733b50882f2`.

**Conferir PDF (3 questões):** escolha 1 básica, 1 específica e 1 com figura. Compare
enunciado, alternativas, texto-base e gabarito do banco com o texto da página do PDF
(PyMuPDF) e com a grade do gabarito definitivo. Figuras ficam em
`data/2025/CEBRASPE/<ORGAO>/Provas/figuras/<codigo>_<pag>_<n>.png`.
Nesta sessão: 3 de 3 iguais. Mas essa comparação não pega o problema da seção (item d).

Defeitos que a conferência de PDF não pega, para a C1b:
- figura vetorial (tabela desenhada) é recortada E o texto da tabela também fica no
  enunciado (BANRISUL, área 2, Q36);
- o recorte da figura pode cortar o título da tabela (Q36, "Clientes").

**Se falhar:** qualquer invariante do piloto que mudou sem motivo = pare, não aprove nada.
Use o backup do P0.

### 4.6 P6 — Árvore: dispersão de conceitos (custo zero)

Roda depois da carga do lote (P3/P4 de todos os editais do lote) e antes da classificação
das questões na C1b. Não usa LLM. Regra (KAN-64): um conceito com nome próprio fica em um
nó só; o detector acha o mesmo conceito sob pais diferentes.

```bash
venv/bin/python -m scripts.detectar_dispersao_arvore --dry-run   # só relatório
venv/bin/python -m scripts.detectar_dispersao_arvore --propor    # grava as propostas
```

O que conferir:
- grupos novos que envolvem nós criados pelos editais do lote;
- norma (lei, LC, decreto) que aparece em dois lugares da árvore: vira proposta para o dono,
  e não é fundida pelo agente;
- o detector erra às vezes (ex.: Receita × Despesa pública), então cada grupo é uma decisão.

Custo: US$ 0.

## 5. Pausas do dono

1. **Revisão do edital (depois do P3):** abrir `https://datasette.projetoathos.com.br/relatorio/index.html`,
   revisar cada edital e gravar `status_revisao_humana = "APROVADO..."` no
   `revisao_piloto/<edital>.json`. O agente nunca aprova (ADR-028).
   - Antes disso o concurso fica `pendente` e fora da estatística oficial.
   - As questões já entram no banco nesse meio-tempo.
2. **Figura e texto da tabela (C1b):** conferir no site a Q36 do BANRISUL.
3. **Dispersão da árvore (P6):** aprovar ou rejeitar as propostas do detector por grupo, nunca
   em bloco (`python -m scripts.curar_arvore --aprovar-proposta <ids>` ou `--rejeitar-proposta <ids>`).
   O detector erra (ex.: Receita × Despesa pública), então cada grupo é uma decisão.

## 6. Armadilhas conhecidas

- **Ordem do lote.** O P3 de um concurso já consome a fila de **todos** os PDFs baixados.
  Se um caderno é processado antes de o edital do concurso dele existir, o log dá
  `[STATS] ...: cargo N sem registro em cargos_editais` e o caderno fica sem cargo até a
  próxima carga. Aconteceu com o BANRISUL na 1ª execução; a 2ª corrigiu.
  **Regra:** baixar o lote inteiro, extrair **todos** os editais do lote, e só depois
  conferir o banco.
- **`gabarito sem caderno ligado`** para `Ed_7_BANRISUL_2025_Gabaritos.pdf` (edital de
  gabaritos **preliminares**). É inofensivo: os definitivos estão ligados.
- **Teste do site ou do parser com o piloto mudando.** Não rode testes contra o piloto
  enquanto ele muda. Tire um snapshot antes.
- **Chunking não é só o LLM.** Um chunk ruim vira alerta no `.validacao.json`, mas um
  chunk que engole outro pode passar sem alerta. Confira o P2 sempre.

## 7. Pendências para o orquestrador (C2, Dagster)

- Comando de chunking sem LLM dentro do projeto (`--so-chunking` ou similar), no lugar do
  script avulso do P2.
- Extrair **todos** os editais do lote antes de uma única carga de banco.
- Consultas a–e como checagens automáticas no relatório do lote (`inventario/lotes/lote_NN.md`).
- Custo pelo OpenRouter (`/api/v1/key`), e não só o Langfuse.
- Consulta (d) e a de alternativa terminando em caixa alta como alerta do lote.
- Invariante do piloto (consulta e) como checagem automática antes e depois do lote.
- Rodar `detectar_dispersao_arvore --propor` como passo fixo depois da carga de cada lote e
  listar as propostas novas no relatório do lote (KAN-64).
