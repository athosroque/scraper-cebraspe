"""Checagens automáticas do lote, com o lugar onde ver cada resultado (Etapa 9/D2).

Cada checagem é uma consulta SQL só leitura (devolve as linhas problemáticas;
zero linhas = verde), um teste pytest ou um comando. A página "Checagens" da
documentação é gerada a partir deste tuple (`scripts/gerar_docs.py`).
"""

from src.registro.modelo import Checagem

_SQL_INVENTARIO_X_PDFS = """
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
"""

_SQL_INVENTARIO_ERRO = """
SELECT slug, erro FROM inv_concurso WHERE erro IS NOT NULL ORDER BY slug;
"""

_SQL_INVENTARIO_ALERTAS = """
SELECT slug, alertas, incluir FROM inv_concurso
WHERE cardinality(alertas) > 0 AND alertas <> '{curso_formacao}'
ORDER BY slug;
"""

_SQL_CARGOS_E_NIVEIS = """
SELECT c.slug, c.total_chunks, count(ce.id) AS cargos,
       count(ce.id) FILTER (WHERE ce.nivel IS NULL) AS sem_nivel
FROM concursos c
LEFT JOIN cargos_editais ce ON ce.concurso_id = c.id
GROUP BY c.slug, c.total_chunks
HAVING count(ce.id) = 0 OR count(ce.id) FILTER (WHERE ce.nivel IS NULL) > 0
ORDER BY c.slug;
"""

_SQL_CONCURSOS_NAO_APROVADOS = """
SELECT slug, status_revisao FROM concursos
WHERE status_revisao IS DISTINCT FROM 'aprovado'
ORDER BY slug;
"""

_SQL_FILA_NAO_CONCLUIDA = """
SELECT arquivo, categoria, status, concurso_id FROM fila_extracao_questoes
WHERE status <> 'concluido'
ORDER BY concurso_id, arquivo;
"""

_SQL_ME_ALTERNATIVAS = """
SELECT p.arquivo, q.numero FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.tipo = 'multipla_escolha'
  AND (q.alternativas IS NULL
       OR jsonb_array_length(q.alternativas) NOT BETWEEN 4 AND 5)
ORDER BY 1, 2;
"""

_SQL_ITEM_SEM_GABARITO = """
SELECT p.arquivo, q.numero FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.gabarito IS NULL AND NOT q.anulada
ORDER BY 1, 2;
"""

_SQL_GABARITO_FORA_DA_GRADE = """
SELECT p.arquivo, q.numero, q.tipo, q.gabarito FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE (q.tipo = 'multipla_escolha' AND q.gabarito NOT IN ('A','B','C','D','E','X'))
   OR (q.tipo = 'certo_errado' AND q.gabarito NOT IN ('C','E','X'))
ORDER BY 1, 2;
"""

_SQL_NUMERACAO_DUPLICADA = """
SELECT p.arquivo, q.numero, count(*) AS repeticoes FROM questoes q
JOIN provas p ON p.id = q.prova_id
GROUP BY p.id, p.arquivo, q.numero
HAVING count(*) > 1
ORDER BY 1, 2;
"""

_SQL_DISCURSIVA_INCOMPLETA = """
SELECT p.arquivo, d.numero FROM discursivas d
JOIN provas p ON p.id = d.prova_id
WHERE d.quesitos IS NULL OR jsonb_array_length(d.quesitos) = 0
   OR d.padrao_resposta IS NULL
ORDER BY 1, 2;
"""

_SQL_ALTERNATIVA_CAIXA_ALTA = r"""
SELECT p.arquivo, q.numero, right(q.alternativas->-1->>'texto', 60) AS fim_ultima
FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE q.alternativas->-1->>'texto'
      ~ '[.?!:;)]\s+[A-ZÀ-Ú][A-ZÀ-Ú ,()–-]{3,}$'
ORDER BY 1, 2;
"""

_SQL_CADERNO_UMA_SECAO = """
SELECT p.arquivo, count(DISTINCT q.secao) AS secoes, count(*) AS itens
FROM questoes q
JOIN provas p ON p.id = q.prova_id
GROUP BY p.id, p.arquivo
HAVING count(DISTINCT q.secao) = 1 AND count(*) > 20
ORDER BY 1;
"""

_SQL_ALERTAS_DA_QUESTAO = """
SELECT a AS alerta, count(*) AS questoes
FROM questoes, unnest(alertas) AS a
GROUP BY a
ORDER BY 2 DESC;
"""

_SQL_QUESTOES_NAO_UTILIZAVEIS = """
SELECT p.arquivo, q.numero, q.alertas FROM questoes q
JOIN provas p ON p.id = q.prova_id
WHERE NOT q.utilizavel
ORDER BY 1, 2;
"""

_SQL_ME_SEM_TEXTO_BASE = """
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
"""

_SQL_PROVAS_X_INVENTARIO = """
SELECT ic.slug, ic.qtd_cadernos, count(p.id) AS provas
FROM inv_concurso ic
JOIN concursos c ON c.slug = ic.slug
LEFT JOIN provas p ON p.concurso_id = c.id
GROUP BY ic.slug, ic.qtd_cadernos
HAVING count(p.id) <> ic.qtd_cadernos
ORDER BY 1;
"""

_SQL_PROVA_SEM_ITENS = """
SELECT p.arquivo, c.slug FROM provas p
JOIN concursos c ON c.id = p.concurso_id
WHERE NOT EXISTS (SELECT 1 FROM questoes q WHERE q.prova_id = p.id)
  AND NOT EXISTS (SELECT 1 FROM discursivas d WHERE d.prova_id = p.id)
ORDER BY 2, 1;
"""

# Esperado do piloto (5 concursos C/E + ME de 2025), medido em 2026-10-12 antes
# e depois do lote. Só devolve linha se algum valor sair do esperado.
_SQL_INVARIANTE_PILOTO = """
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
"""

_SQL_ARVORE_ORFAOS = """
SELECT n.id, n.pai_id FROM no_arvore n
WHERE n.pai_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM no_arvore p WHERE p.id = n.pai_id)
ORDER BY 1;
"""

_SQL_ARVORE_APOSENTADO_COM_USO = """
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
"""

_SQL_ARVORE_FUNDIDO_SEM_ALVO = """
SELECT n.id, n.fundido_em, t.status AS status_alvo FROM no_arvore n
LEFT JOIN no_arvore t ON t.id = n.fundido_em
WHERE n.status = 'fundido' AND (t.id IS NULL OR t.status <> 'ativo')
ORDER BY 1;
"""

_SQL_SEM_APONTAMENTO = """
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
"""

_SQL_CONFIANCA_MEDIA_BAIXA = """
SELECT 'questao' AS origem, qn.questao_id::text AS ref, qn.no_id, qn.confianca
FROM questao_no qn
WHERE qn.confianca <> 'alta'
UNION ALL
SELECT 'discursiva', dn.discursiva_id::text, dn.no_id, dn.confianca
FROM discursiva_no dn
WHERE dn.confianca <> 'alta'
ORDER BY 1, 2;
"""

_SQL_NOS_NOVOS = """
SELECT n.id, n.nivel, n.origem, n.status, n.nome FROM no_arvore n
WHERE n.origem <> 'semente' OR n.status NOT IN ('ativo', 'aposentado', 'fundido')
ORDER BY 1;
"""

_SQL_CONTAGEM_UTILIZAVEIS = """
SELECT concurso, count(*) AS questoes_utilizaveis
FROM vw_questoes
WHERE utilizavel
GROUP BY concurso
ORDER BY concurso;
"""


CHECAGENS: tuple[Checagem, ...] = (
    # --- download ---------------------------------------------------------
    Checagem(
        id="K01",
        camada="download",
        descricao=(
            "Todo PDF baixado começa com `%PDF-`. Saída vazia = verde; cada "
            "linha impressa é um arquivo que veio como HTML de erro."
        ),
        onde="comando",
        comando=(
            "find data/2025/CEBRASPE -name '*.pdf' -print0 | xargs -0 -I{} "
            'sh -c \'head -c 5 "{}" | grep -q "%PDF-" || echo "NAO PDF: {}"\''
        ),
        adrs=("ADR-037",),
    ),
    Checagem(
        id="K02",
        camada="download",
        descricao=(
            "Contagem de PDFs por tipo (editais, cadernos, gabaritos, padrões) "
            "igual à do inventário (`inv_concurso.qtd_*`) para os concursos "
            "incluídos. Informativo enquanto houver concursos do inventário ainda "
            "não carregados."
        ),
        onde="banco",
        consulta=_SQL_INVENTARIO_X_PDFS,
        bloqueante=False,
        adrs=("ADR-037",),
    ),
    Checagem(
        id="K03",
        camada="download",
        descricao=(
            "Concurso do inventário com erro gravado (`inv_concurso.erro`). "
            "Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_INVENTARIO_ERRO,
        adrs=("ADR-037",),
    ),
    Checagem(
        id="K04",
        camada="download",
        descricao=(
            "Alertas do inventário (`inv_concurso.alertas`), exceto o "
            "informativo `curso_formacao`. Ex.: `aguardando_prova`, "
            "`muitos_nao_classificados`, `sem_caderno`. Informativo."
        ),
        onde="banco",
        consulta=_SQL_INVENTARIO_ALERTAS,
        bloqueante=False,
        adrs=("ADR-037",),
    ),
    # --- edital -----------------------------------------------------------
    Checagem(
        id="K05",
        camada="edital",
        descricao=(
            "Alertas bloqueantes da validação da taxonomia do edital "
            "(`total_alertas` no `.validacao.json` de cada edital). Esperado: "
            "0 em todos. O comando só lê o resultado; rode antes o P3 do runbook."
        ),
        onde="comando",
        comando="grep -H '\"total_alertas\"' revisao_piloto/*.validacao.json",
        adrs=("ADR-025",),
    ),
    Checagem(
        id="K06",
        camada="edital",
        descricao=(
            "Concurso com chunks mas sem cargo em `cargos_editais`, ou com cargo "
            "sem nível. Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_CARGOS_E_NIVEIS,
    ),
    Checagem(
        id="K07",
        camada="edital",
        descricao=(
            "Concurso ainda não aprovado pelo dono (`concursos.status_revisao`). "
            "É o portão humano: o agente nunca aprova."
        ),
        onde="banco",
        consulta=_SQL_CONCURSOS_NAO_APROVADOS,
        adrs=("ADR-028",),
    ),
    Checagem(
        id="K08",
        camada="edital",
        descricao=(
            "Custo do OpenRouter da chave de taxonomia do edital (`usage_daily`). "
            "Não é verde/vermelho: serve para registrar o custo do lote."
        ),
        onde="comando",
        comando=(
            'curl -s -H "Authorization: Bearer $OPENROUTER_KEY_TAXONOMIA_EDITAL" '
            "https://openrouter.ai/api/v1/key"
        ),
        bloqueante=False,
    ),
    # --- prova ------------------------------------------------------------
    Checagem(
        id="K09",
        camada="prova",
        descricao=("Itens da fila de extração que não estão `concluido`."),
        onde="banco",
        consulta=_SQL_FILA_NAO_CONCLUIDA,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K10",
        camada="prova",
        descricao=(
            "Questão ME (`multipla_escolha`) com menos de 4 ou mais de 5 "
            "alternativas, ou sem alternativas."
        ),
        onde="banco",
        consulta=_SQL_ME_ALTERNATIVAS,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K11",
        camada="prova",
        descricao=(
            "Item sem gabarito e não anulado (`sem_gab` da consulta a do runbook)."
        ),
        onde="banco",
        consulta=_SQL_ITEM_SEM_GABARITO,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K12",
        camada="prova",
        descricao=(
            "Gabarito fora da grade: ME aceita só A–E e X (anulada); C/E aceita "
            "só C, E e X. Qualquer outra letra é erro de parser."
        ),
        onde="banco",
        consulta=_SQL_GABARITO_FORA_DA_GRADE,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K13",
        camada="prova",
        descricao=(
            "Numeração duplicada dentro do mesmo caderno (mesmo `prova_id` e "
            "mesmo `numero`)."
        ),
        onde="banco",
        consulta=_SQL_NUMERACAO_DUPLICADA,
    ),
    Checagem(
        id="K14",
        camada="prova",
        descricao=(
            "Discursiva sem quesito ou sem padrão de resposta. Tema vazio é "
            "aceito (ADR-031), por isso não entra aqui."
        ),
        onde="banco",
        consulta=_SQL_DISCURSIVA_INCOMPLETA,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K15",
        camada="prova",
        descricao=(
            "Última alternativa termina em palavras em caixa alta. Sinal de "
            "cabeçalho de matéria colado na alternativa E (defeito da C1a "
            "corrigido em `_eh_cabecalho_layout_me`). Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_ALTERNATIVA_CAIXA_ALTA,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K16",
        camada="prova",
        descricao=(
            "Caderno com uma seção só e mais de 20 itens. Em cadernos SEFA "
            "específicos isso é esperado (o nome da função vira a seção). "
            "Informativo: conferir se a seção bate com as matérias do edital."
        ),
        onde="banco",
        consulta=_SQL_CADERNO_UMA_SECAO,
        bloqueante=False,
        adrs=("ADR-031",),
    ),
    Checagem(
        id="K17",
        camada="prova",
        descricao=(
            "Tipos de alerta gravados em `questoes.alertas`, com a quantidade "
            "de questões. Informativo: zero linhas = nenhum alerta."
        ),
        onde="banco",
        consulta=_SQL_ALERTAS_DA_QUESTAO,
        bloqueante=False,
    ),
    Checagem(
        id="K18",
        camada="prova",
        descricao=(
            "Questões com `utilizavel = false` (fora de 5D/5E). Informativo; "
            "o caso esperado é fórmula ilegível (`simbolo_ilegivel`)."
        ),
        onde="banco",
        consulta=_SQL_QUESTOES_NAO_UTILIZAVEIS,
        bloqueante=False,
    ),
    Checagem(
        id="K19",
        camada="prova",
        descricao=(
            'Alerta "ME sem texto-base": questão ME que cita texto, tabela, '
            "figura, gráfico ou quadro sem texto-base nem figura. Exceções: "
            "BANRISUL Q22, SEFA_PR Q11 e Q50 (por número no concurso). Não "
            "bloqueia; revisar as linhas no PDF."
        ),
        onde="banco",
        consulta=_SQL_ME_SEM_TEXTO_BASE,
        bloqueante=False,
    ),
    # --- banco ------------------------------------------------------------
    Checagem(
        id="K20",
        camada="banco",
        descricao=(
            "Número de provas gravadas por concurso igual a `qtd_cadernos` do "
            "inventário (Provas = caderno objetivo + discursivo). Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_PROVAS_X_INVENTARIO,
        adrs=("ADR-037",),
    ),
    Checagem(
        id="K21",
        camada="banco",
        descricao=(
            "Prova sem nenhum item (questão nem discursiva). Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_PROVA_SEM_ITENS,
    ),
    # --- piloto -----------------------------------------------------------
    Checagem(
        id="K22",
        camada="piloto",
        descricao=(
            "Invariante do piloto (PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, "
            "CD_25_NS): itens 2800, anuladas 129, apontamentos 3029 e hash das "
            "chaves 5D `3257ba6a...`. Devolve linha só se algo mudou. Rodar "
            "antes e depois de todo passo que grava no banco."
        ),
        onde="banco",
        consulta=_SQL_INVARIANTE_PILOTO,
        teste=(
            "tests/test_reconciliacao_inventario.py::"
            "test_regressao_piloto_chaves_5d_inalteradas"
        ),
    ),
    Checagem(
        id="K23",
        camada="piloto",
        descricao=(
            "Reconciliação do piloto: soma de provas e gabaritos dos manifestos "
            "locais bate com o banco."
        ),
        onde="teste",
        teste=(
            "tests/test_reconciliacao_inventario.py::"
            "test_reconciliacao_piloto_manifestos_e_banco"
        ),
    ),
    Checagem(
        id="K24",
        camada="piloto",
        descricao=(
            "Chunking do edital do piloto: os editais reais classificam nos 4 "
            "blocos esperados. Pulado se os PDFs do piloto não estiverem em `data/`."
        ),
        onde="teste",
        teste=(
            "tests/test_edital_parser.py::"
            "test_edital_piloto_real_classifica_os_4_blocos"
        ),
    ),
    # --- arvore -----------------------------------------------------------
    Checagem(
        id="K25",
        camada="arvore",
        descricao=(
            "Nó cujo `pai_id` aponta para nó que não existe em `no_arvore`. "
            "Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_ARVORE_ORFAOS,
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K26",
        camada="arvore",
        descricao=(
            "Nó aposentado que ainda tem apontamento (questão, discursiva, matéria, "
            "tópico, subtópico) ou filho ativo. Zero linhas = verde."
        ),
        onde="banco",
        consulta=_SQL_ARVORE_APOSENTADO_COM_USO,
        teste=("tests/test_arvore.py::test_aposentar_recusado_com_filho_ou_mapeamento"),
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K27",
        camada="arvore",
        descricao=(
            "Nó fundido cujo `fundido_em` não aponta para nó ativo. Informativo: "
            "inclui a fusão em cadeia (fundido que aponta para outro fundido)."
        ),
        onde="banco",
        consulta=_SQL_ARVORE_FUNDIDO_SEM_ALVO,
        bloqueante=False,
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K28",
        camada="arvore",
        descricao=(
            "Guarda de ciclo: mover um nó para dentro de um descendente é recusado."
        ),
        onde="teste",
        teste="tests/test_arvore.py::test_mover_no_ciclo",
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K29",
        camada="arvore",
        descricao=(
            "Regra da árvore: item só mapeia dentro do mesmo pai efetivo, nunca "
            "sob outro pai. Caso ambíguo fica pendente (teste "
            "`test_regra_ambigua_fica_pendente`, no mesmo arquivo)."
        ),
        onde="teste",
        teste="tests/test_regra_arvore.py::test_nao_mapeia_sob_outro_pai",
        adrs=("ADR-030",),
    ),
    # --- classificacao ----------------------------------------------------
    Checagem(
        id="K30",
        camada="classificacao",
        descricao=(
            "Questão utilizável ou discursiva sem nenhum apontamento na árvore. "
            "Zero linhas = verde. Lote novo fica vermelho até a classificação (P8). "
            "O motivo do `sem_no` não fica no banco."
        ),
        onde="banco",
        consulta=_SQL_SEM_APONTAMENTO,
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K31",
        camada="classificacao",
        descricao=(
            "Apontamento de confiança média ou baixa, para revisão em "
            "`classificacao.html` (alta entra em lote). Informativo."
        ),
        onde="banco",
        consulta=_SQL_CONFIANCA_MEDIA_BAIXA,
        bloqueante=False,
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K32",
        camada="classificacao",
        descricao=(
            "Classificação com enunciado que mudou (`hash_enunciado` diferente) é "
            "pulada e conta em `desatualizados`. O teste guarda a regra de pular e "
            "contar. O número real sai no log `[CLASSIFICACAO]`."
        ),
        onde="teste",
        teste=(
            "tests/test_candidatos_questao.py::TestCandidatosEIntegracaoPostgres::"
            "test_aplicar_classificacao_pula_enunciado_divergente"
        ),
        adrs=("ADR-030",),
    ),
    Checagem(
        id="K33",
        camada="classificacao",
        descricao=(
            "Nós criados fora da semente ou com status fora de ativo/aposentado/"
            "fundido, para conferir na revisão."
        ),
        onde="banco",
        consulta=_SQL_NOS_NOVOS,
        bloqueante=False,
        adrs=("ADR-030",),
    ),
    # --- site -------------------------------------------------------------
    Checagem(
        id="K34",
        camada="site",
        descricao="Suíte do pipeline verde (`make test-pipeline`).",
        onde="comando",
        comando="make test-pipeline",
    ),
    Checagem(
        id="K35",
        camada="site",
        descricao=(
            "Contagem de questões utilizáveis por concurso na view que o site lê. "
            "Não é verde/vermelho: é a contagem que o site deve exibir. Confira com "
            "a contagem do site na amostra."
        ),
        onde="banco",
        consulta=_SQL_CONTAGEM_UTILIZAVEIS,
        bloqueante=False,
    ),
    Checagem(
        id="K36",
        camada="site",
        descricao=(
            "Atalho `/q/<codigo>` da questão: o código curto abre a questão certa "
            "(`site/tests/test_codigo_curto.py`)."
        ),
        onde="teste",
        teste="site/tests/test_codigo_curto.py",
    ),
)
