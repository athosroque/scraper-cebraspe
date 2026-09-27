# Correções da Etapa 5C — plano por sessão

Origem: revisão da Etapa 5C (commits `412ac26..5bef5f3`, ADR-031) feita em
2026-09-26. A 5C funciona nos dados reais (374 testes, 2.800 itens, 0 buraco
de numeração, gabarito↔cargo correto nos 42 cadernos). Os achados abaixo são
falhas **silenciosas** que ainda não afetaram os dados, mais dívidas de
documentação. Resolver as sessões 1 a 3 **antes da Etapa 5D**.

## Como usar

- Uma sessão por vez, na ordem. Na nova conversa, diga só:
  `execute a sessão N de scraper_cebraspe/correcoes-etapa-5c.md`.
- Leia **apenas** a seção da sessão pedida e os arquivos citados nela. Não
  releia `task.md`/ADRs inteiros: o contexto necessário está aqui.
- Ao terminar, marque os `[ ]` da sessão, anote o resultado em uma linha
  embaixo dela e commite (`fix(scraper-cebraspe): ...`).

**Detalhamento das Sessões 3–5:** `plano-sessoes-3-5-etapa-5c1.md` (funções,
testes e verificação por item; decisões de 2026-09-27: advisory lock e
reprocessar em qualquer status quando os gabaritos do caderno mudarem).

**Decisão do dono (não reabrir):** `questoes/` **não** é versionado
(gitignored, regenerável por `scripts/extrair_questoes.py`).

**Verificação padrão ao fim de toda sessão que mexe no parser/writer:**

```bash
cd scraper_cebraspe && source venv/bin/activate
pytest -q && ruff check . && ruff format --check src/ scripts/ tests/
python -m scripts.extrair_questoes --reprocessar
```

Depois, no Postgres (`127.0.0.1:5435`), os números devem continuar: 70 provas,
2.800 questões, 129 anuladas, 34 discursivas / 107 quesitos, **123**
textos-base, 10 figuras, 145 linhas `concluido` na fila. Se algum mudar,
explicar o porquê antes de commitar.

---

## Sessão 1 — Posição dos itens no caderno objetivo (prioridade máxima)

**Problema (confirmado com entrada sintética):** `localizar_itens`
(`src/prova_parser.py`) aceita a primeira linha cujo primeiro span é o número
esperado. Uma célula de tabela ou lista numerada com número dentro da faixa
do gabarito, antes do item real, vira o item. A validação só compara
contagem, e `marcadores_fora_do_gabarito` só olha fora da faixa — o caderno
sai `sucesso` com enunciados trocados. Ex. sintético: tabela "2", "3" antes
dos itens reais → item 2 = "12,5", item 3 = "14,0 Julgue ... 2 Segundo item
real. 3 Terceiro item real.". Nos dados reais há números assim em
`167_CDNS_CG1_01` (p. 4) e `094_PF_005_01` ("111"), hoje só depois do item
verdadeiro. O CLAUDE.md §6 diz "span próprio em negrito", mas o código não
confere fonte nem flags.

- [x] Exigir que o marcador seja negrito (`span["flags"] & 16` ou fonte com
      `Bold`) — medir antes nos 42 cadernos se 100% dos marcadores reais são
      negrito; se não forem, usar x0 na margem da coluna como critério
      alternativo.
- [x] Número candidato que aparece mais de uma vez como marcador vira alerta
      **bloqueante** (caderno em falha explícita, nunca escolha silenciosa).
- [x] Ordenação de linhas: hoje é `(coluna, y0)`; incluir `x0` como
      desempate, como documentado.
- [x] Testes novos (linhas sintéticas, no estilo dos de `tests/test_prova_parser.py`):
      número em tabela dentro da faixa; número duplicado; item que cruza
      coluna; item que cruza página; página de duas colunas com bloco de
      largura total no meio (hoje é só suspeita: conferir se inverte a ordem).
- [x] Verificação padrão (nada nos dados reais deve mudar).

Resultado: Medição confirmou 9,64% negrito (só CD); adotado x0 na margem via cluster/moda (~28.3 e ~303.4 pt); duplicados e fora de ordem geram alerta bloqueante; teste de bloco largo marcado xfail; 380 testes (+1 xfail) e base de 2.800 itens inalterada no Postgres.

## Sessão 2 — Alertas por item no banco e fidelidade do texto

**Problema:** 19 itens de `094_PF_005_01` com `�` estão no banco como
questões válidas (ex.: item 58 "E�� � 5."). O alerta `simbolo_ilegivel` só
existe no JSON; 5D/5E e o simulado não têm como saber. Além disso,
`juntar_linhas` achata blocos de código/tabela (STM_003/006: YAML, Java,
JSON), perdendo quebras e indentação.

- [x] Coluna em `questoes` (DDL em `src/sql/`, com `ALTER ... IF NOT EXISTS`)
      para alertas do item — ex.: `alertas text[]` ou `jsonb` — gravada por
      `src/questoes_writer.py` a partir dos alertas do JSON (símbolo
      ilegível, trecho sem recuo anexado, figura mencionada sem imagem).
- [x] Um jeito simples de a 5D/5E excluir item problemático (ex.: coluna
      `utilizavel boolean` ou view que filtra `simbolo_ilegivel`).
- [x] Preservar `\n` e indentação quando o bloco é código ou tabela
      (detectar por fonte monoespaçada ou alinhamento em colunas); teste com
      trecho real do STM.
- [x] Garantir que `questoes.texto_base_id` aponta para texto-base da mesma
      prova (checagem no writer ou constraint).
- [x] Verificação padrão.

Resultado: Colunas `alertas text[]` e `utilizavel boolean`, índices e view `vw_questoes_utilizaveis` criados no banco; 19 itens ilegíveis marcados como utilizavel=false; FK composta com ON DELETE SET NULL (texto_base_id); detecção refinada de código/tabela elimina falsos positivos de prosa (caindo para 23 itens) e calcula indentação Python por x0 (PF_005 itens 110-115); 391 testes (+1 xfail) passando e base de 2.800 itens inalterada no Postgres.

Detalhes da revisão (2ª rodada): recuo de código pela posição do x0 entre os x0 distintos do bloco (sem as constantes 24,7/14,2 pt); linha de código quebrada na borda da coluna volta para a de cima (recuo menor, ou mesmo recuo com delimitador aberto); `$ VAR` → `$VAR` só em código; menos e × da fonte Symbol (``, ``) traduzidos; FK só é recriada quando falta `SET NULL (texto_base_id)` (PostgreSQL 15+). 9 textos mudaram (STM_003 72/73/86/90, PF_005 110/113 e texto-base 10, PF_007 87 e texto-base 4); 401 testes (+1 xfail) e contagens do banco inalteradas.

## Sessão 3 — Fila e gabaritos

**Problemas (confirmados por leitura; o próprio teste mostra o 1º):**
1. `STATUS_PENDENTES` em `scripts/extrair_questoes.py` só pega
   `pendente`/`processando`. Caderno que caiu em `erro` (ex.:
   `falha_sem_gabarito`) nunca volta, mesmo quando uma carga posterior do
   `stats_writer` liga o gabarito (a fila só atualiza `prova_id`, sem mexer
   em `status`) ou quando o parser é corrigido.
2. Preliminar × definitivo não se distinguem: com dois gabaritos do mesmo
   caderno vale o primeiro por nome de arquivo (arbitrário no nome em hash).
   Padrão de resposta com mais de um arquivo usa `padroes[0]` sem alerta.
   Hoje só há definitivos nos dados.
3. ADR-031 diz "consumidor concorrente", mas não há
   `FOR UPDATE SKIP LOCKED`, e linha `processando` de outra execução ativa é
   reprocessada.

- [x] Reprocessar automaticamente o grupo em `erro` quando algum `prova_id`
      dele mudar (guardar os `sha256`/`prova_id` vistos no processamento) e
      criar `--reprocessar-erros`.
- [x] Classificar gabarito como preliminar/definitivo (texto do link e/ou
      conteúdo do PDF), preferir definitivo, alerta quando houver mais de um
      candidato para o mesmo caderno (grade e padrão de resposta).
- [x] Concorrência: implementar `SKIP LOCKED` **ou** corrigir o texto do
      ADR-031 para "execução única". Escolher o mais simples (execução é
      manual/local).
- [x] Pequenos: `pymupdf.open` sem `close()` em `ler_grade` e
      `extrair_caderno_objetivo` (usar `with`); PDF de gabarito lido duas
      vezes.
- [x] Testes: gabarito ligado depois → caderno reprocessado; dois gabaritos
      do mesmo caderno.
- [x] Verificação padrão.

Resultado: Assinatura de grupo por sha256 na fila reprocessa cadernos quando gabaritos mudam; flag --reprocessar-erros; advisory lock exclusivo (5_031_001) para execução única; classificar_versao restrito ao cabeçalho com fallback por nome e seleção determinística; PDFs fechados com context manager e leitura única; 415 testes (+1 xfail) passando e 70 cadernos / 2.800 itens inalterados no Postgres.


## Sessão 4 — Caderno discursivo

**Problemas:**
1. (Confirmado com entrada sintética) `PADRAO_QUESITO` / `_extrair_quesitos`:
   qualquer linha do enunciado que comece com "1 " (ex.: "1 de janeiro...")
   vira o quesito 1; o "1" real é engolido e a soma de `[valor]` continua
   batendo, então `soma_quesitos_divergente` não dispara. Dados reais não
   afetados.
2. Tema: 13 de 34 saem nulos (com alerta); alguns saem errados sem alerta
   (`057_IBAMA_001_DISC` → "dessa contratação"; `057_IBAMA_002_DISC` → "a
   implantação do referido sistema..."), e vão para `provas.tema`.
3. `ligar_padrao_resposta` liga por ordem, não por título ("Questão N" /
   "Peça"). O `numero` da discursiva vem do `enumerate` sobre blocos e conta
   blocos vazios pulados (pode ter buraco).
4. Soma não conferida e sem alerta quando falta `[valor]`
   (`PF_25_ADM_DISC_011`) ou não há quesitos (`094_PF_DISC_015`).
5. Padrão de resposta do CD carrega o rodapé ("CÂMARA DOS DEPUTADOS | CARGO 1
   ... CÓDIGO").

- [x] Quesitos só a partir do comando ("aborde os seguintes aspectos",
      "redija...") e/ou exigir sequência 1, 2, ... com `[valor]`.
- [x] Tema: rejeitar candidato anafórico ("dessa", "desse", "referido",
      "a implantação do...") e alertar; manter nulo com alerta quando não
      achar.
- [x] Ligar padrão de resposta pelo título; numerar discursiva sem contar
      blocos pulados.
- [x] Alerta informativo quando não há `[valor]` ou não há quesitos.
- [x] Remover rodapé do CD no padrão de resposta.
- [x] `_extrair_quesitos` está anotado `-> list[dict]` mas devolve tupla:
      corrigir a anotação.
- [x] Testes sintéticos para cada item acima. Verificação padrão (107
      quesitos devem se manter; se um tema mudar, conferir no PDF).

Resultado: Quesitos extraídos após comando sem falso positivo de datas; tema anafórico rejeitado com alerta (IBAMA 001/002 passam a None com justificativa); padrão ligado por chave de título e numeração contínua sem buracos; alertas sem_quesitos e quesito_sem_valor ativos; cabeçalhos/rodapés institucionais removidos; 435 testes (+1 xfail) passando e contagens da base inalteradas (34 discursivas, 107 quesitos mantidos).


## Sessão 5 — Documentação e limpeza (depois das anteriores)

- [x] `task.md` (bloco "Concluída" da 5C) e ADR-031: 124 → **123**
      textos-base.
- [x] CLAUDE.md §6/§7/§12 e ADR-031 alinhados ao que as sessões 1–4
      entregaram (negrito/x0 na segmentação; figura ligada à linha logo
      acima na mesma coluna com sobreposição horizontal, com a exceção item →
      preâmbulo — não "interseção vertical"; concorrência).
- [x] CLAUDE.md §12, nota do topo: "ADR-001 a ADR-029" → incluir ADR-031
      (ADR-030 reservado à 5B.1).
- [x] Docstring de `scripts/extrair_questoes.py`, passo 3: tirar
      "(versionados)".
- [x] Remover `concluir-etapa-5c.md` (plano obsoleto: tudo `[ ]`, "371
      testes", manda commitar `questoes/`).
- [x] Recolocar no ADR-031 as decisões que sumiram do `task.md`: falha não
      grava parcial; justificativa de alteração fica `concluido`; só figura
      raster; trecho sem recuo é anexado ao item com alerta.
- [x] Registrar em ADR-031 a convenção dos nomes de caderno discursivo (há 3
      formatos no mesmo concurso: `094_PF_014_DISC`, `094_PF_DISC_015`,
      `PF_25_ADM_DISC_001`) — só documentar, vêm do CEBRASPE.
- [x] `ruff format` em `src/stats_writer.py` e `tests/test_prova_parser.py`.
- [x] Opcional: artefato da conferência manual dos 3 cadernos (ex.: nota em
      `docs/` com item, texto do PDF e texto extraído).
- [x] Ao fechar: marcar a Etapa 5C.1 como `[x]` no `task.md`.

Resultado: ADR-031, CLAUDE.md e task.md totalmente alinhados às entregas das Sessões 1–4; 123 textos-base corrigidos; concluir-etapa-5c.md removido; lição adicionada em LESSONS.md; ruff format --check e pytest (435 testes + 1 xfail) 100% verdes.

