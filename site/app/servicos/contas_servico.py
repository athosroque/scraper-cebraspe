"""Regras de conta e histórico (5F.3): correção, gravação e desempenho por nó."""

from app.modelos import (
    ConcursoAlvo,
    FiltroQuestoes,
    ItemPlano,
    NoDesempenho,
    PlanoEstudo,
    RespostaResultado,
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
    """Árvore matéria → assunto → subassunto só com os nós respondidos."""
    ultimas = usuarios_repo.ultimas_respostas(usuario_id)
    filtros_dict = filtros.model_dump(exclude_none=True)
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
