import copy

import pytest

from src.arvore import (
    ARVORE_PADRAO,
    ArvoreInvalida,
    ArvoreMestre,
    Mapeamento,
    Proposta,
    _caminho_no,
    _nome_e_a_norma,
    _normas_do_nome,
    _verificar_ciclo,
    aplicar_lote,
    aposentar_no,
    aprovar,
    aprovar_propostas,
    carregar,
    chave_item,
    criar_no,
    desmapear,
    detectar_compostos,
    detectar_homonimos,
    fundir_nos,
    mapear,
    materia_do_no,
    mover_no,
    propor,
    rebaixar_materia,
    rejeitar,
    rejeitar_proposta,
    renomear_no,
    resolver_no,
    salvar,
)
from src.canonico import chave_regra


def test_criar_no():
    arvore = ArvoreMestre()
    m_id = criar_no(arvore, "materia", "Direito Administrativo", None)
    assert arvore.nos[m_id].nivel == "materia"
    assert arvore.nos[m_id].pai is None

    a_id = criar_no(arvore, "assunto", "Atos", m_id)
    assert arvore.nos[a_id].pai == m_id

    s_id = criar_no(arvore, "subassunto", "Conceito", a_id)
    assert arvore.nos[s_id].pai == a_id


def test_criar_no_invalido():
    arvore = ArvoreMestre()
    with pytest.raises(ArvoreInvalida, match="precisa de pai"):
        criar_no(arvore, "assunto", "Assunto sem pai", None)

    m_id = criar_no(arvore, "materia", "Mat", None)
    with pytest.raises(ArvoreInvalida, match="Matéria não pode ter pai"):
        criar_no(arvore, "materia", "Mat2", m_id)

    with pytest.raises(ArvoreInvalida, match="Nível do pai .* inválido"):
        criar_no(arvore, "subassunto", "Sub", m_id)


def test_renomear_no():
    arvore = ArvoreMestre()
    m_id = criar_no(arvore, "materia", "Dir", None)
    renomear_no(arvore, m_id, "Direito Penal")
    assert arvore.nos[m_id].nome == "Direito Penal"


def test_mover_no():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    m2 = criar_no(arvore, "materia", "M2", None)
    a1 = criar_no(arvore, "assunto", "A1", m1)

    mover_no(arvore, a1, m2)
    assert arvore.nos[a1].pai == m2

    with pytest.raises(ArvoreInvalida, match="Matéria não pode ser movida"):
        mover_no(arvore, m1, m2)


def test_mover_no_ciclo():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    a1 = criar_no(arvore, "assunto", "A1", m1)
    s1 = criar_no(arvore, "subassunto", "S1", a1)

    with pytest.raises(ArvoreInvalida, match="Ciclo detectado"):
        # This simulates a cycle though s1 -> a1 -> s1 is invalid by levels,
        # let's just test cycle directly if it was possible, but levels prevent it.
        # Actually it's prevented by levels first.
        arvore.nos[m1].pai = s1
        _verificar_ciclo(arvore, s1, m1)


def test_fundir_nos():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "Mat 1", None)
    m2 = criar_no(arvore, "materia", "Mat 2", None)
    a1 = criar_no(arvore, "assunto", "Assunto 1", m1)

    fundir_nos(arvore, m1, m2)

    assert arvore.nos[m1].status == "fundido"
    assert arvore.nos[m1].fundido_em == m2

    # Redirecionamento funciona
    assert resolver_no(arvore, m1) == m2

    # Filhos são atualizados
    assert arvore.nos[a1].pai == m2


def test_mapear_e_desmapear():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    m2 = criar_no(arvore, "materia", "M2", None)

    mapear(arvore, "item1", [m1, m2])
    assert len(arvore.mapeamentos["item1"]) == 2
    assert {m.no_id for m in arvore.mapeamentos["item1"]} == {m1, m2}

    desmapear(arvore, "item1", m1)
    assert len(arvore.mapeamentos["item1"]) == 1
    assert arvore.mapeamentos["item1"][0].no_id == m2

    desmapear(arvore, "item1", m2)
    assert "item1" not in arvore.mapeamentos


def test_mapear_no_fundido():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    m2 = criar_no(arvore, "materia", "M2", None)
    fundir_nos(arvore, m1, m2)

    # Mapear para m1 deve redirecionar para m2
    mapear(arvore, "item", [m1])
    assert arvore.mapeamentos["item"][0].no_id == m2


def test_resolver_no_multiplo():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    m2 = criar_no(arvore, "materia", "M2", None)
    m3 = criar_no(arvore, "materia", "M3", None)

    fundir_nos(arvore, m1, m2)
    fundir_nos(arvore, m2, m3)

    assert resolver_no(arvore, m1) == m3


def test_criar_no_repetido_levanta_erro():
    arvore = ArvoreMestre()
    criar_no(arvore, "materia", "M1", None)
    with pytest.raises(ArvoreInvalida, match="já existe"):
        criar_no(arvore, "materia", "M1", None)


def test_mover_sem_pai_levanta_erro():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    a1 = criar_no(arvore, "assunto", "A1", m1)
    with pytest.raises(ArvoreInvalida, match="novo pai"):
        mover_no(arvore, a1, None)


def test_mapear_humano_aprova_proposta_existente():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    arvore.mapeamentos["item"] = [Mapeamento(m1, "llm", "proposto")]
    mapear(arvore, "item", [m1])
    assert arvore.mapeamentos["item"] == [Mapeamento(m1, "humano", "aprovado")]


def test_aprovar_rejeitar_e_desmapear_exigem_apontamento():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    m2 = criar_no(arvore, "materia", "M2", None)
    arvore.mapeamentos["item"] = [Mapeamento(m1, "llm", "proposto")]
    for operacao in (aprovar, rejeitar, desmapear):
        with pytest.raises(ArvoreInvalida, match="não aponta"):
            operacao(arvore, "item", m2)
    rejeitar(arvore, "item", m1)
    assert arvore.mapeamentos["item"][0].status == "rejeitado"
    aprovar(arvore, "item", m1)
    assert arvore.mapeamentos["item"][0].status == "aprovado"


def test_aprovar_pelo_id_fundido():
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "M1", None)
    m2 = criar_no(arvore, "materia", "M2", None)
    arvore.mapeamentos["item"] = [Mapeamento(m1, "llm", "proposto")]
    fundir_nos(arvore, m1, m2)
    aprovar(arvore, "item", m2)
    assert arvore.mapeamentos["item"][0].status == "aprovado"


def test_chave_item():
    assert chave_item("direito") == "direito"
    assert chave_item(("direito", "atos", "conceito")) == "direito|atos|conceito"


def test_salvar_uma_linha_por_registro_e_ida_e_volta(tmp_path):
    arvore = ArvoreMestre()
    m1 = criar_no(arvore, "materia", "Matéria", None)
    a1 = criar_no(arvore, "assunto", "Assunto", m1)
    mapear(arvore, "materia", [m1])
    mapear(arvore, "materia|assunto", [a1])
    path = tmp_path / "arvore.json"
    salvar(arvore, path)
    linhas = path.read_text(encoding="utf-8").splitlines()
    # {, "nos": {, 2 nós, }, "mapeamentos": {, 2 itens, }, }
    assert len(linhas) == 10
    assert "Matéria" in path.read_text(encoding="utf-8")  # sem escape ASCII
    assert carregar(path) == arvore
    conteudo = path.read_text(encoding="utf-8")
    salvar(carregar(path), path)
    assert path.read_text(encoding="utf-8") == conteudo


def test_proposta_id_idempotente():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    p1 = propor(arv, "fundir", {"origem": m1, "destino": m2}, "regra", "fusão", "M1")
    p2 = propor(
        arv,
        "fundir",
        {"destino": m2, "origem": m1},
        "regra",
        "outra justificativa",
        "M1",
    )
    assert p1 == p2
    assert p1.startswith("P-")
    assert len(arv.propostas) == 1


def test_propor_e_aprovar_fundir():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    pid = propor(arv, "fundir", {"origem": m1, "destino": m2}, "regra", "fusão", "M1")
    assert arv.propostas[pid].status == "proposto"
    assert arv.nos[m1].status == "ativo"

    aprovar_propostas(arv, [pid])
    assert arv.propostas[pid].status == "aprovado"
    assert arv.nos[m1].status == "fundido"
    assert arv.nos[m1].fundido_em == m2


def test_propor_e_aprovar_mover():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    pid = propor(arv, "mover", {"no": a1, "pai": m2}, "humano", "mover A1", "M1")
    assert arv.nos[a1].pai == m1

    aprovar_propostas(arv, [pid])
    assert arv.propostas[pid].status == "aprovado"
    assert arv.nos[a1].pai == m2


def test_propor_e_aprovar_criar():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    pid = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": m1, "nome": "Novo Assunto"},
        "llm",
        "criar assunto",
        "M1",
    )
    novo_id = arv.propostas[pid].args["id"]
    assert novo_id in arv.nos
    assert arv.nos[novo_id].status == "proposto"

    aprovar_propostas(arv, [pid])
    assert arv.propostas[pid].status == "aprovado"
    assert arv.nos[novo_id].status == "ativo"


def test_propor_e_rejeitar_criar():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    pid = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": m1, "nome": "Descartável"},
        "llm",
        "criar e rejeitar",
        "M1",
    )
    novo_id = arv.propostas[pid].args["id"]
    assert novo_id in arv.nos
    rejeitar_proposta(arv, pid)
    assert arv.propostas[pid].status == "rejeitado"
    assert novo_id not in arv.nos


def test_rejeitar_criar_mantem_no_se_referenciado():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    pid_c = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": m1, "nome": "Pai Proposto"},
        "llm",
        "criar pai",
        "M1",
    )
    novo_id = arv.propostas[pid_c].args["id"]
    criar_no(arv, "subassunto", "S1", novo_id)

    rejeitar_proposta(arv, pid_c)
    assert arv.propostas[pid_c].status == "rejeitado"
    # S1 ainda tem novo_id como pai, então não é apagado
    assert novo_id in arv.nos


def test_propor_e_aprovar_remapear():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    a2 = criar_no(arv, "assunto", "A2", m1)
    a3 = criar_no(arv, "assunto", "A3", m1)
    mapear(arv, "item1", [a1])

    pid = propor(
        arv,
        "remapear",
        {"item": "item1", "de": a1, "para": [a2, a3]},
        "regra",
        "remapeamento para irmãos",
        "M1",
    )
    assert len(arv.mapeamentos["item1"]) == 1
    assert arv.mapeamentos["item1"][0].no_id == a1

    aprovar_propostas(arv, [pid])
    assert arv.propostas[pid].status == "aprovado"
    nos_mapeados = {m.no_id for m in arv.mapeamentos["item1"]}
    assert nos_mapeados == {a2, a3}


def test_propor_e_aprovar_aposentar():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    pid = propor(arv, "aposentar", {"no": a1}, "regra", "aposentar sem uso", "M1")
    assert arv.nos[a1].status == "ativo"

    aprovar_propostas(arv, [pid])
    assert arv.propostas[pid].status == "aprovado"
    assert arv.nos[a1].status == "aposentado"


def test_proposta_invalida_nao_gravada():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    with pytest.raises(ArvoreInvalida, match="não existe"):
        propor(
            arv,
            "fundir",
            {"origem": m1, "destino": "NAO-EXISTE"},
            "regra",
            "teste",
            "M1",
        )
    assert len(arv.propostas) == 0

    with pytest.raises(ArvoreInvalida, match="Nível .* inválido"):
        propor(
            arv,
            "criar",
            {"nivel": "invalido", "pai": m1, "nome": "X"},
            "llm",
            "teste",
            "M1",
        )
    assert len(arv.propostas) == 0


def test_lote_tudo_ou_nada():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    p_valida = propor(
        arv, "fundir", {"origem": m1, "destino": m2}, "regra", "valida", "M1"
    )

    p_invalida = Proposta(
        id="P-invalida",
        tipo="mover",
        args={"no": a1, "pai": "INEXISTENTE"},
        origem="humano",
        justificativa="invalida",
        status="proposto",
        materia="M1",
    )
    arv.propostas["P-invalida"] = p_invalida

    with pytest.raises(ArvoreInvalida):
        aprovar_propostas(arv, [p_valida, "P-invalida"])

    # Tudo ou nada: m1 não foi fundido e p_valida continua proposto
    assert arv.nos[m1].status == "ativo"
    assert arv.propostas[p_valida].status == "proposto"


def test_criar_e_mover_no_mesmo_lote():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    p_criar = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": m1, "nome": "Novo Assunto"},
        "llm",
        "criar assunto",
        "M1",
    )
    novo_id = arv.propostas[p_criar].args["id"]
    p_mover = propor(
        arv, "mover", {"no": novo_id, "pai": m2}, "humano", "mover novo", "M1"
    )

    aprovar_propostas(arv, [p_criar, p_mover])
    assert arv.nos[novo_id].status == "ativo"
    assert arv.nos[novo_id].pai == m2


def test_aposentar_recusado_com_filho_ou_mapeamento():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    criar_no(arv, "subassunto", "S1", a1)

    # Recusado porque tem filho ativo S1
    with pytest.raises(ArvoreInvalida, match="filhos ativos"):
        aposentar_no(arv, a1)

    # Sem filhos, mas com mapeamento aprovado
    a2 = criar_no(arv, "assunto", "A2", m1)
    mapear(arv, "item", [a2])
    with pytest.raises(ArvoreInvalida, match="mapeamento aprovado"):
        aposentar_no(arv, a2)

    # Desmapeado, agora pode ser aposentado
    desmapear(arv, "item", a2)
    aposentar_no(arv, a2)
    assert arv.nos[a2].status == "aposentado"


def test_operacoes_recusam_alvo_aposentado():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    a2 = criar_no(arv, "assunto", "A2", m1)
    aposentar_no(arv, a1)

    # Mapear para aposentado falha
    with pytest.raises(ArvoreInvalida, match="aposentado"):
        mapear(arv, "item", [a1])

    # Mover para pai aposentado falha
    s1 = criar_no(arv, "subassunto", "S1", a2)
    with pytest.raises(ArvoreInvalida, match="aposentado"):
        mover_no(arv, s1, a1)

    # Mover nó aposentado falha
    with pytest.raises(ArvoreInvalida, match="aposentado"):
        mover_no(arv, a1, m1)

    # Fundir com destino aposentado falha
    with pytest.raises(ArvoreInvalida, match="aposentado"):
        fundir_nos(arv, a2, a1)

    # Fundir nó aposentado falha
    with pytest.raises(ArvoreInvalida, match="aposentado"):
        fundir_nos(arv, a1, a2)


def test_salvar_com_propostas_ida_e_volta(tmp_path):
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "Direito", None)
    m2 = criar_no(arv, "materia", "Administração", None)
    propor(arv, "fundir", {"origem": m1, "destino": m2}, "regra", "teste", "M1")
    path = tmp_path / "arvore_com_propostas.json"
    salvar(arv, path)

    carregada = carregar(path)
    assert carregada == arv
    assert len(carregada.propostas) == 1
    [p] = carregada.propostas.values()
    assert p.tipo == "fundir"
    assert p.status == "proposto"


def test_detectar_compostos_fixture():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "Direito Constitucional", None, id_override="M-DC")
    a1 = criar_no(arv, "assunto", "Administração Pública", m1, id_override="A-ADM")
    criar_no(arv, "subassunto", "Disposições gerais", a1, id_override="S-DG")
    criar_no(arv, "subassunto", "Servidores públicos", a1, id_override="S-SP")
    s_comp = criar_no(
        arv,
        "subassunto",
        "Disposições gerais, servidores públicos",
        a1,
        id_override="S-COMP",
    )
    mapear(arv, "item|composto", [s_comp])

    detectados = detectar_compostos(arv)
    assert detectados == {"S-COMP": ["S-DG", "S-SP"]}
    # Verifica que remapear e aposentar foram propostos
    props = list(arv.propostas.values())
    tipos = {p.tipo for p in props}
    assert "remapear" in tipos
    assert "aposentar" in tipos


def test_detectar_compostos_dados_reais():
    # Os 2 compostos da 5B.2 foram aposentados e não voltam a ser detectados;
    # o que a regra achar agora tem de ter cada parte num irmão ativo.
    arv = carregar()
    detectados = detectar_compostos(arv)
    assert not {"A-4529f205f7", "S-7b3b2a86ce"} & detectados.keys()
    assert arv.nos["A-4529f205f7"].status == "aposentado"
    assert arv.nos["S-7b3b2a86ce"].status == "aposentado"
    for composto, irmaos in detectados.items():
        pai = resolver_no(arv, arv.nos[composto].pai)
        for irmao in irmaos:
            assert arv.nos[irmao].status == "ativo"
            assert resolver_no(arv, arv.nos[irmao].pai) == pai


def test_detectar_homonimos_propoe_fusao_no_irmao_mais_usado():
    arv = ArvoreMestre()
    m = criar_no(arv, "materia", "Direito", None, id_override="M-1")
    a = criar_no(arv, "assunto", "Administração pública", m, id_override="A-1")
    s1 = criar_no(arv, "subassunto", "Disposições gerais", a, id_override="S-1")
    s2 = criar_no(arv, "subassunto", "Disposições gerais.", a, id_override="S-2")
    criar_no(arv, "subassunto", "Servidores públicos", a, id_override="S-3")
    mapear(arv, "direito|adm|dg 1", [s2])
    mapear(arv, "direito|adm|dg 2", [s2])
    mapear(arv, "direito|adm|dg 3", [s1])

    detectados = detectar_homonimos(arv)

    assert detectados == {"S-2": ["S-1"]}
    (prop,) = arv.propostas.values()
    assert (prop.tipo, prop.origem, prop.status) == ("fundir", "regra", "proposto")
    assert prop.args == {"origem": "S-1", "destino": "S-2"}
    aprovar_propostas(arv, [prop.id])
    assert resolver_no(arv, "S-1") == "S-2"
    assert detectar_homonimos(arv) == {}


def test_detectar_homonimos_ignora_mesmo_nome_em_pais_diferentes():
    arv = ArvoreMestre()
    m = criar_no(arv, "materia", "Direito", None, id_override="M-1")
    a1 = criar_no(arv, "assunto", "Poder Judiciário", m, id_override="A-1")
    a2 = criar_no(arv, "assunto", "Poder Legislativo", m, id_override="A-2")
    criar_no(arv, "subassunto", "Disposições gerais", a1, id_override="S-1")
    criar_no(arv, "subassunto", "Disposições gerais", a2, id_override="S-2")

    assert detectar_homonimos(arv) == {}
    assert arv.propostas == {}


def test_propor_alternativas_aposentar_e_mover():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    a2 = criar_no(arv, "assunto", "A2", m1)

    p_aposentar = propor(
        arv, "aposentar", {"no": a1}, "regra", "aposentar sem uso", "M1"
    )
    p_mover = propor(
        arv, "mover", {"no": a1, "pai": m2}, "llm", "alternativa mover", "M1"
    )
    p_fundir = propor(
        arv, "fundir", {"origem": a1, "destino": a2}, "llm", "alternativa fundir", "M1"
    )

    assert p_aposentar in arv.propostas
    assert p_mover in arv.propostas
    assert p_fundir in arv.propostas
    assert arv.propostas[p_aposentar].status == "proposto"
    assert arv.propostas[p_mover].status == "proposto"
    assert arv.propostas[p_fundir].status == "proposto"


def test_propor_alternativas_fundir_concorrente():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    m3 = criar_no(arv, "materia", "M3", None)

    p1 = propor(arv, "fundir", {"origem": m1, "destino": m2}, "llm", "opcao 1")
    p2 = propor(arv, "fundir", {"origem": m1, "destino": m3}, "llm", "opcao 2")

    assert p1 in arv.propostas
    assert p2 in arv.propostas


def test_aprovar_propostas_fora_de_ordem_com_dependencia():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    s1 = criar_no(arv, "subassunto", "S1", a1)
    s2 = criar_no(arv, "subassunto", "S2", a1)
    s_comp = criar_no(arv, "subassunto", "S_COMP", a1)
    mapear(arv, "item|teste", [s_comp])

    p_rem = propor(
        arv,
        "remapear",
        {"item": "item|teste", "de": s_comp, "para": [s1, s2]},
        "regra",
        "remapear",
        "M1",
    )
    p_apo = propor(arv, "aposentar", {"no": s_comp}, "regra", "aposentar", "M1")

    # Passa aposentar antes de remapear no lote
    aprovados = aprovar_propostas(arv, [p_apo, p_rem])
    assert set(aprovados) == {p_apo, p_rem}
    assert arv.nos[s_comp].status == "aposentado"
    assert arv.propostas[p_apo].status == "aprovado"
    assert arv.propostas[p_rem].status == "aprovado"


def test_aprovar_proposta_ja_aprovada_ou_rejeitada_falha():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    p = propor(arv, "fundir", {"origem": m1, "destino": m2}, "regra", "fusao", "M1")

    aprovar_propostas(arv, [p])
    assert arv.propostas[p].status == "aprovado"

    with pytest.raises(ArvoreInvalida, match="já foi aprovada"):
        aprovar_propostas(arv, [p])

    with pytest.raises(ArvoreInvalida, match="já foi aprovada"):
        rejeitar_proposta(arv, p)


def test_aposentar_no_fundido_falha():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    fundir_nos(arv, m1, m2)

    with pytest.raises(ArvoreInvalida, match="Nó fundido"):
        aposentar_no(arv, m1)
    # Garante que m2 não foi afetado
    assert arv.nos[m2].status == "ativo"


def test_aposentar_com_filho_proposto_falha():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    criar_no(arv, "assunto", "A_PROP", m1, status="proposto")

    with pytest.raises(ArvoreInvalida, match="filhos ativos/propostos"):
        aposentar_no(arv, m1)


def test_aprovar_mapeamento_para_aposentado_falha():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    # Mapeamento proposto
    mapear(arv, "item|teste", [a1], status="proposto")
    aposentar_no(arv, a1)

    with pytest.raises(ArvoreInvalida, match="nó aposentado"):
        aprovar(arv, "item|teste", a1)


def test_criar_no_sob_aposentado_falha():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    aposentar_no(arv, a1)

    with pytest.raises(ArvoreInvalida, match="sob o nó aposentado"):
        criar_no(arv, "subassunto", "S1", a1)


def test_propor_origem_invalida_falha():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)

    with pytest.raises(ArvoreInvalida, match="Origem .* inválida"):
        propor(
            arv,
            "fundir",
            {"origem": m1, "destino": m2},
            "invalido",  # type: ignore
            "justificativa",
        )


def test_propor_argumentos_obrigatorios_faltantes():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)

    with pytest.raises(ArvoreInvalida, match="nome.*obrigatório"):
        propor(arv, "criar", {"nivel": "assunto", "pai": m1}, "llm", "just")

    with pytest.raises(ArvoreInvalida, match="origem.*destino.*obrigatórios"):
        propor(arv, "fundir", {"origem": m1}, "regra", "just")

    with pytest.raises(ArvoreInvalida, match="no.*pai.*obrigatórios"):
        propor(arv, "mover", {"no": a1}, "humano", "just")

    with pytest.raises(ArvoreInvalida, match="item.*de.*para.*obrigatórios"):
        propor(arv, "remapear", {"item": "x", "de": a1}, "regra", "just")

    with pytest.raises(ArvoreInvalida, match="Argumento 'no' obrigatório"):
        propor(arv, "aposentar", {}, "regra", "just")


def test_propor_canonicalizacao_equivalente():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    a2 = criar_no(arv, "assunto", "A2", m1)
    mapear(arv, "item", [a1])

    p1 = propor(
        arv,
        "remapear",
        {"item": "item", "de": a1, "para": a2},
        "regra",
        "remapeamento str",
        "M1",
    )
    p2 = propor(
        arv,
        "remapear",
        {"item": "item", "de": a1, "para": [a2]},
        "regra",
        "remapeamento lista",
        "M1",
    )
    assert p1 == p2
    assert len(arv.propostas) == 1

    p_apo1 = propor(arv, "aposentar", {"no": a2}, "regra", "apo1", "M1")
    p_apo2 = propor(arv, "aposentar", {"no_id": a2}, "regra", "apo2", "M1")
    assert p_apo1 == p_apo2


def test_aprovar_propostas_com_ids_duplicados():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    a2 = criar_no(arv, "assunto", "A2", m1)
    mapear(arv, "item", [a1])

    p_criar = propor(
        arv,
        "criar",
        {"nivel": "subassunto", "pai": a1, "nome": "Sub"},
        "llm",
        "criar",
        "M1",
    )
    p_rem = propor(
        arv,
        "remapear",
        {"item": "item", "de": a1, "para": [a2]},
        "regra",
        "rem",
        "M1",
    )

    # Duplicatas no lote não devem causar conflito de estado interno
    aprovados = aprovar_propostas(arv, [p_criar, p_criar, p_rem, p_rem])
    assert set(aprovados) == {p_criar, p_rem}
    assert arv.propostas[p_criar].status == "aprovado"
    assert arv.propostas[p_rem].status == "aprovado"


def test_rejeitar_proposta_limpa_orfaos_em_cadeia():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    p_criar = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": m1, "nome": "Assunto Temporario"},
        "llm",
        "criar",
        "M1",
    )
    no_temp = arv.propostas[p_criar].args["id"]

    a1 = criar_no(arv, "assunto", "A1", m1)
    s1 = criar_no(arv, "subassunto", "S1", a1)
    p_mover = propor(
        arv, "mover", {"no": s1, "pai": no_temp}, "llm", "mover para temp", "M1"
    )

    # Rejeitar criação primeiro: o nó ainda é referenciado por p_mover, logo permanece
    rejeitar_proposta(arv, p_criar)
    assert no_temp in arv.nos

    # Rejeitar p_mover em seguida: agora o nó temp ficou sem referências e deve ser removido
    rejeitar_proposta(arv, p_mover)
    assert no_temp not in arv.nos


def test_propor_aposentar_com_filho_proposto_aposentar():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    s1 = criar_no(arv, "subassunto", "S1", a1)

    p_apo_filho = propor(arv, "aposentar", {"no": s1}, "regra", "apo filho", "M1")
    p_apo_pai = propor(arv, "aposentar", {"no": a1}, "regra", "apo pai", "M1")

    assert p_apo_filho in arv.propostas
    assert p_apo_pai in arv.propostas


def test_rejeitar_proposta_limpa_orfaos_cadeia_multinivel():
    arv = ArvoreMestre()
    m = criar_no(arv, "materia", "M", None)
    pa = propor(
        arv, "criar", {"nivel": "assunto", "pai": m, "nome": "A"}, "llm", "just"
    )
    nid_a = arv.propostas[pa].args["id"]
    pb = propor(
        arv, "criar", {"nivel": "subassunto", "pai": nid_a, "nome": "B"}, "llm", "just"
    )
    nid_b = arv.propostas[pb].args["id"]

    s_existente = criar_no(arv, "assunto", "A_ex", m)
    pc = propor(arv, "mover", {"no": nid_b, "pai": s_existente}, "llm", "just")

    assert nid_a in arv.nos
    assert nid_b in arv.nos

    rejeitar_proposta(arv, pa)
    rejeitar_proposta(arv, pb)
    rejeitar_proposta(arv, pc)

    assert nid_a not in arv.nos
    assert nid_b not in arv.nos


def test_aposentar_no_com_filho_resolvido_por_fusao_em_cadeia_falha():
    arv = ArvoreMestre()
    m = criar_no(arv, "materia", "M", None)
    a1 = criar_no(arv, "assunto", "A1", m)
    a2 = criar_no(arv, "assunto", "A2", m)
    a3 = criar_no(arv, "assunto", "A3", m)
    s = criar_no(arv, "subassunto", "S", a1)
    fundir_nos(arv, a1, a2)
    fundir_nos(arv, a2, a3)
    # Simula estado em que pai aponta para a1 na hierarquia resolvida
    arv.nos[s].pai = a1

    with pytest.raises(ArvoreInvalida, match="filhos ativos/propostos"):
        aposentar_no(arv, a3)


def test_proposta_dataclass_materia_opcional_retrocompatibilidade():
    p_dict = {
        "id": "P-123",
        "tipo": "aposentar",
        "args": {"no": "S-1"},
        "origem": "regra",
        "justificativa": "teste",
        "status": "proposto",
    }
    prop = Proposta(**p_dict)
    assert prop.materia == ""
    assert prop.id == "P-123"


def test_executar_operacao_missing_keys_raises_arvore_invalida():
    from src.arvore import _executar_operacao

    arv = ArvoreMestre()
    with pytest.raises(ArvoreInvalida, match="origem.*destino"):
        _executar_operacao(arv, "fundir", {"origem": "X"})
    with pytest.raises(ArvoreInvalida, match="no.*pai"):
        _executar_operacao(arv, "mover", {"no": "X"})
    with pytest.raises(ArvoreInvalida, match="nivel.*nome"):
        _executar_operacao(arv, "criar", {"nivel": "assunto"})
    with pytest.raises(ArvoreInvalida, match="item.*de.*para"):
        _executar_operacao(arv, "remapear", {"item": "X", "de": "Y"})
    with pytest.raises(ArvoreInvalida, match="Argumento 'no' obrigatório"):
        _executar_operacao(arv, "aposentar", {})


def test_inferir_materia_proposta_remapear_fallback_destinos():
    arv = ArvoreMestre()
    m = criar_no(arv, "materia", "Mat", None)
    a = criar_no(arv, "assunto", "Assunto", m)
    s = criar_no(arv, "subassunto", "Sub", a)
    mapear(arv, "item|teste", [s])

    p = propor(
        arv,
        "remapear",
        {"item": "item|teste", "de": s, "para": [s]},
        "regra",
        "teste",
    )
    assert arv.propostas[p].materia == m


def test_remover_no_proposto_se_orfao_respeita_aliases_fundidos():
    from src.arvore import _remover_no_proposto_se_orfao

    arv = ArvoreMestre()
    m = criar_no(arv, "materia", "M", None)
    p_criar = propor(
        arv, "criar", {"nivel": "assunto", "pai": m, "nome": "Temp"}, "llm", "just"
    )
    nid_temp = arv.propostas[p_criar].args["id"]

    a1 = criar_no(arv, "assunto", "A1", m)
    a2 = criar_no(arv, "assunto", "A2", m)
    fundir_nos(arv, a1, a2)
    # Referencia via alias a1 que resolve para a2, e depois a2 aponta para nid_temp
    arv.nos[a2].pai = nid_temp
    _remover_no_proposto_se_orfao(arv, nid_temp)
    assert nid_temp in arv.nos


def test_arvore_curada_sem_irmaos_homonimos():
    """Guarda da curadoria: dois irmãos ativos com a mesma `chave_regra` duplicam o
    filtro do site. Se falhar, funda com `curar_arvore.py --fundir ORIGEM:DESTINO`."""
    assert detectar_homonimos(carregar()) == {}


def test_arvore_curada_sem_disciplinas_homonimas():
    """`detectar_homonimos` só olha nós com pai; a disciplina é a raiz, então a
    checagem de nome repetido entre disciplinas fica aqui."""
    nomes: dict[str, list[str]] = {}
    for no in carregar().nos.values():
        if no.status == "ativo" and no.nivel == "materia":
            nomes.setdefault(chave_regra(no.nome).chave, []).append(no.id)
    assert {k: v for k, v in nomes.items() if len(v) > 1} == {}


# Normas consolidadas no nó único (KAN-64). A lista só cresce quando o dono
# consolida uma norma nova; não acrescente norma aqui para "passar" um teste.
NORMAS_CONSOLIDADAS = {
    "LGPD": {("lei", "13709")},
    "LAI": {("lei", "12527")},
    "LRF": {("lei complementar", "101")},
}


def test_normas_consolidadas_em_um_no_so():
    """Um conceito com nome próprio, um lugar (ADR-030, KAN-64): cada norma
    consolidada tem exatamente um nó ativo fora da matéria."""
    arv = carregar(ARVORE_PADRAO)
    falhas = {}
    for sigla, normas in NORMAS_CONSOLIDADAS.items():
        nos = [
            no
            for no in arv.nos.values()
            if no.status == "ativo"
            and no.nivel != "materia"
            and _nome_e_a_norma(no.nome)
            and _normas_do_nome(no.nome) & normas
        ]
        if len(nos) != 1:
            falhas[sigla] = [f"{no.id} ({_caminho_no(arv, no.id)})" for no in nos]
    assert not falhas, f"norma em mais de um lugar ou sumida: {falhas}"


def _arv_entre_niveis():
    arv = ArvoreMestre()
    m1 = criar_no(arv, "materia", "M1", None)
    m2 = criar_no(arv, "materia", "M2", None)
    a1 = criar_no(arv, "assunto", "A1", m1)
    a2 = criar_no(arv, "assunto", "A2", m2)
    s1 = criar_no(arv, "subassunto", "S1", a1)
    return arv, m1, m2, a1, a2, s1


def test_fundir_subassunto_sem_filhos_em_assunto_de_outra_materia():
    arv, _, _, a1, a2, s1 = _arv_entre_niveis()
    mapear(arv, "item", [s1])
    fundir_nos(arv, s1, a2)
    assert arv.nos[s1].status == "fundido"
    assert arv.nos[s1].fundido_em == a2
    assert resolver_no(arv, s1) == a2
    assert arv.nos[a1].status == "ativo"


def test_fundir_assunto_sem_filhos_em_subassunto():
    arv, _, m2, a1, a2, s1 = _arv_entre_niveis()
    s2 = criar_no(arv, "subassunto", "S2", a2)
    arv.nos[s1].status = "aposentado"  # a1 fica sem filhos ativos
    fundir_nos(arv, a1, s2)
    assert arv.nos[a1].status == "fundido"
    assert resolver_no(arv, a1) == s2


def test_fundir_entre_niveis_com_filho_ativo_falha_sem_gravar():
    arv, _, _, a1, a2, s1 = _arv_entre_niveis()
    s2 = criar_no(arv, "subassunto", "S2", a2)
    with pytest.raises(ArvoreInvalida, match="sem filhos ativos"):
        fundir_nos(arv, a1, s2)
    assert arv.nos[a1].status == "ativo" and arv.nos[a1].fundido_em is None
    assert arv.nos[s1].pai == a1


def test_fundir_filho_no_proprio_pai_sem_filhos():
    arv, _, _, a1, _, s1 = _arv_entre_niveis()
    fundir_nos(arv, s1, a1)
    assert arv.nos[s1].status == "fundido"
    assert resolver_no(arv, s1) == a1


def test_fundir_materia_com_outro_nivel_falha():
    arv, m1, _, a1, _, _ = _arv_entre_niveis()
    m3 = criar_no(arv, "materia", "M3", None)
    with pytest.raises(ArvoreInvalida, match="Matéria"):
        fundir_nos(arv, m3, a1)
    with pytest.raises(ArvoreInvalida, match="Matéria"):
        fundir_nos(arv, a1, m1)
    assert arv.nos[m3].status == "ativo"


def test_fundir_entre_niveis_destino_nao_ativo_falha():
    arv, _, _, _, a2, s1 = _arv_entre_niveis()
    arv.nos[a2].status = "proposto"
    with pytest.raises(ArvoreInvalida, match="ativos"):
        fundir_nos(arv, s1, a2)
    assert arv.nos[s1].status == "ativo"


def test_proposta_fundir_entre_niveis_valida_e_aprova_pela_mesma_regra():
    arv, _, _, a1, a2, s1 = _arv_entre_niveis()
    pid = propor(arv, "fundir", {"origem": s1, "destino": a2}, "regra", "x", "")
    assert arv.nos[s1].status == "ativo"
    s2 = criar_no(arv, "subassunto", "S2", a2)
    with pytest.raises(ArvoreInvalida):  # a1 tem filho ativo: nem propõe
        propor(arv, "fundir", {"origem": a1, "destino": s2}, "regra", "x", "")
    aprovar_propostas(arv, [pid])
    assert arv.propostas[pid].status == "aprovado"
    assert resolver_no(arv, s1) == a2


def _arvore_rebaixar():
    arv = ArvoreMestre()
    criar_no(arv, "materia", "TI", None, id_override="M-TI")
    criar_no(arv, "assunto", "Desenvolvimento", "M-TI", id_override="A-DEV")
    criar_no(arv, "subassunto", "Python", "A-DEV", id_override="S-PY")
    criar_no(arv, "materia", "DevOps", None, id_override="M-OPS")
    criar_no(arv, "assunto", "Kubernetes", "M-OPS", id_override="A-K8S")
    criar_no(arv, "subassunto", "Pods", "A-K8S", id_override="S-POD")
    criar_no(arv, "subassunto", "Python no CI", "A-K8S", id_override="S-PYCI")
    criar_no(arv, "assunto", "Git", "M-OPS", id_override="A-GIT")
    mapear(arv, "devops|git", ["A-GIT"])
    return arv


def test_rebaixar_materia_assuntos_viram_subassuntos():
    arv = _arvore_rebaixar()
    rebaixar_materia(arv, "M-OPS", "A-DEV", {"S-PYCI": "S-PY"})

    assert (arv.nos["A-K8S"].nivel, arv.nos["A-K8S"].pai) == ("subassunto", "A-DEV")
    assert (arv.nos["A-GIT"].nivel, arv.nos["A-GIT"].pai) == ("subassunto", "A-DEV")
    assert arv.nos["S-POD"].fundido_em == "A-K8S"
    assert arv.nos["S-PYCI"].fundido_em == "S-PY"
    assert (arv.nos["M-OPS"].status, arv.nos["M-OPS"].fundido_em) == (
        "fundido",
        "A-DEV",
    )
    assert materia_do_no(arv, "A-GIT") == "M-TI"
    assert materia_do_no(arv, "S-POD") == "M-TI"
    assert resolver_no(arv, "M-OPS") == "A-DEV"
    assert arv.mapeamentos["devops|git"][0].no_id == "A-GIT"


def test_rebaixar_materia_erro_nao_altera_nada():
    arv = _arvore_rebaixar()
    antes = copy.deepcopy(arv)
    with pytest.raises(ArvoreInvalida, match="não é subassunto que fica"):
        rebaixar_materia(arv, "M-OPS", "A-DEV", {"S-PYCI": "S-POD"})
    assert arv == antes
    with pytest.raises(ArvoreInvalida, match="não é assunto ativo"):
        rebaixar_materia(arv, "M-OPS", "M-TI")
    with pytest.raises(ArvoreInvalida, match="está dentro de"):
        rebaixar_materia(arv, "M-OPS", "A-K8S")
    with pytest.raises(ArvoreInvalida, match="não é subassunto ativo de"):
        rebaixar_materia(arv, "M-OPS", "A-DEV", {"S-PY": "A-GIT"})
    assert arv == antes


def test_rebaixar_materia_recusa_no_proposto():
    arv = _arvore_rebaixar()
    criar_no(arv, "subassunto", "Helm", "A-K8S", status="proposto", id_override="S-H")
    with pytest.raises(ArvoreInvalida, match="nós propostos: S-H"):
        rebaixar_materia(arv, "M-OPS", "A-DEV")


def test_fundir_continua_recusando_materia_entre_niveis():
    arv = _arvore_rebaixar()
    with pytest.raises(ArvoreInvalida, match="Matéria não funde"):
        fundir_nos(arv, "M-OPS", "A-DEV")


def test_aplicar_lote_com_apelido_e_tudo_ou_nada():
    arv = _arvore_rebaixar()
    feitas = aplicar_lote(
        arv,
        [
            {
                "tipo": "criar",
                "apelido": "@infra",
                "args": {"nivel": "assunto", "nome": "Infraestrutura", "pai": "M-TI"},
            },
            {"tipo": "rebaixar", "args": {"materia": "M-OPS", "destino": "@infra"}},
            {
                "tipo": "renomear",
                "args": {"no": "M-TI", "nome": "Tecnologia da Informação"},
            },
        ],
    )
    assert len(feitas) == 3
    infra = resolver_no(arv, "M-OPS")
    assert arv.nos[infra].nome == "Infraestrutura"
    assert arv.nos["A-GIT"].pai == infra
    assert arv.nos["M-TI"].nome == "Tecnologia da Informação"

    arv = _arvore_rebaixar()
    antes = copy.deepcopy(arv)
    with pytest.raises(ArvoreInvalida, match="Operação 2 .*@nada"):
        aplicar_lote(
            arv,
            [
                {"tipo": "renomear", "args": {"no": "M-TI", "nome": "X"}},
                {"tipo": "rebaixar", "args": {"materia": "M-OPS", "destino": "@nada"}},
            ],
        )
    assert arv == antes
