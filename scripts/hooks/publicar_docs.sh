#!/usr/bin/env bash
# Publica o site de documentação (MkDocs) depois de commit ou merge que mexe nos docs.
#
# Uso (chamado pelos despachantes de `make hooks-instalar`):
#   publicar_docs.sh post-commit | post-merge
#
# Regras (ADR-040, atualização de 2026-10-13):
#   - só age no checkout principal: o nginx serve o build/docs dele, e os hooks
#     são compartilhados com as worktrees;
#   - só age se o commit (ou o merge, via ORIG_HEAD..HEAD) tocou docs/, mkdocs.yml,
#     scripts/gerar_docs.py, scripts/gerar_numeros.py, scripts/exportar_pdf_executivo.py
#     ou src/registro/;
#   - o build roda em segundo plano, com log em logs/publicar_docs.log;
#   - nunca falha o commit: qualquer problema vira uma linha no stderr.

evento="${1:-post-commit}"

# Nunca devolver erro ao git, aconteça o que acontecer.
trap 'exit 0' EXIT

raiz_git="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
dir_git="$(git rev-parse --absolute-git-dir 2>/dev/null)" || exit 0
dir_comum="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || exit 0

# Worktree: o git-dir dela é .git/worktrees/<nome>, diferente do comum.
[ "$dir_git" = "$dir_comum" ] || exit 0

projeto="$raiz_git/scraper_cebraspe"
[ -f "$projeto/Makefile" ] || exit 0

if [ "$evento" = "post-merge" ]; then
    if git rev-parse --verify -q ORIG_HEAD >/dev/null; then
        arquivos="$(git diff --name-only ORIG_HEAD HEAD 2>/dev/null)"
    else
        arquivos="$(git diff --name-only HEAD~1 HEAD 2>/dev/null)"
    fi
else
    arquivos="$(git diff-tree --root --no-commit-id --name-only -r HEAD 2>/dev/null)"
fi

if ! printf '%s\n' "$arquivos" | grep -Eq '^scraper_cebraspe/(docs/|mkdocs\.yml$|scripts/(gerar_docs|gerar_numeros|exportar_pdf_executivo)\.py$|src/registro/)'; then
    exit 0
fi

mkdir -p "$projeto/logs"
log="$projeto/logs/publicar_docs.log"

# Um build por vez (flock); o log mostra início, fim e o código de saída.
(
    cd "$projeto" || exit 0
    exec env -u GIT_DIR -u GIT_INDEX_FILE -u GIT_WORK_TREE \
        nohup bash -c '
            {
                echo "=== $(date -Is) início do build ($0)"
                if flock 9; then
                    make docs-build; codigo=$?
                    echo "=== $(date -Is) fim do build: código $codigo"
                fi
            } >>"$1" 2>&1 9>"$1.lock"
        ' "$evento" "$log" >/dev/null 2>&1 &
) 
echo "publicar_docs: build do site de docs em segundo plano (log: scraper_cebraspe/logs/publicar_docs.log)" >&2
exit 0
