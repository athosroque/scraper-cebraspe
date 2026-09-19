# Lições — scraper-cebraspe

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
