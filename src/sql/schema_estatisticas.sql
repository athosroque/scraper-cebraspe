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

-- Extensões ------------------------------------------------------------------

-- `unaccent`: palavra-chave da listagem do site sem diferenciar acentos (5H.4).
-- Sempre em `public` (não no schema temporário dos testes), onde a role de
-- leitura do site a enxerga pelo `search_path` padrão. Extensão "trusted" no
-- PG16: o dono do banco cria sem superusuário.
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA public;

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
-- `nome_de_cargo`: derivado na carga via bool_and(materia_origem = 'cargo') (Etapa 5E).
CREATE TABLE IF NOT EXISTS dim_materia (
    id SERIAL PRIMARY KEY,
    chave TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    nocoes BOOLEAN NOT NULL DEFAULT false,
    nome_de_cargo BOOLEAN NOT NULL DEFAULT false
);

ALTER TABLE dim_materia ADD COLUMN IF NOT EXISTS nome_de_cargo BOOLEAN NOT NULL DEFAULT false;

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
    materia_origem TEXT CHECK (materia_origem IN ('cabecalho', 'prefixo', 'cargo')),
    UNIQUE (concurso_id, chunk_index, topico_ordem)
);

-- Migração idempotente para bancos existentes antes da introdução da coluna:
ALTER TABLE taxonomia_itens ADD COLUMN IF NOT EXISTS cargos_restritos INTEGER[];
ALTER TABLE taxonomia_itens ADD COLUMN IF NOT EXISTS materia_origem TEXT
    CHECK (materia_origem IN ('cabecalho', 'prefixo', 'cargo'));
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

CREATE INDEX IF NOT EXISTS idx_provas_cargos_cargo ON provas_cargos (cargo_edital_id);

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

DROP VIEW IF EXISTS vw_discursivas CASCADE;
DROP VIEW IF EXISTS vw_peso_materia_cargo CASCADE;
DROP VIEW IF EXISTS vw_edital_vs_prova CASCADE;
DROP VIEW IF EXISTS vw_prova_cobra_no CASCADE;
DROP FUNCTION IF EXISTS fn_prova_cobra CASCADE;
DROP VIEW IF EXISTS vw_comparativo_nivel CASCADE;
DROP VIEW IF EXISTS vw_certo_errado_por_no CASCADE;
DROP VIEW IF EXISTS vw_prova_cobra_materia CASCADE;
DROP VIEW IF EXISTS vw_prova_cobra_assunto CASCADE;
DROP VIEW IF EXISTS vw_prova_cobra_subassunto CASCADE;
DROP VIEW IF EXISTS vw_prova_cobra_base CASCADE;
DROP VIEW IF EXISTS vw_questoes CASCADE;
DROP VIEW IF EXISTS vw_questoes_contexto CASCADE;
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

-- Questões e Prova × Árvore (Etapa 5E, ADR-032) -----------------------------

-- Contexto plano de cada aplicação de questão por cargo.
-- Grão: 1 linha por (questão × cargo). Caderno básico expandido para os N cargos
-- que cobre via provas_cargos.
-- Chave canônica (decisão 8): `questao_canonica_id` identifica enunciados
-- idênticos aplicados em cadernos diferentes do mesmo concurso.
CREATE OR REPLACE VIEW vw_questoes_contexto AS
WITH canonica AS (
    SELECT
        q.id AS questao_id,
        min(q.id) OVER (
            -- Texto-base comparado sem espaços/quebras: o mesmo texto em
            -- cadernos de layout diferente pode quebrar parágrafo (ou a
            -- linha da fonte) em lugar diferente (5G.1).
            PARTITION BY p.concurso_id, md5(q.enunciado),
                COALESCE(md5(regexp_replace(tb.texto, '\s+', ' ', 'g')), ''),
                q.gabarito
        ) AS questao_canonica_id
    FROM questoes q
    JOIN provas p ON p.id = q.prova_id
    LEFT JOIN textos_base tb ON tb.id = q.texto_base_id
)
SELECT
    q.id AS questao_id,
    can.questao_canonica_id,
    (c.slug || '|' || p.codigo_caderno || '|' || q.numero) AS questao_chave,
    q.numero,
    p.codigo_caderno,
    p.tipo AS prova_tipo,
    CASE
        WHEN p.tipo = 'objetiva_basica' THEN 'basico'
        WHEN p.tipo = 'objetiva_especifica' THEN 'especifico'
        ELSE p.tipo
    END AS tipo_conhecimento,
    c.slug AS concurso,
    o.sigla AS orgao,
    c.banca,
    c.ano,
    ce.id AS cargo_edital_id,
    ce.numero AS cargo_numero,
    ce.nome AS cargo,
    ce.nivel,
    q.gabarito,
    q.anulada,
    q.utilizavel,
    c.status_revisao
FROM questoes q
JOIN canonica can ON can.questao_id = q.id
JOIN provas p ON p.id = q.prova_id
JOIN concursos c ON c.id = p.concurso_id
JOIN dim_orgao o ON o.id = c.orgao_id
JOIN provas_cargos pc ON pc.prova_id = p.id
JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id;

-- Base plana de busca do site (Etapa 5F.1).
-- Grão: 1 linha por (questão × cargo × nó aprovado). O site filtra por dimensões
-- e agrupa por `questao_id`.
CREATE OR REPLACE VIEW vw_questoes AS
-- `nome_de_cargo` aqui é da disciplina (nó): o nó ainda tem o nome de uma
-- matéria-cargo do edital (nó não curado). Depois que o dono renomeia o nó
-- para a área (Estatística, Psicologia...), o card e os filtros mostram o
-- nome do nó, nunca "Conhecimentos específicos — <nome do nó>" (ADR-030).
WITH materia_info AS (
    SELECT mn.no_id,
           bool_or(m.nome_de_cargo AND upper(m.nome) = upper(na.nome)) AS nome_de_cargo,
           bool_or(m.nocoes) AS nocoes
    FROM materia_no mn
    JOIN dim_materia m ON m.id = mn.materia_id
    JOIN no_arvore na ON na.id = mn.no_id
    GROUP BY mn.no_id
)
SELECT
    ctx.questao_id,
    ctx.questao_canonica_id,
    ctx.questao_chave,
    ctx.numero,
    ctx.codigo_caderno,
    ctx.prova_tipo,
    ctx.tipo_conhecimento,
    ctx.concurso,
    ctx.orgao,
    ctx.banca,
    ctx.ano,
    ctx.cargo_edital_id,
    ctx.cargo_numero,
    ctx.cargo,
    ctx.nivel,
    ctx.gabarito,
    ctx.anulada,
    ctx.utilizavel,
    ctx.status_revisao,
    q.enunciado,
    q.secao,
    -- Figuras do texto-base (tabelas do grupo) antes das do item: o card só
    -- lê esta coluna, e `tem_figuras` já considerava as duas.
    COALESCE(tb.figuras, '[]'::jsonb) || q.figuras AS figuras,
    q.texto_base_id,
    tb.texto AS texto_base_texto,
    (q.texto_base_id IS NOT NULL) AS tem_texto_base,
    (jsonb_array_length(q.figuras) > 0 OR (tb.id IS NOT NULL AND jsonb_array_length(tb.figuras) > 0)) AS tem_figuras,
    qn.no_id,
    qn.no_caminho,
    qn.no_nivel,
    qn.no_nome,
    qn.materia_id,
    qn.assunto_id,
    qn.papel,
    qn.confianca,
    qn.fora_do_edital,
    COALESCE(mi.nocoes, false) AS nocoes,
    COALESCE(mi.nome_de_cargo, false) AS nome_de_cargo,
    CASE
        WHEN COALESCE(mi.nome_de_cargo, false) THEN 'Conhecimentos específicos — ' || ctx.cargo
        ELSE na_mat.nome
    END AS rotulo_materia
FROM vw_questoes_contexto ctx
JOIN questoes q ON q.id = ctx.questao_id
LEFT JOIN textos_base tb ON tb.id = q.texto_base_id
JOIN vw_questao_no qn ON qn.questao_id = ctx.questao_id
LEFT JOIN materia_info mi ON mi.no_id = qn.materia_id
LEFT JOIN no_arvore na_mat ON na_mat.id = qn.materia_id;

-- Base de incidência de questões subindo a árvore (análoga a vw_edital_cobra_base).
-- Grão: 1 linha por (questão × cargo × nível_alvo × nó_alvo).
-- Regra de subida:
-- - Questão em subassunto gera subassunto, assunto e matéria.
-- - Questão em assunto gera assunto e matéria (nunca subassunto).
-- - Questão em matéria gera matéria (nunca assunto nem subassunto).
-- Só entram questões utilizáveis de concursos com revisão humana aprovada.
CREATE OR REPLACE VIEW vw_prova_cobra_base AS
WITH par AS MATERIALIZED (
    -- (questão × cargo × nó) do universo oficial, calculado uma vez só.
    SELECT
        ctx.questao_id, ctx.questao_canonica_id, ctx.concurso, ctx.orgao,
        ctx.banca, ctx.ano, ctx.cargo_edital_id, ctx.cargo_numero, ctx.cargo,
        ctx.nivel, ctx.tipo_conhecimento, ctx.anulada, qn.papel,
        qn.no_id, qn.no_nivel, qn.materia_id, qn.assunto_id
    FROM vw_questoes_contexto ctx
    JOIN vw_questao_no qn ON qn.questao_id = ctx.questao_id
    WHERE ctx.utilizavel IS TRUE
      AND ctx.status_revisao = 'aprovado'
),
subida AS (
    SELECT par.*, 'subassunto'::text AS nivel_alvo, no_id AS alvo_id
    FROM par WHERE no_nivel = 'subassunto'
    UNION ALL
    -- Questão em subassunto sobe para o assunto; questão em assunto fica nele.
    SELECT par.*, 'assunto'::text,
           CASE WHEN no_nivel = 'subassunto' THEN assunto_id ELSE no_id END
    FROM par
    WHERE no_nivel IN ('subassunto', 'assunto')
      AND (CASE WHEN no_nivel = 'subassunto' THEN assunto_id ELSE no_id END) IS NOT NULL
    UNION ALL
    SELECT par.*, 'materia'::text, materia_id
    FROM par WHERE materia_id IS NOT NULL
)
SELECT
    questao_id,
    questao_canonica_id,
    concurso,
    orgao,
    banca,
    ano,
    cargo_edital_id,
    cargo_numero,
    cargo,
    nivel,
    tipo_conhecimento,
    anulada,
    CASE WHEN bool_or(papel = 'principal') THEN 'principal' ELSE 'secundario' END AS papel,
    materia_id AS no_materia_id,
    assunto_id AS no_assunto_id,
    nivel_alvo,
    alvo_id
FROM subida
GROUP BY
    questao_id, questao_canonica_id, concurso, orgao, banca, ano,
    cargo_edital_id, cargo_numero, cargo, nivel, tipo_conhecimento,
    anulada, materia_id, assunto_id, nivel_alvo, alvo_id;

-- "O que mais cai" com filtros (API do site, Etapa 5F).
-- As contagens são `count(DISTINCT questao_canonica_id)` e NÃO se somam entre
-- linhas: a mesma questão do caderno básico está em N cargos. Toda agregação
-- com filtro (vários cargos, um nível, um órgão...) passa por esta função,
-- que filtra a base primeiro e conta depois. Parâmetro NULL = sem filtro;
-- `p_nivel_alvo` NULL devolve os três níveis.
-- Denominadores:
-- - `pct_do_universo` = questões válidas distintas do universo filtrado.
-- - `pct_medio_por_concurso` = média, com peso igual por concurso, do % do nó
--   dentro da matéria no concurso (subassunto/assunto) ou dentro do concurso
--   (matéria). Entra na média todo concurso com questão na matéria (ou com
--   questão, para matéria); quem não tem questão no nó entra com 0%.
-- Anuladas ficam fora de `questoes` e de todo denominador (só em `anuladas`).
-- A soma dos percentuais pode passar de 100%: a questão com 2 nós conta nos dois.
CREATE OR REPLACE FUNCTION fn_prova_cobra(
    p_nivel_alvo TEXT DEFAULT NULL,
    p_banca TEXT DEFAULT NULL,
    p_orgao TEXT DEFAULT NULL,
    p_ano INTEGER DEFAULT NULL,
    p_concurso TEXT DEFAULT NULL,
    p_cargo_numero INTEGER DEFAULT NULL,
    p_nivel TEXT DEFAULT NULL,
    p_tipo_conhecimento TEXT DEFAULT NULL
)
RETURNS TABLE (
    nivel_alvo TEXT,
    no_id TEXT,
    caminho TEXT,
    no_nome TEXT,
    materia_id TEXT,
    assunto_id TEXT,
    questoes BIGINT,
    anuladas BIGINT,
    so_principal BIGINT,
    total_universo BIGINT,
    pct_do_universo NUMERIC,
    pct_medio_por_concurso NUMERIC
)
LANGUAGE sql STABLE AS $$
WITH b AS MATERIALIZED (
    SELECT *
    FROM vw_prova_cobra_base v
    WHERE (p_banca IS NULL OR v.banca = p_banca)
      AND (p_orgao IS NULL OR v.orgao = p_orgao)
      AND (p_ano IS NULL OR v.ano = p_ano)
      AND (p_concurso IS NULL OR v.concurso = p_concurso)
      AND (p_cargo_numero IS NULL OR v.cargo_numero = p_cargo_numero)
      AND (p_nivel IS NULL OR v.nivel = p_nivel)
      AND (p_tipo_conhecimento IS NULL OR v.tipo_conhecimento = p_tipo_conhecimento)
),
nc AS MATERIALIZED (
    -- Sem materializar, o planner repete a CTE recursiva por linha.
    SELECT * FROM vw_no_caminho
),
universo AS (
    SELECT count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) AS total
    FROM b
),
alvo AS (
    SELECT * FROM b WHERE p_nivel_alvo IS NULL OR b.nivel_alvo = p_nivel_alvo
),
-- Escopo do denominador por concurso: a matéria (subassunto/assunto) ou o
-- concurso inteiro (matéria, escopo = '').
den AS (
    SELECT concurso, no_materia_id AS escopo,
           count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) AS total
    FROM b
    GROUP BY concurso, no_materia_id
    HAVING count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) > 0
    UNION ALL
    SELECT concurso, '' AS escopo,
           count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada)
    FROM b
    GROUP BY concurso
    HAVING count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) > 0
),
elegiveis AS (
    SELECT escopo, count(*) AS n_concursos FROM den GROUP BY escopo
),
por_concurso AS (
    SELECT a.nivel_alvo, a.alvo_id,
           CASE WHEN a.nivel_alvo = 'materia' THEN '' ELSE a.no_materia_id END AS escopo,
           count(DISTINCT a.questao_canonica_id) FILTER (WHERE NOT a.anulada) * 100.0
               / d.total AS pct
    FROM alvo a
    JOIN den d ON d.concurso = a.concurso
              AND d.escopo = CASE WHEN a.nivel_alvo = 'materia' THEN '' ELSE a.no_materia_id END
    GROUP BY a.nivel_alvo, a.alvo_id, a.no_materia_id, d.total
),
media AS (
    SELECT p.nivel_alvo, p.alvo_id, round(sum(p.pct) / e.n_concursos, 2) AS pct_medio
    FROM por_concurso p
    JOIN elegiveis e ON e.escopo = p.escopo
    GROUP BY p.nivel_alvo, p.alvo_id, e.n_concursos
),
contagem AS (
    SELECT nivel_alvo, alvo_id,
           count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) AS questoes,
           count(DISTINCT questao_canonica_id) FILTER (WHERE anulada) AS anuladas,
           count(DISTINCT questao_canonica_id)
               FILTER (WHERE NOT anulada AND papel = 'principal') AS so_principal
    FROM alvo
    GROUP BY nivel_alvo, alvo_id
)
SELECT
    c.nivel_alvo,
    c.alvo_id,
    nc.caminho,
    nc.nome,
    nc.materia_id,
    CASE WHEN c.nivel_alvo = 'materia' THEN NULL ELSE nc.assunto_id END,
    c.questoes,
    c.anuladas,
    c.so_principal,
    u.total,
    round(c.questoes * 100.0 / NULLIF(u.total, 0), 2),
    COALESCE(m.pct_medio, 0)
FROM contagem c
CROSS JOIN universo u
JOIN nc ON nc.id = c.alvo_id
LEFT JOIN media m ON m.nivel_alvo = c.nivel_alvo AND m.alvo_id = c.alvo_id
$$;

-- "O que mais cai" no grão máximo (concurso × cargo × tipo × nó), para
-- inspeção e para a consulta de um cargo só. NÃO some `questoes` entre
-- linhas (a mesma questão básica está em N cargos) nem reagregue os %:
-- com filtro de vários cargos/níveis, use `fn_prova_cobra`.
-- `pct_do_universo` divide pelo total do cargo naquele tipo de conhecimento
-- (`total_universo`); `pct_medio_por_concurso` é o global de
-- `fn_prova_cobra` sem filtro (igual em todas as linhas do nó).
CREATE OR REPLACE VIEW vw_prova_cobra_no AS
WITH b AS MATERIALIZED (
    SELECT * FROM vw_prova_cobra_base
),
totais_cargo AS (
    SELECT concurso, cargo_edital_id, tipo_conhecimento,
           count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) AS total_universo
    FROM b
    GROUP BY concurso, cargo_edital_id, tipo_conhecimento
),
contagem AS (
    SELECT
        nivel_alvo, alvo_id, banca, orgao, ano, concurso, cargo_edital_id,
        cargo_numero, cargo, nivel, tipo_conhecimento,
        count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) AS questoes,
        count(DISTINCT questao_canonica_id) FILTER (WHERE anulada) AS anuladas,
        count(DISTINCT questao_canonica_id)
            FILTER (WHERE NOT anulada AND papel = 'principal') AS so_principal
    FROM b
    GROUP BY nivel_alvo, alvo_id, banca, orgao, ano, concurso, cargo_edital_id,
             cargo_numero, cargo, nivel, tipo_conhecimento
)
SELECT
    c.nivel_alvo,
    c.alvo_id AS no_id,
    g.caminho,
    g.no_nome,
    g.materia_id,
    g.assunto_id,
    c.banca,
    c.orgao,
    c.ano,
    c.concurso,
    c.cargo_numero,
    c.cargo,
    c.nivel,
    c.tipo_conhecimento,
    c.questoes,
    c.anuladas,
    c.so_principal,
    t.total_universo,
    round(c.questoes * 100.0 / NULLIF(t.total_universo, 0), 2) AS pct_do_universo,
    g.pct_medio_por_concurso
FROM contagem c
JOIN totais_cargo t ON t.concurso = c.concurso
                   AND t.cargo_edital_id = c.cargo_edital_id
                   AND t.tipo_conhecimento = c.tipo_conhecimento
JOIN fn_prova_cobra() g ON g.nivel_alvo = c.nivel_alvo AND g.no_id = c.alvo_id;

-- Atalhos por nível (mesmas regras e ressalvas de `vw_prova_cobra_no`).
CREATE OR REPLACE VIEW vw_prova_cobra_subassunto AS
SELECT * FROM vw_prova_cobra_no WHERE nivel_alvo = 'subassunto';

CREATE OR REPLACE VIEW vw_prova_cobra_assunto AS
SELECT * FROM vw_prova_cobra_no WHERE nivel_alvo = 'assunto';

CREATE OR REPLACE VIEW vw_prova_cobra_materia AS
SELECT * FROM vw_prova_cobra_no WHERE nivel_alvo = 'materia';

-- Proporção de itens Certo / Errado e taxa de anulação por nó.
-- Percentual de C e E calculado sobre o total de itens válidos (não anulados).
-- Percentual de anulação calculado sobre o total geral de itens.
CREATE OR REPLACE VIEW vw_certo_errado_por_no AS
SELECT
    b.alvo_id AS no_id,
    nc.caminho,
    nc.nivel AS no_nivel,
    count(DISTINCT b.questao_canonica_id) AS total_itens,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND q.gabarito = 'C') AS certos,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND q.gabarito = 'E') AS errados,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE b.anulada) AS anuladas,
    round(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND q.gabarito = 'C') * 100.0 / NULLIF(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada), 0), 2) AS pct_certos,
    round(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND q.gabarito = 'E') * 100.0 / NULLIF(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada), 0), 2) AS pct_errados,
    round(count(DISTINCT b.questao_canonica_id) FILTER (WHERE b.anulada) * 100.0 / NULLIF(count(DISTINCT b.questao_canonica_id), 0), 2) AS pct_anuladas
FROM vw_prova_cobra_base b
JOIN questoes q ON q.id = b.questao_id
JOIN vw_no_caminho nc ON nc.id = b.alvo_id
GROUP BY b.alvo_id, nc.caminho, nc.nivel;

-- Comparativo Médio × Superior por nó.
-- Permite ver a diferença de incidência de um nó entre provas de nível médio e superior.
CREATE OR REPLACE VIEW vw_comparativo_nivel AS
WITH totais_universo AS (
    SELECT
        count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada AND nivel = 'medio') AS total_medio,
        count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada AND nivel = 'superior') AS total_superior
    FROM vw_prova_cobra_base
)
SELECT
    b.alvo_id AS no_id,
    nc.caminho,
    nc.nivel AS no_nivel,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'medio') AS questoes_medio,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'superior') AS questoes_superior,
    round(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'medio') * 100.0 / NULLIF(t.total_medio, 0), 2) AS pct_medio,
    round(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'superior') * 100.0 / NULLIF(t.total_superior, 0), 2) AS pct_superior,
    round(
        COALESCE(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'superior') * 100.0 / NULLIF(t.total_superior, 0), 0) -
        COALESCE(count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'medio') * 100.0 / NULLIF(t.total_medio, 0), 0),
        2
    ) AS diferenca_pct
FROM vw_prova_cobra_base b
JOIN vw_no_caminho nc ON nc.id = b.alvo_id
CROSS JOIN totais_universo t
GROUP BY b.alvo_id, nc.caminho, nc.nivel, t.total_medio, t.total_superior
HAVING count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'medio') > 0
    OR count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada AND b.nivel = 'superior') > 0;

-- Cruzamento Edital × Prova por (concurso × cargo × nó).
-- Compara a cobertura do edital com as questões efetivamente cobradas na prova.
-- Respeita a regra de cobertura descendente (Decisão 5, ADR-032):
-- - Um item previsto no edital em nó X cobre X e todos os descendentes de X.
-- - 'cobrado_no_edital': previsto no edital (direto ou via ancestral) e cobrado na prova.
-- - 'no_edital_nunca_cobrado': previsto no edital, mas com zero questões cobradas nele ou em seus descendentes.
-- - 'cobrado_fora_do_edital': cobrado na prova, porém sem ancestral-ou-igual previsto no edital daquele cargo.
-- Na prática o item de edital aponta também para o nó da matéria (materia_no),
-- então "fora" aparece quando a matéria nem consta no edital do cargo, ou
-- quando o item não tem matéria mapeada.
-- Níveis misturados: a questão classificada direto num assunto não desce para
-- o subassunto previsto abaixo dele, que pode aparecer como nunca cobrado.
CREATE OR REPLACE VIEW vw_edital_vs_prova AS
WITH edital_base AS (
    SELECT
        concurso, orgao, banca, ano, cargo_edital_id, cargo_numero, cargo, nivel,
        no_id, no_nivel, no_assunto_id, no_materia_id, taxonomia_item_id
    FROM vw_arvore_edital_por_cargo
    WHERE status_revisao = 'aprovado'
),
-- Nós que o edital do cargo aponta diretamente. A cobertura descendente
-- procura o nó da questão ou um ancestral dele SÓ aqui: a subida abaixo
-- (edital_nos) põe o assunto/matéria-pai de todo item previsto, e usá-la
-- faria um subassunto irmão, nunca previsto, parecer coberto.
edital_direto AS MATERIALIZED (
    SELECT DISTINCT cargo_edital_id, no_id FROM edital_base
),
edital_subida AS (
    SELECT concurso, orgao, banca, ano, cargo_edital_id, cargo_numero, cargo, nivel,
           'subassunto'::text AS no_nivel, no_id, taxonomia_item_id
    FROM edital_base
    WHERE no_nivel = 'subassunto'

    UNION

    SELECT concurso, orgao, banca, ano, cargo_edital_id, cargo_numero, cargo, nivel,
           'assunto'::text AS no_nivel, no_assunto_id AS no_id, taxonomia_item_id
    FROM edital_base
    WHERE no_assunto_id IS NOT NULL

    UNION

    SELECT concurso, orgao, banca, ano, cargo_edital_id, cargo_numero, cargo, nivel,
           'materia'::text AS no_nivel, no_materia_id AS no_id, taxonomia_item_id
    FROM edital_base
    WHERE no_materia_id IS NOT NULL
),
edital_nos AS (
    SELECT
        concurso, orgao, banca, ano,
        cargo_edital_id, cargo_numero, cargo, nivel,
        no_id, no_nivel,
        count(DISTINCT taxonomia_item_id) AS previsao
    FROM edital_subida
    GROUP BY
        concurso, orgao, banca, ano,
        cargo_edital_id, cargo_numero, cargo, nivel,
        no_id, no_nivel
),
prova_nos AS (
    SELECT
        b.concurso, b.orgao, b.banca, b.ano,
        b.cargo_edital_id, b.cargo_numero, b.cargo, b.nivel,
        b.alvo_id AS no_id,
        b.nivel_alvo AS no_nivel,
        count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada) AS questoes
    FROM vw_prova_cobra_base b
    GROUP BY
        b.concurso, b.orgao, b.banca, b.ano,
        b.cargo_edital_id, b.cargo_numero, b.cargo, b.nivel,
        b.alvo_id, b.nivel_alvo
),
combinado AS (
    SELECT
        COALESCE(e.concurso, p.concurso) AS concurso,
        COALESCE(e.orgao, p.orgao) AS orgao,
        COALESCE(e.banca, p.banca) AS banca,
        COALESCE(e.ano, p.ano) AS ano,
        COALESCE(e.cargo_edital_id, p.cargo_edital_id) AS cargo_edital_id,
        COALESCE(e.cargo_numero, p.cargo_numero) AS cargo_numero,
        COALESCE(e.cargo, p.cargo) AS cargo,
        COALESCE(e.nivel, p.nivel) AS nivel,
        COALESCE(e.no_id, p.no_id) AS no_id,
        COALESCE(e.no_nivel, p.no_nivel) AS no_nivel,
        (COALESCE(e.previsao, 0) > 0) AS no_edital_direto,
        COALESCE(e.previsao, 0) AS previsao,
        COALESCE(p.questoes, 0) AS questoes
    FROM edital_nos e
    FULL OUTER JOIN prova_nos p ON p.cargo_edital_id = e.cargo_edital_id
                               AND p.no_nivel = e.no_nivel
                               AND p.no_id = e.no_id
)
SELECT
    c.concurso,
    c.orgao,
    c.banca,
    c.ano,
    c.cargo_edital_id,
    c.cargo_numero,
    c.cargo,
    c.nivel,
    c.no_id,
    nc.nome AS no_nome,
    c.no_nivel,
    nc.caminho,
    nc.materia_id,
    nc.assunto_id,
    (c.no_edital_direto OR EXISTS (
        SELECT 1 FROM edital_direto ed
        WHERE ed.cargo_edital_id = c.cargo_edital_id
          AND ed.no_id IN (c.no_id, nc.assunto_id, nc.materia_id)
    )) AS no_edital,
    c.previsao,
    c.questoes,
    CASE
        WHEN c.previsao > 0 THEN round(c.questoes * 1.0 / c.previsao, 2)
        ELSE NULL
    END AS razao,
    CASE
        WHEN c.previsao > 0 AND c.questoes > 0 THEN 'cobrado_no_edital'
        WHEN c.previsao > 0 AND c.questoes = 0 THEN 'no_edital_nunca_cobrado'
        WHEN c.previsao = 0 AND c.questoes > 0 THEN
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM edital_direto ed
                    WHERE ed.cargo_edital_id = c.cargo_edital_id
                      AND ed.no_id IN (c.no_id, nc.assunto_id, nc.materia_id)
                ) THEN 'cobrado_no_edital'
                ELSE 'cobrado_fora_do_edital'
            END
    END AS situacao
FROM combinado c
JOIN vw_no_caminho nc ON nc.id = c.no_id;

-- Peso percentual de cada matéria por cargo (a prova do cargo = básico + específico).
-- A questão com nós em 2 matérias conta nas duas: a soma de `pct_da_prova`
-- do cargo pode passar de 100%.
-- Trata matérias com nome de cargo (`nome_de_cargo = true`) como
-- "Conhecimentos específicos — <cargo>" para clareza na visualização do candidato.
CREATE OR REPLACE VIEW vw_peso_materia_cargo AS
WITH totais_cargo AS (
    SELECT
        b.concurso,
        b.cargo_edital_id,
        count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada) AS total_cargo
    FROM vw_prova_cobra_base b
    WHERE b.nivel_alvo = 'materia'
    GROUP BY b.concurso, b.cargo_edital_id
),
-- Por concurso: um nó pode juntar a matéria-cargo de um concurso com a
-- matéria nomeada de outro (TÉCNICO EM COMUNICAÇÃO SOCIAL da PF fundido em
-- COMUNICAÇÃO SOCIAL do STM, ADR-030). Agregar só por nó rotularia o cargo
-- do STM como "Conhecimentos específicos".
materia_info AS (
    SELECT mn.no_id, c.slug AS concurso, bool_or(m.nome_de_cargo) AS nome_de_cargo
    FROM materia_no mn
    JOIN dim_materia m ON m.id = mn.materia_id
    JOIN taxonomia_itens ti ON ti.materia_id = m.id
    JOIN concursos c ON c.id = ti.concurso_id
    GROUP BY mn.no_id, c.slug
)
SELECT
    b.concurso,
    b.orgao,
    b.banca,
    b.ano,
    b.cargo_edital_id,
    b.cargo_numero,
    b.cargo,
    b.nivel,
    b.alvo_id AS materia_id,
    nc.nome AS materia_nome,
    COALESCE(mi.nome_de_cargo, false) AS nome_de_cargo,
    CASE
        WHEN COALESCE(mi.nome_de_cargo, false) THEN 'Conhecimentos específicos — ' || b.cargo
        ELSE nc.nome
    END AS rotulo_materia,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada) AS questoes,
    count(DISTINCT b.questao_canonica_id) FILTER (WHERE b.anulada) AS anuladas,
    tc.total_cargo,
    round(
        count(DISTINCT b.questao_canonica_id) FILTER (WHERE NOT b.anulada) * 100.0 / NULLIF(tc.total_cargo, 0),
        2
    ) AS pct_da_prova
FROM vw_prova_cobra_base b
JOIN vw_no_caminho nc ON nc.id = b.alvo_id
JOIN totais_cargo tc ON tc.concurso = b.concurso AND tc.cargo_edital_id = b.cargo_edital_id
LEFT JOIN materia_info mi ON mi.no_id = b.alvo_id AND mi.concurso = b.concurso
WHERE b.nivel_alvo = 'materia'
GROUP BY
    b.concurso, b.orgao, b.banca, b.ano,
    b.cargo_edital_id, b.cargo_numero, b.cargo, b.nivel,
    b.alvo_id, nc.nome, mi.nome_de_cargo, tc.total_cargo;

-- Discursivas analíticas ligadas aos nós da árvore mestre (Etapa 5D/5E, ADR-032).
-- Exibe tema, título, quesitos, gabarito/padrão de resposta e matérias associadas.
-- Discursivas NÃO entram nas contagens de questões das views de incidência objetiva.
CREATE OR REPLACE VIEW vw_discursivas AS
-- Por concurso, como em `vw_peso_materia_cargo` (ADR-030).
WITH materia_info AS (
    SELECT mn.no_id, c.slug AS concurso, bool_or(m.nome_de_cargo) AS nome_de_cargo
    FROM materia_no mn
    JOIN dim_materia m ON m.id = mn.materia_id
    JOIN taxonomia_itens ti ON ti.materia_id = m.id
    JOIN concursos c ON c.id = ti.concurso_id
    GROUP BY mn.no_id, c.slug
)
SELECT
    d.id AS discursiva_id,
    c.slug AS concurso,
    o.sigla AS orgao,
    c.banca,
    c.ano,
    ce.id AS cargo_edital_id,
    ce.numero AS cargo_numero,
    ce.nome AS cargo,
    ce.nivel,
    d.numero,
    d.titulo,
    d.tema,
    d.enunciado,
    d.quesitos,
    d.padrao_resposta,
    nc.no_efetivo AS no_id,
    nc.nome AS no_nome,
    nc.nivel AS no_nivel,
    nc.caminho,
    nc.materia_id,
    nc.assunto_id,
    dn.papel,
    dn.confianca,
    dn.fora_do_edital,
    COALESCE(mi.nome_de_cargo, false) AS nome_de_cargo,
    CASE
        WHEN COALESCE(mi.nome_de_cargo, false) THEN 'Conhecimentos específicos — ' || ce.nome
        ELSE na_mat.nome
    END AS rotulo_materia,
    c.status_revisao
FROM discursivas d
JOIN provas p ON p.id = d.prova_id
JOIN concursos c ON c.id = p.concurso_id
JOIN dim_orgao o ON o.id = c.orgao_id
JOIN provas_cargos pc ON pc.prova_id = p.id
JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id
JOIN discursiva_no dn ON dn.discursiva_id = d.id
JOIN vw_no_caminho nc ON nc.id = dn.no_id
LEFT JOIN materia_info mi ON mi.no_id = nc.materia_id AND mi.concurso = c.slug
LEFT JOIN no_arvore na_mat ON na_mat.id = nc.materia_id
WHERE dn.status = 'aprovado' AND c.status_revisao = 'aprovado';

-- Tabelas do Inventário (Etapa 8.0) -------------------------------------------

CREATE TABLE IF NOT EXISTS inv_concurso (
    slug TEXT PRIMARY KEY,
    orgao TEXT NOT NULL,
    ano INTEGER,
    situacao TEXT NOT NULL,
    url TEXT NOT NULL,
    data_mapeamento TIMESTAMPTZ,
    qtd_editais INTEGER NOT NULL DEFAULT 0,
    qtd_cadernos INTEGER NOT NULL DEFAULT 0,
    qtd_gabaritos INTEGER NOT NULL DEFAULT 0,
    qtd_padroes INTEGER NOT NULL DEFAULT 0,
    qtd_administrativos INTEGER NOT NULL DEFAULT 0,
    qtd_nao_classificados INTEGER NOT NULL DEFAULT 0,
    formato_provavel TEXT,
    alertas TEXT[] NOT NULL DEFAULT '{}',
    incluir BOOLEAN,
    no_banco BOOLEAN NOT NULL DEFAULT false,
    erro TEXT
);

CREATE TABLE IF NOT EXISTS inv_pdf (
    id SERIAL PRIMARY KEY,
    concurso_slug TEXT NOT NULL REFERENCES inv_concurso(slug) ON DELETE CASCADE,
    url TEXT NOT NULL,
    texto TEXT NOT NULL,
    tipo TEXT NOT NULL,
    versao TEXT,
    UNIQUE (concurso_slug, url)
);

-- Fora do site (ADR-037): incluir=false vem de inventario/exclusoes.json, e o
-- PDF de curso de formação não vai para o lote mesmo em concurso incluído.
ALTER TABLE inv_concurso ADD COLUMN IF NOT EXISTS categoria_exclusao TEXT;
ALTER TABLE inv_concurso ADD COLUMN IF NOT EXISTS motivo_exclusao TEXT;
ALTER TABLE inv_pdf ADD COLUMN IF NOT EXISTS curso_formacao BOOLEAN NOT NULL DEFAULT false;

DROP VIEW IF EXISTS vw_inventario_ano;
CREATE VIEW vw_inventario_ano AS
SELECT
    ano,
    situacao,
    COUNT(*) AS total_concursos,
    COUNT(*) FILTER (WHERE incluir IS FALSE) AS concursos_fora_do_site,
    SUM(qtd_cadernos) AS total_cadernos,
    SUM(qtd_gabaritos) AS total_gabaritos,
    SUM(qtd_padroes) AS total_padroes,
    COUNT(*) FILTER (WHERE formato_provavel = 'me') AS concursos_me,
    COUNT(*) FILTER (WHERE formato_provavel = 'ce') AS concursos_ce,
    COUNT(*) FILTER (WHERE no_banco) AS concursos_no_banco
FROM inv_concurso
GROUP BY ano, situacao
ORDER BY ano DESC NULLS LAST, situacao;
