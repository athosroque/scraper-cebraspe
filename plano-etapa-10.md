# Plano da Etapa 10 — Portfólio público: identidade visual, processos e GitHub

Data da decisão: 2026-11-13. Pedido do dono: apresentar o projeto no GitHub como
portfólio público, melhorar a apresentação visual e nomear o que o projeto já faz
com o vocabulário de **mapeamento e documentação de processos** (BPMN, matriz RACI,
indicadores, Jira/ITSM), que é o que o mercado pede na vaga que motivou a etapa.

Decisões do dono tomadas na abertura:

1. Redesenhar **os dois** fronts, o site de documentação primeiro e o site de questões depois.
2. Manter o `docs/index.md` (roteador) **e** o `docs/executivo/index.md` (apresentação).
   Cortar apenas o parágrafo de abertura, que hoje aparece quase igual nos dois.
3. Incluir uma **seção completa de processos e governança**, não apenas um diagrama.
4. Publicar um **repositório público só do `scraper_cebraspe`**, sem expor o resto do
   homelab.

Ferramenta de apoio: a skill `frontend-design` (instalada em
`~/.claude/skills/frontend-design/`) guia as sessões P1 e P4 — plano de design antes do
código, e revisão do plano contra o brief antes de construir.

## Guardas que valem para toda a etapa

- `make check` verde ao fim de cada sessão (inclui `mkdocs build --strict`).
- P71: nenhuma sessão desta etapa escreve no banco; o piloto fica intacto (2.800 itens,
  129 anuladas, 3.029 apontamentos). K22–K24 só se alguma sessão tocar em carga.
- A62: as páginas de `docs/tecnico/` não são editadas à mão. Mudança de estrutura ali
  passa por `src/registro/` e `make docs-gerar`.
- Página nova entra no `nav` do `mkdocs.yml`, senão o `--strict` falha (ADR-040).
- A07 e A44: nenhum segredo entra em arquivo versionado — crítico na P3.

## P1 — Identidade visual do site de documentação

Objetivo: o site de documentação deixa de parecer um tema Material de prateleira e passa
a ter uma identidade própria, ligada ao assunto (concurso público, edital, caderno de
prova), sem perder a legibilidade de documentação técnica.

- `[ ]` Brief e plano de design: paleta de 4 a 6 cores nomeadas, tipografia com papéis
  definidos, conceito de layout e princípios. Revisar o plano contra o brief e registrar
  o que foi mudado por soar genérico. **Aprovação do dono antes de escrever CSS.**
- `[ ]` Aplicar em `docs/stylesheets/tema.css`, preservando: fonte do sistema para o
  Mermaid medir o rótulo certo (`font: false`, ADR-040), modo claro e escuro, e
  `impressao.css` para o PDF executivo.
- `[ ]` Tratar a abertura do `docs/index.md`: um papel por página, sem o parágrafo
  repetido no `executivo/index.md`.
- `[ ]` Hero da `executivo/index.md`: abrir pelo que é mais característico do projeto,
  não por um número grande com rótulo pequeno.
- `[ ]` Piso de qualidade: responsivo no celular, foco visível no teclado,
  `prefers-reduced-motion` respeitado, contraste conferido nos dois modos.
- `[ ]` Conferir no Chromium (`make docs-serve` + navegador) e no PDF
  (`make docs-build`), nos dois modos de cor.
- `[ ]` ADR-043 com a direção visual escolhida e o que foi descartado.

Pronto quando: `make check` verde, o PDF executivo sai correto, e o dono aprova as
telas nos dois modos.

## P2 — Seção "Processos e governança"

Objetivo: tornar explícito, na linguagem de processos, o que o projeto já pratica. Nada
aqui é invenção para a vitrine — cada artefato descreve um processo que existe e aponta
para o código, o ADR ou a regra que o sustenta.

- `[ ]` **Fluxo BPMN da curadoria de edital**, em piscinas e raias (dono/curador,
  pipeline automático, LLM). É o processo que mais rende: tem tarefa de usuário, tarefa
  de serviço, gateway de decisão (aprova / devolve) e evento de erro. Mermaid não faz
  BPMN de verdade; avaliar na sessão entre SVG desenhado à mão e exportação de uma
  ferramenta BPMN, e registrar a escolha.
- `[ ]` **Matriz RACI** por etapa do pipeline (coleta, extração, revisão humana,
  curadoria da árvore, classificação, carga, publicação), com as colunas dono/curador,
  agente, pipeline e revisor externo.
- `[ ]` **Painel de indicadores**: o que `docs/executivo/numeros.md` já mede, mais fonte,
  periodicidade e como a evidência é auditável (trilha de auditoria, Langfuse, checagens
  K22–K24).
- `[ ]` **Registro de riscos e plano de ação**: tabela curta com risco, impacto,
  controle existente e ação pendente. Fonte: ADRs, `LESSONS.md` e anti-patterns.
- `[ ]` **Política de versionamento documental**: git, `--strict` como guarda, páginas
  geradas de `src/registro/`, hook de publicação. Já existe; falta nomear.
- `[ ]` **Fluxo de card no Jira** (ler → 31 → comentar → 41) como processo de ITSM, com
  a ligação card ↔ etapa ↔ commit.
- `[ ]` `nav` do `mkdocs.yml` atualizado, com `index.md` de abertura da seção.
- `[ ]` ADR-044 com o recorte da seção e o critério do que não entra.

Pronto quando: a seção está no ar, `make check` verde, e cada artefato tem link para a
fonte no código ou no ADR que o sustenta.

## P3 — Repositório público do scraper e README de portfólio

Objetivo: um repositório público contendo só este projeto, apresentável a quem avalia o
portfólio, sem arrastar o resto do homelab nem nenhum segredo.

- `[x]` Decidir, com o dono, histórico novo (commit inicial único) ou extração do
  histórico com `git filter-repo`. O histórico tem valor de portfólio, mas exige
  varredura completa antes.
- `[x]` Varredura de segredos no que for publicado: `.env`, chaves `OPENROUTER_KEY_*`,
  senha do Postgres, senha de role do site, URLs internas e o e-mail pessoal onde não
  for intencional. Conferir também o histórico, se ele for publicado.
- `[x]` Definir o que fica fora: `data/`, `logs/`, `questoes/`, `revisao_piloto/*.db`,
  `build/`, `venv/`.
- `[x]` Reescrever o `README.md` como apresentação de portfólio: o que o projeto resolve,
  arquitetura em uma imagem, o que ele demonstra, e só depois o passo a passo de
  instalação (que hoje abre o arquivo e ocupa as primeiras 60 linhas).
- `[x]` Ligar README ↔ site de documentação ↔ PDF executivo, nos dois sentidos.
- `[x]` Resolver o acesso à documentação antes de linká-la: `docs.projetoathos.com.br`
  hoje está atrás do Cloudflare Access, restrito ao dono (ADR-040). Link de um README
  público para uma porta trancada não serve de vitrine. Opções: abrir o host, publicar
  uma cópia do `build/docs` no GitHub Pages do repositório novo, ou deixar só o PDF
  executivo versionado no repositório. Decisão do dono, com ADR.
- `[x]` Conferir se o CLAUDE.md e o `task.md` devem ir junto — eles mostram método, mas
  também expõem decisões internas. Decisão do dono.
- `[ ]` Criar o repositório e publicar. **Confirmação explícita do dono antes do push**,
  por ser ação pública e difícil de reverter.
- `[ ]` Depois da primeira publicação: transformar os dois comandos do `subtree split` em
  script registrado em `src/registro/scripts.py` (P70) com alvo no `Makefile`, para que
  publicar não seja um passo de memória (A13). Fica para depois de o repositório existir,
  porque o registro novo exige `make docs-gerar` e, com ele, a regeneração de
  `docs/tecnico/`.
- `[x]` Atualizar o campo "Repositório GitHub" no `CLAUDE.md` (§1), hoje
  "homelab local / a versionar".
- `[x]` ADR-045 com a decisão de repositório, histórico e escopo publicado.
- `[x]` `mkdocs.yml` com `site_url`, `repo_url`, `repo_name` e `edit_uri` do repositório
  público, e `site_description`/`site_author` para o cartão de compartilhamento.
- `[x]` `.github/workflows/publicar-docs.yml`: `mkdocs build --strict` e deploy no Pages
  por OIDC, com permissões mínimas e `concurrency: pages`. Inerte no monorepo (o GitHub só
  lê `.github/workflows/` na raiz do repositório), ativo depois do `subtree split`.
- `[x]` `requirements-docs.txt`: só `mkdocs-material`, `pymdown-extensions`, `playwright`
  e `pymupdf`. O build do site não precisa de banco nem de chave de LLM.
- `[x]` PDF executivo gerado no próprio job, com
  `--url-base https://athosroque.github.io/scraper-cebraspe`, senão o botão da página
  executiva cai em 404 no Pages.

Pronto quando: o repositório público está no ar, sem segredo nenhum, e o README abre
pela apresentação do projeto.

### P3b — Card no README do perfil do GitHub

O perfil `github.com/athosroque` é a primeira página que um recrutador abre, e o README
dele mora no repositório `athosroque/athosroque` (público, última alteração em
2026-09-18). Hoje ele destaca cinco projetos e não cita o scraper. Depois que o
repositório público existir:

- `[ ]` Escrever o card do scraper CEBRASPE no mesmo formato dos outros (título com link,
  uma linha de chamada, um parágrafo e as badges da stack), posicionado como projeto de
  destaque: é o único do portfólio com pipeline de ponta a ponta, banco próprio,
  governança documentada e site público.
- `[ ]` Puxar para o card o que a vaga de mapeamento de processos valoriza e que nenhum
  outro projeto do perfil mostra: BPMN da curadoria, matriz RACI, indicadores auditáveis,
  ADRs numerados, versionamento da documentação e fluxo de card no Jira (vem da P2).
- `[ ]` Corrigir o link do card do Genesys: aponta para `genesys-manager-v2-pilot`, nome
  antigo do repositório `genesys-manager-api`. Funciona por redirecionamento do GitHub,
  mas o endereço certo é o atual.
- `[ ]` Avaliar com o dono o enxugamento da seção "Stack Tecnológica": são cerca de 30
  badges em cinco grupos, e a lista longa dilui o que ele realmente quer destacar.
- `[ ]` Decidir se entram no perfil os públicos hoje não citados (`portfolio-sites`,
  `mushroom-information-gain`, `Power-B.I-projetos`, `-Movie-Recommender-System-MLOps`).
- `[ ]` **Confirmação explícita do dono antes de qualquer push** em
  `athosroque/athosroque`: é conteúdo público e com o nome dele.

Pronto quando: o perfil abre citando o scraper entre os destaques, com link que resolve
para o repositório novo.

## P4 — Identidade visual do site de questões

Objetivo: o produto ganha personalidade própria, sem perder o que as etapas 5G e 5H
validaram (fidelidade ao caderno, card e filtros no formato Gran).

- `[ ]` Brief e plano de design, revisado contra o brief. **Aprovação do dono antes do
  código.** O ADR-035 fixou o formato Gran em teal; esta sessão precisa dizer o que
  muda e o que fica, e se o ADR-035 é substituído ou complementado.
- `[ ]` Aplicar em `site/estilos/entrada.css`, `site/tailwind.config.js` e nos templates,
  sem quebrar HTMX nem Alpine.
- `[ ]` Rodar o teste do site no navegador (`docs/guia-teste-navegador.md`).
- `[ ]` `make test-all` verde; `site/openapi.json` só muda se rota ou modelo mudarem.
- `[ ]` ADR novo (ou "Atualização" no ADR-035) com a direção escolhida.

Pronto quando: o site roda com a identidade nova, o teste de navegador passa e o dono
aprova as telas.

## O que esta etapa não faz

- Não mexe no pipeline, no banco nem na árvore mestre.
- Não retoma o deploy público do site de questões (5F.12, opcional por decisão do dono).
- Não altera a 8.C, que segue sendo a prioridade de execução.
