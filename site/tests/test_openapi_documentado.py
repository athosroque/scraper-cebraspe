"""Guarda da documentação da API (5F.6): o Swagger é a documentação.

Roda sobre `app.openapi()` (sem banco). Toda operação tem summary e
description; 401/403/404 aparecem conforme a dependência e o parâmetro de
caminho; todo schema próprio e todo campo dele têm descrição.
"""

import pytest

from app.main import app

METODOS = {"get", "post", "put", "patch", "delete"}
# Schemas gerados pelo FastAPI, fora do nosso controle.
SCHEMAS_EXTERNOS = {"HTTPValidationError", "ValidationError"}


@pytest.fixture(scope="module")
def spec():
    return app.openapi()


def _operacoes(spec):
    for caminho, item in spec["paths"].items():
        for metodo, op in item.items():
            if metodo in METODOS:
                yield caminho, metodo, op


def test_toda_operacao_tem_summary_e_description(spec):
    faltando = [
        f"{m.upper()} {c}"
        for c, m, op in _operacoes(spec)
        if not op.get("summary") or not op.get("description")
    ]
    assert not faltando, faltando


def test_tags_descritas_e_usadas(spec):
    descritas = {t["name"]: t.get("description") for t in spec["tags"]}
    assert all(descritas.values()), descritas
    for c, m, op in _operacoes(spec):
        assert op.get("tags"), f"{m.upper()} {c} sem tag"
        assert set(op["tags"]) <= set(descritas), f"{m.upper()} {c}: {op['tags']}"


def test_esquemas_de_seguranca(spec):
    esquemas = spec["components"]["securitySchemes"]
    assert esquemas["sessao"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "sessao",
        "description": esquemas["sessao"]["description"],
    }
    assert esquemas["csrf"]["in"] == "header"
    assert esquemas["csrf"]["name"] == "X-CSRFToken"


def test_respostas_de_erro_declaradas(spec):
    problemas = []
    for c, m, op in _operacoes(spec):
        nomes = {n for s in op.get("security", []) for n in s}
        respostas = op["responses"]
        if "sessao" in nomes and "401" not in respostas:
            problemas.append(f"{m.upper()} {c}: falta 401")
        if "csrf" in nomes and "403" not in respostas:
            problemas.append(f"{m.upper()} {c}: falta 403")
        tem_caminho = any(p["in"] == "path" for p in op.get("parameters", []))
        if tem_caminho and "404" not in respostas:
            problemas.append(f"{m.upper()} {c}: falta 404")
        if m in {"post", "delete"} and "csrf" not in nomes:
            problemas.append(f"{m.upper()} {c}: POST/DELETE sem CSRF")
    assert not problemas, problemas


def test_autenticacao_no_contrato_e_html_fora(spec):
    assert {"/entrar", "/auth/google", "/sair"} <= set(spec["paths"])
    for caminho in ("/entrar", "/auth/google", "/sair"):
        for op in spec["paths"][caminho].values():
            assert op["tags"] == ["Autenticação"]
            assert "303" in op["responses"]
    for caminho in ("/", "/sobre", "/conta", "/simulado", "/estatisticas"):
        assert caminho not in spec["paths"]


def test_todo_schema_e_campo_com_descricao(spec):
    faltando = []
    for nome, schema in spec["components"]["schemas"].items():
        if nome in SCHEMAS_EXTERNOS or "properties" not in schema:
            continue
        if not schema.get("description"):
            faltando.append(nome)
        for campo, prop in schema["properties"].items():
            if not prop.get("description"):
                faltando.append(f"{nome}.{campo}")
    assert not faltando, faltando


def test_parametros_com_descricao(spec):
    faltando = [
        f"{m.upper()} {c} {p['name']}"
        for c, m, op in _operacoes(spec)
        for p in op.get("parameters", [])
        if not p.get("description")
    ]
    assert not faltando, faltando
