# Coleta e download de arquivos

Mecanismos de raspagem (crawler/spider Playwright) e download com validação e deduplicação de editais, cadernos de prova e gabaritos.

**Para que serve:** Descrever a lógica do crawler, as duas camadas de deduplicação, o controle de inventário e os filtros de exclusão. **Quando ler:** Antes de alterar seletores de navegação, rotinas de download de PDFs ou regras de inventário.

## Crawler e Spider com Playwright

O spider adota a URL `/concursos/encerrado` do portal CEBRASPE como ponto de partida primário da navegação. A listagem de encerrados reúne o ciclo documental completo dos certames já finalizados (editais de abertura, cadernos de prova aplicados e gabaritos oficiais), ao contrário da raiz `/concursos/`, na qual predominam certames em andamento sem provas disponíveis ([ADR-002](../adr/ADR-002-fonte-primaria-concursos-encerrados.md)).
Fonte: src/spider.py:280-286

Na varredura dos elementos HTML dos cards de concurso, o atributo `href` obtido via `get_attribute("href")` retorna o caminho relativo bruto emitido pelo servidor (como `/concursos/SLUG`). Toda URL é resolvida contra a URL da página corrente por meio de `urljoin(page.url, raw_href)` antes de qualquer comparação de prefixo, eliminando o descarte silencioso de links que ocorreria ao comparar caminhos relativos contra URLs absolutas ([ADR-008](../adr/ADR-008-resolucao-href-relativo.md), [P11](../tecnico/regras.md#p11), [A01](../tecnico/regras.md#a01)).
Fonte: src/spider.py:298-306

Como os botões dos cards de concurso exibem invariavelmente o texto genérico "MAIS INFORMAÇÕES", a filtragem temporal e a extração do órgão não utilizam o texto visível do link. O ano de aplicação (`_YY` ou `_YYYY`) e o prefixo do órgão são extraídos diretamente do slug da URL por meio da regex `PADRAO_ANO_SLUG` e da função `extract_orgao_from_slug`, assegurando identificação determinística sem necessidade de requisições HTTP adicionais ([ADR-001](../adr/ADR-001-filtro-ano-slug-url.md), [ADR-006](../adr/ADR-006-extracao-orgao-slug.md), [P01](../tecnico/regras.md#p01), [P08](../tecnico/regras.md#p08), [A02](../tecnico/regras.md#a02)).
Fonte: src/spider.py:86-121

A ordenação do processamento prioriza concursos de órgãos de grande porte definidos em `PRIORITY_KEYWORDS` (tais como PF, PRF, INSS, TCU). A identificação desses termos é realizada dividindo o slug em segmentos delimitados por sublinhado ou hífen, prevenindo falhas de casamento de fronteira de palavra (`\b`) causadas pela presença de caracteres alfanuméricos contíguos ao sublinhado ([ADR-004](../adr/ADR-004-priorizacao-cargo-slug.md), [P06](../tecnico/regras.md#p06)).
Fonte: src/spider.py:41-64

Ao navegar para a página de cada certame, o crawler inspeciona todas as tags `<a>` com extensão `.pdf`, resolvendo os endereços relativos e catalogando os arquivos entre editais de abertura, provas e gabaritos por meio de `classificar_link_pdf`. Concursos presentes na lista de exclusões manuais ou documentos associados a cursos de formação têm sua coleta ignorada nessa etapa ([ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md), [P31](../tecnico/regras.md#p31)).
Fonte: src/spider.py:357-430

O fluxo de execução preserva o isolamento de falhas: o tratamento de cada concurso opera dentro de blocos protegidos de exceção, impedindo que falhas de rede ou parsing em um certame específico interrompam o lote inteiro ([P02](../tecnico/regras.md#p02), [A03](../tecnico/regras.md#a03)). A idempotência é controlada pelo arquivo local `data/processed_concursos.json`, no qual o slug é registrado exclusivamente após a conclusão bem-sucedida do download de todos os seus arquivos físicos ([ADR-005](../adr/ADR-005-idempotencia-registro-json.md), [ADR-013](../adr/ADR-013-ligacao-spider-downloader.md), [P07](../tecnico/regras.md#p07)).
Fonte: src/spider.py:456-470

## Downloader de Arquivos PDF

O download dos arquivos PDF é totalmente desacoplado da sessão do navegador Playwright, sendo executado de forma síncrona por meio de requisições HTTP diretas via biblioteca `requests`. Essa arquitetura economiza memória e processamento, utilizando User-Agents rotativos e intervalos orgânicos de espera (`stealth_wait`) entre requisições.
Fonte: src/downloader.py:160-169

A integridade do documento é verificada no conteúdo binário bruto por meio da função `_is_valid_pdf`, que exige a presença dos magic bytes `%PDF-` no início do fluxo recebido. Esse teste impede que respostas com status HTTP 200 contendo páginas HTML de erro, redirecionamentos ou telas de bloqueio sejam salvas como PDFs no disco ([P09](../tecnico/regras.md#p09)).
Fonte: src/downloader.py:76-95

O mecanismo opera com deduplicação em duas camadas antes de efetivar o salvamento em disco. Na Camada 1, o downloader verifica se a URL de origem já se encontra registrada no manifesto local `.manifest.json` com arquivo existente; na Camada 2, calcula o hash SHA-256 do fluxo binário e, caso o conteúdo já exista sob outro nome de arquivo, reaproveita o arquivo físico previamente salvo, desambiguando nomes colidentes com um sufixo do hash ([ADR-007](../adr/ADR-007-dedup-download-dupla-camada.md), [P10](../tecnico/regras.md#p10)).
Fonte: src/downloader.py:146-204

Durante a gravação das provas, o texto descritivo original do link HTML é persistido no arquivo auxiliar `provas_texto_link.json`, preservando informações sobre cargos e cadernos (como `CB1`, `CB2`, `DISC`) para o processamento das etapas subsequentes. Adicionalmente, o downloader escolhe o edital canônico de abertura para posterior extração pelo LLM via `escolher_edital_extracao`, registrando os metadados do documento vencedor diretamente no `.manifest.json`.
Fonte: src/downloader.py:221-269

## Organização do Sistema de Arquivos

Os arquivos baixados são distribuídos no sistema de arquivos seguindo a estrutura padronizada `data/<ano>/CEBRASPE/<orgao_slug>/{Editais,Provas,Gabaritos}/`. Cada categoria possui diretório próprio sob a pasta do órgão correspondente ao certame.
Fonte: src/downloader.py:221-232

A nomenclatura das pastas dos órgãos é normalizada de forma determinística pela função `slugify`. O procedimento decompõe caracteres acentuados na forma NFKD, remove caracteres especiais não alfanuméricos e converte o texto para maiúsculas, garantindo que certames do mesmo órgão convirjam para o mesmo caminho físico de diretório ([P03](../tecnico/regras.md#p03)).
Fonte: src/downloader.py:46-58

Como concursos distintos do mesmo órgão e ano compartilham o mesmo diretório em disco, o caminho do arquivo não é suficiente para determinar o concurso de origem. A função `resolver_concurso_do_pdf` recupera a URL de origem armazenada no `.manifest.json` e extrai o slug do certame a partir do padrão `/concursos/<slug>/`, prevenindo atribuições incorretas de arquivos ([A15](../tecnico/regras.md#a15)).
Fonte: src/downloader.py:104-143

## Inventário e Regras de Escopo

O diretório `inventario/` mantém o registro do acervo documental em três artefatos principais: `concursos.jsonl`, contendo o mapeamento de cada concurso e seus respectivos PDFs; `anos.json`, que consolida os totais por ano de realização; e `RELATORIO.md`, que documenta a auditoria de links e alertas. Os quantitativos agregados desses concursos constam em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: src/inventario.py:27-35

O escopo dos concursos que entram no site é delimitado por `inventario/exclusoes.json`, processado pela função `carregar_exclusoes`. Esse arquivo lista certames que devem ser desconsiderados com base em justificativas auditadas nas categorias estritas `cancelado`, `sem_prova`, `pagina_vazia`, `discursiva_sem_caderno`, `nao_e_concurso` e `curso_formacao`, excluindo esses certames da reamostragem e do relatório de inconsistências ([ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md), [P67](../tecnico/regras.md#p67)).
Fonte: src/inventario.py:250-258

Arquivos de prova relativos a cursos de formação são descartados do site de questões pela função `pdf_vai_para_o_site`, uma vez que avaliam matérias restritas ao curso ministrado e não os conteúdos previstos no edital de abertura. Quando um concurso regular possui provas de curso de formação, apenas esses PDFs específicos são desconsiderados, mantendo-se os cadernos e gabaritos principais do concurso ([ADR-037](../adr/ADR-037-escopo-do-site-no-inventario.md)).
Fonte: src/inventario.py:261-268

## Referências e Regras Relacionadas

- Regras de negócio e engenharia da coleta:
  - [P01 — Filtro de ano pelo slug da URL](../tecnico/regras.md#p01)
  - [P02 — Falha isolada por concurso não aborta lote](../tecnico/regras.md#p02)
  - [P03 — Slugify determinístico para pastas de órgãos](../tecnico/regras.md#p03)
  - [P06 — Priorização de cargo grande por slug da URL](../tecnico/regras.md#p06)
  - [P07 — Idempotência do crawler via registro JSON](../tecnico/regras.md#p07)
  - [P08 — Nome de órgão extraído do slug](../tecnico/regras.md#p08)
  - [P09 — Validação de PDF por magic bytes (%PDF-)](../tecnico/regras.md#p09)
  - [P10 — Dedup de download em duas camadas](../tecnico/regras.md#p10)
  - [P11 — Resolução de href relativo com urljoin](../tecnico/regras.md#p11)
  - [P31 — Filtro de editais de abertura no crawler](../tecnico/regras.md#p31)
  - [P67 — Escopo fora do site gerenciado em exclusoes.json](../tecnico/regras.md#p67)
  - [A01 — Nunca comparar href cru contra URL absoluta](../tecnico/regras.md#a01)
  - [A02 — Nunca filtrar ano com regex no texto do link](../tecnico/regras.md#a02)
  - [A03 — Nunca envolver o loop inteiro num único try/except](../tecnico/regras.md#a03)
  - [A15 — Nunca deduzir concurso pelo caminho da pasta em disco](../tecnico/regras.md#a15)

- Decisões de arquitetura:
  - [ADR-001 — Filtro de ano por slug de URL, não por texto do link](../adr/ADR-001-filtro-ano-slug-url.md)
  - [ADR-002 — Fonte primária de crawling é /concursos/encerrado](../adr/ADR-002-fonte-primaria-concursos-encerrados.md)
  - [ADR-004 — Priorização de cargo por slug](../adr/ADR-004-priorizacao-cargo-slug.md)
  - [ADR-005 — Idempotência via registro JSON local](../adr/ADR-005-idempotencia-registro-json.md)
  - [ADR-006 — Nome de órgão também vem do slug](../adr/ADR-006-extracao-orgao-slug.md)
  - [ADR-007 — Dedup de download em duas camadas (URL + hash)](../adr/ADR-007-dedup-download-dupla-camada.md)
  - [ADR-008 — Resolução de href relativo no crawler](../adr/ADR-008-resolucao-href-relativo.md)
  - [ADR-013 — Ligação do spider com o downloader antes de marcar idempotência](../adr/ADR-013-ligacao-spider-downloader.md)
  - [ADR-037 — Escopo do site no inventário e exclusões](../adr/ADR-037-escopo-do-site-no-inventario.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
