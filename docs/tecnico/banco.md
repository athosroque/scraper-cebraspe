<!-- Gerado por scripts/gerar_docs.py a partir de src/registro/. Não editar à mão: rode `make docs-gerar`. -->

# Banco

Tabelas e views do `scraper-cebraspe-db`: o schema `public` (pipeline) e o `app` (usuários e simulados do site). Use para escrever uma consulta ou conferir uma coluna sem abrir o banco.

A estrutura é lida do `information_schema`. Só tabelas base e views; os schemas `test_*` dos testes ficam de fora.

## cargos_editais

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| concurso_id | integer | não |
| cargo_id | integer | não |
| numero | integer | não |
| nome | text | não |
| nivel | text | sim |

## concursos

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| slug | text | não |
| orgao_id | integer | não |
| ano | integer | sim |
| edital_arquivo | text | sim |
| status_revisao | text | não |
| total_chunks | integer | sim |
| metadados | jsonb | não |
| carregado_em | timestamp with time zone | não |
| banca | text | não |

## dim_ano

| Coluna | Tipo | Nulo |
|---|---|---|
| ano | integer | não |

## dim_cargo

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| chave | text | não |
| nome | text | não |

## dim_materia

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| chave | text | não |
| nome | text | não |
| nocoes | boolean | não |
| nome_de_cargo | boolean | não |

## dim_orgao

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| sigla | text | não |

## dim_subtopico

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| topico_id | integer | não |
| chave | text | não |
| nome | text | não |

## dim_topico

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| materia_id | integer | não |
| chave | text | não |
| nome | text | não |

## discursiva_no

| Coluna | Tipo | Nulo |
|---|---|---|
| discursiva_id | integer | não |
| no_id | text | não |
| papel | text | não |
| confianca | text | não |
| fora_do_edital | boolean | não |
| origem | text | não |
| status | text | não |
| criado_em | timestamp with time zone | não |
| atualizado_em | timestamp with time zone | não |

## discursivas

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| prova_id | integer | não |
| numero | integer | não |
| titulo | text | sim |
| tema | text | sim |
| enunciado | text | não |
| quesitos | jsonb | não |
| padrao_resposta | text | sim |

## fila_extracao_questoes

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| concurso_id | integer | não |
| categoria | text | não |
| arquivo | text | não |
| path_relativo | text | não |
| url | text | sim |
| sha256 | text | não |
| prova_id | integer | sim |
| status | text | não |
| criado_em | timestamp with time zone | não |
| atualizado_em | timestamp with time zone | não |
| tipo_documento | text | sim |
| mensagem | text | sim |
| assinatura_grupo | text | sim |

## inv_concurso

| Coluna | Tipo | Nulo |
|---|---|---|
| slug | text | não |
| orgao | text | não |
| ano | integer | sim |
| situacao | text | não |
| url | text | não |
| data_mapeamento | timestamp with time zone | sim |
| qtd_editais | integer | não |
| qtd_cadernos | integer | não |
| qtd_gabaritos | integer | não |
| qtd_padroes | integer | não |
| qtd_administrativos | integer | não |
| qtd_nao_classificados | integer | não |
| formato_provavel | text | sim |
| alertas | ARRAY | não |
| incluir | boolean | sim |
| no_banco | boolean | não |
| erro | text | sim |
| categoria_exclusao | text | sim |
| motivo_exclusao | text | sim |

## inv_pdf

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| concurso_slug | text | não |
| url | text | não |
| texto | text | não |
| tipo | text | não |
| versao | text | sim |
| curso_formacao | boolean | não |

## materia_no

| Coluna | Tipo | Nulo |
|---|---|---|
| materia_id | integer | não |
| no_id | text | não |

## no_arvore

| Coluna | Tipo | Nulo |
|---|---|---|
| id | text | não |
| nivel | text | não |
| nome | text | não |
| pai_id | text | sim |
| origem | text | não |
| status | text | não |
| fundido_em | text | sim |

## provas

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| concurso_id | integer | não |
| arquivo | text | não |
| identificador | text | sim |
| tipo | text | não |
| texto_link | text | sim |
| tema | text | sim |
| codigo_caderno | text | sim |
| parser_versao | integer | sim |

## provas_cargos

| Coluna | Tipo | Nulo |
|---|---|---|
| prova_id | integer | não |
| cargo_edital_id | integer | não |

## questao_no

| Coluna | Tipo | Nulo |
|---|---|---|
| questao_id | integer | não |
| no_id | text | não |
| papel | text | não |
| confianca | text | não |
| fora_do_edital | boolean | não |
| origem | text | não |
| status | text | não |
| criado_em | timestamp with time zone | não |
| atualizado_em | timestamp with time zone | não |

## questoes

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| prova_id | integer | não |
| numero | integer | não |
| enunciado | text | não |
| texto_base_id | integer | sim |
| gabarito | text | não |
| anulada | boolean | não |
| figuras | jsonb | não |
| secao | text | sim |
| alertas | ARRAY | não |
| utilizavel | boolean | não |
| tipo | character varying | não |
| alternativas | jsonb | sim |
| texto_tabela | text | sim |

## subtopico_no

| Coluna | Tipo | Nulo |
|---|---|---|
| subtopico_id | integer | não |
| no_id | text | não |

## taxonomia_itens

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| concurso_id | integer | não |
| cargo_edital_id | integer | sim |
| materia_id | integer | não |
| topico_id | integer | não |
| tipo_conhecimento | text | sim |
| nivel | text | sim |
| apenas_discursiva | boolean | não |
| chunk_index | integer | não |
| topico_ordem | integer | não |
| topico_nome | text | não |
| metadados | jsonb | não |
| cargos_restritos | ARRAY | sim |
| materia_origem | text | sim |

## taxonomia_subitens

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| taxonomia_item_id | integer | não |
| subtopico_id | integer | não |
| ordem | integer | não |
| nome | text | não |

## textos_base

| Coluna | Tipo | Nulo |
|---|---|---|
| id | integer | não |
| prova_id | integer | não |
| ordem | integer | não |
| texto | text | não |
| figuras | jsonb | não |

## topico_no

| Coluna | Tipo | Nulo |
|---|---|---|
| topico_id | integer | não |
| no_id | text | não |

## app.resposta

| Coluna | Tipo | Nulo |
|---|---|---|
| id | bigint | não |
| usuario_id | bigint | sim |
| questao_chave | text | não |
| resposta | character | sim |
| acertou | boolean | não |
| simulado_id | bigint | sim |
| respondida_em | timestamp with time zone | sim |

## app.simulado

| Coluna | Tipo | Nulo |
|---|---|---|
| id | bigint | não |
| usuario_id | bigint | sim |
| concurso | text | não |
| cargo_numero | integer | sim |
| inicio | timestamp with time zone | sim |
| fim | timestamp with time zone | sim |
| nota | numeric | sim |

## app.usuario

| Coluna | Tipo | Nulo |
|---|---|---|
| id | bigint | não |
| google_sub | text | não |
| email | text | não |
| nome | text | sim |
| criado_em | timestamp with time zone | sim |
| concurso_alvo | text | sim |
| cargo_alvo | integer | sim |

## Views

- `vw_arvore_edital_por_cargo`
- `vw_certo_errado_por_no`
- `vw_comparativo_nivel`
- `vw_discursivas`
- `vw_edital_cobra_assunto`
- `vw_edital_cobra_assunto_todas`
- `vw_edital_cobra_base`
- `vw_edital_cobra_materia`
- `vw_edital_cobra_materia_todas`
- `vw_edital_cobra_subassunto`
- `vw_edital_cobra_subassunto_todas`
- `vw_edital_vs_prova`
- `vw_incidencia_topico`
- `vw_incidencia_topico_todas`
- `vw_inventario_ano`
- `vw_no_apelidos`
- `vw_no_caminho`
- `vw_peso_materia_cargo`
- `vw_prova_cobra_assunto`
- `vw_prova_cobra_base`
- `vw_prova_cobra_materia`
- `vw_prova_cobra_no`
- `vw_prova_cobra_subassunto`
- `vw_questao_no`
- `vw_questoes`
- `vw_questoes_contexto`
- `vw_questoes_utilizaveis`
- `vw_subtopico_detalhe`
- `vw_taxonomia_detalhe`
