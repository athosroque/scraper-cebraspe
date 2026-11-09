"""Mapeamento de item novo de edital por regra (Etapa 5B.1, ADR-030)."""

from pathlib import Path

import pytest

from src import arvore as arv_mod
from src import canonico
from src.arvore import (
    ArvoreMestre,
    carregar,
    criar_no,
    fundir_nos,
    mapear,
    rejeitar,
    salvar,
)


def _nome(nome):
    return {"nome": nome, "ocorrencias": {("XX_25", "superior")}}


@pytest.fixture
def arvore_path(tmp_path):
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-DA")
    criar_no(arv, "materia", "Direito Constitucional", None, id_override="M-DC")
    criar_no(arv, "assunto", "Atos administrativos", "M-DA", id_override="A-ATO")
    criar_no(arv, "assunto", "Poder Executivo", "M-DC", id_override="A-EXE")
    mapear(arv, "direito administrativo", ["M-DA"])
    mapear(arv, "nocoes de direito administrativo", ["M-DA"])
    mapear(arv, "direito constitucional", ["M-DC"])
    mapear(arv, "direito administrativo|atos administrativos", ["A-ATO"])
    mapear(arv, "direito constitucional|poder executivo", ["A-EXE"])
    path = tmp_path / "arvore.json"
    salvar(arv, path)
    return path


def _rodar(monkeypatch, tmp_path, arvore_path, **niveis):
    nomes = canonico.NomesOrigem(**niveis)
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens_por_regra(tmp_path, arvore_path)


def test_mapeia_dentro_do_mesmo_pai_efetivo(monkeypatch, tmp_path, arvore_path):
    # O pai "nocoes de direito administrativo" aponta para o mesmo nó (M-DA),
    # e "Ato administrativo" tem a mesma chave de regra de "Atos administrativos".
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        assunto={
            ("direito administrativo", "atos administrativos"): _nome(
                "Atos administrativos"
            ),
            ("nocoes de direito administrativo", "ato administrativo"): _nome(
                "Ato administrativo"
            ),
        },
    )
    assert novos == 1
    [m] = carregar(arvore_path).mapeamentos[
        "nocoes de direito administrativo|ato administrativo"
    ]
    assert (m.no_id, m.origem, m.status) == ("A-ATO", "regra", "aprovado")


def test_nao_mapeia_sob_outro_pai(monkeypatch, tmp_path, arvore_path):
    # Mesma chave de regra de "Atos administrativos", mas o pai é Constitucional.
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        assunto={
            ("direito administrativo", "atos administrativos"): _nome(
                "Atos administrativos"
            ),
            ("direito constitucional", "atos administrativos"): _nome(
                "Atos administrativos"
            ),
        },
    )
    assert novos == 0
    assert (
        "direito constitucional|atos administrativos"
        not in carregar(arvore_path).mapeamentos
    )


def test_item_sem_pai_mapeado_e_nome_novo_ficam_pendentes(
    monkeypatch, tmp_path, arvore_path
):
    conteudo = arvore_path.read_text(encoding="utf-8")
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"direito penal": _nome("Direito Penal")},
        assunto={
            ("direito penal", "atos administrativos"): _nome("Atos administrativos"),
            ("direito administrativo", "licitacoes"): _nome("Licitações"),
        },
    )
    assert novos == 0
    # Nada mudou: nunca cria nó nem grava sem necessidade.
    assert arvore_path.read_text(encoding="utf-8") == conteudo


def test_regra_ambigua_fica_pendente(monkeypatch, tmp_path, arvore_path):
    arv = carregar(arvore_path)
    criar_no(arv, "assunto", "Atos (outro)", "M-DA", id_override="A-ATO2")
    mapear(arv, "direito administrativo|ato", ["A-ATO2"])
    salvar(arv, arvore_path)
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        assunto={
            ("direito administrativo", "atos administrativos"): _nome(
                "Atos administrativos"
            ),
            ("direito administrativo", "ato"): _nome("Atos administrativos"),
            ("nocoes de direito administrativo", "atos"): _nome("Ato administrativo"),
        },
    )
    assert novos == 0


def test_titulo_de_bloco_fora_da_lista_vira_assunto(monkeypatch, tmp_path, arvore_path):
    # "Poder Executivo" não é disciplina da lista fechada, mas é assunto de M-DC.
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"poder executivo": _nome("Poder Executivo")},
    )
    assert novos == 1
    [m] = carregar(arvore_path).mapeamentos["poder executivo"]
    assert (m.no_id, m.origem, m.status) == ("A-EXE", "regra", "aprovado")


def test_titulo_de_bloco_sem_assunto_equivalente_fica_pendente(
    monkeypatch, tmp_path, arvore_path
):
    conteudo = arvore_path.read_text(encoding="utf-8")
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"licenciamento de drones": _nome("Licenciamento de drones")},
    )
    assert novos == 0
    assert arvore_path.read_text(encoding="utf-8") == conteudo


def test_titulo_de_bloco_com_dois_assuntos_de_mesmo_nome_fica_pendente(
    monkeypatch, tmp_path, arvore_path
):
    arv = carregar(arvore_path)
    criar_no(arv, "assunto", "Poder Executivo", "M-DA", id_override="A-EXE2")
    salvar(arv, arvore_path)
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"poder executivo": _nome("Poder Executivo")},
    )
    assert novos == 0
    assert "poder executivo" not in carregar(arvore_path).mapeamentos


def test_proposta_automatica_nao_cria_disciplina():
    from src.arvore import ArvoreInvalida, propor

    arv = ArvoreMestre()
    for origem in ("llm", "regra"):
        with pytest.raises(ArvoreInvalida, match="Disciplina nova"):
            propor(
                arv,
                "criar",
                {"nivel": "materia", "nome": "Drones"},
                origem,
                "teste",
            )


# Memória das decisões do dono no passo determinístico (P73) -----------------------


def _mexer(arvore_path, fn):
    arv = carregar(arvore_path)
    fn(arv)
    salvar(arv, arvore_path)


def test_memoria_no_passo_deterministico(monkeypatch, tmp_path, arvore_path):
    # Decisão humana de outro edital: grafia diferente não casa por nome no edital
    # atual, mas a memória (mesma chave_regra, mesmo pai) resolve sem LLM.
    _mexer(
        arvore_path,
        lambda a: mapear(
            a, "direito administrativo|controle externo", ["A-ATO"], "humano"
        ),
    )
    antes = carregar(arvore_path).mapeamentos
    res = canonico.mapear_novos_itens
    nomes = canonico.NomesOrigem(
        assunto={
            ("nocoes de direito administrativo", "controles externos"): _nome(
                "Controles externos"
            ),
        }
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    r = res(tmp_path, arvore_path)
    assert (r.por_nome, r.por_memoria, r.pendentes) == (0, 1, 0)
    arv = carregar(arvore_path)
    [m] = arv.mapeamentos["nocoes de direito administrativo|controles externos"]
    assert (m.no_id, m.origem, m.status) == ("A-ATO", "regra", "aprovado")
    # Piloto/itens já mapeados não mudam.
    for chave, lista in antes.items():
        assert arv.mapeamentos[chave] == lista
    # Idempotente.
    assert res(tmp_path, arvore_path).total == 0


def test_no_ativo_semente_nao_vira_apelido_no_passo(monkeypatch, tmp_path, arvore_path):
    # "Atos administrativos" é nó ativo: item com o mesmo nome em outra grafia
    # (sem decisão aprovada) não é mapeado por apelido.
    nomes = canonico.NomesOrigem(
        assunto={("direito administrativo", "atos admin"): _nome("Atos admin")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    r = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert r.total == 0 and r.pendentes == 1


def test_no_fundido_vira_apelido_no_passo(monkeypatch, tmp_path, arvore_path):
    def ajusta(a):
        criar_no(a, "assunto", "Probidade", "M-DA", "humano", id_override="A-PRO")
        fundir_nos(a, "A-PRO", "A-ATO")

    _mexer(arvore_path, ajusta)
    nomes = canonico.NomesOrigem(
        assunto={("direito administrativo", "probidade"): _nome("Probidade")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    r = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert r.por_memoria == 1
    [m] = carregar(arvore_path).mapeamentos["direito administrativo|probidade"]
    assert m.no_id == "A-ATO"


def test_proposta_nao_aprovada_nunca_promove(monkeypatch, tmp_path, arvore_path):
    _mexer(
        arvore_path,
        lambda a: mapear(
            a, "direito administrativo|controle", ["A-ATO"], "llm", "proposto"
        ),
    )
    nomes = canonico.NomesOrigem(
        assunto={("direito administrativo", "controles"): _nome("Controle")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    r = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert r.total == 0
    assert "direito administrativo|controles" not in carregar(arvore_path).mapeamentos


def test_par_rejeitado_nunca_e_devolvido_no_passo(monkeypatch, tmp_path, arvore_path):
    def ajusta(a):
        mapear(a, "direito administrativo|controle", ["A-ATO"], "humano")
        mapear(a, "direito constitucional|controle", ["A-EXE"], "humano")
        mapear(a, "x|controle", ["A-ATO"], "llm", "proposto")
        rejeitar(a, "x|controle", "A-ATO")

    _mexer(arvore_path, ajusta)
    nomes = canonico.NomesOrigem(
        assunto={("nocoes de direito administrativo", "controle"): _nome("Controle")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    assert canonico.mapear_novos_itens(tmp_path, arvore_path).total == 0


def test_titulo_de_bloco_com_par_rejeitado_nao_e_reintroduzido(
    monkeypatch, tmp_path, arvore_path
):
    # KAN-80: o dono rejeitou "processo" -> assunto homônimo de outra disciplina.
    # O item já está em `mapeamentos` (só rejeitado), então o passo não o regrava
    # como regra/aprovado nem o conta como pendente.
    _mexer(
        arvore_path,
        lambda a: (
            mapear(a, "poder executivo", ["A-EXE"], "humano"),
            rejeitar(a, "poder executivo", "A-EXE"),
        ),
    )
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"poder executivo": _nome("Poder Executivo")},
    )
    assert novos == 0
    [m] = carregar(arvore_path).mapeamentos["poder executivo"]
    assert (m.no_id, m.origem, m.status) == ("A-EXE", "humano", "rejeitado")


def test_memoria_encadeia_materia_assunto_subassunto(
    monkeypatch, tmp_path, arvore_path
):
    def ajusta(a):
        criar_no(a, "subassunto", "Anulação", "A-ATO", id_override="S-ANU")
        criar_no(a, "materia", "Direito Adm. Geral", None, id_override="M-OLD")
        fundir_nos(a, "M-OLD", "M-DA")
        mapear(a, "direito administrativo|atos administrativos|anulacao", ["S-ANU"])

    _mexer(arvore_path, ajusta)
    nomes = canonico.NomesOrigem(
        materia={"direito adm. geral": _nome("Direito Adm. Geral")},
        assunto={
            ("direito adm. geral", "atos administrativos"): _nome(
                "Atos administrativos"
            )
        },
        subassunto={
            ("direito adm. geral", "atos administrativos", "anulacao"): _nome(
                "Anulação"
            )
        },
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    r = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert (r.total, r.pendentes) == (3, 0)
    arv = carregar(arvore_path)
    chave = "direito adm. geral|atos administrativos|anulacao"
    assert [m.no_id for m in arv.mapeamentos[chave]] == ["S-ANU"]


def test_sem_gravar_nao_salva_mas_altera_arvore_em_memoria(
    monkeypatch, tmp_path, arvore_path
):
    _mexer(
        arvore_path,
        lambda a: mapear(
            a, "direito administrativo|controle externo", ["A-ATO"], "humano"
        ),
    )
    nomes = canonico.NomesOrigem(
        assunto={
            ("nocoes de direito administrativo", "controles externos"): _nome(
                "Controles externos"
            )
        }
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    conteudo = arvore_path.read_text(encoding="utf-8")
    mem = carregar(arvore_path)
    r = canonico.mapear_novos_itens(tmp_path, arvore_path, gravar=False, arvore_mem=mem)
    assert r.por_memoria == 1
    assert "nocoes de direito administrativo|controles externos" in mem.mapeamentos
    assert arvore_path.read_text(encoding="utf-8") == conteudo


# --- KAN-82 (M2): título de bloco genérico x assunto homônimo de outra disciplina ---


@pytest.fixture
def arvore_processo(arvore_path):
    arv = carregar(arvore_path)
    criar_no(arv, "materia", "Direito Processual Civil", None, id_override="M-DPC")
    criar_no(arv, "materia", "Tecnologia da Informação", None, id_override="M-TI")
    criar_no(arv, "assunto", "Processo", "M-DPC", id_override="A-PROC")
    criar_no(arv, "assunto", "Engenharia de software", "M-TI", id_override="A-ES")
    criar_no(
        arv, "assunto", "Ciclo de vida do processo", "M-DPC", id_override="A-CICLO"
    )
    salvar(arv, arvore_path)
    return arvore_path


def test_titulo_generico_nao_casa_com_assunto_de_outra_disciplina(
    monkeypatch, tmp_path, arvore_processo
):
    # Filhos do bloco já mapeados em TI: "Processo" não pode virar Direito Processual.
    _mexer(
        arvore_processo,
        lambda a: mapear(a, "processo|ciclos de vida", ["A-ES"], "humano"),
    )
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_processo,
        materia={"processo": _nome("PROCESSO")},
        assunto={("processo", "ciclos de vida"): _nome("Ciclos de vida")},
    )
    assert novos == 0
    assert "processo" not in carregar(arvore_processo).mapeamentos


def test_titulo_generico_sem_como_inferir_disciplina_fica_pendente(
    monkeypatch, tmp_path, arvore_processo
):
    novos = _rodar(
        monkeypatch, tmp_path, arvore_processo, materia={"processo": _nome("PROCESSO")}
    )
    assert novos == 0
    assert "processo" not in carregar(arvore_processo).mapeamentos


def test_titulo_generico_casa_com_disciplina_compativel(
    monkeypatch, tmp_path, arvore_processo
):
    _mexer(
        arvore_processo,
        lambda a: mapear(a, "processo|ciclos", ["A-CICLO"], "humano"),
    )
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_processo,
        materia={"processo": _nome("PROCESSO")},
        assunto={("processo", "ciclos"): _nome("Ciclos")},
    )
    assert novos == 1
    [m] = carregar(arvore_processo).mapeamentos["processo"]
    assert (m.no_id, m.status) == ("A-PROC", "aprovado")


def test_nome_longo_unico_continua_casando_sem_disciplina_inferida(
    monkeypatch, tmp_path, arvore_path
):
    arv = carregar(arvore_path)
    criar_no(arv, "assunto", "Finanças públicas", "M-DC", id_override="A-FIN")
    salvar(arv, arvore_path)
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"financas publicas": _nome("Finanças Públicas")},
    )
    assert novos == 1
    [m] = carregar(arvore_path).mapeamentos["financas publicas"]
    assert (m.no_id, m.status) == ("A-FIN", "aprovado")


def test_titulo_igual_a_propria_disciplina_continua_casando(
    monkeypatch, tmp_path, arvore_path
):
    arv = carregar(arvore_path)
    criar_no(arv, "materia", "Estatística", None, id_override="M-EST")
    salvar(arv, arvore_path)
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"estatistica": _nome("ESTATÍSTICA")},
    )
    assert novos == 1


def test_titulo_generico_de_duas_palavras_nao_casa_por_nome(
    monkeypatch, tmp_path, arvore_path
):
    arv = carregar(arvore_path)
    criar_no(arv, "assunto", "Conceitos básicos", "M-DC", id_override="A-CB")
    salvar(arv, arvore_path)
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"conceitos basicos": _nome("CONCEITOS BÁSICOS")},
    )
    assert novos == 0
    assert "conceitos basicos" not in carregar(arvore_path).mapeamentos


def test_ramo_de_titulo_respeita_veto_de_outra_chave_com_mesma_chave_regra(
    monkeypatch, tmp_path, arvore_path
):
    # O dono rejeitou "Poder Executivo" -> A-EXE sob a chave "outro|poder executivo";
    # o título "poder executivo" tem a mesma chave_regra e não é regravado.
    _mexer(
        arvore_path,
        lambda a: (
            mapear(a, "outro|poder executivo", ["A-EXE"], "humano"),
            rejeitar(a, "outro|poder executivo", "A-EXE"),
        ),
    )
    novos = _rodar(
        monkeypatch,
        tmp_path,
        arvore_path,
        materia={"poder executivo": _nome("Poder Executivo")},
    )
    assert novos == 0
    assert "poder executivo" not in carregar(arvore_path).mapeamentos


def test_titulos_genericos_exportados():
    assert canonico.titulo_generico("PROCESSO")
    assert canonico.titulo_generico("Conceitos Básicos")
    assert not canonico.titulo_generico("Finanças públicas")
    assert canonico.chave_regra("Legislação").chave in canonico.TITULOS_GENERICOS


# Herança de nó-folha (KAN-85) ----------------------------------------------------


@pytest.fixture
def arvore_folha(arvore_path):
    """Tópico "BSC" aponta para o subassunto-folha S-BSC; "Redes" para S-RED;
    "Dupla" aponta para dois nós."""

    def montar(a):
        criar_no(a, "materia", "Governança de TI", None, id_override="M-TI")
        criar_no(a, "assunto", "Gestão", "M-TI", id_override="A-GES")
        criar_no(a, "subassunto", "BSC", "A-GES", id_override="S-BSC")
        criar_no(a, "subassunto", "Redes", "A-GES", id_override="S-RED")
        criar_no(a, "subassunto", "Dupla A", "A-GES", id_override="S-DA")
        criar_no(a, "subassunto", "Dupla B", "A-GES", id_override="S-DB")
        mapear(a, "governanca de ti", ["M-TI"])
        mapear(a, "governanca de ti|bsc", ["S-BSC"])
        mapear(a, "governanca de ti|redes", ["S-RED"])
        mapear(a, "governanca de ti|dupla", ["S-DA", "S-DB"])

    _mexer(arvore_path, montar)
    return arvore_path


def _filhos(monkeypatch, tmp_path, arvore_path, itens):
    sub = {("governanca de ti", pai, k): _nome(n) for pai, k, n in itens}
    nomes = canonico.NomesOrigem(subassunto=sub)
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens(tmp_path, arvore_path)


def _cb(*partes):
    return "|".join(partes)


def test_faceta_herda_no_folha(monkeypatch, tmp_path, arvore_folha):
    res = _filhos(
        monkeypatch,
        tmp_path,
        arvore_folha,
        [
            ("bsc", "perspectiva financeira", "Perspectiva financeira"),
            ("bsc", "backup", "Backup"),
        ],
    )
    assert (res.por_heranca, res.por_nome, res.por_memoria, res.total) == (2, 0, 0, 2)
    arv = carregar(arvore_folha)
    m = arv.mapeamentos[_cb("governanca de ti", "bsc", "backup")]
    assert [(x.no_id, x.origem, x.status) for x in m] == [
        ("S-BSC", "regra", "aprovado")
    ]


def test_no_e_folha_exige_ativo_nivel_e_sem_filhos(arvore_folha):
    arv = carregar(arvore_folha)
    assert canonico.no_e_folha(arv, "S-BSC", "subassunto")
    assert not canonico.no_e_folha(arv, "A-GES")
    assert not canonico.no_e_folha(arv, "S-BSC", "assunto")
    assert not canonico.no_e_folha(arv, "inexistente")
    # Filho ativo (montado direto, a API de criação não permite nível inválido).
    arv.nos["S-DA"].pai = "S-BSC"
    assert not canonico.no_e_folha(arv, "S-BSC", "subassunto")
    assert not canonico.sem_filhos_ativos(arv, "S-BSC")


def test_pai_em_assunto_com_filhos_nao_herda(monkeypatch, tmp_path, arvore_folha):
    # O tópico "gestao" aponta para o assunto A-GES (nível assunto, com filhos).
    _mexer(arvore_folha, lambda a: mapear(a, "governanca de ti|gestao", ["A-GES"]))
    res = _filhos(monkeypatch, tmp_path, arvore_folha, [("gestao", "x", "Escopo X")])
    assert res.por_heranca == 0 and res.pendentes == 1


def test_pai_com_dois_nos_nao_herda(monkeypatch, tmp_path, arvore_folha):
    res = _filhos(monkeypatch, tmp_path, arvore_folha, [("dupla", "x", "Escopo X")])
    assert res.por_heranca == 0 and res.pendentes == 1


def test_nome_generico_nao_herda(monkeypatch, tmp_path, arvore_folha):
    res = _filhos(
        monkeypatch,
        tmp_path,
        arvore_folha,
        [("bsc", "conceitos basicos", "Conceitos básicos")],
    )
    assert res.por_heranca == 0 and res.pendentes == 1


def test_par_vetado_nao_herda(monkeypatch, tmp_path, arvore_folha):
    _mexer(
        arvore_folha,
        lambda a: (
            mapear(a, "outro|bsc|perspectivas", ["S-BSC"], "humano"),
            rejeitar(a, "outro|bsc|perspectivas", "S-BSC"),
        ),
    )
    res = _filhos(
        monkeypatch, tmp_path, arvore_folha, [("bsc", "perspectivas", "Perspectivas")]
    )
    assert res.por_heranca == 0 and res.pendentes == 1


def test_item_com_entrada_previa_fica_intocado(monkeypatch, tmp_path, arvore_folha):
    _mexer(
        arvore_folha,
        lambda a: (
            mapear(a, "governanca de ti|bsc|prop", ["S-RED"], "llm", "proposto"),
            mapear(a, "governanca de ti|bsc|rej", ["S-RED"], "humano"),
            rejeitar(a, "governanca de ti|bsc|rej", "S-RED"),
        ),
    )
    res = _filhos(
        monkeypatch,
        tmp_path,
        arvore_folha,
        [("bsc", "prop", "Prop"), ("bsc", "rej", "Rej")],
    )
    assert res.por_heranca == 0
    arv = carregar(arvore_folha)
    assert arv.mapeamentos["governanca de ti|bsc|prop"][0].status == "proposto"
    assert arv.mapeamentos["governanca de ti|bsc|rej"][0].status == "rejeitado"


def test_heranca_idempotente(monkeypatch, tmp_path, arvore_folha):
    itens = [("bsc", "backup", "Backup"), ("redes", "redes locais", "Redes locais")]
    r1 = _filhos(monkeypatch, tmp_path, arvore_folha, itens)
    antes = carregar(arvore_folha).mapeamentos["governanca de ti|bsc|backup"]
    r2 = _filhos(monkeypatch, tmp_path, arvore_folha, itens)
    assert r1.por_heranca == 2 and r2.por_heranca == 0 and r2.total == 0
    assert len(
        carregar(arvore_folha).mapeamentos["governanca de ti|bsc|backup"]
    ) == len(antes)


def test_heranca_dry_run_nao_grava(monkeypatch, tmp_path, arvore_folha):
    nomes = canonico.NomesOrigem(
        subassunto={("governanca de ti", "bsc", "backup"): _nome("Backup")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    mem = carregar(arvore_folha)
    res = canonico.mapear_novos_itens(
        tmp_path, arvore_folha, gravar=False, arvore_mem=mem
    )
    assert res.por_heranca == 1
    assert "governanca de ti|bsc|backup" in mem.mapeamentos
    assert "governanca de ti|bsc|backup" not in carregar(arvore_folha).mapeamentos


# Filho único de mesmo nome (KAN-97, M14) -------------------------------------------


@pytest.fixture
def arvore_sefa(arvore_path):
    """Estrutura do SEFA_PR_25: o título de bloco "Administração Geral e Pública"
    aponta para 3 nós de outros editais; os filhos de mesmo nome já existem."""

    def montar(a):
        criar_no(a, "materia", "Administração Geral", None, id_override="M-AG")
        criar_no(a, "materia", "Administração Pública", None, id_override="M-AP")
        criar_no(a, "materia", "Administração Financeira", None, id_override="M-AF")
        criar_no(a, "assunto", "Evolução da administração", "M-AG", id_override="A-EVO")
        criar_no(a, "assunto", "Processo administrativo", "M-AG", id_override="A-PRO")
        criar_no(a, "assunto", "Governo eletrônico", "M-AP", id_override="A-GOV")
        criar_no(a, "subassunto", "Abordagens", "A-EVO", id_override="S-ABO")
        criar_no(a, "subassunto", "Transparência", "A-GOV", id_override="S-TRA")
        criar_no(a, "subassunto", "Accountability", "A-GOV", id_override="S-ACC")
        criar_no(
            a, "subassunto", "Cultura organizacional", "A-PRO", id_override="S-CUL"
        )
        mapear(a, "administracao geral e publica", ["M-AG", "M-AP", "M-AF"])

    _mexer(arvore_path, montar)
    return arvore_path


def _rodar_filho(monkeypatch, tmp_path, arvore_path, assunto=(), subassunto=()):
    bloco = "administracao geral e publica"
    nomes = canonico.NomesOrigem(
        assunto={(bloco, canonico.chave_regra(n).chave): _nome(n) for n in assunto},
        subassunto={
            (bloco, canonico.chave_regra(t).chave, canonico.chave_regra(s).chave): (
                _nome(s)
            )
            for t, s in subassunto
        },
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens(tmp_path, arvore_path)


def _destino(arvore_path, *partes):
    arv = carregar(arvore_path)
    return [
        (m.no_id, m.origem, m.status) for m in arv.mapeamentos.get(_cb(*partes), [])
    ]


def test_filho_unico_resolve_os_casos_do_sefa(monkeypatch, tmp_path, arvore_sefa):
    # O pai tem 3 nós; "Evolução da administração" é filho único no conjunto, e o
    # subassunto sobe junto na mesma execução (cascata assunto -> subassunto).
    res = _rodar_filho(
        monkeypatch,
        tmp_path,
        arvore_sefa,
        assunto=["Evolução da administração", "Governo eletrônico"],
        subassunto=[
            ("Evolução da administração", "Abordagens"),
            ("Governo eletrônico", "Transparência"),
            ("Governo eletrônico", "Accountability"),
        ],
    )
    assert (res.por_filho, res.por_nome, res.por_memoria, res.pendentes) == (5, 0, 0, 0)
    assert res.total == 5
    bloco = "administracao geral e publica"
    ok = [("A-EVO", "regra", "aprovado")]
    assert _destino(arvore_sefa, bloco, "evolucao da administracao") == ok
    assert _destino(arvore_sefa, bloco, "governo eletronico") == [
        ("A-GOV", "regra", "aprovado")
    ]
    assert _destino(arvore_sefa, bloco, "governo eletronico", "accountability") == [
        ("S-ACC", "regra", "aprovado")
    ]
    assert _destino(arvore_sefa, bloco, "governo eletronico", "transparencia") == [
        ("S-TRA", "regra", "aprovado")
    ]


def test_filho_unico_subassunto_sob_assunto_de_outro_bloco(
    monkeypatch, tmp_path, arvore_sefa
):
    res = _rodar_filho(
        monkeypatch,
        tmp_path,
        arvore_sefa,
        assunto=["Processo administrativo"],
        subassunto=[("Processo administrativo", "Cultura organizacional")],
    )
    assert res.por_filho == 2 and res.pendentes == 0
    assert _destino(
        arvore_sefa,
        "administracao geral e publica",
        "processo administrativo",
        "cultura organizacional",
    ) == [("S-CUL", "regra", "aprovado")]


def test_filho_unico_idempotente(monkeypatch, tmp_path, arvore_sefa):
    kw = dict(
        assunto=["Governo eletrônico"],
        subassunto=[("Governo eletrônico", "Accountability")],
    )
    r1 = _rodar_filho(monkeypatch, tmp_path, arvore_sefa, **kw)
    antes = arvore_sefa.read_text(encoding="utf-8")
    r2 = _rodar_filho(monkeypatch, tmp_path, arvore_sefa, **kw)
    assert r1.por_filho == 2 and r2.total == 0 and r2.por_filho == 0
    assert arvore_sefa.read_text(encoding="utf-8") == antes


def test_filho_duplicado_sob_pais_diferentes_do_conjunto_fica_pendente(
    monkeypatch, tmp_path, arvore_sefa
):
    # Mesmo nome sob M-AG e M-AP, ambos no conjunto do pai: ambíguo.
    _mexer(
        arvore_sefa,
        lambda a: criar_no(
            a, "assunto", "Governo eletrônico", "M-AG", id_override="A-G2"
        ),
    )
    res = _rodar_filho(
        monkeypatch, tmp_path, arvore_sefa, assunto=["Governo eletrônico"]
    )
    assert res.por_filho == 0 and res.pendentes == 1
    assert (
        "administracao geral e publica|governo eletronico"
        not in carregar(arvore_sefa).mapeamentos
    )


def test_filho_duplicado_sob_o_mesmo_pai_fica_pendente(
    monkeypatch, tmp_path, arvore_sefa
):
    _mexer(
        arvore_sefa,
        lambda a: criar_no(
            a, "assunto", "Governo eletrônico", "M-AP", id_override="A-G2"
        ),
    )
    res = _rodar_filho(
        monkeypatch, tmp_path, arvore_sefa, assunto=["Governo eletrônico"]
    )
    assert res.por_filho == 0 and res.pendentes == 1


def test_filho_proposto_ou_aposentado_nao_conta(monkeypatch, tmp_path, arvore_sefa):
    def montar(a):
        a.nos["A-GOV"].status = "proposto"
        a.nos["A-EVO"].status = "aposentado"

    _mexer(arvore_sefa, montar)
    res = _rodar_filho(
        monkeypatch,
        tmp_path,
        arvore_sefa,
        assunto=["Governo eletrônico", "Evolução da administração"],
    )
    assert res.por_filho == 0 and res.pendentes == 2


def test_par_vetado_nunca_vai_para_o_filho(monkeypatch, tmp_path, arvore_sefa):
    _mexer(
        arvore_sefa,
        lambda a: (
            mapear(a, "outro|governo eletronico", ["A-GOV"], "humano"),
            rejeitar(a, "outro|governo eletronico", "A-GOV"),
        ),
    )
    res = _rodar_filho(
        monkeypatch, tmp_path, arvore_sefa, assunto=["Governo eletrônico"]
    )
    assert res.por_filho == 0 and res.pendentes == 1


def test_titulo_generico_nunca_vai_para_o_filho(monkeypatch, tmp_path, arvore_sefa):
    assert canonico.titulo_generico("Conceitos básicos")
    _mexer(
        arvore_sefa,
        lambda a: criar_no(
            a, "assunto", "Conceitos básicos", "M-AG", id_override="A-CB"
        ),
    )
    res = _rodar_filho(
        monkeypatch, tmp_path, arvore_sefa, assunto=["Conceitos básicos"]
    )
    assert res.por_filho == 0 and res.pendentes == 1


def test_nivel_incompativel_nunca_vai_para_o_filho(monkeypatch, tmp_path, arvore_sefa):
    # O assunto-item "Gestão" aponta para a matéria M-AF, e o único filho de mesmo
    # nome dela é um assunto: o subassunto-item não pode ir para um nó de assunto.
    def montar(a):
        criar_no(a, "assunto", "Orçamento", "M-AF", id_override="A-ORC")
        mapear(a, "administracao geral e publica|gestao", ["M-AF"])

    _mexer(arvore_sefa, montar)
    res = _rodar_filho(
        monkeypatch, tmp_path, arvore_sefa, subassunto=[("Gestão", "Orçamento")]
    )
    # O ramo 4 continua sem aceitar o assunto; desde o M16 (KAN-102) quem casa é o
    # nome igual (casamento global), com as travas dele.
    assert (res.por_filho, res.por_global, res.pendentes) == (0, 1, 0)


def test_item_de_materia_nao_passa_pelo_ramo_do_filho(
    monkeypatch, tmp_path, arvore_sefa
):
    nomes = canonico.NomesOrigem(
        materia={"governo eletronico": _nome("Governo eletrônico")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    res = canonico.mapear_novos_itens(tmp_path, arvore_sefa, gravar=False)
    assert res.por_filho == 0


def test_filho_unico_sem_pai_mapeado_fica_pendente(monkeypatch, tmp_path, arvore_sefa):
    nomes = canonico.NomesOrigem(
        assunto={("bloco sem no", "governo eletronico"): _nome("Governo eletrônico")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    res = canonico.mapear_novos_itens(tmp_path, arvore_sefa)
    assert res.por_filho == 0 and res.pendentes == 1


def test_filho_unico_dry_run_nao_grava(monkeypatch, tmp_path, arvore_sefa):
    nomes = canonico.NomesOrigem(
        assunto={
            ("administracao geral e publica", "governo eletronico"): _nome(
                "Governo eletrônico"
            )
        }
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    mem = carregar(arvore_sefa)
    res = canonico.mapear_novos_itens(
        tmp_path, arvore_sefa, gravar=False, arvore_mem=mem
    )
    assert res.por_filho == 1
    chave = "administracao geral e publica|governo eletronico"
    assert chave in mem.mapeamentos
    assert chave not in carregar(arvore_sefa).mapeamentos


# Pai provisório pelo cargo (KAN-86, M4) --------------------------------------------

DISCIPLINAS = {
    "M-TI": "Tecnologia da Informação",
    "M-DA": "Direito Administrativo",
    "M-AP": "Administração Pública",
    "M-AD": "Administração",
}
CARGO_TI = "TÉCNICO EM TECNOLOGIA DA INFORMAÇÃO II – ÁREA 1: BANCO DE DADOS"


@pytest.fixture
def arvore_ti(arvore_path):
    """TI com assunto "Banco de dados" (e subassunto "Normalização"), assunto
    "Redes" e o assunto "Atos administrativos" de Direito Administrativo."""

    def montar(a):
        criar_no(a, "materia", "Tecnologia da Informação", None, id_override="M-TI")
        criar_no(a, "assunto", "Banco de dados", "M-TI", id_override="A-BD")
        criar_no(a, "assunto", "Modelagem relacional", "M-TI", id_override="A-MOD")
        criar_no(a, "assunto", "Processos", "M-TI", id_override="A-PROC")
        criar_no(a, "subassunto", "Normalização", "A-MOD", id_override="S-NORM")
        criar_no(a, "subassunto", "Índices", "A-BD", id_override="S-IDX")

    _mexer(arvore_path, montar)
    return arvore_path


def _ti(
    monkeypatch, tmp_path, arvore_path, assunto=(), subassunto=(), cargos=None, **kw
):
    """Roda o passo com o título "bloco ti" sem nó, vindo só de `CARGO_TI`."""
    bloco = "bloco ti"
    nomes = canonico.NomesOrigem(
        assunto={(bloco, canonico.normalizar(n)): _nome(n) for n in assunto},
        subassunto={
            (bloco, canonico.normalizar(t), canonico.normalizar(s)): (_nome(s))
            for t, s in subassunto
        },
        cargos_materia={bloco: {CARGO_TI} if cargos is None else cargos},
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens(
        tmp_path, arvore_path, disciplinas=DISCIPLINAS, **kw
    )


def test_cargo_de_ti_infere_ti():
    assert canonico.disciplina_do_cargo(CARGO_TI, DISCIPLINAS) == "M-TI"
    assert (
        canonico.disciplina_do_cargo("Analista de Direito Administrativo", DISCIPLINAS)
        == "M-DA"
    )


def test_cargo_sem_disciplina_nao_infere():
    assert canonico.disciplina_do_cargo("AGENTE ADMINISTRATIVO", DISCIPLINAS) is None
    assert canonico.disciplina_do_cargo("ENFERMEIRO", DISCIPLINAS) is None


def test_cargo_com_duas_disciplinas_nao_infere():
    # "Administração Pública" e "Administração" cabem no mesmo nome de cargo.
    cargo = "ANALISTA DE ADMINISTRAÇÃO PÚBLICA"
    assert canonico.disciplina_do_cargo(cargo, DISCIPLINAS) is None


def test_chunk_basico_ou_sem_cargo_nao_infere(arvore_ti):
    arv = carregar(arvore_ti)
    nomes = canonico.NomesOrigem(
        cargos_materia={
            "so especifico": {CARGO_TI},
            "tambem basico": {CARGO_TI, None},
            "dois cargos": {CARGO_TI, "ENFERMEIRO"},
        }
    )
    prov = canonico.disciplinas_provisorias(arv, nomes, DISCIPLINAS)
    assert prov == {"so especifico": "M-TI"}


def test_pais_efetivos_prefere_o_titulo_mapeado():
    assert canonico.pais_efetivos(frozenset({"M-DA"}), "M-TI") == {"M-DA"}
    assert canonico.pais_efetivos(frozenset(), "M-TI") == {"M-TI"}
    assert canonico.pais_efetivos(frozenset(), None) == frozenset()


def test_coletar_nomes_guarda_o_cargo_so_do_chunk_especifico(tmp_path):
    import json

    def chunk(i, tipo, numero, materia):
        return {
            "chunk_index": i,
            "cargo": None,
            "materia_chunk": materia,
            "tipo_conhecimento": tipo,
            "nivel": "superior",
            "cargo_numero": numero,
            "materia_normalizada": materia,
            "apenas_discursiva": False,
            "cargos_restritos": None,
            "materia_origem": "cabecalho",
            "taxonomia_extraida": {
                "materia": materia,
                "topicos": [{"nome": "Item", "subtopicos": []}],
            },
        }

    edital = {
        "edital": "x.pdf",
        "concurso": {"slug": "XX_25", "orgao": "XX", "ano": 2025},
        "cargos": [{"numero": 1, "nome": CARGO_TI, "nivel": "superior"}],
        "resultados": [
            chunk(0, "basico", None, "Legislação"),
            chunk(1, "especifico", 1, "Banco de Dados"),
        ],
    }
    (tmp_path / "x.json").write_text(json.dumps(edital), encoding="utf-8")
    nomes = canonico.coletar_nomes(tmp_path)
    assert nomes.cargos_materia == {"legislacao": {None}, "banco de dados": {CARGO_TI}}


def test_filho_resolve_pela_disciplina_inferida_sem_gravar_o_titulo(
    monkeypatch, tmp_path, arvore_ti
):
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Banco de dados"])
    assert res.por_filho == 1 and res.por_pai_provisorio == 1 and res.pendentes == 0
    assert _destino(arvore_ti, "bloco ti", "banco de dados") == [
        ("A-BD", "regra", "aprovado")
    ]
    assert "bloco ti" not in carregar(arvore_ti).mapeamentos  # P72: título intocado


def test_sem_pai_provisorio_o_filho_fica_pendente(monkeypatch, tmp_path, arvore_ti):
    res = _ti(
        monkeypatch,
        tmp_path,
        arvore_ti,
        assunto=["Banco de dados"],
        pai_provisorio=False,
    )
    assert res.total == 0 and res.pendentes == 1 and res.comparados == 0


def test_assunto_casa_com_subassunto_da_subarvore(monkeypatch, tmp_path, arvore_ti):
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Normalização"])
    assert res.por_pai_provisorio == 1
    assert _destino(arvore_ti, "bloco ti", "normalizacao")[0][0] == "S-NORM"


def test_cascata_assunto_para_subassunto(monkeypatch, tmp_path, arvore_ti):
    # O assunto sobe pelo pai provisório e o subassunto pelo nó real dele.
    _mexer(
        arvore_ti,
        lambda a: criar_no(
            a, "subassunto", "Formas normais", "A-MOD", id_override="S-FN"
        ),
    )
    res = _ti(
        monkeypatch,
        tmp_path,
        arvore_ti,
        assunto=["Modelagem relacional"],
        subassunto=[("Modelagem relacional", "Formas normais")],
    )
    assert res.por_pai_provisorio == 1 and res.por_filho == 2 and res.pendentes == 0
    assert (
        _destino(arvore_ti, "bloco ti", "modelagem relacional", "formas normais")[0][0]
        == "S-FN"
    )


def test_candidato_duplicado_na_subarvore_fica_pendente(
    monkeypatch, tmp_path, arvore_ti
):
    _mexer(
        arvore_ti,
        lambda a: criar_no(
            a, "subassunto", "Banco de dados", "A-MOD", id_override="S-BD2"
        ),
    )
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Banco de dados"])
    assert res.total == 0 and res.pendentes == 1 and res.com_pai_provisorio == 1


def test_candidato_fora_da_disciplina_inferida_nao_casa(
    monkeypatch, tmp_path, arvore_ti
):
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Atos administrativos"])
    assert res.total == 0 and res.pendentes == 1


def test_veto_do_dono_barra_o_pai_provisorio(monkeypatch, tmp_path, arvore_ti):
    _mexer(
        arvore_ti,
        lambda a: (
            mapear(a, "outro|banco de dados", ["A-BD"], "humano"),
            rejeitar(a, "outro|banco de dados", "A-BD"),
        ),
    )
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Banco de dados"])
    assert res.total == 0 and res.pendentes == 1


def test_titulo_generico_barra_o_pai_provisorio(monkeypatch, tmp_path, arvore_ti):
    assert canonico.titulo_generico("Processos")
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Processos"])
    assert res.total == 0 and res.pendentes == 1


def test_bloco_com_itens_aprovados_em_outra_disciplina_recua(
    monkeypatch, tmp_path, arvore_ti
):
    # Um item do bloco já foi aprovado em Direito Administrativo: o nome do cargo
    # não prevalece sobre o dado aprovado.
    _mexer(arvore_ti, lambda a: mapear(a, "bloco ti|outro", ["A-ATO"]))
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Banco de dados", "Outro"])
    assert res.com_pai_provisorio == 0 and res.total == 0


def test_apelido_de_no_fundido_nao_vale_com_pai_provisorio(
    monkeypatch, tmp_path, arvore_ti
):
    def montar(a):
        criar_no(
            a, "subassunto", "Instalação e administração", "A-BD", id_override="S-OLD"
        )
        fundir_nos(a, "S-OLD", "A-MOD")

    _mexer(arvore_ti, montar)
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Instalação e administração"])
    assert res.total == 0 and res.pendentes == 1


def test_pai_provisorio_idempotente(monkeypatch, tmp_path, arvore_ti):
    assert _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Banco de dados"]).total == 1
    antes = carregar(arvore_ti).mapeamentos
    res = _ti(monkeypatch, tmp_path, arvore_ti, assunto=["Banco de dados"])
    assert res.total == 0 and res.comparados == 0
    assert carregar(arvore_ti).mapeamentos == antes


def test_pai_provisorio_dry_run_nao_grava(monkeypatch, tmp_path, arvore_ti):
    mem = carregar(arvore_ti)
    res = _ti(
        monkeypatch,
        tmp_path,
        arvore_ti,
        assunto=["Banco de dados"],
        gravar=False,
        arvore_mem=mem,
    )
    assert res.por_pai_provisorio == 1 and "bloco ti|banco de dados" in mem.mapeamentos
    assert "bloco ti|banco de dados" not in carregar(arvore_ti).mapeamentos


def test_banrisul_ganha_mais_de_100_itens_comparados(tmp_path):
    """Nos 4 cargos de TI do BANRISUL_25, o pai provisório destrava a comparação de
    pelo menos 100 itens que antes ficavam sem pai. Só leitura (árvore em memória)."""
    import shutil

    origem = Path(__file__).resolve().parent.parent / "revisao_piloto"
    jsons = list(origem.glob("*Banrisul*.json"))
    if not jsons or not arv_mod.ARVORE_PADRAO.exists():
        pytest.skip("sem revisao_piloto ou árvore local")
    for j in jsons:
        if not j.name.endswith((".auditoria.json", ".validacao.json")):
            shutil.copy(j, tmp_path)
    sem = canonico.mapear_novos_itens(
        tmp_path, gravar=False, arvore_mem=arv_mod.carregar(), pai_provisorio=False
    )
    com = canonico.mapear_novos_itens(
        tmp_path, gravar=False, arvore_mem=arv_mod.carregar()
    )
    assert com.comparados - sem.comparados >= 100
    assert com.total >= sem.total


# Casamento global por nome (KAN-87, M6) --------------------------------------------

BLOCO_G = "gestao e governanca"
LGPD = "Lei Geral de Proteção de Dados – LGPD (Lei nº 13.709/2018)"


@pytest.fixture
def arvore_global(arvore_path):
    """Bloco de TI ("Gestão e governança" -> TI) com o assunto "Legislação de TI"; em
    Direito Administrativo, os nós de contratos e a LGPD; em Atualidades, "economia"."""

    def montar(a):
        criar_no(a, "materia", "Tecnologia da Informação", None, id_override="M-TI")
        criar_no(a, "materia", "Atualidades", None, id_override="M-ATU")
        criar_no(a, "assunto", "Legislação de TI", "M-TI", id_override="A-LEGTI")
        criar_no(a, "assunto", "Governança de TI", "M-TI", id_override="A-GOVTI")
        criar_no(
            a, "assunto", "Contratos administrativos", "M-DA", id_override="A-CONT"
        )
        criar_no(
            a,
            "assunto",
            "Licitações e contratos administrativos",
            "M-DA",
            id_override="A-LIC",
        )
        criar_no(a, "assunto", "economia", "M-ATU", id_override="A-ECO")
        for sid, nome in {
            "S-FISC": "Papel do fiscalizador do contrato",
            "S-PREP": "Papel do preposto da contratada",
            "S-CONC": "Conceitos básicos e aplicações",
            "S-APL": "Aplicações",
            "S-GPROC": "Gestão de processos",
            "S-ELAB": "Elaboração de contratos de software",
            "S-LGPD": LGPD,
            "S-LAI": "Lei de Acesso à Informação – LAI (Lei nº 12.527/2011)",
        }.items():
            criar_no(a, "subassunto", nome, "A-CONT", id_override=sid)
        criar_no(
            a, "subassunto", "Dispensa de licitação", "A-LIC", id_override="S-DISP"
        )
        # mesmo nome em TI: o equivalente da disciplina do pai vale mais (exceção TI)
        criar_no(
            a,
            "subassunto",
            "Elaboração de contratos de software",
            "A-GOVTI",
            id_override="S-TI-ELAB",
        )
        mapear(a, BLOCO_G, ["M-TI"])
        mapear(a, f"{BLOCO_G}|legislacao de ti", ["A-LEGTI"])

    _mexer(arvore_path, montar)
    return arvore_path


def _g(monkeypatch, tmp_path, arvore_path, subassunto=(), assunto=(), gravar=True):
    """Itens do bloco de TI: subassunto sob "Legislação de TI"; assunto sob o bloco."""
    nomes = canonico.NomesOrigem(
        assunto={(BLOCO_G, canonico.chave_regra(n).chave): _nome(n) for n in assunto},
        subassunto={
            (BLOCO_G, "legislacao de ti", canonico.chave_regra(s).chave): _nome(s)
            for s in subassunto
        },
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens(tmp_path, arvore_path, gravar=gravar)


def _dest(arvore_path, nome, topico="legislacao de ti"):
    chave = _cb(BLOCO_G, topico, canonico.chave_regra(nome).chave)
    return [
        (m.no_id, m.origem, m.status)
        for m in carregar(arvore_path).mapeamentos.get(chave, [])
    ]


def test_contratos_de_ti_casam_em_direito_administrativo(
    monkeypatch, tmp_path, arvore_global
):
    res = _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=[
            "Papel do fiscalizador do contrato",
            "Papel do preposto da contratada",
        ],
    )
    assert (res.por_global, res.total, res.pendentes) == (2, 2, 0)
    assert len(res.chaves_global_fora_disciplina) == 2
    ok = lambda s: [(s, "regra", "aprovado")]  # noqa: E731
    assert _dest(arvore_global, "Papel do fiscalizador do contrato") == ok("S-FISC")
    assert _dest(arvore_global, "Papel do preposto da contratada") == ok("S-PREP")


def test_lgpd_casa_global_por_norma(monkeypatch, tmp_path, arvore_global):
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Lei nº 13.709/2018"])
    assert res.por_global == 1
    assert _dest(arvore_global, "Lei nº 13.709/2018") == [
        ("S-LGPD", "regra", "aprovado")
    ]


def test_norma_de_uma_palavra_casa_em_qualquer_disciplina(
    monkeypatch, tmp_path, arvore_global
):
    # "LAI" tem 1 palavra relevante: só a norma (KAN-64) atravessa a disciplina.
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["LAI"])
    assert res.por_global == 1
    assert _dest(arvore_global, "LAI") == [("S-LAI", "regra", "aprovado")]


def test_norma_em_dois_nos_nao_casa(monkeypatch, tmp_path, arvore_global):
    _mexer(
        arvore_global,
        lambda a: criar_no(
            a, "subassunto", "LGPD (Lei nº 13.709/2018)", "A-GOVTI", id_override="S-LG2"
        ),
    )
    # um dos dois está na disciplina do pai (TI): a exceção TI escolhe esse
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Lei nº 13.709/2018"])
    assert _dest(arvore_global, "Lei nº 13.709/2018") == [
        ("S-LG2", "regra", "aprovado")
    ]
    assert res.chaves_global_fora_disciplina == []
    # sem equivalente na disciplina do pai, a norma repetida fica pendente
    _mexer(
        arvore_global,
        lambda a: criar_no(
            a, "subassunto", "LGPD (Lei nº 13.709/2018)", "A-ATO", id_override="S-LG3"
        ),
    )
    mem = carregar(arvore_global)
    for chave in list(mem.mapeamentos):
        if chave.startswith(f"{BLOCO_G}|legislacao de ti|"):
            del mem.mapeamentos[chave]
    mem.nos["S-LG2"].status = "aposentado"
    salvar(mem, arvore_global)
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Lei nº 13.709/2018"])
    assert (res.por_global, res.pendentes) == (0, 1)


def test_nome_curto_nao_atravessa_disciplina(monkeypatch, tmp_path, arvore_global):
    # "Dispensa de licitação" tem 2 palavras relevantes e só existe em DA: fica de fora
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Dispensa de licitação"])
    assert (res.por_global, res.pendentes) == (0, 1)
    assert _dest(arvore_global, "Dispensa de licitação") == []


def test_nome_curto_casa_dentro_da_disciplina(monkeypatch, tmp_path, arvore_global):
    # "Dispensa de licitação" no bloco que o pai mapeia para DA: mesma disciplina
    _mexer(
        arvore_global,
        lambda a: mapear(a, f"{BLOCO_G}|legislacao de ti", ["A-CONT"]),
    )
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Dispensa de licitação"])
    assert (res.por_global, res.chaves_global_fora_disciplina) == (1, [])
    assert _dest(arvore_global, "Dispensa de licitação") == [
        ("S-DISP", "regra", "aprovado")
    ]


def test_economia_nao_casa_com_atualidades(monkeypatch, tmp_path, arvore_global):
    # ECONOMIA (1 palavra) no bloco de TI não vai para Atualidades › economia
    res = _g(monkeypatch, tmp_path, arvore_global, assunto=["ECONOMIA"])
    assert (res.por_global, res.pendentes) == (0, 1)


@pytest.mark.parametrize(
    "nome",
    [
        "Conceitos básicos e aplicações",
        "Aplicações",
        "Gestão de processos",  # 2 palavras: nunca atravessa disciplina
    ],
)
def test_generico_nunca_casa_global(monkeypatch, tmp_path, arvore_global, nome):
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=[nome])
    assert (res.por_global, res.pendentes) == (0, 1)


def test_genericos_do_global_nao_travam_os_ramos_com_pai():
    # Decisão D3 do dono (2026-11-06): os genéricos do KAN-87 travam só o global.
    for nome in (
        "Aplicações",
        "Definição",
        "Tipos",
        "Instalação, configuração e administração",
        "Conceitos básicos e aplicações",
    ):
        assert canonico.titulo_generico_global(nome), nome
        assert not canonico.titulo_generico(nome), nome
    # a lista dos ramos com pai continua valendo no global
    assert canonico.titulo_generico_global("Conceitos")
    assert canonico.titulo_generico("Conceitos")
    assert not canonico.titulo_generico_global("Tipos de indicadores")
    assert not canonico.titulo_generico_global("Papel do fiscalizador do contrato")


def test_tipos_casa_pelo_filho_unico_dentro_do_pai(monkeypatch, tmp_path, arvore_path):
    # "Licitação › Tipos" de um edital novo vai para o filho "Tipos" do nó de
    # Licitação: o pai dá o contexto que falta ao rótulo genérico.
    def montar(a):
        criar_no(a, "assunto", "Licitação", "M-DA", id_override="A-LICIT")
        criar_no(a, "subassunto", "Tipos", "A-LICIT", id_override="S-TIPOS")
        mapear(a, "direito administrativo|licitacao", ["A-LICIT"])

    _mexer(arvore_path, montar)
    nomes = canonico.NomesOrigem(
        subassunto={("direito administrativo", "licitacao", "tipos"): _nome("Tipos")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    res = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert (res.por_filho, res.pendentes) == (1, 0)
    assert _destino(arvore_path, "direito administrativo", "licitacao", "tipos") == [
        ("S-TIPOS", "regra", "aprovado")
    ]


def test_candidato_duplicado_nao_casa(monkeypatch, tmp_path, arvore_global):
    # o mesmo nome em duas outras disciplinas: ambíguo, fica pendente
    def dup(a):
        criar_no(
            a,
            "subassunto",
            "Cláusulas de nível de serviço",
            "A-CONT",
            id_override="S-D1",
        )
        criar_no(
            a,
            "subassunto",
            "Cláusulas de nível de serviço",
            "A-ECO",
            id_override="S-D2",
        )

    _mexer(arvore_global, dup)
    res = _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=["Cláusulas de nível de serviço"],
    )
    assert (res.por_global, res.pendentes) == (0, 1)


def test_excecao_ti_prefere_o_equivalente_da_disciplina_do_pai(
    monkeypatch, tmp_path, arvore_global
):
    # "Elaboração de contratos de software" existe em DA (S-ELAB) e em TI (S-TI-ELAB):
    # o item de TI vai para o de TI, sem atravessar disciplina
    res = _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=["Elaboração de contratos de software"],
    )
    assert (res.por_global, res.chaves_global_fora_disciplina) == (1, [])
    assert _dest(arvore_global, "Elaboração de contratos de software") == [
        ("S-TI-ELAB", "regra", "aprovado")
    ]


def test_dois_equivalentes_na_disciplina_do_pai_ficam_pendentes(
    monkeypatch, tmp_path, arvore_global
):
    _mexer(
        arvore_global,
        lambda a: criar_no(
            a,
            "subassunto",
            "Elaboração de contratos de software",
            "A-LEGTI",
            id_override="S-TI-ELAB2",
        ),
    )
    # S-TI-ELAB2 é filho do pai (A-LEGTI): o filho único o resolve antes do global
    res = _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=["Elaboração de contratos de software"],
    )
    assert (res.por_filho, res.por_global) == (1, 0)
    assert _dest(arvore_global, "Elaboração de contratos de software") == [
        ("S-TI-ELAB2", "regra", "aprovado")
    ]


def test_veto_do_dono_barra_o_global(monkeypatch, tmp_path, arvore_global):
    chave = f"{BLOCO_G}|outro|papel do fiscalizador do contrato"

    def vetar(a):
        mapear(a, chave, ["S-FISC"], "llm", "proposto")
        rejeitar(a, chave, "S-FISC")

    _mexer(arvore_global, vetar)
    res = _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=["Papel do fiscalizador do contrato"],
    )
    assert (res.por_global, res.pendentes) == (0, 1)


def test_global_em_cascata_assunto_para_subassunto(
    monkeypatch, tmp_path, arvore_global
):
    # o assunto casa global em DA e o subassunto, filho dele, sobe na mesma execução
    nomes = canonico.NomesOrigem(
        assunto={
            (BLOCO_G, "licitacoes e contratos administrativos"): _nome(
                "Licitações e contratos administrativos"
            )
        },
        subassunto={
            (
                BLOCO_G,
                "licitacoes e contratos administrativos",
                "dispensa de licitacao",
            ): _nome("Dispensa de licitação")
        },
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    res = canonico.mapear_novos_itens(tmp_path, arvore_global)
    assert (res.por_global, res.por_filho, res.pendentes) == (1, 1, 0)
    arv = carregar(arvore_global)
    assert (
        arv.mapeamentos[_cb(BLOCO_G, "licitacoes e contratos administrativos")][0].no_id
        == "A-LIC"
    )
    assert (
        arv.mapeamentos[
            _cb(
                BLOCO_G,
                "licitacoes e contratos administrativos",
                "dispensa de licitacao",
            )
        ][0].no_id
        == "S-DISP"
    )


def test_nivel_incompativel_nao_casa_global(monkeypatch, tmp_path, arvore_global):
    # subassunto não aponta para nó de assunto: "Contratos administrativos" é A-CONT
    res = _g(
        monkeypatch, tmp_path, arvore_global, subassunto=["Contratos administrativos"]
    )
    assert (res.por_global, res.pendentes) == (0, 1)


def test_global_idempotente_e_dry_run(monkeypatch, tmp_path, arvore_global):
    itens = ["Papel do fiscalizador do contrato", "Lei nº 13.709/2018"]
    antes = arvore_global.read_bytes()
    mem = carregar(arvore_global)
    nomes = canonico.NomesOrigem(
        subassunto={
            (BLOCO_G, "legislacao de ti", canonico.chave_regra(s).chave): _nome(s)
            for s in itens
        }
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    res = canonico.mapear_novos_itens(
        tmp_path, arvore_global, gravar=False, arvore_mem=mem
    )
    assert res.por_global == 2 and arvore_global.read_bytes() == antes
    assert _g(monkeypatch, tmp_path, arvore_global, subassunto=itens).por_global == 2
    assert _g(monkeypatch, tmp_path, arvore_global, subassunto=itens).total == 0


def test_global_com_pai_provisorio_atravessa_para_direito_administrativo(
    monkeypatch, tmp_path, arvore_ti
):
    # BANRISUL: o bloco de TI não tem nó, o cargo infere TI (M4) e o subitem de
    # contratos, de nome idêntico a um subassunto de DA, vai para o nó de DA.
    _mexer(
        arvore_ti,
        lambda a: criar_no(
            a,
            "subassunto",
            "Papel do fiscalizador do contrato",
            "A-ATO",
            id_override="S-FISC",
        ),
    )
    res = _ti(
        monkeypatch,
        tmp_path,
        arvore_ti,
        subassunto=[("Legislação aplicável", "Papel do fiscalizador do contrato")],
    )
    assert (res.por_global, res.por_pai_provisorio, res.pendentes) == (1, 1, 0)
    assert len(res.chaves_global_fora_disciplina) == 1
    [m] = carregar(arvore_ti).mapeamentos[
        "bloco ti|legislacao aplicavel|papel do fiscalizador do contrato"
    ]
    assert (m.no_id, m.origem, m.status) == ("S-FISC", "regra", "aprovado")


def test_apelido_de_no_fundido_de_outra_disciplina_casa_global(
    monkeypatch, tmp_path, arvore_global
):
    def fundir(a):
        criar_no(
            a,
            "subassunto",
            "Gestão de acordos de nível de serviço",
            "A-CONT",
            id_override="S-OLD",
        )
        fundir_nos(a, "S-OLD", "S-PREP")

    _mexer(arvore_global, fundir)
    res = _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=["Gestão de acordos de nível de serviço"],
    )
    assert res.por_global == 1
    assert _dest(arvore_global, "Gestão de acordos de nível de serviço") == [
        ("S-PREP", "regra", "aprovado")
    ]


# Pai sem nó: casamento global só como proposta (KAN-87, decisão D2) -------------------

BLOCO_SEM_NO = "contabilidade"


def _sem_pai(monkeypatch, tmp_path, arvore_path, itens, gravar=True, arvore_mem=None):
    """Subassuntos sob "contabilidade|tópico solto", sem nó para o pai."""
    nomes = canonico.NomesOrigem(
        subassunto={
            (BLOCO_SEM_NO, "topico solto", canonico.chave_regra(s).chave): _nome(s)
            for s in itens
        }
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens(
        tmp_path, arvore_path, gravar=gravar, arvore_mem=arvore_mem
    )


def _dest_sem_pai(arvore_path, nome):
    chave = _cb(BLOCO_SEM_NO, "topico solto", canonico.chave_regra(nome).chave)
    return [
        (m.no_id, m.origem, m.status)
        for m in carregar(arvore_path).mapeamentos.get(chave, [])
    ]


def test_pai_sem_no_casa_global_como_proposta(monkeypatch, tmp_path, arvore_global):
    res = _sem_pai(
        monkeypatch, tmp_path, arvore_global, ["Papel do fiscalizador do contrato"]
    )
    assert (res.propostos_sem_pai, res.total, res.pendentes) == (1, 0, 0)
    assert _dest_sem_pai(arvore_global, "Papel do fiscalizador do contrato") == [
        ("S-FISC", "regra", "proposto")
    ]


def test_pai_sem_no_norma_casa_como_proposta(monkeypatch, tmp_path, arvore_global):
    res = _sem_pai(monkeypatch, tmp_path, arvore_global, ["Lei nº 13.709/2018"])
    assert res.propostos_sem_pai == 1
    assert _dest_sem_pai(arvore_global, "Lei nº 13.709/2018") == [
        ("S-LGPD", "regra", "proposto")
    ]


@pytest.mark.parametrize("nome", ["Dispensa de licitação", "Aplicações", "Economia"])
def test_pai_sem_no_nome_curto_ou_generico_fica_pendente(
    monkeypatch, tmp_path, arvore_global, nome
):
    # sem disciplina de contexto, nome com menos de 3 palavras relevantes não casa
    res = _sem_pai(monkeypatch, tmp_path, arvore_global, [nome])
    assert (res.propostos_sem_pai, res.pendentes) == (0, 1)
    assert _dest_sem_pai(arvore_global, nome) == []


def test_pai_sem_no_proposta_rejeitada_nao_volta(monkeypatch, tmp_path, arvore_global):
    nome = "Papel do fiscalizador do contrato"
    _sem_pai(monkeypatch, tmp_path, arvore_global, [nome])
    chave = _cb(BLOCO_SEM_NO, "topico solto", canonico.chave_regra(nome).chave)
    _mexer(arvore_global, lambda a: rejeitar(a, chave, "S-FISC"))
    res = _sem_pai(monkeypatch, tmp_path, arvore_global, [nome])
    assert res.propostos_sem_pai == 0
    assert _dest_sem_pai(arvore_global, nome) == [("S-FISC", "regra", "rejeitado")]


def test_pai_sem_no_proposta_dry_run_nao_grava(monkeypatch, tmp_path, arvore_global):
    antes = arvore_global.read_bytes()
    mem = carregar(arvore_global)
    res = _sem_pai(
        monkeypatch,
        tmp_path,
        arvore_global,
        ["Papel do fiscalizador do contrato"],
        gravar=False,
        arvore_mem=mem,
    )
    assert res.propostos_sem_pai == 1 and arvore_global.read_bytes() == antes


# Título genérico não herda decisão de outro edital (KAN-88, M11, P78) ---------------


def _nome_ed(nome, edital):
    return {"nome": nome, "ocorrencias": {(edital, "superior")}}


def _generico(
    monkeypatch,
    tmp_path,
    arvore_path,
    doador_ed,
    item_ed,
    nome_doador="Controle",
    nome_item="Controles",
):
    """Doador aprovado (A-ATO) no edital `doador_ed`; item novo, sob outro bloco que
    aponta para o mesmo nó-pai, no edital `item_ed`."""
    regra_doador = canonico.chave_regra(nome_doador).chave
    regra_item = canonico.chave_regra(nome_item).chave
    _mexer(
        arvore_path,
        lambda a: mapear(
            a, f"direito administrativo|{regra_doador}", ["A-ATO"], "humano"
        ),
    )
    nomes = canonico.NomesOrigem(
        assunto={
            ("direito administrativo", regra_doador): _nome_ed(nome_doador, doador_ed),
            ("nocoes de direito administrativo", regra_item): _nome_ed(
                nome_item, item_ed
            ),
        }
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    return canonico.mapear_novos_itens(tmp_path, arvore_path)


CHAVE_G = "nocoes de direito administrativo|controle"


def test_titulo_generico_nao_herda_de_outro_edital(monkeypatch, tmp_path, arvore_path):
    res = _generico(monkeypatch, tmp_path, arvore_path, "ED_A_25", "ED_B_25")
    assert (res.por_nome, res.por_memoria, res.total) == (0, 0, 0)
    assert res.pendentes == 0 and res.barrados_generico == 1
    assert res.chaves_barradas_generico == [CHAVE_G]
    # Nada aprovado em nome do dono: a decisão de outro edital vira proposta (D5).
    assert (res.propostos_generico, res.chaves_propostas_generico) == (1, [CHAVE_G])
    [m] = carregar(arvore_path).mapeamentos[CHAVE_G]
    assert (m.no_id, m.origem, m.status) == ("A-ATO", "regra", "proposto")


def test_titulo_generico_herda_dentro_do_mesmo_edital(
    monkeypatch, tmp_path, arvore_path
):
    res = _generico(monkeypatch, tmp_path, arvore_path, "ED_A_25", "ED_A_25")
    assert (res.por_nome, res.pendentes, res.barrados_generico) == (1, 0, 0)
    [m] = carregar(arvore_path).mapeamentos[CHAVE_G]
    assert (m.no_id, m.origem, m.status) == ("A-ATO", "regra", "aprovado")


def test_titulo_especifico_continua_herdando_de_outro_edital(
    monkeypatch, tmp_path, arvore_path
):
    res = _generico(
        monkeypatch,
        tmp_path,
        arvore_path,
        "ED_A_25",
        "ED_B_25",
        "Atos administrativos",
        "Ato administrativo",
    )
    assert (res.por_nome, res.barrados_generico) == (1, 0)


def test_titulo_generico_sem_origem_conhecida_nao_herda_pela_memoria(
    monkeypatch, tmp_path, arvore_path
):
    # Decisão do dono em item que nenhum edital em disco traz: origem desconhecida
    # conta como "outro edital".
    _mexer(
        arvore_path,
        lambda a: mapear(a, "direito administrativo|controle", ["A-ATO"], "humano"),
    )
    nomes = canonico.NomesOrigem(
        assunto={("nocoes de direito administrativo", "controle"): _nome("Controle")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    res = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert (res.total, res.pendentes, res.barrados_generico) == (0, 0, 1)
    [m] = carregar(arvore_path).mapeamentos["nocoes de direito administrativo|controle"]
    assert (m.no_id, m.origem, m.status) == ("A-ATO", "regra", "proposto")


def test_titulo_generico_barrado_e_idempotente(monkeypatch, tmp_path, arvore_path):
    _generico(monkeypatch, tmp_path, arvore_path, "ED_A_25", "ED_B_25")
    antes = carregar(arvore_path).mapeamentos
    # a proposta já é entrada da chave: a segunda execução não reavalia o item
    res = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert (res.total, res.barrados_generico, res.propostos_generico) == (0, 0, 0)
    assert carregar(arvore_path).mapeamentos == antes


def test_titulo_generico_proposta_rejeitada_nao_volta(
    monkeypatch, tmp_path, arvore_path
):
    _generico(monkeypatch, tmp_path, arvore_path, "ED_A_25", "ED_B_25")
    _mexer(arvore_path, lambda a: rejeitar(a, CHAVE_G, "A-ATO"))
    res = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert res.propostos_generico == 0
    [m] = carregar(arvore_path).mapeamentos[CHAVE_G]
    assert m.status == "rejeitado"


def test_titulo_generico_aprovado_pelo_dono_deixa_de_ser_pendente(
    monkeypatch, tmp_path, arvore_path
):
    _generico(monkeypatch, tmp_path, arvore_path, "ED_A_25", "ED_B_25")
    _mexer(arvore_path, lambda a: mapear(a, CHAVE_G, ["A-ATO"], "humano"))
    res = canonico.mapear_novos_itens(tmp_path, arvore_path)
    assert (res.total, res.pendentes, res.barrados_generico) == (0, 0, 0)


# M16 (KAN-102): subtópico casa com assunto de mesmo nome --------------------------


def test_m16_subtopico_casa_com_assunto_de_mesmo_nome(
    monkeypatch, tmp_path, arvore_global
):
    # "Governança de TI" é assunto em TI; antes do M16 o subtópico ficava pendente.
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Governança de TI"])
    assert (res.por_global, res.pendentes) == (1, 0)
    assert _dest(arvore_global, "Governança de TI") == [
        ("A-GOVTI", "regra", "aprovado")
    ]


def test_m16_assunto_de_nome_diferente_continua_recusado(
    monkeypatch, tmp_path, arvore_global
):
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Governança"])
    assert (res.por_global, res.pendentes) == (0, 1)
    assert _dest(arvore_global, "Governança") == []


def test_m16_nome_generico_nao_casa_com_assunto(monkeypatch, tmp_path, arvore_global):
    _mexer(
        arvore_global,
        lambda a: criar_no(
            a, "assunto", "Conceitos básicos", "M-TI", id_override="A-CB"
        ),
    )
    res = _g(monkeypatch, tmp_path, arvore_global, subassunto=["Conceitos básicos"])
    assert res.por_global == 0
    assert _dest(arvore_global, "Conceitos básicos") == []


def test_m16_dois_assuntos_de_mesmo_nome_ficam_pendentes(
    monkeypatch, tmp_path, arvore_global
):
    def montar(a):
        criar_no(a, "assunto", "Gestão de riscos de TI", "M-TI", id_override="A-R1")
        criar_no(a, "assunto", "Gestão de riscos de TI", "M-TI", id_override="A-R2")

    _mexer(arvore_global, montar)
    res = _g(
        monkeypatch, tmp_path, arvore_global, subassunto=["Gestão de riscos de TI"]
    )
    assert (res.por_global, res.pendentes) == (0, 1)


def test_m16_subassunto_de_mesmo_nome_vale_mais_que_o_assunto(
    monkeypatch, tmp_path, arvore_global
):
    # Com subassunto de mesmo nome, o resultado é o de antes do M16 (sem ambiguidade).
    _mexer(
        arvore_global,
        lambda a: criar_no(
            a,
            "assunto",
            "Elaboração de contratos de software",
            "M-DA",
            id_override="A-ELAB",
        ),
    )
    _g(
        monkeypatch,
        tmp_path,
        arvore_global,
        subassunto=["Elaboração de contratos de software"],
    )
    assert _dest(arvore_global, "Elaboração de contratos de software") == [
        ("S-TI-ELAB", "regra", "aprovado")
    ]


def test_m16_nivel_aceito_por_nome():
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Administração Pública", None, id_override="M-AP")
    criar_no(arv, "assunto", "Processo decisório", "M-AP", id_override="A-INT")
    no = arv.nos["A-INT"]
    regra = canonico.chave_regra("processo decisório").chave
    assert canonico.nivel_aceito_por_nome(no, "subassunto", regra)
    assert not canonico.nivel_aceito_por_nome(no, "subassunto", "outra coisa")
    assert canonico.nivel_aceito_por_nome(no, "assunto", "qualquer")
    assert not canonico.nivel_aceito_por_nome(no, "materia", regra)
