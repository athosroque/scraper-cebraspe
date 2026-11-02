"""Camada canônica de sinônimos: matéria → assunto → subassunto (Etapa 5B, ADR-029).

Fonte da verdade versionada: `canonico/sinonimos.json` (o banco é
regenerável). Três níveis (`materia`, `assunto`, `subassunto`), cada um com:

- **entradas**: a unidade mínima de agrupamento. Uma entrada junta os nomes de
  origem que têm a mesma *chave de regra* (`chave_regra`) dentro do mesmo pai
  (a entrada de matéria de um assunto; a de assunto de um subassunto). O ID é
  derivado só de `(nível, pai, chave_regra)`, então é estável entre
  reexecuções e entre máquinas.
- **grupos**: o canônico. `membros` são IDs de entrada, com `origem`
  (`regra` | `llm` | `humano`) e `status` (`proposto` | `aprovado` |
  `rejeitado`).

Invariantes:
1. Toda entrada presente está em **exatamente um** grupo `aprovado`. Quando
   nenhuma decisão existe, é o grupo identidade (ID do grupo == ID da
   entrada, `origem = regra`): a regra "este nome é ele mesmo" é
   determinística e não junta nada.
2. Entradas com a mesma chave de regra no mesmo escopo (grupo do pai) são
   juntadas por regra e aprovadas automaticamente.
3. Proposta (`proposto`) nunca muda o mapeamento: até ser aprovada, os
   membros continuam no grupo aprovado de antes. Nada proposto entra na
   estatística.
4. Reexecução das regras nunca mexe em grupo `llm`/`humano` nem em status
   decidido por humano; só cria entradas/grupos identidade novos e junta
   grupos `regra`.

Esquema de ID (documentado no ADR-029):
- entrada: `M-`/`A-`/`S-` + sha1(`nível|pai|chave_regra`)[:10];
- grupo identidade: o próprio ID da entrada;
- grupo por regra que junta entradas: `MR-`/`AR-`/`SR-` + sha1(`escopo|chave_regra`)[:10];
- grupo proposto pelo LLM: `ML-`/`AL-`/`SL-` + sha1(membros ordenados)[:10];
- grupo criado por humano (`--mover ...:NOVO`): `MH-`/`AH-`/`SH-` + sha1(membros)[:10].
"""

import copy
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.comparacao_texto import normalizar
from src.logger import logger

PROJETO_DIR = Path(__file__).resolve().parent.parent
SINONIMOS_PADRAO = PROJETO_DIR / "canonico" / "sinonimos.json"


def caminho_sinonimos(revisao_dir: Path) -> Path:
    """`canonico/sinonimos.json` ao lado de `revisao_piloto/` (no projeto real é
    `SINONIMOS_PADRAO`; em teste, fica dentro do diretório temporário)."""
    return Path(revisao_dir).resolve().parent / "canonico" / "sinonimos.json"


NIVEIS = ("materia", "assunto", "subassunto")
PREFIXO = {"materia": "M", "assunto": "A", "subassunto": "S"}
PAI = {"materia": None, "assunto": "materia", "subassunto": "assunto"}

ORIGEM_REGRA, ORIGEM_LLM, ORIGEM_HUMANO = "regra", "llm", "humano"
STATUS_PROPOSTO, STATUS_APROVADO, STATUS_REJEITADO = "proposto", "aprovado", "rejeitado"

VERSAO_ESQUEMA = 1

# Falhas semânticas da proposta do LLM contra a lista fechada (tipadas como as
# técnicas do ADR-022).
STATUS_FALHA_ID_DESCONHECIDO = "falha_id_desconhecido"
STATUS_FALHA_ID_AUSENTE = "falha_id_ausente"
STATUS_FALHA_ID_DUPLICADO = "falha_id_duplicado"
STATUS_FALHA_GRUPO_ENTRE_BLOCOS = "falha_grupo_entre_blocos"


# Regras determinísticas ---------------------------------------------------------

# "Noções de/sobre", no começo do nome. Aplicado no texto normalizado.
PADRAO_NOCOES = re.compile(
    r"^nocoes\s+(?:basicas\s+|gerais\s+)?(?:de|sobre|do|da|dos|das)\s+"
)
# "Fundamentos de", "conceitos (básicos|gerais) de": prefixo ignorado como "noções
# de", mas sem ligar o sinalizador `nocoes` (KAN-84, M12). Exige o que vem depois.
PADRAO_PREFIXO_CONCEITUAL = re.compile(
    r"^(?:fundamentos|conceitos(?:\s+(?:basicos|gerais))?)\s+"
    r"(?:de|sobre|do|da|dos|das)\s+(?=\S)"
)
# Sinônimos de palavra inteira que a chave unifica. Só gestão e gerenciamento:
# "administração" fica de fora (é matéria própria: administração pública etc.).
SINONIMOS_TOKEN = {"gerenciamento": "gestao"}
# Sigla: último parêntese com 2 a 8 letras/dígitos e ao menos 2 maiúsculas no texto cru.
PADRAO_SIGLA_PAREN = re.compile(r"\(\s*([A-Za-z0-9]{2,8})\s*\)\s*$")
# Mesmo padrão sobre o texto cru, só para o nome de exibição do canônico.
PADRAO_NOCOES_CRU = re.compile(
    r"^\s*no[çc][õo]es\s+(?:b[áa]sicas\s+|gerais\s+)?(?:de|sobre|do|da|dos|das)\s+",
    re.IGNORECASE,
)
# Numeração do item colada no nome ("7 Despesa ...", "5.1 Disposições ...").
PADRAO_NUMERACAO = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")
PADRAO_ARTIGO = re.compile(r"^(?:o|a|os|as|um|uma|uns|umas)\s+")
# Parêntese com um nível de parêntese interno (mesma ideia do ADR-028).
PADRAO_PARENTESES = re.compile(r"\((?:[^()]|\([^()]*\))*\)")

# Norma: tipo + (nº) + número + (data) + ano, sobre o texto já normalizado
# ("Lei nº 9.784/1999" -> "lei no 9 784 1999"; "Lei n o 9.784/1999" ->
# "lei n o 9 784 1999"; "Lei 9.784, de 29 de janeiro de 1999").
TIPOS_NORMA = (
    "lei complementar",
    "decreto lei",
    "lei",
    "decreto",
    "medida provisoria",
    "emenda constitucional",
    "resolucao",
    "portaria",
)
PADRAO_NORMA = re.compile(
    r"\b(" + "|".join(t.replace(" ", r"\s+") for t in TIPOS_NORMA) + r")\s+"
    r"(?:(?:no|nr|n|numero)\s+(?:o\s+)?)?"
    r"(\d{1,3}(?:\s\d{3}\b)+|\d+)\b"
    r"(?:\s+de\s+\d{1,2}\s+de\s+[a-z]+\s+de|\s+de)?"
    r"(?:\s+(\d{4}|\d{2})\b)?"
)
PADRAO_ALTERACOES = re.compile(r"\s+e\s+(?:suas\s+)?alteracoes(?:\s+posteriores)?$")

# Palavras em que o "s" final não é plural (ou cujo "singular" colidiria com
# outra palavra: "ônus" -> "onu").
NAO_PLURAL = frozenset(
    {
        "onus",
        "bonus",
        "virus",
        "campus",
        "status",
        "corpus",
        "habeas",
        "lapis",
        "tenis",
        "pires",
        "juris",
        "mais",
    }
)


def _singular(token: str) -> str:
    """Singular/plural simples e conservador: só -ões/-ães → -ão, -ns → -m e
    -as/-es/-os → sem o "s". Não mexe em -is/-us nem em palavra curta.
    Nunca junta duas palavras diferentes que o dicionário separaria
    (`atos` → `ato`, `contratos` → `contrato`)."""
    if len(token) <= 3 or token in NAO_PLURAL or not token.isalpha():
        return token
    if token.endswith(("oes", "aes")):
        return token[:-3] + "ao"
    if token.endswith("ns"):
        return token[:-2] + "m"
    if token[-1] == "s" and token[-2] in "aeo":
        return token[:-1]
    return token


def _forma_norma(m: re.Match) -> str:
    tipo = re.sub(r"\s+", " ", m.group(1))
    numero = m.group(2).replace(" ", "")
    ano = m.group(3)
    if ano and len(ano) == 2:
        ano = ("19" if int(ano) >= 30 else "20") + ano
    return f"{tipo} {numero}" + (f" {ano}" if ano else "")


@dataclass(frozen=True)
class ChaveRegra:
    chave: str
    nocoes: bool
    # Sigla do nome (entre parênteses, ou o próprio nome se for só a sigla). Não
    # entra na igualdade nem na chave: só serve ao casamento por sigla única.
    sigla: str = field(default="", compare=False)


def sigla_do_nome(nome: str) -> str:
    """Sigla em minúsculas ("Minimum Viable Product (MVP)" -> "mvp"; "MVP" -> "mvp"),
    ou "" se o nome não tem. Exige 2+ maiúsculas, para não tomar "(rede)" por sigla."""
    bruto = (nome or "").strip()
    m = PADRAO_SIGLA_PAREN.search(bruto)
    cand = (
        m.group(1) if m else (bruto if re.fullmatch(r"[A-Za-z0-9]{2,8}", bruto) else "")
    )
    if sum(c.isupper() for c in cand) < 2:
        return ""
    return normalizar(cand).replace(" ", "")


def candidato_unico_por_sigla(sigla: str, candidatos: dict[str, str]):
    """Chave do único candidato cuja sigla é `sigla`, ou None.

    `candidatos` mapeia uma chave qualquer (nó, regra, item) à sigla dela. Sem
    sigla, sem candidato ou com 2+ chaves de mesma sigla, não equivale (a sigla
    "CI" serve a Integração Contínua e a Controle Interno)."""
    if not sigla:
        return None
    achados = [k for k, s in candidatos.items() if s == sigla]
    return achados[0] if len(achados) == 1 else None


def chave_regra(nome: str) -> ChaveRegra:
    """Chave de agrupamento determinístico de um nome de origem.

    Nomes com a mesma chave (no mesmo escopo) são o mesmo canônico, aprovado
    por regra. Conservadora de propósito: não junta por similaridade de
    texto, só por formas equivalentes (maiúsculas/acentos, "noções de",
    artigo inicial, qualificador entre parênteses, forma da norma,
    singular/plural simples).
    """
    texto = PADRAO_PARENTESES.sub(" ", nome or "")
    texto = normalizar(texto)
    texto = PADRAO_NORMA.sub(_forma_norma, texto)
    texto = PADRAO_ALTERACOES.sub("", texto)
    nocoes = False
    for _ in range(2):  # "a noções de ..." / "noções de o ..."
        texto, n = PADRAO_NOCOES.subn("", texto)
        nocoes = nocoes or bool(n)
        texto = PADRAO_PREFIXO_CONCEITUAL.sub("", texto)
        texto = PADRAO_ARTIGO.sub("", texto)
    texto = " ".join(
        SINONIMOS_TOKEN.get(t, t) for t in (_singular(t) for t in texto.split())
    )
    return ChaveRegra(texto.strip(), nocoes, sigla_do_nome(nome))


def nome_sem_nocoes(nome: str) -> str:
    return PADRAO_NOCOES_CRU.sub("", nome).strip() or nome


def _hoje() -> str:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat()


def _hash(*partes) -> str:
    return hashlib.sha1("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[
        :10
    ]


def id_entrada(nivel: str, pai: str | None, chave: str) -> str:
    return f"{PREFIXO[nivel]}-{_hash(nivel, pai or '', chave)}"


def id_grupo(
    nivel: str, origem: str, *, membros=(), escopo: str | None = None, chave: str = ""
) -> str:
    if origem == ORIGEM_REGRA:
        return f"{PREFIXO[nivel]}R-{_hash(escopo or '', chave)}"
    sufixo = "L" if origem == ORIGEM_LLM else "H"
    return f"{PREFIXO[nivel]}{sufixo}-{_hash(*sorted(membros))}"


# Nomes de origem ----------------------------------------------------------------


@dataclass
class NomesOrigem:
    """Nomes de origem por nível, com as ocorrências (concurso, nível) de cada."""

    materia: dict[str, dict] = field(
        default_factory=dict
    )  # chave -> {nome, ocorrencias}
    assunto: dict[tuple[str, str], dict] = field(default_factory=dict)
    subassunto: dict[tuple[str, str, str], dict] = field(default_factory=dict)


def _registrar_nome(
    destino: dict, chave, nome: str, ocorrencia: tuple[str, str | None]
) -> None:
    info = destino.setdefault(chave, {"nome": nome, "ocorrencias": set()})
    info["ocorrencias"].add(ocorrencia)


def coletar_nomes(revisao_dir: Path) -> NomesOrigem:
    """Nomes de matéria/tópico/subtópico dos `<edital>.json`, com a mesma
    chave natural do writer (`montar_carga_concurso` + `normalizar`)."""
    # Import local: stats_writer importa este módulo.
    from src.stats_writer import listar_jsons_edital, montar_carga_concurso

    nomes = NomesOrigem()
    for json_path in listar_jsons_edital(revisao_dir):
        carga = montar_carga_concurso(json.loads(json_path.read_text(encoding="utf-8")))
        niveis_cargo = {c["numero"]: c.get("nivel") for c in carga["cargos"]}
        for item in carga["itens"]:
            nivel = item["nivel"] or niveis_cargo.get(item["cargo_numero"])
            oc = (carga["slug"], nivel)
            m, t = item["materia_chave"], item["topico_chave"]
            _registrar_nome(nomes.materia, m, item["materia_nome"], oc)
            _registrar_nome(nomes.assunto, (m, t), item["topico_nome"], oc)
            for sub in item["subtopicos"]:
                s = normalizar(sub)
                if s:
                    _registrar_nome(nomes.subassunto, (m, t, s), sub, oc)
    return nomes


# Estado (sinonimos.json) ----------------------------------------------------------


def estado_vazio() -> dict:
    return {
        "versao_esquema": VERSAO_ESQUEMA,
        "descricao": (
            "Camada canônica de sinônimos (ADR-029). Gerado/atualizado por src.canonico "
            "(regras), scripts/propor_sinonimos.py (LLM) e scripts/aprovar_sinonimos.py "
            "(decisão humana). Só grupo 'aprovado' entra no banco."
        ),
        **{
            nivel: {"entradas": {}, "grupos": {}, "avaliados_llm": {}}
            for nivel in NIVEIS
        },
    }


def carregar(path: Path = SINONIMOS_PADRAO) -> dict:
    if not path.exists():
        return estado_vazio()
    estado = json.loads(path.read_text(encoding="utf-8"))
    for nivel in NIVEIS:
        estado.setdefault(nivel, {"entradas": {}, "grupos": {}})
        estado[nivel].setdefault("avaliados_llm", {})
    return estado


def salvar(estado: dict, path: Path = SINONIMOS_PADRAO) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ordenado por ID para o diff do git mostrar só o que mudou.
    # Uma linha por entrada/grupo: o arquivo fica menor (~4 mil registros) e
    # o diff do git continua mostrando só o registro que mudou.
    linhas = ["{"]
    cabecalho = {k: v for k, v in estado.items() if k not in NIVEIS}
    for k, v in cabecalho.items():
        linhas.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
    for i, nivel in enumerate(NIVEIS):
        linhas.append(f' "{nivel}": {{')
        chaves = ("entradas", "grupos", "avaliados_llm")
        for j, chave in enumerate(chaves):
            itens = sorted(estado[nivel].get(chave, {}).items())
            estado[nivel][chave] = dict(itens)
            linhas.append(f'  "{chave}": {{')
            linhas.extend(
                f"   {json.dumps(k)}: {json.dumps(v, ensure_ascii=False, sort_keys=True)}"
                + ("," if n < len(itens) - 1 else "")
                for n, (k, v) in enumerate(itens)
            )
            linhas.append("  }" + ("," if j < len(chaves) - 1 else ""))
        linhas.append(" }" + ("," if i < len(NIVEIS) - 1 else ""))
    linhas.append("}")
    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def grupo_aprovado_por_entrada(estado: dict, nivel: str) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for gid, g in estado[nivel]["grupos"].items():
        if g["status"] == STATUS_APROVADO:
            for e in g["membros"]:
                mapa[e] = gid
    return mapa


def proposta_por_entrada(estado: dict, nivel: str) -> dict[str, str]:
    mapa: dict[str, str] = {}
    for gid, g in estado[nivel]["grupos"].items():
        if g["status"] == STATUS_PROPOSTO:
            for e in g["membros"]:
                mapa[e] = gid
    return mapa


def escopo_da_entrada(
    estado: dict, nivel: str, entrada_id: str, efetivo: bool = False
) -> str | None:
    """Grupo do pai da entrada (None para matéria). `efetivo=True` usa a
    proposta pendente do pai quando houver — é o escopo em que o LLM propõe
    o nível de baixo antes de o dono aprovar o de cima."""
    nivel_pai = PAI[nivel]
    if nivel_pai is None:
        return None
    pai = estado[nivel]["entradas"][entrada_id]["pai"]
    if efetivo:
        proposta = proposta_por_entrada(estado, nivel_pai).get(pai)
        if proposta:
            return proposta
    return grupo_aprovado_por_entrada(estado, nivel_pai).get(pai)


def _nome_exibicao(estado: dict, nivel: str, membros: list[str]) -> str:
    """Nome canônico determinístico: sem "noções", mais concursos, sem
    parêntese, mais curto, alfabético."""
    candidatos = []
    for e in membros:
        for n in estado[nivel]["entradas"][e]["nomes"]:
            candidatos.append(
                (
                    n.get("nocoes", False),
                    -n.get("concursos", 0),
                    bool(PADRAO_NUMERACAO.match(n["nome"])),
                    "(" in n["nome"],
                    len(n["nome"]),
                    n["nome"],
                )
            )
    if not candidatos:
        return membros[0]
    melhor = min(candidatos)[-1]
    return nome_sem_nocoes(PADRAO_NUMERACAO.sub("", melhor).strip() or melhor)


nome_exibicao = _nome_exibicao


def _entradas_do_nivel(
    nivel: str, nomes: NomesOrigem, entrada_pai: dict
) -> dict[str, dict]:
    """Entradas calculadas a partir dos nomes de origem (nível, pai, chave)."""
    entradas: dict[str, dict] = {}
    fonte = getattr(nomes, nivel)
    for chave_origem, info in fonte.items():
        regra = chave_regra(info["nome"])
        if not regra.chave:
            continue
        if nivel == "materia":
            pai, registro = None, {"chave": chave_origem}
        elif nivel == "assunto":
            pai = entrada_pai.get(chave_origem[0])
            registro = {"materia": chave_origem[0], "chave": chave_origem[1]}
        else:
            pai = entrada_pai.get(chave_origem[:2])
            registro = {
                "materia": chave_origem[0],
                "topico": chave_origem[1],
                "chave": chave_origem[2],
            }
        if nivel != "materia" and pai is None:
            continue
        eid = id_entrada(nivel, pai, regra.chave)
        entrada = entradas.setdefault(
            eid, {"chave_regra": regra.chave, "pai": pai, "nomes": [], "presente": True}
        )
        entrada["nomes"].append(
            {
                **registro,
                "nome": info["nome"],
                "nocoes": regra.nocoes,
                "concursos": len({slug for slug, _ in info["ocorrencias"]}),
            }
        )
    for entrada in entradas.values():
        entrada["nomes"].sort(
            key=lambda n: (n["chave"], n.get("materia", ""), n.get("topico", ""))
        )
    return entradas


@dataclass
class ResumoRegras:
    entradas_novas: dict[str, int] = field(default_factory=dict)
    grupos_regra_multiplos: dict[str, int] = field(default_factory=dict)
    nomes: dict[str, int] = field(default_factory=dict)
    entradas: dict[str, int] = field(default_factory=dict)


def aplicar_regras(estado: dict, nomes: NomesOrigem) -> ResumoRegras:
    """Atualiza o estado com as regras determinísticas, nível a nível.

    Idempotente e conservador: grupo `llm`/`humano` e status decidido nunca
    são alterados; só grupos `regra` são criados, juntados ou (quando o
    escopo deixa de existir) desfeitos em identidades.
    """
    resumo = ResumoRegras()
    entrada_pai: dict = {}
    for nivel in NIVEIS:
        nivel_estado = estado[nivel]
        calculadas = _entradas_do_nivel(nivel, nomes, entrada_pai)
        novas = 0
        for eid, entrada in nivel_estado["entradas"].items():
            if eid not in calculadas:
                entrada["presente"] = False
        for eid, calc in calculadas.items():
            if eid not in nivel_estado["entradas"]:
                novas += 1
            nivel_estado["entradas"][eid] = calc

        grupos = nivel_estado["grupos"]
        aprovado = grupo_aprovado_por_entrada(estado, nivel)
        # Invariante 1: toda entrada presente num grupo aprovado.
        for eid, entrada in nivel_estado["entradas"].items():
            if entrada["presente"] and eid not in aprovado:
                grupos[eid] = {
                    "nome": "",
                    "origem": ORIGEM_REGRA,
                    "status": STATUS_APROVADO,
                    "membros": [eid],
                    "escopo": None,
                }
                aprovado[eid] = eid

        # Grupo `regra` com membros em escopos diferentes (o pai foi
        # desfeito) volta a identidades.
        for gid in [
            g
            for g, d in grupos.items()
            if d["origem"] == ORIGEM_REGRA and d["status"] == STATUS_APROVADO
        ]:
            membros = grupos[gid]["membros"]
            escopos = {escopo_da_entrada(estado, nivel, e) for e in membros}
            if len(membros) > 1 and len(escopos) > 1:
                logger.warning(
                    f"[CANONICO] {nivel} {gid}: escopo do pai mudou, grupo por regra desfeito."
                )
                del grupos[gid]
                for e in membros:
                    grupos[e] = {
                        "nome": "",
                        "origem": ORIGEM_REGRA,
                        "status": STATUS_APROVADO,
                        "membros": [e],
                        "escopo": None,
                    }

        # Invariante 2: mesma chave de regra no mesmo escopo -> um grupo regra.
        aprovado = grupo_aprovado_por_entrada(estado, nivel)
        baldes: dict[tuple, list[str]] = {}
        for eid, entrada in nivel_estado["entradas"].items():
            gid = aprovado.get(eid)
            if gid is None or grupos[gid]["origem"] != ORIGEM_REGRA:
                continue
            escopo = escopo_da_entrada(estado, nivel, eid)
            baldes.setdefault((escopo, entrada["chave_regra"]), []).append(eid)
        for (escopo, chave), membros in baldes.items():
            if len(membros) < 2:
                continue
            alvo = id_grupo(nivel, ORIGEM_REGRA, escopo=escopo, chave=chave)
            atuais = {aprovado[e] for e in membros}
            if atuais == {alvo}:
                continue
            for gid in atuais - {alvo}:
                grupos[gid]["membros"] = [
                    e for e in grupos[gid]["membros"] if e not in membros
                ]
                if not grupos[gid]["membros"]:
                    del grupos[gid]
            grupos[alvo] = {
                "nome": "",
                "origem": ORIGEM_REGRA,
                "status": STATUS_APROVADO,
                "membros": sorted(membros),
                "escopo": escopo,
            }

        # Proposta cujos membros a regra já juntou (ex.: o mesmo assunto em
        # duas matérias que acabaram de ser aprovadas juntas) ficou
        # redundante: sai, com log.
        aprovado = grupo_aprovado_por_entrada(estado, nivel)
        for gid in [g for g, d in grupos.items() if d["status"] == STATUS_PROPOSTO]:
            destinos = {aprovado.get(e) for e in grupos[gid]["membros"]}
            if len(destinos) == 1 and None not in destinos:
                logger.info(
                    f"[CANONICO] {nivel} {gid}: proposta redundante (membros já juntos em "
                    f"{destinos.pop()}), removida."
                )
                del grupos[gid]

        # Nome e escopo dos grupos regra são derivados (determinísticos).
        for d in grupos.values():
            if d["origem"] == ORIGEM_REGRA:
                d["nome"] = _nome_exibicao(estado, nivel, d["membros"])
                d["escopo"] = escopo_da_entrada(estado, nivel, d["membros"][0])

        # Pai das entradas do nível de baixo.
        if nivel == "materia":
            entrada_pai = {
                n["chave"]: eid
                for eid, e in nivel_estado["entradas"].items()
                for n in e["nomes"]
            }
        elif nivel == "assunto":
            entrada_pai = {
                (n["materia"], n["chave"]): eid
                for eid, e in nivel_estado["entradas"].items()
                for n in e["nomes"]
            }

        presentes = [e for e in nivel_estado["entradas"].values() if e["presente"]]
        resumo.entradas_novas[nivel] = novas
        resumo.entradas[nivel] = len(presentes)
        resumo.nomes[nivel] = sum(len(e["nomes"]) for e in presentes)
        resumo.grupos_regra_multiplos[nivel] = sum(
            1
            for d in grupos.values()
            if d["origem"] == ORIGEM_REGRA
            and d["status"] == STATUS_APROVADO
            and sum(len(nivel_estado["entradas"][e]["nomes"]) for e in d["membros"]) > 1
        )
    return resumo


def atualizar_por_regras(
    revisao_dir: Path, path: Path = SINONIMOS_PADRAO
) -> ResumoRegras:
    """Lê os editais, aplica as regras e grava `sinonimos.json` (pipeline, ADR-019)."""
    estado = carregar(path)
    resumo = aplicar_regras(estado, coletar_nomes(revisao_dir))
    salvar(estado, path)
    for nivel in NIVEIS:
        logger.info(
            f"[CANONICO] {nivel}: {resumo.nomes[nivel]} nomes em {resumo.entradas[nivel]} entradas "
            f"({resumo.entradas_novas[nivel]} novas), {resumo.grupos_regra_multiplos[nivel]} grupos por regra "
            "com mais de um nome."
        )
    return resumo


# Validação da proposta do LLM (lista fechada) -------------------------------------


def validar_agrupamento(
    ids_por_bloco: dict[str, list[str]], grupos: list[list[str]]
) -> tuple[str | None, str | None]:
    """Confere a resposta do LLM contra a lista fechada de IDs enviada.

    Cada ID de entrada deve aparecer em exatamente um grupo, e um grupo não
    pode misturar blocos (escopos). Retorna `(motivo, detalhe)`, com
    `motivo` None quando válido.
    """
    bloco_do_id = {i: b for b, ids in ids_por_bloco.items() for i in ids}
    vistos: Counter = Counter(i for g in grupos for i in g)
    desconhecidos = sorted(set(vistos) - set(bloco_do_id))
    if desconhecidos:
        return STATUS_FALHA_ID_DESCONHECIDO, f"IDs fora da lista: {desconhecidos[:10]}"
    duplicados = sorted(i for i, n in vistos.items() if n > 1)
    if duplicados:
        return STATUS_FALHA_ID_DUPLICADO, f"IDs em mais de um grupo: {duplicados[:10]}"
    ausentes = sorted(set(bloco_do_id) - set(vistos))
    if ausentes:
        return STATUS_FALHA_ID_AUSENTE, f"IDs sem grupo: {ausentes[:10]}"
    for g in grupos:
        blocos = {bloco_do_id[i] for i in g}
        if len(blocos) > 1:
            return (
                STATUS_FALHA_GRUPO_ENTRE_BLOCOS,
                f"grupo {g} mistura os blocos {sorted(blocos)}",
            )
    return None, None


# Decisões ------------------------------------------------------------------------


def registrar_proposta(
    estado: dict,
    nivel: str,
    membros: list[str],
    nome: str,
    escopo: str | None,
    justificativa: str | None,
) -> str | None:
    """Grava um grupo `proposto` (origem `llm`). Não grava se repete um grupo
    rejeitado ou uma proposta pendente com os mesmos membros."""
    membros = sorted(set(membros))
    grupos = estado[nivel]["grupos"]
    for gid, g in grupos.items():
        if (
            g["status"] in (STATUS_REJEITADO, STATUS_PROPOSTO)
            and sorted(g["membros"]) == membros
        ):
            logger.info(
                f"[CANONICO] {nivel}: proposta igual ao grupo {gid} ({g['status']}), ignorada."
            )
            return None
    gid = id_grupo(nivel, ORIGEM_LLM, membros=membros)
    grupos[gid] = {
        "nome": nome.strip(),
        "origem": ORIGEM_LLM,
        "status": STATUS_PROPOSTO,
        "membros": membros,
        "escopo": escopo,
        "justificativa": (justificativa or "").strip() or None,
        "proposto_em": _hoje(),
    }
    return gid


class DecisaoInvalida(ValueError):
    pass


def _achar_grupo(estado: dict, gid: str) -> str:
    for nivel in NIVEIS:
        if gid in estado[nivel]["grupos"]:
            return nivel
    raise DecisaoInvalida(f"grupo {gid} não existe")


def _achar_entrada(estado: dict, eid: str) -> str:
    for nivel in NIVEIS:
        if eid in estado[nivel]["entradas"]:
            return nivel
    raise DecisaoInvalida(f"entrada {eid} não existe")


def _tirar_de_grupos(
    estado: dict,
    nivel: str,
    eid: str,
    status: tuple[str, ...],
    exceto: str | None = None,
) -> None:
    grupos = estado[nivel]["grupos"]
    for gid in list(grupos):
        g = grupos[gid]
        if gid == exceto or g["status"] not in status or eid not in g["membros"]:
            continue
        g["membros"] = [e for e in g["membros"] if e != eid]
        if not g["membros"]:
            del grupos[gid]


def aprovar(estado: dict, gid: str) -> None:
    """Aprova um grupo proposto: os membros saem dos grupos aprovados atuais
    e passam a este. Assunto/subassunto só com o pai já decidido (todos os
    membros no mesmo grupo aprovado do nível de cima)."""
    nivel = _achar_grupo(estado, gid)
    g = estado[nivel]["grupos"][gid]
    if g["status"] == STATUS_APROVADO:
        return
    escopos = {escopo_da_entrada(estado, nivel, e) for e in g["membros"]}
    if len(escopos) > 1:
        raise DecisaoInvalida(
            f"{gid}: membros em grupos diferentes do nível de cima ({sorted(map(str, escopos))}) — "
            f"aprove antes o grupo do nível '{PAI[nivel]}' que os junta ({g.get('escopo')})."
        )
    for e in g["membros"]:
        _tirar_de_grupos(
            estado, nivel, e, (STATUS_APROVADO, STATUS_PROPOSTO), exceto=gid
        )
    g["status"] = STATUS_APROVADO
    g["escopo"] = escopos.pop()
    g["decidido_em"] = _hoje()


def rejeitar(estado: dict, gid: str) -> None:
    """Rejeita um grupo. Proposto: só marca. Aprovado `llm`/`humano`: os
    membros voltam a grupos identidade (a regra reagrupa o que for dela)."""
    nivel = _achar_grupo(estado, gid)
    g = estado[nivel]["grupos"][gid]
    if g["origem"] == ORIGEM_REGRA:
        raise DecisaoInvalida(
            f"{gid}: grupo por regra não é rejeitável — use --mover para separar uma entrada."
        )
    if g["status"] == STATUS_APROVADO:
        for e in g["membros"]:
            estado[nivel]["grupos"][e] = {
                "nome": "",
                "origem": ORIGEM_REGRA,
                "status": STATUS_APROVADO,
                "membros": [e],
                "escopo": None,
            }
    g["status"] = STATUS_REJEITADO
    g["decidido_em"] = _hoje()


def mover(estado: dict, eid: str, destino: str) -> str:
    """Move uma entrada para outro grupo (proposto ou aprovado) do mesmo
    nível. `destino == "NOVO"` cria um grupo humano aprovado só com ela.
    Retorna o ID do grupo de destino."""
    nivel = _achar_entrada(estado, eid)
    grupos = estado[nivel]["grupos"]
    if destino.upper() == "NOVO":
        destino = id_grupo(nivel, ORIGEM_HUMANO, membros=[eid, "novo"])
        grupos[destino] = {
            "nome": "",
            "origem": ORIGEM_HUMANO,
            "status": STATUS_PROPOSTO,
            "membros": [],
            "escopo": None,
        }
        _tirar_de_grupos(estado, nivel, eid, (STATUS_PROPOSTO,))
        grupos[destino]["membros"] = [eid]
        grupos[destino]["nome"] = _nome_exibicao(estado, nivel, [eid])
        aprovar(estado, destino)
        return destino
    if destino not in grupos:
        raise DecisaoInvalida(f"grupo {destino} não existe no nível {nivel}")
    g = grupos[destino]
    if g["status"] == STATUS_REJEITADO:
        raise DecisaoInvalida(f"grupo {destino} está rejeitado")
    if g["status"] == STATUS_APROVADO:
        escopo = escopo_da_entrada(estado, nivel, eid)
        if (
            len(g["membros"])
            and escopo_da_entrada(estado, nivel, g["membros"][0]) != escopo
        ):
            raise DecisaoInvalida(
                f"{eid} e o grupo {destino} estão em escopos diferentes do nível de cima"
            )
        _tirar_de_grupos(
            estado, nivel, eid, (STATUS_APROVADO, STATUS_PROPOSTO), exceto=destino
        )
    else:
        _tirar_de_grupos(estado, nivel, eid, (STATUS_PROPOSTO,), exceto=destino)
    if eid not in g["membros"]:
        g["membros"] = sorted([*g["membros"], eid])
    g["editado_por_humano"] = True
    return destino


def renomear(estado: dict, gid: str, nome: str) -> None:
    nivel = _achar_grupo(estado, gid)
    g = estado[nivel]["grupos"][gid]
    if g["origem"] == ORIGEM_REGRA:
        # Nome de grupo regra é derivado a cada execução; renomear o fixa
        # como decisão humana.
        g["origem"] = ORIGEM_HUMANO
    g["nome"] = nome.strip()


# Índice para o banco ----------------------------------------------------------------


@dataclass
class IndiceCanonico:
    """Só grupos aprovados. Chaves no formato das dimensões do banco."""

    materia: dict[str, str] = field(default_factory=dict)  # dim_materia.chave -> grupo
    assunto: dict[tuple[str, str], str] = field(default_factory=dict)
    subassunto: dict[tuple[str, str, str], str] = field(default_factory=dict)
    grupos: dict[str, dict[str, dict]] = field(
        default_factory=dict
    )  # nível -> gid -> {nome, origem, pai}


def indice_aprovado(estado: dict) -> IndiceCanonico:
    indice = IndiceCanonico()
    for nivel in NIVEIS:
        aprovado = grupo_aprovado_por_entrada(estado, nivel)
        destino = getattr(indice, nivel)
        usados: set[str] = set()
        for eid, entrada in estado[nivel]["entradas"].items():
            gid = aprovado.get(eid)
            if gid is None or not entrada.get("presente", True):
                continue
            usados.add(gid)
            for n in entrada["nomes"]:
                if nivel == "materia":
                    destino[n["chave"]] = gid
                elif nivel == "assunto":
                    destino[(n["materia"], n["chave"])] = gid
                else:
                    destino[(n["materia"], n["topico"], n["chave"])] = gid
        indice.grupos[nivel] = {
            gid: {
                "nome": g["nome"],
                "origem": g["origem"],
                "pai": escopo_da_entrada(estado, nivel, g["membros"][0]),
            }
            for gid, g in estado[nivel]["grupos"].items()
            if gid in usados
        }
    return indice


# Escopos para a proposta do LLM ---------------------------------------------------


@dataclass
class Escopo:
    """Um bloco da lista fechada: grupos aprovados do mesmo nível que podem
    ser juntados entre si (mesmo grupo — aprovado ou proposto — do pai)."""

    nivel: str
    escopo_id: str | None
    rotulo: str
    itens: list[str]  # IDs de grupo aprovado


def concursos_da_entrada(nivel: str, entrada: dict, nomes: NomesOrigem) -> set[str]:
    fonte = getattr(nomes, nivel)
    slugs: set[str] = set()
    for n in entrada["nomes"]:
        if nivel == "materia":
            chave = n["chave"]
        elif nivel == "assunto":
            chave = (n["materia"], n["chave"])
        else:
            chave = (n["materia"], n["topico"], n["chave"])
        slugs |= {slug for slug, _ in fonte.get(chave, {}).get("ocorrencias", ())}
    return slugs


# Chave de `avaliados_llm` para o escopo global (matérias).
ESCOPO_GLOBAL = "*"


def marcar_avaliados(
    estado: dict, nivel: str, itens: list[str], escopo: str | None
) -> None:
    """Registra que o LLM já avaliou estes grupos neste escopo, para uma
    reexecução não pagar de novo pelo mesmo bloco."""
    avaliados = estado[nivel].setdefault("avaliados_llm", {})
    for gid in itens:
        avaliados[gid] = escopo or ESCOPO_GLOBAL


def montar_escopos(
    estado: dict, nivel: str, nomes: NomesOrigem, reavaliar: bool = False
) -> list[Escopo]:
    """Escopos com o que as regras não agruparam e vale mandar ao LLM.

    - item = grupo aprovado do nível (identidade ou já decidido);
    - fica de fora grupo com membro em proposta pendente (decida antes);
    - escopo = grupo efetivo do pai (proposta pendente do pai vale, para
      propor o nível de baixo sem esperar a aprovação do de cima);
    - escopo com menos de 2 itens, ou com nomes de um concurso só (a lista
      de um edital já não repete item), é pulado;
    - escopo em que todos os itens já foram avaliados pelo LLM nesse mesmo
      escopo (`avaliados_llm`) é pulado, salvo `reavaliar=True`. Se houver
      item novo, o bloco vai inteiro (o novo pode ser sinônimo de um antigo).
    """
    avaliados = estado[nivel].get("avaliados_llm", {})
    entradas = estado[nivel]["entradas"]
    grupos = estado[nivel]["grupos"]
    pendentes = proposta_por_entrada(estado, nivel)
    por_escopo: dict[str | None, list[str]] = {}
    for gid, g in sorted(grupos.items()):
        if g["status"] != STATUS_APROVADO:
            continue
        membros = [e for e in g["membros"] if entradas.get(e, {}).get("presente")]
        if not membros or any(e in pendentes for e in g["membros"]):
            continue
        escopo = escopo_da_entrada(estado, nivel, membros[0], efetivo=True)
        por_escopo.setdefault(escopo, []).append(gid)

    escopos = []
    for escopo, itens in por_escopo.items():
        if len(itens) < 2:
            continue
        slugs = set()
        for gid in itens:
            for e in grupos[gid]["membros"]:
                if e in entradas:
                    slugs |= concursos_da_entrada(nivel, entradas[e], nomes)
        if len(slugs) < 2:
            continue
        if not reavaliar and all(
            avaliados.get(g) == (escopo or ESCOPO_GLOBAL) for g in itens
        ):
            continue
        rotulo = (
            "todas as matérias"
            if escopo is None
            else _rotulo_grupo(estado, PAI[nivel], escopo)
        )
        escopos.append(Escopo(nivel, escopo, rotulo, itens))
    return escopos


def _rotulo_grupo(estado: dict, nivel: str, gid: str) -> str:
    g = estado[nivel]["grupos"].get(gid)
    if g is None:
        return gid
    if nivel == "assunto":
        pai = escopo_da_entrada(estado, "assunto", g["membros"][0], efetivo=True)
        return f"{_rotulo_grupo(estado, 'materia', pai)} › {g['nome']}"
    return g["nome"]


# Títulos de bloco genéricos demais para casar sozinhos, por nome, com um assunto
# de outra disciplina (KAN-82, M2): "Processo" não é Direito Processual Civil e
# "Arquitetura" não é Direito. Guardados pela `chave_regra`; reutilizável por quem
# mapeia título de bloco por nome (KAN-87, KAN-88).
TITULOS_GENERICOS_NOMES = (
    "Processo",
    "Processos",
    "Legislação",
    "Arquitetura",
    "Conceitos básicos",
    "Conceitos gerais",
    "Conceitos",
    "Projeto",
    "Projetos",
    "Produto",
    "Produtos",
    "Fundamentos",
    "Introdução",
    "Noções gerais",
    "Noções básicas",
    "Noções introdutórias",
    "Estratégia",
    "Gestão",
    "Gerenciamento",
    "Planejamento",
    "Controle",
    "Controles",
    "Segurança",
    "Sistemas",
    "Sistema",
    "Serviços",
    "Servidores",
    "Redes",
    "Dados",
    "Governança",
    "Tópicos especiais",
    "Outros",
    "Geral",
    "Gerais",
)
TITULOS_GENERICOS = frozenset(chave_regra(n).chave for n in TITULOS_GENERICOS_NOMES)

_PALAVRAS_VAZIAS_TITULO = frozenset(
    "de da do das dos e em no na nos nas a o as os ao aos um uma uns umas para por "
    "com sem sobre entre ou ante ate desde pelo pela pelos pelas".split()
)


def titulo_generico(nome_ou_chave: str) -> bool:
    """True se o nome (ou a `chave_regra` dele) é um título genérico."""
    return chave_regra(nome_ou_chave).chave in TITULOS_GENERICOS


def palavras_relevantes(nome: str) -> list[str]:
    """Palavras do nome sem palavras vazias (artigos, preposições, conjunções)."""
    return [
        t
        for t in chave_regra(nome).chave.split()
        if len(t) >= 3 and t not in _PALAVRAS_VAZIAS_TITULO
    ]


def nome_especifico(nome: str) -> bool:
    """Nome com 2 ou mais palavras relevantes e que não é título genérico: pode
    casar por nome sozinho com um nó único (M2)."""
    return len(palavras_relevantes(nome)) >= 2 and not titulo_generico(nome)


def _disciplina_do_no(arvore, no_id: str) -> str | None:
    """Matéria (disciplina) ativa à qual o nó pertence, ou ele mesmo se for matéria."""
    from src import arvore as arv_mod

    atual = arv_mod.resolver_no(arvore, no_id)
    for _ in range(6):
        no = arvore.nos.get(atual)
        if no is None:
            return None
        if no.nivel == "materia":
            return no.id
        if not no.pai:
            return None
        atual = arv_mod.resolver_no(arvore, no.pai)
    return None


def disciplinas_inferidas_do_bloco(
    arvore, chave_materia: str, filhos: dict[str, list[str]]
) -> frozenset[str]:
    """Disciplinas dos itens (assunto/subassunto) já aprovados do mesmo bloco.

    `filhos` mapeia a chave da matéria às chaves dos itens abaixo dela. Vazio
    quando nada foi mapeado: sem como inferir, o título não casa por nome."""
    discs = set()
    for chave in filhos.get(chave_materia, ()):
        for m in arvore.mapeamentos.get(chave, []):
            if m.status == "aprovado":
                d = _disciplina_do_no(arvore, m.no_id)
                if d:
                    discs.add(d)
    return frozenset(discs)


def alvo_de_titulo_por_nome(
    arvore,
    regra: str,
    nome: str,
    alvo: set[str],
    discs_bloco: frozenset[str],
    vetados: dict[tuple[str, str], str],
) -> frozenset[str] | None:
    """Ramo 3 do passo determinístico: nó único de mesmo nome para um título de
    bloco, ou None. Recusa par vetado pelo dono; só casa se o nó está numa
    disciplina compatível com a inferida do bloco, ou se o nome é específico
    (2+ palavras relevantes, não genérico) e o candidato é único."""
    if len(alvo) != 1 or any((regra, n) in vetados for n in alvo):
        return None
    (no_id,) = alvo
    # Título igual ao nome da própria disciplina não é homônimo de outra (M2).
    if (
        arvore.nos[no_id].nivel == "materia"
        or _disciplina_do_no(arvore, no_id) in discs_bloco
        or nome_especifico(nome)
    ):
        return frozenset(alvo)
    return None


@dataclass
class ResultadoRegra:
    """Contagem do passo determinístico (regra de nome + memória do dono)."""

    por_nome: int = 0
    por_memoria: int = 0
    pendentes: int = 0
    # Chaves dos itens que o passo tentou e não mapeou (sem nó equivalente, regra
    # ambígua, pai sem nó). Item que já tinha entrada (aprovada, proposta ou
    # rejeitada) não passa pelo passo e não entra aqui.
    chaves_pendentes: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.por_nome + self.por_memoria


def mapear_novos_itens_por_regra(
    revisao_dir: Path, arvore_path: Path | None = None, *, gravar: bool = True
) -> int:
    """Passo determinístico (sem LLM). Devolve quantos itens foram mapeados;
    o detalhe (nome vs. memória vs. pendentes) está em `mapear_novos_itens`."""
    return mapear_novos_itens(revisao_dir, arvore_path, gravar=gravar).total


def mapear_novos_itens(
    revisao_dir: Path,
    arvore_path: Path | None = None,
    *,
    gravar: bool = True,
    arvore_mem=None,
) -> ResultadoRegra:
    """Mapeia item novo de edital para a árvore mestre sem LLM (ADR-030).

    Por nível (matéria, tópico, subtópico), nesta ordem:
    1. regra de nome: o item sem mapeamento herda os nós de um item já aprovado
       com a mesma `chave_regra` **no mesmo nó-pai efetivo**; regra ambígua
       (dois itens com nós diferentes) fica pendente;
    2. memória das decisões do dono (`memoria_mapeamento`, P73): decisão aprovada
       repetida em outro edital ou apelido de nó fundido; nunca usa proposta não
       aprovada nem devolve par rejeitado;
    3. título de bloco (matéria) sem equivalente aponta para o único nó de
       disciplina ou assunto de mesmo nome, nunca vira disciplina nova. Só se o
       nó está numa disciplina compatível com a inferida dos itens do bloco (ou é a
       própria disciplina de mesmo nome), ou se o nome tem 2+ palavras relevantes e não é título genérico
       (`TITULOS_GENERICOS`); par vetado pelo dono nunca é regravado (M2).
    Item cujo pai não tem nó fica pendente. Nunca cria nó. O assunto mapeado
    agora serve de pai do subassunto. Com `gravar=False` (dry-run) a árvore em
    memória muda, mas nada é salvo. `arvore_mem` (opcional) é uma árvore já
    carregada, alterada no lugar, para o chamador enxergar o resultado.
    """
    # Import local: memoria_mapeamento importa este módulo.
    from src import arvore as arv_mod
    from src import memoria_mapeamento

    res = ResultadoRegra()
    arvore_path = arvore_path or arv_mod.ARVORE_PADRAO
    if arvore_mem is None and not arvore_path.exists():
        return res
    arvore = arvore_mem if arvore_mem is not None else arv_mod.carregar(arvore_path)
    nomes = coletar_nomes(revisao_dir)

    def nos_aprovados(chave: str) -> frozenset[str]:
        return frozenset(
            arv_mod.resolver_no(arvore, m.no_id)
            for m in arvore.mapeamentos.get(chave, [])
            if m.status == "aprovado"
        )

    def assinatura(nivel: str, chave_origem, nome: str):
        """(nível, nós do pai, chave de regra), ou None se não dá para comparar."""
        regra = chave_regra(nome).chave
        if not regra:
            return None
        partes = (chave_origem,) if isinstance(chave_origem, str) else chave_origem
        pais = (
            nos_aprovados(arv_mod.chave_item(partes[:-1]))
            if len(partes) > 1
            else frozenset()
        )
        if len(partes) > 1 and not pais:
            return None
        return (nivel, pais, regra)

    nos_por_nome: dict[str, set[str]] = {}
    for no in arvore.nos.values():
        if no.status == "ativo" and no.nivel in ("materia", "assunto"):
            regra = chave_regra(no.nome).chave
            if regra:
                nos_por_nome.setdefault(regra, set()).add(no.id)

    # Itens abaixo de cada título de bloco, para inferir a disciplina (M2).
    filhos_por_materia: dict[str, list[str]] = {}
    for nivel_filho in ("assunto", "subassunto"):
        for chave_filho in getattr(nomes, nivel_filho):
            filhos_por_materia.setdefault(chave_filho[0], []).append(
                arv_mod.chave_item(chave_filho)
            )

    # Nível a nível: o assunto mapeado agora já serve de pai para o subassunto.
    for nivel in NIVEIS:
        fonte = getattr(nomes, nivel)
        chave_orig_por_chave = {arv_mod.chave_item(k): k for k in fonte}
        indice: dict[tuple, set[frozenset[str]]] = {}
        pendentes = []
        for chave_origem, info in fonte.items():
            chave = arv_mod.chave_item(chave_origem)
            sig = assinatura(nivel, chave_origem, info["nome"])
            if chave in arvore.mapeamentos:
                nos = nos_aprovados(chave)
                if sig and nos:
                    indice.setdefault(sig, set()).add(nos)
            elif sig:
                pendentes.append((chave, sig))
            else:
                res.pendentes += 1
                res.chaves_pendentes.append(chave)
        memoria = memoria_mapeamento.construir_indice(arvore) if pendentes else None
        for chave, sig in pendentes:
            candidatos = indice.get(sig, set())
            origem_memoria = False
            if not candidatos:
                nos_mem = memoria_mapeamento.resolver_por_memoria(
                    arvore, sig[2], nivel, sig[1], memoria
                )
                if nos_mem:
                    candidatos = {nos_mem}
                    origem_memoria = True
            if not candidatos and nivel == "materia":
                # Título de bloco fora da lista de disciplinas: vira o assunto de
                # mesmo nome, nunca disciplina nova (Etapa 5B.3, ADR-030).
                # Só com disciplina compatível ou nome específico, sem veto (M2).
                nome_item = fonte[chave_orig_por_chave[chave]]["nome"]
                nos_titulo = alvo_de_titulo_por_nome(
                    arvore,
                    sig[2],
                    nome_item,
                    nos_por_nome.get(sig[2], set()),
                    disciplinas_inferidas_do_bloco(arvore, chave, filhos_por_materia),
                    memoria.vetados,
                )
                if nos_titulo:
                    candidatos = {nos_titulo}
            if len(candidatos) != 1:
                res.pendentes += 1
                res.chaves_pendentes.append(chave)
                continue
            (nos,) = candidatos
            try:
                arv_mod.mapear(
                    arvore, chave, sorted(nos), origem="regra", status="aprovado"
                )
            except arv_mod.ArvoreInvalida as e:
                logger.warning(f"[ARVORE] Mapeamento recusado para {chave}: {e}")
                res.pendentes += 1
                res.chaves_pendentes.append(chave)
                continue
            if origem_memoria:
                res.por_memoria += 1
            else:
                res.por_nome += 1

    if res.total and gravar:
        arv_mod.salvar(arvore, arvore_path)
    logger.info(
        f"[ARVORE] Passo determinístico: {res.por_nome} por regra de nome, "
        f"{res.por_memoria} por memória do dono, {res.pendentes} pendente(s)."
    )
    return res


def arvore_apos_passo(revisao_dir: Path, arvore):
    """Cópia da árvore com o passo determinístico aplicado em memória.

    É a única definição de "este item tem destino na árvore?" para o relatório de
    revisão e para a tabela do Datasette (M1, Etapa 5B.4): quem mostra o estado
    dos itens lê esta cópia, em vez de reimplementar a equivalência. Um item tem
    destino quando a cópia tem mapeamento aprovado para a chave; o que o passo
    não mapeia é pendente, proposto ou sem equivalente. Nada é gravado, e a
    árvore recebida não muda. Devolve `(cópia, ResultadoRegra)`.
    """
    copia = copy.deepcopy(arvore)
    res = mapear_novos_itens(revisao_dir, gravar=False, arvore_mem=copia)
    return copia, res
