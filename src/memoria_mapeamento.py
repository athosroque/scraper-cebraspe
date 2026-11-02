"""Memória das decisões do dono na árvore mestre (ADR-030, ADR-032).

Funções puras sobre `arvore.ArvoreMestre` (leitura só pelo modelo de `src/arvore.py`,
A28; nada de rede, nada de LLM). Elas transformam o que o dono já decidiu em:

a) `resolver_por_memoria`: resposta determinística para item novo que repete uma
   decisão aprovada (mesma `chave_regra`, mesmo pai efetivo) ou cujo nome é um
   apelido exato de nó (nome de nó fundido, ou de nó ativo de origem humana/semente);
b) `exemplos_aprovados`: pares item -> caminho do nó, para o few-shot do prompt;
c) `rejeicoes`: pares (item, nó) que o dono rejeitou, para o prompt avisar e a
   pós-validação descartar a repetição.

Fonte de decisão: só mapeamento `aprovado`. Proposta `proposto` nunca é fonte (A30);
`llm`+`aprovado` só existe depois que o dono aprova (ciclo de aprendizagem), e
`regra`+`aprovado` é cópia de decisão já aprovada (P52). Este módulo nunca altera
status de nada: quem grava é o chamador, via `arvore.mapear`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from src import arvore
from src.canonico import chave_regra
from src.comparacao_texto import normalizar

# Nível de nó que cada nível de item de edital pode receber (mesma tabela do
# `mapeamento_llm`; repetida aqui para não criar import circular).
NIVEIS_ALVO = {
    "materia": ("materia", "assunto"),
    "assunto": ("assunto", "subassunto"),
    "subassunto": ("subassunto",),
}
_NIVEL_POR_PROFUNDIDADE = {1: "materia", 2: "assunto", 3: "subassunto"}

# Origens cujo nome de nó ativo vale como apelido: curadas pelo dono (ou semeadas
# dos grupos que ele aprovou na 5B). Nó ativo de origem `llm` fica de fora.
_ORIGENS_APELIDO = frozenset({"semente", "humano"})
# Origens de mapeamento aprovado que servem de exemplo no prompt: decisões
# não triviais. `regra` e `semente` são cópias por nome e não ensinam nada.
_ORIGENS_EXEMPLO = frozenset({"humano", "llm"})

_PALAVRAS_VAZIAS = frozenset(
    "para como pelo pela pelos pelas sobre entre desde ate com sem dos das nos nas "
    "uma uns umas que por aos suas seus sua seu nao ser ter".split()
)


def _tokens(texto: str) -> set[str]:
    return {t for t in normalizar(texto).split() if len(t) >= 4} - _PALAVRAS_VAZIAS


def _nos_aprovados(arv: arvore.ArvoreMestre, chave: str) -> frozenset[str]:
    """Nós ativos (resolvidos) de um item com mapeamento aprovado."""
    saida = set()
    for m in arv.mapeamentos.get(chave, []):
        if m.status != "aprovado":
            continue
        final = arvore.resolver_no(arv, m.no_id)
        no = arv.nos.get(final)
        if no and no.status == "ativo":
            saida.add(final)
    return frozenset(saida)


def _partes(chave: str) -> list[str]:
    return chave.split("|")


def nos_aprovados_do_pai(arv: arvore.ArvoreMestre, chave: str) -> frozenset[str]:
    """Pai efetivo do item `chave`: nós aprovados do item do nível de cima."""
    partes = _partes(chave)
    if len(partes) < 2:
        return frozenset()
    return _nos_aprovados(arv, "|".join(partes[:-1]))


def caminho_no(arv: arvore.ArvoreMestre, no_id: str) -> str:
    """`Disciplina › Assunto › Subassunto` do nó (resolve fusão)."""
    nomes = []
    atual = arvore.resolver_no(arv, no_id)
    visto = set()
    while atual and atual in arv.nos and atual not in visto:
        visto.add(atual)
        no = arv.nos[atual]
        nomes.append(no.nome)
        atual = arvore.resolver_no(arv, no.pai) if no.pai else ""
    return " › ".join(reversed(nomes))


# Rejeições ------------------------------------------------------------------------


def rejeicoes(arv: arvore.ArvoreMestre) -> dict[tuple[str, str], str]:
    """Pares que o dono rejeitou: `(chave_regra do item, nó resolvido) -> nome`.

    O par vale para qualquer item de mesma `chave_regra` (a mesma expressão em
    outro edital ou caminho), não só para a chave exata já decidida."""
    pares: dict[tuple[str, str], str] = {}
    for chave, lista in arv.mapeamentos.items():
        nome = _partes(chave)[-1]
        regra = chave_regra(nome).chave
        if not regra:
            continue
        for m in lista:
            if m.status == "rejeitado":
                pares.setdefault((regra, arvore.resolver_no(arv, m.no_id)), nome)
    return pares


# Índice e resolução ----------------------------------------------------------------


@dataclass
class Indice:
    """Decisões aprovadas e apelidos de nó, calculados uma vez por execução."""

    # (nível, nós do pai, chave_regra) -> conjuntos de nós aprovados distintos
    decisoes: dict[tuple, set[frozenset[str]]] = field(default_factory=dict)
    # chave_regra -> nós ativos que têm esse nome (atual ou histórico de fundido)
    apelidos: dict[str, set[str]] = field(default_factory=dict)
    vetados: dict[tuple[str, str], str] = field(default_factory=dict)


def construir_indice(arv: arvore.ArvoreMestre) -> Indice:
    ind = Indice(vetados=rejeicoes(arv))
    for chave in arv.mapeamentos:
        partes = _partes(chave)
        nivel = _NIVEL_POR_PROFUNDIDADE.get(len(partes))
        if not nivel:
            continue
        nos = _nos_aprovados(arv, chave)
        if not nos:
            continue
        pais = nos_aprovados_do_pai(arv, chave)
        if len(partes) > 1 and not pais:
            continue
        regra = chave_regra(partes[-1]).chave
        if regra:
            ind.decisoes.setdefault((nivel, pais, regra), set()).add(nos)
    for no in arv.nos.values():
        if no.status == "fundido" or (
            no.status == "ativo" and no.origem in _ORIGENS_APELIDO
        ):
            regra = chave_regra(no.nome).chave
            final = arvore.resolver_no(arv, no.id)
            alvo = arv.nos.get(final)
            if regra and alvo and alvo.status == "ativo":
                ind.apelidos.setdefault(regra, set()).add(final)
    return ind


def resolver_por_memoria(
    arv: arvore.ArvoreMestre,
    regra: str,
    nivel: str,
    pais: frozenset[str],
    indice: Indice | None = None,
) -> frozenset[str] | None:
    """Nós do item novo, ou None se a memória não resolve sem ambiguidade.

    `regra` é `chave_regra(nome).chave`; `pais` são os nós aprovados do pai efetivo
    (vazio no nível de matéria). Ordem: (1) decisão aprovada de item de mesma regra
    e mesmo pai; (2) apelido exato de nó (nível compatível, mesma disciplina do pai,
    candidato único). Nó de par rejeitado pelo dono nunca é devolvido."""
    if not regra:
        return None
    ind = indice or construir_indice(arv)
    if nivel != "materia" and not pais:
        return None

    def livre(nos: Iterable[str]) -> frozenset[str] | None:
        nos = frozenset(nos)
        if not nos or any((regra, n) in ind.vetados for n in nos):
            return None
        return nos

    candidatos = ind.decisoes.get((nivel, frozenset(pais), regra), set())
    if len(candidatos) == 1:
        (nos,) = candidatos
        return livre(nos)
    if len(candidatos) > 1:
        return None  # decisões divergentes: ambíguo, vai para o LLM/dono

    disciplinas = {arvore.materia_do_no(arv, p) for p in pais} - {""}
    alvo = NIVEIS_ALVO[nivel]
    achados = {
        n
        for n in ind.apelidos.get(regra, set())
        if arv.nos[n].nivel in alvo
        and (nivel == "materia" or arvore.materia_do_no(arv, n) in disciplinas)
    }
    if len(achados) == 1:
        return livre(achados)
    return None


# Exemplos para o few-shot ----------------------------------------------------------


@dataclass(frozen=True)
class Exemplo:
    item: str
    pai: str
    no_id: str
    caminho: str
    origem: str


def exemplos_aprovados(
    arv: arvore.ArvoreMestre,
    nivel: str,
    disciplina: str | Iterable[str],
    n: int,
    referencia: str = "",
    rotulos: dict[str, str] | None = None,
) -> list[Exemplo]:
    """Até `n` pares item -> nó aprovados por humano (ou LLM aprovado pelo dono)
    da mesma `disciplina` (ID ou conjunto de IDs; vazio = qualquer), do mesmo nível.

    Ordena por sobreposição de palavras com `referencia` (os itens do lote), depois
    por decisão não trivial (nome do item diferente do nome do nó) e por nome, para
    ser determinístico. `rotulos` mapeia chave de item -> nome original (acentos)."""
    discs = {disciplina} if isinstance(disciplina, str) else set(disciplina)
    discs.discard("")
    alvo_tokens = _tokens(referencia)
    rotulos = rotulos or {}
    brutos = []
    for chave, lista in arv.mapeamentos.items():
        partes = _partes(chave)
        if _NIVEL_POR_PROFUNDIDADE.get(len(partes)) != nivel:
            continue
        for m in lista:
            if m.status != "aprovado" or m.origem not in _ORIGENS_EXEMPLO:
                continue
            final = arvore.resolver_no(arv, m.no_id)
            no = arv.nos.get(final)
            if not no or no.status != "ativo":
                continue
            if discs and arvore.materia_do_no(arv, final) not in discs:
                continue
            nome = rotulos.get(chave) or partes[-1]
            pai = (
                rotulos.get("|".join(partes[:-1]), partes[-2])
                if len(partes) > 1
                else ""
            )
            trivial = chave_regra(partes[-1]).chave == chave_regra(no.nome).chave
            pontos = len(_tokens(nome) & alvo_tokens)
            brutos.append((-pontos, trivial, nome, final, pai, m.origem))
    brutos.sort()
    saida: list[Exemplo] = []
    vistos = set()
    for _p, _t, nome, final, pai, origem in brutos:
        if (nome, final) in vistos:
            continue
        vistos.add((nome, final))
        saida.append(Exemplo(nome, pai, final, caminho_no(arv, final), origem))
        if len(saida) >= n:
            break
    return saida
