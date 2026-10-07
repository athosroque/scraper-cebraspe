"""Regras de conta e histórico (5F.3): correção, gravação e desempenho por nó."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.modelos import (
    ConcursoAlvo,
    FiltroEstatistica,
    FiltroQuestoes,
    ItemPlano,
    NoDesempenho,
    PlanoEstudo,
    Prioridade,
    RespostaResultado,
    ResumoConta,
    Usuario,
)
from app.repositorio import estatisticas_repo, questoes_repo, usuarios_repo
from app.servicos import questoes_servico


class LoginNecessario(Exception):
    """Filtro de histórico pedido sem usuário logado."""


def entrar_com_google(google_sub: str, email: str, nome: str | None) -> Usuario:
    return Usuario(**usuarios_repo.upsert_usuario(google_sub, email, nome))


def obter_usuario(usuario_id: int) -> Usuario | None:
    linha = usuarios_repo.obter_usuario(usuario_id)
    return Usuario(**linha) if linha else None


def apagar_conta(usuario_id: int) -> bool:
    return usuarios_repo.apagar_usuario(usuario_id)


def responder(
    chave: str, resposta: str, usuario_id: int | None
) -> RespostaResultado | None:
    """Corrige e, com login, grava. Anulada não grava: não há certo nem errado."""
    questao = questoes_servico.obter_questao_por_chave(chave)
    if not questao:
        return None
    acertou = not questao.anulada and questao.gabarito == resposta
    gravar = usuario_id is not None and not questao.anulada
    if gravar:
        usuarios_repo.gravar_resposta(usuario_id, chave, resposta, acertou)
    return RespostaResultado(
        questao_chave=chave,
        resposta=resposta,
        gabarito=questao.gabarito,
        anulada=questao.anulada,
        acertou=acertou,
        gravada=gravar,
    )


def filtros_com_historico(filtros: FiltroQuestoes, usuario_id: int | None) -> dict:
    """Traduz `historico` em chaves a incluir/excluir para o repositório."""
    filtros_dict = filtros.model_dump(exclude_none=True)
    if filtros.historico == "todas":
        return filtros_dict
    if usuario_id is None:
        raise LoginNecessario
    ultimas = usuarios_repo.ultimas_respostas(usuario_id)
    if filtros.historico == "nao_resolvidas":
        filtros_dict["chaves_excluir"] = list(ultimas)
    else:
        quer = {"resolvidas": None, "certas": True, "erradas": False}[filtros.historico]
        filtros_dict["chaves_incluir"] = [
            c for c, acertou in ultimas.items() if quer is None or acertou is quer
        ]
    return filtros_dict


def desempenho(usuario_id: int, filtros: FiltroQuestoes) -> list[NoDesempenho]:
    """Árvore disciplina → assunto → subassunto só com os nós respondidos.

    O `no_id` segue a cascata da listagem (`nos_da_consulta`, 5H.3)."""
    ultimas = usuarios_repo.ultimas_respostas(usuario_id)
    filtros_dict = filtros.model_dump(exclude_none=True)
    if filtros_dict.get("no_id"):
        filtros_dict["no_id"] = questoes_servico.nos_da_consulta(filtros_dict["no_id"])
    linhas = questoes_repo.desempenho_por_no(
        filtros_dict, list(ultimas), list(ultimas.values())
    )
    nos = {
        r["id"]: NoDesempenho(
            id=r["id"],
            nome=r["nome"],
            nivel=r["nivel"],
            total=r["total"],
            acertos=r["acertos"],
            percentual=round(100 * r["acertos"] / r["total"], 1),
        )
        for r in linhas
    }
    raizes = []
    for r in linhas:
        pai = nos.get(r["pai_id"]) if r["pai_id"] else None
        if pai:
            pai.filhos.append(nos[r["id"]])
        else:
            raizes.append(nos[r["id"]])

    def ordenar(lista):
        lista.sort(key=lambda n: (-n.total, n.nome))
        for n in lista:
            ordenar(n.filhos)

    ordenar(raizes)
    return raizes


def resumo(usuario_id: int) -> dict:
    """KPIs da conta pela resposta mais recente de cada questão (regra do `historico`)."""
    ultimas = usuarios_repo.ultimas_respostas(usuario_id)
    total = len(ultimas)
    certas = sum(1 for acertou in ultimas.values() if acertou)
    return {
        "resolvidas": total,
        "certas": certas,
        "erradas": total - certas,
        "percentual": round(100 * certas / total, 1) if total else None,
    }


# -- Resumo e prioridades (5F.8) --
FUSO_DIAS = "America/Sao_Paulo"
MINIMO_RESPOSTAS_PRIORIDADE = 2
# Sem LIMIT efetivo: a incidência precisa cobrir todo subassunto respondido.
_SEM_LIMITE = 100_000


def contar_dias_seguidos(dias: list[date], hoje: date) -> int:
    """Dias consecutivos com resposta terminando hoje (ou ontem, se hoje ainda não teve)."""
    conjunto = set(dias)
    dia = hoje if hoje in conjunto else hoje - timedelta(days=1)
    seguidos = 0
    while dia in conjunto:
        seguidos += 1
        dia -= timedelta(days=1)
    return seguidos


def resumo_completo(usuario_id: int) -> ResumoConta:
    """KPIs de `resumo()` + nota líquida (certo +1, errado −1) e dias seguidos."""
    base = resumo(usuario_id)
    hoje = datetime.now(ZoneInfo(FUSO_DIAS)).date()
    dias = usuarios_repo.dias_com_resposta(usuario_id, FUSO_DIAS)
    return ResumoConta(
        **base,
        nota_liquida=base["certas"] - base["erradas"],
        erradas_pendentes=base["erradas"],
        dias_seguidos=contar_dias_seguidos(dias, hoje),
    )


def _subassuntos(nos: list[NoDesempenho], caminho: tuple[str, ...] = ()):
    for no in nos:
        atual = (*caminho, no.nome)
        if no.nivel == "subassunto":
            yield no, " › ".join(atual)
        yield from _subassuntos(no.filhos, atual)


def prioridades(usuario_id: int, limite: int = 10) -> list[Prioridade]:
    """Subassuntos com ≥ 2 respostas, por incidência na prova × taxa de erro.

    As respostas (role `site_app`) e a incidência (`fn_prova_cobra`, role
    `site_leitura`) são lidas em separado e cruzadas aqui pelo `no_id`:
    nunca um JOIN entre `app.resposta` e as views.
    """
    candidatos = [
        (no, caminho)
        for no, caminho in _subassuntos(desempenho(usuario_id, FiltroQuestoes()))
        if no.total >= MINIMO_RESPOSTAS_PRIORIDADE
    ]
    if not candidatos:
        return []
    incidencia = {
        r["no_id"]: float(r["pct_medio_por_concurso"] or 0)
        for r in estatisticas_repo.prova_cobra(
            "subassunto", FiltroEstatistica().model_dump(), None, _SEM_LIMITE
        )
    }
    itens = []
    for no, caminho in candidatos:
        taxa_erro = round(100 * (no.total - no.acertos) / no.total, 1)
        pct = incidencia.get(no.id, 0.0)
        itens.append(
            Prioridade(
                no_id=no.id,
                nome=no.nome,
                caminho=caminho,
                respondidas=no.total,
                acertos=no.acertos,
                taxa_erro=taxa_erro,
                incidencia=round(pct, 2),
                prioridade=round(pct * taxa_erro / 100, 3),
            )
        )
    itens.sort(key=lambda p: (-p.prioridade, -p.taxa_erro, -p.respondidas, p.nome))
    return itens[: max(1, limite)]


# -- Plano de estudo e concurso-alvo (5F.8) --
class ConcursoInexistente(Exception):
    """Concurso ou cargo sem prova na base."""


def _validar_concurso_cargo(concurso: str, cargo_numero: int) -> None:
    pares = {(c["concurso"], c["cargo_numero"]) for c in estatisticas_repo.cargos()}
    if (concurso, cargo_numero) not in pares:
        raise ConcursoInexistente


def obter_concurso_alvo(usuario_id: int) -> ConcursoAlvo | None:
    usuario = usuarios_repo.obter_usuario(usuario_id)
    if not usuario or not usuario["concurso_alvo"] or not usuario["cargo_alvo"]:
        return None
    return ConcursoAlvo(
        concurso=usuario["concurso_alvo"], cargo_numero=usuario["cargo_alvo"]
    )


def salvar_concurso_alvo(usuario_id: int, alvo: ConcursoAlvo) -> bool:
    """Valida o par na base e grava. Levanta `ConcursoInexistente`."""
    _validar_concurso_cargo(alvo.concurso, alvo.cargo_numero)
    return usuarios_repo.salvar_concurso_alvo(
        usuario_id, alvo.concurso, alvo.cargo_numero
    )


def plano_estudo(usuario_id: int, concurso: str, cargo_numero: int) -> PlanoEstudo:
    """Peso da matéria no cargo × (1 − acerto do usuário na matéria).

    O acerto vem da regra do desempenho (resposta mais recente de cada questão,
    em qualquer prova). As respostas são lidas pela `site_app` e entram nas
    views por parâmetro, nunca num JOIN entre `app.*` e as views.
    """
    _validar_concurso_cargo(concurso, cargo_numero)
    ultimas = usuarios_repo.ultimas_respostas(usuario_id)
    por_materia = {
        r["id"]: r
        for r in questoes_repo.desempenho_por_no(
            {}, list(ultimas), list(ultimas.values())
        )
        if r["nivel"] == "materia"
    }
    itens = []
    for p in estatisticas_repo.peso_materia_cargo(concurso, cargo_numero):
        d = por_materia.get(p["materia_id"])
        total, acertos = (d["total"], d["acertos"]) if d else (0, 0)
        acerto = acertos / total if total else 0.0
        pct = float(p["pct_da_prova"])
        itens.append(
            ItemPlano(
                materia_id=p["materia_id"],
                rotulo_materia=p["rotulo_materia"],
                pct_da_prova=pct,
                respondidas=total,
                acertos=acertos,
                acerto=round(acerto, 4),
                prioridade=round(pct * (1 - acerto), 4),
            )
        )
    itens.sort(key=lambda i: (-i.prioridade, -i.pct_da_prova, i.rotulo_materia))
    return PlanoEstudo(concurso=concurso, cargo_numero=cargo_numero, itens=itens)
