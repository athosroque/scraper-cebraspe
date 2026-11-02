# Planos concluídos

Planos de execução, sessão por sessão, das etapas já concluídas.

**Para que serve:** ver como uma etapa foi feita e o que ficou de fora. São histórico: o
estado atual está no `task.md` (checklist) e no `CLAUDE.md` (§5), e as
decisões estão nos ADRs (`docs/adr/`). Não editar; se algo daqui voltar a
valer, levar para o `task.md`.

Só o plano da etapa em andamento fica na raiz do projeto (hoje,
`plano-etapa-8.md`, `plano-etapa-8c.md` e `plano-etapa-9.md`). Ao concluir a etapa, `git mv` para cá e
acrescente o plano na tabela abaixo e no `nav` do `mkdocs.yml` (grupo "Planos concluídos").

| Arquivo | Etapa | ADR |
|---|---|---|
| `plano-etapa-5b2.md` | 5B.2 — Curadoria da árvore | ADR-030 |
| `correcoes-etapa-5c.md` | 5C.1 — Correções da extração dos cadernos | ADR-031 |
| `plano-etapa-5d.md` | 5D — Classificação das questões na árvore | ADR-032 |
| `plano-etapa-5e.md` | 5E — Estatísticas (views no banco) | ADR-032 |
| `plano-etapa-5f.md` | 5F — Site público (5F.1 a 5F.11; a 5F.12, deploy, foi para o `task.md`) | ADR-033 |
| `correcoes-interface-5f.md` | 5F.11b — Correções da interface web (pendências levadas para o `task.md`) | ADR-033 |
| `plano-etapa-5h.md` | 5H — Card e filtros no formato Gran | ADR-035 |
| `plano-etapa-8m.md` | 8.M — Múltipla escolha (S1 a S4 e Gate; a regra de agregação da S2 foi revista pelo ADR-039) | ADR-038 |
| `plano-etapa-8m1.md` | 8.M.1 — Incidência em dois níveis com prova distinta | ADR-039 |
| `plano-etapa-5b3.md` | 5B.3 — Auditoria da hierarquia da árvore (disciplina → assunto → subassunto) | ADR-030 |
| `plano-kan-30.md` | 8.C/C0 — Download guiado pelo inventário (KAN-30; a 8.C segue em andamento) | ADR-037 |

Os planos 5B.2, 5C.1, 5D e 5E tinham sido apagados ao concluir a etapa e
foram recuperados do histórico do git em 2026-10-08, porque o `task.md` e
os ADRs ainda os citam.

## Prompts e passagens de bastão arquivados

Prompts de sessão e passagens de bastão do Dagster (Etapa 9/D5a e D5b) e do KAN-66, já
cumpridos. Ficam em `docs/planos/prompts/` como histórico (não editar) e fora do `nav`.

| Arquivo | Para que serviu |
|---|---|
| `prompts/prompt-dagster-d5.md` | Prompt das rodadas 1 e 2 do Dagster (D5a e D5b) |
| `prompts/prompt-dagster-d5a-correcoes.md` | Correções da rodada 1 (D5a) |
| `prompts/prompt-dagster-d5b-correcoes.md` | Correções da rodada 2 (D5b) |
| `prompts/prompt-kan-66-busca.md` | Prompt da busca do site (KAN-66) |
| `prompts/proximos-passos-dagster.md` | Passagem de bastão do Dagster |
