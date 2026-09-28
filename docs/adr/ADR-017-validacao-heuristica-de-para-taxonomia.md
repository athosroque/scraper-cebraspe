# ADR-017: Validação Heurística "De-Para" entre Texto-Fonte e Taxonomia Extraída

## Status
Aceito (complementado pelo [ADR-020](ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md): quarto tipo de alerta, `chunk_sem_classificacao`; e pelo [ADR-021](ADR-021-reparo-local-nome-topico-numerico.md): quinto tipo de alerta, `topico_nome_numerico`, e `extrair_itens_numerados`/`PADRAO_ITEM_NUMERADO` movidos para `src/edital_parser.py`)

## Data
2026-09-21

## Contexto

O checkpoint de revisão humana da Etapa 4 (`status_revisao_humana: PENDENTE`)
não tinha nenhuma checagem automática de que a extração do LLM capturou
**todos** os tópicos presentes no texto do edital. A trilha de auditoria
introduzida no ADR-014 (`<edital>.auditoria.json`) registra o que foi
*enviado* ao LLM por chunk (`texto_enviado_llm`), mas nada compara isso
contra o que *voltou* (`topico["nome"]` em `<edital>.json`). O usuário
relatou dificuldade em fazer esse de-para manualmente navegando as tabelas
separadas do Datasette (`chunks` vs. `taxonomia_topicos`) e pediu uma forma
de sinalizar automaticamente tópico que "ficou de fora" da extração.

### Descoberta que mudou o desenho da solução

O prompt de `taxonomia_extractor.py` instrui o LLM a "usar os tópicos
numerados do próprio edital como nome de cada tópico" (`src/taxonomia_extractor.py`,
`PROMPT_SISTEMA`). A hipótese inicial era comparar **números** de item entre
fonte e extração (ex.: `"3 Domínio da ortografia oficial"` no texto-fonte →
`topico["nome"] == "3 Domínio da ortografia oficial"` na extração). Testado
ao vivo contra o edital piloto real (`Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5`,
39 chunks), essa abordagem gerou **385 alertas de falso-positivo**: o LLM
**não preserva a numeração de forma consistente entre chunks do mesmo
edital** — no mesmo run, o chunk 0 devolveu `"1 Compreensão e interpretação
de textos"` (numerado) e o chunk seguinte devolveu só `"Estruturas
lógicas"` (sem número), ambos corretos e completos. Um diff por número
sozinho é, portanto, inútil como critério de comparação.

Depois de trocar para comparação por **texto normalizado**, mais dois bugs
de normalização precisaram ser corrigidos antes do sinal ficar utilizável
(detalhes completos em `LESSONS.md`, tag `llm, extracao, taxonomia,
validacao, unicode, regex`):
1. Cortar o "rótulo" de um item na primeira ocorrência de `"."` truncava
   citações legais embutidas no próprio rótulo (ex.: `"Lei nº 8.429/1992
   (Lei de improbidade administrativa)."` virava só `"Lei nº 8"`).
2. `unicodedata.normalize("NFKD", ...).encode("ascii", "ignore")` descarta
   silenciosamente caracteres não-ASCII sem forma de decomposição — hífen
   tipográfico Unicode (`‐`, U+2010, comum em texto extraído de PDF) sumia
   sem deixar espaço, colando palavras (`"ético‐político"` →
   `"eticopolitico"`), enquanto o hífen ASCII `-` do texto do LLM virava
   espaço normalmente (`"etico politico"`) — a mesma frase normalizava para
   strings diferentes e o `in` (substring) falhava.

Depois das duas correções, o mesmo edital piloto caiu de 385 para **2
alertas**, ambos achados genuínos (não ruído): um caso onde o LLM consolidou
2 itens duplicados do próprio edital (`"7 Educação corporativa"` e `"11
Educação corporativa"`) num único tópico, e um caso de numeração realmente
corrompida no texto extraído do PDF-fonte (chunk `TÉCNICO EM COMUNICAÇÃO
SOCIAL`, um `"1"` duplicado no meio do texto por artefato de extração).

## Decisão

Implementar `scripts/validar_taxonomia.py`, que compara, **por chunk**, os
itens numerados de primeiro nível do texto-fonte contra os tópicos
extraídos, usando o **texto normalizado** (não o número) como chave de
correspondência.

### 1. Extração de itens de primeiro nível do texto-fonte

```python
PADRAO_ITEM_NUMERADO = re.compile(r"(?<!\d\.)\b(\d{1,3})\s+(?=[A-ZÀ-Ú(])")
```

- `(?<!\d\.)` — nega itens pontuados (`"3.1"`) sem bloquear um item de
  primeiro nível colado ao ponto final do item anterior sem espaço (achado
  real: `"...lógicos.4 Lógica..."` — aqui `"4"` é item novo, não `"X.4"`,
  porque os dois caracteres imediatamente antes do dígito são `"s"` e
  `"."`, não `"3"` e `"."`).
- A lookahead `(?=[A-ZÀ-Ú(])` exige maiúscula ou parêntese logo após o
  número (com espaço no meio), evitando casar números soltos em citações
  legais (`"Lei 8.112, de 11 de dezembro de 1990"` → 0 matches).
- `extrair_itens_numerados(texto)` retorna `list[tuple[numero: str,
  texto_do_item: str]]`, onde `texto_do_item` vai do fim do match até o
  início do próximo item de primeiro nível (ou fim da string) — inclui o
  texto de subitens/alíneas do próprio item, propositalmente **sem** cortar
  na primeira pontuação.

### 2. Normalização para comparação

```python
def normalizar(texto: str) -> str:
    texto = texto.strip()
    texto = re.sub(
        r"^\d+(\.\d+)*\.?\s+", "", texto
    )  # remove prefixo numérico ("1 ", "3.1 ", "1. ")
    texto = re.sub(
        r"[^\w]", " ", texto, flags=re.UNICODE
    )  # pontuação/hífen (incl. Unicode) -> espaço
    sem_acento = (
        unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()
```

Ordem importa: a troca de pontuação por espaço acontece **antes** de
derrubar acento/Unicode — inverter a ordem reintroduz o bug do hífen
tipográfico descrito no Contexto.

### 3. Critério de correspondência

```python
TAMANHO_MINIMO_SUBSTRING = 6


def _contido(nome_norm: str, item_norm: str) -> bool:
    return len(nome_norm) >= TAMANHO_MINIMO_SUBSTRING and nome_norm in item_norm
```

Um `topico_nome` extraído (normalizado) "corresponde" a um item da fonte se
aparece como substring do texto completo normalizado do item (não apenas
de um rótulo cortado). O limite de 6 caracteres evita correspondência
espúria de fragmentos curtos genéricos.

### 4. Três tipos de alerta, por chunk

| Tipo | Condição | Significado |
|---|---|---|
| `topico_ausente` | Item de primeiro nível na fonte sem nenhum `topico_nome` extraído que o contenha | Candidato a tópico que o LLM deixou de fora |
| `topico_extra` | `topico_nome` extraído sem correspondência em nenhum item da fonte | Possível erro de chunking/alucinação, ou paráfrase/consolidação do LLM |
| `chunk_sem_extracao` | Chunk com `status == "falha"` (sem `taxonomia_extraida`) e com itens numerados na fonte | Lista agregada dos números perdidos por falha de extração |

**Casos que deliberadamente não geram alerta** (heurística, não prova
formal):
- Matéria sem nenhuma numeração no texto-fonte (`itens_fonte` vazio) — nada
  a comparar em nenhuma direção, melhor não opinar do que gerar ruído.
- Chunk com falha e sem nenhum item numerado na fonte.

### 5. Desambiguação por posição, não por número

Alertas `topico_ausente` carregam `posicao_item` (índice de aparição do
item na lista de itens do chunk, 0-based) além de `numero_item` (o número
literal, só para exibição humana). Números podem se repetir dentro do
mesmo chunk quando o texto-fonte vem corrompido pela extração de PDF (achado
real, chunk `TÉCNICO EM COMUNICAÇÃO SOCIAL`) — usar só o número como chave
marcaria/destacaria todas as ocorrências repetidas, não apenas a
efetivamente sinalizada. `posicao_item` é consumido por
`scripts/gerar_relatorio_revisao.py` (ver ADR-018) para destacar a
ocorrência exata no HTML.

### 6. Formato de saída — `<edital>.validacao.json`

```json
{
  "edital": "Ed_1_2025_PF_Administrativo_Abertura_atualizado_ret_5.pdf",
  "total_chunks_analisados": 39,
  "total_alertas": 2,
  "alertas": [
    {
      "chunk_index": 31,
      "cargo": "CARGO 13: TÉCNICO EM ASSUNTOS EDUCACIONAIS – ÁREA: PEDAGOGIA",
      "materia": "TÉCNICO EM ASSUNTOS EDUCACIONAIS – ÁREA: PEDAGOGIA",
      "tipo": "topico_extra",
      "numero_item": null,
      "posicao_item": null,
      "texto_item_origem": null,
      "topico_nome_extraido": "Educação corporativa (atuação do pedagogo)"
    },
    {
      "chunk_index": 32,
      "cargo": "CARGO 14: TÉCNICO EM COMUNICAÇÃO SOCIAL",
      "materia": "TÉCNICO EM COMUNICAÇÃO SOCIAL",
      "tipo": "topico_ausente",
      "numero_item": "1",
      "posicao_item": 2,
      "texto_item_origem": "Fundamentos e finalidades. 2.1 Assessoria de comunicação. [...]",
      "topico_nome_extraido": null
    }
  ]
}
```

Campos por objeto em `alertas[]`:

| Campo | Tipo | Presente em | Descrição |
|---|---|---|---|
| `chunk_index` | int \| null | todos | Posição do chunk no edital (chave de junção com `<edital>.auditoria.json` e `<edital>.json`) |
| `cargo` | str \| null | todos | Cargo do chunk (`null` = Conhecimentos Básicos) |
| `materia` | str | todos | Matéria do chunk conforme detectada no parsing |
| `tipo` | `"topico_ausente"` \| `"topico_extra"` \| `"chunk_sem_extracao"` \| `"chunk_sem_classificacao"` (ADR-020) \| `"topico_nome_numerico"` (ADR-021) | todos | Categoria do alerta |
| `numero_item` | str \| null | `topico_ausente`, `chunk_sem_extracao` (lista separada por vírgula) | Número(s) do item na fonte, só para exibição |
| `posicao_item` | int \| null | só `topico_ausente` | Índice de aparição do item no chunk (0-based) — chave de desambiguação |
| `texto_item_origem` | str \| null | `topico_ausente` | Texto do item na fonte, truncado em 200 chars |
| `topico_nome_extraido` | str \| null | `topico_extra` | `topico["nome"]` extraído sem correspondência |

CLI: `python -m scripts.validar_taxonomia [revisao_piloto_dir]` — itera
todos os `<edital>.json` do diretório (default `revisao_piloto/`), pula
editais sem `.auditoria.json` correspondente (formato legado, sem
`texto_enviado_llm` não há o que comparar) com log de aviso, e escreve
`<edital>.validacao.json` ao lado dos demais artefatos da Etapa 4.

## Consequências

### Positivas
- Reduz o esforço de revisão humana de "ler 39 chunks inteiros" para "olhar
  N alertas pontuais" — no piloto, 2 alertas genuínos em 39 chunks.
- Não introduz dependência nova (só stdlib: `re`, `unicodedata`, `json`).
- Roda em milissegundos (comparação local, sem chamada LLM) — pode rodar a
  cada regeneração do piloto sem custo de API.
- Alertas carregam contexto suficiente (`chunk_index`, `cargo`, `materia`,
  `texto_item_origem`) para virar ponto de partida da investigação, não só
  um booleano de "tem problema".

### Limitações conhecidas (heurística, não prova formal)
- Matéria sem nenhuma numeração no PDF não é coberta (nada a comparar).
- Numeração irregular/corrompida no PDF-fonte pode gerar falso positivo ou
  negativo — todo alerta é candidato a revisão humana, não erro confirmado.
- `topico_extra` não distingue "LLM alucinou conteúdo inexistente" de "LLM
  parafraseou/consolidou itens legítimos da fonte" (achado real: consolidação
  de 2 itens duplicados do próprio edital) — a categoria sinaliza divergência
  textual, a interpretação fica com o revisor humano.
- Só compara `topico["nome"]` (nível de tópico); `subtopicos` não são
  validados por esta ferramenta.
- O regex `PADRAO_ITEM_NUMERADO` contempla dígitos arábicos (`\d{1,3}`); itens
  compostos exclusivamente por algarismos romanos (`I, II, III`) ou alíneas
  alfabéticas (`a), b)`) de primeiro nível não são detectados como início de
  item independente nesta versão.

### Alternativas Descartadas
- **Diff por número de item:** primeira tentativa, descartada depois de
  comprovar (385 falsos positivos no piloto) que o LLM não preserva
  numeração de forma confiável entre chunks do mesmo edital.
- **Validação via segundo LLM como "juiz":** descartada por ora — mais
  cara (chamada de API adicional por chunk), não-determinística, e a
  heurística textual local já convergiu para um sinal/ruído aceitável no
  piloto sem custo de inferência.
- **Fuzzy matching (`difflib.SequenceMatcher`, distância de edição):**
  descartado em favor de substring simples — o padrão observado nos dados
  reais é que o `topico_nome` extraído, quando corresponde a um item real,
  aparece como substring quase literal do texto-fonte normalizado; um score
  de similaridade contínuo adicionaria um limiar arbitrário sem ganho
  demonstrado contra os dados do piloto.

## Atualização — [ADR-020](ADR-020-classificacao-nivel-tipo-conhecimento-concurso.md) (2026-09-21)

Um quarto tipo de alerta foi adicionado sem mudar a heurística de-para
descrita acima:

| Tipo | Condição | Significado |
|---|---|---|
| `chunk_sem_classificacao` | Chunk com os campos de classificação do ADR-020 e `tipo_conhecimento` ou `nivel` nulo | O chunk fica fora dos filtros por nível ou básico/específico (bloco não reconhecido, ou bloco sem nível único como "PARA TODOS OS CARGOS") |

- Aparece junto com os outros alertas do mesmo chunk, antes deles. Um chunk
  com falha e sem classificação gera `chunk_sem_classificacao` e
  `chunk_sem_extracao`.
- Campos: `numero_item`/`posicao_item`/`topico_nome_extraido` ficam nulos,
  e `texto_item_origem` traz os valores encontrados
  (`"tipo_conhecimento=..., nivel=..."`).
- Auditoria anterior ao ADR-020 (sem os campos de classificação) não gera
  esse alerta, porque não há o que comparar.
- O `tipo` em `alertas[]` passa a ser `"topico_ausente"` \| `"topico_extra"`
  \| `"chunk_sem_extracao"` \| `"chunk_sem_classificacao"`.
- Piloto `PF_25_ADM` após o backfill: 0 alertas de classificação. Os
  mesmos 2 alertas genuínos de antes continuam.

## Atualização — [ADR-021](ADR-021-reparo-local-nome-topico-numerico.md) (2026-09-21)

Um quinto tipo de alerta foi adicionado como rede de segurança passiva, e a extração de itens numerados foi centralizada:

| Tipo | Condição | Significado |
|---|---|---|
| `topico_nome_numerico` | `topico["nome"].strip().isdigit()` nos tópicos retornados | Tópico cujo nome é puramente numérico (o LLM inseriu o número do item em vez do texto); atua como alerta complementar para capturar dados persistidos antes do reparo ou casos residuais |

- Disparado de forma aditiva: não substitui `topico_ausente`/`topico_extra` (que continuam sinalizando a divergência de conteúdo).
- `extrair_itens_numerados()` e `PADRAO_ITEM_NUMERADO` foram migrados para `src/edital_parser.py`, servindo como fonte única de verdade compartilhada entre a validação heurística e o reparo local determinístico em `src/taxonomia_extractor.py`.
