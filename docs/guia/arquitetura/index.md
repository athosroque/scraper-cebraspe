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

-   :material-spider: **[Coleta e download](../coleta.md)**

    ---

    Crawler, deduplicação em duas camadas de PDFs e controle de inventário.

-   :material-brain: **[Extração por LLM](../extracao-llm.md)**

    ---

    Recorte, chunking, chamadas ao OpenRouter/GLM e observabilidade no Langfuse.

-   :material-account-check: **[Revisão humana](../revisao-humana.md)**

    ---

    Datasette, relatórios por edital e portões que bloqueiam avanço de etapas.

-   :material-file-tree: **[Árvore mestre](../arvore.md)**

    ---

    Estrutura de nó, assunto e subassunto, e o ciclo de curadoria semear → propor → curar.

-   :material-web: **[Site público](../site.md)**

    ---

    Aplicação pública com simulação de provas, correção CEBRASPE e estatísticas.

-   :material-api: **[API do site](../api.md)**

    ---

    Contratos OpenAPI, rotas FastAPI, autenticação Google e histórico de resolução.

</div>
