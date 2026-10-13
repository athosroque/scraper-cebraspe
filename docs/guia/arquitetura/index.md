# Arquitetura

Como o sistema é montado: os componentes, a ordem das etapas do pipeline e onde os dados ficam.

**Para que serve:** entender o caminho de um concurso, do site do CEBRASPE até o banco e o site de questões, e saber onde cada peça vive no código. **Quando ler:** antes de mudar um componente, de criar uma etapa nova ou de escrever uma consulta no banco.

<div class="grid cards" markdown>

-   :material-puzzle-outline: **[Componentes](../../architecture.md)**

    ---

    Crawler, downloader, parser, extração por LLM, revisão humana e banco: o que cada um faz e as integrações com a infra do homelab.

-   :material-pipe: **[Pipeline e etapas](../../tecnico/pipeline.md)**

    ---

    O grafo das etapas, com dependências, portões humanos e etapas com LLM. Cada etapa mostra o comando, as entradas e as saídas.

-   :material-database-outline: **[Banco de dados](../../tecnico/banco.md)**

    ---

    As tabelas e views dos schemas `public` (pipeline) e `app` (usuários do site) do `scraper-cebraspe-db`, lidas do próprio banco.

</div>
