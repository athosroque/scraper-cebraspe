"""O tailwind.css versionado tem de bater com o gerado dos templates."""

import subprocess
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
BIN = SITE / "bin" / "tailwindcss"


@pytest.mark.skipif(
    not BIN.exists(), reason="binário do Tailwind ausente (rode scripts/gerar_css.sh)"
)
def test_tailwind_css_versionado_em_dia(tmp_path):
    saida = tmp_path / "tailwind.css"
    subprocess.run(
        [
            str(BIN),
            "-c",
            "tailwind.config.js",
            "-i",
            "estilos/entrada.css",
            "-o",
            str(saida),
            "--minify",
        ],
        cwd=SITE,
        check=True,
        capture_output=True,
    )
    versionado = (SITE / "app" / "static" / "tailwind.css").read_text()
    assert saida.read_text() == versionado, "rode site/scripts/gerar_css.sh"
