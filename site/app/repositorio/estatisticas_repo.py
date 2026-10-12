"""Leituras das estatísticas da 5E para as páginas da 5F.4.

Toda conta de questão vem de `fn_prova_cobra` (nunca soma de
`vw_prova_cobra_*` entre cargos). Os rankings de prova ordenam pela
incidência média em dois níveis (`pct_do_universo`: média das provas distintas
de cada concurso e depois entre os concursos, cada concurso pesando 1; ADR-039),
nunca pela contagem bruta, que faria a prova maior pesar mais. A conta do edital repete a regra da
`vw_edital_cobra_base` com filtros: ocorrência = item de edital distinto,
subindo a árvore, só concurso `aprovado`.
"""

from psycopg2.extras import RealDictCursor

from app.cache import cache_ttl
from app.db import get_conexao_leitura


def prova_cobra(
    nivel_alvo: str, filtros: dict, materia_id: str | None, limite: int
) -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT no_id, no_nome, caminho, materia_id, questoes, anuladas,
                   total_universo, pct_do_universo, pct_medio_por_concurso
            FROM fn_prova_cobra(
                %(nivel_alvo)s,
                p_concurso => %(concurso)s,
                p_cargo_numero => %(cargo_numero)s,
                p_nivel => %(nivel)s,
                p_tipo_conhecimento => %(tipo_conhecimento)s
            )
            WHERE (%(materia_id)s::text IS NULL OR materia_id = %(materia_id)s)
            ORDER BY pct_do_universo DESC, pct_medio_por_concurso DESC,
                     questoes DESC, no_nome
            LIMIT %(limite)s
            """,
            {
                "nivel_alvo": nivel_alvo,
                "materia_id": materia_id,
                "limite": limite,
                **filtros,
            },
        )
        return cur.fetchall()


def edital_cobra(
    nivel_alvo: str, filtros: dict, materia_id: str | None, limite: int
) -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            WITH e AS MATERIALIZED (
                SELECT taxonomia_item_id, no_id, no_nivel, no_assunto_id, no_materia_id
                FROM vw_arvore_edital_por_cargo
                WHERE status_revisao = 'aprovado'
                  AND (%(concurso)s::text IS NULL OR concurso = %(concurso)s)
                  AND (%(cargo_numero)s::int IS NULL OR cargo_numero = %(cargo_numero)s)
                  AND (%(nivel)s::text IS NULL OR nivel = %(nivel)s)
                  AND (%(tipo_conhecimento)s::text IS NULL
                       OR tipo_conhecimento = %(tipo_conhecimento)s)
            ),
            b AS (
                SELECT taxonomia_item_id, 'subassunto' AS nivel_alvo, no_id AS alvo_id
                FROM e WHERE no_nivel = 'subassunto'
                UNION
                SELECT taxonomia_item_id, 'assunto', no_assunto_id
                FROM e WHERE no_assunto_id IS NOT NULL
                UNION
                SELECT taxonomia_item_id, 'materia', no_materia_id FROM e
            )
            SELECT b.alvo_id AS no_id, nc.nome AS no_nome, nc.caminho, nc.materia_id,
                   count(DISTINCT b.taxonomia_item_id) AS ocorrencias
            FROM b
            JOIN vw_no_caminho nc ON nc.id = b.alvo_id
            WHERE b.nivel_alvo = %(nivel_alvo)s
              AND (%(materia_id)s::text IS NULL OR nc.materia_id = %(materia_id)s)
            GROUP BY b.alvo_id, nc.nome, nc.caminho, nc.materia_id
            ORDER BY ocorrencias DESC, nc.nome
            LIMIT %(limite)s
            """,
            {
                "nivel_alvo": nivel_alvo,
                "materia_id": materia_id,
                "limite": limite,
                **filtros,
            },
        )
        return cur.fetchall()


def edital_vs_prova(concurso: str, cargo_numero: int) -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT no_id, no_nome, no_nivel, caminho, materia_id,
                   previsao, questoes, situacao
            FROM vw_edital_vs_prova
            WHERE concurso = %s AND cargo_numero = %s
            ORDER BY caminho
            """,
            (concurso, cargo_numero),
        )
        return cur.fetchall()


def peso_materia_cargo(concurso: str, cargo_numero: int) -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT materia_id, rotulo_materia, questoes, anuladas, total_cargo,
                   pct_da_prova
            FROM vw_peso_materia_cargo
            WHERE concurso = %s AND cargo_numero = %s
            ORDER BY questoes DESC, rotulo_materia
            """,
            (concurso, cargo_numero),
        )
        return cur.fetchall()


def materias() -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT DISTINCT b.no_materia_id AS id, nc.nome
            FROM vw_prova_cobra_base b
            JOIN vw_no_caminho nc ON nc.id = b.no_materia_id
            ORDER BY nc.nome
            """
        )
        return cur.fetchall()


def cargos() -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT DISTINCT concurso, cargo_numero, cargo, nivel
            FROM vw_prova_cobra_base
            ORDER BY concurso, cargo_numero
            """
        )
        return cur.fetchall()


def materia_ativa(no_id: str) -> dict | None:
    """Nó de nível matéria da cadeia ativa (`vw_no_caminho` só expõe a ativa)."""
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            "SELECT id, nome FROM vw_no_caminho WHERE id = %s AND nivel = 'materia'",
            (no_id,),
        )
        return cur.fetchone()


@cache_ttl(300)
def materias_com_contagem(materia_id: str | None = None) -> list[dict]:
    """Matérias ativas com questões utilizáveis distintas (mesma conta da árvore).

    Usa `fn_prova_cobra` para manter a coerência entre a home e o painel:
    contagem de válidas desduplicadas e % médio em dois níveis (provas distintas
    de cada concurso, depois entre os concursos), que também dá a ordem.
    """
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT f.no_id AS id, f.no_nome AS nome,
                   f.questoes AS total_questoes,
                   f.pct_do_universo AS pct_incidencia,
                   coalesce(nc.nome_de_cargo, false) AS nome_de_cargo
            FROM fn_prova_cobra('materia') f
            LEFT JOIN (
                SELECT materia_id, bool_or(nome_de_cargo) AS nome_de_cargo
                FROM vw_questoes WHERE utilizavel GROUP BY materia_id
            ) nc ON nc.materia_id = f.no_id
            WHERE (%(materia_id)s::text IS NULL OR f.no_id = %(materia_id)s)
            ORDER BY f.pct_do_universo DESC, f.questoes DESC, f.no_nome
            """,
            {"materia_id": materia_id},
        )
        return cur.fetchall()


def nos_ativos() -> list[dict]:
    """Todos os nós da cadeia ativa (para a busca por nome em Python)."""
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute("SELECT id, nome, nivel, caminho, materia_id FROM vw_no_caminho")
        return cur.fetchall()


def apelidos_por_no() -> dict[str, list[str]]:
    """Apelidos de busca de cada nó efetivo (KAN-64), da view `vw_no_apelidos`."""
    with get_conexao_leitura() as conn, conn.cursor() as cur:
        cur.execute("SELECT no_id, apelidos FROM vw_no_apelidos")
        return {no_id: list(apelidos) for no_id, apelidos in cur.fetchall()}
