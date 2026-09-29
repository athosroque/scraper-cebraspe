import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "exportar_openapi.py"


def test_openapi_versionado_em_dia():
    spec = importlib.util.spec_from_file_location("exportar_openapi", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    atual = modulo.ARQUIVO.read_text(encoding="utf-8")
    assert atual == modulo.gerar(), (
        "site/openapi.json desatualizado: rode python site/scripts/exportar_openapi.py"
    )
