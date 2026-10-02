"""Simulado (5F.5): monta a prova de um cargo e corrige no padrão CEBRASPE."""

from app.modelos import (
    DiscursivaSimulado,
    ItemCorrigido,
    ItemSimulado,
    MateriaSimulado,
    PlacarSimulado,
    ProvaSimulado,
    ResultadoSimulado,
    SimuladoResumo,
)
from app.repositorio import simulados_repo


class SimuladoJaEncerrado(Exception):
    """O simulado gravado já tem nota: corrigir de novo duplicaria respostas."""


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


def placar(situacoes: list[str]) -> PlacarSimulado:
    """Certo +1, errado −1, branco 0; anulada não entra na nota nem no máximo."""
    certas = situacoes.count("certo")
    erradas = situacoes.count("errado")
    anuladas = situacoes.count("anulada")
    return PlacarSimulado(
        certas=certas,
        erradas=erradas,
        brancos=situacoes.count("branco"),
        anuladas=anuladas,
        nota=certas - erradas,
        nota_maxima=len(situacoes) - anuladas,
    )


def corrigir(
    itens: list[dict], respostas: dict[str, str]
) -> tuple[PlacarSimulado, list[MateriaSimulado], list[ItemCorrigido]]:
    """Corrige os itens da prova. Resposta para chave fora da prova é ignorada."""
    corrigidos = []
    por_materia: dict[str, tuple[str, list[str]]] = {}
    for item in itens:
        resposta = respostas.get(item["questao_chave"])
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
        if item.get("materia_id"):
            nome = item.get("materia_nome") or item["materia_id"]
            por_materia.setdefault(item["materia_id"], (nome, []))[1].append(sit)
    materias = [
        MateriaSimulado(materia_id=mid, nome=nome, **placar(sits).model_dump())
        for mid, (nome, sits) in por_materia.items()
    ]
    materias.sort(key=lambda m: (-m.nota_maxima, m.nome))
    return placar([i.situacao for i in corrigidos]), materias, corrigidos


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
    return _resultado(
        registro["concurso"], registro["cargo_numero"], itens, respostas, simulado_id
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
