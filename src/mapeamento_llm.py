"""Mapeamento de item novo de edital para a árvore mestre pelo LLM (ADR-030, ADR-032).

O item de edital (matéria, tópico, subtópico) sem entrada em `arvore.mapeamentos`
e que a regra (`canonico.mapear_novos_itens_por_regra`) não resolveu é
apresentado ao modelo com uma LISTA FECHADA de nós ativos da disciplina dele.
O modelo escolhe um nó dessa lista ou responde "nenhum". Ele nunca cria nó nem
disciplina (P72) e nunca aprova: a proposta entra como `origem="llm"`,
`status="proposto"` (A30); a aprovação é do dono, por `scripts/curar_arvore.py`.

Este módulo não faz I/O de rede por conta própria: a chamada vai por
`llm_openrouter.chamar_llm_json` (reasoning `REASONING_PADRAO`, P16), e toda
leitura e escrita da árvore passa por `src/arvore.py` (A28).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from src import arvore, canonico, llm_openrouter
from src.comparacao_texto import normalizar
from src.llm_openrouter import (
    REASONING_PADRAO,
    ResultadoPosValidacao,
    chamar_llm_json,
)
from src.logger import logger

NOME_TRACE = "mapear_itens_novos"
CACHE_NOME = ".mapear_itens_novos_cache.json"

MAX_TOKENS = 12000
TIMEOUT = 180
TENTATIVAS = 2
BACKOFF_SEGUNDOS = 5
ITENS_POR_LOTE = 25
# Teto de nós candidatos quando a disciplina do item não está resolvida: o
# modelo vê só os nós de mesmo tema (sobreposição de palavras), nunca a árvore toda.
LIMITE_CANDIDATOS_LIVRE = 120

STATUS_FALHA_ID_DESCONHECIDO = "falha_id_desconhecido"
STATUS_FALHA_ITENS_DIVERGENTES = "falha_itens_divergentes"
STATUS_FALHA_VALIDACAO_SCHEMA = "falha_validacao_schema"

# Níveis de nó que cada nível de item de edital pode receber. Título de bloco
# (matéria do edital) vira disciplina ou assunto; tópico vira assunto ou
# subassunto; subtópico vira subassunto (padrão do que já está mapeado).
NIVEIS_ALVO = {
    "materia": ("materia", "assunto"),
    "assunto": ("assunto", "subassunto"),
    "subassunto": ("subassunto",),
}
ROTULO_ITEM = {"materia": "Matéria", "assunto": "Tópico", "subassunto": "Subtópico"}

PROMPT_SISTEMA = """Você é um especialista em taxonomia de editais de concursos públicos brasileiros.
Cada ITEM é um trecho do conteúdo programático de um edital que ainda não aponta para a árvore mestre de disciplinas. Sua tarefa é dizer para QUAL nó da lista CANDIDATOS o item aponta.

REGRAS ESTRITAS:
- Use APENAS os IDs locais listados em CANDIDATOS (ex: N1, N2...). NUNCA invente IDs e NUNCA proponha criar nó, renomear ou mover nada.
- Escolha o nó que trata do MESMO conceito do item. Se o item for mais específico que todos os candidatos, escolha o candidato mais próximo apenas quando ele realmente cobrir o item; se for um conceito que a lista não cobre, responda "nenhum".
- Na dúvida entre apontar para um nó duvidoso e responder "nenhum", responda "nenhum": um item sem nó vai para o dono decidir, um nó errado esconde o erro.
- Cada item recebe no máximo UM nó.
- Forneça uma resposta para CADA item listado.
- "confianca": "alta" (mesmo conceito), "media" (conceito abrangente ou fronteiriço), "baixa" (enquadramento duvidoso).
- Em "justificativa", uma frase curta.

Devolva APENAS JSON válido, sem formatação markdown:
{"itens": [{"numero": 1, "no": "N3", "nenhum": false, "confianca": "alta", "justificativa": "..."}, {"numero": 2, "no": null, "nenhum": true, "confianca": "alta", "justificativa": "..."}]}"""


class ItemMapeado(BaseModel):
    numero: int | str
    no: str | None = None
    nenhum: bool = False
    confianca: Literal["alta", "media", "baixa"] = "alta"
    justificativa: str = ""


class RespostaMapeamento(BaseModel):
    itens: list[ItemMapeado]


@dataclass
class Contabilidade:
    chamadas: int = 0
    lotes_ok: int = 0
    lotes_falhos: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    pendentes: int = 0
    pulados_cache: int = 0
    propostos: int = 0
    nenhum: int = 0
    rejeitados_gravacao: int = 0
    falhas: Counter = field(default_factory=Counter)
    confianca: Counter = field(default_factory=Counter)
    # Só no dry-run: estimativa de entrada em caracteres e chamadas previstas.
    chamadas_previstas: int = 0
    caracteres_previstos: int = 0

    def registrar_usage(self, usage: dict | None) -> None:
        usage = usage or {}
        self.tokens_entrada += usage.get("prompt_tokens", 0) or 0
        self.tokens_saida += usage.get("completion_tokens", 0) or 0
        self.custo_usd += float(usage.get("cost", 0) or 0)


@dataclass
class Pendente:
    """Item de edital sem mapeamento na árvore."""

    chave: str  # `arvore.chave_item`
    nivel: Literal["materia", "assunto", "subassunto"]
    nome: str
    # Chaves dos ancestrais, do mais próximo ao mais distante.
    pais: list[str]
    # Nomes dos ancestrais, da matéria para baixo (contexto do prompt).
    contexto: list[str]
    concursos: set[str]
    materia_chave: str


# Levantamento ---------------------------------------------------------------------


def levantar_pendentes(
    revisao_dir: Path,
    arv: arvore.ArvoreMestre,
    concurso: str | None = None,
) -> list[Pendente]:
    """Itens dos `<edital>.json` sem entrada em `arv.mapeamentos` (mesma
    chave natural de `canonico.mapear_novos_itens_por_regra`). Item com
    mapeamento rejeitado também conta como já decidido: não é reavaliado."""
    nomes = canonico.coletar_nomes(revisao_dir)
    pendentes: list[Pendente] = []
    for nivel in arvore.NIVEIS:
        for chave_origem, info in getattr(nomes, nivel).items():
            chave = arvore.chave_item(chave_origem)
            if chave in arv.mapeamentos:
                continue
            concursos = {slug for slug, _ in info["ocorrencias"]}
            if concurso and concurso not in concursos:
                continue
            if nivel == "materia":
                m = chave_origem
                pais: list[str] = []
                contexto: list[str] = []
            elif nivel == "assunto":
                m = chave_origem[0]
                pais = [arvore.chave_item(m)]
                contexto = [nomes.materia[m]["nome"]]
            else:
                m, t = chave_origem[0], chave_origem[1]
                pais = [arvore.chave_item((m, t)), arvore.chave_item(m)]
                contexto = [nomes.materia[m]["nome"], nomes.assunto[(m, t)]["nome"]]
            pendentes.append(
                Pendente(
                    chave=chave,
                    nivel=nivel,
                    nome=info["nome"],
                    pais=pais,
                    contexto=contexto,
                    concursos=concursos,
                    materia_chave=arvore.chave_item(m),
                )
            )
    return pendentes


# Candidatos -----------------------------------------------------------------------

_PALAVRAS_VAZIAS = frozenset(
    "para como pelo pela pelos pelas sobre entre desde ate com sem dos das nos nas "
    "uma uns umas que por aos suas seus sua seu nao ser ter".split()
)


def _tokens(texto: str) -> set[str]:
    return {t for t in normalizar(texto).split() if len(t) >= 4} - _PALAVRAS_VAZIAS


def _nos_do_pai(arv: arvore.ArvoreMestre, pendente: Pendente) -> list[str]:
    """Nós ativos do mapeamento (não rejeitado) do ancestral mais próximo que tem."""
    for chave_pai in pendente.pais:
        nos = []
        for m in arv.mapeamentos.get(chave_pai, []):
            if m.status == "rejeitado":
                continue
            final = arvore.resolver_no(arv, m.no_id)
            no = arv.nos.get(final)
            if no and no.status == "ativo":
                nos.append(final)
        if nos:
            return sorted(set(nos))
    return []


def disciplinas_do_pendente(
    arv: arvore.ArvoreMestre, pendente: Pendente
) -> tuple[frozenset[str], list[str]]:
    """Disciplinas (nós de matéria) do pai já resolvido e os nós de onde saíram."""
    nos = _nos_do_pai(arv, pendente)
    disciplinas = {arvore.materia_do_no(arv, n) for n in nos} - {""}
    return frozenset(disciplinas), nos


def _ativos(arv: arvore.ArvoreMestre, niveis: tuple[str, ...]) -> list[arvore.NoArvore]:
    return [n for n in arv.nos.values() if n.status == "ativo" and n.nivel in niveis]


def selecionaveis_da_disciplina(
    arv: arvore.ArvoreMestre, disciplinas: frozenset[str], nivel: str
) -> set[str]:
    """Nós ativos das `disciplinas` que o item de `nivel` pode receber."""
    return {
        n.id
        for n in _ativos(arv, NIVEIS_ALVO[nivel])
        if arvore.materia_do_no(arv, n.id) in disciplinas
    }


def selecionaveis_por_tema(
    arv: arvore.ArvoreMestre, itens: list[Pendente], nivel: str
) -> set[str]:
    """Sem disciplina resolvida: disciplinas (se o nível aceita) e os nós de mesmo
    tema, ranqueados pela sobreposição de palavras com os itens e seus pais."""
    alvo = NIVEIS_ALVO[nivel]
    texto = set()
    for it in itens:
        texto |= _tokens(it.nome)
        for c in it.contexto:
            texto |= _tokens(c)
    escolhidos: set[str] = set()
    if "materia" in alvo:
        escolhidos |= {n.id for n in _ativos(arv, ("materia",))}
    pontuados = []
    for n in _ativos(arv, tuple(x for x in alvo if x != "materia")):
        pontos = len(_tokens(n.nome) & texto)
        if pontos:
            pontuados.append((-pontos, n.nome, n.id))
    pontuados.sort()
    escolhidos |= {i for _, _, i in pontuados[:LIMITE_CANDIDATOS_LIVRE]}
    return escolhidos


def formatar_candidatos(
    arv: arvore.ArvoreMestre, selecionaveis: set[str]
) -> tuple[str, dict[str, str]]:
    """Árvore com IDs locais N1..Nn só nos nós selecionáveis; os ancestrais
    entram sem ID, apenas como contexto. Devolve (texto, local -> ID)."""
    visiveis = set(selecionaveis)
    for no_id in list(selecionaveis):
        no = arv.nos[no_id]
        while no.pai and no.pai in arv.nos:
            visiveis.add(no.pai)
            no = arv.nos[no.pai]
    filhos: dict[str | None, list[arvore.NoArvore]] = {}
    for no_id in visiveis:
        no = arv.nos[no_id]
        filhos.setdefault(no.pai if no.pai in visiveis else None, []).append(no)
    for lista in filhos.values():
        lista.sort(key=lambda n: (n.nome, n.id))

    linhas: list[str] = []
    local_para_id: dict[str, str] = {}

    def emitir(no: arvore.NoArvore, profundidade: int) -> None:
        recuo = "  " * profundidade
        rotulo = "disciplina" if no.nivel == "materia" else no.nivel
        if no.id in selecionaveis:
            local = f"N{len(local_para_id) + 1}"
            local_para_id[local] = no.id
            linhas.append(f"{recuo}[{local}] {no.nome} ({rotulo})")
        else:
            linhas.append(f"{recuo}{no.nome} ({rotulo}, só contexto)")
        for filho in filhos.get(no.id, []):
            emitir(filho, profundidade + 1)

    for raiz in filhos.get(None, []):
        emitir(raiz, 0)
    return "\n".join(linhas), local_para_id


# Prompt e validação ---------------------------------------------------------------


def montar_prompt(
    itens: list[Pendente],
    texto_candidatos: str,
    dicas: dict[str, list[str]],
    arv: arvore.ArvoreMestre,
) -> str:
    linhas = ["CANDIDATOS:", texto_candidatos, "", "ITENS:"]
    for i, it in enumerate(itens, start=1):
        trilha = " › ".join(it.contexto) if it.contexto else "(sem pai)"
        linha = f'{i}. [{ROTULO_ITEM[it.nivel]}] "{it.nome}" | dentro de: {trilha}'
        nos_pai = dicas.get(it.chave, [])
        if nos_pai:
            nomes = "; ".join(
                f"{arv.nos[n].nome} ({arv.nos[n].nivel})" for n in nos_pai
            )
            linha += f" | o pai foi mapeado para: {nomes}"
        linhas.append(linha)
    linhas.append("")
    linhas.append("Responda um objeto para cada número de item acima.")
    return "\n".join(linhas)


def pos_validacao_mapeamento(
    local_para_id: dict[str, str],
    numeros_esperados: list[int],
    ultimo_erro: list[str] | None = None,
):
    """Validação estrita: ID da lista, um objeto por item, `no` xor `nenhum`."""

    def falha(motivo: str, msg: str, **meta) -> ResultadoPosValidacao:
        if ultimo_erro is not None:
            ultimo_erro[0] = msg
        return ResultadoPosValidacao(
            motivo=motivo,
            erro=f"[{motivo.upper()}] {msg}",
            metadata={"tipo_erro": motivo, **meta},
        )

    def validar(resposta: RespostaMapeamento, _content: str) -> ResultadoPosValidacao:
        desconhecidos = sorted(
            {it.no for it in resposta.itens if it.no and it.no not in local_para_id}
        )
        if desconhecidos:
            return falha(
                STATUS_FALHA_ID_DESCONHECIDO,
                f"IDs locais desconhecidos ou inventados: {desconhecidos}",
                ids=desconhecidos,
            )
        esperados = {str(n) for n in numeros_esperados}
        recebidos = [str(it.numero) for it in resposta.itens]
        faltando = sorted(esperados - set(recebidos))
        sobrando = sorted(set(recebidos) - esperados)
        if faltando or sobrando or len(recebidos) != len(set(recebidos)):
            return falha(
                STATUS_FALHA_ITENS_DIVERGENTES,
                f"Itens divergentes. Faltando: {faltando}, sobrando: {sobrando}, "
                "ou número repetido",
            )
        for it in resposta.itens:
            if it.nenhum and it.no:
                return falha(
                    STATUS_FALHA_VALIDACAO_SCHEMA,
                    f"Item {it.numero} marcado 'nenhum' mas com nó {it.no}",
                )
            if not it.nenhum and not it.no:
                return falha(
                    STATUS_FALHA_VALIDACAO_SCHEMA,
                    f"Item {it.numero} sem nó e com 'nenhum' false",
                )
        return ResultadoPosValidacao(objeto=resposta, metadata={"status": "ok"})

    return validar


def chamar_lote(
    prompt_usuario: str,
    numeros: list[int],
    local_para_id: dict[str, str],
    metadata_base: dict,
    conta: Contabilidade,
) -> RespostaMapeamento | None:
    """Até `TENTATIVAS` chamadas; a 2ª leva o erro da 1ª no prompt."""
    resultado = None
    correcao = ""
    ultimo_erro = [""]
    for tentativa in range(1, TENTATIVAS + 1):
        conta.chamadas += 1
        resultado = chamar_llm_json(
            PROMPT_SISTEMA,
            prompt_usuario + correcao,
            RespostaMapeamento,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT,
            reasoning=REASONING_PADRAO,
            extras_payload={"usage": {"include": True}},
            metadata={**metadata_base, "tentativa": tentativa, "itens": len(numeros)},
            pos_validacao=pos_validacao_mapeamento(local_para_id, numeros, ultimo_erro),
            nome_generation=f"mapear_itens_{metadata_base.get('grupo', 'lote')}",
            nome_trace=NOME_TRACE,
            api_key=llm_openrouter.chave_openrouter(
                llm_openrouter.ETAPA_MAPEAMENTO_ITENS,
                llm_openrouter.ETAPA_CURADORIA_ARVORE[0],
            ),
        )
        conta.registrar_usage(resultado.usage)
        if resultado.motivo is None:
            break
        conta.falhas[resultado.motivo] += 1
        if resultado.motivo in (
            STATUS_FALHA_ID_DESCONHECIDO,
            STATUS_FALHA_ITENS_DIVERGENTES,
            STATUS_FALHA_VALIDACAO_SCHEMA,
        ):
            correcao = (
                f"\n\nATENÇÃO: sua resposta anterior foi rejeitada ({resultado.motivo}). "
                f"Detalhe: {ultimo_erro[0]}\n"
                f"- Responda um objeto para CADA número de item: {numeros}.\n"
                "- Use ESTRITAMENTE os IDs locais [N1, N2, ...] de CANDIDATOS.\n"
                '- Sem nó adequado: "nenhum": true e "no": null.'
            )
        if tentativa < TENTATIVAS:
            time.sleep(BACKOFF_SEGUNDOS)
    if resultado is None or resultado.motivo is not None:
        conta.lotes_falhos += 1
        logger.error(
            f"[MAPEAR] Lote falhou ({resultado.motivo if resultado else 'sem_resultado'})."
        )
        return None
    conta.lotes_ok += 1
    return resultado.objeto


# Cache (idempotência do "nenhum") --------------------------------------------------


def _carregar_cache(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning(f"[MAPEAR] Falha ao ler cache {path}: {e}")
    return {}


def _salvar_cache(cache: dict, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cache, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(f"[MAPEAR] Falha ao salvar cache {path}: {e}")


def hash_candidatos(chave: str, ids: set[str]) -> str:
    """Muda se o item ou o conjunto de candidatos mudar (árvore curada depois)."""
    base = chave + "\n" + "\n".join(sorted(ids))
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# Orquestração -------------------------------------------------------------------


def _grupos(
    arv: arvore.ArvoreMestre, pendentes: list[Pendente]
) -> list[tuple[str, str, frozenset[str], list[Pendente], dict[str, list[str]]]]:
    """(rótulo, nível, disciplinas, itens, dicas) por disciplina; sem pai resolvido,
    por matéria do edital. Mais de um lote por grupo é partido em `ITENS_POR_LOTE`."""
    por_chave: dict[tuple, list[Pendente]] = {}
    dicas: dict[str, list[str]] = {}
    nomes_disc = {n.id: n.nome for n in _ativos(arv, ("materia",))}
    rotulos: dict[tuple, str] = {}
    for p in pendentes:
        disciplinas, nos_pai = disciplinas_do_pendente(arv, p)
        if disciplinas:
            chave = (p.nivel, disciplinas)
            rotulos[chave] = ", ".join(
                sorted(nomes_disc.get(d, d) for d in disciplinas)
            )
            dicas[p.chave] = nos_pai
        else:
            chave = (p.nivel, frozenset(), p.materia_chave)
            rotulos[chave] = (
                f"sem disciplina: {p.contexto[0] if p.contexto else p.nome}"
            )
        por_chave.setdefault(chave, []).append(p)
    grupos = []
    for chave, itens in por_chave.items():
        itens.sort(key=lambda x: x.chave)
        for i in range(0, len(itens), ITENS_POR_LOTE):
            grupos.append(
                (
                    rotulos[chave],
                    chave[0],
                    chave[1],
                    itens[i : i + ITENS_POR_LOTE],
                    dicas,
                )
            )
    grupos.sort(key=lambda g: (arvore.NIVEIS.index(g[1]), g[0], g[3][0].chave))
    return grupos


def mapear_itens_novos(
    revisao_dir: Path,
    arvore_path: Path | None = None,
    *,
    concurso: str | None = None,
    dry_run: bool = False,
    reavaliar: bool = False,
    limite: int | None = None,
) -> Contabilidade:
    """Propõe nó da árvore para cada item de edital pendente.

    Nível a nível (matéria, tópico, subtópico): o que foi proposto num nível serve
    de pai para o seguinte. Grava `proposto/llm` e salva a árvore a cada lote
    (checkpoint). Nunca grava `aprovado`, nunca cria nó. Item já mapeado (aprovado,
    proposto ou rejeitado) não é reavaliado; o "nenhum" fica em cache por hash dos
    candidatos e só é reavaliado com `reavaliar` ou se a árvore mudar.
    """
    arvore_path = arvore_path or arvore.ARVORE_PADRAO
    conta = Contabilidade()
    if not arvore_path.exists():
        logger.warning(f"[MAPEAR] {arvore_path} não existe.")
        return conta
    arv = arvore.carregar(arvore_path)
    cache_path = arvore_path.parent / CACHE_NOME
    cache = _carregar_cache(cache_path)
    nenhum_cache: dict = cache.setdefault("nenhum", {})
    lotes_feitos = 0

    todos = levantar_pendentes(revisao_dir, arv, concurso)
    conta.pendentes = len(todos)
    logger.info(f"[MAPEAR] {len(todos)} item(ns) pendente(s) sem nó na árvore.")

    for nivel in arvore.NIVEIS:
        # Relê os pendentes do nível: no modo real, o nível anterior já gravou propostas.
        pend_nivel = [
            p for p in todos if p.nivel == nivel and p.chave not in arv.mapeamentos
        ]
        for rotulo, _nivel, disciplinas, itens, dicas in _grupos(arv, pend_nivel):
            if disciplinas:
                sel = selecionaveis_da_disciplina(arv, disciplinas, nivel)
            else:
                sel = selecionaveis_por_tema(arv, itens, nivel)
            if not sel:
                continue
            hashes = {it.chave: hash_candidatos(it.chave, sel) for it in itens}
            if not reavaliar:
                restantes = [
                    it
                    for it in itens
                    if nenhum_cache.get(it.chave, {}).get("hash") != hashes[it.chave]
                ]
                conta.pulados_cache += len(itens) - len(restantes)
                itens = restantes
            if not itens:
                continue
            if limite is not None and lotes_feitos >= limite:
                return conta
            texto, local_para_id = formatar_candidatos(arv, sel)
            prompt = montar_prompt(itens, texto, dicas, arv)
            numeros = list(range(1, len(itens) + 1))
            if dry_run:
                conta.chamadas_previstas += 1
                conta.caracteres_previstos += len(PROMPT_SISTEMA) + len(prompt)
                logger.info(
                    f"[MAPEAR] (dry-run) {ROTULO_ITEM[nivel]} | {rotulo}: "
                    f"{len(itens)} item(ns), {len(local_para_id)} candidato(s)."
                )
                lotes_feitos += 1
                continue
            resposta = chamar_lote(
                prompt,
                numeros,
                local_para_id,
                {"etapa": "mapear_itens_novos", "grupo": rotulo, "nivel": nivel},
                conta,
            )
            lotes_feitos += 1
            if resposta is None:
                continue
            por_numero = {str(r.numero): r for r in resposta.itens}
            for i, it in enumerate(itens, start=1):
                r = por_numero[str(i)]
                conta.confianca[r.confianca] += 1
                if r.nenhum or not r.no:
                    conta.nenhum += 1
                    nenhum_cache[it.chave] = {
                        "hash": hashes[it.chave],
                        "justificativa": r.justificativa,
                    }
                    continue
                if it.chave in arv.mapeamentos:
                    continue
                try:
                    arvore.mapear(
                        arv,
                        it.chave,
                        [local_para_id[r.no]],
                        origem="llm",
                        status="proposto",
                    )
                except arvore.ArvoreInvalida as e:
                    conta.rejeitados_gravacao += 1
                    logger.warning(f"[MAPEAR] Proposta recusada para {it.chave}: {e}")
                    continue
                conta.propostos += 1
                nenhum_cache.pop(it.chave, None)
                cache.setdefault("propostos", {})[it.chave] = {
                    "no": local_para_id[r.no],
                    "confianca": r.confianca,
                    "justificativa": r.justificativa,
                }
            arvore.salvar(arv, arvore_path)
            _salvar_cache(cache, cache_path)
    return conta
