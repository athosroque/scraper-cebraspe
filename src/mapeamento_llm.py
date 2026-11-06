"""Mapeamento de item novo de edital para a árvore mestre pelo LLM (ADR-030, ADR-032).

O item de edital (matéria, tópico, subtópico) sem entrada em `arvore.mapeamentos`
e que a regra (`canonico.mapear_novos_itens_por_regra`) não resolveu é
apresentado ao modelo com uma LISTA FECHADA de nós ativos: os da disciplina dele
mais os melhores de outras disciplinas por similaridade (KAN-91, P80). O modelo
escolhe até `MAX_NOS_POR_ITEM` nós dessa lista (um, salvo item composto) ou responde
"nenhum". Ele nunca cria nó nem disciplina (P72) e nunca aprova: a proposta entra como `origem="llm"`,
`status="proposto"` (A30); a aprovação é do dono, por `scripts/curar_arvore.py`.

Este módulo não faz I/O de rede por conta própria: a chamada vai por
`llm_openrouter.chamar_llm_json` (reasoning `REASONING_PADRAO`, P16), e toda
leitura e escrita da árvore passa por `src/arvore.py` (A28).
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from src import arvore, canonico, llm_openrouter, memoria_mapeamento
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
# Contexto dos subitens no prompt (extraído do `<edital>.json`, sem texto do PDF).
MAX_SUBITENS = 8
MAX_CARACTERES_SUBITENS = 300
# Few-shot do dono e pares rejeitados no prompt.
MAX_EXEMPLOS = 8
MAX_VETADOS = 15
# Teto de nós candidatos quando a disciplina do item não está resolvida: o
# modelo vê só os nós de mesmo tema (sobreposição de palavras), nunca a árvore toda.
LIMITE_CANDIDATOS_LIVRE = 80
# Marca do desenho de candidatos e prompt (KAN-91, M9). Entra no hash do cache: mudar o
# desenho (candidatos globais, subassunto como alvo de título, até 3 nós) invalida os
# "nenhum" guardados sob o desenho anterior.
DESENHO = "m9-v1"
# Item composto ("A e B") pode apontar até este número de nós (a árvore é N:N).
MAX_NOS_POR_ITEM = 3
# Candidatos globais (KAN-91, M9): por item, os melhores nós de OUTRAS disciplinas
# por similaridade com o nome e os subitens; no lote, no máximo MAX_GLOBAIS_LOTE.
GLOBAIS_POR_ITEM = 4
MAX_GLOBAIS_LOTE = 40
# Para um nó de outra disciplina ser oferecido: massa mínima (soma de idf das palavras
# em comum, que barra o casamento só por palavra comum) e cobertura mínima do nome do
# nó (fração do idf das palavras DELE que o item cobre, o que barra nó longo que só
# repete vocabulário). Palavra que vem só dos subitens ou do pai vale o peso abaixo.
MASSA_MINIMA_GLOBAL = 4.0
COBERTURA_MINIMA_GLOBAL = 0.4
# Sem disciplina, o ranking só traz nó com ao menos esta cobertura do nome dele.
COBERTURA_MINIMA_LIVRE = 0.2
PESO_PALAVRA_FRACA = 0.5
# Título de bloco numa disciplina já inferida: além das disciplinas e assuntos dela, os
# subassuntos mais parecidos com o título e os subitens (o nó natural costuma ser um
# subassunto: "Sistemas operacionais", "Modelagens de dados").
SUBASSUNTOS_POR_TITULO = 40
MAX_NOMES_RANKING = 40

STATUS_FALHA_ID_DESCONHECIDO = "falha_id_desconhecido"
STATUS_FALHA_ITENS_DIVERGENTES = "falha_itens_divergentes"
STATUS_FALHA_VALIDACAO_SCHEMA = "falha_validacao_schema"

# Níveis de nó que cada nível de item de edital pode receber. Título de bloco
# (matéria do edital) vira disciplina, assunto ou subassunto (KAN-91, M9: o nó natural
# de "Sistemas operacionais" é subassunto; a proposta é sempre `proposto`, o título
# nunca cria disciplina, P72); tópico vira assunto ou subassunto; subtópico vira
# subassunto (padrão do que já está mapeado).
NIVEIS_ALVO = {
    "materia": ("materia", "assunto", "subassunto"),
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
- Cada item traz CONTEXTO tirado do próprio edital: "dentro de" (o último elemento é o pai imediato) e "contém" (subitens ou principais tópicos). Use-o só para DESAMBIGUAR o sentido do item (ex: "Arquitetura" de software, de computadores ou de edificações). Se, mesmo com o contexto, o sentido continuar ambíguo, responda "nenhum".
- Se houver "O DONO JÁ DECIDIU ASSIM", siga o mesmo critério nos itens parecidos. Se houver "PARES REJEITADOS", NUNCA proponha esses pares.
- Em geral cada item recebe UM nó. Item COMPOSTO, que junta conceitos distintos ("A e B", "contratos e licitações"), pode receber até 3 nós, um por conceito, em "nos". Nunca ponha dois nós para o mesmo conceito, um nó e o descendente dele, nem nó "só para garantir".
- HERANÇA: o subtópico sem nó mais específico aponta para o nó do TÓPICO. Se o item traz "o pai foi mapeado para: X" e X está em CANDIDATOS, use X para um subtópico que é parte ou detalhe do tópico, em vez de "nenhum"; confiança "media".
- Alguns candidatos vêm de OUTRAS disciplinas (aparecem sob a disciplina deles). Um conceito tem um nó só: se a disciplina do item já tem o nó equivalente, use esse; se só uma outra disciplina trata do conceito (ex: contratos administrativos, LGPD), use o nó dela.
- Forneça uma resposta para CADA item listado.
- "confianca": "alta" (mesmo conceito), "media" (conceito abrangente ou fronteiriço), "baixa" (enquadramento duvidoso).
- Em "justificativa", uma frase curta.

Devolva APENAS JSON válido, sem formatação markdown:
{"itens": [{"numero": 1, "nos": ["N3"], "nenhum": false, "confianca": "alta", "justificativa": "..."}, {"numero": 2, "nos": ["N5", "N9"], "nenhum": false, "confianca": "media", "justificativa": "item composto"}, {"numero": 3, "nos": [], "nenhum": true, "confianca": "alta", "justificativa": "..."}]}"""


class ItemMapeado(BaseModel):
    numero: int | str
    # `no` (um só) continua aceito; `nos` leva até MAX_NOS_POR_ITEM para item composto.
    no: str | None = None
    nos: list[str] = []
    nenhum: bool = False
    confianca: Literal["alta", "media", "baixa"] = "alta"
    justificativa: str = ""

    @property
    def ids_locais(self) -> list[str]:
        """IDs locais escolhidos, sem repetir, na ordem da resposta."""
        vistos: list[str] = []
        for x in [self.no, *self.nos]:
            if x and x not in vistos:
                vistos.append(x)
        return vistos


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
    # Resolvidos antes do LLM pelo passo determinístico (regra de nome / memória).
    resolvidos_regra: int = 0
    resolvidos_memoria: int = 0
    descartados_rejeitados: int = 0
    # Só no dry-run: itens que iriam ao LLM.
    itens_previstos: int = 0
    propostos: int = 0
    # Itens compostos que receberam 2 ou 3 nós (KAN-91).
    propostos_multiplos: int = 0
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
    # Nomes dos filhos diretos no edital (tópicos da matéria; subtópicos do tópico).
    subitens: list[str] = field(default_factory=list)
    # Disciplina inferida pelo cargo do chunk (KAN-86, M4), usada como pai provisório
    # quando nenhum ancestral tem nó. Só restringe os candidatos do prompt; o título
    # continua sem mapeamento e nada é gravado por causa dela.
    disciplina_provisoria: str | None = None


# Levantamento ---------------------------------------------------------------------


def coletar_filhos(revisao_dir: Path) -> dict[str, list[str]]:
    """Chave do item -> nomes dos filhos diretos nos `<edital>.json` (ordem do
    edital, sem repetir): tópicos de uma matéria e subtópicos de um tópico."""
    from src.stats_writer import listar_jsons_edital, montar_carga_concurso

    filhos: dict[str, dict[str, str]] = {}

    def somar(chave: str, nome: str) -> None:
        if nome and nome.strip():
            filhos.setdefault(chave, {}).setdefault(normalizar(nome), nome.strip())

    if not revisao_dir.exists():
        return {}
    for json_path in listar_jsons_edital(revisao_dir):
        try:
            carga = montar_carga_concurso(
                json.loads(json_path.read_text(encoding="utf-8"))
            )
        except (OSError, ValueError, KeyError, TypeError) as e:
            # Contexto é só ajuda de prompt; o erro de fato aparece em `coletar_nomes`.
            logger.warning(
                f"[MAPEAR] Sem contexto de subitens de {json_path.name}: {e}"
            )
            continue
        for item in carga["itens"]:
            m, t = item["materia_chave"], item["topico_chave"]
            somar(arvore.chave_item(m), item["topico_nome"])
            for sub in item["subtopicos"]:
                somar(arvore.chave_item((m, t)), sub if isinstance(sub, str) else "")
    return {k: list(v.values()) for k, v in filhos.items()}


def formatar_subitens(
    nomes: list[str],
    max_itens: int = MAX_SUBITENS,
    max_caracteres: int = MAX_CARACTERES_SUBITENS,
) -> str:
    """`a; b; c…` com no máximo `max_itens` nomes e `max_caracteres` caracteres."""
    if not nomes:
        return ""
    texto = "; ".join(" ".join(n.split()) for n in nomes[:max_itens])
    if len(texto) > max_caracteres:
        return texto[: max_caracteres - 1].rstrip(" ;,") + "…"
    return texto + ("…" if len(nomes) > max_itens else "")


def levantar_pendentes(
    revisao_dir: Path,
    arv: arvore.ArvoreMestre,
    concurso: str | None = None,
    nomes: canonico.NomesOrigem | None = None,
) -> list[Pendente]:
    """Itens dos `<edital>.json` sem entrada em `arv.mapeamentos` (mesma
    chave natural de `canonico.mapear_novos_itens_por_regra`). Item com
    mapeamento rejeitado também conta como já decidido: não é reavaliado."""
    nomes = nomes or canonico.coletar_nomes(revisao_dir)
    filhos = coletar_filhos(revisao_dir)
    provisorias = canonico.disciplinas_provisorias(arv, nomes)
    filhos_bloco = canonico.filhos_por_materia(nomes)
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
                    subitens=filhos.get(chave, []),
                    disciplina_provisoria=canonico.disciplina_provisoria_do_bloco(
                        arv, m, provisorias, filhos_bloco
                    ),
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
    """Disciplinas (nós de matéria) do pai já resolvido e os nós de onde saíram.

    Sem nenhum ancestral com nó, vale a disciplina inferida pelo cargo (pai
    provisório, KAN-86): `(frozenset({disciplina}), [])`, sem nós de origem."""
    nos = _nos_do_pai(arv, pendente)
    disciplinas = {arvore.materia_do_no(arv, n) for n in nos} - {""}
    if not disciplinas and pendente.disciplina_provisoria:
        disciplinas = {pendente.disciplina_provisoria}
    return frozenset(disciplinas), nos


def _ativos(arv: arvore.ArvoreMestre, niveis: tuple[str, ...]) -> list[arvore.NoArvore]:
    return [n for n in arv.nos.values() if n.status == "ativo" and n.nivel in niveis]


def selecionaveis_da_disciplina(
    arv: arvore.ArvoreMestre,
    disciplinas: frozenset[str],
    nivel: str,
    niveis: tuple[str, ...] | None = None,
) -> set[str]:
    """Nós ativos das `disciplinas` que o item de `nivel` pode receber."""
    return {
        n.id
        for n in _ativos(arv, niveis or NIVEIS_ALVO[nivel])
        if arvore.materia_do_no(arv, n.id) in disciplinas
    }


def selecionaveis_por_tema(
    arv: arvore.ArvoreMestre,
    itens: list[Pendente],
    nivel: str,
    indice: IndiceNos | None = None,
) -> set[str]:
    """Sem disciplina resolvida: as disciplinas (se o nível aceita) e os nós de mesmo
    tema, ranqueados pela sobreposição de palavras com o nome, os subitens e os pais
    dos itens (KAN-91: antes só o nome entrava no ranking)."""
    indice = indice or IndiceNos(arv)
    uniao: set[str] = set()
    for fixos in selecionar_lote(arv, indice, itens, frozenset(), nivel).values():
        uniao |= fixos
    return uniao


# Ranking por similaridade (KAN-91, M9) --------------------------------------------


class IndiceNos:
    """Palavras relevantes (as da `chave_regra`, com singular) dos nós ativos de
    assunto e subassunto, com o peso idf de cada palavra na árvore."""

    def __init__(self, arv: arvore.ArvoreMestre) -> None:
        self.arv = arv
        self.palavras: dict[str, frozenset[str]] = {}
        self.regra: dict[str, str] = {}
        df: Counter = Counter()
        for n in _ativos(arv, ("assunto", "subassunto")):
            ps = frozenset(canonico.palavras_relevantes(n.nome))
            self.palavras[n.id] = ps
            self.regra[n.id] = canonico.chave_regra(n.nome).chave
            df.update(ps)
        total = max(len(self.palavras), 1)
        self.idf = {t: math.log(1 + total / c) for t, c in df.items()}
        self.massa_no = {
            i: sum(self.idf[t] for t in ps) or 1.0 for i, ps in self.palavras.items()
        }
        self.disciplina = {i: arvore.materia_do_no(arv, i) for i in self.palavras}

    def pontuar(
        self,
        fortes: frozenset[str],
        fracas: frozenset[str],
        niveis: tuple[str, ...],
        fora_de: frozenset[str] | None = None,
        so_de: frozenset[str] | None = None,
    ) -> list[tuple[float, float, float, str]]:
        """(pontuação, cobertura, massa, id) dos nós de `niveis` com alguma palavra em
        comum, do maior para o menor. Cobertura: fração do idf do NOME DO NÓ que o
        item cobre (as palavras do nome do item valem 1; as dos subitens e do pai,
        `PESO_PALAVRA_FRACA`). Massa: idf das palavras em comum. A pontuação é a
        cobertura mais um bônus pequeno pela massa. `so_de`: só nós dessas
        disciplinas; `fora_de`: exclui-as."""
        achados = []
        for i, ps in self.palavras.items():
            if self.arv.nos[i].nivel not in niveis:
                continue
            disc = self.disciplina[i]
            if (so_de is not None and disc not in so_de) or (
                fora_de is not None and disc in fora_de
            ):
                continue
            forte = sum(self.idf[t] for t in ps & fortes)
            fraco = sum(self.idf[t] for t in (ps & fracas) - fortes)
            massa = forte + fraco
            if massa <= 0:
                continue
            cobertura = (forte + PESO_PALAVRA_FRACA * fraco) / self.massa_no[i]
            achados.append((cobertura + 0.05 * min(massa, 10), cobertura, massa, i))
        achados.sort(key=lambda x: (-x[0], self.arv.nos[x[3]].nome, x[3]))
        return achados


def palavras_do_item(item: Pendente) -> tuple[frozenset[str], frozenset[str]]:
    """(fortes, fracas): palavras do nome do item; e as dos subitens e dos pais."""
    fortes = frozenset(canonico.palavras_relevantes(item.nome))
    fracas: set[str] = set()
    for sub in item.subitens[:MAX_NOMES_RANKING]:
        fracas |= set(canonico.palavras_relevantes(sub))
    for c in item.contexto:
        fracas |= set(canonico.palavras_relevantes(c))
    return fortes, frozenset(fracas - fortes)


def selecionar_lote(
    arv: arvore.ArvoreMestre,
    indice: IndiceNos,
    itens: list[Pendente],
    disciplinas: frozenset[str],
    nivel: str,
    dicas: dict[str, list[str]] | None = None,
) -> dict[str, set[str]]:
    """Candidatos de cada item do lote (chave -> IDs de nós).

    Com disciplina resolvida: os nós dela (no título de bloco, as disciplinas e os
    assuntos, mais os subassuntos mais parecidos) e os melhores nós de OUTRAS
    disciplinas por similaridade, sem título genérico e sem repetir conceito que a
    disciplina já tem (um conceito, um nó; D3 e M6). Sem disciplina: as disciplinas
    (se o nível aceita) e os nós de mesmo tema em toda a árvore. Só oferece nós
    ativos, dos níveis que o item aceita; a escolha continua sendo do modelo.

    `dicas` (chave do item -> nós do pai): o nó de assunto do tópico-pai entra também
    para o subtópico, para que a herança "sem nó mais específico, o subtópico aponta
    para o nó do tópico" (M5) seja possível quando esse nó não é folha de subassunto."""
    alvo = NIVEIS_ALVO[nivel]
    niveis_nos = tuple(x for x in alvo if x != "materia")
    por_item: dict[str, set[str]] = {}
    extras: dict[str, list[tuple[float, str]]] = {}
    if disciplinas:
        niveis_base = ("materia", "assunto") if nivel == "materia" else alvo
        base = selecionaveis_da_disciplina(arv, disciplinas, nivel, niveis_base)
        regras_disc = {indice.regra[i] for i in base if i in indice.regra}
        for it in itens:
            fortes, fracas = palavras_do_item(it)
            fixos = set(base) | {
                n
                for n in (dicas or {}).get(it.chave, [])
                if arv.nos[n].nivel in ("assunto", "subassunto")
            }
            if nivel == "materia":
                subs = indice.pontuar(
                    fortes, fracas, ("subassunto",), so_de=disciplinas
                )
                fixos |= {x[3] for x in subs[:SUBASSUNTOS_POR_TITULO]}
            fora = [
                (pontos, i)
                for pontos, cobertura, massa, i in indice.pontuar(
                    fortes, fracas, niveis_nos, fora_de=disciplinas
                )
                if massa >= MASSA_MINIMA_GLOBAL
                and cobertura >= COBERTURA_MINIMA_GLOBAL
                and indice.regra[i] not in regras_disc
                and not canonico.titulo_generico_global(arv.nos[i].nome)
            ]
            por_item[it.chave] = fixos
            extras[it.chave] = fora[:GLOBAIS_POR_ITEM]
        teto = MAX_GLOBAIS_LOTE
    else:
        fixos_livres = (
            {n.id for n in _ativos(arv, ("materia",))} if "materia" in alvo else set()
        )
        k_item = max(8, LIMITE_CANDIDATOS_LIVRE // max(len(itens), 1))
        for it in itens:
            fortes, fracas = palavras_do_item(it)
            por_item[it.chave] = set(fixos_livres)
            ranqueados = indice.pontuar(fortes, fracas, niveis_nos)
            extras[it.chave] = [
                (x[0], x[3]) for x in ranqueados if x[1] >= COBERTURA_MINIMA_LIVRE
            ][:k_item]
        teto = LIMITE_CANDIDATOS_LIVRE
    melhor: dict[str, float] = {}
    for lista in extras.values():
        for pontos, i in lista:
            melhor[i] = max(melhor.get(i, 0.0), pontos)
    mantidos = {
        i for i, _ in sorted(melhor.items(), key=lambda kv: (-kv[1], kv[0]))[:teto]
    }
    for chave, lista in extras.items():
        por_item[chave] |= {i for _, i in lista if i in mantidos}
    return por_item


def formatar_candidatos(
    arv: arvore.ArvoreMestre,
    selecionaveis: set[str],
    prioridade: frozenset[str] = frozenset(),
) -> tuple[str, dict[str, str]]:
    """Árvore com IDs locais N1..Nn só nos nós selecionáveis; os ancestrais
    entram sem ID, apenas como contexto. As disciplinas de `prioridade` (a do pai ou
    a inferida pelo cargo) vêm primeiro. Devolve (texto, local -> ID)."""
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
    for chave_pai, lista in filhos.items():
        if chave_pai is None:
            lista.sort(key=lambda n: (n.id not in prioridade, n.nome, n.id))
        else:
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
    exemplos: list[str] | None = None,
    vetados: list[str] | None = None,
) -> str:
    linhas = ["CANDIDATOS:", texto_candidatos, ""]
    if exemplos:
        linhas += ["O DONO JÁ DECIDIU ASSIM (siga o mesmo critério):", *exemplos, ""]
    if vetados:
        linhas += [
            "PARES REJEITADOS PELO DONO (NÃO proponha estes pares):",
            *vetados,
            "",
        ]
    linhas.append("ITENS:")
    for i, it in enumerate(itens, start=1):
        trilha = " › ".join(it.contexto) if it.contexto else "(sem pai)"
        linha = f'{i}. [{ROTULO_ITEM[it.nivel]}] "{it.nome}" | dentro de: {trilha}'
        nos_pai = dicas.get(it.chave, [])
        if nos_pai:
            nomes = "; ".join(
                f"{arv.nos[n].nome} ({arv.nos[n].nivel})" for n in nos_pai
            )
            linha += f" | o pai foi mapeado para: {nomes}"
        rotulo_filhos = "principais tópicos" if it.nivel == "materia" else "contém"
        filhos = formatar_subitens(it.subitens)
        if filhos:
            linha += f" | {rotulo_filhos}: {filhos}"
        linhas.append(linha)
    linhas.append("")
    linhas.append("Responda um objeto para cada número de item acima.")
    return "\n".join(linhas)


def _tem_ancestral(arv: arvore.ArvoreMestre, no_ids: list[str]) -> bool:
    """True se algum nó da lista é ancestral de outro da lista."""
    conjunto = set(no_ids)
    for i in conjunto:
        atual = arv.nos.get(i)
        for _ in range(6):
            if atual is None or not atual.pai:
                break
            if atual.pai in conjunto:
                return True
            atual = arv.nos.get(atual.pai)
    return False


def pos_validacao_mapeamento(
    local_para_id: dict[str, str],
    numeros_esperados: list[int],
    ultimo_erro: list[str] | None = None,
    arv: arvore.ArvoreMestre | None = None,
):
    """Validação estrita: IDs da lista, um objeto por item, nós xor `nenhum`, no
    máximo `MAX_NOS_POR_ITEM` nós por item e nunca um nó com o descendente dele
    (um conceito, um nó). O 4º nó é recusado, não cortado."""

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
            {
                x
                for it in resposta.itens
                for x in it.ids_locais
                if x not in local_para_id
            }
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
            ids = it.ids_locais
            if it.nenhum and ids:
                return falha(
                    STATUS_FALHA_VALIDACAO_SCHEMA,
                    f"Item {it.numero} marcado 'nenhum' mas com nó {ids}",
                )
            if not it.nenhum and not ids:
                return falha(
                    STATUS_FALHA_VALIDACAO_SCHEMA,
                    f"Item {it.numero} sem nó e com 'nenhum' false",
                )
            if len(ids) > MAX_NOS_POR_ITEM:
                return falha(
                    STATUS_FALHA_VALIDACAO_SCHEMA,
                    f"Item {it.numero} com {len(ids)} nós (máximo {MAX_NOS_POR_ITEM})",
                )
            if arv is not None and _tem_ancestral(arv, [local_para_id[x] for x in ids]):
                return falha(
                    STATUS_FALHA_VALIDACAO_SCHEMA,
                    f"Item {it.numero} aponta para um nó e o descendente dele "
                    "(um conceito, um nó)",
                )
        return ResultadoPosValidacao(objeto=resposta, metadata={"status": "ok"})

    return validar


def chamar_lote(
    prompt_usuario: str,
    numeros: list[int],
    local_para_id: dict[str, str],
    metadata_base: dict,
    conta: Contabilidade,
    arv: arvore.ArvoreMestre | None = None,
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
            pos_validacao=pos_validacao_mapeamento(
                local_para_id, numeros, ultimo_erro, arv
            ),
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
                f'- No máximo {MAX_NOS_POR_ITEM} nós por item (lista "nos"), nunca um nó '
                "e o descendente dele.\n"
                '- Sem nó adequado: "nenhum": true e "nos": [].'
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


def hash_candidatos(
    chave: str, ids: set[str], contexto: str = "", assinatura: str = ""
) -> str:
    """Muda se o item, os candidatos (árvore curada depois), o contexto dos subitens
    ou a `assinatura` mudar. A assinatura leva o desenho (`DESENHO`) e a disciplina
    provisória pelo cargo (M4) quando é ela que restringe os candidatos: item com
    "nenhum" em cache volta ao modelo se qualquer um deles mudar. Sem contexto e sem
    assinatura, o hash é o mesmo de antes."""
    base = chave + "\n" + "\n".join(sorted(ids))
    if contexto:
        base += "\n#" + contexto
    if assinatura:
        base += "\n@" + assinatura
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


def _assinatura(disciplina_provisoria: frozenset[str]) -> str:
    """Parte do hash do cache que não vem dos candidatos nem dos subitens: o desenho
    do prompt e a disciplina provisória que restringiu os candidatos."""
    return DESENHO + "|" + ",".join(sorted(disciplina_provisoria))


def _rotulos(nomes: canonico.NomesOrigem) -> dict[str, str]:
    """Chave de item -> nome original no edital (para exemplos legíveis)."""
    saida = {}
    for nivel in arvore.NIVEIS:
        for chave, info in getattr(nomes, nivel).items():
            saida[arvore.chave_item(chave)] = info["nome"]
    return saida


def _linhas_exemplos(exemplos: list[memoria_mapeamento.Exemplo]) -> list[str]:
    linhas = []
    for e in exemplos:
        pai = f' (dentro de "{e.pai}")' if e.pai else ""
        linhas.append(f'- "{e.item}"{pai} -> {e.caminho}')
    return linhas


def _linhas_vetados(
    arv: arvore.ArvoreMestre,
    indice: memoria_mapeamento.Indice,
    itens: list[Pendente],
    local_para_id: dict[str, str],
) -> list[str]:
    """Pares rejeitados que dizem respeito ao lote e a nós oferecidos nele."""
    id_para_local = {v: k for k, v in local_para_id.items()}
    regras = {canonico.chave_regra(it.nome).chave for it in itens}
    tokens = set()
    for it in itens:
        tokens |= _tokens(it.nome)
    linhas = []
    for (regra, no_id), nome in sorted(indice.vetados.items()):
        local = id_para_local.get(no_id)
        if not local:
            continue
        if regra in regras or (_tokens(nome) & tokens):
            linhas.append(f'- "{nome}" NÃO é [{local}] {arv.nos[no_id].nome}')
    return linhas[:MAX_VETADOS]


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

    # A memória do dono faz parte do passo determinístico (P73): aqui só se garante
    # que ele já rodou (idempotente) e o LLM trata o que sobrar. No dry-run nada é
    # salvo, mas a árvore em memória enxerga o resultado.
    pre = canonico.mapear_novos_itens(
        revisao_dir, arvore_path, gravar=not dry_run, arvore_mem=arv
    )
    conta.resolvidos_regra = pre.por_nome
    conta.resolvidos_memoria = pre.por_memoria
    nomes = canonico.coletar_nomes(revisao_dir)
    rotulos = _rotulos(nomes)
    todos = levantar_pendentes(revisao_dir, arv, concurso, nomes=nomes)
    conta.pendentes = len(todos)
    indice = memoria_mapeamento.construir_indice(arv)
    ranking = IndiceNos(arv)
    logger.info(f"[MAPEAR] {len(todos)} item(ns) pendente(s) sem nó na árvore.")

    for nivel in arvore.NIVEIS:
        # Relê os pendentes do nível: no modo real, o nível anterior já gravou propostas.
        pend_nivel = [
            p for p in todos if p.nivel == nivel and p.chave not in arv.mapeamentos
        ]
        for rotulo, _nivel, disciplinas, itens, dicas in _grupos(arv, pend_nivel):
            por_item = selecionar_lote(arv, ranking, itens, disciplinas, nivel, dicas)
            if not any(por_item.values()):
                continue
            # A disciplina provisória (M4) só conta quando é ela que restringe.
            hashes = {
                it.chave: hash_candidatos(
                    it.chave,
                    por_item[it.chave],
                    formatar_subitens(it.subitens),
                    _assinatura(
                        disciplinas if not dicas.get(it.chave) else frozenset()
                    ),
                )
                for it in itens
            }
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
            sel = set().union(*(por_item[it.chave] for it in itens))
            texto, local_para_id = formatar_candidatos(arv, sel, disciplinas)
            referencia = " ".join(" ".join([it.nome, *it.contexto]) for it in itens)
            exemplos = _linhas_exemplos(
                memoria_mapeamento.exemplos_aprovados(
                    arv, nivel, disciplinas, MAX_EXEMPLOS, referencia, rotulos
                )
            )
            vetados = _linhas_vetados(arv, indice, itens, local_para_id)
            prompt = montar_prompt(itens, texto, dicas, arv, exemplos, vetados)
            numeros = list(range(1, len(itens) + 1))
            if dry_run:
                conta.chamadas_previstas += 1
                conta.itens_previstos += len(itens)
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
                arv,
            )
            lotes_feitos += 1
            if resposta is None:
                continue
            por_numero = {str(r.numero): r for r in resposta.itens}
            for i, it in enumerate(itens, start=1):
                r = por_numero[str(i)]
                conta.confianca[r.confianca] += 1
                if r.nenhum or not r.ids_locais:
                    conta.nenhum += 1
                    nenhum_cache[it.chave] = {
                        "hash": hashes[it.chave],
                        "justificativa": r.justificativa,
                    }
                    continue
                if it.chave in arv.mapeamentos:
                    continue
                regra_item = canonico.chave_regra(it.nome).chave
                destinos = []
                for local in r.ids_locais:
                    final = arvore.resolver_no(arv, local_para_id[local])
                    if (regra_item, final) in indice.vetados:
                        # Par que o dono já rejeitou: nunca é reproposto.
                        conta.descartados_rejeitados += 1
                    elif final not in destinos:
                        destinos.append(final)
                if not destinos:
                    conta.nenhum += 1
                    nenhum_cache[it.chave] = {
                        "hash": hashes[it.chave],
                        "justificativa": "par rejeitado pelo dono",
                    }
                    continue
                try:
                    arvore.mapear(
                        arv,
                        it.chave,
                        destinos,
                        origem="llm",
                        status="proposto",
                    )
                except arvore.ArvoreInvalida as e:
                    conta.rejeitados_gravacao += 1
                    logger.warning(f"[MAPEAR] Proposta recusada para {it.chave}: {e}")
                    continue
                conta.propostos += 1
                conta.propostos_multiplos += len(destinos) > 1
                nenhum_cache.pop(it.chave, None)
                cache.setdefault("propostos", {})[it.chave] = {
                    "no": destinos[0],
                    "nos": destinos,
                    "confianca": r.confianca,
                    "justificativa": r.justificativa,
                }
            arvore.salvar(arv, arvore_path)
            _salvar_cache(cache, cache_path)
    return conta
