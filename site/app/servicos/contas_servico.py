"""Regras de conta e histórico (5F.3): correção, gravação e desempenho por nó."""

from app.modelos import FiltroQuestoes, NoDesempenho, RespostaResultado, Usuario
from app.repositorio import questoes_repo, usuarios_repo
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
