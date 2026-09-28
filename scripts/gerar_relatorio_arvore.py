import json
import sys
from html import escape
from pathlib import Path

PROJETO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJETO_DIR))
from src.arvore import carregar, resolver_no
from src.canonico import coletar_nomes

ARVORE_JSON = PROJETO_DIR / "canonico" / "arvore.json"
REVISAO_DIR = PROJETO_DIR / "revisao_piloto"
HTML_OUT = REVISAO_DIR / "relatorio" / "arvore.html"

def gerar_relatorio_arvore():
    try:
        arvore = carregar(ARVORE_JSON)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Erro ao carregar {ARVORE_JSON}: {e}")
        return

    # Coletar contexto dos itens de edital
    nomes = coletar_nomes(REVISAO_DIR)
    
    # Criar um dict item_str -> lista de (concurso, cargo, nivel)
    from src.arvore import chave_item
    contexto_item = {}
    for nivel in ("materia", "assunto", "subassunto"):
        fonte = getattr(nomes, nivel)
        for chave, info in fonte.items():
            chave_str = chave_item(chave if isinstance(chave, tuple) else (chave,))
            # info["concursos"] set de slugs
            contexto_item[chave_str] = {
                "concursos": list(info.get("concursos", set())),
                "cargos": list(info.get("cargos", set())),
                "niveis": list(info.get("niveis", set()))
            }

    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Árvore Mestre</title>"]
    html.append("<style>")
    html.append("body { font-family: sans-serif; margin: 20px; }")
    html.append("ul { list-style-type: none; padding-left: 20px; border-left: 1px dashed #ccc; }")
    html.append(".no-materia { font-weight: bold; font-size: 1.2em; color: #2c3e50; margin-top: 10px; }")
    html.append(".no-assunto { font-weight: bold; color: #2980b9; }")
    html.append(".no-subassunto { color: #8e44ad; }")
    html.append(".status-proposto { color: #f39c12; }")
    html.append(".item-edital { color: #7f8c8d; font-size: 0.9em; margin-left: 10px; }")
    html.append("</style></head><body>")
    html.append("<h1>Relatório da Árvore Mestre</h1>")

    pendentes = []
    itens_por_no = {}
    
    # Adicionar itens que estão nos editais mas sem nenhum mapeamento na árvore (ou lista vazia)
    for chave_str in contexto_item:
        if chave_str not in arvore.mapeamentos or not arvore.mapeamentos[chave_str]:
            pendentes.append((chave_str, "Sem mapeamento"))

    for item, maps in arvore.mapeamentos.items():
        if not maps:
            if not any(p[0] == item for p in pendentes):
                pendentes.append((item, "Sem mapeamento"))
            continue
        for m in maps:
            no_id = resolver_no(arvore, m.no_id)
            status = m.status
            if status == "proposto":
                pendentes.append((item, f"Proposto para {no_id}"))
            elif status == "aprovado":
                if no_id not in itens_por_no:
                    itens_por_no[no_id] = []
                itens_por_no[no_id].append(item)

    if pendentes:
        html.append("<h2>Mapeamentos Pendentes / Propostos / Sem mapeamento</h2><ul>")
        for p in pendentes:
            html.append(f"<li>{escape(str(p[0]))}: {escape(str(p[1]))}</li>")
        html.append("</ul>")

    filhos = {}
    raizes = []
    for nid, no in arvore.nos.items():
        if no.status == "fundido":
            continue
        pai = resolver_no(arvore, no.pai) if no.pai else None
        if pai:
            if pai not in filhos:
                filhos[pai] = []
            filhos[pai].append(nid)
        else:
            raizes.append(nid)

    html.append("<h2>Árvore</h2>")
    
    def render_no(nid):
        no = arvore.nos.get(nid)
        if not no: return ""
        nivel = no.nivel
        nome = no.nome
        status = no.status
        
        css_class = f"no-{nivel}"
        if status == "proposto": css_class += " status-proposto"
        
        out = f"<li><span class='{css_class}'>{escape(nome)}</span> <code>({escape(nid)})</code>"
        
        itens = itens_por_no.get(nid, [])
        if itens:
            out += "<ul>"
            for item in itens:
                ctx = contexto_item.get(item, {})
                c_str = ""
                if ctx:
                    c_str = f" [Concursos: {','.join(ctx['concursos'])} | Níveis: {','.join(ctx['niveis'])}]"
                out += f"<li class='item-edital'>📄 {escape(str(item))}{escape(c_str)}</li>"
            out += "</ul>"
            
        if nid in filhos:
            out += "<ul>"
            filhos_ordenados = sorted(filhos[nid], key=lambda x: arvore.nos[x].nome)
            for f in filhos_ordenados:
                out += render_no(f)
            out += "</ul>"
        out += "</li>"
        return out

    html.append("<ul>")
    raizes_ordenadas = sorted(raizes, key=lambda x: arvore.nos[x].nome)
    for r in raizes_ordenadas:
        html.append(render_no(r))
    html.append("</ul>")
    
    html.append("</body></html>")

    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write("".join(html))

if __name__ == "__main__":
    gerar_relatorio_arvore()
