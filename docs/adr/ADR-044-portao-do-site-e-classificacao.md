# ADR-044: O portão do site é a classificação aprovada, não a aprovação do edital

- **Status:** Aceito
- **Data:** 2026-11-13
- **Etapa:** 5B.4, onda 6 (C2 do `SEFA_PR_25`; KAN-56)
- **Decisores:** Dono do produto
- **Relaciona-se com:** ADR-030 (árvore mestre e site de questões), ADR-032 (classificação
  das questões na árvore), ADR-019 (checkpoint de revisão humana do edital), P41 e A25

---

## 1. Contexto

O projeto tem dois atos de aprovação humana distintos, e até aqui ninguém tinha dito
qual deles decide o que o público vê:

1. **Aprovação do edital** (Etapa 4, P41): o dono revisa a taxonomia extraída e grava
   `status_revisao_humana: APROVADO` no `<edital>.json`. O writer relê esse campo a cada
   carga, e a A25 proíbe fazer isso por `UPDATE` no banco.
2. **Aprovação da classificação** (Etapa 5D, ADR-032): o dono aprova os apontamentos que
   ligam cada questão a um nó da árvore, via `scripts/curar_classificacao.py`.

A redação da P41 — "aprovação da revisão humana é o `status_revisao_humana`" — dá a
entender que o ato 1 é o portão de publicação. **Não é.** A `vw_questoes`, que alimenta
a API e o site, filtra por apontamento de classificação **aprovado**; o
`status_revisao_humana` do edital não entra nessa view.

O descompasso ficou visível em 2026-11-13, na C2 do `SEFA_PR_25`:

- O `BANRISUL_25` tinha o **edital aprovado** desde 2026-11-11 e **nenhuma** das suas 230
  questões aparecia no site, porque os 239 apontamentos seguiam `proposto`.
- O `SEFA_PR_25` tinha o **edital pendente** e, assim que o dono aprovou em lote os 407
  apontamentos, as 379 questões entraram no site na mesma hora — sem que ninguém tivesse
  tocado no `status_revisao_humana`.

Ou seja: os dois concursos estavam em estados opostos do que a leitura ingênua da P41
previa. O efeito colateral prático foi quebrar 14 testes de `site/tests/` que fixavam o
total de questões do banco.

## 2. Decisão

**O portão de publicação é a classificação aprovada.** Fica como está, por decisão do
dono em 2026-11-13.

A aprovação do edital continua existindo, com outro papel: é o aceite da **taxonomia
extraída** (que itens o edital cobra, e em que hierarquia), e é o que a carga do star
schema respeita. Ela não governa, e não passará a governar, a presença da questão no
site.

Consequências aceitas:

- Aprovar classificação **publica**. Quem aprova em lote por confiança está publicando
  em lote, e deve saber disso.
- Um concurso pode ter questões no ar com o edital ainda `PENDENTE`. É o caso do
  `SEFA_PR_25` entre a aprovação da classificação e a do edital, no mesmo dia.
- A aprovação do edital, quando vem depois, é **escrituração**: registra o aceite da
  taxonomia, não muda o que está publicado.

## 3. Alternativa descartada

**Exigir os dois atos para a questão chegar ao site.** Seria mais fiel à leitura literal
da P41 e daria um portão único e explícito de publicação.

Descartada pelo dono porque adiciona um segundo bloqueio para um ganho pequeno: a
classificação já é revisada item a item (ou em lote por confiança, com amostragem por
nó), e é ela que determina onde a questão aparece. Exigir também o aceite do edital
atrasaria a publicação sem melhorar a qualidade do que é publicado.

## 4. O que protege a qualidade, já que o portão é um só

- `questoes.utilizavel = false` tira do site a questão com defeito de extração, sem
  derrubar o caderno (ver o alerta `formula_perdida`, criado no mesmo dia para as 9
  questões de Estatística do `SEFA_PR_25` cujas fórmulas o PDF não entregava em Unicode).
- O painel de `scripts/curar_classificacao.py --pendentes` lista o que exige decisão:
  item `sem_no` e proposta de confiança baixa.
- K22 a K24 continuam guardando o piloto a cada escrita no banco (P71).

## 5. Dívida que esta decisão deixa

Teste de site **não pode** fixar total global do banco: ele cresce a cada classificação
aprovada. Os 14 testes quebrados em 2026-11-13 foram reescritos para ancorar no piloto
(invariante por P71/K22) ou calcular o esperado das tabelas-base.
