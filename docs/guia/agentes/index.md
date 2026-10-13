# Para agentes

O contexto que um agente (ou uma pessoa nova no projeto) precisa antes de mexer no código.

**Para que serve:** achar, para uma tarefa concreta, as páginas a ler e as regras que não podem ser esquecidas, sem ler o `CLAUDE.md` inteiro. **Quando ler:** no começo de qualquer tarefa não trivial. Comece pela tarefa e só depois desça para a regra.

<div class="grid cards" markdown>

-   :material-format-list-checks: **[Tarefas por tipo de trabalho](../../tecnico/tarefas.md)**

    ---

    Para a tarefa X, leia Y. Cada tarefa (rodar um lote, curar a árvore, mexer no site…) lista páginas, regras, etapas, comandos, checagens e ADRs.

-   :material-gavel: **[Regras do projeto](../../tecnico/regras.md)**

    ---

    Patterns e anti-patterns por área, com a ADR que motiva cada um e o teste que o guarda. O **núcleo** são as regras que quebram dados se forem esquecidas.

-   :material-file-cog-outline: **[Como as páginas são geradas](../../tecnico/index.md)**

    ---

    De onde vêm as páginas geradas, como regerar e o teste que recusa página desatualizada.

</div>

!!! tip "Fluxo recomendado"

    1. Ache a sua tarefa em [Tarefas](../../tecnico/tarefas.md).
    2. Leia as páginas e as regras do **núcleo** que ela lista.
    3. Antes de reabrir uma escolha (stack, banco, parser, site), leia a ADR em [Decisões](../../adr/README.md).
