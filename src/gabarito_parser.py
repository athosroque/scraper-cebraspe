"""Leitura determinística dos PDFs de gabarito do CEBRASPE (Etapa 5C, ADR-031).

Três tipos de documento chegam na pasta `Gabaritos/` (ou como "padrão de
resposta" em `Provas/`):

- **grade definitiva** (`Gab_Definitivo_<caderno>.pdf` ou nome em hash):
  linhas `Item 1 2 ... 20` seguidas de `Gabarito C E ... X`, com `0` de
  enchimento nas células vazias. A grade é lida **por posição** (palavras do
  PyMuPDF agrupadas em linhas e casadas por coluna), não pela ordem do texto
  corrido — no texto corrido os números e as letras saem em blocos separados
  e o enchimento `0` se mistura aos dois.
- **padrão de resposta** da discursiva: texto livre, guardado inteiro e
  dividido por questão (`Prova Discursiva – Questão N` / `Peça ...`) quando o
  caderno tem mais de uma.
- **justificativas de alteração de gabarito**: documento do concurso inteiro,
  sem caderno. Não é gabarito de nenhum caderno; é reconhecido para não contar
  como "gabarito sem prova".

O código do caderno (`094_PF_CB1_01`, `167_CDNS_002_01`) é lido do
**conteúdo** do PDF: é o que liga os gabaritos com nome em hash (CD/TCU) ao
caderno.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from src.comparacao_texto import extrair_cargos_do_texto
from src.edital_parser import extrair_texto_paginas

# 094_PF_CB1_01, 072_STM_CG2_01, 167_CDNS_002_01, 108_TCUTEFC_001_01 e, com
# sublinhado na sigla do concurso, 169_SEBRAE_26_PSE_1_CG1_02 (SEBRAE 2026) e
# 053_SEBRAE_PSE_CG1_02. A sigla aceita até 4 segmentos extras `_XXX`; como o
# código termina em fronteira de palavra, um código sem sublinhado na sigla
# continua casando igual (mesmo trecho, mesmo token).
PADRAO_CODIGO_CADERNO = re.compile(
    r"\b(\d{3})_([A-Z0-9]+(?:_[A-Z0-9]+){0,4})_(C[BG]\d+|\d{3})_(\d{2})\b"
)
PADRAO_JUSTIFICATIVA = re.compile(r"justificativas?\s+de\s+altera", re.IGNORECASE)
PADRAO_PADRAO_RESPOSTA = re.compile(r"PADR[ÃA]O\s+DE\s+RESPOSTA", re.IGNORECASE)

QUESTAO_CERTO_ERRADO = "certo_errado"
QUESTAO_MULTIPLA_ESCOLHA = "multipla_escolha"
GRADE_MISTA = "misto"
# O rótulo da linha de números diz o tipo da questão: conferido nas 42 grades
# do piloto (todas `Item`, só C/E/X) e nas 3 grades ME da amostra da 8.0
# (BANRISUL_25, SEBRAE_26, SEFA_PR_25: todas `Questão`, A–E/X). Validar a letra
# pelo tipo impede que uma letra espúria numa grade C/E passe calada.
TIPO_POR_ROTULO = {
    "Item": QUESTAO_CERTO_ERRADO,
    "Questão": QUESTAO_MULTIPLA_ESCOLHA,
    "Questao": QUESTAO_MULTIPLA_ESCOLHA,
}
LETRAS_POR_TIPO = {
    QUESTAO_CERTO_ERRADO: frozenset({"C", "E", "X"}),
    QUESTAO_MULTIPLA_ESCOLHA: frozenset({"A", "B", "C", "D", "E", "X"}),
}
LETRAS_VALIDAS = set().union(*LETRAS_POR_TIPO.values())

# Cabeçalho de cada questão no padrão de resposta de caderno com várias:
# "Prova Discursiva – Questão 1 – Conhecimentos Básicos", "Prova Discursiva –
# Peça de natureza técnica". Caderno de questão única traz só "Prova Discursiva".
PADRAO_CABECALHO_PADRAO_RESPOSTA = re.compile(
    r"^\s*Prova\s+Discursiva\b[^\n]*$", re.IGNORECASE | re.MULTILINE
)
# Cabeçalho institucional do topo da página seguinte que fica anexado ao fim
# da seção (CD e TCU): a marca é uma linha inteira em caixa alta, seguida só de
# linhas de cabeçalho ("CARGO 2: ...", "ESPECIALIDADE: ...", "CÓDIGO: ...").
# Sem IGNORECASE: "Câmara dos Deputados aprovou..." no corpo não é marca.
PADRAO_INSTITUCIONAL_FIM = re.compile(
    r"^\s*(?:CÂMARA DOS DEPUTADOS|TRIBUNAL DE CONTAS DA UNIÃO)\s*$",
    re.MULTILINE,
)
MAX_LINHAS_CABECALHO_INSTITUCIONAL = 6

TIPO_GRADE = "grade"
TIPO_PADRAO_RESPOSTA = "padrao_resposta"
TIPO_JUSTIFICATIVA = "justificativa"
TIPO_DESCONHECIDO = "desconhecido"

VERSAO_DEFINITIVO = "definitivo"
VERSAO_PRELIMINAR = "preliminar"


@dataclass
class GradeGabarito:
    """Grade definitiva de um caderno objetivo.

    `tipos` guarda o tipo de cada número, lido do rótulo da linha da grade
    (`Item` → C/E, `Questão` → ME). `tipo_detectado` sai dele: um tipo só,
    esse tipo; os dois na mesma grade, `GRADE_MISTA`. Sem `tipos` (grade
    montada à mão, fora de `ler_grade`), cai na regra antiga pelas letras.
    """

    codigo_caderno: str | None
    respostas: dict[int, str] = field(default_factory=dict)
    cabecalho: str | None = None
    alertas: list[str] = field(default_factory=list)
    tipo_detectado: str | None = None
    tipos: dict[int, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tipo_detectado is not None:
            return
        presentes = set(self.tipos.values())
        if len(presentes) == 1:
            self.tipo_detectado = presentes.pop()
        elif presentes:
            self.tipo_detectado = GRADE_MISTA
        elif any(letra in {"A", "B", "D"} for letra in self.respostas.values()):
            self.tipo_detectado = QUESTAO_MULTIPLA_ESCOLHA
        else:
            self.tipo_detectado = QUESTAO_CERTO_ERRADO

    @property
    def numeros(self) -> list[int]:
        return sorted(self.respostas)

    @property
    def anulados(self) -> list[int]:
        return [n for n, letra in sorted(self.respostas.items()) if letra == "X"]


@dataclass
class PadraoResposta:
    texto: str
    # Uma entrada por questão, na ordem do documento: {"titulo", "texto"}.
    secoes: list[dict] = field(default_factory=list)
    cargos_numeros: list[int] = field(default_factory=list)


def codigo_caderno_do_texto(texto: str) -> str | None:
    m = PADRAO_CODIGO_CADERNO.search(texto or "")
    return m.group(0) if m else None


def token_caderno(codigo: str | None) -> str | None:
    """`094_PF_CB1_01` -> `CB1`; `167_CDNS_002_01` -> `002`;
    `169_SEBRAE_26_PSE_1_CG1_02` -> `CG1`."""
    m = PADRAO_CODIGO_CADERNO.fullmatch(codigo or "")
    return m.group(3) if m else None


def classificar_documento(texto: str) -> str:
    """Tipo do PDF de gabarito a partir do texto (primeira página basta)."""
    if PADRAO_JUSTIFICATIVA.search(texto):
        return TIPO_JUSTIFICATIVA
    if PADRAO_PADRAO_RESPOSTA.search(texto):
        return TIPO_PADRAO_RESPOSTA
    if re.search(r"GABARITOS?\s+OFICIA", texto, re.IGNORECASE) and re.search(
        r"^\s*(?:Item|Quest[ãa]o)\b", texto, re.MULTILINE
    ):
        return TIPO_GRADE
    return TIPO_DESCONHECIDO


def _linhas_de_palavras(page, tolerancia: float = 3.0) -> list[list[tuple]]:
    """Palavras da página agrupadas em linhas visuais (mesmo centro vertical,
    com tolerância), cada linha ordenada por x."""
    palavras = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    linhas: list[list[tuple]] = []
    centro_atual = None
    for w in palavras:
        centro = (w[1] + w[3]) / 2
        if centro_atual is None or abs(centro - centro_atual) > tolerancia:
            linhas.append([])
            centro_atual = centro
        linhas[-1].append(w)
    return [sorted(linha, key=lambda w: w[0]) for linha in linhas]


def _centro_x(w) -> float:
    return (w[0] + w[2]) / 2


def ler_grade_de_linhas(linhas: list[list[tuple]]) -> tuple[dict[int, str], list[str]]:
    """`(respostas, alertas)` de `ler_grade_tipada_de_linhas`, sem os tipos."""
    respostas, _tipos, alertas = ler_grade_tipada_de_linhas(linhas)
    return respostas, alertas


def ler_grade_tipada_de_linhas(
    linhas: list[list[tuple]],
) -> tuple[dict[int, str], dict[int, str], list[str]]:
    """Casa cada linha `Item ...` ou `Questão ...` com a linha `Gabarito ...`
    logo abaixo, por coluna (centro x mais próximo). Descarta o enchimento `0`.

    Devolve `(respostas, tipos, alertas)`. O tipo de cada número vem do rótulo
    da linha (`TIPO_POR_ROTULO`), e a letra é validada contra o tipo
    (`LETRAS_POR_TIPO`): `A` numa linha `Item` vira alerta, não resposta.

    Função pura sobre as linhas de palavras (tuplas no formato do
    `page.get_text("words")`) para poder ser testada sem PDF.
    """
    respostas: dict[int, str] = {}
    tipos: dict[int, str] = {}
    alertas: list[str] = []
    for i, linha in enumerate(linhas):
        tipo = TIPO_POR_ROTULO.get(linha[0][4]) if linha else None
        if tipo is None:
            continue
        numeros = [w for w in linha[1:] if w[4].isdigit() and w[4] != "0"]
        if not numeros:
            continue
        letras_linha = next(
            (
                outra
                for outra in linhas[i + 1 : i + 3]
                if outra and outra[0][4] == "Gabarito"
            ),
            None,
        )
        if letras_linha is None:
            alertas.append(
                f"linha de itens {numeros[0][4]}..{numeros[-1][4]} sem linha de gabarito abaixo"
            )
            continue
        letras = [w for w in letras_linha[1:] if w[4] != "0"]
        for w in numeros:
            numero = int(w[4])
            letra = min(
                letras, key=lambda c: abs(_centro_x(c) - _centro_x(w)), default=None
            )
            if letra is None or abs(_centro_x(letra) - _centro_x(w)) > 8:
                alertas.append(f"item {numero} sem letra na mesma coluna")
                continue
            if letra[4] not in LETRAS_POR_TIPO[tipo]:
                alertas.append(f"item {numero} com gabarito inválido {letra[4]!r}")
                continue
            if numero in respostas:
                alertas.append(f"item {numero} repetido na grade")
            respostas[numero] = letra[4]
            tipos[numero] = tipo
    return respostas, tipos, alertas


def classificar_versao(texto: str, nome_arquivo: str = "") -> str | None:
    """Classifica a versão do gabarito (definitivo ou preliminar).

    Examina exclusivamente o cabeçalho/primeira página com regexes estritas
    para evitar falsos positivos no corpo de padrões de resposta.
    Se não encontrar no texto, verifica o nome do arquivo.
    """
    m = (
        re.search(
            r"GABARITOS?\s+OFICIA\w*\s+(DEFINITIV|PRELIMINAR)",
            (texto or "")[:2000],
            re.IGNORECASE,
        )
        or re.search(
            r"PADR[ÃA]O\s+(?:DE\s+RESPOSTAS?\s+)?(DEFINITIV|PRELIMINAR)",
            (texto or "")[:600],
            re.IGNORECASE,
        )
        or re.search(
            r"PADR[ÃA]O\s+(DEFINITIV|PRELIMINAR)\w*\s+DE\s+RESPOSTA",
            (texto or "")[:600],
            re.IGNORECASE,
        )
    )
    if m:
        grupo = m.group(1).upper()
        if grupo.startswith("DEFINITIV"):
            return VERSAO_DEFINITIVO
        if grupo.startswith("PRELIMINAR"):
            return VERSAO_PRELIMINAR

    if nome_arquivo:
        if re.search(r"Gab_Definitivo_", nome_arquivo, re.IGNORECASE):
            return VERSAO_DEFINITIVO
        if re.search(r"Gab_Preliminar_", nome_arquivo, re.IGNORECASE):
            return VERSAO_PRELIMINAR

    return None


def _ler_grade_doc(doc: pymupdf.Document) -> GradeGabarito:
    respostas: dict[int, str] = {}
    tipos: dict[int, str] = {}
    alertas: list[str] = []
    texto = ""
    for page in doc:
        texto += page.get_text().replace("\xa0", " ") + "\n"
        r, t, a = ler_grade_tipada_de_linhas(_linhas_de_palavras(page))
        respostas.update(r)
        tipos.update(t)
        alertas.extend(a)
    cabecalho = None
    m = re.search(
        r"^\s*((?:CARGO\s+\d+|CONHECIMENTOS\s+(?:BÁSICOS|GERAIS|ESPECÍFICOS))[^\n]*)$",
        texto,
        re.MULTILINE,
    )
    if m:
        cabecalho = re.sub(r"\s+", " ", m.group(1)).strip()
    numeros = sorted(respostas)
    if numeros and numeros != list(range(numeros[0], numeros[-1] + 1)):
        faltando = sorted(set(range(numeros[0], numeros[-1] + 1)) - set(numeros))
        alertas.append(f"grade com buraco na numeração: {faltando}")
    if len(set(tipos.values())) > 1:
        alertas.append(
            "grade com linhas `Item` e `Questão` misturadas: "
            f"{sorted(set(tipos.values()))}"
        )
    return GradeGabarito(
        codigo_caderno=codigo_caderno_do_texto(texto),
        respostas=respostas,
        cabecalho=cabecalho,
        alertas=alertas,
        tipos=tipos,
    )


def ler_grade(pdf_path: Path) -> GradeGabarito:
    with pymupdf.open(pdf_path) as doc:
        return _ler_grade_doc(doc)


def _remover_rodape_paginas(paginas: list[str], n_linhas: int = 5) -> list[str]:
    """Remove linhas de rodapé que se repetem em >= 2 páginas nas últimas N linhas
    de cada página (rodapé genérico). Se documento tiver 1 página, remove rodapé
    conhecido via regex específica."""
    if not paginas:
        return paginas

    if len(paginas) >= 2:
        candidatos_por_pagina: list[set[str]] = []
        for pag in paginas:
            linhas = [l.strip() for l in pag.splitlines() if l.strip()]
            candidatos_por_pagina.append(set(linhas[-n_linhas:]))

        contagem: dict[str, int] = {}
        for s in candidatos_por_pagina:
            for l in s:
                contagem[l] = contagem.get(l, 0) + 1

        linhas_rodape = {l for l, c in contagem.items() if c >= 2}

        if linhas_rodape:
            paginas_limpas = []
            for pag in paginas:
                linhas = pag.splitlines()
                while linhas and (
                    linhas[-1].strip() in linhas_rodape or not linhas[-1].strip()
                ):
                    linhas.pop()
                paginas_limpas.append("\n".join(linhas))
            return paginas_limpas

    elif len(paginas) == 1:
        texto = paginas[0]
        linhas = texto.splitlines()
        padrao = re.compile(r"^\s*CÂMARA DOS DEPUTADOS\s*\|.*$", re.IGNORECASE)
        modificado = False
        while linhas and (padrao.match(linhas[-1].strip()) or not linhas[-1].strip()):
            if padrao.match(linhas[-1].strip()):
                modificado = True
                linhas.pop()
            elif modificado:
                linhas.pop()
            else:
                break
        return ["\n".join(linhas)]

    return paginas


def _remover_cabecalho_institucional_fim(trecho: str) -> str:
    """Corta o trecho a partir da última linha-marca institucional, só se
    todas as linhas não vazias depois dela forem de cabeçalho (no máximo
    `MAX_LINHAS_CABECALHO_INSTITUCIONAL`, nenhuma com minúscula). Senão,
    devolve o trecho intacto: na dúvida, não corta conteúdo."""
    marcas = list(PADRAO_INSTITUCIONAL_FIM.finditer(trecho))
    if not marcas:
        return trecho
    ultima = marcas[-1]
    seguintes = [
        linha.strip() for linha in trecho[ultima.end() :].split("\n") if linha.strip()
    ]
    if len(seguintes) > MAX_LINHAS_CABECALHO_INSTITUCIONAL or any(
        linha != linha.upper() for linha in seguintes
    ):
        return trecho
    return trecho[: ultima.start()]


def dividir_padrao_resposta(texto: str) -> list[dict]:
    """Uma seção por cabeçalho `Prova Discursiva ...`. Sem cabeçalho, uma
    seção só com o texto inteiro. Remove blocos institucionais do topo da
    página seguinte anexados ao fim de cada seção."""
    marcas = list(PADRAO_CABECALHO_PADRAO_RESPOSTA.finditer(texto))
    if not marcas:
        return [
            {
                "titulo": None,
                "texto": _remover_cabecalho_institucional_fim(texto).strip(),
            }
        ]
    secoes = []
    for i, m in enumerate(marcas):
        fim = marcas[i + 1].start() if i + 1 < len(marcas) else len(texto)
        trecho = texto[m.start() : fim].strip()
        trecho_limpo = _remover_cabecalho_institucional_fim(trecho).strip()
        secoes.append(
            {
                "titulo": re.sub(r"\s+", " ", m.group(0)).strip(),
                "texto": trecho_limpo,
            }
        )
    return secoes


def _padrao_de_paginas(paginas: list[str]) -> PadraoResposta:
    paginas_limpas = _remover_rodape_paginas(paginas)
    texto = "\n".join(paginas_limpas)
    cabecalho = texto[:600]
    return PadraoResposta(
        texto=texto.strip(),
        secoes=dividir_padrao_resposta(texto),
        cargos_numeros=extrair_cargos_do_texto(cabecalho),
    )


def ler_padrao_resposta(pdf_path: Path) -> PadraoResposta:
    paginas = extrair_texto_paginas(pdf_path)
    return _padrao_de_paginas(paginas)


def ler_documento(pdf_path: Path) -> dict:
    """Lê qualquer PDF da categoria gabarito e devolve
    `{"tipo", "codigo_caderno", "grade" | "padrao_resposta" | None, "versao"}`."""
    with pymupdf.open(pdf_path) as doc:
        paginas = [page.get_text().replace("\xa0", " ") for page in doc]
        texto = "\n".join(paginas)
        tipo = classificar_documento(paginas[0] if paginas else "")
        grade = None
        padrao_resposta = None
        versao = None
        if tipo == TIPO_GRADE:
            grade = _ler_grade_doc(doc)
            versao = classificar_versao(texto[:2000], pdf_path.name)
        elif tipo == TIPO_PADRAO_RESPOSTA:
            padrao_resposta = _padrao_de_paginas(paginas)
            versao = classificar_versao(texto[:600], pdf_path.name)
        return {
            "tipo": tipo,
            "codigo_caderno": codigo_caderno_do_texto(texto),
            "grade": grade,
            "padrao_resposta": padrao_resposta,
            "versao": versao,
        }
