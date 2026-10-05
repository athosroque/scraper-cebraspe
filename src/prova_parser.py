"""Extração determinística de questões dos cadernos do CEBRASPE (Etapa 5C, ADR-031).

Sem LLM. Dois formatos:

**Caderno objetivo (Certo/Errado).** A lista de itens esperados vem do
gabarito (verdade de referência). O corte é feito sobre as **linhas** do
PyMuPDF (com posição e fonte), não sobre o texto corrido:

- marcador de item: linha que começa com o próximo número esperado **num span
  próprio** (o CEBRASPE compõe o número numa fonte/tamanho diferentes do
  corpo). Número no começo de linha de texto comum ("55 metros.") não conta;
  só entra como fallback, entre dois vizinhos já achados;
- continuação do item: recuo deslocado do número (a margem do texto do item
  fica ~18 pt à direita do número, em qualquer coluna/página);
- o que sobra entre um item e o próximo sem esse recuo é o **preâmbulo** do
  grupo seguinte, desde que traga um comando ("julgue ..."). O comando é o
  rótulo de seção (pista para a classificação da Etapa 5D); o que vem antes
  dele é o **texto-base** compartilhado pelos itens do grupo;
- figuras: imagens raster da página (tiras vizinhas unidas), renderizadas em
  PNG e ligadas ao trecho (item, texto-base) cuja linha está logo acima na
  mesma coluna.

**Caderno discursivo.** Uma ou mais questões ("Questão N", "Peça de natureza
técnica"), cada uma com enunciado, tema e quesitos (`N texto [valor: X
pontos]`). O padrão de resposta (outro PDF) é ligado depois, por questão.

Nada é descartado em silêncio: divergência entre itens extraídos e itens do
gabarito vira `status` de falha no caderno, e trecho que não se encaixa vira
alerta com o texto na auditoria.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from src.edital_parser import extrair_texto_paginas
from src.logger import logger

STATUS_SUCESSO = "sucesso"
STATUS_FALHA_ITENS_DIVERGENTES = "falha_itens_divergentes"
STATUS_FALHA_SEM_GABARITO = "falha_sem_gabarito"
STATUS_FALHA_SEM_QUESTAO = "falha_sem_questao"

SEVERIDADE_BLOQUEANTE = "bloqueante"
SEVERIDADE_INFORMATIVO = "informativo"

PADRAO_CABECALHO = re.compile(r"^\s*CEBRASPE\s*[–-].*Edital", re.IGNORECASE)
PADRAO_FAIXA_SECAO = re.compile(r"^\s*--")  # "-- CONHECIMENTOS BÁSICOS --"
PADRAO_RUIDO = re.compile(
    r"^\s*(?:Espaço livre|PROVAS? OBJETIVAS?|RASCUNHO)\s*$", re.IGNORECASE
)
# "julgue os itens", "assertiva a ser julgada" e, nos textos em inglês, "judge".
PADRAO_COMANDO_OBJETIVO = re.compile(
    r"\bjulgue\b|\bjulgad[ao]s?\b|\bjudge\b", re.IGNORECASE
)
# Comando sem texto-base próprio que se refere ao texto do grupo anterior.
# "texto precedente", "tabela anterior", "texto CG4A1", "proposição P
# apresentada" — e não "é apresentada uma situação hipotética" (cada item
# traz a sua).
PADRAO_COMANDO_REFERE_TEXTO = re.compile(
    r"\b(?:textos?|fragmentos?|tabelas?|quadros?|dados|informa[çc](?:ão|ões)|proposi[çc](?:ão|ões)"
    r"|situa[çc](?:ão|ões)(?: hipot[ée]ticas?)?|casos?|c[óo]digos?|modelos?|planilhas?|gr[áa]ficos?"
    r"|figuras?|cen[áa]rios?)"
    r"\s+(?:[^,.;]{0,40}?\s)?(?:precedentes?|anterior(?:es)?|apresentad[ao]s?|acima)\b"
    r"|\btextos?\s+[A-Z]{1,3}\d?[A-Z]\d",
    re.IGNORECASE,
)
# Item que anuncia material logo depois dele ("O fragmento de texto a seguir
# ...", "... os seguintes eventos:"): o trecho sem recuo entre ele e o
# comando seguinte é dele, não texto-base do próximo grupo.
PADRAO_ITEM_ANUNCIA = re.compile(r"\ba seguir\b|:\s*$", re.IGNORECASE)
# Referência a uma figura do caderno ("figura a seguir", "gráfico
# precedente", "figura A"), não o sentido figurado ("figura do monarca",
# "imagem institucional").
PADRAO_MENCIONA_FIGURA = re.compile(
    r"\b[Ff]iguras?\s+(?:[A-Z]\b|a seguir|precedente|anterior|acima|apresentad|mostrad|ilustrad)"
    r"|\b(?:[Gg]r[áa]fico|[Dd]iagrama|[Ii]magem)\s+(?:a seguir|precedente|anterior|acima|apresentad|mostrad)"
)
# Fim do texto-base antes do comando. Sem ")" nem aspas: "(Lei n.º
# 8.112/1990)" e "(CG1A1)" aparecem no meio do comando.
TERMINAIS_COMANDO = (".", "!", "?", ":")
MAX_LINHAS_COMANDO = 8
# Fim de frase (com aspas/parêntese de fechamento opcionais) seguido de frase
# nova: `debater.” Com base na proposição P ...`.
PADRAO_FRONTEIRA_FRASE = re.compile(r"([.!?][”\"’»)]*)\s+(?=[A-ZÀ-Ú])")
TERMINAIS_FRASE = (".", ":", "!", "?", ")", "”", '"')

PADRAO_CONTROLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
SIMBOLO_ILEGIVEL = "\ufffd"
# Fonte Symbol sem mapa Unicode sai na \u00e1rea de uso privado (0xF000 + c\u00f3digo
# Symbol): `len(lista) \uf02d 1` (`094_PF_005_01`, item 110), `185 mmHg \uf0b4
# 146 mmHg` (`094_PF_007_01`). Menos vira `-` ASCII para o c\u00f3digo continuar
# v\u00e1lido. C\u00f3digo fora da tabela fica como veio.
SIMBOLO_PUA = str.maketrans(
    {
        "\uf02b": "+",
        "\uf02d": "-",
        "\uf03c": "<",
        "\uf03d": "=",
        "\uf03e": ">",
        "\uf0a3": "\u2264",
        "\uf0a5": "\u221e",
        "\uf0ae": "\u2192",
        "\uf0b1": "\u00b1",
        "\uf0b3": "\u2265",
        "\uf0b4": "\u00d7",
        "\uf0b8": "\u00f7",
        "\uf0b9": "\u2260",
        "\uf0d6": "\u221a",
        "\uf0d7": "\u22c5",
    }
)
# `$ CI_COMMIT_TAG` (`072_STM_003_01`, itens 72-73): o PDF traz espa\u00e7o depois
# do `$` de vari\u00e1vel; s\u00f3 em c\u00f3digo, e s\u00f3 antes de nome em mai\u00fasculas (prompt
# de shell `$ git ...` fica intacto).
PADRAO_VARIAVEL_ESPACADA = re.compile(r"\$ (?=[A-Z_][A-Z0-9_]*\b)")
# Linha de c\u00f3digo quebrada pelo PDF termina at\u00e9 5,3 pt antes da borda da
# coluna (`072_STM_003_01`, item 86: `s.length()-` / `1));`).
TOLERANCIA_BORDA_CODIGO = 8.0
TOLERANCIA_RECUO = 2.0  # recuo real: 18 pt exatos; célula de tabela a 15 pt não conta
TOLERANCIA_MESMA_LINHA = 2.0
# Parágrafo do texto-base (5G.1): recuo da 1ª linha em relação à moda do x0
# da coluna. No CEBRASPE é ~28,5 pt (56,8 × 28,3 em `167_CDNS_CG1_01`); acima
# do teto é linha centralizada/à direita (fonte "Internet: <...>"), não recuo.
RECUO_PARAGRAFO_MIN = 8.0
RECUO_PARAGRAFO_MAX = 45.0
TERMINAIS_PARAGRAFO = (".", "!", "?", ":", "”", '"', ")", "»")
LIMITE_COLUNA_DIREITA = 290.0
ALTURA_CABECALHO = 70  # faixa decorativa do topo da página (imagem de cabeçalho)
TAMANHO_MINIMO_FIGURA = 15
DPI_FIGURA = 150


# Linhas -----------------------------------------------------------------------


@dataclass
class Linha:
    pagina: int
    bloco: int
    texto: str
    x0: float
    y0: float
    x1: float
    y1: float
    inicio_bloco: bool
    # Texto do primeiro span (o número do item vem num span próprio).
    primeiro_span: str = ""
    negrito: bool = False
    monoespacada: bool = False
    # Maior x1 da coluna da linha na página (ver `_marcar_borda_direita`).
    borda_direita: float | None = None
    # x0 do primeiro span com texto (o PDF põe spans " " antes do recuo de
    # parágrafo, e o x0 da linha ficaria na margem). None = usar `x0`.
    x0_texto: float | None = None

    @property
    def bbox(self) -> list[float]:
        return [
            round(self.x0, 1),
            round(self.y0, 1),
            round(self.x1, 1),
            round(self.y1, 1),
        ]


def _obter_fontes_monoespacadas(doc) -> set[str]:
    """Conjunto de nomes de fontes de largura fixa (código/tabela) do PDF."""
    mono: set[str] = set()
    for page in doc:
        for f in page.get_fonts():
            xref, _, _, name, _, _ = f
            if name in mono:
                continue
            obj = doc.xref_object(xref)
            ws = obj.find("/Widths [")
            if ws != -1:
                we = obj.find("]", ws)
                w_list = [int(w) for w in obj[ws + 9 : we].split() if w.isdigit()]
                if len(w_list) >= 20 and len(set(w_list)) == 1:
                    mono.add(name)
                    if "+" in name:
                        mono.add(name.split("+", 1)[1])
    return mono


def _texto_spans(spans: list[dict]) -> str:
    return "".join(s["text"] for s in spans).replace("\xa0", " ").translate(SIMBOLO_PUA)


def ordenar_blocos(blocos: list[dict], largura_pagina: float) -> list[dict]:
    """Blocos de texto em ordem visual: coluna da esquerda de cima para baixo,
    depois a da direita (página de uma coluna: só de cima para baixo).

    A ordem do fluxo do PDF não basta: tabela desenhada à parte vem no fim da
    página (`072_STM_010_01`, itens 115-116), e seria colada ao último item.
    A página é de duas colunas quando algum bloco largo começa na margem da
    coluna da direita (tabela estreita à direita, sozinha, não conta).
    """
    meio = largura_pagina / 2
    texto = [b for b in blocos if b.get("type") == 0]

    def coluna_direita(b) -> bool:
        return b["bbox"][0] >= meio - 12

    if _duas_colunas(texto, largura_pagina):
        return sorted(
            texto, key=lambda b: (coluna_direita(b), b["bbox"][1], b["bbox"][0])
        )
    return sorted(texto, key=lambda b: (b["bbox"][1], b["bbox"][0]))


def _duas_colunas(blocos_texto: list[dict], largura_pagina: float) -> bool:
    meio = largura_pagina / 2
    return any(
        meio - 12 <= b["bbox"][0] <= meio + 25
        and b["bbox"][2] - b["bbox"][0] > 0.35 * largura_pagina
        for b in blocos_texto
    )


def _marcar_borda_direita(
    linhas: list[Linha], largura_pagina: float, duas_colunas: bool
) -> None:
    """Borda direita de cada coluna da página: o maior x1 das suas linhas.
    Serve para achar linha de código que o PDF quebrou por não caber na
    coluna. Em página de duas colunas, linha da esquerda que passa do meio
    (cabeçalho de largura total) não conta."""
    meio = largura_pagina / 2
    esquerda = [linha for linha in linhas if linha.x0 < meio - 12]
    direita = [linha for linha in linhas if linha.x0 >= meio - 12]
    if not duas_colunas:
        esquerda, direita = linhas, []
    for coluna, limite in ((esquerda, meio + 12), (direita, largura_pagina)):
        x1s = [linha.x1 for linha in coluna if not duas_colunas or linha.x1 <= limite]
        borda = max(x1s, default=None)
        for linha in coluna:
            linha.borda_direita = borda


def _span_mono(sp: dict, mono_fonts: set[str]) -> bool:
    font = sp.get("font", "")
    font_clean = font.split("+", 1)[1] if "+" in font else font
    flags = sp.get("flags", 0)
    return (
        font_clean in mono_fonts
        or bool(flags & 8)
        or any(k in font.lower() for k in ("mono", "courier", "consolas"))
    )


def _linha_monoespacada(spans: list[dict], mono_fonts: set[str]) -> bool:
    """Verifica se a linha é predominantemente código/tabela monoespaçado.

    Exige que todos os spans com palavras de texto corrido (2+ letras) sejam
    monoespaçados. Evita que frases de prosa iniciadas com termos técnicos
    monoespaçados (ex.: `workflow.rules`, `ALTER DATABASE`, `Meus Documentos`)
    quebrem a prosa ao meio. Símbolos e pontuações isolados (ex.: sinal de menos
    ou pipes) não invalidam a linha de código.
    """
    spans_com_texto = [s for s in spans if s.get("text", "").strip()]
    if not spans_com_texto:
        return False
    if not any(_span_mono(s, mono_fonts) for s in spans_com_texto):
        return False
    for s in spans_com_texto:
        if not _span_mono(s, mono_fonts) and re.search(
            r"[a-zA-ZÀ-ÿ]{2,}", s.get("text", "")
        ):
            return False
    return True


def extrair_linhas(doc) -> list[Linha]:
    """Linhas visuais do documento em ordem de leitura (`ordenar_blocos`).
    Linhas do mesmo bloco na mesma altura são unidas: texto justificado às
    vezes sai quebrado em várias "linhas" de uma palavra."""
    mono_fonts = _obter_fontes_monoespacadas(doc)
    linhas: list[Linha] = []
    bloco_global = 0
    for num_pagina, page in enumerate(doc):
        blocos = page.get_text("dict")["blocks"]
        inicio_pagina = len(linhas)
        for bloco in ordenar_blocos(blocos, page.rect.width):
            if bloco.get("type") != 0:
                continue
            bloco_global += 1
            atual: Linha | None = None
            for linha in bloco["lines"]:
                texto = _texto_spans(linha["spans"])
                if not texto.strip():
                    continue
                x0, y0, x1, y1 = linha["bbox"]
                centro = (y0 + y1) / 2
                sp0 = linha["spans"][0]
                sp0_flags = sp0.get("flags", 0)
                sp0_font = sp0.get("font", "")
                is_bold = bool(sp0_flags & 16) or ("bold" in sp0_font.lower())
                is_mono = _linha_monoespacada(linha["spans"], mono_fonts)
                x0_texto = next(
                    (sp["bbox"][0] for sp in linha["spans"] if sp["text"].strip()),
                    x0,
                )
                if (
                    atual is not None
                    and abs(centro - (atual.y0 + atual.y1) / 2)
                    <= TOLERANCIA_MESMA_LINHA
                ):
                    atual.texto = f"{atual.texto.rstrip()} {texto.strip()}"
                    atual.x0, atual.x1 = min(atual.x0, x0), max(atual.x1, x1)
                    atual.x0_texto = min(atual.x0_texto, x0_texto)
                    atual.monoespacada = atual.monoespacada and is_mono
                    continue
                atual = Linha(
                    pagina=num_pagina,
                    bloco=bloco_global,
                    texto=texto,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    inicio_bloco=not any(
                        linha_existente.bloco == bloco_global
                        for linha_existente in linhas[-1:]
                    ),
                    primeiro_span=sp0["text"]
                    .replace("\xa0", " ")
                    .translate(SIMBOLO_PUA),
                    negrito=is_bold,
                    monoespacada=is_mono,
                    x0_texto=x0_texto,
                )
                linhas.append(atual)
        _marcar_borda_direita(
            linhas[inicio_pagina:],
            page.rect.width,
            _duas_colunas([b for b in blocos if b.get("type") == 0], page.rect.width),
        )
    return linhas


def remover_ruido(linhas: list[Linha]) -> tuple[list[Linha], list[str]]:
    """Tira cabeçalho de página, "Espaço livre", faixas de seção e as
    instruções da capa (tudo antes da primeira faixa `-- ... --`)."""
    removidas: list[str] = []
    primeira_faixa = next(
        (i for i, linha in enumerate(linhas) if PADRAO_FAIXA_SECAO.match(linha.texto)),
        None,
    )
    resultado = []
    for i, linha in enumerate(linhas):
        if primeira_faixa is not None and i < primeira_faixa:
            removidas.append(linha.texto.strip())
            continue
        if (
            PADRAO_CABECALHO.match(linha.texto)
            or PADRAO_FAIXA_SECAO.match(linha.texto)
            or PADRAO_RUIDO.match(linha.texto)
        ):
            removidas.append(linha.texto.strip())
            continue
        resultado.append(linha)
    return resultado, removidas


# Marcadores de item ----------------------------------------------------------


def _casa_numero(linha: Linha, numero: int) -> bool:
    return re.match(rf"\s*{numero}(?:\s|$)", linha.texto) is not None


def _marcador_estrito(linha: Linha, numero: int) -> bool:
    return linha.primeiro_span.strip() == str(numero)


def _detectar_margens_colunas(linhas: list[Linha]) -> list[float]:
    """Identifica as margens esquerdas das colunas de texto (geralmente
    ~28 pt para a coluna da esquerda e ~303 pt para a coluna da direita).
    Calcula a partir do cluster mais denso (moda com tolerância) de x0 entre
    as linhas candidatas a número (ou todas as linhas), evitando que linhas
    isoladas (tabelas, cabeçalhos ou bordas com x0 atípico) desloquem a margem.
    """
    if not linhas:
        return []

    cands = [ln for ln in linhas if ln.primeiro_span.strip().isdigit()] or linhas
    esq_vals = [ln.x0 for ln in cands if ln.x0 < 290]
    dir_vals = [ln.x0 for ln in cands if ln.x0 >= 290]

    def _cluster_mais_denso(valores: list[float], tol: float = 2.0) -> float | None:
        if not valores:
            return None
        melhor_val = None
        melhor_cont = -1
        for v in sorted(valores):
            cluster = [x for x in valores if abs(x - v) <= tol]
            if len(cluster) > melhor_cont:
                melhor_cont = len(cluster)
                melhor_val = sum(cluster) / len(cluster)
        return melhor_val

    esq = _cluster_mais_denso(esq_vals)
    dir_m = _cluster_mais_denso(dir_vals)
    return [m for m in (esq, dir_m) if m is not None]


def _na_margem_coluna(
    linha: Linha, margens: list[float], tolerancia: float = 2.0
) -> bool:
    if not margens:
        return True
    return any(abs(linha.x0 - m) <= tolerancia for m in margens)


def _eh_candidato_marcador(linha: Linha, numero: int, margens: list[float]) -> bool:
    if not (_casa_numero(linha, numero) and _marcador_estrito(linha, numero)):
        return False
    # Critério: negrito (flags & 16 ou fonte com Bold) ou x0 na margem da coluna
    return bool(linha.negrito or _na_margem_coluna(linha, margens))


def _termina_frase(linha: Linha) -> bool:
    return linha.texto.rstrip().endswith(TERMINAIS_FRASE)


def localizar_itens(
    linhas: list[Linha],
    esperados: list[int],
    margens: list[float] | None = None,
    alertas: list[dict] | None = None,
) -> dict[int, tuple[int, bool]]:
    """`{numero: (indice_da_linha, estrito)}`.

    1ª passada: busca candidatos estritos para cada número esperado.
    Exige marcador em negrito ou com x0 na margem da coluna. Se um número
    candidato aparecer mais de uma vez como marcador, vira alerta bloqueante
    (caderno em falha explícita, nunca escolha silenciosa).
    2ª passada: para cada número ainda ausente, linha que começa com ele entre
    os vizinhos achados, desde que seja início de bloco ou venha depois de fim
    de frase e esteja na margem da coluna ou em negrito.
    """
    if margens is None:
        margens = _detectar_margens_colunas(linhas)

    achados: dict[int, tuple[int, bool]] = {}
    numeros_duplicados: set[int] = set()
    pos = 0

    for numero in esperados:
        candidatos = [
            i
            for i, linha in enumerate(linhas)
            if _eh_candidato_marcador(linha, numero, margens)
        ]
        if len(candidatos) == 1:
            idx = candidatos[0]
            if idx >= pos:
                achados[numero] = (idx, True)
                pos = idx + 1
            else:
                if alertas is not None:
                    alertas.append(
                        {
                            "tipo": "marcador_fora_de_ordem",
                            "severidade": SEVERIDADE_BLOQUEANTE,
                            "item": numero,
                            "indice": idx,
                            "linhas": [linhas[idx].texto[:100]],
                        }
                    )
        elif len(candidatos) > 1:
            numeros_duplicados.add(numero)
            if alertas is not None:
                alertas.append(
                    {
                        "tipo": "marcador_duplicado",
                        "severidade": SEVERIDADE_BLOQUEANTE,
                        "item": numero,
                        "indices": candidatos,
                        "linhas": [linhas[i].texto[:100] for i in candidatos],
                    }
                )

    for idx, numero in enumerate(esperados):
        if numero in achados or numero in numeros_duplicados:
            continue
        anteriores = [achados[n][0] for n in esperados[:idx] if n in achados]
        posteriores = [achados[n][0] for n in esperados[idx + 1 :] if n in achados]
        inicio = max(anteriores) + 1 if anteriores else 0
        fim = min(posteriores) if posteriores else len(linhas)
        candidatos_fallback = []
        for i in range(inicio, fim):
            linha = linhas[i]
            if (
                _casa_numero(linha, numero)
                and (linha.inicio_bloco or i == 0 or _termina_frase(linhas[i - 1]))
                and (linha.negrito or _na_margem_coluna(linha, margens))
            ):
                candidatos_fallback.append(i)
        if len(candidatos_fallback) == 1:
            achados[numero] = (candidatos_fallback[0], False)
        elif len(candidatos_fallback) > 1 and alertas is not None:
            alertas.append(
                {
                    "tipo": "marcador_duplicado",
                    "severidade": SEVERIDADE_BLOQUEANTE,
                    "item": numero,
                    "indices": candidatos_fallback,
                    "linhas": [linhas[i].texto[:100] for i in candidatos_fallback],
                }
            )
    return achados


def marcadores_fora_do_gabarito(
    linhas: list[Linha],
    esperados: list[int],
    margens: list[float] | None = None,
) -> list[int]:
    """Marcadores de item (número em span próprio) que continuam a sequência
    do gabarito para fora dela (`max+1`, `max+2`, ... ou `min-1`, ...).

    Sem essa checagem, um item do caderno que falta no gabarito seria
    engolido pelo item anterior sem aviso. Só olha a vizinhança da faixa: um
    número solto em célula de tabela não vira falso alarme.
    """
    if not esperados:
        return []
    if margens is None:
        margens = _detectar_margens_colunas(linhas)
    estritos = {
        int(linha.primeiro_span.strip())
        for linha in linhas
        if linha.primeiro_span.strip().isdigit()
        and _eh_candidato_marcador(linha, int(linha.primeiro_span.strip()), margens)
    }
    extras = []
    for passo, inicio in ((1, esperados[-1] + 1), (-1, esperados[0] - 1)):
        n = inicio
        while n > 0 and n in estritos:
            extras.append(n)
            n += passo
    return sorted(extras)


# Segmentação -----------------------------------------------------------------


def _margens_colunas(linhas: list[Linha], indices_itens: list[int]) -> list[float]:
    margens: list[float] = []
    for i in indices_itens:
        x = linhas[i].x0
        if not any(abs(x - m) < 5 for m in margens):
            margens.append(x)
    return sorted(margens)


def _recuo_item(linhas: list[Linha], i_item: int) -> float:
    """Deslocamento entre o número do item e a margem do seu texto (~18 pt).
    Medido na 2ª linha do item; sem ela, usa o padrão do CEBRASPE.
    A faixa (12 a 24 pt) cobre a variação real de recuo dos itens sem
    capturar o recuo de parágrafo de textos-base subsequentes (~28 a 29 pt)."""
    numero = linhas[i_item]
    for linha in linhas[i_item + 1 : i_item + 3]:
        delta = linha.x0 - numero.x0
        if linha.pagina == numero.pagina and 12 < delta < 24:
            return delta
    return 18.0


def _eh_continuacao(linha: Linha, margens: list[float], recuo: float) -> bool:
    candidatas = [m for m in margens if m <= linha.x0 + 2]
    margem = max(candidatas) if candidatas else (margens[0] if margens else linha.x0)
    return abs((linha.x0 - margem) - recuo) <= TOLERANCIA_RECUO


PADRAO_CODIGO_INICIO = re.compile(
    r"^\s*(?:"
    r"public\s+(?:class|static|void|boolean|int|String)|"
    r"class\s+\w+|package\s+[\w.]+|import\s+[\w.*]+|"
    r"apiVersion:\s*|kind:\s*|metadata:\s*|spec:\s*|"
    r"CREATE\s+TABLE|INSERT\s+INTO|SELECT\s+|INHERITS\s*\(|"
    r"[-=]{3,}\+[-=]{3,}|"
    r"\{[\"'\w]|\[\{"
    r")",
    re.IGNORECASE,
)

PADRAO_CODIGO_CONTINUACAO = re.compile(
    r"^\s*(?:"
    r"return\b|System\.out|HttpRequest|SELECT\b|FROM\b|WHERE\b|VALUES\b|INHERITS\b|[}\])]"
    r")",
    re.IGNORECASE,
)


def _eh_codigo_ou_tabela(
    item: Linha | str,
    texto: str,
    anterior_era_codigo: bool = False,
    prox_texto: str = "",
    ultimo_texto_codigo: str = "",
) -> bool:
    if getattr(item, "monoespacada", False):
        return True
    texto_strip = texto.strip()
    if PADRAO_CODIGO_INICIO.match(texto_strip):
        return True
    if "---" in texto or texto.count("|") >= 2:
        return True
    # Linha com 1 pipe pertencente a tabela ASCII com divisória (---) logo acima ou abaixo
    if "|" in texto and ("---" in prox_texto or "---" in ultimo_texto_codigo):
        return True
    return bool(
        anterior_era_codigo
        and (
            texto.startswith(("  ", "\t"))
            or PADRAO_CODIGO_CONTINUACAO.match(texto_strip)
        )
    )


def _recuo_texto(texto: str) -> int:
    return len(texto) - len(texto.lstrip(" \t"))


def _compara_recuo(a: Linha | str, texto_a: str, b: Linha | str, texto_b: str) -> int:
    """-1, 0 ou 1: recuo de `b` menor, igual ou maior que o de `a` (x0 da
    linha e, na mesma posição, espaços no início do texto)."""
    x0_a, x0_b = getattr(a, "x0", 0.0), getattr(b, "x0", 0.0)
    if abs(x0_a - x0_b) > TOLERANCIA_MESMA_LINHA:
        return -1 if x0_b < x0_a else 1
    ra, rb = _recuo_texto(texto_a), _recuo_texto(texto_b)
    return (rb > ra) - (rb < ra)


def _delimitador_aberto(texto: str) -> bool:
    abertos = sum(texto.count(c) for c in "([{")
    fechados = sum(texto.count(c) for c in ")]}")
    return abertos > fechados or texto.count('"') % 2 == 1


def _continua_linha_quebrada(
    primeira: Linha | str,
    ultima: Linha | str,
    texto: str,
    atual: Linha | str,
    texto_atual: str,
) -> bool:
    """Linha longa de código que o PDF quebrou na borda da coluna: a sobra
    desce para a linha seguinte sem o recuo da original (`"anos_prisao": 5},`
    em `094_PF_005_01`, item 113; `'merge_request_event'` em `072_STM_003_01`,
    item 72). `primeira`/`texto` são a linha lógica até aqui; `ultima`, o
    pedaço físico mais recente dela."""
    borda = getattr(ultima, "borda_direita", None)
    if borda is None or getattr(atual, "pagina", None) != ultima.pagina:
        return False
    if ultima.x1 < borda - TOLERANCIA_BORDA_CODIGO:
        return False
    if texto.rstrip().endswith((";", "{", "}")):
        return False
    comparacao = _compara_recuo(primeira, texto, atual, texto_atual)
    if comparacao < 0:
        return True
    # Mesmo recuo só é quebra com parêntese/colchete/aspas abertos
    # (`sum(dados["anos_prisao"] for` / `dados in prisao.values())`): linha
    # completa que só encosta na borda (`... // 2`, item 114) não é.
    return comparacao == 0 and _delimitador_aberto(texto)


def _formatar_codigo(bloco: list[tuple[Linha | str, str]]) -> str:
    """Bloco de código/tabela: uma linha lógica por linha, com recuo.

    O recuo vem do texto quando o PDF traz espaços (YAML/Java do STM). Quando
    não traz, vem do x0: o Python de `094_PF_005_01` recua com deslocamentos
    irregulares (24,7 pt no 1º nível, 14,2 pt nos seguintes), então o nível é a
    posição do x0 entre os x0 distintos do bloco na mesma coluna, não uma
    conta em pontos que dependeria da fonte.
    """
    logicas: list[list] = []  # [primeira, ultima, texto]
    for item, texto in bloco:
        if logicas and _continua_linha_quebrada(*logicas[-1], item, texto):
            anterior = logicas[-1][2].rstrip()
            sep = "" if anterior.endswith(("-", "(", "[", ".")) else " "
            logicas[-1][1] = item
            logicas[-1][2] = f"{anterior}{sep}{texto.strip()}"
        else:
            logicas.append([item, item, texto])

    def coluna(item: Linha | str) -> tuple:
        return (getattr(item, "pagina", None), getattr(item, "borda_direita", None))

    niveis: dict[tuple, list[float]] = {}
    for primeira, _, _ in logicas:
        x0 = getattr(primeira, "x0", None)
        if x0 is None:
            continue
        posicoes = niveis.setdefault(coluna(primeira), [])
        if all(abs(x0 - p) > TOLERANCIA_MESMA_LINHA for p in posicoes):
            posicoes.append(x0)
    for posicoes in niveis.values():
        posicoes.sort()

    saida = []
    for primeira, _, texto in logicas:
        x0 = getattr(primeira, "x0", None)
        nivel = 0
        if x0 is not None:
            posicoes = niveis[coluna(primeira)]
            nivel = min(range(len(posicoes)), key=lambda k: abs(posicoes[k] - x0))
        texto = PADRAO_VARIAVEL_ESPACADA.sub("$", texto.rstrip())
        saida.append("    " * nivel + texto)
    return "\n".join(saida)


def _x0_texto(linha: Linha | str) -> float | None:
    if not isinstance(linha, Linha):
        return None
    return linha.x0_texto if linha.x0_texto is not None else linha.x0


def _coluna_paragrafo(linha: Linha) -> tuple[int, bool]:
    return (linha.pagina, (_x0_texto(linha) or 0.0) >= LIMITE_COLUNA_DIREITA)


def _margens_prosa(linhas: list[Linha | str]) -> dict[tuple[int, bool], float]:
    """Margem do corpo de cada coluna (página, lado): a moda do x0 do texto
    das linhas, em pontos inteiros. A 1ª linha de parágrafo é minoria, então
    não desloca a moda."""
    contagem: dict[tuple[int, bool], Counter] = {}
    for linha in linhas:
        x0 = _x0_texto(linha)
        if x0 is None:
            continue
        contagem.setdefault(_coluna_paragrafo(linha), Counter())[round(x0)] += 1
    margens = {}
    for coluna, cont in contagem.items():
        moda, freq = cont.most_common(1)[0]
        # Moda de 1 linha não é régua (texto de 1-2 linhas): sem parágrafo.
        if freq >= 2:
            margens[coluna] = float(moda)
    return margens


def _inicia_paragrafo(
    linha: Linha | str, margens: dict[tuple[int, bool], float], anterior: str
) -> bool:
    """Linha recuada da margem do corpo (recuo de 1ª linha, ~28 pt no
    CEBRASPE) depois de uma linha que fecha frase."""
    x0 = _x0_texto(linha)
    if x0 is None:
        return False
    margem = margens.get(_coluna_paragrafo(linha))
    if margem is None:
        return False
    recuo = x0 - margem
    return (
        RECUO_PARAGRAFO_MIN <= recuo <= RECUO_PARAGRAFO_MAX
        and anterior.rstrip().endswith(TERMINAIS_PARAGRAFO)
    )


def juntar_linhas(linhas: list[Linha | str], paragrafos: bool = False) -> str:
    """Junta linhas num parágrafo ou bloco de código/tabela.

    - `paragrafos=True` (texto-base): linha com recuo de 1ª linha em relação
      à margem da coluna abre parágrafo novo (`\\n\\n`). Enunciado de item
      não usa (a chave da 5D depende dele).

    - Parágrafos de texto corrido: junta com espaço, desfaz quebra de linha e
      respeita hifenização (`executá-` + `los` -> `executá-los`).
    - Blocos de código ou tabela (detectados por fonte monoespaçada, alinhamento
      de colunas ou sintaxe de linguagens): preserva quebras `\\n` e indentação
      (ver `_formatar_codigo`).
    """
    # 1ª passada: limpa e classifica cada linha (prosa ou código/tabela).
    classificadas: list[tuple[Linha | str, str, bool]] = []
    anterior_era_codigo = False
    ultimo_texto_codigo = ""
    for idx, item in enumerate(linhas):
        texto_raw = item.texto if hasattr(item, "texto") else str(item)
        # Fonte de fórmula sem mapa Unicode sai como caractere de controle
        # (`094_PF_005_01`): vira "�", visível, e o item ganha alerta.
        texto_limpo = PADRAO_CONTROLE.sub(SIMBOLO_ILEGIVEL, texto_raw)
        if not texto_limpo.strip():
            continue
        prox_item = linhas[idx + 1] if idx + 1 < len(linhas) else None
        prox_raw = (
            prox_item.texto if hasattr(prox_item, "texto") else str(prox_item or "")
        )
        eh_cod = _eh_codigo_ou_tabela(
            item,
            texto_limpo,
            anterior_era_codigo,
            prox_texto=prox_raw,
            ultimo_texto_codigo=ultimo_texto_codigo,
        )
        if eh_cod:
            ultimo_texto_codigo = texto_limpo
        classificadas.append((item, texto_limpo, eh_cod))
        anterior_era_codigo = eh_cod

    margens = (
        _margens_prosa([it for it, _, cod in classificadas if not cod])
        if paragrafos
        else {}
    )
    resultado = ""
    anterior_era_codigo = False
    i = 0
    while i < len(classificadas):
        item, texto_limpo, eh_cod = classificadas[i]
        if eh_cod:
            fim = i
            while fim < len(classificadas) and classificadas[fim][2]:
                fim += 1
            bloco = _formatar_codigo([(it, t) for it, t, _ in classificadas[i:fim]])
            resultado = f"{resultado}\n{bloco}" if resultado else bloco
            anterior_era_codigo = True
            i = fim
            continue
        texto_formatado = re.sub(r"\s+", " ", texto_limpo).strip()
        if not resultado:
            resultado = texto_formatado
        elif anterior_era_codigo:
            resultado = f"{resultado}\n{texto_formatado}"
        elif paragrafos and _inicia_paragrafo(item, margens, resultado):
            resultado = f"{resultado}\n\n{texto_formatado}"
        elif resultado.endswith("-") and texto_formatado[:1].islower():
            resultado += texto_formatado
        else:
            resultado = f"{resultado} {texto_formatado}"
        anterior_era_codigo = False
        i += 1
    return resultado


def _linhas_coladas(anterior: Linha, atual: Linha) -> bool:
    """Mesma página e mesma coluna, sem espaço de parágrafo entre as duas."""
    altura = max(atual.y1 - atual.y0, 1)
    return (
        anterior.pagina == atual.pagina
        and abs(anterior.x0 - atual.x0) < 40
        and -3 <= atual.y0 - anterior.y1 < altura
    )


def _inicio_comando(linhas: list[Linha], inicio: int, fim: int) -> int | None:
    """Índice da linha onde começa o comando (`... julgue ...`) do preâmbulo
    `linhas[inicio:fim]`: volta pelas linhas coladas (mesma página, sem
    espaço de parágrafo) até a linha anterior que termina frase. Não usa o
    bloco do PyMuPDF: há caderno (TCU) em que cada linha é um bloco."""
    j = next(
        (
            k
            for k in range(fim - 1, inicio - 1, -1)
            if PADRAO_COMANDO_OBJETIVO.search(linhas[k].texto)
        ),
        None,
    )
    if j is None:
        return None
    k = j
    while (
        k > inicio
        and j - k < MAX_LINHAS_COMANDO
        and _linhas_coladas(linhas[k - 1], linhas[k])
        and not linhas[k - 1].texto.rstrip().endswith(TERMINAIS_COMANDO)
    ):
        k -= 1
    # Tabela ou código colado no comando (linha anterior termina em número ou
    # em ";", como numa lista de INSERTs): o comando começa na última linha
    # em maiúscula depois dela.
    for m in range(j, k, -1):
        anterior = linhas[m - 1].texto.rstrip()
        if (
            linhas[m].texto.lstrip()[:1].isupper()
            and anterior
            and (anterior[-1].isdigit() or anterior[-1] == ";")
        ):
            return m
    return k


@dataclass
class ResultadoSegmentacao:
    itens: dict[int, dict] = field(default_factory=dict)
    textos_base: list[dict] = field(default_factory=list)
    alertas: list[dict] = field(default_factory=list)
    # índice da linha -> ("item", numero) | ("texto_base", ordem) | ("comando", ordem_grupo)
    dono_linha: dict[int, tuple[str, int]] = field(default_factory=dict)


def segmentar(
    linhas: list[Linha], achados: dict[int, tuple[int, bool]]
) -> ResultadoSegmentacao:
    res = ResultadoSegmentacao()
    ordem_itens = sorted(achados, key=lambda n: achados[n][0])
    if not ordem_itens:
        return res
    indices = [achados[n][0] for n in ordem_itens]
    margens = _margens_colunas(linhas, indices)

    # Preâmbulo antes do 1º item + o que sobra entre itens.
    grupo_atual: dict | None = None
    texto_base_anterior: int | None = None

    def abrir_grupo(inicio: int, fim: int, numero_seguinte: int) -> dict:
        nonlocal texto_base_anterior
        k = _inicio_comando(linhas, inicio, fim)
        if k is None:
            res.alertas.append(
                {
                    "tipo": "preambulo_sem_comando",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "item": numero_seguinte,
                    "texto": juntar_linhas(linhas[inicio:fim])[:300],
                }
            )
            k = fim
        comando = juntar_linhas(linhas[k:fim]) or None
        base = juntar_linhas(linhas[inicio:k], paragrafos=True)
        # O comando pode começar no meio da linha, colado ao fim do texto-base
        # ("... biodiversidade. Acerca desse tema, julgue ..."): a última frase
        # antes do "julgue" é o comando, o resto volta para o texto-base.
        if comando:
            pos = PADRAO_COMANDO_OBJETIVO.search(comando)
            fronteiras = [
                m
                for m in PADRAO_FRONTEIRA_FRASE.finditer(comando)
                if pos and m.end() <= pos.start()
            ]
            if fronteiras:
                corte = fronteiras[-1]
                base = f"{base} {comando[: corte.end(1)]}".strip()
                comando = comando[corte.end() :]
        ordem_base = None
        herdado = False
        if base:
            ordem_base = len(res.textos_base)
            res.textos_base.append(
                {
                    "ordem": ordem_base,
                    "texto": base,
                    "paginas": sorted({linha.pagina + 1 for linha in linhas[inicio:k]}),
                    "linhas_brutas": [linha.texto for linha in linhas[inicio:k]],
                    "figuras": [],
                }
            )
            for i in range(inicio, k):
                res.dono_linha[i] = ("texto_base", ordem_base)
            texto_base_anterior = ordem_base
        elif (
            comando
            and texto_base_anterior is not None
            and PADRAO_COMANDO_REFERE_TEXTO.search(comando)
        ):
            ordem_base, herdado = texto_base_anterior, True
        for i in range(k, fim):
            res.dono_linha[i] = ("comando", numero_seguinte)
        return {
            "grupo": numero_seguinte,
            "secao": comando,
            "texto_base_ordem": ordem_base,
            "texto_base_herdado": herdado,
        }

    grupo_atual = abrir_grupo(0, indices[0], ordem_itens[0])

    for pos, numero in enumerate(ordem_itens):
        i_item = indices[pos]
        proximo = indices[pos + 1] if pos + 1 < len(indices) else len(linhas)
        recuo = _recuo_item(linhas, i_item)

        # Maior sufixo de linhas sem recuo de item = candidato a preâmbulo.
        corte = proximo
        while corte - 1 > i_item and not _eh_continuacao(
            linhas[corte - 1], margens, recuo
        ):
            corte -= 1
        sufixo = linhas[corte:proximo]
        tem_comando = any(
            PADRAO_COMANDO_OBJETIVO.search(linha.texto) for linha in sufixo
        )

        if pos + 1 < len(indices) and sufixo and tem_comando:
            fim_item = corte
            k = _inicio_comando(linhas, corte, proximo)
            texto_item = juntar_linhas(linhas[i_item:corte])
            comando = juntar_linhas(linhas[k:proximo]) if k else ""
            if (
                k is not None
                and k > corte
                and PADRAO_ITEM_ANUNCIA.search(texto_item)
                and not PADRAO_COMANDO_REFERE_TEXTO.search(comando)
            ):
                fim_item = k
                res.alertas.append(
                    {
                        "tipo": "trecho_anunciado_anexado_ao_item",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "item": numero,
                        "texto": juntar_linhas(linhas[corte:k])[:300],
                    }
                )
        else:
            fim_item = proximo
            if sufixo and pos + 1 < len(indices):
                res.alertas.append(
                    {
                        "tipo": "trecho_sem_recuo_anexado_ao_item",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "item": numero,
                        "texto": juntar_linhas(sufixo)[:300],
                    }
                )
            elif sufixo:
                # Depois do último item (cabeçalho, rodapé e "Espaço livre" já
                # saíram no `remover_ruido`): o que sobra costuma ser tabela
                # do próprio item — fica no item, com alerta, nunca some.
                res.alertas.append(
                    {
                        "tipo": "trecho_sem_recuo_anexado_ao_item",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "item": numero,
                        "texto": juntar_linhas(sufixo)[:300],
                    }
                )

        brutas = [linha.texto for linha in linhas[i_item:fim_item]]
        enunciado = juntar_linhas(linhas[i_item:fim_item])
        enunciado = re.sub(rf"^{numero}\s*", "", enunciado, count=1)
        res.itens[numero] = {
            "numero": numero,
            "enunciado": enunciado,
            "secao": grupo_atual["secao"],
            "texto_base_ordem": grupo_atual["texto_base_ordem"],
            "texto_base_herdado": grupo_atual["texto_base_herdado"],
            "grupo": grupo_atual["grupo"],
            "marcador_estrito": achados[numero][1],
            "pagina": linhas[i_item].pagina + 1,
            "linhas_brutas": brutas,
            "figuras": [],
        }
        for i in range(i_item, fim_item):
            res.dono_linha[i] = ("item", numero)

        if fim_item < proximo and pos + 1 < len(indices):
            grupo_atual = abrir_grupo(fim_item, proximo, ordem_itens[pos + 1])
    return res


# Figuras ----------------------------------------------------------------------


def _unir_tiras(rects: list[pymupdf.Rect]) -> list[pymupdf.Rect]:
    """Uma figura às vezes vem fatiada em tiras horizontais empilhadas
    (`094_PF_007_01`); tiras com a mesma faixa horizontal e encostadas viram
    uma figura só."""
    unidas: list[pymupdf.Rect] = []
    for r in sorted(rects, key=lambda r: (r.y0, r.x0)):
        for u in unidas:
            mesma_faixa = abs(u.x0 - r.x0) < 3 and abs(u.x1 - r.x1) < 3
            if mesma_faixa and -1 <= r.y0 - u.y1 <= 3:
                u.include_rect(r)
                break
        else:
            unidas.append(pymupdf.Rect(r))
    return unidas


def figuras_da_pagina(page) -> list[pymupdf.Rect]:
    rects = []
    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & page.rect
        if (
            r.is_empty
            or r.width < TAMANHO_MINIMO_FIGURA
            or r.height < TAMANHO_MINIMO_FIGURA
        ):
            continue
        # Faixas decorativas: o cabeçalho da página e as tarjas de largura
        # total e pouca altura ("PROVAS OBJETIVAS" da capa).
        if r.y1 <= ALTURA_CABECALHO or (
            r.width > 0.8 * page.rect.width and r.height < 25
        ):
            continue
        rects.append(r)
    return _unir_tiras(rects)


def dono_da_figura(
    rect: pymupdf.Rect,
    pagina: int,
    linhas: list[Linha],
    dono_linha: dict[int, tuple[str, int]],
) -> tuple[str, int] | None:
    """Trecho da linha logo acima da figura na mesma coluna (sobreposição
    horizontal); sem linha acima, o da primeira linha abaixo.

    Exceção: figura entre o fim de um item e o preâmbulo do grupo seguinte
    (linha acima = item, linha abaixo = texto-base/comando) é do grupo
    seguinte — é o caso de "Considerando as figuras A e B, julgue ...". A
    figura do próprio item tem texto do item depois dela ("Nesse caso, ...")
    ou o próximo item logo abaixo."""
    acima, abaixo = None, None
    for i, linha in enumerate(linhas):
        if linha.pagina != pagina or i not in dono_linha:
            continue
        sobrepoe = min(linha.x1, rect.x1) - max(linha.x0, rect.x0) > 0
        if not sobrepoe:
            continue
        if linha.y1 <= rect.y0 + 2 and (acima is None or linha.y1 >= linhas[acima].y1):
            acima = i
        elif linha.y0 >= rect.y1 - 2 and (
            abaixo is None or linha.y0 < linhas[abaixo].y0
        ):
            abaixo = i
    dono_acima = dono_linha.get(acima) if acima is not None else None
    dono_abaixo = dono_linha.get(abaixo) if abaixo is not None else None
    if (
        dono_acima
        and dono_abaixo
        and dono_acima[0] == "item"
        and dono_abaixo[0] != "item"
    ):
        return dono_abaixo
    return dono_acima or dono_abaixo


# Caderno objetivo -------------------------------------------------------------


def extrair_caderno_objetivo(
    pdf_path: Path,
    gabarito: dict[int, str] | None,
    caderno: str,
    dir_figuras: Path | None = None,
) -> tuple[dict, dict]:
    """Devolve `(resultado, auditoria)` de um caderno Certo/Errado.

    `gabarito` = `{numero: 'C'|'E'|'X'}` (grade definitiva). Sem gabarito, o
    caderno falha com `falha_sem_gabarito` — a faixa de itens não é chutada.
    """
    resultado = {
        "caderno": caderno,
        "arquivo": pdf_path.name,
        "tipo": "objetiva",
        "status": STATUS_SUCESSO,
        "itens_esperados": len(gabarito or {}),
        "itens_extraidos": 0,
        "itens_faltando": [],
        "questoes": [],
        "textos_base": [],
        "alertas": [],
    }
    auditoria = {
        "caderno": caderno,
        "arquivo": pdf_path.name,
        "linhas_removidas": [],
        "itens": {},
    }
    if not gabarito:
        resultado["status"] = STATUS_FALHA_SEM_GABARITO
        resultado["alertas"].append(
            {"tipo": "sem_gabarito", "severidade": SEVERIDADE_BLOQUEANTE}
        )
        return resultado, auditoria

    with pymupdf.open(pdf_path) as doc:
        linhas, removidas = remover_ruido(extrair_linhas(doc))
        auditoria["linhas_removidas"] = removidas
        esperados = sorted(gabarito)
        alertas_loc: list[dict] = []
        achados = localizar_itens(linhas, esperados, alertas=alertas_loc)
        resultado["alertas"].extend(alertas_loc)
        seg = segmentar(linhas, achados)

        # Figuras.
        total_figuras = 0
        for num_pagina, page in enumerate(doc):
            for n, rect in enumerate(figuras_da_pagina(page), start=1):
                dono = dono_da_figura(rect, num_pagina, linhas, seg.dono_linha)
                nome = f"{caderno}_{num_pagina + 1}_{n}.png"
                figura = {
                    "arquivo": nome,
                    "pagina": num_pagina + 1,
                    "bbox": [round(v, 1) for v in rect],
                }
                if dir_figuras is not None:
                    dir_figuras.mkdir(parents=True, exist_ok=True)
                    page.get_pixmap(clip=rect, dpi=DPI_FIGURA).save(dir_figuras / nome)
                total_figuras += 1
                if dono is None:
                    resultado["alertas"].append(
                        {
                            "tipo": "figura_sem_dono",
                            "severidade": SEVERIDADE_INFORMATIVO,
                            "figura": nome,
                        }
                    )
                    continue
                tipo, chave = dono
                if tipo == "texto_base":
                    seg.textos_base[chave]["figuras"].append(figura)
                elif tipo == "item":
                    seg.itens[chave]["figuras"].append(figura)
                else:
                    # Figura no preâmbulo do grupo (entre o comando e o item
                    # anterior): é base comum dos itens do grupo. Sem texto-base,
                    # vira um texto-base só com a figura.
                    grupo = [i for i in seg.itens.values() if i["grupo"] == chave]
                    ordem = grupo[0]["texto_base_ordem"] if grupo else None
                    if ordem is None or grupo[0]["texto_base_herdado"]:
                        ordem = len(seg.textos_base)
                        seg.textos_base.append(
                            {
                                "ordem": ordem,
                                "texto": "",
                                "paginas": [num_pagina + 1],
                                "linhas_brutas": [],
                                "figuras": [],
                            }
                        )
                        for i in grupo:
                            i["texto_base_ordem"], i["texto_base_herdado"] = (
                                ordem,
                                False,
                            )
                    seg.textos_base[ordem]["figuras"].append(figura)

    for item in seg.itens.values():
        if SIMBOLO_ILEGIVEL in item["enunciado"]:
            resultado["alertas"].append(
                {
                    "tipo": "simbolo_ilegivel",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "item": item["numero"],
                }
            )
        tem_figura = item["figuras"] or (
            item["texto_base_ordem"] is not None
            and seg.textos_base[item["texto_base_ordem"]]["figuras"]
        )
        if PADRAO_MENCIONA_FIGURA.search(item["enunciado"]) and not tem_figura:
            # Figura vetorial (desenhada com traços, não imagem) não é
            # extraída: fica o alerta para conferir no PDF.
            resultado["alertas"].append(
                {
                    "tipo": "figura_mencionada_sem_imagem",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "item": item["numero"],
                }
            )

    resultado["alertas"].extend(seg.alertas)
    faltando = [n for n in esperados if n not in seg.itens]
    vazios = [n for n, item in seg.itens.items() if not item["enunciado"].strip()]
    extras = marcadores_fora_do_gabarito(linhas, esperados)
    resultado["itens_faltando"] = faltando
    resultado["itens_fora_do_gabarito"] = extras
    resultado["itens_extraidos"] = len(seg.itens) - len(vazios)
    tem_bloqueante = any(
        a.get("severidade") == SEVERIDADE_BLOQUEANTE for a in resultado["alertas"]
    )
    if faltando or vazios or extras or tem_bloqueante:
        resultado["status"] = STATUS_FALHA_ITENS_DIVERGENTES
        if faltando or vazios or extras:
            resultado["alertas"].append(
                {
                    "tipo": "itens_divergentes_do_gabarito",
                    "severidade": SEVERIDADE_BLOQUEANTE,
                    "faltando": faltando,
                    "vazios": vazios,
                    "fora_do_gabarito": extras,
                }
            )

    for numero in esperados:
        item = seg.itens.get(numero)
        if item is None:
            continue
        auditoria["itens"][str(numero)] = {
            "pagina": item["pagina"],
            "marcador_estrito": item["marcador_estrito"],
            "linhas_brutas": item["linhas_brutas"],
        }
        item_alertas = list(
            dict.fromkeys(
                a["tipo"]
                for a in resultado["alertas"]
                if a.get("item") == numero and "tipo" in a
            )
        )
        resultado["questoes"].append(
            {
                "numero": numero,
                "enunciado": item["enunciado"],
                "gabarito": gabarito[numero],
                "anulada": gabarito[numero] == "X",
                "texto_base_ordem": item["texto_base_ordem"],
                "texto_base_herdado": item["texto_base_herdado"],
                "secao": item["secao"],
                "pagina": item["pagina"],
                "figuras": item["figuras"],
                "alertas": item_alertas,
            }
        )
    resultado["textos_base"] = [
        {k: v for k, v in tb.items() if k != "linhas_brutas"} for tb in seg.textos_base
    ]
    auditoria["textos_base"] = [
        {"ordem": tb["ordem"], "linhas_brutas": tb["linhas_brutas"]}
        for tb in seg.textos_base
    ]
    resultado["total_figuras"] = total_figuras
    nao_estritos = [n for n, (_, estrito) in achados.items() if not estrito]
    if nao_estritos:
        resultado["alertas"].append(
            {
                "tipo": "marcador_sem_fonte_propria",
                "severidade": SEVERIDADE_INFORMATIVO,
                "itens": sorted(nao_estritos),
            }
        )
    logger.info(
        f"[QUESTOES] {caderno}: {resultado['itens_extraidos']}/{len(esperados)} itens, "
        f"{len(seg.textos_base)} textos-base, {total_figuras} figuras, status={resultado['status']}"
    )
    return resultado, auditoria


# Caderno discursivo -----------------------------------------------------------

PADRAO_TITULO_QUESTAO = re.compile(
    r"^\s*(Quest[ãa]o\s+(\d+)|Pe[çc]a\s+de\s+natureza\s+t[ée]cnica)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
PADRAO_VALOR = re.compile(r"\[\s*valor\s*:\s*([\d.,]+)\s*pontos?\s*\]", re.IGNORECASE)
PADRAO_QUESITO = re.compile(r"^\s*(\d{1,2})\s*$|^\s*(\d{1,2})\s+(?=\S)", re.MULTILINE)
PADRAO_RASCUNHO = re.compile(r"^.*RASCUNHO.*$", re.IGNORECASE | re.MULTILINE)
PADRAO_COMANDO = re.compile(
    r"\b(redija|elabore|aborde|discorra|atendendo ao que se pede)\b", re.IGNORECASE
)
PADRAO_TEMA_ANAFORICO = re.compile(
    r"\b(dess[ae]s?|dest[ae]s?|referid[ao]s?|mencionad[ao]s?|tal|tais)\b", re.IGNORECASE
)
PADRAO_TEMA_CAIXA_ALTA = re.compile(
    r"seguinte\s+tema\.?\s*\n\s*([^\n]{10,})", re.IGNORECASE
)
PADRAO_TEMA_ACERCA = re.compile(
    r"\b(?:redija|elabore)\b[^.]*?\b(?:acerca|a respeito|sobre)\s+(?:d[aeo]s?\s+)?(.+?)(?:\[valor|\.\s|\.$|, (?:contemplando|atendendo|com base)|\. Em seu texto)",
    re.IGNORECASE | re.DOTALL,
)
PADRAO_PONTOS_TOTAL = re.compile(
    r"atribu[íi]dos\s+at[ée]\s+([\d.,]+)\s+pontos?,\s+dos\s+quais\s+at[ée]\s+([\d.,]+)\s+pontos?",
    re.IGNORECASE,
)
PADRAO_PONTOS_PECA = re.compile(
    r"pe[çc]a\s+de\s+natureza\s+t[ée]cnica,\s+esses\s+valores\s+corresponder[ãa]o\s+a\s+([\d.,]+)\s+pontos?\s+e\s+([\d.,]+)",
    re.IGNORECASE,
)


def _numero_br(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _chave_titulo(titulo: str | None) -> tuple[str, int | None] | None:
    if not titulo:
        return None
    t = titulo.strip()
    m = re.search(r"quest[ãa]o\s+(\d+)", t, re.IGNORECASE)
    if m:
        return ("questao", int(m.group(1)))
    if re.search(r"pe[çc]a(?:\s+de\s+natureza\s+t[ée]cnica)?", t, re.IGNORECASE):
        return ("peca", None)
    return None


def _limpar_paginas_discursiva(paginas: list[str]) -> tuple[str, str]:
    """(instruções da capa, corpo): remove cabeçalho de página e grades de
    rascunho (linhas numeradas vazias depois de `RASCUNHO`)."""
    corpo_paginas = []
    instrucoes = ""
    for texto in paginas:
        linhas = [
            linha for linha in texto.split("\n") if not PADRAO_CABECALHO.match(linha)
        ]
        texto = "\n".join(linhas)
        # Grade de rascunho: tudo depois de "... RASCUNHO" que for só número/espaço.
        texto = re.sub(
            r"(?im)^[^\n]*RASCUNHO[^\n]*\n(?:\s*\d{1,2}\s*\n|\s*\n)*", "\n", texto
        )
        texto = re.sub(r"(?im)^\s*RASCUNHO\s*$", "", texto)
        corpo_paginas.append(texto)
    corpo = "\n".join(corpo_paginas)
    m = re.search(
        r"^\s*--\s*PROVA DISCURSIVA\s*[–-]+\s*$", corpo, re.IGNORECASE | re.MULTILINE
    )
    if m:
        instrucoes, corpo = corpo[: m.start()], corpo[m.end() :]
    return instrucoes, corpo


def _extrair_quesitos(
    bloco: str, alertas: list[dict] | None = None
) -> tuple[list[dict], int | None]:
    """Quesitos numerados (`1 texto [valor: X pontos]`); sem numeração, cada
    `[valor: ...]` fecha um quesito com o trecho anterior a ele."""
    m_cmd = PADRAO_COMANDO.search(bloco)
    if m_cmd:
        marcas = list(PADRAO_QUESITO.finditer(bloco, m_cmd.start()))
    else:
        marcas = list(PADRAO_QUESITO.finditer(bloco))
        if alertas is not None:
            alertas.append(
                {
                    "tipo": "comando_nao_identificado",
                    "severidade": SEVERIDADE_INFORMATIVO,
                }
            )

    # Só vale como lista de quesitos a sequência 1, 2, 3... a partir do 1.
    sequencia = []
    esperado = 1
    for m in marcas:
        numero = int(m.group(1) or m.group(2))
        if numero == esperado:
            sequencia.append(m)
            esperado += 1
    quesitos = []
    if sequencia:
        for i, m in enumerate(sequencia):
            fim = sequencia[i + 1].start() if i + 1 < len(sequencia) else len(bloco)
            texto = juntar_linhas(bloco[m.end() : fim].split("\n"))
            # Um quesito pode ter mais de um `[valor]` (uma parte para cada
            # pedido); o valor do quesito é a soma.
            valores = [_numero_br(v) for v in PADRAO_VALOR.findall(texto)]
            sem_valor = re.sub(r"\s+([.,;])", r"\1", PADRAO_VALOR.sub("", texto))
            quesitos.append(
                {
                    "numero": i + 1,
                    "texto": re.sub(r"\s+", " ", sem_valor).strip(),
                    "valor_pontos": round(sum(valores), 2) if valores else None,
                }
            )
        return quesitos, sequencia[0].start()

    # Caso não haja sequência numerada, buscar PADRAO_VALOR após m_cmd.start() (ou no bloco)
    pos_busca = m_cmd.start() if m_cmd else 0
    valores = list(PADRAO_VALOR.finditer(bloco, pos_busca))
    if not valores and m_cmd:
        valores = list(PADRAO_VALOR.finditer(bloco))
    if not valores:
        return [], None

    # Sem numeração: cada [valor] marca um quesito com o trecho da frase que o precede.
    inicio = pos_busca if valores[0].start() >= pos_busca else 0
    for i, v in enumerate(valores):
        trecho = bloco[inicio : v.start()]
        trecho = re.split(r"(?<=[.:])\s|,\s(?=citando|cite|e cite)", trecho)[-1]
        quesitos.append(
            {
                "numero": i + 1,
                "texto": juntar_linhas(trecho.split("\n")).strip(" ,;"),
                "valor_pontos": _numero_br(v.group(1)),
            }
        )
        inicio = v.end()
    return quesitos, None


def _tema(enunciado: str) -> tuple[str | None, str | None]:
    """Extrai o tema do enunciado. Devolve tupla `(tema, candidato_rejeitado)`.
    Se o candidato contiver anáfora (ex.: 'dessa contratação', 'o referido sistema'),
    o tema é rejeitado e devolvido como candidato_rejeitado."""
    candidato = None
    m = PADRAO_TEMA_CAIXA_ALTA.search(enunciado)
    if m and m.group(1).strip().isupper():
        candidato = juntar_linhas([m.group(1)])
    else:
        m = PADRAO_TEMA_ACERCA.search(enunciado)
        if m:
            candidato = juntar_linhas(m.group(1).split("\n")).strip(" ,;")

    if candidato:
        if PADRAO_TEMA_ANAFORICO.search(candidato):
            return None, candidato
        return candidato, None
    return None, None


def extrair_caderno_discursivo(pdf_path: Path, caderno: str) -> tuple[dict, dict]:
    paginas = extrair_texto_paginas(pdf_path)
    instrucoes, corpo = _limpar_paginas_discursiva(paginas)
    resultado = {
        "caderno": caderno,
        "arquivo": pdf_path.name,
        "tipo": "discursiva",
        "status": STATUS_SUCESSO,
        "questoes": [],
        "alertas": [],
    }
    auditoria = {
        "caderno": caderno,
        "arquivo": pdf_path.name,
        "instrucoes": instrucoes.strip(),
        "questoes": [],
    }

    total = PADRAO_PONTOS_TOTAL.search(instrucoes.replace("\n", " "))
    peca = PADRAO_PONTOS_PECA.search(instrucoes.replace("\n", " "))

    titulos = list(PADRAO_TITULO_QUESTAO.finditer(corpo))
    if titulos:
        blocos = [
            (
                m.group(1).strip(),
                corpo[
                    m.end() : titulos[i + 1].start()
                    if i + 1 < len(titulos)
                    else len(corpo)
                ],
            )
            for i, m in enumerate(titulos)
        ]
    else:
        blocos = [(None, corpo)]

    contador_sequencial = 1
    for titulo, bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue

        chave = _chave_titulo(titulo)
        if chave and chave[0] == "questao" and chave[1] is not None:
            numero = chave[1]
            contador_sequencial = max(contador_sequencial, numero + 1)
        else:
            numero = contador_sequencial
            contador_sequencial += 1

        quesitos, inicio_quesitos = _extrair_quesitos(bloco, resultado["alertas"])
        enunciado_bruto = bloco if inicio_quesitos is None else bloco[:inicio_quesitos]
        enunciado = "\n\n".join(
            juntar_linhas(p.split("\n"))
            for p in re.split(r"\n\s*\n", enunciado_bruto)
            if p.strip()
        )
        eh_peca = bool(titulo and re.match(r"pe[çc]a", titulo, re.IGNORECASE))
        tema, candidato_rejeitado = _tema(enunciado)
        questao = {
            "numero": numero,
            "titulo": titulo,
            "tema": tema,
            "enunciado": enunciado,
            "quesitos": quesitos,
            "padrao_resposta": None,
        }
        # Conferência: soma dos quesitos = pontos de conteúdo (total menos a
        # parte de apresentação), quando a capa informa os dois.
        referencia = peca if (eh_peca and peca) else total
        if (
            referencia
            and quesitos
            and all(q["valor_pontos"] is not None for q in quesitos)
        ):
            esperado = round(
                _numero_br(referencia.group(1)) - _numero_br(referencia.group(2)), 2
            )
            soma = round(sum(q["valor_pontos"] for q in quesitos), 2)
            questao["pontos_conteudo"] = esperado
            if abs(soma - esperado) > 0.01:
                resultado["alertas"].append(
                    {
                        "tipo": "soma_quesitos_divergente",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "questao": numero,
                        "soma": soma,
                        "esperado": esperado,
                    }
                )

        if not quesitos:
            resultado["alertas"].append(
                {
                    "tipo": "sem_quesitos",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "questao": numero,
                }
            )
        elif any(q["valor_pontos"] is None for q in quesitos):
            resultado["alertas"].append(
                {
                    "tipo": "quesito_sem_valor",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "questao": numero,
                    "quesitos": [
                        q["numero"] for q in quesitos if q["valor_pontos"] is None
                    ],
                }
            )

        if candidato_rejeitado:
            resultado["alertas"].append(
                {
                    "tipo": "tema_anaforico",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "questao": numero,
                    "candidato": candidato_rejeitado,
                }
            )
        elif questao["tema"] is None:
            resultado["alertas"].append(
                {
                    "tipo": "tema_nao_identificado",
                    "severidade": SEVERIDADE_INFORMATIVO,
                    "questao": numero,
                }
            )

        resultado["questoes"].append(questao)
        auditoria["questoes"].append(
            {"numero": numero, "titulo": titulo, "texto_bruto": bloco}
        )

    # Verificar se há número repetido ou salto/buraco na numeração dos blocos válidos
    numeros_finais = [q["numero"] for q in resultado["questoes"]]
    tem_repetido = len(numeros_finais) != len(set(numeros_finais))
    tem_buraco = bool(
        numeros_finais
        and numeros_finais != list(range(numeros_finais[0], numeros_finais[-1] + 1))
    )
    if tem_repetido or tem_buraco:
        resultado["alertas"].append(
            {
                "tipo": "numeracao_discursiva",
                "severidade": SEVERIDADE_INFORMATIVO,
                "numeros": numeros_finais,
            }
        )

    if not resultado["questoes"]:
        resultado["status"] = STATUS_FALHA_SEM_QUESTAO
        resultado["alertas"].append(
            {"tipo": "sem_questao", "severidade": SEVERIDADE_BLOQUEANTE}
        )
    logger.info(
        f"[QUESTOES] {caderno}: discursiva com {len(resultado['questoes'])} questão(ões), "
        f"{sum(len(q['quesitos']) for q in resultado['questoes'])} quesitos."
    )
    return resultado, auditoria


def ligar_padrao_resposta(resultado: dict, secoes: list[dict], arquivo: str) -> None:
    """Liga as seções do padrão de resposta às questões do caderno:
    1. Se todas as questões e todas as seções tiverem chaves válidas pelo título,
       sem chave repetida (entre as seções ou entre as questões), liga
       diretamente por chave.
    2. Senão, se o número de seções for igual ao de questões, liga pela ordem
       (com alerta se não for questão única sem título).
    3. Senão, o texto inteiro vai para todas as questões, com alerta."""
    questoes = resultado["questoes"]
    chaves_questoes = [_chave_titulo(q.get("titulo")) for q in questoes]
    chaves_secoes = [_chave_titulo(s.get("titulo")) for s in secoes]

    # 1. Sucesso por chave
    if (
        chaves_questoes
        and all(c is not None for c in chaves_questoes)
        and chaves_secoes
        and all(c is not None for c in chaves_secoes)
        and len(set(chaves_questoes)) == len(chaves_questoes)
        and len(set(chaves_secoes)) == len(chaves_secoes)
    ):
        secoes_por_chave = {c: s for c, s in zip(chaves_secoes, secoes)}
        if all(c in secoes_por_chave for c in chaves_questoes):
            for questao, chave in zip(questoes, chaves_questoes):
                questao["padrao_resposta"] = secoes_por_chave[chave]["texto"]
                questao["padrao_resposta_arquivo"] = arquivo
            return

    # 2. Liga pela ordem
    if len(secoes) == len(questoes):
        for questao, secao in zip(questoes, secoes):
            questao["padrao_resposta"] = secao["texto"]
            questao["padrao_resposta_arquivo"] = arquivo
        if not (len(questoes) == 1 and questoes[0].get("titulo") is None):
            resultado["alertas"].append(
                {
                    "tipo": "padrao_ligado_por_ordem",
                    "severidade": SEVERIDADE_INFORMATIVO,
                }
            )
        return

    # 3. Não dividido
    texto = "\n\n".join(s["texto"] for s in secoes)
    for questao in questoes:
        questao["padrao_resposta"] = texto
        questao["padrao_resposta_arquivo"] = arquivo
    resultado["alertas"].append(
        {
            "tipo": "padrao_resposta_nao_dividido",
            "severidade": SEVERIDADE_INFORMATIVO,
            "secoes": len(secoes),
            "questoes": len(questoes),
        }
    )
