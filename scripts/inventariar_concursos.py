#!/usr/bin/env python3
"""Script de inventário de concursos e cadernos do CEBRASPE (2020 até hoje) - Etapa 8.0.

Permite:
- --listagens: Mapear as 4 listagens do CEBRASPE e agrupar por ano em inventario/anos.json.
- --mapear: Varrer as páginas individuais dos concursos 2020+ e salvar em inventario/concursos.jsonl.
- --reclassificar: Reaplicar o classificador fino aos textos já gravados (sem rede).
- --amostra-formato: Amostrar cadernos de prova objetivos para classificar formato (CE vs ME).
- --gravar-banco: Persistir o inventário nas tabelas inv_concurso e inv_pdf no PostgreSQL.
- --relatorio: Gerar o relatório analítico Markdown em inventario/RELATORIO.md.
- --tudo: Executar todos os passos em pipeline sequencial.
"""

import argparse
import os
import random
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
import requests

PROJETO_DIR = Path(__file__).resolve().parent.parent
if str(PROJETO_DIR) not in sys.path:
    sys.path.insert(0, str(PROJETO_DIR))

from playwright.sync_api import Page, sync_playwright

from src import spider, stats_writer
from src.inventario import (
    AMOSTRA_DIR,
    CONCURSOS_PILOTO,
    FORMATO_DESCONHECIDO,
    INVENTARIO_ANOS_PATH,
    INVENTARIO_CONCURSOS_PATH,
    INVENTARIO_EXCLUSOES_PATH,
    INVENTARIO_RELATORIO_PATH,
    TIPO_CADERNO_OBJETIVO,
    adicionar_concurso_jsonl,
    aplicar_exclusao,
    carregar_anos_json,
    carregar_concursos_jsonl,
    carregar_exclusoes,
    detectar_formato_caderno,
    escolher_cadernos_calibracao_me,
    gerar_relatorio_md,
    pdf_vai_para_o_site,
    reclassificar_inventario,
    resumir_pdfs,
    salvar_anos_json,
    salvar_concursos_jsonl,
    salvar_relatorio_md,
)
from src.logger import logger
from src.spider import (
    USER_AGENTS,
    extract_orgao_from_slug,
    setup_stealth,
)


@contextmanager
def contexto_navegador(headless: bool = True, page_override: Page | None = None):
    """Gerencia ciclo de vida do navegador Playwright ou injeta página simulada."""
    if page_override is not None:
        yield page_override
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        setup_stealth(page)
        try:
            yield page
        finally:
            context.close()
            browser.close()


def conectar_banco():
    """Conecta ao PostgreSQL via DATABASE_URL ou padrão do projeto."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(db_url)
    return stats_writer.conectar()


def agrupar_por_ano(concursos: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrupa lista de concursos do CEBRASPE por ano e situação.

    Estrutura:
    {
        "<ano>": {
            "encerrado": [slugs],
            "em_andamento": [slugs],
            "inscricoes_abertas": [slugs],
            "novos": [slugs],
            "outros": [slugs]
        },
        "ano_desconhecido": [slugs]
    }
    """
    dados: dict[str, dict[str, list[str]]] = {}
    ano_desconhecido: list[str] = []

    for c in sorted(concursos, key=lambda x: str(x.get("slug", ""))):
        slug = c.get("slug")
        if not slug:
            continue
        ano = c.get("ano")
        situacao = (c.get("situacao") or "").replace("-", "_")

        if ano is None:
            ano_desconhecido.append(slug)
            continue

        ano_str = str(ano)
        if ano_str not in dados:
            dados[ano_str] = {
                "encerrado": [],
                "em_andamento": [],
                "inscricoes_abertas": [],
                "novos": [],
                "outros": [],
            }

        if situacao == "encerrado":
            dados[ano_str]["encerrado"].append(slug)
        elif situacao == "em_andamento":
            dados[ano_str]["em_andamento"].append(slug)
        elif situacao == "inscricoes_abertas":
            dados[ano_str]["inscricoes_abertas"].append(slug)
            dados[ano_str]["outros"].append(slug)
        elif situacao == "novos":
            dados[ano_str]["novos"].append(slug)
            dados[ano_str]["outros"].append(slug)
        else:
            dados[ano_str]["outros"].append(slug)

    resultado: dict[str, Any] = {}
    for chave_ano in sorted(
        dados.keys(),
        key=lambda k: int(k) if k.isdigit() else -1,
        reverse=True,
    ):
        resultado[chave_ano] = dados[chave_ano]

    resultado["ano_desconhecido"] = sorted(set(ano_desconhecido))
    return resultado


def extrair_concursos_de_anos_json(
    anos_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Converte inventario/anos.json em lista de metadados mínimos de concursos."""
    concursos: list[dict[str, Any]] = []
    seen: set[str] = set()

    for chave_ano, valor in anos_data.items():
        if chave_ano == "ano_desconhecido":
            if isinstance(valor, list):
                for slug in valor:
                    if slug in seen:
                        continue
                    seen.add(slug)
                    url = f"https://www.cebraspe.org.br/concursos/{slug}"
                    concursos.append(
                        {
                            "slug": slug,
                            "orgao": extract_orgao_from_slug(url),
                            "ano": None,
                            "situacao": "desconhecida",
                            "url": url,
                        }
                    )
            continue

        if not isinstance(valor, dict):
            continue

        ano_num = int(chave_ano) if chave_ano.isdigit() else None
        for sit_key, slugs in valor.items():
            if sit_key == "outros" or not isinstance(slugs, list):
                continue
            for slug in slugs:
                if slug in seen:
                    continue
                seen.add(slug)
                url = f"https://www.cebraspe.org.br/concursos/{slug}"
                concursos.append(
                    {
                        "slug": slug,
                        "orgao": extract_orgao_from_slug(url),
                        "ano": ano_num,
                        "situacao": sit_key,
                        "url": url,
                    }
                )

    return sorted(concursos, key=lambda x: str(x.get("slug", "")))


def executar_listagens(
    page: Any,
    caminho_anos: Path = INVENTARIO_ANOS_PATH,
) -> dict[str, Any]:
    """Mapeia as 4 listagens do CEBRASPE e grava inventario/anos.json agrupado."""
    logger.info("Iniciando varredura das 4 listagens do CEBRASPE...")
    todos_concursos = spider.listar_todas_listagens(page)
    logger.info(f"Encontrados {len(todos_concursos)} concursos únicos nas listagens.")

    dados_agrupados = agrupar_por_ano(todos_concursos)
    salvar_anos_json(dados_agrupados, caminho_anos)
    logger.info(f"Inventário de listagens salvo com sucesso em: {caminho_anos}")
    return dados_agrupados


def executar_mapear(
    page: Any,
    ano: int | None = None,
    situacao: str | None = None,
    refazer: bool = False,
    limite: int | None = None,
    caminho_concursos: Path = INVENTARIO_CONCURSOS_PATH,
    caminho_anos: Path = INVENTARIO_ANOS_PATH,
    concursos_base: list[dict[str, Any]] | None = None,
    caminho_exclusoes: Path = INVENTARIO_EXCLUSOES_PATH,
) -> int:
    """Varre páginas individuais de concursos 2020+ e salva incrementalmente em concursos.jsonl.

    Concurso de `inventario/exclusoes.json` já mapeado não é buscado de novo,
    nem com `refazer`.
    """
    logger.info("Iniciando etapa de mapeamento de páginas de concursos...")

    if concursos_base is not None:
        candidatos = list(concursos_base)
    elif Path(caminho_anos).exists():
        anos_data = carregar_anos_json(caminho_anos)
        candidatos = extrair_concursos_de_anos_json(anos_data)
    else:
        logger.info(
            f"Arquivo {caminho_anos} não encontrado. Executando listagens primeiro..."
        )
        candidatos = spider.listar_todas_listagens(page)
        salvar_anos_json(agrupar_por_ano(candidatos), caminho_anos)

    # Filtro de ano
    if ano is not None:
        concursos = [c for c in candidatos if c.get("ano") == ano]
    else:
        # Default: 2020 até hoje
        concursos = [
            c for c in candidatos if c.get("ano") is not None and c.get("ano") >= 2020
        ]

    # Filtro de situação
    if situacao is not None:
        situacoes_alvo = {
            s.strip().replace("-", "_") for s in situacao.split(",") if s.strip()
        }
        concursos = [
            c
            for c in concursos
            if (c.get("situacao") or "").replace("-", "_") in situacoes_alvo
        ]

    concursos = sorted(concursos, key=lambda x: str(x.get("slug", "")))
    logger.info(f"Total de concursos qualificados para mapeamento: {len(concursos)}")

    existentes = {c["slug"]: c for c in carregar_concursos_jsonl(caminho_concursos)}
    exclusoes = carregar_exclusoes(caminho_exclusoes)
    processados = 0

    for c in concursos:
        slug = c["slug"]
        if slug in existentes and not refazer:
            logger.debug(f"Concurso '{slug}' já mapeado. Pulando...")
            continue
        # Fora do site (inventario/exclusoes.json): não se busca de novo.
        if slug in exclusoes and slug in existentes:
            categoria = exclusoes[slug]["categoria"]
            logger.info(f"Concurso '{slug}' fora do site ({categoria}). Pulando...")
            continue

        if limite is not None and processados >= limite:
            logger.info(f"Limite atingido ({limite} concursos processados).")
            break

        url = c.get("url") or f"https://www.cebraspe.org.br/concursos/{slug}"
        logger.info(f"Mapeando PDFs do concurso: {slug} ({url})")

        data_mapeamento = datetime.now(UTC).isoformat()
        erro = None
        pdfs: list[dict[str, Any]] = []

        try:
            pdfs = spider.mapear_links_pdf(page, url)
        except Exception as exc:
            logger.error(f"Erro ao mapear PDFs de '{slug}': {exc}")
            erro = str(exc)

        formato_provavel = None
        if slug in existentes:
            formato_provavel = existentes[slug].get("formato_provavel")

        situacao_concurso = c.get("situacao", "desconhecida")
        registro = {
            "slug": slug,
            "orgao": c.get("orgao") or extract_orgao_from_slug(url),
            "ano": c.get("ano"),
            "situacao": situacao_concurso,
            "url": url,
            "data_mapeamento": data_mapeamento,
            **resumir_pdfs(slug, pdfs, situacao_concurso),
            "formato_provavel": formato_provavel,
            "no_banco": bool(slug in CONCURSOS_PILOTO),
            "erro": erro,
            "pdfs": pdfs,
        }
        registro = aplicar_exclusao(registro, exclusoes)

        if slug in existentes:
            existentes[slug] = registro
            ordenados = sorted(
                existentes.values(), key=lambda x: str(x.get("slug", ""))
            )
            salvar_concursos_jsonl(ordenados, caminho_concursos)
        else:
            existentes[slug] = registro
            adicionar_concurso_jsonl(registro, caminho_concursos)

        processados += 1

    logger.info(f"Mapeamento concluído: {processados} concursos gravados.")
    return processados


def executar_reclassificar(
    caminho_concursos: Path = INVENTARIO_CONCURSOS_PATH,
) -> dict[str, Any]:
    """Reclassifica os PDFs de concursos.jsonl pelo texto do link, sem rede."""
    resultado = reclassificar_inventario(caminho_concursos)
    for tipo in sorted(set(resultado["antes"]) | set(resultado["depois"])):
        logger.info(
            f"Reclassificação {tipo}: {resultado['antes'].get(tipo, 0)} -> "
            f"{resultado['depois'].get(tipo, 0)}"
        )
    return resultado


TENTATIVAS_CADERNO_AMOSTRA = 5


def _nome_arquivo_amostra(slug: str, url_pdf: str) -> str:
    return (
        f"{slug}_{url_pdf.split('/')[-1].split('?')[0].split('#')[0] or 'caderno.pdf'}"
    )


def _cadernos_objetivos(concurso: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        p
        for p in concurso.get("pdfs") or []
        if p.get("tipo") == TIPO_CADERNO_OBJETIVO
        and pdf_vai_para_o_site(p)
        and p.get("url")
    ]


def selecionar_amostra(concursos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Todos os concursos de 2025 e 2026 e 3 por ano de 2020 a 2024.

    Em 2020–2024 entram primeiro os que têm caderno objetivo, em ordem de slug.
    Concurso fora do site (`incluir` falso) não entra.
    """
    por_ano: dict[int, list[dict[str, Any]]] = {}
    for c in sorted(concursos, key=lambda x: str(x.get("slug", ""))):
        if c.get("incluir") is False:
            continue
        if isinstance(c.get("ano"), int):
            por_ano.setdefault(c["ano"], []).append(c)

    amostrados: list[dict[str, Any]] = []
    for ano in (2025, 2026):
        amostrados.extend(por_ano.get(ano, []))
    for ano in (2024, 2023, 2022, 2021, 2020):
        cands = por_ano.get(ano, [])
        com_caderno = [c for c in cands if _cadernos_objetivos(c)]
        sem_caderno = [c for c in cands if not _cadernos_objetivos(c)]
        amostrados.extend((com_caderno + sem_caderno)[:3])
    return amostrados


def limpar_amostra(concursos: list[dict[str, Any]], diretorio_amostra: Path) -> int:
    """Apaga da pasta de amostra o PDF que não é caderno objetivo do inventário."""
    validos = {
        _nome_arquivo_amostra(c["slug"], p["url"])
        for c in concursos
        for p in _cadernos_objetivos(c)
    }
    removidos = 0
    for arquivo in Path(diretorio_amostra).glob("*"):
        if arquivo.is_file() and arquivo.name not in validos:
            arquivo.unlink()
            removidos += 1
            logger.info(f"Amostra: removido {arquivo.name} (não é caderno objetivo).")
    return removidos


def executar_amostra_formato(
    caminho_concursos: Path = INVENTARIO_CONCURSOS_PATH,
    diretorio_amostra: Path = AMOSTRA_DIR,
    session_requests: Any | None = None,
) -> int:
    """Amostra cadernos objetivos e detecta formato de prova (CE vs ME).

    O formato é derivado só da amostra atual: concurso fora dela fica sem
    `formato_provavel` (sai no download do lote, 8.1).
    """
    logger.info("Iniciando amostragem de formato de prova (CE vs ME)...")
    concursos = carregar_concursos_jsonl(caminho_concursos)
    if not concursos:
        logger.warning(f"Nenhum concurso em {caminho_concursos} para amostragem.")
        return 0

    for c in concursos:
        c["formato_provavel"] = None
        c.pop("amostra_formato", None)

    amostrados = selecionar_amostra(concursos)
    logger.info(f"Total de concursos selecionados na amostra: {len(amostrados)}")
    diretorio_amostra = Path(diretorio_amostra)
    diretorio_amostra.mkdir(parents=True, exist_ok=True)
    limpar_amostra(concursos, diretorio_amostra)
    req = session_requests or requests

    atualizados = 0
    for c in amostrados:
        slug = c["slug"]
        cadernos_candidatos = _cadernos_objetivos(c)
        if not cadernos_candidatos:
            logger.debug(f"Concurso '{slug}' não tem caderno_objetivo. Ignorando.")
            continue

        formato_final = FORMATO_DESCONHECIDO
        amostra = None
        for caderno in cadernos_candidatos[:TENTATIVAS_CADERNO_AMOSTRA]:
            url_pdf = caderno["url"]
            caminho_pdf = diretorio_amostra / _nome_arquivo_amostra(slug, url_pdf)

            conteudo_valido = (
                caminho_pdf.is_file()
                and caminho_pdf.stat().st_size > 0
                and caminho_pdf.read_bytes().startswith(b"%PDF-")
            )
            if not conteudo_valido:
                try:
                    headers = {"User-Agent": random.choice(USER_AGENTS)}
                    resp = req.get(url_pdf, headers=headers, timeout=30)
                    resp.raise_for_status()
                    conteudo = resp.content
                    if not conteudo.startswith(b"%PDF-"):
                        logger.warning(
                            f"Download de {url_pdf} não começou com '%PDF-'."
                        )
                        continue
                    caminho_pdf.write_bytes(conteudo)
                except Exception as exc:
                    logger.error(
                        f"Falha ao baixar PDF de amostra {slug} ({url_pdf}): {exc}"
                    )
                    continue
                finally:
                    spider.stealth_wait()

            amostra = {
                "arquivo": caminho_pdf.name,
                "url": url_pdf,
                "texto": caderno.get("texto", ""),
            }
            formato_final = detectar_formato_caderno(caminho_pdf)
            if formato_final != FORMATO_DESCONHECIDO:
                break

        c["formato_provavel"] = formato_final
        if amostra:
            c["amostra_formato"] = amostra
        atualizados += 1
        logger.info(f"Formato detectado para '{slug}': {formato_final}")

    salvar_concursos_jsonl(concursos, caminho_concursos)
    logger.info(
        f"Amostragem de formato concluída: {atualizados} concursos atualizados."
    )
    return atualizados


def executar_gravar_banco(
    caminho_concursos: Path = INVENTARIO_CONCURSOS_PATH,
    conn: Any | None = None,
) -> int:
    """Carrega concursos.jsonl e persiste no Postgres via stats_writer.gravar_inventario."""
    logger.info("Iniciando gravação do inventário no PostgreSQL...")
    concursos = carregar_concursos_jsonl(caminho_concursos)
    if not concursos:
        logger.warning(f"Nenhum concurso em {caminho_concursos} para gravar.")
        return 0

    fechar_conn = False
    if conn is None:
        conn = conectar_banco()
        fechar_conn = True

    try:
        stats_writer.criar_schema(conn)
        stats_writer.gravar_inventario(conn, concursos)
        logger.info(
            f"Inventário de {len(concursos)} concursos gravado no banco de dados."
        )
        return len(concursos)
    finally:
        if fechar_conn:
            conn.close()


def executar_relatorio(
    caminho_concursos: Path = INVENTARIO_CONCURSOS_PATH,
    caminho_anos: Path = INVENTARIO_ANOS_PATH,
    caminho_relatorio: Path = INVENTARIO_RELATORIO_PATH,
    diretorio_amostra: Path = AMOSTRA_DIR,
) -> str:
    """Gera o relatório analítico Markdown em inventario/RELATORIO.md."""
    logger.info("Gerando relatório analítico do inventário...")
    concursos = carregar_concursos_jsonl(caminho_concursos)
    anos_data = carregar_anos_json(caminho_anos)

    calibracao = escolher_cadernos_calibracao_me(concursos, diretorio_amostra)
    conteudo = gerar_relatorio_md(concursos, anos_data, calibracao)
    salvar_relatorio_md(conteudo, caminho_relatorio)
    logger.info(f"Relatório gerado com sucesso em: {caminho_relatorio}")
    return conteudo


def criar_parser() -> argparse.ArgumentParser:
    """Cria e configura o parser de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Inventariar concursos e cadernos do CEBRASPE (2020 até hoje) - Etapa 8.0.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Ações
    parser.add_argument(
        "--listagens",
        action="store_true",
        help="Mapeia as 4 listagens do CEBRASPE e gera inventario/anos.json agrupado por ano.",
    )
    parser.add_argument(
        "--mapear",
        action="store_true",
        help="Varre as páginas individuais de concursos de 2020+ e grava inventario/concursos.jsonl.",
    )
    parser.add_argument(
        "--reclassificar",
        action="store_true",
        help="Reaplica o classificador fino aos textos de link já gravados em concursos.jsonl (sem rede).",
    )
    parser.add_argument(
        "--amostra-formato",
        action="store_true",
        help="Amostra cadernos objetivos para detectar formato de prova (CE vs ME) e grava em concursos.jsonl.",
    )
    parser.add_argument(
        "--gravar-banco",
        action="store_true",
        help="Carrega inventario/concursos.jsonl e persiste no Postgres via stats_writer.gravar_inventario.",
    )
    parser.add_argument(
        "--relatorio",
        action="store_true",
        help="Gera relatório analítico consolidado em inventario/RELATORIO.md.",
    )
    parser.add_argument(
        "--tudo",
        action="store_true",
        help="Executa o pipeline completo: --listagens -> --mapear -> --amostra-formato -> --gravar-banco -> --relatorio.",
    )
    parser.add_argument(
        "subcomando",
        nargs="?",
        choices=[
            "listagens",
            "mapear",
            "reclassificar",
            "amostra-formato",
            "gravar-banco",
            "relatorio",
            "tudo",
        ],
        help="Subcomando alternativo (ex: python scripts/inventariar_concursos.py mapear)",
    )

    # Filtros e opções
    parser.add_argument(
        "--ano",
        type=int,
        default=None,
        help="Filtra por ano para --mapear (ex: --ano 2025). Padrão: todos >= 2020.",
    )
    parser.add_argument(
        "--situacao",
        type=str,
        default=None,
        help="Filtra por situação para --mapear (ex: --situacao encerrado ou encerrado,em_andamento).",
    )
    parser.add_argument(
        "--refazer",
        action="store_true",
        help="Força reprocessamento de concursos já mapeados em inventario/concursos.jsonl.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Limite máximo de concursos a mapear (útil para testes e lotes pequenos).",
    )

    # Modo de execução do Playwright
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Executar navegador em modo headless (padrão: True). Use --no-headless para ver interface.",
    )
    parser.add_argument(
        "--headed",
        dest="headless",
        action="store_false",
        help="Executar navegador com interface gráfica visível (equivalente a --no-headless).",
    )

    # Caminhos alternativos
    parser.add_argument(
        "--anos-json",
        type=Path,
        default=INVENTARIO_ANOS_PATH,
        help="Caminho do arquivo anos.json.",
    )
    parser.add_argument(
        "--concursos-jsonl",
        type=Path,
        default=INVENTARIO_CONCURSOS_PATH,
        help="Caminho do arquivo concursos.jsonl.",
    )
    parser.add_argument(
        "--relatorio-md",
        type=Path,
        default=INVENTARIO_RELATORIO_PATH,
        help="Caminho do arquivo RELATORIO.md.",
    )
    parser.add_argument(
        "--amostra-dir",
        type=Path,
        default=AMOSTRA_DIR,
        help="Diretório de PDFs de amostra.",
    )
    return parser


def main(
    argv: list[str] | None = None,
    page_override: Any | None = None,
    conn_override: Any | None = None,
    requests_override: Any | None = None,
) -> int:
    """Ponto de entrada da CLI."""
    parser = criar_parser()
    args = parser.parse_args(argv)

    if args.subcomando:
        if args.subcomando == "listagens":
            args.listagens = True
        elif args.subcomando == "mapear":
            args.mapear = True
        elif args.subcomando == "reclassificar":
            args.reclassificar = True
        elif args.subcomando == "amostra-formato":
            args.amostra_formato = True
        elif args.subcomando == "gravar-banco":
            args.gravar_banco = True
        elif args.subcomando == "relatorio":
            args.relatorio = True
        elif args.subcomando == "tudo":
            args.tudo = True

    if args.tudo:
        args.listagens = True
        args.mapear = True
        args.amostra_formato = True
        args.gravar_banco = True
        args.relatorio = True

    if not (
        args.listagens
        or args.mapear
        or args.reclassificar
        or args.amostra_formato
        or args.gravar_banco
        or args.relatorio
    ):
        parser.print_help()
        return 0

    precisa_navegador = args.listagens or args.mapear

    if precisa_navegador:
        with contexto_navegador(
            headless=args.headless, page_override=page_override
        ) as page:
            if args.listagens:
                executar_listagens(page, caminho_anos=args.anos_json)

            if args.mapear:
                executar_mapear(
                    page=page,
                    ano=args.ano,
                    situacao=args.situacao,
                    refazer=args.refazer,
                    limite=args.limite,
                    caminho_concursos=args.concursos_jsonl,
                    caminho_anos=args.anos_json,
                )

    if args.reclassificar:
        executar_reclassificar(caminho_concursos=args.concursos_jsonl)

    if args.amostra_formato:
        executar_amostra_formato(
            caminho_concursos=args.concursos_jsonl,
            diretorio_amostra=args.amostra_dir,
            session_requests=requests_override,
        )

    if args.gravar_banco:
        executar_gravar_banco(
            caminho_concursos=args.concursos_jsonl,
            conn=conn_override,
        )

    if args.relatorio:
        executar_relatorio(
            caminho_concursos=args.concursos_jsonl,
            caminho_anos=args.anos_json,
            caminho_relatorio=args.relatorio_md,
            diretorio_amostra=args.amostra_dir,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
