from pathlib import Path
from unittest.mock import MagicMock

from scripts import atualizar_revisao


class TestAtualizarArtefatosRevisao:
    def test_chama_as_tres_etapas_na_ordem_e_reinicia_datasette(self, monkeypatch, tmp_path):
        chamadas = []
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: chamadas.append(("validar", d)))
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: chamadas.append(("relatorio", d)))
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: chamadas.append(("db", d)))

        subprocess_mock = MagicMock(return_value=MagicMock(returncode=0, stderr=""))
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)

        atualizar_revisao.atualizar_artefatos_revisao(tmp_path)

        assert chamadas == [("validar", tmp_path), ("relatorio", tmp_path), ("db", tmp_path)]
        subprocess_mock.assert_called_once()
        args = subprocess_mock.call_args
        assert args[0][0] == ["docker", "compose", "restart", "scraper-cebraspe-datasette"]
        assert args[1]["cwd"] == str(Path(__file__).resolve().parent.parent)

    def test_reiniciar_datasette_false_nao_chama_subprocess(self, monkeypatch, tmp_path):
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: None)

        subprocess_mock = MagicMock()
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)

        atualizar_revisao.atualizar_artefatos_revisao(tmp_path, reiniciar_datasette=False)

        subprocess_mock.assert_not_called()

    def test_container_indisponivel_apenas_loga_aviso_sem_lancar_excecao(self, monkeypatch, tmp_path):
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: None)

        def _levanta_oserror(*args, **kwargs):
            raise OSError("docker não encontrado")

        monkeypatch.setattr(atualizar_revisao.subprocess, "run", _levanta_oserror)

        # Não deve propagar a exceção — pipeline de extração não pode falhar
        # só porque o Datasette local não está rodando.
        atualizar_revisao.atualizar_artefatos_revisao(tmp_path)

    def test_comando_docker_com_returncode_nao_zero_apenas_loga_aviso(self, monkeypatch, tmp_path):
        monkeypatch.setattr(atualizar_revisao, "validar_taxonomia", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_relatorios", lambda d: None)
        monkeypatch.setattr(atualizar_revisao, "gerar_db", lambda d: None)

        subprocess_mock = MagicMock(return_value=MagicMock(returncode=1, stderr="container não existe"))
        monkeypatch.setattr(atualizar_revisao.subprocess, "run", subprocess_mock)

        atualizar_revisao.atualizar_artefatos_revisao(tmp_path)
        subprocess_mock.assert_called_once()
