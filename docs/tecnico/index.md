<!-- Gerado por scripts/gerar_docs.py a partir de src/registro/. Não editar à mão: rode `make docs-gerar`. -->

# Como as páginas são geradas

Parte do Guia técnico não é escrita à mão: sai do registro do pipeline em `src/registro/` (scripts, etapas, checagens, regras e tarefas) e do schema do banco.

**Para que serve:** uma fonte só para o pipeline documentado e o executado. Página gerada nunca fica desatualizada sem aviso, porque o teste `tests/test_registro.py` recusa página diferente do código.

## Como regerar

- `make docs-gerar`: regrava as páginas abaixo; lê o schema do banco.
- `venv/bin/python -m scripts.gerar_docs --sem-banco`: sem banco, mantém a página do banco como está.
- `venv/bin/python -m scripts.gerar_docs --verificar`: só confere; sai 1 se alguma página estiver diferente.

Não edite estas páginas à mão (regra [A62](regras.md#a62)): mude o registro e regere.

## Páginas geradas

- [Tarefas](tarefas.md): 12 tarefas de agente e o que ler para cada uma.
- [Pipeline](pipeline.md): 13 etapas, dependências e portões humanos.
- [Comandos](comandos.md): 32 scripts e seus argumentos.
- [Regras](regras.md): 139 patterns e anti-patterns do projeto.
- [Checagens](checagens.md): 36 checagens do pipeline.
- [Banco](banco.md): tabelas e views dos schemas `public` e `app`.
