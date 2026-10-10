"""Consumidor da fila `fila_extracao_questoes` (Etapa 5C, ADR-031). Sem LLM.

Para cada caderno de prova da fila (com os gabaritos ligados a ele pelo
`stats_writer`):

1. marca as linhas da fila como `processando`;
2. lê o gabarito (`src.gabarito_parser`) e extrai o caderno
   (`src.prova_parser`): objetivo → itens, textos-base, seções e figuras,
   conferidos contra a grade; discursivo → questões, quesitos e padrão de
   resposta;
3. grava `questoes/<caderno>.json` + `<caderno>.auditoria.json`
   e as tabelas `textos_base`/`questoes`/`discursivas` (caderno substituído
   numa transação);
4. marca `concluido`, ou `erro` com o motivo em `mensagem` — divergência
   entre itens extraídos e gabarito é `erro` visível, nunca perda silenciosa.

Gabarito sem caderno: justificativa de alteração (documento do concurso) é
`concluido` com `tipo_documento = 'justificativa'`; grade/padrão sem caderno
ligado é `erro`.

Gatilhos de processamento:
- `pendente`: cadernos com linhas em status pendente ou deixadas em processando;
- `gabaritos_mudaram`: cadernos cuja composição de arquivos/gabaritos mudou
  (assinatura_grupo diverge da gravada);
- `reprocessar`: refaz todos os cadernos e órfãos (`--reprocessar`);
- `reprocessar_erros`: refaz cadernos e órfãos com status 'erro' (`--reprocessar-erros`).

Uso:
    python -m scripts.extrair_questoes [--reprocessar] [--reprocessar-erros]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import gabarito_parser, prova_parser, questoes_writer
from src.downloader import DATA_DIR
from src.logger import logger
from src.stats_writer import (
    aplicar_classificacao,
    conectar,
    criar_schema,
    nome_caderno,
)

PROJETO_DIR = Path(__file__).resolve().parent.parent
QUESTOES_DIR = PROJETO_DIR / "questoes"

# ADR-031: lock exclusivo de sessão no Postgres para garantir consumidor de execução única.
LOCK_FILA_QUESTOES = 5_031_001

# Linhas pendentes ou em processamento deixadas por execuções interrompidas.
# Com o advisory lock (LOCK_FILA_QUESTOES), execuções concorrentes não ocorrem.
STATUS_PENDENTES = ("pendente", "processando")


def carregar_fila(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT f.id, f.categoria, f.arquivo, f.path_relativo, f.status, f.prova_id,
                   f.sha256, f.assinatura_grupo,
                   c.slug, c.banca, p.arquivo, p.tipo, p.identificador, p.codigo_caderno,
                   (SELECT array_agg(ce.numero ORDER BY ce.numero) FROM provas_cargos pc
                    JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id WHERE pc.prova_id = p.id)
            FROM fila_extracao_questoes f
            JOIN concursos c ON c.id = f.concurso_id
            LEFT JOIN provas p ON p.id = f.prova_id
            ORDER BY c.slug, f.prova_id NULLS LAST, f.categoria DESC, f.arquivo
            """
        )
        colunas = [
            "id",
            "categoria",
            "arquivo",
            "path_relativo",
            "status",
            "prova_id",
            "sha256",
            "assinatura_grupo",
            "slug",
            "banca",
            "prova_arquivo",
            "tipo",
            "identificador",
            "codigo_caderno",
            "cargos",
        ]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


def assinatura_grupo(grupo: list[dict]) -> str:
    """Calcula sha256 determinístico da composição do grupo (prova_id + sha256 de cada arquivo)."""
    prova_id = grupo[0]["prova_id"]
    partes = [str(prova_id)] + sorted(l["sha256"] or "" for l in grupo)
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


def marcar(
    conn,
    ids: list[int],
    status: str,
    tipos: dict[int, str] | None = None,
    mensagem: str | None = None,
    assinatura: str | None = None,
) -> None:
    with conn, conn.cursor() as cur:
        for id_ in ids:
            cur.execute(
                "UPDATE fila_extracao_questoes SET status = %s, mensagem = %s, "
                "tipo_documento = COALESCE(%s, tipo_documento), "
                "assinatura_grupo = COALESCE(%s, assinatura_grupo), "
                "atualizado_em = now() WHERE id = %s",
                (status, mensagem, (tipos or {}).get(id_), assinatura, id_),
            )


def _salvar_json(
    saida_dir: Path, caderno: str, resultado: dict, auditoria: dict
) -> None:
    saida_dir.mkdir(parents=True, exist_ok=True)
    (saida_dir / f"{caderno}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (saida_dir / f"{caderno}.auditoria.json").write_text(
        json.dumps(auditoria, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _escolher_documento(
    docs: list[tuple[dict, dict]], prova: dict, tipo_documento: str
) -> tuple[tuple[dict, dict] | None, list[dict]]:
    """Escolhe o documento adequado (grade ou padrão de resposta) entre os ligados.

    Filtra por tipo_documento. Para grade com múltiplos candidatos, filtra por token do caderno.
    Desempata preferindo versão definitiva sobre outras, e pelo nome do arquivo.
    Gera alertas 'mais_de_um_gabarito' e 'gabarito_preliminar' conforme aplicável.
    """
    candidatos = [item for item in docs if item[1]["tipo"] == tipo_documento]
    alertas: list[dict] = []
    if tipo_documento == gabarito_parser.TIPO_GRADE and len(candidatos) > 1:
        certas = [
            c
            for c in candidatos
            if gabarito_parser.token_caderno(c[1]["codigo_caderno"])
            == prova["identificador"]
        ]
        if certas:
            candidatos = certas

    if len(candidatos) > 1:
        candidatos.sort(
            key=lambda item: (
                0 if item[1].get("versao") == gabarito_parser.VERSAO_DEFINITIVO else 1,
                item[0]["arquivo"],
            )
        )
        alertas.append(
            {
                "tipo": "mais_de_um_gabarito",
                "severidade": prova_parser.SEVERIDADE_INFORMATIVO,
                "arquivos": [c[0]["arquivo"] for c in candidatos],
                "versoes": [c[1].get("versao") for c in candidatos],
            }
        )

    escolhido = candidatos[0] if candidatos else None
    if escolhido and escolhido[1].get("versao") == gabarito_parser.VERSAO_PRELIMINAR:
        alertas.append(
            {
                "tipo": "gabarito_preliminar",
                "severidade": prova_parser.SEVERIDADE_INFORMATIVO,
                "arquivo": escolhido[0]["arquivo"],
            }
        )
    return escolhido, alertas


def processar_caderno(
    conn, linhas: list[dict], data_dir: Path, saida_dir: Path
) -> dict:
    """Extrai um caderno (linha `prova` + gabaritos ligados) e atualiza a fila."""
    linha_prova = next(
        (linha for linha in linhas if linha["categoria"] == "prova"), None
    )
    gabaritos = [linha for linha in linhas if linha["categoria"] == "gabarito"]
    base = linha_prova or linhas[0]
    prova = {
        "slug": base["slug"],
        "arquivo": base["prova_arquivo"],
        "tipo": base["tipo"],
        "identificador": base["identificador"],
        "codigo_caderno": base["codigo_caderno"],
    }
    caderno = nome_caderno(prova)
    ids = [linha["id"] for linha in linhas]
    marcar(conn, ids, "processando")
    tipos: dict[int, str] = {}
    assinatura = assinatura_grupo(linhas)

    try:
        if linha_prova is None:
            raise FileNotFoundError(
                f"caderno {prova['arquivo']} fora da fila (só o gabarito está)"
            )
        pdf = data_dir / linha_prova["path_relativo"]
        docs = []
        for g in gabaritos:
            doc = gabarito_parser.ler_documento(data_dir / g["path_relativo"])
            tipos[g["id"]] = doc["tipo"]
            docs.append((g, doc))

        cabecalho = {
            "caderno": caderno,
            "concurso": prova["slug"],
            "banca": base["banca"],
            "tipo_prova": prova["tipo"],
            "codigo_caderno": prova["codigo_caderno"],
            "cargos": base["cargos"] or [],
        }
        if prova["tipo"] == "discursiva":
            tipos[linha_prova["id"]] = "caderno_discursivo"
            resultado, auditoria = prova_parser.extrair_caderno_discursivo(pdf, caderno)
            escolhido, alertas_padrao = _escolher_documento(
                docs, prova, gabarito_parser.TIPO_PADRAO_RESPOSTA
            )
            resultado["alertas"].extend(alertas_padrao)
            if escolhido:
                g, d = escolhido
                prova_parser.ligar_padrao_resposta(
                    resultado, d["padrao_resposta"].secoes, g["arquivo"]
                )
                cabecalho["padrao_resposta_versao"] = d.get("versao")
            else:
                resultado["alertas"].append(
                    {
                        "tipo": "sem_padrao_resposta",
                        "severidade": prova_parser.SEVERIDADE_INFORMATIVO,
                    }
                )
        else:
            tipos[linha_prova["id"]] = "caderno_objetivo"
            escolhida, alertas_grade = _escolher_documento(
                docs, prova, gabarito_parser.TIPO_GRADE
            )
            grade = escolhida[1]["grade"] if escolhida else None
            dir_figuras = pdf.parent / "figuras"
            resultado, auditoria = prova_parser.extrair_caderno_objetivo(
                pdf,
                grade.respostas if grade else None,
                caderno,
                dir_figuras,
                tipos=grade.tipos if grade else None,
            )
            rel_figuras = dir_figuras.relative_to(data_dir)
            for item in resultado["questoes"] + resultado["textos_base"]:
                for figura in item["figuras"]:
                    figura["path_relativo"] = str(rel_figuras / figura["arquivo"])
            resultado["alertas"].extend(alertas_grade)
            if escolhida:
                cabecalho["gabarito_arquivo"] = escolhida[0]["arquivo"]
                cabecalho["gabarito_cabecalho"] = escolhida[1]["grade"].cabecalho
                cabecalho["gabarito_versao"] = escolhida[1].get("versao")
                resultado["alertas"].extend(
                    {
                        "tipo": "grade_irregular",
                        "severidade": prova_parser.SEVERIDADE_INFORMATIVO,
                        "detalhe": a,
                    }
                    for a in escolhida[1]["grade"].alertas
                )

        resultado = {**cabecalho, **resultado, "caderno": caderno}
        _salvar_json(saida_dir, caderno, resultado, auditoria)

        if resultado["status"] == prova_parser.STATUS_SUCESSO:
            if prova["tipo"] == "discursiva":
                questoes_writer.gravar_caderno_discursivo(
                    conn, base["prova_id"], resultado
                )
            else:
                questoes_writer.gravar_caderno_objetivo(
                    conn, base["prova_id"], resultado
                )
            marcar(conn, ids, "concluido", tipos, assinatura=assinatura)
        else:
            questoes_writer.limpar_caderno(conn, base["prova_id"])
            marcar(
                conn,
                ids,
                "erro",
                tipos,
                mensagem=resultado["status"],
                assinatura=assinatura,
            )
        return resultado
    except Exception as e:  # noqa: BLE001 — um caderno ruim não para a fila
        logger.error(
            f"[QUESTOES] {caderno}: falha na extração ({type(e).__name__}: {e})"
        )
        conn.rollback()
        marcar(
            conn,
            ids,
            "erro",
            tipos,
            mensagem=f"excecao: {type(e).__name__}: {e}",
            assinatura=assinatura,
        )
        return {
            "caderno": caderno,
            "status": "excecao",
            "questoes": [],
            "tipo": prova["tipo"],
        }


def processar_orfao(conn, linha: dict, data_dir: Path) -> str:
    """Linha da fila sem caderno ligado."""
    if linha["categoria"] == "prova":
        marcar(
            conn,
            [linha["id"]],
            "erro",
            mensagem="caderno sem registro em provas (sem texto de link)",
        )
        return "prova_sem_registro"
    try:
        doc = gabarito_parser.ler_documento(data_dir / linha["path_relativo"])
    except Exception as e:  # noqa: BLE001
        marcar(
            conn, [linha["id"]], "erro", mensagem=f"excecao: {type(e).__name__}: {e}"
        )
        return "excecao"
    tipos = {linha["id"]: doc["tipo"]}
    if doc["tipo"] == gabarito_parser.TIPO_JUSTIFICATIVA:
        marcar(
            conn,
            [linha["id"]],
            "concluido",
            tipos,
            mensagem="justificativa de alteração: documento do concurso, sem caderno",
        )
        return "justificativa"
    marcar(conn, [linha["id"]], "erro", tipos, mensagem="gabarito sem caderno ligado")
    logger.warning(
        f"[QUESTOES] {linha['slug']}/{linha['arquivo']}: gabarito ({doc['tipo']}) sem caderno ligado."
    )
    return "gabarito_sem_prova"


def _motivo_processar(
    grupo: list[dict], assinatura: str, reprocessar: bool, reprocessar_erros: bool
) -> str | None:
    if reprocessar:
        return "reprocessar"
    if any(l["status"] in STATUS_PENDENTES for l in grupo):
        return "pendente"
    if any(l.get("assinatura_grupo") != assinatura for l in grupo):
        return "gabaritos_mudaram"
    if reprocessar_erros and any(l["status"] == "erro" for l in grupo):
        return "reprocessar_erros"
    return None


def processar_fila(
    conn=None,
    data_dir: Path = DATA_DIR,
    saida_dir: Path = QUESTOES_DIR,
    reprocessar: bool = False,
    reprocessar_erros: bool = False,
) -> dict:
    proprio = conn is None
    conn = conn or conectar()
    totais = {
        "cadernos": 0,
        "cadernos_sucesso": 0,
        "cadernos_falha": {},
        "itens_extraidos": 0,
        "discursivas_questoes": 0,
        "justificativas": 0,
        "gabaritos_sem_prova": 0,
        "provas_sem_registro": 0,
    }
    pegou_lock = False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_FILA_QUESTOES,))
            pegou_lock = cur.fetchone()[0]
        if not pegou_lock:
            logger.warning("[QUESTOES] outra execução em andamento, saindo")
            return {**totais, "ocupado": True}

        criar_schema(conn)
        linhas = carregar_fila(conn)
        por_prova: dict[int, list[dict]] = {}
        orfaos = []
        for linha in linhas:
            if linha["prova_id"] is None:
                orfaos.append(linha)
            else:
                por_prova.setdefault(linha["prova_id"], []).append(linha)

        for grupo in por_prova.values():
            assinatura = assinatura_grupo(grupo)
            motivo = _motivo_processar(
                grupo, assinatura, reprocessar, reprocessar_erros
            )
            if motivo is None:
                continue
            base = next((l for l in grupo if l["categoria"] == "prova"), grupo[0])
            prova_info = {
                "slug": base["slug"],
                "arquivo": base["prova_arquivo"],
                "tipo": base["tipo"],
                "identificador": base["identificador"],
                "codigo_caderno": base["codigo_caderno"],
            }
            caderno_nome = nome_caderno(prova_info)
            if motivo != "pendente":
                logger.info(f"[QUESTOES] {caderno_nome}: reprocessando ({motivo})")
            resultado = processar_caderno(conn, grupo, data_dir, saida_dir)
            totais["cadernos"] += 1
            if resultado["status"] == prova_parser.STATUS_SUCESSO:
                totais["cadernos_sucesso"] += 1
            else:
                falhas = totais["cadernos_falha"]
                falhas[resultado["status"]] = falhas.get(resultado["status"], 0) + 1
            if resultado.get("tipo") == "discursiva":
                totais["discursivas_questoes"] += len(resultado["questoes"])
            else:
                totais["itens_extraidos"] += len(resultado["questoes"])

        for linha in orfaos:
            if (
                not reprocessar
                and not (reprocessar_erros and linha["status"] == "erro")
                and linha["status"] not in STATUS_PENDENTES
            ):
                continue
            desfecho = processar_orfao(conn, linha, data_dir)
            if desfecho == "justificativa":
                totais["justificativas"] += 1
            elif desfecho == "prova_sem_registro":
                totais["provas_sem_registro"] += 1
        try:
            res_class = aplicar_classificacao(conn)
            if res_class:
                logger.info(
                    f"[QUESTOES] Classificação canônica reaplicada ao banco: {res_class}"
                )
        except Exception as e:  # noqa: BLE001
            # O DELETE em cascata das questões já apagou a ponte: falhar aqui
            # deixa `questao_no` vazia até a próxima carga, então o erro é
            # visível nos totais e no código de saída.
            logger.error(
                f"[QUESTOES] Falha ao reaplicar a classificação canônica: "
                f"{type(e).__name__}: {e}"
            )
            totais["classificacao_erro"] = f"{type(e).__name__}: {e}"

        logger.info(f"[QUESTOES] Fila processada: {totais}")
        return totais
    finally:
        if pegou_lock:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (LOCK_FILA_QUESTOES,))
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[QUESTOES] erro ao liberar lock: {e}")
        if proprio:
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--reprocessar",
        action="store_true",
        help="refaz também o que já está concluído",
    )
    parser.add_argument(
        "--reprocessar-erros",
        action="store_true",
        help="refaz cadernos e órfãos com status 'erro'",
    )
    args = parser.parse_args()
    totais_fila = processar_fila(
        reprocessar=args.reprocessar, reprocessar_erros=args.reprocessar_erros
    )
    print(json.dumps(totais_fila, ensure_ascii=False, indent=2))
    if "classificacao_erro" in totais_fila:
        sys.exit(1)
