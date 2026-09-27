# Lições — scraper-cebraspe

### [tags: edital-parser, regex, modelagem, cebraspe, postgres]
**Sintoma:** `dim_materia` tinha 106 matérias, mas 4 eram a mesma matéria do
STM com a restrição de cargo no nome (`DIREITO PENAL MILITAR (APENAS PARA O
CARGO 1: ... E PARA O CARGO 8: ...)`), e havia espaço duplo no IBAMA. Na
primeira correção, a regex `\([^)]*\)` parava no primeiro `)` e
`ANALISTA (TI)` deixava o resto da cláusula no nome. Restrição sem número de
cargo (`PARA OS CARGOS DE NÍVEL SUPERIOR`) era apagada e a matéria passava a
valer para todos os cargos.
**Causa:** a chave natural da matéria vinha do nome cru. O ADR-024 já tinha
aceitado o parêntese com `:` interno para não truncar o nome, mas não separou
a restrição. A primeira correção removia do nome antes de saber se tinha
extraído algum cargo.
**Solução (ADR-028):** a restrição vira `cargos_restritos` e só sai do nome
quando há número de cargo; sem número, fica no nome e loga
`[RESTRICAO_SEM_CARGO]`. A regex aceita um nível de parêntese interno. O
número de cargo vem de `extrair_cargos_do_texto`, a mesma função do writer.
**Custo do aprendizado:** ~40 min, somando a auditoria da entrega da 5A, que
achou os dois casos de borda com testes de mesa (não aparecem nos 5 editais
atuais).

### [tags: edital-parser, spider, chunking, multiline, regex, camara-dos-deputados]
**Sintoma:** Na coleta e extração do concurso da Câmara dos Deputados (`CD_25_NS`):
1. O Cargo 1 absorvia a primeira linha de um título de matéria multi-linha (`REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM DO CONGRESSO NACIONAL E`) dentro do seu próprio rótulo de cargo, e a matéria resultante ficava truncada apenas como `CÓDIGO DE ÉTICA`.
2. O Cargo 2 gerava chunk onde o nome da matéria repetia o próprio nome do cargo, engolindo o título `NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS` dentro do texto programático, porque o edital original omitiu o delimitador dois-pontos (`:`) antes do item numerado `1`.
3. No crawler, editais administrativos de retificação citando "reabertura de período de acesso à imagem da prova discursiva" eram mapeados falsamente como editais de abertura.
**Causa:**
1. `PADRAO_MATERIA` era estritamente mono-linha; permitir `\n` genérico causava regressão no edital do IBAMA (onde a segunda linha de um cargo longo era engolida como matéria).
2. `dividir_por_cargo_e_materia` assumia que a presença de itens numerados imediatos sob um cargo indicava especialidade médica/técnica (onde a matéria é o cargo), sem verificar se havia um título em caixa alta antes do primeiro item `1`.
3. `re.search(r'EDITAL.*?ABERTURA', text)` casava `REABERTURA` por ausência de fronteira de palavra `\b`.
**Solução (ADR-024):**
1. Refinar `PADRAO_MATERIA` para permitir quebras de linha estritamente condicionadas a conectivos/preposições no final da linha (`(?:,\s*|\s+(?:E|OU|DE|DA|DO|DOS|DAS))\s*\n`).
2. Detectar determinísticamente prefixos em caixa alta antes do primeiro item numerado no bloco do cargo para nomear a matéria e ajustar o offset do texto do chunk.
3. Usar fronteira de palavra `\bABERTURA\b` no crawler.
**Resultado:** Extração de 15/15 chunks do `CD_25_NS` com 100% de sucesso, 0 falhas e **0 alertas de validação**, com 165 testes unitários e de integração aprovados.
**Custo do aprendizado:** ~25 min entre inspeção visual da formatação crua do PDF da Câmara, ajuste com regexes de conectivos e validação de não-regressão.

### [tags: pymupdf, pdf-parsing, regex, edital, whitespace]
**Sintoma:** Marcadores essenciais de seção (`OBJETOS DE AVALIAÇÃO`) ou cabeçalhos de bloco e matérias não eram localizados pelo parser ou regexes em editais de 2025 (como STM e IBAMA), resultando em `secao is None` ou cabeçalhos engolidos silenciosamente.
**Causa:** Certos PDFs gerados por diagramadores do CEBRASPE contêm espaços não-separáveis (`\xa0` / `&nbsp;`) entre as palavras (ex.: `"15\xa0DOS\xa0OBJETOS\xa0DE\xa0AVALIAÇÃO"` ou `"CARGO\xa01:"`). O `str.find` com espaço normal `" "` e expressões regulares não configuradas com `\s` falham em casar o padrão.
**Solução:** Fazer a substituição determinística `.replace("\xa0", " ")` na camada mais baixa de extração de páginas do PyMuPDF (`extrair_texto_paginas` e inspeção preliminar de edital).
**Custo do aprendizado:** ~10 min de inspeção nos bytes crus retornados por `page.get_text()`.

### [tags: edital-parser, chunking, multiline, regex]
**Sintoma:** No edital do IBAMA, títulos longos de cargo quebrados em múltiplas linhas geravam chunks fantasmas com o nome da segunda linha (ex.: matéria `"QUALIDADE AMBIENTAL"` sem tópicos); no STM, matérias com colons em parênteses (ex.: `LÍNGUA INGLESA (APENAS PARA O CARGO 3: ...):`) tinham o nome truncado prematuramente; e blocos intitulados `CONHECIMENTOS GERAIS` ficavam sem classificação de nível/tipo.
**Causa:** (1) `dividir_por_cargo_e_materia` considerava qualquer texto intermediário não-vazio após um `CARGO N:` como matéria própria; (2) `PADRAO_MATERIA` parava no primeiro dois-pontos encontrado, mesmo dentro de parênteses explicativos; (3) `PADRAO_BLOCO` só conhecia `BÁSICOS`, `ESPECÍFICOS` e `COMPLEMENTARES`.
**Solução:** (1) Testar `extrair_itens_numerados(texto_bloco)` antes de criar chunk de cargo: se não há itens, anexar o texto ao rótulo do cargo; (2) Aceitar bloco parentético antes do colon (`(?:\s*\([^)]*\))?:`); (3) Incluir `GERAIS` mapeado para `"basico"` e prefixos numéricos de subitem no bloco.
**Custo do aprendizado:** ~25 min entre identificação no relatório HTML e criação dos testes de regressão correspondentes.

### [tags: validacao, taxonomia, falsos-positivos, unicode, nfd, ligaturas]
**Sintoma:** A validação heurística do edital `IBAMA_25` gerou 1.271 alertas de validação (`topico_ausente` e `topico_extra`) em 33 chunks que haviam sido extraídos pelo LLM com 100% de sucesso estrutural.
**Causa (cinco fatores combinados):**
1. *Acentos decompostos (NFD):* O PDF continha caracteres com diacríticos combinantes isolados (`i` + `\u0301`). O regex `[^\w]` arrancava o diacrítico, divergindo da forma precomposta gerada pelo LLM.
2. *Ligaduras corrompidas de fonte:* Fontes embutidas do CEBRASPE codificavam ligaduras tipográficas em caracteres Unicode privados ou raros (`Ɵ` para "ti", `Ō` para "ft", `ﬁ` para "fi", etc.), transformando `administraƟva` em `administra va` e falhando contra `administrativa`.
3. *Cobertura de subtópicos ignorada:* O validador só olhava `topico["nome"]`. Quando o LLM organizava tópicos com `subtopicos`, cada item subordinado virava falso `topico_ausente`.
4. *Piso de substring alto:* `TAMANHO_MINIMO_SUBSTRING = 6` impedia o casamento de palavras legítimas com menos de 6 caracteres (ex.: "Crime", "Atos", "Bens").
5. *Emissão de `topico_extra` cega:* Tópicos válidos extraídos do corpo do texto que não casavam diretamente com um item numerado individual eram tachados de alucinação, mesmo estando contidos no texto original do chunk.
**Solução:** Compor caracteres via `unicodedata.normalize("NFC")` antes de limpar pontuação; criar `MAPA_LIGATURAS_FONTES` para substituir glifos corrompidos; validar presença em tópicos OU subtópicos (`todos_extraidos`); permitir casamento por fronteira `\b` e igualdade exata para >= 3 caracteres; e verificar presença no texto integral (`texto_fonte_norm`) antes de acusar `topico_extra`.
**Resultado:** Queda de 1.271 para **1 alerta** no IBAMA_25. Em 135 chunks de 4 editais de 2025, restaram apenas 3 alertas no total.
**Custo do aprendizado:** ~45 min iterando sobre os dados de auditoria e validação reais do IBAMA e STM.

### [tags: llm-extraction, taxonomia, validacao, cebraspe]
**Sintoma:** Teste completo de ponta a ponta (coleta + extração) rodado do
zero contra `PF_25_ADM` (2026-09-21) devolveu 88 alertas de
`validar_taxonomia.py`, contra os 2 alertas genuínos documentados no piloto
original (ADR-018) — mesmo edital, 39/39 chunks com `status="sucesso"`, 0
falhas de extração.
**Causa:** Em 2 dos 39 chunks (ambos do CARGO 3: CONTADOR — matérias
"CONTABILIDADE APLICADA AO SETOR PÚBLICO" e "MATEMÁTICA FINANCEIRA"), o LLM
preencheu `topico["nome"]` com o **numeral do item da
fonte** ("1", "2", "3", ...) em vez do texto real do tópico, empurrando o
texto verdadeiro para `subtopicos`. A extração é estruturalmente válida
(JSON parseia, Pydantic aceita, por isso `status="sucesso"`) mas
semanticamente errada — e como `validar_taxonomia.py` compara
`topico["nome"]` contra o texto do item-fonte, todo item da matéria vira
`topico_ausente` (nome extraído não bate) + `topico_extra` (o numeral
"1"/"2"/... não corresponde a nada), inflando o total de alertas sem
nenhuma falha real de rede/parsing. Não reproduziu nos outros 37 chunks do
mesmo edital nem no piloto anterior — é não-determinismo do LLM,
aparentemente mais provável em matérias com listas numeradas longas
(comum em conteúdo de Contabilidade/Direito).
**Como identificar rápido:** um chunk com `status="sucesso"` mas **todos**
os `topico["nome"]` sendo só dígitos é o padrão — `grep`/filtro por
`topico.nome.isdigit()` no `<edital>.json` isola o problema sem precisar
reler o texto inteiro do chunk.
**Corrigido (ADR-021):** reparo local determinístico em
`src/taxonomia_extractor.py` — o texto-fonte já tem o item completo pra
cada numeral, mapeado pela mesma extração de itens numerados que
`validar_taxonomia.py` usa (`extrair_itens_numerados`, movida pra
`src/edital_parser.py`). Zero chamada nova ao LLM, determinístico,
rastreável por log (`[REPARO_NOME_NUMERICO]`) e metadata no Langfuse.
Um retry cego reaproveitando o loop genérico foi a primeira versão
implementada e foi descartado antes de fechar: repetir a mesma chamada sem
contexto do erro não garante correção e não deixa rastro distinto de um
retry por falha de rede. Prompt reforçado (mitigação na origem) e um
quinto tipo de alerta passivo (`topico_nome_numerico`, aditivo) somam
defesa em profundidade para dado já persistido antes do fix ou caso o
reparo não cubra. `scripts/reprocessar_falhas_piloto.py` ganhou `--chunks
17,21` pra forçar reprocessamento por `chunk_index` mesmo com
`status="sucesso"`, usado pra corrigir os 2 chunks já malformados em
disco. Ver ADR-021.
**Custo do aprendizado:** ~15 min, comparando a distribuição de alertas por
`chunk_index` (`Counter` sobre `.validacao.json`) contra o `.json` de
resultado — a causa fica óbvia assim que se olha `topico["nome"]` do chunk
concentrando os alertas.

### [tags: llm-extraction, openrouter, langfuse, observabilidade, exceptions]
**Sintoma:** Chunks com falha na inferência do LLM eram marcados indistintamente com `status="falha"` no `.auditoria.json`, relatório HTML e Datasette, impedindo distinguir instabilidades transitórias de rede de problemas estruturais de resposta.
**Causa:** `_chamar_llm_uma_vez` capturava qualquer falha de rede sob um `except requests.RequestException` genérico e agrupava erros de decodificação JSON e validação Pydantic sob o mesmo tratamento que devolvia `None`. Isso mascarava a causa-raiz (timeout, rate-limit 429, queda de conexão, truncamento de tokens por corte de output, ou schema inválido retornado pelo modelo).
**Solução (ADR-022):** Encadeamento de exceções da mais específica para a mais genérica com códigos de status persistidos explícitos (`falha_timeout`, `falha_conexao`, `falha_rate_limit`, `falha_http`, `falha_rede`, `falha_conteudo_vazio`, `falha_parse_json`, `falha_validacao_schema`, `falha_nome_numerico_nao_mapeado`). Centralização via `_falha_chamada` com tags de log greppáveis `[FALHA_*]` e injeção do campo estruturado `metadata["tipo_erro"]` nos eventos do Langfuse.
**Custo do aprendizado:** ~20 min para estruturação da taxonomia de exceções e cobertura completa por testes unitários em `tests/test_taxonomia_extractor.py`.

### [tags: playwright, scraping, cebraspe]
**Sintoma:** O filtro de concursos de 2025 em `spider.py`
(`re.search(r'2025', text)` sobre o texto do link) retorna lista vazia,
sem lançar nenhum erro.
**Causa:** O texto visível de todo card de concurso na listagem do CEBRASPE
é sempre "MAIS INFORMAÇÕES" — o ano nunca aparece no texto do link. O ano
está no **slug da URL**, como sufixo de 2 dígitos (ex:
`/concursos/TJ_CE_25_NOTARIOS` → 2025; `/concursos/ADEAL_26` → 2026).
**Solução:** Extrair o ano via regex sobre o slug da URL (padrão
`_(\d{2})(_|$)`), nunca sobre o texto do link.
**Custo do aprendizado:** Achado antes de rodar em produção, via verificação
ao vivo com Playwright (~15 min) — mas o gotcha é traiçoeiro porque a falha
é *silenciosa* (0 resultados, sem exceção), fácil de não notar sem inspecionar
a contagem manualmente.

### [tags: playwright, scraping, cebraspe]
**Sintoma:** Crawlear apenas `https://www.cebraspe.org.br/concursos/`
(raiz) capturava só 80 links de concurso.
**Causa:** A listagem do CEBRASPE é dividida em abas por status
(`/concursos/novos`, `/concursos/inscricoes-abertas/`,
`/concursos/em-andamento/`, `/concursos/encerrado`), cada uma em URL própria;
a raiz não agrega todo o histórico. `/concursos/encerrado` sozinho já tem 423
concursos, sem paginação/infinite-scroll (todos os links já vêm no DOM num
único load).
**Solução:** Usar `/concursos/encerrado` como fonte primária — é onde estão
os concursos já realizados, que têm Prova e Gabarito publicados (o objetivo
do crawler).
**Custo do aprendizado:** ~10 min, verificação exploratória ao vivo.

### [tags: python, regex, scraping]
**Sintoma:** Regex `\b(INSS|PF|...)\b` aplicada sobre um slug como
`INSS_25` não dá match, mesmo com "INSS" claramente presente no início da
string.
**Causa:** `\b` marca fronteira entre um caractere de palavra (`\w`, que
inclui letras, dígitos **e underscore**) e um não-`\w`. Como `_` é `\w`,
não existe fronteira entre `INSS` e `_25` — o `\b` depois de `INSS` nunca
dispara em slugs delimitados por underscore.
**Solução:** Dividir o slug em segmentos (`re.split(r'[_\-]', slug)`) e
comparar cada segmento contra um set de keywords, em vez de tentar casar
fronteira de palavra direto na string com underscore.
**Custo do aprendizado:** ~5 min — pego durante teste unitário manual antes
de rodar contra o site real; o gotcha é o tipo de erro silencioso (sem
exceção, só "nunca prioriza nada") que só aparece inspecionando o resultado.

### [tags: playwright, scraping, cebraspe, href]
**Sintoma:** `get_contest_links` retorna lista vazia contra o site real
(0 concursos), mesmo depois de todas as correções da Etapa 2 (filtro de
ano, `/concursos/encerrado`, priorização) já estarem certas e cobertas por
lições anteriores. `task.md`/`CLAUDE.md` marcavam a Fase 2 como concluída
sem que ninguém tivesse rodado o crawler ponta a ponta contra o DOM real
depois da última alteração.
**Causa:** Os cards da listagem usam `href` **relativo**
(`/concursos/PF_25_ADM`), não absoluto. `element.get_attribute("href")`
devolve o atributo cru do HTML — ele NÃO resolve contra a URL da página,
ao contrário da propriedade `.href` do DOM (que o browser resolve
automaticamente). O filtro `href.startswith("https://www.cebraspe.org.br/concursos/")`
comparava um path relativo contra uma URL absoluta e nunca dava match —
100% dos 424 cards descartados, silenciosamente, sem exceção.
**Solução:** Resolver o href antes de comparar:
`href = urljoin(page.url, raw_href)`. Funciona tanto para href relativo
quanto absoluto (idempotente se já for absoluto).
**Custo do aprendizado:** ~20 min — só apareceu numa auditoria dedicada que
rodou `get_contest_links` de verdade contra o site (não só as funções
puras de extração de slug/ano/órgão, que já tinham teste unitário e
passavam). **Lição maior:** testar unitariamente `extract_year_from_slug`,
`extract_orgao_from_slug` etc. isoladamente não garante que o crawler
funciona ponta a ponta — o bug estava no ponto de entrada
(`get_contest_links`), não em nenhuma das funções já testadas. Uma tarefa
"corrigir o crawler" só deve ser marcada `[x]` depois de rodar o método
público (`get_contest_links`/`run`) contra o site real, não só as funções
auxiliares que ele chama.

### [tags: pymupdf, regex, parsing, cebraspe, edital]
**Sintoma:** No chunking de `edital_parser.py`, 1 chunk (matéria
"MATEMÁTICA FINANCEIRA") saiu com 41850 chars — quase 55% da seção inteira
de "OBJETOS DE AVALIAÇÃO" (76334 chars) — enquanto os outros 17 chunks
tinham entre 400 e 3700 chars. Nenhum erro, nenhuma exceção; só um número
visualmente absurdo.
**Causa:** O regex de cabeçalho de matéria só aceitava letras/espaço/hífen
(`[A-ZÀ-Ú /\-]`). Dois formatos reais de cabeçalho no mesmo edital não
batiam: `CARGO 7: MÉDICO CLÍNICO` (tem dígito) e `ADMINISTRAÇÃO FINANCEIRA,
ORÇAMENTÁRIA E ORÇAMENTO PÚBLICO:` (tem vírgula) — e também
`ATUALIDADES (SOMENTE PARA A PROVA DISCURSIVA):` (tem parênteses). Como
"MATEMÁTICA FINANCEIRA" foi o último cabeçalho reconhecido antes de um
trecho de ~14 cargos de especialidade médica (cada um com cabeçalho
`CARGO N: <especialidade>`, todos invisíveis pro regex), o chunk dela se
estendeu por engano até o próximo cabeçalho que o regex *conseguia* ver.
**Solução:** Ampliar a classe de caracteres para `[A-ZÀ-Ú0-9 /,()\-]` e
tratar `CARGO N: <nome>` como um tipo de marcador à parte (não uma matéria),
com `(?!CARGO \d)` no regex de matéria pra não colidir com ele. O chunking
final ficou em dois níveis (cargo + matéria), porque alguns cargos (ex:
especialidades médicas) não têm matéria nomeada à parte — o cabeçalho do
próprio cargo já é o rótulo do conteúdo programático.
**Custo do aprendizado:** ~25 min — só apareceu ao imprimir o tamanho de
cada chunk lado a lado e notar o outlier (nenhum teste unitário isolado
pegaria isso sem uma amostra real do PDF; um teste sintético "bonito" com
poucos cabeçalhos não reproduz a variedade de formatos que aparece no
edital de verdade). **Lição maior:** ao validar um parser/chunker contra
PDF real, sempre imprimir a distribuição de tamanhos dos chunks (não só a
contagem) — um chunk desproporcionalmente grande é o sintoma mais barato de
detectar de um cabeçalho perdido silenciosamente.

### [tags: llm, litellm, reasoning-model, glm]
**Sintoma:** Chamada ao LiteLLM (`glm-5.3-flash`) com `max_tokens` baixo
(ex: 10) volta HTTP 200, sem erro, mas `choices[0].message.content` é
`None` — só `reasoning_content` vem preenchido, e `finish_reason` é
`"length"`.
**Causa:** `glm-5.3-flash` é um modelo de raciocínio — parte do orçamento
de `max_tokens` é consumida por um bloco de `reasoning_content` interno
*antes* da resposta final em `content`. Com um teste trivial ("responda
apenas: ok", `max_tokens=10`), os 10 tokens inteiros foram gastos em
reasoning, sem sobrar nada pro `content`. Com `max_tokens=200`, o mesmo
prompt gastou 108 tokens de reasoning e só então respondeu "ok" (102
tokens usados no total). Um chunk real de edital gastou ~700 tokens de
reasoning antes do JSON final.
**Solução:** Nunca usar um orçamento de tokens baixo para este modelo —
`max_tokens=8192` (mesmo valor já usado no `study-rag-agent` para
extração), e tratar `content=None`/vazio como falha explícita da chamada
(não deixar `json.loads(None)` estourar uma exceção genérica).
**Custo do aprendizado:** ~10 min — descoberto testando a integração
isoladamente antes de escrever o parsing da resposta, o que evitou
confundir esse comportamento com um bug de parsing.

### [tags: cebraspe, pdf-parsing, modelagem]
**Sintoma:** Ao validar manualmente os PDFs baixados de PF/2025, apareceram
`094_PF_CB1_01.pdf` e `094_PF_CB2_01.pdf` — duas provas objetivas de
Conhecimentos Básicos no mesmo concurso, uma para os cargos 1–14 e outra só
para o cargo 15. A suposição inicial (1 prova objetiva por concurso) estava
errada.
**Causa:** O CEBRASPE agrupa Conhecimentos Básicos por cargos de mesmo
nível/perfil, gerando N cadernos "CBx" por concurso. O texto que identifica
isso ("PROVA OBJETIVA - CONHECIMENTOS BÁSICOS PARA O CARGO 15") **não existe
dentro do conteúdo do PDF** — confirmado inspecionando todas as páginas de
`094_PF_CB1_01.pdf`/`094_PF_CB2_01.pdf` com PyMuPDF (nem no texto, nem nos
metadados). Só existe no texto do link na página do concurso. Achado
relacionado: o gabarito da prova discursiva usa "PADRÃO DE RESPOSTA
DEFINITIVO" no link, nunca a palavra "GABARITO".
**Solução:** `map_pdf_links` guarda `{"url": ..., "texto": ...}` por prova
em vez de só a URL — o texto do link precisa ser capturado no momento do
crawl (Etapa 2), não reconstruído depois a partir do PDF (Etapa 4).
`download_concurso_pdfs` repassa esse texto para
`<concurso_dir>/provas_texto_link.json` (chave = nome do arquivo). Modelagem
cargo↔prova em `models_scraper.py` (`ProvaObjetiva.cargos_numeros`) trata
Conhecimentos Básicos como N:1 (compartilhado por grupo de cargos) e
Conhecimentos Específicos/Discursiva como 1:1. Ver decisão em `CLAUDE.md`
(seção 12).
**Custo do aprendizado:** ~30 min, repetido **duas vezes** na mesma sessão —
a primeira aplicação desse fix (em `spider.py`/`models_scraper.py`) foi
perdida entre uma conversa e outra porque este projeto nunca foi commitado
em git (diretório inteiro `untracked`) e existe uma worktree separada
(`worktree-scraper-cebraspe-etapa3`) com trabalho concorrente da Etapa 2/3
que aparentemente sobrescreveu os arquivos sem levar a mudança junto.
**Lição de processo:** commitar este projeto assim que possível — sem
histórico de git, uma correção já feita pode ser silenciosamente desfeita
por outra sessão/worktree mexendo nos mesmos arquivos.

### [tags: cebraspe, idempotencia, orquestracao]
**Sintoma:** Usuário rodou `python -m src.spider` e perguntou "o script vai
rodando e faz o que depois?" — suspeita correta: nada. `run()` mapeava os
PDFs de cada concurso, logava as contagens e marcava o slug como
"processado" em `data/processed_concursos.json`, mas nunca chamava
`download_concurso_pdfs`. Nenhum PDF era efetivamente baixado.
**Causa:** A Etapa 2 (crawler) foi escrita/testada isoladamente da Etapa 3
(downloader) e nunca foram ligadas dentro de `run()`. Como `mark_processed`
rodava de qualquer forma, o registro de idempotência achava que 12
concursos já tinham sido processados quando zero PDFs existiam pra eles em
disco — só `PF_25_ADM` tinha download real (feito antes da idempotência
existir). Sem essa auditoria, esses 12 seriam pulados silenciosamente para
sempre, mesmo depois de ligar o downloader.
**Solução:** `run()` agora chama `download_concurso_pdfs` e só marca como
processado depois do download rodar (nunca antes de tentar). Registro
`processed_concursos.json` limpo manualmente para conter só o slug com
download real.
**Custo do aprendizado:** ~20 min — exigiu comparar o registro JSON contra
o conteúdo real de `data/` (via `extract_orgao_from_slug` + `slugify`) para
confirmar quais dos 13 slugs tinham pasta de fato.

### [tags: llm, litellm, reasoning-model, glm, extractacao, retry, max-tokens]
**Sintoma:** Extração de 39 chunks de edital via `glm-5.3-flash` com
`max_tokens=8192` e LiteLLM falhou repetidamente: todas as respostas voltavam
com `finish_reason="length"`, `content=None`, log mostrando "possivelmente
max_tokens insuficiente para o reasoning do glm-5.3-flash". Nenhum chunk
conseguiu completar validação contra `TaxonomiaEdital` do Pydantic.
**Causa:** `glm-5.3-flash` é modelo de raciocínio; lição anterior já
documentava que "parte do orçamento de `max_tokens` é consumida por
`reasoning_content` interno". Mas foi validada com prompts triviais ("responda
apenas: ok"). Um chunk real de edital (~700 chars conteúdo programático)
requer ~700+ tokens de reasoning *sozinhos* — total >1400 tokens só para
processar. Com `max_tokens=8192` total de budget, reasoning consume a maior
parte, deixando <1000 para `content` final (JSON estruturado) → chega a
`finish_reason="length"` e `content=None`.
**Solução (VALIDADA ao vivo, 2026-09-20):** Dois runs reais completos contra
os 39 chunks do edital piloto (2026-09-19 e 2026-09-20) confirmaram que a
falha é **majoritariamente não-determinística** — comparando os dois runs
chunk a chunk, só 2 das 5 falhas de cada run coincidiam; 3 falhas de um run
tinham tido sucesso no outro, mesmo texto, mesmo `temperature=0.1`. Isso
tornou **retry com backoff** (3 tentativas, 5s/15s) o fix de maior retorno,
implementado em `extrair_taxonomia_chunk`
(`src/taxonomia_extractor.py`).
Rodado também um experimento controlado (`scripts/experimento_falhas_llm.py`,
2026-09-20) nos 5 chunks que falharam no run de 20/09, comparando 4
configs isoladas (1 tentativa cada, sem retry, pra isolar o efeito):
`baseline` (8192/120s) 2/5 sucesso; `max_tokens=24576,timeout=240s` **5/5**;
`thinking: {"type":"disabled"}` 3/5 (mesmo chunk falhou com a MESMA
assinatura de erro ligado e desligado — indício forte de que o z-ai/
OpenRouter **ignora** esse parâmetro pass-through do LiteLLM, não confiar
nele como mitigação); `thinking:disabled` + texto sem nota de retificação
4/5. Também achado nesse experimento: pro chunk maior (6977 chars,
PSICÓLOGO ORGANIZACIONAL), a falha não era só reasoning — o `content` (JSON)
em si veio cortado no meio (`json.JSONDecodeError: Unterminated string`,
~7510 chars) com `max_tokens=8192`, ou seja o teto também é insuficiente
pro output final em chunks grandes, não só pro reasoning. `MAX_TOKENS=24576`
e `REQUEST_TIMEOUT=240` adotados como novo default de produção. Ver
CLAUDE.md seção 12 pro racional completo.
**Custo do aprendizado:** ~15 min diagnóstico inicial (2026-09-19) + ~1h
entre implementação de retry/parametrização, experimento controlado (20
chamadas reais) e análise dos resultados (2026-09-20).

### [tags: llm, extracao, taxonomia, validacao, unicode, regex]
**Sintoma:** Primeira versão de `scripts/validar_taxonomia.py` (diff por
**número** de item entre texto-fonte e `topico["nome"]` extraído) gerou 385
alertas de "tópico ausente" contra o edital piloto (39 chunks) — um número
absurdamente alto pra uma extração já auditada como 39/39 sucesso. Depois de
trocar pra comparação por **texto normalizado**, o número caiu mas ainda
oscilou 37 → 81 → 6 alertas a cada tentativa de correção, sinal de que cada
fix estava caçando o sintoma errado.
**Causa (três bugs empilhados, cada um mascarando o próximo):**
1. O prompt de `taxonomia_extractor.py` pede pro LLM preservar a numeração
   original do edital em `topico["nome"]`, mas ele **não obedece
   consistentemente** — no mesmo edital, chunk 0 preserva `"1 Compreensão..."`
   e o chunk seguinte devolve só `"Estruturas lógicas"`, sem número. Um diff
   por número sozinho é inútil — precisa comparar pelo **texto** do tópico,
   com o número (quando existe) descartado dos dois lados antes de comparar.
2. Ao extrair o "rótulo" de cada item numerado do texto-fonte, cortar na
   primeira "." (pra descartar subitens) trunca citações legais embutidas no
   próprio rótulo (`"Lei nº 8.429/1992 (Lei de improbidade administrativa)."`
   virava só `"Lei nº 8"`) — qualquer matéria de Direito/Ética tem isso.
   Solução: comparar contra o texto **completo** do item (via substring),
   nunca cortar na primeira pontuação.
3. O regex de normalização (`unicodedata.normalize("NFKD", ...).encode("ascii",
   "ignore")`) **descarta silenciosamente** caracteres não-ASCII sem
   decomposição, incluindo hífen tipográfico Unicode (`‐`, U+2010, comum em
   PDF extraído) — `"ético‐político"` virava `"eticopolitico"` (colado, sem
   espaço), enquanto o hífen ASCII `-` do texto extraído pelo LLM virava
   `"etico politico"` (espaçado) na mesma normalização. Substrings deixavam
   de bater por causa de um caractere invisível. Fix: trocar qualquer
   não-alfanumérico (`[^\w]`, Unicode-aware) por espaço **antes** de
   derrubar acento, nunca depois.
   Bônus: números de item podem se **repetir** dentro do mesmo chunk quando
   o texto do PDF vem corrompido (achado real no chunk "TÉCNICO EM
   COMUNICAÇÃO SOCIAL": um "1" duplicado no meio do texto por artefato de
   extração) — destacar/rastrear pelo **número** sozinho marca as duas
   ocorrências; precisa da **posição** do item na ordem de aparição pra
   desambiguar.
**Solução:** `normalizar()` em `validar_taxonomia.py` remove pontuação
Unicode-aware antes do fold de acento; comparação usa substring do texto
completo do item (não um rótulo cortado); alertas carregam `posicao_item`
(índice de aparição), não só `numero_item`, pra apontar sem ambiguidade a
ocorrência exata. Resultado final no edital piloto: 2 alertas genuínos (um
LLM que consolidou 2 itens duplicados do próprio edital num tópico só;
um artefato real de corrupção de texto no PDF-fonte) — nenhum falso positivo
de normalização.
**Custo do aprendizado:** ~40 min, iterando contra dados reais (`revisao_piloto/`)
a cada ajuste em vez de só ler o código — o bug do hífen Unicode em
particular só apareceu comparando a normalização das duas strings char a
char, não seria visível revisando o regex isoladamente.

### [tags: cebraspe, edital, parsing, modelagem, taxonomia]
**Sintoma:** No edital piloto (`PF_25_ADM`), os chunks 0 e 6 saíam idênticos
em tudo, menos no texto: `cargo=None`, `materia="LÍNGUA PORTUGUESA"`. O mesmo
valia para Raciocínio Lógico, Ética e Informática. Nenhum erro: a taxonomia
parecia completa, mas era impossível filtrar "Português de nível médio".
**Causa:** O edital agrupa as matérias em blocos `CONHECIMENTOS BÁSICOS/
ESPECÍFICOS PARA OS CARGOS DE NÍVEL SUPERIOR/MÉDIO`, e o bloco básico repete
os mesmos nomes de matéria em cada nível, com conteúdo diferente. O chunking
(cargo + matéria) ignorava esses cabeçalhos. "Básico" só era inferível pela
convenção `cargo=None`, e o nível não aparecia em lugar nenhum. Os
cabeçalhos ainda grudavam na cauda do chunk anterior como ruído.
**Solução:** Cabeçalho de bloco virou um terceiro tipo de marcador
(`PADRAO_BLOCO`), que define `tipo_conhecimento`/`nivel` e zera o cargo
corrente. Bloco sem nível único vira `nivel=None` + alerta, nunca some. O
concurso vem do manifesto do downloader: a pasta em disco é por órgão, não
por concurso. Como tudo vem do parser, o piloto foi completado por backfill
sem chamar o LLM. Ver ADR-020.
**Custo do aprendizado:** ~20 min. **Lição maior:** nome de matéria não é
identificador. Qualquer chave de taxonomia precisa de
`(concurso, tipo_conhecimento, nivel, cargo, materia)`. Ao validar chunking,
procurar pares `(cargo, materia)` duplicados é tão barato quanto olhar a
distribuição de tamanhos e pega esse tipo de colisão.

### [tags: langfuse, observabilidade, deprecacao, credenciais]
**Sintoma:** Chamadas de ingestão de telemetria pareciam funcionar normalmente nos scripts e testes, mas os traces não refletiam atualizações esperadas ou falhavam em silêncio. Além disso, a API de ingestão retornava aviso de depreciação que passava despercebido.
**Causa (dois problemas combinados):**
1. O uso de `requests.post(..., timeout=5)` e `httpx.AsyncClient.post` sem verificação de status code (`response.raise_for_status()` ou `if not resp.ok: logger.warning(...)`) tratou qualquer resposta HTTP (inclusive 401 Unauthorized decorrente de rotação de credenciais) como sucesso do envio, mascarando completamente falhas de autenticação.
2. A API REST v3 de ingestão (`POST /api/public/ingestion`) emitiu no corpo da resposta o aviso de sunset programado para 2026-11-16 (quando passará a aceitar exclusivamente eventos de score e recusará traces e generations). Sem ler o corpo das respostas de telemetria, o aviso só foi descoberto em inspeção ativa de depuração de rede.
**Solução:**
1. Migração definitiva para o SDK oficial `langfuse>=3,<4` (OTel, ADR-023), que gerencia internamente retries, autenticação, threads de exportação e flush em `atexit`.
2. Em qualquer código de telemetria ou cliente HTTP que envolva ingestão secundária, nunca descartar status HTTP de resposta silenciosamente.
**Custo do aprendizado:** ~15 min de diagnóstico e validação ao vivo com a API do Langfuse Cloud.


### [tags: llm-extraction, taxonomia, validacao, cebraspe]
**Sintoma:** Depois de zerar o ruído heurístico, sobraram 3 alertas em 150 chunks, e cada um tinha uma causa diferente: o LLM **omitiu** um item (IBAMA, `1 IN Ibama 05/2021.`), **desambiguou** o nome de um item que o edital repete (PF, `Educação corporativa (atuação do pedagogo)`) e **corrigiu** um erro de digitação do PDF (STM, `bBiblioteca Flyway`).
**Causa:** "Alerta de validação" misturava duas coisas: perda real de dado e divergência explicável entre fonte e extração. O LLM tende a pular item curto que é só sigla ou norma, e a "melhorar" a fonte (desambiguar, corrigir).
**Solução (ADR-025):** Reinjeção determinística do item omitido a partir do texto-fonte (sem LLM, só item simples) e severidade `informativo` para paráfrase leve (parêntese acrescentado, similaridade ≥ 0,92), visível mas fora de `total_alertas`. A comparação textual (`src/comparacao_texto.py`) é a mesma no reparo e no validador.
**Pegadinha na implementação:** o casamento tolerante por parêntese, se comparado contra o **texto-fonte inteiro**, deixa um tópico parafraseado de um item "cobrir" a omissão de **outro** item do mesmo chunk. Nas checagens por item, compare só contra o texto daquele item (há teste pra isso).
**Achado lateral:** os 5 editais de 2025 terminam a seção com a assinatura (nome + cargo) colada no último item, em 4 formatos diferentes. Ancorar a remoção no **cargo** do signatário no fim do texto, não no nome em caixa alta: o STM tem nome sem caixa alta e o PF tem o nome na mesma linha do último item.
**Custo do aprendizado:** ~40 min. **Lição maior:** antes de automatizar o tratamento de alertas, classificar cada um por "o dado está errado?". Consertar dado e rebaixar severidade são respostas diferentes para perguntas diferentes.

### [tags: llm, glm, sinonimos, validacao, pydantic, lista-fechada]
**Sintoma:** na proposta de sinônimos (Etapa 5B), um lote de 74 assuntos
falhou duas vezes com `falha_validacao_schema` ("72 validation errors"),
com o JSON bem formado e todos os IDs certos.
**Causa:** o prompt pedia `nome_canonico` em todo grupo, mas o
`glm-5.3-flash` omite o campo nos grupos de 1 ID (sem sinônimo, não vê o que
nomear). Com o campo obrigatório no Pydantic, um detalhe cosmético derrubou
o lote inteiro, e a segunda tentativa repetiu o comportamento.
**Solução:** campo opcional no schema e nome determinístico (o da regra)
quando falta num grupo de 2+ IDs. O que importa para a validação (cada ID
em exatamente um grupo) continua estrito. Achado junto: proposta de
assunto/subassunto que junta nomes **iguais** de matérias diferentes fica
redundante quando o dono aprova a matéria (a regra junta sozinha), então a
reexecução das regras a remove e o relatório avisa.
**Lição:** em schema de resposta de LLM, obrigatório só o que a validação
precisa; o resto tem default. Campo obrigatório "de conveniência" vira
falha de lote inteiro.
**Custo do aprendizado:** ~15 min, mais uma reexecução do nível de assunto
(4 chamadas, US$ 0,0024).

### [tags: prova-parser, segmentacao, recuo, cebraspe, pdf-parsing]
**Sintoma:** Em cadernos com diagramação de 1 coluna (ex: `094_PF_007_01`), itens com enunciado de apenas 1 linha física (itens 55 e 62) engoliam a primeira linha do texto-base seguinte ("Um paciente de 66 anos de idade...").
**Causa:** A função `_recuo_item` media o deslocamento da linha seguinte aceitando qualquer delta entre `8 < delta < 30`. Quando o item tinha apenas 1 linha física, ela media o delta da 1ª linha do texto-base seguinte (~28.3 pt), capturando o recuo de parágrafo como se fosse recuo de continuação do item.
**Solução (ADR-031):** Calibrar a janela de medição de `_recuo_item` para a faixa estrita de `12 < delta < 24 pt` (~18 pt real no CEBRASPE), mantendo uma margem segura de separação em relação ao recuo de parágrafo (~28–29 pt) de textos-base.
**Custo do aprendizado:** ~20 min entre inspeção geométrica, teste de regressão em `TestSegmentacao` e reprocessamento completo.

### [tags: prova-parser, gabarito-parser, pymupdf, hash-url, ordem-visual]
**Sintoma:** Gabaritos com nomes em hash (TCU e Câmara dos Deputados) baixados pelo crawler não traziam o código do caderno no nome do arquivo nem na URL; e o fluxo interno de objetos retornado pelo PyMuPDF não seguia a ordem de leitura em cadernos de duas colunas.
**Causa:** Os servidores do CEBRASPE usam hashes aleatórios em links de download de certos gabaritos; no PDF de prova, a ordem dos blocos nos bytes brutos reflete a ordem em que foram gerados no software de diagramação, não a ordem geométrica visual.
**Solução (ADR-031):**
1. O leitor de gabaritos extrai o código impresso do caderno (`108_TCUTEFC_...`, `167_CDNS_...`) diretamente do conteúdo do PDF, vinculando 100% dos gabaritos com provas sem depender da URL.
2. O parser de provas implementa segmentação geométrica em colunas e ordena por `(coluna, y0, x0)` antes de recortar itens por span tipográfico.
3. Cadernos geram 140 arquivos JSON em `questoes/` mantidos localmente (gitignored por volume), garantindo reprodutibilidade determinística sem sobrecarregar o git.
**Custo do aprendizado:** ~35 min no desenvolvimento e validação dos 70 cadernos reais.

### [tags: gabarito-parser, discursivas, cebraspe, regex, definitivo]
**Sintoma:** Dois riscos de falso positivo identificados na revisão da Etapa 5C
(nenhum afetou os dados reais: os 70 gabaritos/padrões coletados são todos
definitivos e os 107 quesitos não mudaram):
1. O padrão de resposta definitivo do cargo 2 da PF cita "definitivo" no corpo
   ("o diagnóstico precoce, ainda que não definitivo"). Uma busca solta pela
   palavra no texto inteiro classificaria como definitivo um padrão
   preliminar com a mesma redação.
2. Confirmado com entrada sintética: no caderno discursivo, uma linha do
   enunciado que comece com "1 " (ex.: "1 de janeiro...") virava o quesito 1,
   o "1" real era engolido e a soma de `[valor]` continuava batendo, então
   `soma_quesitos_divergente` não disparava.
**Causa:**
1. A palavra "definitivo" aparece tanto no cabeçalho do documento quanto no
   conteúdo técnico da resposta.
2. `PADRAO_QUESITO` casa qualquer linha que comece com 1–2 dígitos e era
   aplicado ao bloco inteiro da questão, incluindo o enunciado antes do
   comando.
**Solução (ADR-031):**
1. `classificar_versao` olha só o cabeçalho (primeiros 600 caracteres no
   padrão de resposta, 2000 na grade), com fallback pelo prefixo do nome do
   arquivo (`Gab_Definitivo_` / `Gab_Preliminar_`); nunca aceita match solto
   no corpo.
2. Quesitos só são procurados a partir do verbo de comando (`redija`,
   `elabore`, `aborde`, `discorra`, etc.).
**Custo do aprendizado:** ~25 min em auditoria e testes sintéticos (o risco
não gerou retrabalho em dados).
