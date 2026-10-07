"""Cascata Disciplina → Assunto → Subassunto do painel (5H.3): rótulo
"Disciplina", assunto desabilitado sem disciplina, opções restritas aos pais
marcados, seleção coerente no servidor (órfão sai, link direto ganha os pais),
refino por ramo na consulta do site e filtro avançado como padrão."""

import json
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.test_stats_writer import _postgres_disponivel

com_banco = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponivel"
)

HX = {"HX-Request": "true"}


# --- regras puras (árvore falsa) ------------------------------------------------


@pytest.fixture
def arvore_falsa(monkeypatch):
    """M1 → A1 → S1, S1b; M1 → A1b; M2 → A2 → S2."""
    from app.servicos import questoes_servico as qs

    nos = {
        "M1": qs.NoInfo("Disc 1", "materia", "Disc 1", None),
        "A1": qs.NoInfo("Ass 1", "assunto", "Disc 1 › Ass 1", "M1"),
        "A1b": qs.NoInfo("Ass 1b", "assunto", "Disc 1 › Ass 1b", "M1"),
        "S1": qs.NoInfo("Sub 1", "subassunto", "…", "A1"),
        "S1b": qs.NoInfo("Sub 1b", "subassunto", "…", "A1"),
        "M2": qs.NoInfo("Disc 2", "materia", "Disc 2", None),
        "A2": qs.NoInfo("Ass 2", "assunto", "Disc 2 › Ass 2", "M2"),
        "S2": qs.NoInfo("Sub 2", "subassunto", "…", "A2"),
    }
    monkeypatch.setattr(qs, "_mapa_nos", lambda: nos)
    return qs


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (None, None),
        ([], []),
        (["M1"], ["M1"]),
        # Link direto (card, estatística): os pais entram.
        (["S1"], ["M1", "A1", "S1"]),
        (["A2"], ["M2", "A2"]),
        (["A1", "A2"], ["M1", "M2", "A1", "A2"]),
        # Assunto de outra disciplina, com disciplina marcada: órfão, sai.
        (["M1", "A2"], ["M1"]),
        (["M1", "S2"], ["M1"]),
        # Subassunto de assunto não marcado, com assunto marcado: sai.
        (["M1", "A1b", "S1"], ["M1", "A1b"]),
        # Disciplina marcada sem assunto: o assunto do subassunto entra.
        (["M1", "S1"], ["M1", "A1", "S1"]),
        # Assunto órfão sai antes de julgar o subassunto (que fica, com o pai).
        (["M1", "A2", "S1"], ["M1", "A1", "S1"]),
        # Id fora da árvore fica como veio, no fim; repetido conta uma vez.
        (["X9", "M1", "M1"], ["M1", "X9"]),
    ],
)
def test_coerir_nos(arvore_falsa, entrada, esperado):
    assert arvore_falsa.coerir_nos(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (["M1"], ["M1"]),
        (["M1", "A1"], ["A1"]),
        (["M1", "A1", "S1"], ["S1"]),
        # Disciplina sem filho marcado vale inteira, ao lado do ramo refinado.
        (["M1", "M2", "A1"], ["M2", "A1"]),
        (["M1", "A1", "A1b", "S1"], ["A1b", "S1"]),
    ],
)
def test_refinar_por_ramo(arvore_falsa, entrada, esperado):
    assert arvore_falsa.refinar_por_ramo(entrada) == esperado


# --- página e recontagem (banco real) -------------------------------------------


def _json(texto: str, id_: str):
    m = re.search(rf'<script[^>]*id="{id_}"[^>]*>(.*?)</script>', texto, re.DOTALL)
    assert m, id_
    return json.loads(m.group(1))


def _total_api(cliente, **params):
    r = cliente.get("/api/v1/questoes", params={**params, "tamanho_pagina": 1})
    assert r.status_code == 200, r.text
    return r.json()["total"]


def _total_html(texto: str) -> int:
    m = re.search(r">([\d.]+)</strong> questões encontradas", texto)
    assert m, "total ausente no HTML"
    return int(m.group(1).replace(".", ""))


def _botao(texto: str, chave: str) -> str:
    m = re.search(
        rf'<button[^>]*id="botao-{chave}"[^>]*>.*?</button>', texto, re.DOTALL
    )
    assert m, chave
    return m.group(0)


@pytest.fixture
def arvore(cliente):
    """Nós reais: disciplina com 2+ assuntos com questão, e um assunto com
    subassunto, mais uma 2ª disciplina."""
    from app.servicos import questoes_servico

    nos = questoes_servico.info_nos()
    facetas = cliente.get("/api/v1/facetas").json()
    sub = next(s["valor"] for s in facetas["subassuntos"] if s["total"])
    assunto = nos[sub].pai
    disciplina = nos[assunto].pai
    outra = next(
        m["valor"]
        for m in facetas["materias"]
        if m["total"] and m["valor"] != disciplina
    )
    assunto_outra = next(
        a["valor"]
        for a in facetas["assuntos"]
        if a["total"] and nos[a["valor"]].pai == outra
    )
    return {
        "nos": nos,
        "facetas": facetas,
        "disciplina": disciplina,
        "assunto": assunto,
        "sub": sub,
        "outra": outra,
        "assunto_outra": assunto_outra,
    }


@com_banco
def test_rotulo_disciplina_no_painel_e_no_site(cliente, arvore):
    r = cliente.get("/questoes")
    botao = _botao(r.text, "materia")
    assert ">Disciplina</span>" in botao
    assert "Matéria" not in botao
    # Nenhum texto "matéria" sobra nas páginas HTML (o contrato da API fica).
    paginas = [
        "/",
        "/questoes",
        f"/questoes?no_id={arvore['sub']}",
        "/estatisticas",
        "/estatisticas/edital",
        "/estatisticas/edital-vs-prova?concurso=PF_25_ADM&cargo_numero=1",
        f"/materias/{arvore['disciplina']}",
        "/simulado",
    ]
    for url in paginas:
        r = cliente.get(url)
        assert r.status_code == 200, url
        # Fora o conteúdo das provas (enunciado, texto-base, nomes de nó em
        # JSON), que pode citar "matéria" por si.
        texto = re.sub(r"<(script|article)\b.*?</\1>", "", r.text, flags=re.DOTALL)
        assert "atéria" not in texto and "ATÉRIA" not in texto, url
    resultado = cliente.post(
        "/simulado/corrigir", data={"concurso": "PF_25_ADM", "cargo_numero": "1"}
    )
    assert "Por disciplina" in resultado.text
    assert "Por matéria" not in resultado.text
    assert "Disciplinas" in cliente.get("/").text  # menu
    # Chip do servidor (<noscript>) com o nível e só o nome do nó.
    r = cliente.get("/questoes", params={"no_id": arvore["sub"]})
    rotulos = re.findall(r'aria-label="Remover filtro ([^"]+)"', r.text)
    nos = arvore["nos"]
    assert rotulos == [
        f"Disciplina: {nos[arvore['disciplina']].nome}",
        f"Assunto: {nos[arvore['assunto']].nome}",
        f"Subassunto: {nos[arvore['sub']].nome}",
    ]
    assert not any("›" in t for t in rotulos)


@com_banco
def test_assunto_desabilitado_sem_disciplina(cliente, arvore):
    sem = cliente.get("/questoes").text
    for chave, dica in (
        ("assunto", "Requer disciplina"),
        ("subassunto", "Requer assunto"),
    ):
        botao = _botao(sem, chave)
        assert re.search(r"\sdisabled\s", botao), chave
        assert ':disabled="!habilitado"' in botao
        assert dica in botao
    assert not re.search(r"\sdisabled\s", _botao(sem, "materia"))
    # A dica curta cabe no botão; a frase inteira fica no title.
    assert 'title="Escolha uma disciplina para liberar os assuntos dela"' in sem
    # Sem disciplina marcada não há opção de assunto nem de subassunto.
    dados = _json(sem, "dados-facetas")
    assert dados["assunto"] == [] and dados["subassunto"] == []

    com = cliente.get("/questoes", params={"no_id": arvore["disciplina"]}).text
    assert not re.search(r"\sdisabled\s", _botao(com, "assunto"))
    assert re.search(r"\sdisabled\s", _botao(com, "subassunto"))


@com_banco
def test_opcoes_restritas_aos_pais_marcados(cliente, arvore):
    nos = arvore["nos"]

    def facetas(params):
        r = cliente.get("/questoes/facetas", params=params, headers=HX)
        assert r.status_code == 200
        return _json(r.text, "dados-facetas")

    d = facetas({"no_id": arvore["disciplina"]})
    assert d["assunto"], "a disciplina tem assuntos"
    assert {a["pai"] for a in d["assunto"]} == {arvore["disciplina"]}
    # Todos os assuntos com questão da disciplina, nenhum de fora.
    esperados = {
        a["valor"]
        for a in arvore["facetas"]["assuntos"]
        if a["total"] and nos[a["valor"]].pai == arvore["disciplina"]
    }
    assert {a["valor"] for a in d["assunto"] if a["total"]} == esperados
    assert d["subassunto"] == []
    # Só o nome do próprio nó (sem caminho nem nome do pai).
    for a in d["assunto"]:
        assert set(a) == {"valor", "rotulo", "total", "pai"}
        assert a["rotulo"] == nos[a["valor"]].nome
    assert len(d["materia"]) == len(arvore["facetas"]["materias"])

    d = facetas({"no_id": [arvore["disciplina"], arvore["assunto"]]})
    assert d["subassunto"]
    assert {s["pai"] for s in d["subassunto"]} == {arvore["assunto"]}

    # Duas disciplinas: assuntos das duas (o painel agrupa pelo pai).
    d = facetas({"no_id": [arvore["disciplina"], arvore["outra"]]})
    assert {a["pai"] for a in d["assunto"]} == {arvore["disciplina"], arvore["outra"]}


@com_banco
def test_assunto_orfao_sai_no_servidor(cliente, arvore):
    params = {"no_id": [arvore["disciplina"], arvore["assunto_outra"]]}
    for headers in ({}, HX):
        r = cliente.get("/questoes", params=params, headers=headers)
        assert _total_html(r.text) == _total_api(cliente, no_id=arvore["disciplina"])
    pagina = cliente.get("/questoes", params=params).text
    assert _json(pagina, "dados-selecao")["no_id"] == [arvore["disciplina"]]
    # A recontagem também ignora o órfão: as opções seguem só da disciplina.
    r = cliente.get("/questoes/facetas", params=params, headers=HX)
    assert {a["pai"] for a in _json(r.text, "dados-facetas")["assunto"]} == {
        arvore["disciplina"]
    }


@com_banco
def test_link_direto_ganha_os_pais(cliente, arvore):
    pagina = cliente.get("/questoes", params={"no_id": arvore["sub"]}).text
    assert _json(pagina, "dados-selecao")["no_id"] == [
        arvore["disciplina"],
        arvore["assunto"],
        arvore["sub"],
    ]
    # O resultado é o do subassunto, como antes (e como na API).
    assert _total_html(pagina) == _total_api(cliente, no_id=arvore["sub"])
    # Assunto e subassunto ficam habilitados e com as opções do ramo.
    assert not re.search(r"\sdisabled\s", _botao(pagina, "subassunto"))
    dados = _json(pagina, "dados-facetas")
    assert arvore["sub"] in {s["valor"] for s in dados["subassunto"]}


@com_banco
def test_refino_por_ramo_na_lista(cliente, arvore):
    d, a, outra = arvore["disciplina"], arvore["assunto"], arvore["outra"]
    so_disciplina = _total_api(cliente, no_id=d)
    so_assunto = _total_api(cliente, no_id=a)
    assert so_assunto < so_disciplina
    r = cliente.get("/questoes", params={"no_id": [d, a]}, headers=HX)
    assert _total_html(r.text) == so_assunto
    # A outra disciplina, sem assunto marcado, vale inteira.
    r = cliente.get("/questoes", params={"no_id": [d, outra, a]}, headers=HX)
    assert _total_html(r.text) == _total_api(cliente, no_id=[a, outra])
    # A API não muda (contrato da 5F.1): nós em OU, a disciplina inteira.
    assert _total_api(cliente, no_id=[d, a]) == so_disciplina
    # A faceta de banca (fora da árvore) conta o recorte refinado.
    r = cliente.get("/questoes/facetas", params={"no_id": [d, a]}, headers=HX)
    banca = _json(r.text, "dados-facetas")["banca"]
    assert sum(b["total"] for b in banca) == so_assunto


@com_banco
def test_chip_da_disciplina_tira_os_filhos(cliente, arvore):
    d, a, s = arvore["disciplina"], arvore["assunto"], arvore["sub"]
    pagina = cliente.get("/questoes", params={"no_id": [d, a, s], "orgao": "PF"}).text
    noscript = "".join(
        t.split("</noscript>")[0] for t in pagina.split("<noscript>")[1:]
    )
    links = {
        rotulo: href.replace("&amp;", "&")
        for href, rotulo in re.findall(
            r'href="([^"]+)" class="ml-1[^"]*" aria-label="Remover filtro ([^"]+)"',
            noscript,
        )
    }
    nos = arvore["nos"]

    def query(rotulo):
        return parse_qs(urlsplit(links[rotulo]).query)

    assert query(f"Disciplina: {nos[d].nome}") == {"orgao": ["PF"]}
    assert query(f"Assunto: {nos[a].nome}") == {"orgao": ["PF"], "no_id": [d]}
    assert query(f"Subassunto: {nos[s].nome}") == {"orgao": ["PF"], "no_id": [d, a]}


@com_banco
def test_filtro_avancado_e_o_padrao(cliente):
    r = cliente.get("/questoes").text
    # Sem JS (x-show não age) a linha avançada aparece: nada a esconde no HTML.
    avancados = re.search(r'<div id="filtros-avancados"[^>]*>', r).group(0)
    assert "x-cloak" not in avancados and "hidden" not in avancados
    assert 'style="display' not in avancados
    # Com JS, o store nasce avançado e só a preferência salva "0" o esconde.
    assert "avancado: true," in r
    assert 'localStorage.getItem(CHAVE_LS) !== "0"' in r
    for chave in ("ano", "concurso", "cargo", "nivel", "tipo_conhecimento"):
        assert f'id="botao-{chave}"' in r
