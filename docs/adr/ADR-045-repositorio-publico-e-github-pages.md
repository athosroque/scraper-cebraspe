# ADR-045: Repositório público do scraper e documentação no GitHub Pages

- **Status:** Aceito
- **Data:** 2026-11-17
- **Etapa:** 10, sessão P3 (KAN-105; plano em `plano-etapa-10.md`)
- **Decisores:** Dono do produto
- **Relaciona-se com:** ADR-040 (site de documentação em MkDocs, servido por nginx atrás
  do Cloudflare Access), ADR-041 (páginas técnicas geradas de `src/registro/`), ADR-043
  (identidade visual da documentação), A42 (nunca commitar `questoes/`), A07 (credenciais
  só em `.env`)

---

## 1. Contexto

O projeto vive em `scraper_cebraspe/`, um diretório do monorepo **privado**
`athosroque/Homelab`, que também guarda outros projetos do portfólio, configuração de
infraestrutura e serviços do servidor. Nada disso pode ser publicado junto.

A documentação existe e está completa — 97 páginas, com a visão executiva, o guia
técnico e as páginas geradas do registro —, mas é servida por nginx em
`docs.projetoathos.com.br`, atrás do Cloudflare Access, com acesso restrito à conta do
dono (ADR-040). Essa escolha fazia sentido enquanto a documentação era interna. Como
vitrine de portfólio ela não serve: um link no README público levaria o leitor a uma
tela de login.

Em 2026-11-13 o dono decidiu transformar o projeto em portfólio público (Etapa 10) e,
em 2026-11-17, escolheu o **GitHub Pages** como endereço público da documentação,
pedindo também o README do repositório e a entrada no README do perfil.

O campo "Repositório GitHub" do `CLAUDE.md` dizia, até aqui, "homelab local / a
versionar".

## 2. Decisão

### 2.1 Repositório próprio, público, com o projeto na raiz

`github.com/athosroque/scraper-cebraspe`, público, branch padrão `main`. O nome em
kebab-case segue os outros repositórios do portfólio (`study-rag-agent`,
`genesys-manager-api`, `hub-seo`). O projeto fica na raiz, não num subdiretório: é o que
faz os caminhos do README, do `mkdocs.yml` e dos comandos funcionarem como estão
escritos.

### 2.2 O histórico vai junto, extraído com `git subtree split`

Os 256 commits que tocam `scraper_cebraspe/` são preservados, com os caminhos reescritos
para a raiz:

```bash
git subtree split --prefix=scraper_cebraspe -b publico/scraper
git push git@github.com:athosroque/scraper-cebraspe.git publico/scraper:main
```

`git subtree split` é nativo e resolve o caso; não é preciso instalar `git filter-repo`.

A decisão de preservar depende da varredura de segredos, feita antes (KAN-105): 438
caminhos já existiram no histórico do diretório, e o único arquivo sensível por natureza
é `.env.example`, sem valores. A busca por `sk-or-v1-`, `sk-lf-`, `pk-lf-`,
`ghp_`/`gho_`/`github_pat_`, `AKIA…`, `BEGIN PRIVATE KEY`, token de bot do Telegram,
`POSTGRES_PASSWORD=` com valor literal e `password: "…"` só encontrou placeholders de
documentação, valores de teste e prefixos truncados de chave **pública** do Langfuse em
texto de ADR. As duas menções ao e-mail pessoal do dono, em `CLAUDE.md` e `task.md`,
foram trocadas por "a conta do dono" antes da publicação.

A mesma varredura tratou o que não é segredo mas é infraestrutura privada: o
`.env.example` trazia a instância real do Jira em `JIRA_URL`, trocada por
`https://<sua-instancia>.atlassian.net`, e dez links `…atlassian.net/browse/KAN-N` no
`docs/executivo/roadmap.md` e no `docs/planos/plano-kan-30.md` viraram o código do card
em `code`. Link para instância privada é porta trancada para quem lê a vitrine, e o
código do card preserva a rastreabilidade sem prometer uma página que o leitor não pode
abrir.

O histórico é parte do que o portfólio demonstra: mensagens em Conventional Commits, em
português, cada uma amarrada a um card do Jira e a um ADR. Um commit inicial único
apagaria exatamente a evidência de método que a vitrine quer mostrar.

### 2.3 Documentação no GitHub Pages, pelo mesmo build

`.github/workflows/publicar-docs.yml` roda `mkdocs build --strict` e publica
`build/docs` no Pages, por push em `main` que toque `docs/`, `mkdocs.yml`,
`requirements-docs.txt`, o exportador de PDF ou o próprio workflow, e por
`workflow_dispatch`. Permissões mínimas (`contents: read`, `pages: write`,
`id-token: write`) e `concurrency: pages` sem `cancel-in-progress`, para não deixar o
Pages servindo um build parcial.

O nginx interno **continua existindo**. São duas publicações do mesmo build: o Pages é o
endereço de portfólio, e `docs.projetoathos.com.br` segue como cópia interna, que o hook
`post-commit` atualiza no servidor. `site_url` aponta para o Pages, porque é o endereço
canônico para quem vem de fora.

### 2.4 `requirements-docs.txt` separado

O workflow instala `mkdocs-material`, `pymdown-extensions`, `playwright` e `pymupdf` —
não o `requirements.txt` inteiro, que carrega Postgres, LLM, Dagster e Playwright de
coleta. O build de HTML não precisa de nada disso. As páginas de `docs/tecnico/` são
versionadas (ADR-041), então o site constrói **sem banco**.

### 2.5 O PDF da visão executiva é gerado no CI

O botão "Baixar esta visão em PDF" aponta para um arquivo que não está versionado. O
workflow roda `scripts/exportar_pdf_executivo.py` depois do build, com
`--url-base https://athosroque.github.io/scraper-cebraspe`, para que os links absolutos
do PDF levem ao Pages e não ao host interno atrás do Access.

### 2.6 O que não é publicado

`data/` (PDFs baixados), `questoes/` (texto das questões extraídas, A42), `logs/`,
`build/`, `venv/`, `revisao_piloto/*.db` e `.env` — todos já no `.gitignore`. O conteúdo
das provas é da banca; o repositório guarda só o que é derivado e próprio: a árvore de
assuntos, a classificação (ligada ao enunciado por *hash*, nunca pelo texto) e as
estatísticas.

### 2.7 `CLAUDE.md`, `task.md` e `LESSONS.md` vão junto

Mostram o método: o roteiro por etapas, as regras e anti-padrões, os post-mortems. Para
a vaga de mapeamento e documentação de processos que motivou a Etapa 10, isso vale mais
que o código. Vão sem o e-mail pessoal (§2.2).

### 2.8 O README abre pela apresentação

O README anterior começava pelo `cd /home/athos/homelab/scraper_cebraspe` e gastava as
primeiras 60 linhas em instalação, com uma lista de funcionalidades que havia parado no
ADR-022. O novo abre pelo problema, mostra um de-para real lido do banco, os números, o
diagrama do pipeline e o que o repositório demonstra; a instalação vem depois. O que era
lista de funcionalidades virou link para a documentação, que fica em dia sozinha.

### 2.9 O monorepo continua sendo a fonte

O trabalho continua em `athosroque/Homelab`. A publicação é um `subtree split` seguido
de push para o repositório público — nunca o contrário. Isso evita manter dois checkouts
em sincronia à mão, e aceita de propósito que o repositório público ande atrás do
privado entre publicações.

## 3. Alternativas descartadas

- **Commit inicial único.** Seguro e rápido, mas joga fora 256 mensagens de commit que
  são evidência de método (§2.2).
- **`git filter-repo`.** Mais poderoso, com reescrita fina de autor, caminho e conteúdo.
  Não está instalado e não é necessário: `subtree split` resolve a extração de um
  subdiretório.
- **Mover o projeto de vez para fora do monorepo.** Quebraria a convenção de descoberta
  do portfólio (`CLAUDE.md` por subdiretório) e os caminhos relativos dos agentes.
- **Abrir `docs.projetoathos.com.br` ao público.** Expõe o servidor doméstico e o
  Traefik para ganhar o que o Pages dá de graça, com CDN e sem manutenção.
- **Publicar só o PDF executivo no repositório.** Resolve o link, mas deixa 97 páginas,
  os ADRs e as páginas geradas fora da vitrine.
- **`mkdocs gh-deploy` com branch `gh-pages`.** Mais simples, porém commita HTML
  construído no histórico do repositório e não roda em CI com permissões mínimas. O Pages
  por Actions publica um artefato, sem sujar o histórico.
- **Deixar o README do perfil como estava.** O perfil é a primeira página que um
  recrutador abre, e nenhum dos projetos listados nele comunica processo ou governança
  documentada — exatamente o que este projeto tem a mostrar.

## 4. Consequências

**Positivas**

- A documentação ganha endereço público, com HTTPS e CDN, sem expor o servidor.
- O histórico, os ADRs e o roteiro por etapas ficam legíveis por quem avalia o
  portfólio.
- O build publicado é o mesmo que o `make check` já exige, em `--strict`: documentação
  quebrada não chega ao ar.
- O repositório público não depende de banco nem de chave de API para construir o site.

**Negativas e custos**

- Duas publicações do mesmo build (Pages e nginx) podem divergir entre um push e outro.
  Mitigação: ambas saem do mesmo `mkdocs build`, e o Pages é atualizado no push.
- O repositório público fica atrás do privado entre publicações, por desenho (§2.9).
- Publicação de histórico é irreversível na prática: um `git push --force` depois não
  apaga o que foi clonado ou indexado. Daí a varredura antes, e não depois.
- O `subtree split` reescreve os hashes, então os commits do repositório público não
  batem com os do monorepo. As mensagens, as datas e o autor, sim.
