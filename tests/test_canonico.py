"""Camada canônica de sinônimos (Etapa 5B, ADR-029)."""

from typing import ClassVar

import pytest

from src import canonico
from src.canonico import NomesOrigem, chave_regra


def _nomes(materias=None, assuntos=None, subassuntos=None) -> NomesOrigem:
    """Monta NomesOrigem com a mesma chave natural do writer (`normalizar`)."""
    from src.comparacao_texto import normalizar

    nomes = NomesOrigem()
    for nome, slugs in (materias or {}).items():
        nomes.materia[normalizar(nome)] = {
            "nome": nome,
            "ocorrencias": {(s, "superior") for s in slugs},
        }
    for (materia, nome), slugs in (assuntos or {}).items():
        nomes.assunto[(normalizar(materia), normalizar(nome))] = {
            "nome": nome,
            "ocorrencias": {(s, "superior") for s in slugs},
        }
    for (materia, topico, nome), slugs in (subassuntos or {}).items():
        nomes.subassunto[
            (normalizar(materia), normalizar(topico), normalizar(nome))
        ] = {
            "nome": nome,
            "ocorrencias": {(s, "medio") for s in slugs},
        }
    return nomes


class TestChaveRegraJunta:
    """Pares reais que a regra determinística deve juntar."""

    @pytest.mark.parametrize(
        "a, b",
        [
            ("Lei nº 9.784/1999", "Lei n o 9.784/1999"),
            ("Lei nº 9.784/1999", "Lei 9.784, de 29 de janeiro de 1999"),
            ("Lei n.º 8.112/1990", "Lei nº 8.112/1990"),
            ("Lei nº 8.666/93 e suas alterações", "Lei nº 8.666/1993"),
            ("Atos administrativos", "Ato administrativo"),
            ("Licitações", "Licitação"),
            ("Gestão por competências", "Gestão por competência"),
            ("Os processos de gestão de pessoas", "Processos de gestão de pessoas"),
            ("Educação corporativa (atuação do pedagogo)", "Educação corporativa"),
            ("5 Administração Pública", "Administração pública"),
            ("NOÇÕES DE DIREITO ADMINISTRATIVO", "DIREITO ADMINISTRATIVO"),
            ("NOÇÕES DE LÍNGUA INGLESA", "LÍNGUA INGLESA"),
            ("Noções de organização administrativa", "Organização administrativa"),
        ],
    )
    def test_mesma_chave(self, a, b):
        assert chave_regra(a).chave == chave_regra(b).chave

    def test_forma_unica_de_norma(self):
        assert chave_regra("Lei nº 9.784/1999").chave == "lei 9784 1999"
        assert chave_regra("Lei n o 9.784/1999").chave == "lei 9784 1999"
        assert chave_regra("Decreto-Lei nº 200/1967").chave == "decreto lei 200 1967"

    def test_nocoes_vira_marca(self):
        assert chave_regra("NOÇÕES DE DIREITO ADMINISTRATIVO") == canonico.ChaveRegra(
            "direito administrativo", True
        )
        assert chave_regra("NOÇÕES SOBRE DEVOPS") == canonico.ChaveRegra("devops", True)
        assert chave_regra("DIREITO ADMINISTRATIVO").nocoes is False


class TestChaveRegraSepara:
    """Falsos positivos reais de similaridade (task.md, 2026-09-22): a regra
    nunca junta; só a aprovação humana poderia."""

    @pytest.mark.parametrize(
        "a, b",
        [
            ("atos administrativos", "contratos administrativos"),
            ("mensuração de ativos", "mensuração de passivos"),
            ("gestão de processos", "gestão de pessoas"),
            (
                "ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA",
                "ADMINISTRAÇÃO ORÇAMENTÁRIA E FINANCEIRA",
            ),
            ("CONTABILIDADE PÚBLICA", "CONTABILIDADE APLICADA AO SETOR PÚBLICO"),
            ("DIREITO CONSTITUCIONAL", "DIREITO CONSTITUCIONAL E PROCESSO LEGISLATIVO"),
            ("Lei nº 8.112/1990", "Lei nº 8.212/1991"),
            ("Ônus da prova", "ONU da prova"),
            ("Nível", "Níveis"),  # -eis não é tratado: sem regra, não junta
        ],
    )
    def test_chaves_diferentes(self, a, b):
        assert chave_regra(a).chave != chave_regra(b).chave


class TestAplicarRegras:
    def test_agrupa_por_regra_e_aprova_automaticamente(self):
        estado = canonico.estado_vazio()
        nomes = _nomes(
            materias={
                "DIREITO ADMINISTRATIVO": ["PF_25"],
                "NOÇÕES DE DIREITO ADMINISTRATIVO": ["STM_25"],
            },
            assuntos={
                ("DIREITO ADMINISTRATIVO", "Atos administrativos"): ["PF_25"],
                ("NOÇÕES DE DIREITO ADMINISTRATIVO", "Ato administrativo"): ["STM_25"],
                ("DIREITO ADMINISTRATIVO", "Contratos administrativos"): ["PF_25"],
            },
        )
        resumo = canonico.aplicar_regras(estado, nomes)
        assert resumo.entradas["materia"] == 1
        assert resumo.entradas["assunto"] == 2  # atos (2 nomes) + contratos

        indice = canonico.indice_aprovado(estado)
        gid = indice.materia["direito administrativo"]
        assert indice.materia["nocoes de direito administrativo"] == gid
        grupo = estado["materia"]["grupos"][gid]
        assert (grupo["origem"], grupo["status"], grupo["nome"]) == (
            "regra",
            "aprovado",
            "DIREITO ADMINISTRATIVO",
        )
        assert (
            indice.assunto[("direito administrativo", "atos administrativos")]
            == indice.assunto[
                ("nocoes de direito administrativo", "ato administrativo")
            ]
        )
        assert (
            indice.assunto[("direito administrativo", "atos administrativos")]
            != indice.assunto[("direito administrativo", "contratos administrativos")]
        )

    def test_ids_estaveis_e_idempotente(self):
        nomes = _nomes(
            materias={"LÍNGUA PORTUGUESA": ["A"], "RACIOCÍNIO LÓGICO": ["B"]}
        )
        e1, e2 = canonico.estado_vazio(), canonico.estado_vazio()
        canonico.aplicar_regras(e1, nomes)
        canonico.aplicar_regras(e2, nomes)
        assert e1 == e2
        antes = repr(e1)
        canonico.aplicar_regras(e1, nomes)
        assert repr(e1) == antes
        assert (
            canonico.id_entrada("materia", None, "lingua portuguesa")
            in e1["materia"]["entradas"]
        )

    def test_proposta_nao_muda_mapeamento_ate_aprovar(self):
        estado = canonico.estado_vazio()
        nomes = _nomes(
            materias={
                "ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA": ["PF_25"],
                "ADMINISTRAÇÃO ORÇAMENTÁRIA E FINANCEIRA": ["STM_25"],
            }
        )
        canonico.aplicar_regras(estado, nomes)
        antes = canonico.indice_aprovado(estado).materia
        membros = list(estado["materia"]["entradas"])
        gid = canonico.registrar_proposta(
            estado, "materia", membros, "AFO", None, "ordem invertida"
        )
        assert estado["materia"]["grupos"][gid]["status"] == "proposto"
        assert canonico.indice_aprovado(estado).materia == antes
        assert len(set(antes.values())) == 2

        canonico.aprovar(estado, gid)
        depois = canonico.indice_aprovado(estado).materia
        assert set(depois.values()) == {gid}

    def test_reexecucao_nao_sobrescreve_decisao_humana(self):
        estado = canonico.estado_vazio()
        nomes = _nomes(
            materias={
                "CONTABILIDADE PÚBLICA": ["A"],
                "CONTABILIDADE APLICADA AO SETOR PÚBLICO": ["B"],
            }
        )
        canonico.aplicar_regras(estado, nomes)
        gid = canonico.registrar_proposta(
            estado, "materia", list(estado["materia"]["entradas"]), "CASP", None, None
        )
        canonico.aprovar(estado, gid)
        canonico.renomear(estado, gid, "Contabilidade Aplicada ao Setor Público")
        canonico.aplicar_regras(estado, nomes)
        grupo = estado["materia"]["grupos"][gid]
        assert (grupo["status"], grupo["origem"], grupo["nome"]) == (
            "aprovado",
            "llm",
            "Contabilidade Aplicada ao Setor Público",
        )
        assert set(canonico.indice_aprovado(estado).materia.values()) == {gid}

    def test_rejeitada_nao_volta_a_ser_proposta(self):
        estado = canonico.estado_vazio()
        canonico.aplicar_regras(estado, _nomes(materias={"X": ["A"], "Y": ["B"]}))
        membros = list(estado["materia"]["entradas"])
        gid = canonico.registrar_proposta(estado, "materia", membros, "X", None, None)
        canonico.rejeitar(estado, gid)
        assert (
            canonico.registrar_proposta(estado, "materia", membros, "X", None, None)
            is None
        )

    def test_assunto_igual_junta_por_regra_depois_da_materia_aprovada(self):
        estado = canonico.estado_vazio()
        nomes = _nomes(
            materias={
                "CONTABILIDADE PÚBLICA": ["A"],
                "CONTABILIDADE APLICADA AO SETOR PÚBLICO": ["B"],
            },
            assuntos={
                ("CONTABILIDADE PÚBLICA", "Receita pública"): ["A"],
                ("CONTABILIDADE APLICADA AO SETOR PÚBLICO", "Receitas públicas"): ["B"],
            },
        )
        canonico.aplicar_regras(estado, nomes)
        # Matérias diferentes: o mesmo assunto fica em escopos diferentes.
        assert len(set(canonico.indice_aprovado(estado).assunto.values())) == 2

        gid = canonico.registrar_proposta(
            estado, "materia", list(estado["materia"]["entradas"]), "CASP", None, None
        )
        canonico.aprovar(estado, gid)
        canonico.aplicar_regras(estado, nomes)
        grupos_assunto = set(canonico.indice_aprovado(estado).assunto.values())
        assert len(grupos_assunto) == 1
        assert next(iter(grupos_assunto)).startswith("AR-")

    def test_aprovar_assunto_exige_pai_decidido(self):
        estado = canonico.estado_vazio()
        nomes = _nomes(
            materias={
                "CONTABILIDADE PÚBLICA": ["A"],
                "CONTABILIDADE APLICADA AO SETOR PÚBLICO": ["B"],
            },
            assuntos={
                ("CONTABILIDADE PÚBLICA", "Receita pública"): ["A"],
                ("CONTABILIDADE APLICADA AO SETOR PÚBLICO", "Receita orçamentária"): [
                    "B"
                ],
            },
        )
        canonico.aplicar_regras(estado, nomes)
        canonico.registrar_proposta(
            estado, "materia", list(estado["materia"]["entradas"]), "CASP", None, None
        )
        proposta = canonico.registrar_proposta(
            estado, "assunto", list(estado["assunto"]["entradas"]), "R", None, None
        )
        with pytest.raises(canonico.DecisaoInvalida):
            canonico.aprovar(estado, proposta)

    def test_mover_para_novo_grupo(self):
        estado = canonico.estado_vazio()
        canonico.aplicar_regras(
            estado, _nomes(materias={"X": ["A"], "Y": ["B"], "Z": ["C"]})
        )
        e_x, e_y, e_z = sorted(
            estado["materia"]["entradas"],
            key=lambda e: estado["materia"]["entradas"][e]["chave_regra"],
        )
        gid = canonico.registrar_proposta(
            estado, "materia", [e_x, e_y, e_z], "XYZ", None, None
        )
        novo = canonico.mover(estado, e_z, "NOVO")
        assert estado["materia"]["grupos"][gid]["membros"] == sorted([e_x, e_y])
        assert estado["materia"]["grupos"][novo]["origem"] == "humano"
        canonico.aprovar(estado, gid)
        indice = canonico.indice_aprovado(estado)
        assert indice.materia["x"] == indice.materia["y"] == gid
        assert indice.materia["z"] == novo


class TestValidarAgrupamento:
    BLOCOS: ClassVar[dict] = {"B1": ["i1", "i2", "i3"], "B2": ["i4"]}

    def test_valido(self):
        assert canonico.validar_agrupamento(
            self.BLOCOS, [["i1", "i2"], ["i3"], ["i4"]]
        ) == (None, None)

    @pytest.mark.parametrize(
        "grupos, motivo",
        [
            (
                [["i1", "i2", "i3"], ["i4"], ["i9"]],
                canonico.STATUS_FALHA_ID_DESCONHECIDO,
            ),
            ([["i1", "i2"], ["i2", "i3"], ["i4"]], canonico.STATUS_FALHA_ID_DUPLICADO),
            ([["i1", "i2"], ["i4"]], canonico.STATUS_FALHA_ID_AUSENTE),
            ([["i1", "i2"], ["i3", "i4"]], canonico.STATUS_FALHA_GRUPO_ENTRE_BLOCOS),
        ],
    )
    def test_falhas_tipadas(self, grupos, motivo):
        assert canonico.validar_agrupamento(self.BLOCOS, grupos)[0] == motivo


def test_proposta_redundante_some_quando_a_regra_junta():
    estado = canonico.estado_vazio()
    nomes = _nomes(
        materias={
            "CONTABILIDADE PÚBLICA": ["A"],
            "CONTABILIDADE APLICADA AO SETOR PÚBLICO": ["B"],
        },
        assuntos={
            ("CONTABILIDADE PÚBLICA", "Receita pública"): ["A"],
            ("CONTABILIDADE APLICADA AO SETOR PÚBLICO", "Receita pública"): ["B"],
        },
    )
    canonico.aplicar_regras(estado, nomes)
    mat = canonico.registrar_proposta(
        estado, "materia", list(estado["materia"]["entradas"]), "CASP", None, None
    )
    ass = canonico.registrar_proposta(
        estado, "assunto", list(estado["assunto"]["entradas"]), "Receita", mat, None
    )
    canonico.aprovar(estado, mat)
    canonico.aplicar_regras(estado, nomes)
    assert ass not in estado["assunto"]["grupos"]
    assert len(set(canonico.indice_aprovado(estado).assunto.values())) == 1
