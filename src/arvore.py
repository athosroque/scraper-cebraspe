import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from src import canonico

PROJETO_DIR = Path(__file__).resolve().parent.parent
ARVORE_PADRAO = PROJETO_DIR / "canonico" / "arvore.json"

NIVEIS = ("materia", "assunto", "subassunto")
NIVEL_PAI = {"materia": None, "assunto": "materia", "subassunto": "assunto"}


class ArvoreInvalida(ValueError):
    pass


@dataclass
class NoArvore:
    id: str
    nivel: Literal["materia", "assunto", "subassunto"]
    nome: str
    pai: str | None
    origem: Literal["semente", "humano", "llm"]
    status: Literal["ativo", "proposto", "fundido", "aposentado"]
    fundido_em: str | None = None


@dataclass
class Mapeamento:
    no_id: str
    origem: Literal["semente", "regra", "llm", "humano"]
    status: Literal["proposto", "aprovado", "rejeitado"]


@dataclass
class Proposta:
    id: str
    tipo: Literal["fundir", "mover", "criar", "remapear", "aposentar"]
    args: dict
    origem: Literal["regra", "llm", "humano"]
    justificativa: str
    status: Literal["proposto", "aprovado", "rejeitado"]
    materia: str = ""


@dataclass
class ArvoreMestre:
    nos: dict[str, NoArvore] = field(default_factory=dict)
    mapeamentos: dict[str, list[Mapeamento]] = field(default_factory=dict)
    propostas: dict[str, Proposta] = field(default_factory=dict)


def resolver_no(arvore: ArvoreMestre, no_id: str) -> str:
    vistos = set()
    atual = no_id
    while atual in arvore.nos:
        no = arvore.nos[atual]
        if no.status == "fundido" and no.fundido_em:
            if atual in vistos:
                raise ArvoreInvalida(f"Ciclo de fusão detectado em {atual}")
            vistos.add(atual)
            atual = no.fundido_em
        else:
            break
    return atual


def _gerar_id(nivel: str, s: str) -> str:
    prefixo = {"materia": "NM", "assunto": "NA", "subassunto": "NS"}[nivel]
    return f"{prefixo}-{hashlib.sha1(s.encode('utf-8')).hexdigest()[:10]}"


def criar_no(
    arvore: ArvoreMestre,
    nivel: str,
    nome: str,
    pai: str | None,
    origem: str = "humano",
    status: str = "ativo",
    id_override: str | None = None,
) -> str:
    if nivel != "materia":
        if not pai:
            raise ArvoreInvalida(f"Nó de nível {nivel} precisa de pai")
        pai = resolver_no(arvore, pai)
        no_pai = arvore.nos.get(pai)
        if not no_pai:
            raise ArvoreInvalida(f"Pai {pai} não existe")
        if no_pai.status == "aposentado":
            raise ArvoreInvalida(f"Não é possível criar nó sob o nó aposentado {pai}")
        if no_pai.nivel != NIVEL_PAI[nivel]:
            raise ArvoreInvalida(
                f"Nível do pai ({no_pai.nivel}) inválido para nó {nivel}"
            )
    else:
        if pai:
            raise ArvoreInvalida("Matéria não pode ter pai")

    no_id = id_override or _gerar_id(nivel, f"{pai or ''}|{nome}")
    if no_id in arvore.nos:
        raise ArvoreInvalida(f"Nó {no_id} já existe ({arvore.nos[no_id].nome})")

    arvore.nos[no_id] = NoArvore(
        id=no_id,
        nivel=nivel,
        nome=nome,
        pai=pai,
        origem=origem,
        status=status,
    )
    return no_id


def renomear_no(arvore: ArvoreMestre, no_id: str, nome: str) -> None:
    no_id = resolver_no(arvore, no_id)
    if no_id not in arvore.nos:
        raise ArvoreInvalida(f"Nó {no_id} não existe")
    arvore.nos[no_id].nome = nome


def _verificar_ciclo(arvore: ArvoreMestre, no_id: str, novo_pai: str) -> None:
    atual = novo_pai
    while atual:
        if atual == no_id:
            raise ArvoreInvalida(
                f"Ciclo detectado: não é possível mover {no_id} para {novo_pai}"
            )
        if atual not in arvore.nos:
            break
        atual = arvore.nos[atual].pai if arvore.nos[atual].pai else None


def mover_no(arvore: ArvoreMestre, no_id: str, novo_pai: str) -> None:
    if not novo_pai:
        raise ArvoreInvalida("Informe o novo pai (matéria não se move)")
    no_id = resolver_no(arvore, no_id)
    no = arvore.nos.get(no_id)
    if not no:
        raise ArvoreInvalida(f"Nó {no_id} não existe")
    if no.nivel == "materia":
        raise ArvoreInvalida("Matéria não pode ser movida")
    if no.status == "fundido":
        raise ArvoreInvalida(f"Nó fundido {no_id} não pode ser movido")
    if no.status == "aposentado":
        raise ArvoreInvalida(f"Nó aposentado {no_id} não pode ser movido")

    novo_pai = resolver_no(arvore, novo_pai)
    pai_no = arvore.nos.get(novo_pai)
    if not pai_no:
        raise ArvoreInvalida(f"Novo pai {novo_pai} não existe")
    if pai_no.status == "aposentado":
        raise ArvoreInvalida(f"Não é possível mover para o nó aposentado {novo_pai}")
    if pai_no.nivel != NIVEL_PAI[no.nivel]:
        raise ArvoreInvalida(
            f"Nível do novo pai ({pai_no.nivel}) inválido para nó {no.nivel}"
        )

    _verificar_ciclo(arvore, no_id, novo_pai)
    no.pai = novo_pai


def fundir_nos(arvore: ArvoreMestre, origem_id: str, destino_id: str) -> None:
    origem_id = resolver_no(arvore, origem_id)
    destino_id = resolver_no(arvore, destino_id)

    if origem_id == destino_id:
        return

    no_orig = arvore.nos.get(origem_id)
    no_dest = arvore.nos.get(destino_id)

    if not no_orig or not no_dest:
        raise ArvoreInvalida("Nó de origem ou destino não existe")

    if no_orig.nivel != no_dest.nivel:
        raise ArvoreInvalida("Não é possível fundir nós de níveis diferentes")

    if no_orig.status == "aposentado":
        raise ArvoreInvalida(f"Nó aposentado {origem_id} não pode ser fundido")
    if no_dest.status == "aposentado":
        raise ArvoreInvalida(
            f"Nó aposentado {destino_id} não pode ser destino de fusão"
        )

    no_orig.status = "fundido"
    no_orig.fundido_em = destino_id

    # Atualizar pais que apontam para o nó fundido
    for no in arvore.nos.values():
        if no.pai == origem_id:
            no.pai = destino_id


def aposentar_no(arvore: ArvoreMestre, no_id: str) -> None:
    no = arvore.nos.get(no_id)
    if not no:
        raise ArvoreInvalida(f"Nó {no_id} não existe")
    if no.status == "fundido":
        raise ArvoreInvalida(f"Nó fundido {no_id} não pode ser aposentado")
    if no.status == "aposentado":
        return

    # Exige nenhum filho ativo ou proposto
    filhos_ativos = [
        f.id
        for f in arvore.nos.values()
        if f.pai
        and resolver_no(arvore, f.pai) == no_id
        and f.status in ("ativo", "proposto")
    ]
    if filhos_ativos:
        raise ArvoreInvalida(
            f"Nó {no_id} possui filhos ativos/propostos ({len(filhos_ativos)}) e não pode ser aposentado"
        )

    # Exige nenhum mapeamento aprovado
    for item, maps in arvore.mapeamentos.items():
        for m in maps:
            if m.status == "aprovado" and (
                m.no_id == no_id or resolver_no(arvore, m.no_id) == no_id
            ):
                raise ArvoreInvalida(
                    f"Nó {no_id} possui mapeamento aprovado ({item}) e não pode ser aposentado"
                )

    no.status = "aposentado"


def mapear(
    arvore: ArvoreMestre,
    item: str,
    no_ids: list[str],
    origem: str = "humano",
    status: str = "aprovado",
) -> None:
    resolvidos = []
    for n in no_ids:
        final_id = resolver_no(arvore, n)
        no = arvore.nos.get(final_id)
        if not no:
            raise ArvoreInvalida(f"Nó {final_id} não existe")
        if no.status == "fundido":
            raise ArvoreInvalida(f"Não é possível mapear para o nó fundido {final_id}")
        if no.status == "aposentado":
            raise ArvoreInvalida(
                f"Não é possível mapear para o nó aposentado {final_id}"
            )
        resolvidos.append(final_id)

    lista = arvore.mapeamentos.setdefault(item, [])
    for n in resolvidos:
        existente = next((m for m in lista if m.no_id == n), None)
        if existente is None:
            lista.append(Mapeamento(no_id=n, origem=origem, status=status))
        elif status == "aprovado" and existente.status != "aprovado":
            # Mapear de novo um apontamento proposto/rejeitado é a decisão do dono.
            existente.origem = origem
            existente.status = "aprovado"


def _mapeamentos_do_no(arvore: ArvoreMestre, item: str, no_id: str) -> list[Mapeamento]:
    """Apontamentos de `item` para `no_id` (aceita o ID original ou o resolvido)."""
    alvo = resolver_no(arvore, no_id)
    encontrados = [
        m
        for m in arvore.mapeamentos.get(item, [])
        if m.no_id == no_id or resolver_no(arvore, m.no_id) == alvo
    ]
    if not encontrados:
        raise ArvoreInvalida(f"Item {item!r} não aponta para o nó {no_id}")
    return encontrados


def desmapear(arvore: ArvoreMestre, item: str, no_id: str) -> None:
    remover = _mapeamentos_do_no(arvore, item, no_id)
    restantes = [
        m for m in arvore.mapeamentos[item] if all(m is not r for r in remover)
    ]
    if restantes:
        arvore.mapeamentos[item] = restantes
    else:
        del arvore.mapeamentos[item]


def aprovar(arvore: ArvoreMestre, item: str, no_id: str) -> None:
    alvo = resolver_no(arvore, no_id)
    no = arvore.nos.get(alvo)
    if no and no.status == "aposentado":
        raise ArvoreInvalida(
            f"Não é possível aprovar mapeamento para o nó aposentado {no_id}"
        )
    for m in _mapeamentos_do_no(arvore, item, no_id):
        m.status = "aprovado"


def rejeitar(arvore: ArvoreMestre, item: str, no_id: str) -> None:
    for m in _mapeamentos_do_no(arvore, item, no_id):
        m.status = "rejeitado"


def chave_item(chave: str | tuple[str, ...]) -> str:
    """Chave do item de edital no JSON: a chave natural do banco unida por `|`
    (`materia`, `materia|topico`, `materia|topico|subtopico`)."""
    if isinstance(chave, str):
        return chave
    return "|".join(chave)


def carregar(path: Path = ARVORE_PADRAO) -> ArvoreMestre:
    if not path.exists():
        return ArvoreMestre()

    data = json.loads(path.read_text(encoding="utf-8"))

    arvore = ArvoreMestre()
    for no_id, n_data in data.get("nos", {}).items():
        arvore.nos[no_id] = NoArvore(**n_data)

    for item, maps in data.get("mapeamentos", {}).items():
        arvore.mapeamentos[item] = [Mapeamento(**m) for m in maps]

    for prop_id, p_data in data.get("propostas", {}).items():
        arvore.propostas[prop_id] = Proposta(**p_data)

    return arvore


def salvar(arvore: ArvoreMestre, path: Path = ARVORE_PADRAO) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas = ["{"]
    linhas.append(' "nos": {')

    nos_items = sorted(arvore.nos.items())
    for i, (no_id, no) in enumerate(nos_items):
        linha = f"  {json.dumps(no_id)}: {json.dumps(asdict(no), ensure_ascii=False)}"
        if i < len(nos_items) - 1:
            linha += ","
        linhas.append(linha)

    linhas.append(" },")
    linhas.append(' "mapeamentos": {')

    map_items = sorted(arvore.mapeamentos.items())
    for i, (item, maps) in enumerate(map_items):
        maps_dict_list = [asdict(m) for m in sorted(maps, key=lambda x: x.no_id)]
        linha = (
            f"  {json.dumps(item)}: {json.dumps(maps_dict_list, ensure_ascii=False)}"
        )
        if i < len(map_items) - 1:
            linha += ","
        linhas.append(linha)

    if arvore.propostas:
        linhas.append(" },")
        linhas.append(' "propostas": {')
        prop_items = sorted(arvore.propostas.items())
        for i, (prop_id, prop) in enumerate(prop_items):
            linha = f"  {json.dumps(prop_id)}: {json.dumps(asdict(prop), ensure_ascii=False)}"
            if i < len(prop_items) - 1:
                linha += ","
            linhas.append(linha)
        linhas.append(" }")
    else:
        linhas.append(" }")
    linhas.append("}")

    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def materia_do_no(arv: ArvoreMestre, no_id: str) -> str:
    """Devolve o ID da matéria ancestral do nó (ou o próprio nó se for matéria)."""
    no_id = resolver_no(arv, no_id)
    no = arv.nos.get(no_id)
    if not no:
        return ""
    if no.nivel == "materia":
        return no.id
    if no.nivel == "assunto":
        return resolver_no(arv, no.pai) if no.pai else ""
    if no.nivel == "subassunto":
        if not no.pai:
            return ""
        assunto_id = resolver_no(arv, no.pai)
        assunto = arv.nos.get(assunto_id)
        if not assunto or not assunto.pai:
            return ""
        return resolver_no(arv, assunto.pai)
    return ""


def _canonizar_args(args: dict, tipo: str | None = None) -> dict:
    canon = {}
    for k in sorted(args.keys()):
        v = args[k]
        if isinstance(v, list):
            canon[k] = sorted(v)
        else:
            canon[k] = v

    if tipo == "remapear" and "para" in canon:
        p = canon["para"]
        if isinstance(p, str):
            canon["para"] = [p]
        elif isinstance(p, (list, tuple, set)):
            canon["para"] = sorted(p)
    elif tipo == "aposentar" and "no_id" in canon and "no" not in canon:
        canon["no"] = canon.pop("no_id")

    return canon


def _gerar_id_proposta(tipo: str, args: dict) -> str:
    args_json = json.dumps(
        _canonizar_args(args, tipo=tipo), sort_keys=True, ensure_ascii=False
    )
    digest = hashlib.sha1(f"{tipo}:{args_json}".encode()).hexdigest()[:10]
    return f"P-{digest}"


def _executar_operacao(
    arv: ArvoreMestre, tipo: str, args: dict, origem: str = "regra"
) -> None:
    if tipo == "fundir":
        if "origem" not in args or "destino" not in args:
            raise ArvoreInvalida(
                "Argumentos 'origem' e 'destino' obrigatórios para fundir"
            )
        fundir_nos(arv, args["origem"], args["destino"])
    elif tipo == "mover":
        if "no" not in args or "pai" not in args:
            raise ArvoreInvalida("Argumentos 'no' e 'pai' obrigatórios para mover")
        mover_no(arv, args["no"], args["pai"])
    elif tipo == "criar":
        if "nivel" not in args or "nome" not in args:
            raise ArvoreInvalida("Argumentos 'nivel' e 'nome' obrigatórios para criar")
        no_id = args.get("id") or _gerar_id(
            args["nivel"], f"{args.get('pai') or ''}|{args['nome']}"
        )
        if no_id in arv.nos:
            if arv.nos[no_id].status != "proposto":
                raise ArvoreInvalida(
                    f"Nó {no_id} já existe com status {arv.nos[no_id].status}"
                )
            arv.nos[no_id].status = "ativo"
        else:
            criar_no(
                arv,
                nivel=args["nivel"],
                nome=args["nome"],
                pai=args.get("pai"),
                origem=origem,
                status="ativo",
                id_override=no_id,
            )
    elif tipo == "remapear":
        if "item" not in args or "de" not in args or "para" not in args:
            raise ArvoreInvalida(
                "Argumentos 'item', 'de' e 'para' obrigatórios para remapear"
            )
        desmapear(arv, args["item"], args["de"])
        destinos = (
            [args["para"]] if isinstance(args["para"], str) else list(args["para"])
        )
        mapear(arv, args["item"], destinos, origem=origem, status="aprovado")
    elif tipo == "aposentar":
        no_id = args.get("no") or args.get("no_id")
        if not no_id:
            raise ArvoreInvalida("Argumento 'no' obrigatório para aposentar")
        aposentar_no(arv, no_id)
    else:
        raise ArvoreInvalida(f"Tipo de proposta inválido: {tipo!r}")


def _inferir_materia_proposta(arv: ArvoreMestre, tipo: str, args: dict) -> str:
    if tipo == "criar":
        pai = args.get("pai")
        if pai:
            return materia_do_no(arv, pai)
        return args.get("id", "")
    elif tipo == "mover":
        return materia_do_no(arv, args.get("no", ""))
    elif tipo == "fundir":
        return materia_do_no(arv, args.get("destino", ""))
    elif tipo == "remapear":
        m = materia_do_no(arv, args.get("de", ""))
        if m:
            return m
        destinos = args.get("para", [])
        if isinstance(destinos, str):
            destinos = [destinos]
        for d in destinos:
            m = materia_do_no(arv, d)
            if m:
                return m
        return ""
    elif tipo == "aposentar":
        return materia_do_no(arv, args.get("no") or args.get("no_id", ""))
    return ""


def propor(
    arv: ArvoreMestre,
    tipo: Literal["fundir", "mover", "criar", "remapear", "aposentar"],
    args: dict,
    origem: Literal["regra", "llm", "humano"],
    justificativa: str,
    materia: str = "",
) -> str:
    if tipo not in ("fundir", "mover", "criar", "remapear", "aposentar"):
        raise ArvoreInvalida(f"Tipo de proposta inválido: {tipo!r}")

    if origem not in ("regra", "llm", "humano"):
        raise ArvoreInvalida(f"Origem {origem!r} inválida (use regra, llm, humano)")

    args_canonicos = _canonizar_args(args, tipo=tipo)

    if tipo == "criar":
        if args_canonicos.get("nivel") not in NIVEIS:
            raise ArvoreInvalida(
                f"Nível {args_canonicos.get('nivel')!r} inválido (use {', '.join(NIVEIS)})"
            )
        if not args_canonicos.get("nome") or not str(args_canonicos["nome"]).strip():
            raise ArvoreInvalida("Argumento 'nome' obrigatório para criar nó")
        if "id" not in args_canonicos:
            no_id = _gerar_id(
                args_canonicos["nivel"],
                f"{args_canonicos.get('pai') or ''}|{args_canonicos['nome']}",
            )
            args_canonicos["id"] = no_id
    elif tipo == "fundir":
        if not args_canonicos.get("origem") or not args_canonicos.get("destino"):
            raise ArvoreInvalida(
                "Argumentos 'origem' e 'destino' obrigatórios para fundir"
            )
    elif tipo == "mover":
        if not args_canonicos.get("no") or not args_canonicos.get("pai"):
            raise ArvoreInvalida("Argumentos 'no' e 'pai' obrigatórios para mover")
    elif tipo == "remapear":
        if (
            not args_canonicos.get("item")
            or not args_canonicos.get("de")
            or not args_canonicos.get("para")
        ):
            raise ArvoreInvalida(
                "Argumentos 'item', 'de' e 'para' obrigatórios para remapear"
            )
    elif tipo == "aposentar":
        if not args_canonicos.get("no"):
            raise ArvoreInvalida("Argumento 'no' obrigatório para aposentar")

    prop_id = _gerar_id_proposta(tipo, args_canonicos)

    if not materia:
        materia = _inferir_materia_proposta(arv, tipo, args_canonicos)

    if prop_id in arv.propostas:
        return prop_id

    # Validar em cópia isolada (deepcopy)
    copia = copy.deepcopy(arv)

    # Para propostas de aposentadoria, simulamos apenas os remapeamentos pendentes
    # que liberam o nó alvo (e eventuais movimentos/fusões de filhos do nó alvo),
    # sem executar propostas não relacionadas que possam conflitar com alternativas.
    if tipo == "aposentar":
        no_alvo = args_canonicos.get("no", "")
        for p in copia.propostas.values():
            if p.status == "proposto":
                if p.tipo == "remapear" and (
                    p.args.get("de") == no_alvo
                    or resolver_no(copia, p.args.get("de", "")) == no_alvo
                ):
                    try:
                        _executar_operacao(copia, p.tipo, p.args, origem=p.origem)
                    except ArvoreInvalida:
                        pass
                elif p.tipo in ("mover", "fundir", "aposentar"):
                    filho_id = (
                        p.args.get("no")
                        if p.tipo in ("mover", "aposentar")
                        else p.args.get("origem")
                    )
                    filho_no = copia.nos.get(filho_id)
                    if (
                        filho_no
                        and filho_no.pai
                        and resolver_no(copia, filho_no.pai) == no_alvo
                    ):
                        try:
                            _executar_operacao(copia, p.tipo, p.args, origem=p.origem)
                        except ArvoreInvalida:
                            pass

    if tipo == "criar":
        criar_no(
            copia,
            nivel=args_canonicos["nivel"],
            nome=args_canonicos["nome"],
            pai=args_canonicos.get("pai"),
            origem=origem,
            status="proposto",
            id_override=args_canonicos.get("id"),
        )
        criar_no(
            arv,
            nivel=args_canonicos["nivel"],
            nome=args_canonicos["nome"],
            pai=args_canonicos.get("pai"),
            origem=origem,
            status="proposto",
            id_override=args_canonicos.get("id"),
        )
    else:
        _executar_operacao(copia, tipo, args_canonicos, origem=origem)

    arv.propostas[prop_id] = Proposta(
        id=prop_id,
        tipo=tipo,
        args=args_canonicos,
        origem=origem,
        justificativa=justificativa,
        status="proposto",
        materia=materia,
    )
    return prop_id


def aprovar_propostas(arv: ArvoreMestre, ids: list[str]) -> list[str]:
    """Aplica as propostas com execução transacional atômica (tudo ou nada).

    Se houver dependências no mesmo lote (ex.: remapear antes de aposentar, ou
    criar antes de mover), resolve em múltiplas passagens preservando atomicidade.
    """
    ids_unicos = list(dict.fromkeys(ids))
    for pid in ids_unicos:
        if pid not in arv.propostas:
            raise ArvoreInvalida(f"Proposta {pid} não existe")
        prop = arv.propostas[pid]
        if prop.status == "aprovado":
            raise ArvoreInvalida(f"Proposta {pid} já foi aprovada")
        if prop.status == "rejeitado":
            raise ArvoreInvalida(
                f"Proposta {pid} já foi rejeitada e não pode ser aprovada"
            )

    copia = copy.deepcopy(arv)
    tentativas = list(ids_unicos)
    ultimo_erro = None

    while tentativas:
        progresso = False
        proxima_rodada = []
        for pid in tentativas:
            prop = copia.propostas[pid]
            snapshot = copy.deepcopy(copia)
            try:
                _executar_operacao(copia, prop.tipo, prop.args, origem=prop.origem)
                prop.status = "aprovado"
                progresso = True
            except ArvoreInvalida as e:
                copia = snapshot
                proxima_rodada.append(pid)
                ultimo_erro = e

        if not progresso:
            raise ultimo_erro or ArvoreInvalida("Falha ao aprovar lote de propostas")
        tentativas = proxima_rodada

    # Tudo deu certo: atualiza árvore real
    arv.nos = copia.nos
    arv.mapeamentos = copia.mapeamentos
    arv.propostas = copia.propostas
    return ids_unicos


def _remover_no_proposto_se_orfao(arv: ArvoreMestre, no_id: str) -> None:
    if no_id not in arv.nos or arv.nos[no_id].status != "proposto":
        return
    referenciado = (
        any(
            n.pai and resolver_no(arv, n.pai) == no_id
            for n in arv.nos.values()
            if n.id != no_id
        )
        or any(
            n.fundido_em and resolver_no(arv, n.fundido_em) == no_id
            for n in arv.nos.values()
        )
        or any(
            resolver_no(arv, m.no_id) == no_id
            for maps in arv.mapeamentos.values()
            for m in maps
        )
        or any(
            p.status == "proposto"
            and (
                p.args.get("no") == no_id
                or p.args.get("pai") == no_id
                or p.args.get("origem") == no_id
                or p.args.get("destino") == no_id
                or p.args.get("de") == no_id
                or (isinstance(p.args.get("para"), list) and no_id in p.args["para"])
                or p.args.get("para") == no_id
            )
            for p in arv.propostas.values()
        )
    )
    if not referenciado:
        del arv.nos[no_id]


def rejeitar_proposta(arv: ArvoreMestre, id: str) -> None:
    if id not in arv.propostas:
        raise ArvoreInvalida(f"Proposta {id} não existe")

    prop = arv.propostas[id]
    if prop.status == "aprovado":
        raise ArvoreInvalida(f"Proposta {id} já foi aprovada e não pode ser rejeitada")
    if prop.status == "rejeitado":
        return

    prop.status = "rejeitado"

    if prop.tipo == "criar":
        no_id = prop.args.get("id") or _gerar_id(
            prop.args["nivel"],
            f"{prop.args.get('pai') or ''}|{prop.args['nome']}",
        )
        _remover_no_proposto_se_orfao(arv, no_id)

    # Limpar eventuais nós propostos cujas propostas de criação já foram rejeitadas
    # mas que foram mantidos devido a referências que agora não existem mais.
    # Executa em loop até ponto fixo para cobrir dependências em cadeia.
    mudou = True
    while mudou:
        nos_antes = len(arv.nos)
        for p in arv.propostas.values():
            if p.tipo == "criar" and p.status == "rejeitado":
                nid = p.args.get("id") or _gerar_id(
                    p.args["nivel"],
                    f"{p.args.get('pai') or ''}|{p.args['nome']}",
                )
                _remover_no_proposto_se_orfao(arv, nid)
        mudou = len(arv.nos) < nos_antes


PADRAO_DECOMPOSICAO = re.compile(r"[,;]|\s+e\s+", re.IGNORECASE)


def detectar_compostos(arv: ArvoreMestre) -> dict[str, list[str]]:
    """Examina cada nó ativo, decompondo seu nome por ',', ';' e ' e '.

    Se todas as partes tiverem correspondência exata via `chave_regra` com
    irmãos ativos sob o mesmo pai efetivo, gera propostas com origem 'regra':
    'remapear' dos itens do composto para os irmãos e 'aposentar' do composto.

    Devolve dict {no_id: [irmao_id1, irmao_id2, ...]}.
    """
    detectados: dict[str, list[str]] = {}

    for no_id, no in sorted(arv.nos.items()):
        if no.status != "ativo" or not no.pai:
            continue
        partes = [p.strip() for p in PADRAO_DECOMPOSICAO.split(no.nome) if p.strip()]
        if len(partes) < 2:
            continue

        pai_efetivo = resolver_no(arv, no.pai)
        irmaos = [
            s
            for s in arv.nos.values()
            if s.id != no.id
            and s.status == "ativo"
            and s.pai
            and resolver_no(arv, s.pai) == pai_efetivo
            and s.nivel == no.nivel
        ]
        mapa_irmaos: dict[str, list[str]] = {}
        for irmao in irmaos:
            c = canonico.chave_regra(irmao.nome).chave
            mapa_irmaos.setdefault(c, []).append(irmao.id)

        matches = []
        valido = True
        for p in partes:
            c = canonico.chave_regra(p).chave
            if c in mapa_irmaos and len(mapa_irmaos[c]) == 1:
                matches.append(mapa_irmaos[c][0])
            else:
                valido = False
                break

        if not valido or len(set(matches)) != len(partes):
            continue

        irmaos_dest = sorted(matches)
        detectados[no.id] = irmaos_dest
        materia_id = materia_do_no(arv, no.id)

        # Gerar remapear para itens que apontam para o composto
        for item, maps in sorted(arv.mapeamentos.items()):
            aponta = any(
                m.status == "aprovado"
                and (m.no_id == no.id or resolver_no(arv, m.no_id) == no.id)
                for m in maps
            )
            if aponta:
                propor(
                    arv,
                    tipo="remapear",
                    args={"item": item, "de": no.id, "para": irmaos_dest},
                    origem="regra",
                    justificativa=(
                        f"Remapeamento determinístico de composto {no.id} "
                        f"({no.nome!r}) para os irmãos {', '.join(irmaos_dest)}"
                    ),
                    materia=materia_id,
                )

        # Tentar gerar aposentar para o nó composto
        try:
            propor(
                arv,
                tipo="aposentar",
                args={"no": no.id},
                origem="regra",
                justificativa=(
                    f"Aposentadoria de nó composto {no.id} ({no.nome!r}) sem uso"
                ),
                materia=materia_id,
            )
        except ArvoreInvalida:
            pass

    return detectados


def detectar_homonimos(arv: ArvoreMestre) -> dict[str, list[str]]:
    """Propõe `fundir` (origem 'regra') para irmãos ativos com a mesma `chave_regra`.

    Fundir dois assuntos junta os filhos sob o destino, mas não funde os
    subassuntos de mesmo nome que vieram de cada lado. O destino é o irmão com
    mais apontamentos aprovados e filhos ativos (empate: menor ID).

    Devolve dict {destino_id: [origem_id, ...]}.
    """
    uso: dict[str, int] = {}
    for maps in arv.mapeamentos.values():
        for m in maps:
            if m.status == "aprovado":
                alvo = resolver_no(arv, m.no_id)
                uso[alvo] = uso.get(alvo, 0) + 1
    for n in arv.nos.values():
        if n.status == "ativo" and n.pai:
            pai = resolver_no(arv, n.pai)
            uso[pai] = uso.get(pai, 0) + 1

    grupos: dict[tuple[str, str, str], list[str]] = {}
    for no in arv.nos.values():
        if no.status != "ativo" or not no.pai:
            continue
        chave = canonico.chave_regra(no.nome).chave
        grupos.setdefault((resolver_no(arv, no.pai), no.nivel, chave), []).append(no.id)

    detectados: dict[str, list[str]] = {}
    for ids in grupos.values():
        if len(ids) < 2:
            continue
        destino, *origens = sorted(ids, key=lambda i: (-uso.get(i, 0), i))
        detectados[destino] = origens
        for origem in origens:
            propor(
                arv,
                tipo="fundir",
                args={"origem": origem, "destino": destino},
                origem="regra",
                justificativa=(
                    f"Irmãos homônimos: {arv.nos[origem].nome!r} ({origem}) e "
                    f"{arv.nos[destino].nome!r} ({destino}) sob o mesmo pai"
                ),
                materia=materia_do_no(arv, destino),
            )
    return detectados
