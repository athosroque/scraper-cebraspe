# Contrato de Documentação — Guia Técnico

> Este arquivo define o contrato de escrita para todas as páginas manuais em `docs/guia/`.
> Qualquer tarefa que produza ou edite páginas deste guia deve seguir rigorosamente estas diretrizes.

---

## 1. Princípios Fundamentais

1. **Só leitura no código:** A página descreve fielmente o que o código faz hoje, sem especulação ou abstrações inventadas.
2. **Evidência por parágrafo (`Fonte:`):** Todo parágrafo que afirme um fato técnico, regra de negócio, comportamento ou estrutura deve terminar com `Fonte: caminho/do/arquivo:linha` (ou faixa de linhas).
3. **Números canônicos linkados:** Nenhum número de contagem (ex.: total de questões, editais, cadernos, acertos) deve ser fixado diretamente em texto se existir em `docs/executivo/numeros.md`. Em vez disso, crie um link relativo para `[docs/executivo/numeros.md](../executivo/numeros.md)`.
4. **Sem duplicação de regras ou ADRs:** Quando uma regra de negócio ou decisão for relevante, insira o link correspondente para a regra em `[docs/tecnico/regras.md](../tecnico/regras.md#id)` ou para o ADR em `[docs/adr/](../adr/ADR-xxx.md)`, sem copiar blocos de texto.
5. **Idioma e estilo:** Português do Brasil com acentuação correta, frases diretas, seções curtas e vocabulário técnico preciso.

---

## 2. Arquivos Estritamente Proibidos

As tarefas de escrita das páginas do guia **NÃO PODEM** editar nenhum dos seguintes arquivos:
- `mkdocs.yml` (gerenciado pela coordenação na Onda 0 e Onda 3);
- `docs/tecnico/*` (gerado automaticamente pelo registro — Regra A62);
- `src/registro/*` (código-fonte do registro técnico);
- `CLAUDE.md`;
- `docs/adr/*` (decisões de arquitetura históricas/imutáveis).

Cada tarefa da Onda 1 opera em isolamento e escreve exclusivamente nas páginas designadas.

---

## 3. Modelo Canônico de Página

Toda página em `docs/guia/` deve seguir a seguinte estrutura:

```markdown
# [Título Claro e Descritivo]

[Resumo em um parágrafo conciso explicando o objetivo e o escopo da página.]

**Para que serve:** [Descrição direta do objetivo da página]. **Quando ler:** [Momento específico em que um agente ou desenvolvedor deve consultar esta página].

## [Seção 1: Visão Geral / Mecanismo Principal]

Texto explicativo objetivo com as operações e contratos reais do código.
Fonte: src/exemplo.py:45

## [Seção 2: Detalhes Técnicos / Fluxo]

Detalhamento de parâmetros, rotas, regras e fluxos.
Fonte: src/outro.py:120-135

## Referências e Regras Relacionadas

- Regra relacionada: [P51 - Nome da Regra](../tecnico/regras.md#p51)
- Decisão de arquitetura: [ADR-030 - Nome da Decisão](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
```

---

## 4. Checklist de Aceite

- [ ] "Para que serve" e "Quando ler" presentes no topo.
- [ ] Todo parágrafo que descreve lógica possui citação `Fonte: ...`.
- [ ] Nenhuma duplicação de ADRs ou regras registradas (apenas links).
- [ ] Nenhum arquivo proibido foi tocado.
- [ ] Rodapé com "Verificado em [data] contra commit [hash]" presente.
