from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts import atualizar_revisao


@pytest.fixture(autouse=True)
def _sem_banco_real(monkeypatch):
    # Nunca gravar no Postgres real a partir destes testes.
    chamadas = []
    monkeypatch.setattr(
        atualizar_revisao, "gravar_estatisticas", lambda d: chamadas.append(d)
    )
    monkeypatch.setattr(
        atualizar_revisao, "processar_fila", lambda: chamadas.append("fila")
    )
    monkeypatch.setattr(
        atualizar_revisao,
        "_reaplicar_permissoes_site",
        lambda: chamadas.append("grants"),
    )
    return chamadas


class TestAtualizarArtefatosRevisao:
    def test_chama_as_tres_etapas_na_ordem_e_reinicia_datasette(
        self, monkeypatch, tmp_path
    ):
        chamadas = []
        monkeypatch.setattr(
            atualizar_revisao,
            "validar_taxonomia",
            lambda d: chamadas.append(("validar", d)),
        )
        monkeypatch.setattr(
            atualizar_revisao,
            "gerar_relatorios",
            lambda d: chamadas.append(("relatorio", d)),
        )
        monkeypatch.setattr(
            atualizar_revisao, "gerar_db", lambda d: chamadas.append(("db", d))
        )

        subprocess_mock = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)

        atualizar_revisao.atualizar_artefatos_revisao(tmp_path)

        assert chamadas == [
            ("validar", tmp_path),
            ("relatorio", tmp_path),
            ("db", tmp_path),
        ]
        subprocess_mock.assert_called_once()
        args = subprocess_mock.call_args
        assert args[0][0] == [
            "docker",
            "compose",
            "restart",
            "scraper-cebraspe-datasette",
        ]
        assert args[1]["cwd"] == str(Path(__file__).resolve().parent.parent)

    def test_reiniciar_datasette_false_nao_chama_subprocess(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: None)

        subprocess_mock = MagicMock()
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)

        atualizar_revisao.atualizar_artefatos_revisao(
            tmp_path, reiniciar_datasette=False
        )

        subprocess_mock.assert_not_called()

    def test_container_indisponivel_apenas_loga_aviso_sem_lancar_excecao(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: None)

        def _levanta_oserror(*args, **kwargs):
            raise OSError("docker não encontrado")

        monkeypatch.setattr(atualizar_revisao.subprocess, "run", _levanta_oserror)

        # Não deve propagar a exceção — pipeline de extração não pode falhar
        # só porque o Datasette local não está rodando.
        atualizar_revisao.atualizar_artefatos_revisao(tmp_path)

    def test_comando_docker_com_returncode_nao_zero_apenas_loga_aviso(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: None)

        subprocess_mock = MagicMock(
            return_value=MagicMock(returncode=1, stderr="container não existe")
        )
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)

        atualizar_revisao.atualizar_artefatos_revisao(tmp_path)
        subprocess_mock.assert_called_once()


class TestGravacaoBancoEstatisticas:
    def _sem_etapas(self, monkeypatch):
        for nome in ("validar_taxonomia", "gerar_relatorios", "gerar_db"):
            monkeypatch.setattr(atualizar_revisao, nome, lambda d: None)

    def test_grava_estatisticas_ao_final(self, monkeypatch, tmp_path, _sem_banco_real):
        self._sem_etapas(monkeypatch)
        atualizar_revisao.atualizar_artefatos_revisao(
            tmp_path, reiniciar_datasette=False
        )
        # Carga, fila de cadernos (5C) e reaplicação dos grants do site.
        assert _sem_banco_real == [tmp_path, "fila", "grants"]

    def test_gravar_banco_false_nao_grava(self, monkeypatch, tmp_path, _sem_banco_real):
        self._sem_etapas(monkeypatch)
        atualizar_revisao.atualizar_artefatos_revisao(
            tmp_path, reiniciar_datasette=False, gravar_banco=False
        )
        assert _sem_banco_real == []

    def test_banco_indisponivel_apenas_loga_aviso(self, monkeypatch, tmp_path):
        self._sem_etapas(monkeypatch)

        def _falha(d):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(atualizar_revisao, "gravar_estatisticas", _falha)
        atualizar_revisao.atualizar_artefatos_revisao(
            tmp_path, reiniciar_datasette=False
        )

    def test_carga_falhou_nao_processa_fila(
        self, monkeypatch, tmp_path, _sem_banco_real
    ):
        self._sem_etapas(monkeypatch)

        def _falha(d):
            raise RuntimeError("connection refused")

        monkeypatch.setattr(atualizar_revisao, "gravar_estatisticas", _falha)
        atualizar_revisao.atualizar_artefatos_revisao(
            tmp_path, reiniciar_datasette=False
        )
        assert "fila" not in _sem_banco_real

    def test_falha_na_fila_apenas_loga_aviso(self, monkeypatch, tmp_path, caplog):
        self._sem_etapas(monkeypatch)

        def _falha():
            raise RuntimeError("pdf corrompido")

        monkeypatch.setattr(atualizar_revisao, "processar_fila", _falha)
        with caplog.at_level("WARNING"):
            atualizar_revisao.atualizar_artefatos_revisao(
                tmp_path, reiniciar_datasette=False
            )
        assert "Não foi possível processar a fila" in caplog.text


class TestSinonimosNoPipeline:
    def test_regras_e_relatorio_de_sinonimos_rodam_sem_llm(self, monkeypatch, tmp_path):
        for nome in ("validar_taxonomia", "gerar_relatorios", "gerar_db"):
            monkeypatch.setattr(atualizar_revisao, nome, lambda d: None)
        monkeypatch.setattr(
            atualizar_revisao, "listar_jsons_edital", lambda d: [d / "Ed.json"]
        )
        chamadas = []
        import scripts.gerar_relatorio_arvore
        import src.canonico

        monkeypatch.setattr(
            src.canonico,
            "mapear_novos_itens_por_regra",
            lambda d: chamadas.append(("regras", d)),
        )
        monkeypatch.setattr(
            scripts.gerar_relatorio_arvore,
            "gerar_relatorio_arvore",
            lambda: chamadas.append(("relatorio",)),
        )
        atualizar_revisao.atualizar_artefatos_revisao(
            tmp_path, reiniciar_datasette=False, gravar_banco=False
        )
        assert chamadas == [("regras", tmp_path), ("relatorio",)]

    def test_sem_edital_nao_escreve_sinonimos(self, monkeypatch, tmp_path):
        revisao = tmp_path / "revisao"
        revisao.mkdir()
        atualizar_revisao.atualizar_arvore(revisao)
        assert not (tmp_path / "canonico").exists()

    def test_erro_nos_sinonimos_so_loga_aviso(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            atualizar_revisao, "listar_jsons_edital", lambda d: [d / "Ed.json"]
        )

        def _falha(d):
            raise ValueError("json corrompido")

        import src.canonico

        monkeypatch.setattr(src.canonico, "mapear_novos_itens_por_regra", _falha)
        atualizar_revisao.atualizar_arvore(tmp_path)


class TestReaplicarPermissoesSite:
    def test_roda_o_script_do_site(self, monkeypatch):
        monkeypatch.undo()
        subprocess_mock = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)
        atualizar_revisao._reaplicar_permissoes_site()
        assert subprocess_mock.call_args.args[0][-1].endswith("aplicar_schema_app.py")

    def test_falha_so_loga_aviso(self, monkeypatch):
        monkeypatch.undo()

        def _levanta(*a, **k):
            raise OSError("sem python")

        monkeypatch.setattr(atualizar_revisao.subprocess, "run", _levanta)
        atualizar_revisao._reaplicar_permissoes_site()
