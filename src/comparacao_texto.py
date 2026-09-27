"""Comparação textual entre item do edital (texto-fonte) e tópico extraído
pelo LLM — usada tanto pela validação de-para (`scripts/validar_taxonomia.py`)
quanto pelo reparo local pós-LLM (`src/taxonomia_extractor.py`).

Vive em `src/` (e não em `scripts/`) pelo mesmo motivo do
`extrair_itens_numerados` (ADR-021): reparo e validação nunca podem divergir
sobre o que conta como "o item foi coberto". Se o reparo reinjetasse um item
que o validador considera coberto (ou vice-versa), um dos dois estaria
mentindo.
"""

import re
import unicodedata
from difflib import SequenceMatcher

MAPA_LIGATURAS_FONTES = {
    "Ɵ": "ti",
    "Ō": "ft",
    "ﬃ": "ffi",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬀ": "ff",
    "ﬄ": "ffl",
}

# Comprimento mínimo para match de substring geral sem fronteira de palavra
TAMANHO_MINIMO_SUBSTRING = 6

# Similaridade mínima (difflib) para tratar um nome extraído como paráfrase
# leve do item da fonte (erro de digitação corrigido pelo LLM, ex.: STM
# "bBiblioteca Flyway" -> "Biblioteca Flyway", ratio ~0,99). Calibrado contra
# os 150 chunks reais de 2025: um qualificador inventado ("Educação
# corporativa avançada" vs "Educação corporativa") fica em ~0,82 — abaixo do
# corte, continua alerta bloqueante. Ver ADR-025.
SIMILARIDADE_MINIMA_DIVERGENCIA_LEVE = 0.92

# Sufixo entre parênteses acrescentado pelo LLM para desambiguar item
# repetido no próprio edital (achado real: PF "Educação corporativa" nos
# itens 7 e 11 -> "Educação corporativa (atuação do pedagogo)").
PADRAO_SUFIXO_PARENTETICO = re.compile(r"\s*\([^()]*\)\s*$")

# Subitem numerado ("1.1 ", "10.2.3 ") dentro do texto de um item de primeiro
# nível. Exige espaço + maiúscula depois do número — "Lei nº 5.197/1967" e
# "JPA 2.0" não contam como subitem.
PADRAO_SUBITEM = re.compile(r"(?<![\d/.])\b\d{1,3}(?:\.\d{1,3})+\.?\s+(?=[A-ZÀ-Ú(])")


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento/pontuação, sem número de prefixo ('1 ', '3.1 ')."""
    texto = texto.strip()
    texto = re.sub(r"^\d+(\.\d+)*\.?\s+", "", texto)
    for de, para in MAPA_LIGATURAS_FONTES.items():
        if de in texto:
            texto = texto.replace(de, para)
    # Converte para NFC para unir acentos combinantes (ex.: i + ́ -> í)
    # antes da remoção de caracteres não-palavra
    texto = unicodedata.normalize("NFC", texto)
    # Troca qualquer pontuação/hífen por espaço
    texto = re.sub(r"[^\w]", " ", texto, flags=re.UNICODE)
    sem_acento = (
        unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def contido(nome_norm: str, item_norm: str) -> bool:
    """Casamento estrito (textos já normalizados): igualdade, fronteira de
    palavra para termos ≥ 3 chars, ou substring livre para termos ≥ 6 chars."""
    if not nome_norm or not item_norm:
        return False
    if nome_norm == item_norm:
        return True
    if len(nome_norm) >= 3 and re.search(
        r"\b" + re.escape(nome_norm) + r"\b", item_norm
    ):
        return True
    if len(item_norm) >= 3 and re.search(
        r"\b" + re.escape(item_norm) + r"\b", nome_norm
    ):
        return True
    if len(nome_norm) >= TAMANHO_MINIMO_SUBSTRING and nome_norm in item_norm:
        return True
    return len(item_norm) >= TAMANHO_MINIMO_SUBSTRING and item_norm in nome_norm


def rotulo_item(item_texto: str) -> str:
    """Texto do item de primeiro nível até o primeiro subitem (`N.1`) — o
    "título" do item, sem o conteúdo dos subitens."""
    m = PADRAO_SUBITEM.search(item_texto)
    return (item_texto[: m.start()] if m else item_texto).strip()


def divergencia_leve(nome: str, textos_item: list[str], texto_fonte_norm: str) -> bool:
    """O nome extraído não casa de forma estrita, mas é paráfrase leve de um
    item da fonte: (1) sem o sufixo entre parênteses, casa com o texto-fonte;
    ou (2) é quase idêntico (difflib) ao rótulo ou ao texto completo de algum
    item. Não suprime nada sozinho — quem chama decide a severidade."""
    sem_parenteses = PADRAO_SUFIXO_PARENTETICO.sub("", nome)
    if sem_parenteses != nome and contido(normalizar(sem_parenteses), texto_fonte_norm):
        return True

    nome_norm = normalizar(nome)
    if not nome_norm:
        return False
    for item_texto in textos_item:
        for candidato in {normalizar(item_texto), normalizar(rotulo_item(item_texto))}:
            if (
                candidato
                and SequenceMatcher(None, nome_norm, candidato).ratio()
                >= SIMILARIDADE_MINIMA_DIVERGENCIA_LEVE
            ):
                return True
    return False


# Números de cargo citados num texto (link de caderno ou restrição de matéria
# no edital). O intervalo exige "de" ("cargos de 1 a 14") para "cargo 1 a 3
# horas" não virar [1, 2, 3].
PADRAO_CARGOS_MENCIONADOS = re.compile(
    r"\bcargos?\s+(?:de\s+(\d+)\s+a\s+(\d+)|((?:\d+\s*(?:,|e|/|\s)\s*)*\d+))\b",
    re.IGNORECASE,
)


def extrair_cargos_do_texto(texto: str) -> list[int]:
    """Cargos citados no texto, na ordem em que aparecem e sem repetição.

    Aceita intervalo ('cargos de 1 a 14'), lista ('cargos 2, 4, 5 e 7') e
    várias menções separadas por texto ('cargo 1: ... e para o cargo 8: ...').
    Lista vazia = o texto não cita cargo (ex.: TCU, cargo único) — quem chama
    decide o que fazer.
    """
    resultado: list[int] = []
    for m in PADRAO_CARGOS_MENCIONADOS.finditer(texto or ""):
        if m.group(1):
            nums = range(int(m.group(1)), int(m.group(2)) + 1)
        else:
            nums = (int(n) for n in re.findall(r"\d+", m.group(3)))
        for n in nums:
            if n not in resultado:
                resultado.append(n)
    return resultado
