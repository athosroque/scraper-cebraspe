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

## Estatísticas e Views de Incidência (Etapa 5E — Concluída em 2026-09-29)

Na Etapa 5E, o modelo dimensional e as views analíticas foram desenvolvidos para responder às consultas centrais de produto do site de questões (*"o que mais cai"*, busca de questões, proporção Certo/Errado, comparativo de níveis, edital × prova, peso por matéria e discursivas analíticas), sem nenhuma dependência de LLM (custo financeiro $0).

### 1. Decisões de Modelagem e Agregação

1. **Grão Base e Expansão por Cargo (`vw_questoes_contexto`):**
   - Grão: 1 linha por (questão × cargo). Cadernos de conhecimentos básicos cobrem múltiplos cargos (ex.: `CB1` atende 14 cargos na PF). A ponte `provas_cargos` expande as linhas para viabilizar filtros precisos por cargo e nível.
2. **Subida na Árvore (`vw_prova_cobra_base`):**
   - Analogamente à `vw_edital_cobra_base` (ADR-030), uma questão classificada em subassunto sobe na árvore e soma no subassunto, no assunto e na matéria. Questões classificadas diretamente em assunto somam no assunto e na matéria, **nunca descendo para subassuntos**.
3. **Desduplicação Canônica Inter-Cadernos (`questao_canonica_id`):**
   - Foram detectados **99 grupos de enunciados idênticos** repetidos entre cadernos específicos diferentes do mesmo concurso (81 no `STM_25`, 18 no `PF_25_ADM`; 0 nos demais concursos).
   - Validação da chave completa `(concurso, hash_enunciado, texto_base, gabarito)`: **99 de 99 confirmados com 0 divergências**.
   - Solução: criada a coluna derivadora `questao_canonica_id` via window function particionada por `(concurso_id, md5(enunciado), md5(texto_base), gabarito)`. As views agregadas `vw_prova_cobra_*` utilizam `count(DISTINCT questao_canonica_id)`, eliminando distorções estatísticas no consolidado sem prejudicar buscas locais por caderno/cargo (`vw_questoes`).
4. **Reconciliação Estrita do Universo de Questões:**
   - **2.800 questões físicas** extraídas no banco de dados.
   - **2.781 questões utilizáveis oficiais** = 2.652 válidas + 129 anuladas.
   - **19 questões não utilizáveis** (`simbolo_ilegivel`) descartadas de todas as agregações.
   - **129 questões anuladas:** rigorosamente excluídas do total de `questoes` e do denominador de todos os percentuais, sendo computadas em coluna dedicada `anuladas`.
   - **2.657 questões canônicas utilizáveis com nó:** consolidadas na `vw_prova_cobra_base` (2.532 válidas + 125 anuladas), absorvendo as 124 aplicações repetidas entre cadernos do mesmo concurso.
5. **Média Ponderada por Concurso (`pct_medio_por_concurso`):**
   - Evita distorções de concursos com cadernos básicos gigantescos (ex.: Câmara com 90 questões).
   - Cada concurso possui peso idêntico. Concursos sem questões na matéria ficam fora da média; concursos com a matéria presente mas 0 questões no nó entram na média com 0.00%.
6. **Interdisciplinaridade:**
   - Todas as classificações aprovadas somam nas contagens gerais (questão multidisciplinar cobra ambos os tópicos); a coluna `so_principal` é exposta para alternância no frontend.
7. **Matéria-Cargo (`nome_de_cargo`):**
   - Identificada deterministicamente na Sessão A (`taxonomia_itens.materia_origem` = `cargo` e `dim_materia.nome_de_cargo = true`).
   - Apresentada na `vw_questoes` e `vw_peso_materia_cargo` com o rótulo formatado `"Conhecimentos específicos — <cargo>"`.
8. **Cobertura Descendente Edital × Prova (Decisão 5):**
   - Um item previsto no edital em nó X cobre X e todos os descendentes de X.
   - `situacao`:
     - `'cobrado_no_edital'`: previsto no edital (direto ou via ancestral) e cobrado na prova;
     - `'no_edital_nunca_cobrado'`: previsto no edital, mas com zero questões cobradas nele ou em seus descendentes;
     - `'cobrado_fora_do_edital'`: cobrado na prova, porém sem ancestral-ou-igual previsto no edital daquele cargo.
   - Subida hierárquica na prova garante que questões em subassuntos contam no assunto do edital, eliminando falsos "nunca cobrado".

### 2. Views Implementadas (`src/sql/schema_estatisticas.sql`)

- `vw_questoes_contexto`: Grão (questão × cargo), expondo metadados de aplicação, concurso, nível e chave canônica.
- `vw_questoes`: Base para a busca do site (5F.1), ligando o enunciado e textos-base à árvore e dimensões de filtro.
- `vw_prova_cobra_base`: Base normalizada da subida hierárquica, filtrando concursos aprovados e questões utilizáveis.
- `fn_prova_cobra(p_nivel_alvo, p_banca, p_orgao, p_ano, p_concurso, p_cargo_numero, p_nivel, p_tipo_conhecimento)`: **interface de leitura do site** para "o que mais cai". Filtra a base primeiro e conta depois, então a questão básica aplicada em N cargos conta 1× em qualquer combinação de filtros. Devolve `total_universo` (denominador do `pct_do_universo`) e o `pct_medio_por_concurso` calculado **sob os filtros**.
- `vw_prova_cobra_no` (+ atalhos `vw_prova_cobra_{subassunto,assunto,materia}`): grão máximo (concurso × cargo × tipo × nó), para inspeção e consulta de um cargo só.
- `vw_certo_errado_por_no`: Taxa de itens certos, errados e anulados por nó hierárquico.
- `vw_comparativo_nivel`: Comparativo lado a lado de incidência Médio × Superior com diferença percentual.
- `vw_edital_vs_prova`: Cruzamento (concurso × cargo × nó) com previsão do edital, questões da prova, razão e situação (`cobrado_no_edital`, `no_edital_nunca_cobrado`, `cobrado_fora_do_edital`). 7.051 linhas geradas em ~0,38s.
- `vw_peso_materia_cargo`: Peso percentual de cada matéria dentro da prova de cada cargo (básico + específico), com formatação de `nome_de_cargo = true` como `"Conhecimentos específicos — <cargo>"`. 274 linhas em ~0,23s.
- `vw_discursivas`: 64 linhas analíticas com tema, título, quesitos, gabarito e nós associados. Discursivas rigorosamente isoladas das contagens objetivas.

### 3. Reconciliação e Aceite Final (Consultas do "Pronto Quando")

1. **Top 10 Subassuntos de Língua Portuguesa Superior × Médio (`vw_comparativo_nivel`):**
   - Superior liderado por: *Substituição de palavras ou de trechos de texto* (11 questões sup vs 3 médio), *Concordância verbal e nominal* (7 sup vs 3 médio), *Relações de subordinação* (7 sup vs 3 médio), *Emprego de elementos de referenciação e conectores* (7 sup vs 3 médio).
2. **Questões Filtradas por Cargo e Nível (`vw_questoes`):**
   - Busca em `PF_25_ADM`, cargo 1 (`ADMINISTRADOR`, nível superior) em *Concordância verbal e nominal*: recupera questões 13 (C) e 14 (E) instantaneamente com caminho e metadados.
3. **"No edital, nunca cobrado" do PF_25_ADM Cargo 1 (`vw_edital_vs_prova`):**
   - Retorna 27 assuntos e 96 subassuntos previstos no edital que não tiveram nenhuma questão cobrada na prova (ex.: *Características das organizações formais modernas*, *Excelência nos serviços públicos*, *Ato administrativo*, *Responsabilidade civil do Estado*).
4. **Consistência Canônica 5D × 5E:**
   - 4.055 pares expandidos: **0 divergências**, mas a checagem não discrimina nada no piloto: os 3.029 apontamentos do `classificacao_questoes.json` têm `fora_do_edital = false`. Só 1 questão foi para a passada de reserva (`STM_25|072_STM_008_01|64`), saiu `sem_no` e foi mapeada pelo dono via `curar_classificacao.py --mapear`, que grava sempre `fora_do_edital = false` (`scripts/curar_classificacao.py:213`). Recalculado pela regra correta (nó ou ancestral apontado **diretamente** pelo edital do cargo), as 2.781 questões continuam cobertas.
   - **Correção pós-revisão da `vw_edital_vs_prova`:** a primeira versão procurava o ancestral em `edital_nos`, que já inclui a subida do edital; um subassunto irmão nunca previsto parecia coberto e `cobrado_fora_do_edital` praticamente não ocorria. Agora a busca é em `edital_direto` (o que `vw_arvore_edital_por_cargo` aponta). Como o item de edital também aponta o nó da matéria (`materia_no`), na prática "fora do edital" = matéria ausente do edital do cargo ou item sem matéria mapeada. O teste de consistência passou a usar fixture com um caso `true` (irmão fora) em vez do banco real.
   - **Decisão do dono (2026-09-29):** manter a regra como está. O nó da matéria apontado pelo item de edital conta na cobertura, então a questão de um assunto não citado dentro de uma matéria prevista conta como "no edital". Usar só o nó mais específico de cada item fica descartado por ora.
   - **Pendência para a curadoria:** `--mapear` deveria herdar ou calcular o `fora_do_edital`, não fixar `false`. Enquanto isso, a fonte de "fora do edital" para o site é a `vw_edital_vs_prova`.
5. **Custo Financeiro e Qualidade:**
   - Custo: **$0.00 USD** (100% determinístico).
   - Suíte de testes: 609 passed, 1 xfailed (18 testes dedicados de views em `tests/test_estatisticas_views.py`), `ruff check .` 100% verde.
