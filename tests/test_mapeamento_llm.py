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


# Contexto dos subitens ---------------------------------------------------------------


def _com_filhos(monkeypatch, filhos):
    monkeypatch.setattr(mapeamento_llm, "coletar_filhos", lambda _d: filhos)


def test_subitens_entram_no_prompt(cenario, monkeypatch):
    _com_filhos(
        monkeypatch,
        {
            "direito administrativo|invalidacao dos atos": [
                "Anulação",
                "Revogação",
                "Convalidação",
            ],
            "direito penal": ["Homicídio", "Lesão corporal"],
        },
    )
    _, falso, _ = _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {}))
    prompts = "\n".join(c["prompt"] for c in falso.chamadas)
    assert "contém: Anulação; Revogação; Convalidação" in prompts
    # Título de bloco (matéria): "principais tópicos" no lugar de "contém".
    bloco = mapeamento_llm.Pendente(
        "bloco", "materia", "Bloco", [], [], set(), "bloco", ["Homicídio", "Lesão"]
    )
    texto = mapeamento_llm.montar_prompt([bloco], "", {}, arvore.ArvoreMestre())
    assert "principais tópicos: Homicídio; Lesão" in texto
    # O caminho do edital (matéria › tópico) já vem em "dentro de".
    assert "dentro de: DIREITO ADMINISTRATIVO" in prompts


def test_formatar_subitens_limita_itens_e_caracteres():
    nomes = [f"Subitem {i}" for i in range(12)]
    texto = mapeamento_llm.formatar_subitens(nomes)
    assert texto.count(";") == 7 and texto.endswith("…")
    longo = mapeamento_llm.formatar_subitens(["x" * 200, "y" * 200])
    assert len(longo) <= mapeamento_llm.MAX_CARACTERES_SUBITENS and longo.endswith("…")
    assert mapeamento_llm.formatar_subitens([]) == ""


def test_contexto_dos_subitens_entra_no_hash_e_reavalia(cenario, monkeypatch):
    base = mapeamento_llm.hash_candidatos("k", {"A"})
    assert base == mapeamento_llm.hash_candidatos("k", {"A"}, "")
    assert base != mapeamento_llm.hash_candidatos("k", {"A"}, "Anulação")
    nenhum = lambda p, _n: _itens_por_nome(p, {})  # noqa: E731
    _com_filhos(monkeypatch, {})
    _, f1, _ = _rodar(cenario, monkeypatch, nenhum)
    assert f1.chamadas
    _, f2, _ = _rodar(cenario, monkeypatch, nenhum)
    assert f2.chamadas == []  # nada mudou: o "nenhum" fica em cache
    _com_filhos(monkeypatch, {"direito penal|homicidio": ["Doloso", "Culposo"]})
    _, f3, _ = _rodar(cenario, monkeypatch, nenhum)
    # Só o item cujo contexto mudou volta ao modelo.
    assert len(f3.chamadas) == 1
    assert "Homicídio" in f3.chamadas[0]["prompt"].split("ITENS:")[1]
    assert "Invalidação" not in f3.chamadas[0]["prompt"].split("ITENS:")[1]


def test_prompt_de_sistema_explica_contexto():
    assert "DESAMBIGUAR" in mapeamento_llm.PROMPT_SISTEMA
    assert '"nenhum"' in mapeamento_llm.PROMPT_SISTEMA


# Memória -----------------------------------------------------------------------------


def _mexer_arvore(cenario, fn):
    _, caminho = cenario
    arv = arvore.carregar(caminho)
    fn(arv)
    arvore.salvar(arv, caminho)


def test_memoria_resolve_item_repetido_entre_dois_editais(cenario, monkeypatch):
    # "Licitações" (edital 1) já está aprovado; o edital 2 traz a mesma expressão
    # com outra grafia sob a mesma matéria, e o pai é o mesmo nó aprovado.
    _, caminho = cenario
    nomes = canonico.NomesOrigem()
    oc = {("OUTRO_25", "superior")}
    nomes.materia = {
        "direito administrativo": {"nome": "DIREITO ADMINISTRATIVO", "ocorrencias": oc}
    }
    nomes.assunto = {
        ("direito administrativo", "licitacoes (lei 14.133)"): {
            "nome": "Licitações (Lei 14.133)",
            "ocorrencias": oc,
        }
    }
    nomes.subassunto = {}
    monkeypatch.setattr(mapeamento_llm.canonico, "coletar_nomes", lambda _d: nomes)
    conta, falso, arv = _rodar(
        cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {})
    )
    assert falso.chamadas == []
    assert conta.resolvidos_memoria == 1 and conta.propostos == 0
    m = arv.mapeamentos["direito administrativo|licitacoes (lei 14.133)"]
    assert [(x.no_id, x.origem, x.status) for x in m] == [
        ("A-LIC", "regra", "aprovado")
    ]


def test_memoria_nao_promove_proposta_nao_aprovada(cenario, monkeypatch):
    # Só existe proposta LLM (não aprovada) para "Invalidação dos atos".
    _mexer_arvore(
        cenario,
        lambda a: arvore.mapear(
            a, "direito administrativo|outro nome", ["S-ANUL"], "llm", "proposto"
        ),
    )
    escolhas = {"Invalidação dos atos": None, "Homicídio": None, "Algo inédito": None}
    conta, _, arv = _rodar(
        cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas)
    )
    assert conta.resolvidos_memoria == 0
    assert "direito administrativo|invalidacao dos atos" not in arv.mapeamentos
    m = arv.mapeamentos["direito administrativo|outro nome"]
    assert [(x.origem, x.status) for x in m] == [("llm", "proposto")]


def test_ciclo_de_aprendizagem_llm_aprovada_resolve_na_proxima(cenario, monkeypatch):
    escolhas = {
        "Invalidação dos atos": "Anulação e revogação",
        "Homicídio": None,
        "Algo inédito": None,
    }
    _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas))
    chave = "direito administrativo|invalidacao dos atos"
    # Enquanto é só proposta, nada é copiado.
    nomes = canonico.coletar_nomes(cenario[0])
    oc = {("OUTRO_25", "superior")}
    nomes.assunto = {
        ("direito administrativo", "invalidacao dos atos (nova lei)"): {
            "nome": "Invalidação dos atos (nova lei)",
            "ocorrencias": oc,
        }
    }
    nomes.subassunto = {}
    nomes.materia = {
        "direito administrativo": {"nome": "DIREITO ADMINISTRATIVO", "ocorrencias": oc}
    }
    monkeypatch.setattr(mapeamento_llm.canonico, "coletar_nomes", lambda _d: nomes)
    nenhum = lambda p, _n: _itens_por_nome(p, {})  # noqa: E731
    conta, _, _ = _rodar(cenario, monkeypatch, nenhum)
    assert conta.resolvidos_memoria == 0
    # O dono aprova a proposta; a próxima execução já resolve sem LLM.
    _mexer_arvore(cenario, lambda a: arvore.aprovar(a, chave, "S-ANUL"))
    conta, falso, arv = _rodar(cenario, monkeypatch, nenhum)
    assert falso.chamadas == [] and conta.resolvidos_memoria == 1
    m = arv.mapeamentos["direito administrativo|invalidacao dos atos (nova lei)"]
    assert [(x.no_id, x.origem, x.status) for x in m] == [
        ("S-ANUL", "regra", "aprovado")
    ]
    # A decisão original do dono continua como estava.
    assert [(x.origem, x.status) for x in arv.mapeamentos[chave]] == [
        ("llm", "aprovado")
    ]


def test_par_rejeitado_nao_e_reproposto_e_vai_no_prompt(cenario, monkeypatch):
    _mexer_arvore(
        cenario,
        lambda a: (
            arvore.mapear(
                a, "direito civil|invalidacao dos atos", ["S-ANUL"], "llm", "proposto"
            ),
            arvore.rejeitar(a, "direito civil|invalidacao dos atos", "S-ANUL"),
        ),
    )
    escolhas = {
        "Invalidação dos atos": "Anulação e revogação",
        "Homicídio": None,
        "Algo inédito": None,
    }
    conta, falso, arv = _rodar(
        cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, escolhas)
    )
    prompt = falso.chamadas[0]["prompt"]
    assert "PARES REJEITADOS" in prompt and "NÃO é [" in prompt
    assert conta.descartados_rejeitados == 1 and conta.propostos == 0
    assert "direito administrativo|invalidacao dos atos" not in arv.mapeamentos


def test_exemplos_aprovados_aparecem_no_prompt(cenario, monkeypatch):
    _mexer_arvore(
        cenario,
        lambda a: arvore.mapear(
            a, "direito administrativo|revogacao do ato", ["S-ANUL"], "humano"
        ),
    )
    _, falso, _ = _rodar(cenario, monkeypatch, lambda p, _n: _itens_por_nome(p, {}))
    prompt = "\n".join(c["prompt"] for c in falso.chamadas)
    assert "O DONO JÁ DECIDIU ASSIM" in prompt
    assert (
        "Direito Administrativo › Atos administrativos › Anulação e revogação" in prompt
    )


def test_dry_run_estima_sem_os_itens_da_memoria(cenario, monkeypatch):
    nomes = canonico.NomesOrigem()
    oc = {("OUTRO_25", "superior")}
    nomes.materia = {
        "direito administrativo": {"nome": "DIREITO ADMINISTRATIVO", "ocorrencias": oc}
    }
    nomes.assunto = {
        ("direito administrativo", "licitacoes (lei 14.133)"): {
            "nome": "Licitações (Lei 14.133)",
            "ocorrencias": oc,
        }
    }
    nomes.subassunto = {}
    monkeypatch.setattr(mapeamento_llm.canonico, "coletar_nomes", lambda _d: nomes)
    antes = cenario[1].read_text(encoding="utf-8")
    conta, falso, _ = _rodar(cenario, monkeypatch, lambda p, _n: [], dry_run=True)
    assert falso.chamadas == []
    assert conta.resolvidos_memoria == 1 and conta.itens_previstos == 0
    assert conta.chamadas_previstas == 0
    assert cenario[1].read_text(encoding="utf-8") == antes


def test_script_resumo_mostra_memoria_llm_e_sem_no(cenario, monkeypatch, capsys):
    revisao, caminho = cenario
    escolhas = {
        "Invalidação dos atos": "Anulação e revogação",
        "Homicídio": None,
        "Algo inédito": None,
    }
    monkeypatch.setattr(
        mapeamento_llm,
        "chamar_llm_json",
        LLMFalso(lambda p, _n: _itens_por_nome(p, escolhas)),
    )
    script.main([str(revisao), "--arvore", str(caminho)])
    saida = json.loads(capsys.readouterr().out)
    assert saida["resolvidos_por_memoria"] == 0
    assert saida["propostos_por_llm"] == 1
    assert saida["sem_no"] == 2
