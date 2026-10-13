# Operação

Como rodar o pipeline e conferir que ele está certo.

**Para que serve:** executar o trabalho do dia a dia (carregar concursos, rodar um script, testar o site) e saber se o resultado está verde. **Quando ler:** antes de rodar um lote ou um comando que grava no banco, e depois, para conferir.

<div class="grid cards" markdown>

-   :material-clipboard-text-outline: **[Runbook de lote](../../runbook-lote.md)**

    ---

    O passo a passo para levar um lote de concursos de múltipla escolha do site do CEBRASPE até o banco, com o que conferir em cada passo.

-   :material-console: **[Comandos](../../tecnico/comandos.md)**

    ---

    Todos os scripts (`python -m …`) por categoria, com os argumentos lidos do código.

-   :material-checkbox-marked-circle-outline: **[Checagens](../../tecnico/checagens.md)**

    ---

    O que valida cada parte do pipeline: consulta SQL (zero linhas é verde), teste do pytest ou comando.

-   :material-web-check: **[Teste do site no navegador](../../guia-teste-navegador.md)**

    ---

    Roteiro para testar o site de questões num navegador real, como visitante anônimo, com formato de relatório.

</div>

!!! warning "Piloto inalterado"

    Nenhum lote nem passo que grava no banco pode alterar o piloto de 2025. As checagens K22 a K24 rodam antes e depois, e uma diferença bloqueia o lote (regra [P71](../../tecnico/regras.md#p71)).
