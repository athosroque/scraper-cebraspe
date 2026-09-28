import pytest

from src.arvore import (
    ArvoreInvalida,
    ArvoreMestre,
    _verificar_ciclo,
    criar_no,
    desmapear,
    fundir_nos,
    mapear,
    mover_no,
    renomear_no,
    resolver_no,
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
