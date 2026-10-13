#!/usr/bin/env bash
# Instala os despachantes de post-commit e post-merge em .git/hooks (compartilhado
# por todos os projetos do monorepo). Idempotente: o despachante leva um marcador;
# hook de outro projeto, sem o marcador, é guardado como <hook>.anterior e
# encadeado antes do nosso.
set -euo pipefail

dir_hooks="$(git rev-parse --path-format=absolute --git-path hooks)"
hooksPath="$(git config --get core.hooksPath || true)"
if [ -n "$hooksPath" ]; then
    echo "core.hooksPath=$hooksPath está configurado; ajuste este script antes de instalar." >&2
    exit 1
fi
mkdir -p "$dir_hooks"
marcador="# hook-scraper-cebraspe-docs"

for evento in post-commit post-merge; do
    destino="$dir_hooks/$evento"
    if [ -e "$destino" ] && ! grep -q "$marcador" "$destino"; then
        mv "$destino" "$destino.anterior"
        echo "hook existente guardado em $destino.anterior (será encadeado)"
    fi
    cat >"$destino" <<DESPACHANTE
#!/usr/bin/env bash
$marcador
# Despachante gerado por 'make hooks-instalar' (scraper_cebraspe). Não edite:
# rode o alvo de novo. Encadeia o hook anterior, se houver, e publica os docs.
dir_hooks="\$(dirname "\$0")"
if [ -x "\$dir_hooks/$evento.anterior" ]; then
    "\$dir_hooks/$evento.anterior" "\$@" || true
fi
raiz="\$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
hook="\$raiz/scraper_cebraspe/scripts/hooks/publicar_docs.sh"
[ -x "\$hook" ] && "\$hook" $evento || true
exit 0
DESPACHANTE
    chmod +x "$destino"
    echo "instalado: $destino"
done
