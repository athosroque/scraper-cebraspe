# Plano — Etapa 5D: Classificação das Questões na Árvore Mestre

> **Documento autocontido para execução em 3 sessões (uma por conversa).**  
> Não requer reler `task.md` ou ADRs anteriores para ser executado.  
> Base normativa: ADR-022 (erros tipados LLM), ADR-028/030 (canônico como fonte da verdade, banco derivado), ADR-031 (extração de cadernos e gabaritos).

---

## 1. Contexto e Motivação

A **Etapa 5B.2** concluiu com sucesso a curadoria da árvore mestre (`canonico/arvore.json`, com 3.577 nós ativos distribuídos entre matérias, assuntos e subassuntos). A **Etapa 5C/5C.1** extraiu de forma determinística 2.800 itens objetivos (42 cadernos) e 34 discursivas (28 cadernos).

O objetivo da **Etapa 5D** é estabelecer a ponte entre cada questão extraída e os nós da árvore mestre. Esta classificação é a fundação para:
1. As estatísticas oficiais de *"o que mais cai"* e *"edital × prova"* (**Etapa 5E**);
2. Os filtros de navegação hierárquica e simulados no site público (**Etapa 5F**).

A regra central (ADR-030 §6) determina que cada questão deve ser classificada no **nó mais específico possível** (de preferência um subassunto; ou um assunto quando nenhum subassunto atender).

---

## 2. Decisões Fechadas pelo Dono (2026-09-29, não reabrir)

1. **Confiança categórica:**
   - Valores restritos: `alta` | `media` | `baixa`.
   - O critério é formalizado explicitamente no prompt do modelo.
2. **Cardinalidade e papéis dos nós por questão:**
   - Até 2 nós por questão.
   - 1 nó `principal` obrigatório.
   - Apenas se a questão for genuinamente interdisciplinar, 1 nó `secundario` opcional.
3. **Cálculo de `fora_do_edital` é estritamente local:**
   - O LLM **não** decide se a questão está fora do edital.
   - O script calcula a flag booleana localmente:
     - Se o nó escolhido veio dos **candidatos preferenciais** (edital do cargo): `fora_do_edital = false`.
     - Se o nó escolhido veio dos **candidatos de reserva** (subárvore global da matéria): `fora_do_edital = true`.
4. **Fonte canônica da verdade:**
   - A classificação reside em `canonico/classificacao_questoes.json`, versionado no repositório, com formatação estável (ordenado por chave, uma linha por registro, no padrão de `canonico/arvore.json`).
   - O banco PostgreSQL é **derivado**: recarregável a qualquer momento e reverte qualquer edição manual direta nas tabelas.
5. **Instabilidade de `questoes.id` e chave natural:**
   - `questoes_writer.gravar_caderno_objetivo` faz `DELETE + INSERT` a cada reextração do caderno.
   - Por isso, a amarração não pode depender de IDs seriais do banco.
   - A chave natural canônica é:
     - Objetivas: `<slug_concurso>|<codigo_caderno>|<numero>`
     - Discursivas: `<slug_concurso>|<codigo_caderno>|D<numero>`
   - Cada registro canônico guarda o `hash_enunciado` (SHA-1). Se uma reextração alterar o enunciado, o registro é marcado como desatualizado e elegível para nova classificação.
6. **Governança de aprovação:**
   - O LLM e os scripts apenas **propõem** (`status = 'proposto'`, `origem = 'llm'`).
   - **O agente nunca aprova em nome do dono.** Somente o dono executa ações de aprovação ou rejeição via CLI.
   - Sem criação automática de nós: se nenhum nó servir mesmo na reserva, o item fica registrado como `sem_no` e entra na fila de pendências do dono (ADR-030 §5).

---

## 3. Números Medidos no Banco (2026-09-29)

- **Candidatos preferenciais por caderno (`vw_arvore_edital_por_cargo` × `provas_cargos`):**
  - Conhecimentos básicos: 43 a 187 nós (média de 99 nós, abrangendo 3 a 10 matérias).
  - Conhecimentos específicos: 18 a 502 nós (média de 129 nós, abrangendo 1 a 12 matérias).
- **Estrutura dos cadernos:**
  - 733 seções distintas nos enunciados.
  - 530 questões com texto-base compartilhado (total de 123 textos-base).
  - 2.270 questões sem texto-base.
- **Situação de itens:**
  - 129 itens anulados no gabarito oficial.
  - 19 itens marcados como não utilizáveis (`simbolo_ilegivel`).
- **Granularidade dos lotes:**
  - Total estimado de ~300 lotes para chamada ao LLM (agrupamento por texto-base ou blocos de até 10 itens por seção).

---

## 4. Desenho de Arquitetura e Modelo de Dados

### 4.1 Estrutura do Arquivo Canônico (`canonico/classificacao_questoes.json`)

Armazenado como um JSON ordenado, com chaves naturais e registros em uma linha cada:

```json
{
  "registros": {
    "PF_25_ADM|094_PF_CB1_01|1": {
      "hash_enunciado": "4a5b6c...",
      "sem_no": false,
      "apontamentos": [
        {
          "no_id": "NS-a1b2c3d4e5",
          "papel": "principal",
          "confianca": "alta",
          "fora_do_edital": false,
          "origem": "llm",
          "status": "proposto"
        }
      ]
    },
    "PF_25_ADM|094_PF_CB1_01|2": {
      "hash_enunciado": "9f8e7d...",
      "sem_no": false,
      "apontamentos": [
        {
          "no_id": "NS-1122334455",
          "papel": "principal",
          "confianca": "media",
          "fora_do_edital": false,
          "origem": "llm",
          "status": "proposto"
        },
        {
          "no_id": "NS-9988776655",
          "papel": "secundario",
          "confianca": "baixa",
          "fora_do_edital": true,
          "origem": "llm",
          "status": "proposto"
        }
      ]
    }
  }
}
```

### 4.2 Banco de Dados (`src/sql/schema_estatisticas.sql`)

Tabelas ponte N:N e views correspondentes:

```sql
-- Classificação de questões objetivas
CREATE TABLE IF NOT EXISTS questao_no (
    questao_id INTEGER NOT NULL REFERENCES questoes (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id),
    papel TEXT NOT NULL CHECK (papel IN ('principal', 'secundario')),
    confianca TEXT NOT NULL CHECK (confianca IN ('alta', 'media', 'baixa')),
    fora_do_edital BOOLEAN NOT NULL DEFAULT false,
    origem TEXT NOT NULL CHECK (origem IN ('llm', 'humano')),
    status TEXT NOT NULL CHECK (status IN ('proposto', 'aprovado', 'rejeitado')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (questao_id, no_id)
);

CREATE INDEX IF NOT EXISTS idx_questao_no_no ON questao_no (no_id);
CREATE INDEX IF NOT EXISTS idx_questao_no_status ON questao_no (status);

-- Classificação de discursivas
CREATE TABLE IF NOT EXISTS discursiva_no (
    discursiva_id INTEGER NOT NULL REFERENCES discursivas (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id),
    papel TEXT NOT NULL CHECK (papel IN ('principal', 'secundario')),
    confianca TEXT NOT NULL CHECK (confianca IN ('alta', 'media', 'baixa')),
    fora_do_edital BOOLEAN NOT NULL DEFAULT false,
    origem TEXT NOT NULL CHECK (origem IN ('llm', 'humano')),
    status TEXT NOT NULL CHECK (status IN ('proposto', 'aprovado', 'rejeitado')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (discursiva_id, no_id)
);

-- View oficial para estatísticas e simulados (apenas registros aprovados, com nó efetivo resolvido)
CREATE OR REPLACE VIEW vw_questao_no AS
SELECT
    qn.questao_id,
    q.prova_id,
    p.codigo_caderno,
    q.numero,
    q.enunciado,
    q.gabarito,
    q.anulada,
    q.utilizavel,
    nc.no_efetivo AS no_id,
    nc.nivel AS no_nivel,
    nc.nome AS no_nome,
    nc.caminho AS no_caminho,
    nc.materia_id,
    nc.assunto_id,
    qn.papel,
    qn.confianca,
    qn.fora_do_edital,
    qn.origem
FROM questao_no qn
JOIN questoes q ON q.id = qn.questao_id
JOIN provas p ON p.id = q.prova_id
JOIN vw_no_caminho nc ON nc.id = qn.no_id
WHERE qn.status = 'aprovado';
```

### 4.3 Carga Idempotente (`src/stats_writer.py`)

- `stats_writer.aplicar_classificacao(conn, classificacao_path)`:
  1. Carrega `canonico/classificacao_questoes.json`.
  2. Mapeia chaves naturais `<concurso>|<codigo_caderno>|<numero>` para `questoes.id` e `<concurso>|<codigo_caderno>|D<numero>` para `discursivas.id`.
  3. Insere/atualiza registros em `questao_no` e `discursiva_no` (com todos os status, permitindo auditoria no banco).
  4. Integrado em `atualizar_revisao._gravar_banco_estatisticas` e no final de `scripts/extrair_questoes.py` (garantindo que um reprocessamento com `DELETE + INSERT` em `questoes` restaure imediatamente a ponte de classificação sem intervenção manual).

---

## 5. Sessões de Execução

---

### Sessão A — Modelo, Candidatos e Banco (sem LLM)

**Objetivo:** Construir toda a infraestrutura determinística de dados, modelos em memória, resolução de candidatos preferenciais/reserva, particionamento de lotes e persistência no PostgreSQL, com testes completos.

#### Checklist

- `[x]` **Módulo canônico `src/classificacao.py`:**
  - `@dataclass ApontamentoQuestao`: `no_id`, `papel: Literal['principal', 'secundario']`, `confianca: Literal['alta', 'media', 'baixa']`, `fora_do_edital: bool`, `origem: Literal['llm', 'humano']`, `status: Literal['proposto', 'aprovado', 'rejeitado']`.
  - `@dataclass RegistroQuestao`: `chave: str`, `hash_enunciado: str`, `sem_no: bool`, `apontamentos: list[ApontamentoQuestao]`.
  - `@dataclass ClassificacaoQuestoes`: `registros: dict[str, RegistroQuestao]`.
  - Funções canônicas:
    - `chave_questao(concurso: str, codigo_caderno: str, numero: int | str, discursiva: bool = False) -> str`
    - `calcular_hash_enunciado(enunciado: str) -> str`
    - `carregar(path: Path = CLASSIFICACAO_PADRAO) -> ClassificacaoQuestoes`
    - `salvar(classificacao: ClassificacaoQuestoes, path: Path = CLASSIFICACAO_PADRAO) -> None` (uma linha por registro, ordenado por chave).
  - Validações de integridade (`ClassificacaoInvalida`):
    - Nó deve existir e estar com status `ativo` (ou ser resolvido para nó ativo via `arvore.resolver_no`).
    - Máximo de 2 apontamentos por questão.
    - Exatamente 1 apontamento com papel `principal` (se houver apontamentos e não for `sem_no`).
    - Se houver segundo apontamento, deve ter papel `secundario`.
  - Funções de curadoria:
    - `mapear_questao(classificacao, arv, chave, hash_enunciado, nos_papeis, confianca, fora_do_edital, origem="humano", status="aprovado")`
    - `aprovar_apontamento(classificacao, chave, no_id)`
    - `rejeitar_apontamento(classificacao, chave, no_id)`
    - `aprovar_lote(classificacao, confianca="alta", caderno=None) -> int` (aprova em lote propostas com a confiança indicada).
- `[x]` **Módulo de candidatos e lotes `src/candidatos_questao.py`:**
  - `candidatos_preferenciais(conn, prova_id: int) -> dict[str, dict]`:
    - Consulta `vw_arvore_edital_por_cargo` combinada com `provas_cargos` da prova.
    - Filtra por tipo de caderno:
      - Caderno básico (`tipo == 'objetiva'` e itens básicos): nós com `tipo_conhecimento = 'basico'`.
      - Caderno específico: nós com `tipo_conhecimento` específico.
      - Caderno discursivo: todos os nós associados ao(s) cargo(s) da prova.
    - Resolve nós fundidos para `no_efetivo` via `vw_no_caminho`.
    - **Inclusão de ancestrais:** garante que todos os pais (`assunto` e `materia`) dos subassuntos contemplados estejam presentes na lista de candidatos (permitindo que o item caia num assunto caso nenhum subassunto seja estritamente adequado).
    - Retorna dicionário `{no_id: {"nome": ..., "nivel": ..., "caminho": ..., "materia_id": ...}}`.
  - `candidatos_reserva(arv: ArvoreMestre, materias_ids: set[str]) -> dict[str, dict]`:
    - Extrai toda a subárvore ativa das matérias envolvidas no caderno (usando `arvore.materia_do_no`).
    - Utilizado como segunda camada caso a questão não pertença aos nós explícitos do edital do cargo.
  - `montar_lotes(questoes: list[dict]) -> list[list[dict]]`:
    - Agrupamento determinístico:
      1. Questões com o mesmo `texto_base_id` devem permanecer no mesmo lote.
      2. Questões consecutivas da mesma `secao`.
      3. Lotes são limitados a no máximo 10 itens; grupos pequenos adjacentes da mesma seção são agrupados até atingir ~10 itens.
- `[x]` **Schema do Banco de Dados (`src/sql/schema_estatisticas.sql`):**
  - Criação das tabelas `questao_no` e `discursiva_no` (FK ON DELETE CASCADE para questões/discursivas, FK para `no_arvore`, checks de domínio, timestamps).
  - Criação da view `vw_questao_no` (filtrando `status = 'aprovado'` e integrando com `vw_no_caminho`).
  - Execução idempotente compatível com o histórico de migrações (`CREATE TABLE IF NOT EXISTS`, índices, grants).
- `[x]` **Carga e sincronização (`src/stats_writer.py`):**
  - Implementação de `aplicar_classificacao(conn, path: Path) -> dict[str, int]`.
  - Resolução estável de chaves: `<concurso>|<codigo_caderno>|<numero>` → `questoes.id` via `provas.codigo_caderno` e `questoes.numero`.
  - Inserção/atualização atômica em lote (`execute_batch`).
  - Chamada automática no final de `atualizar_revisao._gravar_banco_estatisticas`.
  - Chamada automática no final de `scripts/extrair_questoes.py::processar_fila` (recuperando a classificação se houver reextração de cadernos).
- `[x]` **Testes automatizados (`tests/test_classificacao.py` e `tests/test_candidatos_questao.py`):**
  - Serialização e desserialização de `canonico/classificacao_questoes.json` (round-trip exato, preservando formatação e ordenação).
  - Validações: nó inexistente rejeitado, nó aposentado rejeitado, > 2 nós rejeitado, > 1 principal rejeitado, ciclo de fusão resolvido.
  - Candidatos preferenciais: validação contra casos com `cargos_restritos` (ex.: IBAMA) e concurso de cargo único (ex.: TCU).
  - Divisão de lotes: garantia de texto-base indiviso e teto de 10 itens por lote.
  - Teste de integração Postgres: reextração de 1 caderno com deleção de questões recarrega `questao_no` intacto via `aplicar_classificacao`.

#### Critério de Conclusão da Sessão A
- `venv/bin/pytest tests/test_classificacao.py tests/test_candidatos_questao.py` 100% verde.
- `ruff check src/ tests/` sem advertências.
- Execução de carga de teste popula `questao_no` no Postgres local sem erros.

---

### Sessão B — `scripts/classificar_questoes.py` (LLM + Rodada Real)

**Objetivo:** Implementar o pipeline de inferência com chamadas estruturadas ao LLM via OpenRouter, validação estrita pós-resposta, tratamento em 2 passadas (preferencial → reserva), fallback seguro para `sem_no`, e executar a rodada real nos cadernos extraídos.

#### Checklist

- `[x]` **Script `scripts/classificar_questoes.py`:**
  - Reutilização da infraestrutura comprovada na Etapa 5B.2:
    - `src.llm_openrouter.chamar_llm_json` com `REASONING_PADRAO`.
    - Langfuse com trace `nome_trace="classificar_questoes"`.
    - Classe `Contabilidade` rastreando chamadas, tokens de entrada/saída, custo em USD e distribuição de falhas.
    - Laço de 2 tentativas com injeção estruturada do erro no prompt na segunda tentativa.
  - **Formatação de entrada e prompt:**
    - Contexto do caderno: concurso, órgão, cargo(s), nível de escolaridade, tipo de conhecimento.
    - Seção do caderno (ex.: *"Julgue os itens relativos a Atos Administrativos"*).
    - Texto-base compartilhado (se houver; figuras mencionadas apenas pelo marcador `[Figura <arquivo>]`).
    - Enunciado dos itens numerados do lote.
    - Árvore de candidatos formatada com indentação hierárquica e IDs locais curtos (`C1`, `C2`, ..., `Cn`) para contenção de tokens e precisão cirúrgica:
      ```text
      [C1] DIREITO ADMINISTRATIVO (matéria)
        [C2] Atos administrativos (assunto)
          [C3] Conceito e requisitos (subassunto)
          [C4] Anulação e revogação (subassunto)
      ```
    - Critérios formais de confiança no prompt do sistema:
      - `alta`: item aborda diretamente e univocamente o assunto/subassunto indicado.
      - `media`: item aborda conceito abrangente ou fronteiriço, enquadrando-se no assunto mas sem especificidade perfeita.
      - `baixa`: enquadramento duvidoso, periférico ou dependente de interpretação extensiva.
  - **Schema Pydantic de saída:**
    ```python
    class ItemClassificado(BaseModel):
        numero: int
        nos: list[str] = Field(..., max_length=2)  # IDs locais (ex: ["C3"] ou ["C3", "C8"])
        confianca: Literal["alta", "media", "baixa"]
        nenhum_serve: bool = False
        justificativa: str = ""

    class RespostaClassificacaoLote(BaseModel):
        itens: list[ItemClassificado]
    ```
  - **Validação estrita pós-chamada (`pos_validacao`):**
    - ID retornado que não conste na lista do lote → `falha_id_desconhecido`.
    - Divergência entre itens enviados e retornados (número faltando ou sobrando) → `falha_itens_divergentes`.
    - Mais de 2 nós para um item → `falha_validacao_schema`.
    - Caso `nenhum_serve == true`, `nos` deve ser vazio.
  - **Segunda passada para itens sem enquadramento (`nenhum_serve`):**
    - Se o modelo marcar `nenhum_serve = true` na lista preferencial, o item é reempacotado em um novo lote contendo a **subárvore de reserva** (subárvore completa das matérias daquele caderno).
    - Nós atribuídos na segunda passada recebem automaticamente `fora_do_edital = true`.
    - Se mesmo na reserva o modelo retornar `nenhum_serve = true`, o registro é gravado como `sem_no = true`, sem nós associados, permanecendo pendente para intervenção do dono (respeitando rigorosamente o ADR-030 §5: **o agente nunca cria nós**).
  - **Idempotência e performance:**
    - Antes de processar, verifica se a questão já possui registro canônico com o mesmo `hash_enunciado` e apontamento não rejeitado. Em caso afirmativo, pula o processamento.
    - Flags CLI:
      - `--caderno <codigo>`: restringe a execução a um caderno específico.
      - `--dry-run`: renderiza e imprime o prompt e lote no terminal sem efetuar chamadas de API.
      - `--limite <N>`: limita o número de lotes processados para testes controlados.
      - `--reclassificar`: força a reavaliação de questões mesmo que já possuam propostas.
    - **Isolamento de custos:** este script **não** roda automaticamente no pipeline de revisão do scraper (`atualizar_revisao.py`), evitando consumo acidental de créditos da API.
- `[x]` **Testes automatizados com LLM mockado (`tests/test_classificar_questoes.py`):**
  - Classificação bem-sucedida em 1ª tentativa.
  - Recuperação na 2ª tentativa após injeção de ID inválido.
  - Roteamento para lista de reserva quando `nenhum_serve = true`.
  - Gravação de `sem_no` quando ambas as passadas falham.
  - Respeito à flag de idempotência por hash de enunciado.
- `[x]` **Execução da Rodada Real:**
  1. Teste de sanity check com `--dry-run` em 1 lote.
  2. Execução real em 1 caderno piloto (`094_PF_CB1_01`, 50 itens).
  3. Inspeção dos resultados, log de chamadas e conformidade dos IDs.
  4. Execução completa para todos os cadernos extraídos (2.800 itens objetivos e 34 discursivas = 2.834 registros).
  5. Registro detalhado da contabilidade final: 450 chamadas ao LLM (444 lotes OK, 0 falhas finais), custo total $0.1939 USD, 2.412 nós com confiança alta, 613 média, 3 baixa, 1 item sem nó.

#### Critério de Conclusão da Sessão B
- 100% dos itens utilizáveis e discursivas processados e registrados em `canonico/classificacao_questoes.json`.
- Log final de contabilidade gerado e verificado.
- `pytest tests/test_classificar_questoes.py` verde.

---

### Sessão C — Revisão, CLI e Checkpoint do Dono

**Objetivo:** Construir o relatório HTML para auditoria visual humana, desenvolver a CLI de curadoria, submeter os dados à aprovação soberana do dono do projeto e consolidar a documentação no ADR-032 e no repositório.

#### Checklist

- `[x]` **Relatório visual de classificação (`scripts/gerar_relatorio_classificacao.py`):**
  - Gera `revisao_piloto/relatorio/classificacao.html` (com link adicionado no `index.html` da revisão).
  - Organização por caderno, com sumário no topo exibindo indicadores-chave: total de itens, distribuição por confiança (`baixa`, `media`, `alta`), total de itens fora do edital e contagem de itens `sem_no`.
  - Ordenação dos itens dentro de cada caderno por prioridade de atenção humana:
    1. Casos críticos `sem_no` no topo absoluto.
    2. Questões com confiança `baixa`.
    3. Questões com confiança `media`.
    4. Questões com confiança `alta`.
  - Exibição de cada item: enunciado completo, texto-base associado (em componente recolhível `<details>` para economia de espaço), gabarito oficial, árvore de caminho completo do nó mapeado (`Matéria › Assunto › Subassunto`), selo visual em destaque quando `fora_do_edital = true`, e justificativa emitida pelo modelo.
  - Integrado à rotina padrão de `scripts/atualizar_revisao.py`.
- `[x]` **CLI de curadoria humana (`scripts/curar_classificacao.py`):**
  - Comandos para intervenção pontual e em lote:
    - `--mapear CHAVE:NO1[,NO2]`: atribui nós manualmente a uma questão (sai imediatamente com `origem: "humano"`, `status: "aprovado"`).
    - `--aprovar CHAVE:NO`: aprova uma proposta específica de classificação.
    - `--rejeitar CHAVE:NO`: rejeita uma proposta específica.
    - `--aprovar-lote --confianca alta [--caderno X]`: aprova em lote todas as classificações com confiança `alta` (globalmente ou restrito a um caderno).
    - `--pendentes`: lista no terminal o resumo de itens aguardando decisão humana (`sem_no` e confiança `baixa`).
    - `--html`: regenera o relatório `classificacao.html`.
  - **Invariante:** o script valida rigorosamente que toda aprovação execute somente sob comando direto do usuário humano.
- `[x]` **Testes da CLI e Relatório (`tests/test_curar_classificacao.py`):**
  - Validação das flags `--mapear`, `--aprovar`, `--rejeitar`, `--aprovar-lote`.
  - Verificação de renderização do HTML e contagem dos indicadores.
- `[x]` **Checkpoint do Dono:**
  - O dono do projeto inspeciona `classificacao.html` (via interface Datasette/Traefik).
  - Revisão e decisão item a item para as questões `sem_no` e com confiança `baixa`.
  - Decisão sobre os itens com confiança `media`.
  - Execução de aprovação em lote das classificações com confiança `alta`.
  - Carga final do banco de dados: `python -m src.stats_writer`.
- `[x]` **Documentação e Encerramento:**
  - Criação do `docs/adr/ADR-032-classificacao-questoes-arvore.md` documentando o modelo conceitual, os resultados medidos da rodada real, custos, aprendizados e decisões de curadoria.
  - Atualização do `CLAUDE.md` (§3 Arquitetura, §5 Scripts de Revisão e Banco, §6 Comandos Frequentes, §7 Invariantes do Pipeline).
  - Atualização do `task.md` (marcando as tarefas da 5D como concluídas).
  - Registro de armadilhas ou lições em `LESSONS.md` se aplicável.

#### Critério de Conclusão da Sessão C
- Zero pendências em `canonico/classificacao_questoes.json` após a deliberação do dono.
- `vw_questao_no` no PostgreSQL cobre integralmente os itens aprovados utilizáveis e discursivas.
- Relatório `revisao_piloto/relatorio/classificacao.html` publicado e acessível.
- `pytest` total e `ruff` 100% verdes.

---

## 6. Critério de Conclusão Geral da Etapa 5D ("Pronto quando")

1. **Cobertura Canônica Integral:** Toda questão utilizável (2.800 itens) e discursiva (34 cadernos) extraída possui registro em `canonico/classificacao_questoes.json`.
2. **Resolução de Pendências:** Não resta nenhum item com status `proposto` ou `sem_no` não deliberado pelo dono do projeto.
3. **Consistência do Banco de Dados:** A view `vw_questao_no` reflete perfeitamente as questões aprovadas, ligando-as aos nós efetivos ativos da árvore.
4. **Resiliência a Reextrações:** Executar a reextração de um caderno (`python -m scripts.extrair_questoes`) executa o ciclo de `DELETE + INSERT` em `questoes`, e o recarregamento automático restaura integralmente a tabela `questao_no` a partir do canônico sem perda de dados.
5. **Qualidade e Conformidade:** `venv/bin/pytest` com 100% de testes aprovados e `ruff check` limpo em todo o repositório.

---

## 7. Mapeamento de Arquivos

### Arquivos Novos
- `plano-etapa-5d.md` (este documento de planejamento)
- `src/classificacao.py` (modelo de dados canônico, I/O e validações)
- `src/candidatos_questao.py` (geração de candidatos preferenciais/reserva e particionamento de lotes)
- `scripts/classificar_questoes.py` (orquestrador de inferência LLM com OpenRouter e Langfuse)
- `scripts/curar_classificacao.py` (CLI de curadoria e aprovação pelo dono)
- `scripts/gerar_relatorio_classificacao.py` (gerador do relatório HTML de revisão)
- `canonico/classificacao_questoes.json` (base canônica versionada)
- `docs/adr/ADR-032-classificacao-questoes-arvore.md` (registro de decisão arquitetural)
- `tests/test_classificacao.py`
- `tests/test_candidatos_questao.py`
- `tests/test_classificar_questoes.py`
- `tests/test_curar_classificacao.py`

### Arquivos Alterados
- `src/sql/schema_estatisticas.sql` (tabelas `questao_no`, `discursiva_no` e view `vw_questao_no`)
- `src/stats_writer.py` (função `aplicar_classificacao` e integração na carga)
- `scripts/atualizar_revisao.py` (integração do relatório HTML e recarga no pipeline de revisão)
- `scripts/extrair_questoes.py` (chamada a `aplicar_classificacao` após conclusão da fila)
- `task.md` (resumo e links para o plano)
- `CLAUDE.md` (atualização das convenções, comandos e tabelas)

### Componentes Reutilizados
- `src/llm_openrouter.py` (`chamar_llm_json`, `REASONING_PADRAO`, `ResultadoPosValidacao`)
- `src/arvore.py` (`resolver_no`, `materia_do_no`, padrões de serialização e validação)
- `scripts/propor_arvore.py` (padrões de `propor_lote`, classe `Contabilidade`, dicionário de IDs locais)
- Views de banco existentes: `vw_arvore_edital_por_cargo`, `vw_no_caminho`
- Padrão visual de relatórios de revisão: `scripts/gerar_relatorio_arvore.py` e CSS de `revisao_piloto/`

---

## 8. Guia de Verificação

### Verificação Desta Sessão de Planejamento
- [x] `plano-etapa-5d.md` legível e autocontido, sem dependência de reconsulta a outros documentos.
- [x] Seção 5D do `task.md` substituída por resumo objetivo apontando para este plano.
- [x] Título da seção de prioridade em `task.md` (linha 317) devidamente atualizado indicando a Etapa 5D como próxima prioridade.

### Verificação por Sessão de Execução
- **Sessão A:**
  ```bash
  venv/bin/pytest tests/test_classificacao.py tests/test_candidatos_questao.py
  venv/bin/ruff check src/ tests/
  python -c "from src import classificacao, candidatos_questao; print('Imports OK')"
  ```
  *Teste prático de integridade:* Rodar `aplicar_classificacao` com JSON de fixture e comprovar que reextração de um caderno preserva os apontamentos de `questao_no`.
- **Sessão B:**
  ```bash
  venv/bin/pytest tests/test_classificar_questoes.py
  python -m scripts.classificar_questoes --caderno 094_PF_CB1_01 --dry-run
  ```
  *Inspeção manual:* Conferir a classificação do caderno `094_PF_CB1_01` antes de disparar o processamento em lote.
- **Sessão C:**
  ```bash
  venv/bin/pytest tests/test_curar_classificacao.py
  python -m scripts.atualizar_revisao
  ```
  *Validação visual e relacional:*
  - Acessar `https://datasette.projetoathos.com.br/relatorio/classificacao.html`.
  - Executar no banco de estatísticas:
    ```sql
    SELECT count(*), count(DISTINCT questao_id) FROM vw_questao_no;
    SELECT confianca, fora_do_edital, count(*) FROM vw_questao_no GROUP BY 1, 2;
    ```
