# Prompt de correção: Dagster D5b (KAN-32), devolução da rodada 2

Criado em 2026-10-21. Para o agente que entregou a D5b (`prompt-dagster-d5.md`, "Rodada 2").
A D5b está sem commit no checkout principal (`master`); a D5a já está commitada (`c3a6eb9`).

---

# Tarefa: corrigir a D5b e devolver para nova validação

Trabalhe em /home/athos/homelab/scraper_cebraspe, no checkout onde a D5b está (sem commit).
Leia só este arquivo, `src/c2/checks.py`, `src/c2/relatorio.py`, `src/c2/assets.py`,
`scripts/executar_c2.py`, `tests/test_c2_checks_relatorio.py`, `docs/runbook-lote.md` (§4.5),
`docs/tecnico/checagens.md` e `docs/tecnico/banco.md`. Responda em português do Brasil, com
acentos.

A validação encontrou que o K22 (invariante do piloto), o portão P3, o `--so-chunking` e os
testes estão corretos (69 testes verdes, `ruff` e `gerar_docs --verificar` limpos). O defeito é
que **o relatório do lote produz falsos verdes por construção**. O critério da D5b é "o relatório
do lote da C1 sai com as checagens verdes", e isso só vale se as checagens forem calculadas.

## 1. Obrigatório: nada de status fixo no relatório

Em `scripts/executar_c2.py` (bloco "Consolidação e geração do relatório do lote"), o dicionário
`checks_resultado` traz `download`, `edital`, `banco`, `classificacao` e `site` com
`"status": "ok"` escrito à mão. Em `src/c2/relatorio.py` a linha "Site" usa `_badge('OK')` fixo,
e a linha "Classificação" começa com o texto "Todos os itens classificados e curados" quando
nenhum dado do portão chega. `propostas_dispersao=[]` também é fixo.

Faça cada camada vir de um cálculo, com o que ela mediu:

- **Download:** PDFs do lote no disco (manifesto, `%PDF-`) contra a contagem do inventário.
- **Edital:** resultado do portão P3 de cada concurso (aprovado, pendente ou sem edital).
- **Prova:** fila `concluido`, itens == gabarito, gabarito dentro da grade e alternativas
  (consultas do runbook).
- **Banco:** K22 antes e depois, mais as contagens do lote (provas, questões, discursivas).
- **Classificação:** por concurso, quantas questões têm ao menos um apontamento aprovado, em
  `N de M`. Defina "classificada" a partir de `docs/tecnico/banco.md` e das checagens K do
  registro, e escreva a definição no código.
- **Site:** se não houver uma verificação real, o status é `NAO_VERIFICADO` (neutro, nunca
  `OK`). Uma verificação real aceitável: as questões do lote aparecem em `vw_questoes` com o
  mesmo total das provas. Escolha uma e justifique.
- **Dispersão:** as propostas que o P6 gerou de fato, vindas do asset, e não `[]`.

Proibido deixar qualquer camada com `ok` literal ou com texto de sucesso como valor padrão. Se
o dado não chegou, o status é `NAO_VERIFICADO`.

## 2. Obrigatório: o portão P9 precisa enxergar o que falta classificar

`verificar_portao_classificacao` só conta apontamentos com `status='proposto'`. Um concurso com
**zero** apontamentos tem "zero pendências" e passa. Hoje isso acontece com a C1: 610 questões,
0 classificadas (conferido no banco).

- O portão passa a contar também as questões do lote **sem nenhum apontamento aprovado**.
  Devolva `(aprovado, n_pendentes)` com as duas parcelas separadas (propostas a aprovar e
  questões sem classificação), para o relatório poder dizer qual é qual.
- Teste: concurso com questões e **nenhum** apontamento → portão bloqueia. Hoje esse teste
  passaria (é o bug).

## 3. Obrigatório: o veredito reflete os portões

Três estados, nunca "aprovado" com portão pendente:

- `BLOQUEADO`: falha de checagem automática (K22, download, prova).
- `AGUARDANDO PORTOES HUMANOS`: checagens automáticas verdes, mas ao menos um portão (P3, P7
  ou P9) pendente.
- `APROVADO PARA REVISAO HUMANA` não existe mais. O estado final verde é
  `PRONTO PARA O SITE`, só com todos os portões aprovados.

Para a C1 hoje (edital `PENDENTE`, 0 de 610 classificadas), o relatório **deve** sair
`AGUARDANDO PORTOES HUMANOS`, com Download, Prova e Banco verdes e calculados, e Edital e
Classificação pendentes. Esse é o resultado correto, e é o que o critério "checagens verdes"
quer dizer: as automáticas, e não os portões humanos.

## 4. Decidir: `@asset_check` do Dagster ou desvio justificado

O plano falava em "asset checks". Hoje as checagens são funções chamadas dentro dos assets, e
nada aparece como check na interface do Dagster. Faça um dos dois:

- **Preferido:** `@asset_check` (com `blocking=True` onde a checagem for bloqueante) para K22,
  download, prova e os portões, na versão fixada do Dagster (1.9.13; não mude os pins).
- Se não for viável, escreva no relatório final o motivo concreto. O relatório da rodada 2
  disse "nenhum desvio", e isso não era verdade.

## 5. Os relatórios gerados

- Regenere `inventario/lotes/lote_01.md` com o lote da C1 **inteiro** (`SEFA_PR_25` +
  `BANRISUL_25`). O atual lista só `BANRISUL_25`.
- Os testes não podem escrever em `inventario/lotes/` real: use `tmp_path` e confirme que
  `git status` não ganha arquivo novo depois de rodar a suíte.
- Diga se `inventario/lotes/` deve ser versionado ou ignorado, e proponha a linha do
  `.gitignore` (não aplique sem eu aprovar).

## 6. Conferir e responder (sem mudar nada se estiver certo)

As consultas (a) e (b) do runbook saem vazias nos dois relatórios ("Nenhum dado retornado").
Confirme no `docs/runbook-lote.md` §4.5 se vazio significa verde ou se há filtro errado, e
escreva a conclusão com a evidência (a consulta rodada e o resultado). Se for filtro errado,
corrija.

## Proibições (as mesmas das rodadas anteriores)

- Nada grava no banco do piloto nem em produção. Só conferência; `--no-conferencia` não é seguro
  até a D5b ser aprovada.
- Não mudar os pins do `dagster` no `requirements.txt` (1.9.13, de propósito: a 1.8.13 não
  resolve com o `langfuse`).
- Sem credencial no código (A07); o relatório não pode conter chave, token nem URL com
  credencial.
- Não aprovar nada em nome do dono (A25, A27, A30).
- Não editar à mão `docs/tecnico/` (A62), `docs/adr/`, `CLAUDE.md` nem `mkdocs.yml`. O ADR-042
  fica para depois da D5b.
- Não mexer em `site/`. Não commitar, não mexer no Jira, nem em `git stash/checkout/reset`.

## Relatório final (obrigatório, para eu validar)

1. Arquivos alterados, por item (1 a 6).
2. `make test-fast`, `ruff check .`, `ruff format --check .` e
   `venv/bin/python -m scripts.gerar_docs --verificar` (cole as saídas).
3. O relatório do lote da C1 **inteiro**, colado, mostrando de onde veio cada status.
4. O teste que prova que um falso verde é impossível (portão P9 com concurso sem apontamento
   bloqueando; relatório da C1 não sai aprovado).
5. As contagens antes e depois (provas, questões, discursivas, apontamentos e fila dos 2
   concursos, mais o K22), por SQL.
6. O que ficou de fora ou diferente do plano, e por quê.

---

## Revalidação (por quem delegou)

- Ler `executar_c2.py` e `relatorio.py` procurando status literal (`"ok"`, `_badge('OK')`).
- Rodar o lote da C1 em conferência com um número de lote próprio e conferir que sai
  `AGUARDANDO PORTOES HUMANOS`, com Classificação `0 de 610`.
- Conferir no banco que 610 questões continuam sem classificação e que nada mudou (K22 e
  contagens).
- `git status` limpo de artefatos de teste; suíte e `gerar_docs --verificar` verdes.
- Depois disso: commit da D5b, ADR-042 e a página do Dagster no guia.
