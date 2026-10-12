import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from src.comparacao_texto import extrair_cargos_do_texto
from src.logger import logger

# Análise exploratória manual (2026-09-19, edital real
# Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.pdf, PF_25_ADM):
# a única seção com valor pra taxonomia matéria→tópico→subtópico é
# "OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)" (item 14 nesse
# edital, mas o número do item varia por concurso — por isso o corte usa o
# texto do marcador, não o número). Outras seções candidatas foram
# descartadas por não servirem ao objetivo de taxonomia de estudo:
# cronograma, critérios de desempate e requisitos/atividades por cargo são
# dados operacionais do concurso, não conteúdo programático. Ver CLAUDE.md
# seção 12 para o racional completo.
MARCADOR_INICIO_SECAO = "OBJETOS DE AVALIAÇÃO"
MARCADOR_FIM_SECAO = "ANEXO I"

# Cabeçalho de cargo dentro de "CONHECIMENTOS ESPECÍFICOS PARA OS CARGOS...",
# ex: "CARGO 7: MÉDICO CLÍNICO". Cargos de especialidade médica costumam ter
# o conteúdo direto embaixo do próprio "CARGO N: <nome>" (sem matéria
# nomeada à parte); cargos administrativos usam "CARGO N: <nome>" só como
# rótulo, seguido de matérias nomeadas (ver PADRAO_MATERIA). Ambos os casos
# são reais no PF_25_ADM — o parser trata os dois.
PADRAO_CARGO = re.compile(r"\nCARGO\s+(\d+):\s*([^\n]+)")

# Cabeçalho de área de conhecimento em caixa alta, linha inteira, ex.
# "ÁREA 1: ADMINISTRAÇÃO DE BANCO DE DADOS" (BANRISUL_25). Cada área faz prova
# específica própria, então é tratada como cargo. Só a forma em caixa alta e
# no início da linha: "áreas de conhecimento" no corpo do texto não casa.
PADRAO_AREA = re.compile(r"\nÁREA\s+(\d+):\s*([^\n]+)")

# Cabeçalho de matéria, ex: "LÍNGUA PORTUGUESA: 1 Compreensão ...",
# "ADMINISTRAÇÃO FINANCEIRA, ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO: ...",
# "ATUALIDADES (SOMENTE PARA A PROVA DISCURSIVA): ...",
# "LÍNGUA INGLESA (APENAS PARA O CARGO 3: ... E CARGO 6: ...): ...".
# Suporta especificações entre parênteses que contêm colons sem perder a fronteira da matéria.
PADRAO_MATERIA = re.compile(
    r"\n(?!(?:CARGO|ÁREA)\s+\d)"
    r"("
    r"[A-ZÀ-Ú][A-ZÀ-Ú0-9 /,–\-]{2,90}"
    r"(?:(?:,\s*|\s+(?:E|OU|DE|DA|DO|DOS|DAS))\s*\n\s*[A-ZÀ-Ú0-9 /,–\-]{2,90})?"
    r"(?:\s*\([^)]*\))?"
    r"):\s*"
)

# Sub-matéria numerada em romano dentro de uma matéria composta, ex. (SEFA_PR_25):
# "DIREITO CONSTITUCIONAL, DIREITO ADMINISTRATIVO E ESTATUTO DA CRIANÇA E DO
# ADOLESCENTE: I DIREITO CONSTITUCIONAL: 1 Constituição. ... II DIREITO
# ADMINISTRATIVO: 1 Conceito ..." — o romano fica colado ao texto anterior, na
# mesma linha, então não passa por `PADRAO_MATERIA` (que exige quebra de linha).
# Exige romano + nome em caixa alta + ":", para não casar "inciso II do art. 5º".
PADRAO_SUBMATERIA_ROMANA = re.compile(
    r"(?<!\S)(?:IX|IV|VI{0,3}|I{1,3}|X)\s+([A-ZÀ-Ú][A-ZÀ-Ú ,–\-/\n]{2,150}?):\s*"
)

# Cabeçalho de bloco que agrupa matérias por tipo de conhecimento e nível,
# ex: "CONHECIMENTOS BÁSICOS PARA OS CARGOS DE NÍVEL SUPERIOR",
# "CONHECIMENTOS ESPECÍFICOS PARA O CARGO DE NÍVEL MÉDIO",
# "CONHECIMENTOS GERAIS",
# "15.2.2 CONHECIMENTOS BÁSICOS PARA O CARGO DE ANALISTA ADMINISTRATIVO".
PADRAO_BLOCO = re.compile(
    r"\n(?:\d+(?:\.\d+)*\s+)?CONHECIMENTOS\s+(BÁSICOS|ESPECÍFICOS|COMPLEMENTARES|GERAIS)([^\n:]*)(?=\n)"
)
TIPO_CONHECIMENTO = {
    "BÁSICOS": "basico",
    "ESPECÍFICOS": "especifico",
    "COMPLEMENTARES": "complementar",
    "GERAIS": "basico",
}

# Marca de matéria cobrada só na prova discursiva, ex: "ATUALIDADES (SOMENTE
# PARA A PROVA DISCURSIVA)" — vira flag `apenas_discursiva` e sai do nome
# normalizado da matéria, pra "ATUALIDADES" ser comparável entre concursos.
PADRAO_APENAS_DISCURSIVA = re.compile(
    r"\s*\(SOMENTE PARA (?:AS? )?PROVAS? DISCURSIVAS?\)", re.IGNORECASE
)

# Restrição de cargos embutida no nome da matéria, ex.:
# "DIREITO PENAL MILITAR (APENAS PARA O CARGO 1: ... E PARA O CARGO 8: ...)"
# Vira a lista `cargos_restritos` no ChunkTaxonomia e sai de `materia_normalizada`.
# Aceita um nível de parêntese dentro da restrição ("ANALISTA (TI)"), senão o
# `)` interno cortaria a cláusula no meio e o resto sobraria no nome.
PADRAO_RESTRICAO_CARGO = re.compile(
    r"\s*\((?:APENAS|SOMENTE)\s+PARA\s+(?:O|OS|A|AS)?\s*CARGOS?(?:[^()]|\([^()]*\))*\)",
    re.IGNORECASE,
)

# Nota de retificação embutida no meio do texto programático (ex: "CARGO 12:
# PSICÓLOGO ORGANIZACIONAL", achado ao vivo 2026-09-20, ver CLAUDE.md seção
# 12): "(Retificado por meio do Edital nº 5 – PF – Administrativo, de 13 de
# junho de 2025...)". É ruído administrativo, não conteúdo de estudo.
PADRAO_RETIFICACAO = re.compile(
    r"\s*\(Retificado\s+por\s+meio\s+do\s+Edital[^)]*\)\s*", re.IGNORECASE
)

# Linha de cargo do signatário no bloco de assinatura do fim do edital (ver
# `remover_assinatura_final`). Sem IGNORECASE: no corpo programático essas
# palavras aparecem em minúscula ou no meio de frase ("7.3.1 Presidente da
# República." — e essa linha tem ponto, o que já a exclui).
PADRAO_CARGO_ASSINATURA = re.compile(
    r"^\s*(?:Ministr[oa]|Presidente|Diretor[a]?|Secret[áa]ri[oa]|Delegad[oa]|Coordenador[a]?"
    r"|Superintendente|Reitor[a]?|Procurador[a]?)\b"
)

# Item de primeiro nível numerado dentro do texto de uma matéria/cargo, ex:
# "1 Compreensão e interpretação de textos." — usado tanto por
# `scripts/validar_taxonomia.py` (comparação de-para) quanto pelo reparo
# determinístico de `src/taxonomia_extractor.py` (ver ADR-021), então mora
# aqui pra não duplicar/divergir entre os dois usos. `(?<!\d\.)` evita casar
# o segundo número de itens pontuados ("3.1") sem bloquear um item de
# primeiro nível colado ao ponto final do item anterior sem espaço (ex.:
# "...lógicos.4 Lógica..." — "4" é item novo, não "X.4"). A lookahead por
# maiúscula/parêntese evita casar números soltos em citações legais ("Lei
# 8.112, de 11 de dezembro de 1990").
PADRAO_ITEM_NUMERADO = re.compile(r"(?<!\d\.)\b(\d{1,3})\s+(?=[A-ZÀ-Ú(])")

# Tamanho mínimo de texto para um bloco entrar na checagem de coluna — um
# bloco curto isolado (ex: bloco de assinatura, centralizado) tem x0
# diferente da margem do corpo do texto sem que isso indique colunas
# paralelas de conteúdo corrido. Achado real (2026-09-19): sem esse piso, a
# checagem dava falso positivo na página de assinatura ao fim da seção 14.
TAMANHO_MINIMO_BLOCO_COLUNA = 150


@dataclass
class ChunkTaxonomia:
    cargo: str | None  # None para CONHECIMENTOS BÁSICOS (sem cargo associado)
    materia: str
    texto: str  # já limpo de ruído conhecido (ver _limpar_ruido_edital) — é o que vai pro LLM
    # offset_inicio/offset_fim apontam pro span BRUTO consumido da seção (antes da limpeza
    # de ruído) — úteis pra auditoria rastrear de volta ao PDF, não reconstroem `texto` via
    # slice+strip quando há ruído removido no meio.
    offset_inicio: int = 0
    offset_fim: int = 0
    # Vêm do cabeçalho de bloco (PADRAO_BLOCO) em que o chunk está. None =
    # chunk fora de bloco reconhecido, ou bloco que não declara um nível
    # único (ex: "PARA TODOS OS CARGOS") — `validar_taxonomia` alerta.
    tipo_conhecimento: str | None = None  # "basico" | "especifico" | "complementar"
    nivel: str | None = None  # "medio" | "superior"
    cargo_numero: int | None = None
    materia_origem: str = "cabecalho"  # "cabecalho" | "prefixo" | "cargo"

    @property
    def apenas_discursiva(self) -> bool:
        return bool(PADRAO_APENAS_DISCURSIVA.search(self.materia))

    @property
    def cargos_restritos(self) -> list[int] | None:
        cargos: list[int] = []
        for _, numeros in restricoes_de_cargo(self.materia):
            cargos += [n for n in numeros if n not in cargos]
        return cargos or None

    @property
    def materia_normalizada(self) -> str:
        texto = PADRAO_APENAS_DISCURSIVA.sub("", self.materia)
        # Só sai do nome a restrição que virou `cargos_restritos`. Sem número
        # de cargo ("PARA OS CARGOS DE NÍVEL SUPERIOR"), removê-la faria a
        # matéria valer para todos os cargos sem aviso.
        for trecho, numeros in restricoes_de_cargo(texto):
            if numeros:
                texto = texto.replace(trecho, "", 1)
        return re.sub(r"\s+", " ", texto).strip()


def restricoes_de_cargo(materia: str) -> list[tuple[str, list[int]]]:
    return [
        (m.group(0), extrair_cargos_do_texto(m.group(0)))
        for m in PADRAO_RESTRICAO_CARGO.finditer(materia)
    ]


# Campos de classificação do chunk propagados pra `.json`/`.auditoria.json`/
# banco de revisão — lista única pra os scripts não divergirem entre si.
CAMPOS_CLASSIFICACAO_CHUNK = (
    "tipo_conhecimento",
    "nivel",
    "cargo_numero",
    "materia_normalizada",
    "apenas_discursiva",
    "cargos_restritos",
    "materia_origem",
)


def metadados_chunk(chunk: ChunkTaxonomia) -> dict:
    return {campo: getattr(chunk, campo) for campo in CAMPOS_CLASSIFICACAO_CHUNK}


def _nivel_do_bloco(resto_cabecalho: str) -> str | None:
    tem_superior = "SUPERIOR" in resto_cabecalho
    tem_medio = "MÉDIO" in resto_cabecalho or "MEDIO" in resto_cabecalho
    if tem_superior == tem_medio:
        # Nenhum ou os dois níveis no mesmo bloco — não dá pra atribuir um
        # nível único às matérias; fica None e vira alerta na validação.
        return None
    return "superior" if tem_superior else "medio"


def detectar_cargo_e_nivel_edital(pdf_path: Path) -> dict[str, str | None]:
    """Inspeciona as páginas preliminares do edital para identificar se o concurso
    possui cargo único e/ou nível de escolaridade único (médio/superior).

    Útil para editais de cargo único (ex.: TCU_25_TEFC), onde a seção de Objetos de
    Avaliação não repete 'PARA CARGOS DE NÍVEL...' nem usa 'CARGO 1: ...', pois
    todo o concurso é destinado a um único cargo e nível.
    """
    try:
        with pymupdf.open(pdf_path) as doc:
            texto = "\n".join(page.get_text().replace("\xa0", " ") for page in doc[:15])
    except (pymupdf.FileDataError, OSError, RuntimeError) as e:
        logger.warning(
            f"Não foi possível inspecionar páginas preliminares de {pdf_path.name}: {e}"
        )
        return {"cargo": None, "nivel": None}

    # 1. Detecção de cargo único no item 1 ou 2:
    # '2 DO CARGO DE TÉCNICO...' ou '1 DO CARGO DE ...' (singular, diferente de 'DOS CARGOS')
    cargo_unico = None
    m_cargo = re.search(
        r"\n(?:1|2)\s+DO CARGO(?:\s+DE|\s*:)?\s+([^\n]+)", texto, re.IGNORECASE
    )
    if m_cargo:
        cargo_bruto = m_cargo.group(1).strip()
        # Remove sufixos como '- TEFC', etc.
        cargo_limpo = re.sub(r"\s*[-–]\s*[A-Z0-9/]+\s*$", "", cargo_bruto).strip()
        cargo_unico = cargo_limpo

    return {
        "cargo": cargo_unico,
        "nivel": detectar_nivel_no_texto(texto),
    }


def detectar_nivel_no_texto(texto: str) -> str | None:
    """Nível único ("medio"/"superior") declarado nas páginas preliminares.
    Primeiro pelo bloco de REQUISITOS; sem nenhum trecho de REQUISITOS que
    diga nível, pela "ESCOLARIDADE EXIGIDA PARA O CARGO" (ex.: BANRISUL_25,
    que não tem bloco de requisitos). Se os dois níveis aparecem, fica None.
    """
    requisitos = re.findall(
        r"REQUISITO[S]?:\s*([^\n]+(?:\n[^\n]+){1,3})", texto, re.IGNORECASE
    )
    tem_medio, tem_superior = _niveis_citados(requisitos)
    if not tem_medio and not tem_superior:
        escolaridade = re.findall(
            r"ESCOLARIDADE\s+EXIGIDA[^:\n]*:\s*([^\n]+(?:\n[^\n]+){0,3})", texto
        )
        tem_medio, tem_superior = _niveis_citados(escolaridade)

    if tem_medio and not tem_superior:
        return "medio"
    if tem_superior and not tem_medio:
        return "superior"
    return None


def _niveis_citados(trechos: list[str]) -> tuple[bool, bool]:
    tem_medio = any(
        re.search(
            r"ensino\s+m[ée]dio|n[íi]vel\s+m[ée]dio|intermedi[áa]rio|segundo\s+grau",
            r,
            re.IGNORECASE,
        )
        for r in trechos
    )
    tem_superior = any(
        re.search(
            r"n[íi]vel\s+superior|gradua[çc][ãa]o|bacharelado|licenciatura|terceiro\s+grau",
            r,
            re.IGNORECASE,
        )
        for r in trechos
    )
    return tem_medio, tem_superior


def mapear_cargos(
    chunks: list[ChunkTaxonomia],
    cargo_padrao: str | None = None,
    nivel_padrao: str | None = None,
) -> list[dict]:
    """Lista de cargos do edital com o nível herdado do bloco de
    conhecimentos específicos onde o `CARGO N:` aparece (ex: PF_25_ADM:
    cargos 1–14 superior, 15 médio). Base para ligar os blocos básicos
    (N cargos por nível) aos cadernos CB1/CB2 na Fase 5.
    """
    cargos: dict[int, dict] = {}
    for chunk in chunks:
        if chunk.cargo_numero is None or chunk.cargo_numero in cargos:
            continue
        cargos[chunk.cargo_numero] = {
            "numero": chunk.cargo_numero,
            "nome": chunk.cargo.split(": ", 1)[-1] if chunk.cargo else None,
            "nivel": chunk.nivel,
        }
    if not cargos and cargo_padrao:
        return [
            {
                "numero": 1,
                "nome": cargo_padrao.split(": ", 1)[-1] if cargo_padrao else None,
                "nivel": nivel_padrao,
            }
        ]
    return [cargos[n] for n in sorted(cargos)]


@dataclass
class SecaoExtraida:
    """Seção "OBJETOS DE AVALIAÇÃO" recortada do edital, com os metadados de
    corte (páginas/chars totais do PDF, offsets do recorte) necessários pra
    trilha de auditoria de entrada/saída do parser — ver
    `scripts/revisar_taxonomia_piloto.py`.
    """

    texto: str
    paginas_pdf_total: int
    chars_pdf_total: int
    offset_inicio: int
    offset_fim: int
    marcador_fim_encontrado: (
        bool  # False = cortou até o fim do PDF, sem achar "ANEXO I"
    )
    cargo_detectado: str | None = None
    nivel_detectado: str | None = None


def extrair_texto_paginas(pdf_path: Path) -> list[str]:
    with pymupdf.open(pdf_path) as doc:
        return [page.get_text().replace("\xa0", " ") for page in doc]


def extrair_secao_objetos_avaliacao_detalhada(pdf_path: Path) -> SecaoExtraida | None:
    """Versão de `extrair_secao_objetos_avaliacao` que também devolve os
    metadados do corte (offsets, contagem de páginas/chars do PDF inteiro),
    usados para montar a trilha de auditoria de entrada/saída do filtro.
    Retorna None nas mesmas condições da versão simples (marcador de início
    ausente).
    """
    paginas = extrair_texto_paginas(pdf_path)
    texto_completo = "\n".join(paginas)

    inicio = texto_completo.find(MARCADOR_INICIO_SECAO)
    if inicio == -1:
        logger.warning(
            f"Seção 'OBJETOS DE AVALIAÇÃO' não encontrada em {pdf_path.name}"
        )
        return None

    fim = texto_completo.find(MARCADOR_FIM_SECAO, inicio)
    marcador_fim_encontrado = fim != -1
    if fim == -1:
        fim = len(texto_completo)

    info_edital = detectar_cargo_e_nivel_edital(pdf_path)

    return SecaoExtraida(
        texto=texto_completo[inicio:fim],
        paginas_pdf_total=len(paginas),
        chars_pdf_total=len(texto_completo),
        offset_inicio=inicio,
        offset_fim=fim,
        marcador_fim_encontrado=marcador_fim_encontrado,
        cargo_detectado=info_edital.get("cargo"),
        nivel_detectado=info_edital.get("nivel"),
    )


def extrair_secao_objetos_avaliacao(pdf_path: Path) -> str | None:
    """Recorta a seção "OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)"
    do edital, do marcador de início até o próximo "ANEXO" (ou fim do PDF
    se não houver anexo). Retorna None se o marcador não existir — editais
    diferentes podem numerar/nomear a seção de outro jeito, e isso deve ser
    logado, não estourar exceção (mesmo padrão de resiliência do
    crawler/downloader).
    """
    secao = extrair_secao_objetos_avaliacao_detalhada(pdf_path)
    return secao.texto if secao else None


def _limpar_ruido_edital(texto: str) -> str:
    """Remove ruído administrativo conhecido (não é conteúdo de estudo) que
    aparece embutido no meio do texto programático de um chunk — hoje só a
    nota de retificação (`PADRAO_RETIFICACAO`). Achado ao vivo 2026-09-20:
    esse ruído inflava o chunk sem agregar taxonomia, consumindo orçamento
    de reasoning do LLM à toa. Ver CLAUDE.md seção 12.
    """
    return remover_assinatura_final(PADRAO_RETIFICACAO.sub(" ", texto).strip())


def remover_assinatura_final(texto: str) -> str:
    """Remove o bloco de assinatura do fim da seção de Objetos de Avaliação
    (nome do signatário + cargo), que o recorte da seção cola na cauda do
    último item. Todos os 5 editais de 2025 do piloto terminam assim, em
    formatos diferentes: nome em caixa alta (`RODRIGO AGOSTINHO\\nPresidente
    do Ibama`), nome na mesma linha depois do ponto final do último item (PF),
    nome sem caixa alta (STM, `Ten Brig Ar ...\\nMinistro-Presidente`), cargo
    em várias linhas (TCU, CD).

    Âncora é o **cargo** do signatário (`PADRAO_CARGO_ASSINATURA`), não o
    nome: só conta se estiver no fim do texto, se nada depois dele tiver
    ponto final (item programático termina em ponto; linha de assinatura não)
    e se a linha anterior tiver cara de nome (sem dígito, curta). Qualquer
    dúvida devolve o texto intacto — perder um pedaço de conteúdo é pior que
    deixar a assinatura.
    """
    linhas = texto.rstrip().split("\n")
    idx_cargo = None
    for i in range(len(linhas) - 1, 0, -1):
        if "." in linhas[i]:
            break
        if PADRAO_CARGO_ASSINATURA.match(linhas[i]):
            idx_cargo = i
    if idx_cargo is None:
        return texto

    idx_nome = idx_cargo - 1
    while idx_nome > 0 and not linhas[idx_nome].strip():
        idx_nome -= 1
    prefixo, _, nome = linhas[idx_nome].rpartition(". ")
    nome = nome.strip()
    if not nome or len(nome) > 80 or len(nome.split()) < 2 or re.search(r"\d", nome):
        return texto
    if len("\n".join(linhas[idx_cargo:])) > 300:
        return texto

    manter = linhas[:idx_nome] + ([f"{prefixo}."] if prefixo else [])
    return "\n".join(manter).strip()


def extrair_itens_numerados(texto: str) -> list[tuple[str, str]]:
    """Retorna [(numero, texto_do_item)] para os itens de primeiro nível do
    texto-fonte — da posição após o número até o próximo item de primeiro
    nível (inclui o texto de subitens/alíneas do próprio item).

    Não corta na primeira "." — citações legais dentro do próprio item
    (ex.: "Lei nº 8.429/1992") têm ponto embutido no meio do rótulo, e um
    corte ingênuo trunca o texto antes do fim do rótulo real.
    """
    matches = list(PADRAO_ITEM_NUMERADO.finditer(texto))
    itens = []
    for i, match in enumerate(matches):
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        item_texto = texto[match.end() : fim].strip()
        if item_texto:
            itens.append((match.group(1), item_texto))
    return itens


# Candidato a subitem numerado ("1.2", "1.2.10.1", "21.1.6"): profundidade >= 2,
# seguido de espaço e de letra (maiúscula OU minúscula: o BANRISUL tem
# "2.1 acessibilidade e usabilidade") ou "(". Não casa "8.069/1990" (sem
# espaço depois) nem número colado a outro (`(?<![\d./])`).
PADRAO_SUBITEM_CANDIDATO = re.compile(
    r"(?<![\d/])(\d{1,3}(?:\.\d{1,3})+)\.?\s+(?=[A-Za-zÀ-ÿ(])"
)

# Item de 1º nível escrito com ponto ("8. Psicologia social"), que
# `PADRAO_ITEM_NUMERADO` não enxerga. Aqui só serve para encerrar o texto do
# subitem anterior e trocar o item corrente; exige a mesma fronteira.
PADRAO_ITEM_PRIMEIRO_NIVEL_COM_PONTO = re.compile(
    r"(?<![\d/.])(\d{1,3})\.\s+(?=[A-ZÀ-Ú])"
)

# Nota de retificação colada ao subitem, ex.: "(Incluído por meio do Edital
# nº 2 – SEFA/PR, ...)" — não faz parte do texto do item.
PADRAO_NOTA_RETIFICACAO = re.compile(
    r"\(\s*(?:Inclu[íi]d[oa]s?|Alterad[oa]s?|Retificad[oa]s?)\s+por\s+meio\b[^)]*\)?",
    re.IGNORECASE,
)

# Pontuação que pode vir logo antes de um subitem verdadeiro ("...texto. 1.2 Foo",
# "...(PCASP). 9.1 ..."). Número precedido de palavra ("NBC T 16.1 a 16.11",
# "UML 2.5.1 (2017)", "JPA 2.0 e") é número dentro do texto, não item.
FRONTEIRA_SUBITEM = ".;:!?)]"

# Tolerância para o 1º filho de um item (normalmente ".1"): retificações do
# edital podem excluir os primeiros irmãos.
MAXIMO_PRIMEIRO_FILHO = 3


def _fronteira_de_item(texto: str, posicao: int) -> bool:
    """Antes do número só há espaço/quebra de linha e, antes disso, início do
    texto ou pontuação de fim de item."""
    i = posicao - 1
    while i >= 0 and texto[i].isspace():
        i -= 1
    return i < 0 or texto[i] in FRONTEIRA_SUBITEM


def extrair_subitens_numerados(texto: str) -> list[tuple[str, str]]:
    """Retorna [(numero, texto_proprio)] dos subitens (profundidade >= 2:
    "1.2", "1.2.10.1") do texto-fonte. O texto próprio vai da posição após o
    número até o início do próximo item de QUALQUER nível (um subitem não
    inclui os filhos, ao contrário de `extrair_itens_numerados`).

    Um candidato só é aceito como item se passar em três critérios, para não
    confundir número dentro do texto ("NBC T 16.1 a 16.11", "UML 2.5.1 (2017)",
    "Lei nº 8.069/1990", "JPA 2.0") com subitem:
    1. fronteira: antes dele só há início de texto ou pontuação de fim de
       item (`.`, `;`, `:`, `!`, `?`, `)`, `]`);
    2. pai visível: o 1º componente é o item de 1º nível corrente (o último
       visto via `PADRAO_ITEM_NUMERADO`) e o pai imediato ("1.2" para
       "1.2.10") está no caminho de itens já aceitos;
    3. sequência plausível: se o pai já tem filho aceito, o número novo é
       maior que o último irmão; se é o 1º filho, é <= MAXIMO_PRIMEIRO_FILHO.
    Sem item de 1º nível visto, nada é aceito.
    """
    texto = remover_assinatura_final(texto)
    eventos = [
        (m.start(), m.end(), (int(m.group(1)),), True)
        for m in PADRAO_ITEM_NUMERADO.finditer(texto)
    ]
    for m in PADRAO_ITEM_PRIMEIRO_NIVEL_COM_PONTO.finditer(texto):
        if _fronteira_de_item(texto, m.start()):
            eventos.append((m.start(), m.end(), (int(m.group(1)),), True))
    for m in PADRAO_SUBITEM_CANDIDATO.finditer(texto):
        if _fronteira_de_item(texto, m.start()):
            numero = tuple(int(p) for p in m.group(1).split("."))
            eventos.append((m.start(), m.end(), numero, False))
    eventos.sort(key=lambda e: (e[0], not e[3]))

    aceitos: list[tuple[int, int, tuple[int, ...]]] = []
    caminho: list[tuple[int, ...]] = []
    for inicio, fim, numero, primeiro_nivel in eventos:
        if primeiro_nivel:
            caminho = [numero]
            aceitos.append((inicio, fim, numero))
            continue
        profundidade = len(numero)
        if len(caminho) < profundidade - 1 or caminho[profundidade - 2] != numero[:-1]:
            continue
        if len(caminho) >= profundidade:
            if numero[-1] <= caminho[profundidade - 1][-1]:
                continue
        elif numero[-1] > MAXIMO_PRIMEIRO_FILHO:
            continue
        caminho = caminho[: profundidade - 1] + [numero]
        aceitos.append((inicio, fim, numero))

    subitens = []
    for i, (_, fim, numero) in enumerate(aceitos):
        if len(numero) < 2:
            continue
        limite = aceitos[i + 1][0] if i + 1 < len(aceitos) else len(texto)
        proprio = PADRAO_NOTA_RETIFICACAO.sub("", texto[fim:limite]).strip()
        if proprio:
            subitens.append((".".join(map(str, numero)), proprio))
    return subitens


# Número de item com subníveis ("2", "2.1", "21.1.6"). Mesma ideia de
# PADRAO_ITEM_NUMERADO, mas enxerga os descendentes, que precisam ser achados
# para saber onde termina um item excluído.
PADRAO_ITEM_HIERARQUICO = re.compile(
    r"(?<![\d.])(\d{1,3}(?:\.\d{1,3})*)\s+(?=[A-ZÀ-Ú(])"
)

# Nota de retificação que marca item excluído do edital, ex.:
# "(Tópico 29 excluído por meio do Edital nº 2 – SEFA/PR, ...)". Só "excluí"
# casa: a nota "(Incluído por meio do Edital ...)" é conteúdo novo e fica.
PADRAO_NOTA_EXCLUSAO = re.compile(
    r"\(\s*(?:T[óo]picos?|Subitens?|Subitem|Itens?|Item)\s+"
    r"(?P<numeros>\d+(?:\.\d+)*(?:\s*(?:,|e)\s*\d+(?:\.\d+)*)*)\s+"
    r"exclu[íi]d[oa]s?[^)]*\)"
)


def _inicio_do_item(texto: str, numero: str, ate: int) -> int | None:
    """Posição do último item `numero` que começa antes de `ate`."""
    inicio = None
    for m in PADRAO_ITEM_HIERARQUICO.finditer(texto, 0, ate):
        if m.group(1) == numero:
            inicio = m.start()
    return inicio


def remover_topicos_excluidos(texto: str) -> str:
    """Remove itens excluídos por retificação do edital, antes do LLM.

    Para cada nota "(Tópico N excluído ...)": remove a nota e o item N, que
    vai do início de "N " até o início do próximo item que não seja
    descendente de N (ou até a nota). Subitens N.x vão junto. Nota sem o
    item correspondente no texto remove só a nota e loga aviso. Notas
    "(Incluído ...)" não são tocadas.
    """
    alterado = False
    while True:
        nota = PADRAO_NOTA_EXCLUSAO.search(texto)
        if nota is None:
            break
        alterado = True
        intervalos = [(nota.start(), nota.end())]
        for numero in re.findall(r"\d+(?:\.\d+)*", nota.group("numeros")):
            inicio = _inicio_do_item(texto, numero, nota.start())
            if inicio is None:
                logger.warning(
                    f"[TOPICO_EXCLUIDO_SEM_ITEM] nota cita o item {numero}, mas o "
                    "texto não tem esse item antes dela; só a nota foi removida"
                )
                continue
            fim = nota.start()
            for m in PADRAO_ITEM_HIERARQUICO.finditer(texto, inicio + 1, nota.start()):
                n = m.group(1)
                if n != numero and not n.startswith(f"{numero}."):
                    fim = m.start()
                    break
            intervalos.append((inicio, fim))
            logger.info(f"[TOPICO_EXCLUIDO] item {numero} removido do texto do chunk")
        for ini, fim in sorted(intervalos, reverse=True):
            texto = texto[:ini] + texto[fim:]
    return texto.rstrip() if alterado else texto


def checar_ordem_confiavel(pdf_path: Path, pagina_inicio: int, pagina_fim: int) -> bool:
    """Validação de sanidade contra embaralhamento multi-coluna.

    `page.get_text()` (usado em `extrair_secao_objetos_avaliacao`) não
    garante ordem de leitura correta em layouts de múltiplas colunas — ele
    pode intercalar texto da coluna esquerda com a direita. Essa função
    inspeciona os blocos de texto (`get_text("blocks")`, que vêm com
    coordenadas x0) nas páginas do intervalo dado: se blocos de texto
    *longos* (corpo de texto, não títulos/assinaturas curtos) começam em
    margens x0 bem diferentes na mesma página, é sinal de colunas lado a
    lado — a ordem de `get_text()` pode estar errada e o resultado deve
    ser revisado manualmente antes de confiar em lote.

    Validado ao vivo (2026-09-19) contra `Ed_1_2025_PF_Administrativo_
    Abertura_atualizado_ret_5.pdf`, páginas 44–62: layout de coluna única
    (todo bloco de corpo de texto com x0 ≈ 42.5). A página 62 tem um bloco
    de assinatura centralizado (x0 ≈ 218) que dispara falso positivo se a
    checagem não ignorar blocos curtos — por isso o piso de
    `TAMANHO_MINIMO_BLOCO_COLUNA`.
    """
    margem_tolerancia = 50  # pontos; acima disso, considera colunas distintas
    with pymupdf.open(pdf_path) as doc:
        for i in range(pagina_inicio - 1, min(pagina_fim, len(doc))):
            blocks = doc[i].get_text("blocks")
            x0s = [
                b[0] for b in blocks if len(b[4].strip()) >= TAMANHO_MINIMO_BLOCO_COLUNA
            ]
            if not x0s:
                continue
            if max(x0s) - min(x0s) > margem_tolerancia:
                logger.warning(
                    f"Página {i + 1} de {pdf_path.name} tem blocos de corpo de texto "
                    f"com x0 variando de {min(x0s):.1f} a {max(x0s):.1f} — possível "
                    "layout multi-coluna; revisar a ordem do texto extraído antes "
                    "de confiar no output em lote."
                )
                return False
    return True


def dividir_por_cargo_e_materia(
    secao_texto: str,
    cargo_padrao: str | None = None,
    nivel_padrao: str | None = None,
    cargo_numero_padrao: int | None = None,
) -> list[ChunkTaxonomia]:
    """Chunking: separa o texto da seção de objetos de avaliação em blocos
    por cargo e por matéria, prontos para virar prompt de extração LLM.

    Percorre os cabeçalhos de cargo (`CARGO N: <nome>`) e de matéria
    (`NOME DA MATÉRIA: ...`) em ordem de aparição no texto, mantendo qual é
    o cargo corrente. Dois formatos reais coexistem no mesmo edital:
    - cargo com matérias nomeadas à parte (ex: "CARGO 1: ADMINISTRADOR"
      seguido de "ADMINISTRAÇÃO GERAL E PÚBLICA:", "GESTÃO DE PESSOAS:" etc.)
      → 1 chunk por matéria, todos com o mesmo `cargo`;
    - cargo de especialidade sem matéria nomeada à parte (ex: "CARGO 7:
      MÉDICO CLÍNICO" com o conteúdo programático direto embaixo) → 1
      chunk cujo `materia` é o próprio nome do cargo.
    Matérias fora de qualquer cargo (bloco de CONHECIMENTOS BÁSICOS) saem
    com `cargo=None`.

    Um terceiro tipo de marcador, o cabeçalho de bloco (`CONHECIMENTOS
    BÁSICOS/ESPECÍFICOS PARA ... NÍVEL SUPERIOR/MÉDIO`, ver PADRAO_BLOCO),
    não gera chunk: define `tipo_conhecimento`/`nivel` de todo chunk até o
    próximo bloco, zera o cargo corrente (um bloco básico depois de um
    específico não pode herdar cargo) e serve de fronteira — sem ele, o
    próprio cabeçalho do bloco seguinte grudava na cauda do chunk anterior.
    """
    marcadores = []
    for m in PADRAO_BLOCO.finditer(secao_texto):
        marcadores.append(
            (
                m.start(),
                m.end(),
                "bloco",
                (TIPO_CONHECIMENTO[m.group(1)], _nivel_do_bloco(m.group(2))),
            )
        )
    for m in PADRAO_CARGO.finditer(secao_texto):
        rotulo_cargo = f"CARGO {m.group(1)}: {m.group(2).strip()}"
        marcadores.append(
            (m.start(), m.end(), "cargo", (rotulo_cargo, int(m.group(1))))
        )
    for m in PADRAO_AREA.finditer(secao_texto):
        numero = int(m.group(1))
        nome_area = re.sub(r"\s+", " ", m.group(2).strip())
        prefixo = f"CARGO {numero}: "
        if cargo_padrao is not None:
            prefixo += f"{cargo_padrao} – "
        rotulo_cargo = f"{prefixo}ÁREA {numero}: {nome_area}"
        marcadores.append((m.start(), m.end(), "cargo", (rotulo_cargo, numero)))
    romanos = list(PADRAO_SUBMATERIA_ROMANA.finditer(secao_texto))
    inicios_romanos = [m.start() for m in romanos]
    for m in PADRAO_MATERIA.finditer(secao_texto):
        if _conflita_com_submateria_romana(m.start(), m.end(), romanos):
            continue
        # Cabeçalho guarda-chuva ("A, B E C:") seguido direto de "I ...": quem
        # vira chunk são as sub-matérias. Vira só fronteira ("descartada"), senão
        # o nome do guarda-chuva vazaria para o fim do chunk anterior.
        proximo_romano = next((i for i in inicios_romanos if i >= m.end()), None)
        if (
            proximo_romano is not None
            and not secao_texto[m.end() : proximo_romano].strip()
        ):
            marcadores.append((m.start(), m.end(), "descartada", None))
            continue
        marcadores.append(
            (m.start(), m.end(), "materia", re.sub(r"\s+", " ", m.group(1).strip()))
        )
    for m in romanos:
        marcadores.append(
            (m.start(), m.end(), "materia", re.sub(r"\s+", " ", m.group(1).strip()))
        )
    marcadores.sort(key=lambda x: x[0])

    if not any(tipo != "bloco" for _, _, tipo, _ in marcadores):
        return []

    chunks: list[ChunkTaxonomia] = []
    cargo_atual: str | None = None
    cargo_numero_atual: int | None = None
    tipo_conhecimento_atual: str | None = None
    nivel_atual: str | None = None
    for idx, (_, fim_cabecalho, tipo, rotulo) in enumerate(marcadores):
        proximo_inicio = (
            marcadores[idx + 1][0] if idx + 1 < len(marcadores) else len(secao_texto)
        )
        texto_bloco = _limpar_ruido_edital(
            secao_texto[fim_cabecalho:proximo_inicio].strip()
        )

        if tipo == "descartada":
            continue

        if tipo == "bloco":
            tipo_conhecimento_atual, nivel_bloco = rotulo
            nivel_atual = nivel_bloco if nivel_bloco is not None else nivel_padrao
            if tipo_conhecimento_atual == "especifico" and cargo_padrao is not None:
                cargo_atual = (
                    f"CARGO 1: {cargo_padrao}"
                    if not cargo_padrao.startswith("CARGO")
                    else cargo_padrao
                )
                cargo_numero_atual = (
                    cargo_numero_padrao if cargo_numero_padrao is not None else 1
                )
            else:
                cargo_atual, cargo_numero_atual = None, None
            if nivel_atual is None:
                logger.warning(
                    f"Bloco '{secao_texto[marcadores[idx][0] : fim_cabecalho].strip()}' sem nível único "
                    "(médio/superior) — matérias desse bloco ficam com nivel=None."
                )
            continue

        classificacao = {
            "tipo_conhecimento": tipo_conhecimento_atual,
            "nivel": nivel_atual,
        }
        if tipo == "cargo":
            cargo_atual, cargo_numero_atual = rotulo
            itens = extrair_itens_numerados(texto_bloco)
            if not itens:
                # Não há itens programáticos diretos: qualquer texto intermediário
                # (ex.: quebra de linha do título do cargo no PDF) é continuação do rótulo
                if texto_bloco:
                    cargo_limpo = _limpar_ruido_edital(
                        f"{cargo_atual} {texto_bloco}"
                    ).strip()
                    cargo_atual = re.sub(r"[ \t]+", " ", cargo_limpo)
            else:
                m_primeiro_item = PADRAO_ITEM_NUMERADO.search(texto_bloco)
                prefixo_materia = (
                    texto_bloco[: m_primeiro_item.start()].strip()
                    if m_primeiro_item
                    else ""
                )
                if (
                    prefixo_materia
                    and len(prefixo_materia) >= 3
                    and prefixo_materia.isupper()
                ):
                    materia_nome = re.sub(r"\s+", " ", prefixo_materia)
                    texto_final = texto_bloco[m_primeiro_item.start() :].strip()
                    materia_origem = "prefixo"
                else:
                    materia_nome = re.sub(
                        r"\s+", " ", cargo_atual.split(": ", 1)[-1].strip()
                    )
                    texto_final = texto_bloco
                    materia_origem = "cargo"

                chunks.append(
                    ChunkTaxonomia(
                        cargo=cargo_atual,
                        materia=materia_nome,
                        texto=texto_final,
                        offset_inicio=fim_cabecalho,
                        offset_fim=proximo_inicio,
                        cargo_numero=cargo_numero_atual,
                        materia_origem=materia_origem,
                        **classificacao,
                    )
                )
            continue

        chunks.append(
            ChunkTaxonomia(
                cargo=cargo_atual,
                materia=rotulo,
                texto=texto_bloco,
                offset_inicio=fim_cabecalho,
                offset_fim=proximo_inicio,
                cargo_numero=cargo_numero_atual,
                materia_origem="cabecalho",
                **classificacao,
            )
        )

    # Itens excluídos por retificação saem antes do LLM (ver remover_topicos_excluidos).
    for chunk in chunks:
        chunk.texto = remover_topicos_excluidos(chunk.texto)

    _logar_restricoes(chunks)
    return chunks


def _conflita_com_submateria_romana(
    inicio: int, fim: int, romanos: list[re.Match]
) -> bool:
    return any(inicio < m.end() and m.start() < fim for m in romanos)


def _logar_restricoes(chunks: list[ChunkTaxonomia]) -> None:
    for indice, chunk in enumerate(chunks):
        if chunk.cargos_restritos:
            logger.info(
                f"[RESTRICAO_CARGO] chunk #{indice} '{chunk.materia_normalizada}' → só cargos {chunk.cargos_restritos}"
            )
        if any(not numeros for _, numeros in restricoes_de_cargo(chunk.materia)):
            logger.warning(
                f"[RESTRICAO_SEM_CARGO] chunk #{indice} matéria '{chunk.materia}' tem restrição de cargo sem "
                "número — mantida no nome, cargos_restritos não preenchido."
            )
