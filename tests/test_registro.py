"""Registro do pipeline: guardas sobre o registro real e testes do gerador (Etapa 9/D2, KAN-69).

As guardas leem o `REGISTRO` real e o disco; o gerador é testado com um registro
mínimo montado aqui, para não depender do conteúdo que os outros agentes preenchem.
"""

import re
import textwrap

import pytest

from scripts import gerar_docs
from src.registro import REGISTRO
from src.registro.modelo import Checagem, Etapa, Registro, Regra, Script

RAIZ = gerar_docs.PROJETO_DIR
_RE_MAIN = re.compile(r"""if __name__ == ["']__main__["']""")


def _modulos_registrados() -> set[str]:
    return {s.modulo for s in REGISTRO.scripts}


def _adrs_citados() -> list[tuple[str, str]]:
    """Pares (dono, ADR) de todo o registro."""
    pares = [(f"script {s.modulo}", a) for s in REGISTRO.scripts for a in s.adrs]
    pares += [(f"etapa {e.id}", a) for e in REGISTRO.etapas for a in e.adrs]
    pares += [(f"checagem {c.id}", a) for c in REGISTRO.checagens for a in c.adrs]
    pares += [(f"regra {r.id}", a) for r in REGISTRO.regras for a in r.adrs]
    pares += [(f"tarefa {t.id}", a) for t in REGISTRO.tarefas for a in t.adrs]
    return pares


def _testes_citados() -> list[tuple[str, str]]:
    """Pares (dono, nodeid) de regras e checagens."""
    pares = [(f"regra {r.id}", t) for r in REGISTRO.regras for t in r.testes]
    pares += [(f"checagem {c.id}", c.teste) for c in REGISTRO.checagens if c.teste]
    return pares


def _ciclo(etapas) -> list[str]:
    """Ids de um ciclo em `depois_de` (DFS), ou [] se o grafo é acíclico."""
    deps = {e.id: e.depois_de for e in etapas}
    cor: dict[str, int] = {}  # 1 = em visita, 2 = concluído
    pilha: list[str] = []

    def visitar(no: str) -> list[str]:
        cor[no] = 1
        pilha.append(no)
        for dep in deps.get(no, ()):
            if cor.get(dep) == 1:
                return [*pilha[pilha.index(dep) :], dep]
            if dep not in cor:
                achado = visitar(dep)
                if achado:
                    return achado
        pilha.pop()
        cor[no] = 2
        return []

    for no in deps:
        if no not in cor:
            achado = visitar(no)
            if achado:
                return achado
    return []


# ----------------------------------------------------------- guardas do registro


def test_todo_script_esta_no_registro():
    """Todo scripts/*.py e todo src/*.py com __main__ tem Script; todo Script tem arquivo."""
    esperados = {
        f"scripts.{p.stem}"
        for p in (RAIZ / "scripts").glob("*.py")
        if p.name != "__init__.py"
    }
    esperados |= {
        f"src.{p.stem}"
        for p in (RAIZ / "src").glob("*.py")
        if _RE_MAIN.search(p.read_text(encoding="utf-8"))
    }
    faltam = sorted(esperados - _modulos_registrados())
    sem_arquivo = sorted(
        s.modulo
        for s in REGISTRO.scripts
        if not gerar_docs.caminho_do_modulo(s.modulo).exists()
    )
    assert not faltam, f"sem Script no registro (src/registro/scripts.py): {faltam}"
    assert not sem_arquivo, f"Script aponta para arquivo inexistente: {sem_arquivo}"


def test_etapas_citam_scripts_registrados():
    """Todo script citado por uma etapa está registrado."""
    registrados = _modulos_registrados()
    problemas = [
        f"etapa {e.id} -> {m}"
        for e in REGISTRO.etapas
        for m in e.scripts
        if m not in registrados
    ]
    assert not problemas, f"etapas citam scripts não registrados: {problemas}"


def test_depois_de_sem_ciclo_e_ids_existentes():
    """`depois_de` aponta só para etapas existentes e forma um grafo sem ciclo."""
    ids = {e.id for e in REGISTRO.etapas}
    inexistentes = [
        f"etapa {e.id} depois_de {d}"
        for e in REGISTRO.etapas
        for d in e.depois_de
        if d not in ids
    ]
    assert not inexistentes, f"depois_de com id inexistente: {inexistentes}"
    ciclo = _ciclo(REGISTRO.etapas)
    assert not ciclo, f"ciclo em depois_de: {' -> '.join(ciclo)}"


def test_ids_unicos():
    """Ids de etapas, checagens, regras e tarefas não se repetem."""
    colecoes = {
        "etapas": [e.id for e in REGISTRO.etapas],
        "checagens": [c.id for c in REGISTRO.checagens],
        "regras": [r.id for r in REGISTRO.regras],
        "tarefas": [t.id for t in REGISTRO.tarefas],
    }
    for nome, ids in colecoes.items():
        repetidos = sorted({i for i in ids if ids.count(i) > 1})
        assert not repetidos, f"{nome} com id repetido: {repetidos}"


def test_adrs_citados_existem():
    """Toda ADR citada no registro tem arquivo em docs/adr/."""
    faltam = sorted(
        {
            f"{dono}: {adr}"
            for dono, adr in _adrs_citados()
            if not list((RAIZ / "docs" / "adr").glob(f"{adr}-*.md"))
        }
    )
    assert not faltam, f"ADRs citadas sem arquivo em docs/adr/: {faltam}"


def test_testes_citados_existem():
    """Todo teste guarda de regra ou checagem existe; se tem ::nome, o nome está no arquivo."""
    problemas = []
    for dono, nodeid in _testes_citados():
        arquivo, *partes = nodeid.split("::")
        caminho = RAIZ / arquivo
        if not caminho.exists():
            problemas.append(f"{dono}: arquivo {arquivo} não existe")
            continue
        if not partes:
            continue
        nome = partes[-1].split("[")[0]
        texto = caminho.read_text(encoding="utf-8")
        if not re.search(rf"^\s*(def|class) {re.escape(nome)}\b", texto, re.M):
            problemas.append(f"{dono}: {nome} não aparece em {arquivo}")
    assert not problemas, f"testes guarda citados e inexistentes: {problemas}"


def _secao_do_claude_md(titulo: str) -> str:
    """Texto de uma seção do CLAUDE.md, do título até o próximo `## `."""
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    inicio = texto.index(f"\n{titulo}\n")
    fim = texto.index("\n## ", inicio + 1)
    return texto[inicio:fim]


def test_nucleo_do_claude_md_bate_com_o_registro():
    """As regras citadas em §6 e §7 do CLAUDE.md são o núcleo do registro, com link."""
    citados: set[str] = set()
    for titulo in ("## 6. Patterns", "## 7. Anti-patterns"):
        for linha in _secao_do_claude_md(titulo).splitlines():
            ids = re.findall(r"\*\*([PA]\d{2,3})\*\*", linha)
            for id_regra in ids:
                citados.add(id_regra)
                assert f"docs/tecnico/regras.md#{id_regra.lower()}" in linha, (
                    f"{id_regra} citada sem link para docs/tecnico/regras.md"
                )
    nucleo = {r.id for r in REGISTRO.regras if r.nucleo}
    assert citados == nucleo, (
        f"CLAUDE.md e registro divergem no núcleo: "
        f"só no CLAUDE.md {sorted(citados - nucleo)}, "
        f"só no registro {sorted(nucleo - citados)}"
    )


def test_links_relativos_do_claude_md_existem():
    """Todo link relativo do CLAUDE.md aponta para arquivo ou diretório existente."""
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    problemas = []
    for alvo in re.findall(r"\]\(([^)\s]+)\)", texto):
        if alvo.startswith(("http", "#", "mailto:")):
            continue
        if not (RAIZ / alvo.split("#", 1)[0]).exists():
            problemas.append(alvo)
    assert not problemas, f"links quebrados no CLAUDE.md: {problemas}"


def test_claude_md_aponta_para_tarefas():
    """O CLAUDE.md leva o agente ao índice de tarefas."""
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    assert "docs/tecnico/tarefas.md" in texto


def test_tarefas_citam_ids_existentes():
    """Regras, etapas, scripts, checagens, ADRs e páginas de `leia` citados existem."""
    ids = {
        "regras": {r.id for r in REGISTRO.regras},
        "etapas": {e.id for e in REGISTRO.etapas},
        "scripts": _modulos_registrados(),
        "checagens": {c.id for c in REGISTRO.checagens},
    }
    problemas = []
    for tarefa in REGISTRO.tarefas:
        for campo, existentes in ids.items():
            for item in getattr(tarefa, campo):
                if item not in existentes:
                    problemas.append(f"tarefa {tarefa.id}: {campo} {item} inexistente")
        for adr in tarefa.adrs:
            if not list((RAIZ / "docs" / "adr").glob(f"{adr}-*.md")):
                problemas.append(f"tarefa {tarefa.id}: ADR {adr} sem arquivo")
        for pagina in tarefa.leia:
            if not (RAIZ / "docs" / pagina).exists():
                problemas.append(f"tarefa {tarefa.id}: leia {pagina} inexistente")
    assert not problemas, f"tarefas citam itens inexistentes: {problemas}"


def test_toda_area_com_regra_tem_tarefa():
    """Toda área usada por uma regra aparece em pelo menos uma tarefa."""
    usadas = {r.area for r in REGISTRO.regras}
    cobertas = {a for t in REGISTRO.tarefas for a in t.areas}
    faltam = sorted(usadas - cobertas)
    assert not faltam, f"áreas sem tarefa (regras ficariam fora do índice): {faltam}"


def test_paginas_geradas_batem_com_o_disco():
    """As páginas de docs/tecnico/ são as que o registro gera hoje."""
    diferentes = []
    for caminho, esperado in gerar_docs.gerar_paginas(com_banco=False).items():
        if not caminho.exists() or caminho.read_text(encoding="utf-8") != esperado:
            diferentes.append(str(caminho.relative_to(RAIZ)))
    assert not diferentes, (
        f"páginas ausentes ou desatualizadas: {diferentes}. rode make docs-gerar"
    )


def test_dagster_definitions_batem_com_o_registro():
    """Assets do Dagster batem com as etapas do registro."""
    pytest.skip("Dagster ainda não existe (D5a, KAN-31)")


# ----------------------------------------------------------- testes do gerador


@pytest.fixture
def registro_minimo() -> Registro:
    scripts = (
        Script(
            "scripts.extrair_questoes",
            "Extrai questões dos cadernos.",
            "pipeline",
            "argparse",
            adrs=("ADR-031",),
        ),
        Script(
            "scripts.curar_arvore",
            "Curadoria da árvore mestre.",
            "curadoria",
            "argparse",
            adrs=("ADR-030",),
        ),
        Script(
            "scripts.atualizar_revisao",
            "Atualiza os artefatos da revisão.",
            "relatorio",
            "argv",
            uso_argv="python -m scripts.atualizar_revisao [diretorio_revisao]",
        ),
    )
    etapas = (
        Etapa(
            "P1",
            "Extração",
            ("python -m scripts.extrair_questoes",),
            ("scripts.extrair_questoes",),
            ("cadernos PDF",),
            ("questões JSON",),
            adrs=("ADR-031",),
        ),
        Etapa(
            "P2.1",
            "Curadoria | árvore",
            ("python -m scripts.curar_arvore --html",),
            ("scripts.curar_arvore",),
            ("questões JSON",),
            ("árvore",),
            depois_de=("P1",),
            portao_humano="Dono aprova o mapeamento.",
        ),
        Etapa(
            "P3",
            "Relatório",
            ("python -m scripts.atualizar_revisao",),
            ("scripts.atualizar_revisao",),
            ("árvore",),
            ("relatórios",),
            depois_de=("P2.1",),
            llm="modelo-x",
        ),
    )
    checagens = (
        Checagem(
            "K01",
            "banco",
            "Questões sem assunto",
            "banco",
            consulta="SELECT 1 WHERE false",
        ),
    )
    regras = (
        Regra(
            "P01",
            "pattern",
            "coleta",
            "Filtro de ano pelo slug da URL.",
            adrs=("ADR-001",),
            testes=("tests/test_registro.py::test_ids_unicos",),
        ),
        Regra(
            "A01",
            "anti-pattern",
            "llm",
            "Não chamar LLM sem log.\n- sub-item preservado",
        ),
    )
    return Registro(scripts, etapas, checagens, regras)


def test_pipeline_mermaid_tem_arestas_e_portao(registro_minimo):
    """O grafo tem as arestas de depois_de, o estilo de portão e o de LLM."""
    pagina = gerar_docs.pagina_pipeline(registro_minimo)
    assert "flowchart TD" in pagina
    assert 'P1["P1 Extração"]' in pagina
    assert 'P2_1["P2.1 Curadoria | árvore"]' in pagina
    assert "P1 --> P2_1" in pagina
    assert "P2_1 --> P3" in pagina
    assert "classDef portao stroke:#f59e0b" in pagina
    assert "class P2_1 portao" in pagina
    assert "class P3 llm" in pagina
    assert "## P2.1 Curadoria | árvore" in pagina
    assert "[ADR-031](../adr/ADR-031-" in pagina


def test_comandos_lista_argparse_real(registro_minimo):
    """Argumentos de um script argparse real aparecem; os ocultos ficam de fora."""
    pagina = gerar_docs.pagina_comandos(registro_minimo)
    assert "### `python -m scripts.curar_arvore`" in pagina
    assert "| `--mapear`" in pagina
    assert "`--desmapear`" in pagina
    assert "`--arvore`" not in pagina  # help=argparse.SUPPRESS


def test_comandos_mostra_uso_argv(registro_minimo):
    """Script com cli argv mostra o uso em bloco bash."""
    pagina = gerar_docs.pagina_comandos(registro_minimo)
    assert (
        "```bash\npython -m scripts.atualizar_revisao [diretorio_revisao]\n```"
        in pagina
    )


def test_argumentos_do_bloco_main():
    """Argumentos dentro do bloco `if __name__ == "__main__"` são lidos."""
    args = gerar_docs.argumentos_argparse(RAIZ / "scripts" / "extrair_questoes.py")
    assert [n for a in args for n in a["nomes"]] == [
        "--reprocessar",
        "--reprocessar-erros",
    ]
    assert args[0]["action"] == "store_true"
    assert args[0]["help"] == "refaz também o que já está concluído"
    assert args[0]["default"] == ""


def test_argumentos_em_arquivo_temporario(tmp_path):
    """Grupo exclusivo, positional com choices, default não literal e oculto."""
    script = tmp_path / "exemplo.py"
    script.write_text(
        textwrap.dedent(
            """
            import argparse

            CAMINHO = "x"

            def montar():
                ap = argparse.ArgumentParser()
                grupo = ap.add_mutually_exclusive_group()
                grupo.add_argument("--a", action="store_true", help="liga a")
                grupo.add_argument("--b", default=3, help="valor | outro")
                ap.add_argument("--caminho", default=CAMINHO)
                ap.add_argument("--interno", help=argparse.SUPPRESS)
                ap.add_argument("pdf", nargs="?", choices=["p", "q"])
                return ap

            if __name__ == "__main__":
                montar().parse_args()
            """
        ),
        encoding="utf-8",
    )
    args = gerar_docs.argumentos_argparse(script)
    por_nome = {a["nomes"][0]: a for a in args}
    assert [a["nomes"] for a in args] == [
        ["--a"],
        ["--b"],
        ["--caminho"],
        ["--interno"],
        ["pdf"],
    ]
    assert por_nome["--a"]["exclusivo"] is True
    assert por_nome["--a"]["action"] == "store_true"
    assert por_nome["--b"]["exclusivo"] is True
    assert por_nome["--b"]["default"] == "3"
    assert por_nome["--caminho"]["exclusivo"] is False
    assert por_nome["--caminho"]["default"] == "CAMINHO"
    assert por_nome["--interno"]["oculto"] is True
    assert por_nome["pdf"]["choices"] == ["p", "q"]
    assert por_nome["pdf"]["nargs"] == "?"


def test_pipe_em_celula_e_escapado(tmp_path, monkeypatch):
    """`|` dentro da ajuda de um argumento vira `\\|` na tabela."""
    monkeypatch.setattr(gerar_docs, "PROJETO_DIR", tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "fake.py").write_text(
        "import argparse\nap = argparse.ArgumentParser()\n"
        'ap.add_argument("--x", help="a | b")\n',
        encoding="utf-8",
    )
    reg = Registro(
        scripts=(Script("scripts.fake", "Falso.", "manutencao", "argparse"),)
    )
    pagina = gerar_docs.pagina_comandos(reg)
    assert "a \\| b" in pagina
    assert "| a | b" not in pagina


def test_render_e_deterministico(registro_minimo):
    """Duas chamadas com o mesmo registro dão o mesmo texto, terminando em quebra de linha."""
    funcoes = (
        gerar_docs.pagina_pipeline,
        gerar_docs.pagina_comandos,
        gerar_docs.pagina_regras,
        gerar_docs.pagina_checagens,
    )
    for funcao in funcoes:
        primeira = funcao(registro_minimo)
        assert primeira == funcao(registro_minimo), funcao.__name__
        assert primeira.endswith("\n"), funcao.__name__
        assert primeira.startswith(gerar_docs.CABECALHO), funcao.__name__
    colunas = [("t", "id", "integer", "NO")]
    assert gerar_docs.pagina_banco(colunas, ["vw_t"]) == gerar_docs.pagina_banco(
        colunas, ["vw_t"]
    )


def test_regras_e_checagens_renderizam_guardas(registro_minimo):
    """Teste guarda ou 'sem teste guarda', sub-lista preservada, SQL em bloco."""
    regras = gerar_docs.pagina_regras(registro_minimo)
    assert "#### P01" in regras
    assert "Teste guarda: `tests/test_registro.py::test_ids_unicos`" in regras
    assert "Teste guarda: sem teste guarda" in regras
    assert "- sub-item preservado" in regras
    checagens = gerar_docs.pagina_checagens(registro_minimo)
    assert "### K01 Questões sem assunto" in checagens
    assert "- **Bloqueante:** sim" in checagens
    assert "```sql\nSELECT 1 WHERE false\n```" in checagens


def test_pagina_banco_monta_tabelas_e_views():
    """Tabelas com colunas (nulo sim/não) e a lista de views."""
    pagina = gerar_docs.pagina_banco(
        [("t", "id", "integer", "NO"), ("t", "nome", "text", "YES")], ["vw_t"]
    )
    assert "## t" in pagina
    assert "| id | integer | não |" in pagina
    assert "| nome | text | sim |" in pagina
    assert "## Views" in pagina
    assert "- `vw_t`" in pagina


def test_caminho_do_modulo():
    """scripts.x e src.y apontam para os arquivos do projeto."""
    assert gerar_docs.caminho_do_modulo("scripts.x") == RAIZ / "scripts" / "x.py"
    assert gerar_docs.caminho_do_modulo("src.y") == RAIZ / "src" / "y.py"
    with pytest.raises(ValueError):
        gerar_docs.caminho_do_modulo("tests.x")


def test_ciclo_detector_acha_ciclo_e_aceita_cadeia():
    """O detector de ciclo acha um ciclo de duas etapas e não acusa uma cadeia."""
    cadeia = (
        Etapa("A", "a", (), (), (), ()),
        Etapa("B", "b", (), (), (), (), depois_de=("A",)),
    )
    ciclo = (
        Etapa("A", "a", (), (), (), (), depois_de=("B",)),
        Etapa("B", "b", (), (), (), (), depois_de=("A",)),
    )
    assert _ciclo(cadeia) == []
    assert _ciclo(ciclo)


def test_cli_verificar_e_gravar(tmp_path, monkeypatch):
    """--verificar sai 1 com páginas ausentes e 0 depois de gravar; não toca docs/tecnico/."""
    destino = tmp_path / "tecnico"
    monkeypatch.setattr(gerar_docs, "DESTINO", destino)
    assert gerar_docs.main(["--verificar", "--sem-banco"]) == 1
    assert gerar_docs.main(["--sem-banco"]) == 0
    assert (destino / "pipeline.md").exists()
    assert not (destino / "banco.md").exists()
    assert gerar_docs.main(["--verificar", "--sem-banco"]) == 0
