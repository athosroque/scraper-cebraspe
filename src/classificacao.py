"""Camada canônica de classificação de questões na árvore mestre (Etapa 5D, ADR-030).

Fonte da verdade versionada: `canonico/classificacao_questoes.json` (o banco Postgres é derivado).
A amarração usa chave natural estável (<concurso>|<codigo_caderno>|<numero> para objetivas e
<concurso>|<codigo_caderno>|D<numero> para discursivas), imune a recargas e deleções em `questoes`.

Cada registro contém:
- `chave`: chave natural estável;
- `hash_enunciado`: SHA-1 do enunciado limpo;
- `sem_no`: booleano indicando que a questão não possui nó adequado na árvore;
- `apontamentos`: lista de até 2 apontamentos (1 'principal' e opcionalmente 1 'secundario').
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from src import arvore

PROJETO_DIR = Path(__file__).resolve().parent.parent
CLASSIFICACAO_PADRAO = PROJETO_DIR / "canonico" / "classificacao_questoes.json"

PAPEIS_VALIDOS = ("principal", "secundario")
CONFIANCAS_VALIDAS = ("alta", "media", "baixa")
ORIGENS_VALIDAS = ("llm", "humano")
STATUS_VALIDOS = ("proposto", "aprovado", "rejeitado")


class ClassificacaoInvalida(ValueError):
    """Exceção levantada quando um registro de classificação viola regras de integridade."""


@dataclass
class ApontamentoQuestao:
    no_id: str
    papel: Literal["principal", "secundario"]
    confianca: Literal["alta", "media", "baixa"]
    fora_do_edital: bool = False
    origem: Literal["llm", "humano"] = "llm"
    status: Literal["proposto", "aprovado", "rejeitado"] = "proposto"


@dataclass
class RegistroQuestao:
    chave: str
    hash_enunciado: str
    sem_no: bool = False
    apontamentos: list[ApontamentoQuestao] = field(default_factory=list)


@dataclass
class ClassificacaoQuestoes:
    registros: dict[str, RegistroQuestao] = field(default_factory=dict)


def chave_questao(
    concurso: str,
    codigo_caderno: str,
    numero: int | str,
    discursiva: bool = False,
) -> str:
    """Gera a chave natural estável da questão ou discursiva."""
    num_str = str(numero).strip()
    if discursiva and not num_str.startswith("D"):
        num_str = f"D{num_str}"
    return f"{concurso.strip()}|{codigo_caderno.strip()}|{num_str}"


def calcular_hash_enunciado(enunciado: str) -> str:
    """Calcula o hash SHA-1 do enunciado limpo."""
    limpo = (enunciado or "").strip()
    return hashlib.sha1(limpo.encode("utf-8")).hexdigest()


def validar_registro(
    classificacao: ClassificacaoQuestoes,
    arv: arvore.ArvoreMestre,
    reg: RegistroQuestao,
) -> None:
    """Valida a integridade do registro contra a árvore mestre e regras de domínio."""
    if reg.sem_no:
        if reg.apontamentos:
            raise ClassificacaoInvalida(
                f"Registro {reg.chave} marcado como sem_no não pode ter apontamentos"
            )
        return

    if len(reg.apontamentos) > 2:
        raise ClassificacaoInvalida(
            f"Registro {reg.chave} possui {len(reg.apontamentos)} apontamentos (máximo permitido: 2)"
        )

    if not reg.apontamentos:
        return

    nos_vistos = set()
    papeis = []
    for idx, ap in enumerate(reg.apontamentos):
        if ap.papel not in PAPEIS_VALIDOS:
            raise ClassificacaoInvalida(
                f"Papel {ap.papel!r} inválido no apontamento {idx} da questão {reg.chave}"
            )
        if ap.confianca not in CONFIANCAS_VALIDAS:
            raise ClassificacaoInvalida(
                f"Confiança {ap.confianca!r} inválida no apontamento {idx} da questão {reg.chave}"
            )
        if ap.origem not in ORIGENS_VALIDAS:
            raise ClassificacaoInvalida(
                f"Origem {ap.origem!r} inválida no apontamento {idx} da questão {reg.chave}"
            )
        if ap.status not in STATUS_VALIDOS:
            raise ClassificacaoInvalida(
                f"Status {ap.status!r} inválido no apontamento {idx} da questão {reg.chave}"
            )

        no_efetivo = arvore.resolver_no(arv, ap.no_id)
        no = arv.nos.get(no_efetivo)
        if not no:
            raise ClassificacaoInvalida(
                f"Nó {ap.no_id} (resolvido: {no_efetivo}) não existe na árvore"
            )
        if no.status != "ativo":
            raise ClassificacaoInvalida(
                f"Nó {ap.no_id} (resolvido: {no_efetivo}) não está ativo (status: {no.status})"
            )

        if no_efetivo in nos_vistos:
            raise ClassificacaoInvalida(
                f"Nó duplicado {ap.no_id} (resolvido: {no_efetivo}) na questão {reg.chave}"
            )
        nos_vistos.add(no_efetivo)
        papeis.append(ap.papel)

    if len(papeis) == 1:
        if papeis[0] != "principal":
            raise ClassificacaoInvalida(
                f"Apontamento único da questão {reg.chave} deve ter papel 'principal', recebido {papeis[0]!r}"
            )
    elif len(papeis) == 2 and (papeis[0] != "principal" or papeis[1] != "secundario"):
        raise ClassificacaoInvalida(
            f"Dois apontamentos na questão {reg.chave} devem ser ('principal', 'secundario'), recebidos {tuple(papeis)}"
        )


def carregar(path: Path = CLASSIFICACAO_PADRAO) -> ClassificacaoQuestoes:
    """Carrega o arquivo canônico de classificação de questões."""
    if not path.exists():
        return ClassificacaoQuestoes()

    data = json.loads(path.read_text(encoding="utf-8"))
    cq = ClassificacaoQuestoes()
    for chave, r_data in data.get("registros", {}).items():
        apontamentos = [
            ApontamentoQuestao(
                no_id=a["no_id"],
                papel=a["papel"],
                confianca=a["confianca"],
                fora_do_edital=a.get("fora_do_edital", False),
                origem=a.get("origem", "llm"),
                status=a.get("status", "proposto"),
            )
            for a in r_data.get("apontamentos", [])
        ]
        cq.registros[chave] = RegistroQuestao(
            chave=chave,
            hash_enunciado=r_data.get("hash_enunciado", ""),
            sem_no=r_data.get("sem_no", False),
            apontamentos=apontamentos,
        )
    return cq


def salvar(
    classificacao: ClassificacaoQuestoes,
    path: Path = CLASSIFICACAO_PADRAO,
) -> None:
    """Salva o arquivo canônico ordenado por chave com 1 linha por registro."""
    path.parent.mkdir(parents=True, exist_ok=True)

    linhas = ["{", '  "registros": {']
    items = sorted(classificacao.registros.items())
    for i, (chave, reg) in enumerate(items):
        reg_dict = {
            "hash_enunciado": reg.hash_enunciado,
            "sem_no": reg.sem_no,
            "apontamentos": [asdict(a) for a in reg.apontamentos],
        }
        linha = f"    {json.dumps(chave)}: {json.dumps(reg_dict, ensure_ascii=False)}"
        if i < len(items) - 1:
            linha += ","
        linhas.append(linha)
    linhas.append("  }")
    linhas.append("}")

    path.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def mapear_questao(
    classificacao: ClassificacaoQuestoes,
    arv: arvore.ArvoreMestre,
    chave: str,
    hash_enunciado: str,
    nos: list[
        str
        | tuple[str, Literal["principal", "secundario"]]
        | tuple[str, Literal["principal", "secundario"], bool]
    ],
    confianca: Literal["alta", "media", "baixa"] = "alta",
    fora_do_edital: bool = False,
    origem: Literal["llm", "humano"] = "humano",
    status: Literal["proposto", "aprovado", "rejeitado"] = "aprovado",
) -> RegistroQuestao:
    """Mapeia uma questão a nós da árvore mestre e registra em `classificacao`.

    Cada item de `nos` é `no_id`, `(no_id, papel)` ou `(no_id, papel,
    fora_do_edital)`. O `fora_do_edital` é **por nó** (o principal pode estar
    no edital e o secundário fora); `fora_do_edital` do parâmetro é só o valor
    padrão dos itens que não trazem o seu.
    """
    if not nos:
        reg = RegistroQuestao(
            chave=chave,
            hash_enunciado=hash_enunciado,
            sem_no=True,
            apontamentos=[],
        )
        validar_registro(classificacao, arv, reg)
        classificacao.registros[chave] = reg
        return reg

    apontamentos: list[ApontamentoQuestao] = []
    for idx, item in enumerate(nos):
        fora_no = fora_do_edital
        if isinstance(item, (list, tuple)):
            if len(item) == 3:
                no_raw, papel, fora_no = item
            else:
                no_raw, papel = item
        else:
            no_raw = item
            papel = "principal" if idx == 0 else "secundario"

        no_efetivo = arvore.resolver_no(arv, no_raw)
        apontamentos.append(
            ApontamentoQuestao(
                no_id=no_efetivo,
                papel=papel,
                confianca=confianca,
                fora_do_edital=fora_no,
                origem=origem,
                status=status,
            )
        )

    reg = RegistroQuestao(
        chave=chave,
        hash_enunciado=hash_enunciado,
        sem_no=False,
        apontamentos=apontamentos,
    )
    validar_registro(classificacao, arv, reg)
    classificacao.registros[chave] = reg
    return reg


def aprovar_apontamento(
    classificacao: ClassificacaoQuestoes, chave: str, no_id: str
) -> None:
    """Aprova um apontamento específico de uma questão."""
    reg = classificacao.registros.get(chave)
    if not reg:
        raise ClassificacaoInvalida(f"Questão {chave} não encontrada")

    encontrado = False
    for ap in reg.apontamentos:
        if ap.no_id == no_id:
            ap.status = "aprovado"
            encontrado = True
            break

    if not encontrado:
        raise ClassificacaoInvalida(
            f"Apontamento para o nó {no_id} não encontrado na questão {chave}"
        )


def rejeitar_apontamento(
    classificacao: ClassificacaoQuestoes, chave: str, no_id: str
) -> None:
    """Rejeita um apontamento específico de uma questão."""
    reg = classificacao.registros.get(chave)
    if not reg:
        raise ClassificacaoInvalida(f"Questão {chave} não encontrada")

    encontrado = False
    for ap in reg.apontamentos:
        if ap.no_id == no_id:
            ap.status = "rejeitado"
            encontrado = True
            break

    if not encontrado:
        raise ClassificacaoInvalida(
            f"Apontamento para o nó {no_id} não encontrado na questão {chave}"
        )


def aprovar_lote(
    classificacao: ClassificacaoQuestoes,
    confianca: Literal["alta", "media", "baixa"] = "alta",
    caderno: str | None = None,
) -> int:
    """Aprova em lote todos os apontamentos propostos com a confiança indicada."""
    total = 0
    for chave, reg in classificacao.registros.items():
        if caderno is not None:
            partes = chave.split("|")
            caderno_bate = (
                len(partes) >= 2 and partes[1] == caderno
            ) or chave.startswith(f"{caderno}|")
            if not caderno_bate:
                continue

        for ap in reg.apontamentos:
            if ap.status == "proposto" and ap.confianca == confianca:
                ap.status = "aprovado"
                total += 1

    return total
