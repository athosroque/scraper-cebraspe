from psycopg2.extras import RealDictCursor

from app.db import get_conexao_leitura


def montar_where(filtros_dict: dict, params: dict) -> str:
    """WHERE sobre `vw_questoes` a partir dos filtros; preenche `params`."""
    condicoes = ["1 = 1"]

    if filtros_dict.get("banca"):
        condicoes.append("banca = %(banca)s")
        params["banca"] = filtros_dict["banca"]

    if filtros_dict.get("orgao"):
        condicoes.append("orgao = %(orgao)s")
        params["orgao"] = filtros_dict["orgao"]

    if filtros_dict.get("ano"):
        condicoes.append("ano = %(ano)s")
        params["ano"] = filtros_dict["ano"]

    if filtros_dict.get("concurso"):
        condicoes.append("concurso = %(concurso)s")
        params["concurso"] = filtros_dict["concurso"]

    if filtros_dict.get("cargo_numero"):
        condicoes.append("cargo_numero = %(cargo_numero)s")
        params["cargo_numero"] = filtros_dict["cargo_numero"]

    if filtros_dict.get("nivel"):
        condicoes.append("nivel = %(nivel)s")
        params["nivel"] = filtros_dict["nivel"]

    if filtros_dict.get("tipo_conhecimento"):
        condicoes.append("tipo_conhecimento = %(tipo_conhecimento)s")
        params["tipo_conhecimento"] = filtros_dict["tipo_conhecimento"]

    if filtros_dict.get("no_id"):
        condicoes.append(
            "(no_id = %(no_id)s OR assunto_id = %(no_id)s OR materia_id = %(no_id)s)"
        )
        params["no_id"] = filtros_dict["no_id"]

    if filtros_dict.get("anuladas") == "excluir":
        condicoes.append("anulada = false")
    elif filtros_dict.get("anuladas") == "so":
        condicoes.append("anulada = true")

    if filtros_dict.get("utilizaveis", "so") == "so":
        condicoes.append("utilizavel")

    if filtros_dict.get("fora_do_edital") == "nao":
        condicoes.append("fora_do_edital = false")
    elif filtros_dict.get("fora_do_edital") == "sim":
        condicoes.append("fora_do_edital = true")

    # Histórico do usuário (5F.3): as respostas ficam no schema `app`, que a
    # role de leitura não enxerga; o serviço resolve as chaves antes.
    if filtros_dict.get("chaves_incluir") is not None:
        condicoes.append("questao_chave = ANY(%(chaves_incluir)s)")
        params["chaves_incluir"] = list(filtros_dict["chaves_incluir"])
    if filtros_dict.get("chaves_excluir"):
        condicoes.append("NOT (questao_chave = ANY(%(chaves_excluir)s))")
        params["chaves_excluir"] = list(filtros_dict["chaves_excluir"])

    # Uma questão por enunciado canônico (o mesmo item em cadernos diferentes
    # do concurso fica só uma vez).
    if filtros_dict.get("apenas_canonicas"):
        condicoes.append("questao_id = questao_canonica_id")

    return " AND ".join(condicoes)


def buscar_questoes(
    filtros_dict: dict, limit: int, offset: int
) -> tuple[list[dict], int]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        params = {}
        where_clause = montar_where(filtros_dict, params)

        # Contagem total
        query_total = f"SELECT count(DISTINCT questao_id) AS total FROM vw_questoes WHERE {where_clause}"
        cur.execute(query_total, params)
        total = cur.fetchone()["total"]

        # Paginação com agregação JSONB
        params["limit"] = limit
        params["offset"] = offset

        query = f"""
        WITH pagina_ids AS (
            SELECT questao_id
            FROM vw_questoes
            WHERE {where_clause}
            GROUP BY questao_id, concurso, codigo_caderno, numero
            ORDER BY concurso, codigo_caderno, numero
            LIMIT %(limit)s OFFSET %(offset)s
        )
        SELECT
            q.questao_id,
            q.questao_chave,
            q.numero,
            q.codigo_caderno,
            q.concurso,
            q.orgao,
            q.banca,
            q.ano,
            q.gabarito,
            q.anulada,
            q.utilizavel,
            q.enunciado,
            q.secao,
            q.tem_texto_base,
            q.tem_figuras,
            jsonb_agg(DISTINCT jsonb_build_object(
                'cargo_edital_id', q.cargo_edital_id,
                'cargo_numero', q.cargo_numero,
                'cargo', q.cargo,
                'nivel', q.nivel
            )) AS cargos,
            jsonb_agg(DISTINCT jsonb_build_object(
                'no_id', q.no_id,
                'no_nome', q.no_nome,
                'no_nivel', q.no_nivel,
                'no_caminho', q.no_caminho,
                'materia_id', q.materia_id,
                'assunto_id', q.assunto_id,
                'papel', q.papel,
                'confianca', q.confianca,
                'fora_do_edital', q.fora_do_edital,
                'rotulo_materia', q.rotulo_materia
            )) AS nos
        FROM vw_questoes q
        JOIN pagina_ids p ON p.questao_id = q.questao_id
        GROUP BY
            q.questao_id, q.questao_chave, q.concurso, q.codigo_caderno, q.numero,
            q.orgao, q.banca, q.ano, q.gabarito, q.anulada, q.utilizavel,
            q.enunciado, q.secao, q.tem_texto_base, q.tem_figuras
        ORDER BY q.concurso, q.codigo_caderno, q.numero
        """
        cur.execute(query, params)
        linhas = cur.fetchall()

        return linhas, total


def obter_questao_por_chave(chave: str) -> dict | None:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        query = """
        SELECT
            q.questao_id,
            q.questao_chave,
            q.numero,
            q.codigo_caderno,
            q.concurso,
            q.orgao,
            q.banca,
            q.ano,
            q.gabarito,
            q.anulada,
            q.utilizavel,
            q.enunciado,
            q.secao,
            q.tem_texto_base,
            q.tem_figuras,
            q.texto_base_texto,
            q.figuras,
            f.url AS link_pdf,
            jsonb_agg(DISTINCT jsonb_build_object(
                'cargo_edital_id', q.cargo_edital_id,
                'cargo_numero', q.cargo_numero,
                'cargo', q.cargo,
                'nivel', q.nivel
            )) AS cargos,
            jsonb_agg(DISTINCT jsonb_build_object(
                'no_id', q.no_id,
                'no_nome', q.no_nome,
                'no_nivel', q.no_nivel,
                'no_caminho', q.no_caminho,
                'materia_id', q.materia_id,
                'assunto_id', q.assunto_id,
                'papel', q.papel,
                'confianca', q.confianca,
                'fora_do_edital', q.fora_do_edital,
                'rotulo_materia', q.rotulo_materia
            )) AS nos
        FROM vw_questoes q
        LEFT JOIN provas p ON p.codigo_caderno = q.codigo_caderno AND p.concurso_id = (SELECT id FROM concursos WHERE slug = q.concurso)
        LEFT JOIN fila_extracao_questoes f ON (f.prova_id = p.id OR (f.concurso_id = p.concurso_id AND f.arquivo = p.arquivo)) AND f.categoria = 'prova'
        WHERE q.questao_chave = %(chave)s
        GROUP BY
            q.questao_id, q.questao_chave, q.concurso, q.codigo_caderno, q.numero,
            q.orgao, q.banca, q.ano, q.gabarito, q.anulada, q.utilizavel,
            q.enunciado, q.secao, q.tem_texto_base, q.tem_figuras, q.texto_base_texto, q.figuras, f.url
        """
        cur.execute(query, {"chave": chave})
        row = cur.fetchone()
        return row


def obter_arvore_com_contagens() -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        query = """
        WITH contagens AS (
            SELECT materia_id AS alvo_id, count(DISTINCT questao_id) AS total_questoes
            FROM vw_questoes WHERE utilizavel AND materia_id IS NOT NULL GROUP BY materia_id
            UNION ALL
            SELECT coalesce(assunto_id, no_id) AS alvo_id, count(DISTINCT questao_id) AS total_questoes
            FROM vw_questoes WHERE utilizavel AND (assunto_id IS NOT NULL OR no_nivel = 'assunto') GROUP BY coalesce(assunto_id, no_id)
            UNION ALL
            SELECT no_id AS alvo_id, count(DISTINCT questao_id) AS total_questoes
            FROM vw_questoes WHERE utilizavel AND no_nivel = 'subassunto' GROUP BY no_id
        )
        SELECT 
            c.id, c.nome, c.nivel, c.pai_id,
            COALESCE(cnt.total_questoes, 0) AS total_questoes,
            (c.nivel = 'materia' AND EXISTS (
                SELECT 1 FROM vw_questoes q
                WHERE q.materia_id = c.id AND q.utilizavel AND q.nome_de_cargo
            )) AS nome_de_cargo
        FROM vw_no_caminho c
        LEFT JOIN contagens cnt ON cnt.alvo_id = c.id
        ORDER BY COALESCE(cnt.total_questoes, 0) DESC, c.nome ASC
        """
        cur.execute(query)
        return cur.fetchall()


def obter_facetas() -> dict:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        facetas = {}
        for col in [
            "banca",
            "orgao",
            "ano",
            "tipo_conhecimento",
        ]:
            cur.execute(
                f"SELECT {col} AS valor, count(DISTINCT questao_id) AS total FROM vw_questoes WHERE utilizavel GROUP BY {col} ORDER BY total DESC"
            )
            facetas[col] = cur.fetchall()

        cur.execute(
            "SELECT concurso AS valor, count(DISTINCT questao_id) AS total FROM vw_questoes WHERE utilizavel GROUP BY concurso ORDER BY max(orgao), max(ano)"
        )
        facetas["concurso"] = cur.fetchall()

        cur.execute(
            "SELECT nivel AS valor, count(DISTINCT questao_id) AS total FROM vw_questoes WHERE utilizavel GROUP BY nivel ORDER BY nivel DESC"
        )
        facetas["nivel"] = cur.fetchall()

        cur.execute("""
            SELECT cargo_numero, cargo, concurso, nivel, count(DISTINCT questao_id) AS total
            FROM vw_questoes
            WHERE utilizavel
            GROUP BY cargo_numero, cargo, concurso, nivel
            ORDER BY cargo_numero ASC
        """)
        facetas["cargos"] = cur.fetchall()
        return facetas


def desempenho_por_no(
    filtros_dict: dict, chaves: list[str], acertos: list[bool]
) -> list[dict]:
    """Acertos/total por nó para as questões respondidas (uma resposta por chave).

    Mesma regra da 5E: a questão sobe a árvore (subassunto → assunto →
    matéria, nunca desce) e conta uma vez por nó, mesmo com 2 nós na mesma
    matéria. Anuladas ficam de fora.
    """
    if not chaves:
        return []
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        params = {"chaves": chaves, "acertos": acertos}
        where_clause = montar_where(
            {**filtros_dict, "anuladas": "excluir", "chaves_incluir": chaves}, params
        )
        query = f"""
        WITH r AS (
            SELECT * FROM unnest(%(chaves)s::text[], %(acertos)s::boolean[])
                AS r(chave, acertou)
        ),
        q AS (
            SELECT DISTINCT questao_chave, materia_id, assunto_id, no_id, no_nivel
            FROM vw_questoes
            WHERE {where_clause}
        ),
        alvos AS (
            SELECT questao_chave, materia_id AS alvo FROM q WHERE materia_id IS NOT NULL
            UNION
            SELECT questao_chave, assunto_id FROM q WHERE assunto_id IS NOT NULL
            UNION
            SELECT questao_chave, no_id FROM q WHERE no_nivel = 'subassunto'
        )
        SELECT c.id, c.nome, c.nivel, c.pai_id,
               count(*) AS total,
               count(*) FILTER (WHERE r.acertou) AS acertos
        FROM alvos a
        JOIN r ON r.chave = a.questao_chave
        JOIN vw_no_caminho c ON c.id = a.alvo
        GROUP BY c.id, c.nome, c.nivel, c.pai_id
        """
        cur.execute(query, params)
        return cur.fetchall()


def chaves_mesmo_enunciado(chave: str) -> list[str] | None:
    """Chaves com o mesmo enunciado canônico da questão (inclui a própria).

    `None` quando a chave não existe.
    """
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT DISTINCT o.questao_chave
            FROM vw_questoes q
            JOIN vw_questoes o ON o.questao_canonica_id = q.questao_canonica_id
            WHERE q.questao_chave = %(chave)s
            """,
            {"chave": chave},
        )
        return [r["questao_chave"] for r in cur.fetchall()] or None


def ranking_subassuntos() -> list[dict]:
    """Ranking completo de subassuntos (`fn_prova_cobra`, sem filtros)."""
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(
            """
            SELECT no_id, materia_id, questoes
            FROM fn_prova_cobra('subassunto')
            ORDER BY materia_id, questoes DESC, pct_medio_por_concurso DESC, no_nome
            """
        )
        return cur.fetchall()
