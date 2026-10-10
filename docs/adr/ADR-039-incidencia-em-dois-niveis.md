# ADR-039: Incidência agregada em dois níveis (prova → concurso)

- **Status:** Aceito (implementação pendente: Etapa 8.M.1, `plano-etapa-8m1.md`)
- **Data:** 2026-10-10
- **Etapa:** 8.M.1 (corrige a regra da 8.M/S2)
- **Decisores:** Dono do produto
- **Substitui:** a unidade de agregação do ADR-032 §1.5 (concurso) e da 8.M/S2
  (concurso × cargo, `fd4be1d`)

---

## 1. Contexto

A incidência do site ("o que mais cai") é um percentual: questões do nó sobre
questões da prova. Entre várias provas, ele é agregado por média, nunca pela
soma bruta (decisão de 2026-10-09: a soma faria a prova C/E de ~120 itens pesar
o dobro da ME de ~60). A dúvida é **qual é a unidade da média**.

A regra já mudou duas vezes:

1. **5E (ADR-032 §1.5):** a unidade era o **concurso**, com todas as questões
   distintas do concurso num único universo. Os cadernos específicos de todos
   os cargos ficam juntos: no PF_25_ADM, os 975 itens específicos dos 15 cargos
   somam 10× o básico (99), e o básico quase some no % do concurso.
2. **8.M/S2 (`fd4be1d`):** a unidade passou a ser a **prova (concurso × cargo)**,
   e a média dá peso igual a cada prova. Resolve o problema de cima, mas cria
   outro. Um concurso é um edital com vários cargos, e o caderno básico costuma
   ser um só por nível, aplicado a todos os cargos daquele nível. Com peso igual
   por prova, o mesmo caderno básico entra N vezes na média, e o concurso com
   mais cargos domina o resultado.

Peso de cada concurso na média por prova (piloto 2025, 31 provas):

| Concurso | Cargos | Peso na média por prova |
|---|---|---|
| PF_25_ADM | 15 | 48% |
| STM_25 | 10 | 32% |
| IBAMA_25 | 3 | 10% |
| CD_25_NS | 2 | 6% |
| TCU_25_TEFC | 1 | 3% |

Efeito no ranking de matérias (sem filtros, consulta de 2026-10-10 no
`scraper-cebraspe-db`):

| Matéria | Média por prova (8.M/S2) | Dois níveis (esta decisão) |
|---|---|---|
| Língua Portuguesa | 13,06% | 13,81% |
| Direito Administrativo | 8,08% | 10,59% |
| Ética no Serviço Público | 7,07% | 4,81% |
| Direito Constitucional | 5,21% | 6,33% |
| Psicologia | 3,75% | 1,55% |
| Comunicação Social | 3,72% | 1,92% |
| Informática | 3,03% | 1,25% |
| Administração Geral | 2,27% | 4,20% |

Ética, Psicologia, Comunicação Social e Informática ficam infladas porque vêm do
básico ou de cargos específicos da PF. Direito Administrativo e Administração
Geral, mais fortes nos concursos com poucos cargos, ficam subestimadas.

---

## 2. Decisão

A incidência agregada é uma **média em dois níveis**:

1. **Nível 1, a prova (concurso × cargo):** % do nó na prova = questões válidas
   distintas do nó / questões válidas distintas da prova (básico + específico,
   sob os filtros). Continua sendo a unidade de quem estuda para um cargo.
2. **Nível 2, o concurso:** dentro do concurso, a média simples dos % das provas
   dele (o "cargo médio" daquele edital); entre concursos, a média simples
   desses valores. **Cada concurso (edital) pesa 1.**

Regras:

- **Quem entra em cada média:** no nível 1, toda prova do concurso com universo
  maior que 0 sob os filtros, e a que não cobrou o nó entra com 0%. No nível 2,
  todo concurso com pelo menos uma prova elegível, e o que não cobrou o nó entra
  com 0%.
- **% dentro da matéria (`pct_medio_por_concurso` de subassunto/assunto):** a
  mesma regra, com o universo da matéria. No nível 1 entram as provas do
  concurso que têm questão na matéria, e no nível 2 os concursos com pelo menos
  uma dessas provas.
- **Filtros:** filtram a base antes de tudo, como hoje. Com o filtro de um
  concurso, o resultado é a média das provas dele. Com o filtro de uma prova, é
  a conta direta questões / total, igual ao que já existe.
- **Contagens** (`questoes`, `anuladas`, `so_principal`, `total_universo`)
  não mudam: continuam `count(DISTINCT questao_canonica_id)` sobre o universo
  filtrado, e o básico aplicado a N cargos conta 1×.
- **C/E e ME** continuam contando igualmente, e as anuladas continuam fora de
  todo denominador.
- **`vw_comparativo_nivel`** segue a mesma regra por nível: média das provas do
  nível dentro do concurso, depois média entre os concursos que têm aquele nível.
- **Nome:** `pct_medio_por_concurso` volta a dizer a verdade, e o contrato da API
  não muda de forma (só as descrições).

### 2.1 Alternativas descartadas

- **Soma bruta entre provas:** a prova C/E pesa o dobro da ME, e o concurso com
  mais cargos pesa mais (já recusada em 2026-10-09).
- **Concurso como universo único (5E):** o específico de muitos cargos afoga o
  básico, e o % deixa de ser comparável ao de uma prova real.
- **Média por prova (8.M/S2):** o caderno básico compartilhado se multiplica pelo
  número de cargos (§1).
- **Caderno físico distinto como unidade:** resolve a duplicação do básico, mas
  mistura cadernos básicos e específicos de tamanhos diferentes e perde a noção
  de "a prova do meu cargo", que é o que o candidato quer comparar.
- **Peso 1/N por cargo dentro do concurso só no básico:** dá o mesmo efeito do
  nível 2 com uma regra mais difícil de explicar e de testar.

---

## 3. Consequências

- Os números do site mudam quando o recorte junta mais de um concurso: o
  ranking geral, `/estatisticas`, `/materias`, `incidencia` na questão,
  `/eu/prioridades` e o comparativo médio × superior. Recorte de uma prova não
  muda, então o simulado e o plano de um cargo ficam iguais (ex.: PF_25_ADM
  cargo 1 continua começando por AOF, 17,80%).
- Os testes de média por prova (`tests/test_estatisticas_views.py`,
  `tests/test_questoes_writer.py`, `site/tests/test_estatisticas.py`,
  `site/tests/test_materia.py`) ganham o caso que motivou a decisão: um concurso
  com 3 cargos que dividem o básico contra um concurso com 1 cargo, cada um com
  peso 50%.
- Os lotes da Etapa 8 (centenas de concursos, alguns com dezenas de cargos)
  deixam de ser dominados pelos editais grandes.
- A pendência "Incidência de subassunto com vários recortes" (`task.md`) usa
  esta regra para o "% geral da banca".
