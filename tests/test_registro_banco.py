"""Registro do pipeline com banco: página banco.md e consultas das checagens (Etapa 9/D2, KAN-69).

Marcado como `db` pelo conftest. Só leitura: nenhuma consulta altera o banco.
"""

import psycopg2
import pytest

from scripts.gerar_docs import DESTINO, ler_schema, pagina_banco
from src.registro import REGISTRO
from src.stats_writer import conectar


@pytest.fixture
def conn():
    try:
        conexao = conectar()
    except Exception as erro:  # sem .env, senha ou servidor: pula em vez de falhar
        pytest.skip(f"banco indisponível: {erro}")
    yield conexao
    conexao.close()


def test_pagina_banco_bate_com_o_schema(conn):
    """docs/tecnico/banco.md é o que o schema atual do banco gera."""
    esperado = pagina_banco(*ler_schema(conn))
    arquivo = DESTINO / "banco.md"
    assert arquivo.exists(), "docs/tecnico/banco.md não existe. rode make docs-gerar"
    assert arquivo.read_text(encoding="utf-8") == esperado, (
        "docs/tecnico/banco.md desatualizado com o schema. rode make docs-gerar"
    )


def test_consultas_das_checagens_sao_validas(conn):
    """Toda consulta de checagem de banco passa no EXPLAIN (sem executar)."""
    invalidas = []
    conn.set_session(readonly=True)
    for checagem in REGISTRO.checagens:
        if not checagem.consulta:
            continue
        try:
            with conn.cursor() as cur:
                cur.execute("EXPLAIN " + checagem.consulta)
        except psycopg2.Error as erro:
            invalidas.append(f"{checagem.id}: {erro.pgerror or erro}")
        finally:
            conn.rollback()
    assert not invalidas, f"consultas de checagem inválidas: {invalidas}"
