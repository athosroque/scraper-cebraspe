# Guia técnico

Tudo o que é preciso para trabalhar no projeto: o contexto para agentes, a arquitetura e a operação do pipeline.

**Para que serve:** responder "como isso funciona?" e "como eu faço X?" sem precisar ler o `CLAUDE.md` inteiro ou o código. **Quando ler:** antes de mexer no código, de rodar um lote ou de investigar um problema.

<div class="grid cards" markdown>

-   :material-compass-outline: **[Começando](comecando.md)**

    ---

    Trilhas de leitura e primeiros passos para cada perfil (dono, agente ou visitante).

-   :material-book-alphabet: **[Glossário](glossario.md)**

    ---

    Vocabulário canônico: termos e definições técnicas do projeto.

-   :material-robot-outline: **[Para agentes](agentes/index.md)**

    ---

    O ponto de partida de quem vai mexer no projeto. Para cada tarefa, o que ler e as regras que valem nela.

-   :material-sitemap-outline: **[Arquitetura](arquitetura/index.md)**

    ---

    Como o sistema é montado: os componentes, as etapas do pipeline com as dependências entre elas, e o banco de dados.

-   :material-cog-play-outline: **[Operação](operacao/index.md)**

    ---

    Como rodar e conferir: o runbook de lote, os comandos com seus argumentos, as checagens e o roteiro de teste do site.

</div>

!!! info "Páginas geradas do código"

    Parte deste guia (tarefas, regras, pipeline, banco, comandos e checagens) é gerada de `src/registro/` por `make docs-gerar`. Não edite à mão (regra [A62](../tecnico/regras.md#a62)). Mude o registro e regere as páginas. Detalhes em [Como as páginas são geradas](../tecnico/index.md).
