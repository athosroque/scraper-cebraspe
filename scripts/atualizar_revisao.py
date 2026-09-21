"""Atualiza, em sequência, todos os artefatos derivados do checkpoint de
revisão humana (Etapa 4) a partir dos `<edital>.json` + `<edital>.auditoria.json`
presentes em `revisao_piloto/`, e reinicia o container Datasette pra servir
a versão nova.

Chamado automaticamente ao final de qualquer pipeline que gere ou atualize
esses dois arquivos (`scripts/revisar_taxonomia_piloto.py`,
`scripts/reprocessar_falhas_piloto.py`) — não precisa ser rodado manualmente
depois de uma extração, só se algo mudou nos JSONs por fora desses scripts
(ex.: revisão humana editando um `.json` na mão).

Sequência (cada etapa é idempotente e reconstrói do zero, ver ADR-015):
1. `scripts.validar_taxonomia` — recalcula `<edital>.validacao.json`
2. `scripts.gerar_relatorio_revisao` — recalcula `revisao_piloto/relatorio/*.html`
3. `scripts.gerar_db_datasette` — recalcula `revisao_piloto/revisao.db`
4. `docker compose restart scraper-cebraspe-datasette` — best-effort; se o
   container não estiver no ar (ex.: ambiente de dev sem Docker), loga aviso
   e segue sem falhar o pipeline de extração que chamou isso.

Uso:
    python -m scripts.atualizar_revisao [revisao_piloto_dir]
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_db_datasette import REVISAO_DIR_PADRAO, gerar_db
from scripts.gerar_relatorio_revisao import gerar_relatorios
from scripts.validar_taxonomia import main as validar_taxonomia
from src.logger import logger

PROJETO_DIR = Path(__file__).resolve().parent.parent
CONTAINER_DATASETTE = "scraper-cebraspe-datasette"


def _reiniciar_datasette() -> None:
    try:
        res = subprocess.run(
            ["docker", "compose", "restart", CONTAINER_DATASETTE],
            cwd=str(PROJETO_DIR),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if res.returncode == 0:
            logger.info("Container Datasette reiniciado com sucesso.")
        else:
            logger.warning(f"Não foi possível reiniciar o container Datasette: {res.stderr}")
    except OSError as e:
        logger.warning(f"Erro ao tentar reiniciar o Datasette: {e}")


def atualizar_artefatos_revisao(revisao_dir: Path = REVISAO_DIR_PADRAO, reiniciar_datasette: bool = True) -> None:
    logger.info("Atualizando artefatos derivados de revisão (validação + relatório + banco)...")
    validar_taxonomia(revisao_dir)
    gerar_relatorios(revisao_dir)
    gerar_db(revisao_dir)

    if reiniciar_datasette:
        _reiniciar_datasette()


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    atualizar_artefatos_revisao(diretorio)
