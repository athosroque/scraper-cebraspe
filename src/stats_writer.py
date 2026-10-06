"""Grava o star schema de estatísticas no Postgres próprio (Etapa 5, ADR-027).

Duas fontes:
1. `revisao_piloto/<edital>.json` — concurso, cargos e taxonomia extraída.
2. `data/<ano>/CEBRASPE/<orgao>/` — manifesto do downloader (URL -> hash) e
   `provas_texto_link.json` (texto do link, única fonte de tipo/cargos de cada
   caderno), que alimentam `provas`/`provas_cargos` e a fila
   `fila_extracao_questoes`.

Idempotência:
- dimensões: upsert por chave natural normalizada;
- fatos de um concurso (taxonomia, provas): substituídos numa transação —
  upsert linha a linha deixaria tópico órfão quando uma reextração muda a
  taxonomia;
- provas: upsert por `(concurso, arquivo)` — o `provas.id` fica estável para
  as questões extraídas na Etapa 5C apontarem para ele;
- fila: upsert por `sha256` sem tocar `status` (estado do consumidor,
  `scripts/extrair_questoes.py`). Gabarito com nome em hash é ligado ao
  caderno pelo código impresso no PDF (ADR-031).

Dados com revisão humana pendente entram marcados
(`concursos.status_revisao = 'pendente'`); as views de estatística só contam
concurso `aprovado`.

Camada canônica (Etapa 5B, ADR-029): `canonico/sinonimos.json` é lido a cada
carga; só grupo `aprovado` vira linha em `materia_canonica`/
`assunto_canonico`/`subassunto_canonico` e ID nas dimensões. Nome sem grupo
aprovado fica com o ID NULL.

Uso:
    python -m src.stats_writer [revisao_piloto_dir] [data_dir]
"""

import json
import os
import re
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json, execute_batch

from src import arvore, canonico, classificacao, gabarito_parser
from src.comparacao_texto import extrair_cargos_do_texto, normalizar
from src.downloader import (
    DATA_DIR,
    MANIFEST_FILENAME,
    PROVAS_TEXTO_FILENAME,
    _filename_from_url,
    _load_manifest,
)
from src.logger import logger
from src.spider import extract_orgao_from_slug, extract_year_from_slug

PROJETO_DIR = Path(__file__).resolve().parent.parent
REVISAO_DIR_PADRAO = PROJETO_DIR / "revisao_piloto"
SCHEMA_SQL = Path(__file__).resolve().parent / "sql" / "schema_estatisticas.sql"

PASTA_CATEGORIA_FILA = {"Provas": "prova", "Gabaritos": "gabarito"}

# Classificação do texto do link, já passado por `normalizar` (minúsculas,
# sem acento/pontuação). Ordem importa: "PADRÃO ... RESPOSTA – PROVA
# DISCURSIVA" é gabarito, não prova; edital administrativo que cita prova
# (resultado, locais) caiu em Provas/ antes da correção do spider.
PADRAO_EDITAL_ADMINISTRATIVO = re.compile(
    r"\bedital\b|\bresultado\b|\blocais de aplicacao\b"
)
PADRAO_PADRAO_RESPOSTA = re.compile(r"\bpadr\w* .*\brespostas?\b")
PADRAO_DISCURSIVA = re.compile(r"\bdiscursivas?\b")
PADRAO_BASICA = re.compile(r"\bconhecimentos (?:basicos|gerais)\b")
PADRAO_ESPECIFICA = re.compile(r"\bconhecimentos especificos\b")

# Token do caderno no nome do arquivo: 094_PF_CB1_01, 072_STM_CG2_01,
# 057_IBAMA_001_01, 094_PF_014_DISC, 094_PF_DISC_015.
PADRAO_ID_BASICA = re.compile(r"_(C[BG]\d+)_\d{2}$", re.IGNORECASE)
PADRAO_ID_ESPECIFICA = re.compile(r"_(\d{3})_\d{2}$")
PADRAO_ID_DISCURSIVA = re.compile(r"_(\d{3})_DISC$|_DISC_(\d{3})$", re.IGNORECASE)
PREFIXO_GABARITO = re.compile(r"^Gab_Definitivo_", re.IGNORECASE)

# Único valor hoje: o projeto só coleta CEBRASPE. Vem do path
# `data/<ano>/<BANCA>/<orgao>/` (ver `coletar_pdfs_fila`).
BANCA_PADRAO = "CEBRASPE"

STATUS_REVISAO_PENDENTE = "pendente"
STATUS_REVISAO_APROVADO = "aprovado"


# Conexão/schema -------------------------------------------------------------


def conectar(**kwargs):
    """Conexão com `scraper-cebraspe-db` a partir de `POSTGRES_*` no `.env`.
    Sem default de senha, mesma regra do compose (ADR-026)."""
    load_dotenv(PROJETO_DIR / ".env")
    senha = os.getenv("POSTGRES_PASSWORD")
    if not senha:
        raise RuntimeError("POSTGRES_PASSWORD não definido no .env — ver .env.example.")
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5435")),
        dbname=os.getenv("POSTGRES_DB", "cebraspe"),
        user=os.getenv("POSTGRES_USER", "cebraspe"),
        password=senha,
        **kwargs,
    )


# Privilégios dados a outras roles (as do site, `site/sql/app_schema.sql`) em
# objetos do `public`. O schema recria as views com `DROP VIEW ... CASCADE`, o
# que apaga os GRANTs: sem reaplicar, toda carga derruba o site com
# "permission denied for view vw_questoes".
_SQL_GRANTS_PUBLIC = """
    SELECT format('GRANT %s ON %s TO %I', a.privilege_type,
                  c.oid::regclass, r.rolname)
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     CROSS JOIN LATERAL aclexplode(c.relacl) a
      JOIN pg_roles r ON r.oid = a.grantee
     WHERE n.nspname = current_schema() AND a.grantee <> c.relowner
    UNION ALL
    SELECT format('GRANT EXECUTE ON FUNCTION %s TO %I',
                  p.oid::regprocedure, r.rolname)
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     CROSS JOIN LATERAL aclexplode(p.proacl) a
      JOIN pg_roles r ON r.oid = a.grantee
     WHERE n.nspname = current_schema() AND a.grantee <> p.proowner
"""


def criar_schema(conn) -> None:
    with conn, conn.cursor() as cur:
        cur.execute(_SQL_GRANTS_PUBLIC)
        grants = [linha[0] for linha in cur.fetchall()]
        cur.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        for grant in grants:
            # Objeto que deixou de existir no schema novo perde o GRANT.
            cur.execute("SAVEPOINT grant_publico")
            try:
                cur.execute(grant)
            except psycopg2.Error:
                cur.execute("ROLLBACK TO SAVEPOINT grant_publico")
                logger.warning("[GRANT_PERDIDO] %s", grant)
            else:
                cur.execute("RELEASE SAVEPOINT grant_publico")


# Funções puras ----------------------------------------------------------------


def status_revisao(resultado: dict) -> str:
    texto = (resultado.get("status_revisao_humana") or "").strip().upper()
    return (
        STATUS_REVISAO_APROVADO
        if texto.startswith("APROVADO")
        else STATUS_REVISAO_PENDENTE
    )


def classificar_prova_por_texto(texto: str) -> dict | None:
    """Tipo do caderno + cargos cobertos a partir do texto do link.

    Retorna `{"tipo": ..., "cargos_numeros": [...]}` com `tipo` em
    `objetiva_basica`, `objetiva_especifica`, `discursiva` ou
    `padrao_resposta` (gabarito da discursiva, vai pra fila como gabarito).
    Retorna None para edital administrativo ou texto não reconhecido.
    """
    texto_norm = normalizar(texto or "")
    if not texto_norm:
        return None
    if PADRAO_PADRAO_RESPOSTA.search(texto_norm):
        tipo = "padrao_resposta"
    elif PADRAO_EDITAL_ADMINISTRATIVO.search(texto_norm):
        return None
    elif PADRAO_DISCURSIVA.search(texto_norm):
        tipo = "discursiva"
    elif PADRAO_BASICA.search(texto_norm):
        tipo = "objetiva_basica"
    elif PADRAO_ESPECIFICA.search(texto_norm):
        tipo = "objetiva_especifica"
    else:
        return None
    return {"tipo": tipo, "cargos_numeros": extrair_cargos_do_texto(texto_norm)}


def identificador_prova(nome_arquivo: str) -> str | None:
    """Token do caderno no nome do arquivo (`CB1`, `CG2`, `001`, `DISC_014`).
    None quando o nome não segue o padrão (ex.: arquivo com nome em hash)."""
    stem = Path(nome_arquivo).stem
    m = PADRAO_ID_DISCURSIVA.search(stem)
    if m:
        return f"DISC_{m.group(1) or m.group(2)}"
    m = PADRAO_ID_BASICA.search(stem)
    if m:
        return m.group(1).upper()
    m = PADRAO_ID_ESPECIFICA.search(stem)
    if m:
        return m.group(1)
    return None


def codigo_caderno_do_nome(nome_arquivo: str) -> str | None:
    """`094_PF_CB1_01.pdf` -> `094_PF_CB1_01`; nome em hash ou fora do padrão
    -> None (o código vem do gabarito, ver `ligar_gabarito_por_conteudo`)."""
    stem = Path(nome_arquivo).stem.upper()
    return stem if gabarito_parser.PADRAO_CODIGO_CADERNO.fullmatch(stem) else None


def ligar_gabarito_por_conteudo(
    pdf_path: Path, provas: list[dict], discursiva_por_cargo: dict[int, int]
) -> tuple[int | None, str | None]:
    """Liga gabarito sem correspondência pelo nome (hash de CD/TCU) ao caderno,
    lendo o **conteúdo** do PDF (Etapa 5C, ADR-031). Devolve
    `(prova_id, codigo_caderno)`.

    - grade: código do caderno impresso na grade (`167_CDNS_001_01`) -> token
      `001`/`CG1` -> prova com esse identificador; senão, específica cujo
      único cargo é o número do token, ou a única básica do concurso;
    - padrão de resposta: cargo do cabeçalho -> discursiva desse cargo; sem
      cargo, a única discursiva do concurso;
    - justificativa de alteração (documento do concurso) e PDF ilegível: sem
      ligação.

    Só liga quando há exatamente um candidato — ambíguo fica sem caderno e
    aparece como "gabarito sem prova".
    """
    try:
        doc = gabarito_parser.ler_documento(pdf_path)
    except Exception as e:  # noqa: BLE001 — PDF corrompido não derruba a carga
        logger.warning(
            f"[STATS] {pdf_path.name}: gabarito ilegível ({e}), sem ligação."
        )
        return None, None

    if doc["tipo"] == gabarito_parser.TIPO_GRADE and doc["codigo_caderno"]:
        token = gabarito_parser.token_caderno(doc["codigo_caderno"])
        objetivas = [p for p in provas if p["tipo"] != "discursiva"]
        candidatos = [p for p in objetivas if p["identificador"] == token]
        if not candidatos and token and token.isdigit():
            candidatos = [
                p
                for p in objetivas
                if p["tipo"] == "objetiva_especifica" and p["cargos"] == [int(token)]
            ]
        if not candidatos and token and not token.isdigit():
            basicas = [p for p in objetivas if p["tipo"] == "objetiva_basica"]
            candidatos = basicas if len(basicas) == 1 else []
        if len(candidatos) == 1:
            return candidatos[0]["id"], doc["codigo_caderno"]
    elif doc["tipo"] == gabarito_parser.TIPO_PADRAO_RESPOSTA:
        cargos = doc["padrao_resposta"].cargos_numeros
        if len(cargos) == 1 and cargos[0] in discursiva_por_cargo:
            return discursiva_por_cargo[cargos[0]], None
        discursivas = [p for p in provas if p["tipo"] == "discursiva"]
        if not cargos and len(discursivas) == 1:
            return discursivas[0]["id"], None
    return None, None


def montar_carga_concurso(resultado: dict) -> dict:
    """Linhas de concurso/cargos/taxonomia de um `<edital>.json`, com chaves
    naturais já normalizadas. Tópico sem chave normalizável é pulado (log)."""
    concurso = resultado.get("concurso") or {}
    if not concurso.get("slug"):
        raise ValueError(
            f"{resultado.get('edital')}: sem `concurso.slug` — rode o backfill do ADR-020."
        )

    cargos = [
        {
            "numero": c["numero"],
            "nome": c["nome"],
            "chave": normalizar(c["nome"]),
            "nivel": c.get("nivel"),
        }
        for c in resultado.get("cargos") or []
    ]

    itens = []
    for item in resultado.get("resultados", []):
        materia_nome = item.get("materia_normalizada") or item["materia_chunk"]
        materia_chave = normalizar(materia_nome)
        taxonomia = item["taxonomia_extraida"]
        if not item.get("materia_origem"):
            # Sem valor padrão: um `cabecalho` inventado esconderia o cargo de
            # especialidade e zeraria `dim_materia.nome_de_cargo` sem aviso.
            logger.warning(
                f"[STATS] {concurso['slug']} chunk {item.get('chunk_index')}: "
                "sem `materia_origem` — rode o backfill (Etapa 5E); gravado NULL."
            )
        for ordem, topico in enumerate(taxonomia.get("topicos", [])):
            topico_chave = normalizar(topico["nome"])
            if not materia_chave or not topico_chave:
                logger.warning(
                    f"[STATS] {concurso['slug']} chunk {item.get('chunk_index')}: "
                    f"tópico sem chave normalizável ({topico['nome']!r}), pulado."
                )
                continue
            itens.append(
                {
                    "chunk_index": item["chunk_index"],
                    "topico_ordem": ordem,
                    "cargo_numero": item.get("cargo_numero"),
                    "tipo_conhecimento": item.get("tipo_conhecimento"),
                    "nivel": item.get("nivel"),
                    "apenas_discursiva": bool(item.get("apenas_discursiva")),
                    "cargos_restritos": list(item["cargos_restritos"])
                    if item.get("cargos_restritos")
                    else None,
                    "materia_origem": item.get("materia_origem"),
                    "materia_nome": materia_nome,
                    "materia_chave": materia_chave,
                    "topico_nome": topico["nome"],
                    "topico_chave": topico_chave,
                    "subtopicos": list(topico.get("subtopicos", [])),
                    "metadados": {
                        "materia_chunk": item.get("materia_chunk"),
                        "materia_extraida": taxonomia.get("materia"),
                        "cargo_chunk": item.get("cargo"),
                    },
                }
            )

    return {
        "slug": concurso["slug"],
        "orgao": concurso.get("orgao") or extract_orgao_from_slug(concurso["slug"]),
        "ano": concurso.get("ano") or extract_year_from_slug(concurso["slug"]),
        "edital_arquivo": resultado.get("edital"),
        "status_revisao": status_revisao(resultado),
        "total_chunks": resultado.get("total_chunks"),
        "metadados": {
            "extraidos_com_sucesso": resultado.get("extraidos_com_sucesso"),
            "falhas": resultado.get("falhas"),
        },
        "cargos": cargos,
        "itens": itens,
    }


def _slug_da_url(url: str) -> str | None:
    m = re.search(r"/concursos/([^/]+)/", url)
    return m.group(1) if m else None


def coletar_pdfs_fila(data_dir: Path = DATA_DIR) -> dict[str, list[dict]]:
    """PDFs em `Provas/`/`Gabaritos/` agrupados por slug do concurso.

    Percorre o que existe em disco e casa cada arquivo com o manifesto pelo
    nome (mesma regra de `resolver_concurso_do_pdf`: o `path` gravado no
    manifesto pode apontar pra outra cópia do repo). Arquivo sem entrada no
    manifesto, ou ambíguo entre concursos, é logado e pulado.
    """
    por_slug: dict[str, list[dict]] = {}
    for manifest_path in sorted(data_dir.glob(f"*/CEBRASPE/*/{MANIFEST_FILENAME}")):
        orgao_dir = manifest_path.parent
        manifest = _load_manifest(manifest_path)
        textos = _load_manifest(orgao_dir / PROVAS_TEXTO_FILENAME)

        por_nome: dict[str, list[tuple[str, dict]]] = {}
        for url, entry in manifest.items():
            for nome in {_filename_from_url(url), Path(entry.get("path", "")).name}:
                if nome:
                    por_nome.setdefault(nome, []).append((url, entry))

        for pasta, categoria in PASTA_CATEGORIA_FILA.items():
            for pdf in sorted((orgao_dir / pasta).glob("*")):
                if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
                    continue
                candidatos = por_nome.get(pdf.name, [])
                slugs = {_slug_da_url(url) for url, _ in candidatos} - {None}
                hashes = {entry.get("hash") for _, entry in candidatos} - {None}
                if len(slugs) != 1 or len(hashes) != 1:
                    logger.warning(
                        f"[STATS] {pdf.relative_to(data_dir)}: concurso/hash não identificado "
                        f"pelo manifesto (slugs={sorted(slugs)}), fora da fila."
                    )
                    continue
                url = next(u for u, _ in candidatos)
                por_slug.setdefault(slugs.pop(), []).append(
                    {
                        "arquivo": pdf.name,
                        "categoria": categoria,
                        "path_relativo": str(pdf.relative_to(data_dir)),
                        "url": url,
                        "sha256": hashes.pop(),
                        "texto_link": textos.get(pdf.name),
                        "banca": pdf.relative_to(data_dir).parts[1],
                    }
                )
    return por_slug


def _stem_prova_do_gabarito(nome_arquivo: str) -> str | None:
    stem = Path(nome_arquivo).stem
    sem_prefixo = PREFIXO_GABARITO.sub("", stem)
    return sem_prefixo.upper() if sem_prefixo != stem else None


# Gravação ---------------------------------------------------------------------


def _upsert_retorna_id(cur, sql: str, params: tuple) -> int:
    cur.execute(sql, params)
    return cur.fetchone()[0]


def _upsert_concurso(
    cur,
    slug: str,
    orgao: str,
    ano: int | None,
    extras: dict | None = None,
    banca: str = BANCA_PADRAO,
) -> int:
    orgao_id = _upsert_retorna_id(
        cur,
        "INSERT INTO dim_orgao (sigla) VALUES (%s) "
        "ON CONFLICT (sigla) DO UPDATE SET sigla = EXCLUDED.sigla RETURNING id",
        (orgao,),
    )
    if ano is not None:
        cur.execute(
            "INSERT INTO dim_ano (ano) VALUES (%s) ON CONFLICT DO NOTHING", (ano,)
        )

    if extras is None:
        # Concurso visto só pelo manifesto (sem edital extraído): cria se não
        # existir, sem sobrescrever o que a carga do edital gravou.
        return _upsert_retorna_id(
            cur,
            "INSERT INTO concursos (slug, orgao_id, ano, banca) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (slug) DO UPDATE SET banca = EXCLUDED.banca RETURNING id",
            (slug, orgao_id, ano, banca),
        )
    return _upsert_retorna_id(
        cur,
        """
        INSERT INTO concursos
            (slug, orgao_id, ano, edital_arquivo, status_revisao, total_chunks, metadados, banca,
             carregado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (slug) DO UPDATE SET
            orgao_id = EXCLUDED.orgao_id,
            banca = EXCLUDED.banca,
            ano = EXCLUDED.ano,
            edital_arquivo = EXCLUDED.edital_arquivo,
            status_revisao = EXCLUDED.status_revisao,
            total_chunks = EXCLUDED.total_chunks,
            metadados = EXCLUDED.metadados,
            carregado_em = now()
        RETURNING id
        """,
        (
            slug,
            orgao_id,
            ano,
            extras["edital_arquivo"],
            extras["status_revisao"],
            extras["total_chunks"],
            Json(extras["metadados"]),
            banca,
        ),
    )


def gravar_concurso(conn, carga: dict) -> int:
    """Grava um concurso numa transação: dimensões por upsert, cargos por
    upsert em `(concurso, numero)` (a ponte `provas_cargos` aponta pra eles) e
    taxonomia substituída por inteiro. Retorna o `concursos.id`."""
    with conn, conn.cursor() as cur:
        concurso_id = _upsert_concurso(
            cur, carga["slug"], carga["orgao"], carga["ano"], extras=carga
        )

        cargo_edital_ids: dict[int, int] = {}
        for cargo in carga["cargos"]:
            cargo_id = _upsert_retorna_id(
                cur,
                "INSERT INTO dim_cargo (chave, nome) VALUES (%s, %s) "
                "ON CONFLICT (chave) DO UPDATE SET nome = dim_cargo.nome RETURNING id",
                (cargo["chave"], cargo["nome"]),
            )
            cargo_edital_ids[cargo["numero"]] = _upsert_retorna_id(
                cur,
                """
                INSERT INTO cargos_editais (concurso_id, cargo_id, numero, nome, nivel)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (concurso_id, numero) DO UPDATE SET
                    cargo_id = EXCLUDED.cargo_id, nome = EXCLUDED.nome, nivel = EXCLUDED.nivel
                RETURNING id
                """,
                (concurso_id, cargo_id, cargo["numero"], cargo["nome"], cargo["nivel"]),
            )
        cur.execute(
            "DELETE FROM cargos_editais WHERE concurso_id = %s AND NOT (numero = ANY(%s))",
            (concurso_id, list(cargo_edital_ids) or [-1]),
        )

        cur.execute(
            "DELETE FROM taxonomia_itens WHERE concurso_id = %s", (concurso_id,)
        )
        materia_ids: dict[str, int] = {}
        topico_ids: dict[tuple[int, str], int] = {}
        subtopico_ids: dict[tuple[int, str], int] = {}
        total_subitens = 0
        for item in carga["itens"]:
            materia_id = materia_ids.get(item["materia_chave"])
            if materia_id is None:
                materia_id = materia_ids[item["materia_chave"]] = _upsert_retorna_id(
                    cur,
                    "INSERT INTO dim_materia (chave, nome) VALUES (%s, %s) "
                    "ON CONFLICT (chave) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
                    (item["materia_chave"], item["materia_nome"]),
                )
            topico_id = topico_ids.get((materia_id, item["topico_chave"]))
            if topico_id is None:
                topico_id = topico_ids[(materia_id, item["topico_chave"])] = (
                    _upsert_retorna_id(
                        cur,
                        "INSERT INTO dim_topico (materia_id, chave, nome) VALUES (%s, %s, %s) "
                        "ON CONFLICT (materia_id, chave) DO UPDATE SET nome = dim_topico.nome RETURNING id",
                        (materia_id, item["topico_chave"], item["topico_nome"]),
                    )
                )
            cargo_numero = item["cargo_numero"]
            cargo_edital_id = (
                cargo_edital_ids.get(cargo_numero) if cargo_numero is not None else None
            )
            if cargo_numero is not None and cargo_edital_id is None:
                logger.warning(
                    f"[STATS] {carga['slug']} chunk {item['chunk_index']}: cargo {cargo_numero} "
                    "fora da lista de cargos do edital — gravado sem cargo."
                )
            item_id = _upsert_retorna_id(
                cur,
                """
                INSERT INTO taxonomia_itens
                    (concurso_id, cargo_edital_id, materia_id, topico_id, tipo_conhecimento, nivel,
                     apenas_discursiva, chunk_index, topico_ordem, topico_nome, metadados,
                     cargos_restritos, materia_origem)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    concurso_id,
                    cargo_edital_id,
                    materia_id,
                    topico_id,
                    item["tipo_conhecimento"],
                    item["nivel"],
                    item["apenas_discursiva"],
                    item["chunk_index"],
                    item["topico_ordem"],
                    item["topico_nome"],
                    Json(item["metadados"]),
                    item.get("cargos_restritos"),
                    item.get("materia_origem"),
                ),
            )
            # Subtópico: 1 linha por subtópico (Etapa 5B), dimensão por
            # (tópico, chave natural). Sem chave normalizável é pulado.
            for ordem_sub, sub_nome in enumerate(item["subtopicos"]):
                sub_chave = normalizar(sub_nome)
                if not sub_chave:
                    continue
                subtopico_id = subtopico_ids.get((topico_id, sub_chave))
                if subtopico_id is None:
                    subtopico_id = subtopico_ids[(topico_id, sub_chave)] = (
                        _upsert_retorna_id(
                            cur,
                            "INSERT INTO dim_subtopico (topico_id, chave, nome) VALUES (%s, %s, %s) "
                            "ON CONFLICT (topico_id, chave) DO UPDATE SET nome = dim_subtopico.nome RETURNING id",
                            (topico_id, sub_chave, sub_nome),
                        )
                    )
                cur.execute(
                    "INSERT INTO taxonomia_subitens (taxonomia_item_id, subtopico_id, ordem, nome) "
                    "VALUES (%s, %s, %s, %s)",
                    (item_id, subtopico_id, ordem_sub, sub_nome),
                )
                total_subitens += 1
    restritos = sum(1 for item in carga["itens"] if item.get("cargos_restritos"))
    logger.info(
        f"[STATS] {carga['slug']} ({carga['status_revisao']}): {len(carga['cargos'])} cargos, "
        f"{len(carga['itens'])} tópicos gravados, {restritos} com cargos restritos."
    )
    logger.info(
        f"[STATS] {carga['slug']}: {total_subitens} subtópicos gravados (taxonomia_subitens)."
    )
    return concurso_id


def atualizar_dim_materia_nome_de_cargo(conn) -> int:
    """Atualiza o atributo derivado `dim_materia.nome_de_cargo` (Etapa 5E).

    A verdade fica em `taxonomia_itens.materia_origem` (grão do chunk); aqui
    só se deriva `bool_and(materia_origem = 'cargo')` sobre os itens da
    matéria. Matéria sem itens fica `false`.
    """
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE dim_materia m
            SET nome_de_cargo = COALESCE(
                (SELECT bool_and(ti.materia_origem = 'cargo')
                 FROM taxonomia_itens ti
                 WHERE ti.materia_id = m.id),
                false
            )
            """
        )
        return cur.rowcount


def gravar_provas_e_fila(
    conn, slug: str, pdfs: list[dict], data_dir: Path = DATA_DIR
) -> dict[str, int]:
    """Grava as provas do concurso e faz upsert da fila (sem tocar `status`).
    Tudo numa transação.

    Provas por upsert em `(concurso, arquivo)`, e não substituídas: as
    questões extraídas (Etapa 5C) apontam para `provas.id`, que precisa ficar
    estável entre cargas. Prova cujo arquivo sumiu do disco é removida (e
    leva as questões junto, por cascata).
    """
    contagem = {"provas": 0, "fila": 0, "pulados": 0, "gabaritos_sem_prova": 0}
    banca = next((p.get("banca") for p in pdfs if p.get("banca")), BANCA_PADRAO)
    with conn, conn.cursor() as cur:
        concurso_id = _upsert_concurso(
            cur,
            slug,
            extract_orgao_from_slug(slug),
            extract_year_from_slug(slug),
            banca=banca,
        )
        cur.execute(
            "SELECT numero, id FROM cargos_editais WHERE concurso_id = %s",
            (concurso_id,),
        )
        cargo_edital_ids = dict(cur.fetchall())

        prova_por_stem: dict[str, int] = {}
        discursiva_por_cargo: dict[int, int] = {}
        provas_gravadas: list[dict] = []
        entradas_fila = []

        for pdf in pdfs:
            classificacao = (
                classificar_prova_por_texto(pdf["texto_link"])
                if pdf["texto_link"]
                else None
            )
            if (
                pdf["categoria"] == "prova"
                and pdf["texto_link"]
                and classificacao is None
            ):
                logger.warning(
                    f"[STATS] {slug}/{pdf['arquivo']}: texto do link não é caderno de prova "
                    f"({pdf['texto_link'][:80]!r}), fora da fila."
                )
                contagem["pulados"] += 1
                continue

            categoria, prova_id = pdf["categoria"], None
            if classificacao and classificacao["tipo"] == "padrao_resposta":
                categoria = "gabarito"
            elif categoria == "prova" and classificacao:
                cargos = classificacao["cargos_numeros"] or sorted(cargo_edital_ids)
                identificador = identificador_prova(pdf["arquivo"])
                if (
                    identificador is None
                    and classificacao["tipo"] == "discursiva"
                    and len(classificacao["cargos_numeros"]) == 1
                ):
                    identificador = f"DISC_{classificacao['cargos_numeros'][0]:03d}"
                prova_id = _upsert_retorna_id(
                    cur,
                    """
                    INSERT INTO provas
                        (concurso_id, arquivo, identificador, tipo, texto_link, codigo_caderno)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (concurso_id, arquivo) DO UPDATE SET
                        identificador = COALESCE(EXCLUDED.identificador, provas.identificador),
                        tipo = EXCLUDED.tipo,
                        texto_link = EXCLUDED.texto_link,
                        codigo_caderno = COALESCE(EXCLUDED.codigo_caderno, provas.codigo_caderno)
                    RETURNING id
                    """,
                    (
                        concurso_id,
                        pdf["arquivo"],
                        identificador,
                        classificacao["tipo"],
                        pdf["texto_link"],
                        codigo_caderno_do_nome(pdf["arquivo"]),
                    ),
                )
                contagem["provas"] += 1
                prova_por_stem[Path(pdf["arquivo"]).stem.upper()] = prova_id
                provas_gravadas.append(
                    {
                        "id": prova_id,
                        "arquivo": pdf["arquivo"],
                        "tipo": classificacao["tipo"],
                        "identificador": identificador,
                        "cargos": classificacao["cargos_numeros"],
                    }
                )
                cur.execute(
                    "DELETE FROM provas_cargos WHERE prova_id = %s", (prova_id,)
                )
                for numero in cargos:
                    cargo_edital_id = cargo_edital_ids.get(numero)
                    if cargo_edital_id is None:
                        logger.warning(
                            f"[STATS] {slug}/{pdf['arquivo']}: cargo {numero} sem registro em cargos_editais."
                        )
                        continue
                    cur.execute(
                        "INSERT INTO provas_cargos (prova_id, cargo_edital_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (prova_id, cargo_edital_id),
                    )
                    if classificacao["tipo"] == "discursiva":
                        discursiva_por_cargo[numero] = prova_id
            elif categoria == "prova":
                logger.warning(
                    f"[STATS] {slug}/{pdf['arquivo']}: sem texto de link, entra na fila sem registro em provas."
                )
            entradas_fila.append((pdf, categoria, prova_id, classificacao))

        cur.execute(
            "DELETE FROM provas WHERE concurso_id = %s AND NOT (arquivo = ANY(%s))",
            (concurso_id, [p["arquivo"] for p in provas_gravadas] or [""]),
        )

        for pdf, categoria, prova_id, classificacao in entradas_fila:
            if categoria == "gabarito" and prova_id is None:
                stem_prova = _stem_prova_do_gabarito(pdf["arquivo"])
                prova_id = prova_por_stem.get(stem_prova) if stem_prova else None
                if (
                    prova_id is None
                    and classificacao
                    and len(classificacao["cargos_numeros"]) == 1
                ):
                    prova_id = discursiva_por_cargo.get(
                        classificacao["cargos_numeros"][0]
                    )
                if prova_id is None:
                    prova_id, codigo = ligar_gabarito_por_conteudo(
                        data_dir / pdf["path_relativo"],
                        provas_gravadas,
                        discursiva_por_cargo,
                    )
                    if prova_id is not None and codigo:
                        cur.execute(
                            "UPDATE provas SET codigo_caderno = %s, "
                            "identificador = COALESCE(identificador, %s) WHERE id = %s",
                            (codigo, gabarito_parser.token_caderno(codigo), prova_id),
                        )
                    if prova_id is not None:
                        logger.info(
                            f"[STATS] {slug}/{pdf['arquivo']}: gabarito ligado ao caderno pelo conteúdo"
                            + (f" ({codigo})." if codigo else " (padrão de resposta).")
                        )
                if prova_id is None:
                    contagem["gabaritos_sem_prova"] += 1
            cur.execute(
                """
                INSERT INTO fila_extracao_questoes
                    (concurso_id, categoria, arquivo, path_relativo, url, sha256, prova_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sha256) DO UPDATE SET
                    concurso_id = EXCLUDED.concurso_id,
                    categoria = EXCLUDED.categoria,
                    arquivo = EXCLUDED.arquivo,
                    path_relativo = EXCLUDED.path_relativo,
                    url = EXCLUDED.url,
                    prova_id = EXCLUDED.prova_id,
                    atualizado_em = now()
                """,
                (
                    concurso_id,
                    categoria,
                    pdf["arquivo"],
                    pdf["path_relativo"],
                    pdf["url"],
                    pdf["sha256"],
                    prova_id,
                ),
            )
            contagem["fila"] += 1

    logger.info(
        f"[STATS] {slug}: {contagem['provas']} provas, {contagem['fila']} PDFs na fila, "
        f"{contagem['pulados']} pulados, {contagem['gabaritos_sem_prova']} gabaritos sem prova."
    )
    return contagem


def _limpar_dimensoes_orfas(conn) -> dict[str, int]:
    with conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM dim_subtopico s WHERE NOT EXISTS "
            "(SELECT 1 FROM taxonomia_subitens i WHERE i.subtopico_id = s.id)"
        )
        subtopicos = cur.rowcount
        cur.execute(
            "DELETE FROM dim_topico t WHERE NOT EXISTS (SELECT 1 FROM taxonomia_itens i WHERE i.topico_id = t.id)"
        )
        topicos = cur.rowcount
        cur.execute(
            "DELETE FROM dim_materia m WHERE NOT EXISTS (SELECT 1 FROM dim_topico t WHERE t.materia_id = m.id) "
            "AND NOT EXISTS (SELECT 1 FROM taxonomia_itens i WHERE i.materia_id = m.id) RETURNING nome"
        )
        materias = [linha[0] for linha in cur.fetchall()]
    # Matéria órfã aparece quando a chave natural muda (ex.: restrição de cargo
    # saindo do nome, ADR-028) — o nome ajuda a conferir que era a esperada.
    logger.info(
        f"[STATS] Órfãs removidas: {len(materias)} matérias, {topicos} tópicos"
        + (f" ({'; '.join(materias)})" if materias else "")
        + "."
    )
    logger.info(f"[STATS] Subtópicos órfãos removidos: {subtopicos}.")
    return {"materias": len(materias), "topicos": topicos, "subtopicos": subtopicos}


def aplicar_arvore(conn, arvore_path: Path) -> dict[str, int]:
    """Carrega `canonico/arvore.json` em `no_arvore` e nas pontes N:N (ADR-030).

    Todos os nós entram, com o status: `vw_no_caminho` só expõe a cadeia
    `ativa` e resolve o `fundido`, então proposta nunca muda estatística e
    nenhuma ponte fica sem nó (FK). Pontes só com mapeamento `aprovado`, já
    com o nó resolvido. Tudo numa transação, recarregado a cada execução.
    """
    if not arvore_path.exists():
        logger.warning(f"[ARVORE] {arvore_path} não existe — nenhuma árvore carregada.")
        return {}

    arv = arvore.carregar(arvore_path)
    nos = [
        (
            no_id,
            no.nivel,
            no.nome,
            arvore.resolver_no(arv, no.pai) if no.pai else None,
            no.origem,
            no.status,
            no.fundido_em,
        )
        for no_id, no in sorted(arv.nos.items())
    ]

    with conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM no_arvore WHERE NOT (id = ANY(%s))", ([n[0] for n in nos],)
        )
        execute_batch(
            cur,
            "INSERT INTO no_arvore (id, nivel, nome, pai_id, origem, status, fundido_em) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET nivel = EXCLUDED.nivel, nome = EXCLUDED.nome, "
            "pai_id = EXCLUDED.pai_id, origem = EXCLUDED.origem, status = EXCLUDED.status, "
            "fundido_em = EXCLUDED.fundido_em",
            nos,
        )

        # `nocoes` é atributo do nome da matéria (regra da 5B), não da árvore.
        cur.execute("SELECT id, nome FROM dim_materia")
        execute_batch(
            cur,
            "UPDATE dim_materia SET nocoes = %s WHERE id = %s",
            [(canonico.chave_regra(nome).nocoes, id_) for id_, nome in cur.fetchall()],
        )

        cur.execute("SELECT chave, id FROM dim_materia")
        ids = {arvore.chave_item((chave,)): id_ for chave, id_ in cur.fetchall()}
        cur.execute(
            "SELECT m.chave, t.chave, t.id FROM dim_topico t "
            "JOIN dim_materia m ON m.id = t.materia_id"
        )
        ids.update({arvore.chave_item((m, t)): id_ for m, t, id_ in cur.fetchall()})
        cur.execute(
            "SELECT m.chave, t.chave, s.chave, s.id FROM dim_subtopico s "
            "JOIN dim_topico t ON t.id = s.topico_id "
            "JOIN dim_materia m ON m.id = t.materia_id"
        )
        ids.update(
            {arvore.chave_item((m, t, st)): id_ for m, t, st, id_ in cur.fetchall()}
        )

        pontes: dict[str, set[tuple[int, str]]] = {
            "materia_no": set(),
            "topico_no": set(),
            "subtopico_no": set(),
        }
        tabela_por_partes = {1: "materia_no", 2: "topico_no", 3: "subtopico_no"}
        for chave, mapeamentos in arv.mapeamentos.items():
            dim_id = ids.get(chave)
            if dim_id is None:
                continue
            tabela = tabela_por_partes[chave.count("|") + 1]
            for m in mapeamentos:
                if m.status == "aprovado":
                    pontes[tabela].add((dim_id, arvore.resolver_no(arv, m.no_id)))

        colunas = {
            "materia_no": "materia_id",
            "topico_no": "topico_id",
            "subtopico_no": "subtopico_id",
        }
        for tabela, linhas in pontes.items():
            cur.execute(f"DELETE FROM {tabela}")
            execute_batch(
                cur,
                f"INSERT INTO {tabela} ({colunas[tabela]}, no_id) VALUES (%s, %s)",
                sorted(linhas),
            )

    totais = {"nos": len(nos), **{t: len(linhas) for t, linhas in pontes.items()}}
    logger.info(
        f"[ARVORE] banco: {totais['nos']} nós, pontes: {totais['materia_no']} matérias, "
        f"{totais['topico_no']} tópicos, {totais['subtopico_no']} subtópicos mapeados."
    )
    return totais


def nome_caderno(prova: dict) -> str:
    """Nome estável do caderno: código impresso no gabarito
    (`094_PF_CB1_01`), senão `<slug>_<identificador>` (`PF_25_ADM_DISC_001`),
    senão o nome do arquivo higienizado."""
    if prova.get("codigo_caderno"):
        return prova["codigo_caderno"]
    stem = Path(prova.get("arquivo", "")).stem
    if re.fullmatch(r"\d{3}_[A-Z0-9]+_(?:\d{3}_DISC|DISC_\d{3})", stem, re.IGNORECASE):
        return stem.upper()
    if prova.get("identificador"):
        return f"{prova['slug']}_{prova['identificador']}"
    return re.sub(r"[^A-Za-z0-9]+", "_", f"{prova.get('slug', '')}_{stem}").strip("_")


def aplicar_classificacao(
    conn, classificacao_path: Path = classificacao.CLASSIFICACAO_PADRAO
) -> dict[str, int]:
    """Carrega `canonico/classificacao_questoes.json` em `questao_no` e `discursiva_no` (ADR-030).

    Mapeia as chaves naturais para os IDs seriais de `questoes` e `discursivas`.
    Numa transação atômica, limpa e recarrega as tabelas derivadas com todos os registros canônicos.

    Registro cujo `hash_enunciado` não bate com o enunciado atual do banco é
    **pulado** (a reextração mudou a questão, e a classificação antiga
    descreveria outro texto): entra em `desatualizados` e no log, e volta a
    ser classificado pelo `classificar_questoes.py`.
    """
    if not classificacao_path.exists():
        logger.info(
            f"[CLASSIFICACAO] {classificacao_path} não existe — nenhuma classificação carregada."
        )
        return {}

    cq = classificacao.carregar(classificacao_path)
    if not cq.registros:
        logger.info(f"[CLASSIFICACAO] {classificacao_path} não possui registros.")
        return {}

    with conn, conn.cursor() as cur:
        # Mapeia chaves de questões objetivas
        # Objetivas e discursivas usam a mesma regra de nome de caderno
        # (`nome_caderno`), a mesma da extração e do JSON canônico.
        cur.execute(
            """
            SELECT c.slug, p.codigo_caderno, p.arquivo, p.identificador,
                   q.numero, q.id, q.enunciado
            FROM questoes q
            JOIN provas p ON p.id = q.prova_id
            JOIN concursos c ON c.id = p.concurso_id
            """
        )
        map_questoes = {}
        for slug, cod_caderno, arquivo, ident, num, q_id, enunciado in cur.fetchall():
            cad_nome = nome_caderno(
                {
                    "slug": slug,
                    "codigo_caderno": cod_caderno,
                    "arquivo": arquivo,
                    "identificador": ident,
                }
            )
            map_questoes[f"{slug}|{cad_nome}|{num}"] = (q_id, enunciado)

        # Mapeia chaves de discursivas
        cur.execute(
            """
            SELECT c.slug, p.codigo_caderno, p.arquivo, p.identificador,
                   d.numero, d.id, d.enunciado
            FROM discursivas d
            JOIN provas p ON p.id = d.prova_id
            JOIN concursos c ON c.id = p.concurso_id
            """
        )
        map_discursivas = {}
        for slug, cod_caderno, arquivo, ident, num, d_id, enunciado in cur.fetchall():
            cad_nome = nome_caderno(
                {
                    "slug": slug,
                    "codigo_caderno": cod_caderno,
                    "arquivo": arquivo,
                    "identificador": ident,
                }
            )
            map_discursivas[f"{slug}|{cad_nome}|D{num}"] = (d_id, enunciado)

        linhas_questoes = []
        linhas_discursivas = []
        desatualizados: list[str] = []

        for chave, reg in sorted(cq.registros.items()):
            if reg.sem_no:
                continue

            alvo = map_discursivas.get(chave) or map_questoes.get(chave)
            if alvo is not None and (
                reg.hash_enunciado != classificacao.calcular_hash_enunciado(alvo[1])
            ):
                desatualizados.append(chave)
                continue

            if chave in map_discursivas:
                d_id = map_discursivas[chave][0]
                for a in reg.apontamentos:
                    linhas_discursivas.append(
                        (
                            d_id,
                            a.no_id,
                            a.papel,
                            a.confianca,
                            a.fora_do_edital,
                            a.origem,
                            a.status,
                        )
                    )
            elif chave in map_questoes:
                q_id = map_questoes[chave][0]
                for a in reg.apontamentos:
                    linhas_questoes.append(
                        (
                            q_id,
                            a.no_id,
                            a.papel,
                            a.confianca,
                            a.fora_do_edital,
                            a.origem,
                            a.status,
                        )
                    )
            else:
                logger.warning(
                    f"[CLASSIFICACAO] Chave canônica não encontrada no banco: {chave}"
                )

        cur.execute("DELETE FROM questao_no")
        cur.execute("DELETE FROM discursiva_no")

        execute_batch(
            cur,
            """
            INSERT INTO questao_no (
                questao_id, no_id, papel, confianca, fora_do_edital, origem, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (questao_id, no_id) DO UPDATE SET
                papel = EXCLUDED.papel,
                confianca = EXCLUDED.confianca,
                fora_do_edital = EXCLUDED.fora_do_edital,
                origem = EXCLUDED.origem,
                status = EXCLUDED.status,
                atualizado_em = now()
            """,
            linhas_questoes,
        )

        execute_batch(
            cur,
            """
            INSERT INTO discursiva_no (
                discursiva_id, no_id, papel, confianca, fora_do_edital, origem, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (discursiva_id, no_id) DO UPDATE SET
                papel = EXCLUDED.papel,
                confianca = EXCLUDED.confianca,
                fora_do_edital = EXCLUDED.fora_do_edital,
                origem = EXCLUDED.origem,
                status = EXCLUDED.status,
                atualizado_em = now()
            """,
            linhas_discursivas,
        )

    totais = {
        "questao_no": len(linhas_questoes),
        "discursiva_no": len(linhas_discursivas),
        "desatualizados": len(desatualizados),
    }
    if desatualizados:
        logger.warning(
            f"[CLASSIFICACAO] {len(desatualizados)} registro(s) com enunciado "
            f"diferente do banco (reextração mudou a questão); pulados, "
            f"reclassificar: {desatualizados[:5]}"
        )
    logger.info(
        f"[CLASSIFICACAO] banco: {totais['questao_no']} apontamentos de questões, "
        f"{totais['discursiva_no']} de discursivas."
    )
    return totais


def listar_jsons_edital(revisao_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in revisao_dir.glob("*.json")
        if not p.name.endswith(".auditoria.json")
        and not p.name.endswith(".validacao.json")
    )


def gravar_estatisticas(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    data_dir: Path = DATA_DIR,
    conn=None,
    arvore_path: Path | None = None,
    classificacao_path: Path | None = None,
) -> dict[str, int]:
    """Carga completa: schema, concursos extraídos, provas, fila e camada canônica."""
    proprio = conn is None
    conn = conn or conectar()
    try:
        criar_schema(conn)
        totais = {
            "concursos": 0,
            "topicos": 0,
            "provas": 0,
            "fila": 0,
            "pulados": 0,
            "gabaritos_sem_prova": 0,
        }
        por_status: dict[str, int] = {}
        for json_path in listar_jsons_edital(revisao_dir):
            carga = montar_carga_concurso(
                json.loads(json_path.read_text(encoding="utf-8"))
            )
            gravar_concurso(conn, carga)
            totais["concursos"] += 1
            totais["topicos"] += len(carga["itens"])
            por_status[carga["status_revisao"]] = (
                por_status.get(carga["status_revisao"], 0) + 1
            )

        for slug, pdfs in coletar_pdfs_fila(data_dir).items():
            contagem = gravar_provas_e_fila(conn, slug, pdfs, data_dir)
            for chave in ("provas", "fila", "pulados", "gabaritos_sem_prova"):
                totais[chave] += contagem[chave]

        _limpar_dimensoes_orfas(conn)
        atualizar_dim_materia_nome_de_cargo(conn)
        arvore_path = arvore_path or arvore.ARVORE_PADRAO
        aplicar_arvore(conn, arvore_path)
        classificacao_path = classificacao_path or classificacao.CLASSIFICACAO_PADRAO
        aplicar_classificacao(conn, classificacao_path)
        revisao = (
            ", ".join(f"{n} {status}" for status, n in sorted(por_status.items()))
            or "nenhum"
        )
        logger.info(f"[STATS] Carga concluída: {totais} · revisão: {revisao}")
        return totais
    finally:
        if proprio:
            conn.close()


if __name__ == "__main__":
    revisao = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    dados = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR
    gravar_estatisticas(revisao, dados)
