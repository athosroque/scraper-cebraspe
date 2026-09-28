import json
import uuid

import psycopg2
import pytest
from psycopg2 import sql

from src import stats_writer
from src.stats_writer import (
    classificar_prova_por_texto,
    extrair_cargos_do_texto,
    identificador_prova,
    montar_carga_concurso,
)


class TestClassificarProvaPorTexto:
    # Textos reais dos `provas_texto_link.json` de PF, STM, IBAMA, CD e TCU.
    @pytest.mark.parametrize(
        ("texto", "tipo", "cargos"),
        [
            (
                "PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA OS CARGOS DE 1 A 14",
                "objetiva_basica",
                list(range(1, 15)),
            ),
            (
                "PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA O CARGO 15",
                "objetiva_basica",
                [15],
            ),
            (
                "PROVA OBJETIVA - CONHECIMENTOS GERAIS PARA OS CARGOS 2, 4, 5 E 7",
                "objetiva_basica",
                [2, 4, 5, 7],
            ),
            (
                "PROVA OBJETIVA – CONHECIMENTOS GERAIS PARA OS CARGOS 1 E 2",
                "objetiva_basica",
                [1, 2],
            ),
            ("PROVA OBJETIVA – CONHECIMENTOS BÁSICOS", "objetiva_basica", []),
            (
                "PROVA OBJETIVA - CONHECIMENTOS ESPECÍFICOS – CARGO 10",
                "objetiva_especifica",
                [10],
            ),
            (
                "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS PARA O CARGO 3",
                "objetiva_especifica",
                [3],
            ),
            ("PROVA DISCURSIVA – CARGO 14", "discursiva", [14]),
            ("PROVAS DISCURSIVAS (P3)", "discursiva", []),
            (
                "PADRÃO DEFINITIVO DE RESPOSTA – PROVA DISCURSIVA – CARGO 2",
                "padrao_resposta",
                [2],
            ),
            (
                "PADRÃO DEFINITIVO DE RESPOSTAS – PROVA DISCURSIVA – CARGO 1",
                "padrao_resposta",
                [1],
            ),
        ],
    )
    def test_textos_reais(self, texto, tipo, cargos):
        assert classificar_prova_por_texto(texto) == {
            "tipo": tipo,
            "cargos_numeros": cargos,
        }

    @pytest.mark.parametrize(
        "texto",
        [
            "EDITAL Nº 6 – RESULTADO FINAL NAS PROVAS OBJETIVAS E O RESULTADO PROVISÓRIO NA PROVA DISCURSIVA",
            "EDITAL Nº 5 – LOCAIS DE APLICAÇÃO DAS PROVAS OBJETIVAS E DA PROVA DISCURSIVA",
            "",
            "CADERNO QUALQUER",
        ],
    )
    def test_edital_administrativo_ou_desconhecido_retorna_none(self, texto):
        assert classificar_prova_por_texto(texto) is None

    def test_cargos_intervalo_tem_prioridade_sobre_lista(self):
        assert extrair_cargos_do_texto("cargos de 3 a 5") == [3, 4, 5]


class TestExtrairCargosDoTexto:
    @pytest.mark.parametrize(
        ("texto", "esperado"),
        [
            (
                "PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA OS CARGOS DE 1 A 14",
                list(range(1, 15)),
            ),
            ("PROVA OBJETIVA – CONHECIMENTOS GERAIS PARA OS CARGOS 1 E 2", [1, 2]),
            ("PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA O CARGO 15", [15]),
            (
                "(APENAS PARA O CARGO 1: ANALISTA JUDICIÁRIO – ÁREA: ADMINISTRATIVA E PARA O CARGO 8: TÉCNICO JUDICIÁRIO – ÁREA: ADMINISTRATIVA)",
                [1, 8],
            ),
            (
                "(APENAS PARA O CARGO 3: ANALISTA... E PARA O CARGO 6: TÉCNICO...)",
                [3, 6],
            ),
            ("cargos de 3 a 5", [3, 4, 5]),
            ("cargos 2, 4, 5 e 7", [2, 4, 5, 7]),
            ("cargo 1 e cargos de 3 a 5", [1, 3, 4, 5]),
            ("cargos 1, 2 e cargo 1", [1, 2]),
            ("cargo 1 a 3 horas", [1]),
            ("", []),
            ("sem cargos aqui", []),
        ],
    )
    def test_extrair_cargos_cenarios(self, texto, esperado):
        assert extrair_cargos_do_texto(texto) == esperado


class TestIdentificadorProva:
    @pytest.mark.parametrize(
        ("nome", "esperado"),
        [
            ("094_PF_CB1_01.pdf", "CB1"),
            ("072_STM_CG5_01.pdf", "CG5"),
            ("057_IBAMA_003_01.pdf", "003"),
            ("094_PF_014_DISC.pdf", "DISC_014"),
            ("094_PF_DISC_015.pdf", "DISC_015"),
            ("PROVA DISCURSIVA_CARGO 1.pdf", None),
            (
                "E61A04B682ABA7AF746F702D22B1516C4A4BC005855CE5CFFF5D2280F3E790CE.pdf",
                None,
            ),
        ],
    )
    def test_nomes_reais(self, nome, esperado):
        assert identificador_prova(nome) == esperado


def _resultado(slug="XX_25", topicos_especificos=("Topico A", "Topico B")) -> dict:
    return {
        "edital": f"Ed_1_{slug}.pdf",
        "concurso": {"slug": slug, "orgao": slug.split("_")[0], "ano": 2025},
        "cargos": [
            {"numero": 1, "nome": "ANALISTA", "nivel": "superior"},
            {"numero": 2, "nome": "TÉCNICO", "nivel": "medio"},
        ],
        "total_chunks": 2,
        "extraidos_com_sucesso": 2,
        "falhas": 0,
        "chunks_com_falha": [],
        "status_revisao_humana": "PENDENTE — ainda não revisado.",
        "resultados": [
            {
                "chunk_index": 0,
                "cargo": None,
                "materia_chunk": "LÍNGUA PORTUGUESA",
                "tipo_conhecimento": "basico",
                "nivel": "superior",
                "cargo_numero": None,
                "materia_normalizada": "LÍNGUA PORTUGUESA",
                "apenas_discursiva": False,
                "taxonomia_extraida": {
                    "materia": "Língua Portuguesa",
                    "topicos": [
                        {"nome": "Ortografia oficial", "subtopicos": ["Acentuação"]},
                        {"nome": "...", "subtopicos": []},
                    ],
                },
            },
            {
                "chunk_index": 1,
                "cargo": "CARGO 1: ANALISTA",
                "materia_chunk": "DIREITO",
                "tipo_conhecimento": "especifico",
                "nivel": "superior",
                "cargo_numero": 1,
                "materia_normalizada": "DIREITO",
                "apenas_discursiva": False,
                "taxonomia_extraida": {
                    "materia": "Direito",
                    "topicos": [
                        {"nome": nome, "subtopicos": []} for nome in topicos_especificos
                    ],
                },
            },
        ],
    }


class TestMontarCargaConcurso:
    def test_basico_sem_cargo_e_topico_sem_chave_pulado(self):
        carga = montar_carga_concurso(_resultado())
        assert carga["slug"] == "XX_25"
        assert carga["status_revisao"] == "pendente"
        # "..." não tem chave normalizável — pulado, não gravado vazio.
        assert [i["topico_nome"] for i in carga["itens"]] == [
            "Ortografia oficial",
            "Topico A",
            "Topico B",
        ]
        basico = carga["itens"][0]
        assert basico["cargo_numero"] is None
        assert basico["subtopicos"] == ["Acentuação"]
        assert basico["materia_chave"] == "lingua portuguesa"

    def test_chave_de_materia_igual_entre_concursos(self):
        a = montar_carga_concurso(_resultado("AA_25"))
        b = montar_carga_concurso(_resultado("BB_25"))
        assert a["itens"][0]["materia_chave"] == b["itens"][0]["materia_chave"]

    def test_aprovado(self):
        resultado = _resultado()
        resultado["status_revisao_humana"] = "APROVADO em 2026-09-30"
        assert montar_carga_concurso(resultado)["status_revisao"] == "aprovado"

    def test_sem_slug_levanta_erro(self):
        resultado = _resultado()
        resultado["concurso"] = None
        with pytest.raises(ValueError):
            montar_carga_concurso(resultado)

    def test_cargos_restritos_propagados_quando_presentes(self):
        resultado = _resultado()
        resultado["resultados"][0]["cargos_restritos"] = [1, 8]
        resultado["resultados"][1]["cargos_restritos"] = None
        carga = montar_carga_concurso(resultado)
        assert carga["itens"][0]["cargos_restritos"] == [1, 8]
        assert carga["itens"][1]["cargos_restritos"] is None


def _montar_data_dir(data_dir):
    orgao_dir = data_dir / "2025" / "CEBRASPE" / "XX"
    arquivos = {
        "Provas/001_XX_CB1_01.pdf": "PROVA OBJETIVA – CONHECIMENTOS BÁSICOS PARA OS CARGOS 1 E 2",
        "Provas/001_XX_001_01.pdf": "PROVA OBJETIVA – CONHECIMENTOS ESPECÍFICOS – CARGO 1",
        "Provas/Ed_9_resultado.pdf": "EDITAL Nº 9 – RESULTADO FINAL NA PROVA DISCURSIVA",
        "Provas/PADRAO_CARGO_1.pdf": "PADRÃO DEFINITIVO DE RESPOSTA – PROVA DISCURSIVA – CARGO 1",
        "Gabaritos/Gab_Definitivo_001_XX_CB1_01.pdf": None,
    }
    manifest, textos = {}, {}
    for i, (rel, texto) in enumerate(arquivos.items()):
        path = orgao_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 teste")
        manifest[
            f"https://cdn.cebraspe.org.br/concursos/XX_25/arquivos/{path.name}"
        ] = {
            "hash": f"hash{i}",
            "path": f"/outra/copia/{path.name}",
        }
        if texto:
            textos[path.name] = texto
    (orgao_dir / ".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (orgao_dir / "provas_texto_link.json").write_text(
        json.dumps(textos), encoding="utf-8"
    )


class TestColetarPdfsFila:
    def test_agrupa_por_slug_pelo_manifesto(self, tmp_path):
        _montar_data_dir(tmp_path)
        por_slug = stats_writer.coletar_pdfs_fila(tmp_path)
        assert list(por_slug) == ["XX_25"]
        pdfs = {p["arquivo"]: p for p in por_slug["XX_25"]}
        assert len(pdfs) == 5
        assert pdfs["Gab_Definitivo_001_XX_CB1_01.pdf"]["categoria"] == "gabarito"
        assert (
            pdfs["001_XX_CB1_01.pdf"]["path_relativo"]
            == "2025/CEBRASPE/XX/Provas/001_XX_CB1_01.pdf"
        )

    def test_arquivo_fora_do_manifesto_e_pulado(self, tmp_path):
        _montar_data_dir(tmp_path)
        (tmp_path / "2025/CEBRASPE/XX/Provas/orfao.pdf").write_bytes(b"%PDF-")
        arquivos = {
            p["arquivo"] for p in stats_writer.coletar_pdfs_fila(tmp_path)["XX_25"]
        }
        assert "orfao.pdf" not in arquivos


def _postgres_disponivel() -> bool:
    try:
        stats_writer.conectar(connect_timeout=2).close()
        return True
    except (RuntimeError, psycopg2.Error):
        return False


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)
class TestGravacaoPostgres:
    """Roda contra o Postgres real, num schema temporário descartado no fim."""

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

    @staticmethod
    def _contagens(conn) -> dict:
        tabelas = (
            "concursos",
            "cargos_editais",
            "taxonomia_itens",
            "dim_materia",
            "dim_topico",
            "provas",
            "provas_cargos",
            "fila_extracao_questoes",
        )
        with conn.cursor() as cur:
            resultado = {}
            for tabela in tabelas:
                cur.execute(
                    sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(tabela))
                )
                resultado[tabela] = cur.fetchone()[0]
            return resultado

    def _preparar(self, tmp_path, topicos=("Topico A", "Topico B")):
        revisao_dir = tmp_path / "revisao"
        revisao_dir.mkdir(exist_ok=True)
        (revisao_dir / "Ed_1_XX_25.json").write_text(
            json.dumps(_resultado(topicos_especificos=topicos), ensure_ascii=False),
            encoding="utf-8",
        )
        data_dir = tmp_path / "data"
        if not data_dir.exists():
            _montar_data_dir(data_dir)
        return revisao_dir, data_dir

    def test_carga_completa_e_idempotente(self, conn, tmp_path, caplog):
        revisao_dir, data_dir = self._preparar(tmp_path)
        with caplog.at_level("INFO"):
            totais = stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        assert (
            "[STATS] XX_25 (pendente): 2 cargos, 3 tópicos gravados, 0 com cargos restritos."
            in caplog.text
        )
        assert "· revisão: 1 pendente" in caplog.text
        assert totais == {
            "concursos": 1,
            "topicos": 3,
            "provas": 2,
            "fila": 4,
            "pulados": 1,
            # PADRAO_CARGO_1.pdf: o concurso de teste não tem discursiva, e o
            # PDF falso não tem conteúdo para ligar (Etapa 5C).
            "gabaritos_sem_prova": 1,
        }
        primeira = self._contagens(conn)

        stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        assert self._contagens(conn) == primeira

        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.identificador, array_agg(ce.numero ORDER BY ce.numero) FROM provas p "
                "JOIN provas_cargos pc ON pc.prova_id = p.id JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id "
                "GROUP BY 1 ORDER BY 1"
            )
            assert cur.fetchall() == [("001", [1]), ("CB1", [1, 2])]
            cur.execute(
                "SELECT arquivo, categoria, prova_id IS NOT NULL FROM fila_extracao_questoes ORDER BY arquivo"
            )
            assert cur.fetchall() == [
                ("001_XX_001_01.pdf", "prova", True),
                ("001_XX_CB1_01.pdf", "prova", True),
                ("Gab_Definitivo_001_XX_CB1_01.pdf", "gabarito", True),
                ("PADRAO_CARGO_1.pdf", "gabarito", False),
            ]
            cur.execute(
                "SELECT count(*) FROM taxonomia_itens WHERE cargo_edital_id IS NULL"
            )
            assert cur.fetchone()[0] == 1  # o chunk básico

    def test_reextracao_remove_topico_sem_deixar_orfao(self, conn, tmp_path, caplog):
        revisao_dir, data_dir = self._preparar(tmp_path)
        stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)

        revisao_dir, data_dir = self._preparar(tmp_path, topicos=("Topico A",))
        with caplog.at_level("INFO"):
            stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        assert "[STATS] Órfãs removidas: 0 matérias, 1 tópicos." in caplog.text

        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM dim_topico ORDER BY nome")
            assert [r[0] for r in cur.fetchall()] == ["Ortografia oficial", "Topico A"]
            cur.execute("SELECT count(*) FROM taxonomia_itens")
            assert cur.fetchone()[0] == 2

    def test_status_da_fila_nao_e_resetado(self, conn, tmp_path):
        revisao_dir, data_dir = self._preparar(tmp_path)
        stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        with conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE fila_extracao_questoes SET status = 'concluido' WHERE arquivo = '001_XX_001_01.pdf'"
            )

        stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, prova_id IS NOT NULL FROM fila_extracao_questoes WHERE arquivo = '001_XX_001_01.pdf'"
            )
            assert cur.fetchone() == ("concluido", True)

    def test_gravacao_cargos_restritos(self, conn, tmp_path, caplog):
        resultado = _resultado()
        resultado["resultados"][0]["cargos_restritos"] = [1, 8]
        resultado["resultados"][1]["cargos_restritos"] = None

        revisao_dir = tmp_path / "revisao"
        revisao_dir.mkdir(exist_ok=True)
        (revisao_dir / "Ed_1_XX_25.json").write_text(
            json.dumps(resultado, ensure_ascii=False), encoding="utf-8"
        )
        data_dir = tmp_path / "data"
        _montar_data_dir(data_dir)

        with caplog.at_level("INFO"):
            stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn)
        assert "3 tópicos gravados, 1 com cargos restritos." in caplog.text

        with conn.cursor() as cur:
            cur.execute(
                "SELECT topico_nome, cargos_restritos FROM taxonomia_itens ORDER BY id"
            )
            rows = cur.fetchall()
            assert rows[0] == ("Ortografia oficial", [1, 8])
            assert rows[1] == ("Topico A", None)
            assert rows[2] == ("Topico B", None)

            cur.execute(
                "SELECT topico, cargos_restritos FROM vw_taxonomia_detalhe ORDER BY topico"
            )
            view_rows = {topico: restritos for topico, restritos in cur.fetchall()}
            assert view_rows["Ortografia oficial"] == [1, 8]
            assert view_rows["Topico A"] is None
            assert view_rows["Topico B"] is None

    def test_arvore_so_carrega_aprovado(self, conn, tmp_path):
        import json
        resultado = _resultado(
            topicos_especificos=(
                "Atos administrativos",
                "Ato administrativo",
                "Topico B",
            )
        )
        resultado["resultados"][1]["materia_normalizada"] = "NOÇÕES DE DIREITO"
        revisao_dir = tmp_path / "revisao"
        revisao_dir.mkdir()
        (revisao_dir / "Ed_1_XX_25.json").write_text(
            json.dumps(resultado, ensure_ascii=False), encoding="utf-8"
        )
        data_dir = tmp_path / "data"
        _montar_data_dir(data_dir)

        arvore_path = tmp_path / "canonico" / "arvore.json"
        arvore_path.parent.mkdir(parents=True, exist_ok=True)
        arvore_dados = {
            "nos": {
                "M-1": {"nivel": "materia", "nome": "DIREITO", "pai": None, "origem": "semente", "status": "ativo"}
            },
            "mapeamentos": {
                "nocoes de direito": [{"no_id": "M-1", "status": "proposto"}]
            }
        }
        arvore_path.write_text(json.dumps(arvore_dados, ensure_ascii=False), encoding="utf-8")

        stats_writer.gravar_estatisticas(revisao_dir, data_dir, conn=conn, arvore_path=arvore_path)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM materia_no")
            assert cur.fetchone()[0] == 0

