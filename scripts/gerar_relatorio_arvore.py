import json
from pathlib import Path
from html import escape

PROJETO_DIR = Path(__file__).resolve().parent.parent
ARVORE_JSON = PROJETO_DIR / "canonico" / "arvore.json"
HTML_OUT = PROJETO_DIR / "revisao_piloto" / "relatorio" / "arvore.html"

def gerar_relatorio_arvore():
    try:
        with open(ARVORE_JSON, "r", encoding="utf-8") as f:
            arvore = json.load(f)
    except Exception as e:
        print(f"Erro ao carregar {ARVORE_JSON}: {e}")
        return

    nos = arvore.get("nos", {})
    if isinstance(nos, list):
        nos = {n["id"]: n for n in nos}
        
    mapeamentos = arvore.get("mapeamentos", {})

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

    # Mapeamentos pendentes (não resolvidos ou com nó fundido/inválido)
    pendentes = []
    
    # Agrupar itens de edital por nó
    itens_por_no = {}
    for item, maps in mapeamentos.items():
        if not maps:
            pendentes.append((item, "Sem mapeamento"))
            continue
        for m in maps:
            no_id = m.get("no") or m.get("id") or (m.get("nos")[0] if m.get("nos") else None)
            status = m.get("status", "")
            if status == "proposto":
                pendentes.append((item, f"Proposto para {no_id}"))
            elif status == "aprovado":
                if no_id not in itens_por_no:
                    itens_por_no[no_id] = []
                itens_por_no[no_id].append(item)

    if pendentes:
        html.append("<h2>Mapeamentos Pendentes / Propostos</h2><ul>")
        for p in pendentes:
            html.append(f"<li>{escape(str(p[0]))}: {escape(str(p[1]))}</li>")
        html.append("</ul>")

    # Construir hierarquia de nós
    filhos = {}
    raizes = []
    for nid, no in nos.items():
        if no.get("status") == "fundido":
            continue
        pai = no.get("pai")
        if pai:
            if pai not in filhos:
                filhos[pai] = []
            filhos[pai].append(nid)
        else:
            raizes.append(nid)

    html.append("<h2>Árvore</h2>")
    
    def render_no(nid):
        no = nos.get(nid)
        if not no: return ""
        nivel = no.get("nivel", "desconhecido")
        nome = no.get("nome", "Sem nome")
        status = no.get("status", "")
        
        css_class = f"no-{nivel}"
        if status == "proposto": css_class += " status-proposto"
        
        out = f"<li><span class='{css_class}'>{escape(nome)}</span> <code>({escape(nid)})</code>"
        
        itens = itens_por_no.get(nid, [])
        if itens:
            out += "<ul>"
            for item in itens:
                out += f"<li class='item-edital'>📄 {escape(str(item))}</li>"
            out += "</ul>"
            
        if nid in filhos:
            out += "<ul>"
            # Sort filhos by name
            filhos_ordenados = sorted(filhos[nid], key=lambda x: nos[x].get("nome", ""))
            for f in filhos_ordenados:
                out += render_no(f)
            out += "</ul>"
        out += "</li>"
        return out

    html.append("<ul>")
    raizes_ordenadas = sorted(raizes, key=lambda x: nos[x].get("nome", ""))
    for r in raizes_ordenadas:
        html.append(render_no(r))
    html.append("</ul>")
    
    html.append("</body></html>")

    HTML_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write("".join(html))

if __name__ == "__main__":
    gerar_relatorio_arvore()
