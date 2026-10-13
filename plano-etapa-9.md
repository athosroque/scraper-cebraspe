# Plano da Etapa 9: documentação viva e acompanhamento do pipeline

Criado em 2026-10-12. Estado: **planejado, decisões do dono fechadas em 2026-10-13, nenhuma
sessão iniciada**.

> Jira: KAN-67 (etapa); D1 = KAN-68, D2 = KAN-69, D3 = KAN-70, D4 = KAN-71; D5a = KAN-31 e
> D5b = KAN-32 (são a C2 da 8.C, `plano-etapa-8c.md`).
> Ao abrir uma sessão, ler só este arquivo e a seção dela.

## Pedido do dono

> Preciso de um frontend, uma aplicação qualquer ou algo que me auxilie de forma visual, em
> todas as validações e documentação do projeto, algo profissional e escalável,
> principalmente dos pipelines e fluxos internos de coleta. Regras etc., algo que sempre que
> o projeto for modificado reflita.

Contexto que o dono deu depois (2026-10-12):

- O ambiente de desenvolvimento é o **Orca**, que organiza sessões, branches, agentes e
  worktrees. Os agentes precisam achar esse contexto quando o dono pedir.
- As tarefas ficam no **Jira** (KAN-N, via MCP do Atlassian; ver `agents/WHEN-TO-USE.md`).
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
| Execução e acompanhamento do pipeline | Dagster, no papel da C2 da 8.C (decidido em 2026-10-13) | dono |
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

## Decisões do dono (2026-10-13)

1. **Dagster já como C2.** A C2 da 8.C deixa de ser o script `scripts/lote_concursos.py`: o
   orquestrador mínimo nasce no Dagster (sessões D5a e D5b, cards KAN-31 e KAN-32), e os
   lotes C3 a C7 já rodam nele. O que sobra da 8.1 (`--proximo` na ordem dos anos, tamanho do
   lote, teto de custo) entra depois como schedule, sensor e config do Dagster.
2. **Documentação em paralelo à 8.C.** D1 a D4 não mexem no pipeline nem no banco e rodam
   numa worktree própria no Orca, sem esperar a coleta ME.
3. **Site em `docs.projetoathos.com.br`, atrás do Cloudflare Access**, como o Datasette
   (ADR-015). Para quem é de fora, o PDF da parte executiva (D4).
4. **D3 aprovado, com núcleo no `CLAUDE.md`:** o detalhe das regras de §6 e §7 vai para as
   páginas de regras, e o `CLAUDE.md` mantém uma lista curta das regras que quebram dados se
   forem esquecidas (piloto inalterado, `.env`, portões humanos), cada uma com link para a
   página.

## Ordem: duas trilhas

| Trilha | Sequência | Onde |
|---|---|---|
| A, documentação | D1 → D2 → D3 e D4 (em qualquer ordem depois do D2) | worktree própria, em paralelo |
| B, coleta ME (8.C) | C1b.0 → C1b.1 → C1b → **D5a → D5b (= C2)** → C3…C7 → C8 | `plano-etapa-8c.md` |

O D5a monta os assets do Dagster a partir do registro do D2. Se o D2 não estiver pronto quando
a C1b fechar, o D5a cria o registro só com as etapas, e o D2 completa depois com regras e
checagens.

## Sessões (uma sessão e um card no Jira por item)

### D1: Esqueleto do MkDocs (KAN-68)

- `mkdocs.yml` com Material, navegação "Executivo" e "Técnico", busca e Mermaid.
- Os docs atuais (ADRs, runbook, planos, `architecture.md`, relatórios) entram sem ser
  reescritos.
- `site_dir: build/docs`: o padrão `site/` colide com o app FastAPI em `site/`. `build/` no
  `.gitignore` e `mkdocs-material` nas dependências.
- Alvos no `Makefile` (`docs-serve`, `docs-build`) e `mkdocs build --strict` no `make check`.
- Container `scraper-cebraspe-docs` (nginx:alpine servindo o build) com rótulos do Traefik
  para `docs.projetoathos.com.br`. O dono cria a aplicação no Cloudflare Access (passo
  manual, como no Datasette).
- Pronto quando: o site sobe local e no domínio atrás do Access, todos os links internos
  resolvem e o `--strict` passa.

### D2: Registro e páginas geradas (KAN-69)

- Registro de etapas, checagens e regras, com as páginas e o diagrama Mermaid gerados dele
  (substitui o diagrama parado na fase 5). O mesmo registro é a fonte dos assets do Dagster
  (D5a): uma fonte só para o pipeline documentado e o executado.
- Teste guarda de sincronia: registro ↔ `scripts/` e registro ↔ `Definitions` do Dagster,
  quando existir.
- Checagens que hoje só aparecem no pytest ou no log passam a ter um resultado consultável
  (arquivo JSON gerado ou query documentada), para a página de validações mostrar o estado.
- Pronto quando: um script novo sem entrada no registro quebra o teste, e as páginas geradas
  batem com o código.

### D3: Contexto para agentes (KAN-70)

- Índice por tarefa (ex.: "rodar um lote", "curar a árvore", "mexer no site") apontando
  para as páginas certas.
- `CLAUDE.md` mais enxuto: o detalhe das regras de §6 e §7 passa para as páginas de regras,
  e o `CLAUDE.md` fica com identidade, estado, ponteiros e o núcleo de regras que quebram
  dados se forem esquecidas (piloto inalterado, `.env`, portões humanos), cada uma com link.
  **Aprovado pelo dono em 2026-10-13**, nesse formato.
- Pronto quando: um agente novo no Orca acha, a partir do `CLAUDE.md`, a regra e o runbook
  de uma tarefa sem ler o arquivo inteiro.

### D4: Documentação executiva (KAN-71)

- Visão (problema, solução, para quem), arquitetura em diagrama C4, números atuais
  (concursos, questões, custo de LLM), decisões principais (resumo dos ADRs) e roadmap
  ligado ao Jira.
- Exportação em PDF, para quem é de fora (o site fica atrás do Cloudflare Access).
- Pronto quando: o dono consegue enviar o PDF a alguém de fora sem precisar explicar o
  projeto antes.

### D5a: Dagster, infra e assets (KAN-31; é a C2 da 8.C, parte 1)

- `Dockerfile.dagster` (requirements do projeto + `dagster`, `dagster-webserver`,
  `dagster-postgres` e o Chromium do Playwright). Serviços webserver e daemon no
  `docker-compose.yml`, código por bind mount (como o bot), `data/`, `inventario/` e
  `revisao_piloto/` montados, credenciais do `.env`.
- Storage do Dagster num banco `dagster` separado dentro do `scraper-cebraspe-db` (nunca no
  `cebraspe`).
- Traefik em `dagster.projetoathos.com.br` + Cloudflare Access (o dono cria a aplicação).
- Assets gerados do registro (D2), particionados por concurso (partições dinâmicas vindas do
  inventário). Chamam as funções atuais, sem reescrever: `process_contest`,
  `revisar_edital_piloto`, `processar_fila`/`atualizar_artefatos_revisao`,
  `classificar_todas_questoes`; `--concurso` no `classificar_questoes` (hoje só `--caderno`).
- Lote = uma execução com 2 partições. O estado vem do Dagster (materializações) e do banco
  (`status_revisao_humana`); o `inventario/lotes.json` do plano antigo deixa de ser
  necessário.
- Testes: `Definitions` carrega; assets com as funções mockadas (retomada, parada no portão,
  aprovação).
- Pronto quando: materializar o lote da C1 (`SEFA_PR_25` + `BANRISUL_25`) em modo conferência
  não muda nada (idempotente), e a UI abre no domínio com Access.

### D5b: checagens, portões e relatório (KAN-32; é a C2 da 8.C, parte 2)

- Asset checks: tabela "Checagens automáticas por lote" do `plano-etapa-8.md` (download,
  edital, prova, banco, classificação, site), invariante do piloto antes e depois do lote,
  consultas a–e do `docs/runbook-lote.md`, alternativa terminando em caixa alta, custo pelo
  OpenRouter (`/api/v1/key`) e o alerta "ME sem texto-base" (questão ME que cita texto,
  tabela, figura, gráfico ou quadro sem texto-base nem figura; exceções BANRISUL Q22,
  SEFA_PR Q11 e Q50; não bloqueia).
- Portões humanos como checks bloqueantes que leem `status_revisao_humana` e as pendências da
  curadoria: a etapa seguinte não roda até o dono aprovar (Datasette, `curar_arvore.py`).
- Detector de dispersão (`detectar_dispersao_arvore --propor`) como asset depois da carga; as
  propostas novas vão para o relatório (KAN-64).
- Pendências do §7 do runbook: chunking sem LLM (`--so-chunking`) e todos os editais do lote
  extraídos antes de uma carga só.
- Relatório `inventario/lotes/lote_NN.md` gerado dos resultados das checks.
- Pronto quando: o relatório do lote da C1 sai com as checagens verdes e um teste mostra o
  portão travando a etapa seguinte.
