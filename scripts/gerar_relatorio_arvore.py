"""Relatório da árvore mestre (Etapa 5B.1, ADR-030).

Gera `revisao_piloto/relatorio/arvore.html`, servido pelo mesmo Datasette
(`--static relatorio:/data/relatorio`) e linkado do `index.html`. Substitui o
`sinonimos.html` da 5B. Mostra:

- itens de edital sem mapeamento (o que a regra do pipeline não resolveu);
- mapeamentos e nós propostos, pendentes de decisão do dono;
- a árvore navegável, com os itens de edital de cada nó e onde eles
  aparecem (concurso, cargo, nível).

Roda automaticamente em `scripts/atualizar_revisao.py` e em
`scripts/curar_arvore.py --html`.

Uso:
    python -m scripts.gerar_relatorio_arvore [revisao_piloto_dir]
"""

import json
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_revisao import CSS, RELATORIO_SUBDIR
from src import arvore as arv_mod
from src.comparacao_texto import normalizar
from src.logger import logger
from src.stats_writer import listar_jsons_edital, montar_carga_concurso

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
ARQUIVO_HTML = "arvore.html"

CSS_ARVORE = """
ul.arvore, ul.arvore ul { list-style: none; padding-left: 1.2rem;
    border-left: 1px dashed color-mix(in srgb, CanvasText 25%, Canvas); }
.no-materia { font-weight: 700; }
.no-assunto { font-weight: 600; }
.proposto { color: #b45309; }
.item-edital { font-size: 0.85rem; opacity: 0.8; }
.ocorrencias { font-size: 0.8rem; opacity: 0.7; }
details > summary { cursor: pointer; }
code { font-size: 0.85em; }
.indicadores-curadoria { background: color-mix(in srgb, CanvasText 5%, Canvas);
    padding: 0.8rem 1rem; border-radius: 6px; margin: 1rem 0; font-size: 0.95rem; }
.tipo-proposta { font-weight: 600; color: #2563eb; }
.cmd-aprovar { display: inline-block; margin: 0.3rem 0; padding: 0.2rem 0.5rem;
    background: color-mix(in srgb, CanvasText 8%, Canvas); border-radius: 4px; }
.lista-propostas { list-style: none; padding-left: 0; }
.proposta-item { margin-bottom: 0.8rem; padding: 0.5rem; border-left: 3px solid #2563eb;
    background: color-mix(in srgb, CanvasText 2%, Canvas); }
.justificativa { opacity: 0.85; }
"""


Ocorrencia = tuple[str, str, str]  # (concurso, cargo, nível)


def coletar_ocorrencias(revisao_dir: Path) -> dict[str, set[Ocorrencia]]:
    """Chave do item (`arvore.chave_item`) → onde ele aparece nos editais."""
    ocorrencias: dict[str, set[Ocorrencia]] = {}
    for json_path in listar_jsons_edital(revisao_dir):
        carga = montar_carga_concurso(json.loads(json_path.read_text(encoding="utf-8")))
        niveis_cargo = {c["numero"]: c.get("nivel") for c in carga["cargos"]}
        for item in carga["itens"]:
            numero = item["cargo_numero"]
            if numero is not None:
                cargo = f"cargo {numero}"
            elif item["cargos_restritos"]:
                cargo = "cargos " + ", ".join(map(str, item["cargos_restritos"]))
            else:
                cargo = "básico"
            nivel = item["nivel"] or niveis_cargo.get(numero) or "?"
            oc = (carga["slug"], cargo, nivel)
            m, t = item["materia_chave"], item["topico_chave"]
            chaves = [(m,), (m, t)]
            chaves += [(m, t, s) for s in map(normalizar, item["subtopicos"]) if s]
            for chave in chaves:
                ocorrencias.setdefault(arv_mod.chave_item(chave), set()).add(oc)
    return ocorrencias


def _formatar_ocorrencias(ocs: set[Ocorrencia]) -> str:
    if not ocs:
        return ""
    texto = "; ".join(
        f"{slug} · {cargo} · {nivel}" for slug, cargo, nivel in sorted(ocs)
    )
    return f" <span class='ocorrencias'>[{escape(texto)}]</span>"


def _formatar_antes_depois(arvore: arv_mod.ArvoreMestre, p: arv_mod.Proposta) -> str:
    def n_txt(nid: str) -> str:
        no = arvore.nos.get(nid)
        return f"{no.nome} ({nid})" if no else nid

    if p.tipo == "fundir":
        return f"{n_txt(p.args['origem'])} → {n_txt(p.args['destino'])}"
    elif p.tipo == "mover":
        return f"{n_txt(p.args['no'])} → novo pai {n_txt(p.args['pai'])}"
    elif p.tipo == "criar":
        pai_s = n_txt(p.args["pai"]) if p.args.get("pai") else "raiz"
        return f"+ ({p.args['nivel']}) {p.args['nome']!r} sob {pai_s}"
    elif p.tipo == "remapear":
        destinos = (
            p.args["para"] if isinstance(p.args["para"], list) else [p.args["para"]]
        )
        para_s = ", ".join(n_txt(d) for d in destinos)
        return f"📄 {p.args['item']}: {n_txt(p.args['de'])} → {para_s}"
    elif p.tipo == "aposentar":
        nid = p.args.get("no") or p.args.get("no_id", "")
        return f"🚫 aposentar {n_txt(nid)}"
    return str(p.args)


def _contar_ocorrencias_no(
    arvore: arv_mod.ArvoreMestre,
    no_id: str,
    ocorrencias: dict[str, set[Ocorrencia]],
) -> int:
    ocs: set[Ocorrencia] = set()
    for item, maps in arvore.mapeamentos.items():
        for m in maps:
            if m.status == "aprovado" and arv_mod.resolver_no(arvore, m.no_id) == no_id:
                ocs |= ocorrencias.get(item, set())
    return len(ocs)


def renderizar_arvore(
    arvore: arv_mod.ArvoreMestre, ocorrencias: dict[str, set[Ocorrencia]]
) -> str:
    sem_mapeamento = sorted(
        chave
        for chave in ocorrencias
        if not any(m.status == "aprovado" for m in arvore.mapeamentos.get(chave, []))
    )
    propostas_legado: list[tuple[str, str]] = []
    itens_por_no: dict[str, list[str]] = {}
    for item, mapeamentos in sorted(arvore.mapeamentos.items()):
        for m in mapeamentos:
            no_id = arv_mod.resolver_no(arvore, m.no_id)
            if m.status == "proposto":
                propostas_legado.append((item, no_id))
            elif m.status == "aprovado":
                itens_por_no.setdefault(no_id, []).append(item)

    filhos: dict[str, list[str]] = {}
    raizes: list[str] = []
    for no_id, no in arvore.nos.items():
        if no.status in ("fundido", "aposentado"):
            continue
        if no.pai:
            filhos.setdefault(arv_mod.resolver_no(arvore, no.pai), []).append(no_id)
        else:
            raizes.append(no_id)

    def nome_no(no_id: str) -> str:
        no = arvore.nos.get(no_id)
        return f"{no.nome} ({no_id})" if no else no_id

    def render_no(no_id: str) -> str:
        no = arvore.nos[no_id]
        classe = f"no-{no.nivel}" + (" proposto" if no.status == "proposto" else "")
        rotulo = f"<span class='{classe}'>{escape(no.nome)}</span> <code>{escape(no_id)}</code>"
        if no.status == "proposto":
            rotulo += " <span class='proposto'>(proposto)</span>"
        itens = "".join(
            f"<li class='item-edital'>📄 {escape(item)}"
            f"{_formatar_ocorrencias(ocorrencias.get(item, set()))}</li>"
            for item in itens_por_no.get(no_id, [])
        )
        sub = "".join(
            render_no(f)
            for f in sorted(filhos.get(no_id, []), key=lambda x: arvore.nos[x].nome)
        )
        corpo = f"<ul>{itens}{sub}</ul>" if itens or sub else ""
        return f"<li><details><summary>{rotulo}</summary>{corpo}</details></li>"

    propostas_op = [p for p in arvore.propostas.values() if p.status == "proposto"]
    nos_propostos = sorted(
        i
        for i, n in arvore.nos.items()
        if n.status == "proposto"
        and not any(p.tipo == "criar" and p.args.get("id") == i for p in propostas_op)
    )
    total_propostas = len(propostas_op) + len(propostas_legado) + len(nos_propostos)

    # Indicadores de critério de pronto (Etapa 5B.2)
    qtd_dg = _contar_ocorrencias_no(arvore, "S-10973fad79", ocorrencias)
    qtd_sp = _contar_ocorrencias_no(arvore, "S-de2a8684f9", ocorrencias)

    # Agrupar propostas por matéria
    ORDEM_TIPOS = {"criar": 1, "mover": 2, "fundir": 3, "remapear": 4, "aposentar": 5}

    def _chave_ordem_proposta(p: arv_mod.Proposta) -> tuple[int, str]:
        return (ORDEM_TIPOS.get(p.tipo, 99), p.id)

    propostas_por_materia: dict[str, list[arv_mod.Proposta]] = {}
    for p in propostas_op:
        propostas_por_materia.setdefault(p.materia, []).append(p)

    propostas_blocos = []
    for m_id, props in sorted(propostas_por_materia.items()):
        m_no = arvore.nos.get(m_id)
        m_nome = m_no.nome if m_no else (m_id or "Sem matéria")
        props_ordenadas = sorted(props, key=_chave_ordem_proposta)
        todos_ids = ",".join(p.id for p in props_ordenadas)
        cmd_todas = (
            f"<div class='cmd-aprovar-todas'><small>Aprovar todas desta matéria:</small><br>"
            f"<pre class='cmd-aprovar'><code>python -m scripts.curar_arvore --aprovar-proposta {escape(todos_ids)}</code></pre></div>"
            if len(props_ordenadas) > 1
            else ""
        )
        itens_bloco = []
        for p in props_ordenadas:
            antes_depois = _formatar_antes_depois(arvore, p)
            itens_bloco.append(
                f"<li class='proposta-item'>"
                f"<strong><code>{escape(p.id)}</code></strong> "
                f"<span class='tipo-proposta'>[{escape(p.tipo.upper())}]</span> "
                f"<em>({escape(p.origem)})</em>: "
                f"<span>{escape(antes_depois)}</span>"
                f"<br><small class='justificativa'>{escape(p.justificativa)}</small>"
                f"<br><pre class='cmd-aprovar'><code>python -m scripts.curar_arvore --aprovar-proposta {escape(p.id)}</code></pre>"
                f"</li>"
            )
        propostas_blocos.append(
            f"<h3>Matéria: {escape(m_nome)} <code>{escape(m_id)}</code></h3>"
            f"{cmd_todas}"
            f"<ul class='lista-propostas'>{''.join(itens_bloco)}</ul>"
        )

    if propostas_legado or nos_propostos:
        itens_legado = [
            *(
                f"<li>mapear <code>{escape(item)}</code> → {escape(nome_no(no_id))}</li>"
                for item, no_id in propostas_legado
            ),
            *(f"<li>nó {escape(nome_no(no_id))}</li>" for no_id in nos_propostos),
        ]
        propostas_blocos.append(
            f"<h3>Outras propostas pendentes (legado)</h3><ul>{''.join(itens_legado)}</ul>"
        )

    if not propostas_blocos:
        propostas_blocos.append("<p>Nenhuma proposta pendente.</p>")

    partes = [
        "<h1>Árvore mestre</h1>",
        (
            f"<div class='indicadores-curadoria'>"
            f"<strong>Indicadores de Curadoria (Critério Etapa 5B.2):</strong> "
            f"<span>Disposições gerais (<code>S-10973fad79</code>): <strong>{qtd_dg}/8</strong></span> · "
            f"<span>Servidores públicos (<code>S-de2a8684f9</code>): <strong>{qtd_sp}/8</strong></span>"
            f"</div>"
        ),
        (
            f"<p>{sum(n.status == 'ativo' for n in arvore.nos.values())} nós ativos · "
            f"{len(arvore.mapeamentos)} itens mapeados · {len(sem_mapeamento)} sem mapeamento "
            f"aprovado · {total_propostas} propostas pendentes</p>"
        ),
        f"<h2>Itens sem mapeamento aprovado ({len(sem_mapeamento)})</h2><ul>",
        *(
            f"<li>{escape(c)}{_formatar_ocorrencias(ocorrencias[c])}</li>"
            for c in sem_mapeamento
        ),
        "</ul>",
        f"<h2>Propostas pendentes ({total_propostas})</h2>",
        "".join(propostas_blocos),
        "<h2>Árvore</h2><ul class='arvore'>",
        *(render_no(r) for r in sorted(raizes, key=lambda x: arvore.nos[x].nome)),
        "</ul>",
    ]
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Árvore mestre</title><style>{CSS}{CSS_ARVORE}</style></head>
<body><p><a href="index.html">← Índice</a></p>
{"".join(partes)}
</body></html>
"""


def gerar_relatorio_arvore(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    arvore_path: Path = arv_mod.ARVORE_PADRAO,
) -> Path:
    arvore = arv_mod.carregar(arvore_path)
    html = renderizar_arvore(arvore, coletar_ocorrencias(revisao_dir))
    saida = revisao_dir / RELATORIO_SUBDIR / ARQUIVO_HTML
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")
    logger.info(f"[ARVORE] relatório gerado em {saida}")
    return saida


if __name__ == "__main__":
    gerar_relatorio_arvore(
        Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    )
