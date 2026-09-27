import json
import shutil
import uuid
from pathlib import Path
from typing import ClassVar

import pymupdf
import pytest

from scripts import extrair_questoes
from scripts.extrair_questoes import nome_caderno, processar_fila
from src import stats_writer
from src.gabarito_parser import ler_grade
from src.stats_writer import (
    codigo_caderno_do_nome,
    gravar_estatisticas,
    ligar_gabarito_por_conteudo,
)
from tests.test_gabarito_parser import gerar_pdf_grade
from tests.test_stats_writer import _postgres_disponivel, _resultado

FIXTURES = Path(__file__).parent / "fixtures" / "questoes"


class TestNomeCaderno:
    @pytest.mark.parametrize(
        ("prova", "nome"),
        [
            (
                {"codigo_caderno": "167_CDNS_001_01", "arquivo": "A1B2.pdf"},
                "167_CDNS_001_01",
            ),
            (
                {"codigo_caderno": None, "arquivo": "057_IBAMA_001_DISC.pdf"},
                "057_IBAMA_001_DISC",
            ),
            (
                {"codigo_caderno": None, "arquivo": "094_PF_DISC_015.pdf"},
                "094_PF_DISC_015",
            ),
            (
                {
                    "codigo_caderno": None,
                    "arquivo": "PROVA DISCURSIVA_CARGO 1.pdf",
                    "identificador": "DISC_001",
                    "slug": "PF_25_ADM",
                },
                "PF_25_ADM_DISC_001",
            ),
            (
                {
                    "codigo_caderno": None,
                    "arquivo": "x y.pdf",
                    "identificador": None,
                    "slug": "XX_25",
                },
                "XX_25_x_y",
            ),
        ],
    )
    def test_nome(self, prova, nome):
        assert nome_caderno(prova) == nome


class TestLigacaoPorConteudo:
    PROVAS: ClassVar[list[dict]] = [
        {"id": 10, "tipo": "objetiva_basica", "identificador": "CG1", "cargos": [1, 2]},
        {"id": 11, "tipo": "objetiva_especifica", "identificador": None, "cargos": [1]},
        {"id": 12, "tipo": "objetiva_especifica", "identificador": None, "cargos": [2]},
        {"id": 13, "tipo": "discursiva", "identificador": "DISC_001", "cargos": [1]},
    ]

    def test_codigo_do_nome(self):
        assert codigo_caderno_do_nome("094_PF_CB1_01.pdf") == "094_PF_CB1_01"
        assert codigo_caderno_do_nome("E01DCB98.pdf") is None
        assert codigo_caderno_do_nome("094_PF_014_DISC.pdf") is None

    def test_grade_em_hash_liga_pela_especifica_do_cargo(self):
        # Gabarito real do CD (nome em hash, código 167_CDNS_001_01): o
        # caderno do CD também tem nome em hash, sem identificador — liga
        # pela específica cujo único cargo é o 1.
        prova_id, codigo = ligar_gabarito_por_conteudo(
            FIXTURES / "gabarito_hash_CD_001.pdf", self.PROVAS, {1: 13}
        )
        assert (prova_id, codigo) == (11, "167_CDNS_001_01")

    def test_basica_unica_do_concurso(self, tmp_path):
        pdf = gerar_pdf_grade(tmp_path / "h.pdf", "167_CDNS_CG9_01", {1: "C"})
        provas = [p for p in self.PROVAS if p["identificador"] != "CG1"] + [
            {
                "id": 20,
                "tipo": "objetiva_basica",
                "identificador": None,
                "cargos": [1, 2],
            }
        ]
        assert ligar_gabarito_por_conteudo(pdf, provas, {}) == (20, "167_CDNS_CG9_01")

    def test_ambiguo_ou_ilegivel_fica_sem_ligacao(self, tmp_path):
        pdf = gerar_pdf_grade(tmp_path / "h.pdf", "167_CDNS_003_01", {91: "C"})
        assert ligar_gabarito_por_conteudo(pdf, self.PROVAS, {}) == (None, None)
        falso = tmp_path / "falso.pdf"
        falso.write_bytes(b"%PDF-1.4 teste")
        assert ligar_gabarito_por_conteudo(falso, self.PROVAS, {}) == (None, None)


def _pdf_texto(path: Path, texto: str) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 80), texto, fontsize=10)
    doc.save(path)
    return path


def _montar_concurso(tmp_path: Path) -> tuple[Path, Path]:
    """Concurso XX_25 com PDFs reais (recortes de página) e gabaritos
    sintéticos no layout da grade."""
    revisao_dir = tmp_path / "revisao"
    revisao_dir.mkdir()
    (revisao_dir / "Ed_1_XX_25.json").write_text(
        json.dumps(_resultado(), ensure_ascii=False), encoding="utf-8"
    )
    data_dir = tmp_path / "data"
    orgao = data_dir / "2025" / "CEBRASPE" / "XX"
    (orgao / "Provas").mkdir(parents=True)
    (orgao / "Gabaritos").mkdir()
    grade_real = ler_grade(FIXTURES / "Gab_Definitivo_094_PF_CB1_01.pdf").respostas

    shutil.copy(
        FIXTURES / "094_PF_CB1_01_pag2.pdf", orgao / "Provas" / "001_XX_CB1_01.pdf"
    )
    shutil.copy(
        FIXTURES / "094_PF_CB1_01_pag3.pdf", orgao / "Provas" / "001_XX_001_01.pdf"
    )
    shutil.copy(
        FIXTURES / "PF_DISC_CARGO_1.pdf",
        orgao / "Provas" / "PROVA DISCURSIVA_CARGO 1.pdf",
    )
    # Gabarito do básico com nome em hash: liga pelo código no conteúdo.
    gerar_pdf_grade(
        orgao / "Gabaritos" / "ABC123.pdf",
        "001_XX_CB1_01",
        {n: grade_real[n] for n in range(15, 28)},
    )
    # Gabarito do específico cita o item 51, que não está no caderno.
    gerar_pdf_grade(
        orgao / "Gabaritos" / "Gab_Definitivo_001_XX_001_01.pdf",
        "001_XX_001_01",
        {n: grade_real.get(n, "C") for n in range(28, 52)},
    )
    _pdf_texto(
        orgao / "Gabaritos" / "Justif.pdf",
        "Justificativas de alteração do gabarito de itens",
    )

    textos = {
        "001_XX_CB1_01.pdf": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS PARA OS CARGOS 1 E 2",
        "001_XX_001_01.pdf": "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 1",
        "PROVA DISCURSIVA_CARGO 1.pdf": "PROVA DISCURSIVA – CARGO 1",
    }
    manifest = {}
    for i, pdf in enumerate(sorted(orgao.glob("*/*.pdf"))):
        manifest[f"https://cdn.cebraspe.org.br/concursos/XX_25/arquivos/{pdf.name}"] = {
            "hash": f"hash{i}",
            "path": str(pdf),
        }
    (orgao / ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (orgao / "provas_texto_link.json").write_text(json.dumps(textos), encoding="utf-8")
    return revisao_dir, data_dir


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)
class TestConsumidorPostgres:
    @pytest.fixture
    def conn(self):
        schema = f"test_{uuid.uuid4().hex[:12]}"
        admin = stats_writer.conectar()
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(f"CREATE SCHEMA {schema}")
        conn = stats_writer.conectar(options=f"-c search_path={schema}")
        try:
            yield conn
        finally:
            conn.close()
            with admin.cursor() as cur:
                cur.execute(f"DROP SCHEMA {schema} CASCADE")
            admin.close()

    def _fila(self, conn):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT arquivo, status, tipo_documento, mensagem, prova_id IS NOT NULL "
                "FROM fila_extracao_questoes ORDER BY arquivo"
            )
            return cur.fetchall()

    def test_fila_ponta_a_ponta_e_idempotente(self, conn, tmp_path):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        totais = gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        assert totais["gabaritos_sem_prova"] == 1  # só a justificativa

        saida = tmp_path / "questoes"
        resumo = processar_fila(conn, data_dir, saida)
        assert resumo["cadernos"] == 3
        assert resumo["cadernos_sucesso"] == 2
        assert resumo["cadernos_falha"] == {"falha_itens_divergentes": 1}
        assert resumo["itens_extraidos"] == 13 + 23
        assert resumo["justificativas"] == 1
        assert resumo["gabaritos_sem_prova"] == 0

        assert self._fila(conn) == [
            (
                "001_XX_001_01.pdf",
                "erro",
                "caderno_objetivo",
                "falha_itens_divergentes",
                True,
            ),
            ("001_XX_CB1_01.pdf", "concluido", "caderno_objetivo", None, True),
            ("ABC123.pdf", "concluido", "grade", None, True),
            (
                "Gab_Definitivo_001_XX_001_01.pdf",
                "erro",
                "grade",
                "falha_itens_divergentes",
                True,
            ),
            (
                "Justif.pdf",
                "concluido",
                "justificativa",
                "justificativa de alteração: documento do concurso, sem caderno",
                False,
            ),
            (
                "PROVA DISCURSIVA_CARGO 1.pdf",
                "concluido",
                "caderno_discursivo",
                None,
                True,
            ),
        ]

        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.codigo_caderno, count(q.*), count(q.texto_base_id), sum(q.anulada::int) "
                "FROM questoes q JOIN provas p ON p.id = q.prova_id GROUP BY 1"
            )
            # Caderno com falha não grava questão nenhuma.
            assert cur.fetchall() == [("001_XX_CB1_01", 13, 5, 0)]
            cur.execute("SELECT tema, jsonb_array_length(quesitos) FROM discursivas")
            assert cur.fetchall() == [("licitações", 4)]
            cur.execute("SELECT DISTINCT banca FROM concursos")
            assert cur.fetchall() == [("CEBRASPE",)]

        assert sorted(p.name for p in saida.iterdir()) == [
            "001_XX_001_01.auditoria.json",
            "001_XX_001_01.json",
            "001_XX_CB1_01.auditoria.json",
            "001_XX_CB1_01.json",
            "XX_25_DISC_001.auditoria.json",
            "XX_25_DISC_001.json",
        ]
        falha = json.loads((saida / "001_XX_001_01.json").read_text(encoding="utf-8"))
        assert falha["status"] == "falha_itens_divergentes"
        assert falha["itens_faltando"] == [51]
        assert falha["concurso"] == "XX_25"
        assert falha["cargos"] == [1]

        # Segunda passada: nada pendente, nada muda. Nova carga do writer
        # mantém os IDs de prova (upsert), então as questões continuam lá.
        antes = (saida / "001_XX_CB1_01.json").read_text(encoding="utf-8")
        assert processar_fila(conn, data_dir, saida)["cadernos"] == 0
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM questoes")
            assert cur.fetchone()[0] == 13
        assert processar_fila(conn, data_dir, saida, reprocessar=True)["cadernos"] == 3
        assert (saida / "001_XX_CB1_01.json").read_text(encoding="utf-8") == antes
        with conn.cursor() as cur:
            cur.execute("SELECT count(*), count(DISTINCT numero) FROM questoes")
            assert cur.fetchone() == (13, 13)

    def test_excecao_num_caderno_marca_erro_e_segue(self, conn, tmp_path, monkeypatch):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)

        def _explode(*args, **kwargs):
            raise ValueError("pdf quebrado")

        monkeypatch.setattr(
            extrair_questoes.prova_parser, "extrair_caderno_discursivo", _explode
        )
        resumo = processar_fila(conn, data_dir, tmp_path / "questoes")
        assert resumo["cadernos_falha"] == {"excecao": 1, "falha_itens_divergentes": 1}
        erro = [
            linha
            for linha in self._fila(conn)
            if linha[0] == "PROVA DISCURSIVA_CARGO 1.pdf"
        ]
        assert erro[0][1] == "erro"
        assert erro[0][3] == "excecao: ValueError: pdf quebrado"

    def test_caderno_com_gabarito_ligado_depois_e_reprocessado(self, conn, tmp_path):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        orgao = data_dir / "2025" / "CEBRASPE" / "XX"
        gabarito_cb1 = orgao / "Gabaritos" / "ABC123.pdf"
        gabarito_cb1_backup = tmp_path / "ABC123.pdf"
        shutil.copy(gabarito_cb1, gabarito_cb1_backup)
        gabarito_cb1.unlink()

        manifest_path = orgao / ".manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        url_removida = next(u for u, v in manifest.items() if "ABC123.pdf" in v["path"])
        del manifest[url_removida]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        saida = tmp_path / "questoes"
        processar_fila(conn, data_dir, saida)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, mensagem, prova_id FROM fila_extracao_questoes WHERE arquivo = '001_XX_CB1_01.pdf'"
            )
            status_cb1, msg_cb1, prova_id_cb1 = cur.fetchone()
            assert status_cb1 == "erro"
            assert msg_cb1 == "falha_sem_gabarito"

        # Simula stats_writer ligando o gabarito posteriormente
        shutil.copy(gabarito_cb1_backup, gabarito_cb1)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fila_extracao_questoes (concurso_id, categoria, arquivo, path_relativo, sha256, prova_id, status) "
                "VALUES ((SELECT id FROM concursos WHERE slug = 'XX_25'), 'gabarito', 'ABC123.pdf', "
                "'2025/CEBRASPE/XX/Gabaritos/ABC123.pdf', 'hash_abc123_novo', %s, 'pendente')",
                (prova_id_cb1,),
            )

        resumo2 = processar_fila(conn, data_dir, saida)
        assert resumo2["cadernos_sucesso"] >= 1
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM fila_extracao_questoes WHERE arquivo = '001_XX_CB1_01.pdf'"
            )
            assert cur.fetchone()[0] == "concluido"

    def _espiar_cadernos(self, monkeypatch) -> list[str]:
        """Troca `processar_caderno` por um espião que anota o arquivo da prova
        de cada grupo processado e delega para a função real."""
        processados: list[str] = []
        original = extrair_questoes.processar_caderno

        def _espiao(conn, linhas, data_dir, saida_dir):
            processados.append(linhas[0]["prova_arquivo"])
            return original(conn, linhas, data_dir, saida_dir)

        monkeypatch.setattr(extrair_questoes, "processar_caderno", _espiao)
        return processados

    def test_caderno_concluido_com_gabarito_alterado_e_reprocessado(
        self, conn, tmp_path, monkeypatch
    ):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        saida = tmp_path / "questoes"
        processar_fila(conn, data_dir, saida)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, assinatura_grupo FROM fila_extracao_questoes WHERE arquivo = '001_XX_CB1_01.pdf'"
            )
            status_antes, ass_antes = cur.fetchone()
            assert status_antes == "concluido"
            assert ass_antes is not None

            # Altera o sha256 do gabarito simulando nova versão baixada
            cur.execute(
                "UPDATE fila_extracao_questoes SET sha256 = 'novo_hash_gabarito' WHERE arquivo = 'ABC123.pdf'"
            )

        processados = self._espiar_cadernos(monkeypatch)
        resumo = processar_fila(conn, data_dir, saida)
        assert resumo["cadernos"] == 1
        assert processados == ["001_XX_CB1_01.pdf"]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, assinatura_grupo FROM fila_extracao_questoes WHERE arquivo = '001_XX_CB1_01.pdf'"
            )
            status_depois, ass_depois = cur.fetchone()
            assert status_depois == "concluido"
            assert ass_depois != ass_antes

    def test_gabarito_movido_de_a_para_b_reprocessa_os_dois(
        self, conn, tmp_path, monkeypatch
    ):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        saida = tmp_path / "questoes"
        processar_fila(conn, data_dir, saida)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT prova_id FROM fila_extracao_questoes WHERE arquivo = '001_XX_001_01.pdf'"
            )
            prova_b = cur.fetchone()[0]
            # Move o gabarito ABC123 para o caderno 001_01
            cur.execute(
                "UPDATE fila_extracao_questoes SET prova_id = %s WHERE arquivo = 'ABC123.pdf'",
                (prova_b,),
            )

        processados = self._espiar_cadernos(monkeypatch)
        resumo = processar_fila(conn, data_dir, saida)
        assert resumo["cadernos"] == 2
        assert sorted(processados) == ["001_XX_001_01.pdf", "001_XX_CB1_01.pdf"]

    def test_reprocessar_erros_pega_orfao_em_erro(self, conn, tmp_path):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        saida = tmp_path / "questoes"
        processar_fila(conn, data_dir, saida)

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO fila_extracao_questoes (concurso_id, categoria, arquivo, path_relativo, sha256, prova_id, status) "
                "VALUES ((SELECT id FROM concursos WHERE slug = 'XX_25'), 'gabarito', 'orfao.pdf', "
                "'2025/CEBRASPE/XX/Gabaritos/Justif.pdf', 'hash_orfao_1', NULL, 'erro')"
            )

        resumo_sem = processar_fila(conn, data_dir, saida)
        assert resumo_sem["justificativas"] == 0

        resumo_com = processar_fila(conn, data_dir, saida, reprocessar_erros=True)
        assert resumo_com["justificativas"] == 1

    def _adicionar_manifesto(self, pdf_path: Path):
        orgao = pdf_path.parent.parent
        manifest_path = orgao / ".manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        url = f"https://cdn.cebraspe.org.br/concursos/XX_25/arquivos/{pdf_path.name}"
        manifest[url] = {
            "hash": f"hash_{pdf_path.stem}",
            "path": str(pdf_path),
        }
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_dois_gabaritos_preliminar_e_definitivo(self, conn, tmp_path):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        orgao = data_dir / "2025" / "CEBRASPE" / "XX"
        grade_real = ler_grade(FIXTURES / "Gab_Definitivo_094_PF_CB1_01.pdf").respostas
        # Cria gabarito preliminar com cabeçalho de preliminar
        g_prelim = orgao / "Gabaritos" / "Gab_Preliminar_001_XX_CB1_01.pdf"
        gerar_pdf_grade(
            g_prelim,
            "001_XX_CB1_01",
            {n: grade_real[n] for n in range(15, 28)},
            titulo="GABARITOS OFICIAIS PRELIMINARES",
        )
        self._adicionar_manifesto(g_prelim)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM provas WHERE codigo_caderno = '001_XX_CB1_01'")
            pid = cur.fetchone()[0]
            cur.execute(
                "UPDATE fila_extracao_questoes SET prova_id = %s "
                "WHERE arquivo IN ('ABC123.pdf', 'Gab_Preliminar_001_XX_CB1_01.pdf')",
                (pid,),
            )

        saida = tmp_path / "questoes"
        processar_fila(conn, data_dir, saida)

        conteudo = json.loads(
            (saida / "001_XX_CB1_01.json").read_text(encoding="utf-8")
        )
        assert conteudo["gabarito_versao"] == "definitivo"
        tipos_alerta = [a["tipo"] for a in conteudo["alertas"]]
        assert "mais_de_um_gabarito" in tipos_alerta

        # Agora deixa apenas o preliminar ligado
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fila_extracao_questoes SET prova_id = NULL WHERE arquivo = 'ABC123.pdf'"
            )

        processar_fila(conn, data_dir, saida)
        conteudo_prelim = json.loads(
            (saida / "001_XX_CB1_01.json").read_text(encoding="utf-8")
        )
        assert conteudo_prelim["gabarito_versao"] == "preliminar"
        tipos_alerta_prelim = [a["tipo"] for a in conteudo_prelim["alertas"]]
        assert "gabarito_preliminar" in tipos_alerta_prelim

    def test_dois_padroes_resposta_preliminar_e_definitivo(self, conn, tmp_path):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        orgao = data_dir / "2025" / "CEBRASPE" / "XX"
        p_prelim = orgao / "Gabaritos" / "Padrao_Preliminar.pdf"
        p_def = orgao / "Gabaritos" / "Padrao_Definitivo.pdf"
        _pdf_texto(
            p_prelim,
            "CARGO 1\nProva Discursiva\nPADRÃO DE RESPOSTA PRELIMINAR\nTexto preliminar",
        )
        _pdf_texto(
            p_def,
            "CARGO 1\nProva Discursiva\nPADRÃO DE RESPOSTA DEFINITIVO\nTexto definitivo",
        )
        self._adicionar_manifesto(p_prelim)
        self._adicionar_manifesto(p_def)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM provas WHERE tipo = 'discursiva'")
            pid_disc = cur.fetchone()[0]
            cur.execute(
                "UPDATE fila_extracao_questoes SET prova_id = %s "
                "WHERE arquivo IN ('Padrao_Preliminar.pdf', 'Padrao_Definitivo.pdf')",
                (pid_disc,),
            )

        saida = tmp_path / "questoes"
        processar_fila(conn, data_dir, saida)

        conteudo = json.loads(
            (saida / "XX_25_DISC_001.json").read_text(encoding="utf-8")
        )
        assert conteudo["padrao_resposta_versao"] == "definitivo"
        tipos_alerta = [a["tipo"] for a in conteudo["alertas"]]
        assert "mais_de_um_gabarito" in tipos_alerta

        # Agora deixa apenas o preliminar ligado
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fila_extracao_questoes SET prova_id = NULL WHERE arquivo = 'Padrao_Definitivo.pdf'"
            )

        processar_fila(conn, data_dir, saida)
        conteudo_prelim = json.loads(
            (saida / "XX_25_DISC_001.json").read_text(encoding="utf-8")
        )
        assert conteudo_prelim["padrao_resposta_versao"] == "preliminar"
        tipos_alerta_prelim = [a["tipo"] for a in conteudo_prelim["alertas"]]
        assert "gabarito_preliminar" in tipos_alerta_prelim

    def test_advisory_lock_concorrente(self, conn, tmp_path):
        revisao_dir, data_dir = _montar_concurso(tmp_path)
        gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        saida = tmp_path / "questoes"

        outra_conn = stats_writer.conectar()
        outra_conn.autocommit = True
        try:
            with outra_conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_lock(%s)",
                    (extrair_questoes.LOCK_FILA_QUESTOES,),
                )

            resumo = processar_fila(conn, data_dir, saida)
            assert resumo.get("ocupado") is True
            assert resumo["cadernos"] == 0
        finally:
            with outra_conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (extrair_questoes.LOCK_FILA_QUESTOES,),
                )
            outra_conn.close()
