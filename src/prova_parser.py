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

**Caderno com gabarito** ("PROVA E GABARITO", 8.M/S3). As respostas vêm
impressas no próprio caderno (justificativa por item ou por alternativa, ou o
veredito na linha do item): `separar_gabarito_embutido` as tira antes da
segmentação e as devolve como grade (`ler_gabarito_embutido`).

**Caderno discursivo.** Uma ou mais questões ("Questão N", "Peça de natureza
técnica"), cada uma com enunciado, tema e quesitos (`N texto [valor: X
pontos]`). O padrão de resposta (outro PDF) é ligado depois, por questão.

Nada é descartado em silêncio: divergência entre itens extraídos e itens do
gabarito vira `status` de falha no caderno, e trecho que não se encaixa vira
alerta com o texto na auditoria.
"""

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path

import pymupdf

from src.comparacao_texto import normalizar
from src.edital_parser import extrair_texto_paginas
from src.gabarito_parser import (
    LETRAS_POR_TIPO,
    QUESTAO_CERTO_ERRADO,
    QUESTAO_MULTIPLA_ESCOLHA,
    TIPO_GRADE,
    VERSAO_DEFINITIVO,
    VERSAO_PRELIMINAR,
    GradeGabarito,
)
from src.logger import logger

STATUS_SUCESSO = "sucesso"
STATUS_FALHA_ITENS_DIVERGENTES = "falha_itens_divergentes"
STATUS_FALHA_SEM_GABARITO = "falha_sem_gabarito"
STATUS_FALHA_SEM_QUESTAO = "falha_sem_questao"

SEVERIDADE_BLOQUEANTE = "bloqueante"
SEVERIDADE_INFORMATIVO = "informativo"
# Alertas por item que tiram a questão do site (`questoes.utilizavel=false`)
# sem derrubar o caderno inteiro (o que a severidade bloqueante faria).
ALERTAS_ITEM_INUTILIZAVEL = frozenset(
    {"simbolo_ilegivel", "possivel_preambulo_no_item"}
)

PADRAO_CABECALHO = re.compile(r"^\s*CEBRASPE\s*[–-].*Edital", re.IGNORECASE)
PADRAO_FAIXA_SECAO = re.compile(r"^\s*--")  # "-- CONHECIMENTOS BÁSICOS --"
# Código de controle impresso no rodapé dos cadernos ME
# (`<SEFAPR177001A01E2977>`, `<SEBRAE_26_PSE_1169CG1A01E1035>`): todos os
# cadernos da amostra 2020+ terminam em `A<2 dígitos>E<4 dígitos>`. Sensível a
# maiúsculas e nesse formato, para `<html>`/`<div>` de questão de TI ficarem.
PADRAO_RUIDO = re.compile(
    r"^\s*(?:Espaço livre|PROVAS? OBJETIVAS?|RASCUNHO|(?-i:<[A-Z0-9_]+A\d{2}E\d{4}>))\s*$",
    re.IGNORECASE,
)
PADRAO_QUESTAO_ME = re.compile(r"^\s*Quest[ãa]o\s+(\d+)\b", re.IGNORECASE)
# Cabeçalho de seção ME ("LÍNGUA PORTUGUESA", "RACIOCÍNIO LÓGICO",
# "CONHECIMENTOS DO SEBRAE"): sempre em caixa alta. Sensível a caixa, senão
# a linha quebrada de uma alternativa ("legislação vigente.") corta a questão
# (ver `_eh_cabecalho_secao_me`).
PADRAO_CABECALHO_SECAO_ME = re.compile(
    r"^\s*(?:L[ÍI]NGUA\s+[A-ZÀ-Ú]+|CONHECIMENTOS\b.*|NO[ÇC][ÕO]ES\s+DE\b.*|ADMINISTRA[ÇC][ÃA]O\s*$|RACIOC[ÍI]NIO\s+L[ÓO]GICO\b.*|LEGISLA[ÇC][ÃA]O\b.*|DIREITO\s+[A-ZÀ-Ú]+|INFORM[ÁA]TICA\b.*)"
)
# Fim de linha de cabeçalho de seção ME que continua na linha de baixo.
PADRAO_CONECTIVO_FINAL_SECAO_ME = re.compile(
    r"(?:\b(?:E|OU|DE|DA|DO|DOS|DAS|AO|AOS|À|ÀS|NA|NO|NAS|NOS|EM|PARA|COM)|,)\s*$"
)
TAMANHO_MAXIMO_SECAO_ME = 60
# Rótulo de texto-base ME, sozinho na linha: "Texto CB1A1", "Texto CB1A3-II",
# "Texto 1A3", "Text CB1A2" (prova de inglês), "Textos CG1A1-I e CG1A1-II".
ROTULO_TEXTO_ME = r"[A-Z0-9]*\d[A-Z0-9]*(?:-[A-Z0-9]+)*"
PADRAO_TEXTO_ROTULO_ME = re.compile(
    rf"^\s*Text(?:os?|s)?\s+{ROTULO_TEXTO_ME}(?:\s*(?:,|e|and)\s*{ROTULO_TEXTO_ME})*\s*$"
)
# Citação do rótulo no enunciado ("mencionados no texto CB1A3-I", "of text
# CB1A2"); o rótulo em si é sensível a caixa.
PADRAO_CITA_TEXTO_ME = re.compile(
    rf"\btext(?:os?|s)?\s+(?-i:({ROTULO_TEXTO_ME}))", re.IGNORECASE
)
# Selo "Questão N" (tarja + ícone) e a faixa "PROVA OBJETIVA -- ... --" dos
# cadernos ME são imagens; não são figura da questão.
ALTURA_MAX_SELO_ME = 30.0
FOLGA_SELO_ME = 30.0
ALTURA_MAX_FAIXA_ME = 50.0
PADRAO_LETRA_ALT = re.compile(r"^(?:\(?([A-E])\)|([A-E])[\.\)]|([A-E])\s+)")
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
# Figuras vetoriais (5G.3): traços a até FOLGA_VETORIAL pt viram uma região;
# região com menos de TAMANHO_MINIMO_FIGURA_VETORIAL pt num dos lados é
# separador de grupo (duas linhas finas paralelas, ~4 pt de altura).
FOLGA_VETORIAL = 3.0
TAMANHO_MINIMO_FIGURA_VETORIAL = 10
ESPESSURA_LINHA = 2.0
# Legenda de figura/tabela vetorial (KAN-76): palavras-chave obrigatórias no início.
PADRAO_LEGENDA_TABELA = re.compile(
    r"^\s*(?:Tabela|Figura|Gr[aá]fico|Quadro)\b", re.IGNORECASE
)
DISTANCIA_MAX_LEGENDA_TABELA = 15.0
# Separador de colunas encurtado pela faixa "PROVA OBJETIVA" da 1ª página
# (~79% da altura): passa do corte de 80% e, encostado nos filetes, unia a
# coluna esquerda inteira numa caixa só. Traço vertical fino acima dessa
# fração da altura também é layout.
FRACAO_SEPARADOR_COLUNAS = 0.6
TOLERANCIA_BORDA = 2.0
LIMIAR_BRANCO = 0.97
ALTURA_RODAPE = 40
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

    def _eff_y0(b: dict) -> float:
        lines = [
            l
            for l in b.get("lines", [])
            if "".join(s["text"] for s in l.get("spans", [])).strip()
        ]
        return min((l["bbox"][1] for l in lines), default=b["bbox"][1])

    def coluna_direita(b) -> bool:
        return b["bbox"][0] >= meio - 12

    if _duas_colunas(texto, largura_pagina):
        return sorted(
            texto, key=lambda b: (coluna_direita(b), _eff_y0(b), b["bbox"][0])
        )
    return sorted(texto, key=lambda b: (_eff_y0(b), b["bbox"][0]))


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
                    # Primeiro span com texto: a letra da alternativa pode vir
                    # depois de um span " " (SEFA_PR_25, CG1 Q65).
                    primeiro_span=next(
                        (sp["text"] for sp in linha["spans"] if sp["text"].strip()),
                        sp0["text"],
                    )
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


def _ruptura_do_item(
    linhas: list[Linha], i_item: int, fim: int, margens: list[float], recuo: float
) -> int | None:
    """1ª linha de `linhas[i_item+1:fim]` que não continua o item: a anterior
    fecha frase e ela está fora do recuo do item (margem da coluna ou recuo
    de parágrafo). Item que anuncia material ("a seguir", ":") não rompe."""
    for j in range(i_item + 1, fim):
        anterior = linhas[j - 1].texto.rstrip()
        if not anterior.endswith(TERMINAIS_COMANDO) or anterior.endswith(":"):
            continue
        if _eh_continuacao(linhas[j], margens, recuo):
            continue
        if PADRAO_ITEM_ANUNCIA.search(juntar_linhas(linhas[i_item:j])):
            return None
        return j
    return None


# Comando que retoma um material ("Com base nessas informações", "desses
# dados") sem texto-base próprio: o material ficou em outro lugar.
PADRAO_COMANDO_ANAFORICO = re.compile(
    r"\b(?:n|d)?(?:ess|est)[ae]s?\s+(?:informa|dados|tabela|quadro|valores|situa)",
    re.IGNORECASE,
)


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
            # Linha de tabela do grupo seguinte pode cair no recuo do item
            # (célula a ~17 pt da margem, `072_STM_005_01` item 64) e parar a
            # volta acima: o texto-base que vem antes do novo comando começa
            # na 1ª linha, depois do fim de frase do item, fora do recuo.
            ruptura = _ruptura_do_item(linhas, i_item, corte, margens, recuo)
            if ruptura is not None:
                corte = ruptura
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
            # Resíduo: o comando novo retoma um material que não virou
            # texto-base, e o item anterior segue depois de fechar frase —
            # o material provavelmente ficou no item.
            if (
                grupo_atual["texto_base_ordem"] is None
                and PADRAO_COMANDO_ANAFORICO.search(grupo_atual["secao"] or "")
                and any(
                    linhas[j - 1].texto.rstrip().endswith((".", "!", "?"))
                    for j in range(i_item + 1, fim_item)
                )
            ):
                res.alertas.append(
                    {
                        "tipo": "possivel_preambulo_no_item",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "item": numero,
                        "texto": juntar_linhas(linhas[i_item:fim_item])[:300],
                    }
                )
    return res


# Múltipla escolha -------------------------------------------------------------


def _eh_multipla_escolha(
    linhas: list[Linha],
    esperados: list[int],
    gabarito: dict[int, str],
    tipos: dict[int, str] | None = None,
) -> bool:
    """Detecta se o caderno segue o formato de Múltipla Escolha (A-E ou A-D).

    Decide pelo tipo da grade (`GradeGabarito.tipos`, lido do rótulo `Item` ou
    `Questão`) quando ele cobre todos os números com um tipo só. As letras e a
    contagem de "Questão N" no caderno ficam para grade sem tipo ou mista.
    """
    tipos_grade = {(tipos or {}).get(n) for n in esperados}
    if len(tipos_grade) == 1 and None not in tipos_grade:
        return tipos_grade.pop() == QUESTAO_MULTIPLA_ESCOLHA
    if any(letra in {"A", "B", "D"} for letra in gabarito.values()):
        return True
    achados_me = sum(
        1
        for l in linhas
        if (m := PADRAO_QUESTAO_ME.match(l.texto)) and int(m.group(1)) in esperados
    )
    if achados_me >= max(1, len(esperados) // 2):
        return True
    return False


LETRAS_ALT = "ABCDE"


def _marcador_no_span(linha: Linha, letra: str) -> bool:
    """A letra vem num span próprio (o círculo com a letra do caderno real)."""
    return linha.primeiro_span.strip() in {
        letra,
        f"{letra})",
        f"({letra})",
        f"{letra}.",
    }


def _eh_marcador_alt(linha: Linha, letra: str, margens: list[float]) -> bool:
    """Marcador da alternativa `letra` (caminho de reserva).

    Além do span próprio, aceita a letra no mesmo span do texto só com
    pontuação explícita (`A)`, `(A)`, `A.`): a letra solta seguida de espaço
    é ambígua com o artigo ("A respeito das funções ..., assinale"). A linha
    tem de abrir bloco, estar em negrito ou na margem da coluna (`margens`,
    medidas no próprio trecho)."""
    if _marcador_no_span(linha, letra):
        return True
    if not re.match(rf"^\s*(?:\({letra}\)|{letra}[.)])\s", linha.texto):
        return False
    return bool(
        linha.negrito
        or linha.inicio_bloco
        or _na_margem_coluna(linha, margens, tolerancia=6.0)
    )


def _sequencia_alternativas(trecho: list[Linha], eh_marcador) -> list[tuple[str, int]]:
    """Primeira ocorrência de A, depois de B, ... na ordem do trecho.

    Depois, cada letra é reancorada (de trás para a frente) na última
    ocorrência antes da letra seguinte que está na coluna dela (mesmo x0): o
    enunciado que começa com o artigo "A" em span próprio, no recuo do
    parágrafo, não é a alternativa A (SEFA_PR_25, Q24 do cargo 4)."""
    achadas: list[tuple[str, int]] = []
    for i, linha in enumerate(trecho):
        if len(achadas) == len(LETRAS_ALT):
            break
        letra = LETRAS_ALT[len(achadas)]
        if eh_marcador(linha, letra):
            achadas.append((letra, i))
    for k in range(len(achadas) - 2, -1, -1):
        letra, inicio = achadas[k]
        _, i_seguinte = achadas[k + 1]
        x0_seguinte = trecho[i_seguinte].x0
        for i in range(i_seguinte - 1, inicio, -1):
            if abs(trecho[i].x0 - x0_seguinte) <= 1.5 and eh_marcador(trecho[i], letra):
                achadas[k] = (letra, i)
                break
    return achadas


def _localizar_alternativas_questao(
    trecho: list[Linha],
) -> list[tuple[str, int]]:
    """Localiza as alternativas A, B, C, D (e E) no trecho da questão.
    Devolve lista de tuplas `(letra, indice_no_trecho)`.
    """
    # 1. A letra num span próprio (formato dos cadernos reais).
    estritos = _sequencia_alternativas(trecho, _marcador_no_span)
    if len(estritos) in (4, 5):
        return estritos

    # 2. Reserva: letra no span do texto, com pontuação explícita.
    margens = _detectar_margens_colunas(trecho)
    return _sequencia_alternativas(
        trecho, lambda linha, letra: _eh_marcador_alt(linha, letra, margens)
    )


def _eh_cabecalho_secao_me(texto: str) -> bool:
    """Cabeçalho de seção ME: palavra-chave em caixa alta e nenhuma letra
    minúscula fora de parênteses (`LEGISLAÇÃO (Lei n.º ...)` vale; a
    alternativa quebrada em "LEGISLAÇÃO vigente" não)."""
    texto = texto.strip()
    if not PADRAO_CABECALHO_SECAO_ME.match(texto):
        return False
    return not re.search(r"[a-zà-ÿ]", re.sub(r"\([^)]*\)", "", texto))


# Cabeçalho de matéria pelo layout: o caderno ME centraliza o título na coluna
# e deixa alternativa e comando na margem. Sem isso, cabeçalho fora da lista
# de palavras-chave ("BANCO DE DADOS", BANRISUL) virava o fim da alternativa E.
# (margem, borda direita) das duas colunas, em pt, medidos nos cadernos reais.
COLUNAS_ME = ((28.4, 293.6), (304.3, 569.5))
TOLERANCIA_CENTRO_COLUNA_ME = 12.0
RECUO_MINIMO_CABECALHO_ME = 8.0
PADRAO_SIGLA_PARENTESES_ME = re.compile(r"\([A-ZÀ-Ú]+\)")
PADRAO_CARACTERES_CABECALHO_ME = re.compile(r"^[A-ZÀ-Ú ,\-–—]+$")


def _eh_cabecalho_layout_me(linha: Linha) -> bool:
    """Linha em caixa alta, sem dígito nem caractere de código, centralizada
    na coluna (ou em negrito) e afastada da margem. Sigla entre parênteses
    ("(AFO)") é aceita. Alternativa de código ("SUM()", "SELECT ...") fica na
    margem e não passa."""
    texto = linha.texto.strip()
    if not texto or re.search(r"\d", texto):
        return False
    sem_sigla = PADRAO_SIGLA_PARENTESES_ME.sub("", texto).strip()
    if not PADRAO_CARACTERES_CABECALHO_ME.match(sem_sigla):
        return False
    if len(re.findall(r"[A-ZÀ-Ú]", texto)) < 4:
        return False
    for margem, borda in COLUNAS_ME:
        if margem <= linha.x0 < borda:
            # Centro da coluna ou da largura do texto: título que atravessa as
            # duas colunas ("INOVAÇÃO EM TI NO SISTEMA FINANCEIRO", BANRISUL_004).
            centros = [(m + b) / 2 for m, b in COLUNAS_ME]
            centros.append((COLUNAS_ME[0][0] + COLUNAS_ME[-1][1]) / 2)
            centro_linha = (linha.x0 + linha.x1) / 2
            centralizada = any(
                abs(centro_linha - c) <= TOLERANCIA_CENTRO_COLUNA_ME for c in centros
            )
            afastada = linha.x0 - margem >= RECUO_MINIMO_CABECALHO_ME
            return afastada and (centralizada or linha.negrito)
    return False


def _eh_rotulo_texto_me(texto: str) -> bool:
    return PADRAO_TEXTO_ROTULO_ME.match(texto) is not None


def _so_maiusculas(texto: str) -> bool:
    """Tem letra e nenhuma minúscula fora de parênteses."""
    texto = re.sub(r"\([^)]*\)", "", texto.strip())
    return bool(re.search(r"[A-ZÀ-Ú]", texto)) and not re.search(r"[a-zà-ÿ]", texto)


def localizar_questoes_me(
    linhas: list[Linha],
    esperados: list[int],
    alertas: list[dict] | None = None,
) -> dict[int, tuple[int, bool]]:
    """Localiza as linhas onde cada questão de múltipla escolha começa (`Questão N`).
    Devolve `{numero: (indice_da_linha, estrito)}`.
    """
    achados: dict[int, tuple[int, bool]] = {}
    candidatos_por_numero: dict[int, list[int]] = {}
    for i, linha in enumerate(linhas):
        m = PADRAO_QUESTAO_ME.match(linha.texto)
        if m:
            num = int(m.group(1))
            candidatos_por_numero.setdefault(num, []).append(i)

    pos = 0
    numeros_duplicados: set[int] = set()
    for numero in esperados:
        cands = candidatos_por_numero.get(numero, [])
        if len(cands) == 1:
            idx = cands[0]
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
        elif len(cands) > 1:
            numeros_duplicados.add(numero)
            if alertas is not None:
                alertas.append(
                    {
                        "tipo": "marcador_duplicado",
                        "severidade": SEVERIDADE_BLOQUEANTE,
                        "item": numero,
                        "indices": cands,
                        "linhas": [linhas[i].texto[:100] for i in cands],
                    }
                )
    return achados


def marcadores_fora_do_gabarito_me(
    linhas: list[Linha],
    esperados: list[int],
) -> list[int]:
    """Questões ME delimitadas por 'Questão N' que continuam a sequência
    do gabarito para fora dela (max+1, max+2... ou min-1...).
    """
    if not esperados:
        return []
    questoes_no_texto = {
        int(m.group(1)) for l in linhas if (m := PADRAO_QUESTAO_ME.match(l.texto))
    }
    extras = []
    for passo, inicio in ((1, esperados[-1] + 1), (-1, esperados[0] - 1)):
        n = inicio
        while n > 0 and n in questoes_no_texto:
            extras.append(n)
            n += passo
    return sorted(extras)


def _processar_preambulo_me(
    linhas_preambulo: list[Linha],
) -> tuple[str | None, list[Linha] | None]:
    """Separa o cabeçalho de seção e as linhas de texto-base do preâmbulo ME."""
    if not linhas_preambulo:
        return None, None
    secao = None
    inicio_base = 0
    l0 = linhas_preambulo[0].texto.strip()
    preenchidas = [l for l in linhas_preambulo if l.texto.strip()]
    if _eh_cabecalho_secao_me(l0) or _eh_cabecalho_layout_me(linhas_preambulo[0]):
        secao = l0
        inicio_base = 1
        # Cabeçalho quebrado: "NOÇÕES DE CONTABILIDADE APLICADA AO" + "SETOR
        # PÚBLICO (CASP)" (SEFA_PR_25). Só junta depois de conectivo.
        while (
            inicio_base < len(linhas_preambulo)
            and PADRAO_CONECTIVO_FINAL_SECAO_ME.search(secao)
            and _so_maiusculas(linhas_preambulo[inicio_base].texto)
            and not _eh_rotulo_texto_me(linhas_preambulo[inicio_base].texto)
        ):
            secao = f"{secao} {linhas_preambulo[inicio_base].texto.strip()}"
            inicio_base += 1
    elif (
        len(preenchidas) == 1
        and preenchidas[0] is linhas_preambulo[0]
        and len(l0) <= TAMANHO_MAXIMO_SECAO_ME
        and _so_maiusculas(l0)
        and not _eh_rotulo_texto_me(l0)
    ):
        # Preâmbulo de uma linha só, em caixa alta, sem palavra-chave: a área
        # do caderno específico ("ECONOMIA", "CONTABILIDADE", "ANALISTA
        # FAZENDÁRIO" no SEFA_PR_25). Antes virava texto-base de toda a seção.
        secao = l0
        inicio_base = 1

    resto = linhas_preambulo[inicio_base:]
    if not resto:
        return secao, None

    txt_resto = juntar_linhas(resto, paragrafos=True)
    if (
        len(resto) <= 2
        and not _eh_rotulo_texto_me(resto[0].texto)
        and len(txt_resto) < 80
        and _eh_cabecalho_secao_me(resto[0].texto)
    ):
        secao = txt_resto
        return secao, None
    # Só linha vazia: não vira texto-base vazio.
    if not txt_resto.strip():
        return secao, None

    return secao, resto


def _segmentar_me(
    linhas: list[Linha], achados: dict[int, tuple[int, bool]]
) -> ResultadoSegmentacao:
    res = ResultadoSegmentacao()
    ordem_itens = sorted(achados, key=lambda n: achados[n][0])
    if not ordem_itens:
        return res
    indices = [achados[n][0] for n in ordem_itens]

    # Alcance do texto-base no ME (diferente do grupo C/E, que divide o
    # texto até o próximo comando):
    # - a questão que cita o rótulo ("texto CB1A3-I") aponta para ele;
    # - o texto que abre a seção (antes da 1ª questão dela, ex.: o texto de
    #   Língua Portuguesa) vale para a seção inteira;
    # - o texto no meio da seção vale só para a questão logo depois dele e
    #   para as que o citam. Herdar até a próxima seção daria o "Texto 1A3"
    #   do SEFA_PR (seção única) a 23 questões sem relação com ele.
    secao_atual: str | None = None
    texto_base_atual: int | None = None
    texto_base_abre_secao = False
    primeira_apos_texto = False
    questoes_na_secao = 0
    # Rótulo impresso ("CB1A3-I") -> ordem do texto-base.
    ordem_por_rotulo: dict[str, int] = {}

    def _tratar_preambulo(inicio: int, fim: int, num_seguinte: int) -> None:
        nonlocal secao_atual, texto_base_atual, texto_base_abre_secao
        nonlocal primeira_apos_texto, questoes_na_secao
        if inicio >= fim:
            return
        linhas_preambulo = linhas[inicio:fim]
        sec, base_lines = _processar_preambulo_me(linhas_preambulo)
        if sec:
            secao_atual = sec
            questoes_na_secao = 0
            tam_sec = len(linhas_preambulo) - len(base_lines or [])
            for k in range(inicio, inicio + tam_sec):
                res.dono_linha[k] = ("comando", num_seguinte)
        if base_lines:
            ordem_base = len(res.textos_base)
            base_texto = juntar_linhas(base_lines, paragrafos=True)
            if _eh_rotulo_texto_me(base_lines[0].texto):
                for rotulo in re.findall(ROTULO_TEXTO_ME, base_lines[0].texto):
                    ordem_por_rotulo.setdefault(rotulo, ordem_base)
            res.textos_base.append(
                {
                    "ordem": ordem_base,
                    "texto": base_texto,
                    "paginas": sorted({l.pagina + 1 for l in base_lines}),
                    "linhas_brutas": [l.texto for l in base_lines],
                    "figuras": [],
                }
            )
            idx_base_start = fim - len(base_lines)
            for k in range(idx_base_start, fim):
                res.dono_linha[k] = ("texto_base", ordem_base)
            texto_base_atual = ordem_base
            texto_base_abre_secao = questoes_na_secao == 0
            primeira_apos_texto = True
        elif sec and not base_lines:
            texto_base_atual = None

    _tratar_preambulo(0, indices[0], ordem_itens[0])

    for pos, numero in enumerate(ordem_itens):
        i_item = indices[pos]
        proximo = indices[pos + 1] if pos + 1 < len(indices) else len(linhas)
        trecho = linhas[i_item:proximo]

        alts_loc = _localizar_alternativas_questao(trecho)
        letras = [a[0] for a in alts_loc]

        if letras not in (["A", "B", "C", "D", "E"], ["A", "B", "C", "D"]):
            res.alertas.append(
                {
                    "tipo": "alternativas_invalidas",
                    "severidade": SEVERIDADE_BLOQUEANTE,
                    "item": numero,
                    "encontradas": letras,
                }
            )

        if not alts_loc:
            fim_item = proximo
            enunciado = juntar_linhas(trecho)
            enunciado = PADRAO_QUESTAO_ME.sub("", enunciado, count=1).strip(" -.:\t")
            alts_res: list[dict] = []
        else:
            idx_alt_a = alts_loc[0][1]
            enun_linhas = trecho[1:idx_alt_a]
            m_header = PADRAO_QUESTAO_ME.match(trecho[0].texto)
            sobra_header = (
                trecho[0].texto[m_header.end() :].strip(" -.:\t") if m_header else ""
            )
            enunciado = juntar_linhas(enun_linhas)
            if sobra_header:
                enunciado = (
                    f"{sobra_header} {enunciado}".strip() if enunciado else sobra_header
                )

            last_j = alts_loc[-1][1]
            corte_tb = None
            for k in range(last_j + 1, len(trecho)):
                l = trecho[k]
                if (
                    _eh_cabecalho_secao_me(l.texto)
                    or _eh_cabecalho_layout_me(l)
                    or _eh_rotulo_texto_me(l.texto)
                    or PADRAO_FAIXA_SECAO.match(l.texto.strip())
                ):
                    corte_tb = k
                    break

            fim_item = corte_tb if corte_tb is not None else len(trecho)

            alts_res = []
            for alt_idx, (letra, j_start) in enumerate(alts_loc):
                if alt_idx + 1 < len(alts_loc):
                    j_end = alts_loc[alt_idx + 1][1]
                else:
                    j_end = fim_item
                alt_lines = trecho[j_start:j_end]
                alt_raw = juntar_linhas(alt_lines)
                alt_clean = re.sub(
                    rf"^\s*(?:\(?{letra}\)|{letra}[\.\)]|{letra})\s*", "", alt_raw
                ).strip()
                alts_res.append({"letra": letra, "texto": alt_clean})

        citados = [
            ordem_por_rotulo[r]
            for r in PADRAO_CITA_TEXTO_ME.findall(enunciado)
            if r in ordem_por_rotulo
        ]
        if citados:
            texto_base_item = citados[0]
        elif texto_base_abre_secao or primeira_apos_texto:
            texto_base_item = texto_base_atual
        else:
            texto_base_item = None
        primeira_apos_texto = False
        questoes_na_secao += 1

        brutas = [linha.texto for linha in trecho[:fim_item]]
        res.itens[numero] = {
            "numero": numero,
            "enunciado": enunciado,
            "tipo": "multipla_escolha",
            "alternativas": alts_res,
            "secao": secao_atual,
            "texto_base_ordem": texto_base_item,
            "texto_base_herdado": False,
            "grupo": numero,
            "marcador_estrito": achados[numero][1],
            "pagina": linhas[i_item].pagina + 1,
            "linhas_brutas": brutas,
            "figuras": [],
        }
        for k in range(i_item, i_item + fim_item):
            res.dono_linha[k] = ("item", numero)

        if fim_item < len(trecho) and pos + 1 < len(ordem_itens):
            _tratar_preambulo(i_item + fim_item, proximo, ordem_itens[pos + 1])

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


def _desenho_invisivel(desenho: dict) -> bool:
    """Preenchimento branco sem traço (fundo de bloco) não aparece na página."""
    preenchimento = desenho.get("fill")
    return (
        desenho.get("color") is None
        and preenchimento is not None
        and min(preenchimento) >= LIMIAR_BRANCO
    )


def _agrupar_proximos(
    rects: list[pymupdf.Rect], folga: float
) -> list[list[pymupdf.Rect]]:
    """Fecho transitivo de retângulos a até `folga` pt um do outro."""
    grupos: list[tuple[pymupdf.Rect, list[pymupdf.Rect]]] = [
        (pymupdf.Rect(r), [r]) for r in rects
    ]
    mudou = True
    while mudou:
        mudou = False
        saida: list[tuple[pymupdf.Rect, list[pymupdf.Rect]]] = []
        for caixa, membros in grupos:
            for outra, outros in saida:
                if (outra + (-folga, -folga, folga, folga)).intersects(caixa):
                    outra.include_rect(caixa)
                    outros.extend(membros)
                    mudou = True
                    break
            else:
                saida.append((caixa, membros))
        grupos = saida
    return [membros for _, membros in grupos]


def _so_moldura(membros: list[pymupdf.Rect], caixa: pymupdf.Rect) -> bool:
    """Grupo cujos traços estão todos sobre a borda da própria caixa: é uma
    moldura em volta de um bloco (retângulo ou 4 linhas), não uma figura.
    Tabela e gráfico têm traço interno (linha de grade, eixo, célula)."""
    t = TOLERANCIA_BORDA
    for r in membros:
        caixa_inteira = (
            abs(r.x0 - caixa.x0) < t
            and abs(r.x1 - caixa.x1) < t
            and abs(r.y0 - caixa.y0) < t
            and abs(r.y1 - caixa.y1) < t
        )
        horizontal_na_borda = r.height <= ESPESSURA_LINHA and (
            abs(r.y0 - caixa.y0) < t or abs(r.y1 - caixa.y1) < t
        )
        vertical_na_borda = r.width <= ESPESSURA_LINHA and (
            abs(r.x0 - caixa.x0) < t or abs(r.x1 - caixa.x1) < t
        )
        if not (caixa_inteira or horizontal_na_borda or vertical_na_borda):
            return False
    return True


def _linhas_texto_da_pagina(page) -> list[dict]:
    """Linhas de texto visuais da página com coordenadas e texto."""
    linhas = []
    blocos = page.get_text("dict").get("blocks", [])
    for b in ordenar_blocos(blocos, page.rect.width):
        if b.get("type") != 0:
            continue
        atual = None
        for l in b.get("lines", []):
            texto = _texto_spans(l.get("spans", [])).strip()
            if not texto:
                continue
            x0, y0, x1, y1 = l["bbox"]
            centro = (y0 + y1) / 2
            if (
                atual is not None
                and abs(centro - (atual["y0"] + atual["y1"]) / 2)
                <= TOLERANCIA_MESMA_LINHA
            ):
                atual["texto"] = f"{atual['texto']} {texto}"
                atual["x0"] = min(atual["x0"], x0)
                atual["x1"] = max(atual["x1"], x1)
                atual["y0"] = min(atual["y0"], y0)
                atual["y1"] = max(atual["y1"], y1)
                atual["width"] = atual["x1"] - atual["x0"]
            else:
                atual = {
                    "x0": x0,
                    "y0": y0,
                    "x1": x1,
                    "y1": y1,
                    "texto": texto,
                    "width": x1 - x0,
                }
                linhas.append(atual)
    return linhas


def _detectar_legenda_figura_vetorial(
    caixa: pymupdf.Rect, linhas_pagina: list[dict]
) -> list[dict]:
    """Detecta estritamente a legenda de uma tabela/figura vetorial (KAN-76).

    Condições estritas do dono:
    - Linha de texto logo acima da caixa da tabela (distância <= 15 pt).
    - Linha curta (largura < largura da tabela + 10 pt).
    - Alinhada ou centrada sobre a tabela (x0 >= caixa.x0 - 10 e x1 <= caixa.x1 + 10).
    - Título obrigatoriamente começa com: Tabela, Figura, Gráfico ou Quadro.
    - Se a linha seguinte (entre a linha do título e o início do desenho) for uma
      linha curta de subtítulo (como 'Clientes', 'Pedidos', 'Resultado'),
      engloba ambas.
    - Sem essas regras estritas, não engloba nada.
    """
    candidatas = [
        l
        for l in linhas_pagina
        if l["y1"] <= caixa.y0 + 2.0
        and l["y1"] >= caixa.y0 - 50.0
        and l["x0"] >= caixa.x0 - 10.0
        and l["x1"] <= caixa.x1 + 10.0
    ]
    candidatas.sort(key=lambda l: l["y1"], reverse=True)
    if not candidatas:
        return []

    l1 = candidatas[0]
    # Linha mais próxima colada ao topo da tabela
    if not (
        caixa.y0 - l1["y1"] <= DISTANCIA_MAX_LEGENDA_TABELA
        and l1["width"] < caixa.width + 10.0
    ):
        return []

    # Caso 1: a linha colada já é o título (ex.: "Tabela I - Clientes" ou "Quadro 1")
    if PADRAO_LEGENDA_TABELA.match(l1["texto"]):
        return [l1]

    # Caso 2: a linha colada é um subtítulo e a linha imediatamente acima dela é o título
    if len(candidatas) > 1:
        l0 = candidatas[1]
        if (
            l1["y0"] - l0["y1"] <= DISTANCIA_MAX_LEGENDA_TABELA
            and l0["width"] < caixa.width + 10.0
            and PADRAO_LEGENDA_TABELA.match(l0["texto"])
        ):
            return [l0, l1]

    return []


def figuras_vetoriais_da_pagina(
    page, figuras_raster: list[pymupdf.Rect] | None = None
) -> list[pymupdf.Rect]:
    """Regiões desenhadas com vetores (tabelas com borda, gráficos,
    diagramas): traços visíveis próximos unidos numa caixa.

    Fica de fora o layout do caderno: cabeçalho/rodapé, traços de quase a
    página inteira (separador de colunas, inclusive o curto da 1ª página:
    traço vertical fino com mais de `FRACAO_SEPARADOR_COLUNAS` da altura), os separadores duplos entre
    grupos (finos demais depois de unidos), molduras sem traço interno e o
    que já é figura raster. A caixa devolvida tem uma folga para a borda da
    tabela sair no recorte.

    Legenda de tabela/gráfico (KAN-76): se houver legenda estritamente detectada
    logo acima da tabela, o topo do recorte engloba a legenda."""
    altura, largura = page.rect.height, page.rect.width
    rects = []
    for desenho in page.get_drawings():
        r = pymupdf.Rect(desenho["rect"])
        if _desenho_invisivel(desenho):
            continue
        if r.y1 <= ALTURA_CABECALHO or r.y0 >= altura - ALTURA_RODAPE:
            continue
        if r.width > 0.8 * largura or r.height > 0.8 * altura:
            continue
        if r.width < ESPESSURA_LINHA and r.height > FRACAO_SEPARADOR_COLUNAS * altura:
            continue
        # Linha traçada (não preenchida) tem retângulo de altura/largura 0,
        # que o PyMuPDF trata como vazio em `intersects`/`include_rect`.
        rects.append(r + (-0.5, -0.5, 0.5, 0.5))
    regioes = []
    linhas_texto = None
    words = None
    for membros in _agrupar_proximos(rects, FOLGA_VETORIAL):
        caixa = pymupdf.Rect(membros[0])
        for r in membros[1:]:
            caixa.include_rect(r)
        if (
            caixa.width < TAMANHO_MINIMO_FIGURA_VETORIAL
            or caixa.height < TAMANHO_MINIMO_FIGURA_VETORIAL
            or _so_moldura(membros, caixa)
        ):
            continue
        if any(caixa.intersects(f) for f in figuras_raster or []):
            continue
        r_final = (caixa + (-2, -2, 2, 2)) & page.rect

        if linhas_texto is None:
            linhas_texto = _linhas_texto_da_pagina(page)
        legenda = _detectar_legenda_figura_vetorial(caixa, linhas_texto)

        if words is None:
            words = page.get_text("words")

        if legenda:
            topo_legenda_y0 = legenda[0]["y0"]
            y_pretendido = topo_legenda_y0 - 2.0
            palavras_acima = [
                w
                for w in words
                if w[0] < r_final.x1
                and w[2] > r_final.x0
                and w[1] < topo_legenda_y0
                and w[3] > y_pretendido
            ]
            if palavras_acima:
                r_final.y0 = max(w[3] for w in palavras_acima) + 0.2
            else:
                r_final.y0 = max(0.0, y_pretendido)
            min_x0 = min(l["x0"] for l in legenda)
            max_x1 = max(l["x1"] for l in legenda)
            r_final.x0 = min(r_final.x0, max(0.0, min_x0 - 2.0))
            r_final.x1 = min(page.rect.width, max(r_final.x1, max_x1 + 2.0))
        else:
            # Se a folga superior invade texto acima do desenho, começa abaixo dele
            # para não cortar texto acima ao meio (KAN-75).
            palavras_acima = [
                w
                for w in words
                if w[0] < r_final.x1
                and w[2] > r_final.x0
                and w[1] < caixa.y0
                and w[3] > r_final.y0
            ]
            if palavras_acima:
                r_final.y0 = max(w[3] for w in palavras_acima) + 0.2
        regioes.append(r_final)
    return sorted(regioes, key=lambda r: (r.y0, r.x0))


def _figura_decorativa_me(
    rect: pymupdf.Rect, pagina: int, linhas: list[Linha], largura_pagina: float
) -> bool:
    """Imagem de layout do caderno ME, não figura de questão.

    - Faixa "PROVA OBJETIVA -- CONHECIMENTOS ... --" de largura total (mais
      alta que as tarjas que `figuras_da_pagina` já descarta).
    - Selo da questão: tarja e ícone na altura da linha "Questão N" (até
      `ALTURA_MAX_SELO_ME` pt de altura, a até `FOLGA_SELO_ME` pt dela na
      horizontal). Sem o filtro, o selo de uma questão logo abaixo do
      cabeçalho de seção virava um texto-base vazio.
    """
    if rect.width > 0.8 * largura_pagina and rect.height < ALTURA_MAX_FAIXA_ME:
        return True
    if rect.height > ALTURA_MAX_SELO_ME:
        return False
    for linha in linhas:
        if linha.pagina != pagina or not PADRAO_QUESTAO_ME.match(linha.texto):
            continue
        sobrepoe_v = min(linha.y1, rect.y1) - max(linha.y0, rect.y0) > 0
        perto_h = (
            rect.x0 <= linha.x1 + FOLGA_SELO_ME and rect.x1 >= linha.x0 - FOLGA_SELO_ME
        )
        if sobrepoe_v and perto_h:
            return True
    return False


def dono_da_figura(
    rect: pymupdf.Rect,
    pagina: int,
    linhas: list[Linha],
    dono_linha: dict[int, tuple[str, int]],
    ignorar: list[pymupdf.Rect] | None = None,
) -> tuple[str, int] | None:
    """Trecho da linha logo acima da figura na mesma coluna (sobreposição
    horizontal); sem linha acima, o da primeira linha abaixo.

    Exceção: figura entre o fim de um item e o preâmbulo do grupo seguinte
    (linha acima = item, linha abaixo = texto-base/comando) é do grupo
    seguinte — é o caso de "Considerando as figuras A e B, julgue ...". A
    figura do próprio item tem texto do item depois dela ("Nesse caso, ...")
    ou o próximo item logo abaixo.

    `ignorar`: regiões de figura vetorial da página. O texto dentro de uma
    tabela desenhada é da própria tabela, não vizinho dela; sem isso, a
    primeira de duas tabelas empilhadas acharia a segunda como linha abaixo."""
    acima, abaixo = None, None
    for i, linha in enumerate(linhas):
        if linha.pagina != pagina or i not in dono_linha:
            continue
        centro = pymupdf.Point((linha.x0 + linha.x1) / 2, (linha.y0 + linha.y1) / 2)
        if any(centro in r for r in ignorar or []):
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


# Caderno com gabarito ---------------------------------------------------------

# "PROVA E GABARITO" no mesmo PDF (`caderno_com_gabarito` do inventário,
# ADR-037). Não há grade: a resposta vem impressa junto de cada questão. Os
# formatos abaixo foram conferidos nos PDFs reais da 8.M/S3:
# - justificativa C/E (TC_DF_23, PC_DF_24): "JUSTIFICATIVA - Certo. ..." até
#   "<FimJust>", logo depois do item;
# - justificativa ME (CAESB_24, PM_DF_25, SEPLAD_DF_22): "||JUSTIFICATIVAS||"
#   (ou "JUSTIFICATIVAS") e uma entrada por alternativa, em ordem,
#   "||A|| - Incorreta. ... */" (ou "A - Errado. ... */");
# - código C/E (AGSUS_25_CCE, AGSUS_26_RD): "1 J2418111 - ERRADO | <item>",
#   com o veredito na linha do item ("4 B0702949 – CORRETO - ANULADO | ..."
#   na anulada) e "GABARITO DEFINITIVO" no topo da página.
# As justificativas são do gabarito **preliminar** (o link diz "GABARITO
# PRELIMINAR COM JUSTIFICATIVAS"); o definitivo, quando ligado, tem preferência.
# Fora daqui e sem gabarito (falha explícita): a tabela "ITEM N / GABARITO:
# CERTO" (AGSUS_25_EC) e o rótulo "CORRETA"/"ERRADA" por alternativa (AGU_23).
FORMATO_JUSTIFICATIVA = "justificativa"
FORMATO_CODIGO_CE = "codigo_ce"
# Sensíveis a caixa: "Justificativa" no corpo de uma questão não é marca.
PADRAO_JUSTIFICATIVA_CE = re.compile(r"^\s*JUSTIFICATIVA(?!S)\b")
PADRAO_FIM_JUSTIFICATIVA_CE = re.compile(r"<FimJust>")
PADRAO_JUSTIFICATIVAS_ME = re.compile(r"^\s*(?:\|\|)?JUSTIFICATIVAS(?:\|\|)?\s*$")
# "||E|| Incorreta." (CAESB_24) vem sem o travessão; "A - Errado." precisa
# dele, senão casaria a própria alternativa ("A texto").
PADRAO_ENTRADA_ME = re.compile(
    r"^\s*(?:\|\|([A-E])\|\|\s*[-–]?|([A-E])\s*[-–])\s*(.*)$"
)
# Marca de justificativa que não pode sobrar no texto da questão.
PADRAO_MARCA_JUSTIFICATIVA = re.compile(r"\bJUSTIFICATIVAS?\b|<FimJust>|\|\|[A-E]\|\|")
FIM_ENTRADA_ME = "*/"
PADRAO_CODIGO_ITEM = re.compile(
    r"^(\s*\d+\s+)[A-Z]{1,3}\d{5,8}\s*[-–]\s*(CORRETO|ERRADO|ANULADO)"
    r"(\s*[-–]\s*ANULADO)?\s*\|\s*"
)
# Início de item no formato código, com ou sem veredito legível.
PADRAO_CODIGO_ITEM_INICIO = re.compile(r"^\s*\d+\s+[A-Z]{1,3}\d{5,8}\s*[-–]")
PADRAO_CABECALHO_GABARITO = re.compile(r"^\s*GABARITO\s+(DEFINITIVO|PRELIMINAR)\s*$")
# Cabeçalho do bloco no formato código, entre a faixa "-- BLOCO 1 | CB1 --" e
# o comando do item 1: "PROVA DE CONHECIMENTOS ...", "Curso: ...",
# "<<N. Cargo/>> <<Nome do Cargo/>>" e a linha do cargo ("CB1 CONHECIMENTOS
# BÁSICOS ...", "21 CARGO 21: ...", "60 A 70 CONHECIMENTOS ...").
PADRAO_CABECALHO_BLOCO_CODIGO = re.compile(
    r"^\s*(?:PROVA DE CONHECIMENTOS\b|Curso:|<<N\. Cargo/>>)"
)
# Veredito no começo da justificativa, já normalizado: "Certo.", "CERTO,
# pois", "Incorreta.", "Opção incorreta.", "Errada".
PADRAO_VEREDITO = re.compile(
    r"^(?:opcao )?(?:(certo|certa|correto|correta)|(errado|errada|incorreto|incorreta)"
    r"|(anulado|anulada))\b"
)
VEREDITO_CERTO = "certo"
VEREDITO_ERRADO = "errado"
VEREDITO_ANULADO = "anulado"
LETRA_DO_VEREDITO_CE = {
    VEREDITO_CERTO: "C",
    VEREDITO_ERRADO: "E",
    VEREDITO_ANULADO: "X",
}
MIN_ALTERNATIVAS_ME = 4
MAX_LINHAS_ANTES_ENTRADA_ME = 12
MAX_FRASES_ANTES_VEREDITO = 4
# Maior número de item nos cadernos do piloto e da amostra: 160 (TC_DF_24).
MAX_NUMERO_ITEM = 300


@dataclass
class GabaritoEmbutido:
    """Respostas impressas no próprio caderno (`separar_gabarito_embutido`)."""

    formato: str
    versao: str
    respostas: dict[int, str] = field(default_factory=dict)
    tipos: dict[int, str] = field(default_factory=dict)
    alertas: list[str] = field(default_factory=list)
    # Fecho que faltava no PDF e foi presumido (informativo).
    avisos: list[str] = field(default_factory=list)
    # Entradas da justificativa ME por questão: tem de bater com as
    # alternativas que a segmentação acha.
    alternativas: dict[int, int] = field(default_factory=dict)
    # Trechos tirados do caderno (cada justificativa, cada cabeçalho): não
    # são questão nem texto-base.
    trechos: list[list[Linha]] = field(default_factory=list)

    @property
    def removidas(self) -> list[Linha]:
        return [linha for trecho in self.trechos for linha in trecho]

    def grade(self) -> GradeGabarito:
        return GradeGabarito(
            codigo_caderno=None,
            respostas=dict(self.respostas),
            alertas=list(self.alertas),
            tipos=dict(self.tipos),
        )


def _veredito(texto: str) -> str | None:
    """Veredito no começo do texto ou de uma das primeiras frases: há
    entrada com o tópico antes ("5.1 Relação professor/aluno. Incorreta.",
    "3 Macroeconomia. 3.1 As contas nacionais;_ERRADA.")."""
    # "...(artigos 101 a 105-B)_INCORRETA." (PC_PE_23): o "_" separa o tópico.
    frases = re.split(r"(?<=\.)\s+|_", texto.strip())
    for frase in frases[:MAX_FRASES_ANTES_VEREDITO]:
        m = PADRAO_VEREDITO.match(normalizar(frase))
        if m:
            if m.group(1):
                return VEREDITO_CERTO
            return VEREDITO_ERRADO if m.group(2) else VEREDITO_ANULADO
    return None


def _numero_do_item(linha: Linha) -> int | None:
    """Número do item C/E quando a linha é o marcador (número num span
    próprio). Número fora da faixa dos cadernos é célula de tabela."""
    span = linha.primeiro_span.strip()
    if (
        span.isdigit()
        and 0 < int(span) <= MAX_NUMERO_ITEM
        and _casa_numero(linha, int(span))
    ):
        return int(span)
    return None


def _fim_justificativa_ce(
    linhas: list[Linha], inicio: int, margens: list[float]
) -> tuple[int, bool] | None:
    """`(fim, presumido)` da justificativa de `inicio`: a linha `<FimJust>`;
    sem ela (TC_DF_23, PC_DF_24 têm itens assim), a linha antes da primeira
    na margem da coluna (o próximo item ou comando: a justificativa tem o
    recuo do item). None se outra justificativa começa antes disso."""
    for k in range(inicio, len(linhas)):
        if PADRAO_FIM_JUSTIFICATIVA_CE.search(linhas[k].texto):
            return _absorver_fragmentos(linhas, k), False
        if k == inicio:
            continue
        if PADRAO_JUSTIFICATIVA_CE.match(linhas[k].texto):
            return None
        if _na_margem_coluna(linhas[k], margens):
            return k - 1, True
    return None


def _letra_entrada_me(linha: Linha) -> tuple[str, str] | None:
    m = PADRAO_ENTRADA_ME.match(linha.texto)
    return (m.group(1) or m.group(2), m.group(3)) if m else None


def _entradas_justificativa_me(
    linhas: list[Linha], inicio: int
) -> tuple[int, dict[str, str | None]] | None:
    """`(fim, {letra: veredito})` das entradas `||A|| - ... */` que seguem o
    cabeçalho `JUSTIFICATIVAS` em `inicio`, com as letras em ordem a partir
    de A. A entrada acaba no `*/` (há `*//`) ou, quando ele falta, logo antes
    da entrada da letra seguinte; a última precisa do `*/`, senão não há como
    saber onde ela acaba. Antes de cada entrada podem vir pedaços de fórmula
    dela (a ordem visual os põe antes). None se a sequência não fecha antes
    de outra questão."""

    def fim_do_bloco(k: int) -> bool:
        return k >= len(linhas) or bool(PADRAO_QUESTAO_ME.match(linhas[k].texto))

    def fim_presumido(k: int) -> bool:
        # O que separa uma questão da seguinte no ME: o selo "Questão N", o
        # rótulo do texto-base ou o cabeçalho de seção.
        return fim_do_bloco(k) or bool(
            _eh_rotulo_texto_me(linhas[k].texto)
            or _eh_cabecalho_secao_me(linhas[k].texto)
        )

    def proxima_entrada(k: int, letra: str) -> int | None:
        for j in range(k, min(k + MAX_LINHAS_ANTES_ENTRADA_ME, len(linhas))):
            if fim_presumido(j):
                return None
            entrada = _letra_entrada_me(linhas[j])
            if entrada:
                return j if entrada[0] == letra else None
        return None

    k = inicio + 1
    vereditos: dict[str, str | None] = {}
    fim = None
    presumido = False
    for i_letra, letra in enumerate(LETRAS_ALT):
        achada = proxima_entrada(k, letra)
        if achada is None:
            break
        k = inicio_entrada = achada
        seguinte = LETRAS_ALT[i_letra + 1 : i_letra + 2]
        while FIM_ENTRADA_ME not in linhas[k].texto:
            proxima = _letra_entrada_me(linhas[k + 1]) if k + 1 < len(linhas) else None
            if seguinte and proxima and proxima[0] == seguinte:
                break
            if k + 1 >= len(linhas) or fim_presumido(k + 1):
                # Última entrada sem `*/`: acaba antes do que abre a questão
                # seguinte. Entrada do meio sem nada disso é irrecuperável.
                if len(vereditos) + 1 < MIN_ALTERNATIVAS_ME:
                    return None
                presumido = True
                break
            k += 1
        texto_entrada = " ".join(
            linha.texto
            for linha in linhas[inicio_entrada : min(k, inicio_entrada + 2) + 1]
        )
        vereditos[letra] = _veredito(_letra_entrada_me(linhas[inicio_entrada])[1]) or (
            _veredito(PADRAO_ENTRADA_ME.match(texto_entrada).group(3))
        )
        fim = k
        k += 1
        if presumido:
            break
    if fim is None:
        return None
    if not presumido:
        fim = _absorver_fragmentos(linhas, fim)
    return fim, vereditos, presumido


def _absorver_fragmentos(linhas: list[Linha], fim: int) -> int:
    """Estende o fim do trecho às linhas seguintes que ficam na mesma página e
    coluna e não abaixo da linha de fecho: pedaços de fórmula (índice, fração)
    que a ordem visual põe depois do `*/` ou do `<FimJust>`."""
    fecho = linhas[fim]
    coluna = fecho.x0 >= LIMITE_COLUNA_DIREITA
    while fim + 1 < len(linhas):
        seguinte = linhas[fim + 1]
        if (
            seguinte.pagina != fecho.pagina
            or (seguinte.x0 >= LIMITE_COLUNA_DIREITA) != coluna
            or (seguinte.y0 + seguinte.y1) / 2 > fecho.y1 + TOLERANCIA_MESMA_LINHA
            or PADRAO_QUESTAO_ME.match(seguinte.texto)
            or PADRAO_JUSTIFICATIVA_CE.match(seguinte.texto)
            or _eh_rotulo_texto_me(seguinte.texto)
        ):
            break
        fim += 1
    return fim


def _resposta_me(vereditos: dict[str, str | None]) -> str | None:
    """A única alternativa certa; `X` se todas vêm anuladas; None se ambíguo
    ou se faltam entradas (o caderno ME tem 4 ou 5 alternativas)."""
    if len(vereditos) < MIN_ALTERNATIVAS_ME:
        return None
    if set(vereditos.values()) == {VEREDITO_ANULADO}:
        return "X"
    certas = [letra for letra, v in vereditos.items() if v == VEREDITO_CERTO]
    if len(certas) == 1 and all(
        v == VEREDITO_ERRADO for letra, v in vereditos.items() if letra != certas[0]
    ):
        return certas[0]
    return None


def _registrar_resposta(
    embutido: GabaritoEmbutido,
    vistos: Counter,
    numero: int | None,
    letra: str | None,
    tipo: str,
    contexto: str,
) -> None:
    """Grava a resposta lida, ou um alerta. Número repetido sai da grade (a
    resposta de um deles foi atribuída ao item errado): o caderno falha na
    conferência itens × gabarito, nunca com resposta trocada."""
    if numero is None:
        embutido.alertas.append(f"resposta sem número de questão: {contexto[:60]!r}")
        return
    vistos[numero] += 1
    if vistos[numero] > 1:
        embutido.alertas.append(f"questão {numero} com mais de uma resposta")
        embutido.respostas.pop(numero, None)
        embutido.tipos.pop(numero, None)
        return
    if letra is None or letra not in LETRAS_POR_TIPO[tipo]:
        embutido.alertas.append(
            f"questão {numero} sem resposta legível: {contexto[:60]!r}"
        )
        return
    embutido.respostas[numero] = letra
    embutido.tipos[numero] = tipo


def _separar_justificativas(
    linhas: list[Linha], tem_ce: bool, tem_me: bool
) -> tuple[list[Linha], GabaritoEmbutido]:
    """Tira as justificativas C/E (`tem_ce`) e ME (`tem_me`). A resposta de
    cada uma vai para o último marcador visto depois da justificativa
    anterior: o número do item (C/E) ou a linha "Questão N" (ME)."""
    embutido = GabaritoEmbutido(formato=FORMATO_JUSTIFICATIVA, versao=VERSAO_PRELIMINAR)
    vistos: Counter = Counter()
    mantidas: list[Linha] = []
    margens = _detectar_margens_colunas(linhas)
    item_ce: int | None = None
    ultimo_ce: int | None = None
    questao_me: int | None = None
    i = 0
    while i < len(linhas):
        linha = linhas[i]
        if tem_ce and PADRAO_JUSTIFICATIVA_CE.match(linha.texto):
            fechada = _fim_justificativa_ce(linhas, i, margens)
            if fechada is None:
                # Sem fecho nem margem, não há como saber onde ela acaba.
                embutido.alertas.append(
                    f"justificativa sem fim reconhecível: {linha.texto[:60]!r}"
                )
                mantidas.append(linha)
                i += 1
                continue
            fim, presumido = fechada
            if presumido:
                embutido.avisos.append(
                    f"item {item_ce}: justificativa sem <FimJust>, fim na margem"
                )
            # O veredito pode quebrar de linha ("JUSTIFICATIVA" / "- CERTO").
            abertura = " ".join(lin.texto for lin in linhas[i : min(fim, i + 2) + 1])
            veredito = _veredito(re.sub(r"^\s*JUSTIFICATIVA\s*[-–]?\s*", "", abertura))
            _registrar_resposta(
                embutido,
                vistos,
                item_ce,
                LETRA_DO_VEREDITO_CE.get(veredito),
                QUESTAO_CERTO_ERRADO,
                abertura,
            )
            embutido.trechos.append(linhas[i : fim + 1])
            if item_ce is not None:
                ultimo_ce = item_ce
            item_ce = questao_me = None
            i = fim + 1
            continue
        if tem_me and PADRAO_JUSTIFICATIVAS_ME.match(linha.texto):
            entradas = _entradas_justificativa_me(linhas, i)
            if entradas is None:
                embutido.alertas.append(
                    f"questão {questao_me}: justificativas sem entradas A–E "
                    "reconhecíveis"
                )
                mantidas.append(linha)
                i += 1
                continue
            fim, vereditos, presumido = entradas
            if presumido:
                embutido.avisos.append(
                    f"questão {questao_me}: última justificativa sem */, fim "
                    "antes da questão seguinte"
                )
            if questao_me is not None:
                embutido.alternativas[questao_me] = len(vereditos)
            _registrar_resposta(
                embutido,
                vistos,
                questao_me,
                _resposta_me(vereditos),
                QUESTAO_MULTIPLA_ESCOLHA,
                f"{vereditos}",
            )
            embutido.trechos.append(linhas[i : fim + 1])
            item_ce = questao_me = None
            i = fim + 1
            continue
        # Os itens crescem: número menor é linha de tabela dentro do item.
        numero = _numero_do_item(linha)
        if numero is not None and (ultimo_ce is None or numero > ultimo_ce):
            item_ce = numero
        if m := PADRAO_QUESTAO_ME.match(linha.texto):
            questao_me = int(m.group(1))
        mantidas.append(linha)
        i += 1
    engolidas = [
        linha.texto.strip()
        for linha in embutido.removidas
        if PADRAO_QUESTAO_ME.match(linha.texto)
        or _eh_rotulo_texto_me(linha.texto)
        or _eh_cabecalho_secao_me(linha.texto)
    ]
    if engolidas:
        embutido.alertas.append(
            f"justificativa engoliu o início de questão: {engolidas}"
        )
    return mantidas, embutido


def _separar_codigo_ce(linhas: list[Linha]) -> tuple[list[Linha], GabaritoEmbutido]:
    """Formato código: o veredito sai da linha do item, e o texto fica só com
    o número e o enunciado. Saem também o cabeçalho "GABARITO ..." das páginas
    e o do bloco (curso, cargo), que não são texto-base de nenhum item."""
    versoes = {
        m.group(1)
        for linha in linhas
        if (m := PADRAO_CABECALHO_GABARITO.match(linha.texto))
    }
    embutido = GabaritoEmbutido(
        formato=FORMATO_CODIGO_CE,
        versao=VERSAO_DEFINITIVO if versoes == {"DEFINITIVO"} else VERSAO_PRELIMINAR,
    )
    vistos: Counter = Counter()
    mantidas: list[Linha] = []
    no_cabecalho_bloco = False
    for linha in linhas:
        if PADRAO_CABECALHO_GABARITO.match(linha.texto):
            embutido.trechos.append([linha])
            continue
        if PADRAO_CABECALHO_BLOCO_CODIGO.match(linha.texto):
            no_cabecalho_bloco = True
        if no_cabecalho_bloco:
            # O cabeçalho do bloco vai até o comando do primeiro item.
            if not PADRAO_COMANDO_OBJETIVO.search(linha.texto):
                embutido.trechos.append([linha])
                continue
            no_cabecalho_bloco = False
        m = PADRAO_CODIGO_ITEM.match(linha.texto)
        if m:
            veredito = VEREDITO_ANULADO if m.group(3) else _veredito(m.group(2))
            _registrar_resposta(
                embutido,
                vistos,
                int(m.group(1)),
                LETRA_DO_VEREDITO_CE[veredito],
                QUESTAO_CERTO_ERRADO,
                linha.texto,
            )
            linha = replace(linha, texto=m.group(1) + linha.texto[m.end() :])
        elif PADRAO_CODIGO_ITEM_INICIO.match(linha.texto):
            embutido.alertas.append(
                f"item com código sem veredito legível: {linha.texto[:60]!r}"
            )
        mantidas.append(linha)
    return mantidas, embutido


def separar_gabarito_embutido(
    linhas: list[Linha],
) -> tuple[list[Linha], GabaritoEmbutido | None]:
    """Tira do caderno as respostas impressas nele e as devolve à parte.

    Caderno sem nenhuma marca (o caso comum: grade em outro PDF) volta
    intacto, com None. As linhas tiradas ficam em `removidas`; a resposta
    que não dá para ler sem ambiguidade fica fora da grade, com alerta, e o
    caderno falha na conferência itens × gabarito.
    """
    # Cada formato exige mais que a palavra (veredito, fecho ou item bem
    # formado), para uma linha "JUSTIFICATIVAS" ou um "*/" de código num
    # caderno comum não dispararem nada.
    textos = [linha.texto for linha in linhas]
    # C/E: "JUSTIFICATIVA - <veredito>" (há caderno sem nenhum <FimJust>).
    tem_ce = any(
        (m := PADRAO_JUSTIFICATIVA_CE.match(t))
        and _veredito(t[m.end() :].lstrip(" -–"))
        for t in textos
    )
    tem_me = any(FIM_ENTRADA_ME in t for t in textos) and any(
        PADRAO_JUSTIFICATIVAS_ME.match(t) for t in textos
    )
    if any(PADRAO_CODIGO_ITEM.match(t) for t in textos):
        mantidas, embutido = _separar_codigo_ce(linhas)
    elif tem_ce or tem_me:
        mantidas, embutido = _separar_justificativas(linhas, tem_ce, tem_me)
    else:
        return linhas, None
    # A conferência itens × gabarito só olha as pontas da faixa (a grade
    # separada nunca tem buraco): questão sem resposta no meio seria engolida
    # pela anterior sem aviso.
    numeros = sorted(embutido.respostas)
    buracos = [
        f"{a + 1}" if b - a == 2 else f"{a + 1}–{b - 1}"
        for a, b in zip(numeros, numeros[1:], strict=False)
        if b - a > 1
    ]
    if buracos:
        embutido.alertas.append(f"questões sem resposta no caderno: {buracos}")
    return mantidas, embutido


def ler_gabarito_embutido(pdf_path: Path) -> dict | None:
    """Gabarito impresso no próprio caderno, no formato de
    `gabarito_parser.ler_documento` (`tipo` = grade). None se o caderno não
    traz respostas."""
    with pymupdf.open(pdf_path) as doc:
        linhas, _ = remover_ruido(extrair_linhas(doc))
    _, embutido = separar_gabarito_embutido(linhas)
    if embutido is None:
        return None
    return {
        "tipo": TIPO_GRADE,
        "codigo_caderno": None,
        "grade": embutido.grade(),
        "padrao_resposta": None,
        "versao": embutido.versao,
        "formato": embutido.formato,
    }


def _regioes_removidas(
    trechos: list[list[Linha]],
) -> list[tuple[int, pymupdf.Rect]]:
    """Retângulo de cada trecho removido, por página e coluna (a
    justificativa pode virar de coluna): a figura que cai nele (fórmula de
    uma justificativa) não é da questão."""
    regioes: list[tuple[int, pymupdf.Rect]] = []
    for trecho in trechos:
        partes: dict[tuple[int, bool], pymupdf.Rect] = {}
        for linha in trecho:
            chave = (linha.pagina, linha.x0 >= LIMITE_COLUNA_DIREITA)
            rect = pymupdf.Rect(linha.x0, linha.y0, linha.x1, linha.y1)
            if chave in partes:
                partes[chave].include_rect(rect)
            else:
                partes[chave] = rect
        regioes.extend((pagina, rect) for (pagina, _), rect in partes.items())
    return regioes


def _sem_figuras_removidas(
    rects: list[pymupdf.Rect],
    pagina: int,
    regioes: list[tuple[int, pymupdf.Rect]],
    auditoria: dict,
) -> list[pymupdf.Rect]:
    """Tira as figuras cujo centro cai num trecho removido do caderno."""
    mantidas = []
    for rect in rects:
        centro = pymupdf.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
        if any(p == pagina and centro in r for p, r in regioes):
            auditoria["gabarito_embutido"]["figuras_descartadas"].append(
                {"pagina": pagina + 1, "bbox": [round(v, 1) for v in rect]}
            )
            continue
        mantidas.append(rect)
    return mantidas


def _conferir_sem_justificativa(seg, embutido: GabaritoEmbutido) -> list[dict]:
    """Alertas bloqueantes de justificativa que ficou no texto: marca residual
    (`JUSTIFICATIVA`, `||A||`, `<FimJust>`) em enunciado, alternativa ou
    texto-base, ou questão ME com número de entradas na justificativa
    diferente do de alternativas (uma entrada não reconhecida virou texto)."""
    com_marca = [
        n
        for n, item in seg.itens.items()
        if any(
            PADRAO_MARCA_JUSTIFICATIVA.search(t)
            for t in [item["enunciado"]]
            + [a["texto"] for a in item.get("alternativas") or []]
        )
    ]
    textos_base = [
        tb["ordem"]
        for tb in seg.textos_base
        if PADRAO_MARCA_JUSTIFICATIVA.search(tb["texto"])
    ]
    divergentes = {
        n: (entradas, len(seg.itens[n].get("alternativas") or []))
        for n, entradas in embutido.alternativas.items()
        if n in seg.itens and entradas != len(seg.itens[n].get("alternativas") or [])
    }
    alertas = []
    if com_marca or textos_base:
        alertas.append(
            {
                "tipo": "justificativa_no_texto",
                "severidade": SEVERIDADE_BLOQUEANTE,
                "itens": com_marca,
                "textos_base": textos_base,
            }
        )
    if divergentes:
        alertas.append(
            {
                "tipo": "justificativa_incompleta",
                "severidade": SEVERIDADE_BLOQUEANTE,
                # {questão: (entradas na justificativa, alternativas)}
                "questoes": {str(n): list(v) for n, v in sorted(divergentes.items())},
            }
        )
    return alertas


# Caderno objetivo -------------------------------------------------------------


def _remover_texto_das_tabelas(seg, linhas: list[Linha]) -> None:
    """Tira do texto-base e dos itens as linhas que caem dentro de figura vetorial.

    A tabela desenhada já aparece como imagem; o texto corrido das células
    ("grupo patrimonial 20X1 20X0 ativo circulante $ 154 ...") só repete o
    conteúdo de forma ilegível. No texto-base o texto dentro da tabela é
    descartado; nos itens, é guardado em campo próprio `texto_tabela`
    (KAN-75) e o enunciado fica limpo.
    """
    for tb in seg.textos_base:
        regioes = [
            (f["pagina"] - 1, pymupdf.Rect(f["bbox"]))
            for f in tb["figuras"]
            if f.get("origem") == "vetorial"
        ]
        if not regioes or not tb["texto"]:
            continue
        indices = [
            i
            for i, dono in seg.dono_linha.items()
            if dono == ("texto_base", tb["ordem"])
        ]
        if not indices:
            continue
        indices.sort()

        def dentro(linha: Linha, regioes=regioes) -> bool:
            cx, cy = (linha.x0 + linha.x1) / 2, (linha.y0 + linha.y1) / 2
            return any(
                pagina == linha.pagina and r.contains(pymupdf.Point(cx, cy))
                for pagina, r in regioes
            )

        todas = [linhas[i] for i in indices]
        fora = [linha for linha in todas if not dentro(linha)]
        if len(fora) == len(todas):
            continue
        completo = juntar_linhas(todas, paragrafos=True)
        # O fim do texto-base pode ter recebido a frase colada ao comando
        # (ver `segmentar`); esse sufixo não está nas linhas e é mantido.
        sufixo = (
            tb["texto"][len(completo) :] if tb["texto"].startswith(completo) else ""
        )
        tb["texto"] = f"{juntar_linhas(fora, paragrafos=True)}{sufixo}".strip()

    for item in seg.itens.values():
        item["texto_tabela"] = None
        regioes = [
            (f["pagina"] - 1, pymupdf.Rect(f["bbox"]))
            for f in item.get("figuras", [])
            if f.get("origem") == "vetorial"
        ]
        if not regioes or not item.get("enunciado"):
            continue
        indices = [
            i for i, dono in seg.dono_linha.items() if dono == ("item", item["numero"])
        ]
        if not indices:
            continue
        indices.sort()
        todas = [linhas[i] for i in indices]
        if item.get("tipo") == "multipla_escolha" and item.get("alternativas"):
            alts_loc = _localizar_alternativas_questao(todas)
            todas_enunc = todas[: alts_loc[0][1]] if alts_loc else todas
        else:
            todas_enunc = todas

        def dentro_item(linha: Linha, regioes=regioes) -> bool:
            cx, cy = (linha.x0 + linha.x1) / 2, (linha.y0 + linha.y1) / 2
            return any(
                pagina == linha.pagina and r.contains(pymupdf.Point(cx, cy))
                for pagina, r in regioes
            )

        fora = [l for l in todas_enunc if not dentro_item(l)]
        dentro_linhas = [l for l in todas_enunc if dentro_item(l)]
        if not dentro_linhas or len(fora) == 0:
            continue

        item["texto_tabela"] = (
            juntar_linhas(dentro_linhas, paragrafos=True).strip() or None
        )
        novo_enunc = juntar_linhas(fora, paragrafos=True)
        if item.get("tipo") == "multipla_escolha":
            novo_enunc = (
                PADRAO_QUESTAO_ME.sub("", novo_enunc, count=1).lstrip(" -.:\t").strip()
            )
        else:
            novo_enunc = (
                re.sub(rf"^{item['numero']}\s*", "", novo_enunc, count=1)
                .lstrip(" -.:\t")
                .strip()
            )
        item["enunciado"] = novo_enunc


def extrair_caderno_objetivo(
    pdf_path: Path,
    gabarito: dict[int, str] | None,
    caderno: str,
    dir_figuras: Path | None = None,
    tipos: dict[int, str] | None = None,
) -> tuple[dict, dict]:
    """Devolve `(resultado, auditoria)` de um caderno objetivo (C/E ou ME).

    `gabarito` = `{numero: letra}` (grade definitiva) e `tipos` =
    `{numero: tipo}` da mesma grade (`GradeGabarito.tipos`). Sem gabarito, o
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
        # Caderno com gabarito: as respostas impressas nele saem antes da
        # segmentação, senão viram texto da questão (ou da alternativa E).
        linhas, embutido = separar_gabarito_embutido(linhas)
        regioes_embutido = []
        if embutido is not None:
            regioes_embutido = _regioes_removidas(embutido.trechos)
            auditoria["gabarito_embutido"] = {
                "formato": embutido.formato,
                "linhas_removidas": [
                    linha.texto.strip() for linha in embutido.removidas
                ],
                "figuras_descartadas": [],
                "avisos": embutido.avisos,
            }
            if embutido.avisos:
                resultado["alertas"].append(
                    {
                        "tipo": "gabarito_embutido_fim_presumido",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "detalhes": embutido.avisos,
                    }
                )
            if embutido.alertas:
                # Justificativa que não fechou fica no texto da questão, e
                # resposta ilegível deixa questão fora da grade: o caderno
                # falha mesmo quando a grade usada é o definitivo à parte.
                resultado["alertas"].append(
                    {
                        "tipo": "gabarito_embutido_irregular",
                        "severidade": SEVERIDADE_BLOQUEANTE,
                        "detalhes": embutido.alertas,
                    }
                )
        esperados = sorted(gabarito)
        alertas_loc: list[dict] = []
        eh_me = _eh_multipla_escolha(linhas, esperados, gabarito, tipos)
        if eh_me:
            achados = localizar_questoes_me(linhas, esperados, alertas=alertas_loc)
            resultado["alertas"].extend(alertas_loc)
            seg = _segmentar_me(linhas, achados)
        else:
            achados = localizar_itens(linhas, esperados, alertas=alertas_loc)
            resultado["alertas"].extend(alertas_loc)
            seg = segmentar(linhas, achados)

        # Figuras.
        total_figuras = 0
        for num_pagina, page in enumerate(doc):
            raster = figuras_da_pagina(page)
            vetoriais = figuras_vetoriais_da_pagina(page, raster)
            if regioes_embutido:
                raster = _sem_figuras_removidas(
                    raster, num_pagina, regioes_embutido, auditoria
                )
                vetoriais = _sem_figuras_removidas(
                    vetoriais, num_pagina, regioes_embutido, auditoria
                )
            # Vetoriais depois das raster: o nome das raster não muda.
            if eh_me:
                # No caderno com justificativas (CAESB_24) o selo "Questão N"
                # é desenhado (vetorial); nos ME da amostra, imagem.
                raster, vetoriais = (
                    [
                        r
                        for r in rects
                        if not _figura_decorativa_me(
                            r, num_pagina, linhas, page.rect.width
                        )
                    ]
                    for rects in (raster, vetoriais)
                )
            regioes = [(r, None) for r in raster] + [(r, "vetorial") for r in vetoriais]
            for n, (rect, origem) in enumerate(regioes, start=1):
                dono = dono_da_figura(
                    rect, num_pagina, linhas, seg.dono_linha, ignorar=vetoriais
                )
                nome = f"{caderno}_{num_pagina + 1}_{n}.png"
                figura = {
                    "arquivo": nome,
                    "pagina": num_pagina + 1,
                    "bbox": [round(v, 1) for v in rect],
                }
                if origem:
                    # O texto da tabela/gráfico também está no enunciado ou
                    # no texto-base (extraído como linhas); a imagem é a
                    # forma legível, não substitui o texto.
                    figura["origem"] = origem
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
                elif tipo == "item" or eh_me:
                    # ME: o "comando" é o cabeçalho de seção antes da questão
                    # `chave`; a figura é da questão, nunca texto-base vazio.
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

        _remover_texto_das_tabelas(seg, linhas)

    if embutido is not None:
        resultado["alertas"].extend(_conferir_sem_justificativa(seg, embutido))

    for item in seg.itens.values():
        alts = item.get("alternativas") or []
        textos_item = [item["enunciado"]] + [a["texto"] for a in alts]
        if any(SIMBOLO_ILEGIVEL in t for t in textos_item):
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
        if (
            any(PADRAO_MENCIONA_FIGURA.search(t) for t in textos_item)
            and not tem_figura
        ):
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
    extras = (
        marcadores_fora_do_gabarito_me(linhas, esperados)
        if eh_me
        else marcadores_fora_do_gabarito(linhas, esperados)
    )
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
                "tipo": item.get("tipo", "certo_errado"),
                "alternativas": item.get("alternativas"),
                "texto_tabela": item.get("texto_tabela"),
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
