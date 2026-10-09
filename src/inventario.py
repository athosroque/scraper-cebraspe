"""Inventário de concursos do CEBRASPE (2020 até hoje).

Módulo canônico para classificação de links de PDFs e persistência
de inventário em JSON e JSONL.
"""

import json
import re
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # type: ignore

from src.comparacao_texto import (
    PADRAO_EDITAL_ADMINISTRATIVO,
    PADRAO_PADRAO_RESPOSTA,
    normalizar,
)

SLUGS_NAVEGACAO = {"em-andamento", "encerrado", "inscricoes-abertas", "novos", "main"}
PROJETO_DIR = Path(__file__).resolve().parent.parent
INVENTARIO_DIR = PROJETO_DIR / "inventario"
INVENTARIO_ANOS_PATH = INVENTARIO_DIR / "anos.json"
INVENTARIO_CONCURSOS_PATH = INVENTARIO_DIR / "concursos.jsonl"
INVENTARIO_RELATORIO_PATH = INVENTARIO_DIR / "RELATORIO.md"
INVENTARIO_EXCLUSOES_PATH = INVENTARIO_DIR / "exclusoes.json"
AMOSTRA_DIR = PROJETO_DIR / "data" / "inventario_amostra"
CONCURSOS_PILOTO = {"PF_25_ADM", "TCU_25_TEFC", "IBAMA_25", "STM_25", "CD_25_NS"}

TIPO_EDITAL_ABERTURA = "edital_abertura"
TIPO_CADERNO_OBJETIVO = "caderno_objetivo"
# "PROVA E GABARITO DEFINITIVO", "PROVA OBJETIVA (P1) E GABARITO PRELIMINAR COM
# JUSTIFICATIVAS": um só PDF com as questões e o gabarito de cada uma.
TIPO_CADERNO_COM_GABARITO = "caderno_com_gabarito"
TIPO_CADERNO_DISCURSIVO = "caderno_discursivo"
TIPO_GABARITO = "gabarito"
TIPO_PADRAO_RESPOSTA = "padrao_resposta"
TIPO_PROVA_OUTRA = "prova_outra"
TIPO_ADMINISTRATIVO = "administrativo"
TIPO_NAO_CLASSIFICADO = "nao_classificado"

FORMATO_CE = "ce"
FORMATO_ME = "me"
FORMATO_MISTO = "misto"
FORMATO_DESCONHECIDO = "?"

# Alternativa de questão ME em início de linha. O CEBRASPE usa "A texto"
# sem parênteses; "(A)", "A)" e "A." aparecem em outras bancas e nos testes.
PADRAO_ALTERNATIVA_ME = re.compile(
    r"^[ \t]*(?:\(([A-E])\)|([A-E])[\)\.]?)(?=[ \t]+\S|[ \t]*$)", re.MULTILINE
)
PADRAO_CABECALHO_QUESTAO = re.compile(r"^[ \t]*QUEST[ÃA]O\s+\d+", re.MULTILINE | re.I)
PADRAO_JULGUE = re.compile(r"\bjulgue\b", re.IGNORECASE)
PADRAO_MARCADOR_CE = re.compile(
    r"\bc[óo]digo\s+[CE]\b|\(C\)\s*\(E\)|\[C\]\s*\[E\]|\bmarqu?e\s+o\s+campo\s+[CE]\b"
    r"|\bCERTO\b.*\bERRADO\b|\bERRADO\b.*\bCERTO\b",
    re.IGNORECASE | re.DOTALL,
)
# Distância máxima entre a alternativa A e a D de um mesmo bloco, e entre um
# "julgue" e as alternativas da mesma questão quando não há "Questão N".
JANELA_ALTERNATIVAS = 4000
ALTURA_MINIMA_FIGURA = 100
LARGURA_MINIMA_FIGURA = 80
MARGEM_CABECALHO_FIGURA = 90
MARGEM_RODAPE_FIGURA = 80


# Comunicado, relação de candidatos etc. citam "prova" no título sem serem
# caderno ("Comunicado – Suspensão da prova objetiva"). Fica fora de
# PADRAO_EDITAL_ADMINISTRATIVO porque o stats_writer do piloto usa aquele.
PADRAO_ADMINISTRATIVO_INICIO = re.compile(
    r"^(?:comunicado|relacao|relatorio|composicao|movimentacao|manual|adiamento"
    r"|edital|orientac\w*|sorteio|justificativ\w*)\b"
)
# Prova sem caderno a extrair: oral, didática, tribuna, desempenho prático.
PADRAO_PROVA_OUTRA = re.compile(
    r"\boral\b|\bdidatic|\btribuna\b|\bdesempenho\b|\bsustentacao\b|\bhabilidades\b"
)
# Prova escrita não objetiva que o link não chama de "discursiva"
# ("PROVA ESCRITA DE DIREITO – SEGUNDA FASE", "PROVA SUBJETIVA – P2").
PADRAO_PROVA_ESCRITA = re.compile(r"\bdiscursiv|\bescritas?\b|\bsubjetiv|\bpratic")
# A abertura vem no início do título ("Edital nº 1 – Abertura", "Comunicado nº 1
# – Abertura" do SEBRAE). Solta no meio, é citação: "Edital nº 21 – Prorrogação
# ... do edital de abertura", "Respostas às impugnações ao Edital nº 1 – Abertura".
# "Abertura do prazo/do link/dos portões" também não é o edital de abertura.
PADRAO_EDITAL_ABERTURA = re.compile(
    r"^(?:portaria conjunta e )?(?:edital|comunicado)\b[^a-z]*(?:no?\b[^a-z]*)?"
    r"(?:de\s+)?abertura\b(?!\s+(?:d[oa]s?|de)\b)"
)
# Prova e gabarito no mesmo PDF ("PROVA E GABARITO", "PROVA OBJETIVA (P1) E
# GABARITO"). "1ª PROVA OBJETIVA - GABARITO PRELIMINAR" é só o gabarito.
PADRAO_CADERNO_COM_GABARITO = re.compile(r"\bprovas?\b.*\be gabaritos?\b")
# Link que cita o gabarito sem ser ele: justificativas, recursos, consultas.
PADRAO_GABARITO_ADMINISTRATIVO = re.compile(
    r"justificativ|recurso|prorroga|reabertura|\blink\b|consulta|indisponib"
    r"|esclarecimento|sessao|informac"
)
# Caderno discursivo do SEBRAE: "QUESTÃO DISCURSIVA (ESTUDO DE CASO) – PERFIL 1".
PADRAO_QUESTAO_DISCURSIVA = re.compile(r"^quest(?:ao|oes) discursivas?\b")


def _e_administrativo(texto_bruto: str, texto_norm: str) -> bool:
    """Verifica se o link refere-se a edital ou comunicado administrativo."""
    return bool(
        PADRAO_EDITAL_ADMINISTRATIVO.search(texto_bruto)
        or PADRAO_EDITAL_ADMINISTRATIVO.search(texto_norm)
        or PADRAO_EDITAL_ADMINISTRATIVO.search(texto_bruto.lower())
        or re.search(r"\bcomunicados?\s+loca(?:l|is)\b", texto_norm)
        or PADRAO_ADMINISTRATIVO_INICIO.search(texto_norm)
    )


def _e_edital_abertura(texto_norm: str) -> bool:
    """Verifica se é edital de abertura (incluindo versões atualizadas por retificação).

    "Edital nº 2 – Retificação do edital de abertura" e "reabertura" não casam:
    a abertura tem de vir logo depois do número do edital.
    """
    return bool(PADRAO_EDITAL_ABERTURA.search(texto_norm))


def classificar_link_pdf(texto: str) -> dict[str, Any]:
    """Classifica um link de PDF do CEBRASPE a partir do texto descritivo.

    Retorna um dicionário com:
        - tipo: um dos TIPO_*
        - versao: "definitivo" | "preliminar" | "desconhecida"
        - curso_formacao: bool indicando se refere-se a curso de formação
    """
    # Há link com o nome do arquivo no lugar do título ("CTI_23_PROVA_ORAL_...").
    texto_norm = normalizar((texto or "").replace("_", " "))

    # Versão
    if "definitiv" in texto_norm:
        versao = "definitivo"
    elif "preliminar" in texto_norm or "provisori" in texto_norm:
        versao = "preliminar"
    else:
        versao = "desconhecida"

    # Flag curso de formação
    curso_formacao = "curso de formacao" in texto_norm

    # 1. Padrão de resposta (deve vir antes de "PROVA")
    if PADRAO_PADRAO_RESPOSTA.search(texto or "") or PADRAO_PADRAO_RESPOSTA.search(
        texto_norm
    ):
        return {
            "tipo": TIPO_PADRAO_RESPOSTA,
            "versao": versao,
            "curso_formacao": curso_formacao,
        }

    # 2. Gabarito (e caderno que já traz o gabarito)
    if "gabarito" in texto_norm:
        if PADRAO_CADERNO_COM_GABARITO.search(texto_norm):
            tipo = TIPO_CADERNO_COM_GABARITO
        # O nome do cargo pode ter "recursos" ("GABARITO DEFINITIVO - 16: ...
        # SALAS DE RECURSOS"): título que começa com gabarito é gabarito.
        elif not texto_norm.startswith("gabarito") and (
            PADRAO_GABARITO_ADMINISTRATIVO.search(texto_norm)
        ):
            tipo = TIPO_ADMINISTRATIVO
        else:
            tipo = TIPO_GABARITO
        return {
            "tipo": tipo,
            "versao": versao,
            "curso_formacao": curso_formacao,
        }

    # 3. Edital de abertura
    if _e_edital_abertura(texto_norm):
        return {
            "tipo": TIPO_EDITAL_ABERTURA,
            "versao": versao,
            "curso_formacao": curso_formacao,
        }

    # 4. Caderno de prova
    # Palavra inteira: "Portaria ... Aprova o Regulamento" não é caderno.
    if re.search(r"\bprovas?\b", texto_norm):
        if _e_administrativo(texto or "", texto_norm):
            tipo = TIPO_ADMINISTRATIVO
        elif PADRAO_PROVA_OUTRA.search(texto_norm):
            tipo = TIPO_PROVA_OUTRA
        elif "objetiv" in texto_norm:
            tipo = TIPO_CADERNO_OBJETIVO
        elif PADRAO_PROVA_ESCRITA.search(texto_norm):
            tipo = TIPO_CADERNO_DISCURSIVO
        else:
            tipo = TIPO_CADERNO_OBJETIVO
        return {
            "tipo": tipo,
            "versao": versao,
            "curso_formacao": curso_formacao,
        }

    # 5. Outro edital/comunicado administrativo
    if _e_administrativo(texto or "", texto_norm):
        return {
            "tipo": TIPO_ADMINISTRATIVO,
            "versao": versao,
            "curso_formacao": curso_formacao,
        }

    # 6. Caderno discursivo sem a palavra "prova"
    if PADRAO_QUESTAO_DISCURSIVA.search(texto_norm):
        return {
            "tipo": TIPO_CADERNO_DISCURSIVO,
            "versao": versao,
            "curso_formacao": curso_formacao,
        }

    # 7. Não classificado
    return {
        "tipo": TIPO_NAO_CLASSIFICADO,
        "versao": versao,
        "curso_formacao": curso_formacao,
    }


TIPOS_CADERNO_OBJETIVO = (TIPO_CADERNO_OBJETIVO, TIPO_CADERNO_COM_GABARITO)
TIPOS_CADERNO = (*TIPOS_CADERNO_OBJETIVO, TIPO_CADERNO_DISCURSIVO)
TIPOS_GABARITO = (TIPO_GABARITO, TIPO_CADERNO_COM_GABARITO)
TIPOS_PROVA = (*TIPOS_CADERNO, TIPO_GABARITO, TIPO_PADRAO_RESPOSTA)
TIPOS_CONTAGEM = (
    TIPO_EDITAL_ABERTURA,
    TIPO_CADERNO_OBJETIVO,
    TIPO_CADERNO_COM_GABARITO,
    TIPO_CADERNO_DISCURSIVO,
    TIPO_PROVA_OUTRA,
    TIPO_GABARITO,
    TIPO_PADRAO_RESPOSTA,
    TIPO_ADMINISTRATIVO,
    TIPO_NAO_CLASSIFICADO,
)
LIMITE_NAO_CLASSIFICADOS = 5
# Sem prova publicada ainda: alerta "aguardando_prova", não pendência.
SITUACOES_SEM_PROVA_AINDA = {"em_andamento", "inscricoes_abertas", "novos"}

# Concursos fora do site (ADR-037). Fonte: inventario/exclusoes.json.
CATEGORIAS_EXCLUSAO = {
    "cancelado": "Concurso cancelado ou suspenso antes da prova",
    "sem_prova": "Seleção só por títulos/currículo, sem prova",
    "pagina_vazia": "Página do concurso sem nenhum documento",
    "discursiva_sem_caderno": "Só o padrão de resposta foi publicado, sem o caderno",
    "nao_e_concurso": "Exame de certificação, não concurso",
    "curso_formacao": "Página só do curso de formação",
}


def pdf_vai_para_o_site(pdf: dict[str, Any]) -> bool:
    """PDF de prova que entra no site: caderno, gabarito ou padrão de resposta.

    Prova de curso de formação fica fora (ADR-037): cobra o conteúdo do
    curso, não o edital.
    """
    return pdf.get("tipo") in TIPOS_PROVA and not pdf.get("curso_formacao")


def resumir_pdfs(
    slug: str, pdfs: list[dict[str, Any]], situacao: str | None = None
) -> dict[str, Any]:
    """Contagens por tipo, `qtd_*` e alertas de um concurso a partir dos PDFs.

    `contagens` traz todos os PDFs por tipo. `qtd_cadernos`, `qtd_gabaritos`
    e `qtd_padroes` contam só o que vai para o site (`pdf_vai_para_o_site`);
    o caderno com gabarito conta nos dois.
    """
    por_tipo = Counter(p.get("tipo") for p in pdfs)
    contagens = {tipo: por_tipo.get(tipo, 0) for tipo in TIPOS_CONTAGEM}
    do_site = Counter(p.get("tipo") for p in pdfs if pdf_vai_para_o_site(p))
    qtd_objetivos = sum(do_site[t] for t in TIPOS_CADERNO_OBJETIVO)
    qtd_cadernos = sum(do_site[t] for t in TIPOS_CADERNO)
    qtd_gabaritos = sum(do_site[t] for t in TIPOS_GABARITO)
    qtd_padroes = do_site[TIPO_PADRAO_RESPOSTA]

    alertas: list[str] = []
    if contagens[TIPO_EDITAL_ABERTURA] == 0:
        alertas.append("sem_edital_abertura")
    if (
        situacao in SITUACOES_SEM_PROVA_AINDA
        and qtd_cadernos + qtd_gabaritos + qtd_padroes == 0
    ):
        alertas.append("aguardando_prova")
    else:
        if qtd_cadernos == 0:
            alertas.append("sem_caderno")
        # Discursiva tem padrão de resposta, não gabarito.
        if qtd_objetivos > 0 and qtd_gabaritos == 0:
            alertas.append("sem_gabarito")
    # Segmento "CF" inteiro: PM_DF_25_CFO (Curso de Formação de Oficiais) é
    # concurso de ingresso, com prova coletada normalmente.
    if "CF" in slug.upper().split("_") or any(
        p.get("curso_formacao") and p.get("tipo") in TIPOS_PROVA for p in pdfs
    ):
        alertas.append("curso_formacao")
    if contagens[TIPO_NAO_CLASSIFICADO] > LIMITE_NAO_CLASSIFICADOS:
        alertas.append("muitos_nao_classificados")
    if re.search(r"_\d{4}(?:_|$)", slug):
        alertas.append("ano_4_digitos")

    return {
        "qtd_editais": contagens[TIPO_EDITAL_ABERTURA],
        "qtd_cadernos": qtd_cadernos,
        "qtd_gabaritos": qtd_gabaritos,
        "qtd_padroes": qtd_padroes,
        "qtd_curso_formacao": sum(
            1 for p in pdfs if p.get("curso_formacao") and p.get("tipo") in TIPOS_PROVA
        ),
        "qtd_administrativos": contagens[TIPO_ADMINISTRATIVO],
        "qtd_nao_classificados": contagens[TIPO_NAO_CLASSIFICADO],
        "contagens": contagens,
        "alertas": alertas,
    }


def carregar_exclusoes(
    caminho: Path = INVENTARIO_EXCLUSOES_PATH,
) -> dict[str, dict[str, str]]:
    """Lê `inventario/exclusoes.json`: slug → {categoria, motivo}.

    Categoria fora de `CATEGORIAS_EXCLUSAO`, motivo vazio ou slug repetido
    levantam ValueError (a lista é editada à mão).
    """
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    exclusoes: dict[str, dict[str, str]] = {}
    for item in dados.get("concursos") or []:
        slug = item.get("slug")
        if not slug or slug in exclusoes:
            raise ValueError(f"exclusoes.json: slug vazio ou repetido ({slug!r})")
        if item.get("categoria") not in CATEGORIAS_EXCLUSAO:
            raise ValueError(
                f"exclusoes.json: categoria {item.get('categoria')!r} inválida em {slug}"
            )
        if not (item.get("motivo") or "").strip():
            raise ValueError(f"exclusoes.json: {slug} sem motivo")
        exclusoes[slug] = {"categoria": item["categoria"], "motivo": item["motivo"]}
    return exclusoes


def aplicar_exclusao(
    registro: dict[str, Any], exclusoes: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """Marca `incluir` e `exclusao` no registro a partir da lista de exclusões.

    Concurso fora da lista entra no site (`incluir=True`, decisão do dono em
    2026-10-09); o da lista fica `incluir=False` com categoria e motivo.
    """
    exclusao = exclusoes.get(registro.get("slug", ""))
    return {**registro, "incluir": exclusao is None, "exclusao": exclusao}


def reclassificar_registro(
    registro: dict[str, Any], exclusoes: dict[str, dict[str, str]] | None = None
) -> dict[str, Any]:
    """Reaplica o classificador fino ao `texto` de cada PDF, sem rede.

    Recalcula tipo/versão de cada PDF, as contagens e alertas do concurso e,
    com `exclusoes`, o `incluir`. `formato_provavel` não muda aqui (depende
    da amostra).
    """
    pdfs = []
    for pdf in registro.get("pdfs") or []:
        classif = classificar_link_pdf(pdf.get("texto") or "")
        pdfs.append({**pdf, **classif})
    novo = {
        **registro,
        **resumir_pdfs(registro.get("slug", ""), pdfs, registro.get("situacao")),
        "pdfs": pdfs,
    }
    if exclusoes is not None:
        novo = aplicar_exclusao(novo, exclusoes)
    return novo


def reclassificar_inventario(
    caminho: Path = INVENTARIO_CONCURSOS_PATH,
    caminho_exclusoes: Path = INVENTARIO_EXCLUSOES_PATH,
) -> dict[str, Counter]:
    """Reclassifica todo o `concursos.jsonl` a partir dos textos já gravados.

    Também reaplica `inventario/exclusoes.json`. Devolve a contagem de PDFs
    por tipo antes e depois.
    """
    registros = carregar_concursos_jsonl(caminho)
    exclusoes = carregar_exclusoes(caminho_exclusoes)
    antes = Counter(p.get("tipo") for r in registros for p in r.get("pdfs") or [])
    novos = sorted(
        (reclassificar_registro(r, exclusoes) for r in registros),
        key=lambda r: str(r.get("slug", "")),
    )
    depois = Counter(p.get("tipo") for r in novos for p in r.get("pdfs") or [])
    salvar_concursos_jsonl(novos, caminho)
    return {"antes": antes, "depois": depois}


def salvar_anos_json(dados: dict, caminho: Path = INVENTARIO_ANOS_PATH) -> None:
    """Salva inventário de anos em formato JSON formatado."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def carregar_anos_json(caminho: Path = INVENTARIO_ANOS_PATH) -> dict:
    """Carrega inventário de anos de arquivo JSON."""
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_concursos_jsonl(
    registros: list[dict], caminho: Path = INVENTARIO_CONCURSOS_PATH
) -> None:
    """Salva lista completa de concursos em JSONL."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as f:
        for reg in registros:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")


def adicionar_concurso_jsonl(
    registro: dict, caminho: Path = INVENTARIO_CONCURSOS_PATH
) -> None:
    """Acrescenta um registro de concurso ao final do JSONL."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def carregar_concursos_jsonl(
    caminho: Path = INVENTARIO_CONCURSOS_PATH,
) -> list[dict]:
    """Carrega todos os registros de concursos do arquivo JSONL."""
    return list(iterar_concursos_jsonl(caminho))


def iterar_concursos_jsonl(
    caminho: Path = INVENTARIO_CONCURSOS_PATH,
) -> Iterator[dict]:
    """Itera preguiçosamente pelos registros de concursos do arquivo JSONL."""
    caminho = Path(caminho)
    if not caminho.exists():
        return
    with caminho.open("r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha:
                yield json.loads(linha)


def detectar_formato_caderno(pdf_bytes_ou_path: Path | bytes | str) -> str:
    """Detecta se o caderno de prova é Múltipla Escolha (ME), Certo/Errado (CE), Misto ou Desconhecido (?).

    Lê até as primeiras 5 páginas do PDF com PyMuPDF e inspeciona o texto.
    Se o PDF for inválido ou não contiver texto legível, retorna '?' defensivamente.
    """
    try:
        if isinstance(pdf_bytes_ou_path, (bytes, bytearray)):
            if not pdf_bytes_ou_path:
                return FORMATO_DESCONHECIDO
            doc = fitz.open(stream=pdf_bytes_ou_path, filetype="pdf")
        else:
            p = Path(pdf_bytes_ou_path)
            if not p.is_file():
                return FORMATO_DESCONHECIDO
            doc = fitz.open(str(p))

        with doc:
            if len(doc) == 0:
                return FORMATO_DESCONHECIDO
            paginas = [doc[i].get_text() for i in range(min(5, len(doc)))]
            texto = "\n".join(paginas)
    except Exception:
        return FORMATO_DESCONHECIDO

    return classificar_formato_texto(texto)


def _inicios_blocos_alternativas(texto: str) -> list[int]:
    """Posição de cada sequência de alternativas A, B, C, D em linhas seguidas."""
    marcas = [
        (m.start(), m.group(1) or m.group(2))
        for m in PADRAO_ALTERNATIVA_ME.finditer(texto)
    ]
    inicios = []
    for i in range(len(marcas) - 3):
        janela = marcas[i : i + 4]
        if (
            "".join(letra for _, letra in janela) == "ABCD"
            and janela[3][0] - janela[0][0] <= JANELA_ALTERNATIVAS
        ):
            inicios.append(janela[0][0])
    return inicios


def classificar_formato_texto(texto: str) -> str:
    """Formato do caderno (`ce`, `me`, `misto` ou `?`) pelo texto extraído.

    Questão ME do CEBRASPE pode trazer "Julgue os itens ... Assinale a opção
    correta". Por isso um "julgue" só conta como CE quando não há bloco de
    alternativas A–D depois dele na mesma questão (até o próximo "Questão N").
    """
    if not texto or not texto.strip():
        return FORMATO_DESCONHECIDO

    blocos = _inicios_blocos_alternativas(texto)
    cabecalhos = [m.start() for m in PADRAO_CABECALHO_QUESTAO.finditer(texto)]
    comandos_ce = 0
    for m in PADRAO_JULGUE.finditer(texto):
        pos = m.start()
        fim = min([c for c in cabecalhos if c > pos] + [pos + JANELA_ALTERNATIVAS])
        if not any(pos < b < fim for b in blocos):
            comandos_ce += 1

    if not blocos:
        if comandos_ce or PADRAO_MARCADOR_CE.search(texto):
            return FORMATO_CE
        return FORMATO_DESCONHECIDO
    if comandos_ce == 0:
        return FORMATO_ME
    if comandos_ce >= 2 and len(blocos) >= 2:
        # Um "julgue" solto num caderno ME (alternativas longe do comando)
        # não pode virar misto: o CE precisa ter peso próximo do ME.
        return FORMATO_MISTO if comandos_ce * 3 >= len(blocos) else FORMATO_ME
    return FORMATO_ME if len(blocos) > comandos_ce else FORMATO_CE


def paginas_com_figura(caminho: Path | str) -> list[int]:
    """Páginas (1-based, sem a capa) com imagem no corpo da prova.

    Logotipo de cabeçalho e carimbo de "Espaço livre" são imagens baixas
    (até ~60 pt de altura); figura de questão (diagrama, tabela) é mais alta.
    """
    paginas: list[int] = []
    try:
        with fitz.open(str(caminho)) as doc:
            for indice in range(1, len(doc)):
                pagina = doc[indice]
                altura = pagina.rect.height
                for info in pagina.get_images(full=True):
                    if any(
                        r.height >= ALTURA_MINIMA_FIGURA
                        and r.width >= LARGURA_MINIMA_FIGURA
                        and MARGEM_CABECALHO_FIGURA
                        < r.y0
                        < altura - MARGEM_RODAPE_FIGURA
                        for r in pagina.get_image_rects(info[0])
                    ):
                        paginas.append(indice + 1)
                        break
    except Exception:
        return []
    return paginas


def _e_caderno_basico(texto: str) -> bool:
    t = normalizar(texto or "")
    return any(chave in t for chave in ("basic", "gerais", "comuns"))


def _e_caderno_especifico(texto: str) -> bool:
    return "especific" in normalizar(texto or "")


def escolher_cadernos_calibracao_me(
    concursos: list[dict[str, Any]], amostra_dir: Path = AMOSTRA_DIR
) -> list[dict[str, Any]]:
    """Escolhe até 3 cadernos ME reais da amostra para calibrar a 8.M.

    Um com figura, um de conhecimentos básicos e um de específicos, de
    concursos diferentes, preferindo encerrados (gabarito definitivo
    publicado) e mais recentes.
    """
    candidatos = []
    for c in sorted(
        concursos,
        key=lambda c: (
            c.get("situacao") != "encerrado",
            -(c.get("ano") or 0),
            str(c.get("slug", "")),
        ),
    ):
        amostra = c.get("amostra_formato") or {}
        caminho = Path(amostra_dir) / (amostra.get("arquivo") or "")
        if (
            c.get("formato_provavel") == FORMATO_ME
            and amostra.get("arquivo")
            and caminho.is_file()
        ):
            candidatos.append((c, amostra, caminho))

    criterios = [
        ("com figura", lambda amostra, caminho: paginas_com_figura(caminho)),
        (
            "conhecimentos básicos",
            lambda amostra, _c: _e_caderno_basico(amostra.get("texto")),
        ),
        (
            "conhecimentos específicos",
            lambda amostra, _c: _e_caderno_especifico(amostra.get("texto")),
        ),
    ]
    escolhidos: list[dict[str, Any]] = []
    usados: set[str] = set()
    for papel, criterio in criterios:
        for c, amostra, caminho in candidatos:
            if c["slug"] in usados:
                continue
            resultado = criterio(amostra, caminho)
            if not resultado:
                continue
            usados.add(c["slug"])
            escolhidos.append(
                {
                    "papel": papel,
                    "slug": c["slug"],
                    "texto": amostra.get("texto", ""),
                    "arquivo": amostra["arquivo"],
                    "paginas_figura": paginas_com_figura(caminho),
                }
            )
            break
    return escolhidos


def cobertura_por_ano(
    concursos: list[dict[str, Any]],
    anos_data: dict[str, Any],
    ano_minimo: int = 2020,
) -> list[dict[str, Any]]:
    """Listados × mapeados × com erro × sem estado, por ano das listagens."""
    registros = {c.get("slug"): c for c in concursos}
    linhas = []
    for chave, valor in anos_data.items():
        if (
            not chave.isdigit()
            or int(chave) < ano_minimo
            or not isinstance(valor, dict)
        ):
            continue
        slugs: set[str] = set()
        for situacao, lista in valor.items():
            if situacao != "outros" and isinstance(lista, list):
                slugs.update(lista)
        com_erro = sorted(s for s in slugs if registros.get(s, {}).get("erro"))
        mapeados = sorted(
            s
            for s in slugs
            if s in registros
            and not registros[s].get("erro")
            and registros[s].get("data_mapeamento")
        )
        linhas.append(
            {
                "ano": int(chave),
                "listados": len(slugs),
                "mapeados": len(mapeados),
                "com_erro": com_erro,
                "sem_estado": sorted(slugs - set(mapeados) - set(com_erro)),
            }
        )
    return sorted(linhas, key=lambda linha: -linha["ano"])


def _resumo_concurso(c: dict[str, Any]) -> dict[str, Any]:
    """Registro com `qtd_*` e `alertas`; calcula com `resumir_pdfs` se faltar."""
    if "qtd_cadernos" in c and "alertas" in c:
        return c
    pdfs = c.get("pdfs") if isinstance(c.get("pdfs"), list) else []
    return {**c, **resumir_pdfs(c.get("slug", ""), pdfs, c.get("situacao"))}


def _contar_elementos_concurso(c: dict[str, Any]) -> dict[str, int]:
    """Cadernos, gabaritos e padrões que vão para o site; editais e totais."""
    r = _resumo_concurso(c)
    pdfs = c.get("pdfs")
    total = (
        len(pdfs)
        if isinstance(pdfs, list)
        else sum((c.get("contagens") or {}).values())
    )
    return {
        "cadernos": int(r.get("qtd_cadernos") or 0),
        "gabaritos": int(r.get("qtd_gabaritos") or 0),
        "padroes": int(r.get("qtd_padroes") or 0),
        "editais": int(r.get("qtd_editais") or 0),
        "nao_classificados": int(r.get("qtd_nao_classificados") or 0),
        "total_pdfs": int(total),
    }


def gerar_relatorio_md(
    concursos: list[dict[str, Any]],
    anos_data: dict[str, Any] | None = None,
    calibracao: list[dict[str, Any]] | None = None,
) -> str:
    """Gera conteúdo em Markdown para inventario/RELATORIO.md.

    `calibracao` vem de `escolher_cadernos_calibracao_me` (lê os PDFs da
    amostra; fica fora daqui para o relatório ser testável sem PDF).
    """
    total_concursos = len(concursos)
    total_2020 = sum(
        1
        for c in concursos
        if str(c.get("ano", "")).isdigit() and int(c.get("ano")) >= 2020
    )

    total_pdfs = 0
    for c in concursos:
        el = _contar_elementos_concurso(c)
        total_pdfs += el["total_pdfs"]

    agora_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    linhas = [
        "# Relatório Analítico de Inventário de Concursos CEBRASPE",
        "",
        f"- **Data de geração:** {agora_str}",
        f"- **Total de concursos mapeados:** {total_concursos} ({total_2020} com ano ≥ 2020)",
        f"- **Total de PDFs identificados:** {total_pdfs}",
        "",
    ]

    cobertura = cobertura_por_ano(concursos, anos_data or {})
    if cobertura:
        linhas += [
            "## Cobertura do Mapeamento (2020+)",
            "",
            "Listados = slugs das 4 listagens (`anos.json`); mapeados = página do "
            "concurso lida (`data_mapeamento`); sem estado tem de ser 0.",
            "",
            "| Ano | Listados | Mapeados | Com erro | Sem estado |",
            "|:---|---:|---:|---:|---:|",
        ]
        for linha in cobertura:
            linhas.append(
                f"| {linha['ano']} | {linha['listados']} | {linha['mapeados']} | "
                f"{len(linha['com_erro'])} | {len(linha['sem_estado'])} |"
            )
        linhas.append(
            f"| **Total** | **{sum(x['listados'] for x in cobertura)}** | "
            f"**{sum(x['mapeados'] for x in cobertura)}** | "
            f"**{sum(len(x['com_erro']) for x in cobertura)}** | "
            f"**{sum(len(x['sem_estado']) for x in cobertura)}** |"
        )
        linhas.append("")
        problemas = [
            (s, motivo)
            for x in cobertura
            for motivo, slugs in (
                ("erro", x["com_erro"]),
                ("sem estado", x["sem_estado"]),
            )
            for s in slugs
        ]
        for slug, motivo in problemas:
            linhas.append(f"- **{slug}**: {motivo}")
        if problemas:
            linhas.append("")

    linhas += [
        "## Tabela Resumo por Ano e Situação",
        "",
        "Cadernos, gabaritos e padrões contam só o que vai para o site (sem curso "
        "de formação); o caderno com gabarito conta nas duas colunas.",
        "",
        "| Ano | Situação | Concursos | Fora do Site | Cadernos | Gabaritos | Padrões de Resposta | Formato CE | Formato ME | No Banco |",
        "|:---|:---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    grupos: dict[tuple[int | str, str], dict[str, int]] = {}
    for c in concursos:
        ano = c.get("ano", "Desconhecido")
        situacao = c.get("situacao", "desconhecida")
        chave = (ano, situacao)
        if chave not in grupos:
            grupos[chave] = {
                "concursos": 0,
                "fora_do_site": 0,
                "cadernos": 0,
                "gabaritos": 0,
                "padroes": 0,
                "formato_ce": 0,
                "formato_me": 0,
                "no_banco": 0,
            }
        el = _contar_elementos_concurso(c)
        g = grupos[chave]
        g["concursos"] += 1
        g["fora_do_site"] += c.get("incluir") is False
        g["cadernos"] += el["cadernos"]
        g["gabaritos"] += el["gabaritos"]
        g["padroes"] += el["padroes"]
        if c.get("formato_provavel") == FORMATO_CE:
            g["formato_ce"] += 1
        elif c.get("formato_provavel") == FORMATO_ME:
            g["formato_me"] += 1
        if c.get("no_banco"):
            g["no_banco"] += 1

    def _ordem_chave(k: tuple[int | str, str]) -> tuple[int, str]:
        ano_val, sit_val = k
        try:
            ano_num = int(ano_val)
        except (ValueError, TypeError):
            ano_num = -1
        return (-ano_num, str(sit_val))

    colunas = (
        "concursos",
        "fora_do_site",
        "cadernos",
        "gabaritos",
        "padroes",
        "formato_ce",
        "formato_me",
        "no_banco",
    )
    totais = Counter()
    for chave in sorted(grupos.keys(), key=_ordem_chave):
        ano_val, sit_val = chave
        g = grupos[chave]
        totais.update(g)
        valores = " | ".join(str(g[col]) for col in colunas)
        linhas.append(f"| {ano_val} | {sit_val} | {valores} |")
    valores = " | ".join(f"**{totais[col]}**" for col in colunas)
    linhas.append(f"| **Total** | - | {valores} |")
    linhas.append("")

    # Formato da amostra
    amostrados = [c for c in concursos if c.get("formato_provavel")]
    linhas.append("## Formato na Amostra (CE × ME)")
    linhas.append("")
    linhas.append(
        "Um caderno objetivo por concurso: todos de 2025 e 2026 e 3 por ano de "
        "2020 a 2024. O formato dos demais sai no download do lote (8.1)."
    )
    linhas.append("")
    linhas.append("| Formato | Concursos |")
    linhas.append("|:---|---:|")
    for formato, qtd in sorted(
        Counter(c["formato_provavel"] for c in amostrados).items()
    ):
        linhas.append(f"| `{formato}` | {qtd} |")
    linhas.append("")

    linhas.append("## Cadernos ME para Calibrar a Etapa 8.M")
    linhas.append("")
    if calibracao:
        linhas.append("| Papel | Concurso | Texto do link | PDF | Páginas com figura |")
        linhas.append("|:---|:---|:---|:---|:---|")
        for item in calibracao:
            paginas = ", ".join(str(n) for n in item.get("paginas_figura") or []) or "-"
            linhas.append(
                f"| {item['papel']} | {item['slug']} | {item['texto']} | "
                f"`data/inventario_amostra/{item['arquivo']}` | {paginas} |"
            )
    else:
        linhas.append("Nenhum caderno ME da amostra disponível em disco.")
    linhas.append("")

    linhas.append("## Cadernos de Múltipla Escolha (ME) Identificados")
    linhas.append("")
    me_concursos = [c for c in concursos if c.get("formato_provavel") == FORMATO_ME]
    if me_concursos:
        linhas.append("| Concurso | Ano | Situação | Caderno amostrado | Arquivo |")
        linhas.append("|:---|---:|:---|:---|:---|")
        for c in me_concursos:
            amostra = c.get("amostra_formato") or {}
            linhas.append(
                f"| {c.get('slug', '')} | {c.get('ano', '')} | {c.get('situacao', '')} | "
                f"{amostra.get('texto', '-')} | `{amostra.get('arquivo', '-')}` |"
            )
    else:
        linhas.append(
            "Nenhum caderno de Múltipla Escolha (ME) identificado até o momento."
        )
    linhas.append("")

    # Fora do site (inventario/exclusoes.json, ADR-037)
    resumos = [_resumo_concurso(c) for c in concursos]
    fora = [c for c in resumos if c.get("incluir") is False]
    incluidos = [c for c in resumos if c.get("incluir") is not False]

    linhas.append("## Fora do Site (Decisão do Dono)")
    linhas.append("")
    linhas.append(
        "Lista em `inventario/exclusoes.json` (ADR-037), verificada na página de "
        "cada concurso. Não são remapeados nem entram em amostra ou lote, e ficam "
        "fora dos alertas abaixo."
    )
    linhas.append("")
    if fora:
        linhas.append("| Concurso | Ano | Categoria | Motivo |")
        linhas.append("|:---|---:|:---|:---|")
        for c in sorted(
            fora,
            key=lambda x: ((x.get("exclusao") or {}).get("categoria", ""), x["slug"]),
        ):
            exclusao = c.get("exclusao") or {}
            categoria = exclusao.get("categoria", "-")
            rotulo = CATEGORIAS_EXCLUSAO.get(categoria, categoria)
            linhas.append(
                f"| {c['slug']} | {c.get('ano', '')} | {rotulo} | "
                f"{exclusao.get('motivo', '-')} |"
            )
    else:
        linhas.append("- *(Nenhum concurso excluído)*")
    linhas.append("")

    cf = [c for c in incluidos if c.get("qtd_curso_formacao")]
    linhas.append("### Provas de Curso de Formação (fora do site)")
    linhas.append("")
    linhas.append(
        "Estes concursos **entram no site**: edital, cadernos e gabaritos do "
        "concurso são coletados normalmente. Só ficam fora os PDFs da prova do "
        'curso de formação (link com "curso de formação"), que continuam no '
        "inventário mas não vão para o lote (`pdf_vai_para_o_site`). Concurso de "
        "ingresso com nome de curso (PM_DF_25_CFO, CBM_PA_23_CFP) é concurso "
        "normal. Quantidade de PDFs de curso de formação por concurso:"
    )
    linhas.append("")
    if cf:
        total_cf = sum(c["qtd_curso_formacao"] for c in cf)
        linhas.append(
            f"{total_cf} PDFs de curso de formação em {len(cf)} concursos incluídos:"
        )
        linhas.append("")
        for c in sorted(cf, key=lambda x: x["slug"]):
            linhas.append(f"- **{c['slug']}**: {c['qtd_curso_formacao']}")
    else:
        linhas.append("- *(Nenhum caso identificado)*")
    linhas.append("")

    aguardando = [c for c in incluidos if "aguardando_prova" in c.get("alertas", [])]
    linhas.append("## Aguardando Prova")
    linhas.append("")
    linhas.append(
        "Sem caderno, gabarito ou padrão publicado e ainda não encerrados. Não é "
        "pendência: entram quando o remapeamento mostrar a prova."
    )
    linhas.append("")
    if aguardando:
        for c in sorted(aguardando, key=lambda x: x["slug"]):
            linhas.append(
                f"- **{c['slug']}** ({c.get('ano', '')}, {c.get('situacao', '')})"
            )
    else:
        linhas.append("- *(Nenhum caso identificado)*")
    linhas.append("")

    # Alertas: só concursos que entram no site
    linhas.append("## Alertas e Casos Especiais")
    linhas.append("")
    linhas.append(
        "Só concursos que entram no site; cada item é pendência real da coleta."
    )
    linhas.append("")

    sem_edital: list[str] = []
    sem_caderno_ou_gab: list[str] = []
    ano_4d: list[str] = []
    for c in incluidos:
        slug = c.get("slug", "")
        rotulo = f"- **{slug}** ({c.get('orgao', '')}, {c.get('ano', '')})"
        alertas = c.get("alertas", [])
        if "sem_edital_abertura" in alertas:
            sem_edital.append(rotulo)
        motivos_falta = [
            texto
            for alerta, texto in (
                ("sem_caderno", "sem cadernos de prova"),
                ("sem_gabarito", "sem gabaritos"),
            )
            if alerta in alertas
        ]
        if motivos_falta:
            sem_caderno_ou_gab.append(f"{rotulo}: {', '.join(motivos_falta)}")
        if "ano_4_digitos" in alertas:
            ano_4d.append(f"- **{slug}** (Ano no slug: {c.get('ano', '')})")

    for titulo, itens in (
        ("### Concursos sem Edital de Abertura", sem_edital),
        ("### Concursos sem Caderno de Prova ou sem Gabarito", sem_caderno_ou_gab),
        ("### Concursos com Ano de 4 Dígitos no Slug", ano_4d),
    ):
        linhas.append(titulo)
        linhas.extend(itens or ["- *(Nenhum caso identificado)*"])
        linhas.append("")

    if anos_data and anos_data.get("ano_desconhecido"):
        linhas.append("### Concursos com Ano Desconhecido nas Listagens")
        for s in anos_data["ano_desconhecido"]:
            linhas.append(f"- **{s}**")
        linhas.append("")

    # Concursos do Piloto no Banco
    linhas.append("## Concursos do Piloto no Banco")
    linhas.append("")
    banco_concursos = [c for c in concursos if c.get("no_banco") is True]
    if banco_concursos:
        linhas.append(
            "| Slug | Órgão | Ano | Situação | Cadernos | Gabaritos | Formato | No Banco |"
        )
        linhas.append("|:---|:---|---:|:---|---:|---:|:---:|:---:|")
        for c in sorted(banco_concursos, key=lambda x: str(x.get("slug", ""))):
            slug = c.get("slug", "")
            orgao = c.get("orgao", "")
            ano = c.get("ano", "")
            sit = c.get("situacao", "")
            el = _contar_elementos_concurso(c)
            fmt = c.get("formato_provavel", "?")
            linhas.append(
                f"| {slug} | {orgao} | {ano} | {sit} | {el['cadernos']} | {el['gabaritos']} | {fmt} | Confirmado (`True`) |"
            )
    else:
        linhas.append("Nenhum concurso do piloto com `no_banco = True` registrado.")
    linhas.append("")

    # Top textos não classificados
    linhas.append("## Top Textos Não Classificados")
    linhas.append("")
    textos_nc: list[str] = []
    for c in concursos:
        for p in c.get("pdfs", []):
            if p.get("tipo") in (TIPO_NAO_CLASSIFICADO, "nao_classificado"):
                t = p.get("texto", "").strip()
                if t:
                    textos_nc.append(t)
    if textos_nc:
        linhas.append("| Ocorrências | Texto do Link |")
        linhas.append("|---:|:---|")
        contagem_nc = Counter(textos_nc)
        for txt, qtd in contagem_nc.most_common(20):
            linhas.append(f"| {qtd} | {txt} |")
    else:
        linhas.append("Nenhum link com tipo `nao_classificado` encontrado.")
    linhas.append("")

    return "\n".join(linhas)


def salvar_relatorio_md(
    conteudo: str, caminho: Path = INVENTARIO_RELATORIO_PATH
) -> None:
    """Salva o relatório analítico em formato Markdown UTF-8."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(conteudo, encoding="utf-8")
