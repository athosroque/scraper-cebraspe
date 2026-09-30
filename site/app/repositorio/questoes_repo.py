from psycopg2.extras import RealDictCursor

from app.db import get_conexao_leitura


def buscar_questoes(
    filtros_dict: dict, limit: int, offset: int
) -> tuple[list[dict], int]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        # Construir cláusulas WHERE iterativamente
        condicoes = ["1 = 1"]
        params = {}

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

        where_clause = " AND ".join(condicoes)

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
            COALESCE(cnt.total_questoes, 0) AS total_questoes
        FROM vw_no_caminho c
        LEFT JOIN contagens cnt ON cnt.alvo_id = c.id
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
            "concurso",
            "nivel",
            "tipo_conhecimento",
        ]:
            cur.execute(
                f"SELECT {col} AS valor, count(DISTINCT questao_id) AS total FROM vw_questoes WHERE utilizavel GROUP BY {col} ORDER BY total DESC"
            )
            facetas[col] = cur.fetchall()

        cur.execute("""
            SELECT cargo_numero, cargo, concurso, nivel, count(DISTINCT questao_id) AS total
            FROM vw_questoes
            WHERE utilizavel
            GROUP BY cargo_numero, cargo, concurso, nivel
            ORDER BY total DESC
        """)
        facetas["cargos"] = cur.fetchall()
        return facetas
