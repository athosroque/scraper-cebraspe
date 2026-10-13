<!-- Gerado por scripts/gerar_docs.py a partir de src/registro/. Não editar à mão: rode `make docs-gerar`. -->

# Checagens

O que confere cada parte do pipeline, por camada. Use depois de rodar um lote ou um passo que grava no banco, para saber se o resultado está verde.

Consulta de banco devolve as linhas problemáticas: zero linhas é verde. Checagens de teste ou de comando apontam para o teste do pytest ou para o comando que mostra o resultado.

## download

### K01 Todo PDF baixado começa com `%PDF-`

Saída vazia = verde; cada linha impressa é um arquivo que veio como HTML de erro.

- **Bloqueante:** sim
- **Onde consultar:** comando
- **ADRs:** [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

```bash
find data/2025/CEBRASPE -name '*.pdf' -print0 | xargs -0 -I{} sh -c 'head -c 5 "{}" | grep -q "%PDF-" || echo "NAO PDF: {}"'
```

### K02 Contagem de PDFs por tipo (editais, cadernos, gabaritos, padrões) igual à do inventário (`inv_concurso.qtd_*`) para os concursos incluídos

Informativo enquanto houver concursos do inventário ainda não carregados.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

```sql
SELECT ic.slug, ic.qtd_editais, e.n AS editais_pdf, ic.qtd_cadernos,
       cad.n AS cadernos_pdf, ic.qtd_gabaritos, gab.n AS gabaritos_pdf,
       ic.qtd_padroes, pad.n AS padroes_pdf
FROM inv_concurso ic
LEFT JOIN LATERAL (SELECT count(*) AS n FROM inv_pdf p
  WHERE p.concurso_slug = ic.slug AND p.tipo = 'edital_abertura') e ON true
LEFT JOIN LATERAL (SELECT count(*) AS n FROM inv_pdf p
  WHERE p.concurso_slug = ic.slug
    AND p.tipo IN ('caderno_objetivo', 'caderno_discursivo', 'caderno_com_gabarito')
  ) cad ON true
LEFT JOIN LATERAL (SELECT count(*) AS n FROM inv_pdf p
  WHERE p.concurso_slug = ic.slug
    AND p.tipo IN ('gabarito', 'caderno_com_gabarito')) gab ON true
LEFT JOIN LATERAL (SELECT count(*) AS n FROM inv_pdf p
  WHERE p.concurso_slug = ic.slug AND p.tipo = 'padrao_resposta') pad ON true
WHERE ic.incluir
  AND (ic.qtd_editais, ic.qtd_cadernos, ic.qtd_gabaritos, ic.qtd_padroes)
      IS DISTINCT FROM (e.n, cad.n, gab.n, pad.n)
ORDER BY ic.slug;
```

### K03 Concurso do inventário com erro gravado (`inv_concurso.erro`)

Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

```sql
SELECT slug, erro FROM inv_concurso WHERE erro IS NOT NULL ORDER BY slug;
```

### K04 Alertas do inventário (`inv_concurso.alertas`), exceto o informativo `curso_formacao`

Ex.: `aguardando_prova`, `muitos_nao_classificados`, `sem_caderno`. Informativo.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

```sql
SELECT slug, alertas, incluir FROM inv_concurso
WHERE cardinality(alertas) > 0 AND alertas <> '{curso_formacao}'
ORDER BY slug;
```

## edital

### K05 Alertas bloqueantes da validação da taxonomia do edital (`total_alertas` no `.validacao.json` de cada edital)

Esperado: 0 em todos. O comando só lê o resultado; rode antes o P3 do runbook.

- **Bloqueante:** sim
- **Onde consultar:** comando
- **ADRs:** [ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)

```bash
grep -H '"total_alertas"' revisao_piloto/*.validacao.json
```

### K06 Concurso com chunks mas sem cargo em `cargos_editais`, ou com cargo sem nível

Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT c.slug, c.total_chunks, count(ce.id) AS cargos,
       count(ce.id) FILTER (WHERE ce.nivel IS NULL) AS sem_nivel
FROM concursos c
LEFT JOIN cargos_editais ce ON ce.concurso_id = c.id
GROUP BY c.slug, c.total_chunks
HAVING count(ce.id) = 0 OR count(ce.id) FILTER (WHERE ce.nivel IS NULL) > 0
ORDER BY c.slug;
```

### K07 Concurso ainda não aprovado pelo dono (`concursos.status_revisao`)

É o portão humano: o agente nunca aprova.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-028](../adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md)

```sql
SELECT slug, status_revisao FROM concursos
WHERE status_revisao IS DISTINCT FROM 'aprovado'
ORDER BY slug;
```

### K08 Custo do OpenRouter da chave de taxonomia do edital (`usage_daily`)

Não é verde/vermelho: serve para registrar o custo do lote.

- **Bloqueante:** não
- **Onde consultar:** comando
- **ADRs:** nenhuma

```bash
curl -s -H "Authorization: Bearer $OPENROUTER_KEY_TAXONOMIA_EDITAL" https://openrouter.ai/api/v1/key
```

## prova

### K09 Itens da fila de extração que não estão `concluido`

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT arquivo, categoria, status, concurso_id FROM fila_extracao_questoes
WHERE status <> 'concluido'
ORDER BY concurso_id, arquivo;
```

### K10 Questão ME (`multipla_escolha`) com menos de 4 ou mais de 5 alternativas, ou sem alternativas

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT p.arquivo, q.numero FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.tipo = 'multipla_escolha'
  AND (q.alternativas IS NULL
       OR jsonb_array_length(q.alternativas) NOT BETWEEN 4 AND 5)
ORDER BY 1, 2;
```

### K11 Item sem gabarito e não anulado (`sem_gab` da consulta a do runbook)

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT p.arquivo, q.numero FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.gabarito IS NULL AND NOT q.anulada
ORDER BY 1, 2;
```

### K12 Gabarito fora da grade: ME aceita só A–E e X (anulada); C/E aceita só C, E e X

Qualquer outra letra é erro de parser.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT p.arquivo, q.numero, q.tipo, q.gabarito FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE (q.tipo = 'multipla_escolha' AND q.gabarito NOT IN ('A','B','C','D','E','X'))
   OR (q.tipo = 'certo_errado' AND q.gabarito NOT IN ('C','E','X'))
ORDER BY 1, 2;
```

### K13 Numeração duplicada dentro do mesmo caderno (mesmo `prova_id` e mesmo `numero`)

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT p.arquivo, q.numero, count(*) AS repeticoes FROM questoes q
JOIN provas p ON p.id = q.prova_id
GROUP BY p.id, p.arquivo, q.numero
HAVING count(*) > 1
ORDER BY 1, 2;
```

### K14 Discursiva sem quesito ou sem padrão de resposta

Tema vazio é aceito (ADR-031), por isso não entra aqui.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT p.arquivo, d.numero FROM discursivas d
JOIN provas p ON p.id = d.prova_id
WHERE d.quesitos IS NULL OR jsonb_array_length(d.quesitos) = 0
   OR d.padrao_resposta IS NULL
ORDER BY 1, 2;
```

### K15 Última alternativa termina em palavras em caixa alta

Sinal de cabeçalho de matéria colado na alternativa E (defeito da C1a corrigido em `_eh_cabecalho_layout_me`). Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT p.arquivo, q.numero, right(q.alternativas->-1->>'texto', 60) AS fim_ultima
FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.alternativas->-1->>'texto'
      ~ '[.?!:;)]\s+[A-ZÀ-Ú][A-ZÀ-Ú ,()–-]{3,}$'
ORDER BY 1, 2;
```

### K16 Caderno com uma seção só e mais de 20 itens

Em cadernos SEFA específicos isso é esperado (o nome da função vira a seção). Informativo: conferir se a seção bate com as matérias do edital.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** [ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md)

```sql
SELECT p.arquivo, count(DISTINCT q.secao) AS secoes, count(*) AS itens
FROM questoes q
JOIN provas p ON p.id = q.prova_id
GROUP BY p.id, p.arquivo
HAVING count(DISTINCT q.secao) = 1 AND count(*) > 20
ORDER BY 1;
```

### K17 Tipos de alerta gravados em `questoes.alertas`, com a quantidade de questões

Informativo: zero linhas = nenhum alerta.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT a AS alerta, count(*) AS questoes
FROM questoes, unnest(alertas) AS a
GROUP BY a
ORDER BY 2 DESC;
```

### K18 Questões com `utilizavel = false` (fora de 5D/5E)

Informativo; o caso esperado é fórmula ilegível (`simbolo_ilegivel`).

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT p.arquivo, q.numero, q.alertas FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE NOT q.utilizavel
ORDER BY 1, 2;
```

### K19 Alerta "ME sem texto-base": questão ME que cita texto, tabela, figura, gráfico ou quadro sem texto-base nem figura

Exceções: BANRISUL Q22, SEFA_PR Q11 e Q50 (por número no concurso). Não bloqueia; revisar as linhas no PDF.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT p.arquivo, q.numero FROM questoes q
JOIN provas p ON p.id = q.prova_id
JOIN concursos c ON c.id = p.concurso_id
WHERE q.tipo = 'multipla_escolha'
  AND q.texto_base_id IS NULL
  AND q.enunciado ~* '(texto|tabela|figura|gr[aá]fico|quadro)'
  AND NOT (q.figuras IS NOT NULL AND jsonb_array_length(q.figuras) > 0)
  AND (c.slug, q.numero) NOT IN (
        ('BANRISUL_25', 22), ('SEFA_PR_25', 11), ('SEFA_PR_25', 50))
ORDER BY 1, 2;
```

## banco

### K20 Número de provas gravadas por concurso igual a `qtd_cadernos` do inventário (Provas = caderno objetivo + discursivo)

Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)

```sql
SELECT ic.slug, ic.qtd_cadernos, count(p.id) AS provas
FROM inv_concurso ic
JOIN concursos c ON c.slug = ic.slug
LEFT JOIN provas p ON p.concurso_id = c.id
GROUP BY ic.slug, ic.qtd_cadernos
HAVING count(p.id) <> ic.qtd_cadernos
ORDER BY 1;
```

### K21 Prova sem nenhum item (questão nem discursiva)

Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT p.arquivo, c.slug FROM provas p
JOIN concursos c ON c.id = p.concurso_id
WHERE NOT EXISTS (SELECT 1 FROM questoes q WHERE q.prova_id = p.id)
  AND NOT EXISTS (SELECT 1 FROM discursivas d WHERE d.prova_id = p.id)
ORDER BY 2, 1;
```

## classificacao

### K30 Questão utilizável ou discursiva sem nenhum apontamento na árvore

Zero linhas = verde. Lote novo fica vermelho até a classificação (P8). O motivo do `sem_no` não fica no banco.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```sql
SELECT p.arquivo, q.numero AS item, 'questao_sem_apontamento' AS situacao
FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.utilizavel
  AND NOT EXISTS (SELECT 1 FROM questao_no qn WHERE qn.questao_id = q.id)
UNION ALL
SELECT p.arquivo, d.numero, 'discursiva_sem_apontamento'
FROM discursivas d
JOIN provas p ON p.id = d.prova_id
WHERE NOT EXISTS (SELECT 1 FROM discursiva_no dn WHERE dn.discursiva_id = d.id)
ORDER BY 1, 2;
```

### K31 Apontamento de confiança média ou baixa, para revisão em `classificacao.html` (alta entra em lote)

Informativo.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```sql
SELECT 'questao' AS origem, qn.questao_id::text AS ref, qn.no_id, qn.confianca
FROM questao_no qn
WHERE qn.confianca <> 'alta'
UNION ALL
SELECT 'discursiva', dn.discursiva_id::text, dn.no_id, dn.confianca
FROM discursiva_no dn
WHERE dn.confianca <> 'alta'
ORDER BY 1, 2;
```

### K32 Classificação com enunciado que mudou (`hash_enunciado` diferente) é pulada e conta em `desatualizados`

O teste guarda a regra de pular e contar. O número real sai no log `[CLASSIFICACAO]`.

- **Bloqueante:** sim
- **Onde consultar:** teste
- **Teste:** `tests/test_candidatos_questao.py::TestCandidatosEIntegracaoPostgres::test_aplicar_classificacao_pula_enunciado_divergente`
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

### K33 Nós criados fora da semente ou com status fora de ativo/aposentado/fundido, para conferir na revisão

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```sql
SELECT n.id, n.nivel, n.origem, n.status, n.nome FROM no_arvore n
WHERE n.origem <> 'semente' OR n.status NOT IN ('ativo', 'aposentado', 'fundido')
ORDER BY 1;
```

## arvore

### K25 Nó cujo `pai_id` aponta para nó que não existe em `no_arvore`

Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```sql
SELECT n.id, n.pai_id FROM no_arvore n
WHERE n.pai_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM no_arvore p WHERE p.id = n.pai_id)
ORDER BY 1;
```

### K26 Nó aposentado que ainda tem apontamento (questão, discursiva, matéria, tópico, subtópico) ou filho ativo

Zero linhas = verde.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **Teste:** `tests/test_arvore.py::test_aposentar_recusado_com_filho_ou_mapeamento`
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```sql
SELECT n.id, n.nome FROM no_arvore n
WHERE n.status = 'aposentado'
  AND (EXISTS (SELECT 1 FROM questao_no x WHERE x.no_id = n.id)
    OR EXISTS (SELECT 1 FROM discursiva_no x WHERE x.no_id = n.id)
    OR EXISTS (SELECT 1 FROM materia_no x WHERE x.no_id = n.id)
    OR EXISTS (SELECT 1 FROM topico_no x WHERE x.no_id = n.id)
    OR EXISTS (SELECT 1 FROM subtopico_no x WHERE x.no_id = n.id)
    OR EXISTS (SELECT 1 FROM no_arvore c
               WHERE c.pai_id = n.id AND c.status = 'ativo'))
ORDER BY 1;
```

### K27 Nó fundido cujo `fundido_em` não aponta para nó ativo

Informativo: inclui a fusão em cadeia (fundido que aponta para outro fundido).

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

```sql
SELECT n.id, n.fundido_em, t.status AS status_alvo FROM no_arvore n
LEFT JOIN no_arvore t ON t.id = n.fundido_em
WHERE n.status = 'fundido' AND (t.id IS NULL OR t.status <> 'ativo')
ORDER BY 1;
```

### K28 Guarda de ciclo: mover um nó para dentro de um descendente é recusado

- **Bloqueante:** sim
- **Onde consultar:** teste
- **Teste:** `tests/test_arvore.py::test_mover_no_ciclo`
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

### K29 Regra da árvore: item só mapeia dentro do mesmo pai efetivo, nunca sob outro pai

Caso ambíguo fica pendente (teste `test_regra_ambigua_fica_pendente`, no mesmo arquivo).

- **Bloqueante:** sim
- **Onde consultar:** teste
- **Teste:** `tests/test_regra_arvore.py::test_nao_mapeia_sob_outro_pai`
- **ADRs:** [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

## site

### K34 Suíte do pipeline verde (`make test-pipeline`)

- **Bloqueante:** sim
- **Onde consultar:** comando
- **ADRs:** nenhuma

```bash
make test-pipeline
```

### K35 Contagem de questões utilizáveis por concurso na view que o site lê

Não é verde/vermelho: é a contagem que o site deve exibir. Confira com a contagem do site na amostra.

- **Bloqueante:** não
- **Onde consultar:** banco
- **ADRs:** nenhuma

```sql
SELECT concurso, count(*) AS questoes_utilizaveis
FROM vw_questoes
WHERE utilizavel
GROUP BY concurso
ORDER BY concurso;
```

### K36 Atalho `/q/<codigo>` da questão: o código curto abre a questão certa (`site/tests/test_codigo_curto.py`)

- **Bloqueante:** sim
- **Onde consultar:** teste
- **Teste:** `site/tests/test_codigo_curto.py`
- **ADRs:** nenhuma

## piloto

### K22 Invariante do piloto (PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, CD_25_NS): itens 2800, anuladas 129, apontamentos 3029 e hash das chaves 5D `3257ba6a...`

Devolve linha só se algo mudou. Rodar antes e depois de todo passo que grava no banco.

- **Bloqueante:** sim
- **Onde consultar:** banco
- **Teste:** `tests/test_reconciliacao_inventario.py::test_regressao_piloto_chaves_5d_inalteradas`
- **ADRs:** nenhuma

```sql
WITH pil AS (
  SELECT p.id FROM provas p JOIN concursos c ON c.id = p.concurso_id
  WHERE c.slug IN ('PF_25_ADM', 'TCU_25_TEFC', 'IBAMA_25', 'STM_25', 'CD_25_NS')),
atual AS (
  SELECT
    (SELECT count(*) FROM questoes WHERE prova_id IN (SELECT id FROM pil)) AS itens,
    (SELECT count(*) FROM questoes WHERE prova_id IN (SELECT id FROM pil)
       AND anulada) AS anuladas,
    (SELECT count(*) FROM questao_no qn JOIN questoes q ON q.id = qn.questao_id
       WHERE q.prova_id IN (SELECT id FROM pil))
    + (SELECT count(*) FROM discursiva_no dn
         JOIN discursivas d ON d.id = dn.discursiva_id
       WHERE d.prova_id IN (SELECT id FROM pil)) AS apontamentos,
    (SELECT md5(string_agg(questao_chave, ',' ORDER BY questao_chave))
       FROM vw_questoes
       WHERE split_part(questao_chave, '|', 1)
             IN ('PF_25_ADM', 'TCU_25_TEFC', 'IBAMA_25', 'STM_25', 'CD_25_NS'))
      AS hash_chaves)
SELECT atual.* FROM atual
WHERE atual.itens <> 2800 OR atual.anuladas <> 129
   OR atual.apontamentos <> 3029
   OR atual.hash_chaves IS DISTINCT FROM '3257ba6ba525fdd6b4492733b50882f2';
```

### K23 Reconciliação do piloto: soma de provas e gabaritos dos manifestos locais bate com o banco

- **Bloqueante:** sim
- **Onde consultar:** teste
- **Teste:** `tests/test_reconciliacao_inventario.py::test_reconciliacao_piloto_manifestos_e_banco`
- **ADRs:** nenhuma

### K24 Chunking do edital do piloto: os editais reais classificam nos 4 blocos esperados

Pulado se os PDFs do piloto não estiverem em `data/`.

- **Bloqueante:** sim
- **Onde consultar:** teste
- **Teste:** `tests/test_edital_parser.py::test_edital_piloto_real_classifica_os_4_blocos`
- **ADRs:** nenhuma
