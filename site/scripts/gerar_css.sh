#!/usr/bin/env bash
# Gera app/static/tailwind.css com o binário standalone do Tailwind (sem Node).
# O binário fica em site/bin/ (fora do git); baixa na primeira execução.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSAO="v3.4.17"
BIN="bin/tailwindcss"
if [ ! -x "$BIN" ]; then
  mkdir -p bin
  curl -sSL -o "$BIN" "https://github.com/tailwindlabs/tailwindcss/releases/download/${VERSAO}/tailwindcss-linux-x64"
  chmod +x "$BIN"
fi
"$BIN" -c tailwind.config.js -i estilos/entrada.css -o app/static/tailwind.css --minify "$@"
