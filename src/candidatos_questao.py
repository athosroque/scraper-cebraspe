"""Resolução determinística de candidatos da árvore mestre e agrupamento de lotes (Etapa 5D).

Oferece duas camadas de nós candidatos:
1. Candidatos preferenciais: derivados do edital dos cargos associados à prova
   (`vw_arvore_edital_por_cargo` combinada com `provas_cargos`), incluindo ancestrais
   diretos (assunto e matéria via `vw_no_caminho`) para permitir classificação mais genérica
   caso nenhum subassunto sirva.
2. Candidatos de reserva: subárvore ativa completa das matérias contempladas no caderno,
   extraída diretamente de `arvore.ArvoreMestre`.
"""

from typing import Any

from src import arvore


def candidatos_preferenciais(conn, prova_id: int) -> dict[str, dict[str, Any]]:
    """Busca nós candidatos do edital associados aos cargos da prova, com ancestrais.

    Retorna dicionário indexado pelo ID do nó:
    {no_id: {"id": no_id, "nome": nome, "nivel": nivel, "caminho": caminho,
             "materia_id": materia_id, "assunto_id": assunto_id, "pai_id": pai_id}}
    """
    with conn.cursor() as cur:
        cur.execute("SELECT tipo FROM provas WHERE id = %s", (prova_id,))
        row = cur.fetchone()
        if not row:
            return {}

        tipo_prova = row[0]
        if tipo_prova == "objetiva_basica":
            filtro_tipo = "AND e.tipo_conhecimento = 'basico'"
        elif tipo_prova == "objetiva_especifica":
            filtro_tipo = "AND e.tipo_conhecimento IS DISTINCT FROM 'basico'"
        else:
            # discursiva ou outros tipos: todos os nós associados aos cargos
            filtro_tipo = ""

        query = f"""
        WITH nos_diretos AS (
            SELECT DISTINCT
                e.no_id,
                e.no_materia_id,
                e.no_assunto_id
            FROM provas_cargos pc
            JOIN vw_arvore_edital_por_cargo e ON e.cargo_edital_id = pc.cargo_edital_id
            WHERE pc.prova_id = %(prova_id)s {filtro_tipo}
        ),
        todos_ids AS (
            SELECT no_id AS id FROM nos_diretos
            UNION
            SELECT no_materia_id AS id FROM nos_diretos WHERE no_materia_id IS NOT NULL
            UNION
            SELECT no_assunto_id AS id FROM nos_diretos WHERE no_assunto_id IS NOT NULL
        )
        SELECT DISTINCT
            nc.no_efetivo AS id,
            nc.nome,
            nc.nivel,
            nc.caminho,
            nc.materia_id,
            nc.assunto_id,
            nc.pai_id
        FROM vw_no_caminho nc
        JOIN todos_ids t ON t.id = nc.id
        ORDER BY nc.caminho
        """
        cur.execute(query, {"prova_id": prova_id})
        resultados = {}
        for r in cur.fetchall():
            no_id = r[0]
            resultados[no_id] = {
                "id": no_id,
                "nome": r[1],
                "nivel": r[2],
                "caminho": r[3],
                "materia_id": r[4],
                "assunto_id": r[5],
                "pai_id": r[6],
            }
        return resultados


def candidatos_reserva(
    arv: arvore.ArvoreMestre, materias_ids: set[str]
) -> dict[str, dict[str, Any]]:
    """Extrai a subárvore ativa completa das matérias indicadas a partir de `arvore.ArvoreMestre`."""
    if not materias_ids:
        return {}

    resultados = {}
    for no_id, no in sorted(arv.nos.items()):
        if no.status != "ativo":
            continue

        mat_id = arvore.materia_do_no(arv, no_id)
        if mat_id not in materias_ids:
            continue

        pai_id = arvore.resolver_no(arv, no.pai) if no.pai else None

        if no.nivel == "materia":
            assunto_id = None
            caminho = no.nome
        elif no.nivel == "assunto":
            assunto_id = no.id
            pai_mat = arv.nos.get(pai_id) if pai_id else None
            pai_nome = pai_mat.nome if pai_mat else ""
            caminho = f"{pai_nome} > {no.nome}" if pai_nome else no.nome
        elif no.nivel == "subassunto":
            assunto_id = pai_id
            assunto_no = arv.nos.get(pai_id) if pai_id else None
            assunto_nome = assunto_no.nome if assunto_no else ""
            pai_mat_id = (
                arvore.resolver_no(arv, assunto_no.pai)
                if (assunto_no and assunto_no.pai)
                else None
            )
            mat_no = arv.nos.get(pai_mat_id) if pai_mat_id else None
            mat_nome = mat_no.nome if mat_no else ""
            partes = [p for p in (mat_nome, assunto_nome, no.nome) if p]
            caminho = " > ".join(partes)
        else:
            assunto_id = None
            caminho = no.nome

        resultados[no_id] = {
            "id": no_id,
            "nome": no.nome,
            "nivel": no.nivel,
            "caminho": caminho,
            "materia_id": mat_id,
            "assunto_id": assunto_id,
            "pai_id": pai_id,
        }

    return resultados


def montar_lotes(questoes: list[dict], max_tamanho: int = 10) -> list[list[dict]]:
    """Particiona a lista de questões em lotes estruturados.

    Regras:
    1. Questões com o mesmo `texto_base_id` não nulo permanecem juntas (lote indiviso).
    2. Questões sem texto-base são agrupadas por seções consecutivas.
    3. Seções sem texto-base maiores que `max_tamanho` são fatiadas em blocos de `max_tamanho`.
    4. Grupos adjacentes sem texto-base são combinados até atingir `max_tamanho`.
    """
    if not questoes:
        return []

    def _obter_tb_id(q: dict) -> Any:
        tb = q.get("texto_base_id")
        if tb is None:
            tb = q.get("texto_base_ordem")
        return tb

    # 1. Agrupar questões contíguas em segmentos homogêneos (mesmo TB ou mesma seção sem TB)
    segmentos: list[dict] = []
    for q in questoes:
        tb_id = _obter_tb_id(q)
        secao = q.get("secao")
        if tb_id is not None:
            if (
                segmentos
                and segmentos[-1]["tipo"] == "tb"
                and segmentos[-1]["tb_id"] == tb_id
            ):
                segmentos[-1]["itens"].append(q)
            else:
                segmentos.append({"tipo": "tb", "tb_id": tb_id, "itens": [q]})
        else:
            if (
                segmentos
                and segmentos[-1]["tipo"] == "sem_tb"
                and segmentos[-1]["secao"] == secao
            ):
                segmentos[-1]["itens"].append(q)
            else:
                segmentos.append({"tipo": "sem_tb", "secao": secao, "itens": [q]})

    # 2. Processar segmentos para montar os lotes finais
    lotes: list[list[dict]] = []
    acumulador_sem_tb: list[dict] = []

    def descarregar_acumulador():
        nonlocal acumulador_sem_tb
        if acumulador_sem_tb:
            lotes.append(acumulador_sem_tb)
            acumulador_sem_tb = []

    for seg in segmentos:
        if seg["tipo"] == "tb":
            descarregar_acumulador()
            lotes.append(seg["itens"])
        else:
            itens = seg["itens"]
            for i in range(0, len(itens), max_tamanho):
                bloco = itens[i : i + max_tamanho]
                if len(acumulador_sem_tb) + len(bloco) <= max_tamanho:
                    acumulador_sem_tb.extend(bloco)
                else:
                    descarregar_acumulador()
                    acumulador_sem_tb.extend(bloco)

    descarregar_acumulador()
    return lotes
