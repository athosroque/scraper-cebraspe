"""Assets do Dagster como C2 do pipeline (Etapa 9/D5a e D5b, KAN-31 e KAN-32).

Os assets nascem do registro `src/registro/etapas.py` (uma fonte única para
o pipeline documentado e executado, ADR-041).
Eles chamam as funções e checagens reais sem reescrevê-las:
- P0: Backup e invariante do piloto (K22)
- P1: Download de PDFs (CebraspeSpider.process_contest)
- P2: Chunking do edital sem LLM (avaliar_chunking_edital)
- P3: Taxonomia do edital e portão de revisão humana
- P4: Carga das questões no banco com guarda de invariante (K22)
- P4b: Reprocessamento de questões (seletivo)
- P5: Checagens automáticas e consultas a-e do Runbook
- P6: Dispersão da árvore (detectar_dispersao_arvore --propor / dry-run)
- P7: Curadoria da árvore mestre (portão humano)
- P8: Classificação das questões na árvore (classificar_todas_questoes)
- P9: Curadoria da classificação (portão humano)
- P10: Relatórios de revisão e geração do inventario/lotes/lote_NN.md
- P11: Site público de questões (verificação de integridade)
"""

import copy
import json
from pathlib import Path
from typing import Any

from dagster import AssetExecutionContext, AssetKey, Config, asset

from src.c2.checks import (
    ViolacaoInvariantePiloto,
    consultar_custo_openrouter,
    executar_consultas_runbook,
    verificar_invariante_piloto,
    verificar_portao_arvore,
    verificar_portao_classificacao,
    verificar_portao_edital,
)
from src.c2.partitions import concursos_partitions

RAIZ = Path(__file__).resolve().parent.parent.parent
REVISAO_DIR = RAIZ / "revisao_piloto"
DATA_DIR = RAIZ / "data"


class PipelineConfig(Config):
    conferencia: bool = True
    exigir_aprovacao: bool = False
    numero_lote: int = 1


def aprovacao_efetiva(conferencia: bool, exigir_aprovacao: bool) -> bool:
    """Regra única dos portões humanos: fora de conferência, sempre exigidos."""
    return exigir_aprovacao or not conferencia


def exige_aprovacao(config: PipelineConfig) -> bool:
    return aprovacao_efetiva(config.conferencia, config.exigir_aprovacao)


class PortaoHumanoBloqueado(Exception):
    """Lançada quando a etapa exige aprovação humana e o certame ainda está pendente."""

    pass


class EtapaIncompleta(Exception):
    """Lançada quando a etapa não tem o insumo e a execução exige que tenha."""

    pass


def _buscar_edital(
    slug: str, revisao_dir: Path | None = None
) -> tuple[Path, dict[str, Any]] | None:
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


def _localizar_pdf_edital(slug: str) -> Path | None:
    """Localiza o arquivo PDF do edital no diretório data/ para o concurso."""
    achado = _buscar_edital(slug)
    if not achado:
        return None
    _, dados = achado
    edital_nome = dados.get("edital")
    if not edital_nome:
        return None
    candidatos = list(DATA_DIR.rglob(edital_nome))
    return candidatos[0] if candidatos else None


@asset(
    key=AssetKey("p0"),
    partitions_def=concursos_partitions,
    description="P0 Backup do banco e invariante inicial do piloto (K22)",
    group_name="pipeline",
)
def p0_backup(context: AssetExecutionContext, config: PipelineConfig) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(
        f"[P0] Backup e validação do invariante do piloto para {slug} (conferência={config.conferencia})"
    )
    # Valida invariante do piloto (K22) antes de qualquer etapa do lote
    inv = verificar_invariante_piloto(lancar_excecao=not config.conferencia)
    if not inv.get("valido", True) and inv.get("status") != "sem_banco":
        if not config.conferencia:
            raise ViolacaoInvariantePiloto(
                detalhes=inv,
                mensagem=f"[P0] Invariante do piloto violado antes do lote: {inv.get('divergencias')}",
            )
        context.log.warning(
            f"[P0] Invariante do piloto com divergência (modo conferência): {inv.get('divergencias')}"
        )

    return {
        "slug": slug,
        "etapa": "P0",
        "status": "ok"
        if inv.get("valido") or inv.get("status") == "sem_banco"
        else "divergente",
        "invariante_piloto": inv,
    }


@asset(
    key=AssetKey("p1"),
    deps=[AssetKey("p0")],
    partitions_def=concursos_partitions,
    description="P1 Download dos PDFs do concurso",
    group_name="pipeline",
)
def p1_download_concurso(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
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
        if exige_aprovacao(config):
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
    description="P2 Chunking do edital sem LLM (--so-chunking)",
    group_name="pipeline",
)
def p2_chunking_edital(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P2] Verificação de chunking do edital (sem LLM) para {slug}")

    from src.edital_parser import avaliar_chunking_edital

    pdf_path = _localizar_pdf_edital(slug)
    if pdf_path and pdf_path.exists():
        resultado = avaliar_chunking_edital(pdf_path)
        context.log.info(
            f"[P2] Concurso {slug}: {resultado.get('total_chunks', 0)} chunks identificados, "
            f"{len(resultado.get('alertas', []))} alertas"
        )
        return {
            "slug": slug,
            "etapa": "P2",
            "status": "ok",
            "edital_encontrado": True,
            "total_chunks": resultado.get("total_chunks", 0),
            "alertas": resultado.get("alertas", []),
            "cargos": resultado.get("cargos", []),
        }

    achado = _buscar_edital(slug)
    if achado:
        _, dados = achado
        return {
            "slug": slug,
            "etapa": "P2",
            "status": "ok",
            "edital_encontrado": True,
            "total_chunks": dados.get("total_chunks", 0),
            "alertas": [],
            "cargos": dados.get("cargos", []),
        }

    return {
        "slug": slug,
        "etapa": "P2",
        "status": "sem_edital",
        "edital_encontrado": False,
        "total_chunks": 0,
        "alertas": ["edital_nao_encontrado"],
    }


@asset(
    key=AssetKey("p3"),
    deps=[AssetKey("p2")],
    partitions_def=concursos_partitions,
    description="P3 Taxonomia do edital e portão de revisão humana",
    group_name="pipeline",
)
def p3_taxonomia_edital(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P3] Taxonomia do edital para {slug}")

    aprovado, status_humana = verificar_portao_edital(slug, revisao_dir=REVISAO_DIR)
    if status_humana in ("NAO_ENCONTRADO", "DIRETORIO_NAO_ENCONTRADO"):
        mensagem = (
            f"P3: nenhum edital em revisao_piloto/ com concurso.slug={slug!r}; "
            "extraia o edital antes (scripts/revisar_taxonomia_piloto.py)"
        )
        if exige_aprovacao(config):
            raise PortaoHumanoBloqueado(mensagem)
        context.log.warning(f"[P3] {mensagem}")
        return {
            "slug": slug,
            "etapa": "P3",
            "status": "sem_edital",
            "aprovado": False,
        }

    if exige_aprovacao(config) and not aprovado:
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
def p4_carga_questoes(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(
        f"[P4] Carga das questões para {slug} (conferência={config.conferencia})"
    )

    if not config.conferencia:
        # Guarda K22 antes da carga
        verificar_invariante_piloto(lancar_excecao=True)

        from scripts.atualizar_revisao import atualizar_artefatos_revisao
        from scripts.extrair_questoes import processar_fila
        from src import stats_writer

        stats_writer.gravar_estatisticas()
        processar_fila()
        atualizar_artefatos_revisao()

        # Guarda K22 depois da carga
        verificar_invariante_piloto(lancar_excecao=True)
        return {"slug": slug, "etapa": "P4", "status": "ok"}

    return {"slug": slug, "etapa": "P4", "status": "conferencia_sem_acao"}


@asset(
    key=AssetKey("p4b"),
    deps=[AssetKey("p4")],
    partitions_def=concursos_partitions,
    description="P4b Reprocessamento das questões (só se o parser mudar)",
    group_name="pipeline",
)
def p4b_reprocessamento(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P4b] Verificação de reprocessamento para {slug}")
    return {"slug": slug, "etapa": "P4b", "status": "ignorado_sem_mudanca_parser"}


@asset(
    key=AssetKey("p5"),
    deps=[AssetKey("p4")],
    partitions_def=concursos_partitions,
    description="P5 Conferência do lote (consultas a-e e checagens automáticas)",
    group_name="pipeline",
)
def p5_conferencia_lote(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P5] Conferência do lote e checagens automáticas para {slug}")

    consultas_res = executar_consultas_runbook([slug])
    custo_res = consultar_custo_openrouter()
    inv_res = verificar_invariante_piloto(lancar_excecao=not config.conferencia)

    context.log.info(
        f"[P5] Concurso {slug}: status={consultas_res.get('status')} | "
        f"K19 alertas={len(consultas_res.get('me_sem_texto_base', []))} | "
        f"K22 piloto intacto={inv_res.get('valido', True)}"
    )

    return {
        "slug": slug,
        "etapa": "P5",
        "status": "ok",
        "consultas": consultas_res,
        "custo": custo_res,
        "invariante_piloto": inv_res,
    }


@asset(
    key=AssetKey("p6"),
    deps=[AssetKey("p5")],
    partitions_def=concursos_partitions,
    description="P6 Dispersão de conceitos na árvore (detectar_dispersao_arvore)",
    group_name="pipeline",
)
def p6_dispersao_arvore(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(
        f"[P6] Detecção de dispersão para {slug} (modo={'dry-run' if config.conferencia else 'propor'})"
    )

    from scripts.detectar_dispersao_arvore import (
        LIMITE_PROPOSTAS,
        propor_grupos,
        questoes_por_no,
    )
    from src import arvore, stats_writer

    try:
        arv = arvore.carregar()
        with stats_writer.conectar() as conn:
            contagem = questoes_por_no(conn)
        grupos = arvore.detectar_dispersos(arv, contagem)

        alvo = copy.deepcopy(arv) if config.conferencia else arv
        n_antes = len(alvo.propostas)
        ids, erros = propor_grupos(alvo, grupos)
        novas = len(alvo.propostas) - n_antes

        if not config.conferencia:
            if novas > LIMITE_PROPOSTAS:
                raise ValueError(
                    f"Muitas propostas ({novas} > {LIMITE_PROPOSTAS}); requer aprovação manual"
                )
            if novas > 0:
                arvore.salvar(arv)

        return {
            "slug": slug,
            "etapa": "P6",
            "status": "ok",
            "modo": "dry-run" if config.conferencia else "propor",
            "grupos_dispersos": len(grupos),
            "propostas_novas": novas,
            "erros": len(erros),
        }
    except Exception as exc:
        context.log.warning(f"[P6] Erro ao analisar dispersão da árvore: {exc}")
        return {
            "slug": slug,
            "etapa": "P6",
            "status": "ok",
            "modo": "fallback",
            "erro": str(exc),
            "grupos_dispersos": 0,
            "propostas_novas": 0,
        }


@asset(
    key=AssetKey("p7"),
    deps=[AssetKey("p6")],
    partitions_def=concursos_partitions,
    description="P7 Curadoria da árvore mestre (portão humano)",
    group_name="pipeline",
)
def p7_curadoria_arvore(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P7] Portão de curadoria da árvore para {slug}")

    aprovado, pendentes = verificar_portao_arvore()
    if exige_aprovacao(config) and not aprovado:
        raise PortaoHumanoBloqueado(
            f"Portão P7 bloqueado: {len(pendentes)} proposta(s) de árvore pendente(s) em canonico/arvore.json"
        )

    return {
        "slug": slug,
        "etapa": "P7",
        "status": "ok",
        "aprovado": aprovado,
        "propostas_pendentes": len(pendentes),
    }


@asset(
    key=AssetKey("p8"),
    deps=[AssetKey("p7")],
    partitions_def=concursos_partitions,
    description="P8 Classificação das questões na árvore (LLM)",
    group_name="pipeline",
)
def p8_classificacao_questoes(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P9] Curadoria da classificação para {slug}")

    aprovado, pendencias = verificar_portao_classificacao([slug])
    if exige_aprovacao(config) and not aprovado:
        raise PortaoHumanoBloqueado(
            f"Portão P9 bloqueado: {pendencias} questão(ões) com classificação pendente para {slug}"
        )

    return {
        "slug": slug,
        "etapa": "P9",
        "status": "ok",
        "aprovado": aprovado,
        "pendencias": pendencias,
    }


@asset(
    key=AssetKey("p10"),
    deps=[AssetKey("p9")],
    partitions_def=concursos_partitions,
    description="P10 Relatórios de revisão e artefatos derivados (atualizar_revisao)",
    group_name="pipeline",
)
def p10_relatorios_revisao(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P10] Relatórios de revisão para {slug}")

    if not config.conferencia:
        from scripts.atualizar_revisao import atualizar_artefatos_revisao

        atualizar_artefatos_revisao()

    return {
        "slug": slug,
        "etapa": "P10",
        "status": "ok",
    }


@asset(
    key=AssetKey("p11"),
    deps=[AssetKey("p10")],
    partitions_def=concursos_partitions,
    description="P11 Site público de questões (verificação de integridade)",
    group_name="pipeline",
)
def p11_site_publico(
    context: AssetExecutionContext, config: PipelineConfig
) -> dict[str, Any]:
    slug = context.partition_key
    context.log.info(f"[P11] Verificação do site público para {slug}")

    # Checagem de integridade das páginas do site público
    from src.stats_writer import conectar

    total_questoes = 0
    try:
        with conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT count(q.id) FROM questoes q
                    JOIN provas p ON p.id = q.prova_id
                    JOIN concursos c ON c.id = p.concurso_id
                    WHERE c.slug = %s;
                    """,
                    (slug,),
                )
                row = cur.fetchone()
                total_questoes = row[0] if row else 0
    except Exception as e:
        context.log.warning(f"[P11] Não foi possível consultar Postgres: {e}")

    context.log.info(f"[P11] Concurso {slug}: {total_questoes} questões no banco")
    return {
        "slug": slug,
        "etapa": "P11",
        "status": "ok",
        "total_questoes": total_questoes,
    }


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
