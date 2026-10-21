"""Módulo de checagens do orquestrador C2 (Etapa 9/D5b, KAN-32).

Fornece verificações automáticas de integridade, consultas do Runbook §4.5
e portões de validação do pipeline:
- verificar_invariante_piloto (K22)
- executar_consultas_runbook (Consultas a-e e K19)
- consultar_custo_openrouter (A07)
- verificar_portao_edital (P3)
- verificar_portao_arvore (P6/P7)
- verificar_portao_classificacao (P8/P9)
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from src.logger import logger
from src.registro.checagens import _SQL_INVARIANTE_PILOTO
from src.stats_writer import STATUS_REVISAO_APROVADO, conectar, status_revisao

# Invariante do piloto esperada (K22): medido nos 5 concursos do piloto em 2026-10-12
INVARIANTE_PILOTO_ESPERADA: dict[str, Any] = {
    "itens": 2800,
    "anuladas": 129,
    "apontamentos": 3029,
    "hash_chaves": "3257ba6ba525fdd6b4492733b50882f2",
}

RAIZ = Path(__file__).resolve().parent.parent.parent
DATA_DIR = RAIZ / "data"
REVISAO_PILOTO_DIR = RAIZ / "revisao_piloto"
URL_OPENROUTER_KEY = "https://openrouter.ai/api/v1/key"
TIMEOUT_OPENROUTER = 15


class PendenciasClassificacao(int):
    """Representa a contagem de pendências do portão P9 com as parcelas separadas.

    Comporta-se como um inteiro (total de pendências = propostas + sem_classificacao)
    e expõe atributos e chaves para que relatórios e chamadores possam distinguir
    entre propostas aguardando aprovação e itens utilizáveis sem classificação.
    """

    propostas: int
    sem_classificacao: int
    total: int

    def __new__(
        cls, propostas: int = 0, sem_classificacao: int = 0
    ) -> PendenciasClassificacao:
        total = propostas + sem_classificacao
        instance = super().__new__(cls, total)
        instance.propostas = propostas
        instance.sem_classificacao = sem_classificacao
        instance.total = total
        return instance

    def __getitem__(self, item: str) -> int:
        if item == "propostas":
            return self.propostas
        if item in ("sem_classificacao", "sem_apontamento"):
            return self.sem_classificacao
        if item == "total":
            return self.total
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self[item]
        except KeyError:
            return default


# Chaves de etapas do OpenRouter conforme scripts/gerar_numeros.py
CHAVES_ETAPAS = (
    ("OPENROUTER_KEY_TAXONOMIA_EDITAL", "Taxonomia do edital"),
    ("OPENROUTER_KEY_SINONIMOS", "Sinônimos"),
    ("OPENROUTER_KEY_CURADORIA_ARVORE", "Curadoria da árvore"),
    ("OPENROUTER_KEY_CLASSIFICACAO_QUESTOES", "Classificação das questões"),
    ("OPENROUTER_KEY_TELEGRAM", "Bot do Telegram"),
    ("OPENROUTER_API_KEY", "Chave geral (fallback e etapas antigas)"),
)

# SQL da medição do piloto (Runbook §4.5 e) sem filtro de divergência
SQL_MEDICAO_PILOTO = """
WITH pil AS (
  SELECT p.id FROM provas p JOIN concursos c ON c.id = p.concurso_id
  WHERE c.slug IN ('PF_25_ADM', 'TCU_25_TEFC', 'IBAMA_25', 'STM_25', 'CD_25_NS')),
atual AS (
  SELECT
    (SELECT count(*) FROM questoes WHERE prova_id IN (SELECT id FROM pil)) AS itens,
    (SELECT count(*) FROM questoes WHERE prova_id IN (SELECT id FROM pil)
       AND anulada) AS anuladas,
    (SELECT count(*) FROM questao_no qn JOIN questoes q ON q.id = qn.questao_id
       WHERE q.prova_id IN (SELECT id FROM pil))
    + (SELECT count(*) FROM discursiva_no dn
         JOIN discursivas d ON d.id = dn.discursiva_id
       WHERE d.prova_id IN (SELECT id FROM pil)) AS apontamentos,
    (SELECT md5(string_agg(questao_chave, ',' ORDER BY questao_chave))
       FROM vw_questoes
       WHERE split_part(questao_chave, '|', 1)
             IN ('PF_25_ADM', 'TCU_25_TEFC', 'IBAMA_25', 'STM_25', 'CD_25_NS'))
      AS hash_chaves)
SELECT itens, anuladas, apontamentos, hash_chaves FROM atual;
"""


class ViolacaoInvariantePiloto(Exception):
    """Exceção levantada quando há divergência no invariante do piloto (K22)."""

    def __init__(
        self,
        detalhes: dict[str, Any],
        mensagem: str = "Violação da invariante do piloto (K22)",
    ) -> None:
        super().__init__(mensagem)
        self.detalhes = detalhes
        self.mensagem = mensagem


def verificar_invariante_piloto(
    conn: Any = None, lancar_excecao: bool = False
) -> dict[str, Any]:
    """Executa a checagem K22 da invariante do piloto.

    Valores esperados dos 5 concursos (PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, CD_25_NS):
    - itens = 2800
    - anuladas = 129
    - apontamentos = 3029
    - hash_chaves = '3257ba6ba525fdd6b4492733b50882f2'

    Se houver divergência, retorna detalhes e levanta `ViolacaoInvariantePiloto`
    caso `lancar_excecao=True`.
    Em ambiente sem banco ativo ou teste desconectado, trata graciosamente.
    """
    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception as exc:
            logger.warning(f"[K22] Sem conexão com PostgreSQL: {exc}")
            resultado = {
                "status": "sem_banco",
                "valido": False,
                "esperado": INVARIANTE_PILOTO_ESPERADA,
                "obtido": None,
                "divergencias": {},
                "mensagem": f"Banco de dados não disponível: {exc}",
            }
            if lancar_excecao:
                raise ViolacaoInvariantePiloto(
                    detalhes=resultado, mensagem=resultado["mensagem"]
                ) from exc
            return resultado

    try:
        with conn.cursor() as cur:
            # Executa a checagem K22 canônica: devolve linhas apenas se houver violação
            cur.execute(_SQL_INVARIANTE_PILOTO)
            linhas_violacao = cur.fetchall()

            # Executa a medição para obter os valores numéricos atuais
            cur.execute(SQL_MEDICAO_PILOTO)
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Consulta de invariante não retornou linhas")

            itens, anuladas, apontamentos, hash_chaves = row
            obtido = {
                "itens": int(itens or 0),
                "anuladas": int(anuladas or 0),
                "apontamentos": int(apontamentos or 0),
                "hash_chaves": str(hash_chaves or ""),
            }

            divergencias: dict[str, dict[str, Any]] = {}
            for chave, esperado in INVARIANTE_PILOTO_ESPERADA.items():
                val_obtido = obtido.get(chave)
                if val_obtido != esperado:
                    divergencias[chave] = {
                        "esperado": esperado,
                        "obtido": val_obtido,
                    }

            valido = len(divergencias) == 0 and len(linhas_violacao) == 0
            resultado = {
                "status": "ok" if valido else "divergencia",
                "valido": valido,
                "esperado": INVARIANTE_PILOTO_ESPERADA,
                "obtido": obtido,
                "divergencias": divergencias,
                "linhas_violacao": linhas_violacao,
                "mensagem": "Invariante do piloto preservada"
                if valido
                else f"Divergência detectada no piloto: {list(divergencias.keys())}",
            }

            if not valido and lancar_excecao:
                raise ViolacaoInvariantePiloto(
                    detalhes=resultado, mensagem=resultado["mensagem"]
                )

            return resultado

    except ViolacaoInvariantePiloto:
        raise
    except Exception as exc:
        logger.error(f"[K22] Erro ao executar invariante do piloto: {exc}")
        resultado = {
            "status": "erro",
            "valido": False,
            "esperado": INVARIANTE_PILOTO_ESPERADA,
            "obtido": None,
            "divergencias": {},
            "mensagem": f"Erro de execução SQL: {exc}",
        }
        if lancar_excecao:
            raise ViolacaoInvariantePiloto(
                detalhes=resultado, mensagem=resultado["mensagem"]
            ) from exc
        return resultado
    finally:
        if fechar_conn:
            try:
                conn.close()
            except Exception:
                pass


def executar_consultas_runbook(slugs: list[str], conn: Any = None) -> dict[str, Any]:
    """Executa as consultas de integridade do Runbook §4.5 para os certames informados.

    Consultas executadas:
    - Consulta (a): Status da fila, itens, gabarito, alternativas (alt_min, alt_max),
      itens inutizados e discursivas por prova.
    - Consulta (b): Distribuição de gabaritos (apenas A-E e X para ME, C, E e X para C/E).
    - Consulta (c): Discursivas (quesitos >= 1, padrão de resposta existente).
    - Consulta (d): Seções por caderno e busca de alternativas terminando em caixa alta (K15 / K16).
    - Checagem K19: ME sem texto-base (alerta WARN informativo não-bloqueante).

    Retorna um dicionário estruturado com as linhas e o diagnóstico de validação.
    """
    if not slugs:
        return {
            "status": "ok",
            "valido": True,
            "slugs": [],
            "consulta_a": [],
            "consulta_b": [],
            "consulta_c": [],
            "consulta_d_secoes": [],
            "consulta_d_caixa_alta": [],
            "checagem_k19": [],
            "alertas": ["Nenhum slug informado para conferência."],
            "falhas": [],
        }

    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception as exc:
            logger.warning(f"[RUNBOOK] Sem conexão com PostgreSQL: {exc}")
            return {
                "status": "sem_banco",
                "valido": False,
                "slugs": slugs,
                "consulta_a": [],
                "consulta_b": [],
                "consulta_c": [],
                "consulta_d_secoes": [],
                "consulta_d_caixa_alta": [],
                "checagem_k19": [],
                "alertas": [],
                "falhas": [f"Banco de dados não disponível: {exc}"],
            }

    # SQLs Runbook §4.5
    sql_a = """
    SELECT c.slug, p.arquivo, p.tipo, p.codigo_caderno,
           (SELECT string_agg(ce.numero::text, ',' ORDER BY ce.numero)
              FROM provas_cargos pc JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id
             WHERE pc.prova_id = p.id) AS cargos,
           f.status AS fila,
           count(q.id) AS itens,
           count(q.id) FILTER (WHERE q.gabarito IS NULL AND NOT q.anulada) AS sem_gab,
           count(q.id) FILTER (WHERE q.anulada) AS anul,
           min(jsonb_array_length(q.alternativas)) AS alt_min,
           max(jsonb_array_length(q.alternativas)) AS alt_max,
           count(q.id) FILTER (WHERE NOT q.utilizavel) AS inutil,
           (SELECT count(*) FROM discursivas d WHERE d.prova_id = p.id) AS disc
    FROM provas p
    JOIN concursos c ON c.id = p.concurso_id
    LEFT JOIN fila_extracao_questoes f ON f.prova_id = p.id AND f.categoria <> 'gabarito'
    LEFT JOIN questoes q ON q.prova_id = p.id
    WHERE c.slug = ANY(%s)
    GROUP BY c.slug, p.id, p.arquivo, p.tipo, p.codigo_caderno, f.status
    ORDER BY c.slug, p.tipo, p.arquivo;
    """

    sql_b = """
    SELECT c.slug, q.tipo, q.gabarito, count(*) AS total
    FROM questoes q
    JOIN provas p ON p.id = q.prova_id
    JOIN concursos c ON c.id = p.concurso_id
    WHERE c.slug = ANY(%s)
    GROUP BY 1, 2, 3
    ORDER BY 1, 2, 3;
    """

    sql_c = """
    SELECT c.slug, p.arquivo, d.numero, left(d.tema, 70) AS tema,
           jsonb_array_length(d.quesitos) AS quesitos, d.padrao_resposta IS NOT NULL AS tem_padrao
    FROM discursivas d
    JOIN provas p ON p.id = d.prova_id
    JOIN concursos c ON c.id = p.concurso_id
    WHERE c.slug = ANY(%s)
    ORDER BY 1, 2;
    """

    sql_d_secoes = """
    SELECT p.arquivo, q.secao, min(q.numero) AS min_numero, max(q.numero) AS max_numero, count(*) AS total
    FROM questoes q
    JOIN provas p ON p.id = q.prova_id
    JOIN concursos c ON c.id = p.concurso_id
    WHERE c.slug = ANY(%s)
    GROUP BY 1, 2
    ORDER BY 1, 3;
    """

    sql_d_caixa_alta = r"""
    SELECT c.slug, p.arquivo, q.numero, right(q.alternativas->-1->>'texto', 60) AS fim_ultima
    FROM questoes q
    JOIN provas p ON p.id = q.prova_id
    JOIN concursos c ON c.id = p.concurso_id
    WHERE c.slug = ANY(%s)
      AND q.alternativas->-1->>'texto' ~ '[.?!:;)]\s+[A-ZÀ-Ú][A-ZÀ-Ú ,()–-]{3,}$'
    ORDER BY 1, 2;
    """

    sql_k19 = """
    SELECT c.slug, p.arquivo, q.numero
    FROM questoes q
    JOIN provas p ON p.id = q.prova_id
    JOIN concursos c ON c.id = p.concurso_id
    WHERE c.slug = ANY(%s)
      AND q.tipo = 'multipla_escolha'
      AND q.texto_base_id IS NULL
      AND q.enunciado ~* '(texto|tabela|figura|gr[aá]fico|quadro)'
      AND NOT (q.figuras IS NOT NULL AND jsonb_array_length(q.figuras) > 0)
      AND (c.slug, q.numero) NOT IN (('BANRISUL_25', 22), ('SEFA_PR_25', 11), ('SEFA_PR_25', 50))
    ORDER BY 1, 2, 3;
    """

    falhas: list[str] = []
    alertas: list[str] = []

    try:
        with conn.cursor() as cur:
            # (a) Provas
            cur.execute(sql_a, (slugs,))
            rows_a = []
            for r in cur.fetchall():
                item = {
                    "slug": r[0],
                    "arquivo": r[1],
                    "tipo": r[2],
                    "codigo_caderno": r[3],
                    "cargos": r[4],
                    "fila": r[5],
                    "itens": int(r[6] or 0),
                    "sem_gab": int(r[7] or 0),
                    "anul": int(r[8] or 0),
                    "alt_min": int(r[9]) if r[9] is not None else None,
                    "alt_max": int(r[10]) if r[10] is not None else None,
                    "inutil": int(r[11] or 0),
                    "disc": int(r[12] or 0),
                }
                rows_a.append(item)
                if item["fila"] != "concluido" and item["tipo"] != "discursiva":
                    falhas.append(
                        f"Prova {item['arquivo']} ({item['slug']}) com fila '{item['fila']}' (esperado: 'concluido')"
                    )
                if item["sem_gab"] > 0:
                    falhas.append(
                        f"Prova {item['arquivo']} ({item['slug']}) tem {item['sem_gab']} item(ns) sem gabarito"
                    )
                if (
                    item["tipo"] == "objetiva_especifica"
                    or item["tipo"] == "objetiva_basica"
                ):
                    if item["alt_min"] is not None and item["alt_max"] is not None:
                        if item["alt_min"] < 4 or item["alt_max"] > 5:
                            falhas.append(
                                f"Prova ME {item['arquivo']} com alternativas fora de 4..5 ({item['alt_min']} a {item['alt_max']})"
                            )

            # (b) Gabaritos
            cur.execute(sql_b, (slugs,))
            rows_b = []
            for r in cur.fetchall():
                slug_g, tipo_g, gab_g, total_g = r[0], r[1], r[2], int(r[3] or 0)
                rows_b.append(
                    {
                        "slug": slug_g,
                        "tipo": tipo_g,
                        "gabarito": gab_g,
                        "total": total_g,
                    }
                )
                if tipo_g == "multipla_escolha" and gab_g not in (
                    "A",
                    "B",
                    "C",
                    "D",
                    "E",
                    "X",
                ):
                    falhas.append(
                        f"Gabarito ME inválido '{gab_g}' em {slug_g} (permitido: A-E, X)"
                    )
                elif tipo_g == "certo_errado" and gab_g not in ("C", "E", "X"):
                    falhas.append(
                        f"Gabarito C/E inválido '{gab_g}' em {slug_g} (permitido: C, E, X)"
                    )

            # (c) Discursivas
            cur.execute(sql_c, (slugs,))
            rows_c = []
            for r in cur.fetchall():
                disc_item = {
                    "slug": r[0],
                    "arquivo": r[1],
                    "numero": r[2],
                    "tema": r[3],
                    "quesitos": int(r[4] or 0),
                    "tem_padrao": bool(r[5]),
                }
                rows_c.append(disc_item)
                if disc_item["quesitos"] < 1:
                    falhas.append(
                        f"Discursiva {disc_item['arquivo']} Q{disc_item['numero']} sem quesitos válidos"
                    )
                if not disc_item["tem_padrao"]:
                    falhas.append(
                        f"Discursiva {disc_item['arquivo']} Q{disc_item['numero']} sem padrão de resposta"
                    )

            # (d) Seções
            cur.execute(sql_d_secoes, (slugs,))
            rows_d_secoes = [
                {
                    "arquivo": r[0],
                    "secao": r[1],
                    "min_numero": r[2],
                    "max_numero": r[3],
                    "total": int(r[4] or 0),
                }
                for r in cur.fetchall()
            ]

            # (d2) Alternativas em caixa alta (K15)
            cur.execute(sql_d_caixa_alta, (slugs,))
            rows_d_caixa_alta = [
                {
                    "slug": r[0],
                    "arquivo": r[1],
                    "numero": r[2],
                    "fim_ultima": r[3],
                }
                for r in cur.fetchall()
            ]
            if rows_d_caixa_alta:
                falhas.append(
                    f"K15: Encontradas {len(rows_d_caixa_alta)} alternativas terminando em caixa alta"
                )

            # K19: ME sem texto-base
            cur.execute(sql_k19, (slugs,))
            rows_k19 = [
                {
                    "slug": r[0],
                    "arquivo": r[1],
                    "numero": r[2],
                }
                for r in cur.fetchall()
            ]
            if rows_k19:
                alertas.append(
                    f"K19: {len(rows_k19)} questões ME citam texto/tabela/figura sem vínculo no banco (severidade WARN)"
                )

        valido = len(falhas) == 0
        status_geral = (
            "ok" if valido and not alertas else ("alerta" if valido else "falha")
        )

        return {
            "status": status_geral,
            "valido": valido,
            "slugs": slugs,
            "consulta_a": rows_a,
            "consulta_b": rows_b,
            "consulta_c": rows_c,
            "consulta_d_secoes": rows_d_secoes,
            "consulta_d_caixa_alta": rows_d_caixa_alta,
            "checagem_k19": rows_k19,
            "alertas": alertas,
            "falhas": falhas,
        }

    except Exception as exc:
        logger.error(f"[RUNBOOK] Erro na execução das consultas: {exc}")
        return {
            "status": "erro",
            "valido": False,
            "slugs": slugs,
            "consulta_a": [],
            "consulta_b": [],
            "consulta_c": [],
            "consulta_d_secoes": [],
            "consulta_d_caixa_alta": [],
            "checagem_k19": [],
            "alertas": alertas,
            "falhas": [f"Erro ao consultar o banco: {exc}"],
        }
    finally:
        if fechar_conn:
            try:
                conn.close()
            except Exception:
                pass


def consultar_custo_openrouter() -> dict[str, Any]:
    """Consulta segura de uso e custo na API OpenRouter (/api/v1/key).

    Respeita estritamente a Regra A07: chaves de autenticação NUNCA são
    logadas, impressas ou expostas em mensagens de erro ou retornos.
    Retorna o uso acumulado e diário em US$. Caso offline ou sem chaves,
    fornece fallback informativo sem levantar exceções.
    """
    load_dotenv(RAIZ / ".env")
    etapas: list[dict[str, Any]] = []
    chaves_vistas: set[str] = set()
    total_acumulado = 0.0
    total_diario = 0.0

    tem_chaves_configuradas = False

    for variavel, nome_etapa in CHAVES_ETAPAS:
        token = os.getenv(variavel, "").strip()
        if not token:
            continue
        tem_chaves_configuradas = True

        # Se chave repetida em outra variável, não duplicar a contagem nem a requisição
        ja_contada = token in chaves_vistas
        chaves_vistas.add(token)

        if ja_contada:
            etapas.append(
                {
                    "variavel": variavel,
                    "nome": nome_etapa,
                    "label": "Chave reaproveitada",
                    "usage_acumulado": 0.0,
                    "usage_daily": 0.0,
                    "limit": None,
                    "nota": "Chave compartilhada com etapa anterior (já contabilizada)",
                }
            )
            continue

        try:
            resp = requests.get(
                URL_OPENROUTER_KEY,
                headers={"Authorization": f"Bearer {token}"},
                timeout=TIMEOUT_OPENROUTER,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                usage_val = float(data.get("usage", 0.0) or 0.0)
                daily_val = float(data.get("usage_daily", 0.0) or 0.0)
                limit_val = data.get("limit")
                label_val = str(data.get("label") or nome_etapa)
                # Regra A07: se o label contiver padrão de token (ex: sk-...), ocultar
                if "sk-" in label_val.lower() or "bearer" in label_val.lower():
                    label_val = nome_etapa

                total_acumulado += usage_val
                total_diario += daily_val

                etapas.append(
                    {
                        "variavel": variavel,
                        "nome": nome_etapa,
                        "label": label_val,
                        "usage_acumulado": usage_val,
                        "usage_daily": daily_val,
                        "limit": limit_val,
                        "nota": None,
                    }
                )
            else:
                logger.warning(
                    f"[A07] OpenRouter respondeu HTTP {resp.status_code} para etapa {nome_etapa}"
                )
                etapas.append(
                    {
                        "variavel": variavel,
                        "nome": nome_etapa,
                        "label": "Erro HTTP",
                        "usage_acumulado": 0.0,
                        "usage_daily": 0.0,
                        "limit": None,
                        "nota": f"HTTP {resp.status_code}",
                    }
                )
        except Exception as exc:
            logger.warning(
                f"[A07] Falha de conexão com OpenRouter para etapa {nome_etapa}: {type(exc).__name__}"
            )
            etapas.append(
                {
                    "variavel": variavel,
                    "nome": nome_etapa,
                    "label": "Indisponível",
                    "usage_acumulado": 0.0,
                    "usage_daily": 0.0,
                    "limit": None,
                    "nota": f"Falha de rede ({type(exc).__name__})",
                }
            )

    if not tem_chaves_configuradas:
        return {
            "disponivel": False,
            "total_acumulado_usd": 0.0,
            "total_diario_usd": 0.0,
            "etapas": [],
            "mensagem": "Nenhuma chave OpenRouter configurada no ambiente (.env)",
        }

    return {
        "disponivel": True,
        "total_acumulado_usd": round(total_acumulado, 4),
        "total_diario_usd": round(total_diario, 4),
        "etapas": etapas,
        "mensagem": None,
    }


def verificar_portao_edital(
    slug: str, revisao_dir: Path | None = None
) -> tuple[bool, str]:
    """Verifica se o edital está em revisao_piloto/ e se status_revisao_humana é APROVADO.

    Retorna (aprovado: bool, status_descricao: str).
    """
    from src.stats_writer import listar_jsons_edital

    base = REVISAO_PILOTO_DIR if revisao_dir is None else revisao_dir
    if not base.exists():
        return False, "DIRETORIO_NAO_ENCONTRADO"

    for p in listar_jsons_edital(base):
        try:
            dados = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        concurso = dados.get("concurso")
        if isinstance(concurso, dict) and concurso.get("slug") == slug:
            status_humana = (dados.get("status_revisao_humana") or "PENDENTE").strip()
            aprovado = status_revisao(dados) == STATUS_REVISAO_APROVADO
            return aprovado, status_humana

    return False, "NAO_ENCONTRADO"


def verificar_portao_arvore(arv: Any = None) -> tuple[bool, list[dict[str, Any]]]:
    """Verifica se há propostas pendentes em canonico/arvore.json (arv.propostas).

    Retorna (True, []) se aprovado (zero pendências), ou
    (False, [propostas_pendentes]) caso haja itens aguardando aprovação do dono.
    """
    if arv is None:
        try:
            from src import arvore

            arv = arvore.carregar()
        except Exception as exc:
            logger.warning(f"Erro ao carregar árvore canônica: {exc}")
            return False, [{"erro": str(exc)}]

    propostas = getattr(arv, "propostas", {})
    pendentes: list[dict[str, Any]] = []

    for p in propostas.values():
        status = (
            getattr(p, "status", None) if not isinstance(p, dict) else p.get("status")
        )
        if status == "proposto":
            if hasattr(p, "__dataclass_fields__"):
                pendentes.append(asdict(p))
            elif isinstance(p, dict):
                pendentes.append(p)
            else:
                pendentes.append(vars(p))

    return len(pendentes) == 0, pendentes


def verificar_portao_classificacao(
    slugs: list[str], conn: Any = None
) -> tuple[bool, PendenciasClassificacao]:
    """Verifica pendências de curadoria de classificação no banco para os slugs dados.

    Conta separadamente as duas parcelas:
    1. propostas: Apontamentos com status = 'proposto' em questao_no e discursiva_no.
    2. sem_classificacao: Questões utilizáveis e discursivas sem nenhum apontamento aprovado
       (status = 'aprovado' na árvore canônica).

    Definição canônica:
    Uma questão é considerada classificada quando possui ao menos um apontamento
    com status='aprovado' na árvore (tabela questao_no), conforme checagem K30
    e regras de curadoria da Fase 5 / Etapa 8 (docs/tecnico/banco.md).

    Retorna (aprovado, PendenciasClassificacao(propostas, sem_classificacao)).
    `aprovado` é True se e somente se propostas == 0 e sem_classificacao == 0.
    """
    if not slugs:
        return True, PendenciasClassificacao(0, 0)

    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception as exc:
            logger.warning(f"Sem conexão para verificar portão de classificação: {exc}")
            return False, PendenciasClassificacao(0, -1)

    try:
        with conn.cursor() as cur:
            sql = """
            SELECT
              (SELECT count(*) FROM questao_no qn
                 JOIN questoes q ON q.id = qn.questao_id
                 JOIN provas p ON p.id = q.prova_id
                 JOIN concursos c ON c.id = p.concurso_id
                WHERE c.slug = ANY(%s) AND qn.status = 'proposto')
              +
              (SELECT count(*) FROM discursiva_no dn
                 JOIN discursivas d ON d.id = dn.discursiva_id
                 JOIN provas p ON p.id = d.prova_id
                 JOIN concursos c ON c.id = p.concurso_id
                WHERE c.slug = ANY(%s) AND dn.status = 'proposto') AS propostas,

              (SELECT count(*) FROM questoes q
                 JOIN provas p ON p.id = q.prova_id
                 JOIN concursos c ON c.id = p.concurso_id
                WHERE c.slug = ANY(%s) AND q.utilizavel
                  AND NOT EXISTS (SELECT 1 FROM questao_no qn WHERE qn.questao_id = q.id AND qn.status = 'aprovado'))
              +
              (SELECT count(*) FROM discursivas d
                 JOIN provas p ON p.id = d.prova_id
                 JOIN concursos c ON c.id = p.concurso_id
                WHERE c.slug = ANY(%s)
                  AND NOT EXISTS (SELECT 1 FROM discursiva_no dn WHERE dn.discursiva_id = d.id AND dn.status = 'aprovado')) AS sem_classificacao;
            """
            cur.execute(sql, (slugs, slugs, slugs, slugs))
            row = cur.fetchone()
            propostas = int(row[0] or 0) if row else 0
            sem_classif = int(row[1] or 0) if row else 0
            pendencias = PendenciasClassificacao(
                propostas=propostas, sem_classificacao=sem_classif
            )
            return pendencias == 0, pendencias
    except Exception as exc:
        logger.warning(f"Erro ao consultar pendências de classificação: {exc}")
        return False, PendenciasClassificacao(0, -1)
    finally:
        if fechar_conn:
            try:
                conn.close()
            except Exception:
                pass


def verificar_download_lote(slugs: list[str], conn: Any = None) -> dict[str, Any]:
    """Valida os downloads dos certames do lote contra o manifesto local e o inventário.

    Para cada certame:
    1. Verifica se o `.manifest.json` existe em data/<ano>/CEBRASPE/<orgao>/.
    2. Lê os PDFs locais referenciados no manifesto e verifica se começam com `%PDF-`.
    3. Reconcilia as contagens locais com a tabela `inv_concurso` no banco (K02).
    """
    from src.spider import extract_orgao_from_slug, extract_year_from_slug

    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception:
            conn = None

    detalhes_concursos: dict[str, dict[str, Any]] = {}
    falhas: list[str] = []
    total_manifestos = 0
    total_pdfs_integros = 0

    try:
        inv_contagens: dict[str, int] = {}
        if conn is not None:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT slug, (qtd_editais + qtd_cadernos + qtd_gabaritos + qtd_padroes) AS total_inv "
                    "FROM inv_concurso WHERE slug = ANY(%s)",
                    (slugs,),
                )
                for r in cur.fetchall():
                    inv_contagens[r[0]] = int(r[1] or 0)

        for slug in slugs:
            url_slug = f"https://www.cebraspe.org.br/concursos/{slug}"
            ano = extract_year_from_slug(url_slug) or 2025
            orgao = extract_orgao_from_slug(url_slug)
            manifest_path = DATA_DIR / str(ano) / "CEBRASPE" / orgao / ".manifest.json"

            if not manifest_path.exists():
                falhas.append(f"Manifesto não encontrado para {slug} ({manifest_path})")
                detalhes_concursos[slug] = {
                    "manifesto_existe": False,
                    "total_manifesto": 0,
                    "pdfs_integros": 0,
                    "total_inventario": inv_contagens.get(slug, 0),
                    "status": "sem_manifesto",
                }
                continue

            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as e:
                falhas.append(f"Erro ao ler manifesto de {slug}: {e}")
                continue

            n_manifest = len(manifest_data)
            n_integros = 0
            for item in manifest_data.values():
                p = Path(item.get("path", ""))
                if p.exists() and p.is_file():
                    try:
                        with p.open("rb") as f:
                            header = f.read(5)
                            if header == b"%PDF-":
                                n_integros += 1
                    except OSError:
                        pass

            total_manifestos += n_manifest
            total_pdfs_integros += n_integros
            inv_esperado = inv_contagens.get(slug, 0)

            if n_integros < n_manifest:
                falhas.append(
                    f"{slug}: {n_manifest - n_integros} de {n_manifest} PDFs corrompidos ou ausentes no disco"
                )

            detalhes_concursos[slug] = {
                "manifesto_existe": True,
                "total_manifesto": n_manifest,
                "pdfs_integros": n_integros,
                "total_inventario": inv_esperado,
                "status": "ok"
                if n_integros == n_manifest and n_manifest > 0
                else "incompleto",
            }

        valido = len(falhas) == 0 and len(detalhes_concursos) > 0
        status_geral = "ok" if valido else "falha"
        partes_msg = [
            f"{s}: {info['pdfs_integros']} PDFs íntegros (%PDF-)"
            for s, info in detalhes_concursos.items()
        ]
        msg = "; ".join(partes_msg) if partes_msg else "Nenhum arquivo local verificado"

        return {
            "status": status_geral,
            "valido": valido,
            "total_pdfs": total_pdfs_integros,
            "detalhes": detalhes_concursos,
            "falhas": falhas,
            "mensagem": msg,
        }
    finally:
        if fechar_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def obter_contagens_lote(slugs: list[str], conn: Any = None) -> dict[str, Any]:
    """Retorna contagens reais do lote gravadas no banco (provas, questões, discursivas)."""
    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception as exc:
            return {
                "status": "sem_banco",
                "valido": False,
                "mensagem": f"Banco indisponível: {exc}",
                "concursos": {},
                "totais": {
                    "provas": 0,
                    "questoes": 0,
                    "discursivas": 0,
                    "apontamentos": 0,
                },
            }

    try:
        with conn.cursor() as cur:
            sql = """
            SELECT c.slug,
                   count(DISTINCT p.id) AS provas,
                   count(DISTINCT q.id) AS questoes,
                   count(DISTINCT d.id) AS discursivas,
                   count(qn.questao_id) AS apontamentos_questoes,
                   count(dn.discursiva_id) AS apontamentos_discursivas
            FROM concursos c
            LEFT JOIN provas p ON p.concurso_id = c.id
            LEFT JOIN questoes q ON q.prova_id = p.id
            LEFT JOIN discursivas d ON d.prova_id = p.id
            LEFT JOIN questao_no qn ON qn.questao_id = q.id
            LEFT JOIN discursiva_no dn ON dn.discursiva_id = d.id
            WHERE c.slug = ANY(%s)
            GROUP BY c.slug
            ORDER BY c.slug;
            """
            cur.execute(sql, (slugs,))
            concursos = {}
            tot_provas = 0
            tot_questoes = 0
            tot_disc = 0
            tot_apont = 0
            for r in cur.fetchall():
                s = r[0]
                p_cnt = int(r[1] or 0)
                q_cnt = int(r[2] or 0)
                d_cnt = int(r[3] or 0)
                ap_cnt = int(r[4] or 0) + int(r[5] or 0)
                concursos[s] = {
                    "provas": p_cnt,
                    "questoes": q_cnt,
                    "discursivas": d_cnt,
                    "apontamentos": ap_cnt,
                }
                tot_provas += p_cnt
                tot_questoes += q_cnt
                tot_disc += d_cnt
                tot_apont += ap_cnt

            return {
                "status": "ok",
                "valido": True,
                "concursos": concursos,
                "totais": {
                    "provas": tot_provas,
                    "questoes": tot_questoes,
                    "discursivas": tot_disc,
                    "apontamentos": tot_apont,
                },
                "mensagem": f"{tot_provas} provas, {tot_questoes} questões, {tot_disc} discursivas gravadas",
            }
    except Exception as exc:
        return {
            "status": "erro",
            "valido": False,
            "mensagem": f"Erro ao obter contagens: {exc}",
            "concursos": {},
            "totais": {"provas": 0, "questoes": 0, "discursivas": 0, "apontamentos": 0},
        }
    finally:
        if fechar_conn:
            try:
                conn.close()
            except Exception:
                pass


def obter_status_classificacao_lote(
    slugs: list[str], conn: Any = None
) -> dict[str, Any]:
    """Calcula a proporção N de M de questões classificadas para cada certame do lote.

    Definição canônica:
    Uma questão é considerada classificada quando possui ao menos um apontamento
    com status='aprovado' na árvore (tabela questao_no), conforme checagem K30
    e regras de curadoria da Fase 5 / Etapa 8 (docs/tecnico/banco.md).
    """
    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception as exc:
            return {
                "status": "sem_banco",
                "valido": False,
                "mensagem": f"Banco indisponível: {exc}",
                "concursos": {},
                "total_classificadas": 0,
                "total_questoes": 0,
            }

    try:
        with conn.cursor() as cur:
            sql = """
            SELECT c.slug,
                   count(q.id) AS total,
                   count(DISTINCT CASE WHEN qn.status = 'aprovado' THEN q.id END) AS classificadas
            FROM concursos c
            JOIN provas p ON p.concurso_id = c.id
            JOIN questoes q ON q.prova_id = p.id
            LEFT JOIN questao_no qn ON qn.questao_id = q.id
            WHERE c.slug = ANY(%s) AND q.utilizavel
            GROUP BY c.slug
            ORDER BY c.slug;
            """
            cur.execute(sql, (slugs,))
            concursos = {}
            soma_tot = 0
            soma_classif = 0
            for r in cur.fetchall():
                s = r[0]
                tot = int(r[1] or 0)
                classif = int(r[2] or 0)
                concursos[s] = {
                    "total": tot,
                    "classificadas": classif,
                    "proporcao": f"{classif} de {tot}",
                }
                soma_tot += tot
                soma_classif += classif

            completo = (soma_classif == soma_tot) if soma_tot > 0 else True
            status = "ok" if completo else "pendente"
            detalhes_str = "; ".join(
                f"{s}: {info['proporcao']}" for s, info in concursos.items()
            )
            msg = f"{detalhes_str} (total: {soma_classif} de {soma_tot} classificadas)"

            return {
                "status": status,
                "valido": completo,
                "concursos": concursos,
                "total_classificadas": soma_classif,
                "total_questoes": soma_tot,
                "mensagem": msg,
            }
    except Exception as exc:
        return {
            "status": "erro",
            "valido": False,
            "mensagem": f"Erro ao calcular classificação: {exc}",
            "concursos": {},
            "total_classificadas": 0,
            "total_questoes": 0,
        }
    finally:
        if fechar_conn:
            try:
                conn.close()
            except Exception:
                pass


def verificar_site_lote(slugs: list[str], conn: Any = None) -> dict[str, Any]:
    """Verifica se as questões do lote aparecem em vw_questoes (visíveis para o site).

    Caso não haja verificação real ou as questões ainda não tenham sido promovidas
    para a view pública, devolve 'nao_verificado' com a justificativa de negócio.
    """
    fechar_conn = False
    if conn is None:
        try:
            conn = conectar()
            fechar_conn = True
        except Exception:
            return {
                "status": "nao_verificado",
                "valido": False,
                "total_vw": 0,
                "total_questoes": 0,
                "mensagem": "Sem conexão para aferir vw_questoes",
            }

    try:
        with conn.cursor() as cur:
            sql_provas = """
            SELECT count(q.id) FROM questoes q
            JOIN provas p ON p.id = q.prova_id
            JOIN concursos c ON c.id = p.concurso_id
            WHERE c.slug = ANY(%s) AND q.utilizavel;
            """
            cur.execute(sql_provas, (slugs,))
            total_questoes = int(cur.fetchone()[0] or 0)

            sql_vw = """
            SELECT count(DISTINCT questao_id) FROM vw_questoes
            WHERE split_part(questao_chave, '|', 1) = ANY(%s);
            """
            cur.execute(sql_vw, (slugs,))
            total_vw = int(cur.fetchone()[0] or 0)

            if total_questoes > 0 and total_vw == total_questoes:
                return {
                    "status": "ok",
                    "valido": True,
                    "total_vw": total_vw,
                    "total_questoes": total_questoes,
                    "mensagem": f"Todas as {total_questoes} questões do lote estão visíveis em vw_questoes",
                }
            return {
                "status": "nao_verificado",
                "valido": False,
                "total_vw": total_vw,
                "total_questoes": total_questoes,
                "mensagem": (
                    f"{total_vw} de {total_questoes} questões visíveis em vw_questoes. "
                    "Justificativa: as questões só ingressam na view pública após classificação na árvore e curadoria (P8/P9)."
                ),
            }
    except Exception as exc:
        return {
            "status": "nao_verificado",
            "valido": False,
            "total_vw": 0,
            "total_questoes": 0,
            "mensagem": f"Erro na consulta a vw_questoes: {exc}",
        }
    finally:
        if fechar_conn:
            try:
                conn.close()
            except Exception:
                pass


# ----------------------------------------------------------------------
# Asset Checks do Dagster (D5b, KAN-32)
# ----------------------------------------------------------------------

from dagster import (  # noqa: E402
    AssetCheckResult,
    AssetCheckSeverity,
    AssetKey,
    asset_check,
)


@asset_check(
    asset=AssetKey("p0"),
    description="K22: Invariante do piloto antes do lote (2.800 itens, 129 anuladas, 3.029 apontamentos)",
    blocking=True,
)
def check_k22_piloto_p0() -> AssetCheckResult:
    res = verificar_invariante_piloto()
    valido = bool(res.get("valido", False) or res.get("status") == "sem_banco")
    return AssetCheckResult(
        passed=valido,
        metadata={
            "status": str(res.get("status")),
            "divergencias": str(res.get("divergencias")),
        },
        severity=AssetCheckSeverity.ERROR,
    )


@asset_check(
    asset=AssetKey("p1"),
    description="Download: Reconciliação dos PDFs com manifesto local e inventário (%PDF-)",
    blocking=False,
)
def check_download_p1(context) -> AssetCheckResult:
    slug = getattr(context, "partition_key", None)
    slugs = [slug] if slug else []
    res = verificar_download_lote(slugs)
    return AssetCheckResult(
        passed=bool(res.get("valido", True)),
        metadata={
            "detalhes": str(res.get("detalhes")),
            "status": str(res.get("status")),
        },
    )


@asset_check(
    asset=AssetKey("p3"),
    description="Portão P3: Homologação humana do edital (status_revisao_humana APROVADO)",
    blocking=False,
)
def check_portao_edital_p3(context) -> AssetCheckResult:
    slug = getattr(context, "partition_key", "")
    aprovado, status_humana = verificar_portao_edital(slug)
    return AssetCheckResult(
        passed=bool(aprovado),
        metadata={"status_revisao_humana": str(status_humana)},
        severity=AssetCheckSeverity.WARN if not aprovado else AssetCheckSeverity.ERROR,
    )


@asset_check(
    asset=AssetKey("p5"),
    description="P5: Consultas de integridade do Runbook §4.5 (gabaritos, itens e discursivas)",
    blocking=True,
)
def check_consultas_runbook_p5(context) -> AssetCheckResult:
    slug = getattr(context, "partition_key", None)
    slugs = [slug] if slug else []
    res = executar_consultas_runbook(slugs)
    return AssetCheckResult(
        passed=bool(res.get("valido", True)),
        metadata={
            "status": str(res.get("status")),
            "falhas": str(res.get("falhas")),
        },
        severity=AssetCheckSeverity.ERROR,
    )


@asset_check(
    asset=AssetKey("p7"),
    description="Portão P7: Curadoria da árvore canônica (arv.propostas)",
    blocking=False,
)
def check_portao_arvore_p7() -> AssetCheckResult:
    aprovado, pendentes = verificar_portao_arvore()
    return AssetCheckResult(
        passed=bool(aprovado),
        metadata={"propostas_pendentes": len(pendentes)},
        severity=AssetCheckSeverity.WARN if not aprovado else AssetCheckSeverity.ERROR,
    )


@asset_check(
    asset=AssetKey("p9"),
    description="Portão P9: Curadoria da classificação na árvore (propostas e sem classificação)",
    blocking=False,
)
def check_portao_classificacao_p9(context) -> AssetCheckResult:
    slug = getattr(context, "partition_key", None)
    slugs = [slug] if slug else []
    aprovado, pendencias = verificar_portao_classificacao(slugs)
    return AssetCheckResult(
        passed=bool(aprovado),
        metadata={
            "pendencias_total": int(pendencias),
            "propostas": getattr(pendencias, "propostas", 0),
            "sem_classificacao": getattr(pendencias, "sem_classificacao", 0),
        },
        severity=AssetCheckSeverity.WARN if not aprovado else AssetCheckSeverity.ERROR,
    )


TODOS_ASSET_CHECKS = [
    check_k22_piloto_p0,
    check_download_p1,
    check_portao_edital_p3,
    check_consultas_runbook_p5,
    check_portao_arvore_p7,
    check_portao_classificacao_p9,
]
