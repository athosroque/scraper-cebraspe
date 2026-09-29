"""Aplica `site/sql/app_schema.sql` e cria/atualiza as roles do site.

As senhas vêm do `.env` (SITE_DB_*_PASSWORD) e nunca ficam no SQL versionado.
Conecta como o dono do banco (POSTGRES_USER). Idempotente.

Uso: python site/scripts/aplicar_schema_app.py
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2 import sql

PROJETO_DIR = Path(__file__).resolve().parents[2]
SCHEMA_SQL = PROJETO_DIR / "site" / "sql" / "app_schema.sql"


def _garantir_role(cur, nome: str, senha: str) -> None:
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (nome,))
    comando = (
        "ALTER ROLE {} WITH LOGIN PASSWORD {}"
        if cur.fetchone()
        else "CREATE ROLE {} WITH LOGIN PASSWORD {}"
    )
    cur.execute(sql.SQL(comando).format(sql.Identifier(nome), sql.Literal(senha)))


def main() -> int:
    load_dotenv(PROJETO_DIR / ".env")
    roles = {
        os.getenv("SITE_DB_LEITURA_USER", "site_leitura"): os.getenv(
            "SITE_DB_LEITURA_PASSWORD"
        ),
        os.getenv("SITE_DB_APP_USER", "site_app"): os.getenv("SITE_DB_APP_PASSWORD"),
    }
    vazias = [nome for nome, senha in roles.items() if not senha]
    if vazias:
        print(f"Senha vazia no .env para: {', '.join(vazias)}", file=sys.stderr)
        return 1

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5435"),
        dbname=os.getenv("POSTGRES_DB", "cebraspe"),
        user=os.getenv("POSTGRES_USER", "cebraspe"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    with conn, conn.cursor() as cur:
        for nome, senha in roles.items():
            _garantir_role(cur, nome, senha)
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.close()
    print("Schema app e roles do site aplicados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
