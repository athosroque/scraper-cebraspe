"""CLI de curadoria da árvore mestre (Etapa 5B.1, ADR-030)."""

import json

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


def test_cli_propostas_filtro_case_insensitive(ambiente, capsys):
    path, _, rodar = ambiente
    arv = carregar(path)
    p = propor(
        arv,
        "criar",
        {"nivel": "assunto", "pai": "M-1", "nome": "Novo Assunto"},
        "humano",
        "teste",
        "M-1",
    )
    salvar(arv, path)

    # Nome exato da matéria M-1 no fixture é "Direito"
    assert rodar("--propostas", "direito") == 0
    out = capsys.readouterr().out
    assert p in out

    assert rodar("--propostas", "DIREITO") == 0
    out2 = capsys.readouterr().out
    assert p in out2


def test_cli_aprovar_proposta_lote_com_dependencia(ambiente):
    path, _, rodar = ambiente
    arv = carregar(path)
    s_comp = criar_no(arv, "subassunto", "Composto", "A-1")
    s_dest = criar_no(arv, "subassunto", "Destino", "A-1")
    mapear(arv, "item|teste", [s_comp])

    p_rem = propor(
        arv,
        "remapear",
        {"item": "item|teste", "de": s_comp, "para": [s_dest]},
        "regra",
        "remapear",
        "M-1",
    )
    p_apo = propor(arv, "aposentar", {"no": s_comp}, "regra", "aposentar", "M-1")
    salvar(arv, path)

    # Passa aposentar antes de remapear
    assert rodar("--aprovar-proposta", f"{p_apo},{p_rem}") == 0
    arv_atual = carregar(path)
    assert arv_atual.nos[s_comp].status == "aposentado"
    assert arv_atual.propostas[p_apo].status == "aprovado"
    assert arv_atual.propostas[p_rem].status == "aprovado"


def test_cli_rejeitar_proposta_lote_com_erro_atomico(ambiente, capsys):
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
        "criar",
        "M-2",
    )
    salvar(arv, path)

    # Aprova p1 previamente
    assert rodar("--aprovar-proposta", p1) == 0

    # Tenta rejeitar p2 e p1 (p1 já aprovada)
    antes = path.read_text(encoding="utf-8")
    assert rodar("--rejeitar-proposta", f"{p2},{p1}") == 1
    assert "já foi aprovada" in capsys.readouterr().err
    # p2 não deve ter sido rejeitada
    assert path.read_text(encoding="utf-8") == antes
    arv_atual = carregar(path)
    assert arv_atual.propostas[p2].status == "proposto"


def test_cli_propostas_formatacao_criar_materia_sob_raiz(ambiente, capsys):
    path, _, rodar = ambiente
    arv = carregar(path)
    p = propor(
        arv,
        "criar",
        {"nivel": "materia", "pai": None, "nome": "Processo Legislativo"},
        "humano",
        "nova materia",
    )
    salvar(arv, path)

    assert rodar("--propostas") == 0
    out = capsys.readouterr().out
    assert "sob raiz" in out
    assert p in out


def test_cli_aprovar_e_rejeitar_proposta_vazia_falha(ambiente, capsys):
    _, _, rodar = ambiente
    assert rodar("--aprovar-proposta", "") == 1
    assert "Nenhuma proposta informada" in capsys.readouterr().err

    assert rodar("--rejeitar-proposta", "") == 1
    assert "Nenhuma proposta informada" in capsys.readouterr().err


def test_cli_aprovar_e_rejeitar_proposta_com_ids_duplicados_deduplica_log(
    ambiente, capsys
):
    path, _, rodar = ambiente
    arv = carregar(path)
    p1 = propor(
        arv,
        "criar",
        {"nivel": "subassunto", "pai": "A-1", "nome": "Sub1"},
        "humano",
        "c1",
        "M-1",
    )
    p2 = propor(
        arv,
        "criar",
        {"nivel": "subassunto", "pai": "A-1", "nome": "Sub2"},
        "humano",
        "c2",
        "M-1",
    )
    salvar(arv, path)

    assert rodar("--aprovar-proposta", f"{p1},{p1}") == 0
    out = capsys.readouterr().out
    assert out.strip() == f"propostas aprovadas: {p1}"

    assert rodar("--rejeitar-proposta", f"{p2},{p2}") == 0
    out_rej = capsys.readouterr().out
    assert out_rej.strip() == f"propostas rejeitadas: {p2}"


def _com_norma_no_arquivo(path):
    """Acrescenta a mesma lei sob duas matérias (ADR-030, KAN-64)."""
    arv = carregar(path)
    criar_no(arv, "assunto", "Lei nº 4.320/1964", "M-1", id_override="A-N1")
    criar_no(arv, "assunto", "Lei nº 4.320/1964", "M-2", id_override="A-N2")
    salvar(arv, path)


def test_criar_norma_ja_existente_e_recusada(ambiente, capsys):
    path, _, rodar = ambiente
    _com_norma_no_arquivo(path)
    antes = path.read_text(encoding="utf-8")
    assert rodar("--criar", "assunto:M-2=Lei nº 4.320/1964") == 1
    erro = capsys.readouterr().err
    assert "[NORMA_JA_EXISTE]" in erro
    assert "--mapear ITEM:A-N1" in erro
    assert path.read_text(encoding="utf-8") == antes


def test_criar_norma_repetida_com_flag_cria(ambiente):
    path, _, rodar = ambiente
    _com_norma_no_arquivo(path)
    assert (
        rodar("--criar", "assunto:M-1=Lei nº 4.320/1964", "--permitir-norma-repetida")
        == 0
    )
    nomes = [
        no.id
        for no in carregar(path).nos.values()
        if no.nome == "Lei nº 4.320/1964" and no.status == "ativo"
    ]
    assert len(nomes) == 3


def test_mapear_no_de_norma_repetida_avisa(ambiente, capsys):
    path, _, rodar = ambiente
    _com_norma_no_arquivo(path)
    assert rodar("--mapear", "direito|lei:A-N1") == 0
    saida = capsys.readouterr().out
    assert "[AVISO NORMA_REPETIDA]" in saida
    assert "A-N2" in saida
    [m] = carregar(path).mapeamentos["direito|lei"]
    assert (m.no_id, m.status) == ("A-N1", "aprovado")


def test_rebaixar_e_lote_com_simular(ambiente, tmp_path, capsys):
    path, _, rodar = ambiente
    assert rodar("--criar", "materia:=Legislação") == 0
    [leg] = [n.id for n in carregar(path).nos.values() if n.nome == "Legislação"]
    lote = tmp_path / "lote.json"
    lote.write_text(
        json.dumps(
            {
                "operacoes": [
                    {
                        "tipo": "criar",
                        "apelido": "@normas",
                        "args": {"nivel": "assunto", "nome": "Normas", "pai": "M-1"},
                    },
                    {
                        "tipo": "rebaixar",
                        "args": {"materia": leg, "destino": "@normas"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    antes = path.read_text(encoding="utf-8")
    assert rodar("--lote", str(lote), "--simular") == 0
    saida = capsys.readouterr().out
    assert "Disciplinas ativas: 3 → 2" in saida
    assert "Simulação: nada foi gravado." in saida
    assert path.read_text(encoding="utf-8") == antes

    assert rodar("--lote", str(lote)) == 0
    arv = carregar(path)
    assert arv.nos[leg].status == "fundido"
    assert arv.nos[arv.nos[leg].fundido_em].nome == "Normas"


def test_rebaixar_com_erro_nao_grava(ambiente):
    path, _, rodar = ambiente
    antes = path.read_text(encoding="utf-8")
    assert rodar("--rebaixar", "M-2:M-1") == 1
    assert path.read_text(encoding="utf-8") == antes
