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
from collections.abc import Callable
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import arvore as arv_mod
from src import mapeamento_revisao
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
.badge.ok { background: color-mix(in srgb, #16a34a 25%, Canvas); }
.badge.bloq { background: color-mix(in srgb, #dc2626 30%, Canvas); font-weight: 600; }
.badge.info { background: color-mix(in srgb, #2563eb 18%, Canvas); }
.badge.novo { background: color-mix(in srgb, #7c3aed 25%, Canvas); font-weight: 600; }
.badge.neutro { opacity: 0.85; }
.novo-tag { display: inline-block; border-radius: 4px; padding: 0 0.35rem; margin-left: 0.4rem;
            font-size: 0.7rem; font-weight: 700; letter-spacing: 0.04em; color: #fff; background: #7c3aed; }
.resumo-topo { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.resumo-topo .item { border-radius: 8px; padding: 0.5rem 1rem; min-width: 8rem;
                     background: color-mix(in srgb, CanvasText 6%, Canvas); }
.resumo-topo .item strong { display: block; font-size: 1.5rem; }
.resumo-topo .item.pend { background: color-mix(in srgb, #d97706 20%, Canvas); }
.resumo-topo .item.prob { background: color-mix(in srgb, #dc2626 18%, Canvas); }
.resumo-topo .item.nov { background: color-mix(in srgb, #7c3aed 16%, Canvas); }
.filtros { margin-bottom: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }
.filtros button { font: inherit; padding: 0.3rem 0.9rem; border-radius: 999px; cursor: pointer;
                  border: 1px solid color-mix(in srgb, CanvasText 35%, Canvas); background: Canvas; color: CanvasText; }
.filtros button[aria-pressed="true"] { background: CanvasText; color: Canvas; }
.filtros button:focus-visible, a:focus-visible, summary:focus-visible { outline: 3px solid #2563eb; outline-offset: 2px; }
.index-lista li[hidden] { display: none; }
.secao-pendentes { border: 2px solid #d97706; border-radius: 10px; padding: 0.5rem 1rem 0.75rem;
                   background: color-mix(in srgb, #d97706 6%, Canvas); margin-bottom: 1.5rem; }
.secao-pendentes h2 { margin-top: 0.5rem; }
details.secao { margin-bottom: 1.5rem; }
details.secao > summary { cursor: pointer; font-size: 1.2rem; font-weight: 600; padding: 0.4rem 0; }
.vazio { opacity: 0.7; font-style: italic; }
.revisar-box { margin-bottom: 1.5rem; padding: 1rem 1.25rem; border-radius: 8px;
               border: 2px solid #7c3aed; background: color-mix(in srgb, #7c3aed 8%, Canvas); }
.revisar-box h2 { margin: 0 0 0.5rem; font-size: 1.15rem; }
.revisar-box h3 { margin: 0.8rem 0 0.2rem; font-size: 1rem; }
.revisar-box ul { margin: 0.2rem 0; padding-left: 1.3rem; }
.revisar-box .ok { color: #15803d; font-weight: 600; }
.revisar-box .sub { font-size: 0.85rem; opacity: 0.8; }
.revisar-box .legenda { font-size: 0.85rem; opacity: 0.85; margin: 0 0 0.5rem; }
.revisar-box .novos { border: 2px solid #7c3aed; border-radius: 8px; padding: 0.2rem 0.9rem 0.6rem;
                      background: color-mix(in srgb, #7c3aed 18%, Canvas); }
.revisar-box table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
.revisar-box th, .revisar-box td { text-align: left; padding: 0.25rem 0.5rem; vertical-align: top;
        border-bottom: 1px solid color-mix(in srgb, CanvasText 15%, Canvas); }
.badge.proposta { background: color-mix(in srgb, #0d9488 25%, Canvas); }
.origem-box { margin-bottom: 1.5rem; padding: 0.75rem 1.25rem; border-radius: 8px;
              border: 1px solid color-mix(in srgb, CanvasText 25%, Canvas); }
.origem-box h2 { margin: 0 0 0.5rem; font-size: 1.05rem; }
.origem-box .cards { display: flex; gap: 0.75rem; flex-wrap: wrap; }
.origem-box .card { border-radius: 8px; padding: 0.4rem 0.9rem; min-width: 9rem;
                    background: color-mix(in srgb, CanvasText 6%, Canvas); font-size: 0.85rem; }
.origem-box .card strong { display: block; font-size: 1.4rem; }
.origem-box .card.auto { background: color-mix(in srgb, #16a34a 16%, Canvas); }
.origem-box .card.proposta { background: color-mix(in srgb, #0d9488 22%, Canvas); }
.origem-box .card.sem { background: color-mix(in srgb, #7c3aed 22%, Canvas); }
.nada-a-decidir { margin-bottom: 1rem; padding: 0.6rem 1.25rem; border-radius: 8px; font-weight: 700;
                  color: #14532d; background: color-mix(in srgb, #16a34a 22%, Canvas);
                  border: 2px solid #16a34a; }
.chunk:target { outline: 3px solid #7c3aed; }
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


def _chave(texto: str | None) -> str:
    return " ".join((texto or "").casefold().split())


NOVO_TAG = "<span class='novo-tag'>NOVO</span>"


def _renderizar_taxonomia(
    taxonomia: dict | None, assuntos_novos: set[str] | None = None
) -> str:
    if not taxonomia or not taxonomia.get("topicos"):
        return "<p><em>Sem taxonomia extraída.</em></p>"
    assuntos_novos = assuntos_novos or set()
    itens = []
    for topico in taxonomia["topicos"]:
        subitens = "".join(
            f"<li class='subtopico'>{escape(s)}</li>"
            for s in topico.get("subtopicos", [])
        )
        novo = NOVO_TAG if _chave(topico["nome"]) in assuntos_novos else ""
        itens.append(
            f"<li class='topico'><strong>{escape(topico['nome'])}</strong>{novo}"
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
        elif alerta["tipo"] == "subitem_ausente":
            linhas.append(
                f"<span class='alerta topico_ausente'>⚠ subitem {escape(str(alerta.get('numero_item') or '?'))} "
                f"ausente na taxonomia: “{escape(alerta.get('texto_item_origem') or '')}”</span>"
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


ROTULOS_TIPO_CONHECIMENTO = {
    "basico": "Básico",
    "especifico": "Específico",
    "complementar": "Complementar",
}
ROTULOS_NIVEL = {"superior": "Superior", "medio": "Médio"}


def _renderizar_classificacao(chunk_auditoria: dict) -> str:
    if "tipo_conhecimento" not in chunk_auditoria:
        return ""  # auditoria anterior ao ADR-020
    tipo = ROTULOS_TIPO_CONHECIMENTO.get(
        chunk_auditoria.get("tipo_conhecimento"), "sem bloco"
    )
    nivel = ROTULOS_NIVEL.get(chunk_auditoria.get("nivel"), "sem nível")
    rotulo = f"{tipo} · {nivel}"
    if chunk_auditoria.get("apenas_discursiva"):
        rotulo += " · só discursiva"
    if chunk_auditoria.get("cargos_restritos"):
        rotulo += " · só cargos " + ", ".join(
            str(n) for n in chunk_auditoria["cargos_restritos"]
        )
    sem = (
        " sem"
        if chunk_auditoria.get("tipo_conhecimento") is None
        or chunk_auditoria.get("nivel") is None
        else ""
    )
    return f"<span class='classificacao{sem}'>{escape(rotulo)}</span>"


def _rotulo_concurso(resultado: dict) -> str:
    concurso = resultado.get("concurso") or {}
    return f"{concurso['slug']} — " if concurso.get("slug") else ""


def renderizar_chunk(
    chunk_auditoria: dict,
    resultado_chunk: dict | None,
    alertas: list[dict],
    disciplina_nova: bool = False,
    assuntos_novos: set[str] | None = None,
) -> str:
    posicoes_ausentes = {
        a["posicao_item"]
        for a in alertas
        if a["tipo"] == "topico_ausente" and a.get("posicao_item") is not None
    }
    materia = escape(chunk_auditoria.get("materia") or "")
    cargo = escape(chunk_auditoria.get("cargo") or "—")
    indice = chunk_auditoria.get("chunk_index")
    tag_disciplina = NOVO_TAG if disciplina_nova else ""
    header = (
        f"<div class='chunk-header'><span class='materia'>#{indice} — {materia}{tag_disciplina}</span>"
        f"{_renderizar_classificacao(chunk_auditoria)}<span class='cargo'>{cargo}</span></div>"
    )
    abre = f"<div class='chunk' id='chunk-{escape(str(indice))}'>"

    status = chunk_auditoria.get("status")
    if status is not None and status != "sucesso":
        # Qualquer status que não seja "sucesso" — não só o literal "falha"
        # genérico, mas também status específicos como
        # `STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO` (ADR-021) — significa que
        # não há taxonomia extraída pra mostrar (`resultado_chunk` é None).
        corpo = f"<div class='falha'>Chunk com falha na extração ({escape(status)}) — sem taxonomia.</div>"
        return f"{abre}{header}{_renderizar_alertas_chunk(alertas)}{corpo}</div>"

    texto_fonte = chunk_auditoria.get("texto_enviado_llm") or ""
    fonte_html = _destacar_itens_ausentes(texto_fonte, posicoes_ausentes)
    taxonomia_html = _renderizar_taxonomia(
        resultado_chunk.get("taxonomia_extraida") if resultado_chunk else None,
        assuntos_novos,
    )

    corpo = (
        "<div class='cols'>"
        f"<div class='col fonte'>{fonte_html}</div>"
        f"<div class='col taxonomia'>{taxonomia_html}</div>"
        "</div>"
    )
    return f"{abre}{header}{_renderizar_alertas_chunk(alertas)}{corpo}</div>"


NOVIDADES_VAZIAS = {
    "disciplinas_novas": [],
    "assuntos_novos": [],
    "total_disciplinas": 0,
    "total_assuntos": 0,
    "total_itens_novos": 0,
    "propostas": [],
    "total_propostas": 0,
}

FuncaoNovidades = Callable[[dict], dict]


def _carregar_funcao_novidades() -> FuncaoNovidades | None:
    """Importa `novidades_do_edital` de forma tolerante: sem o módulo, o
    relatório sai sem a camada de novidades (e avisa no log)."""
    try:
        from src.novidades_edital import novidades_do_edital
    except Exception as erro:  # módulo ausente ou quebrado não derruba o relatório
        logger.warning(f"Novidades indisponíveis (sem destaque de itens novos): {erro}")
        return None
    return novidades_do_edital


def _novidades_seguras(resultado: dict, funcao: FuncaoNovidades | None) -> dict:
    if funcao is None:
        return dict(NOVIDADES_VAZIAS)
    try:
        bruto = funcao(resultado) or {}
    except Exception as erro:
        logger.warning(
            f"{resultado.get('edital')}: falha ao calcular novidades: {erro}"
        )
        return dict(NOVIDADES_VAZIAS)
    return {**NOVIDADES_VAZIAS, **bruto}


def _alertas_por_severidade(validacao: dict | None) -> tuple[int, int]:
    """(bloqueantes, informativos). Alerta sem `severidade` é bloqueante."""
    if not validacao:
        return 0, 0
    alertas = validacao.get("alertas")
    if alertas is None:
        return validacao.get("total_alertas", 0), validacao.get("total_informativos", 0)
    informativos = sum(1 for a in alertas if a.get("severidade") == "informativo")
    return len(alertas) - informativos, informativos


def _situacao(resultado: dict) -> str:
    texto = (resultado.get("status_revisao_humana") or "").strip().upper()
    if texto.startswith("APROVADO"):
        return "aprovado"
    if texto.startswith("PENDENTE"):
        return "pendente"
    return "outro"


def _novos_do_edital(novidades: dict) -> tuple[set[str], set[str]]:
    disciplinas = {_chave(d) for d in novidades.get("disciplinas_novas", [])}
    assuntos = {_chave(a.get("assunto")) for a in novidades.get("assuntos_novos", [])}
    return disciplinas, assuntos


def _chunks_da_disciplina(resultado: dict, auditoria: dict, disciplina: str) -> list:
    """Índices dos chunks cuja matéria (extraída ou do edital) é a disciplina."""
    alvo = _chave(disciplina)
    indices = []
    for chunk in auditoria["chunks"]:
        if _chave(chunk.get("materia")) == alvo:
            indices.append(chunk.get("chunk_index"))
    for item in resultado["resultados"]:
        materia = (item.get("taxonomia_extraida") or {}).get("materia")
        if _chave(materia) == alvo and item.get("chunk_index") not in indices:
            indices.append(item.get("chunk_index"))
    return indices


def _chunks_do_assunto(resultado: dict, assunto: str) -> list:
    alvo = _chave(assunto)
    return [
        item.get("chunk_index")
        for item in resultado["resultados"]
        if any(
            _chave(t["nome"]) == alvo
            for t in (item.get("taxonomia_extraida") or {}).get("topicos", [])
        )
    ]


def _link_chunk(indices: list, rotulo: str | None = None) -> str:
    return " ".join(
        f"<a href='#chunk-{escape(str(i))}'>{escape(rotulo or f'chunk #{i}')}</a>"
        for i in indices[:3]
        if i is not None
    )


def _bloco_origem_mapeamento(linhas: list[dict] | None) -> str:
    """Quadro "De onde veio cada mapeamento", em contagens por categoria."""
    if not linhas:
        return ""
    c = mapeamento_revisao.contar_por_categoria(linhas)
    auto = c["auto"] + c["regra_nome"] + c["dono"]
    cards = [
        ("auto", c["regra_nome"], mapeamento_revisao.ROTULOS["regra_nome"]),
        ("auto", c["auto"], mapeamento_revisao.ROTULOS["auto"]),
        ("auto", c["dono"], mapeamento_revisao.ROTULOS["dono"]),
        ("proposta", c["proposta"], mapeamento_revisao.ROTULOS["proposta"]),
        ("sem", c["sem_equivalente"], mapeamento_revisao.ROTULOS["sem_equivalente"]),
    ]
    html = "".join(
        f"<div class='card {cls}'><strong>{n}</strong>{escape(rotulo)}</div>"
        for cls, n, rotulo in cards
    )
    return (
        "<section class='origem-box' aria-label='De onde veio cada mapeamento'>"
        f"<h2>De onde veio cada mapeamento ({len(linhas)} itens, {auto} já resolvidos)</h2>"
        f"<div class='cards'>{html}</div>"
        "<p class='legenda'>Regra de nome e memória das suas decisões gravam com a mesma "
        "origem (<code>regra</code>); por isso aparecem juntas em "
        "&quot;automático (regra/memória)&quot;.</p></section>"
    )


def _bloco_o_que_revisar(
    resultado: dict,
    auditoria: dict,
    validacao: dict | None,
    novidades: dict,
    mapeamento: list[dict] | None = None,
) -> str:
    # (a) alertas bloqueantes e chunks com falha
    itens_a = []
    for a in (validacao or {}).get("alertas", []):
        if a.get("severidade") == "informativo":
            continue
        chunk = a.get("chunk_index")
        onde = _link_chunk([chunk]) if chunk is not None else "edital"
        detalhe = a.get("texto_item_origem") or a.get("topico_nome_extraido") or ""
        itens_a.append(
            f"<li><span class='badge bloq'>{escape(str(a['tipo']))}</span> {onde}"
            f"{' — ' + escape(str(detalhe)) if detalhe else ''}</li>"
        )
    for c in auditoria["chunks"]:
        status = c.get("status")
        if status is not None and status != "sucesso":
            itens_a.append(
                f"<li><span class='badge bloq'>falha</span> {_link_chunk([c.get('chunk_index')])}"
                f" — {escape(str(status))}</li>"
            )
    # (b) realmente novos: sem nó equivalente, aprovado ou proposto
    itens_b = [
        f"<li><span class='novo-tag'>DISCIPLINA</span> <strong>{escape(str(d))}</strong> "
        f"{_link_chunk(_chunks_da_disciplina(resultado, auditoria, d))}</li>"
        for d in novidades.get("disciplinas_novas", [])
    ]
    for a in novidades.get("assuntos_novos", []):
        subs = a.get("subassuntos") or []
        sub_html = (
            f"<div class='sub'>subassuntos: {escape('; '.join(map(str, subs)))}</div>"
            if subs
            else ""
        )
        itens_b.append(
            f"<li><span class='novo-tag'>ASSUNTO</span> <strong>{escape(str(a.get('assunto')))}</strong> "
            f"<span class='sub'>em {escape(str(a.get('disciplina')))}</span> "
            f"{_link_chunk(_chunks_do_assunto(resultado, a.get('assunto') or ''))}{sub_html}</li>"
        )
    # (c) propostas do LLM a conferir
    linhas_c = []
    detalhe_mapeamento = {
        (m["nivel"], m["item"]): m
        for m in (mapeamento or [])
        if m.get("categoria") == "proposta"
    }
    for p in novidades.get("propostas", []):
        nivel = p.get("nivel")
        if nivel == "disciplina":
            indices = _chunks_da_disciplina(resultado, auditoria, p.get("item") or "")
        else:
            alvo = p.get("assunto") if nivel == "subassunto" else p.get("item")
            indices = _chunks_do_assunto(resultado, alvo or "")
        extra = detalhe_mapeamento.get((nivel, p.get("item"))) or {}
        conf = p.get("confianca") or extra.get("confianca")
        just = extra.get("justificativa")
        linhas_c.append(
            f"<tr><td>{escape(str(p.get('item')))}"
            f"<div class='sub'>{escape(str(nivel))} · {escape(str(p.get('disciplina') or ''))}</div></td>"
            f"<td>{escape(str(p.get('no_caminho') or p.get('no_id')))}</td>"
            f"<td>{escape(str(conf)) if conf is not None else '—'}</td>"
            f"<td>{escape(str(just)) if just else '—'}</td>"
            f"<td>{_link_chunk(indices)}</td></tr>"
        )

    if itens_b:
        novos_html = (
            f"<div class='novos'><h3>Realmente novos — sem nó equivalente ({len(itens_b)})</h3>"
            f"<ul>{''.join(itens_b)}</ul></div>"
        )
    else:
        novos_html = "<h3>Realmente novos — sem nó equivalente (0)</h3><p class='ok'>Nenhum item novo sem equivalente.</p>"
    if linhas_c:
        propostas_html = (
            f"<h3>Propostas da IA a conferir ({len(linhas_c)})</h3>"
            "<table><thead><tr><th>Item do edital</th><th>Nó sugerido (caminho)</th>"
            f"<th>Confiança</th><th>Justificativa da IA</th><th>Onde</th></tr></thead><tbody>{''.join(linhas_c)}</tbody></table>"
        )
    else:
        propostas_html = "<h3>Propostas da IA a conferir (0)</h3><p class='ok'>Nenhuma proposta pendente.</p>"

    alertas_html = f"<h3>Alertas bloqueantes e falhas ({len(itens_a)})</h3>" + (
        f"<ul>{''.join(itens_a)}</ul>"
        if itens_a
        else "<p class='ok'>Nenhum alerta bloqueante.</p>"
    )
    nada = not (itens_a or itens_b or linhas_c)
    nada_html = (
        "<p class='nada-a-decidir'>✔ Nada a decidir neste edital: sem alertas "
        "bloqueantes, sem itens novos e sem propostas pendentes. Pode aprovar.</p>"
        if nada
        else ""
    )
    return (
        _bloco_origem_mapeamento(mapeamento)
        + "<section class='revisar-box' aria-label='O que revisar'><h2>O que revisar</h2>"
        + nada_html
        + "<p class='legenda'>Novo = nenhum nó equivalente na árvore; será preciso criar ou mapear "
        "na curadoria. Proposta = a IA achou este nó existente; aprovar via curar_arvore.</p>"
        + alertas_html
        + novos_html
        + propostas_html
        + "</section>"
    )


def renderizar_edital(
    resultado: dict,
    auditoria: dict,
    validacao: dict | None,
    novidades: dict | None = None,
    mapeamento: list[dict] | None = None,
) -> str:
    novidades = {**NOVIDADES_VAZIAS, **(novidades or {})}
    disciplinas_novas, assuntos_novos = _novos_do_edital(novidades)
    resultado_por_index = {
        item["chunk_index"]: item
        for item in resultado["resultados"]
        if item.get("chunk_index") is not None
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

    def _materia_nova(chunk_auditoria: dict) -> bool:
        item = resultado_por_index.get(chunk_auditoria.get("chunk_index")) or {}
        materia_extraida = (item.get("taxonomia_extraida") or {}).get("materia")
        return (
            _chave(chunk_auditoria.get("materia")) in disciplinas_novas
            or _chave(materia_extraida) in disciplinas_novas
        )

    chunks_html = "".join(
        renderizar_chunk(
            chunk_auditoria,
            resultado_por_index.get(chunk_auditoria.get("chunk_index")),
            alertas_por_chunk.get(chunk_auditoria.get("chunk_index"), []),
            disciplina_nova=_materia_nova(chunk_auditoria),
            assuntos_novos=assuntos_novos,
        )
        for chunk_auditoria in auditoria["chunks"]
    )

    total_alertas = validacao["total_alertas"] if validacao else "—"
    total_informativos = validacao.get("total_informativos", 0) if validacao else "—"
    edital = escape(_rotulo_concurso(resultado) + resultado["edital"])
    revisar_html = _bloco_o_que_revisar(
        resultado, auditoria, validacao, novidades, mapeamento
    )
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisão — {edital}</title><style>{CSS}</style></head>
<body>
<p><a href="index.html">← todos os editais</a></p>
<h1>{edital}</h1>
<p><em>{escape(resultado["status_revisao_humana"])}</em></p>
{revisar_html}
<div class="totais">
  <div class="item"><strong>{resultado["total_chunks"]}</strong>chunks</div>
  <div class="item"><strong>{resultado["extraidos_com_sucesso"]}</strong>sucesso</div>
  <div class="item"><strong>{resultado["falhas"]}</strong>falhas</div>
  <div class="item"><strong>{total_alertas}</strong>alertas de validação</div>
  <div class="item"><strong>{total_informativos}</strong>informativos</div>
</div>
{alertas_edital_html}
{chunks_html}
</body></html>
"""


def _resumo_edital(
    resultado: dict, validacao: dict | None, novidades: dict, arquivo_html: str
) -> dict:
    bloqueantes, informativos = _alertas_por_severidade(validacao)
    disciplinas_novas = novidades.get("disciplinas_novas", [])
    assuntos_novos = novidades.get("assuntos_novos", [])
    return {
        "edital": _rotulo_concurso(resultado) + resultado["edital"],
        "arquivo_html": arquivo_html,
        "situacao": _situacao(resultado),
        "total_chunks": resultado["total_chunks"],
        "falhas": resultado.get("falhas", 0),
        "total_alertas": bloqueantes,
        "total_informativos": informativos,
        "total_disciplinas": novidades.get("total_disciplinas", 0),
        "total_assuntos": novidades.get("total_assuntos", 0),
        "disciplinas_novas": len(disciplinas_novas),
        "assuntos_novos": len(assuntos_novos),
        "propostas": len(novidades.get("propostas", [])),
    }


def _tem_problema(e: dict) -> bool:
    return bool(e.get("total_alertas") or e.get("falhas"))


def _tem_novidade(e: dict) -> bool:
    return bool(e.get("disciplinas_novas") or e.get("assuntos_novos"))


def _tem_proposta(e: dict) -> bool:
    return bool(e.get("propostas"))


def _badge(texto: str, classe: str = "") -> str:
    return f"<span class='badge {classe}'>{escape(texto)}</span>"


def _linha_edital(e: dict) -> str:
    badges = []
    if e.get("total_disciplinas") or e.get("total_assuntos"):
        badges.append(
            _badge(
                f"{e.get('total_disciplinas', 0)} disciplinas · {e.get('total_assuntos', 0)} assuntos",
                "neutro",
            )
        )
    badges.append(_badge(f"{e['total_chunks']} chunks", "neutro"))
    if e.get("falhas"):
        badges.append(_badge(f"{e['falhas']} falhas", "bloq"))
    bloq = e.get("total_alertas", 0)
    badges.append(_badge(f"{bloq} alertas bloqueantes", "bloq" if bloq else "ok"))
    if e.get("total_informativos"):
        badges.append(_badge(f"{e['total_informativos']} informativos", "info"))
    if e.get("propostas"):
        badges.append(_badge(f"{e['propostas']} propostas a conferir", "proposta"))
    novos = (e.get("disciplinas_novas") or 0) + (e.get("assuntos_novos") or 0)
    if novos:
        badges.append(_badge(f"{novos} novos sem equivalente", "novo"))
    return (
        f"<li data-problema='{int(_tem_problema(e))}' data-novidade='{int(_tem_novidade(e))}' "
        f"data-proposta='{int(_tem_proposta(e))}'>"
        f"<a href='{escape(e['arquivo_html'])}'>{escape(e['edital'])}</a>{''.join(badges)}</li>"
    )


def _ordenar_pendentes(editais: list[dict]) -> list[dict]:
    return sorted(
        editais,
        key=lambda e: (
            not _tem_problema(e),
            not _tem_novidade(e),
            not _tem_proposta(e),
            e["edital"],
        ),
    )


def _lista(editais: list[dict]) -> str:
    if not editais:
        return "<p class='vazio'>Nenhum edital nesta seção.</p>"
    return f"<ul class='index-lista'>{''.join(_linha_edital(e) for e in editais)}</ul>"


FILTRO_JS = """
(function () {
  var botoes = document.querySelectorAll('.filtros button');
  function aplicar(filtro) {
    botoes.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.filtro === filtro));
    });
    document.querySelectorAll('.index-lista li[data-problema]').forEach(function (li) {
      var mostrar = filtro === 'todos' ||
        (filtro === 'problema' && li.dataset.problema === '1') ||
        (filtro === 'novidade' && li.dataset.novidade === '1') ||
        (filtro === 'proposta' && li.dataset.proposta === '1');
      li.hidden = !mostrar;
    });
  }
  botoes.forEach(function (b) {
    b.addEventListener('click', function () { aplicar(b.dataset.filtro); });
  });
})();
"""


def renderizar_index(editais: list[dict]) -> str:
    pendentes = _ordenar_pendentes(
        [e for e in editais if e.get("situacao") == "pendente"]
    )
    aprovados = [e for e in editais if e.get("situacao") == "aprovado"]
    outros = [e for e in editais if e.get("situacao") not in ("pendente", "aprovado")]
    com_alertas = sum(1 for e in editais if _tem_problema(e))
    com_novidades = sum(1 for e in editais if _tem_novidade(e))
    com_propostas = sum(1 for e in editais if _tem_proposta(e))
    resumo = (
        "<div class='resumo-topo'>"
        f"<div class='item pend'><strong>{len(pendentes)}</strong>aguardando aprovação</div>"
        f"<div class='item'><strong>{len(aprovados)}</strong>aprovados</div>"
        f"<div class='item prob'><strong>{com_alertas}</strong>com problema</div>"
        f"<div class='item nov'><strong>{com_novidades}</strong>com novo sem equivalente</div>"
        f"<div class='item'><strong>{com_propostas}</strong>com proposta a conferir</div>"
        "</div>"
    )
    filtros = (
        "<div class='filtros' role='group' aria-label='Filtrar editais'><span>Mostrar:</span>"
        "<button type='button' data-filtro='todos' aria-pressed='true'>Todos</button>"
        "<button type='button' data-filtro='problema' aria-pressed='false'>Com problema</button>"
        "<button type='button' data-filtro='novidade' aria-pressed='false'>Com novo sem equivalente</button>"
        "<button type='button' data-filtro='proposta' aria-pressed='false'>Com proposta</button>"
        "</div>"
    )
    secao_outros = f"<h2>Outros ({len(outros)})</h2>{_lista(outros)}" if outros else ""
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Revisão de editais — scraper_cebraspe</title><style>{CSS}</style></head>
<body>
<h1>Revisão de editais (Etapa 4)</h1>
{resumo}
{filtros}
<section class="secao-pendentes" aria-label="Aguardando aprovação">
<h2>Aguardando aprovação ({len(pendentes)})</h2>
{_lista(pendentes)}
</section>
<details class="secao">
<summary>Aprovados ({len(aprovados)})</summary>
{_lista(sorted(aprovados, key=lambda e: e["edital"]))}
</details>
{secao_outros}
<h2>Camada canônica (Etapa 5B)</h2>
<ul class="index-lista"><li><a href="arvore.html">Árvore Mestre</a>
<span class="badge">matéria → assunto → subassunto, com aprovação humana</span></li></ul>
<h2>Classificação de Questões (Etapa 5D)</h2>
<ul class="index-lista"><li><a href="classificacao.html">Classificação de Questões na Árvore Mestre</a>
<span class="badge">auditoria de itens, confiança e curadoria humana</span></li></ul>
<script>{FILTRO_JS}</script>
</body></html>
"""


def _carregar_trio(json_path: Path) -> tuple[dict, dict | None, dict | None]:
    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    auditoria = (
        json.loads(auditoria_path.read_text(encoding="utf-8"))
        if auditoria_path.exists()
        else None
    )
    validacao_path = json_path.parent / f"{json_path.stem}.validacao.json"
    validacao = (
        json.loads(validacao_path.read_text(encoding="utf-8"))
        if validacao_path.exists()
        else None
    )
    return resultado, auditoria, validacao


def _contexto_mapeamento():
    try:
        arvore = arv_mod.carregar()
    except Exception as erro:  # noqa: BLE001
        logger.warning(f"Árvore indisponível; sem quadro de origem: {erro}")
        arvore = None
    return arvore, mapeamento_revisao.carregar_cache_propostos()


def gerar_relatorios(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    novidades_fn: FuncaoNovidades | None = None,
) -> Path:
    """`novidades_fn` (injetável nos testes) calcula as novidades de um
    edital; sem ela, tenta `src.novidades_edital.novidades_do_edital`."""
    if novidades_fn is None:
        novidades_fn = _carregar_funcao_novidades()
    saida_dir = revisao_dir / RELATORIO_SUBDIR
    saida_dir.mkdir(exist_ok=True)

    jsons = sorted(
        p
        for p in revisao_dir.glob("*.json")
        if not p.name.endswith(".auditoria.json")
        and not p.name.endswith(".validacao.json")
    )

    arvore, propostos = _contexto_mapeamento()
    editais_index = []
    for json_path in jsons:
        resultado, auditoria, validacao = _carregar_trio(json_path)
        if auditoria is None:
            logger.warning(
                f"{resultado['edital']}: sem .auditoria.json — pulando relatório (formato legado)."
            )
            continue

        novidades = _novidades_seguras(resultado, novidades_fn)
        mapeamento = (
            mapeamento_revisao.classificar_seguro(
                resultado, arvore=arvore, propostos=propostos
            )
            if arvore is not None
            else []
        )
        html = renderizar_edital(resultado, auditoria, validacao, novidades, mapeamento)
        arquivo_html = f"{json_path.stem}.html"
        (saida_dir / arquivo_html).write_text(html, encoding="utf-8")
        editais_index.append(
            _resumo_edital(resultado, validacao, novidades, arquivo_html)
        )
        logger.info(
            f"{resultado['edital']}: relatório gerado em {saida_dir / arquivo_html}."
        )

    (saida_dir / "index.html").write_text(
        renderizar_index(editais_index), encoding="utf-8"
    )
    logger.info(
        f"Índice de relatórios gerado em {saida_dir / 'index.html'} — {len(editais_index)} edital(is)."
    )
    return saida_dir


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    gerar_relatorios(diretorio)
