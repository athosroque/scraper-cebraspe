# ADR-021: Reparo Local Determinístico para Nome de Tópico Numérico

## Status
Aceito

## Data
2026-09-21

## Contexto

Um teste de ponta a ponta rodado do zero contra o edital piloto
(`PF_25_ADM`: coleta + extração + validação, 39 chunks) teve 39/39 chunks
com `status="sucesso"` na extração — mas `scripts/validar_taxonomia.py`
acusou **88 alertas**, muito acima dos 2 alertas genuínos documentados no
[ADR-018](ADR-018-relatorio-html-e-extensao-schema-revisao.md).

Causa raiz: em 2 dos 39 chunks (CARGO 3: CONTADOR — matérias "CONTABILIDADE
APLICADA AO SETOR PÚBLICO", chunk 17, e "MATEMÁTICA FINANCEIRA", chunk 21;
ambas com listas numeradas longas no PDF-fonte), o LLM preencheu
`topico["nome"]` com o **numeral do item da fonte** ("1", "2", "3", ...) em
vez do texto real do tópico, jogando o texto verdadeiro para `subtopicos`.
`nome: str` do Pydantic aceita um numeral numa boa — a extração é
estruturalmente válida, só semanticamente errada — por isso
`status="sucesso"` não pegou o problema. Isso fez `validar_taxonomia.py`
marcar cada item das duas matérias como `topico_ausente` + `topico_extra`
(86 dos 88 alertas; os outros 2 batem exatamente com o ADR-018, não são
regressão). Achado registrado em `LESSONS.md`
(`[tags: llm-extraction, taxonomia, validacao, cebraspe]`).

### Desenho descartado durante a implementação

A primeira versão implementada tratava `nome` numérico como falha técnica
dentro de `_chamar_llm_uma_vez`, retornando `None` pra cair no loop de
retry genérico já existente em `extrair_taxonomia_chunk` (mesmo prompt,
mesmo texto, só uma nova tentativa). Antes de fechar essa versão, o dono do
projeto levantou a objeção central que motivou o redesenho:

> "tenho receio que esse reprocessamento de chunk sem passar nenhum
> contexto para ele, apenas repetir a tarefa possa criar um loop e
> consumir mais tokens que uma etapa extra nesses casos de má formatação,
> seria melhor uma etapa adicional específica para isso, e que seja
> transparente, que conseguimos rastrear quando isso for usado ou
> chamado."

Repetir a chamada idêntica ao LLM (mesmo prompt, mesmo `chunk_text`) não
tem garantia de corrigir o problema — depende só de o modelo "acertar por
sorte" numa nova amostragem — e fica indistinguível, nos logs, de um retry
por falha de rede/timeout. Não é uma correção direcionada, e não deixa
rastro próprio.

## Decisão

Substituir o retry cego por um **reparo local determinístico, sem nenhuma
chamada nova ao LLM**: o texto-fonte já contém o item completo
correspondente a cada numeral (a mesma extração de itens numerados que
`validar_taxonomia.py` usa pra comparação de-para). Movida para
`src/edital_parser.py` (única fonte, evita que reparo e validação
divirjam sobre o que é "o item de origem"):

```python
# src/edital_parser.py
PADRAO_ITEM_NUMERADO = re.compile(r"(?<!\d\.)\b(\d{1,3})\s+(?=[A-ZÀ-Ú(])")

def extrair_itens_numerados(texto: str) -> list[tuple[str, str]]:
    ...  # [(numero, texto_do_item), ...] — ver ADR-017 pro racional do regex
```

`src/taxonomia_extractor.py` ganha o reparo, chamado dentro de
`_chamar_llm_uma_vez` logo após `TaxonomiaEdital.model_validate`:

```python
def _reparar_nomes_numericos(taxonomia: TaxonomiaEdital, chunk_text: str) -> list[str]:
    topicos_numericos = [t for t in taxonomia.topicos if t.nome.strip().isdigit()]
    if not topicos_numericos:
        return []

    mapa_numero_para_texto = dict(extrair_itens_numerados(chunk_text))
    nao_mapeados = []
    for topico in topicos_numericos:
        numero = topico.nome.strip()
        texto_item = mapa_numero_para_texto.get(numero)
        if texto_item is None:
            nao_mapeados.append(numero)
            continue
        logger.warning(
            f"[REPARO_NOME_NUMERICO] tópico '{numero}' reparado localmente "
            f"a partir do texto-fonte: '{texto_item[:60]}'"
        )
        topico.nome = texto_item
    return nao_mapeados
```

- **Zero custo de tokens quando repara** — não é um segundo prompt, é uma
  busca em dicionário sobre o texto que já foi enviado ao LLM na mesma
  chamada.
- **Determinístico** — o mesmo par (taxonomia malformada, texto-fonte)
  sempre produz o mesmo resultado, ao contrário de um retry que depende de
  nova amostragem do modelo.
- **Rastreável de duas formas independentes**, endereçando o pedido
  explícito de transparência:
  1. Log com tag própria e greppável, `[REPARO_NOME_NUMERICO]`, distinta de
     qualquer mensagem de retry por falha técnica.
  2. Quando o reparo resolve 100% dos numéricos, o evento de sucesso
     registrado no Langfuse ganha `metadata["reparo_nome_numerico"]` com a
     lista dos numerais reparados — visível no dashboard sem precisar
     abrir o arquivo de log.
- **Fallback só quando o reparo não cobre tudo**: se sobrar algum numeral
  sem item correspondente no texto-fonte (`nao_mapeados` não vazio), a
  função retorna `None` como qualquer outra falha técnica — cai no
  `status="falha"` normal, capturável por `reprocessar_falhas_piloto.py`
  no fluxo comum. Isso só aciona uma chamada nova ao LLM no caso residual
  em que o reparo determinístico não foi suficiente, não no caminho comum.

Reforço complementar do prompt (`PROMPT_SISTEMA`,
`src/taxonomia_extractor.py`), pra reduzir a chance de o LLM cometer o erro
de novo (mitigação na origem, sem garantia — por isso o reparo local
continua sendo a defesa real):

```
- Use os tópicos numerados do próprio edital como "nome" de cada tópico,
  mas "nome" é sempre o TEXTO do tópico (ex.: "Direitos e garantias
  fundamentais") — nunca apenas o número do item ("1", "2", "3", ...)
  isolado sem o texto que o acompanha.
```

Rede de segurança passiva em `scripts/validar_taxonomia.py::comparar_chunk`
— novo alerta `topico_nome_numerico`, aditivo (não substitui
`topico_ausente`/`topico_extra`, que continuam disparando pro mesmo caso),
pra pegar qualquer dado já persistido antes deste fix ou que sobreviva ao
reparo por algum motivo não previsto:

```python
for nome in topicos_extraidos:
    if nome.strip().isdigit():
        alertas.append({**base, "tipo": "topico_nome_numerico", ...})
```

Por fim, `scripts/reprocessar_falhas_piloto.py::reprocessar_falhas` ganhou
`chunk_indices_forcados: list[int] | None` — permite reprocessar
`chunk_index` específicos mesmo com `status="sucesso"` (CLI: `--chunks
17,21`), usado para corrigir os 2 chunks já malformados no
`revisao_piloto/Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.json`
existente. O mecanismo de substituição por `chunk_index` já era agnóstico
ao motivo da seleção — só a lógica de seleção precisou generalizar.

### Status específico para falha semântica identificada, não "falha" genérica

Revisão adicional durante a implementação: quando o reparo não consegue
mapear todo numeral (`nao_mapeados` não vazio), o chunk não deveria virar
`status="falha"` igual a uma falha técnica comum (rede/timeout/parse) — o
problema não é uma instabilidade transitória (repetir a chamada pode não
resolver, já que depende de o texto-fonte ter a numeração que o LLM usou),
e misturar os dois esconde do humano revisor **por que** aquele chunk
específico não tem taxonomia.

`_chamar_llm_uma_vez`/`extrair_taxonomia_chunk` (`src/taxonomia_extractor.py`)
passam a devolver `tuple[TaxonomiaEdital | None, str | None]` em vez de só
`TaxonomiaEdital | None` — o segundo elemento (`motivo_falha`) é `None` para
falha técnica genérica, ou `STATUS_FALHA_NOME_NUMERICO_NAO_MAPEADO =
"falha_nome_numerico_nao_mapeado"` para este caso específico. Em caso de
múltiplas tentativas, o motivo devolvido é o da **última** tentativa (o
motivo de tentativas anteriores que falharam deixou de importar assim que
uma tentativa seguinte teve outro desfecho).

Os dois orquestradores (`scripts/revisar_taxonomia_piloto.py`,
`scripts/reprocessar_falhas_piloto.py`) persistem esse motivo como o
`status` do chunk em vez do "falha" genérico:
```python
taxonomia, motivo_falha = extrair_taxonomia_chunk(...)
status = "sucesso" if taxonomia is not None else (motivo_falha or "falha")
```
`reprocessar_falhas_piloto.py` ganhou dois ajustes decorrentes:
1. A seleção padrão (sem `--chunks`) passou de `status == "falha"` para
   `status not in (None, "sucesso")` — senão o novo status específico
   deixaria de ser pego automaticamente pelo reprocessamento padrão.
2. O ramo de falha agora também atualiza `auditoria["chunks"][i]["status"]`
   (antes só o ramo de sucesso atualizava) — necessário para o
   reprocessamento **forçado** (`--chunks`) de um chunk que estava
   `"sucesso"` (malformado): sem isso, uma nova falha na tentativa forçada
   deixava o status antigo `"sucesso"` mentindo sobre o resultado da rodada.

`scripts/gerar_relatorio_revisao.py::renderizar_chunk` também precisou
generalizar (`chunk_auditoria.get("status") == "falha"` → `status is not
None and status != "sucesso"`) — senão o relatório HTML deixaria de exibir
o aviso "sem taxonomia" para chunks com o novo status específico e tentaria
renderizar uma taxonomia inexistente. `scripts/gerar_db_datasette.py` **não**
precisou de mudança: `_inserir_chunks_com_auditoria` já grava
`chunk["status"]` verbatim (não hardcoda `"falha"`); só
`_inserir_chunks_sem_auditoria` (caminho legado, pré-ADR-014, sem
`motivo_falha` disponível naquele formato) hardcoda `"falha"`, e isso é
correto para o que aquele formato consegue expressar.
`scripts/validar_taxonomia.py::comparar_chunk` também não precisou mudar: a
condição já é `status == "falha" or resultado_chunk is None`, e
`resultado_chunk` é sempre `None` para qualquer chunk que falhou (nenhum
orquestrador adiciona entrada em `resultados` nesse caso), então o alerta
`chunk_sem_extracao` continua dispensando o status exato.

## Consequências

### Positivas
- Elimina o custo/incerteza de um retry cego no caso comum (2/2 chunks reais
  do achado original foram corrigidos sem nenhuma chamada extra ao LLM,
  verificado reaplicando `_reparar_nomes_numericos` contra os dados reais
  capturados em `.bak` antes deste fix: 32 + 11 tópicos reparados, 0 sem
  correspondência).
- Rastreabilidade própria (log + metadata Langfuse), sem misturar com
  retries de falha técnica.
- Reaproveita a mesma extração de itens numerados que a validação heurística
  já usa (`extrair_itens_numerados`, movida para `src/edital_parser.py`) —
  reparo e validação nunca divergem sobre o que conta como "item de
  origem".
- `reprocessar_falhas_piloto.py` generalizado é reutilizável para qualquer
  futuro caso de "sucesso tecnicamente válido, mas semanticamente
  suspeito", não só este.

### Limitações conhecidas
- Depende de o texto-fonte ter numeração de primeiro nível reconhecível
  pelo mesmo regex da validação (`PADRAO_ITEM_NUMERADO`) — uma matéria sem
  numeração no PDF não tem o que mapear; nesse caso (raro, não observado
  fora deste achado) o chunk cai em falha normal para revisão humana.
- Se o LLM produzir um numeral que não corresponde a nenhum item da fonte
  (ex.: alucinação de número), o reparo não tem como adivinhar — vira
  falha, não erro silencioso.

### Alternativas Descartadas
- **Retry cego reaproveitando o loop genérico** (desenho original,
  descartado após a objeção do dono do projeto): sem contexto do erro, sem
  garantia de correção, sem rastro distinto de outros retries.
- **Uma chamada LLM corretiva dedicada** (enviar a resposta malformada +
  texto-fonte + instrução de correção): mais robusta a casos que o reparo
  local não cobre, mas custa uma chamada extra sempre que o bug ocorre —
  descartada como mecanismo principal porque o reparo determinístico já
  resolveu 100% dos casos reais observados sem gastar nenhum token; fica
  como possível extensão futura (fallback) se o reparo local se mostrar
  insuficiente em editais diferentes de PF_25_ADM.
- **Validator Pydantic em `Topico.nome` rejeitando numeral puro**:
  descartada porque descentraliza a decisão de reparo/retry da camada de
  orquestração (`taxonomia_extractor.py`) para o modelo de dados sem trazer
  benefício — o reparo precisa do `chunk_text` (fonte), que o modelo
  `Topico` não tem acesso.
- **Persistir só o flag de reparo bem-sucedido** (`reparo_nome_numerico:
  true` num campo do `.auditoria.json`), sem tocar no contrato de retorno
  de `extrair_taxonomia_chunk`: cogitado inicialmente para evitar mudar a
  assinatura da função em 3 pontos, mas descartado — o pedido de
  rastreabilidade da revisão cobria os dois desfechos (reparou / não
  reparou), e o desfecho de falha (`nao_mapeados` não vazio) não tinha
  como virar um status específico persistido sem propagar o motivo de
  volta ao chamador. A mudança de contrato (`TaxonomiaEdital | None` →
  `tuple[TaxonomiaEdital | None, str | None]`) foi feita mesmo assim — ver
  seção "Status específico" acima — porque log + metadata Langfuse
  cobrem observabilidade em tempo real, mas não o dado persistido que o
  relatório HTML/Datasette exibem para a revisão humana.
