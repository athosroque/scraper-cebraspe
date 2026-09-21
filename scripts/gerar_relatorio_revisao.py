"""Gera relatório HTML estático de página única por edital para o checkpoint
de revisão humana da Etapa 4 — texto-fonte do edital e taxonomia extraída
lado a lado, por chunk, com os alertas de `validar_taxonomia.py` destacados.

Resolve o problema de fazer o de-para manualmente entre as tabelas
`chunks`/`taxonomia_topicos` do Datasette (ver CLAUDE.md seção 12,
2026-09-21): aqui a comparação já vem pronta numa página só, sem precisar
alternar entre tabelas/queries. Não substitui o Datasette (que continua
servindo busca full-text e navegação tabular) — os dois se complementam e
o Datasette serve estes arquivos como estático (ver `docker-compose.yml`,
`--static relatorio:/data/relatorio`).

HTML puro (stdlib, sem Jinja2) — mesma filosofia de stack enxuta do resto
do projeto.

Uso:
    python -m scripts.gerar_relatorio_revisao [revisao_piloto_dir]
"""

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.edital_parser import PADRAO_ITEM_NUMERADO
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
RELATORIO_SUBDIR = "relatorio"

CSS = """
:root { color-scheme: light dark; }
body { font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 1.5rem;
       background: Canvas; color: CanvasText; }
h1 { font-size: 1.4rem; }
.totais { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.totais .item { background: color-mix(in srgb, CanvasText 6%, Canvas); border-radius: 8px;
                 padding: 0.5rem 1rem; }
.totais .item strong { display: block; font-size: 1.3rem; }
.chunk { border: 1px solid color-mix(in srgb, CanvasText 20%, Canvas); border-radius: 10px;
         margin-bottom: 1.25rem; overflow: hidden; }
.chunk-header { background: color-mix(in srgb, CanvasText 6%, Canvas); padding: 0.6rem 1rem;
                font-size: 0.9rem; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; }
.chunk-header .materia { font-weight: 600; }
.chunk-header .cargo { opacity: 0.75; }
.chunk-header .classificacao { font-size: 0.8rem; border-radius: 999px; padding: 0 0.6rem;
                               background: color-mix(in srgb, #2563eb 14%, Canvas); }
.chunk-header .classificacao.sem { background: color-mix(in srgb, #d97706 25%, Canvas); }
.alertas-chunk { padding: 0.5rem 1rem; font-size: 0.85rem; background: color-mix(in srgb, #d97706 12%, Canvas); }
.alertas-chunk .alerta { display: block; }
.alertas-chunk .topico_extra { background: color-mix(in srgb, #2563eb 10%, Canvas); }
.alertas-chunk .topico_divergencia_leve { color: GrayText; font-style: italic; }
.cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }
.col { padding: 1rem; font-size: 0.9rem; line-height: 1.5; }
.col.fonte { border-right: 1px solid color-mix(in srgb, CanvasText 20%, Canvas); white-space: pre-wrap; }
.col.fonte mark { background: color-mix(in srgb, #d97706 35%, Canvas); }
.col.taxonomia ul { margin: 0; padding-left: 1.2rem; }
.col.taxonomia li.topico { margin-bottom: 0.4rem; }
.col.taxonomia li.subtopico { font-size: 0.85rem; opacity: 0.85; }
.falha { color: #b91c1c; font-weight: 600; padding: 1rem; }
.index-lista { list-style: none; padding: 0; }
.index-lista li { padding: 0.6rem 0; border-bottom: 1px solid color-mix(in srgb, CanvasText 15%, Canvas); }
.index-lista a { font-weight: 600; }
.badge { display: inline-block; border-radius: 999px; padding: 0.1rem 0.6rem; font-size: 0.8rem;
         background: color-mix(in srgb, CanvasText 10%, Canvas); margin-left: 0.4rem; }
.badge.alerta { background: color-mix(in srgb, #d97706 25%, Canvas); }
.alertas-edital-box { margin-bottom: 1.5rem; padding: 1rem; border-radius: 6px; background: color-mix(in srgb, #dc2626 12%, Canvas); border: 1px solid color-mix(in srgb, #dc2626 40%, Canvas); }
.alertas-edital-box .alerta { font-size: 0.95rem; font-weight: 500; margin-bottom: 0.4rem; color: #dc2626; }
"""


def _destacar_itens_ausentes(texto: str, posicoes_ausentes: set[int]) -> str:
    """Marca com <mark> os itens de primeiro nível sinalizados como ausentes.

    Usa a posição do item na ordem de aparição (não o número) — números
    podem se repetir quando o texto-fonte vem corrompido no PDF (ver
    `validar_taxonomia.comparar_chunk`), e destacar por número marcaria
    todas as ocorrências repetidas, não só a sinalizada.
    """
    matches = list(PADRAO_ITEM_NUMERADO.finditer(texto))
    if not matches:
        return escape(texto)

    partes = [escape(texto[: matches[0].start()])]
    for i, match in enumerate(matches):
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        trecho = escape(texto[match.start() : fim])
        if i in posicoes_ausentes:
            partes.append(f"<mark>{trecho}</mark>")
        else:
            partes.append(trecho)
    return "".join(partes)


def _renderizar_taxonomia(taxonomia: dict | None) -> str:
    if not taxonomia or not taxonomia.get("topicos"):
        return "<p><em>Sem taxonomia extraída.</em></p>"
    itens = []
    for topico in taxonomia["topicos"]:
        subitens = "".join(f"<li class='subtopico'>{escape(s)}</li>" for s in topico.get("subtopicos", []))
        itens.append(
            f"<li class='topico'><strong>{escape(topico['nome'])}</strong>"
            f"{'<ul>' + subitens + '</ul>' if subitens else ''}</li>"
        )
    return f"<ul>{''.join(itens)}</ul>"


def _renderizar_alertas_chunk(alertas: list[dict]) -> str:
    if not alertas:
        return ""
    linhas = []
    for alerta in alertas:
        if alerta["tipo"] == "topico_ausente":
            linhas.append(
                f"<span class='alerta topico_ausente'>⚠ item #{alerta.get('numero_item') or '?'} ausente na taxonomia: "
                f"“{escape(alerta.get('texto_item_origem') or '')}”</span>"
            )
        elif alerta["tipo"] == "topico_extra":
            linhas.append(
                f"<span class='alerta topico_extra'>ℹ tópico extraído sem correspondência literal na fonte: "
                f"“{escape(alerta.get('topico_nome_extraido') or '')}”</span>"
            )
        elif alerta["tipo"] == "topico_divergencia_leve":
            linhas.append(
                f"<span class='alerta topico_divergencia_leve'>ⓘ informativo — nome parafraseado/corrigido "
                f"em relação à fonte (não conta como alerta): “{escape(alerta.get('topico_nome_extraido') or '')}”</span>"
            )
        else:
            linhas.append(f"<span class='alerta'>⚠ {escape(alerta['tipo'])}</span>")
    return f"<div class='alertas-chunk'>{''.join(linhas)}</div>"


ROTULOS_TIPO_CONHECIMENTO = {"basico": "Básico", "especifico": "Específico", "complementar": "Complementar"}
ROTULOS_NIVEL = {"superior": "Superior", "medio": "Médio"}


def _renderizar_classificacao(chunk_auditoria: dict) -> str:
    if "tipo_conhecimento" not in chunk_auditoria:
        return ""  # auditoria anterior ao ADR-020
    tipo = ROTULOS_TIPO_CONHECIMENTO.get(chunk_auditoria.get("tipo_conhecimento"), "sem bloco")
    nivel = ROTULOS_NIVEL.get(chunk_auditoria.get("nivel"), "sem nível")
    rotulo = f"{tipo} · {nivel}"
    if chunk_auditoria.get("apenas_discursiva"):
        rotulo += " · só discursiva"
    sem = " sem" if chunk_auditoria.get("tipo_conhecimento") is None or chunk_auditoria.get("nivel") is None else ""
    return f"<span class='classificacao{sem}'>{escape(rotulo)}</span>"


def _rotulo_concurso(resultado: dict) -> str:
    concurso = resultado.get("concurso") or {}
    return f"{concurso['slug']} — " if concurso.get("slug") else ""


def renderizar_chunk(chunk_auditoria: dict, resultado_chunk: dict | None, alertas: list[dict]) -> str:
    posicoes_ausentes = {
        a["posicao_item"] for a in alertas if a["tipo"] == "topico_ausente" and a.get("posicao_item") is not None
    }
    materia = escape(chunk_auditoria.get("materia") or "")
    cargo = escape(chunk_auditoria.get("cargo") or "—")
    header = (
        f"<div class='chunk-header'><span class='materia'>#{chunk_auditoria.get('chunk_index')} — {materia}</span>"
        f"{_renderizar_classificacao(chunk_auditoria)}<span class='cargo'>{cargo}</span></div>"
    )

    status = chunk_auditoria.get("status")
    if status is not None and status != "sucesso":
        # Qualquer status que não seja "sucesso" — não só o literal "falha"
        # genérico, mas também status específicos como
        # `STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO` (ADR-021) — significa que
        # não há taxonomia extraída pra mostrar (`resultado_chunk` é None).
        corpo = f"<div class='falha'>Chunk com falha na extração ({escape(status)}) — sem taxonomia.</div>"
        return f"<div class='chunk'>{header}{_renderizar_alertas_chunk(alertas)}{corpo}</div>"

    texto_fonte = chunk_auditoria.get("texto_enviado_llm") or ""
    fonte_html = _destacar_itens_ausentes(texto_fonte, posicoes_ausentes)
    taxonomia_html = _renderizar_taxonomia(resultado_chunk.get("taxonomia_extraida") if resultado_chunk else None)

    corpo = (
        "<div class='cols'>"
        f"<div class='col fonte'>{fonte_html}</div>"
        f"<div class='col taxonomia'>{taxonomia_html}</div>"
        "</div>"
    )
    return f"<div class='chunk'>{header}{_renderizar_alertas_chunk(alertas)}{corpo}</div>"


def renderizar_edital(resultado: dict, auditoria: dict, validacao: dict | None) -> str:
    resultado_por_index = {
        item["chunk_index"]: item for item in resultado["resultados"] if item.get("chunk_index") is not None
    }
    alertas_por_chunk: dict[int | None, list[dict]] = {}
    for alerta in (validacao or {}).get("alertas", []):
        alertas_por_chunk.setdefault(alerta.get("chunk_index"), []).append(alerta)

    alertas_edital_html = ""
    alertas_edital = alertas_por_chunk.get(None, [])
    if alertas_edital:
        linhas = []
        for a in alertas_edital:
            linhas.append(
                f"<div class='alerta'>🚨 <strong>{escape(a['tipo'])}:</strong> {escape(str(a.get('texto_item_origem') or ''))}</div>"
            )
        alertas_edital_html = f"<div class='alertas-edital-box'>{''.join(linhas)}</div>"

    chunks_html = "".join(
        renderizar_chunk(
            chunk_auditoria,
            resultado_por_index.get(chunk_auditoria.get("chunk_index")),
            alertas_por_chunk.get(chunk_auditoria.get("chunk_index"), []),
        )
        for chunk_auditoria in auditoria["chunks"]
    )

    total_alertas = validacao["total_alertas"] if validacao else "—"
    total_informativos = validacao.get("total_informativos", 0) if validacao else "—"
    edital = escape(_rotulo_concurso(resultado) + resultado["edital"])
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisão — {edital}</title><style>{CSS}</style></head>
<body>
<p><a href="index.html">← todos os editais</a></p>
<h1>{edital}</h1>
<div class="totais">
  <div class="item"><strong>{resultado["total_chunks"]}</strong>chunks</div>
  <div class="item"><strong>{resultado["extraidos_com_sucesso"]}</strong>sucesso</div>
  <div class="item"><strong>{resultado["falhas"]}</strong>falhas</div>
  <div class="item"><strong>{total_alertas}</strong>alertas de validação</div>
  <div class="item"><strong>{total_informativos}</strong>informativos</div>
</div>
{alertas_edital_html}
<p><em>{escape(resultado["status_revisao_humana"])}</em></p>
{chunks_html}
</body></html>
"""


def renderizar_index(editais: list[dict]) -> str:
    itens = "".join(
        f"<li><a href='{escape(e['arquivo_html'])}'>{escape(e['edital'])}</a>"
        f"<span class='badge'>{e['total_chunks']} chunks</span>"
        f"<span class='badge{' alerta' if e['total_alertas'] else ''}'>{e['total_alertas']} alertas</span></li>"
        for e in editais
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisão de editais — scraper_cebraspe</title><style>{CSS}</style></head>
<body>
<h1>Revisão de editais (Etapa 4)</h1>
<ul class="index-lista">{itens}</ul>
</body></html>
"""


def _carregar_trio(json_path: Path) -> tuple[dict, dict | None, dict | None]:
    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    auditoria = json.loads(auditoria_path.read_text(encoding="utf-8")) if auditoria_path.exists() else None
    validacao_path = json_path.parent / f"{json_path.stem}.validacao.json"
    validacao = json.loads(validacao_path.read_text(encoding="utf-8")) if validacao_path.exists() else None
    return resultado, auditoria, validacao


def gerar_relatorios(revisao_dir: Path = REVISAO_DIR_PADRAO) -> Path:
    saida_dir = revisao_dir / RELATORIO_SUBDIR
    saida_dir.mkdir(exist_ok=True)

    jsons = sorted(
        p
        for p in revisao_dir.glob("*.json")
        if not p.name.endswith(".auditoria.json") and not p.name.endswith(".validacao.json")
    )

    editais_index = []
    for json_path in jsons:
        resultado, auditoria, validacao = _carregar_trio(json_path)
        if auditoria is None:
            logger.warning(f"{resultado['edital']}: sem .auditoria.json — pulando relatório (formato legado).")
            continue

        html = renderizar_edital(resultado, auditoria, validacao)
        arquivo_html = f"{json_path.stem}.html"
        (saida_dir / arquivo_html).write_text(html, encoding="utf-8")
        editais_index.append(
            {
                "edital": _rotulo_concurso(resultado) + resultado["edital"],
                "arquivo_html": arquivo_html,
                "total_chunks": resultado["total_chunks"],
                "total_alertas": validacao["total_alertas"] if validacao else 0,
            }
        )
        logger.info(f"{resultado['edital']}: relatório gerado em {saida_dir / arquivo_html}.")

    (saida_dir / "index.html").write_text(renderizar_index(editais_index), encoding="utf-8")
    logger.info(f"Índice de relatórios gerado em {saida_dir / 'index.html'} — {len(editais_index)} edital(is).")
    return saida_dir


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    gerar_relatorios(diretorio)
