"""Exporta o contrato OpenAPI da API para `site/openapi.json` (versionado).

É a fonte para documentação e para os servidores MCP. O teste
`test_openapi_versionado_em_dia` falha se o arquivo divergir do código.

Uso: python site/scripts/exportar_openapi.py
"""

import json
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parents[1]
ARQUIVO = SITE_DIR / "openapi.json"


def gerar() -> str:
    sys.path.insert(0, str(SITE_DIR))
    from app.main import app

    return json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"


if __name__ == "__main__":
    ARQUIVO.write_text(gerar(), encoding="utf-8")
    print(f"OpenAPI exportado em {ARQUIVO}")
