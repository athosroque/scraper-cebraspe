"""Mapeamento de item novo de edital por regra (Etapa 5B.1, ADR-030)."""

import pytest

from src import canonico
from src.arvore import ArvoreMestre, carregar, criar_no, mapear, salvar


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
