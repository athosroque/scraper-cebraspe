# Plano: conteúdo do guia técnico (documentação)

Criado em 2026-10-21. Complementa a Etapa 9 (`plano-etapa-9.md`): D1 a D4 entregaram a
estrutura do site MkDocs, as páginas geradas de `docs/tecnico/` e a visão executiva. Este
plano preenche o que ainda falta no **guia** (`docs/guia/`), escrito à mão.

> Ao abrir uma sessão, ler só este arquivo e a onda dela.

## Lacunas

| # | Lacuna | Hoje | Fonte no código |
|---|---|---|---|
| 1 | Site público (API, frontend, contas, simulado) | só ADR-033/034/035 e `site/openapi.json` | `site/app/`, `site/openapi.json` |
| 2 | Árvore mestre e curadoria, do ponto de vista do dono | só P51 e A27–A29 em regras | `src/arvore.py`, `scripts/curar_arvore.py` |
| 3 | Extração por LLM e observabilidade | espalhada nos ADR-009 a 025 | `src/` (parser, extractor), Langfuse |
| 4 | Revisão humana e portões (Datasette) | trecho no `CLAUDE.md` §9.2 | `scripts/atualizar_revisao.py` |
| 5 | Coleta (crawler, downloader, inventário) | `docs/architecture.md` | `src/spider.py`, `src/downloader.py`, `inventario/` |
| 6 | `docs/architecture.md` provavelmente desatualizado | cita `postgres_fdw`, que o ADR-026 não prevê | a conferir |
| 7 | Glossário e página "começando" | não existem | derivado das páginas acima |

Fora desta rodada: Dagster. Documentar código que ainda não existe (D5a/D5b) gera texto
errado; a página dele entra depois que a D5b fechar.

## Princípios de delegação

- **Arquivos disjuntos.** Cada tarefa escreve só nas suas páginas novas. Ninguém toca em
  `mkdocs.yml`, `docs/tecnico/` (regra A62), `CLAUDE.md`, ADRs ou `src/registro/`.
- **Só leitura no código.** A página descreve o que o código faz, sem inventar. Todo
  parágrafo termina com `Fonte: caminho:linha`. Número que existe em
  `docs/executivo/numeros.md` é linkado, não copiado.
- **Contrato de página**, igual ao dos índices: "Para que serve / Quando ler", seções
  curtas, link para a regra ou o ADR em vez de repetir o texto. Português do Brasil, com
  acentos.
- **Integração e verificação ficam com o responsável pela sessão principal:** nav,
  conferência de fatos, build e commit.

## Fluxo

```
Onda 0              Onda 1 (6 tarefas em paralelo)            Onda 2 (2 tarefas)      Onda 3
contrato + stubs -> T1 site    T2 árvore   T3 LLM          -> T7 glossário         -> nav, build,
nav no mkdocs.yml   T4 revisão T5 coleta   T6 auditoria       T8 "começando"          conferência, commit
```

## Onda 0: contrato e esqueleto (sessão principal, sem delegar)

- Escrever `docs/guia/_contrato.md` (fora do `nav`) com o modelo de página, a regra de
  `Fonte:` e a lista de arquivos proibidos.
- Criar as páginas vazias e ligá-las ao `nav` do `mkdocs.yml` e aos índices de `docs/guia/`:
  `guia/site.md`, `guia/api.md`, `guia/arvore.md`, `guia/extracao-llm.md`,
  `guia/revisao-humana.md`, `guia/coleta.md`, `guia/glossario.md`, `guia/comecando.md`.
  Com isso o `mkdocs build --strict` já fica verde e cada tarefa só preenche o seu arquivo.
- Pronto quando: `make docs-build` passa com as páginas vazias.

## Onda 1: páginas por assunto (paralelo, uma tarefa por grupo de arquivos)

| Tarefa | Escreve | Lê | Conteúdo |
|---|---|---|---|
| T1 | `guia/site.md`, `guia/api.md` | `site/app/`, `site/openapi.json`, ADR-033/034/035 | rotas, contas Google e histórico, simulado com correção CEBRASPE, estatísticas |
| T2 | `guia/arvore.md` | `src/arvore.py`, `scripts/curar_arvore.py`, ADR-029/030, regras P51 e A27–A29 | modelo nó → assunto → subassunto, ciclo semear → propor → curar, o que nunca fazer |
| T3 | `guia/extracao-llm.md` | `src/` (parser e extractor), ADR-009 a 025 | recorte, chunking, chamada ao OpenRouter, retry, trilha de auditoria, o que aparece no Langfuse |
| T4 | `guia/revisao-humana.md` | `scripts/atualizar_revisao.py`, `CLAUDE.md` §9.2, ADR-015/018/019 | Datasette, relatório por edital, `status_revisao_humana`, quais portões travam o quê |
| T5 | `guia/coleta.md` | `src/spider.py`, `src/downloader.py`, `inventario/`, ADR-001 a 008, 037 | crawler, dedup em duas camadas, inventário, `exclusoes.json` |
| T6 | nenhum arquivo do site | `docs/architecture.md` e o código que ele cita | **auditoria, sem editar:** tabela com a frase, o motivo de estar errada e a fonte |

- Pronto quando: as 5 páginas têm `Fonte:` em todo parágrafo e a tabela da T6 está entregue.
- Revisão antes da onda 2: a sessão principal abre 3 afirmações de cada página e compara com
  o código; página reprovada volta à tarefa com a correção. A tabela da T6 é aplicada à mão
  em `docs/architecture.md`.

## Onda 2: páginas que dependem da onda 1 (paralelo, depois da revisão)

| Tarefa | Escreve | Lê | Conteúdo |
|---|---|---|---|
| T7 | `guia/glossario.md` | páginas aprovadas da onda 1 | matéria, assunto, subassunto, portão, partição, piloto, ME, caderno |
| T8 | `guia/comecando.md` | páginas aprovadas da onda 1 e os índices de `guia/` | caminho de leitura por perfil (dono, agente, visitante executivo), só com links |

## Onda 3: integração e verificação (sessão principal)

- `make docs-build` (`--strict`), `make docs-gerar` com `--verificar` e a suíte de
  `tests/test_registro.py` (o teste guarda de `tarefas.md` exige que as páginas citadas
  existam).
- Script curto que confere que todo `Fonte:` aponta para um arquivo existente.
- Conferência por amostragem (3 afirmações por página) e reescrita das páginas que falharem
  duas vezes.
- Um commit por onda, `docs(scraper-cebraspe): …`. Publicação automática pelos hooks
  (`make hooks-instalar`), sem passo manual.
- Pronto quando: o site abre com as 8 páginas novas, o `--strict` passa e nenhuma afirmação
  amostrada contradiz o código.

## Trade-offs

- **Delegar** é mais barato e paraleliza, mas erra detalhe. A regra de `Fonte:` e a
  amostragem existem por isso.
- **Seis tarefas de uma vez** aceleram, mas o `mkdocs.yml` seria gargalo; por isso o nav sai
  pronto na onda 0.
- **Páginas escritas à mão ficam desatualizadas** quando o código muda. Mitigação: linha
  "Verificado em <data> contra <commit>" em cada página e links para as regras geradas, em
  vez de cópia. Se a lacuna continuar crescendo, o passo seguinte é gerar essas páginas do
  registro, como já é feito com `docs/tecnico/`.

## Decisões em aberto

1. Incluir um guia de uso do site para o público (leitor final, não quem mantém o projeto)?
2. Página do Dagster: entra como onda 4, depois da D5b.
3. Registrar como D6 no `plano-etapa-9.md` e abrir card no Jira (o MCP do Atlassian falhou
   ao conectar em 2026-10-21).
