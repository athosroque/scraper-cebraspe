# ADR-031: Extração Determinística de Questões, Gabaritos e Discursivas dos Cadernos de Prova

## Status
Aceito (Etapa 5C concluída em 2026-09-25; refinamentos da Etapa 5C.1 consolidados em 2026-09-27)

## Data
2026-09-25 (atualizado em 2026-09-27)

## Contexto

A Etapa 5 entregou o star schema com a taxonomia dos editais (o que o edital prevê). Contudo, o objetivo nuclear do projeto é saber **o que a banca efetivamente cobra nas provas** (estatísticas de incidência por nível escolar, matérias mais recorrentes, temas discursivos e capacidade de geração de simulados fidedignos para refazer provas).

Para viabilizar isso, era necessário consumir a `fila_extracao_questoes` populada na Etapa 5 e processar os PDFs de cadernos de provas e gabaritos definitivos dos 5 concursos de 2025 (`PF_25_ADM`, `TCU_25_TEFC`, `IBAMA_25`, `STM_25` e `CD_25_NS`).

Os desafios técnicos medidos nos dados reais envolveram:
1. **Gabaritos com nome em hash:** No TCU e na Câmara dos Deputados, o crawler baixou arquivos como `hash.pdf` sem o código do caderno na URL, deixando 11 gabaritos sem prova associada.
2. **Ordem de fluxo do PDF vs. Ordem visual:** O fluxo interno de blocos retornado pelo PyMuPDF não segue a ordem de leitura em cadernos diagramados em duas colunas.
3. **Identificação de itens e textos-base:** Os cadernos Certo/Errado trazem blocos de itens (`Julgue os itens a seguir...`) antecedidos por textos-base compartilhados, fórmulas matemáticas e imagens (ex.: eletrocardiogramas na PF).
4. **Discursivas:** Cadernos com múltiplos temas ou peças técnicas, com quesitos pontuados explicitamente (`[valor: X pontos]`) cuja soma deve bater rigorosamente com a capa da prova.
5. **Bug de recuo de linha única:** Em itens de apenas 1 linha física seguidos por texto-base (caso de páginas em coluna única na PF), a medição permissiva de recuo de continuação do item engolia a primeira linha do parágrafo do texto-base seguinte.
6. **Volumetria dos artefatos:** Os 140 arquivos JSON gerados ocupam ~3,4 MB e possuem centenas de milhares de linhas, sendo desnecessário sobrecarregar o histórico git com dados brutos geráveis sob demanda.

## Decisão

1. **Extração 100% determinística (sem LLM):**
   - [`src/gabarito_parser.py`](file:///home/athos/homelab/scraper_cebraspe/src/gabarito_parser.py):
     - Lê as grades de gabarito definitivas (posições 1 a 120, descartando preenchimento `0`), mapeando `C`, `E` e `X` (anuladas). Extrai o código do caderno diretamente do **conteúdo impresso do PDF** (ex.: `108_TCUTEFC_001_01`, `167_CDNS_002_01`), resolvendo os gabaritos em hash e zerando os gabaritos órfãos reais (restando apenas 5 justificativas de alteração, catalogadas com `tipo_documento='justificativa'`).
     - Classificação de versão do gabarito (`definitivo` × `preliminar`) estritamente pelo cabeçalho (com fallback por prefixo de nome de arquivo), desempate determinístico e alertas informativos (`mais_de_um_gabarito` / `gabarito_preliminar`). Justificativa de alteração (documento do concurso sem caderno) fica com status `concluido` (`tipo_documento = 'justificativa'`).
     - Extrai também o texto oficial dos padrões de resposta discursivos, dividido em seções por questão, removendo o rodapé repetido em todas as páginas e o cabeçalho institucional em caixa alta no fim da seção (só quando as linhas finais são todas de cabeçalho; nunca corta texto do corpo).
   - [`src/prova_parser.py`](file:///home/athos/homelab/scraper_cebraspe/src/prova_parser.py):
     - Segmenta visualmente por colunas com tolerância geométrica, ordenando os blocos por `(coluna, y0, x0)`.
     - Identifica números de itens a partir de x0 na margem da coluna (cluster/moda) e spans próprios tipográficos (evitando falsos positivos com números no meio de frases). Itens duplicados ou fora de ordem são bloqueantes.
     - Trecho sem recuo de margem é anexado ao item com alerta informativo (`trecho_sem_recuo_anexado_ao_item`).
     - Delimita comandos (`secao`) e textos-base compartilhados vinculados aos itens.
     - Apenas figuras raster são extraídas (`get_pixmap`), vetoriais decorativas são ignoradas. Salvas em `data/<ano>/CEBRASPE/<orgao>/Provas/figuras/<caderno>_<pag>_<n>.png`, cada figura ligada à linha logo acima na mesma coluna com sobreposição horizontal; exceção item → preâmbulo.
     - Calibra a função `_recuo_item` na faixa estrita de **12 a 24 pt** (~18 pt real), isolando categoricamente o recuo de parágrafo de textos-base subsequentes (~28 a 29 pt).
   - Provas discursivas:
     - Convenção dos 3 formatos de nome de caderno discursivo originados do CEBRASPE documentada (`094_PF_014_DISC`, `094_PF_DISC_015`, `PF_25_ADM_DISC_001`).
     - Quesitos discursivos extraídos estritamente a partir do comando (`redija`, `elabore`, `aborde`, `discorra`), evitando falso positivo de datas numéricas antes do comando.
     - Tema anafórico ("dessa", "desse", "referido", etc.) rejeitado para `None` com alerta informativo `tema_anaforico`.
     - Número da questão tirado do título (`Questão N`); repetição ou buraco geram o alerta informativo `numeracao_discursiva`. Alertas `sem_quesitos` / `quesito_sem_valor` quando a questão fica sem quesitos extraídos ou algum quesito não tem `[valor: ...]`.
     - Padrão de resposta ligado preferencialmente por chave de título (`_chave_titulo`, em `ligar_padrao_resposta`), o que acerta a ordem mesmo com seções fora de ordem no PDF; se alguma chave faltar ou se repetir (entre as seções ou entre as questões), cai na ligação por ordem (com alerta `padrao_ligado_por_ordem`) ou no texto inteiro para todas as questões (`padrao_resposta_nao_dividido`).
     - Valores parciais de pontuação capturados via regex `\[valor:\s*([\d,\.]+)\s*pontos?\]`, conferindo a soma contra a pontuação da prova.
   - Idempotência e validação:
     - Falha ou divergência de itens vs gabarito não grava parcial no banco (transação atômica que limpa o caderno). A validação exige `itens_extraidos == itens_gabarito`.

2. **Persistência em star-schema no PostgreSQL próprio:**
   - DDL em `src/sql/schema_estatisticas.sql`: tabelas `textos_base`, `questoes` (`prova_id`, `numero`, `enunciado`, `gabarito`, `anulada`, `figuras`, `secao`, `alertas`, `utilizavel`) e `discursivas` (`prova_id`, `numero`, `titulo`, `tema`, `enunciado`, `quesitos`, `padrao_resposta`).
   - Alertas no item persistidos no Postgres (`alertas text[]`, `utilizavel boolean`) e view `vw_questoes_utilizaveis` para consumo limpo.
   - Adicionada coluna `provas.codigo_caderno` e `concursos.banca = 'CEBRASPE'`.
   - `src/questoes_writer.py`: Substitui integralmente o caderno em transação atômica.
   - `scripts/extrair_questoes.py`: consumidor de execução única (advisory lock de sessão `pg_try_advisory_lock(5_031_001)`) com transições seguras de status (`processando` → `concluido` | `erro`).
   - Assinatura do grupo por sha256 na fila (`fila_extracao_questoes.assinatura_grupo`) garante reprocessamento em qualquer status quando os gabaritos mudam; flag `--reprocessar-erros` cobre órfãos e falhas.

3. **Armazenamento local dos JSONs de questões:**
   - O diretório `questoes/` contendo os 140 arquivos JSON (`<caderno>.json` e `<caderno>.auditoria.json`) fica mantido localmente e adicionado ao `.gitignore`. O dataset é 100% reproduzível a qualquer momento via `python -m scripts.extrair_questoes --reprocessar`.

## Consequências e Resultados

- **70 cadernos processados** com 100% de sucesso (0 cadernos com erro).
- **2.800 itens objetivos** extraídos e pareados com o gabarito oficial (129 itens anulados catalogados).
- **34 discursivas** / **107 quesitos** extraídos com pontuação conferida.
- **123 textos-base** e **10 figuras raster** vinculadas com precisão.
- **145 itens da fila** concluídos no banco.
- **435 testes aprovados (+1 xfail)** no `pytest` e conformidade absoluta com `ruff`.
- Base de dados de provas e questões pronta para a Etapa 5D (classificação dos itens por assunto canônico via LLM).
