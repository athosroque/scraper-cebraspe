-- Star schema de estatísticas de concursos (Etapa 5, ADR-027).
--
-- Banco próprio `scraper-cebraspe-db` (ADR-026): nenhuma FK para outro
-- projeto. As dimensões carregam chave natural normalizada
-- (`comparacao_texto.normalizar`), que é a ponte para o cruzamento futuro com
-- `itens_estudo` (Etapa 7).
--
-- Idempotente: executado a cada `stats_writer.gravar_estatisticas`. Nomes sem
-- schema de propósito — o teste de integração roda num schema temporário via
-- `search_path`.

-- Dimensões ------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dim_orgao (
    id SERIAL PRIMARY KEY,
    sigla TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_ano (
    ano INTEGER PRIMARY KEY
);

-- `nocoes`: o nome de origem é "NOÇÕES DE X" — mesma matéria canônica X
-- (decisão do dono, Etapa 5B), com a marca de profundidade.
CREATE TABLE IF NOT EXISTS dim_materia (
    id SERIAL PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    nocoes BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS dim_topico (
    id SERIAL PRIMARY KEY,
    materia_id INTEGER NOT NULL REFERENCES dim_materia (id),
    chave TEXT NOT NULL,
    nome TEXT NOT NULL,
    UNIQUE (materia_id, chave)
);

CREATE TABLE IF NOT EXISTS dim_subtopico (
    id SERIAL PRIMARY KEY,
    topico_id INTEGER NOT NULL REFERENCES dim_topico (id),
    chave TEXT NOT NULL,
    nome TEXT NOT NULL,
    UNIQUE (topico_id, chave)
);

-- Árvore Mestre (Etapa 5B.1, ADR-030) ------------------------------------------
-- Derivada de `canonico/arvore.json`. O ID é estável, herdado da 5B ou sha1.

CREATE TABLE IF NOT EXISTS no_arvore (
    id TEXT PRIMARY KEY,
    nivel TEXT NOT NULL CHECK (nivel IN ('materia', 'assunto', 'subassunto')),
    nome TEXT NOT NULL,
    pai_id TEXT REFERENCES no_arvore (id) DEFERRABLE INITIALLY DEFERRED,
    origem TEXT NOT NULL CHECK (origem IN ('semente', 'humano', 'llm', 'regra')),
    status TEXT NOT NULL CONSTRAINT no_arvore_status_check CHECK (status IN ('ativo', 'proposto', 'fundido', 'aposentado')),
    -- Nó fundido nunca é apagado: aponta para o destino (ver `vw_no_caminho`).
    fundido_em TEXT REFERENCES no_arvore (id) DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE IF NOT EXISTS materia_no (
    materia_id INTEGER NOT NULL REFERENCES dim_materia (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id) ON DELETE CASCADE,
    PRIMARY KEY (materia_id, no_id)
);

CREATE TABLE IF NOT EXISTS topico_no (
    topico_id INTEGER NOT NULL REFERENCES dim_topico (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id) ON DELETE CASCADE,
    PRIMARY KEY (topico_id, no_id)
);

CREATE TABLE IF NOT EXISTS subtopico_no (
    subtopico_id INTEGER NOT NULL REFERENCES dim_subtopico (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id) ON DELETE CASCADE,
    PRIMARY KEY (subtopico_id, no_id)
);


-- Migração idempotente de bancos criados antes da Etapa 5B.1:
ALTER TABLE IF EXISTS dim_materia DROP COLUMN IF EXISTS materia_canonica_id CASCADE;
ALTER TABLE IF EXISTS dim_topico DROP COLUMN IF EXISTS assunto_canonico_id CASCADE;
ALTER TABLE IF EXISTS dim_subtopico DROP COLUMN IF EXISTS subassunto_canonico_id CASCADE;

DROP TABLE IF EXISTS subassunto_canonico CASCADE;
DROP TABLE IF EXISTS assunto_canonico CASCADE;
DROP TABLE IF EXISTS materia_canonica CASCADE;
ALTER TABLE no_arvore ADD COLUMN IF NOT EXISTS fundido_em TEXT
    REFERENCES no_arvore (id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE no_arvore DROP CONSTRAINT IF EXISTS no_arvore_status_check;
ALTER TABLE no_arvore ADD CONSTRAINT no_arvore_status_check
    CHECK (status IN ('ativo', 'proposto', 'fundido', 'aposentado'));

CREATE TABLE IF NOT EXISTS dim_cargo (
    id SERIAL PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL
);

-- Fatos ----------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS concursos (
    id SERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    orgao_id INTEGER NOT NULL REFERENCES dim_orgao (id),
    ano INTEGER REFERENCES dim_ano (ano),
    edital_arquivo TEXT,
    -- A aprovação da revisão humana é registrada no JSON de revisão
    -- (`status_revisao_humana`) e ingerida pelo stats_writer; as views de
    -- estatística só contam concurso `aprovado`.
    status_revisao TEXT NOT NULL DEFAULT 'pendente'
        CHECK (status_revisao IN ('pendente', 'aprovado')),
    total_chunks INTEGER,
    metadados JSONB NOT NULL DEFAULT '{}'::jsonb,
    carregado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cargos_editais (
    id SERIAL PRIMARY KEY,
    concurso_id INTEGER NOT NULL REFERENCES concursos (id) ON DELETE CASCADE,
    cargo_id INTEGER NOT NULL REFERENCES dim_cargo (id),
    numero INTEGER NOT NULL,
    nome TEXT NOT NULL,
    nivel TEXT CHECK (nivel IN ('medio', 'superior')),
    UNIQUE (concurso_id, numero)
);

-- Grão: 1 linha = 1 tópico de 1 chunk. Chunk de conhecimento básico é
-- compartilhado pelos cargos do nível, então `cargo_edital_id` fica NULL.
CREATE TABLE IF NOT EXISTS taxonomia_itens (
    id SERIAL PRIMARY KEY,
    concurso_id INTEGER NOT NULL REFERENCES concursos (id) ON DELETE CASCADE,
    cargo_edital_id INTEGER REFERENCES cargos_editais (id) ON DELETE CASCADE,
    materia_id INTEGER NOT NULL REFERENCES dim_materia (id),
    topico_id INTEGER NOT NULL REFERENCES dim_topico (id),
    tipo_conhecimento TEXT CHECK (tipo_conhecimento IN ('basico', 'especifico', 'complementar')),
    nivel TEXT CHECK (nivel IN ('medio', 'superior')),
    apenas_discursiva BOOLEAN NOT NULL DEFAULT false,
    chunk_index INTEGER NOT NULL,
    topico_ordem INTEGER NOT NULL,
    topico_nome TEXT NOT NULL,
    metadados JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Lista de IDs/números de cargo quando a matéria/chunk é restrita, ou NULL se comum a todos do nível/cargo
    cargos_restritos INTEGER[],
    UNIQUE (concurso_id, chunk_index, topico_ordem)
);

-- Migração idempotente para bancos existentes antes da introdução da coluna:
ALTER TABLE taxonomia_itens ADD COLUMN IF NOT EXISTS cargos_restritos INTEGER[];
-- Etapa 5B: o subtópico saiu do JSONB para `taxonomia_subitens` (a view que
-- dependia da coluna é recriada abaixo).
ALTER TABLE taxonomia_itens DROP COLUMN IF EXISTS subtopicos CASCADE;

-- Grão: 1 linha = 1 subtópico de 1 tópico de 1 chunk (Etapa 5B).
CREATE TABLE IF NOT EXISTS taxonomia_subitens (
    id SERIAL PRIMARY KEY,
    taxonomia_item_id INTEGER NOT NULL REFERENCES taxonomia_itens (id) ON DELETE CASCADE,
    subtopico_id INTEGER NOT NULL REFERENCES dim_subtopico (id),
    ordem INTEGER NOT NULL,
    nome TEXT NOT NULL,
    UNIQUE (taxonomia_item_id, ordem)
);

CREATE INDEX IF NOT EXISTS idx_taxonomia_subitens_subtopico ON taxonomia_subitens (subtopico_id);

CREATE INDEX IF NOT EXISTS idx_taxonomia_itens_topico ON taxonomia_itens (topico_id);
CREATE INDEX IF NOT EXISTS idx_taxonomia_itens_materia ON taxonomia_itens (materia_id);

-- Caderno de prova. Sem `nivel`: nível é atributo do cargo, lido pela ponte.
CREATE TABLE IF NOT EXISTS provas (
    id SERIAL PRIMARY KEY,
    concurso_id INTEGER NOT NULL REFERENCES concursos (id) ON DELETE CASCADE,
    arquivo TEXT NOT NULL,
    identificador TEXT,
    tipo TEXT NOT NULL
        CHECK (tipo IN ('objetiva_basica', 'objetiva_especifica', 'discursiva')),
    texto_link TEXT,
    -- Só discursiva; preenchido pela extração de questões (Etapa 5C), com
    -- os temas das questões do caderno separados por " | ".
    tema TEXT,
    UNIQUE (concurso_id, arquivo)
);

-- Etapa 5C (ADR-031): código do caderno impresso no gabarito
-- (`094_PF_CB1_01`), que liga gabarito e caderno com nome em hash (CD/TCU).
ALTER TABLE provas ADD COLUMN IF NOT EXISTS codigo_caderno TEXT;

-- N:1 nos básicos (CB1 -> cargos 1..14) e 1:1 em específica/discursiva.
CREATE TABLE IF NOT EXISTS provas_cargos (
    prova_id INTEGER NOT NULL REFERENCES provas (id) ON DELETE CASCADE,
    cargo_edital_id INTEGER NOT NULL REFERENCES cargos_editais (id) ON DELETE CASCADE,
    PRIMARY KEY (prova_id, cargo_edital_id)
);

-- Fila da extração de questões (Etapa 5C, consumidor em
-- `scripts/extrair_questoes.py`). O writer nunca altera `status`,
-- `tipo_documento` nem `mensagem`: são estado do consumidor.
CREATE TABLE IF NOT EXISTS fila_extracao_questoes (
    id SERIAL PRIMARY KEY,
    concurso_id INTEGER NOT NULL REFERENCES concursos (id) ON DELETE CASCADE,
    categoria TEXT NOT NULL CHECK (categoria IN ('prova', 'gabarito')),
    arquivo TEXT NOT NULL,
    path_relativo TEXT NOT NULL,
    url TEXT,
    sha256 TEXT NOT NULL UNIQUE,
    prova_id INTEGER REFERENCES provas (id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente', 'processando', 'concluido', 'erro')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fila_status ON fila_extracao_questoes (status);

-- Etapa 5C: o consumidor registra o tipo do documento lido (`grade`,
-- `padrao_resposta`, `justificativa`, `caderno_objetivo`,
-- `caderno_discursivo`) e o motivo de `erro`.
ALTER TABLE fila_extracao_questoes ADD COLUMN IF NOT EXISTS tipo_documento TEXT;
ALTER TABLE fila_extracao_questoes ADD COLUMN IF NOT EXISTS mensagem TEXT;
ALTER TABLE fila_extracao_questoes ADD COLUMN IF NOT EXISTS assinatura_grupo TEXT;

-- Banca organizadora (Etapa 5C). O projeto só coleta CEBRASPE, e a banca vem
-- do path `data/<ano>/<BANCA>/...`.
ALTER TABLE concursos ADD COLUMN IF NOT EXISTS banca TEXT NOT NULL DEFAULT 'CEBRASPE';

-- Questões extraídas dos cadernos (Etapa 5C, ADR-031) -------------------------
-- Substituídas por caderno a cada extração (mesma regra dos fatos do
-- ADR-027). Cargo, nível, ano, órgão e banca vêm por join:
-- prova -> provas_cargos -> cargos_editais -> concursos.

CREATE TABLE IF NOT EXISTS textos_base (
    id SERIAL PRIMARY KEY,
    prova_id INTEGER NOT NULL REFERENCES provas (id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    texto TEXT NOT NULL,
    figuras JSONB NOT NULL DEFAULT '[]'::jsonb,
    UNIQUE (prova_id, ordem)
);

CREATE TABLE IF NOT EXISTS questoes (
    id SERIAL PRIMARY KEY,
    prova_id INTEGER NOT NULL REFERENCES provas (id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    enunciado TEXT NOT NULL,
    texto_base_id INTEGER,
    gabarito TEXT NOT NULL CHECK (gabarito IN ('C', 'E', 'X')),
    anulada BOOLEAN NOT NULL DEFAULT false,
    figuras JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- Comando do grupo ("Julgue os itens relativos a X"): pista para a
    -- classificação por assunto (Etapa 5D).
    secao TEXT,
    alertas TEXT[] NOT NULL DEFAULT '{}',
    utilizavel BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (prova_id, numero)
);

CREATE INDEX IF NOT EXISTS idx_questoes_prova ON questoes (prova_id);

-- Etapa 5C.1 (Sessão 2): integridade referencial prova <-> texto-base.
-- Garante no banco que a questão só pode apontar para texto-base da mesma prova.
-- Usa ON DELETE SET NULL (texto_base_id) (PostgreSQL 15+) para anular apenas a
-- coluna texto_base_id caso o texto-base seja removido, preservando prova_id
-- (SET NULL sem lista zeraria também prova_id, que é NOT NULL).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'textos_base'::regclass AND conname = 'uq_textos_base_id_prova'
    ) THEN
        ALTER TABLE textos_base ADD CONSTRAINT uq_textos_base_id_prova UNIQUE (id, prova_id);
    END IF;

    -- A FK antiga (só texto_base_id) é redundante com a FK composta e pode sair
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'questoes'::regclass AND conname = 'questoes_texto_base_id_fkey'
    ) THEN
        ALTER TABLE questoes DROP CONSTRAINT questoes_texto_base_id_fkey;
    END IF;

    -- Versão anterior da FK composta, com SET NULL sem lista de colunas
    -- (confdelsetcols vazio): troca pela certa. Já certa, não mexe, para não
    -- revalidar a tabela inteira a cada aplicação do schema.
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'questoes'::regclass AND conname = 'fk_questoes_texto_base_mesma_prova'
          AND coalesce(array_length(confdelsetcols, 1), 0) = 0
    ) THEN
        ALTER TABLE questoes DROP CONSTRAINT fk_questoes_texto_base_mesma_prova;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'questoes'::regclass AND conname = 'fk_questoes_texto_base_mesma_prova'
    ) THEN
        ALTER TABLE questoes
            ADD CONSTRAINT fk_questoes_texto_base_mesma_prova
            FOREIGN KEY (texto_base_id, prova_id)
            REFERENCES textos_base (id, prova_id)
            ON DELETE SET NULL (texto_base_id);
    END IF;
END $$;

-- Etapa 5C.1 (Sessão 2): alertas no item e flag de usabilidade para 5D/5E.
ALTER TABLE questoes ADD COLUMN IF NOT EXISTS alertas TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE questoes ADD COLUMN IF NOT EXISTS utilizavel BOOLEAN NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_questoes_utilizavel ON questoes (utilizavel);
CREATE INDEX IF NOT EXISTS idx_questoes_alertas ON questoes USING gin (alertas);

CREATE OR REPLACE VIEW vw_questoes_utilizaveis AS
SELECT * FROM questoes
WHERE utilizavel;

-- 1 linha por questão do caderno discursivo (há caderno com "Questão 1",
-- "Questão 2" e "Peça de natureza técnica").
CREATE TABLE IF NOT EXISTS discursivas (
    id SERIAL PRIMARY KEY,
    prova_id INTEGER NOT NULL REFERENCES provas (id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    titulo TEXT,
    tema TEXT,
    enunciado TEXT NOT NULL,
    quesitos JSONB NOT NULL DEFAULT '[]'::jsonb,
    padrao_resposta TEXT,
    UNIQUE (prova_id, numero)
);

-- Classificação de questões na árvore mestre (Etapa 5D) -----------------------

CREATE TABLE IF NOT EXISTS questao_no (
    questao_id INTEGER NOT NULL REFERENCES questoes (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id),
    papel TEXT NOT NULL CONSTRAINT questao_no_papel_check CHECK (papel IN ('principal', 'secundario')),
    confianca TEXT NOT NULL CONSTRAINT questao_no_confianca_check CHECK (confianca IN ('alta', 'media', 'baixa')),
    fora_do_edital BOOLEAN NOT NULL DEFAULT false,
    origem TEXT NOT NULL CONSTRAINT questao_no_origem_check CHECK (origem IN ('llm', 'humano')),
    status TEXT NOT NULL CONSTRAINT questao_no_status_check CHECK (status IN ('proposto', 'aprovado', 'rejeitado')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (questao_id, no_id)
);

CREATE INDEX IF NOT EXISTS idx_questao_no_no ON questao_no (no_id);
CREATE INDEX IF NOT EXISTS idx_questao_no_status ON questao_no (status);

CREATE TABLE IF NOT EXISTS discursiva_no (
    discursiva_id INTEGER NOT NULL REFERENCES discursivas (id) ON DELETE CASCADE,
    no_id TEXT NOT NULL REFERENCES no_arvore (id),
    papel TEXT NOT NULL CONSTRAINT discursiva_no_papel_check CHECK (papel IN ('principal', 'secundario')),
    confianca TEXT NOT NULL CONSTRAINT discursiva_no_confianca_check CHECK (confianca IN ('alta', 'media', 'baixa')),
    fora_do_edital BOOLEAN NOT NULL DEFAULT false,
    origem TEXT NOT NULL CONSTRAINT discursiva_no_origem_check CHECK (origem IN ('llm', 'humano')),
    status TEXT NOT NULL CONSTRAINT discursiva_no_status_check CHECK (status IN ('proposto', 'aprovado', 'rejeitado')),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (discursiva_id, no_id)
);

CREATE INDEX IF NOT EXISTS idx_discursiva_no_no ON discursiva_no (no_id);
CREATE INDEX IF NOT EXISTS idx_discursiva_no_status ON discursiva_no (status);

-- Views ----------------------------------------------------------------------

DROP VIEW IF EXISTS vw_incidencia_topico CASCADE;
DROP VIEW IF EXISTS vw_incidencia_topico_todas CASCADE;
DROP VIEW IF EXISTS vw_taxonomia_detalhe CASCADE;
DROP VIEW IF EXISTS vw_subtopico_detalhe CASCADE;
DROP VIEW IF EXISTS vw_questao_no CASCADE;
DROP VIEW IF EXISTS vw_no_caminho CASCADE;
DROP VIEW IF EXISTS vw_arvore_edital_por_cargo CASCADE;
DROP VIEW IF EXISTS vw_edital_cobra_subassunto CASCADE;
DROP VIEW IF EXISTS vw_edital_cobra_assunto CASCADE;
DROP VIEW IF EXISTS vw_edital_cobra_materia CASCADE;
DROP VIEW IF EXISTS vw_edital_cobra_base CASCADE;

-- Caminho de cada nó (matéria > assunto > subassunto). Só nó `ativo` com
-- toda a cadeia `ativa` entra: nó `proposto` (e o que estiver abaixo dele)
-- não muda estatística antes da aprovação. O nó `fundido` aparece com o
-- caminho do destino (`no_efetivo`), resolvendo o redirecionamento.
CREATE OR REPLACE VIEW vw_no_caminho AS
WITH RECURSIVE hierarquia AS (
    SELECT id, nivel, nome, pai_id,
           nome AS caminho,
           id AS materia_id,
           NULL::text AS assunto_id
    FROM no_arvore
    WHERE pai_id IS NULL AND status = 'ativo'

    UNION ALL

    SELECT n.id, n.nivel, n.nome, n.pai_id,
           h.caminho || ' > ' || n.nome,
           h.materia_id,
           CASE WHEN n.nivel = 'assunto' THEN n.id ELSE h.assunto_id END
    FROM no_arvore n
    INNER JOIN hierarquia h ON n.pai_id = h.id
    WHERE n.status = 'ativo'
),
resolucao AS (
    SELECT id AS no_id, id AS atual, 0 AS passos
    FROM no_arvore

    UNION ALL

    SELECT r.no_id, n.fundido_em, r.passos + 1
    FROM resolucao r
    INNER JOIN no_arvore n ON n.id = r.atual
    WHERE n.status = 'fundido' AND n.fundido_em IS NOT NULL AND r.passos < 20
),
efetivo AS (
    SELECT DISTINCT ON (no_id) no_id, atual
    FROM resolucao
    ORDER BY no_id, passos DESC
)
SELECT
    e.no_id AS id,
    h.id AS no_efetivo,
    h.nivel,
    h.nome,
    h.pai_id,
    h.caminho,
    h.materia_id,
    h.assunto_id
FROM efetivo e
INNER JOIN hierarquia h ON h.id = e.atual;

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

CREATE OR REPLACE VIEW vw_taxonomia_detalhe AS
SELECT
    c.slug AS concurso,
    o.sigla AS orgao,
    c.ano,
    c.status_revisao,
    ti.tipo_conhecimento,
    ti.nivel,
    ce.numero AS cargo_numero,
    ce.nome AS cargo,
    ti.cargos_restritos,
    m.nome AS materia,
    m.chave AS materia_chave,
    m.nocoes,
    t.nome AS topico,
    t.chave AS topico_chave,
    ti.apenas_discursiva,
    (SELECT count(*) FROM taxonomia_subitens AS s WHERE s.taxonomia_item_id = ti.id) AS total_subtopicos
FROM taxonomia_itens AS ti
INNER JOIN concursos AS c ON ti.concurso_id = c.id
INNER JOIN dim_orgao AS o ON c.orgao_id = o.id
INNER JOIN dim_materia AS m ON ti.materia_id = m.id
INNER JOIN dim_topico AS t ON ti.topico_id = t.id
LEFT JOIN cargos_editais AS ce ON ti.cargo_edital_id = ce.id;

CREATE OR REPLACE VIEW vw_subtopico_detalhe AS
SELECT
    d.concurso,
    d.orgao,
    d.ano,
    d.status_revisao,
    d.tipo_conhecimento,
    d.nivel,
    d.cargo_numero,
    d.materia,
    d.topico,
    si.ordem AS subtopico_ordem,
    si.nome AS subtopico,
    st.chave AS subtopico_chave
FROM taxonomia_subitens AS si
INNER JOIN taxonomia_itens AS ti ON si.taxonomia_item_id = ti.id
INNER JOIN dim_subtopico AS st ON si.subtopico_id = st.id
INNER JOIN LATERAL (
    SELECT c.slug AS concurso, o.sigla AS orgao, c.ano, c.status_revisao, ti.tipo_conhecimento, ti.nivel,
           ce.numero AS cargo_numero, m.nome AS materia, t.nome AS topico
    FROM concursos AS c
    INNER JOIN dim_orgao AS o ON c.orgao_id = o.id
    INNER JOIN dim_materia AS m ON m.id = ti.materia_id
    INNER JOIN dim_topico AS t ON t.id = ti.topico_id
    LEFT JOIN cargos_editais AS ce ON ce.id = ti.cargo_edital_id
    WHERE c.id = ti.concurso_id
) AS d ON true;

CREATE OR REPLACE VIEW vw_arvore_edital_por_cargo AS
WITH expansao_cargos AS (
    SELECT 
        ti.id AS taxonomia_item_id,
        ti.concurso_id,
        ti.materia_id,
        ti.topico_id,
        ti.tipo_conhecimento,
        ti.apenas_discursiva,
        ce.id AS cargo_edital_id,
        ce.numero AS cargo_numero,
        ce.nome AS cargo,
        ce.nivel AS nivel
    FROM taxonomia_itens ti
    CROSS JOIN cargos_editais ce
    WHERE ce.concurso_id = ti.concurso_id 
      AND ti.cargo_edital_id IS NULL
      AND (ti.cargos_restritos IS NULL OR ce.numero = ANY(ti.cargos_restritos))
      AND ce.nivel = ti.nivel
    
    UNION ALL
    
    SELECT
        ti.id AS taxonomia_item_id,
        ti.concurso_id,
        ti.materia_id,
        ti.topico_id,
        ti.tipo_conhecimento,
        ti.apenas_discursiva,
        ce.id AS cargo_edital_id,
        ce.numero AS cargo_numero,
        ce.nome AS cargo,
        ce.nivel AS nivel
    FROM taxonomia_itens ti
    INNER JOIN cargos_editais ce ON ce.id = ti.cargo_edital_id
),
mapeamentos AS (
    -- Matéria
    SELECT e.taxonomia_item_id, e.cargo_edital_id, mn.no_id, 'materia' AS origem_map
    FROM expansao_cargos e
    INNER JOIN materia_no mn ON mn.materia_id = e.materia_id
    
    UNION ALL
    
    -- Tópico
    SELECT e.taxonomia_item_id, e.cargo_edital_id, tn.no_id, 'topico' AS origem_map
    FROM expansao_cargos e
    INNER JOIN topico_no tn ON tn.topico_id = e.topico_id
    
    UNION ALL
    
    -- Subtópico
    SELECT e.taxonomia_item_id, e.cargo_edital_id, sn.no_id, 'subtopico' AS origem_map
    FROM expansao_cargos e
    INNER JOIN taxonomia_subitens si ON si.taxonomia_item_id = e.taxonomia_item_id
    INNER JOIN subtopico_no sn ON sn.subtopico_id = si.subtopico_id
)
SELECT
    c.slug AS concurso,
    o.sigla AS orgao,
    c.banca,
    c.ano,
    c.status_revisao,
    e.nivel,
    e.tipo_conhecimento,
    e.cargo_numero,
    e.cargo,
    nc.caminho,
    nc.nivel AS no_nivel,
    nc.no_efetivo AS no_id,
    nc.materia_id AS no_materia_id,
    nc.assunto_id AS no_assunto_id,
    e.taxonomia_item_id,
    e.cargo_edital_id,
    m.origem_map
FROM mapeamentos m
INNER JOIN expansao_cargos e ON e.taxonomia_item_id = m.taxonomia_item_id AND e.cargo_edital_id = m.cargo_edital_id
INNER JOIN vw_no_caminho nc ON nc.id = m.no_id
INNER JOIN concursos c ON c.id = e.concurso_id
INNER JOIN dim_orgao o ON o.id = c.orgao_id;

-- "O que o edital cobra" (ADR-030): cada linha liga um item do edital ao nó
-- que ele cobra em cada nível, subindo a árvore. O item mapeado para um nó de
-- nível acima soma nesse nível e acima dele, nunca abaixo.
CREATE OR REPLACE VIEW vw_edital_cobra_base AS
SELECT DISTINCT taxonomia_item_id, status_revisao, 'subassunto' AS nivel_alvo, no_id AS alvo_id
FROM vw_arvore_edital_por_cargo
WHERE no_nivel = 'subassunto'
UNION
SELECT DISTINCT taxonomia_item_id, status_revisao, 'assunto', no_assunto_id
FROM vw_arvore_edital_por_cargo
WHERE no_assunto_id IS NOT NULL
UNION
SELECT DISTINCT taxonomia_item_id, status_revisao, 'materia', no_materia_id
FROM vw_arvore_edital_por_cargo;

-- Ocorrência = `taxonomia_itens.id` distinto: o composto e as partes no mesmo
-- item nunca contam 2× no mesmo nó. A variante sem sufixo é a oficial
-- (`status_revisao = 'aprovado'`); `_todas` é para inspeção.
CREATE OR REPLACE VIEW vw_edital_cobra_subassunto_todas AS
SELECT b.alvo_id AS no_id, nc.caminho, count(DISTINCT b.taxonomia_item_id) AS ocorrencias
FROM vw_edital_cobra_base b
INNER JOIN vw_no_caminho nc ON nc.id = b.alvo_id
WHERE b.nivel_alvo = 'subassunto'
GROUP BY b.alvo_id, nc.caminho;

CREATE OR REPLACE VIEW vw_edital_cobra_subassunto AS
SELECT b.alvo_id AS no_id, nc.caminho, count(DISTINCT b.taxonomia_item_id) AS ocorrencias
FROM vw_edital_cobra_base b
INNER JOIN vw_no_caminho nc ON nc.id = b.alvo_id
WHERE b.nivel_alvo = 'subassunto' AND b.status_revisao = 'aprovado'
GROUP BY b.alvo_id, nc.caminho;

CREATE OR REPLACE VIEW vw_edital_cobra_assunto_todas AS
SELECT b.alvo_id AS no_id, nc.caminho, count(DISTINCT b.taxonomia_item_id) AS ocorrencias
FROM vw_edital_cobra_base b
INNER JOIN vw_no_caminho nc ON nc.id = b.alvo_id
WHERE b.nivel_alvo = 'assunto'
GROUP BY b.alvo_id, nc.caminho;

CREATE OR REPLACE VIEW vw_edital_cobra_assunto AS
SELECT b.alvo_id AS no_id, nc.caminho, count(DISTINCT b.taxonomia_item_id) AS ocorrencias
FROM vw_edital_cobra_base b
INNER JOIN vw_no_caminho nc ON nc.id = b.alvo_id
WHERE b.nivel_alvo = 'assunto' AND b.status_revisao = 'aprovado'
GROUP BY b.alvo_id, nc.caminho;

CREATE OR REPLACE VIEW vw_edital_cobra_materia_todas AS
SELECT b.alvo_id AS no_id, nc.caminho, count(DISTINCT b.taxonomia_item_id) AS ocorrencias
FROM vw_edital_cobra_base b
INNER JOIN vw_no_caminho nc ON nc.id = b.alvo_id
WHERE b.nivel_alvo = 'materia'
GROUP BY b.alvo_id, nc.caminho;

CREATE OR REPLACE VIEW vw_edital_cobra_materia AS
SELECT b.alvo_id AS no_id, nc.caminho, count(DISTINCT b.taxonomia_item_id) AS ocorrencias
FROM vw_edital_cobra_base b
INNER JOIN vw_no_caminho nc ON nc.id = b.alvo_id
WHERE b.nivel_alvo = 'materia' AND b.status_revisao = 'aprovado'
GROUP BY b.alvo_id, nc.caminho;

-- Incidência de tópico entre concursos, incluindo os ainda pendentes de
-- revisão (para inspecionar o piloto).
CREATE OR REPLACE VIEW vw_incidencia_topico_todas AS
SELECT
    materia,
    topico,
    ano,
    nivel,
    tipo_conhecimento,
    count(DISTINCT concurso) AS concursos,
    count(*) AS ocorrencias,
    array_agg(DISTINCT concurso ORDER BY concurso) AS lista_concursos
FROM vw_taxonomia_detalhe
GROUP BY materia, topico, ano, nivel, tipo_conhecimento;

-- Estatística "oficial": só concursos com revisão humana aprovada.
CREATE OR REPLACE VIEW vw_incidencia_topico AS
SELECT
    materia,
    topico,
    ano,
    nivel,
    tipo_conhecimento,
    count(DISTINCT concurso) AS concursos,
    count(*) AS ocorrencias,
    array_agg(DISTINCT concurso ORDER BY concurso) AS lista_concursos
FROM vw_taxonomia_detalhe
WHERE status_revisao = 'aprovado'
GROUP BY materia, topico, ano, nivel, tipo_conhecimento;
