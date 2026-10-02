# Correções da interface web (pós-teste em questoes-dev)

Origem: teste manual como visitante em `questoes-dev` (2026-10-02), gerado por IA
e conferido contra o código. Cada sessão abaixo é autocontida: rodar uma por
conversa. Os 4 bugs e o formato de números vêm antes do deploy (5F.12).

Regras valem em todas as sessões: pt-BR, testes no `site/`, `ruff` verde, rodar
`python site/scripts/exportar_openapi.py` se mexer em rota/modelo da API, commit
Conventional por sessão. Dado da árvore só muda via `scripts/curar_arvore.py`
(nunca no template, nunca `UPDATE` no banco).

## Sessão 1 — Bugs de rota e estados vazios

- [x] **Paginação além do fim.** `site/app/web/rotas_web.py` (~l.132): limitar
  `pagina` a `total_paginas` (redirecionar 307 para a URL com a última página,
  mantendo a query). Lista vazia real continua página 1 de 1.
  No template `_lista_parcial.html` (l.51) o "Anterior" só aparece se
  `pagina > 1` e `pagina <= total_paginas`.
- [x] **404 com texto genérico.** `nao_encontrada.html` aceita `titulo` e
  `mensagem` por contexto; `_nao_encontrada(request, titulo=..., mensagem=...)`.
  Questão: "Questão não encontrada"; matéria: "Matéria não encontrada".
- [x] **404 de rota inexistente em HTML.** `exception_handler(StarletteHTTPException)`
  em `main.py`: se o path começa com `/api/` ou `Accept` não aceita HTML,
  devolve o JSON padrão; senão devolve `nao_encontrada.html` (título "Página
  não encontrada") com status 404. 405 segue o mesmo critério.
- [x] **Busca de matérias sem resultado.** `inicio.html`: contar itens visíveis
  no Alpine e mostrar "Nenhuma matéria encontrada para «…»" com botão limpar.
- Testes: `pagina=999` redireciona; `/materias/XYZ` com texto de matéria;
  `/nao-existe` HTML com layout; `/api/v1/nao-existe` continua JSON.
- Pronto quando: os 4 casos manuais do relatório se comportam como acima.

## Sessão 2 — Rótulos e formatação (determinístico)

- [x] **Filtro Jinja `num`/`pct`** em `rotas_web.py` (`templates.env.filters`):
  milhar com ponto e decimal com vírgula (`2.532`, `10,46%`). Aplicar em todos
  os templates (`grep -rn "pct\|total" templates`), inclusive "Universo: …".
- [x] **Rótulo de nível com acento.** `lista_questoes.html:89` usa
  `n.rotulo|title` sobre `medio`. Mapa único `ROTULO_NIVEL` (`superior` →
  "Superior", `medio` → "Médio") em um módulo do `servicos/`, usado por
  filtros, cards e simulado. `questoes_servico.py:175` hoje faz `str(valor)`.
- [x] **Rótulo de concurso legível.** Mapa `slug → "CD 2025 — Nível Superior"`
  (derivado de órgão/ano; fallback no slug) para filtros, simulado e card, no
  mesmo estilo em todo lugar.
- [x] **Ordem dos filtros.** Cargo por número crescente; concurso por órgão e
  ano; nível Superior antes de Médio.
- [x] **Aba inicial de "Meu concurso".** Hoje abre "O que mais cai" mas a
  primeira aba é "Edital × prova": alinhar a ordem das abas
  (`_abas_estatistica.html`) com a rota padrão.
- [x] **Matérias que são cargo.** Listas e filtro de matéria usam o rótulo
  `Conhecimentos específicos — <cargo>` quando `nome_de_cargo = true`
  (mesma regra da `vw_peso_materia_cargo`).
- [x] **Árvore de assuntos** ordenada por quantidade desc., depois nome.
- Testes: unitários dos filtros e do mapa; ordem das opções.

## Sessão 3 — Coerência dos números do painel de matéria

Diagnóstico: os números não estão errados, mas cada um conta uma coisa.
178 = linhas da matéria; "No recorte" = `fn_prova_cobra` (desduplica
enunciados repetidos, ADR-032); o ranking mostra só os 15 maiores subassuntos
e ignora questão classificada direto no assunto; a home usa 2.781 (com
anuladas e duplicatas) e o painel 2.532 (válidas desduplicadas).

- [x] Decidir e documentar a base única do `%`: recomendada **válidas
  desduplicadas** (`fn_prova_cobra`) em home e painel. Atualizar a home.
- [x] Rotular cada número no painel: "Questões da matéria", "Distintas no
  recorte", "Anuladas", "Universo de comparação", com tooltip curto.
- [x] Ranking "O que mais cai": linha final "Outros / direto no assunto" e
  "mostrando N de M" para fechar a soma, sem mudar a regra da 5E.
- [x] Teste de reconciliação: soma do ranking + "outros" = recorte para LP.
- [x] Registrar a decisão em ADR-033 (nota) e no log do `CLAUDE.md`.

## Sessão 4 — Curadoria da árvore (dado, com o dono)

Só via `scripts/curar_arvore.py`; propostas do agente, decisão do dono.

- [x] **Caixa e acentos:** `--renomear` para "NOÇOES"→"NOÇÕES", assuntos em
  minúscula, Title Case × CAIXA ALTA (definir padrão único de exibição;
  preferir normalizar na exibição com função única e corrigir só erro de
  ortografia no dado).
- [x] **Matérias sobrepostas:** TI (3 variantes), Raciocínio Lógico (2),
  Contabilidade (3), Direito Penal (3). Listar candidatos com os itens de edital
  de cada um; fundir só o que o dono aprovar (cuidado: não juntar nome composto
  a uma de suas partes, ADR-030).
- [x] **Assuntos quase idênticos:** "Despesa(s) de exercícios anteriores" (3) e
  pares do ranking ("Atos de improbidade" × "Lei 8.429/1992"). Usar
  `--fundir`; rodar `atualizar_revisao` para recarregar o banco e as views.
- [x] Reconferir: `5D × 5E` sem divergência, contagens de nós no `arvore.html`.

## Sessão 5 — SEO, acessibilidade e UX (menor risco)

- [x] `base.html`: favicon, `<link rel="canonical">`, Open Graph/Twitter por
  página (título, descrição; questão usa o enunciado truncado).
- [x] Link "Pular para o conteúdo" e `aria-label` nos campos sem label.
- [x] "Parecidas": reproduzir a requisição dupla no navegador (suspeita:
  `toggle` do `<details>` aninhado) e corrigir; resultados sem truncar em "…".
- [x] Feedback da resposta em "Certo/Errado" em vez de C/E; botão "Tentar de
  novo" na correção anônima.
- [x] Convite ao login já na primeira resposta; contador de acertos da sessão
  no cabeçalho (Alpine + `localStorage`, só anônimo).
- [x] Texto-base repetido: aviso "mesmo texto da questão anterior" na lista.
- [x] Confirmar com o dono o e-mail do "Sobre" (`athosroque@hotmail.com`, é o
  contato do portfólio) — sem mudança de código se for intencional.

## Sessão 6 — Revalidação ao vivo

- [x] Cobrir o que o teste original não cobriu: login Google, simulado completo,
  abas "Edital × prova" e "O que o edital cobra", layout mobile (Chromium
  headless com viewport real). Repetir os itens do relatório e conferir o
  console sem erro. Só então liberar a 5F.12.
