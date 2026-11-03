"""De onde veio cada mapeamento de item de edital para nó da árvore (revisão).

Função pura, sem LLM e sem gravar: classifica todo item (disciplina, assunto,
subassunto) de um `<edital>.json` em uma de quatro categorias, para o relatório
de revisão e para a tabela `mapeamento_itens` do `revisao.db` (Datasette).

Não há critério de equivalência próprio (M1, Etapa 5B.4): só vale mapeamento
aprovado na árvore recebida. Quem chama passa a árvore já com o passo
determinístico aplicado (`canonico.arvore_apos_passo`), então o que o passo
mapeia aparece como `auto`/`dono` e o resto como `proposta` ou `sem_equivalente`,
exatamente o que `mapear_novos_itens` deixa pendente (P72, ADR-030).

Categorias (`categoria`):
- `auto`: mapeamento aprovado de `origem="regra"`. A memória das decisões do
  dono grava com a mesma origem, então regra de nome gravada e memória não se
  distinguem na proveniência: o rótulo é "automático (regra/memória)".
- `dono`: aprovado por decisão humana ou pela semente (grupos aprovados da 5B).
- `proposta`: proposto pela IA (`origem="llm"`, status `proposto`), a conferir;
  confiança e justificativa vêm do cache de `src/mapeamento_llm.py`, se houver.
- `sem_equivalente`: nada aprovado nem proposto; o dono precisa decidir.

Sobre essas categorias, `montar_revisao` (M10, Etapa 5B.4, KAN-89) só apresenta:
agrupa os pendentes em seções (decisão de bloco, com sugestão, realmente novo,
travado pelo pai, herda do tópico), sugere os 3 nós mais parecidos por
similaridade de palavras (sem LLM) e escreve a linha `curar_arvore` que o dono
copia. A sugestão nunca decide equivalência: quem diz o que tem destino é só o
passo determinístico (P74), e a aprovação continua sendo do dono (A27, A30).
"""

import json
import math
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from src import arvore as arv_mod
from src import canonico
from src.canonico import normalizar
from src.logger import logger
from src.novidades_edital import _caminho, _nos_aprovados, _proposto
from src.stats_writer import montar_carga_concurso

CACHE_PADRAO = arv_mod.PROJETO_DIR / "canonico" / ".mapear_itens_novos_cache.json"

ROTULOS = {
    "auto": "automático (regra/memória)",
    "dono": "decisão sua / semente",
    "proposta": "proposto pela IA (a conferir)",
    "sem_equivalente": "sem equivalente (a decidir)",
}
CATEGORIAS = tuple(ROTULOS)


def carregar_cache_propostos(path: Path = CACHE_PADRAO) -> dict[str, dict]:
    """`propostos` do cache do mapeamento por LLM; vazio se ausente/corrompido."""
    try:
        dados = json.loads(Path(path).read_text(encoding="utf-8"))
        propostos = dados.get("propostos") or {}
        return {k: v for k, v in propostos.items() if isinstance(v, dict)}
    except (OSError, ValueError, AttributeError):
        return {}


def _categoria_aprovada(origem: str) -> str:
    return "auto" if origem == "regra" else "dono"


def classificar_itens(
    resultado: dict,
    arvore: arv_mod.ArvoreMestre | None = None,
    propostos: dict[str, dict] | None = None,
    disciplinas_conhecidas: list[str] | None = None,  # compatibilidade; sem efeito
) -> list[dict]:
    """Uma linha por item distinto do edital (ordem de aparição).

    Campos: `edital`, `nivel`, `item`, `disciplina`, `assunto`, `chave`,
    `no_id`, `no_caminho`, `origem`, `status`, `categoria`, `confianca`,
    `justificativa`. Para `sem_equivalente`, `status` é `sem_equivalente`.
    """
    if arvore is None:
        arvore = arv_mod.carregar()
    if propostos is None:
        propostos = carregar_cache_propostos()

    def resolver(chave: str):
        """(nós, categoria, origem, status, mapeamento)."""
        aprovados = [
            m
            for m in arvore.mapeamentos.get(chave, [])
            if m.status == "aprovado"
            and arv_mod.resolver_no(arvore, m.no_id) in arvore.nos
        ]
        if aprovados:
            nos = _nos_aprovados(arvore, chave)
            m = aprovados[0]
            return nos, _categoria_aprovada(m.origem), m.origem, "aprovado", m
        m = _proposto(arvore, chave)
        if m is not None:
            return (
                {arv_mod.resolver_no(arvore, m.no_id)},
                "proposta",
                m.origem,
                "proposto",
                m,
            )
        return set(), "sem_equivalente", None, "sem_equivalente", None

    edital = resultado.get("edital")
    linhas: dict[str, dict] = {}

    def registrar(chave, nivel, nome, disc, ass, nos, cat, origem, status, m):
        if chave in linhas:
            return
        no_id = sorted(nos)[0] if nos else None
        info = (propostos.get(chave) or {}) if cat == "proposta" else {}
        confianca = info.get("confianca") or getattr(m, "confianca", None)
        linhas[chave] = {
            "edital": edital,
            "nivel": nivel,
            "item": nome,
            "disciplina": disc,
            "assunto": ass,
            "chave": chave,
            "no_id": no_id,
            "no_caminho": _caminho(arvore, no_id) if no_id else None,
            "origem": origem,
            "status": status,
            "categoria": cat,
            "confianca": confianca,
            "justificativa": info.get("justificativa"),
        }

    for item in montar_carga_concurso(resultado)["itens"]:
        m_chave, m_nome = item["materia_chave"], item["materia_nome"]
        chave_m = arv_mod.chave_item(m_chave)
        nos_m, *res_m = resolver(chave_m)
        registrar(chave_m, "disciplina", m_nome, m_nome, None, nos_m, *res_m)

        t_chave = item["topico_chave"]
        chave_t = arv_mod.chave_item((m_chave, t_chave))
        nos_t, *res_t = resolver(chave_t)
        registrar(chave_t, "assunto", item["topico_nome"], m_nome, None, nos_t, *res_t)

        for sub in item["subtopicos"]:
            s_chave = normalizar(sub)
            if not s_chave:
                continue
            chave_s = arv_mod.chave_item((m_chave, t_chave, s_chave))
            nos_s, *res_s = resolver(chave_s)
            registrar(
                chave_s,
                "subassunto",
                sub,
                m_nome,
                item["topico_nome"],
                nos_s,
                *res_s,
            )
    return list(linhas.values())


def classificar_seguro(resultado: dict, **kwargs) -> list[dict]:
    """Como `classificar_itens`, mas nunca levanta: falha vira lista vazia."""
    try:
        return classificar_itens(resultado, **kwargs)
    except Exception as erro:  # noqa: BLE001
        logger.warning(
            f"{resultado.get('edital')}: mapeamento não classificado: {erro}"
        )
        return []


def contar_por_categoria(linhas: list[dict]) -> dict[str, int]:
    contagem = dict.fromkeys(CATEGORIAS, 0)
    for linha in linhas:
        contagem[linha["categoria"]] += 1
    return contagem


# Sugestão por similaridade e seções de revisão (M10, KAN-89) --------------------------

LIMIAR_SUGESTAO = 0.4  # abaixo disso o item é "realmente novo" (sem sugestão útil)
LIMIAR_ALTO = 0.8  # sugestão forte (consulta salva "sugestões >= 0,8")
PENALIDADE_FORA_DA_DISCIPLINA = 0.85
MIN_LISTAR = 0.3  # abaixo disso a sugestão é ruído e nem aparece
TOP_K = 3

SECOES = {
    "decisao_bloco": "Decisão de bloco",
    "com_sugestao": "Com sugestão",
    "novo": "Realmente novo",
    "travado": "Travado pelo pai",
    "herda_topico": "Herda do tópico",
    "proposta": "Proposta da IA",
    "resolvido": "Resolvido",
}

_VAZIAS = frozenset(
    "de da do das dos e em no na nos nas a o as os ao aos um uma para por com sem "
    "sobre entre ou ate pelo pela pelos pelas".split()
)
_TAMANHO_RAIZ = 6


def _palavras(nome: str) -> dict[str, str]:
    """Raiz (6 letras) -> palavra inteira, sem artigos e preposições."""
    saida: dict[str, str] = {}
    for t in normalizar(nome or "").split():
        if len(t) >= 3 and t not in _VAZIAS:
            t = _singular(t)
            saida.setdefault(t[:_TAMANHO_RAIZ], t)
    return saida


def _singular(palavra: str) -> str:
    """Singular grosseiro só para comparar palavras ("licitações" e "licitação")."""
    if len(palavra) <= 3 or not palavra.isalpha():
        return palavra
    if palavra.endswith(("oes", "aes")):
        return palavra[:-3] + "ao"
    if palavra.endswith("ns"):
        return palavra[:-2] + "m"
    if palavra.endswith("s") and palavra[-2] in "aeo":
        return palavra[:-1]
    return palavra


def _tokens(nome: str) -> frozenset[str]:
    """Raízes (6 letras) das palavras do nome, sem artigos e preposições."""
    return frozenset(_palavras(nome))


class IndiceSimilaridade:
    """Nós ativos da árvore com as raízes das palavras e o peso (IDF) de cada uma.

    Função pura sobre a árvore recebida, sem LLM e sem gravar. Construir uma vez
    por árvore e reaproveitar entre os itens."""

    def __init__(self, arvore):
        self.arvore = arvore
        self.nos = {
            n.id: n
            for n in arvore.nos.values()
            if n.status == "ativo" and n.nivel in ("materia", "assunto", "subassunto")
        }
        self.palavras = {i: _palavras(n.nome) for i, n in self.nos.items()}
        self.tokens = {i: frozenset(p) for i, p in self.palavras.items()}
        self._regra: dict[str, str] = {}
        df: dict[str, int] = defaultdict(int)
        for toks in self.tokens.values():
            for t in toks:
                df[t] += 1
        self._df = df
        self._total = len(self.nos) + 1
        self.filhos: dict[str, list[str]] = defaultdict(list)
        for i, n in self.nos.items():
            if n.pai:
                self.filhos[arv_mod.resolver_no(arvore, n.pai)].append(i)
        self._desc: dict[str, frozenset[str]] = {}
        self._disc: dict[str, str] = {}
        self._cam: dict[str, str] = {}

    def peso(self, token: str) -> float:
        return math.log((self._total + 1) / (self._df.get(token, 0) + 1)) + 1.0

    def descendentes(self, no_id: str) -> frozenset[str]:
        if no_id not in self._desc:
            achados: set[str] = set()
            pilha = list(self.filhos.get(no_id, ()))
            while pilha:
                atual = pilha.pop()
                if atual not in achados:
                    achados.add(atual)
                    pilha.extend(self.filhos.get(atual, ()))
            self._desc[no_id] = frozenset(achados)
        return self._desc[no_id]

    def disciplina(self, no_id: str) -> str:
        """Nome da disciplina (matéria) do nó."""
        if no_id not in self._disc:
            mat = arv_mod.materia_do_no(self.arvore, no_id)
            no = self.arvore.nos.get(mat)
            self._disc[no_id] = no.nome if no else ""
        return self._disc[no_id]

    def caminho(self, no_id: str) -> str:
        if no_id not in self._cam:
            self._cam[no_id] = _caminho(self.arvore, no_id)
        return self._cam[no_id]

    def regra(self, no_id: str) -> str:
        """`chave_regra` do nome do nó (a mesma função do passo determinístico)."""
        if no_id not in self._regra:
            self._regra[no_id] = canonico.chave_regra(self.nos[no_id].nome).chave
        return self._regra[no_id]

    def pontuar(
        self,
        palavras_item: dict[str, str],
        nome_item: str,
        no_id: str,
    ) -> float:
        """Similaridade 0..1 entre o item e o nó: Jaccard e contenção ponderadas
        pelo IDF. Raiz igual com palavra diferente ("programação" e "programática")
        vale 70% da palavra igual. O texto inteiro (SequenceMatcher) só ajuda quando
        as palavras já se sobrepõem (erro de digitação), nunca sozinho."""
        tokens_item = frozenset(palavras_item)
        tn = self.tokens[no_id]
        if not tokens_item or not tn:
            return 0.0
        palavras_no = self.palavras[no_id]
        comum = sum(
            self.peso(t) * (1.0 if palavras_item[t] == palavras_no[t] else 0.7)
            for t in tokens_item & tn
        )
        if not comum:
            return 0.0
        pi = sum(self.peso(t) for t in tokens_item)
        pn = sum(self.peso(t) for t in tn)
        jac = comum / (pi + pn - comum)
        cont = comum / min(pi, pn)
        # contenção só vale cheia quando os dois nomes têm 2+ palavras: uma palavra
        # solta ("armazenamento") contida num nó longo não é equivalência
        tokens_score = 0.5 * jac + 0.5 * cont * min(
            1.0, len(tn) / 2, len(tokens_item) / 2
        )
        if tokens_score < 0.4:
            return tokens_score
        texto = SequenceMatcher(
            None, normalizar(nome_item), normalizar(self.nos[no_id].nome)
        ).ratio()
        return max(tokens_score, 0.9 * texto)


_NIVEIS_CANDIDATOS = {
    "disciplina": ("materia", "assunto"),
    "assunto": ("assunto", "subassunto"),
    "subassunto": ("subassunto", "assunto"),
}


def sugerir_nos(
    indice: IndiceSimilaridade,
    nome: str,
    nivel: str,
    pais: frozenset[str] = frozenset(),
    k: int = TOP_K,
) -> list[dict]:
    """Os `k` nós mais parecidos com o item, do mais ao menos parecido.

    `pais`: nós do pai (aprovados, propostos ou a disciplina provisória). Com
    pais, vale a subárvore deles (e eles mesmos); nós de fora entram com
    penalidade, para o "mesmo assunto em outra disciplina" (contratos de TI em
    Direito Administrativo) aparecer sem passar à frente do conteúdo da disciplina.
    Sem pais (título de bloco sem disciplina provisória), vale a árvore toda.
    Cada sugestão: `no_id`, `score`, `caminho`, `disciplina_do_no`, `no_nivel`."""
    niveis = _NIVEIS_CANDIDATOS.get(nivel, ())
    if nivel == "disciplina" and pais:
        niveis = ("assunto",)  # título de bloco vira assunto da disciplina (P72)
    palavras = _palavras(nome)
    regra_item = canonico.chave_regra(nome).chave
    normas = set(arv_mod.nos_da_mesma_norma(indice.arvore, nome))
    if canonico.titulo_generico(nome):
        return []  # "Conceitos básicos", "Projetos": casa com qualquer disciplina
    dentro: set[str] = set()
    for p in pais:
        if p in indice.nos:
            dentro.add(p)
            dentro |= indice.descendentes(p)
    saida = []
    for i, no in indice.nos.items():
        if no.nivel not in niveis:
            continue
        s = indice.pontuar(palavras, nome, i)
        if s < MIN_LISTAR:
            continue
        if pais and i not in dentro:
            # Nó de outra disciplina só entra com o mesmo nome (contratos de TI em
            # Direito Administrativo) ou sendo a mesma norma (a LGPD em "Legislação");
            # parecido não basta: "programação estruturada" não é "estrutura
            # programática" do orçamento (mesmas travas de M6).
            if indice.regra(i) != regra_item and i not in normas:
                continue
            s *= PENALIDADE_FORA_DA_DISCIPLINA
        saida.append((s, i))
    saida.sort(key=lambda x: (-x[0], x[1]))
    return [
        {
            "no_id": i,
            "score": round(s, 3),
            "caminho": indice.caminho(i),
            "disciplina_do_no": indice.disciplina(i),
            "no_nivel": indice.nos[i].nivel,
        }
        for s, i in saida[:k]
    ]


def contexto_revisao(revisao_dir: Path, arvore) -> dict:
    """Pai provisório pelo cargo (M4) para o `revisao_dir` inteiro, só leitura.

    Devolve `provisorias` (chave do título -> id da disciplina inferida pelo cargo)
    e `filhos` (chave do título -> chaves dos itens abaixo), as entradas de
    `canonico.disciplina_provisoria_do_bloco`. Falha vira contexto vazio."""
    try:
        nomes = canonico.coletar_nomes(revisao_dir)
        return {
            "provisorias": canonico.disciplinas_provisorias(arvore, nomes),
            "filhos": canonico.filhos_por_materia(nomes),
        }
    except Exception as erro:  # noqa: BLE001
        logger.warning(f"Pai provisório indisponível para a revisão: {erro}")
        return {"provisorias": {}, "filhos": {}}


def cargos_por_chave(resultado: dict) -> dict[str, list[str]]:
    """Chave do item -> cargos (ou "conhecimentos básicos") em que ele aparece."""
    carga = montar_carga_concurso(resultado)
    nomes = {c["numero"]: c["nome"] for c in carga["cargos"]}
    saida: dict[str, list[str]] = {}

    def somar(chave: str, rotulo: str) -> None:
        lista = saida.setdefault(chave, [])
        if rotulo not in lista:
            lista.append(rotulo)

    for item in carga["itens"]:
        if item.get("cargo_numero") is not None:
            rotulo = nomes.get(item["cargo_numero"]) or f"cargo {item['cargo_numero']}"
        else:
            rotulo = "conhecimentos básicos"
        m, t = item["materia_chave"], item["topico_chave"]
        somar(arv_mod.chave_item(m), rotulo)
        somar(arv_mod.chave_item((m, t)), rotulo)
        for sub in item["subtopicos"]:
            s = normalizar(sub)
            if s:
                somar(arv_mod.chave_item((m, t, s)), rotulo)
    return saida


def _nos_da_linha(arvore, linha: dict) -> frozenset[str]:
    """Nós do item já decidido (aprovado) ou proposto; vazio se pendente."""
    if linha["categoria"] == "sem_equivalente":
        return frozenset()
    chave = linha["chave"]
    nos = _nos_aprovados(arvore, chave)
    if not nos:
        m = _proposto(arvore, chave)
        nos = {arv_mod.resolver_no(arvore, m.no_id)} if m else set()
    return frozenset(n for n in nos if n in arvore.nos)


def _comando_mapear(chave: str, no_id: str) -> str:
    return f"python -m scripts.curar_arvore --mapear '{chave}:{no_id}'"


def _regra_do_item(linha: dict) -> str:
    return canonico.chave_regra(linha["item"]).chave or normalizar(linha["item"])


def montar_revisao(
    linhas: list[dict],
    arvore,
    *,
    provisorias: dict[str, str] | None = None,
    filhos: dict[str, list[str]] | None = None,
    cargos: dict[str, list[str]] | None = None,
    indice: IndiceSimilaridade | None = None,
    k: int = TOP_K,
) -> list[dict]:
    """Enriquece as linhas de `classificar_itens` para a revisão (só apresentação).

    Cada linha ganha: `secao`, `pai_chave`, `bloco` (título do bloco), `travado`,
    `pai_provisorio`, `disciplina_do_no`, `sugestao_no`, `sugestao_caminho`,
    `score`, `sugestoes` (top-k), `cargos`, `grupo`, `representante`, `repete`,
    `itens_bloco` e `travados` (títulos e assuntos), `curar` (linha pronta de
    `curar_arvore`, para o dono copiar; nunca aplicada aqui). Não muda a categoria
    nem o que é pendente: isso é do passo determinístico (P74, A27)."""
    provisorias = provisorias or {}
    filhos = filhos or {}
    cargos = cargos or {}
    indice = indice or IndiceSimilaridade(arvore)
    por_chave = {linha["chave"]: linha for linha in linhas}
    saida: list[dict] = []

    for linha in linhas:
        nova = dict(linha)
        chave = linha["chave"]
        nivel = linha["nivel"]
        pai_chave = chave.rsplit("|", 1)[0] if nivel != "disciplina" else None
        pai = por_chave.get(pai_chave) if pai_chave else None
        nova.update(
            pai_chave=pai_chave,
            bloco=linha["disciplina"],
            travado=False,
            pai_provisorio=False,
            disciplina_do_no=None,
            sugestao_no=None,
            sugestao_caminho=None,
            score=None,
            sugestoes=[],
            cargos=cargos.get(chave, []),
            curar=None,
        )
        if linha["no_id"]:
            nova["disciplina_do_no"] = indice.disciplina(linha["no_id"]) or None
        if linha["categoria"] in ("auto", "dono"):
            nova["secao"] = "resolvido"
        elif linha["categoria"] == "proposta":
            nova["secao"] = "proposta"
            nova["sugestao_no"] = linha["no_id"]
            nova["sugestao_caminho"] = linha["no_caminho"]
        else:
            _classificar_pendente(nova, pai, arvore, indice, provisorias, filhos, k)
        saida.append(nova)

    _contar_blocos(saida)
    _agrupar_duplicatas(saida)
    return saida


def _classificar_pendente(
    nova: dict,
    pai: dict | None,
    arvore,
    indice: IndiceSimilaridade,
    provisorias: dict[str, str],
    filhos: dict[str, list[str]],
    k: int,
) -> None:
    """Preenche seção, sugestões e comando de um item sem destino."""
    chave, nivel = nova["chave"], nova["nivel"]
    pais: frozenset[str] = frozenset()
    if nivel == "disciplina":
        disc = canonico.disciplina_provisoria_do_bloco(
            arvore, chave, provisorias, filhos
        )
        pais = canonico.pais_efetivos(frozenset(), disc)
        nova["pai_provisorio"] = bool(pais)
    else:
        pais = _nos_da_linha(arvore, pai) if pai else frozenset()
        if not pais and nivel == "assunto":
            disc = canonico.disciplina_provisoria_do_bloco(
                arvore, chave.split("|")[0], provisorias, filhos
            )
            pais = canonico.pais_efetivos(frozenset(), disc)
            nova["pai_provisorio"] = bool(pais)
        if not pais:
            nova["travado"] = True
            nova["secao"] = "travado"
            return
    sugestoes = sugerir_nos(indice, nova["item"], nivel, pais, k)
    nova["sugestoes"] = sugestoes
    if sugestoes:
        topo = sugestoes[0]
        nova.update(
            sugestao_no=topo["no_id"],
            sugestao_caminho=topo["caminho"],
            score=topo["score"],
            disciplina_do_no=topo["disciplina_do_no"],
        )
    forte = bool(sugestoes) and sugestoes[0]["score"] >= LIMIAR_SUGESTAO
    herda = (
        nivel == "subassunto"
        and not forte
        and bool(pais)
        and all(canonico.no_e_folha(arvore, p) for p in pais)
    )
    if nivel == "disciplina":
        nova["secao"] = "decisao_bloco"
    elif herda:
        nova["secao"] = "herda_topico"
        primeiro = sorted(pais)[0]
        nova.update(
            sugestao_no=primeiro,
            sugestao_caminho=indice.caminho(primeiro),
            disciplina_do_no=indice.disciplina(primeiro),
            score=None,
        )
    elif forte:
        nova["secao"] = "com_sugestao"
    else:
        nova["secao"] = "novo"
    # Sem sugestão forte não há linha pronta (título de bloco com score baixo, por exemplo).
    if nova["sugestao_no"] and (forte or nova["secao"] == "herda_topico"):
        nova["curar"] = _comando_mapear(chave, nova["sugestao_no"])


def _contar_blocos(linhas: list[dict]) -> None:
    """`itens_bloco`/`travados` nos títulos; `itens_bloco` nos assuntos é o número
    de subassuntos pendentes abaixo dele. Conta só pendentes (sem destino)."""
    por_bloco: dict[str, list[dict]] = defaultdict(list)
    por_assunto: dict[str, list[dict]] = defaultdict(list)
    for li in linhas:
        if li["categoria"] != "sem_equivalente" or li["nivel"] == "disciplina":
            continue
        por_bloco[li["chave"].split("|")[0]].append(li)
        if li["nivel"] == "subassunto":
            por_assunto[li["pai_chave"]].append(li)
    for li in linhas:
        li["itens_bloco"] = 0
        li["travados"] = 0
        if li["categoria"] != "sem_equivalente":
            continue
        if li["nivel"] == "disciplina":
            filhos = por_bloco.get(li["chave"], [])
            li["itens_bloco"] = len(filhos)
            li["travados"] = sum(1 for f in filhos if f["travado"])
        elif li["nivel"] == "assunto":
            li["itens_bloco"] = len(por_assunto.get(li["chave"], []))
            li["travados"] = li["itens_bloco"]


def _agrupar_duplicatas(linhas: list[dict]) -> None:
    """Mesmo item em blocos ou cargos diferentes vira um grupo (uma linha na
    revisão, com a lista de cargos). A chave do grupo usa `chave_regra` do item e
    do pai, a mesma função do passo; é só apresentação e nunca decide destino."""
    por_chave = {li["chave"]: li for li in linhas}
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for li in linhas:
        pai = por_chave.get(li["pai_chave"]) if li["pai_chave"] else None
        pai_regra = _regra_do_item(pai) if pai and li["nivel"] == "subassunto" else ""
        # com sugestão e novo são a mesma família: o mesmo item pode ter sugestão num
        # bloco e não noutro (o pai muda), e o dono lê uma linha só, a melhor
        familia = "sugestao" if li["secao"] in ("com_sugestao", "novo") else li["secao"]
        grupos[(li["nivel"], familia, _regra_do_item(li), pai_regra)].append(li)
    for n, membros in enumerate(grupos.values(), start=1):
        membros.sort(key=lambda m: -(m["score"] or 0))  # estável: o melhor é o 1º
        todos_cargos: list[str] = []
        for m in membros:
            for c in m["cargos"]:
                if c not in todos_cargos:
                    todos_cargos.append(c)
        blocos = list(dict.fromkeys(m["bloco"] for m in membros))
        chaves = [m["chave"] for m in membros]
        for ordem, m in enumerate(membros):
            m["grupo"] = n
            m["representante"] = ordem == 0
            m["repete"] = len(membros)
            m["cargos_grupo"] = todos_cargos
            m["blocos_grupo"] = blocos
            m["chaves_grupo"] = chaves
        rep = membros[0]
        if rep["curar"] and rep["sugestao_no"]:
            rep["curar_grupo"] = [
                _comando_mapear(c, rep["sugestao_no"]) for c in chaves
            ]


def contar_por_secao(linhas: list[dict], so_representantes: bool = True) -> dict:
    """Linhas por seção; por padrão uma por grupo (o que o dono lê)."""
    contagem = dict.fromkeys(SECOES, 0)
    for li in linhas:
        if so_representantes and not li.get("representante", True):
            continue
        contagem[li["secao"]] += 1
    return contagem


COLUNAS_TABELA = (
    "edital",
    "nivel",
    "item",
    "no_id",
    "no_caminho",
    "origem",
    "status",
    "confianca",
    "justificativa",
)

# Colunas de revisão (M10): tipos fixos para o Datasette facetar.
COLUNAS_REVISAO = {
    "assunto": str,
    "chave": str,
    "bloco": str,
    "pai_chave": str,
    "secao": str,
    "travado": int,
    "pai_provisorio": int,
    "disciplina_do_no": str,
    "sugestao_no": str,
    "sugestao_caminho": str,
    "score": float,
    "sugestoes": str,
    "cargos": str,
    "grupo": int,
    "representante": int,
    "repete": int,
    "itens_bloco": int,
    "curar_arvore": str,
}


def _valor_revisao(linha: dict, coluna: str):
    if coluna == "sugestoes":
        return " | ".join(
            f"{s['score']:.2f} {s['caminho']} [{s['no_id']}]"
            for s in linha.get("sugestoes") or []
        )
    if coluna == "cargos":
        return "; ".join(linha.get("cargos_grupo") or linha.get("cargos") or [])
    if coluna == "curar_arvore":
        return linha.get("curar")
    if coluna in ("travado", "pai_provisorio", "representante"):
        return int(bool(linha.get(coluna)))
    return linha.get(coluna)


def inserir_mapeamento_itens(db, linhas: list[dict]) -> None:
    """Acrescenta `linhas` à tabela `mapeamento_itens` do `revisao.db`.

    `disciplina` continua sendo o título do bloco do edital (compatibilidade);
    `disciplina_do_no` é a disciplina da árvore do nó (ou da sugestão)."""
    if not linhas:
        return
    db["mapeamento_itens"].insert_all(
        [
            {
                **{c: linha.get(c) for c in COLUNAS_TABELA},
                "disciplina": linha["disciplina"],
                **{c: _valor_revisao(linha, c) for c in COLUNAS_REVISAO},
            }
            for linha in linhas
        ],
        columns={
            "confianca": str,
            "justificativa": str,
            "no_id": str,
            **COLUNAS_REVISAO,
        },
    )


def criar_tabela_vazia(db) -> None:
    """Garante a tabela mesmo sem linhas, para o Datasette não dar 404."""
    if not db["mapeamento_itens"].exists():
        db["mapeamento_itens"].create(
            {
                "edital": str,
                "nivel": str,
                "item": str,
                "no_id": str,
                "no_caminho": str,
                "origem": str,
                "status": str,
                "confianca": str,
                "justificativa": str,
                "disciplina": str,
                **COLUNAS_REVISAO,
            }
        )


__all__ = [
    "CACHE_PADRAO",
    "CATEGORIAS",
    "COLUNAS_REVISAO",
    "IndiceSimilaridade",
    "LIMIAR_ALTO",
    "LIMIAR_SUGESTAO",
    "ROTULOS",
    "SECOES",
    "cargos_por_chave",
    "contar_por_secao",
    "contexto_revisao",
    "montar_revisao",
    "sugerir_nos",
    "carregar_cache_propostos",
    "classificar_itens",
    "classificar_seguro",
    "contar_por_categoria",
    "criar_tabela_vazia",
    "inserir_mapeamento_itens",
]
