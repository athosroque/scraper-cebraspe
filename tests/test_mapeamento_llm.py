"""Testes de src/mapeamento_llm.py e scripts/mapear_itens_novos.py, com LLM falso."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import mapear_itens_novos as script
from src import arvore, canonico, llm_openrouter, mapeamento_llm
from src.llm_openrouter import ResultadoChamada


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(mapeamento_llm.time, "sleep", lambda *_: None)


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    """Árvore com 1 disciplina, 2 assuntos e 1 subassunto; edital com itens novos."""
    arv = arvore.ArvoreMestre()
    arvore.criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-DA")
    arvore.criar_no(arv, "materia", "Direito Penal", None, id_override="M-DP")
    arvore.criar_no(arv, "assunto", "Atos administrativos", "M-DA", id_override="A-ATO")
    arvore.criar_no(arv, "assunto", "Licitações", "M-DA", id_override="A-LIC")
    arvore.criar_no(
        arv, "assunto", "Crimes contra a vida", "M-DP", id_override="A-VIDA"
    )
    arvore.criar_no(
        arv, "subassunto", "Anulação e revogação", "A-ATO", id_override="S-ANUL"
    )
    # A matéria do edital já está mapeada pela regra: é o pai resolvido dos tópicos.
    arvore.mapear(arv, "direito administrativo", ["M-DA"], "regra", "aprovado")
    arvore.mapear(arv, "direito penal", ["M-DP"], "regra", "aprovado")
    # Um item já aprovado: nunca é reavaliado.
    arvore.mapear(
        arv, "direito administrativo|licitacoes", ["A-LIC"], "semente", "aprovado"
    )
    caminho = tmp_path / "arvore.json"
    arvore.salvar(arv, caminho)

    ocorrencia = {("TESTE_25", "superior")}
    nomes = canonico.NomesOrigem()
    nomes.materia = {
        "direito administrativo": {
            "nome": "DIREITO ADMINISTRATIVO",
            "ocorrencias": set(ocorrencia),
        },
        "direito penal": {"nome": "DIREITO PENAL", "ocorrencias": set(ocorrencia)},
    }
    nomes.assunto = {
        ("direito administrativo", "licitacoes"): {
            "nome": "Licitações",
            "ocorrencias": set(ocorrencia),
        },
        ("direito administrativo", "invalidacao dos atos"): {
            "nome": "Invalidação dos atos",
            "ocorrencias": set(ocorrencia),
        },
        ("direito penal", "homicidio"): {
            "nome": "Homicídio",
            "ocorrencias": set(ocorrencia),
        },
        ("direito penal", "algo inedito"): {
            "nome": "Algo inédito",
            "ocorrencias": {("OUTRO_25", "superior")},
        },
    }
    nomes.subassunto = {}
    monkeypatch.setattr(
        mapeamento_llm.canonico, "coletar_nomes", lambda _dir: nomes, raising=True
    )
    return tmp_path, caminho


class LLMFalso:
    """Substitui `chamar_llm_json`: roda a pós-validação como o núcleo real."""

    def __init__(self, respostas):
        # `respostas`: callable(prompt, tentativa) -> lista de dicts de itens.
        self.respostas = respostas
        self.chamadas: list[dict] = []

    def __call__(self, prompt_sistema, prompt_usuario, schema, **kw):
        self.chamadas.append({"prompt": prompt_usuario, **kw})
        itens = self.respostas(prompt_usuario, len(self.chamadas))
        objeto = schema.model_validate({"itens": itens})
        pos = kw["pos_validacao"](objeto, "")
        if pos.motivo:
            return ResultadoChamada(None, pos.motivo, {"cost": 0.001})
        return ResultadoChamada(pos.objeto, None, {"cost": 0.001})


def _local(prompt: str, nome: str) -> str:
    return re.search(rf"\[(N\d+)\] {re.escape(nome)} \(", prompt).group(1)


def _itens_por_nome(prompt: str, escolhas: dict[str, str | None]) -> list[dict]:
    """Para cada item `"<nome>"` do prompt, escolhe o nó pelo nome (ou nenhum)."""
    saida = []
    for numero, nome in re.findall(r'^(\d+)\. \[[^\]]+\] "([^"]+)"', prompt, re.M):
        alvo = escolhas.get(nome)
        saida.append(
            {
                "numero": int(numero),
                "no": _local(prompt, alvo) if alvo else None,
                "nenhum": alvo is None,
                "confianca": "alta",
                "justificativa": "teste",
            }
        )
    return saida


def _rodar(cenario, monkeypatch, respostas, **kw):
    revisao, caminho = cenario
    falso = LLMFalso(respostas)
    monkeypatch.setattr(mapeamento_llm, "chamar_llm_json", falso)
    conta = mapeamento_llm.mapear_itens_novos(revisao, caminho, **kw)
    return conta, falso, arvore.carregar(caminho)


def test_levantamento_ignora_itens_ja_mapeados(cenario):
    _, caminho = cenario
    arv = arvore.carregar(caminho)
    chaves = {p.chave for p in mapeamento_llm.levantar_pendentes(cenario[0], arv)}
    assert chaves == {
        "direito administrativo|invalidacao dos atos",
        "direito penal|homicidio",
        "direito penal|algo inedito",
    }
    so_outro = mapeamento_llm.levantar_pendentes(cenario[0], arv, "OUTRO_25")
    assert [p.chave for p in so_outro] == ["direito penal|algo inedito"]


def test_proposta_valida_vira_proposto_llm(cenario, monkeypatch):
    escolhas = {
        "Invalidação dos atos": "Anulação e revogação",
        "Homicídio": "Crimes contra a vida",
        "Algo inédito": None,
    }
    conta, _, arv = _rodar(
        cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas)
    )
    m = arv.mapeamentos["direito administrativo|invalidacao dos atos"]
    assert [(x.no_id, x.origem, x.status) for x in m] == [("S-ANUL", "llm", "proposto")]
    m = arv.mapeamentos["direito penal|homicidio"]
    assert [(x.no_id, x.origem, x.status) for x in m] == [("A-VIDA", "llm", "proposto")]
    assert conta.propostos == 2 and conta.nenhum == 1


def test_nunca_aprova_nem_cria_no(cenario, monkeypatch):
    nos_antes = set(arvore.carregar(cenario[1]).nos)
    _, _, arv = _rodar(
        cenario,
        monkeypatch,
        lambda p, _n: _itens_por_nome(
            p,
            {
                "Invalidação dos atos": "Atos administrativos",
                "Homicídio": "Crimes contra a vida",
                "Algo inédito": None,
            },
        ),
    )
    assert set(arv.nos) == nos_antes
    novos = [
        m
        for chave, lista in arv.mapeamentos.items()
        for m in lista
        if m.origem == "llm"
    ]
    assert novos and all(m.status == "proposto" for m in novos)


def test_nenhum_nao_grava_e_continua_pendente(cenario, monkeypatch):
    conta, _, arv = _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {}))
    assert conta.propostos == 0 and conta.nenhum == 3
    assert "direito penal|algo inedito" not in arv.mapeamentos
    pendentes = mapeamento_llm.levantar_pendentes(cenario[0], arv)
    assert len(pendentes) == 3


def test_id_inventado_e_rejeitado_e_a_segunda_tentativa_corrige(cenario, monkeypatch):
    def respostas(prompt, n):
        itens = _itens_por_nome(prompt, {"Homicídio": "Crimes contra a vida"})
        if n == 1:
            itens[0]["no"] = "N999"
            itens[0]["nenhum"] = False
        return itens

    revisao, caminho = cenario
    conta, falso, arv = _rodar(cenario, monkeypatch, respostas, concurso="TESTE_25")
    assert conta.falhas[mapeamento_llm.STATUS_FALHA_ID_DESCONHECIDO] >= 1
    assert "ATENÇÃO" in falso.chamadas[1]["prompt"]
    assert arv.mapeamentos["direito penal|homicidio"][0].no_id == "A-VIDA"


def test_id_inventado_sempre_nao_grava_nada(cenario, monkeypatch):
    def respostas(prompt, _n):
        itens = _itens_por_nome(prompt, {})
        for it in itens:
            it["no"], it["nenhum"] = "N999", False
        return itens

    conta, _, arv = _rodar(cenario, monkeypatch, respostas)
    assert conta.propostos == 0 and conta.lotes_falhos >= 1
    assert not any(
        m.origem == "llm" for lista in arv.mapeamentos.values() for m in lista
    )


def test_no_do_nivel_errado_nao_e_oferecido(cenario, monkeypatch):
    """Tópico recebe assunto ou subassunto; disciplina nem aparece com ID."""
    _, falso, _ = _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {}))
    for chamada in falso.chamadas:
        assert (
            re.search(r"\[N\d+\] Direito (Administrativo|Penal) \(", chamada["prompt"])
            is None
        )
        assert "só contexto" in chamada["prompt"]


def test_usa_reasoning_padrao_e_nome_do_trace(cenario, monkeypatch):
    _, falso, _ = _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {}))
    for chamada in falso.chamadas:
        assert chamada["reasoning"] is llm_openrouter.REASONING_PADRAO
        assert chamada["reasoning"] == {"reasoning": {"max_tokens": 3000}}
        assert chamada["nome_trace"] == "mapear_itens_novos"


def test_chave_com_fallback_para_a_da_curadoria(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY_MAPEAMENTO_ITENS", "")
    monkeypatch.setenv("OPENROUTER_KEY_CURADORIA_ARVORE", "chave-curadoria")
    chave = llm_openrouter.chave_openrouter(
        llm_openrouter.ETAPA_MAPEAMENTO_ITENS,
        llm_openrouter.ETAPA_CURADORIA_ARVORE[0],
    )
    assert chave == "chave-curadoria"


def test_idempotencia_proposto_e_nenhum_nao_voltam_ao_llm(cenario, monkeypatch):
    escolhas = {"Homicídio": "Crimes contra a vida"}
    _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas))
    conta, falso, arv = _rodar(
        cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas)
    )
    assert falso.chamadas == []
    assert conta.pulados_cache == 2  # os dois "nenhum"; o proposto já tem mapeamento
    # --reavaliar volta a perguntar só o que ficou sem nó.
    conta, falso, _ = _rodar(
        cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas), reavaliar=True
    )
    assert len(falso.chamadas) >= 1
    assert "Homicídio" not in falso.chamadas[0]["prompt"].split("ITENS:")[1]


def test_item_aprovado_pelo_dono_nao_e_reavaliado(cenario, monkeypatch):
    _, falso, arv = _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {}))
    assert all(
        "Licitações" not in c["prompt"].split("ITENS:")[1] for c in falso.chamadas
    )
    m = arv.mapeamentos["direito administrativo|licitacoes"]
    assert [(x.origem, x.status) for x in m] == [("semente", "aprovado")]


def test_dry_run_nao_chama_nem_grava(cenario, monkeypatch):
    antes = cenario[1].read_text(encoding="utf-8")
    conta, falso, _ = _rodar(cenario, monkeypatch, lambda p, _n: [], dry_run=True)
    assert falso.chamadas == []
    assert conta.pendentes == 3 and conta.chamadas_previstas >= 1
    assert cenario[1].read_text(encoding="utf-8") == antes
    assert not (cenario[1].parent / mapeamento_llm.CACHE_NOME).exists()


def test_script_dry_run_imprime_estimativa(cenario, capsys):
    revisao, caminho = cenario
    script.main([str(revisao), "--arvore", str(caminho), "--dry-run"])
    saida = json.loads(capsys.readouterr().out)
    assert saida["pendentes"] == 3
    assert saida["chamadas_previstas"] >= 1
    assert saida["tokens_entrada_estimados"] > 0


def test_pos_validacao_exige_no_xor_nenhum():
    validar = mapeamento_llm.pos_validacao_mapeamento({"N1": "A-1"}, [1])
    ruim = mapeamento_llm.RespostaMapeamento.model_validate(
        {"itens": [{"numero": 1, "no": "N1", "nenhum": True}]}
    )
    assert validar(ruim, "").motivo == mapeamento_llm.STATUS_FALHA_VALIDACAO_SCHEMA
    vazio = mapeamento_llm.RespostaMapeamento.model_validate({"itens": [{"numero": 1}]})
    assert validar(vazio, "").motivo == mapeamento_llm.STATUS_FALHA_VALIDACAO_SCHEMA
    faltando = mapeamento_llm.RespostaMapeamento.model_validate({"itens": []})
    assert validar(faltando, "").motivo == mapeamento_llm.STATUS_FALHA_ITENS_DIVERGENTES


def test_arvore_inexistente_nao_quebra(tmp_path):
    conta = mapeamento_llm.mapear_itens_novos(tmp_path, tmp_path / "nao.json")
    assert conta.pendentes == 0
    assert isinstance(Path(tmp_path), Path)
