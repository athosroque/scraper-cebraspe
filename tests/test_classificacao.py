"""Testes do módulo canônico de classificação de questões (Etapa 5D)."""

from pathlib import Path

import pytest

from src import arvore
from src.classificacao import (
    ApontamentoQuestao,
    ClassificacaoInvalida,
    ClassificacaoQuestoes,
    RegistroQuestao,
    aprovar_apontamento,
    aprovar_lote,
    calcular_hash_enunciado,
    carregar,
    chave_questao,
    mapear_questao,
    rejeitar_apontamento,
    salvar,
    validar_registro,
)


@pytest.fixture
def arvore_teste() -> arvore.ArvoreMestre:
    arv = arvore.ArvoreMestre()
    arvore.criar_no(
        arv, "materia", "DIREITO ADMINISTRATIVO", None, id_override="NM-ADM"
    )
    arvore.criar_no(
        arv, "assunto", "Atos Administrativos", "NM-ADM", id_override="NA-ATOS"
    )
    arvore.criar_no(
        arv, "subassunto", "Anulação e revogação", "NA-ATOS", id_override="NS-ANUL"
    )
    arvore.criar_no(
        arv, "subassunto", "Competência e motivos", "NA-ATOS", id_override="NS-COMP"
    )

    arvore.criar_no(
        arv, "assunto", "Serviços Públicos", "NM-ADM", id_override="NA-SERV"
    )
    # Nó fundido
    arvore.criar_no(
        arv, "subassunto", "Delegação e concessão", "NA-SERV", id_override="NS-CONC"
    )
    arvore.criar_no(
        arv, "subassunto", "Concessões", "NA-SERV", id_override="NS-CONC-NOVO"
    )
    arvore.fundir_nos(arv, "NS-CONC", "NS-CONC-NOVO")

    # Nó aposentado
    arvore.criar_no(arv, "assunto", "Tema obsoleto", "NM-ADM", id_override="NA-OBS")
    arvore.aposentar_no(arv, "NA-OBS")
    return arv


def test_chave_questao():
    # Objetiva
    assert chave_questao("PF_25_ADM", "094_PF_CB1_01", 1) == "PF_25_ADM|094_PF_CB1_01|1"
    assert (
        chave_questao("IBAMA_25", "057_IBAMA_001_01", "55")
        == "IBAMA_25|057_IBAMA_001_01|55"
    )

    # Discursiva
    assert (
        chave_questao("PF_25_ADM", "094_PF_014_DISC", 1, discursiva=True)
        == "PF_25_ADM|094_PF_014_DISC|D1"
    )
    # Já com D
    assert (
        chave_questao("PF_25_ADM", "094_PF_014_DISC", "D2", discursiva=True)
        == "PF_25_ADM|094_PF_014_DISC|D2"
    )


def test_calcular_hash_enunciado():
    h1 = calcular_hash_enunciado(
        "O ato administrativo goza de presunção de legitimidade."
    )
    h2 = calcular_hash_enunciado(
        "  O ato administrativo goza de presunção de legitimidade. \n"
    )
    assert h1 == h2
    assert len(h1) == 40


def test_serializacao_desserializacao_roundtrip(tmp_path: Path):
    path = tmp_path / "classificacao.json"
    cq = ClassificacaoQuestoes()
    cq.registros["PF_25_ADM|094_PF_CB1_01|2"] = RegistroQuestao(
        chave="PF_25_ADM|094_PF_CB1_01|2",
        hash_enunciado="hash2",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(
                no_id="NS-COMP",
                papel="principal",
                confianca="media",
                fora_do_edital=False,
                origem="llm",
                status="proposto",
            ),
            ApontamentoQuestao(
                no_id="NS-ANUL",
                papel="secundario",
                confianca="baixa",
                fora_do_edital=True,
                origem="llm",
                status="proposto",
            ),
        ],
    )
    cq.registros["PF_25_ADM|094_PF_CB1_01|1"] = RegistroQuestao(
        chave="PF_25_ADM|094_PF_CB1_01|1",
        hash_enunciado="hash1",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(
                no_id="NS-ANUL",
                papel="principal",
                confianca="alta",
                fora_do_edital=False,
                origem="llm",
                status="proposto",
            )
        ],
    )
    cq.registros["PF_25_ADM|094_PF_CB1_01|3"] = RegistroQuestao(
        chave="PF_25_ADM|094_PF_CB1_01|3",
        hash_enunciado="hash3",
        sem_no=True,
        apontamentos=[],
    )

    salvar(cq, path)
    assert path.exists()

    # Verifica ordenação por chave e 1 linha por registro no arquivo
    linhas = path.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "{"
    assert linhas[1] == '  "registros": {'
    # Ordem: 1, depois 2, depois 3
    assert '"PF_25_ADM|094_PF_CB1_01|1":' in linhas[2]
    assert '"PF_25_ADM|094_PF_CB1_01|2":' in linhas[3]
    assert '"PF_25_ADM|094_PF_CB1_01|3":' in linhas[4]
    assert linhas[5] == "  }"
    assert linhas[6] == "}"

    # Carrega e valida round-trip exato
    cq_carregada = carregar(path)
    assert sorted(cq_carregada.registros.keys()) == sorted(cq.registros.keys())

    reg1 = cq_carregada.registros["PF_25_ADM|094_PF_CB1_01|1"]
    assert reg1.hash_enunciado == "hash1"
    assert reg1.sem_no is False
    assert len(reg1.apontamentos) == 1
    assert reg1.apontamentos[0].no_id == "NS-ANUL"
    assert reg1.apontamentos[0].confianca == "alta"

    reg2 = cq_carregada.registros["PF_25_ADM|094_PF_CB1_01|2"]
    assert len(reg2.apontamentos) == 2
    assert reg2.apontamentos[0].papel == "principal"
    assert reg2.apontamentos[1].papel == "secundario"
    assert reg2.apontamentos[1].fora_do_edital is True

    reg3 = cq_carregada.registros["PF_25_ADM|094_PF_CB1_01|3"]
    assert reg3.sem_no is True
    assert reg3.apontamentos == []


def test_carregar_arquivo_inexistente(tmp_path: Path):
    cq = carregar(tmp_path / "nao_existe.json")
    assert isinstance(cq, ClassificacaoQuestoes)
    assert len(cq.registros) == 0


def test_validacao_sem_no(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()
    # sem_no válido sem apontamentos
    reg_valido = RegistroQuestao(
        chave="K|C|1", hash_enunciado="h", sem_no=True, apontamentos=[]
    )
    validar_registro(cq, arvore_teste, reg_valido)

    # sem_no inválido com apontamentos
    reg_invalido = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=True,
        apontamentos=[
            ApontamentoQuestao(no_id="NS-ANUL", papel="principal", confianca="alta")
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="sem_no não pode ter apontamentos"):
        validar_registro(cq, arvore_teste, reg_invalido)


def test_validacao_cardinalidade_e_papeis(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()

    # Mais de 2 apontamentos
    reg_3 = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NS-ANUL", papel="principal", confianca="alta"),
            ApontamentoQuestao(no_id="NS-COMP", papel="secundario", confianca="media"),
            ApontamentoQuestao(no_id="NA-SERV", papel="secundario", confianca="baixa"),
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="máximo permitido: 2"):
        validar_registro(cq, arvore_teste, reg_3)

    # 1 apontamento mas com papel secundario
    reg_1_sec = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NS-ANUL", papel="secundario", confianca="alta")
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="deve ter papel 'principal'"):
        validar_registro(cq, arvore_teste, reg_1_sec)

    # 2 apontamentos com papeis invertidos ou repetidos
    reg_2_inv = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NS-ANUL", papel="secundario", confianca="alta"),
            ApontamentoQuestao(no_id="NS-COMP", papel="principal", confianca="media"),
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="devem ser"):
        validar_registro(cq, arvore_teste, reg_2_inv)

    reg_2_princ = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NS-ANUL", papel="principal", confianca="alta"),
            ApontamentoQuestao(no_id="NS-COMP", papel="principal", confianca="media"),
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="devem ser"):
        validar_registro(cq, arvore_teste, reg_2_princ)


def test_validacao_no_inexistente_e_aposentado(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()

    # Nó que não existe
    reg_inexistente = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NA-FANTASMA", papel="principal", confianca="alta")
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="não existe na árvore"):
        validar_registro(cq, arvore_teste, reg_inexistente)

    # Nó aposentado
    reg_aposentado = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NA-OBS", papel="principal", confianca="alta")
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="não está ativo"):
        validar_registro(cq, arvore_teste, reg_aposentado)


def test_validacao_no_fundido_e_duplicado(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()

    # Nó fundido NS-CONC aponta para NS-CONC-NOVO (ativo)
    reg_fundido = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(no_id="NS-CONC", papel="principal", confianca="alta")
        ],
    )
    # Validação aceita pois resolver_no aponta para NS-CONC-NOVO que é ativo
    validar_registro(cq, arvore_teste, reg_fundido)

    # Nós que resolvem para o mesmo nó (duplicidade)
    reg_duplicado = RegistroQuestao(
        chave="K|C|1",
        hash_enunciado="h",
        sem_no=False,
        apontamentos=[
            ApontamentoQuestao(
                no_id="NS-CONC-NOVO", papel="principal", confianca="alta"
            ),
            ApontamentoQuestao(no_id="NS-CONC", papel="secundario", confianca="media"),
        ],
    )
    with pytest.raises(ClassificacaoInvalida, match="Nó duplicado"):
        validar_registro(cq, arvore_teste, reg_duplicado)


def test_curadoria_mapear_aprovar_rejeitar(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()
    chave = "PF_25_ADM|094_PF_CB1_01|10"
    hash_enun = calcular_hash_enunciado("Enunciado de teste")

    # Mapeamento automático de lista de IDs (1º vira principal, 2º vira secundario)
    reg = mapear_questao(
        cq,
        arvore_teste,
        chave=chave,
        hash_enunciado=hash_enun,
        nos=["NS-ANUL", "NS-COMP"],
        confianca="alta",
        fora_do_edital=False,
        origem="humano",
        status="proposto",
    )
    assert chave in cq.registros
    assert len(reg.apontamentos) == 2
    assert reg.apontamentos[0].papel == "principal"
    assert reg.apontamentos[0].status == "proposto"
    assert reg.apontamentos[1].papel == "secundario"

    # Aprovar apontamento
    aprovar_apontamento(cq, chave, "NS-ANUL")
    assert reg.apontamentos[0].status == "aprovado"

    # Rejeitar apontamento
    rejeitar_apontamento(cq, chave, "NS-COMP")
    assert reg.apontamentos[1].status == "rejeitado"

    # Erro ao aprovar nó inexistente no registro
    with pytest.raises(ClassificacaoInvalida, match="não encontrado"):
        aprovar_apontamento(cq, chave, "NA-ATOS")


def test_mapear_fora_do_edital_por_no(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()
    reg = mapear_questao(
        cq,
        arvore_teste,
        "C1|CAD1|1",
        "h1",
        [("NS-ANUL", "principal", False), ("NS-COMP", "secundario", True)],
        confianca="media",
        origem="llm",
        status="proposto",
    )
    assert [a.fora_do_edital for a in reg.apontamentos] == [False, True]

    # Sem o terceiro elemento, vale o padrão do parâmetro
    reg2 = mapear_questao(
        cq,
        arvore_teste,
        "C1|CAD1|2",
        "h2",
        [("NS-ANUL", "principal")],
        fora_do_edital=True,
    )
    assert reg2.apontamentos[0].fora_do_edital is True


def test_aprovar_lote(arvore_teste: arvore.ArvoreMestre):
    cq = ClassificacaoQuestoes()
    # Caderno 1
    mapear_questao(
        cq,
        arvore_teste,
        "C1|CAD1|1",
        "h1",
        ["NS-ANUL"],
        confianca="alta",
        status="proposto",
    )
    mapear_questao(
        cq,
        arvore_teste,
        "C1|CAD1|2",
        "h2",
        ["NS-COMP"],
        confianca="media",
        status="proposto",
    )
    # Caderno 2
    mapear_questao(
        cq,
        arvore_teste,
        "C1|CAD2|1",
        "h3",
        ["NS-ANUL"],
        confianca="alta",
        status="proposto",
    )

    # Aprovar alta apenas de CAD1
    total = aprovar_lote(cq, confianca="alta", caderno="CAD1")
    assert total == 1
    assert cq.registros["C1|CAD1|1"].apontamentos[0].status == "aprovado"
    assert cq.registros["C1|CAD1|2"].apontamentos[0].status == "proposto"
    assert cq.registros["C1|CAD2|1"].apontamentos[0].status == "proposto"

    # Aprovar alta geral (CAD2 deve ser aprovado)
    total_restante = aprovar_lote(cq, confianca="alta")
    assert total_restante == 1
    assert cq.registros["C1|CAD2|1"].apontamentos[0].status == "aprovado"
