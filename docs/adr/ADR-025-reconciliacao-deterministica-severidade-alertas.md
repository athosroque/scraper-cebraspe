# ADR-025: Reconciliação Determinística de Item Ausente e Severidade de Alertas

## Status
Aceito

## Data
2026-09-21

## Contexto

Depois do [ADR-021](ADR-021-reparo-local-nome-topico-numerico.md) e dos ajustes
de falso positivo da validação, a base de 2025 (5 editais, 150 chunks) ficou
com 3 alertas residuais em `scripts/validar_taxonomia.py`. Cada um tinha uma
causa-raiz diferente:

| Edital / chunk | Alerta | Causa | O dado estava errado? |
|---|---|---|---|
| IBAMA_25 #32 | `topico_ausente` item 1 | O LLM omitiu `1 IN Ibama 05/2021.`, o único item só com sigla + número de norma | **Sim**, perda de conteúdo |
| PF_25_ADM #31 | `topico_extra` | O edital repete `Educação corporativa` (itens 7 e 11). O LLM desambiguou o segundo para `Educação corporativa (atuação do pedagogo)` | Não, só o nome foi parafraseado |
| STM_25 #31 | `topico_extra` | O PDF traz o erro de digitação `bBiblioteca Flyway`. O LLM corrigiu para `Biblioteca Flyway` | Não, a extração ficou melhor que a fonte |

Tratar os três do mesmo jeito é o erro a evitar. Suprimir o alerta do IBAMA
esconderia perda de dado. "Consertar" o nome do STM para bater com a fonte
reintroduziria o erro de digitação na base de estatísticas.

Achado lateral: os 5 editais terminam a seção de Objetos de Avaliação com o
bloco de assinatura (nome + cargo do signatário), que ficava colado no texto
do último item do último chunk e ia para o LLM.

## Decisão

1. **Reinjeção determinística de item ausente** (`reinjetar_itens_ausentes`,
   `src/taxonomia_extractor.py`), logo depois do reparo de nome numérico, sem
   chamar o LLM de novo. Um item de primeiro nível da fonte que não casa com
   nenhum tópico nem subtópico entra como `Topico` novo, na posição relativa
   da fonte. Só age sobre item **simples**: sem subitens `N.1` e com até
   `TAMANHO_MAXIMO_ITEM_REINJETAVEL` (150) chars. Item omitido e não
   reinjetável não vira falha: continua como `topico_ausente` no validador.
   É rastreável pela tag de log `[REPARO_ITEM_AUSENTE]` e por
   `metadata["reparo_item_ausente"]` no Langfuse.
2. **Severidade no validador**: um tópico sem casamento estrito, mas que é
   paráfrase leve de um item (sufixo entre parênteses que, removido, casa com
   a fonte; ou similaridade `difflib` ≥ 0,92 com o rótulo ou o texto de um
   item), vira `topico_divergencia_leve` com `severidade: "informativo"`.
   Continua no `.validacao.json`, no relatório HTML e no Datasette (coluna
   `severidade`, `editais.total_informativos`), mas não entra em
   `total_alertas`. O lado `topico_ausente` do mesmo par é absorvido para não
   contar o caso duas vezes como bloqueante.
3. **Comparação textual compartilhada** (`src/comparacao_texto.py`:
   `normalizar`, `contido`, `divergencia_leve`) usada pelo reparo e pelo
   validador. Mesmo princípio do ADR-021: reparo e validação nunca podem
   divergir sobre o que é "item coberto".
4. **Remoção da assinatura final** (`remover_assinatura_final`, chamada por
   `_limpar_ruido_edital`). A âncora é a linha de **cargo** do signatário
   (`PADRAO_CARGO_ASSINATURA`) no fim do texto, sem ponto final depois dela,
   com uma linha de nome plausível antes (sem dígito, até 80 chars). Na
   dúvida, devolve o texto intacto. Validada nos 150 chunks reais: removeu a
   assinatura exatamente do último chunk dos 5 editais e não tocou nos
   outros 145.
5. **Prompt reforçado** com duas regras: todo item de primeiro nível vira
   tópico, inclusive norma/sigla; e não acrescentar qualificador ao nome
   (item repetido fica repetido). É mitigação na origem, sem garantia.
6. **Backfill sem LLM** para extrações já salvas:
   `scripts/reconciliar_taxonomia.py`, com backup
   `<edital>.json.pre_reconciliacao.bak`, que chama `atualizar_revisao`
   (ADR-019) no final.

Resultado na base de 2025: **3 → 0 alertas bloqueantes**, 2 informativos
visíveis (PF, STM). O único dado alterado foi o tópico `IN Ibama 05/2021`
reinjetado no IBAMA #32. A simulação do reparo nos 150 chunks produziu
exatamente essa única reinjeção.

## Consequências

### Positivas
- Custo zero de tokens, determinístico, rastreável no log e no Langfuse.
- Corrige o dado de fato (IBAMA), em vez de só silenciar o alerta.
- Divergência explicável deixa de competir por atenção com erro real, sem sumir do relatório.

### Negativas
- O tópico reinjetado vem com o texto cru do PDF, sem a hierarquia que o LLM montaria. Por isso o reparo não age sobre item com subitens.
- Qualquer tolerância (parêntese, 0,92) pode rebaixar para informativo uma alucinação sutil. Mitigação: é rebaixado, não suprimido, e o corte foi calibrado contra contraexemplos (um nome parecido mas diferente continua `topico_extra`; ver testes).
- O tópico reinjetado não carrega marca de origem no `<edital>.json`. O rastro fica no log e no Langfuse (extração nova) ou no `.bak` + diff do git (backfill).

## Alternativas Consideradas

- **Reprocessar o chunk automaticamente quando houver alerta**: é o retry cego já descartado no ADR-021 (sem contexto, sem garantia de corrigir).
- **Chamada corretiva ao LLM com os itens omitidos**: cobre item com subitens, mas custa tokens, não é determinística e pode piorar tópicos que já estavam certos. Nenhum caso real exige isso hoje. Fica como fallback futuro.
- **Campo `numero` no `Topico`**: vínculo item↔tópico mais robusto, mas exige mudar o schema e reextrair os 150 chunks, e o LLM não preserva a numeração de forma confiável (ADR-017/018).
- **Lista de alertas aceitos na revisão humana**: não é automática. Pode entrar quando a revisão humana da Fase 4 começar.
- **Canonicalizar o nome extraído para o texto literal da fonte**: reintroduziria o erro de digitação do STM. Descartado.

## Atualização (2026-10-12, C1a / KAN-56)

O alerta bloqueante `subitem_ausente` (SEFA_PR_25: 128 no chunk 19, ECONOMIA, e 6 no chunk 18, CONTABILIDADE) mostrou o mesmo padrão do item de 1º nível: o LLM guarda só os dois primeiros níveis e descarta os subitens `1.2.6`, `1.2.10.1`, `21.1.1`. Em vez de repetir a chamada, `taxonomia_extractor.reinjetar_subitens_ausentes` repara no dado, sem LLM:

- **Ausente:** `not item_coberto(texto_proprio, tópicos e subtópicos do chunk)`, a mesma regra do validador. A cobertura é recalculada a cada inserção.
- **Destino:** o tópico que cobre o item de 1º nível do subitem (nome normalizado `contido` no texto do item, preferindo o nome do tópico ao de um subtópico). Sem destino, não reinjeta e o alerta fica.
- **Nome:** cadeia dos textos próprios do ancestral de 2º nível até o subitem, unida por ` - ` (profundidade 2: só o texto próprio), igual ao formato que o LLM usa em outros chunks. Acima de 300 caracteres não reinjeta e loga.
- **Posição:** logo depois do subtópico que cobre o subitem anterior mais próximo do mesmo item de 1º nível (ancestral ou irmão); senão, no fim da lista do tópico.
- **Rastro:** log `[REPARO_SUBITEM_AUSENTE]` e `reparo_subitem_ausente` no metadata da generation, no gancho `_pos_validacao_taxonomia` (extrações novas). `scripts/reconciliar_taxonomia.py` aplica o mesmo reparo a extrações salvas e ganhou `--sem-atualizar` (não chama `atualizar_revisao`).

Aplicado só ao SEFA_PR_25 (backup `.json.pre_reconciliacao.bak`): chunk 18 ganhou 6 subtópicos e chunk 19 ganhou 126; `subitem_ausente` foi de 134 para 0. Nenhum tópico ou subtópico foi removido ou renomeado. Os alertas do PF, STM e IBAMA ficam como estavam, por decisão do dono.
