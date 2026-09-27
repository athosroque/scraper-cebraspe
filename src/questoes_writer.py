"""Grava as questões extraídas de um caderno (Etapa 5C, ADR-031).

Mesma regra dos fatos do ADR-027: o conteúdo de um caderno é **substituído**
numa transação a cada extração (upsert linha a linha deixaria questão órfã
quando a reextração muda o corte). A chave é `provas.id`, estável entre
cargas do `stats_writer` (provas por upsert em `(concurso, arquivo)`).

Caderno com falha (itens divergentes do gabarito, sem gabarito) não grava
questão nenhuma: fica só no JSON de revisão e na fila com `status = 'erro'` —
questão parcial no banco distorceria a estatística sem aviso.
"""

from psycopg2.extras import Json


def gravar_caderno_objetivo(conn, prova_id: int, resultado: dict) -> int:
    """Substitui textos-base e questões do caderno. Retorna o nº de questões."""
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM questoes WHERE prova_id = %s", (prova_id,))
        cur.execute("DELETE FROM textos_base WHERE prova_id = %s", (prova_id,))
        ids_base: dict[int, int] = {}
        for tb in resultado["textos_base"]:
            cur.execute(
                "INSERT INTO textos_base (prova_id, ordem, texto, figuras) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (prova_id, tb["ordem"], tb["texto"], Json(tb["figuras"])),
            )
            ids_base[tb["ordem"]] = cur.fetchone()[0]

        # Mapeia alertas do JSON vinculados a cada número de item
        alertas_por_item: dict[int, list[str]] = {}
        for a in resultado.get("alertas", []):
            item_num = a.get("item")
            tipo = a.get("tipo")
            if item_num is not None and tipo:
                if item_num not in alertas_por_item:
                    alertas_por_item[item_num] = []
                if tipo not in alertas_por_item[item_num]:
                    alertas_por_item[item_num].append(tipo)

        for q in resultado["questoes"]:
            tb_ordem = q.get("texto_base_ordem")
            if tb_ordem is not None and tb_ordem not in ids_base:
                ordens = list(ids_base.keys())
                raise ValueError(
                    f"Caderno {prova_id}: questão {q['numero']} aponta para "
                    f"texto_base_ordem={tb_ordem} inexistente nesta prova "
                    f"(ordens disponíveis: {ordens})"
                )
            texto_base_id = ids_base.get(tb_ordem) if tb_ordem is not None else None

            alertas_item = list(
                dict.fromkeys(q.get("alertas") or alertas_por_item.get(q["numero"], []))
            )
            utilizavel = "simbolo_ilegivel" not in alertas_item

            cur.execute(
                """
                INSERT INTO questoes
                    (prova_id, numero, enunciado, texto_base_id, gabarito, anulada, figuras, secao, alertas, utilizavel)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    prova_id,
                    q["numero"],
                    q["enunciado"],
                    texto_base_id,
                    q["gabarito"],
                    q["anulada"],
                    Json(q["figuras"]),
                    q["secao"],
                    alertas_item,
                    utilizavel,
                ),
            )
    return len(resultado["questoes"])


def gravar_caderno_discursivo(conn, prova_id: int, resultado: dict) -> int:
    """Substitui as questões discursivas do caderno e grava os temas em
    `provas.tema`. Retorna o nº de questões."""
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM discursivas WHERE prova_id = %s", (prova_id,))
        for q in resultado["questoes"]:
            cur.execute(
                """
                INSERT INTO discursivas
                    (prova_id, numero, titulo, tema, enunciado, quesitos, padrao_resposta)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    prova_id,
                    q["numero"],
                    q["titulo"],
                    q["tema"],
                    q["enunciado"],
                    Json(q["quesitos"]),
                    q["padrao_resposta"],
                ),
            )
        temas = [q["tema"] for q in resultado["questoes"] if q["tema"]]
        cur.execute(
            "UPDATE provas SET tema = %s WHERE id = %s",
            (" | ".join(temas) or None, prova_id),
        )
    return len(resultado["questoes"])


def limpar_caderno(conn, prova_id: int) -> None:
    """Remove o que um caderno com falha tinha gravado numa extração anterior."""
    with conn, conn.cursor() as cur:
        cur.execute("DELETE FROM questoes WHERE prova_id = %s", (prova_id,))
        cur.execute("DELETE FROM textos_base WHERE prova_id = %s", (prova_id,))
        cur.execute("DELETE FROM discursivas WHERE prova_id = %s", (prova_id,))
