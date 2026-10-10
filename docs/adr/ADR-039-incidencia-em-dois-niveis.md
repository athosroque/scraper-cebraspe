# ADR-039: Incidência agregada em dois níveis (prova → concurso)

- **Status:** Aceito (implementado na 8.M.1)
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

---

## 4. Atualização (2026-10-10): prova distinta

### 4.1 Regra

O nível 1 deixa de ser "cada cargo" e passa a ser a **prova distinta**: dentro de
um concurso, cargos com **exatamente as mesmas questões** sob o universo e os
filtros contam como **uma prova só**. Uma questão igual em mais de um cargo conta
1× dentro do concurso, e agora o percentual também respeita isso (as contagens já
respeitavam, por `questao_canonica_id` e `count(DISTINCT)`).

```
assinatura(concurso, cargo, escopo) = conjunto de questao_canonica_id do cargo no escopo
                                      (escopo '' = prova inteira; ou o id da matéria)
                                      — anuladas incluídas na assinatura
prova distinta = (concurso, escopo, assinatura); um cargo representante a calcula
pct_prova(p)    = questões válidas do nó em p / total válido de p × 100
pct_concurso(c) = média de pct_prova entre as provas distintas elegíveis de c
pct_final       = média de pct_concurso entre os concursos elegíveis
```

- A assinatura é calculada **depois** dos filtros (a base de `fn_prova_cobra`
  continua filtrada primeiro). Com `p_nivel`, só entram cargos daquele nível, e
  `vw_comparativo_nivel` junta provas dentro do nível.
- `pct_do_universo` usa o escopo da prova inteira; `pct_medio_por_concurso` usa o
  escopo da matéria do nó para assunto/subassunto (para matéria é igual ao
  `pct_do_universo`), e a assinatura da matéria é só das questões dela.
- Anuladas entram na assinatura: dois cargos que diferem só por uma anulada são
  provas distintas (caderno diferente), mesmo com as mesmas válidas.
- Contagens (`questoes`, `anuladas`, `so_principal`, `total_universo`) e o filtro
  de uma prova (concurso + cargo) não mudam. Arredonda-se só no fim.
- `vw_comparativo_nivel` ganhou `concursos_medio`/`concursos_superior` (divisor da
  média final); `cargos_*` seguem como contagem informativa.

### 4.2 Por quê

Há concursos em que o cargo não é a unidade da prova: o SEE_PE_22 tem um único
caderno específico para os cargos 3 a 47, e o IPAAM_25 um único básico para os
cargos 1 a 19. Pela regra do §2, as provas desses cargos, que são a mesma, entrariam na média
do concurso 45 vezes (SEE_PE_22) ou 19 vezes (IPAAM_25), e o cargo repetido
passaria a pesar mais que o cargo de prova própria dentro do edital. A prova
distinta faz o nível 1 contar provas reais, não números de cargo.

### 4.3 Conferido no banco (piloto 2025, 70 provas, 31 cargos)

- No piloto cada cargo tem um específico próprio: as 31 provas viram 31 provas
  distintas (PF_25_ADM 15/15, STM_25 10/10, IBAMA_25 3/3, CD_25_NS 2/2,
  TCU_25_TEFC 1/1). Por isso o ranking de matérias sem filtro continua o do §1:
  LP 13,81; Direito Administrativo 10,59; Direito Constitucional 6,33; Ética
  4,81; Administração Geral 4,20; Psicologia 1,55; Comunicação Social 1,92;
  Informática 1,25. Bate também com a consulta de referência do plano.
- As 31 provas filtradas uma a uma (`p_concurso` + `p_cargo_numero`), nos 3
  níveis, saíram idênticas às de antes (`pct_do_universo` e
  `pct_medio_por_concurso`). O plano de PF_25_ADM cargo 1 segue começando por AOF
  (17,80%).
- O que muda: `pct_medio_por_concurso` de assunto/subassunto nas matérias do
  básico (na PF_25_ADM, o CB1 de 14 cargos e o CB2 de 1 cargo passam a pesar
  50/50) e qualquer recorte `p_tipo_conhecimento = 'basico'`. Exemplos sem filtro,
  regra do §2 → prova distinta: LP > Compreensão e interpretação de textos
  32,44 → 27,73; LP > Reescrita de frases 9,13 → 15,76; Legislação > Resolução TCU
  nº 155/2002 9,09 → 50,00. Recorte `basico`, `pct_do_universo` de matéria: LP
  30,33 → 31,66; Ética 16,66 → 11,65; Direito Administrativo 12,68 → 9,66;
  Informática 7,10 → 3,43.
- Testes novos em `tests/test_estatisticas_views.py`: concurso com 3 cargos no
  mesmo básico × concurso de 1 cargo (cada um pesa 50%); 3 cargos com prova
  idêntica + 1 diferente = 2 provas; anulada na assinatura; filtro `basico`
  com cadernos distintos; filtro `p_nivel` batendo com `vw_comparativo_nivel`.
