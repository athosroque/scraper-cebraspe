"""Pipeline de inferência e classificação de questões na árvore mestre via LLM (Etapa 5D, ADR-030).

Uso:
    python -m scripts.classificar_questoes [--caderno CODIGO] [--dry-run]
        [--limite N] [--reclassificar] [--arvore caminho] [--classificacao caminho]

Classifica questões objetivas e discursivas na árvore mestre em duas passadas:
1. Passada preferencial: candidatos restritos ao edital do cargo (vw_arvore_edital_por_cargo).
   Nós classificados aqui recebem fora_do_edital = False.
2. Passada de reserva: itens com nenhum_serve = True são reavaliados com a subárvore
   completa das matérias daquele caderno (arvore.ArvoreMestre).
   Nós classificados aqui recebem fora_do_edital = True.
   Se nenhum nó servir mesmo na reserva, registra sem_no = True (ADR-030 §5).

Idempotência:
- Pula questões com o mesmo hash_enunciado e registro existente, exceto se --reclassificar for passado.
- Checkpoint atômico salvo em canonico/classificacao_questoes.json a cada lote processado.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import arvore, candidatos_questao, classificacao, llm_openrouter
from src.llm_openrouter import (
    REASONING_PADRAO,
    ResultadoPosValidacao,
    chamar_llm_json,
)
from src.logger import logger
from src.stats_writer import conectar, nome_caderno

PROJETO_DIR = Path(__file__).resolve().parent.parent
ARVORE_PATH_PADRAO = PROJETO_DIR / "canonico" / "arvore.json"
CLASSIFICACAO_PATH_PADRAO = PROJETO_DIR / "canonico" / "classificacao_questoes.json"

MAX_TOKENS = 12000
TIMEOUT = 120
TENTATIVAS = 2
BACKOFF_SEGUNDOS = 5

STATUS_FALHA_ID_DESCONHECIDO = "falha_id_desconhecido"
STATUS_FALHA_ITENS_DIVERGENTES = "falha_itens_divergentes"
STATUS_FALHA_VALIDACAO_SCHEMA = "falha_validacao_schema"

PROMPT_SISTEMA = """Você é um especialista em taxonomia e estruturação curricular de editais e provas de concursos públicos brasileiros.
Seu objetivo é classificar cada questão apresentada no nó mais específico possível da árvore de disciplinas (de preferência um subassunto; ou um assunto quando nenhum subassunto atender; ou matéria caso nenhum assunto atenda).

CRITÉRIOS DE CONFIANÇA:
- "alta": a questão aborda diretamente e univocamente o assunto ou subassunto indicado.
- "media": a questão aborda conceito abrangente ou fronteiriço, enquadrando-se no nó mas sem especificidade perfeita.
- "baixa": enquadramento duvidoso, periférico ou dependente de interpretação extensiva.

CARDINALIDADE E PAPÉIS:
- Atribua no máximo 2 nós por questão.
- O primeiro nó indicado em 'nos' será considerado o nó "principal" (obrigatório caso 'nenhum_serve' seja false).
- Apenas se a questão for genuinamente interdisciplinar, inclua um segundo nó opcional em 'nos', que será considerado "secundario".
- Se nenhum candidato da lista fornecida servir para a questão, marque "nenhum_serve": true e deixe "nos": [].

REGRAS ESTRITAS:
- Use APENAS os IDs locais listados em CANDIDATOS (ex: C1, C2...). NUNCA invente novos IDs.
- Forneça uma classificação para CADA item listado no prompt.
- Em 'justificativa', apresente uma explicação concisa e técnica.

Devolva APENAS JSON válido no seguinte formato, sem formatação markdown:
{"itens": [{"numero": 1, "nos": ["C3"], "confianca": "alta", "nenhum_serve": false, "justificativa": "..."}, ...]}"""


class ItemClassificado(BaseModel):
    numero: int | str
    nos: list[str] = Field(default_factory=list, max_length=2)
    confianca: Literal["alta", "media", "baixa"] = "alta"
    nenhum_serve: bool = False
    justificativa: str = ""


class RespostaClassificacaoLote(BaseModel):
    itens: list[ItemClassificado]


@dataclass
class Contabilidade:
    chamadas: int = 0
    falhas: Counter = field(default_factory=Counter)
    lotes_ok: int = 0
    lotes_falhos: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    distribuicao_confianca: Counter = field(default_factory=Counter)
    itens_classificados: int = 0
    total_sem_no: int = 0
    total_fora_edital: int = 0
    itens_pulados_idempotencia: int = 0

    def registrar_usage(self, usage: dict | None) -> None:
        usage = usage or {}
        self.tokens_entrada += usage.get("prompt_tokens", 0) or 0
        self.tokens_saida += usage.get("completion_tokens", 0) or 0
        self.custo_usd += float(usage.get("cost", 0) or 0)


def formatar_arvore_candidatos(
    candidatos: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, str], dict[str, str]]:
    """Formata os candidatos hierarquicamente com IDs locais C1..Cn.

    Retorna:
    - texto_formatado: str
    - local_para_id: dict[str, str] (ex: "C1" -> "M-6f50f4f1dd")
    - id_para_local: dict[str, str] (ex: "M-6f50f4f1dd" -> "C1")
    """
    materias_map: dict[str, dict[str, Any]] = {}
    assuntos_por_materia: dict[str, list[dict[str, Any]]] = {}
    subassuntos_por_assunto: dict[str, list[dict[str, Any]]] = {}

    for no_id, info in candidatos.items():
        nivel = info.get("nivel")
        if nivel == "materia":
            materias_map[no_id] = info
        elif nivel == "assunto":
            m_id = info.get("materia_id") or info.get("pai_id")
            if m_id:
                assuntos_por_materia.setdefault(m_id, []).append(info)
        elif nivel == "subassunto":
            a_id = info.get("assunto_id") or info.get("pai_id")
            if a_id:
                subassuntos_por_assunto.setdefault(a_id, []).append(info)

    # Coleta matérias conhecidas ordenadas por nome
    materias_ordenadas = sorted(materias_map.values(), key=lambda x: x.get("nome", ""))

    local_para_id: dict[str, str] = {}
    id_para_local: dict[str, str] = {}
    linhas: list[str] = []
    contador = 1

    visitados = set()

    for m_info in materias_ordenadas:
        m_id = m_info["id"]
        local_m = f"C{contador}"
        local_para_id[local_m] = m_id
        id_para_local[m_id] = local_m
        contador += 1
        visitados.add(m_id)
        linhas.append(f"[{local_m}] {m_info['nome']} (matéria)")

        assuntos = sorted(
            assuntos_por_materia.get(m_id, []), key=lambda x: x.get("nome", "")
        )
        for a_info in assuntos:
            a_id = a_info["id"]
            local_a = f"C{contador}"
            local_para_id[local_a] = a_id
            id_para_local[a_id] = local_a
            contador += 1
            visitados.add(a_id)
            linhas.append(f"  [{local_a}] {a_info['nome']} (assunto)")

            subs = sorted(
                subassuntos_por_assunto.get(a_id, []),
                key=lambda x: x.get("nome", ""),
            )
            for s_info in subs:
                s_id = s_info["id"]
                local_s = f"C{contador}"
                local_para_id[local_s] = s_id
                id_para_local[s_id] = local_s
                contador += 1
                visitados.add(s_id)
                linhas.append(f"    [{local_s}] {s_info['nome']} (subassunto)")

    # Se restou algum nó fora da hierarquia direta de matérias
    restantes = [n for nid, n in candidatos.items() if nid not in visitados]
    if restantes:
        restantes.sort(key=lambda x: (x.get("nivel", ""), x.get("nome", "")))
        for r_info in restantes:
            r_id = r_info["id"]
            local_r = f"C{contador}"
            local_para_id[local_r] = r_id
            id_para_local[r_id] = local_r
            contador += 1
            nivel = r_info.get("nivel", "nó")
            indent = (
                "    "
                if nivel == "subassunto"
                else ("  " if nivel == "assunto" else "")
            )
            linhas.append(f"{indent}[{local_r}] {r_info['nome']} ({nivel})")

    return "\n".join(linhas), local_para_id, id_para_local


def _pos_validacao_classificacao(
    local_para_id: dict[str, str],
    numeros_esperados: list[int | str],
    ultimo_erro: list[str] | None = None,
):
    """Gancho de pós-validação semântica para chamadas de classificação."""

    def validar(
        resposta: RespostaClassificacaoLote, _content: str
    ) -> ResultadoPosValidacao:
        # 1. Validar IDs locais desconhecidos
        desconhecidos = []
        for it in resposta.itens:
            for lid in it.nos:
                if lid not in local_para_id:
                    desconhecidos.append(lid)
        if desconhecidos:
            msg = (
                f"IDs locais desconhecidos ou inventados: {sorted(set(desconhecidos))}"
            )
            if ultimo_erro is not None:
                ultimo_erro[0] = msg
            return ResultadoPosValidacao(
                motivo=STATUS_FALHA_ID_DESCONHECIDO,
                erro=f"[{STATUS_FALHA_ID_DESCONHECIDO.upper()}] {msg}",
                metadata={
                    "tipo_erro": STATUS_FALHA_ID_DESCONHECIDO,
                    "ids": desconhecidos,
                },
            )

        # 2. Validar divergência de itens
        esperados_set = {str(n).lstrip("D") for n in numeros_esperados}
        recebidos_set = {str(it.numero).lstrip("D") for it in resposta.itens}

        faltando = esperados_set - recebidos_set
        sobrando = recebidos_set - esperados_set
        if faltando or sobrando:
            msg = f"Itens divergentes. Faltando: {sorted(faltando)}, Sobrando: {sorted(sobrando)}"
            if ultimo_erro is not None:
                ultimo_erro[0] = msg
            return ResultadoPosValidacao(
                motivo=STATUS_FALHA_ITENS_DIVERGENTES,
                erro=f"[{STATUS_FALHA_ITENS_DIVERGENTES.upper()}] {msg}",
                metadata={
                    "tipo_erro": STATUS_FALHA_ITENS_DIVERGENTES,
                    "faltando": list(faltando),
                    "sobrando": list(sobrando),
                },
            )

        # 3. Validar integridade individual de cada item
        for it in resposta.itens:
            if it.nenhum_serve:
                if it.nos:
                    msg = (
                        f"Item {it.numero} marcado como 'nenhum_serve=True' "
                        f"mas possui nós atribuídos: {it.nos}"
                    )
                    if ultimo_erro is not None:
                        ultimo_erro[0] = msg
                    return ResultadoPosValidacao(
                        motivo=STATUS_FALHA_VALIDACAO_SCHEMA,
                        erro=f"[{STATUS_FALHA_VALIDACAO_SCHEMA.upper()}] {msg}",
                        metadata={"tipo_erro": STATUS_FALHA_VALIDACAO_SCHEMA},
                    )
            else:
                if not it.nos:
                    msg = f"Item {it.numero} não possui nós e nenhum_serve é False"
                    if ultimo_erro is not None:
                        ultimo_erro[0] = msg
                    return ResultadoPosValidacao(
                        motivo=STATUS_FALHA_VALIDACAO_SCHEMA,
                        erro=f"[{STATUS_FALHA_VALIDACAO_SCHEMA.upper()}] {msg}",
                        metadata={"tipo_erro": STATUS_FALHA_VALIDACAO_SCHEMA},
                    )
                if len(it.nos) > 2:
                    msg = f"Item {it.numero} possui {len(it.nos)} nós (máximo permitido: 2)"
                    if ultimo_erro is not None:
                        ultimo_erro[0] = msg
                    return ResultadoPosValidacao(
                        motivo=STATUS_FALHA_VALIDACAO_SCHEMA,
                        erro=f"[{STATUS_FALHA_VALIDACAO_SCHEMA.upper()}] {msg}",
                        metadata={"tipo_erro": STATUS_FALHA_VALIDACAO_SCHEMA},
                    )
                if len(it.nos) == 2 and it.nos[0] == it.nos[1]:
                    msg = f"Item {it.numero} possui nós duplicados: {it.nos}"
                    if ultimo_erro is not None:
                        ultimo_erro[0] = msg
                    return ResultadoPosValidacao(
                        motivo=STATUS_FALHA_VALIDACAO_SCHEMA,
                        erro=f"[{STATUS_FALHA_VALIDACAO_SCHEMA.upper()}] {msg}",
                        metadata={"tipo_erro": STATUS_FALHA_VALIDACAO_SCHEMA},
                    )

        return ResultadoPosValidacao(objeto=resposta, metadata={"status": "ok"})

    return validar


def montar_prompt_lote(
    caderno_info: dict[str, Any],
    itens: list[dict[str, Any]],
    candidatos_formatados: str,
    texto_base: str | None = None,
    discursiva: bool = False,
) -> str:
    """Monta o prompt de usuário com contexto do caderno, enunciados e árvore."""
    linhas = [
        "CONTEXTO DO CADERNO:",
        f"- Concurso: {caderno_info.get('concurso_slug', '')}",
        f"- Órgão: {caderno_info.get('orgao', '')}",
        f"- Cargos: {', '.join(caderno_info.get('cargos', [])) or 'Todos os cargos'}",
        f"- Tipo de prova: {caderno_info.get('tipo', '')}",
    ]
    niveis = [n for n in caderno_info.get("niveis", []) if n]
    if niveis:
        linhas.append(f"- Nível de escolaridade: {', '.join(sorted(set(niveis)))}")

    secao = itens[0].get("secao")
    if secao and not discursiva:
        linhas.append(f"- Seção do caderno: {secao}")

    if texto_base:
        linhas.extend(
            [
                "",
                "TEXTO-BASE COMPARTILHADO:",
                texto_base.strip(),
            ]
        )

    linhas.extend(
        [
            "",
            "ITENS A CLASSIFICAR:",
        ]
    )

    for it in itens:
        if discursiva:
            num = it.get("numero")
            num_exib = f"D{num}" if not str(num).startswith("D") else str(num)
            titulo = it.get("titulo") or f"Discursiva {num}"
            tema = f" | Tema: {it['tema']}" if it.get("tema") else ""
            linhas.append(f"\n--- Item {num_exib}: {titulo}{tema} ---")
            linhas.append(f"Enunciado:\n{it.get('enunciado', '').strip()}")
            quesitos = it.get("quesitos") or []
            if quesitos:
                linhas.append("Quesitos:")
                for q in quesitos:
                    if isinstance(q, dict):
                        q_num = q.get("numero", "-")
                        q_txt = q.get("texto", "").strip()
                        linhas.append(f"  {q_num}. {q_txt}")
                    else:
                        linhas.append(f"  - {str(q).strip()}")
        else:
            figuras = it.get("figuras") or []
            fig_str = "".join(
                f" [Figura: {f.get('arquivo', '')}]"
                for f in figuras
                if isinstance(f, dict)
            )
            linhas.append(
                f"Item {it['numero']}:{fig_str} {it.get('enunciado', '').strip()}"
            )

    linhas.extend(
        [
            "",
            "CANDIDATOS DISPONÍVEIS NA ÁRVORE (ESCOLHA ENTRE ESTES):",
            candidatos_formatados,
        ]
    )

    return "\n".join(linhas)


def classificar_lote(
    prompt_usuario: str,
    numeros_esperados: list[int | str],
    local_para_id: dict[str, str],
    metadata_base: dict[str, Any],
    conta: Contabilidade,
    dry_run: bool = False,
) -> RespostaClassificacaoLote | None:
    """Executa a chamada ao LLM com até 2 tentativas e feedback de erro."""
    if dry_run:
        logger.info(
            f"[CLASSIFICAR] (dry-run) Lote de {len(numeros_esperados)} itens para {metadata_base.get('caderno')}:\n"
            f"{prompt_usuario[:400]}...\n[Total candidatos: {len(local_para_id)}]"
        )
        return None

    resultado = None
    correcao = ""
    ultimo_erro = [""]
    for tentativa in range(1, TENTATIVAS + 1):
        conta.chamadas += 1
        prompt_envio = prompt_usuario + correcao
        meta = {
            **metadata_base,
            "tentativa": tentativa,
            "itens": len(numeros_esperados),
        }
        resultado = chamar_llm_json(
            PROMPT_SISTEMA,
            prompt_envio,
            RespostaClassificacaoLote,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT,
            reasoning=REASONING_PADRAO,
            extras_payload={"usage": {"include": True}},
            metadata=meta,
            pos_validacao=_pos_validacao_classificacao(
                local_para_id, numeros_esperados, ultimo_erro
            ),
            nome_generation=f"classificar_{metadata_base.get('caderno', 'lote')}",
            nome_trace=llm_openrouter.ETAPA_CLASSIFICACAO_QUESTOES[1],
            api_key=llm_openrouter.chave_openrouter(
                llm_openrouter.ETAPA_CLASSIFICACAO_QUESTOES
            ),
        )
        conta.registrar_usage(resultado.usage)
        if resultado.motivo is None:
            break

        conta.falhas[resultado.motivo] += 1
        if resultado.motivo in (
            STATUS_FALHA_ID_DESCONHECIDO,
            STATUS_FALHA_ITENS_DIVERGENTES,
            STATUS_FALHA_VALIDACAO_SCHEMA,
        ):
            correcao = (
                f"\n\nATENÇÃO: Sua resposta anterior foi rejeitada ({resultado.motivo}). "
                f"Detalhe do erro: {ultimo_erro[0]}\n"
                "Por favor, corrija os seguintes pontos:\n"
                f"- Responda com um objeto para CADA um dos itens esperados: {numeros_esperados}.\n"
                "- Utilize ESTRITAMENTE os IDs locais [C1, C2, ...] da árvore de candidatos fornecida.\n"
                "- Atribua no máximo 2 nós (1 principal, 1 secundário opcional se interdisciplinar).\n"
                '- Caso nenhum nó sirva para o item, marque "nenhum_serve": true e "nos": [].'
            )
        if tentativa < TENTATIVAS:
            time.sleep(BACKOFF_SEGUNDOS)

    if resultado is None or resultado.motivo is not None:
        conta.lotes_falhos += 1
        logger.error(
            f"[CLASSIFICAR] Lote falhou ({resultado.motivo if resultado else 'sem_resultado'})."
        )
        return None

    conta.lotes_ok += 1
    return resultado.objeto


def carregar_dados_caderno(
    conn, prova_id: int
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[int, str]]:
    """Carrega dados completos do caderno (questões ou discursivas e textos-base)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.codigo_caderno, p.arquivo, p.identificador, p.tipo,
                   c.slug, o.sigla,
                   array_agg(DISTINCT ce.nome) FILTER (WHERE ce.nome IS NOT NULL) AS cargos,
                   array_agg(DISTINCT ce.nivel) FILTER (WHERE ce.nivel IS NOT NULL) AS niveis
            FROM provas p
            JOIN concursos c ON c.id = p.concurso_id
            JOIN dim_orgao o ON o.id = c.orgao_id
            LEFT JOIN provas_cargos pc ON pc.prova_id = p.id
            LEFT JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id
            WHERE p.id = %s
            GROUP BY p.id, p.codigo_caderno, p.arquivo, p.identificador, p.tipo, c.slug, o.sigla
            """,
            (prova_id,),
        )
        row = cur.fetchone()
        if not row:
            return {}, [], {}

        cad_nome = nome_caderno(
            {
                "slug": row[5],
                "codigo_caderno": row[1],
                "arquivo": row[2],
                "identificador": row[3],
            }
        )
        info = {
            "prova_id": row[0],
            "codigo_caderno": row[1],
            "arquivo": row[2],
            "identificador": row[3],
            "tipo": row[4],
            "concurso_slug": row[5],
            "orgao": row[6],
            "cargos": row[7] or [],
            "niveis": row[8] or [],
            "nome_caderno": cad_nome,
        }

        tipo = info["tipo"]
        itens: list[dict[str, Any]] = []
        textos_map: dict[int, str] = {}

        if tipo == "discursiva":
            cur.execute(
                """
                SELECT id, numero, titulo, tema, enunciado, quesitos
                FROM discursivas
                WHERE prova_id = %s
                ORDER BY numero
                """,
                (prova_id,),
            )
            for d_id, num, tit, tema, enun, ques in cur.fetchall():
                itens.append(
                    {
                        "id": d_id,
                        "numero": num,
                        "titulo": tit,
                        "tema": tema,
                        "enunciado": enun,
                        "quesitos": ques,
                    }
                )
        else:
            cur.execute(
                """
                SELECT id, texto, figuras
                FROM textos_base
                WHERE prova_id = %s
                """,
                (prova_id,),
            )
            for tb_id, tb_txt, tb_figs in cur.fetchall():
                fig_str = "".join(
                    f" [Figura: {f.get('arquivo', '')}]"
                    for f in (tb_figs or [])
                    if isinstance(f, dict)
                )
                textos_map[tb_id] = f"{tb_txt or ''}{fig_str}".strip() if tb_txt else ""

            cur.execute(
                """
                SELECT id, numero, enunciado, secao, texto_base_id, figuras, utilizavel
                FROM questoes
                WHERE prova_id = %s
                ORDER BY numero
                """,
                (prova_id,),
            )
            for q_id, num, enun, sec, tb_id, figs, util in cur.fetchall():
                itens.append(
                    {
                        "id": q_id,
                        "numero": num,
                        "enunciado": enun,
                        "secao": sec,
                        "texto_base_id": tb_id,
                        "figuras": figs,
                        "utilizavel": util,
                    }
                )

        return info, itens, textos_map


def _tem_decisao_do_dono(reg: classificacao.RegistroQuestao) -> bool:
    """Registro com apontamento humano, aprovado ou rejeitado nunca é reclassificado.

    Só um hash de enunciado diferente (texto reextraído) reabre o registro.
    """
    return any(
        ap.origem == "humano" or ap.status in ("aprovado", "rejeitado")
        for ap in reg.apontamentos
    )


def processar_caderno(
    conn,
    prova_id: int,
    arv: arvore.ArvoreMestre,
    cq: classificacao.ClassificacaoQuestoes,
    conta: Contabilidade,
    dry_run: bool = False,
    reclassificar: bool = False,
    limite: int | None = None,
    classificacao_path: Path = CLASSIFICACAO_PATH_PADRAO,
) -> int:
    """Processa a classificação de um caderno completo (Passada 1 Preferencial + Passada 2 Reserva)."""
    cad_info, itens, textos_map = carregar_dados_caderno(conn, prova_id)
    if not cad_info or not itens:
        return 0

    slug = cad_info["concurso_slug"]
    cad_nome = cad_info["nome_caderno"]
    is_discursiva = cad_info["tipo"] == "discursiva"

    logger.info(
        f"[CLASSIFICAR] Caderno {cad_nome} ({cad_info['tipo']}): {len(itens)} itens."
    )

    # 1. Candidatos preferenciais
    cands_pref = candidatos_questao.candidatos_preferenciais(conn, prova_id)
    if not cands_pref:
        logger.warning(
            f"[CLASSIFICAR] {cad_nome}: nenhum candidato preferencial encontrado!"
        )
        return 0

    prompt_cands_pref, local_para_id_pref, _ = formatar_arvore_candidatos(cands_pref)

    # 2. Agrupamento em lotes
    if is_discursiva:
        lotes = [itens]
    else:
        lotes = candidatos_questao.montar_lotes(itens, max_tamanho=10)

    itens_para_reserva: list[dict[str, Any]] = []
    lotes_processados = 0

    for lote in lotes:
        if limite is not None and lotes_processados >= limite:
            break

        # Filtra itens elegíveis por idempotência
        itens_a_classificar: list[dict[str, Any]] = []
        for it in lote:
            num = it["numero"]
            chave = classificacao.chave_questao(
                slug, cad_nome, num, discursiva=is_discursiva
            )
            h = classificacao.calcular_hash_enunciado(it.get("enunciado", ""))

            reg = cq.registros.get(chave)
            if (
                reg is not None
                and reg.hash_enunciado == h
                and (
                    _tem_decisao_do_dono(reg)
                    or (
                        not reclassificar
                        and (
                            reg.sem_no
                            or any(ap.status == "proposto" for ap in reg.apontamentos)
                        )
                    )
                )
            ):
                conta.itens_pulados_idempotencia += 1
                continue

            itens_a_classificar.append(it)

        if not itens_a_classificar:
            continue

        lotes_processados += 1
        tb_id = itens_a_classificar[0].get("texto_base_id")
        texto_base = textos_map.get(tb_id) if tb_id is not None else None

        nums_esperados = [
            it["numero"]
            if not is_discursiva
            else (
                f"D{it['numero']}"
                if not str(it["numero"]).startswith("D")
                else str(it["numero"])
            )
            for it in itens_a_classificar
        ]

        prompt_user = montar_prompt_lote(
            cad_info,
            itens_a_classificar,
            prompt_cands_pref,
            texto_base=texto_base,
            discursiva=is_discursiva,
        )

        resp = classificar_lote(
            prompt_user,
            nums_esperados,
            local_para_id_pref,
            metadata_base={
                "caderno": cad_nome,
                "passada": "preferencial",
                "tipo": cad_info["tipo"],
            },
            conta=conta,
            dry_run=dry_run,
        )

        if dry_run or resp is None:
            continue

        mapa_itens_lote = {
            str(it["numero"]).lstrip("D"): it for it in itens_a_classificar
        }

        for item_resp in resp.itens:
            chave_num = str(item_resp.numero).lstrip("D")
            it_orig = mapa_itens_lote.get(chave_num)
            if not it_orig:
                continue

            chave = classificacao.chave_questao(
                slug, cad_nome, it_orig["numero"], discursiva=is_discursiva
            )
            h = classificacao.calcular_hash_enunciado(it_orig.get("enunciado", ""))

            if item_resp.nenhum_serve:
                itens_para_reserva.append(it_orig)
            else:
                nos_reais = [local_para_id_pref[lid] for lid in item_resp.nos]
                nos_com_papeis = [
                    (
                        no_id,
                        "principal" if i == 0 else "secundario",
                        False,  # fora_do_edital = False na preferencial
                    )
                    for i, no_id in enumerate(nos_reais)
                ]
                classificacao.mapear_questao(
                    cq,
                    arv,
                    chave=chave,
                    hash_enunciado=h,
                    nos=nos_com_papeis,
                    confianca=item_resp.confianca,
                    fora_do_edital=False,
                    origem="llm",
                    status="proposto",
                )
                conta.distribuicao_confianca[item_resp.confianca] += 1
                conta.itens_classificados += 1

        # Checkpoint por lote
        classificacao.salvar(cq, classificacao_path)

    # 3. Passada de Reserva (para itens com nenhum_serve)
    if itens_para_reserva and not dry_run:
        logger.info(
            f"[CLASSIFICAR] {cad_nome}: {len(itens_para_reserva)} item(ns) na passada de reserva."
        )
        materias_ids = {
            c["materia_id"] for c in cands_pref.values() if c.get("materia_id")
        }
        cands_res = candidatos_questao.candidatos_reserva(arv, materias_ids)

        if not cands_res:
            logger.warning(
                f"[CLASSIFICAR] {cad_nome}: reserva vazia para matérias {materias_ids}. Registrando sem_no."
            )
            for it in itens_para_reserva:
                chave = classificacao.chave_questao(
                    slug, cad_nome, it["numero"], discursiva=is_discursiva
                )
                h = classificacao.calcular_hash_enunciado(it.get("enunciado", ""))
                classificacao.mapear_questao(
                    cq,
                    arv,
                    chave=chave,
                    hash_enunciado=h,
                    nos=[],
                    origem="llm",
                    status="proposto",
                )
                conta.total_sem_no += 1
            classificacao.salvar(cq, classificacao_path)
        else:
            prompt_cands_res, local_para_id_res, _ = formatar_arvore_candidatos(
                cands_res
            )

            # Divide os itens de reserva em blocos de 10
            for i in range(0, len(itens_para_reserva), 10):
                bloco_res = itens_para_reserva[i : i + 10]
                nums_res = [
                    it["numero"]
                    if not is_discursiva
                    else (
                        f"D{it['numero']}"
                        if not str(it["numero"]).startswith("D")
                        else str(it["numero"])
                    )
                    for it in bloco_res
                ]

                # Se todos tiverem o mesmo TB
                tb_id = bloco_res[0].get("texto_base_id")
                texto_base = textos_map.get(tb_id) if tb_id is not None else None

                prompt_user_res = montar_prompt_lote(
                    cad_info,
                    bloco_res,
                    prompt_cands_res,
                    texto_base=texto_base,
                    discursiva=is_discursiva,
                )

                resp_res = classificar_lote(
                    prompt_user_res,
                    nums_res,
                    local_para_id_res,
                    metadata_base={
                        "caderno": cad_nome,
                        "passada": "reserva",
                        "tipo": cad_info["tipo"],
                    },
                    conta=conta,
                    dry_run=dry_run,
                )

                if resp_res is None:
                    continue

                mapa_bloco_res = {str(it["numero"]).lstrip("D"): it for it in bloco_res}

                for item_resp in resp_res.itens:
                    chave_num = str(item_resp.numero).lstrip("D")
                    it_orig = mapa_bloco_res.get(chave_num)
                    if not it_orig:
                        continue

                    chave = classificacao.chave_questao(
                        slug,
                        cad_nome,
                        it_orig["numero"],
                        discursiva=is_discursiva,
                    )
                    h = classificacao.calcular_hash_enunciado(
                        it_orig.get("enunciado", "")
                    )

                    if item_resp.nenhum_serve:
                        # Permanece sem nó (ADR-030 §5)
                        classificacao.mapear_questao(
                            cq,
                            arv,
                            chave=chave,
                            hash_enunciado=h,
                            nos=[],
                            origem="llm",
                            status="proposto",
                        )
                        conta.total_sem_no += 1
                        logger.info(
                            f"[CLASSIFICAR] {chave}: registrado como sem_no após reserva."
                        )
                    else:
                        nos_reais = [local_para_id_res[lid] for lid in item_resp.nos]
                        nos_com_papeis = [
                            (
                                no_id,
                                "principal" if j == 0 else "secundario",
                                True,  # fora_do_edital = True na reserva!
                            )
                            for j, no_id in enumerate(nos_reais)
                        ]
                        classificacao.mapear_questao(
                            cq,
                            arv,
                            chave=chave,
                            hash_enunciado=h,
                            nos=nos_com_papeis,
                            confianca=item_resp.confianca,
                            fora_do_edital=True,
                            origem="llm",
                            status="proposto",
                        )
                        conta.total_fora_edital += 1
                        conta.distribuicao_confianca[item_resp.confianca] += 1
                        conta.itens_classificados += 1

                classificacao.salvar(cq, classificacao_path)

    return lotes_processados


def classificar_todas_questoes(
    caderno: str | None = None,
    dry_run: bool = False,
    limite: int | None = None,
    reclassificar: bool = False,
    arvore_path: Path = ARVORE_PATH_PADRAO,
    classificacao_path: Path = CLASSIFICACAO_PATH_PADRAO,
    conn=None,
) -> Contabilidade:
    """Orquestrador principal para classificação dos cadernos."""
    arv = arvore.carregar(arvore_path)
    cq = (
        classificacao.carregar(classificacao_path)
        if not dry_run
        else classificacao.ClassificacaoQuestoes()
    )
    conta = Contabilidade()

    proprio_conn = conn is None
    conn = conn or conectar()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.codigo_caderno, p.arquivo, p.identificador, c.slug
                FROM provas p
                JOIN concursos c ON c.id = p.concurso_id
                ORDER BY c.slug, p.id
                """
            )
            provas = cur.fetchall()

        cadernos_alvo: list[int] = []
        for pid, cod_cad, arq, ident, slug in provas:
            nome = nome_caderno(
                {
                    "slug": slug,
                    "codigo_caderno": cod_cad,
                    "arquivo": arq,
                    "identificador": ident,
                }
            )
            if (
                caderno is not None
                and caderno != nome
                and caderno != cod_cad
                and caderno != arq
                and caderno != ident
            ):
                continue
            cadernos_alvo.append(pid)

        logger.info(
            f"[CLASSIFICAR] Total de provas/cadernos selecionados: {len(cadernos_alvo)}"
        )

        lotes_acumulados = 0
        for pid in cadernos_alvo:
            if limite is not None and lotes_acumulados >= limite:
                break
            limite_restante = (
                (limite - lotes_acumulados) if limite is not None else None
            )
            processados = processar_caderno(
                conn,
                pid,
                arv,
                cq,
                conta,
                dry_run=dry_run,
                reclassificar=reclassificar,
                limite=limite_restante,
                classificacao_path=classificacao_path,
            )
            lotes_acumulados += processados

        if not dry_run:
            classificacao.salvar(cq, classificacao_path)

        logger.info(
            f"[CLASSIFICAR] Concluído! Chamadas: {conta.chamadas} | Lotes OK: {conta.lotes_ok} | Falhas: {conta.lotes_falhos}\n"
            f"Tokens entrada: {conta.tokens_entrada} | saída: {conta.tokens_saida} | Custo USD: ${conta.custo_usd:.4f}\n"
            f"Itens classificados: {conta.itens_classificados} | Fora do edital: {conta.total_fora_edital} | Sem nó: {conta.total_sem_no}\n"
            f"Confiança: {dict(conta.distribuicao_confianca)} | Pulados idempotência: {conta.itens_pulados_idempotencia}"
        )
        return conta
    finally:
        if proprio_conn:
            conn.close()


def main(args_list: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Classifica questões de concursos na árvore mestre via LLM"
    )
    parser.add_argument(
        "--caderno",
        help="Restringe a execução a um caderno específico (ex: 094_PF_CB1_01)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Exibe prompts e candidatos sem efetuar chamadas ao LLM nem gravar",
    )
    parser.add_argument(
        "--limite",
        type=int,
        help="Limita a quantidade de lotes a processar",
    )
    parser.add_argument(
        "--reclassificar",
        action="store_true",
        help="Força reavaliação de questões já classificadas com mesmo hash",
    )
    parser.add_argument(
        "--arvore",
        type=Path,
        default=ARVORE_PATH_PADRAO,
        help="Caminho do arquivo arvore.json",
    )
    parser.add_argument(
        "--classificacao",
        type=Path,
        default=CLASSIFICACAO_PATH_PADRAO,
        help="Caminho do arquivo classificacao_questoes.json",
    )
    args = parser.parse_args(args_list)

    conta = classificar_todas_questoes(
        caderno=args.caderno,
        dry_run=args.dry_run,
        limite=args.limite,
        reclassificar=args.reclassificar,
        arvore_path=args.arvore,
        classificacao_path=args.classificacao,
    )

    saida = {
        "chamadas": conta.chamadas,
        "lotes_ok": conta.lotes_ok,
        "lotes_falhos": conta.lotes_falhos,
        "tokens_entrada": conta.tokens_entrada,
        "tokens_saida": conta.tokens_saida,
        "custo_usd": conta.custo_usd,
        "itens_classificados": conta.itens_classificados,
        "total_fora_edital": conta.total_fora_edital,
        "total_sem_no": conta.total_sem_no,
        "distribuicao_confianca": dict(conta.distribuicao_confianca),
        "falhas": dict(conta.falhas),
    }
    print(json.dumps(saida, indent=2))


if __name__ == "__main__":
    main()
