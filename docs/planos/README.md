# Planos de etapa concluídos (arquivo)

Planos de execução por sessão das etapas já concluídas. São histórico: o
estado atual está no `task.md` (checklist) e no `CLAUDE.md` (§5), e as
decisões estão nos ADRs (`docs/adr/`). Não editar; se algo daqui voltar a
valer, levar para o `task.md`.

Só o plano da etapa em andamento fica na raiz do projeto (hoje,
`plano-etapa-8.md`). Ao concluir a etapa, `git mv` para cá.

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

Os planos 5B.2, 5C.1, 5D e 5E tinham sido apagados ao concluir a etapa e
foram recuperados do histórico do git em 2026-10-08, porque o `task.md` e
os ADRs ainda os citam.
