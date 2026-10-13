# ADR-040: Site de documentação em MkDocs Material (executivo e técnico)

- **Status:** Aceito
- **Data:** 2026-10-13
- **Etapa:** 9, sessão D1 (KAN-68; plano em `plano-etapa-9.md`, card KAN-67)
- **Decisores:** Dono do produto
- **Relaciona-se com:** ADR-015 (publicação de revisão via Traefik e Cloudflare
  Access), ADR-030 (o site público de questões continua sendo o `site/`)

---

## 1. Contexto

O dono pediu uma documentação visual e atualizada, que reflita o projeto sempre
que ele mudar: pipelines, regras, validações e fluxos de coleta. Hoje a
documentação está espalhada: ADRs em `docs/adr/`, runbooks e planos em `docs/`,
relatórios HTML gerados em `revisao_piloto/` e o diagrama de arquitetura parado
desde a fase 5. Não há um lugar único para ler nem busca sobre tudo.

Duas restrições pesam na escolha:

- O `site/` já é um app FastAPI (ADR-033). Qualquer ferramenta de site estático
  que use `site/` como diretório de saída colide com ele.
- A publicação precisa seguir o padrão do projeto: container atrás do Traefik,
  exposto pelo Cloudflare Tunnel e protegido pelo Cloudflare Access (ADR-015).
  Um servidor de desenvolvimento não serve para isso.

## 2. Decisão

1. **Gerador:** MkDocs com o tema Material, `mkdocs-material>=9.6,<10` no
   `requirements.txt`. A configuração fica em `mkdocs.yml` na raiz do projeto,
   com `docs_dir: docs`.
2. **Saída:** `site_dir: build/docs`. O padrão `site/` apagaria o app FastAPI, e
   `build/` está no `.gitignore`.
3. **Duas abas:** "Executivo" (`docs/executivo/`, visão do produto para quem está
   de fora; conteúdo real entra na D4) e "Técnico" (arquitetura, runbooks, guia de
   teste no navegador, ADRs, planos concluídos e relatórios).
4. **Conteúdo existente entra sem reescrita.** A única alteração em um documento
   antigo é o link do `docs/planos/plano-kan-30.md` que saía de `docs/`
   (`../../plano-etapa-8c.md`), trocado por texto em código.
5. **Navegação explícita.** O `nav` do `mkdocs.yml` é listado à mão, e a seção
   `validation` está com `omitted_files`, `not_found` e `anchors` em `warn`. Com
   `mkdocs build --strict`, isso vira erro: página nova em `docs/` sem entrada no
   `nav`, link quebrado ou âncora inexistente quebram o `make check`. Esse é o
   mecanismo que mantém a documentação em dia sem depender de lembrança.
6. **Busca em português** (plugin `search` com `lang: pt`) e diagramas Mermaid pelo
   `pymdownx.superfences`. As âncoras usam `pymdownx.slugs` no estilo do GitHub, que
   mantém os acentos.
7. **Alvos no `Makefile`:** `make docs-serve` (http://127.0.0.1:8001 para
   desenvolvimento) e `make docs-build` (`mkdocs build --strict`). O `make check`
   passa a rodar lint, format-check, `docs-build` e `test-all`.
8. **Publicação:** container `scraper-cebraspe-docs` com `nginx:alpine`, bind mount
   de `./build/docs` em somente leitura, porta `127.0.0.1:8013`, rede
   `homelab_default` e Traefik com `Host(docs.projetoathos.com.br)`. O endereço
   público fica atrás do Cloudflare Access. O Public Hostname no túnel e a
   aplicação no Access são feitos à mão pelo dono, como no Datasette.
   `make docs-build` precisa rodar antes do primeiro `docker compose up`, porque
   senão o Docker cria `build/docs` como root. Depois do merge, o container sobe
   do checkout principal, já que o bind mount aponta para lá.

## 3. Consequências

- Documentação e checagens viram uma única fonte, navegável no navegador. Quando
  um arquivo novo não entra no `nav`, o `make check` avisa na hora.
- O `build/docs` é regenerável e fica fora do git. O bind mount é somente leitura,
  e o nginx serve arquivos estáticos (sem reload e sem o servidor de
  desenvolvimento).
- A dependência nova é só `mkdocs-material`, com o plugin `search` que já vem com o
  tema. O `nav` explícito dispensa plugin de navegação por glob.
- O acesso externo depende de dois passos manuais do dono (Public Hostname e
  Access). Até lá, o site fica só local em `127.0.0.1:8013`.
- A D2 (registro gerado do código) e a D3 (contexto para agentes) entram no mesmo
  `nav`, sem mudar a estrutura decidida aqui.

### 3.1 Alternativas descartadas

- **`mkdocs serve` num container:** é servidor de desenvolvimento, sem cache e com
  reload. Não serve para publicação.
- **Datasette com `--static`:** misturaria a revisão do piloto com a documentação.
  O Datasette continua só como ferramenta de revisão (ADR-015).
- **Plugin de navegação por glob:** mais uma dependência. O `nav` explícito com
  `omitted_files` já garante que nada escape.
- **Sem gerador (só Markdown no GitHub):** não tem busca, Mermaid com tema
  consistente, nem o alerta de link e âncora quebrados no build.

## Atualização (2026-10-13): navegação por propósito

Antes de aprovar a D3 (KAN-70), o dono achou o site bagunçado. A aba "Técnico" juntava
tudo, e os 41 ADRs abriam de uma vez na barra lateral, com o título longo do H1. O `nav`
passou a ter **5 abas por propósito**:

- **Início:** o que é o projeto, cartões "por onde começar" para cada público e como manter
  o site.
- **Visão executiva:** a seção da D4 (KAN-71).
- **Guia técnico**, com três seções: *Para agentes* (tarefas, regras, páginas geradas),
  *Arquitetura* (componentes, pipeline, banco) e *Operação* (runbook, comandos, checagens,
  teste do site). Páginas geradas e escritas à mão ficam juntas, pelo propósito.
- **Decisões:** os ADRs em 6 grupos por tema, com título curto no `nav` (`001 · Ano pelo
  slug da URL`). O `adr/README.md` traz o catálogo completo nas mesmas 6 tabelas.
- **Histórico:** os planos concluídos e os relatórios.

Regras novas:

- Toda aba e toda seção têm uma página de abertura (`index.md`) que diz o que a seção é,
  para que serve e quando ler, e traz uma grade de cartões com uma linha por página.
- Página nova entra no `nav` na seção do seu propósito. Seção nova ganha a sua página de
  abertura. Nenhum arquivo muda de caminho por causa da navegação, porque o `CLAUDE.md`, o
  `task.md` e os ADRs citam esses caminhos.
- Os ajustes visuais (cartões, seção em caixa alta com linha-guia, aba ativa sublinhada,
  breadcrumb com `navigation.path`) ficam em `docs/stylesheets/tema.css`. O tema continua
  sendo o do D2.

## Atualização (2026-10-13): publicação automática

O nginx serve o `build/docs` do checkout principal, e o site só mudava quando alguém rodava
`make docs-build`, um passo manual que o A13 proíbe. **Decisão:** hooks git `post-commit` e
`post-merge`, instalados por `make hooks-instalar`, chamam `scripts/hooks/publicar_docs.sh`.

- Só age se o commit (ou `ORIG_HEAD..HEAD`, no merge) tocou `docs/`, `mkdocs.yml`,
  `scripts/gerar_docs.py` ou `src/registro/`.
- Só age no checkout principal (`git-dir` igual ao `git-common-dir`): os hooks são
  compartilhados com as worktrees do Orca, mas o nginx só enxerga o build do principal. O
  trabalho da worktree publica quando entra no master por merge.
- O build roda em segundo plano, um por vez (`flock`), com log em `logs/publicar_docs.log`.
  O hook nunca falha o commit: build quebrado vira linha no log.
- O `make docs-build` gera em `build/docs.novo` e só sincroniza com `build/docs` (`rsync
  --delete`) se o `--strict` passar. Sem isso, o `mkdocs` limpa o destino antes de validar,
  e um build quebrado deixava o site fora do ar. Agora o site fica na última versão boa. É
  `rsync`, e não `mv`, porque o bind mount do nginx aponta para o diretório `build/docs`.
- O `.git/hooks` é de todo o monorepo. O instalador é idempotente e, se achar hook de outro
  projeto, guarda como `<hook>.anterior` e o encadeia.

Alternativas descartadas:

- **Cron:** publica com atraso, roda sem mudança e esconde o erro longe do commit.
- **Container rodando o build do mkdocs:** põe Python, o tema e o `venv` na imagem do
  nginx e duplica dependências, para resolver algo que um hook curto resolve.
- **CI/deploy:** o site é local; não há pipeline de entrega para acionar.


## Atualização (2026-10-13): visão executiva e PDF (D4, KAN-71)

A aba "Visão executiva" era um aviso de "em preparação". **Decisão:** ela passa a ter 5 páginas
(visão, arquitetura C4, números, decisões principais e roadmap) e sai também como PDF, para
quem está fora do Cloudflare Access.

- **Números gerados, não digitados.** `docs/executivo/numeros.md` é escrita por
  `scripts/gerar_numeros.py`, que o `make docs-gerar` roda depois do `gerar_docs`. O script lê o
  banco (só leitura, schema `public`) e o custo acumulado de cada chave no OpenRouter
  (`/api/v1/key`). O Langfuse não serve como fonte de custo: a API v2 de métricas devolve custo 0.
  Sem rede, `--sem-custo` gera a página dizendo que o custo não foi consultado. Uma chave trocada
  recomeça do zero, então o total é um piso.
- **C4 em `flowchart`.** Os diagramas `C4Context` e `C4Container` do Mermaid são experimentais, e
  o tema do Material não se aplica a eles. A notação C4 fica nos rótulos (`[Pessoa]`,
  `[Contêiner: FastAPI]`) e na fronteira por `subgraph`. Preenchimento translúcido, como no
  diagrama do pipeline: o Material impõe a cor do texto do Mermaid conforme o tema, e um fundo
  sólido escuro deixava o rótulo ilegível no tema claro.
- **PDF no mesmo build.** `scripts/exportar_pdf_executivo.py` roda dentro do `make docs-build`,
  sobre o `build/docs.novo` e antes do rsync. Assim o PDF nunca fica atrás do site (A13) e é
  servido em `/executivo/scraper-cebraspe-executivo.pdf`. Para imprimir, o script serve o build por
  HTTP local e usa o Chromium do Playwright, que já faz parte da stack. Ele espera o Mermaid
  renderizar, reescreve os links para `https://docs.projetoathos.com.br` e junta capa e páginas
  com PyMuPDF, com sumário e numeração "página X de N" carimbada depois da junção (o Chromium
  numera cada página do site isoladamente). Custo da escolha: o `make docs-build` e o `make check`
  passam a precisar do Chromium e do Mermaid do CDN (unpkg).
- **CSS de impressão** em `docs/stylesheets/impressao.css`, só em `@media print`: esconde o que
  é do site (cabeçalho, abas, barras, rodapé) e tudo com a classe `so-tela` (o botão do PDF e os
  cartões de navegação).
- O hook de publicação também dispara quando mudam `scripts/gerar_numeros.py` ou
  `scripts/exportar_pdf_executivo.py`.

Alternativas descartadas:

- **Plugins de PDF do MkDocs (`mkdocs-with-pdf`, `mkdocs-exporter`):** o primeiro usa WeasyPrint,
  que não executa o JavaScript do Mermaid. O segundo traz outra cópia do Playwright e
  configuração própria, para algo que um script de ~300 linhas resolve com o que já está no `venv`.
- **Números escritos à mão:** envelhecem a cada lote, sem sinal nenhum.
