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

    if no_orig.status == "aposentado":
        raise ArvoreInvalida(f"Nó aposentado {origem_id} não pode ser fundido")
    if no_dest.status == "aposentado":
        raise ArvoreInvalida(
            f"Nó aposentado {destino_id} não pode ser destino de fusão"
        )

    entre_niveis = no_orig.nivel != no_dest.nivel
    if entre_niveis:
        # KAN-64 (ADR-030): nível diferente só para assunto/subassunto e quando a
        # origem não tem filhos ativos (não há como reposicionar a subárvore).
        if no_orig.nivel == "materia" or no_dest.nivel == "materia":
            raise ArvoreInvalida("Matéria não funde com nó de nível diferente")
        if no_orig.status != "ativo" or no_dest.status != "ativo":
            raise ArvoreInvalida(
                "Fusão entre níveis exige origem e destino ativos "
                f"({origem_id}: {no_orig.status}, {destino_id}: {no_dest.status})"
            )
        filhos = sorted(
            no.id
            for no in arvore.nos.values()
            if no.status in ("ativo", "proposto")
            and no.pai
            and resolver_no(arvore, no.pai) == origem_id
        )
        if filhos:
            raise ArvoreInvalida(
                f"Fusão entre níveis exige origem sem filhos ativos; "
                f"{origem_id} tem {', '.join(filhos)}"
            )

    no_orig.status = "fundido"
    no_orig.fundido_em = destino_id

    # Atualizar pais que apontam para o nó fundido (entre níveis não há filhos
    # ativos; os fundidos/aposentados resolvem pelo `fundido_em`).
    if not entre_niveis:
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


def _filhos_ativos(arvore: ArvoreMestre, no_id: str) -> list[NoArvore]:
    return sorted(
        (
            no
            for no in arvore.nos.values()
            if no.status in ("ativo", "proposto")
            and no.pai
            and resolver_no(arvore, no.pai) == no_id
        ),
        key=lambda no: no.id,
    )


def rebaixar_materia(
    arvore: ArvoreMestre,
    materia_id: str,
    destino_id: str,
    subassuntos: dict[str, str] | None = None,
) -> None:
    """Rebaixa uma matéria para dentro do assunto `destino_id` (Etapa 5B.3, D0).

    A árvore tem 3 níveis fixos: os assuntos da matéria viram subassuntos do
    destino (mesmo ID, então apontamentos e mapeamentos continuam valendo), e os
    subassuntos deles fundem no próprio pai ou no irmão indicado em `subassuntos`.
    A matéria termina `fundido` no destino. Tudo ou nada.
    """
    materia_id = resolver_no(arvore, materia_id)
    destino_id = resolver_no(arvore, destino_id)
    materia = arvore.nos.get(materia_id)
    destino = arvore.nos.get(destino_id)
    if not materia or materia.nivel != "materia" or materia.status != "ativo":
        raise ArvoreInvalida(f"{materia_id} não é matéria ativa")
    if not destino or destino.nivel != "assunto" or destino.status != "ativo":
        raise ArvoreInvalida(f"Destino {destino_id} não é assunto ativo")
    if resolver_no(arvore, destino.pai) == materia_id:
        raise ArvoreInvalida(f"Destino {destino_id} está dentro de {materia_id}")

    copia = copy.deepcopy(arvore)
    assuntos = _filhos_ativos(copia, materia_id)
    propostos = [
        no.id
        for a in assuntos
        for no in [a, *_filhos_ativos(copia, a.id)]
        if no.status == "proposto"
    ]
    if propostos:
        raise ArvoreInvalida(
            f"Rebaixar {materia_id} exige decidir antes os nós propostos: "
            f"{', '.join(propostos)}"
        )
    netos = [s for a in assuntos for s in _filhos_ativos(copia, a.id)]
    ids_netos = {s.id for s in netos}
    alvos = subassuntos or {}
    sobrando = sorted(set(alvos) - ids_netos)
    if sobrando:
        raise ArvoreInvalida(
            f"{', '.join(sobrando)} não é subassunto ativo de {materia_id}"
        )

    for a in assuntos:
        a.nivel = "subassunto"
        a.pai = destino_id
    for s in netos:
        alvo = resolver_no(copia, alvos.get(s.id, s.pai))
        no_alvo = copia.nos.get(alvo)
        if (
            alvos.get(s.id) in ids_netos
            or alvo in ids_netos
            or not no_alvo
            or no_alvo.nivel != "subassunto"
        ):
            raise ArvoreInvalida(
                f"Alvo {alvo} de {s.id} não é subassunto que fica depois do rebaixamento"
            )
        fundir_nos(copia, s.id, alvo)

    no_mat = copia.nos[materia_id]
    no_mat.status = "fundido"
    no_mat.fundido_em = destino_id

    arvore.nos = copia.nos
    arvore.mapeamentos = copia.mapeamentos
    arvore.propostas = copia.propostas


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
    elif tipo == "renomear":
        if "no" not in args or "nome" not in args:
            raise ArvoreInvalida("Argumentos 'no' e 'nome' obrigatórios para renomear")
        renomear_no(arv, args["no"], args["nome"])
    elif tipo == "rebaixar":
        if "materia" not in args or "destino" not in args:
            raise ArvoreInvalida(
                "Argumentos 'materia' e 'destino' obrigatórios para rebaixar"
            )
        rebaixar_materia(arv, args["materia"], args["destino"], args.get("subassuntos"))
    else:
        raise ArvoreInvalida(f"Tipo de proposta inválido: {tipo!r}")


def _trocar_apelidos(valor, apelidos: dict[str, str]):
    if isinstance(valor, str) and valor.startswith("@"):
        if valor not in apelidos:
            raise ArvoreInvalida(f"Apelido {valor} não foi criado antes no lote")
        return apelidos[valor]
    if isinstance(valor, list):
        return [_trocar_apelidos(v, apelidos) for v in valor]
    if isinstance(valor, dict):
        return {
            _trocar_apelidos(k, apelidos): _trocar_apelidos(v, apelidos)
            for k, v in valor.items()
        }
    return valor


OPERACOES_DE_ITEM = ("mapear", "desmapear", "aprovar", "rejeitar")


def _executar_operacao_de_item(arv: ArvoreMestre, tipo: str, args: dict) -> None:
    """Decisão do dono sobre o apontamento de um item de edital, dentro do lote.
    `mapear` leva `{"item", "nos"}` (aprovado, origem humano); as outras levam
    `{"item", "no"}` (KAN-95, KAN-98)."""
    if "item" not in args:
        raise ArvoreInvalida(f"Argumento 'item' obrigatório para {tipo}")
    if tipo == "mapear":
        nos = args.get("nos")
        if not nos:
            raise ArvoreInvalida("Argumento 'nos' obrigatório para mapear")
        mapear(arv, args["item"], [nos] if isinstance(nos, str) else list(nos))
        return
    if "no" not in args:
        raise ArvoreInvalida(f"Argumento 'no' obrigatório para {tipo}")
    {"desmapear": desmapear, "aprovar": aprovar, "rejeitar": rejeitar}[tipo](
        arv, args["item"], args["no"]
    )


def aplicar_lote(arv: ArvoreMestre, operacoes: list[dict]) -> list[str]:
    """Aplica um lote ordenado de operações do dono (Etapa 5B.3). Tudo ou nada.

    Cada operação é `{"tipo", "args"}`, com os tipos de `_executar_operacao` e os
    de item (`OPERACOES_DE_ITEM`: mapear, desmapear, aprovar, rejeitar).
    Um `criar` pode levar `"apelido": "@nome"`: o ID do nó é gerado, e as
    operações seguintes citam o nó novo pelo apelido. Devolve uma linha por
    operação.
    """
    copia = copy.deepcopy(arv)
    apelidos: dict[str, str] = {}
    feitas = []
    for i, op in enumerate(operacoes, 1):
        tipo = op.get("tipo", "")
        try:
            args = _trocar_apelidos(op.get("args", {}), apelidos)
            if tipo == "criar":
                no_id = criar_no(copia, args["nivel"], args["nome"], args.get("pai"))
                apelido = op.get("apelido")
                if apelido:
                    if not apelido.startswith("@") or apelido in apelidos:
                        raise ArvoreInvalida(
                            f"Apelido {apelido!r} inválido ou repetido"
                        )
                    apelidos[apelido] = no_id
                feitas.append(f"{i}: criado {no_id} ({args['nivel']}) {args['nome']!r}")
            elif tipo in OPERACOES_DE_ITEM:
                _executar_operacao_de_item(copia, tipo, args)
                feitas.append(f"{i}: {tipo} {json.dumps(args, ensure_ascii=False)}")
            else:
                _executar_operacao(copia, tipo, args, origem="humano")
                feitas.append(f"{i}: {tipo} {json.dumps(args, ensure_ascii=False)}")
        except (ArvoreInvalida, KeyError) as e:
            raise ArvoreInvalida(f"Operação {i} ({tipo}): {e}") from e

    arv.nos = copia.nos
    arv.mapeamentos = copia.mapeamentos
    arv.propostas = copia.propostas
    return feitas


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
        if args_canonicos.get("nivel") == "materia" and origem != "humano":
            raise ArvoreInvalida(
                "Disciplina nova só por decisão do dono (canonico/disciplinas.json): "
                "proponha um assunto"
            )
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


# ---------------------------------------------------------------------------
# Detecção de conceitos dispersos em pais diferentes (KAN-64, Fase 1)
# ---------------------------------------------------------------------------

# Nomes que só fazem sentido com o pai (subassunto "Conceito" de Atos × de
# Contratos são coisas diferentes). A comparação é pela `chave_regra`, então
# plural, acento e "noções de" já estão cobertos. Esses nomes NUNCA entram em
# `mesmo_nome` nem em `nome_contido`.
_NOMES_GENERICOS_BRUTOS = (
    # estrutura de exposição
    "conceito",
    "conceitos",
    "conceito e características",
    "conceito e classificação",
    "conceitos básicos",
    "conceitos fundamentais",
    "conceitos gerais",
    "conceito geral",
    "noções gerais",
    "noções básicas",
    "noções introdutórias",
    "introdução",
    "generalidades",
    "aspectos gerais",
    "considerações gerais",
    "visão geral",
    "disposições gerais",
    "disposições preliminares",
    "disposições finais",
    "disposições transitórias",
    "disposições constitucionais",
    "princípios",
    "princípios gerais",
    "princípios básicos",
    "princípios constitucionais",
    "fundamentos",
    "histórico",
    "evolução histórica",
    "origem",
    "natureza jurídica",
    "natureza",
    "finalidade",
    "finalidades",
    "objetivos",
    "objeto",
    "importância",
    "definição",
    "definições",
    "terminologia",
    "contexto",
    "tendências",
    # lista de subtipos
    "classificação",
    "classificações",
    "características",
    "caracterização",
    "espécies",
    "modalidades",
    "tipos",
    "tipologia",
    "formas",
    "categorias",
    "elementos",
    "requisitos",
    "pressupostos",
    "efeitos",
    "consequências",
    "hipóteses",
    "exceções",
    "limites",
    "limitações",
    "vícios",
    "extinção",
    "atributos",
    "funções",
    "competência",
    "competências",
    "responsabilidade",
    "responsabilidades",
    "controle",
    "fiscalização",
    "sanções",
    "penalidades",
    "infrações",
    "crimes",
    "prazos",
    "prazo",
    "recursos",
    "recurso",
    "procedimento",
    "procedimentos",
    "processo",
    "fases",
    "etapas",
    "regras",
    "regime jurídico",
    "legislação",
    "legislação pertinente",
    "legislação específica",
    "legislação aplicável",
    "legislação especial",
    "legislação correlata",
    "normas",
    "normas gerais",
    "exemplos",
    "aplicações",
    "aplicação",
    "vantagens e desvantagens",
    "vantagens",
    "desvantagens",
    "vantagens e limitações",
    # saúde e afins (padrão repetido por patologia)
    "etiologia, diagnóstico e tratamento",
    "diagnóstico e tratamento",
    "etiologia",
    "diagnóstico",
    "tratamento",
    "epidemiologia",
    "fisiopatologia",
    "quadro clínico",
    "prevenção",
    "profilaxia",
    "complicações",
    "sinais e sintomas",
    "manifestações clínicas",
    "cuidados de enfermagem",
    "tratamento e prevenção",
    # genéricos de TI, estatística e idiomas
    "segurança",
    "gestão",
    "tecnologia",
    "ferramentas",
    "técnicas",
    "métodos",
    "modelos",
    "arquitetura",
    "componentes",
    "protocolos",
    "padrões",
    "estrutura",
    "interpretação de textos",
    "compreensão de textos",
    "reescrita de frases",
    "significação das palavras",
    "emprego das classes de palavras",
    "ortografia",
    "acentuação",
    "pontuação",
    "sintaxe",
    "morfologia",
    "semântica",
)

NOMES_GENERICOS_DISPERSAO: frozenset[str] = frozenset(
    canonico.chave_regra(n).chave for n in _NOMES_GENERICOS_BRUTOS
)

# Nome cujas palavras significativas são TODAS destas é genérico, mesmo sem
# estar na lista acima ("Conceito e objetivos", "Disposições constitucionais
# aplicáveis", "Jurisprudência aplicada dos tribunais superiores").
_TOKENS_GENERICOS_BRUTOS = (
    "conceito objetivos finalidade princípios classificação características "
    "espécies modalidades tipos geral gerais básico básicos fundamental "
    "fundamentais disposições histórico definição natureza importância "
    "evolução introdução noções aspectos elementos requisitos efeitos "
    "procedimentos legislação normas regras doutrinárias constitucionais "
    "aplicáveis aplicada aplicado jurisprudência pacificada tribunais "
    "superiores"
)
TOKENS_GENERICOS_DISPERSAO: frozenset[str] = frozenset(
    canonico.chave_regra(_TOKENS_GENERICOS_BRUTOS).chave.split()
)

# Matérias de ramos diferentes (Direito Penal × Penal Militar × Processual
# Penal × Processual Civil) usam o mesmo nome para coisas de normas distintas:
# `mesmo_nome` entre elas é só média. Compara-se a assinatura de ramo.
RAMOS_DISPERSAO = frozenset(
    {
        "militar",
        "penal",
        "civil",
        "processual",
        "trabalho",
        "tributario",
        "eleitoral",
        "empresarial",
        "ambiental",
        "constitucional",
        "administrativo",
        "financeiro",
        "previdenciario",
        "internacional",
    }
)

# Nome com no máximo este número de palavras significativas (≥ 3 letras, sem
# stopwords) e menos de CHARS_MIN_NOME_ESPECIFICO caracteres é tratado como
# curto demais para valer fora do contexto do pai (ex.: "Prescrição",
# "Princípios", "Agentes públicos"), exceto quando cita norma.
PALAVRAS_MAX_NOME_CURTO = 1
CHARS_MIN_NOME_ESPECIFICO = 14

_STOPWORDS_DISPERSAO = frozenset(
    {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "o",
        "a",
        "os",
        "as",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "ao",
        "aos",
        "um",
        "uma",
        "ou",
        "se",
    }
)

# Apelidos de normas que o edital cita sem número. Chave: `chave_regra` do nome.
APELIDOS_NORMA: dict[str, tuple[str, str]] = {
    "lei de responsabilidade fiscal": ("lei complementar", "101"),
    "lrf": ("lei complementar", "101"),
    "lei geral de protecao de dado": ("lei", "13709"),
    "lgpd": ("lei", "13709"),
    "lei de acesso a informacao": ("lei", "12527"),
    "lai": ("lei", "12527"),
}

_SIGLAS_NORMA = (
    (re.compile(r"\blc\b"), "lei complementar"),
    (re.compile(r"\bdl\b"), "decreto lei"),
    (re.compile(r"\bmp\b"), "medida provisoria"),
    (re.compile(r"\bec\b"), "emenda constitucional"),
)

# Quantas palavras além da norma ainda deixam o nome "essencialmente a norma".
PALAVRAS_MAX_RESTO_NORMA = 8
_FOLGA_NORMA = frozenset(
    {
        "lei",
        "complementar",
        "decreto",
        "emenda",
        "constitucional",
        "medida",
        "provisoria",
        "resolucao",
        "portaria",
        "no",
        "n",
        "nr",
        "numero",
        "suas",
        "alteracoes",
        "posteriores",
        "e",
        "de",
        "da",
        "do",
    }
)


def _normas_do_nome(nome: str) -> set[tuple[str, str]]:
    """Normas citadas no nome, como {(tipo, número sem pontos)}; o ano é
    ignorado para "LC 101" e "LC nº 101/2000" caírem no mesmo grupo."""
    texto = canonico.normalizar(nome)
    for padrao, longo in _SIGLAS_NORMA:
        texto = padrao.sub(longo, texto)
    achadas = {
        (re.sub(r"\s+", " ", m.group(1)), m.group(2).replace(" ", ""))
        for m in canonico.PADRAO_NORMA.finditer(texto)
    }
    apelido = APELIDOS_NORMA.get(canonico.chave_regra(nome).chave)
    if apelido:
        achadas.add(apelido)
    return achadas


# Palavras que indicam recorte do tema da norma ("Crimes ... (Lei X)", "Tipos de
# penalidades previstas na Lei X"): o nó não é a norma inteira.
_PALAVRAS_RECORTE_NORMA = frozenset(
    {
        "tipo",
        "crime",
        "tipificado",
        "previsto",
        "prevista",
        "competencia",
        "topico",
        "selecionado",
        "sancao",
        "penalidade",
        "infracao",
        "dispositivo",
        "regra",
        "disposicao",
        "aplicacao",
        "principio",
        "alteracao",
        "artigo",
        "art",
        "capitulo",
        "titulo",
        "secao",
        "legislacao",
        "aplicavel",
        "regime",
    }
)
_OUTROS_TIPOS_NORMA = frozenset(
    {"portaria", "resolucao", "instrucao", "decreto", "emenda", "medida"}
)


def _nome_e_a_norma(nome: str) -> bool:
    """O nome é essencialmente a norma: cita uma só, e o que há fora do
    parêntese é só o apelido dela ("Improbidade Administrativa (Lei nº
    8.429/1992)"), sem recorte do tema ("Crimes ... (Lei X)"), lista de
    tópicos (":", ";", ",") ou outra norma junto."""
    normas = _normas_do_nome(nome)
    if len(normas) != 1:
        return False
    tipo = next(iter(normas))[0]
    fora = canonico.PADRAO_PARENTESES.sub(" ", nome)
    if re.search(r"[:;,]", fora):
        return False
    tokens = canonico.normalizar(nome).split()
    if (_OUTROS_TIPOS_NORMA - set(tipo.split())) & set(tokens):
        return False
    texto = canonico.PADRAO_NORMA.sub(" ", canonico.normalizar(fora))
    resto = [
        _singular_simples(t)
        for t in texto.split()
        if t not in _FOLGA_NORMA and t not in _STOPWORDS_DISPERSAO
    ]
    return len(resto) <= PALAVRAS_MAX_RESTO_NORMA and not (
        set(resto) & _PALAVRAS_RECORTE_NORMA
    )


def nos_da_mesma_norma(
    arv: ArvoreMestre, nome: str, ignorar: set[str] | None = None
) -> list[str]:
    """IDs (ordenados) dos nós ativos, fora da matéria, que são a mesma norma
    de `nome` (ADR-030, KAN-64: um conceito com nome próprio, um lugar).

    Vale só quando `nome` e o nó são essencialmente a norma (`_nome_e_a_norma`)
    e citam o mesmo tipo e número. Recorte do tema ("Crimes ... (Lei X)") não
    entra, e fundido ou aposentado também não. Se `nome` não é uma norma,
    devolve [].
    """
    if not _nome_e_a_norma(nome):
        return []
    normas = _normas_do_nome(nome)
    ignorar = ignorar or set()
    return sorted(
        no.id
        for no in arv.nos.values()
        if no.status == "ativo"
        and no.nivel != "materia"
        and no.id not in ignorar
        and _nome_e_a_norma(no.nome)
        and normas & _normas_do_nome(no.nome)
    )


def _singular_simples(t: str) -> str:
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


def _nome_generico(nome: str) -> bool:
    chave = canonico.chave_regra(nome).chave
    if chave in NOMES_GENERICOS_DISPERSAO:
        return True
    if _normas_do_nome(nome):
        return False
    palavras = [
        t for t in chave.split() if len(t) >= 3 and t not in _STOPWORDS_DISPERSAO
    ]
    if palavras and all(t in TOKENS_GENERICOS_DISPERSAO for t in palavras):
        return True
    return len(palavras) <= PALAVRAS_MAX_NOME_CURTO and len(chave) < (
        CHARS_MIN_NOME_ESPECIFICO
    )


def _assinatura_ramo(arv: ArvoreMestre, no_id: str) -> frozenset[str]:
    nome = arv.nos[materia_do_no(arv, no_id)].nome
    return frozenset(canonico.chave_regra(nome).chave.split()) & frozenset(
        canonico.chave_regra(" ".join(RAMOS_DISPERSAO)).chave.split()
    )


def _termo_principal(nome: str) -> str:
    """Chave do trecho antes de ":" ou "(" ("Balanced Scorecard (BSC): ..." →
    "balanced scorecard")."""
    corte = re.split(r"[:(]", nome, maxsplit=1)[0]
    return canonico.chave_regra(corte).chave


def _caminho_no(arv: ArvoreMestre, no_id: str) -> str:
    partes = []
    atual = resolver_no(arv, no_id)
    while atual and atual in arv.nos:
        no = arv.nos[atual]
        partes.append(no.nome)
        atual = resolver_no(arv, no.pai) if no.pai else ""
    return " › ".join(reversed(partes))


def _itens_aprovados_por_no(arv: ArvoreMestre) -> dict[str, int]:
    uso: dict[str, set[str]] = {}
    for item, maps in arv.mapeamentos.items():
        for m in maps:
            if m.status == "aprovado":
                uso.setdefault(resolver_no(arv, m.no_id), set()).add(item)
    return {k: len(v) for k, v in uso.items()}


_RANK_NIVEL = {"assunto": 0, "subassunto": 1}


def _escolher_destino(
    ids: list[str],
    arv: ArvoreMestre,
    questoes: dict[str, int],
    itens: dict[str, int],
) -> str:
    """Mais questões, depois mais itens de edital, depois nível mais alto
    (assunto > subassunto) e por fim o menor ID."""
    return min(
        ids,
        key=lambda i: (
            -questoes.get(i, 0),
            -itens.get(i, 0),
            _RANK_NIVEL.get(arv.nos[i].nivel, 9),
            i,
        ),
    )


def _operacoes_do_grupo(
    ids: list[str],
    arv: ArvoreMestre,
    questoes: dict[str, int],
    itens: dict[str, int],
) -> tuple[str, list[dict], list[str]]:
    """Destino sugerido do grupo, as fusões executáveis e os nós sem operação.

    Todo membro funde no destino do grupo (um conceito, um nó). Nó do mesmo
    nível funde sempre; nó de nível diferente só quando não tem filhos ativos
    (regra de `fundir_nos`, KAN-64). Nó de nível diferente com filhos fica em
    `sem_operacao`, para o dono decidir (mover os filhos antes, por exemplo).
    """
    destino = _escolher_destino(ids, arv, questoes, itens)
    nivel_destino = arv.nos[destino].nivel
    com_filhos = {
        resolver_no(arv, n.pai)
        for n in arv.nos.values()
        if n.status in ("ativo", "proposto") and n.pai
    }
    operacoes: list[dict] = []
    sem_operacao: list[str] = []
    for origem in sorted(ids):
        if origem == destino:
            continue
        if arv.nos[origem].nivel != nivel_destino and origem in com_filhos:
            sem_operacao.append(origem)
            continue
        operacoes.append({"origem": origem, "destino": destino})
    return destino, operacoes, sem_operacao


def detectar_dispersos(
    arv: ArvoreMestre, questoes_por_no: dict[str, int] | None = None
) -> list[dict]:
    """Conceitos ativos espalhados em pais diferentes (regra, sem LLM).

    `detectar_homonimos` só compara irmãos. Aqui o mesmo conceito sob pais
    diferentes (até em disciplinas diferentes) divide a incidência e o filtro.
    Motivos: `mesma_norma` (cita a mesma lei/LC/decreto/EC; confiança alta
    quando o nó é essencialmente a norma), `mesmo_nome` (mesma `chave_regra`,
    exceto genéricos; alta se o nome é específico) e `nome_contido` (o termo
    principal de um nó é o início do nome de outro; sempre média).

    `questoes_por_no` = questões distintas por `no_id` (já resolvido ou não);
    sem ele, só os itens de edital desempatam. Devolve grupos ordenados por
    nº de questões (desc) com: motivo, confianca, chave, nos, caminhos,
    questoes, itens, destino, operacoes ({origem, destino}) e sem_operacao.
    Não altera a árvore.
    """
    questoes: dict[str, int] = {}
    for no_id, q in (questoes_por_no or {}).items():
        alvo = resolver_no(arv, no_id)
        questoes[alvo] = questoes.get(alvo, 0) + q
    itens = _itens_aprovados_por_no(arv)

    ativos = [
        n for n in arv.nos.values() if n.status == "ativo" and n.nivel != "materia"
    ]
    pai_de = {n.id: resolver_no(arv, n.pai) for n in ativos if n.pai}

    grupos: list[dict] = []
    usados_alta: set[frozenset[str]] = set()

    def registrar(motivo: str, confianca: str, chave: str, ids: list[str]) -> None:
        ids = sorted(set(ids))
        if len({pai_de.get(i) for i in ids}) < 2:
            return
        destino, ops, sem_op = _operacoes_do_grupo(ids, arv, questoes, itens)
        grupos.append(
            {
                "motivo": motivo,
                "confianca": confianca,
                "chave": chave,
                "nos": ids,
                "caminhos": {i: _caminho_no(arv, i) for i in ids},
                "questoes": {i: questoes.get(i, 0) for i in ids},
                "itens": {i: itens.get(i, 0) for i in ids},
                "destino": destino,
                "operacoes": ops,
                "sem_operacao": sem_op,
            }
        )
        if confianca == "alta":
            usados_alta.add(frozenset(ids))

    # 1) mesma norma
    por_norma: dict[tuple[str, str], list[str]] = {}
    for n in ativos:
        for norma in _normas_do_nome(n.nome):
            por_norma.setdefault(norma, []).append(n.id)
    for norma, ids in sorted(por_norma.items()):
        essenciais = [i for i in ids if _nome_e_a_norma(arv.nos[i].nome)]
        chave = " ".join(norma)
        registrar("mesma_norma", "alta", chave, essenciais)
        resto = [i for i in ids if i not in essenciais]
        if resto and essenciais:
            registrar("mesma_norma", "media", chave, ids)

    # 2) mesmo nome (chave_regra), fora os genéricos
    por_nome: dict[str, list[str]] = {}
    for n in ativos:
        por_nome.setdefault(canonico.chave_regra(n.nome).chave, []).append(n.id)
    for chave, ids in sorted(por_nome.items()):
        if len(ids) < 2 or not chave or _nome_generico(arv.nos[ids[0]].nome):
            continue
        if any(_normas_do_nome(arv.nos[i].nome) for i in ids):
            continue  # já tratado como mesma_norma
        ramos = {_assinatura_ramo(arv, i) for i in ids}
        registrar("mesmo_nome", "alta" if len(ramos) == 1 else "media", chave, ids)

    # 3) nome contido: termo principal de um é o início do nome de outro
    chaves = {n.id: canonico.chave_regra(n.nome).chave for n in ativos}
    termos = {n.id: _termo_principal(n.nome) for n in ativos}
    for n in ativos:
        termo = termos[n.id]
        if not termo or _nome_generico(termo) or len(termo) < 10:
            continue
        outros = [
            o.id
            for o in ativos
            if o.id != n.id
            and pai_de.get(o.id) != pai_de.get(n.id)
            and chaves[o.id] != chaves[n.id]
            and (termos[o.id] == termo or chaves[o.id].startswith(termo + " "))
        ]
        if not outros:
            continue
        ids = [n.id, *outros]
        if any(set(ids) <= g for g in usados_alta):
            continue
        registrar("nome_contido", "media", termo, ids)

    # remove repetição: mesmo conjunto por motivos diferentes e nome_contido
    # cujo conjunto já está inteiro dentro de outro grupo
    vistos: set[tuple[str, str, frozenset[str]]] = set()
    unicos = []
    for g in sorted(grupos, key=lambda g: (g["confianca"] != "alta", -len(g["nos"]))):
        conjunto = frozenset(g["nos"])
        k = (g["motivo"], g["confianca"], conjunto)
        if k in vistos:
            continue
        if g["motivo"] == "nome_contido" and any(
            conjunto <= frozenset(o["nos"]) for o in unicos
        ):
            continue
        vistos.add(k)
        unicos.append(g)
    unicos.sort(key=lambda g: (-sum(g["questoes"].values()), g["chave"]))
    return unicos
