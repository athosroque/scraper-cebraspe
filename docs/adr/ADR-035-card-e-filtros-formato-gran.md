# ADR-035: Card da Questão e Filtros no Formato Gran, em Teal (Etapa 5H)

## Status
Aceito (Etapa 5H concluída e validada no Chromium headless em 2026-10-06;
revisão do painel 5H.3 em 2026-10-07)

## Data
2026-10-06

## Contexto

Com a 5G (ADR-034) o site já tinha filtros multisseleção e o comando do grupo
no topo do card. O dono pediu o card e o painel de filtros no formato do Gran
Questões (prints de 2026-10-06), trocando o laranja do Gran por **teal**. O
card era um bloco único com botões Certo/Errado de um clique, e os filtros
ficavam numa barra lateral de `<details>` que buscava a cada checkbox. O
`questao_id` do banco muda a cada recarga, então não servia como ID visível.
Plano completo em `docs/planos/plano-etapa-5h.md`.

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
   questões" (anuladas, fora do edital — removido em 2026-10-07 —, já resolvidas) e "Questões com"
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

### Revisão do painel (5H.3, 2026-10-07)

Pedido do dono depois da validação da 5H:

- **"Disciplina" no lugar de "Matéria"** em todo texto visível do site
  (painel, chips, card, home, menu, painel da disciplina, estatísticas,
  edital × prova, conta, simulado, 404). Identificadores, a rota
  `/materias/{id}`, parâmetros e campos da API ficam como estavam. (As
  descrições do OpenAPI e a tag "Matérias" mudaram depois, ver "API igual ao
  site" abaixo.)
- **Cascata Disciplina → Assunto → Subassunto.** Assunto fica desabilitado
  ("Requer disciplina") sem disciplina marcada, e Subassunto sem assunto. As
  opções vêm só dos pais marcados: o servidor manda assim (o JSON das
  facetas leva o `pai` de cada nó, sem o caminho, o que também encolhe a
  página) e o Alpine filtra de novo entre a marcação e a recontagem
  ("Atualizando…" enquanto ela não chega). Desmarcar o pai (dropdown ou × do
  chip) poda os filhos no store; o chip do `<noscript>` tira o nó e os filhos
  marcados dele.
- **Seleção coerente no servidor** (`questoes_servico.coerir_nos`, usada por
  `/questoes` e `/questoes/facetas`): assunto de outra disciplina, quando há
  disciplina marcada, é órfão e **é ignorado**; idem subassunto. Sem nada
  marcado no nível de cima, o filho é link direto e **ganha os pais**. Motivo:
  os links do card, da estatística e do painel da disciplina trazem só o
  nó (`?no_id=<subassunto>`); descartá-los quebraria esses links, e
  completá-los mostra a cadeia marcada com o mesmo resultado de antes. Já o
  órfão com disciplina marcada só nasce de URL editada ou desatualizada, e o
  painel nunca o mandaria (podaria ao desmarcar).
- **No mesmo ramo vale o mais específico** (`refinar_por_ramo`):
  disciplina + assunto dela = só o assunto; disciplina sem assunto marcado
  vale inteira. Sem isso a cascata não serviria para nada, porque o `no_id` é
  OU e a disciplina engoliria o assunto. Na primeira entrega (commit
  `025d893`) só o site refinava, e a API ficava em OU puro (contrato da
  5F.1), então a mesma URL dava totais diferentes.
- **API igual ao site** (decisão do dono, 2026-10-07). A coerência e o refino
  viraram o padrão do serviço (`questoes_servico.nos_da_consulta` =
  `refinar_por_ramo(coerir_nos(...))`, aplicado em `filtros_para_repo`), e a
  opção `refinar_ramos` saiu. Valem para todo endpoint que aceita `no_id`:
  `/api/v1/questoes`, `/api/v1/facetas` e `/api/v1/eu/desempenho` (este
  aceita um nó só, então na prática não muda), além das rotas HTML. A regra
  está na descrição do parâmetro `no_id` no OpenAPI (`D_FILTRO_NO_ID`). Nas
  facetas, o nó marcado continua entre as opções mesmo quando o refino o tira
  da consulta. `coerir_nos` é idempotente: o site já coere a seleção para os
  chips, e o serviço aplica de novo sem mudar nada. Os outros endpoints não
  recebem `no_id` (`/estatisticas/*` usa `materia_id`, `/busca` usa `q`,
  `/questoes/{chave}/parecidas` usa o nó principal da questão, e as questões
  do simulado vêm por chave). Teste: `test_site_e_api_dao_o_mesmo_total` e
  `test_exemplo_do_dono_igual_no_site_e_na_api` (LP + "Domínio da estrutura
  morfossintática do período" + Direito Administrativo = 205 nos dois).
  Na mesma decisão, as descrições, a tag ("Disciplinas") e as mensagens
  `detail` da API passaram a dizer "disciplina" ("Disciplina não
  encontrada"); identificadores, paths, parâmetros e campos (`materia_id`,
  `/materias`, `materias`) ficam como estavam.
- **Sem redundância nas caixas.** Conferido no Chromium antes da mudança:
  cada opção de Assunto repetia o próprio nome numa 2ª linha com o caminho
  inteiro (ex.: "Domínio da estrutura morfossintática do período" e, abaixo,
  "LÍNGUA PORTUGUESA › Domínio da estrutura morfossintática do período"), e o
  Subassunto repetia disciplina, assunto e o próprio nome; os chips também
  usavam o caminho. Agora a opção mostra só o nome e o total; com 2+ pais
  marcados, as opções ficam sob um cabeçalho com o nome do pai (com o avô
  entre parênteses só se dois pais tiverem o mesmo nome). Chip:
  "Disciplina: X", "Assunto: Y", com o pai entre parênteses só em homônimos.
  O Cargo mantém o concurso na 2ª linha (não é repetição).
- **Filtro avançado aberto por padrão.** Sem preferência salva abre
  avançado; "Mostrar filtro simples" grava `0` no `localStorage` e só então
  esconde. Sem JS a linha avançada aparece (o `x-show` não age).
- **Foco ao marcar.** Achado na validação, anterior a esta revisão: marcar um
  item que sobe para o topo (o `x-for` move o nó) jogava o foco no `body`, e
  Esc/Tab deixavam o painel. O `marcar` devolve o foco ao checkbox.
- **"Fora do edital" saiu do site** (decisão do dono, 2026-10-07): a banca
  não pode cobrar nada fora do edital e só cobra o que está nos assuntos dele,
  então a informação não tem valor. Saíram o checkbox "Excluir: fora do
  edital" e o chip, o parâmetro `fora_do_edital` das rotas HTML, de
  `/api/v1/questoes`, `/api/v1/facetas` e `/api/v1/eu/desempenho`, o campo
  `fora_do_edital` dos nós da questão e a situação `cobrado_fora_do_edital`
  de `/estatisticas/edital-vs-prova` e `/api/v1/estatisticas/edital-vs-prova`
  (fica "Cobrado e previsto" e "Previsto e nunca cobrado").
  `site/openapi.json` foi refeito. Link antigo com o parâmetro é **ignorado
  em silêncio** (200, mesmo total, sem chip; a paginação não o propaga). O
  banco, `src/`, `scripts/` e `canonico/` não mudaram: `fora_do_edital` da 5D
  e a situação na `vw_edital_vs_prova` ficam como histórico.

## Consequências

- Filtrar 2 matérias + órgão + "excluir anuladas" + palavra-chave só busca no
  Filtrar e bate com a API/SQL (testes `test_filtros_painel.py`,
  `test_filtros_texto.py`, `test_filtros_multi.py`).
- Validação no Chromium headless (1280 e 390 px): dropdown abre, busca e
  marca; fechar reconta (1 requisição a `/questoes/facetas`, lista
  inalterada); Filtrar aplica (PF: 1.131; + excluir anuladas: 1.092); voltar
  do navegador restaura total e checkboxes; ID curto na palavra-chave abre a
  questão; sem rolagem horizontal e sem erro de JS.
- ~~A base do piloto não tem questão marcada `fora_do_edital` (5D), então
  "Excluir: fora do edital" hoje não tira nada.~~ Controle removido na
  revisão de 2026-10-07 (ver acima).
- Revisão 5H.3 validada no Chromium headless (1280 e 390 px): Assunto e
  Subassunto desabilitados no início; LÍNGUA PORTUGUESA + DIREITO
  ADMINISTRATIVO agrupam os assuntos sob os 2 nomes; subassunto só do
  assunto marcado; desmarcar a disciplina poda assunto e subassunto (chips
  inclusive); Filtrar com LP › "Domínio da estrutura morfossintática do
  período" + DIREITO ADMINISTRATIVO dá 205 (= 63 + 142); voltar do
  navegador restaura 205 e a seleção; sem rolagem horizontal e sem erro de
  JS. Desde o alinhamento da API (2026-10-07), a mesma URL em
  `/api/v1/questoes` também dá 205.
- Remover um chip não aplica na hora (só no Filtrar), coerente com a regra do
  botão; diferente da 5G, em que cada mudança buscava.

## Alternativas descartadas

- Manter a busca a cada `change` (5G): uma requisição pesada por clique, e o
  Gran aplica só no botão.
- Usar `questao_id` como ID visível: muda a cada recarga.
- Recontar devolvendo o fragmento inteiro da lista: troca cards que o usuário
  ainda não pediu para trocar.
- Biblioteca de dropdown/ícones: Alpine + SVG inline bastam.
