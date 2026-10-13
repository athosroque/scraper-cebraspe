# Scraper CEBRASPE

O Scraper CEBRASPE é um pipeline batch que coleta os editais, as provas e os gabaritos de concursos do CEBRASPE, extrai a taxonomia de conteúdo de cada edital com LLM e classifica as questões numa árvore mestre (matéria → assunto → subassunto). O resultado alimenta um site público de questões, começando pelo piloto de 2025.

O crawler (Playwright) percorre a listagem de concursos encerrados e mapeia os PDFs de Edital, Prova e Gabarito. O downloader baixa e valida os arquivos. O parser (PyMuPDF) recorta as seções dos editais e dos cadernos, e a extração por LLM (OpenRouter, `z-ai/glm-5.3-flash`) produz a taxonomia, com checkpoint de revisão humana. Os dados vão para um Postgres próprio do projeto, em star schema, e a classificação das questões na árvore mestre alimenta o site.

## Seções

- **[Executivo](executivo/index.md)**: visão para quem não acompanha o código. Em preparação.
- **Técnico**: a [arquitetura](architecture.md), o [runbook de lote](runbook-lote.md), o [guia de teste no navegador](guia-teste-navegador.md), os [ADRs](adr/README.md) (decisões de arquitetura), os [planos concluídos](planos/README.md) e os [relatórios](relatorios/dispersao_arvore_2026-10-12.md).

## Como manter

- `make docs-serve`: sobe o site local em <http://127.0.0.1:8001>, com recarga ao salvar.
- `make docs-build`: gera `build/docs` com `mkdocs build --strict`. O `make check` roda esse alvo também.
- Toda página nova em `docs/` precisa entrar no `nav` do `mkdocs.yml`. Sem isso, o `--strict` falha, e é de propósito.
