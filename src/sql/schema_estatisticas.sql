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

-- Camada canônica (Etapa 5B, ADR-029) ------------------------------------------
-- Derivada de `canonico/sinonimos.json`: só grupo `aprovado` é carregado. O ID
-- é o ID estável do JSON (TEXT), para a classificação de questões (5D) poder
-- apontar para ele entre recargas.

CREATE TABLE IF NOT EXISTS materia_canonica (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('regra', 'llm', 'humano'))
);

CREATE TABLE IF NOT EXISTS assunto_canonico (
    id TEXT PRIMARY KEY,
    materia_canonica_id TEXT NOT NULL REFERENCES materia_canonica (id),
    nome TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('regra', 'llm', 'humano'))
);

CREATE TABLE IF NOT EXISTS subassunto_canonico (
    id TEXT PRIMARY KEY,
    assunto_canonico_id TEXT NOT NULL REFERENCES assunto_canonico (id),
    nome TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('regra', 'llm', 'humano'))
);

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
    nocoes BOOLEAN NOT NULL DEFAULT false,
    materia_canonica_id TEXT REFERENCES materia_canonica (id)
);

CREATE TABLE IF NOT EXISTS dim_topico (
    id SERIAL PRIMARY KEY,
    materia_id INTEGER NOT NULL REFERENCES dim_materia (id),
    chave TEXT NOT NULL,
    nome TEXT NOT NULL,
    assunto_canonico_id TEXT REFERENCES assunto_canonico (id),
    UNIQUE (materia_id, chave)
);

CREATE TABLE IF NOT EXISTS dim_subtopico (
    id SERIAL PRIMARY KEY,
    topico_id INTEGER NOT NULL REFERENCES dim_topico (id),
    chave TEXT NOT NULL,
    nome TEXT NOT NULL,
    subassunto_canonico_id TEXT REFERENCES subassunto_canonico (id),
    UNIQUE (topico_id, chave)
);

-- Migração idempotente de bancos criados antes da Etapa 5B:
ALTER TABLE dim_materia ADD COLUMN IF NOT EXISTS nocoes BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE dim_materia ADD COLUMN IF NOT EXISTS materia_canonica_id TEXT REFERENCES materia_canonica (id);
ALTER TABLE dim_topico ADD COLUMN IF NOT EXISTS assunto_canonico_id TEXT REFERENCES assunto_canonico (id);

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

-- Views ----------------------------------------------------------------------

DROP VIEW IF EXISTS vw_incidencia_topico CASCADE;
DROP VIEW IF EXISTS vw_incidencia_topico_todas CASCADE;
DROP VIEW IF EXISTS vw_taxonomia_detalhe CASCADE;
DROP VIEW IF EXISTS vw_subtopico_detalhe CASCADE;

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
    mc.id AS materia_canonica_id,
    mc.nome AS materia_canonica,
    t.nome AS topico,
    t.chave AS topico_chave,
    ac.id AS assunto_canonico_id,
    ac.nome AS assunto_canonico,
    ti.apenas_discursiva,
    (SELECT count(*) FROM taxonomia_subitens AS s WHERE s.taxonomia_item_id = ti.id) AS total_subtopicos
FROM taxonomia_itens AS ti
INNER JOIN concursos AS c ON ti.concurso_id = c.id
INNER JOIN dim_orgao AS o ON c.orgao_id = o.id
INNER JOIN dim_materia AS m ON ti.materia_id = m.id
INNER JOIN dim_topico AS t ON ti.topico_id = t.id
LEFT JOIN materia_canonica AS mc ON m.materia_canonica_id = mc.id
LEFT JOIN assunto_canonico AS ac ON t.assunto_canonico_id = ac.id
LEFT JOIN cargos_editais AS ce ON ti.cargo_edital_id = ce.id;

-- 1 linha por subtópico, com o canônico de cada nível (Etapa 5B).
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
    d.materia_canonica,
    d.topico,
    d.assunto_canonico,
    si.ordem AS subtopico_ordem,
    si.nome AS subtopico,
    st.chave AS subtopico_chave,
    sc.id AS subassunto_canonico_id,
    sc.nome AS subassunto_canonico
FROM taxonomia_subitens AS si
INNER JOIN taxonomia_itens AS ti ON si.taxonomia_item_id = ti.id
INNER JOIN dim_subtopico AS st ON si.subtopico_id = st.id
LEFT JOIN subassunto_canonico AS sc ON st.subassunto_canonico_id = sc.id
INNER JOIN LATERAL (
    SELECT c.slug AS concurso, o.sigla AS orgao, c.ano, c.status_revisao, ti.tipo_conhecimento, ti.nivel,
           ce.numero AS cargo_numero, m.nome AS materia, mc.nome AS materia_canonica, t.nome AS topico,
           ac.nome AS assunto_canonico
    FROM concursos AS c
    INNER JOIN dim_orgao AS o ON c.orgao_id = o.id
    INNER JOIN dim_materia AS m ON m.id = ti.materia_id
    INNER JOIN dim_topico AS t ON t.id = ti.topico_id
    LEFT JOIN materia_canonica AS mc ON m.materia_canonica_id = mc.id
    LEFT JOIN assunto_canonico AS ac ON t.assunto_canonico_id = ac.id
    LEFT JOIN cargos_editais AS ce ON ce.id = ti.cargo_edital_id
    WHERE c.id = ti.concurso_id
) AS d ON true;

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
