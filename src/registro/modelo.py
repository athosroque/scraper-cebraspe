"""Modelo do registro do pipeline (Etapa 9/D2, KAN-69).

O registro é a fonte única de scripts, etapas, checagens e regras do projeto.
As páginas de `docs/tecnico/` são geradas dele (`scripts/gerar_docs.py`) e o
Dagster (D5a) monta os assets a partir das etapas. Os valores ficam nos módulos
irmãos (`scripts.py`, `etapas.py`, `checagens.py`, `regras_*.py`); este módulo
só define a forma e valida o que é verificável sem olhar o disco. As checagens
que olham o disco (ADR e teste existem, script registrado) ficam no teste guarda
`tests/test_registro.py`.
"""

import re
from dataclasses import dataclass
from typing import Literal

CATEGORIAS_SCRIPT = (
    "pipeline",
    "curadoria",
    "relatorio",
    "manutencao",
    "experimento",
    "obsoleto",
)
CLIS = ("argparse", "argv", "nenhum")
CAMADAS_CHECAGEM = (
    "download",
    "edital",
    "prova",
    "banco",
    "classificacao",
    "arvore",
    "site",
    "piloto",
)
ONDES_CHECAGEM = ("banco", "teste", "comando")
TIPOS_REGRA = ("pattern", "anti-pattern")
AREAS_REGRA = (
    "coleta",
    "edital",
    "prova",
    "llm",
    "banco",
    "arvore",
    "classificacao",
    "site",
    "revisao",
    "testes",
    "infra",
    "processo",
)

_ADR = re.compile(r"^ADR-\d{3}$")
_TESTE = re.compile(r"^(site/)?tests/[\w/]+\.py(::[\w\[\]\-.]+)*$")


class RegistroInvalido(ValueError):
    pass


def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise RegistroInvalido(mensagem)


def _validar_adrs(dono: str, adrs: tuple[str, ...]) -> None:
    for adr in adrs:
        _exigir(bool(_ADR.match(adr)), f"{dono}: ADR mal escrito {adr!r} (ADR-NNN)")


@dataclass(frozen=True)
class Script:
    """Um ponto de entrada `python -m <modulo>` do projeto."""

    modulo: str  # "scripts.curar_arvore", "src.spider"
    resumo: str
    categoria: Literal[
        "pipeline", "curadoria", "relatorio", "manutencao", "experimento", "obsoleto"
    ]
    cli: Literal["argparse", "argv", "nenhum"]
    uso_argv: str = ""  # obrigatório quando cli == "argv"
    adrs: tuple[str, ...] = ()

    def __post_init__(self):
        _exigir(self.modulo.startswith(("scripts.", "src.")), f"{self.modulo}: módulo")
        _exigir(self.categoria in CATEGORIAS_SCRIPT, f"{self.modulo}: categoria")
        _exigir(self.cli in CLIS, f"{self.modulo}: cli")
        _exigir(
            self.cli != "argv" or bool(self.uso_argv),
            f"{self.modulo}: cli argv exige uso_argv",
        )
        _validar_adrs(self.modulo, self.adrs)


@dataclass(frozen=True)
class Etapa:
    """Um passo do pipeline. `depois_de` liga as etapas num grafo sem ciclo."""

    id: str  # "P1", "C1b", ...
    nome: str
    comandos: tuple[str, ...]
    scripts: tuple[str, ...]  # módulos de `Script`
    entradas: tuple[str, ...]
    saidas: tuple[str, ...]
    depois_de: tuple[str, ...] = ()
    llm: str | None = None  # chave/modelo usado; None = sem LLM
    portao_humano: str | None = None  # o que o dono aprova antes da próxima
    adrs: tuple[str, ...] = ()
    notas: str = ""

    def __post_init__(self):
        _exigir(bool(re.match(r"^[A-Z][A-Za-z0-9.]*$", self.id)), f"etapa {self.id}")
        _exigir(self.id not in self.depois_de, f"etapa {self.id} depende de si")
        _validar_adrs(f"etapa {self.id}", self.adrs)


@dataclass(frozen=True)
class Checagem:
    """Uma validação e onde consultar o resultado dela."""

    id: str  # "K01", ...
    camada: str
    descricao: str
    onde: Literal["banco", "teste", "comando"]
    consulta: str = ""  # SQL só leitura, quando onde == "banco"
    teste: str = ""  # nodeid do pytest, quando onde == "teste"
    comando: str = ""  # CLI que imprime o resultado, quando onde == "comando"
    bloqueante: bool = True
    adrs: tuple[str, ...] = ()

    def __post_init__(self):
        _exigir(bool(re.match(r"^K\d{2}$", self.id)), f"checagem {self.id}")
        _exigir(self.camada in CAMADAS_CHECAGEM, f"checagem {self.id}: camada")
        _exigir(self.onde in ONDES_CHECAGEM, f"checagem {self.id}: onde")
        exigido = {"banco": self.consulta, "teste": self.teste, "comando": self.comando}
        _exigir(bool(exigido[self.onde]), f"checagem {self.id}: falta {self.onde}")
        if self.teste:
            _exigir(bool(_TESTE.match(self.teste)), f"checagem {self.id}: teste")
        _validar_adrs(f"checagem {self.id}", self.adrs)


@dataclass(frozen=True)
class Regra:
    """Um pattern ou anti-pattern do projeto. O registro é a fonte do texto (D3);
    o `CLAUDE.md` só cita, em uma linha, as regras do núcleo (`nucleo=True`)."""

    id: str  # "P01" (§6) ou "A01" (§7)
    tipo: Literal["pattern", "anti-pattern"]
    area: str
    texto: str
    adrs: tuple[str, ...] = ()
    testes: tuple[str, ...] = ()  # arquivo ou nodeid do pytest
    nucleo: bool = False  # quebra dado se esquecida; citada no §6/§7 do CLAUDE.md

    def __post_init__(self):
        prefixo = "P" if self.tipo == "pattern" else "A"
        _exigir(self.tipo in TIPOS_REGRA, f"regra {self.id}: tipo")
        _exigir(
            bool(re.match(rf"^{prefixo}\d{{2,3}}$", self.id)), f"regra {self.id}: id"
        )
        _exigir(self.area in AREAS_REGRA, f"regra {self.id}: área {self.area!r}")
        _exigir(bool(self.texto.strip()), f"regra {self.id}: texto vazio")
        _validar_adrs(f"regra {self.id}", self.adrs)
        for teste in self.testes:
            _exigir(bool(_TESTE.match(teste)), f"regra {self.id}: teste {teste!r}")


@dataclass(frozen=True)
class Tarefa:
    """Uma tarefa de agente e o que ler para ela (`docs/tecnico/tarefas.md`, D3).

    O vínculo com as regras é pela área: regra nova da área cai na tarefa sozinha.
    """

    id: str  # "T01"
    nome: str
    quando: str  # uma frase: quando o agente está nesta tarefa
    leia: tuple[str, ...]  # páginas de docs/ (relativas a docs/), em ordem de leitura
    areas: tuple[str, ...]  # AREAS_REGRA
    regras: tuple[str, ...] = ()  # regras extras, de outras áreas
    etapas: tuple[str, ...] = ()  # ids de Etapa
    scripts: tuple[str, ...] = ()  # módulos de Script
    checagens: tuple[str, ...] = ()  # ids de Checagem
    adrs: tuple[str, ...] = ()

    def __post_init__(self):
        _exigir(bool(re.match(r"^T\d{2}$", self.id)), f"tarefa {self.id}")
        _exigir(bool(self.leia), f"tarefa {self.id}: leia vazio")
        for area in self.areas:
            _exigir(area in AREAS_REGRA, f"tarefa {self.id}: área {area!r}")
        for regra in self.regras:
            _exigir(
                bool(re.match(r"^[PA]\d{2,3}$", regra)), f"tarefa {self.id}: {regra}"
            )
        for checagem in self.checagens:
            _exigir(
                bool(re.match(r"^K\d{2}$", checagem)), f"tarefa {self.id}: {checagem}"
            )
        _validar_adrs(f"tarefa {self.id}", self.adrs)


@dataclass(frozen=True)
class Registro:
    scripts: tuple[Script, ...] = ()
    etapas: tuple[Etapa, ...] = ()
    checagens: tuple[Checagem, ...] = ()
    regras: tuple[Regra, ...] = ()
    tarefas: tuple[Tarefa, ...] = ()
