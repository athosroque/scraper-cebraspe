# Scraper CEBRASPE

Pipeline que coleta editais, provas e gabaritos do CEBRASPE, organiza o conteúdo cobrado numa árvore de assuntos e alimenta um site público de questões, começando pelo piloto de 2025.

O crawler (Playwright) percorre os concursos encerrados e baixa os PDFs. O parser (PyMuPDF) recorta os editais e os cadernos de prova, e um LLM (OpenRouter, `z-ai/glm-5.3-flash`) extrai a taxonomia de cada edital, que passa por revisão humana. As questões são classificadas na árvore mestre (matéria → assunto → subassunto) e gravadas num Postgres próprio. Desse banco saem as estatísticas e o site.

## Por onde começar

Escolha pelo que você precisa fazer.

<div class="grid cards" markdown>

-   :material-briefcase-outline: **[Visão executiva](executivo/index.md)**

    ---

    Quero entender o projeto sem ler código: problema, solução, números e próximos passos.

-   :material-robot-outline: **[Para agentes](guia/agentes/index.md)**

    ---

    Vou mexer no código, como pessoa ou agente. Comece pelo índice de tarefas e pelas regras que não podem ser esquecidas.

-   :material-cog-play-outline: **[Operação](guia/operacao/index.md)**

    ---

    Vou rodar um lote de concursos, um comando ou conferir se o pipeline está verde.

-   :material-sitemap-outline: **[Arquitetura](guia/arquitetura/index.md)**

    ---

    Quero ver como as peças se encaixam: componentes, etapas do pipeline e banco de dados.

-   :material-scale-balance: **[Decisões](adr/README.md)**

    ---

    Quero saber por que algo é assim antes de mudar. Os ADRs registram cada escolha e o que foi descartado.

-   :material-history: **[Histórico](historico/index.md)**

    ---

    Quero consultar planos de etapas já concluídas e relatórios datados.

</div>

## Como este site está organizado

| Aba | O que tem | Muda quando |
|---|---|---|
| **Visão executiva** | Resumo para quem não acompanha o código | Fecha uma etapa importante |
| **Guia técnico** | Agentes, arquitetura e operação | Muda o código (parte das páginas é gerada) |
| **Decisões** | ADRs agrupados por tema | Entra uma decisão nova |
| **Histórico** | Planos concluídos e relatórios | Não muda: é registro do passado |

## Como manter esta documentação

- `make docs-serve`: site local em <http://127.0.0.1:8001>, com recarga ao salvar.
- `make docs-build`: gera `build/docs` com `mkdocs build --strict`. O `make check` roda esse alvo também.
- `make docs-gerar`: regera as páginas que vêm do código (ver [Como as páginas são geradas](tecnico/index.md)).
- Publicação automática: depois de `make hooks-instalar`, commit ou merge que toca os docs roda o `docs-build` sozinho (log em `logs/publicar_docs.log`). Se o CSS parecer antigo, force com Ctrl+Shift+R: o Cloudflare guarda o CSS em cache por 4 h.
- Página nova entra no `nav` do `mkdocs.yml`, na seção do seu propósito. Fora do `nav`, o `--strict` falha, e é de propósito.
