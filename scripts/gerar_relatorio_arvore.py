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


def renderizar_arvore(
    arvore: arv_mod.ArvoreMestre, ocorrencias: dict[str, set[Ocorrencia]]
) -> str:
    sem_mapeamento = sorted(
        chave
        for chave in ocorrencias
        if not any(m.status == "aprovado" for m in arvore.mapeamentos.get(chave, []))
    )
    propostas: list[tuple[str, str]] = []
    itens_por_no: dict[str, list[str]] = {}
    for item, mapeamentos in sorted(arvore.mapeamentos.items()):
        for m in mapeamentos:
            no_id = arv_mod.resolver_no(arvore, m.no_id)
            if m.status == "proposto":
                propostas.append((item, no_id))
            elif m.status == "aprovado":
                itens_por_no.setdefault(no_id, []).append(item)

    filhos: dict[str, list[str]] = {}
    raizes: list[str] = []
    for no_id, no in arvore.nos.items():
        if no.status == "fundido":
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

    nos_propostos = sorted(i for i, n in arvore.nos.items() if n.status == "proposto")
    partes = [
        "<h1>Árvore mestre</h1>",
        (
            f"<p>{sum(n.status != 'fundido' for n in arvore.nos.values())} nós · "
            f"{len(arvore.mapeamentos)} itens mapeados · {len(sem_mapeamento)} sem mapeamento "
            f"aprovado · {len(propostas)} mapeamentos e {len(nos_propostos)} nós propostos</p>"
        ),
        f"<h2>Itens sem mapeamento aprovado ({len(sem_mapeamento)})</h2><ul>",
        *(
            f"<li>{escape(c)}{_formatar_ocorrencias(ocorrencias[c])}</li>"
            for c in sem_mapeamento
        ),
        "</ul>",
        f"<h2>Propostas pendentes ({len(propostas) + len(nos_propostos)})</h2><ul>",
        *(
            f"<li>mapear <code>{escape(item)}</code> → {escape(nome_no(no_id))}</li>"
            for item, no_id in propostas
        ),
        *(f"<li>nó {escape(nome_no(no_id))}</li>" for no_id in nos_propostos),
        "</ul>",
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
