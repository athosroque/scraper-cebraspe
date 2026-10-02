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
5. `src.stats_writer.gravar_estatisticas` — grava o star schema no Postgres
   próprio (ADR-027). Também best-effort: banco fora do ar só loga aviso.
6. `scripts.extrair_questoes.processar_fila` — consome a fila de cadernos
   (Etapa 5C, ADR-031): só o que está `pendente`, sem LLM. Best-effort, e só
   roda se a carga do passo 5 deu certo.

Entre os passos 2 e 3, a camada canônica de sinônimos (Etapa 5B, ADR-029):
regras determinísticas em `canonico/sinonimos.json` (`src.canonico`) e o
relatório `relatorio/sinonimos.html`. **Sem LLM:** a proposta de sinônimos
pelo LLM custa tokens e só roda de forma explícita
(`python -m scripts.propor_sinonimos`).

Uso:
    python -m scripts.atualizar_revisao [revisao_piloto_dir]
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import gerar_relatorio_arvore as relatorio_arvore
from scripts import gerar_relatorio_classificacao as relatorio_classificacao
from scripts.extrair_questoes import processar_fila
from scripts.gerar_db_datasette import REVISAO_DIR_PADRAO, gerar_db
from scripts.gerar_relatorio_revisao import gerar_relatorios
from scripts.validar_taxonomia import main as validar_taxonomia
from src import canonico
from src.logger import logger
from src.stats_writer import gravar_estatisticas, listar_jsons_edital

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
            logger.warning(
                f"Não foi possível reiniciar o container Datasette: {res.stderr}"
            )
    except OSError as e:
        logger.warning(f"Erro ao tentar reiniciar o Datasette: {e}")


def atualizar_arvore(revisao_dir: Path) -> None:
    """Atualiza a árvore e o relatório (sem LLM). Best-effort:
    um erro aqui não pode derrubar a extração que já pagou o LLM."""
    if not listar_jsons_edital(revisao_dir):
        logger.info(f"[CANONICO] {revisao_dir}: nenhum edital, árvore não atualizada.")
        return
    try:
        canonico.mapear_novos_itens_por_regra(revisao_dir)
        relatorio_arvore.gerar_relatorio_arvore()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[CANONICO] Não foi possível atualizar a árvore: {e}")


def atualizar_classificacao(revisao_dir: Path) -> None:
    """Atualiza o relatório visual de classificação (sem LLM). Best-effort."""
    try:
        relatorio_classificacao.gerar_relatorio_classificacao(revisao_dir=revisao_dir)
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[CLASSIFICACAO] Não foi possível atualizar o relatório de classificação: {e}"
        )


def _reaplicar_permissoes_site() -> None:
    # A recarga do star schema recria as views e perde os GRANTs de
    # `site_leitura`: sem reaplicar, o site responde "permission denied".
    # Subprocesso porque o diretório `site/` colide com o módulo `site` da
    # stdlib (não dá para importar). Best-effort, como o restart do Datasette.
    script = Path(__file__).resolve().parents[1] / "site" / "scripts" / "aplicar_schema_app.py"
    try:
        resultado = subprocess.run(
            [sys.executable, str(script)], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"[SITE] Não foi possível reaplicar as permissões do site: {e}")
        return
    if resultado.returncode != 0:
        logger.warning(
            f"[SITE] Permissões do site não reaplicadas: {resultado.stderr.strip()}"
        )


def _gravar_banco_estatisticas(revisao_dir: Path) -> None:
    # Exception genérica de propósito: conexão recusada, senha ausente no
    # .env ou erro de SQL não podem derrubar a extração que já pagou o LLM —
    # o banco é regenerável a qualquer momento com `python -m src.stats_writer`.
    try:
        gravar_estatisticas(revisao_dir)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[STATS] Não foi possível gravar no banco de estatísticas: {e}")
        return
    # Mesma regra: a extração de questões é regenerável
    # (`python -m scripts.extrair_questoes`) e não derruba o pipeline.
    try:
        processar_fila()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[QUESTOES] Não foi possível processar a fila de cadernos: {e}")
    _reaplicar_permissoes_site()


def atualizar_artefatos_revisao(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    reiniciar_datasette: bool = True,
    gravar_banco: bool = True,
) -> None:
    logger.info(
        "Atualizando artefatos derivados de revisão (validação + relatório + banco)..."
    )
    validar_taxonomia(revisao_dir)
    gerar_relatorios(revisao_dir)
    atualizar_arvore(revisao_dir)
    atualizar_classificacao(revisao_dir)
    gerar_db(revisao_dir)

    if reiniciar_datasette:
        _reiniciar_datasette()

    if gravar_banco:
        _gravar_banco_estatisticas(revisao_dir)


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    atualizar_artefatos_revisao(diretorio)
