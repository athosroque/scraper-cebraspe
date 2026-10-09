# ADR-038: Suporte a Múltipla Escolha Retrocompatível no Pipeline, Banco e Site

- **Status:** Aceito (site e pipeline implementados; Gate da 8.M pendente, ver §3)
- **Data:** 2026-10-09
- **Etapa:** 8.M (Pré-requisito para ingestão em lotes de 2020 a 2026)
- **Decisores:** Dono do produto e equipe de engenharia

---

## 1. Contexto

Até a conclusão do piloto de 2025 (Etapa 6), o sistema assumia estritamente questões no formato **Certo/Errado** (`C`/`E`/`X`) espalhadas em dezenas de pontos do backend, banco Postgres, regras de negócio de pontuação de simulados e interface web.

No entanto, o inventário completo do CEBRASPE de 2020 a 2026 (Etapa 8.0) revelou que **41 de 83 cadernos amostrados (~50%)** utilizam formato de **Múltipla Escolha** (com 4 ou 5 alternativas consecutivas de A a D ou A a E). A expansão para toda a base histórica exigia destravar o suporte completo a Múltipla Escolha antes de iniciar os lotes de ingestão, garantindo simultaneamente que nenhuma das 2.800 questões do piloto de 2025 sofresse alterações em chaves 5D, hashes ou apontamentos.

---

## 2. Decisões de Arquitetura

### 2.1 Granularidade de Tipo por Questão (e não por Concurso)
O formato é modelado por questão (`questoes.tipo`), permitindo suporte a cadernos mistos ou variações dentro do mesmo certame:
- `tipo = 'certo_errado'` (padrão)
- `tipo = 'multipla_escolha'`

### 2.2 Estrutura de Alternativas e Constraints no Banco de Dados
- Na tabela `questoes` (schema Postgres):
  - Adicionada coluna `tipo VARCHAR(20) NOT NULL DEFAULT 'certo_errado' CHECK (tipo IN ('certo_errado', 'multipla_escolha'))`.
  - Adicionada coluna `alternativas JSONB DEFAULT NULL`.
  - Restrição de `gabarito` expandida de `CHECK (gabarito IN ('C', 'E', 'X'))` para `CHECK (gabarito IN ('A', 'B', 'C', 'D', 'E', 'X'))`.
- Na tabela `app.resposta` (schema `app` do Postgres do projeto, aplicado por `site/scripts/aplicar_schema_app.py`):
  - Restrição de resposta atualizada para `CHECK (resposta IN ('A', 'B', 'C', 'D', 'E'))`.

### 2.3 Estabilidade e Invariância do Hash 5D
Para garantir que as 2.800 questões do piloto mantenham exatamente os mesmos hashes SHA-1 e chaves estáveis 5D (`concurso|caderno|numero`):
- **Certo/Errado:** `calcular_hash_5d` calcula o SHA-1 estritamente sobre o enunciado limpo/normalizado (100% estável).
- **Múltipla Escolha:** `calcular_hash_5d` concatena o enunciado limpo com as alternativas serializadas em JSON determinístico (`json.dumps(alternativas, sort_keys=True, ensure_ascii=False)`), detectando alterações de redação em alternativas.

### 2.4 Parsing de Gabaritos e Provas
- **Gabarito (`src/gabarito_parser.py`):**
  - Reconhecimento de cabeçalhos de linha com `"Questão"` ou `"Item"`.
  - `LETRAS_VALIDAS` expandido para `{"A", "B", "C", "D", "E", "X"}`.
  - Detecção automática de `tipo_detectado` em `GradeGabarito`.
- **Prova (`src/prova_parser.py`):**
  - Ordenação visual de blocos com `_eff_y0`: elimina a inversão causada por blocos vazios ou spans com espaços no topo.
  - Reconhecimento de marcadores de bloco `Questão N`.
  - Segmentação de alternativas `(A)` a `(E)`, suportando continuações multilinha, figuras associadas a enunciados e alternativas, e limpeza de códigos da banca (ex: `<QA01234>`).

### 2.5 Classificação 5D (`scripts/classificar_questoes.py`)
- O prompt do modelo LLM injeta o bloco de alternativas devidamente formatado para itens ME:
  ```
  Item N: <enunciado>
  Alternativas:
  (A) <texto A>
  (B) <texto B>
  ...
  ```
- Para itens CE, a estrutura permanece idêntica à do piloto.

### 2.6 Regras de Negócio do Site e Simulado (`site/`)
- **Resposta conferida pelo tipo:** `C` e `E` existem nos dois formatos (no ME são alternativas), então a letra nunca é validada sozinha. `formatacao.letras_validas(tipo, alternativas)` dá as respostas aceitas: `C`/`E` no certo/errado, as letras das alternativas extraídas no ME (lista vazia aceita A–E). Fora disso:
  - `POST /api/v1/respostas` responde 422 e nada vai para o histórico;
  - `POST /q/correcao` devolve o form com o aviso; o tipo vem do banco, não de campo do form;
  - no simulado, a letra conta como em branco.
- **Pontuação:**
  - `certo_errado`: Acerto = +1, Erro = -1, Em branco = 0, Anulada = 0.
  - `multipla_escolha`: Acerto = +1, Erro = 0, Em branco = 0, Anulada = 0.
- **Interface:**
  - Componente de formulário e card renderiza radio buttons verticais em teal (`destaque-600`) para ME e botões Certo/Errado para CE.
  - Tela de correção destaca a alternativa correta em esmeralda/verde e indica a opção assinalada pelo candidato.
  - Faceta/filtro avançado `tipo` ("Formato") exposto na listagem de questões e na API.
  - OpenAPI 3.1 sincronizado via `exportar_openapi.py`.

---

## 3. Consequências e Validação

1. **Retrocompatibilidade:** as 2.800 questões do piloto seguem com as mesmas chaves 5D (`tests/test_reconciliacao_inventario.py`).
2. **Calibração Real:** Os 3 cadernos ME reais da amostra (`BANRISUL_25`, `SEBRAE_26_PSE_1`, `SEFA_PR_25`) foram extraídos com 100% de sucesso (30, 15 e 50 itens respectivamente).
3. **Testes (2026-10-09):** `make test-all` sobre o `master` com a 8.0 (ADR-037): 1.160 testes (936 em `tests/`, 224 em `site/tests/`), 1.151 passam, 8 pulados, 1 xfail; `ruff check` e `ruff format --check` verdes.
4. **Pendente para o Gate da 8.M:** o banco ainda não tem questão ME (as 4.075 de `vw_questoes` são `certo_errado`), então o caminho ME do site só foi exercitado em teste, com a questão simulada. Faltam a ligação prova ME ↔ gabarito (`task.md`), 1 concurso ME carregado e validado de ponta a ponta no Chromium headless (responder, corrigir, simulado, filtro) e a confirmação, no edital desse concurso, de que o erro no ME não desconta.
