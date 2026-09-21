import hashlib
import json
import random
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.logger import logger
from src.spider import (
    USER_AGENTS,
    extract_orgao_from_slug,
    extract_year_from_slug,
    stealth_wait,
)

# Aponta para o repositório original, não para a worktree, para que VS Code veja os arquivos
# Busca o .git da raiz do homelab e usa scraper_cebraspe/data a partir daí
_project_root = Path(__file__).resolve()
while _project_root != _project_root.parent:
    if (_project_root / ".git").exists():
        break
    _project_root = _project_root.parent

# Se estiver em worktree, volta para o repositório original
if ".claude/worktrees" in str(_project_root):
    _project_root = _project_root.parent.parent.parent

DATA_DIR = _project_root / "scraper_cebraspe" / "data"

CATEGORIA_PASTA = {
    "editais_abertura": "Editais",
    "provas": "Provas",
    "gabaritos": "Gabaritos",
}

MANIFEST_FILENAME = ".manifest.json"
PROVAS_TEXTO_FILENAME = "provas_texto_link.json"
PDF_MAGIC_BYTES = b"%PDF-"
REQUEST_TIMEOUT = 30


def slugify(nome: str) -> str:
    """Normaliza um nome de órgão para um slug determinístico e seguro para paths.

    Mesmo nome de órgão sempre gera o mesmo slug entre execuções diferentes
    (acentos e espaços removidos/normalizados), evitando pastas duplicadas
    para o mesmo órgão em `data/<ano>/CEBRASPE/<orgao_slug>/`.
    """
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", sem_acento).strip("_").upper()
    return slug or "ORGAO_DESCONHECIDO"


def _load_manifest(manifest_path: Path) -> dict[str, dict[str, str]]:
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Manifesto corrompido em {manifest_path}, recriando: {e}")
        return {}


def _save_manifest(manifest_path: Path, manifest: dict[str, dict[str, str]]) -> None:
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _is_valid_pdf(content: bytes, content_type: str | None) -> bool:
    """Valida que o conteúdo baixado é de fato um PDF.

    Checa os magic bytes (`%PDF-`) do conteúdo em si, não só o header
    Content-Type — servidores costumam responder 200 com uma página HTML de
    erro/redirecionamento quando o link está quebrado, e essa página não tem
    os magic bytes de um PDF real.
    """
    if not content.startswith(PDF_MAGIC_BYTES):
        return False
    if content_type and "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
        logger.warning(f"Content-Type inesperado para PDF com magic bytes válidos: {content_type}")
    return True


def _filename_from_url(url: str) -> str:
    nome = Path(urlparse(url).path).name
    if not nome or not nome.lower().endswith(".pdf"):
        nome = f"{nome or 'documento'}.pdf"
    return nome


def resolver_concurso_do_pdf(pdf_path: Path) -> dict | None:
    """Identifica o concurso (slug, órgão, ano) de um PDF já baixado, via
    manifesto da pasta do órgão.

    O path em disco (`data/<ano>/CEBRASPE/<orgao>/Editais/x.pdf`) só carrega
    ano e órgão — não o concurso: dois concursos do mesmo órgão no mesmo ano
    (ex: `TJ_CE_25_NOTARIOS` e `TJ_CE_25_SERVIDOR`) caem na mesma pasta. O
    slug só existe na URL de origem (`.../concursos/PF_25_ADM/arquivos/x.pdf`),
    guardada como chave do manifesto. Casa pelo nome do arquivo, não pelo
    `path` gravado no manifesto — este pode apontar pra outra cópia do repo
    (achado: paths de worktree antiga). Retorna None se não achar ou se o
    nome do arquivo for ambíguo entre concursos.
    """
    manifest = _load_manifest(pdf_path.parent.parent / MANIFEST_FILENAME)
    slugs = set()
    for url, entry in manifest.items():
        if pdf_path.name not in (_filename_from_url(url), Path(entry.get("path", "")).name):
            continue
        match = re.search(r"/concursos/([^/]+)/", url)
        if match:
            slugs.add(match.group(1))

    if len(slugs) != 1:
        logger.warning(
            f"Concurso de {pdf_path.name} não identificado pelo manifesto "
            f"({'ambíguo: ' + ', '.join(sorted(slugs)) if slugs else 'sem entrada'})."
        )
        return None

    slug = slugs.pop()
    return {"slug": slug, "orgao": extract_orgao_from_slug(slug), "ano": extract_year_from_slug(slug)}


def download_pdf(url: str, dest_dir: Path, manifest: dict[str, dict[str, str]]) -> Path | None:
    """Baixa um PDF, validando magic bytes e deduplicando por URL e por hash.

    Retorna o path final do arquivo (novo ou reaproveitado de uma execução
    anterior/duplicata de conteúdo), ou None se o download falhar ou o
    conteúdo não for um PDF válido.
    """
    cached = manifest.get(url)
    if cached and Path(cached["path"]).exists():
        logger.info(f"Já baixado (manifesto): {url}")
        return Path(cached["path"])

    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Falha ao baixar {url}: {e}")
        return None
    finally:
        stealth_wait()

    content = response.content
    content_type = response.headers.get("Content-Type")

    if not _is_valid_pdf(content, content_type):
        logger.error(f"Conteúdo inválido (não é PDF) em {url} — Content-Type: {content_type}")
        return None

    content_hash = hashlib.sha256(content).hexdigest()

    for entry in manifest.values():
        if entry.get("hash") == content_hash and Path(entry["path"]).exists():
            existing_path = Path(entry["path"])
            logger.info(f"Conteúdo duplicado de outro link já baixado, reaproveitando {existing_path}")
            manifest[url] = {"hash": content_hash, "path": str(existing_path)}
            return existing_path

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / _filename_from_url(url)

    if dest_path.exists() and hashlib.sha256(dest_path.read_bytes()).hexdigest() != content_hash:
        # Nome de arquivo colide mas conteúdo é diferente: desambigua com o hash.
        dest_path = dest_dir / f"{dest_path.stem}_{content_hash[:8]}{dest_path.suffix}"

    dest_path.write_bytes(content)
    manifest[url] = {"hash": content_hash, "path": str(dest_path)}
    logger.info(f"Baixado: {url} -> {dest_path}")
    return dest_path


def download_concurso_pdfs(
    orgao: str, ano: int, pdf_map: dict[str, list], data_dir: Path = DATA_DIR
) -> dict[str, list[str]]:
    """Baixa e organiza os PDFs mapeados de um concurso.

    Grava em `<data_dir>/<ano>/CEBRASPE/<orgao_slug>/{Editais,Provas,Gabaritos}/`.
    Uma falha isolada num PDF é logada e não interrompe os demais downloads
    do concurso.

    `pdf_map["provas"]` pode vir como `list[str]` (URLs puras) ou
    `list[dict]` no formato `{"url": ..., "texto": ...}` — o texto do link é
    a única fonte de tipo/nível/cargo(s) cobertos (ver `spider.map_pdf_links`
    e `LESSONS.md`) e é persistido em `PROVAS_TEXTO_FILENAME`, indexado pelo
    nome do arquivo baixado, para a Etapa 4 consumir depois.
    """
    orgao_slug = slugify(orgao)
    concurso_dir = data_dir / str(ano) / "CEBRASPE" / orgao_slug
    manifest_path = concurso_dir / MANIFEST_FILENAME
    provas_texto_path = concurso_dir / PROVAS_TEXTO_FILENAME
    concurso_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(manifest_path)
    provas_texto = _load_manifest(provas_texto_path)

    resultado: dict[str, list[str]] = {categoria: [] for categoria in CATEGORIA_PASTA}

    for categoria, pasta in CATEGORIA_PASTA.items():
        dest_dir = concurso_dir / pasta
        for entry in pdf_map.get(categoria, []):
            url = entry["url"] if isinstance(entry, dict) else entry
            texto = entry.get("texto") if isinstance(entry, dict) else None
            try:
                path = download_pdf(url, dest_dir, manifest)
            except Exception as e:  # noqa: BLE001 — falha de 1 PDF não aborta o concurso
                logger.error(f"Falha inesperada ao baixar {url} ({orgao_slug}): {e}")
                continue
            if path:
                resultado[categoria].append(str(path))
                if texto is not None:
                    provas_texto[Path(path).name] = texto

    _save_manifest(manifest_path, manifest)
    if provas_texto:
        _save_manifest(provas_texto_path, provas_texto)
    return resultado
