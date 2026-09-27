"""Relatório de revisão dos sinônimos canônicos (Etapa 5B, ADR-029).

Gera `revisao_piloto/relatorio/sinonimos.html`, servido pelo mesmo Datasette
(`--static relatorio:/data/relatorio`, SSO do Cloudflare) e linkado do
`index.html`. Mostra, por nível (matéria, assunto, subassunto):

- propostas pendentes do LLM, com os nomes de origem, os concursos e níveis
  (médio/superior) de cada nome, o grupo aprovado atual de cada entrada e os
  IDs estáveis para `scripts/aprovar_sinonimos.py`;
- grupos juntados por regra (aprovados automaticamente);
- grupos aprovados/rejeitados por decisão humana.

Roda automaticamente em `scripts/atualizar_revisao.py` (sem LLM) e ao fim de
`propor_sinonimos.py`/`aprovar_sinonimos.py`.

Uso:
    python -m scripts.gerar_relatorio_sinonimos [revisao_piloto_dir]
"""

import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_revisao import CSS, RELATORIO_SUBDIR
from src import canonico
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
ARQUIVO_HTML = "sinonimos.html"

TITULO_NIVEL = {
    "materia": "Matérias",
    "assunto": "Assuntos",
    "subassunto": "Subassuntos",
}

CSS_SINONIMOS = """
.grupo { border: 1px solid color-mix(in srgb, CanvasText 20%, Canvas); border-radius: 10px;
         margin-bottom: 1rem; overflow: hidden; }
.grupo > header { background: color-mix(in srgb, CanvasText 6%, Canvas); padding: 0.5rem 1rem;
                  display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: baseline; }
.grupo.proposto > header { background: color-mix(in srgb, #d97706 16%, Canvas); }
.grupo.rejeitado > header { background: color-mix(in srgb, #dc2626 12%, Canvas); }
.grupo .nome { font-weight: 600; }
.grupo .justificativa, .grupo .escopo { font-size: 0.85rem; padding: 0.3rem 1rem; opacity: 0.85; }
.grupo .aviso { font-size: 0.85rem; padding: 0.3rem 1rem; color: #b45309; font-weight: 600; }
code { font-size: 0.85em; }
table { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
th, td { text-align: left; padding: 0.3rem 1rem; vertical-align: top;
         border-top: 1px solid color-mix(in srgb, CanvasText 12%, Canvas); }
th { font-weight: 600; }
details > summary { cursor: pointer; font-weight: 600; margin: 0.6rem 0; }
.uso { background: color-mix(in srgb, CanvasText 6%, Canvas); border-radius: 8px; padding: 0.6rem 1rem;
       font-size: 0.85rem; overflow-x: auto; }
"""


def _ocorrencias_por_nome(nomes: canonico.NomesOrigem) -> dict[str, dict]:
    return {
        "materia": nomes.materia,
        "assunto": nomes.assunto,
        "subassunto": nomes.subassunto,
    }


def _chave_nome(nivel: str, n: dict):
    if nivel == "materia":
        return n["chave"]
    if nivel == "assunto":
        return (n["materia"], n["chave"])
    return (n["materia"], n["topico"], n["chave"])


def _formatar_ocorrencias(ocorrencias) -> str:
    por_slug: dict[str, set[str]] = {}
    for slug, nivel in ocorrencias or ():
        por_slug.setdefault(slug, set()).add(nivel or "?")
    return (
        ", ".join(
            f"{escape(s)} ({'/'.join(sorted(n))})" for s, n in sorted(por_slug.items())
        )
        or "—"
    )


def _linhas_membros(
    estado: dict, nivel: str, membros: list[str], fontes: dict, aprovado: dict
) -> str:
    linhas = []
    for eid in membros:
        entrada = estado[nivel]["entradas"].get(eid)
        if entrada is None:
            continue
        atual = aprovado.get(eid)
        atual_txt = f"<code>{escape(atual)}</code>" if atual else "—"
        for i, n in enumerate(entrada["nomes"]):
            contexto = ""
            if nivel == "assunto":
                contexto = f"<br><small>matéria: {escape(n['materia'])}</small>"
            elif nivel == "subassunto":
                contexto = (
                    f"<br><small>{escape(n['materia'])} › {escape(n['topico'])}</small>"
                )
            ocorr = fontes[nivel].get(_chave_nome(nivel, n), {}).get("ocorrencias")
            linhas.append(
                "<tr>"
                + (
                    f"<td rowspan='{len(entrada['nomes'])}'><code>{escape(eid)}</code></td>"
                    if i == 0
                    else ""
                )
                + f"<td>{escape(n['nome'])}{' <em>(noções)</em>' if n.get('nocoes') else ''}{contexto}</td>"
                + f"<td>{_formatar_ocorrencias(ocorr)}</td>"
                + (
                    f"<td rowspan='{len(entrada['nomes'])}'>{atual_txt}</td>"
                    if i == 0
                    else ""
                )
                + "</tr>"
            )
    return (
        "<table><tr><th>Entrada</th><th>Nome de origem</th><th>Concursos (nível)</th>"
        f"<th>Grupo aprovado atual</th></tr>{''.join(linhas)}</table>"
    )


def _renderizar_grupo(
    estado: dict, nivel: str, gid: str, fontes: dict, aprovado: dict
) -> str:
    g = estado[nivel]["grupos"][gid]
    status = g["status"]
    extras = ""
    if g.get("escopo") and canonico.PAI[nivel]:
        pai = canonico.PAI[nivel]
        pai_nome = estado[pai]["grupos"].get(g["escopo"], {}).get("nome", "?")
        extras += (
            f"<div class='escopo'>dentro de {pai}: <strong>{escape(pai_nome)}</strong> "
            f"<code>{escape(g['escopo'])}</code></div>"
        )
    if status == canonico.STATUS_PROPOSTO and canonico.PAI[nivel]:
        escopos = {canonico.escopo_da_entrada(estado, nivel, e) for e in g["membros"]}
        if len(escopos) > 1:
            extras += (
                f"<div class='aviso'>Os membros estão em grupos diferentes do nível "
                f"{canonico.PAI[nivel]}: aprove antes <code>{escape(str(g.get('escopo')))}</code>.</div>"
            )
    chaves = {
        estado[nivel]["entradas"][e]["chave_regra"]
        for e in g["membros"]
        if e in estado[nivel]["entradas"]
    }
    if status == canonico.STATUS_PROPOSTO and len(chaves) == 1 and canonico.PAI[nivel]:
        extras += (
            "<div class='aviso'>Mesma chave de regra em escopos diferentes: a regra junta sozinha "
            "quando o grupo do nível de cima for aprovado (a proposta some).</div>"
        )
    if g.get("justificativa"):
        extras += f"<div class='justificativa'>LLM: {escape(g['justificativa'])}</div>"
    return (
        f"<section class='grupo {status}' id='{escape(gid)}'><header>"
        f"<code>{escape(gid)}</code><span class='nome'>{escape(g['nome'])}</span>"
        f"<span class='badge'>{escape(g['origem'])} · {escape(status)}</span>"
        f"<span class='badge'>{len(g['membros'])} entradas</span></header>{extras}"
        f"{_linhas_membros(estado, nivel, g['membros'], fontes, aprovado)}</section>"
    )


def _total_nomes(estado: dict, nivel: str, g: dict) -> int:
    return sum(
        len(estado[nivel]["entradas"].get(e, {}).get("nomes", [])) for e in g["membros"]
    )


def renderizar_sinonimos(estado: dict, nomes: canonico.NomesOrigem) -> str:
    fontes = _ocorrencias_por_nome(nomes)
    totais_html, secoes = [], []
    for nivel in canonico.NIVEIS:
        grupos = estado[nivel]["grupos"]
        aprovado = canonico.grupo_aprovado_por_entrada(estado, nivel)
        presentes = [e for e in estado[nivel]["entradas"].values() if e.get("presente")]
        propostos = sorted(
            (g for g, d in grupos.items() if d["status"] == canonico.STATUS_PROPOSTO),
            key=lambda g: (-len(grupos[g]["membros"]), grupos[g]["nome"]),
        )
        por_regra = sorted(
            (
                g
                for g, d in grupos.items()
                if d["status"] == canonico.STATUS_APROVADO
                and d["origem"] == canonico.ORIGEM_REGRA
                and _total_nomes(estado, nivel, d) > 1
            ),
            key=lambda g: grupos[g]["nome"],
        )
        decididos = sorted(
            (
                g
                for g, d in grupos.items()
                if d["origem"] != canonico.ORIGEM_REGRA
                and d["status"] != canonico.STATUS_PROPOSTO
            ),
            key=lambda g: (grupos[g]["status"], grupos[g]["nome"]),
        )
        totais_html.append(
            f"<div class='item'><strong>{len(propostos)}</strong>{TITULO_NIVEL[nivel]}: propostas pendentes"
            f"<br><small>{sum(len(e['nomes']) for e in presentes)} nomes · {len(presentes)} entradas · "
            f"{len(por_regra)} grupos por regra</small></div>"
        )

        def bloco(ids, titulo, aberto, nivel=nivel, aprovado=aprovado):
            corpo = (
                "".join(
                    _renderizar_grupo(estado, nivel, g, fontes, aprovado) for g in ids
                )
                or "<p>Nenhum.</p>"
            )
            return f"<details{' open' if aberto else ''}><summary>{titulo} ({len(ids)})</summary>{corpo}</details>"

        secoes.append(
            f"<h2 id='{nivel}'>{TITULO_NIVEL[nivel]}</h2>"
            + bloco(propostos, "Propostas do LLM aguardando aprovação", True)
            + bloco(decididos, "Decididos por humano (aprovados/rejeitados)", False)
            + bloco(por_regra, "Juntados por regra (aprovados automaticamente)", False)
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sinônimos canônicos</title><style>{CSS}{CSS_SINONIMOS}</style></head>
<body>
<p><a href="index.html">← relatórios de editais</a></p>
<h1>Sinônimos canônicos — revisão humana (Etapa 5B)</h1>
<p>Nada <em>proposto</em> entra na estatística: até a aprovação, cada nome continua no grupo
aprovado atual (a própria entrada, se ninguém decidiu nada). Grupos por regra são
determinísticos e já aprovados. Níveis: <a href="#materia">matérias</a> ·
<a href="#assunto">assuntos</a> · <a href="#subassunto">subassuntos</a>.</p>
<div class="totais">{"".join(totais_html)}</div>
<pre class="uso">python -m scripts.aprovar_sinonimos --aprovar ML-xxxx,AL-yyyy --rejeitar SL-zzzz
python -m scripts.aprovar_sinonimos --mover A-entrada:AL-grupo   # entrada para outro grupo
python -m scripts.aprovar_sinonimos --mover A-entrada:NOVO       # separa num grupo próprio
python -m scripts.aprovar_sinonimos --renomear "ML-xxxx=Nome canônico"</pre>
{"".join(secoes)}
</body></html>
"""


def gerar_relatorio_sinonimos(
    revisao_dir: Path = REVISAO_DIR_PADRAO, sinonimos_path: Path | None = None
) -> Path:
    sinonimos_path = sinonimos_path or canonico.caminho_sinonimos(revisao_dir)
    estado = canonico.carregar(sinonimos_path)
    nomes = canonico.coletar_nomes(revisao_dir)
    saida_dir = revisao_dir / RELATORIO_SUBDIR
    saida_dir.mkdir(parents=True, exist_ok=True)
    saida = saida_dir / ARQUIVO_HTML
    saida.write_text(renderizar_sinonimos(estado, nomes), encoding="utf-8")
    logger.info(f"[CANONICO] Relatório de sinônimos gerado em {saida}.")
    return saida


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    gerar_relatorio_sinonimos(diretorio)
