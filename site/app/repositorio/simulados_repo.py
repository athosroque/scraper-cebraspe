"""Simulado (5F.5): a prova vem das views (role `site_leitura`) e o registro
do simulado do schema `app` (role `site_app`), nunca numa query só."""

from psycopg2.extras import RealDictCursor

from app.db import get_conexao_app, get_conexao_leitura


def itens_da_prova(concurso: str, cargo_numero: int) -> list[dict]:
    """Itens do cargo na ordem da prova: básico, depois específico.

    A matéria do item é a do nó principal (a questão com 2 nós em matérias
    diferentes conta uma vez, na principal).
    """
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT
                questao_chave, numero, codigo_caderno, tipo_conhecimento,
                cargo, nivel, enunciado, secao, texto_base_texto, figuras,
                gabarito, anulada,
                (array_agg(materia_id ORDER BY papel = 'principal' DESC))[1]
                    AS materia_id,
                (array_agg(rotulo_materia ORDER BY papel = 'principal' DESC))[1]
                    AS materia_nome
            FROM vw_questoes
            WHERE concurso = %(concurso)s
              AND cargo_numero = %(cargo_numero)s
              AND utilizavel
            GROUP BY questao_chave, numero, codigo_caderno, tipo_conhecimento,
                     cargo, nivel, enunciado, secao, texto_base_texto, figuras,
                     gabarito, anulada
            ORDER BY tipo_conhecimento <> 'basico', codigo_caderno, numero
            """,
            {"concurso": concurso, "cargo_numero": cargo_numero},
        )
        return cur.fetchall()


def itens_omitidos(concurso: str, cargo_numero: int) -> int:
    """Itens do cargo com `utilizavel = false`, que o simulado deixa de fora."""
    with get_conexao_leitura() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT count(DISTINCT questao_chave) FROM vw_questoes
            WHERE concurso = %(concurso)s
              AND cargo_numero = %(cargo_numero)s
              AND NOT utilizavel
            """,
            {"concurso": concurso, "cargo_numero": cargo_numero},
        )
        return cur.fetchone()[0]


def discursivas_da_prova(concurso: str, cargo_numero: int) -> list[dict]:
    # A view tem uma linha por nó da discursiva: uma por discursiva aqui.
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT DISTINCT ON (numero, discursiva_id)
                numero, titulo, tema, enunciado, quesitos, padrao_resposta
            FROM vw_discursivas
            WHERE concurso = %(concurso)s AND cargo_numero = %(cargo_numero)s
            ORDER BY numero, discursiva_id
            """,
            {"concurso": concurso, "cargo_numero": cargo_numero},
        )
        return cur.fetchall()


def criar_simulado(usuario_id: int, concurso: str, cargo_numero: int) -> int:
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app.simulado (usuario_id, concurso, cargo_numero)
            VALUES (%s, %s, %s) RETURNING id
            """,
            (usuario_id, concurso, cargo_numero),
        )
        simulado_id = cur.fetchone()[0]
        conn.commit()
        return simulado_id


def obter_simulado(simulado_id: int, usuario_id: int) -> dict | None:
    with (
        get_conexao_app() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT id, concurso, cargo_numero, inicio, fim, nota
            FROM app.simulado WHERE id = %s AND usuario_id = %s
            """,
            (simulado_id, usuario_id),
        )
        linha = cur.fetchone()
        conn.rollback()
        return linha


def listar_simulados(usuario_id: int) -> list[dict]:
    with (
        get_conexao_app() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT id, concurso, cargo_numero, inicio, fim, nota
            FROM app.simulado WHERE usuario_id = %s
            ORDER BY inicio DESC, id DESC
            """,
            (usuario_id,),
        )
        linhas = cur.fetchall()
        conn.rollback()
        return linhas


def encerrar_simulado(
    simulado_id: int, usuario_id: int, nota: int, respostas: list[tuple[str, str, bool]]
) -> bool:
    """Grava nota, fim e respostas numa transação. Só encerra uma vez."""
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE app.simulado SET fim = now(), nota = %s
            WHERE id = %s AND usuario_id = %s AND fim IS NULL
            """,
            (nota, simulado_id, usuario_id),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return False
        cur.executemany(
            """
            INSERT INTO app.resposta
                (usuario_id, questao_chave, resposta, acertou, simulado_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [(usuario_id, c, r, a, simulado_id) for c, r, a in respostas],
        )
        conn.commit()
        return True


def respostas_do_simulado(simulado_id: int, usuario_id: int) -> dict[str, str]:
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT questao_chave, resposta FROM app.resposta
            WHERE simulado_id = %s AND usuario_id = %s
            """,
            (simulado_id, usuario_id),
        )
        linhas = cur.fetchall()
        conn.rollback()
        return dict(linhas)


def nota_anterior(simulado_id: int, usuario_id: int) -> int | None:
    """Nota do simulado encerrado imediatamente antes deste (mesmo usuário,
    concurso e cargo). Usa a nota gravada no encerramento."""
    with get_conexao_app() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT ant.nota FROM app.simulado atual
            JOIN app.simulado ant
              ON ant.usuario_id = atual.usuario_id
             AND ant.concurso = atual.concurso
             AND ant.cargo_numero IS NOT DISTINCT FROM atual.cargo_numero
             AND ant.fim IS NOT NULL
             AND ant.id <> atual.id
             AND (ant.fim, ant.id) < (atual.fim, atual.id)
            WHERE atual.id = %s AND atual.usuario_id = %s AND atual.fim IS NOT NULL
            ORDER BY ant.fim DESC, ant.id DESC
            LIMIT 1
            """,
            (simulado_id, usuario_id),
        )
        linha = cur.fetchone()
        conn.rollback()
        return linha[0] if linha else None
