"""Assets do Dagster como C2 do pipeline (Etapa 9/D5a, KAN-31).

Os assets nascem do registro `src/registro/etapas.py` (uma fonte única para
o pipeline documentado e executado, ADR-041).
Eles chamam as funções atuais sem reescrevê-las:
- `process_contest`
- `revisar_edital_piloto`
- `processar_fila` / `atualizar_artefatos_revisao`
- `classificar_todas_questoes`
"""

import json
from pathlib import Path

from dagster import AssetExecutionContext, AssetKey, Config, asset

from src.c2.partitions import concursos_partitions

RAIZ = Path(__file__).resolve().parent.parent.parent
REVISAO_DIR = RAIZ / "revisao_piloto"
DATA_DIR = RAIZ / "data"


class PipelineConfig(Config):
    conferencia: bool = True
    exigir_aprovacao: bool = False


class PortaoHumanoBloqueado(Exception):
    """Lançada quando a etapa exige aprovação humana e o certame ainda está pendente."""

    pass


class EtapaIncompleta(Exception):
    """Lançada quando a etapa não tem o insumo e a execução exige que tenha."""

    pass


def _buscar_edital(
    slug: str, revisao_dir: Path | None = None
) -> tuple[Path, dict] | None:
    """Acha o `<edital>.json` do concurso em `revisao_dir` pelo `concurso.slug`.

    O nome do arquivo é o do PDF (ou um hash), então só o slug interno serve.
    A listagem é a do writer (`listar_jsons_edital`, regra P41).
    """
    from src.stats_writer import listar_jsons_edital

    base = REVISAO_DIR if revisao_dir is None else revisao_dir
    if not base.exists():
        return None
    for p in listar_jsons_edital(base):
        try:
            dados = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        concurso = dados.get("concurso")
        if isinstance(concurso, dict) and concurso.get("slug") == slug:
            return p, dados
    return None


def _nao_implementado(context: AssetExecutionContext, etapa: str, slug: str) -> dict:
    context.log.warning(
        f"[{etapa}] Etapa ainda não implementada no Dagster (D5b): nada foi feito para {slug}"
    )
    return {"slug": slug, "etapa": etapa, "status": "nao_implementado"}


@asset(
    key=AssetKey("p0"),
    partitions_def=concursos_partitions,
    description="P0 Backup do banco",
    group_name="pipeline",
)
def p0_backup(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(
        f"[P0] Backup para concurso {slug} (modo conferência={config.conferencia})"
    )
    return _nao_implementado(context, "P0", slug)


@asset(
    key=AssetKey("p1"),
    deps=[AssetKey("p0")],
    partitions_def=concursos_partitions,
    description="P1 Download dos PDFs do concurso",
    group_name="pipeline",
)
def p1_download_concurso(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict:
    slug = context.partition_key
    context.log.info(f"[P1] Download de PDFs para {slug}")

    from src.spider import (
        CebraspeSpider,
        extract_orgao_from_slug,
        extract_year_from_slug,
        has_priority_keyword,
    )

    url = f"https://www.cebraspe.org.br/concursos/{slug}"
    ano = extract_year_from_slug(url) or 2025
    orgao = extract_orgao_from_slug(url)
    manifest_path = DATA_DIR / str(ano) / "CEBRASPE" / orgao / ".manifest.json"

    if config.conferencia:
        if manifest_path.exists():
            context.log.info(
                f"[P1] Modo conferência: reaproveitando PDFs locais de {slug} ({manifest_path})"
            )
            return {"slug": slug, "etapa": "P1", "status": "reaproveitado", "ano": ano}
        context.log.info(
            f"[P1] Modo conferência: sem download para {slug} (somente leitura)"
        )
        if config.exigir_aprovacao:
            raise EtapaIncompleta(
                f"P1: sem arquivos locais para {slug} e --exigir-aprovacao ativo"
            )
        return {
            "slug": slug,
            "etapa": "P1",
            "status": "conferencia_sem_arquivos",
            "ano": ano,
        }

    contest = {
        "title": slug,
        "url": url,
        "slug": slug,
        "orgao": orgao,
        "ano": ano,
        "priority": 1 if has_priority_keyword(slug) else 0,
    }

    spider = CebraspeSpider()
    # Em execução direta ou teste com mock
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            baixados = spider.process_contest(page, contest, set())
            browser.close()
            return {"slug": slug, "etapa": "P1", "status": "baixado", "dados": baixados}
    except Exception as e:
        context.log.warning(
            f"[P1] Navegador Playwright não executado ou falhou ({e}); conferindo arquivos locais"
        )
        if manifest_path.exists():
            return {"slug": slug, "etapa": "P1", "status": "reaproveitado_fallback"}
        raise


@asset(
    key=AssetKey("p2"),
    deps=[AssetKey("p1")],
    partitions_def=concursos_partitions,
    description="P2 Chunking do edital (sem LLM)",
    group_name="pipeline",
)
def p2_chunking_edital(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P2] Verificação de chunking do edital para {slug}")
    resultado = _nao_implementado(context, "P2", slug)
    resultado["edital_encontrado"] = _buscar_edital(slug) is not None
    return resultado


@asset(
    key=AssetKey("p3"),
    deps=[AssetKey("p2")],
    partitions_def=concursos_partitions,
    description="P3 Taxonomia do edital pelo LLM (checkpoint de revisão)",
    group_name="pipeline",
)
def p3_taxonomia_edital(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P3] Taxonomia do edital para {slug}")

    achado = _buscar_edital(slug)
    if achado is None:
        # Sem edital: nunca chama o LLM aqui (gasta tokens; só com ordem explícita
        # do dono, via scripts/revisar_taxonomia_piloto.py).
        mensagem = (
            f"P3: nenhum edital em revisao_piloto/ com concurso.slug={slug!r}; "
            "extraia o edital antes (scripts/revisar_taxonomia_piloto.py)"
        )
        if config.exigir_aprovacao or not config.conferencia:
            raise PortaoHumanoBloqueado(mensagem)
        context.log.warning(f"[P3] {mensagem}")
        return {
            "slug": slug,
            "etapa": "P3",
            "status": "sem_edital",
            "aprovado": False,
        }

    from src.stats_writer import STATUS_REVISAO_APROVADO, status_revisao

    _, dados = achado
    status_humana = dados.get("status_revisao_humana", "PENDENTE")
    aprovado = status_revisao(dados) == STATUS_REVISAO_APROVADO
    if config.exigir_aprovacao and not aprovado:
        raise PortaoHumanoBloqueado(
            f"Portão humano P3 bloqueado: concurso {slug} com status_revisao_humana={status_humana!r}"
        )

    context.log.info(
        f"[P3] Concurso {slug} - status_revisao_humana: {status_humana} (aprovado={aprovado})"
    )
    return {
        "slug": slug,
        "etapa": "P3",
        "status": "ok",
        "status_revisao_humana": status_humana,
        "aprovado": aprovado,
    }


@asset(
    key=AssetKey("p4"),
    deps=[AssetKey("p3")],
    partitions_def=concursos_partitions,
    description="P4 Carga das questões no banco",
    group_name="pipeline",
)
def p4_carga_questoes(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(
        f"[P4] Carga das questões para {slug} (conferência={config.conferencia})"
    )

    if not config.conferencia:
        from scripts.atualizar_revisao import atualizar_artefatos_revisao
        from scripts.extrair_questoes import processar_fila
        from src import stats_writer

        # ATENÇÃO: funções globais, não por partição. `--no-conferencia` não
        # deve ser usado antes da D5b (rodar K22–K24 antes e depois do lote).
        stats_writer.gravar_estatisticas()
        processar_fila()
        atualizar_artefatos_revisao()
        return {"slug": slug, "etapa": "P4", "status": "ok"}

    return {"slug": slug, "etapa": "P4", "status": "conferencia_sem_acao"}


@asset(
    key=AssetKey("p4b"),
    deps=[AssetKey("p4")],
    partitions_def=concursos_partitions,
    description="P4b Reprocessamento das questões (só se o parser mudar)",
    group_name="pipeline",
)
def p4b_reprocessamento(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P4b] Verificação de reprocessamento para {slug}")
    return _nao_implementado(context, "P4b", slug)


@asset(
    key=AssetKey("p5"),
    deps=[AssetKey("p4")],
    partitions_def=concursos_partitions,
    description="P5 Conferência do lote (consultas a-e e PDF)",
    group_name="pipeline",
)
def p5_conferencia_lote(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P5] Conferência do lote para {slug}")
    return _nao_implementado(context, "P5", slug)


@asset(
    key=AssetKey("p6"),
    deps=[AssetKey("p5")],
    partitions_def=concursos_partitions,
    description="P6 Dispersão de conceitos na árvore",
    group_name="pipeline",
)
def p6_dispersao_arvore(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P6] Detecção de dispersão para {slug}")
    return _nao_implementado(context, "P6", slug)


@asset(
    key=AssetKey("p7"),
    deps=[AssetKey("p6")],
    partitions_def=concursos_partitions,
    description="P7 Curadoria da árvore mestre (portão humano)",
    group_name="pipeline",
)
def p7_curadoria_arvore(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P7] Portão de curadoria da árvore para {slug}")
    return _nao_implementado(context, "P7", slug)


@asset(
    key=AssetKey("p8"),
    deps=[AssetKey("p7")],
    partitions_def=concursos_partitions,
    description="P8 Classificação das questões na árvore (LLM)",
    group_name="pipeline",
)
def p8_classificacao_questoes(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict:
    slug = context.partition_key
    context.log.info(
        f"[P8] Classificação das questões para {slug} (dry_run={config.conferencia})"
    )

    from scripts.classificar_questoes import classificar_todas_questoes

    conta = classificar_todas_questoes(concurso=slug, dry_run=config.conferencia)
    return {
        "slug": slug,
        "etapa": "P8",
        "status": "conferencia_dry_run" if config.conferencia else "ok",
        "chamadas": conta.chamadas,
        "itens_classificados": conta.itens_classificados,
    }


@asset(
    key=AssetKey("p9"),
    deps=[AssetKey("p8")],
    partitions_def=concursos_partitions,
    description="P9 Curadoria da classificação (portão humano)",
    group_name="pipeline",
)
def p9_curadoria_classificacao(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict:
    slug = context.partition_key
    context.log.info(f"[P9] Curadoria da classificação para {slug}")
    return _nao_implementado(context, "P9", slug)


@asset(
    key=AssetKey("p10"),
    deps=[AssetKey("p9")],
    partitions_def=concursos_partitions,
    description="P10 Relatórios e Datasette de revisão",
    group_name="pipeline",
)
def p10_relatorios_revisao(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict:
    slug = context.partition_key
    context.log.info(f"[P10] Relatórios de revisão para {slug}")

    if not config.conferencia:
        from scripts.atualizar_revisao import atualizar_artefatos_revisao

        # ATENÇÃO: global; `--no-conferencia` não é seguro antes da D5b.
        atualizar_artefatos_revisao()
        return {"slug": slug, "etapa": "P10", "status": "ok"}

    return {"slug": slug, "etapa": "P10", "status": "conferencia_sem_acao"}


@asset(
    key=AssetKey("p11"),
    deps=[AssetKey("p10")],
    partitions_def=concursos_partitions,
    description="P11 Site público de questões",
    group_name="pipeline",
)
def p11_site_publico(context: AssetExecutionContext, config: PipelineConfig) -> dict:
    slug = context.partition_key
    context.log.info(f"[P11] Verificação do site público para {slug}")
    return _nao_implementado(context, "P11", slug)


TODOS_ASSETS = [
    p0_backup,
    p1_download_concurso,
    p2_chunking_edital,
    p3_taxonomia_edital,
    p4_carga_questoes,
    p4b_reprocessamento,
    p5_conferencia_lote,
    p6_dispersao_arvore,
    p7_curadoria_arvore,
    p8_classificacao_questoes,
    p9_curadoria_classificacao,
    p10_relatorios_revisao,
    p11_site_publico,
]
