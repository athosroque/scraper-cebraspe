# ADR-032: Classificação das Questões na Árvore Mestre

## Status
Aceito (Etapa 5D concluída em 2026-09-29)

## Data
2026-09-29

## Contexto

A Etapa 5B.2 concluiu com sucesso a curadoria da árvore mestre (`canonico/arvore.json`, com 3.577 nós ativos distribuídos entre matérias, assuntos e subassuntos). Em paralelo, a Etapa 5C/5C.1 extraiu de forma determinística 2.800 itens objetivos (42 cadernos) e 34 discursivas (28 cadernos).

O objetivo da **Etapa 5D** foi estabelecer a ponte semântica entre cada questão extraída e os nós da árvore mestre, respeitando a regra de especificidade máxima (ADR-030 §6: nó mais específico possível, preferencialmente subassunto). Esta classificação é a fundação para:
1. As estatísticas oficiais de *"o que mais cai"* e *"edital × prova"* (**Etapa 5E**);
2. Os filtros de navegação hierárquica e motor de simulados do site público de questões (**Etapa 5F**).

Os desafios técnicos resolvidos envolveram:
1. **Contenção de tokens e precisão do LLM:** Passar a árvore inteira de 3.577 nós em cada chamada estouraria o contexto e causaria alucinações.
2. **Instabilidade de chaves seriais:** A reextração de cadernos executa `DELETE + INSERT` em `questoes`, tornando IDs seriais inválidos como chave canônica.
3. **Imunidade a alucinações de nós:** O modelo não pode inventar disciplinas ou tópicos inexistentes.
4. **Governança estrita:** O agente/modelo nunca aprova em nome do dono; o banco é derivado do arquivo canônico versionado no repositório.

## Decisão

1. **Confiança Categórica e Papéis Fechados:**
   - Valores restritos de confiança: `alta` | `media` | `baixa`, com critérios formais injetados no prompt do modelo.
   - No máximo 2 nós por questão: exatamente 1 nó `principal` obrigatório e, apenas em casos de interdisciplinaridade genuína, 1 nó `secundario` opcional.

2. **Candidatos em Duas Camadas e Cálculo Local de `fora_do_edital`:**
   - O LLM nunca decide a flag `fora_do_edital`. O cálculo é feito localmente pelo script:
     - **Passada preferencial:** O script filtra os nós do cargo (`vw_arvore_edital_por_cargo` × `provas_cargos`), incluindo ancestrais, com IDs locais curtos (`C1`, `C2`, ..., `Cn`). Questões classificadas aqui recebem `fora_do_edital = false`.
     - **Passada de reserva:** Itens marcados com `nenhum_serve = true` na preferencial são reempacotados com a subárvore completa das matérias daquele caderno (`candidatos_reserva`). Nós atribuídos aqui recebem automaticamente `fora_do_edital = true`.
     - **Item sem nó:** Se mesmo na reserva o item não se enquadrar, é registrado como `sem_no = true`, sem nós associados (ADR-030 §5: **o pipeline nunca cria nós automaticamente**).

3. **Chave Natural Canônica Estável e Hash de Enunciado:**
   - Fonte da verdade: `canonico/classificacao_questoes.json`, ordenado por chave, com um registro por linha.
   - Chave natural estável: `<slug_concurso>|<codigo_caderno>|<numero>` para objetivas e `<slug_concurso>|<codigo_caderno>|D<numero>` para discursivas.
   - Cada registro armazena o SHA-1 do enunciado limpo (`hash_enunciado`). Se uma reextração alterar o texto, a carga detecta a divergência e marca o item para reavaliação.

4. **Banco Derivado Idempotente (`src/sql/schema_estatisticas.sql` e `src/stats_writer.py`):**
   - Tabelas ponte N:N `questao_no` e `discursiva_no` com constraints de domínio e chaves estrangeiras com `ON DELETE CASCADE`.
   - View oficial `vw_questao_no` filtrando exclusivamente `status = 'aprovado'` e integrando com `vw_no_caminho` (resolvendo fusões de nós transparentemente).
   - Função idempotente `stats_writer.aplicar_classificacao(conn, classificacao_path)` chamada automaticamente no final de `atualizar_revisao` e `scripts/extrair_questoes.py`. Uma reextração que apaga e reinsere `questoes` restaura instantaneamente os apontamentos sem intervenção manual.

5. **Interface de Auditoria e Curadoria Soberana:**
   - `scripts/gerar_relatorio_classificacao.py`: Relatório HTML navegável (`revisao_piloto/relatorio/classificacao.html`) linkado no índice de revisão, priorizando visualmente itens `sem_no`, seguidos de confiança `baixa`, `media` e `alta`. Traz textos-base em componentes expansíveis `<details>`, gabaritos, seções de prova e atalhos CLI copiáveis.
   - `scripts/curar_classificacao.py`: CLI de curadoria humana com comandos `--mapear`, `--aprovar`, `--rejeitar`, `--aprovar-lote` e `--pendentes`. Garante a soberania do dono sobre toda e qualquer decisão.

## Consequências e Resultados Medidos

- **Inferência Real Concluída:**
  - 450 chamadas estruturadas ao modelo `z-ai/glm-5.3-flash` via OpenRouter com telemetria no Langfuse (444 lotes concluídos com sucesso, 0 falhas finais).
  - Custo financeiro total da inferência: **$0.1939 USD** (~R$ 1,07).
- **Cobertura Canônica Integral (2.834 questões):**
  - **2.800 questões objetivas** e **34 questões discursivas** classificadas.
  - Distribuição de apontamentos: **2.412 nós com confiança alta**, **613 com confiança média**, **3 com confiança baixa** e apenas **1 item sem nó**.
- **Qualidade e Resiliência:**
  - 100% dos nós mapeados validados contra a árvore mestre ativa.
  - Testes automatizados cobrindo I/O canônico, geração de candidatos, particionamento de lotes, CLI de curadoria e persistência idempotente no PostgreSQL.
  - Base de dados totalmente preparada para o cálculo das estatísticas de incidência da Etapa 5E.
