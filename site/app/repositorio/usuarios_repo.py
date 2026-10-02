"""Schema `app` (5F.3): usuários e respostas, sempre pela role `site_app`."""

from psycopg2.extras import RealDictCursor

from app.db import get_conexao_app


def upsert_usuario(google_sub: str, email: str, nome: str | None) -> dict:
    with (
        get_conexao_app() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            INSERT INTO app.usuario (google_sub, email, nome)
            VALUES (%s, %s, %s)
            ON CONFLICT (google_sub)
                DO UPDATE SET email = EXCLUDED.email, nome = EXCLUDED.nome
            RETURNING id, email, nome
            """,
            (google_sub, email, nome),
        )
        usuario = cur.fetchone()
        conn.commit()
        return usuario


def obter_usuario(usuario_id: int) -> dict | None:
    with (
        get_conexao_app() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            "SELECT id, email, nome, concurso_alvo, cargo_alvo"
            " FROM app.usuario WHERE id = %s",
            (usuario_id,),
        )
        usuario = cur.fetchone()
        conn.rollback()
        return usuario


def gravar_resposta(
    usuario_id: int, questao_chave: str, resposta: str, acertou: bool
) -> None:
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.resposta (usuario_id, questao_chave, resposta, acertou)
            VALUES (%s, %s, %s, %s)
            """,
            (usuario_id, questao_chave, resposta, acertou),
        )
        conn.commit()


def ultimas_respostas(usuario_id: int) -> dict[str, bool]:
    """Chave → acertou, pela resposta mais recente de cada questão."""
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (questao_chave) questao_chave, acertou
            FROM app.resposta
            WHERE usuario_id = %s AND simulado_id IS NULL
            ORDER BY questao_chave, respondida_em DESC, id DESC
            """,
            (usuario_id,),
        )
        linhas = cur.fetchall()
        conn.rollback()
        return dict(linhas)


def dias_com_resposta(usuario_id: int, fuso: str) -> list:
    """Datas distintas (no fuso dado) com alguma resposta, da mais recente à mais antiga.

    Conta resposta avulsa e de simulado: dia seguido é dia em que o usuário estudou.
    """
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT (respondida_em AT TIME ZONE %s)::date AS dia
            FROM app.resposta
            WHERE usuario_id = %s
            ORDER BY dia DESC
            """,
            (fuso, usuario_id),
        )
        linhas = cur.fetchall()
        conn.rollback()
        return [d for (d,) in linhas]


def apagar_usuario(usuario_id: int) -> bool:
    """Apaga a conta; respostas e simulados saem em cascata."""
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM app.usuario WHERE id = %s", (usuario_id,))
        apagou = cur.rowcount > 0
        conn.commit()
        return apagou


def salvar_concurso_alvo(usuario_id: int, concurso: str, cargo_numero: int) -> bool:
    """Grava o concurso-alvo (5F.8). Falso se o usuário não existe mais."""
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE app.usuario SET concurso_alvo = %s, cargo_alvo = %s WHERE id = %s",
            (concurso, cargo_numero, usuario_id),
        )
        atualizou = cur.rowcount > 0
        conn.commit()
        return atualizou
