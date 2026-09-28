"""CLI de curadoria da árvore mestre (Etapa 5B.1, ADR-030)."""

import pytest

from scripts import curar_arvore
from src.arvore import (
    ArvoreMestre,
    Mapeamento,
    carregar,
    criar_no,
    mapear,
    propor,
    salvar,
)


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Direito", None, id_override="M-1")
    criar_no(arv, "materia", "Português", None, id_override="M-2")
    criar_no(arv, "assunto", "Atos", "M-1", id_override="A-1")
    criar_no(arv, "assunto", "Atos (dup)", "M-1", id_override="A-2")
    mapear(arv, "direito", ["M-1"])
    arv.mapeamentos["direito|atos"] = [Mapeamento("A-1", "llm", "proposto")]
    path = tmp_path / "arvore.json"
    salvar(arv, path)
    revisao = tmp_path / "revisao"
    revisao.mkdir()

    def rodar(*args):
        return curar_arvore.main(
            [*args, "--arvore", str(path), "--revisao-dir", str(revisao)]
        )

    return path, revisao, rodar


def test_mapear_varios_nos_e_gerar_relatorio(ambiente):
    path, revisao, rodar = ambiente
    assert rodar("--mapear", "direito|composto:A-1,A-2") == 0
    nos = [
        (m.no_id, m.origem, m.status)
        for m in carregar(path).mapeamentos["direito|composto"]
    ]
    assert nos == [("A-1", "humano", "aprovado"), ("A-2", "humano", "aprovado")]
    assert (revisao / "relatorio" / "arvore.html").exists()


def test_mapear_de_novo_aprova_a_proposta(ambiente):
    path, _, rodar = ambiente
    assert rodar("--mapear", "direito|atos:A-1") == 0
    [m] = carregar(path).mapeamentos["direito|atos"]
    assert (m.origem, m.status) == ("humano", "aprovado")


@pytest.mark.parametrize(
    "acao, status", [("--aprovar", "aprovado"), ("--rejeitar", "rejeitado")]
)
def test_aprovar_e_rejeitar(ambiente, acao, status):
    path, _, rodar = ambiente
    assert rodar(acao, "direito|atos:A-1") == 0
    assert carregar(path).mapeamentos["direito|atos"][0].status == status


def test_criar_renomear_mover_fundir_desmapear(ambiente):
    path, _, rodar = ambiente
    assert rodar("--criar", "assunto:M-2=Crase") == 0
    [novo] = [i for i, n in carregar(path).nos.items() if n.nome == "Crase"]
    assert novo.startswith("NA-") and carregar(path).nos[novo].pai == "M-2"

    assert rodar("--renomear", f"{novo}=Emprego da crase") == 0
    assert rodar("--mover", f"{novo}:M-1") == 0
    assert rodar("--fundir", "A-2:A-1") == 0
    assert rodar("--desmapear", "direito:M-1") == 0

    arv = carregar(path)
    assert (arv.nos[novo].nome, arv.nos[novo].pai) == ("Emprego da crase", "M-1")
    assert (arv.nos["A-2"].status, arv.nos["A-2"].fundido_em) == ("fundido", "A-1")
    assert "direito" not in arv.mapeamentos


@pytest.mark.parametrize(
    "args, mensagem",
    [
        (("--mapear", "direito|x:NAO-EXISTE"), "não existe"),
        (("--aprovar", "direito|atos:A-2"), "não aponta"),
        (("--desmapear", "inexistente:M-1"), "não aponta"),
        (("--mover", "A-1:"), "Formato esperado"),
        (("--mover", "A-1:A-2"), "inválido"),
        (("--criar", "assunto:M-1"), "Formato esperado"),
        (("--criar", "topico:M-1=X"), "Nível"),
    ],
)
def test_erros_nao_gravam(ambiente, capsys, args, mensagem):
    path, _, rodar = ambiente
    antes = path.read_text(encoding="utf-8")
    assert rodar(*args) == 1
    assert mensagem in capsys.readouterr().err
    assert path.read_text(encoding="utf-8") == antes


def test_sem_argumentos_mostra_ajuda():
    assert curar_arvore.main([]) == 2


def test_cli_propostas_listagem_e_filtro(ambiente, capsys):
    path, _, rodar = ambiente
    arv = carregar(path)
    p1 = propor(
        arv, "fundir", {"origem": "A-2", "destino": "A-1"}, "regra", "fusão", "M-1"
    )
    p2 = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": "M-2", "nome": "Novo P"},
        "humano",
        "criar em M-2",
        "M-2",
    )
    salvar(arv, path)

    # Listagem geral
    assert rodar("--propostas") == 0
    out = capsys.readouterr().out
    assert p1 in out
    assert p2 in out
    assert "M-1" in out
    assert "M-2" in out

    # Listagem filtrada por matéria
    assert rodar("--propostas", "M-1") == 0
    out_filtrada = capsys.readouterr().out
    assert p1 in out_filtrada
    assert p2 not in out_filtrada


def test_cli_aprovar_proposta_lote(ambiente):
    path, _, rodar = ambiente
    arv = carregar(path)
    p1 = propor(
        arv, "fundir", {"origem": "A-2", "destino": "A-1"}, "regra", "fusão", "M-1"
    )
    p2 = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": "M-2", "nome": "Sintaxe"},
        "humano",
        "novo assunto",
        "M-2",
    )
    salvar(arv, path)

    assert rodar("--aprovar-proposta", f"{p1},{p2}") == 0
    arv_atual = carregar(path)
    assert arv_atual.propostas[p1].status == "aprovado"
    assert arv_atual.propostas[p2].status == "aprovado"
    assert arv_atual.nos["A-2"].status == "fundido"
    novo_id = arv_atual.propostas[p2].args["id"]
    assert arv_atual.nos[novo_id].status == "ativo"


def test_cli_aprovar_proposta_tudo_ou_nada_falha(ambiente, capsys):
    path, _, rodar = ambiente
    arv = carregar(path)
    p1 = propor(
        arv, "fundir", {"origem": "A-2", "destino": "A-1"}, "regra", "fusão", "M-1"
    )
    salvar(arv, path)
    antes = path.read_text(encoding="utf-8")

    # Passa p1 e uma proposta inexistente
    assert rodar("--aprovar-proposta", f"{p1},P-inexistente") == 1
    assert "não existe" in capsys.readouterr().err
    # Arquivo não foi modificado
    assert path.read_text(encoding="utf-8") == antes
    assert carregar(path).nos["A-2"].status == "ativo"


def test_cli_rejeitar_proposta(ambiente):
    path, _, rodar = ambiente
    arv = carregar(path)
    p = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": "M-1", "nome": "Temporário"},
        "llm",
        "descartar",
        "M-1",
    )
    novo_id = arv.propostas[p].args["id"]
    salvar(arv, path)

    assert rodar("--rejeitar-proposta", p) == 0
    arv_atual = carregar(path)
    assert arv_atual.propostas[p].status == "rejeitado"
    assert novo_id not in arv_atual.nos
