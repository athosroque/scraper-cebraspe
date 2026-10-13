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
