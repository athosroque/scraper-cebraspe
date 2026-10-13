<!-- Gerado por scripts/gerar_docs.py a partir de src/registro/. Não editar à mão: rode `make docs-gerar`. -->

# Comandos

Todos os scripts do projeto, por categoria, cada um com o resumo e os argumentos. Use para achar o comando de uma tarefa e conferir as opções sem abrir o código.

Cada script é um ponto de entrada `python -m <módulo>`. Os argumentos são lidos do código-fonte; os ocultos (`argparse.SUPPRESS`) ficam de fora.

## Pipeline

### `python -m scripts.classificar_questoes`

Classifica as questões na árvore mestre pelo LLM, em duas passadas.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--caderno` | Restringe a execução a um caderno específico (ex: 094_PF_CB1_01) | — |
| `--dry-run` | Exibe prompts e candidatos sem efetuar chamadas ao LLM nem gravar | — |
| `--limite` | Limita a quantidade de lotes a processar | — |
| `--reclassificar` | Força reavaliação de questões já classificadas com mesmo hash | — |
| `--arvore` | Caminho do arquivo arvore.json | `ARVORE_PATH_PADRAO` |
| `--classificacao` | Caminho do arquivo classificacao_questoes.json | `CLASSIFICACAO_PATH_PADRAO` |

### `python -m scripts.detectar_dispersao_arvore`

Detecta conceitos espalhados em pais diferentes da árvore mestre, por regra.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--dry-run` (grupo exclusivo) | só relatório (padrão) | — |
| `--propor` (grupo exclusivo) | grava as propostas | — |
| `--relatorio` | — | `RELATORIO_PADRAO` |
| `--arvore` | — | `arvore.ARVORE_PADRAO` |
| `--sem-banco` | não consulta questao_no (só itens de edital desempatam) | — |

### `python -m scripts.extrair_questoes`

Consumidor da fila de extração: extrai questões, gabaritos e discursivas, sem LLM.

**ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--reprocessar` | refaz também o que já está concluído | — |
| `--reprocessar-erros` | refaz cadernos e órfãos com status 'erro' | — |

### `python -m scripts.inventariar_concursos`

Inventário de concursos e cadernos do CEBRASPE (2020 até hoje).

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--listagens` | Mapeia as 4 listagens do CEBRASPE e gera inventario/anos.json agrupado por ano. | — |
| `--mapear` | Varre as páginas individuais de concursos de 2020+ e grava inventario/concursos.jsonl. | — |
| `--reclassificar` | Reaplica o classificador fino aos textos de link já gravados em concursos.jsonl (sem rede). | — |
| `--amostra-formato` | Amostra cadernos objetivos para detectar formato de prova (CE vs ME) e grava em concursos.jsonl. | — |
| `--gravar-banco` | Carrega inventario/concursos.jsonl e persiste no Postgres via stats_writer.gravar_inventario. | — |
| `--relatorio` | Gera relatório analítico consolidado em inventario/RELATORIO.md. | — |
| `--tudo` | Executa o pipeline completo: --listagens -> --mapear -> --amostra-formato -> --gravar-banco -> --relatorio. | — |
| `subcomando` | Subcomando alternativo (ex: python scripts/inventariar_concursos.py mapear) | — |
| `--ano` | Filtra por ano para --mapear (ex: --ano 2025). Padrão: todos >= 2020. | `None` |
| `--situacao` | Filtra por situação para --mapear (ex: --situacao encerrado ou encerrado,em_andamento). | `None` |
| `--refazer` | Força reprocessamento de concursos já mapeados em inventario/concursos.jsonl. | — |
| `--limite` | Limite máximo de concursos a mapear (útil para testes e lotes pequenos). | `None` |
| `--headless` | Executar navegador em modo headless (padrão: True). Use --no-headless para ver interface. | `True` |
| `--headed` | Executar navegador com interface gráfica visível (equivalente a --no-headless). | — |
| `--anos-json` | Caminho do arquivo anos.json. | `INVENTARIO_ANOS_PATH` |
| `--concursos-jsonl` | Caminho do arquivo concursos.jsonl. | `INVENTARIO_CONCURSOS_PATH` |
| `--relatorio-md` | Caminho do arquivo RELATORIO.md. | `INVENTARIO_RELATORIO_PATH` |
| `--amostra-dir` | Diretório de PDFs de amostra. | `AMOSTRA_DIR` |

### `python -m scripts.revisar_taxonomia_piloto`

Checkpoint de revisão humana: roda o pipeline do edital e salva o JSON para revisão.

**ADRs:** [ADR-019](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md), [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md)

```bash
python -m scripts.revisar_taxonomia_piloto <edital.pdf> [saida.json]
```

### `python -m scripts.validar_taxonomia`

Valida se a taxonomia extraída capturou todos os tópicos do edital.

**ADRs:** [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md), [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)

```bash
python -m scripts.validar_taxonomia [diretorio_revisao]
```

### `python -m src.spider`

Crawler de concursos do CEBRASPE, com download dos PDFs.

**ADRs:** [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--slug` | Slug específico de concurso a processar (ex: TCU_25_TEFC) | `None` |

### `python -m src.stats_writer`

Grava o star schema de estatísticas no Postgres próprio.

**ADRs:** [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-026](../adr/ADR-026-banco-postgres-proprio.md), [ADR-027](../adr/ADR-027-star-schema-estatisticas.md), [ADR-028](../adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md), [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md), [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md), [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```bash
python -m src.stats_writer [revisao_piloto_dir] [data_dir]
```

## Curadoria

### `python -m scripts.aprovar_sinonimos`

Aplica as decisões humanas sobre os sinônimos canônicos.

**ADRs:** [ADR-019](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md), [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--aprovar` | IDs de grupo, separados por vírgula | — |
| `--rejeitar` | IDs de grupo, separados por vírgula | — |
| `--mover` | ENTRADA:GRUPO (ou ENTRADA:NOVO) | `[]` |
| `--renomear` | GRUPO=Nome canônico | `[]` |
| `--revisao-dir` | — | `REVISAO_DIR_PADRAO` |
| `--sem-banco` | não grava o Postgres ao final | — |

### `python -m scripts.curar_arvore`

CLI de curadoria da árvore mestre: toda decisão do dono passa por aqui.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--mapear` | ITEM:NO1,NO2 — aponta o item para os nós (aprovado); avisa se o nó é uma norma que já existe em outro lugar (aviso, não bloqueia) | — |
| `--desmapear` | ITEM:NO — remove o apontamento | — |
| `--aprovar` | ITEM:NO — aprova um apontamento proposto | — |
| `--rejeitar` | ITEM:NO — rejeita um apontamento proposto | — |
| `--fundir` | ORIGEM:DESTINO — funde nós (nível diferente só se a origem não tem filhos ativos) | — |
| `--mover` | NO:PAI — troca o pai (nível de cima) | — |
| `--criar` | NIVEL:PAI=Nome — cria nó (matéria: 'materia:=Nome'); recusa norma que já existe em outro nó ([NORMA_JA_EXISTE]) | — |
| `--permitir-norma-repetida` | com --criar: desliga a trava de norma repetida (outro conceito de mesmo nome) | — |
| `--renomear` | NO=Nome — renomeia o nó | — |
| `--aprovar-proposta` | P1,P2... — aprova propostas em lote (tudo ou nada) | — |
| `--rejeitar-proposta` | P1,P2... — rejeita propostas | — |
| `--propostas` | Lista propostas pendentes no terminal (opcional: [M-..]) | — |
| `--html` | Regenera o arvore.html | — |

### `python -m scripts.curar_classificacao`

CLI de curadoria e deliberação humana da classificação das questões.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--classificacao` | Caminho para canonico/classificacao_questoes.json | `classif_mod.CLASSIFICACAO_PADRAO` |
| `--arvore` | Caminho para canonico/arvore.json | `arv_mod.ARVORE_PADRAO` |
| `--revisao-dir` | Diretório de revisão piloto para relatórios | `REVISAO_DIR_PADRAO` |
| `--mapear` | Mapeia manualmente uma questão a 1 ou 2 nós (sai aprovado) | `[]` |
| `--aprovar` | Aprova uma proposta específica de classificação | `[]` |
| `--rejeitar` | Rejeita uma proposta específica de classificação | `[]` |
| `--aprovar-lote` | Aprova em lote propostas com a confiança indicada | — |
| `--confianca` | Nível de confiança para aprovação em lote (padrão: alta) | `'alta'` |
| `--caderno` | Restringe a aprovação em lote a um caderno específico | `None` |
| `--pendentes` | Lista no terminal o resumo de itens aguardando decisão humana | — |
| `--html` | Regenera o relatório visual classificacao.html | — |
| `--aplicar-banco` | Aplica as classificações do arquivo canônico no PostgreSQL | — |

### `python -m scripts.propor_arvore`

Propõe operações na árvore mestre pelo LLM, por matéria, sobre lista fechada.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `revisao_dir` | — | `REVISAO_DIR_PADRAO` |
| `--arvore` | Caminho alternativo para arvore.json | `None` |
| `--materias` | IDs de matérias separados por vírgula (ex: M-5edb4898a0,M-841dde7520) | `''` |
| `--so-regras` | Executa apenas a detecção determinística de compostos, sem chamar LLM | — |
| `--dry-run` | Monta e loga os prompts sem chamar o OpenRouter nem gravar propostas | — |
| `--reavaliar` | Reavalia matérias mesmo se o hash da subárvore não tiver mudado | — |

### `python -m scripts.propor_sinonimos`

Propõe sinônimos pelo LLM, sobre lista fechada de IDs. Custa tokens.

**ADRs:** [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md), [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `revisao_dir` | — | `REVISAO_DIR_PADRAO` |
| `--niveis` | — | `','.join(canonico.NIVEIS)` |
| `--limite-itens` | — | `LIMITE_ITENS_LOTE` |
| `--reavaliar` | manda de novo ao LLM blocos já avaliados (padrão: só blocos com item novo) | — |
| `--dry-run` | só monta e loga os prompts, sem chamar o LLM | — |

## Relatórios

### `python -m scripts.atualizar_revisao`

Atualiza em sequência os artefatos derivados da revisão humana e reinicia o Datasette.

**ADRs:** [ADR-015](../adr/ADR-015-revisao-datasette-traefik.md), [ADR-027](../adr/ADR-027-star-schema-estatisticas.md), [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md), [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```bash
python -m scripts.atualizar_revisao [diretorio_revisao]
```

### `python -m scripts.exportar_pdf_executivo`

Exporta a visão executiva do site de documentação para PDF, para quem está fora do Cloudflare Access.

**ADRs:** [ADR-040](../adr/ADR-040-site-documentacao-mkdocs.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--site` | diretório de um build do MkDocs (padrão: build/docs) | `SITE_PADRAO` |
| `--saida` | — | `None` |
| `--url-base` | endereço público que substitui o servidor local nos links do PDF | `URL_BASE_PADRAO` |

### `python -m scripts.gerar_db_datasette`

Constrói o banco SQLite servido via Datasette para revisão humana.

**ADRs:** [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-026](../adr/ADR-026-banco-postgres-proprio.md)

```bash
python -m scripts.gerar_db_datasette [diretorio_revisao]
```

### `python -m scripts.gerar_docs`

Gera as páginas de docs/tecnico/ a partir do registro (Etapa 9/D2).

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--sem-banco` | não gera banco.md e não abre conexão com o banco | — |
| `--verificar` | não grava; compara com o disco e sai com 1 se algum arquivo difere | — |

### `python -m scripts.gerar_numeros`

Gera a página de números da visão executiva a partir do banco e do custo de LLM no OpenRouter.

**ADRs:** [ADR-040](../adr/ADR-040-site-documentacao-mkdocs.md), [ADR-041](../adr/ADR-041-registro-e-paginas-geradas.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `--sem-custo` | não consulta o OpenRouter; a seção de custo diz que não foi consultada | — |
| `--saida` | arquivo Markdown a gravar (padrão: docs/executivo/numeros.md) | `DESTINO` |

### `python -m scripts.gerar_relatorio_arvore`

Gera o relatório HTML da árvore mestre para revisão do dono.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```bash
python -m scripts.gerar_relatorio_arvore [diretorio_revisao]
```

### `python -m scripts.gerar_relatorio_classificacao`

Gera o relatório visual da classificação das questões na árvore mestre.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```bash
python -m scripts.gerar_relatorio_classificacao [diretorio_revisao]
```

### `python -m scripts.gerar_relatorio_revisao`

Gera o relatório HTML por edital para o checkpoint de revisão humana.

**ADRs:** [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md)

```bash
python -m scripts.gerar_relatorio_revisao [diretorio_revisao]
```

## Manutenção

### `python -m scripts.backfill_classificacao_chunks`

Completa concurso, nível e tipo de conhecimento em extrações já feitas, sem LLM.

**ADRs:** [ADR-020](../adr/ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md), [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md), [ADR-028](../adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md)

```bash
python -m scripts.backfill_classificacao_chunks [edital.pdf [saida.json]]
```

### `python -m scripts.reconciliar_taxonomia`

Aplica o reparo local de item ausente a extrações já salvas, sem LLM.

**ADRs:** [ADR-019](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md), [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)

```bash
python -m scripts.reconciliar_taxonomia [--sem-atualizar] [<edital>.json ...]
```

### `python -m scripts.reprocessar_falhas_piloto`

Reprocessa chunks com falha e consolida o edital piloto.

**ADRs:** [ADR-019](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md), [ADR-021](../adr/ADR-021-reparo-local-nome-topico-numerico.md)

| Argumento | Ajuda | Padrão |
|---|---|---|
| `json_path` | Caminho do <edital>.json | `JSON_PADRAO` |
| `--chunks` | chunk_index separados por vírgula a forçar mesmo com status=sucesso (ex.: --chunks 17,21) | `None` |

### `python -m scripts.semear_arvore`

Semeia canonico/arvore.json com os grupos aprovados da camada de sinônimos.

**ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```bash
python -m scripts.semear_arvore [--forcar]
```

### `python -m src.telegram_bot`

Bot do Telegram de suporte técnico ao projeto, com contexto fixo.

**ADRs:** [ADR-026](../adr/ADR-026-banco-postgres-proprio.md)

Sem argumentos.

## Experimentos

### `python -m scripts.experimento_falhas_llm`

Experimento controlado sobre os chunks que falharam na extração real. Custa tokens.

```bash
python -m scripts.experimento_falhas_llm [caminho_auditoria.json]
```

## Obsoletos

### `python -m scripts.gerar_relatorio_sinonimos`

Relatório de revisão dos sinônimos canônicos, substituído pelo da árvore.

**ADRs:** [ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md)

```bash
python -m scripts.gerar_relatorio_sinonimos [diretorio_revisao]
```
