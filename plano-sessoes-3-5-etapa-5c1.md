# Plano — Etapa 5C.1, Sessões 3 a 5 (`correcoes-etapa-5c.md`)

## Contexto

As Sessões 1 e 2 da 5C.1 foram concluídas (posição dos itens e alertas no
banco). Faltam três sessões antes da Etapa 5D:

- **Sessão 3:** fila e gabaritos;
- **Sessão 4:** caderno discursivo;
- **Sessão 5:** documentação e limpeza.

Este plano detalha **como** executar cada item, com arquivos, funções e
testes. Você executa, uma sessão por conversa, e pede a revisão nesta sessão.

Decisões do dono (2026-09-27, não reabrir):
- concorrência por **advisory lock** do Postgres (execução única garantida);
- reprocessar o caderno quando o conjunto de gabaritos ligados mudar, **em
  qualquer status** (inclusive `concluido`);
- `questoes/` continua fora do git (decisão anterior).

Fato conferido nos PDFs reais: todo gabarito diz a versão no **conteúdo**.
Grades trazem `GABARITOS OFICIAIS DEFINITIVOS` (inclusive as com nome em hash
do CD/TCU) e padrões de resposta trazem `PADRÃO DE RESPOSTA DEFINITIVO`. Os
dois PDFs em hash que citam "PRELIMINAR" e "DEFINITIVO" (`CD/036DDD…`,
`PF/F2B1…`) são justificativas de alteração, iguais às do IBAMA/STM.

Verificação padrão (ao fim de cada sessão que mexe no código):

```bash
cd scraper_cebraspe && source venv/bin/activate
pytest -q && ruff check . && ruff format --check src/ scripts/ tests/
python -m scripts.extrair_questoes --reprocessar
```

Os números devem continuar: 70 provas, 2.800 questões, 129 anuladas,
34 discursivas / 107 quesitos, 123 textos-base, 10 figuras e 145 linhas
`concluido` na fila.

---

## Sessão 3 — Fila e gabaritos

Arquivos: `scripts/extrair_questoes.py`, `src/gabarito_parser.py`,
`src/prova_parser.py`, `src/edital_parser.py`,
`src/sql/schema_estatisticas.sql`, `tests/test_extrair_questoes.py`,
`tests/test_gabarito_parser.py`.

### 3.1 Reprocessar quando os gabaritos do caderno mudarem

Hoje um grupo (caderno + gabaritos) só é processado quando alguma linha está
`pendente`/`processando` (`STATUS_PENDENTES`). O `stats_writer` só atualiza o
`prova_id` e nunca mexe em `status` (padrão do CLAUDE.md §6, mantido). Por
isso, um gabarito órfão ligado numa carga posterior não faz o caderno voltar
para a fila.

1. DDL (`schema_estatisticas.sql`, junto dos `ALTER` da 5C):
   `ALTER TABLE fila_extracao_questoes ADD COLUMN IF NOT EXISTS assinatura_grupo TEXT;`
2. `carregar_fila`: incluir `f.sha256` e `f.assinatura_grupo` no `SELECT` e
   em `colunas`.
3. Nova função pura
   `assinatura_grupo(grupo: list[dict]) -> str`: `sha256` de
   `f"{prova_id}|" + "|".join(sorted(l["sha256"] for l in grupo))`.
4. `marcar(...)` ganha `assinatura: str | None = None` e grava
   `assinatura_grupo = COALESCE(%s, assinatura_grupo)`. `processar_caderno`
   calcula a assinatura e a passa nos dois `marcar` finais (`concluido` e
   `erro`, inclusive no `except`).
5. `processar_fila`: substituir o filtro por uma função
   `_motivo_processar(grupo, assinatura, reprocessar, reprocessar_erros) -> str | None`
   que devolve o motivo (`"reprocessar"`, `"pendente"`, `"gabaritos_mudaram"`,
   `"reprocessar_erros"`) ou `None`. `gabaritos_mudaram` vale quando alguma
   linha do grupo tem `assinatura_grupo` diferente da atual, **em qualquer
   status**. Logar `[QUESTOES] <caderno>: reprocessando (<motivo>)`.
   - Um gabarito que sai do caderno A e vai para o B muda a assinatura dos
     dois, e os dois são reprocessados.
   - Na primeira execução depois da migração, todas as assinaturas são
     `NULL`, então os 70 grupos são reprocessados uma vez (equivale a
     `--reprocessar`). É esperado; documentar no resultado da sessão.
6. `--reprocessar-erros` (argparse + parâmetro `reprocessar_erros` em
   `processar_fila`): reprocessa grupos com alguma linha `erro` e órfãos em
   `erro`. Órfãos não têm assinatura. Se um órfão for ligado depois, ele
   entra num grupo e o item 5 cobre o caso.
7. Docstring do módulo: explicar os três gatilhos e a nova flag.

### 3.2 Gabarito preliminar × definitivo

1. `gabarito_parser.py`:
   - constantes `VERSAO_DEFINITIVO = "definitivo"` e
     `VERSAO_PRELIMINAR = "preliminar"`;
   - `classificar_versao(texto: str, nome_arquivo: str = "") -> str | None`,
     que olha **só o cabeçalho**. Ex.:
     `GABARITOS?\s+OFICIA\w*\s+(DEFINITIV|PRELIMINAR)`,
     `PADR[ÃA]O\s+(?:DE\s+RESPOSTAS?\s+)?(DEFINITIV|PRELIMINAR)` e
     `PADR[ÃA]O\s+(DEFINITIV|PRELIMINAR)\w*\s+DE\s+RESPOSTA`. Nunca procurar
     `definitivo` solto: o padrão de resposta do cargo 2 da PF tem
     "definitivo" no corpo. Se o cabeçalho não disser, usar o nome do
     arquivo (`Gab_Definitivo_` / `Gab_Preliminar_`); senão, `None`;
   - `ler_documento` devolve também `"versao"`. Justificativa não recebe
     versão (é classificada antes).
2. `extrair_questoes.py`: generalizar `_escolher_grade` para
   `_escolher_documento(docs, prova, tipo) -> (escolhido, alertas)`, usado
   para grade **e** padrão de resposta (substitui o `padroes[0]`):
   - grade: primeiro filtrar pelo token do caderno, como hoje;
   - preferir `definitivo`; empate desempata pelo nome do arquivo
     (determinístico);
   - mais de um candidato gera o alerta `mais_de_um_gabarito`
     (informativo), com `arquivos` e `versoes`. Substitui
     `mais_de_uma_grade`;
   - escolhido `preliminar` gera o alerta `gabarito_preliminar`
     (informativo);
   - `cabecalho["gabarito_versao"]` e, na discursiva,
     `padrao_resposta_versao` no JSON.

### 3.3 Concorrência: advisory lock

1. `extrair_questoes.py`: `LOCK_FILA_QUESTOES = 5_031_001` (constante com
   comentário: ADR-031, execução única).
2. `processar_fila`, logo depois de `conectar()`: rodar
   `SELECT pg_try_advisory_lock(%s)`. Se devolver `False`, logar
   `[QUESTOES] outra execução em andamento, saindo` e devolver
   `totais | {"ocupado": True}` sem tocar a fila. No `finally`, rodar
   `pg_advisory_unlock`.
   - O lock é de sessão: commit/rollback não o soltam, só o unlock ou o
     fechamento da conexão.
   - O `commit` do `criar_schema` e dos `marcar` não afeta o lock.
3. Com o lock, linha `processando` só pode vir de execução interrompida.
   Manter `processando` em `STATUS_PENDENTES` e ajustar o comentário.
4. ADR-031, linha 40: trocar "Consumidor concorrente da fila" por "consumidor
   de execução única (advisory lock `pg_try_advisory_lock`)". A Sessão 5 só
   confere.

### 3.4 PDFs abertos e leitura dupla

- `edital_parser.extrair_texto_paginas` (linha ~274, usada pelo gabarito e
  pela discursiva): `with pymupdf.open(...) as doc:`.
- `gabarito_parser.ler_grade`: `with`.
- `prova_parser.extrair_caderno_objetivo` (linha ~1095): o `doc` é usado até
  as figuras, então envolver o trecho inteiro no `with`.
- Leitura dupla: `ler_documento` abre o PDF **uma vez**. Criar
  `_ler_grade_doc(doc)` e `_padrao_de_paginas(paginas)`, e manter
  `ler_grade(path)` / `ler_padrao_resposta(path)` como wrappers finos,
  porque os testes usam.
- Opcional, mesmo commit: `edital_parser.py` linhas ~187 e ~414 têm o mesmo
  `open` sem `close`.
- A leitura feita pelo `stats_writer.ligar_gabarito_por_conteudo` é outro
  processo/etapa e fica como está.

### 3.5 Testes

`tests/test_extrair_questoes.py` (fixture `conn`, estilo de
`test_fila_ponta_a_ponta_e_idempotente`):
- caderno objetivo em `erro` `falha_sem_gabarito`: fazer `UPDATE` do
  `prova_id` do gabarito, como o `stats_writer` faria, e rodar
  `processar_fila()` **sem flags**. Resultado esperado: `concluido`;
- caderno `concluido` com o gabarito trocado: é reprocessado;
- nada mudou: a segunda execução processa 0 cadernos (contador ou
  monkeypatch de `processar_caderno`);
- gabarito movido de A para B: os dois são reprocessados;
- `--reprocessar-erros` pega órfão em `erro`;
- dois gabaritos (preliminar + definitivo) do mesmo caderno: vence o
  definitivo e sai `mais_de_um_gabarito`. Só preliminar gera
  `gabarito_preliminar`. O mesmo vale para o padrão de resposta;
- lock: outra conexão segura `pg_advisory_lock(LOCK_FILA_QUESTOES)`, e
  `processar_fila` devolve `ocupado` sem mudar status.

`tests/test_gabarito_parser.py`:
- `classificar_versao`: grade definitiva, grade preliminar, padrão definitivo,
  "definitivo" só no corpo (retorna `None`) e fallback pelo nome;
- `ler_documento` abre o PDF uma vez (monkeypatch contando
  `pymupdf.open`).

### 3.6 Verificação

- Verificação padrão com números iguais.
- Rodar `python -m scripts.extrair_questoes` **sem flags** duas vezes: a 1ª
  reprocessa os 70 (assinatura nula), a 2ª processa 0.
- Conferir que todos os JSONs têm `gabarito_versao = "definitivo"` e zero
  alertas `mais_de_um_gabarito`/`gabarito_preliminar`.
- Marcar os `[ ]`, escrever uma linha de resultado e commitar:
  `fix(scraper-cebraspe): reprocessa caderno quando o gabarito muda, versão do gabarito e lock da fila (Sessão 3)`.

---

## Sessão 4 — Caderno discursivo

Arquivos: `src/prova_parser.py` (bloco "Caderno discursivo", linhas
~1255–1495), `src/gabarito_parser.py` (`dividir_padrao_resposta` e
`ler_padrao_resposta`), `tests/test_prova_parser.py`,
`tests/test_gabarito_parser.py`.

**Antes de mudar qualquer coisa:** gerar uma foto do estado atual das 34
discursivas (`caderno`, `numero`, `titulo`, `tema`, nº de quesitos e soma) a
partir de `questoes/*.json`, salva em `$CLAUDE_JOB_DIR/tmp` ou `/tmp`. A
comparação de antes × depois é a principal evidência da sessão.

### 4.1 Quesitos só a partir do comando

- `PADRAO_COMANDO = re.compile(r"\b(redija|elabore|aborde|discorra|atendendo ao que se pede)\b", re.I)`.
  A lista de verbos deve ser conferida nas 34 discursivas reais.
- `_extrair_quesitos(bloco)`: procurar a sequência 1, 2, ... **só depois do
  primeiro comando**, com os offsets devolvidos relativos ao bloco inteiro.
  Sem comando, usar o comportamento atual e o alerta
  `comando_nao_identificado` (informativo). Para devolver alerta, a função
  passa a retornar uma tupla de 3 ou recebe `alertas: list`, no mesmo estilo
  de `localizar_itens(..., alertas=)` da Sessão 1.
- Anotação correta: `-> tuple[list[dict], int | None]` (ou a nova forma).

### 4.2 Tema anafórico

- `PADRAO_TEMA_ANAFORICO` casa `\b(dess[ae]s?|dest[ae]s?|referid[ao]s?|mencionad[ao]s?|tal|tais)\b`
  no candidato.
- `_tema(enunciado) -> tuple[str | None, str | None]`, com
  `(tema, candidato_rejeitado)`. Candidato anafórico dá `tema=None` e o
  alerta `tema_anaforico` (informativo) com o candidato. Quando não há
  candidato, continua `tema_nao_identificado`.
- Esperado: `057_IBAMA_001_DISC` e `057_IBAMA_002_DISC` passam a ter tema
  nulo com alerta. Qualquer outro tema que mude precisa ser conferido no
  PDF.

### 4.3 Padrão de resposta pelo título e numeração sem buraco

- `_chave_titulo(titulo) -> tuple[str, int | None] | None`:
  `"Questão 2"` → `("questao", 2)`; `"Peça de natureza técnica"` →
  `("peca", None)`; o mesmo para o título da seção do padrão
  (`"Prova Discursiva – Questão 1 – ..."`).
- `ligar_padrao_resposta`:
  1. todas as questões casam uma seção pela chave → liga pela chave;
  2. senão, contagens iguais → liga pela ordem, com o alerta
     `padrao_ligado_por_ordem` (informativo). A exceção é uma questão sem
     título e uma seção só (caso normal), que não gera alerta;
  3. senão, faz como hoje (`padrao_resposta_nao_dividido`).
- Numeração em `extrair_caderno_discursivo`: o número do título, quando
  existe (`Questão 3` → 3). Senão, um contador que só avança em bloco não
  vazio. Número repetido ou buraco geram o alerta `numeracao_discursiva`
  (informativo).

### 4.4 Alertas de valor e quesitos

- Quesitos em que algum `valor_pontos` é `None` → `quesito_sem_valor`
  (informativo, com os números). Hoje a soma é pulada em silêncio
  (`PF_25_ADM_DISC_011`).
- Nenhum quesito → `sem_quesitos` (informativo) (`094_PF_DISC_015`).

### 4.5 Rodapé do CD no padrão de resposta

- Primeiro, inspecionar o texto real (`CD/D5F3…pdf` e `CD/1C23…pdf` em
  `Provas/`, via `extrair_texto_paginas`) para ver o formato exato do rodapé
  e se ele se repete por página.
- Recomendado: em `ler_padrao_resposta`, remover linhas que se repetem em
  ≥ 2 páginas nas últimas N linhas de cada página (rodapé genérico). Se o
  documento tiver 1 página, usar uma regex específica
  (`^\s*CÂMARA DOS DEPUTADOS\s*\|.*$` + linha do código). Nunca remover
  linha só por estar em caixa alta.

### 4.6 Testes sintéticos (um por item)

- enunciado com "1 de janeiro de 2020" antes do comando, e o quesito 1
  continua sendo o real;
- tema "dessa contratação" → nulo + `tema_anaforico`;
- padrão com seções fora de ordem (Questão 2 antes da 1) liga certo;
- bloco vazio no meio não cria buraco no `numero`;
- `quesito_sem_valor` e `sem_quesitos`;
- rodapé removido do padrão (texto sintético de 2 páginas).

### 4.7 Verificação

- Verificação padrão: **107 quesitos** e 34 discursivas mantidos.
- Diff da foto de 4.0: listar cada tema/número/ligação que mudou e conferir
  no PDF.
- Commit:
  `fix(scraper-cebraspe): quesitos a partir do comando, tema anafórico e padrão de resposta por título (Sessão 4)`.

---

## Sessão 5 — Documentação e limpeza

Sem código de produção. Checklist com os pontos exatos:

- `task.md:592` e ADR-031 linha 50: 124 → **123** textos-base.
- ADR-031 linha 31: "interseções verticais" → "figura ligada à linha logo
  acima na mesma coluna com sobreposição horizontal; exceção item →
  preâmbulo". A linha 40 deve já estar corrigida pela Sessão 3; só
  conferir.
- CLAUDE.md:
  - §6, bullet "Segmentação de cadernos": trocar "span próprio em negrito"
    por "x0 na margem da coluna (cluster/moda); duplicado/fora de ordem é
    bloqueante";
  - §6: novos bullets da Sessão 3 (assinatura do grupo, advisory lock,
    versão do gabarito pelo cabeçalho) e da Sessão 4 (quesitos a partir do
    comando, tema anafórico, padrão por título);
  - §7: anti-patterns correspondentes (ex.: "nunca procurar `definitivo`
    solto no corpo do padrão");
  - §12: entrada da 5C.1 e a nota do topo "ADR-001 a ADR-029" → incluir
    ADR-031 (ADR-030 reservado à 5B.1);
  - §5: contagem de testes atualizada e a 5C.1 marcada.
- `scripts/extrair_questoes.py:11`: tirar "(versionados)".
- `git rm concluir-etapa-5c.md`.
- ADR-031: recolocar as decisões perdidas (falha não grava parcial;
  justificativa de alteração fica `concluido`; só figura raster; trecho sem
  recuo anexado ao item com alerta), a convenção dos 3 formatos de nome de
  caderno discursivo (`094_PF_014_DISC`, `094_PF_DISC_015`,
  `PF_25_ADM_DISC_001`, que vêm do CEBRASPE) e as decisões das Sessões 3/4.
- `ruff format src/stats_writer.py tests/test_prova_parser.py`, e depois
  `ruff format --check` limpo.
- Opcional: `docs/conferencia-5c.md` com a conferência manual dos 3 cadernos.
- `LESSONS.md`: registrar se a Sessão 3/4 revelar um gotcha que custou tempo
  (ex.: "definitivo" no corpo do padrão de resposta).
- Fechar: `[x]` na 5C.1 do `task.md`, a linha de prioridade (CLAUDE.md §5 e
  `task.md:306`) apontando para 5B/5B.1 → 5D, e os `[ ]` da Sessão 5 no
  `correcoes-etapa-5c.md`.
- Commit: `docs(scraper-cebraspe): alinha ADR-031 e CLAUDE.md às correções da 5C.1 (Sessão 5)`.

---

## O que vou conferir quando você pedir a revisão

- **S3:**
  - a assinatura é gravada em todos os caminhos de `marcar` (inclusive no
    `except`);
  - o lock é liberado no `finally`;
  - "definitivo" é casado só no cabeçalho;
  - os testes cobrem gabarito ligado depois, `concluido` reprocessado e
    segunda execução sem trabalho;
  - os números do banco não mudaram.
- **S4:**
  - a foto antes × depois das 34 discursivas;
  - os 107 quesitos;
  - cada tema alterado tem justificativa;
  - nenhuma remoção de rodapé come conteúdo.
- **S5:**
  - `grep` por "124", "interseção", "concorrente" e "versionados" sem
    sobras;
  - `ruff format --check` verde.

## Entrega deste plano

Depois da aprovação, copiar este arquivo para
`scraper_cebraspe/plano-sessoes-3-5-etapa-5c1.md`, adicionar em
`correcoes-etapa-5c.md` um link para ele ("detalhamento das Sessões 3–5") e
commitar (`docs(scraper-cebraspe): plano detalhado das Sessões 3 a 5 da 5C.1`).
