-- Schema `app` e permissões do site (ADR-033). Idempotente.
-- Aplicar com: python site/scripts/aplicar_schema_app.py (lê as senhas do .env)

CREATE SCHEMA IF NOT EXISTS app;

-- 1. Tabelas
CREATE TABLE IF NOT EXISTS app.usuario (
    id bigserial PRIMARY KEY,
    google_sub text UNIQUE NOT NULL,
    email text NOT NULL,
    nome text,
    criado_em timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app.resposta (
    id bigserial PRIMARY KEY,
    usuario_id bigint REFERENCES app.usuario ON DELETE CASCADE,
    questao_chave text NOT NULL,
    resposta char(1) CHECK (resposta IN ('A', 'B', 'C', 'D', 'E')),
    acertou boolean NOT NULL,
    simulado_id bigint NULL,
    respondida_em timestamptz DEFAULT now()
);

DO $$
DECLARE
    r record;
BEGIN
    FOR r IN (
        SELECT conname, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE conrelid = 'app.resposta'::regclass AND contype = 'c'
    ) LOOP
        IF r.def LIKE '%''C''%' AND NOT r.def LIKE '%''A''%' THEN
            EXECUTE 'ALTER TABLE app.resposta DROP CONSTRAINT ' || quote_ident(r.conname);
            EXECUTE 'ALTER TABLE app.resposta ADD CONSTRAINT ' || quote_ident(r.conname) || ' CHECK (resposta IN (''A'', ''B'', ''C'', ''D'', ''E''))';
        END IF;
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS app.simulado (
    id bigserial PRIMARY KEY,
    usuario_id bigint REFERENCES app.usuario ON DELETE CASCADE,
    concurso text NOT NULL,
    cargo_numero integer,
    inicio timestamptz DEFAULT now(),
    fim timestamptz NULL,
    nota numeric(6, 2) NULL
);

-- 5F.8: concurso-alvo do usuário (aditivo; os dois juntos ou nenhum).
ALTER TABLE app.usuario ADD COLUMN IF NOT EXISTS concurso_alvo text;
ALTER TABLE app.usuario ADD COLUMN IF NOT EXISTS cargo_alvo integer;

CREATE INDEX IF NOT EXISTS resposta_usuario_chave_idx
    ON app.resposta (usuario_id, questao_chave, respondida_em DESC);

-- 2. Roles site_leitura/site_app: criadas (com senha do .env) por
--    site/scripts/aplicar_schema_app.py antes deste arquivo. Nunca pôr senha aqui.

-- 3. Permissões de Leitura (site_leitura)
GRANT USAGE ON SCHEMA public TO site_leitura;
GRANT SELECT ON vw_questoes TO site_leitura;
GRANT SELECT ON vw_discursivas TO site_leitura;
GRANT SELECT ON vw_no_caminho TO site_leitura;
GRANT SELECT ON vw_no_apelidos TO site_leitura;
GRANT SELECT ON vw_questao_no TO site_leitura;
GRANT SELECT ON vw_edital_cobra_materia TO site_leitura;
GRANT SELECT ON vw_edital_cobra_assunto TO site_leitura;
GRANT SELECT ON vw_edital_cobra_subassunto TO site_leitura;
GRANT SELECT ON vw_edital_vs_prova TO site_leitura;
GRANT SELECT ON vw_prova_cobra_base TO site_leitura;
GRANT SELECT ON vw_prova_cobra_no TO site_leitura;
GRANT SELECT ON vw_prova_cobra_materia TO site_leitura;
GRANT SELECT ON vw_prova_cobra_assunto TO site_leitura;
GRANT SELECT ON vw_prova_cobra_subassunto TO site_leitura;
GRANT SELECT ON vw_certo_errado_por_no TO site_leitura;
GRANT SELECT ON vw_comparativo_nivel TO site_leitura;
GRANT SELECT ON vw_peso_materia_cargo TO site_leitura;
-- 5F.4: "o que o edital cobra" com filtro de concurso/cargo/nível.
GRANT SELECT ON vw_arvore_edital_por_cargo TO site_leitura;
GRANT EXECUTE ON FUNCTION fn_prova_cobra TO site_leitura;
REVOKE CREATE ON SCHEMA public FROM site_leitura;

-- 4. Permissões de App (site_app)
GRANT USAGE ON SCHEMA app TO site_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO site_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA app TO site_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO site_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO site_app;

GRANT USAGE ON SCHEMA public TO site_app;
GRANT SELECT ON vw_questoes TO site_app;
GRANT SELECT ON vw_no_caminho TO site_app;
REVOKE CREATE ON SCHEMA public FROM site_app;

-- Tabelas usadas no JOIN do link do PDF (detalhe da questão)
GRANT SELECT ON provas TO site_leitura;
GRANT SELECT ON fila_extracao_questoes TO site_leitura;
GRANT SELECT ON concursos TO site_leitura;
