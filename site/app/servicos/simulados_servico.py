"""Simulado (5F.5): monta a prova de um cargo e corrige no padrão CEBRASPE."""

from app.modelos import (
    DiscursivaSimulado,
    FiltroQuestoes,
    ItemCorrigido,
    ItemSimulado,
    MateriaSimulado,
    PaginaQuestoes,
    PlacarSimulado,
    ProvaSimulado,
    ResultadoSimulado,
    SimuladoResumo,
)
from app.repositorio import simulados_repo
from app.servicos.formatacao import letras_validas


class SimuladoJaEncerrado(Exception):
    """O simulado gravado já tem nota: corrigir de novo duplicaria respostas."""


class SimuladoAberto(Exception):
    """O simulado ainda não foi encerrado: não há situação por item."""


def _figuras(figuras: list[dict] | None) -> list[dict]:
    # Mesmo fallback do detalhe da questão: a figura é servida em `/figuras`.
    figuras = figuras or []
    for f in figuras:
        if "url" not in f and "path_relativo" in f:
            f["url"] = f"/figuras/{f['path_relativo']}"
    return figuras


def montar_prova(concurso: str, cargo_numero: int) -> ProvaSimulado | None:
    linhas = simulados_repo.itens_da_prova(concurso, cargo_numero)
    if not linhas:
        return None
    return ProvaSimulado(
        concurso=concurso,
        cargo_numero=cargo_numero,
        cargo=linhas[0]["cargo"],
        nivel=linhas[0]["nivel"],
        itens_omitidos=simulados_repo.itens_omitidos(concurso, cargo_numero),
        itens=[
            ItemSimulado(**{**r, "figuras": _figuras(r["figuras"])}) for r in linhas
        ],
        discursivas=[
            DiscursivaSimulado(**{**d, "padrao_resposta": None})
            for d in simulados_repo.discursivas_da_prova(concurso, cargo_numero)
        ],
    )


def situacao(gabarito: str, anulada: bool, resposta: str | None) -> str:
    if anulada:
        return "anulada"
    if resposta is None:
        return "branco"
    return "certo" if resposta == gabarito else "errado"


def placar(situacoes: list[str | tuple[str, str]]) -> PlacarSimulado:
    """Pontuação do simulado por formato:
    - certo_errado: acerto = +1, erro = -1, em branco = 0 (anulada desconsiderada).
    - multipla_escolha: acerto = +1, erro = 0, em branco = 0 (anulada desconsiderada).
    """
    certas = 0
    erradas = 0
    brancos = 0
    anuladas = 0
    nota = 0
    for el in situacoes:
        if isinstance(el, tuple):
            sit, tipo = el
        else:
            sit, tipo = el, "certo_errado"

        if sit == "certo":
            certas += 1
            nota += 1
        elif sit == "errado":
            erradas += 1
            if tipo != "multipla_escolha":
                nota -= 1
        elif sit == "anulada":
            anuladas += 1
        elif sit == "branco":
            brancos += 1

    return PlacarSimulado(
        certas=certas,
        erradas=erradas,
        brancos=brancos,
        anuladas=anuladas,
        nota=nota,
        nota_maxima=len(situacoes) - anuladas,
    )


def corrigir(
    itens: list[dict], respostas: dict[str, str]
) -> tuple[PlacarSimulado, list[MateriaSimulado], list[ItemCorrigido]]:
    """Corrige os itens da prova. Resposta para chave fora da prova é ignorada, e
    letra fora do formato do item (`A` num C/E) conta como em branco."""
    corrigidos = []
    situacoes: list[tuple[str, str]] = []
    por_materia: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for item in itens:
        tipo = item.get("tipo", "certo_errado")
        resposta = respostas.get(item["questao_chave"])
        if resposta not in letras_validas(tipo, item.get("alternativas")):
            resposta = None
        sit = situacao(item["gabarito"], item["anulada"], resposta)
        corrigidos.append(
            ItemCorrigido(
                questao_chave=item["questao_chave"],
                numero=item["numero"],
                codigo_caderno=item["codigo_caderno"],
                resposta=resposta,
                gabarito=item["gabarito"],
                situacao=sit,
            )
        )
        situacoes.append((sit, tipo))
        if item.get("materia_id"):
            nome = item.get("materia_nome") or item["materia_id"]
            por_materia.setdefault(item["materia_id"], (nome, []))[1].append(
                (sit, tipo)
            )
    materias = [
        MateriaSimulado(materia_id=mid, nome=nome, **placar(sits).model_dump())
        for mid, (nome, sits) in por_materia.items()
    ]
    materias.sort(key=lambda m: (-m.nota_maxima, m.nome))
    return placar(situacoes), materias, corrigidos


def iniciar(usuario_id: int, concurso: str, cargo_numero: int) -> int | None:
    if not simulados_repo.itens_da_prova(concurso, cargo_numero):
        return None
    return simulados_repo.criar_simulado(usuario_id, concurso, cargo_numero)


def corrigir_avulso(
    concurso: str, cargo_numero: int, respostas: dict[str, str]
) -> ResultadoSimulado | None:
    """Simulado sem login: corrige e não grava nada."""
    itens = simulados_repo.itens_da_prova(concurso, cargo_numero)
    if not itens:
        return None
    return _resultado(concurso, cargo_numero, itens, respostas, None)


def encerrar(
    simulado_id: int, usuario_id: int, respostas: dict[str, str]
) -> ResultadoSimulado | None:
    """Corrige o simulado gravado e grava nota, fim e respostas.

    Só grava resposta de item não anulado e não em branco (como no histórico).
    """
    registro = simulados_repo.obter_simulado(simulado_id, usuario_id)
    if not registro:
        return None
    if registro["fim"] is not None:
        raise SimuladoJaEncerrado
    itens = simulados_repo.itens_da_prova(
        registro["concurso"], registro["cargo_numero"]
    )
    resultado = _resultado(
        registro["concurso"], registro["cargo_numero"], itens, respostas, simulado_id
    )
    gravar = [
        (i.questao_chave, i.resposta, i.situacao == "certo")
        for i in resultado.itens
        if i.situacao in ("certo", "errado")
    ]
    # O UPDATE só pega simulado aberto: dois envios simultâneos gravam uma vez.
    if not simulados_repo.encerrar_simulado(
        simulado_id, usuario_id, resultado.placar.nota, gravar
    ):
        raise SimuladoJaEncerrado
    return _com_historico(resultado, simulado_id, usuario_id)


def _com_historico(
    resultado: ResultadoSimulado, simulado_id: int, usuario_id: int
) -> ResultadoSimulado:
    """Duração (início → encerramento) e nota do simulado anterior."""
    registro = simulados_repo.obter_simulado(simulado_id, usuario_id)
    if registro and registro["fim"] is not None and registro["inicio"] is not None:
        resultado.duracao_segundos = max(
            0, int((registro["fim"] - registro["inicio"]).total_seconds())
        )
    resultado.nota_anterior = simulados_repo.nota_anterior(simulado_id, usuario_id)
    return resultado


def obter_resultado(simulado_id: int, usuario_id: int) -> ResultadoSimulado | None:
    """Resultado de um simulado já encerrado, refeito a partir das respostas gravadas.

    O placar é recalculado com o gabarito atual (não lê `app.simulado.nota`):
    se o gabarito mudar depois, o resultado acompanha. Resposta em item
    anulado não é gravada e aparece em branco.
    """
    registro = simulados_repo.obter_simulado(simulado_id, usuario_id)
    if not registro or registro["fim"] is None:
        return None
    itens = simulados_repo.itens_da_prova(
        registro["concurso"], registro["cargo_numero"]
    )
    respostas = simulados_repo.respostas_do_simulado(simulado_id, usuario_id)
    resultado = _resultado(
        registro["concurso"], registro["cargo_numero"], itens, respostas, simulado_id
    )
    return _com_historico(resultado, simulado_id, usuario_id)


def questoes_por_situacao(
    simulado_id: int,
    usuario_id: int,
    situacao: str,
    pagina: int = 1,
    tamanho_pagina: int = 20,
) -> PaginaQuestoes | None:
    """Questões do simulado encerrado com a situação pedida (errado/branco).

    None se o simulado não existe ou não é do usuário; `SimuladoAberto` se
    ainda não foi encerrado. A situação vem da mesma correção do resultado.
    """
    registro = simulados_repo.obter_simulado(simulado_id, usuario_id)
    if not registro:
        return None
    if registro["fim"] is None:
        raise SimuladoAberto
    resultado = obter_resultado(simulado_id, usuario_id)
    chaves = [i.questao_chave for i in resultado.itens if i.situacao == situacao]
    # Import tardio, como em questoes_servico (evita ciclo com contas_servico).
    from app.servicos import questoes_servico

    return questoes_servico.listar_questoes(
        FiltroQuestoes(utilizaveis="todas"),
        pagina,
        tamanho_pagina,
        chaves_incluir=chaves,
    )


def _resultado(concurso, cargo_numero, itens, respostas, simulado_id):
    placar_geral, materias, corrigidos = corrigir(itens, respostas)
    return ResultadoSimulado(
        simulado_id=simulado_id,
        concurso=concurso,
        cargo_numero=cargo_numero,
        cargo=itens[0]["cargo"],
        itens_omitidos=simulados_repo.itens_omitidos(concurso, cargo_numero),
        placar=placar_geral,
        por_materia=materias,
        itens=corrigidos,
        discursivas=[
            DiscursivaSimulado(**d)
            for d in simulados_repo.discursivas_da_prova(concurso, cargo_numero)
        ],
    )


def obter_simulado(simulado_id: int, usuario_id: int) -> dict | None:
    return simulados_repo.obter_simulado(simulado_id, usuario_id)


def listar(usuario_id: int) -> list[SimuladoResumo]:
    return [SimuladoResumo(**r) for r in simulados_repo.listar_simulados(usuario_id)]
