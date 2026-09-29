import contextlib

from psycopg2 import pool

from app.config import settings

pool_leitura = None
pool_app = None


def inicializar_pools():
    global pool_leitura, pool_app

    # Pool de leitura
    pool_leitura = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.site_db_leitura_user,
        password=settings.site_db_leitura_password,
    )

    # Pool de app
    pool_app = pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.site_db_app_user,
        password=settings.site_db_app_password,
    )


def fechar_pools():
    if pool_leitura:
        pool_leitura.closeall()
    if pool_app:
        pool_app.closeall()


@contextlib.contextmanager
def get_conexao_leitura():
    conn = pool_leitura.getconn()
    try:
        yield conn
    finally:
        pool_leitura.putconn(conn)


@contextlib.contextmanager
def get_conexao_app():
    conn = pool_app.getconn()
    try:
        yield conn
    finally:
        pool_app.putconn(conn)
