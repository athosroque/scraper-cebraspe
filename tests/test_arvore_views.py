"""Views de "o que o edital cobra" sobre a árvore mestre (Etapa 5B.1, ADR-030).

Roda contra o Postgres real, num schema temporário descartado no fim.
"""

import json
import uuid

import pytest

from src import stats_writer
from src.arvore import ArvoreMestre, Mapeamento, criar_no, fundir_nos, mapear, salvar
from tests.test_stats_writer import _postgres_disponivel

CARGOS = [
    {"numero": 1, "nome": "ANALISTA", "nivel": "superior"},
    {"numero": 2, "nome": "TÉCNICO", "nivel": "medio"},
    {"numero": 3, "nome": "AUDITOR", "nivel": "superior"},
]


def _chunk(indice, materia, topicos, *, cargo=None, restritos=None, nivel="superior"):
    return {
        "chunk_index": indice,
        "cargo": f"CARGO {cargo}" if cargo else None,
        "materia_chunk": materia,
        "tipo_conhecimento": "especifico" if cargo else "basico",
        "nivel": nivel,
        "cargo_numero": cargo,
        "materia_normalizada": materia,
        "apenas_discursiva": False,
        "cargos_restritos": restritos,
        "taxonomia_extraida": {
            "materia": materia,
            "topicos": [{"nome": n, "subtopicos": subs} for n, subs in topicos],
        },
    }


def _edital(slug, chunks, aprovado):
    return {
        "edital": f"Ed_{slug}.pdf",
        "concurso": {"slug": slug, "orgao": slug.split("_")[0], "ano": 2025},
        "cargos": CARGOS,
        "total_chunks": len(chunks),
        "extraidos_com_sucesso": len(chunks),
        "falhas": 0,
        "chunks_com_falha": [],
        "status_revisao_humana": "APROVADO em teste" if aprovado else "PENDENTE",
        "resultados": chunks,
    }


DA = "direito administrativo"
LP = "lingua portuguesa"
COMPOSTO = f"{DA}|disposicoes gerais servidores publicos"


def _arvore() -> ArvoreMestre:
    arv = ArvoreMestre()
    criar_no(arv, "materia", "Direito Administrativo", None, id_override="M-DA")
    criar_no(arv, "assunto", "Disposições gerais", "M-DA", id_override="A-DG")
    criar_no(arv, "assunto", "Servidores públicos", "M-DA", id_override="A-SP")
    criar_no(arv, "subassunto", "Regime jurídico", "A-DG", id_override="S-RJ")
    criar_no(arv, "subassunto", "Estabilidade", "A-SP", id_override="S-EST")
    criar_no(arv, "materia", "Língua Portuguesa", None, id_override="M-LP")
    criar_no(arv, "assunto", "Ortografia", "M-LP", id_override="A-OR")
    criar_no(arv, "assunto", "Ortografia (antigo)", "M-LP", id_override="A-OLD")
    criar_no(
        arv, "assunto", "Proposta", "M-LP", status="proposto", id_override="A-PROP"
    )
    criar_no(
        arv, "assunto", "Aposentado", "M-LP", status="aposentado", id_override="A-APO"
    )

    mapear(arv, DA, ["M-DA"])
    mapear(arv, COMPOSTO, ["A-DG", "A-SP"])  # composto → 2 nós
    mapear(arv, f"{COMPOSTO}|regime juridico", ["S-RJ"])
    mapear(arv, f"{DA}|disposicoes gerais", ["A-DG"])
    mapear(arv, f"{DA}|servidores publicos", ["A-SP"])
    mapear(arv, f"{DA}|servidores publicos|estabilidade", ["S-EST"])
    mapear(arv, LP, ["M-LP"])
    # Subtópico apontando para um assunto (nível acima).
    mapear(arv, f"{LP}|ortografia|acentuacao", ["A-OR"])
    # Apontamento aprovado para nó que depois foi fundido: a carga resolve.
    arv.mapeamentos[f"{LP}|ortografia"] = [Mapeamento("A-OLD", "humano", "aprovado")]
    fundir_nos(arv, "A-OLD", "A-OR")
    # Apontamento aprovado para nó proposto: não conta antes da aprovação do nó.
    mapear(arv, f"{LP}|tema amplo", ["A-PROP"])
    return arv


@pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)
class TestEditalCobra:
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

    @pytest.fixture
    def carregado(self, conn, tmp_path):
        revisao = tmp_path / "revisao"
        revisao.mkdir()
        aprovado = [
            _chunk(
                0,
                "DIREITO ADMINISTRATIVO",
                [
                    ("Disposições gerais, servidores públicos", ["Regime jurídico"]),
                    ("Disposições gerais", []),
                ],
            ),
            _chunk(
                1,
                "DIREITO ADMINISTRATIVO",
                [("Servidores públicos", ["Estabilidade"])],
                restritos=[3],
            ),
            _chunk(
                2,
                "LÍNGUA PORTUGUESA",
                [("Ortografia", ["Acentuação"]), ("Tema amplo", [])],
                cargo=1,
            ),
        ]
        pendente = [_chunk(0, "LÍNGUA PORTUGUESA", [("Ortografia", [])], cargo=1)]
        for slug, chunks, ok in (("XX_25", aprovado, True), ("YY_25", pendente, False)):
            (revisao / f"Ed_{slug}.json").write_text(
                json.dumps(_edital(slug, chunks, ok), ensure_ascii=False),
                encoding="utf-8",
            )
        arvore_path = tmp_path / "arvore.json"
        salvar(_arvore(), arvore_path)
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        stats_writer.gravar_estatisticas(
            revisao, data_dir, conn=conn, arvore_path=arvore_path
        )
        return conn

    @staticmethod
    def _contagem(conn, view) -> dict[str, int]:
        with conn.cursor() as cur:
            cur.execute(f"SELECT no_id, ocorrencias FROM {view}")
            return dict(cur.fetchall())

    def test_composto_conta_uma_vez_em_cada_no(self, carregado):
        assunto = self._contagem(carregado, "vw_edital_cobra_assunto")
        # Composto + "Disposições gerais" em A-DG; composto + "Servidores" em A-SP.
        # O composto também chega a A-DG pelo subtópico S-RJ, sem contar 2×.
        assert assunto["A-DG"] == 2
        assert assunto["A-SP"] == 2
        assert self._contagem(carregado, "vw_edital_cobra_subassunto") == {
            "S-RJ": 1,
            "S-EST": 1,
        }

    def test_nivel_acima_soma_no_assunto_e_fundido_resolve(self, carregado):
        assunto = self._contagem(carregado, "vw_edital_cobra_assunto")
        # "Ortografia" aponta para o nó fundido A-OLD e o subtópico "Acentuação"
        # aponta direto para o assunto A-OR: um item só.
        assert assunto["A-OR"] == 1
        assert "A-OLD" not in assunto
        assert self._contagem(carregado, "vw_edital_cobra_materia") == {
            "M-DA": 3,
            "M-LP": 2,
        }

    def test_no_proposto_nao_conta(self, carregado):
        assert "A-PROP" not in self._contagem(
            carregado, "vw_edital_cobra_assunto_todas"
        )
        with carregado.cursor() as cur:
            cur.execute("SELECT status FROM no_arvore WHERE id = 'A-PROP'")
            assert cur.fetchone() == ("proposto",)

    def test_variante_todas_inclui_pendente(self, carregado):
        assert self._contagem(carregado, "vw_edital_cobra_assunto")["A-OR"] == 1
        assert self._contagem(carregado, "vw_edital_cobra_assunto_todas")["A-OR"] == 2

    def test_basico_expandido_por_cargo_com_restricao(self, carregado):
        with carregado.cursor() as cur:
            cur.execute(
                "SELECT e.no_id, array_agg(DISTINCT e.cargo_numero ORDER BY e.cargo_numero) "
                "FROM vw_arvore_edital_por_cargo e WHERE e.concurso = 'XX_25' "
                "AND e.no_nivel = 'subassunto' GROUP BY e.no_id"
            )
            cargos = dict(cur.fetchall())
        # Básico superior sem restrição: cargos 1 e 3 (o 2 é de nível médio).
        assert cargos["S-RJ"] == [1, 3]
        # Básico restrito ao cargo 3.
        assert cargos["S-EST"] == [3]

    def test_caminho_resolve_fundido(self, carregado):
        with carregado.cursor() as cur:
            cur.execute(
                "SELECT id, no_efetivo, caminho FROM vw_no_caminho WHERE id IN ('A-OLD', 'A-PROP')"
            )
            assert cur.fetchall() == [
                ("A-OLD", "A-OR", "Língua Portuguesa > Ortografia")
            ]

    def test_no_aposentado_nao_polui_views(self, carregado):
        assert "A-APO" not in self._contagem(carregado, "vw_edital_cobra_assunto")
        assert "A-APO" not in self._contagem(carregado, "vw_edital_cobra_assunto_todas")
        with carregado.cursor() as cur:
            cur.execute("SELECT status FROM no_arvore WHERE id = 'A-APO'")
            assert cur.fetchone() == ("aposentado",)
            cur.execute("SELECT id FROM vw_no_caminho WHERE id = 'A-APO'")
            assert cur.fetchone() is None
