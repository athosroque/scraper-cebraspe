# Plano — Etapa 8.M.1: Incidência em dois níveis (prova → concurso)

> Autocontido: dá para executar numa sessão só, sem reler o `task.md` nem os
> ADRs. Decisão em `docs/adr/ADR-039-incidencia-em-dois-niveis.md` (aceita pelo
> dono em 2026-10-10).

## Goal

Trocar a média por prova (concurso × cargo) da 8.M/S2 por uma **média em dois
níveis**: o % do nó em cada prova; a média das provas dentro do concurso; a média
entre concursos. Cada concurso (edital) pesa 1, e o caderno básico compartilhado
por N cargos deixa de entrar N vezes na média.

## Por quê (resumo do ADR-039)

No piloto, o PF_25_ADM tem 15 das 31 provas e pesa 48% da média; o TCU_25_TEFC
tem 1 e pesa 3%. Ética no Serviço Público (básico da PF) aparece com 7,07%, e
com dois níveis fica com 4,81%. Direito Administrativo vai de 8,08% para 10,59%.

## Regra (o que implementar)

Para cada nó e sob os filtros (a base é filtrada antes, como hoje):

```
pct_prova(p)     = questoes_no(p) / total(p) × 100      -- p = concurso × cargo
pct_concurso(c)  = média de pct_prova(p) entre as provas elegíveis de c
pct_final        = média de pct_concurso(c) entre os concursos elegíveis
```

- **`pct_do_universo`** (incidência do site): o universo de `total(p)` é a prova
  inteira (escopo `''`). Provas elegíveis: todas com `total > 0`; quem não cobrou
  o nó entra com 0. Concursos elegíveis: todos com pelo menos 1 prova elegível;
  quem não cobrou o nó entra com 0.
- **`pct_medio_por_concurso`**: para subassunto/assunto, o universo é a matéria
  do nó na prova (escopo = `no_materia_id`), e elegíveis são as provas com
  questão na matéria e os concursos com pelo menos uma dessas provas. Para
  matéria, é igual ao `pct_do_universo`.
- Contagens (`questoes`, `anuladas`, `so_principal`, `total_universo`) **não
  mudam**.
- Filtro de 1 prova → igual à conta direta; filtro de 1 concurso → média das
  provas dele (igual à regra da S2 com esse filtro).

### Esboço SQL (`fn_prova_cobra`)

Os CTEs `den`, `elegiveis` e `por_prova` já existem. Muda o que vem depois:

```sql
-- quantas provas elegíveis cada concurso tem, por escopo
provas_conc AS (
    SELECT concurso, escopo, count(*) AS n_provas FROM den GROUP BY concurso, escopo
),
-- quantos concursos elegíveis por escopo (divisor do nível 2)
concursos_esc AS (
    SELECT escopo, count(DISTINCT concurso) AS n_concursos FROM den GROUP BY escopo
),
-- nível 1 → 2: média das provas dentro do concurso (quem não cobrou = 0)
por_concurso AS (
    SELECT p.nivel_alvo, p.alvo_id, p.concurso, d.escopo,
           sum(p.questoes * 100.0 / d.total) / pc.n_provas AS pct
    FROM por_prova p
    JOIN den d ON d.concurso = p.concurso AND d.cargo_edital_id = p.cargo_edital_id
              AND d.escopo = <'' para pct_do_universo | escopo da matéria para o outro>
    JOIN provas_conc pc ON pc.concurso = p.concurso AND pc.escopo = d.escopo
    GROUP BY p.nivel_alvo, p.alvo_id, p.concurso, d.escopo, pc.n_provas
),
-- nível 2: média entre concursos (quem não cobrou = 0)
media AS (
    SELECT pc.nivel_alvo, pc.alvo_id, round(sum(pc.pct) / ce.n_concursos, 2) AS pct
    FROM por_concurso pc JOIN concursos_esc ce ON ce.escopo = pc.escopo
    GROUP BY pc.nivel_alvo, pc.alvo_id, ce.n_concursos
)
```

Fazer isso duas vezes (como hoje: `media_prova` com escopo `''` e `media_escopo`
com o escopo da matéria) ou parametrizar por um CTE de escopo. Arredondar só no
fim.

## Arquivos

| Arquivo | O que muda |
|---|---|
| `src/sql/schema_estatisticas.sql` | `fn_prova_cobra` (regra acima e o comentário acima dela, l. ~955–985); comentário geral das views (l. ~444); `vw_comparativo_nivel` (média das provas do nível dentro do concurso, depois entre concursos; somar as colunas `concursos_medio`/`concursos_superior` como divisor, mantendo `cargos_*`); comentário da `vw_prova_cobra_no` (l. ~1113) |
| `tests/test_estatisticas_views.py` | docstring do topo; `test_pct_medio_por_concurso_pesos_iguais` (l. ~497) e o teste dos 54,17% (l. ~719) recalculados; **caso novo**: concurso A com 3 cargos dividindo o mesmo básico × concurso B com 1 cargo → cada um pesa 50%; prova única e concurso único continuam iguais |
| `tests/test_questoes_writer.py` | conferir o exemplo da l. ~569 (média de 50% e 10%) |
| `site/app/modelos.py` | descrições de `pct_do_universo`, `pct_medio_por_concurso` e dos campos de % (l. ~260, 567, 610–622, 642, 665): "média das provas dentro de cada concurso e depois entre os concursos, com peso igual por concurso" |
| `site/app/api/v1/rotas_estatisticas.py`, `rotas_materias.py` | descrições (l. ~42, 23, 37) |
| `site/app/repositorio/estatisticas_repo.py`, `questoes_repo.py`, `site/app/servicos/contas_servico.py` | docstrings (a ordem continua `pct_do_universo DESC, pct_medio_por_concurso DESC, ...`) |
| `site/app/templates/estatisticas.html`, `materia.html` | textos de ajuda ("cada concurso × cargo com o mesmo peso" → "cada concurso com o mesmo peso; dentro dele, a média das provas dos cargos") |
| `site/tests/test_estatisticas.py`, `site/tests/test_materia.py` | expectativas de ranking que dependem da média |
| `site/openapi.json` | `python site/scripts/exportar_openapi.py` depois de mudar as descrições |
| `docs/adr/ADR-039-...md` | status → "Aceito (implementado)", com os números conferidos |
| `CLAUDE.md` §5/§6, `task.md` 8.M.1 | marcar como concluída e mover este plano para `docs/planos/` |

## Passos

1. Testes primeiro (`tests/test_estatisticas_views.py`): o caso 3 cargos × 1
   cargo falha com a regra atual.
2. Reescrever `fn_prova_cobra` e `vw_comparativo_nivel`; aplicar o schema
   (`python -m src.stats_writer` recria as views e reaplica os GRANTs).
3. Conferir no banco (consulta de referência abaixo): o ranking de matérias tem
   de bater com a tabela do ADR-039 (LP 13,81; Dir. Adm. 10,59; Ética 4,81;
   Dir. Const. 6,33; Psicologia 1,55; Com. Social 1,92; Informática 1,25;
   Adm. Geral 4,20).
4. Conferir que não mudou: as 31 provas filtradas uma a uma, nos 3 níveis
   (`p_concurso` + `p_cargo_numero`), dão os mesmos `pct_do_universo` e
   `pct_medio_por_concurso` de antes (guardar a saída antes do passo 2). O plano
   de PF_25_ADM cargo 1 continua começando por AOF (17,80%).
5. Textos do site, OpenAPI, testes do site.
6. `make test-all` verde; validar `/estatisticas` e `/materias` no Chromium
   headless.
7. Documentação (tabela acima) e commit `fix(scraper-cebraspe): ...`.

### Consulta de referência (a mesma do ADR-039)

```sql
WITH b AS (SELECT * FROM vw_prova_cobra_base),
den AS (SELECT concurso, cargo_edital_id,
               count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) t
        FROM b GROUP BY 1,2),
pp AS (SELECT alvo_id, concurso, cargo_edital_id,
              count(DISTINCT questao_canonica_id) FILTER (WHERE NOT anulada) q
       FROM b WHERE nivel_alvo='materia' GROUP BY 1,2,3),
pct AS (SELECT d.concurso, d.cargo_edital_id, m.alvo_id, COALESCE(pp.q,0)*100.0/d.t p
        FROM den d CROSS JOIN (SELECT DISTINCT alvo_id FROM pp) m
        LEFT JOIN pp ON pp.concurso=d.concurso AND pp.cargo_edital_id=d.cargo_edital_id
                    AND pp.alvo_id=m.alvo_id),
por_conc AS (SELECT concurso, alvo_id, avg(p) p FROM pct GROUP BY 1,2)
SELECT nc.nome, round(avg(p),2) AS media_2_niveis
FROM por_conc JOIN vw_no_caminho nc ON nc.id = alvo_id
GROUP BY nc.nome ORDER BY 2 DESC LIMIT 12;
```

## Done When

- [ ] `fn_prova_cobra` e `vw_comparativo_nivel` com a média em dois níveis; o
      ranking de matérias bate com a consulta de referência.
- [ ] As 31 provas filtradas uma a uma não mudam.
- [ ] Teste novo (3 cargos com básico compartilhado × 1 cargo) verde.
- [ ] Textos do site e `site/openapi.json` descrevem a regra nova.
- [ ] `make test-all` verde; ADR-039, `task.md` e `CLAUDE.md` atualizados.

## Fora do escopo

- Filtros novos de `fn_prova_cobra` (`p_formato`, gabarito C/E) e o "% geral da
  banca" ao lado do % da prova: pendência "Incidência de subassunto com vários
  recortes" no `task.md`, que passa a usar esta regra.
