"""Registro do pipeline: scripts, etapas, checagens e regras (Etapa 9/D2, ADR-041).

Fonte única das páginas de `docs/tecnico/` (`scripts/gerar_docs.py`) e dos assets
do Dagster (D5a). Script novo entra em `scripts.py`; depois, `make docs-gerar`.
"""

from src.registro.checagens import CHECAGENS
from src.registro.etapas import ETAPAS
from src.registro.modelo import Registro
from src.registro.regras_antipatterns import REGRAS_ANTIPATTERNS
from src.registro.regras_patterns import REGRAS_PATTERNS_1
from src.registro.regras_patterns_2 import REGRAS_PATTERNS_2
from src.registro.scripts import SCRIPTS

REGRAS = REGRAS_PATTERNS_1 + REGRAS_PATTERNS_2 + REGRAS_ANTIPATTERNS

REGISTRO = Registro(SCRIPTS, ETAPAS, CHECAGENS, REGRAS)

__all__ = ["CHECAGENS", "ETAPAS", "REGISTRO", "REGRAS", "SCRIPTS"]
