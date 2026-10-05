from psycopg2.extras import RealDictCursor

from app.cache import cache_ttl
from app.db import get_conexao_leitura


def _lista(valor) -> list:
    """Filtro como lista: chamadas internas ainda passam valor único."""
    if valor is None or valor == "" or valor == []:
        return []
    if isinstance(valor, (list, tuple, set)):
        return [v for v in valor if v not in (None, "")]
    return [valor]


# Filtro (chave do dict) → coluna de `vw_questoes`. Valores do mesmo filtro
# combinam com OU (`= ANY`), filtros diferentes com E.
_COLUNAS = {
    "banca": "banca",
    "orgao": "orgao",
    "ano": "ano",
    "concurso": "concurso",
    "cargo_numero": "cargo_numero",
    "nivel": "nivel",
    "tipo_conhecimento": "tipo_conhecimento",
}


def montar_where(filtros_dict: dict, params: dict, ignorar: tuple = ()) -> str:
    """WHERE sobre `vw_questoes` a partir dos filtros; preenche `params`.

    `ignorar`: filtros deixados de fora (a faceta conta os valores dela
    considerando só os outros filtros).
    """
    condicoes = ["1 = 1"]

    for chave, coluna in _COLUNAS.items():
        valores = _lista(filtros_dict.get(chave))
        if valores and chave not in ignorar:
            condicoes.append(f"{coluna} = ANY(%({chave})s)")
            params[chave] = valores

    cargos = _lista(filtros_dict.get("cargo"))
    if cargos and "cargo" not in ignorar:
        # `CONCURSO:NUMERO`: o número do cargo se repete entre concursos.
        condicoes.append("(concurso || ':' || cargo_numero) = ANY(%(cargo)s)")
        params["cargo"] = [str(c) for c in cargos]

    nos = _lista(filtros_dict.get("no_id"))
    if nos and "no_id" not in ignorar:
        # Nó em qualquer nível: matéria e assunto incluem os descendentes.
        condicoes.append(
            "(no_id = ANY(%(no_id)s) OR assunto_id = ANY(%(no_id)s)"
            " OR materia_id = ANY(%(no_id)s))"
        )
        params["no_id"] = nos

    anuladas = None if "anuladas" in ignorar else filtros_dict.get("anuladas")
    if anuladas == "excluir":
        condicoes.append("anulada = false")
    elif anuladas == "so":
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


@cache_ttl(300)
def obter_arvore_com_contagens() -> list[dict]:
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        query = """
        WITH contagens AS MATERIALIZED (
            -- Base única: questões válidas distintas (fn_prova_cobra), a mesma
            -- da home e do painel de matéria; sobe a árvore e exclui anuladas.
            SELECT no_id AS alvo_id, questoes AS total_questoes FROM fn_prova_cobra('materia')
            UNION ALL
            SELECT no_id, questoes FROM fn_prova_cobra('assunto')
            UNION ALL
            SELECT no_id, questoes FROM fn_prova_cobra('subassunto')
        )
        SELECT 
            c.id, c.nome, c.nivel, c.pai_id,
            COALESCE(cnt.total_questoes, 0) AS total_questoes,
            COALESCE(nc.nome_de_cargo, false) AS nome_de_cargo
        FROM vw_no_caminho c
        LEFT JOIN contagens cnt ON cnt.alvo_id = c.id
        LEFT JOIN (
            SELECT materia_id, bool_or(nome_de_cargo) AS nome_de_cargo
            FROM vw_questoes WHERE utilizavel GROUP BY materia_id
        ) nc ON nc.materia_id = c.id AND c.nivel = 'materia'
        ORDER BY COALESCE(cnt.total_questoes, 0) DESC, c.nome ASC
        """
        cur.execute(query)
        return cur.fetchall()


# Colunas que as facetas leem: a view é avaliada uma vez só (CTE) e cada
# faceta conta sobre essas linhas com o próprio FILTER.
_COLUNAS_FACETA = """
    questao_id, questao_chave, questao_canonica_id, banca, orgao, ano, concurso,
    cargo_numero, cargo, nivel, tipo_conhecimento, no_id, no_nivel, assunto_id,
    materia_id, anulada, utilizavel, fora_do_edital
"""


def obter_facetas(filtros_dict: dict | None = None) -> dict:
    """Valores de cada filtro com o total de questões distintas.

    O total de cada faceta considera os outros filtros (não o dela mesma):
    marcar 2025 não zera os outros anos. Valores com total 0 também vêm, para
    a interface manter visível o que já está marcado.
    """
    filtros_dict = filtros_dict or {}
    params: dict = {}

    def onde(*ignorar) -> str:
        return montar_where(filtros_dict, params, ignorar)

    partes = []
    for faceta, coluna in [
        ("banca", "banca"),
        ("orgao", "orgao"),
        ("ano", "ano"),
        ("concurso", "concurso"),
        ("nivel", "nivel"),
        ("tipo_conhecimento", "tipo_conhecimento"),
    ]:
        partes.append(f"""
            SELECT '{faceta}' AS faceta, {coluna}::text AS valor,
                   NULL::text AS cargo, NULL::text AS concurso, NULL::int AS cargo_numero,
                   NULL::text AS nivel, max(orgao) AS ord1, max(ano)::text AS ord2,
                   count(DISTINCT questao_id) FILTER (WHERE {onde(faceta)}) AS total
            FROM base GROUP BY {coluna}""")
    partes.append(f"""
            SELECT 'cargo', concurso || ':' || cargo_numero, max(cargo), concurso,
                   cargo_numero, max(nivel), NULL, NULL,
                   count(DISTINCT questao_id) FILTER (WHERE {onde("cargo", "cargo_numero")})
            FROM base GROUP BY concurso, cargo_numero""")
    nos = onde("no_id")
    partes.append(f"""
            SELECT 'materia', materia_id, NULL, NULL, NULL, NULL, NULL, NULL,
                   count(DISTINCT questao_id) FILTER (WHERE {nos})
            FROM base WHERE materia_id IS NOT NULL GROUP BY materia_id""")
    partes.append(f"""
            SELECT 'assunto', assunto_id, NULL, NULL, NULL, NULL, NULL, NULL,
                   count(DISTINCT questao_id) FILTER (WHERE {nos})
            FROM base WHERE assunto_id IS NOT NULL GROUP BY assunto_id""")
    partes.append(f"""
            SELECT 'subassunto', no_id, NULL, NULL, NULL, NULL, NULL, NULL,
                   count(DISTINCT questao_id) FILTER (WHERE {nos})
            FROM base WHERE no_nivel = 'subassunto' GROUP BY no_id""")
    partes.append(f"""
            SELECT 'anuladas', anulada::text, NULL, NULL, NULL, NULL, NULL, NULL,
                   count(DISTINCT questao_id) FILTER (WHERE {onde("anuladas")})
            FROM base GROUP BY anulada""")

    query = (
        f"WITH base AS MATERIALIZED (SELECT {_COLUNAS_FACETA} FROM vw_questoes) "
        + " UNION ALL ".join(partes)
    )
    with (
        get_conexao_leitura() as conn,
        conn.cursor(cursor_factory=RealDictCursor) as cur,
    ):
        cur.execute(query, params)
        linhas = cur.fetchall()

    facetas: dict[str, list[dict]] = {}
    for r in linhas:
        facetas.setdefault(r["faceta"], []).append(r)
    for nome in (
        "banca",
        "orgao",
        "ano",
        "tipo_conhecimento",
        "materia",
        "assunto",
        "subassunto",
        "anuladas",
    ):
        facetas.setdefault(nome, []).sort(key=lambda r: (-r["total"], str(r["valor"])))
    facetas.setdefault("concurso", []).sort(
        key=lambda r: (r["ord1"] or "", r["ord2"] or "", r["valor"])
    )
    facetas.setdefault("nivel", []).sort(key=lambda r: str(r["valor"]), reverse=True)
    facetas.setdefault("cargo", []).sort(
        key=lambda r: (r["cargo_numero"], r["concurso"])
    )
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
