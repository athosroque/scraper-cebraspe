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


# Cobertura aproximada de subitem dentro de um texto extraído maior (ADR-017,
# atualização 2026-10-12): o LLM corrige erro de digitação da fonte ("mediada"
# -> "mediana") e abrevia ("Sistema Público de Escrituração Digital (SPED)" ->
# "SPED") dentro de um subtópico que junta vários itens.
MINIMO_PALAVRAS_JANELA = 3
MINIMO_PALAVRAS_SEQUENCIA = 12
COBERTURA_MINIMA_SEQUENCIA = 0.8


def _coberto_aproximadamente(item_norm: str, extraido_norm: str) -> bool:
    """(1) Alguma janela de palavras do extraído, com o mesmo tamanho do item,
    tem similaridade >= `SIMILARIDADE_MINIMA_DIVERGENCIA_LEVE`; ou (2) item
    longo (>= 12 palavras) cujas palavras aparecem, em ordem, em >= 80% no
    extraído. Item curto nunca passa pela regra (2): "Inflação de custos" e
    "Inflação de demanda" são itens distintos."""
    palavras_item = item_norm.split()
    palavras_ext = extraido_norm.split()
    n = len(palavras_item)
    if n < MINIMO_PALAVRAS_JANELA:
        return False
    for i in range(max(len(palavras_ext) - n + 1, 1)):
        janela = " ".join(palavras_ext[i : i + n])
        if (
            SequenceMatcher(None, item_norm, janela).ratio()
            >= SIMILARIDADE_MINIMA_DIVERGENCIA_LEVE
        ):
            return True
    if n >= MINIMO_PALAVRAS_SEQUENCIA:
        casadas = sum(
            b.size
            for b in SequenceMatcher(
                None, palavras_item, palavras_ext, autojunk=False
            ).get_matching_blocks()
        )
        return casadas / n >= COBERTURA_MINIMA_SEQUENCIA
    return False


def item_coberto(texto_item: str, textos_extraidos: list[str]) -> bool:
    """O item (ou subitem) da fonte está coberto pela taxonomia extraída?

    `texto_item`: texto do item na fonte (com ou sem número de prefixo).
    `textos_extraidos`: nomes de TODOS os tópicos e subtópicos extraídos do
    mesmo chunk (qualquer nível).

    Coberto se (1) o texto do item está CONTIDO (igualdade ou fronteira de
    palavra, após `normalizar`) em algum texto extraído — o que cobre um
    subtópico que junta vários itens ("Mecanismos de segurança: criptografia,
    assinatura digital, ...") — ou (2) algum texto extraído é paráfrase leve
    dele (`divergencia_leve`, comparada só contra ESTE item), ou (3) casa de
    forma aproximada dentro de um texto extraído maior (`_coberto_aproximadamente`:
    erro de digitação corrigido, sigla no lugar do nome por extenso).

    Diferença deliberada para `contido`, que também aceita o sentido inverso
    (texto extraído contido no item): para subitem esse sentido gera cobertura
    falsa em massa, porque o tópico-pai ("Ativo", "Inflação") está contido em
    todo filho ("Ativo imobilizado", "Inflação de custos") e esconderia a
    perda dos filhos. O 1º nível segue com `contido` nos dois sentidos
    (validador e reinjeção atuais), sem alteração.
    """
    item_norm = normalizar(texto_item)
    if not item_norm:
        return True
    padrao = re.compile(r"\b" + re.escape(item_norm) + r"\b")
    extraidos_norm = [normalizar(t) for t in textos_extraidos if t]
    if any(padrao.search(e) for e in extraidos_norm):
        return True
    if any(_coberto_aproximadamente(item_norm, e) for e in extraidos_norm):
        return True
    return any(
        divergencia_leve(t, [texto_item], item_norm) for t in textos_extraidos if t
    )


# Números de cargo citados num texto (link de caderno ou restrição de matéria
# no edital). O intervalo exige "de" ("cargos de 1 a 14") para "cargo 1 a 3
# horas" não virar [1, 2, 3].
PADRAO_CARGOS_MENCIONADOS = re.compile(
    r"\bcargos?\s+(?:de\s+(\d+)\s+a\s+(\d+)|((?:\d+\s*(?:,|e|/|\s)\s*)*\d+))\b",
    re.IGNORECASE,
)

# Padrão de resposta da discursiva (singular ou plural) — funciona tanto no
# texto bruto quanto no texto normalizado.
PADRAO_PADRAO_RESPOSTA = re.compile(r"\bpadr\w*\s+.*\brespostas?\b", re.IGNORECASE)

# Editais e comunicados administrativos que citam termos como prova/edital
# mas não são cadernos nem editais de abertura.
PADRAO_EDITAL_ADMINISTRATIVO = re.compile(
    r"edital\s+n[ºo]|resultado|loca(?:l|is)\s+de\s+(?:aplica|realiza)|comunicado\s*[-–\s]+\s*loca(?:l|is)\b|convoca|reabertura|retifica",
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


# --- Forma das listas e facetas (KAN-94, M8) --------------------------------
# Vive aqui, e não no extrator, pelo mesmo motivo do resto do módulo: o reparo
# (`taxonomia_extractor`) e o validador (`validar_taxonomia`) precisam concordar
# sobre o que é uma lista com ";", uma faceta solta e uma frase longa.

# Nome de tópico acima disso é frase-assunto: informativo no validador. Calibrado
# nos 1.812 tópicos dos 7 editais (p95 = 98, p99 = 172): 150 pega 29 (1,6%), a
# maioria título de norma com ementa, que o dono pode aceitar.
TAMANHO_FRASE_LONGA = 150

# Palavras que, sozinhas e em minúsculas, são aspecto genérico de um conceito
# ("Balanced Scorecard: conceitos, aplicações, perspectivas, metas...") e não um
# assunto de estudo. Lista fechada e curta de propósito: "Backup", "Cluster",
# "jQuery", "estados" ou "mensageria" são subtópicos legítimos e ficam de fora.
FACETAS_GENERICAS = frozenset(
    {
        "aplicação",
        "aplicações",
        "características",
        "conceito",
        "conceitos",
        "espécies",
        "fundamentos",
        "indicadores",
        "limites",
        "metas",
        "objetivos",
        "perspectivas",
    }
)

# Termos que um pedaço de lista não pode abrir: é continuação da frase anterior,
# não um item.
_ABRE_CONTINUACAO = frozenset(
    {"e", "ou", "que", "com", "sem", "em", "de", "do", "da", "dos", "das", "para"}
)
_ABREVIATURAS_COM_PONTO = frozenset(
    {"etc", "art", "arts", "nº", "ed", "vol", "inc", "cf", "ex", "obs", "pp"}
)
PADRAO_SIGLA_ENTRE_PARENTESES = re.compile(r"\(\s*[A-ZÀ-Ú][A-Za-zÀ-ÿ0-9]{1,9}\s*\)")
MAX_PALAVRAS_CABECA = 8


def sem_pontuacao_final(nome: str) -> str:
    """Tira ".", ";" e "," do fim do nome, menos o ponto de abreviatura ("etc.",
    "S.A."). A chave (`normalizar`) já ignora pontuação: isto só limpa o texto."""
    base = " ".join(nome.split())
    while base and base[-1] in ".;,":
        if base[-1] == ".":
            ultimo = re.split(r"[\s(]", base)[-1].rstrip(".")
            if ultimo.casefold() in _ABREVIATURAS_COM_PONTO or re.fullmatch(
                r"(?:[A-Za-z]\.)+[A-Za-z]", ultimo
            ):
                break
        base = base[:-1].rstrip()
    return base


def partes_por_ponto_e_virgula(nome: str) -> list[str]:
    """Pedaços do nome separados por ";" fora de parênteses/colchetes. Parêntese
    desbalanceado: não divide (devolve o nome inteiro). Sem normalizar o texto."""
    partes: list[str] = []
    atual: list[str] = []
    nivel = 0
    for ch in nome:
        if ch in "([":
            nivel += 1
        elif ch in ")]":
            nivel -= 1
        if ch == ";" and nivel == 0:
            partes.append("".join(atual))
            atual = []
        else:
            atual.append(ch)
    partes.append("".join(atual))
    if nivel != 0:
        return [" ".join(nome.split())]
    return [" ".join(p.split()) for p in partes]


def parte_de_lista_valida(parte: str) -> bool:
    """Pedaço de lista com sentido isolado: tem letra/dígito e não abre com
    palavra de continuação ("e", "ou", "que", "com"...)."""
    if not re.search(r"\w", parte):
        return False
    return parte.split()[0] not in _ABRE_CONTINUACAO


def cabeca_e_resto(parte: str) -> tuple[str, str] | None:
    """Separa "Cabeça: resto" no primeiro ":" fora de parênteses, se a cabeça tem
    1 a `MAX_PALAVRAS_CABECA` palavras e há resto; senão None."""
    nivel = 0
    for pos, ch in enumerate(parte):
        if ch in "([":
            nivel += 1
        elif ch in ")]":
            nivel -= 1
        elif ch == ":" and nivel == 0:
            cabeca, resto = parte[:pos].strip(), parte[pos + 1 :].strip()
            if cabeca and resto and len(cabeca.split()) <= MAX_PALAVRAS_CABECA:
                return cabeca, resto
            return None
    return None


def eh_fragmento_de_uma_palavra(sub: str) -> bool:
    """Uma palavra só e minúscula na inicial. Sozinho NÃO prova nada: "jQuery",
    "keycloak" e "estados" também são assim e são assuntos legítimos."""
    palavras = sub.split()
    return len(palavras) == 1 and palavras[0][:1].islower()


def eh_faceta_generica(sub: str) -> bool:
    return eh_fragmento_de_uma_palavra(sub) and sub.strip(" .;,").casefold() in (
        FACETAS_GENERICAS
    )
