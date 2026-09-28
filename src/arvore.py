import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

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
    status: Literal["ativo", "proposto", "fundido"]
    fundido_em: str | None = None


@dataclass
class Mapeamento:
    no_id: str
    origem: Literal["semente", "regra", "llm", "humano"]
    status: Literal["proposto", "aprovado", "rejeitado"]


@dataclass
class ArvoreMestre:
    nos: dict[str, NoArvore] = field(default_factory=dict)
    mapeamentos: dict[str, list[Mapeamento]] = field(default_factory=dict)


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

    novo_pai = resolver_no(arvore, novo_pai)
    pai_no = arvore.nos.get(novo_pai)
    if not pai_no:
        raise ArvoreInvalida(f"Novo pai {novo_pai} não existe")
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

    no_orig.status = "fundido"
    no_orig.fundido_em = destino_id

    # Atualizar pais que apontam para o nó fundido
    for no in arvore.nos.values():
        if no.pai == origem_id:
            no.pai = destino_id


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

    linhas.append(" }")
    linhas.append("}")

    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")
