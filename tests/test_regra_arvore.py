"""Mapeamento de item novo de edital por regra (Etapa 5B.1, ADR-030)."""

import pytest

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
        lambda a: mapear(a, "direito administrativo|controle", ["A-ATO"], "humano"),
    )
    nomes = canonico.NomesOrigem(
        assunto={("nocoes de direito administrativo", "controle"): _nome("Controle")}
    )
    monkeypatch.setattr(canonico, "coletar_nomes", lambda d: nomes)
    conteudo = arvore_path.read_text(encoding="utf-8")
    mem = carregar(arvore_path)
    r = canonico.mapear_novos_itens(tmp_path, arvore_path, gravar=False, arvore_mem=mem)
    assert r.por_memoria == 1
    assert "nocoes de direito administrativo|controle" in mem.mapeamentos
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
