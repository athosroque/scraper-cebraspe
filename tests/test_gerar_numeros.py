"""Testes de scripts/gerar_numeros.py: página pura, custo (rede mockada) e banco falso."""

from datetime import date

import pytest
import requests

from scripts import gerar_numeros as gn

GERADO_EM = date(2026, 10, 13)


def _banco() -> dict:
    return {
        "inventario": [(2020, 26), (2021, 60), (2025, 52)],
        "concursos": {"aprovado": 5, "pendente": 2},
        "cargos": 41,
        "cadernos": 87,
        "questoes": {
            "total": 3410,
            "certo_errado": 2800,
            "multipla_escolha": 610,
            "anuladas": 152,
            "utilizaveis": 3391,
            "discursivas": 39,
        },
        "arvore": {"materia": 74, "assunto": 1016, "subassunto": 2255},
        "itens_edital": 1812,
        "subitens_edital": 3936,
        "apontamentos": 2965,
    }


def _custo() -> dict:
    etapas = [
        {"nome": "Taxonomia do edital", "usd": 0.0198},
        {"nome": "Chave geral (fallback e etapas antigas)", "usd": 0.2907},
    ]
    return {"etapas": etapas, "total": 0.3105}


# ------------------------------------------------------------ página


def test_pagina_comeca_com_cabecalho_gerado():
    texto = gn.pagina_numeros(_banco(), None, GERADO_EM)
    primeira = texto.splitlines()[0]
    assert primeira.startswith("<!-- Gerado por scripts/gerar_numeros.py")
    assert "Não edite à mão" in primeira
    assert "# Números" in texto.splitlines()[2]


def test_pagina_traz_data_no_formato_brasileiro():
    texto = gn.pagina_numeros(_banco(), None, GERADO_EM)
    assert "Atualizado em 13/10/2026, a partir do banco do projeto." in texto


def test_pagina_formata_numeros_com_ponto_de_milhar():
    texto = gn.pagina_numeros(_banco(), None, GERADO_EM)
    assert "| Total de questões | 3.410 |" in texto
    assert "| Assuntos ativos | 1.016 |" in texto
    assert "| Subassuntos ativos | 2.255 |" in texto
    assert "| Apontamentos questão → nó da árvore | 2.965 |" in texto
    assert "| **Total** | **138** |" in texto


def test_pagina_sem_custo_diz_que_nao_foi_consultado():
    texto = gn.pagina_numeros(_banco(), None, GERADO_EM)
    assert "## Custo do LLM" in texto
    assert "não foi consultado nesta geração" in texto
    assert "US$" not in texto


def test_pagina_com_custo_mostra_tabela_e_total():
    texto = gn.pagina_numeros(_banco(), _custo(), GERADO_EM)
    assert "| Taxonomia do edital | US$ 0,0198 |" in texto
    assert "| Chave geral (fallback e etapas antigas) | US$ 0,2907 |" in texto
    assert "| **Total** | **US$ 0,3105** |" in texto
    assert "z-ai/glm-5.3-flash" in texto
    assert "não foi consultado" not in texto


def test_pagina_explica_siglas_para_leitor_de_fora():
    texto = gn.pagina_numeros(_banco(), _custo(), GERADO_EM)
    assert "Certo ou errado (C/E)" in texto
    assert "Uma questão anulada foi cancelada pela banca" in texto
    assert "Utilizável é a questão" in texto
    assert "Um apontamento liga uma questão a um nó da árvore" in texto


def test_pagina_tem_as_quatro_secoes_de_numeros():
    texto = gn.pagina_numeros(_banco(), None, GERADO_EM)
    for secao in (
        "## Cobertura",
        "## Questões",
        "## Árvore de assuntos",
        "## Custo do LLM",
    ):
        assert secao in texto


def test_usd_usa_duas_a_quatro_casas_e_virgula():
    assert gn._usd(0.31) == "US$ 0,31"
    assert gn._usd(0.0042) == "US$ 0,0042"
    assert gn._usd(1234.5) == "US$ 1.234,50"


# ------------------------------------------------------------ custo


class _Resposta:
    def __init__(self, status: int, usage: float | None = None):
        self.status_code = status
        self._usage = usage

    def json(self):
        return {"data": {"usage": self._usage}}


VARIAVEIS_CUSTO = (
    "OPENROUTER_KEY_TAXONOMIA_EDITAL",
    "OPENROUTER_KEY_SINONIMOS",
    "OPENROUTER_KEY_CURADORIA_ARVORE",
    "OPENROUTER_KEY_CLASSIFICACAO_QUESTOES",
    "OPENROUTER_KEY_TELEGRAM",
    "OPENROUTER_API_KEY",
)


@pytest.fixture
def ambiente_custo(monkeypatch):
    """Zera as chaves reais: o `.env` não sobrescreve variável já definida."""
    for variavel in VARIAVEIS_CUSTO:
        monkeypatch.setenv(variavel, "")
    return monkeypatch


def test_coletar_custo_soma_as_etapas(ambiente_custo, monkeypatch):
    ambiente_custo.setenv("OPENROUTER_KEY_TAXONOMIA_EDITAL", "chave-a")
    ambiente_custo.setenv("OPENROUTER_KEY_TELEGRAM", "chave-b")
    usos = {"chave-a": 0.25, "chave-b": 0.5}
    chamadas = []

    def falso_get(url, headers, timeout):
        chamadas.append((url, headers["Authorization"], timeout))
        return _Resposta(200, usos[headers["Authorization"].removeprefix("Bearer ")])

    monkeypatch.setattr(gn.requests, "get", falso_get)
    custo = gn.coletar_custo()

    assert custo["etapas"] == [
        {"nome": "Taxonomia do edital", "usd": 0.25},
        {"nome": "Bot do Telegram", "usd": 0.5},
    ]
    assert custo["total"] == pytest.approx(0.75)
    assert all(url == gn.URL_CHAVE_OPENROUTER for url, _, _ in chamadas)
    assert all(timeout == 15 for _, _, timeout in chamadas)


def test_coletar_custo_conta_chave_repetida_uma_vez(ambiente_custo, monkeypatch):
    ambiente_custo.setenv("OPENROUTER_KEY_SINONIMOS", "mesma")
    ambiente_custo.setenv("OPENROUTER_API_KEY", "mesma")
    chamadas = []

    def falso_get(url, headers, timeout):
        chamadas.append(headers)
        return _Resposta(200, 0.1)

    monkeypatch.setattr(gn.requests, "get", falso_get)
    custo = gn.coletar_custo()

    assert len(chamadas) == 1
    assert [e["nome"] for e in custo["etapas"]] == ["Sinônimos"]
    assert custo["total"] == pytest.approx(0.1)


def test_coletar_custo_ignora_variavel_vazia(ambiente_custo, monkeypatch):
    ambiente_custo.setenv("OPENROUTER_KEY_SINONIMOS", "   ")
    chamadas = []
    monkeypatch.setattr(
        gn.requests, "get", lambda *a, **k: chamadas.append(a) or _Resposta(200, 0.0)
    )
    custo = gn.coletar_custo()
    assert chamadas == []
    assert custo == {"etapas": [], "total": 0}


def test_coletar_custo_erro_http_levanta_sem_vazar_chave(ambiente_custo, monkeypatch):
    segredo = "sk-or-segredo-que-nao-pode-vazar"
    ambiente_custo.setenv("OPENROUTER_KEY_TELEGRAM", segredo)
    monkeypatch.setattr(gn.requests, "get", lambda *a, **k: _Resposta(401))

    with pytest.raises(gn.ErroCusto) as info:
        gn.coletar_custo()

    mensagem = str(info.value)
    assert "Bot do Telegram" in mensagem
    assert "HTTP 401" in mensagem
    assert segredo not in mensagem


def test_coletar_custo_erro_de_rede_levanta_sem_vazar_chave(
    ambiente_custo, monkeypatch
):
    segredo = "sk-or-outro-segredo"
    ambiente_custo.setenv("OPENROUTER_API_KEY", segredo)

    def falha(*args, **kwargs):
        raise requests.ConnectionError(f"falhou com {segredo}")

    monkeypatch.setattr(gn.requests, "get", falha)

    with pytest.raises(gn.ErroCusto) as info:
        gn.coletar_custo()

    assert "ConnectionError" in str(info.value)
    assert segredo not in str(info.value)


def test_main_sai_com_1_quando_custo_falha(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(gn, "conectar", lambda: _ConexaoFalsa(_banco()))

    def falha():
        raise gn.ErroCusto("Taxonomia do edital: o OpenRouter respondeu HTTP 500")

    monkeypatch.setattr(gn, "coletar_custo", falha)
    saida = tmp_path / "numeros.md"

    assert gn.main(["--saida", str(saida)]) == 1
    assert not saida.exists()
    assert "--sem-custo" in capsys.readouterr().err


def test_main_sem_custo_nao_consulta_openrouter(monkeypatch, tmp_path):
    monkeypatch.setattr(gn, "conectar", lambda: _ConexaoFalsa(_banco()))

    def nao_deve_chamar():
        raise AssertionError("coletar_custo não deveria rodar com --sem-custo")

    monkeypatch.setattr(gn, "coletar_custo", nao_deve_chamar)
    saida = tmp_path / "numeros.md"

    assert gn.main(["--sem-custo", "--saida", str(saida)]) == 0
    assert "não foi consultado" in saida.read_text(encoding="utf-8")


# ------------------------------------------------------------ banco falso


class _CursorFalso:
    """Responde cada SQL pelo trecho que ele contém; registra o que foi executado."""

    def __init__(self, respostas: dict, executados: list):
        self._respostas = respostas
        self._executados = executados
        self._resultado: list = []

    def execute(self, sql):
        self._executados.append(sql)
        for trecho, linhas in self._respostas.items():
            if trecho in sql:
                self._resultado = linhas
                return
        raise AssertionError(f"consulta inesperada: {sql}")

    def fetchone(self):
        return self._resultado[0]

    def fetchall(self):
        return self._resultado

    def close(self):
        pass


class _ConexaoFalsa:
    def __init__(self, banco: dict):
        self.somente_leitura = False
        self.executados: list[str] = []
        self.fechada = False
        self._respostas = {
            "inv_concurso": [(ano, total) for ano, total in banco["inventario"]],
            "from public.concursos": list(banco["concursos"].items()),
            "cargos_editais": [(banco["cargos"],)],
            "from public.provas": [(banco["cadernos"],)],
            "group by tipo": [
                ("certo_errado", banco["questoes"]["certo_errado"]),
                ("multipla_escolha", banco["questoes"]["multipla_escolha"]),
            ],
            "from public.questoes where anulada": [(banco["questoes"]["anuladas"],)],
            "vw_questoes_utilizaveis": [(banco["questoes"]["utilizaveis"],)],
            "from public.discursivas": [(banco["questoes"]["discursivas"],)],
            "from public.questoes": [(banco["questoes"]["total"],)],
            "no_arvore": list(banco["arvore"].items()),
            "taxonomia_subitens": [(banco["subitens_edital"],)],
            "taxonomia_itens": [(banco["itens_edital"],)],
            "questao_no": [(banco["apontamentos"],)],
        }

    def set_session(self, readonly=False):
        self.somente_leitura = readonly

    def cursor(self):
        return _CursorFalso(self._respostas, self.executados)

    def rollback(self):
        pass

    def close(self):
        self.fechada = True


def test_coletar_banco_le_so_o_schema_public_e_monta_os_numeros():
    conexao = _ConexaoFalsa(_banco())
    banco = gn.coletar_banco(conexao)

    assert conexao.somente_leitura is True
    assert banco["inventario"] == [(2020, 26), (2021, 60), (2025, 52)]
    assert banco["concursos"] == {"aprovado": 5, "pendente": 2}
    assert banco["questoes"]["total"] == 3410
    assert banco["questoes"]["certo_errado"] == 2800
    assert banco["questoes"]["multipla_escolha"] == 610
    assert banco["questoes"]["utilizaveis"] == 3391
    assert banco["arvore"] == {"materia": 74, "assunto": 1016, "subassunto": 2255}
    assert banco["apontamentos"] == 2965
    assert all("public." in sql for sql in conexao.executados)
    assert not any(
        palavra in sql.lower()
        for sql in conexao.executados
        for palavra in ("insert", "update", "delete", "drop", "alter")
    )
