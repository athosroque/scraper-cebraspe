# ADR-030: Árvore Mestre de Assuntos (Semeada com a 5B) e Site Público de Questões como Objetivo do Produto

## Status
Aceito (decisão de direção; a Etapa 5B.1 está implementada, e as Etapas 5B.2, 5D, 5E e 5F vêm a seguir no `task.md`)

## Data
2026-09-28

## Contexto

**Objetivo do produto, definido pelo dono em 2026-09-27/28:** um **site
público de questões** (item de portfólio), no estilo Gran Questões, com mais
filtros e estatísticas da base de concursos. O escopo inicial é só o piloto
2025 (5 concursos, ~2.800 itens). A questão é a entidade central, e o
**subassunto** é a unidade de estudo: quem estuda escolhe um subassunto
específico. As estatísticas, em ordem de importância, são: (1) o que mais cai
na prova; (2) o que o edital cobra; (3) edital × prova; (4) desempenho
pessoal do usuário. Tudo filtrável por banca, órgão, ano, concurso, cargo,
nível e pela árvore matéria › assunto › subassunto.

Até a 5C, a arquitetura tinha outro centro: a **taxonomia do edital**. A
camada canônica da 5B (ADR-029) monta a árvore a partir dos nomes dos
editais, juntados por sinônimo, e **o pai de cada nome é o pai que ele tem no
edital**. Com só 5 concursos, isso já gerou três problemas que o modelo não
resolve sem mecanismos especiais:

1. **Nome composto.** `Disposições gerais, servidores públicos` (PF, TCU,
   IBAMA básico, CD cargo 1) é o mesmo conteúdo que `Disposições gerais` +
   `Servidores públicos` (STM 2×, IBAMA cargo 1, CD cargo 2). A estatística
   dava 4 + 4 + 4 em três subassuntos, e o certo é 8 + 8 em dois. Juntar o
   composto a uma das partes (`SL-065b9773e6`) contaria "servidores públicos"
   como "disposições gerais", e a proposta foi rejeitada.
2. **Matéria composta.** O CD põe os assuntos de Constitucional ("Poder
   Legislativo", "Administração pública"...) debaixo de `DIREITO
   CONSTITUCIONAL E PROCESSO LEGISLATIVO` (16 assuntos, 9 com a mesma chave
   de regra de um assunto de Direito Constitucional) e de `NOÇÕES DE DIREITO
   CONSTITUCIONAL E DE REGIMENTO INTERNO…` (11 assuntos: 6 batem com
   Constitucional e 1 com Regimento). Como o pai vem do edital, esses
   assuntos não somam com os dos outros concursos. Resolver isso na 5B
   exigiria "dividir" a matéria e "realocar" os filhos, uma exceção ao
   próprio invariante do ADR-029.
3. **Granularidade diferente.** O mesmo conteúdo é assunto num edital e
   subassunto em outro.

Além disso, cada edital novo traz nomes novos que precisam de aprovação. A
5B terminou com 89 matérias, 1148 assuntos e 2493 subassuntos canônicos, e
essa lista cresceria a cada concurso, o que não serve de filtro num site.

O primeiro plano da 5B.1 ("divisão de nomes compostos": operação `divisao`
1 → N, pontes N:N e realocação de filhos) resolvia os casos 1 e 2 com
mecanismos especiais, mas não o 3. Na discussão dele, o dono apontou que a
arquitetura estava misturando o objetivo do produto (site de questões) com
estatística de edital.

## Decisão

1. **A taxonomia passa a ser uma árvore mestre curada** (matéria → assunto
   → subassunto), independente dos editais. O **pai pertence ao nó**, não
   ao edital.
2. **Item de edital e questão apontam para nós (N:N).** O item pode apontar
   para um nó de qualquer nível, e a estatística soma subindo a árvore. Os
   três casos acima viram mapeamento comum: o composto aponta para 2 nós, o
   assunto do CD aponta para o nó de Direito Constitucional e o item de
   outra granularidade aponta para o nó do nível certo. **Nenhum mecanismo
   de divisão ou realocação é necessário.**
3. **Semeada com a 5B, sem perder trabalho.** Cada grupo aprovado do
   `sinonimos.json` vira um nó **com o mesmo ID**, e cada nome de origem vira
   um mapeamento `semente`. Depois da semeadura, `sinonimos.json` fica
   congelado como histórico, e a fonte da verdade passa a ser
   `canonico/arvore.json` (versionado, uma linha por registro).
4. **IDs estáveis e fusão sem apagar ID.** Um nó fundido vira
   `status = fundido` com `fundido_em`, e toda leitura resolve o
   redirecionamento. Nó novo: `NM-/NA-/NS-` + sha1.
5. **Invariantes da 5B mantidos:** nada `proposto` entra na estatística; o
   LLM só propõe, com lista fechada e validação local tipada (ADR-022); o
   agente nunca aprova em nome do dono; item novo de edital só é mapeado
   automaticamente por **regra determinística** (`chave_regra` igual a um
   nome já mapeado no mesmo nó-pai efetivo). Nunca se cria nó novo
   automaticamente.
6. **A questão é classificada no nó mais específico** (5D). Os candidatos
   preferenciais são os nós do edital do caderno, e os de reserva são a
   subárvore global dessas matérias, então uma questão fora do edital ainda
   entra na árvore (e alimenta "edital × prova").
7. **Contagem:** ocorrência de edital = `taxonomia_itens.id` distinto, e o
   item básico é expandido por cargo, respeitando `cargos_restritos`.
   Ocorrência de prova = questão distinta. Nunca se conta o mesmo item 2× no
   mesmo nó.
8. **Produto:** as views no Postgres (5E) alimentam um **site público**
   (5F), com API, frontend, contas, histórico e simulado. O Datasette
   continua só como ferramenta de revisão do dono, atrás do SSO. A stack e a
   autenticação do site ficam para o ADR-033 (5F.0).

## Consequências

- **Positivas:**
  - Composto, matéria composta e granularidade são resolvidos pelo mesmo
    mecanismo (mapeamento N:N).
  - O filtro do site é uma árvore estável, que não cresce a cada edital.
  - As quatro estatísticas saem de duas relações: item de edital → nó e
    questão → nó. O desempenho pessoal é resposta → questão → nó.
  - O ID dos nós semeados é o dos grupos da 5B, então nada do que foi
    aprovado se perde.
- **Negativas / custos:**
  - É preciso uma curadoria inicial da árvore (5B.2), pequena no piloto.
  - Mapear item de edital → nó é um passo de classificação (regra + LLM +
    revisão) e deixa de ser um agrupamento de nomes.
  - As tabelas `materia_canonica`/`assunto_canonico`/`subassunto_canonico`
    e as FKs `*_canonico_id` saem do banco, substituídas por `no_arvore` e
    pelas pontes. Nada fora da 5B as usava.
  - O site acrescenta ao projeto infraestrutura nova (API, auth, dados de
    usuário, exposição pública sem Zero Trust).

## Implementação (Etapa 5B.1, 2026-09-28)

- **Arquivo:** `canonico/arvore.json`, com `nos` (`id`, `nivel`, `nome`,
  `pai`, `origem`, `status`, `fundido_em`) e `mapeamentos` (chave do item →
  lista de `{no_id, origem, status}`). A chave do item é a chave natural do
  banco unida por `|` (`materia`, `materia|topico`,
  `materia|topico|subtopico`). Uma linha por registro, ordenado por ID.
  Leitura e escrita só por `src/arvore.py` (`carregar`, `salvar`,
  `chave_item`).
- **Semente:** `scripts/semear_arvore.py` reproduz a 5B: 89 matérias, 1148
  assuntos e 2493 subassuntos (3730 nós) e 4050 mapeamentos `semente`, com
  100% dos nomes mapeados. Rodar de novo sobre o mesmo `sinonimos.json` não
  gera diff. Se a árvore em disco já foi curada, o script se recusa a
  sobrescrever sem `--forcar`.
- **Operações** (`src/arvore.py`): `criar_no`, `renomear_no`, `mover_no`,
  `fundir_nos` (os filhos passam para o destino), `mapear`, `desmapear`,
  `aprovar`, `rejeitar` e `resolver_no`. Validação: nível do pai, ciclo, ID
  repetido, nó inexistente e apontamento inexistente. Toda falha levanta
  `ArvoreInvalida`. A CLI `scripts/curar_arvore.py` não grava nada quando uma
  operação falha.
- **Pipeline:** `canonico.mapear_novos_itens_por_regra` (chamado por
  `atualizar_revisao.atualizar_arvore`) copia os nós aprovados de um item com
  a mesma `chave_regra` e o mesmo conjunto de nós do pai. Regra ambígua ou
  pai sem nó fica pendente no `arvore.html`, que mostra os itens por nó
  (concurso · cargo · nível), os pendentes e as propostas.
- **Banco:** `no_arvore` recebe todos os nós com o status, e as pontes
  `materia_no`/`topico_no`/`subtopico_no` recebem só apontamento `aprovado`,
  com o nó resolvido. `vw_no_caminho` expõe só a cadeia `ativa`, com o
  `no_efetivo` e o caminho do destino para o nó fundido. Por isso, nó
  proposto não entra na estatística e a ponte nunca fica sem FK.
  `vw_arvore_edital_por_cargo` expande o chunk básico para os cargos do
  nível, respeitando `cargos_restritos` (9569 linhas; os 1485 itens estão
  cobertos). `vw_edital_cobra_base` liga cada item ao nó que ele cobra em
  cada nível, subindo a árvore. `vw_edital_cobra_{materia,assunto,subassunto}`
  (oficial, `aprovado`) e `..._todas` contam `taxonomia_itens.id` distinto.
  As tabelas `*_canonico` e as FKs `*_canonico_id` saíram.
- **Testes:** semeadura e recusa de sobrescrever; operações e validações;
  CLI de ponta a ponta; regra só no mesmo nó-pai efetivo; no Postgres, o
  composto conta 1× em cada nó, o item em nível acima soma no assunto, o
  fundido resolve, o proposto não conta e o básico é expandido por cargo com
  `cargos_restritos`.
- **Ponto de partida da 5B.2:** `Disposições gerais` / `Servidores públicos`
  / o composto dão 3 / 3 / 4 em `vw_edital_cobra_subassunto`.

## Alternativas Consideradas

- **Manter a árvore emergente e implementar a "divisão de nomes compostos"
  (plano original da 5B.1):** resolve o composto e, com realocação de
  filhos, a matéria do CD. Mas não resolve a granularidade, abre exceção no
  invariante do pai e faz a lista de canônicos crescer a cada edital.
  Descartada.
- **Árvore mestre construída do zero** (sem aproveitar a 5B): joga fora a
  revisão já aprovada pelo dono (104 propostas e as regras). Descartada: a
  5B é a semente.
- **Árvore externa pronta** (taxonomia de um site existente): não há fonte
  aberta e reutilizável, e haveria risco de direito autoral. Descartada.
- **Classificar a questão só entre os assuntos do edital** (5D original):
  a questão fora do edital ficaria sem nó, e o "edital × prova" perderia o
  lado "cobrado fora do edital". Substituída pelos candidatos preferenciais
  + reserva.
- **Simulado em HTML estático no Datasette** (5E original): não atende um
  site público com contas. Movido para a 5F.

## Relacionados

- ADR-029 (camada canônica de sinônimos): vira a **semente** desta árvore.
- ADR-022 (falhas tipadas), ADR-019 (pipeline automático), ADR-027 (star
  schema e idempotência por concurso).
- ADR-031 (extração de questões), ADR-032 (classificação e estatísticas, a
  escrever na 5D/5E), ADR-033 (stack e deploy do site, a escrever na 5F.0).
