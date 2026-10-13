"""Guarda dos ADRs: todo `docs/adr/ADR-*.md` está no catálogo e no `nav` (Etapa 9/D1, ADR-040).

O `mkdocs build --strict` só pega o ADR que falta no `nav`. Aqui se confere também o
catálogo `docs/adr/README.md`: uma linha por ADR, sem duplicata e sem link quebrado.
As verificações são funções puras sobre texto e dicionários, testadas com casos ruins
montados em `tmp_path`; o último bloco roda sobre os arquivos reais. Sem banco e sem rede.
"""

import re
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
PASTA_ADR = RAIZ / "docs" / "adr"
MKDOCS = RAIZ / "mkdocs.yml"
ABA_DECISOES = "Decisões"

_RE_LINHA_CATALOGO = re.compile(r"^\|\s*\[(ADR-\d+)\]\(([^)]+)\)", re.MULTILINE)
_RE_ARQUIVO_ADR = re.compile(r"^ADR-\d+-.+\.md$")


class _LoaderSemTags(yaml.SafeLoader):
    """Loader que ignora as tags customizadas do `mkdocs.yml` (`!!python/name:...`)."""


def _ignorar_tag(loader, sufixo, no):
    """Constrói o nó sem executar nada; o valor da tag customizada não interessa."""
    if isinstance(no, yaml.MappingNode):
        return loader.construct_mapping(no, deep=True)
    if isinstance(no, yaml.SequenceNode):
        return loader.construct_sequence(no, deep=True)
    return loader.construct_scalar(no)


_LoaderSemTags.add_multi_constructor("tag:yaml.org,2002:python/", _ignorar_tag)
_LoaderSemTags.add_multi_constructor("!", _ignorar_tag)


def carregar_nav(caminho: Path = MKDOCS) -> list:
    """Lê o `nav` do mkdocs.yml sem quebrar nas tags YAML customizadas."""
    config = yaml.load(caminho.read_text(encoding="utf-8"), Loader=_LoaderSemTags)
    return config["nav"]


def _folhas(no) -> list[str]:
    """Todos os caminhos de arquivo (folhas) de um trecho do `nav`."""
    if isinstance(no, str):
        return [no]
    if isinstance(no, list):
        return [f for item in no for f in _folhas(item)]
    if isinstance(no, dict):
        return [f for valor in no.values() for f in _folhas(valor)]
    return []


def _adrs_do_nav(nav: list) -> tuple[list[str], list[str]]:
    """Arquivos `adr/ADR-*.md` do nav: (dentro da aba Decisões, fora dela)."""
    dentro: list[str] = []
    fora: list[str] = []
    for aba in nav:
        titulo, conteudo = (
            next(iter(aba.items())) if isinstance(aba, dict) else ("", aba)
        )
        destino = dentro if titulo == ABA_DECISOES else fora
        destino += [
            Path(f).name
            for f in _folhas(conteudo)
            if re.match(r"adr/ADR-\d+-.+\.md$", f)
        ]
    return dentro, fora


def verificar_catalogo(readme: str, arquivos: set[str]) -> list[str]:
    """Problemas entre as linhas do README e os arquivos ADR existentes."""
    linhas = _RE_LINHA_CATALOGO.findall(readme)
    problemas = []
    vistos: dict[str, int] = {}
    for _, alvo in linhas:
        vistos[alvo] = vistos.get(alvo, 0) + 1
    for alvo, vezes in sorted(vistos.items()):
        if vezes > 1:
            problemas.append(
                f"docs/adr/README.md: {alvo} aparece {vezes} vezes no catálogo"
            )
        if alvo not in arquivos:
            problemas.append(
                f"docs/adr/README.md: link para arquivo que não existe: {alvo}"
            )
    for arquivo in sorted(arquivos - set(vistos)):
        problemas.append(
            f"docs/adr/README.md: falta a linha do catálogo para {arquivo}"
        )
    return problemas


def verificar_nav(nav: list, arquivos: set[str]) -> list[str]:
    """Problemas entre o `nav` do mkdocs.yml e os arquivos ADR existentes."""
    dentro, fora = _adrs_do_nav(nav)
    problemas = []
    for arquivo in sorted(set(fora)):
        problemas.append(f"mkdocs.yml: {arquivo} está fora da aba {ABA_DECISOES}")
    for arquivo in sorted({d for d in dentro if dentro.count(d) > 1}):
        problemas.append(
            f"mkdocs.yml: {arquivo} aparece mais de uma vez na aba {ABA_DECISOES}"
        )
    for arquivo in sorted(set(dentro) - arquivos):
        problemas.append(f"mkdocs.yml: nav aponta para ADR que não existe: {arquivo}")
    for arquivo in sorted(arquivos - set(dentro) - set(fora)):
        problemas.append(f"mkdocs.yml: falta {arquivo} no nav, na aba {ABA_DECISOES}")
    return problemas


def _arquivos_adr(pasta: Path) -> set[str]:
    return {p.name for p in pasta.glob("ADR-*.md") if _RE_ARQUIVO_ADR.match(p.name)}


# --- casos ruins, montados em tmp_path (não mexem nos arquivos reais) ---

_README_OK = (
    "| ADR | Data | Título | Status |\n|---|---|---|---|\n"
    "| [ADR-001](ADR-001-a.md) | 2026-01-01 | A | Aceito |\n"
    "| [ADR-002](ADR-002-b.md) | 2026-01-01 | B | Aceito |\n"
)

_MKDOCS_OK = """\
nav:
  - Início: index.md
  - Decisões:
      - adr/README.md
      - Tema:
          - "001 · A": adr/ADR-001-a.md
          - "002 · B": adr/ADR-002-b.md
  - Histórico:
      - historico.md
plugins:
  - mkdocstrings:
      handler: !!python/name:os.path.join
      extra: !!python/object/apply:os.getcwd []
"""


def _montar(tmp_path: Path, readme: str, mkdocs: str) -> tuple[str, list, set[str]]:
    pasta = tmp_path / "adr"
    pasta.mkdir()
    for nome in ("ADR-001-a.md", "ADR-002-b.md"):
        (pasta / nome).write_text("# ADR\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(mkdocs, encoding="utf-8")
    return readme, carregar_nav(tmp_path / "mkdocs.yml"), _arquivos_adr(pasta)


def test_caso_bom_sintetico_passa_e_tags_yaml_nao_quebram(tmp_path):
    readme, nav, arquivos = _montar(tmp_path, _README_OK, _MKDOCS_OK)
    assert verificar_catalogo(readme, arquivos) == []
    assert verificar_nav(nav, arquivos) == []


def test_adr_sem_linha_no_catalogo_e_apontado(tmp_path):
    readme, _, arquivos = _montar(tmp_path, _README_OK, _MKDOCS_OK)
    sem = readme.replace("| [ADR-002](ADR-002-b.md) | 2026-01-01 | B | Aceito |\n", "")
    assert verificar_catalogo(sem, arquivos) == [
        "docs/adr/README.md: falta a linha do catálogo para ADR-002-b.md"
    ]


def test_link_para_arquivo_inexistente_no_catalogo_e_apontado(tmp_path):
    readme, _, arquivos = _montar(tmp_path, _README_OK, _MKDOCS_OK)
    errado = readme.replace("ADR-002-b.md", "ADR-002-errado.md")
    problemas = verificar_catalogo(errado, arquivos)
    assert any("não existe: ADR-002-errado.md" in p for p in problemas)
    assert any("falta a linha do catálogo para ADR-002-b.md" in p for p in problemas)


def test_adr_duplicado_no_catalogo_e_apontado(tmp_path):
    readme, _, arquivos = _montar(tmp_path, _README_OK, _MKDOCS_OK)
    problemas = verificar_catalogo(
        readme + "| [ADR-001](ADR-001-a.md) | x | A | Aceito |\n", arquivos
    )
    assert problemas == ["docs/adr/README.md: ADR-001-a.md aparece 2 vezes no catálogo"]


def test_adr_fora_do_nav_e_apontado(tmp_path):
    mk = _MKDOCS_OK.replace('          - "002 · B": adr/ADR-002-b.md\n', "")
    _, nav, arquivos = _montar(tmp_path, _README_OK, mk)
    assert verificar_nav(nav, arquivos) == [
        "mkdocs.yml: falta ADR-002-b.md no nav, na aba Decisões"
    ]


def test_adr_em_outra_aba_e_apontado(tmp_path):
    mk = _MKDOCS_OK.replace('          - "002 · B": adr/ADR-002-b.md\n', "").replace(
        "      - historico.md\n", "      - historico.md\n      - B: adr/ADR-002-b.md\n"
    )
    _, nav, arquivos = _montar(tmp_path, _README_OK, mk)
    assert verificar_nav(nav, arquivos) == [
        "mkdocs.yml: ADR-002-b.md está fora da aba Decisões"
    ]


def test_nav_apontando_para_adr_inexistente_e_apontado(tmp_path):
    mk = _MKDOCS_OK.replace("ADR-002-b.md", "ADR-002-c.md")
    _, nav, arquivos = _montar(tmp_path, _README_OK, mk)
    problemas = verificar_nav(nav, arquivos)
    assert any("não existe: ADR-002-c.md" in p for p in problemas)
    assert any("falta ADR-002-b.md no nav" in p for p in problemas)


# --- guardas sobre os arquivos reais ---


def test_todo_adr_esta_no_catalogo():
    readme = (PASTA_ADR / "README.md").read_text(encoding="utf-8")
    problemas = verificar_catalogo(readme, _arquivos_adr(PASTA_ADR))
    assert not problemas, "Catálogo de ADRs fora de dia:\n" + "\n".join(problemas)


def test_todo_adr_esta_no_nav_da_aba_decisoes():
    problemas = verificar_nav(carregar_nav(), _arquivos_adr(PASTA_ADR))
    assert not problemas, "Nav de ADRs fora de dia:\n" + "\n".join(problemas)
