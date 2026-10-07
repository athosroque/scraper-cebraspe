# ADR-035: Card da Questão e Filtros no Formato Gran, em Teal (Etapa 5H)

## Status
Aceito (Etapa 5H concluída e validada no Chromium headless em 2026-10-06)

## Data
2026-10-06

## Contexto

Com a 5G (ADR-034) o site já tinha filtros multisseleção e o comando do grupo
no topo do card. O dono pediu o card e o painel de filtros no formato do Gran
Questões (prints de 2026-10-06), trocando o laranja do Gran por **teal**. O
card era um bloco único com botões Certo/Errado de um clique, e os filtros
ficavam numa barra lateral de `<details>` que buscava a cada checkbox. O
`questao_id` do banco muda a cada recarga, então não servia como ID visível.
Plano completo em `plano-etapa-5h.md`.

## Decisão

1. **Cor `destaque` (teal)** como token em `site/tailwind.config.js`, usada no
   site inteiro. Nenhum `*-blue-*` sobra nos templates; o CSS versionado é
   refeito por `site/scripts/gerar_css.sh` (teste `test_tailwind.py`).
2. **ID curto estável**: `Q` + 8 hex maiúsculos do SHA-1 de
   `concurso|caderno|numero` (`formatacao.codigo_curto`), campo `codigo` em
   `QuestaoResumo`. `/q/{codigo}` responde 301 para a URL canônica; há teste
   de colisão sobre todas as chaves.
3. **Card novo** (`_card_questao.html`): barra cinza (posição · ID · matéria ▸
   assunto), linha Ano/Banca/Órgão/Prova com links de filtro, "Texto
   associado ⊕" sob demanda, radios Certo/Errado + Responder (macro
   `form_resposta`, também no "Tentar de novo"), barra de ações e "Fonte:
   CEBRASPE". Responder sem marcar devolve fragmento amigável, não 422.
4. **Filtros no topo** (`lista_questoes.html`): palavra-chave, dropdowns com
   busca rápida (Matéria, Assunto, Subassunto, Banca, Órgão; no modo avançado
   também Ano, Concurso, Cargo, Nível, Conhecimento), linhas "Excluir
   questões" (anuladas, fora do edital, já resolvidas) e "Questões com"
   (texto associado, figuras, que errei) e a barra "Filtrar por:" com chips.
   O estado pendente vive num `Alpine.store`; o `<form>` tem
   `hx-trigger="submit"` e **só busca no botão Filtrar**. Marcar e fechar um
   dropdown dispara a recontagem em `GET /questoes/facetas`, que devolve só
   o `#dados-facetas` (OOB, `hx-swap="none"`), sem tocar a lista. A
   preferência simples/avançado fica no `localStorage` (com `try/catch`), e o
   avançado abre sozinho quando há filtro avançado ativo.
5. **Chips fora do fragmento da lista.** Com JS, os chips saem do store (o ×
   desmarca e reconta, e vale no próximo Filtrar). Sem JS, um `<noscript>`
   na página inteira traz os chips do servidor, cada um com o link sem aquele
   valor. O fragmento da lista leva só o total, os cards e as facetas (OOB).
6. **Filtros novos no backend** (5H.4): `texto` (palavra-chave com
   `unaccent`, palavras em E, curinga tratado como literal) e `com`
   (`texto_base`, `figuras`) na API, nas facetas e no `openapi.json`. Termo
   igual a um ID curto existente abre a questão: `HX-Redirect` no submit
   HTMX, 303 sem HTMX. Os filtros da query são lidos por uma dependência
   única (`_filtros_da_query`), usada por `/questoes` e `/questoes/facetas`.

### Desvios do plano

- A caixa do ID curto ficou em **slate-500** (não no cinza mais claro do
  print), por contraste do texto branco (WCAG AA).
- O nó **secundário** na barra cinza mostra só o trecho do caminho que difere
  do principal (ex.: `, Gestão de pessoas` em vez de repetir a matéria).
- "Questões parecidas" **quebra em 2 linhas** no celular (390 px) na barra de
  ações em 2 colunas; aceito, sem rolagem horizontal.
- Os chips **saíram do fragmento da lista** (item 5): o plano não dizia onde
  ficariam; os testes antigos que liam o chip no fragmento passaram a ler a
  página inteira (`<noscript>`) e o nome nas facetas OOB.

## Consequências

- Filtrar 2 matérias + órgão + "excluir anuladas" + palavra-chave só busca no
  Filtrar e bate com a API/SQL (testes `test_filtros_painel.py`,
  `test_filtros_texto.py`, `test_filtros_multi.py`).
- Validação no Chromium headless (1280 e 390 px): dropdown abre, busca e
  marca; fechar reconta (1 requisição a `/questoes/facetas`, lista
  inalterada); Filtrar aplica (PF: 1.131; + excluir anuladas: 1.092); voltar
  do navegador restaura total e checkboxes; ID curto na palavra-chave abre a
  questão; sem rolagem horizontal e sem erro de JS.
- A base do piloto não tem questão marcada `fora_do_edital` (5D), então
  "Excluir: fora do edital" hoje não tira nada; o controle fica para quando
  houver.
- Remover um chip não aplica na hora (só no Filtrar), coerente com a regra do
  botão; diferente da 5G, em que cada mudança buscava.

## Alternativas descartadas

- Manter a busca a cada `change` (5G): uma requisição pesada por clique, e o
  Gran aplica só no botão.
- Usar `questao_id` como ID visível: muda a cada recarga.
- Recontar devolvendo o fragmento inteiro da lista: troca cards que o usuário
  ainda não pediu para trocar.
- Biblioteca de dropdown/ícones: Alpine + SVG inline bastam.
