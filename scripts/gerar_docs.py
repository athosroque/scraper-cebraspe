"""Gera as páginas técnicas do MkDocs (`docs/tecnico/`) a partir do registro.

O registro (`src/registro/`) é a fonte única de scripts, etapas, checagens e
regras do projeto. Este módulo transforma esse registro em Markdown
determinístico: mesma entrada, mesma saída, sem data nem hora. As páginas são
versionadas no git, e `tests/test_registro.py` falha quando o disco fica para
trás do registro.

Uso:
    python -m scripts.gerar_docs               grava todas as páginas
    python -m scripts.gerar_docs --sem-banco   não gera banco.md (sem conexão)
    python -m scripts.gerar_docs --verificar   não grava; sai com 1 se algo difere

Os argumentos dos scripts são lidos com `ast`: este módulo nunca importa nem
executa os scripts do projeto.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

import psycopg2

from src.registro import REGISTRO
from src.registro.modelo import (
    AREAS_REGRA,
    CAMADAS_CHECAGEM,
    CATEGORIAS_SCRIPT,
    Checagem,
    Etapa,
    Registro,
    Regra,
    Script,
)
from src.stats_writer import conectar

PROJETO_DIR = Path(__file__).resolve().parent.parent
DESTINO = PROJETO_DIR / "docs" / "tecnico"
ADR_DIR = PROJETO_DIR / "docs" / "adr"
CABECALHO = (
    "<!-- Gerado por scripts/gerar_docs.py a partir de src/registro/. "
    "Não editar à mão: rode `make docs-gerar`. -->\n\n"
)

# `public` (pipeline) e `app` (usuários e simulados do site). Os schemas
# `test_*` são criados pelos testes e ficam de fora. Fora do `public`, o nome
# sai qualificado (`app.usuario`).
_NOME = (
    "CASE WHEN {a}.table_schema = 'public' THEN {a}.table_name "
    "ELSE {a}.table_schema || '.' || {a}.table_name END"
)
_SQL_COLUNAS = f"""
    SELECT {_NOME.format(a="c")}, c.column_name, c.data_type, c.is_nullable
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name
     WHERE c.table_schema IN ('public', 'app') AND t.table_type = 'BASE TABLE'
     ORDER BY c.table_schema DESC, c.table_name, c.ordinal_position
"""
_SQL_VIEWS = f"""
    SELECT {_NOME.format(a="v")}
      FROM information_schema.views v
     WHERE v.table_schema IN ('public', 'app')
     ORDER BY v.table_schema DESC, v.table_name
"""

_TITULO_CATEGORIA = {
    "pipeline": "Pipeline",
    "curadoria": "Curadoria",
    "relatorio": "Relatórios",
    "manutencao": "Manutenção",
    "experimento": "Experimentos",
    "obsoleto": "Obsoletos",
}


# ---------------------------------------------------------------- leitura AST


def _valor_literal(no: ast.AST | None, padrao):
    """Valor literal do nó, ou `padrao` quando o nó é ausente ou não literal."""
    if no is None:
        return padrao
    try:
        return ast.literal_eval(no)
    except (ValueError, TypeError, SyntaxError):
        return padrao


def _nomes_de_grupos_exclusivos(arvore: ast.AST) -> set[str]:
    """Nomes de variáveis atribuídas a `add_mutually_exclusive_group()`."""
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign) or not isinstance(no.value, ast.Call):
            continue
        func = no.value.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "add_mutually_exclusive_group"
        ):
            nomes.update(alvo.id for alvo in no.targets if isinstance(alvo, ast.Name))
    return nomes


def _descrever_argumento(chamada: ast.Call, exclusivo: bool) -> dict:
    kw = {k.arg: k.value for k in chamada.keywords if k.arg}
    nomes = [
        a.value
        for a in chamada.args
        if isinstance(a, ast.Constant) and isinstance(a.value, str)
    ]

    no_default = kw.get("default")
    if no_default is None:
        padrao = ""
    else:
        try:
            padrao = repr(ast.literal_eval(no_default))
        except (ValueError, TypeError, SyntaxError):
            padrao = ast.unparse(no_default)

    no_help = kw.get("help")
    ajuda = _valor_literal(no_help, "")
    choices = _valor_literal(kw.get("choices"), None)
    return {
        "nomes": nomes,
        "help": ajuda if isinstance(ajuda, str) else "",
        "action": _valor_literal(kw.get("action"), ""),
        "default": padrao,
        "choices": list(choices) if isinstance(choices, (list, tuple)) else None,
        "required": bool(_valor_literal(kw.get("required"), False)),
        "nargs": _valor_literal(kw.get("nargs"), None),
        # argparse.SUPPRESS: o --help do próprio argparse também esconde o item.
        "oculto": isinstance(no_help, ast.Attribute) and no_help.attr == "SUPPRESS",
        "exclusivo": exclusivo,
    }


def argumentos_argparse(caminho: Path) -> list[dict]:
    """Argumentos `add_argument(...)` do arquivo, na ordem do código.

    Lê o arquivo com `ast`, sem importá-lo. Cobre parsers em `main()`, funções
    auxiliares, o bloco `if __name__ == "__main__"` e grupos mutuamente
    exclusivos (marcados com `exclusivo=True`). Valores não literais viram ""
    (exceto `default`, que cai para o código-fonte via `ast.unparse`).
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    grupos = _nomes_de_grupos_exclusivos(arvore)
    chamadas = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "add_argument"
    ]
    chamadas.sort(key=lambda no: (no.lineno, no.col_offset))
    return [
        _descrever_argumento(
            chamada,
            exclusivo=isinstance(chamada.func.value, ast.Name)
            and chamada.func.value.id in grupos,
        )
        for chamada in chamadas
    ]


def caminho_do_modulo(modulo: str) -> Path:
    """`scripts.x` -> PROJETO_DIR/scripts/x.py; `src.y` -> PROJETO_DIR/src/y.py."""
    if not modulo.startswith(("scripts.", "src.")):
        raise ValueError(f"módulo fora de scripts/ e src/: {modulo!r}")
    *pacotes, nome = modulo.split(".")
    return PROJETO_DIR.joinpath(*pacotes, f"{nome}.py")


# ------------------------------------------------------------------- helpers


def _celula(texto: str) -> str:
    """Texto seguro para célula de tabela Markdown."""
    return texto.replace("|", "\\|").replace("\n", " ").strip()


def _id_mermaid(id_etapa: str) -> str:
    """Id de nó Mermaid: só letras, números e sublinhado."""
    return re.sub(r"[^A-Za-z0-9_]", "_", id_etapa)


def _link_adr(adr: str) -> str:
    """Link para o arquivo da ADR em docs/adr/, ou só o id se não houver arquivo."""
    achados = sorted(ADR_DIR.glob(f"{adr}-*.md"))
    if not achados:
        return adr
    return f"[{adr}](../adr/{achados[0].name})"


def _lista_adrs(adrs: tuple[str, ...]) -> str:
    return ", ".join(_link_adr(adr) for adr in adrs) or "nenhuma"


def _relativo(caminho: Path) -> str:
    try:
        return str(caminho.relative_to(PROJETO_DIR))
    except ValueError:
        return str(caminho)


def _pagina(corpo: str) -> str:
    return CABECALHO + corpo


# ------------------------------------------------------------------- páginas


def pagina_indice(reg: Registro) -> str:
    """Página `index.md`: abre em `/tecnico/` (sem ela, o nginx responde 403)."""
    linhas = [
        "# Gerado do código",
        "",
        "Páginas geradas de `src/registro/` por `make docs-gerar`. O teste "
        "`tests/test_registro.py` recusa página diferente do código.",
        "",
        f"- [Pipeline](pipeline.md): {len(reg.etapas)} etapas, dependências e portões humanos.",
        f"- [Comandos](comandos.md): {len(reg.scripts)} scripts e seus argumentos.",
        f"- [Regras](regras.md): {len(reg.regras)} patterns e anti-patterns do `CLAUDE.md`.",
        f"- [Checagens](checagens.md): {len(reg.checagens)} checagens do pipeline.",
        "- [Banco](banco.md): tabelas e views dos schemas `public` e `app`.",
    ]
    return _pagina("\n".join(linhas) + "\n")


def pagina_pipeline(reg: Registro) -> str:
    """Página `pipeline.md`: grafo Mermaid e uma seção por etapa."""
    linhas = [
        "# Pipeline",
        "",
        "Etapas do pipeline e suas dependências (`depois_de`), geradas do registro. "
        "Borda laranja grossa: portão humano, o dono aprova antes da próxima etapa. "
        "Fundo azul: etapa que usa LLM.",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    for etapa in reg.etapas:
        rotulo = f"{etapa.id} {etapa.nome}".replace('"', "'")
        linhas.append(f'    {_id_mermaid(etapa.id)}["{rotulo}"]')
    for etapa in reg.etapas:
        for dependencia in etapa.depois_de:
            linhas.append(f"    {_id_mermaid(dependencia)} --> {_id_mermaid(etapa.id)}")
    # Portão só na borda e LLM só no fundo: uma etapa pode ter os dois.
    # Fundo semitransparente: o texto do nó segue a cor do tema (claro ou escuro).
    linhas.append("    classDef llm fill:#3b82f633,stroke:#3b82f6")
    linhas.append("    classDef portao stroke:#f59e0b,stroke-width:3px")
    portoes = [_id_mermaid(e.id) for e in reg.etapas if e.portao_humano]
    com_llm = [_id_mermaid(e.id) for e in reg.etapas if e.llm]
    if com_llm:
        linhas.append(f"    class {','.join(com_llm)} llm")
    if portoes:
        linhas.append(f"    class {','.join(portoes)} portao")
    linhas += ["```", ""]

    for etapa in reg.etapas:
        linhas += _secao_etapa(etapa)
    return _pagina("\n".join(linhas).rstrip() + "\n")


def _secao_etapa(etapa: Etapa) -> list[str]:
    linhas = [f"## {etapa.id} {etapa.nome}", ""]
    if etapa.comandos:
        linhas += ["```bash", *etapa.comandos, "```", ""]
    else:
        linhas += ["Sem comando próprio.", ""]
    scripts = ", ".join(f"`{m}`" for m in etapa.scripts) or "nenhum"
    dependencias = ", ".join(etapa.depois_de) or "nenhuma (início do pipeline)"
    linhas += [
        f"**Scripts:** {scripts}",
        "",
        f"**Depende de:** {dependencias}",
        "",
        f"**LLM:** `{etapa.llm}`" if etapa.llm else "**LLM:** não usa",
        "",
        f"**Portão humano:** {etapa.portao_humano}"
        if etapa.portao_humano
        else "**Portão humano:** nenhum",
        "",
        f"**ADRs:** {_lista_adrs(etapa.adrs)}",
        "",
        "**Entradas:**",
        "",
    ]
    linhas += [f"- {item}" for item in etapa.entradas] or ["- nenhuma"]
    linhas += ["", "**Saídas:**", ""]
    linhas += [f"- {item}" for item in etapa.saidas] or ["- nenhuma"]
    if etapa.notas:
        linhas += ["", f"**Notas:** {etapa.notas.strip()}"]
    linhas.append("")
    return linhas


def pagina_comandos(reg: Registro) -> str:
    """Página `comandos.md`: cada script com resumo e argumentos."""
    linhas = [
        "# Comandos",
        "",
        "Cada script é um ponto de entrada `python -m <módulo>`. Os argumentos são "
        "lidos do código-fonte; os ocultos (`argparse.SUPPRESS`) ficam de fora.",
        "",
    ]
    for categoria in CATEGORIAS_SCRIPT:
        grupo = sorted(
            (s for s in reg.scripts if s.categoria == categoria),
            key=lambda s: s.modulo,
        )
        if not grupo:
            continue
        linhas += [f"## {_TITULO_CATEGORIA[categoria]}", ""]
        for script in grupo:
            linhas += _secao_script(script)
    return _pagina("\n".join(linhas).rstrip() + "\n")


def _secao_script(script: Script) -> list[str]:
    linhas = [f"### `python -m {script.modulo}`", "", script.resumo, ""]
    if script.adrs:
        linhas += [f"**ADRs:** {_lista_adrs(script.adrs)}", ""]
    arquivo = caminho_do_modulo(script.modulo)
    if not arquivo.exists():
        linhas += ["Arquivo não encontrado.", ""]
        return linhas
    if script.cli == "argparse":
        linhas += _tabela_argumentos(argumentos_argparse(arquivo))
    elif script.cli == "argv":
        linhas += ["```bash", script.uso_argv, "```", ""]
    else:
        linhas += ["Sem argumentos.", ""]
    return linhas


def _tabela_argumentos(argumentos: list[dict]) -> list[str]:
    visiveis = [a for a in argumentos if not a["oculto"]]
    if not visiveis:
        return ["Sem argumentos.", ""]
    linhas = ["| Argumento | Ajuda | Padrão |", "|---|---|---|"]
    for arg in visiveis:
        nomes = ", ".join(f"`{n}`" for n in arg["nomes"]) or "—"
        if arg["exclusivo"]:
            nomes += " (grupo exclusivo)"
        padrao = f"`{arg['default']}`" if arg["default"] else "—"
        linhas.append(
            f"| {_celula(nomes)} | {_celula(arg['help']) or '—'} | {_celula(padrao)} |"
        )
    return [*linhas, ""]


def pagina_regras(reg: Registro) -> str:
    """Página `regras.md`: patterns (§6) e anti-patterns (§7) por área."""
    linhas = [
        "# Regras",
        "",
        "Textos literais de `CLAUDE.md`: patterns (§6) e anti-patterns (§7). Cada "
        "regra mostra as ADRs que a motivam e o teste que a guarda, quando houver.",
        "",
    ]
    for tipo, titulo in (("pattern", "Patterns"), ("anti-pattern", "Anti-patterns")):
        linhas += [f"## {titulo}", ""]
        regras = [r for r in reg.regras if r.tipo == tipo]
        if not regras:
            linhas += ["Nenhuma regra.", ""]
            continue
        for area in AREAS_REGRA:
            do_grupo = [r for r in regras if r.area == area]
            if not do_grupo:
                continue
            linhas += [f"### {area}", ""]
            for regra in do_grupo:
                linhas += _secao_regra(regra)
    return _pagina("\n".join(linhas).rstrip() + "\n")


def _secao_regra(regra: Regra) -> list[str]:
    guardas = ", ".join(f"`{t}`" for t in regra.testes) or "sem teste guarda"
    return [
        f"#### {regra.id}",
        "",
        regra.texto.strip(),
        "",
        f"ADRs: {_lista_adrs(regra.adrs)}",
        "",
        f"Teste guarda: {guardas}",
        "",
    ]


def pagina_checagens(reg: Registro) -> str:
    """Página `checagens.md`: checagens agrupadas por camada."""
    linhas = [
        "# Checagens",
        "",
        "Cada checagem valida uma parte do pipeline. Consulta de banco devolve as "
        "linhas problemáticas: zero linhas é verde. Checagens de teste ou de comando "
        "apontam para o teste do pytest ou para o comando que mostra o resultado.",
        "",
    ]
    for camada in CAMADAS_CHECAGEM:
        do_grupo = [c for c in reg.checagens if c.camada == camada]
        if not do_grupo:
            continue
        linhas += [f"## {camada}", ""]
        for checagem in do_grupo:
            linhas += _secao_checagem(checagem)
    return _pagina("\n".join(linhas).rstrip() + "\n")


def _titulo_e_resto(descricao: str) -> tuple[str, str]:
    """Primeira frase vira o título da seção; o resto, o parágrafo abaixo."""
    texto = " ".join(descricao.split())
    titulo, _, resto = texto.partition(". ")
    return titulo.rstrip("."), resto


def _secao_checagem(checagem: Checagem) -> list[str]:
    titulo, resto = _titulo_e_resto(checagem.descricao)
    linhas = [f"### {checagem.id} {titulo}", ""]
    if resto:
        linhas += [resto, ""]
    linhas += [
        f"- **Bloqueante:** {'sim' if checagem.bloqueante else 'não'}",
        f"- **Onde consultar:** {checagem.onde}",
    ]
    if checagem.teste:
        linhas.append(f"- **Teste:** `{checagem.teste}`")
    linhas += [f"- **ADRs:** {_lista_adrs(checagem.adrs)}", ""]
    if checagem.comando:
        linhas += ["```bash", checagem.comando.strip(), "```", ""]
    if checagem.consulta:
        linhas += ["```sql", checagem.consulta.strip(), "```", ""]
    return linhas


def pagina_banco(colunas: list[tuple], views: list[str]) -> str:
    """Página `banco.md`: tabelas dos schemas `public` e `app` e lista de views.

    `colunas` vem de `ler_schema`: (tabela, coluna, tipo, is_nullable), já ordenadas.
    """
    por_tabela: dict[str, list[tuple]] = {}
    for tabela, coluna, tipo, anulavel in colunas:
        por_tabela.setdefault(tabela, []).append((coluna, tipo, anulavel))

    linhas = [
        "# Banco",
        "",
        "Estrutura dos schemas `public` (pipeline) e `app` (site) de "
        "`scraper-cebraspe-db`, lida do `information_schema`. Só tabelas base e "
        "views; os schemas `test_*` dos testes ficam de fora.",
        "",
    ]
    if not por_tabela:
        linhas += ["Nenhuma tabela.", ""]
    for tabela, cols in por_tabela.items():
        linhas += [
            f"## {tabela}",
            "",
            "| Coluna | Tipo | Nulo |",
            "|---|---|---|",
        ]
        for coluna, tipo, anulavel in cols:
            nulo = "sim" if anulavel == "YES" else "não"
            linhas.append(f"| {_celula(coluna)} | {_celula(tipo)} | {nulo} |")
        linhas.append("")
    linhas += ["## Views", ""]
    linhas += [f"- `{view}`" for view in views] or ["Nenhuma view."]
    return _pagina("\n".join(linhas).rstrip() + "\n")


def ler_schema(conn) -> tuple[list, list]:
    """Lê colunas e views de `public` e `app`. Só leitura; use uma conexão nova.

    Devolve (colunas, views): colunas são (tabela, coluna, tipo, is_nullable) e
    views são nomes, ambos ordenados.
    """
    conn.set_session(readonly=True)
    try:
        with conn.cursor() as cur:
            cur.execute(_SQL_COLUNAS)
            colunas = [tuple(linha) for linha in cur.fetchall()]
            cur.execute(_SQL_VIEWS)
            views = [linha[0] for linha in cur.fetchall()]
    finally:
        conn.rollback()
    return colunas, views


def gerar_paginas(
    reg: Registro | None = None, com_banco: bool = False
) -> dict[Path, str]:
    """Conteúdo de cada página, indexado pelo caminho de destino.

    Usa `src.registro.REGISTRO` quando `reg` é None. Com `com_banco`, abre uma
    conexão só leitura para gerar também `banco.md`.
    """
    reg = REGISTRO if reg is None else reg
    paginas = {
        DESTINO / "index.md": pagina_indice(reg),
        DESTINO / "pipeline.md": pagina_pipeline(reg),
        DESTINO / "comandos.md": pagina_comandos(reg),
        DESTINO / "regras.md": pagina_regras(reg),
        DESTINO / "checagens.md": pagina_checagens(reg),
    }
    if com_banco:
        conn = conectar()
        try:
            paginas[DESTINO / "banco.md"] = pagina_banco(*ler_schema(conn))
        finally:
            conn.close()
    return paginas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Gera docs/tecnico/ a partir do registro em src/registro/."
    )
    ap.add_argument(
        "--sem-banco",
        action="store_true",
        help="não gera banco.md e não abre conexão com o banco",
    )
    ap.add_argument(
        "--verificar",
        action="store_true",
        help="não grava; compara com o disco e sai com 1 se algum arquivo difere",
    )
    args = ap.parse_args(argv)

    try:
        paginas = gerar_paginas(com_banco=not args.sem_banco)
    except (RuntimeError, psycopg2.Error) as erro:
        print(f"Erro ao ler o banco para banco.md: {erro}", file=sys.stderr)
        print("Use --sem-banco para gerar só as páginas do registro.", file=sys.stderr)
        return 2

    if args.verificar:
        diferentes = [
            caminho
            for caminho, texto in paginas.items()
            if not caminho.exists() or caminho.read_text(encoding="utf-8") != texto
        ]
        if diferentes:
            for caminho in diferentes:
                print(f"ausente ou diferente: {_relativo(caminho)}")
            print("Rode `make docs-gerar`.")
            return 1
        print(f"{len(paginas)} página(s) em dia.")
        return 0

    DESTINO.mkdir(parents=True, exist_ok=True)
    for caminho, texto in paginas.items():
        caminho.write_text(texto, encoding="utf-8")
    print(f"{len(paginas)} página(s) gravada(s) em {_relativo(DESTINO)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
