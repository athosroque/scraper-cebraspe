# Plano da Etapa 9: documentação viva e acompanhamento do pipeline

Criado em 2026-10-12. Estado: **planejado, nenhuma sessão iniciada**.

## Pedido do dono

> Preciso de um frontend, uma aplicação qualquer ou algo que me auxilie de forma visual, em
> todas as validações e documentação do projeto, algo profissional e escalável,
> principalmente dos pipelines e fluxos internos de coleta. Regras etc., algo que sempre que
> o projeto for modificado reflita.

Contexto que o dono deu depois (2026-10-12):

- O ambiente de desenvolvimento é o **Orca**, que organiza sessões, branches, agentes e
  worktrees. Os agentes precisam achar esse contexto quando o dono pedir.
- As tarefas ficam no **Jira** (KAN-N, via `scripts/jira_sync.py`).
- Vale combinar mais de uma ferramenta, cada uma na parte em que é melhor. Construir uma
  ferramenta própria só se a customização exigir.
- A documentação precisa servir também para **vender o projeto como projeto executivo**.

## O que existe hoje (levantamento de 2026-10-12, exploradores com Opus 5.5)

- **Relatórios:** HTML estático montado com f-string em `scripts/gerar_relatorio_*.py`
  (`<edital>.html`, `index.html`, `arvore.html`, `classificacao.html`, `sinonimos.html`,
  este último obsoleto). O Datasette serve esses arquivos em `/relatorio/` e é refeito por
  `scripts/atualizar_revisao.py`.
- **Documentação:** `docs/adr/` (ADR-001 a 039), `docs/planos/`, `docs/runbook-lote.md`,
  `docs/relatorios/`, `task.md` (~1.250 linhas) e `CLAUDE.md` (~950 linhas, com as regras em
  §6 e §7). O diagrama Mermaid de `docs/architecture.md` parou na fase 5. Não há gerador de
  documentação (MkDocs, Sphinx) em nenhum lugar do homelab.
- **Pipeline:** não tem orquestrador nem registro de etapas. É uma sequência de CLIs
  `python -m ...` que o dono roda na mão. O único encadeamento automático é
  `atualizar_artefatos_revisao`. O grafo de etapas só existe implícito nos imports e nos
  arquivos que uma etapa grava e a seguinte lê. `scripts/lote_concursos.py` (C2) é citado no
  runbook, mas ainda não existe.
- **Validações:** algumas ficam guardadas e dá para consultar (`questoes.alertas`,
  `utilizavel`, status do caderno na fila, alertas do inventário em `inv_concurso`). Outras
  aparecem só na saída do pytest ou no log (guardas da árvore, `desatualizados` da
  classificação, a maior parte das invariantes do piloto).
- **Banco:** não há tabela de execuções nem de custo de LLM. O custo fica só no Langfuse
  (traces `cebraspe-<etapa>-<função>`).
- **Grafana:** não tem fonte de dados para o `scraper-cebraspe-db`.

## Decisão: uma fonte só e cada ferramenta numa parte

Tudo nasce como arquivo no repositório (Markdown e um registro em Python). Um agente do Orca
lê os `.md` direto na worktree dele, sem servidor nem login. O dono e um possível cliente
leem o mesmo conteúdo como site.

| Parte | Ferramenta | Quem usa |
|---|---|---|
| Documentação executiva (problema, solução, arquitetura, números, custos, roadmap) | MkDocs Material, seção "Executivo", exportada em PDF | cliente, dono |
| Documentação técnica (pipeline, etapas, regras, checagens, ADRs, runbook, banco) | MkDocs, seção "Técnico", com páginas geradas do código | dono, agentes |
| Contexto para agentes | os mesmos `.md`, um índice "para a tarefa X, leia Y" e um `CLAUDE.md` curto que aponta para lá | agentes do Orca |
| Execução e acompanhamento do pipeline | Dagster, no papel da C2 (decisão aberta, ver abaixo) | dono |
| Tarefas | Jira, como hoje; a documentação cita o KAN-N | dono, agentes |
| Tela própria | só se algo não couber nas ferramentas acima (ex.: aprovar em lote) | dono |

Alternativas descartadas como solução única:

- **App próprio ("Central")** com tudo: cobre todas as partes, mas obriga a construir e
  manter cada tela, e o grafo do pipeline sai de um registro em vez da execução real. Volta
  a ser considerado só para o que as ferramentas prontas não cobrirem.
- **Só MkDocs:** não mostra o estado ao vivo (lotes, pendências do dono, execuções).
- **Só Dagster:** não cobre regras, ADRs nem a parte executiva.

### Como a documentação acompanha o código

- As páginas técnicas são **geradas**, nunca escritas à mão: etapas, regras, checagens,
  comandos de cada script (introspecção do `argparse`), schema do banco
  (`information_schema`) e o diagrama Mermaid do pipeline.
- A fonte é um **registro em Python** (ex.: `src/registro.py`) com etapas (comando, entradas,
  saídas, se usa LLM e qual chave, portão humano), checagens e regras (com o ADR e o teste
  guarda de cada uma).
- Um **teste guarda** falha se surgir um script em `scripts/` ou uma etapa que não esteja no
  registro, ou se uma regra citar um ADR ou teste inexistente.
- O site é reconstruído no `make check` (`mkdocs build --strict`). O que é escrito à mão
  (ADRs, textos executivos) segue o fluxo de hoje.

## Sessões (uma sessão e um card no Jira por item)

### D1: Esqueleto do MkDocs

- `mkdocs.yml` com Material, navegação "Executivo" e "Técnico", busca e Mermaid.
- Os docs atuais (ADRs, runbook, planos, `architecture.md`, relatórios) entram sem ser
  reescritos.
- Alvos no `Makefile` (`docs-serve`, `docs-build`) e `mkdocs build --strict` no `make check`.
- Pronto quando: o site sobe local, todos os links internos resolvem e o `--strict` passa.

### D2: Registro e páginas geradas

- Registro de etapas, checagens e regras, com as páginas e o diagrama Mermaid gerados dele
  (substitui o diagrama parado na fase 5).
- Teste guarda de sincronia entre código e registro.
- Checagens que hoje só aparecem no pytest ou no log passam a ter um resultado consultável
  (arquivo JSON gerado ou query documentada), para a página de validações mostrar o estado.
- Pronto quando: um script novo sem entrada no registro quebra o teste, e as páginas geradas
  batem com o código.

### D3: Contexto para agentes

- Índice por tarefa (ex.: "rodar um lote", "curar a árvore", "mexer no site") apontando
  para as páginas certas.
- `CLAUDE.md` mais enxuto: as regras de §6 e §7 passam para as páginas de regras, e o
  `CLAUDE.md` fica com identidade, estado e ponteiros. **Exige aprovação do dono antes de
  mexer**, porque muda o que todo agente carrega.
- Pronto quando: um agente novo no Orca acha, a partir do `CLAUDE.md`, a regra e o runbook
  de uma tarefa sem ler o arquivo inteiro.

### D4: Documentação executiva

- Visão (problema, solução, para quem), arquitetura em diagrama C4, números atuais
  (concursos, questões, custo de LLM), decisões principais (resumo dos ADRs) e roadmap
  ligado ao Jira.
- Exportação em PDF.
- Pronto quando: o dono consegue enviar o PDF a alguém de fora sem precisar explicar o
  projeto antes.

### D5: Dagster como C2 (depende de decisão)

- Etapas viram assets que chamam as funções atuais (não reescrevem), com partição por
  concurso, asset checks para as validações e os portões humanos como checagens que travam a
  etapa seguinte.
- Containers novos no `docker-compose.yml`, expostos via Traefik + Cloudflare Access.

## Decisões abertas (perguntar ao dono antes da sessão correspondente)

1. **Ordem:** começar pela documentação (D1 → D4) ou pôr o Dagster antes? O Dagster ocupa o
   lugar da C2 da 8.C, e hoje a C2 está planejada como script simples, com a coleta ME como
   prioridade do dono.
2. **Acesso ao site de documentação:** só local, ou em `docs.projetoathos.com.br` atrás do
   Cloudflare Access, como o Datasette?
3. **D3:** aprovar a migração das regras de §6 e §7 do `CLAUDE.md` para as páginas.
