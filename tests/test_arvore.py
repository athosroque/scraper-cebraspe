import pytest

from src.arvore import (
    ArvoreInvalida,
    ArvoreMestre,
    Mapeamento,
    Proposta,
    _verificar_ciclo,
    aposentar_no,
    aprovar,
    aprovar_propostas,
    carregar,
    chave_item,
    criar_no,
    desmapear,
    detectar_compostos,
    fundir_nos,
    mapear,
    mover_no,
    propor,
    rejeitar,
    rejeitar_proposta,
    renomear_no,
    resolver_no,
    salvar,
)


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
    arv = carregar()
    detectados = detectar_compostos(arv)
    assert set(detectados.keys()) == {"A-4529f205f7", "S-7b3b2a86ce"}
    assert detectados["A-4529f205f7"] == ["A-2261b82645", "A-91e52e6c2e"]
    assert detectados["S-7b3b2a86ce"] == ["S-10973fad79", "S-de2a8684f9"]
