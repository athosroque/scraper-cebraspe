# ADR-029: Camada Canônica de Sinônimos (Matéria → Assunto → Subassunto) com Aprovação Humana

## Status
Aceito. Aprovação do dono concluída em 2026-09-27. **A partir de 2026-09-28, os grupos aprovados são a semente da árvore mestre (ADR-030)**; depois da semeadura, `sinonimos.json` fica congelado como histórico.

## Data
2026-09-25

## Contexto

O banco da Etapa 5 (ADR-027) agrupa a taxonomia pela chave natural
`normalizar(nome)`. Nos 5 concursos de 2025 isso deixa 102 matérias, 1259
tópicos e 2689 subtópicos distintos, com sinônimos reais que a chave não
junta: `NOÇÕES DE DIREITO ADMINISTRATIVO` × `DIREITO ADMINISTRATIVO`,
`Lei nº 9.784/1999` × `Lei n o 9.784/1999`, `Atos administrativos` × `Ato
administrativo`, `ADMINISTRAÇÃO FINANCEIRA E ORÇAMENTÁRIA` × `ADMINISTRAÇÃO
ORÇAMENTÁRIA E FINANCEIRA`, `CONTABILIDADE PÚBLICA` × `CONTABILIDADE
APLICADA AO SETOR PÚBLICO`.

A medição de 2026-09-22 mostrou que semelhança de texto não serve para
agrupar sozinha (`atos administrativos` ≈ `contratos administrativos` 0,89,
`mensuração de ativos` ≈ `mensuração de passivos` 0,90, `gestão de processos`
≈ `gestão de pessoas` 0,89). O dono já decidiu: regras determinísticas +
proposta do LLM + aprovação humana; nada `proposto` entra na estatística;
`NOÇÕES DE X` é a mesma matéria `X` com `nocoes = true`.

O subtópico estava num `JSONB` em `taxonomia_itens`, sem dimensão própria,
então não tinha como receber um canônico.

## Decisão

1. **Fonte da verdade versionada:** `canonico/sinonimos.json` (o banco é
   regenerável). Três níveis (`materia`, `assunto`, `subassunto`), cada um
   com:
   - **entradas**: juntam os nomes de origem com a mesma *chave de regra*
     dentro do mesmo pai (a entrada de matéria de um assunto; a de assunto de
     um subassunto). Cada nome guarda a chave natural do banco
     (`dim_materia.chave`, `(matéria, tópico)`, `(matéria, tópico,
     subtópico)`);
   - **grupos** (o canônico): `membros` (IDs de entrada), `nome`, `origem`
     (`regra` | `llm` | `humano`), `status` (`proposto` | `aprovado` |
     `rejeitado`), `escopo` (grupo do pai), e `justificativa`/datas quando
     vêm do LLM ou de decisão humana.
   O arquivo é gravado com um registro por linha, ordenado por ID.

2. **ID estável** (não muda entre reexecuções nem entre máquinas):
   - entrada: `M-`/`A-`/`S-` + sha1(`nível|pai|chave_regra`)[:10];
   - grupo identidade: o próprio ID da entrada;
   - grupo por regra que junta entradas: `MR-`/`AR-`/`SR-` + sha1(`escopo|chave_regra`)[:10];
   - proposta do LLM: `ML-`/`AL-`/`SL-` + sha1(membros ordenados)[:10];
   - grupo criado por humano (`--mover X:NOVO`): `MH-`/`AH-`/`SH-`.
   As tabelas canônicas do banco usam esse ID (`TEXT`) como chave primária,
   para a classificação de questões (Etapa 5D) apontar para ele entre
   recargas.

3. **Regras determinísticas conservadoras** (`src/canonico.chave_regra`),
   aplicadas sobre `normalizar`: tira qualificador entre parênteses (um nível
   de parêntese interno), forma única de norma (`Lei nº 9.784/1999`,
   `Lei n o 9.784/1999` e `Lei 9.784, de 29 de janeiro de 1999` →
   `lei 9784 1999`; ano de 2 dígitos expandido; "e suas alterações" no fim
   sai), tira "noções de/sobre" (vira `nocoes = true`) e artigo inicial, e
   aplica singular/plural simples por palavra (-ões/-ães → -ão, -ns → -m,
   -as/-es/-os → sem "s"; nunca -is/-us, nunca palavra de até 3 letras, com
   lista de exceções como `ônus`). Mesma chave no mesmo escopo = mesmo
   grupo, `origem = regra`, aprovado automaticamente. Ordem de palavras e
   sinônimos de vocabulário **não** são regra: vão para o LLM e para o dono.

4. **Invariantes:**
   - toda entrada presente está em exatamente um grupo `aprovado`. Sem
     decisão, é o grupo identidade (`origem = regra`): "este nome é ele
     mesmo" não junta nada;
   - uma proposta (`proposto`) nunca muda o mapeamento. Até a aprovação, os
     membros continuam no grupo aprovado de antes. É assim que "nada
     proposto entra na estatística" se cumpre sem apagar dado;
   - a reexecução das regras só cria entradas/grupos identidade novos e
     junta grupos `regra`. Nunca mexe em grupo `llm`/`humano` nem em status
     decidido. Grupo `regra` cujo escopo deixa de existir volta a
     identidades;
   - aprovar um grupo de assunto/subassunto exige os membros no mesmo grupo
     aprovado do nível de cima (senão o `aprovar_sinonimos` recusa e diz
     qual matéria aprovar antes). Depois da aprovação de uma matéria, os
     assuntos com a mesma chave de regra nela são juntados por regra.

5. **Proposta do LLM** (`scripts/propor_sinonimos.py`), em 3 passos:
   matérias; assuntos dentro de cada matéria canônica (vale a proposta
   pendente do pai, para não esperar a aprovação do nível de cima);
   subassuntos dentro de cada assunto. Itens = grupos aprovados que as
   regras não juntaram; fica de fora grupo com membro em proposta pendente
   e escopo com nomes de um concurso só (a lista de um edital já não repete
   item). O LLM recebe blocos (escopos) com IDs locais curtos (`i1`, `i2`,
   ...) e devolve `{"grupos": [{"ids", "nome_canonico", "justificativa"}]}`.
   Validação local (`validar_agrupamento`): cada ID em exatamente um grupo,
   sem ID desconhecido e sem grupo entre blocos. Falha é tipada
   (`falha_id_desconhecido`, `falha_id_ausente`, `falha_id_duplicado`,
   `falha_grupo_entre_blocos`, além das técnicas do ADR-022). A segunda
   tentativa leva o erro no prompt, então não é retry cego (ADR-021). Só
   grupo com 2+ itens vira proposta. Proposta igual a um grupo rejeitado não
   é regravada. `nome_canonico` é opcional na resposta (o modelo omite o
   nome em grupo de 1 ID); grupo de 2+ IDs sem nome recebe o nome da regra.
   Os blocos já avaliados ficam em `avaliados_llm`, e a reexecução só paga
   pelos blocos com item novo (`--reavaliar` força todos). Proposta cujos
   membros a regra acabou juntando (mesmo assunto em duas matérias aprovadas
   juntas) é removida como redundante. Escopos pequenos são empacotados em lotes de até 90 itens;
   um escopo só é dividido acima de 200 itens (as matérias vão numa chamada).
   **Não roda no pipeline automático**: custa tokens.

6. **Núcleo LLM genérico** (`src/llm_openrouter.chamar_llm_json`), extraído
   de `taxonomia_extractor._chamar_llm_uma_vez`: REST direto ao OpenRouter,
   status tipados (ADR-022), Langfuse via SDK com a generation aberta antes
   da chamada (ADR-023), `max_tokens` generoso e um gancho `pos_validacao`
   para a validação semântica de cada uso (reparo do ADR-021/025 no
   extrator, lista fechada aqui). `extras_payload={"usage": {"include":
   True}}` faz o OpenRouter devolver o custo. **Toda chamada LLM do
   projeto tem reasoning limitado a 3000 tokens** (decisão do dono,
   2026-09-25): `REASONING_PADRAO = {"reasoning": {"max_tokens": 3000}}` é a
   fonte única, default de `chamar_llm_json`, reexportada pelo extrator de
   taxonomia e usada no payload do bot do Telegram. Os defaults do extrator
   seguem `MAX_TOKENS=12000`/`REQUEST_TIMEOUT=120` (vindos do merge
   `b823c31`); a proposta de sinônimos usa `max_tokens=16000` e
   `timeout=240`.

7. **Revisão humana:** `revisao_piloto/relatorio/sinonimos.html` (mesmo
   Datasette/SSO, linkado do `index.html`) lista, por nível, as propostas
   pendentes com os nomes de origem, os concursos e níveis de cada nome, o
   grupo aprovado atual e os IDs, e também os grupos por regra e os
   decididos. Decisões: `scripts/aprovar_sinonimos.py --aprovar ...
   --rejeitar ... --mover ENTRADA:GRUPO|NOVO --renomear GRUPO=Nome`, que
   reaplica as regras, regenera o relatório e grava o banco.

8. **Banco:** `materia_canonica`, `assunto_canonico`, `subassunto_canonico`
   (só grupo aprovado; upsert + remoção dos IDs que saíram);
   `dim_materia.nocoes` + `materia_canonica_id`;
   `dim_topico.assunto_canonico_id`; o subtópico sai do `JSONB` para
   `dim_subtopico` (tópico, chave) + `taxonomia_subitens` (1 linha por
   subtópico, `ON DELETE CASCADE` a partir do item). `vw_taxonomia_detalhe`
   ganha as colunas canônicas e `vw_subtopico_detalhe` é nova. A carga
   continua idempotente (ADR-027).

9. **Pipeline (ADR-019):** `scripts/atualizar_revisao.py` roda as regras e
   o relatório de sinônimos (sem LLM, best-effort) entre o relatório de
   editais e o banco de revisão.

## Consequências

### Execução real (2026-09-25, `z-ai/glm-5.3-flash`)

- 20 chamadas em 3 execuções: a primeira (~8 min) cobriu os 3 níveis com reasoning de 4000 tokens (anterior à padronização
  em 3000); as duas seguintes, já com 3000, refizeram o nível de assunto
  (um lote de 74 itens tinha falhado) e os subassuntos dos escopos novos.
- Falhas por tipo: `falha_validacao_schema` 2 (o mesmo lote, `nome_canonico`
  ausente nos grupos de 1 ID; corrigido no schema), `falha_grupo_entre_blocos`
  1 e `falha_id_ausente` 1 (ambas resolvidas na segunda tentativa com o erro
  no prompt). 16 lotes ok, 1 falho (refeito depois).
- 38.908 tokens de entrada, 35.558 de saída, custo US$ 0,0139.
- 106 propostas pendentes: 3 matérias, 40 assuntos, 63 subassuntos. 61 delas
  juntam nomes com a mesma chave de regra que só estão separados porque as
  matérias-pai ainda não foram aprovadas (somem ao aprovar a matéria); 75
  dependem de aprovar antes o grupo do nível de cima.
- Banco depois da carga: 93 matérias canônicas, 1202 assuntos, 2593
  subassuntos (todas identidade ou regra, já que nada do LLM foi aprovado);
  102/102 matérias, 1259/1259 tópicos e 2689/2689 subtópicos mapeados; 3127
  linhas em `taxonomia_subitens`; 18 matérias com `nocoes = true`. Carga
  repetida com contagens idênticas.

### Positivas
- Regras sobre os 5 concursos: 102 nomes de matéria em 93 entradas (9
  grupos por regra, todos "NOÇÕES DE X" × "X"), 1259 tópicos em 1202
  entradas (52 grupos), 2689 subtópicos em 2593 entradas (85 grupos). Tudo
  aprovado automaticamente e idempotente.
- A estatística oficial continua igual até o dono aprovar (identidade), e
  passa a juntar sinônimos só depois disso.
- O mesmo núcleo LLM serve a Etapa 5D (classificação por lista fechada).
- Os pares de falso positivo medidos em 2026-09-22 ficam separados por
  construção (teste), e só se juntariam por aprovação.

### Negativas
- `sinonimos.json` tem ~2 MB para 5 concursos, puxado pelos subtópicos (um
  registro por entrada e por grupo identidade). Cresce linear com os
  editais; se incomodar, o grupo identidade pode virar implícito.
- A regra de plural não trata -is/-eis/-ais (`nível` × `níveis` ficam
  separados) nem ordem de palavras. Fica para o LLM e o dono.
- Tirar o parêntese junta `X (qualificador)` com `X`, inclusive quando o
  qualificador separa dois itens que o edital repete (PF, "Educação
  corporativa"). É a regra pedida pela spec.
- Assunto proposto dentro de uma matéria ainda pendente só pode ser
  aprovado depois dela.

## Alternativas Consideradas

- **Agrupar por similaridade de texto:** descartado pelos falsos positivos
  medidos.
- **Deixar o nome sem grupo aprovado com canônico NULL até a revisão:**
  tiraria da estatística ~4 mil nomes que não têm sinônimo nenhum. A
  identidade aprovada por regra dá o mesmo resultado de hoje sem inventar
  nada.
- **Mandar as ~4 mil entradas ao LLM de uma vez, ou por similaridade:**
  estoura o contexto e perde a hierarquia. A lista fechada por escopo
  (matéria → assunto → subassunto) limita o que o LLM pode juntar.
- **IDs do próprio JSON no prompt:** IDs locais curtos erram menos; a
  tradução para o ID estável é local.
- **Rodar a proposta do LLM no pipeline automático:** custa tokens a cada
  extração e geraria propostas repetidas.
