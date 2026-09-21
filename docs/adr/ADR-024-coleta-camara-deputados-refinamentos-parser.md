# ADR-024: Coleta da Câmara dos Deputados 2025 e Refinamentos do Parser de Editais

## Status
Aceito

## Data
2026-09-21

## Contexto

Durante a expansão da base de concursos de 2025 com a inclusão de mais um certame de grande relevância nacional — o concurso da **Câmara dos Deputados 2025 (Nível Superior — `CD_25_NS`)**, com cargos de Analista Legislativo e Técnico Legislativo —, o pipeline de crawling, download, parsing e extração LLM se deparou com três desafios estruturais:

1. **Quebra de linha em cabeçalhos de matérias longas:**
   No Cargo 1 (Analista Legislativo), o edital possui matérias com títulos extensos divididos em mais de uma linha pelo layout de diagramação do PDF, como:
   ```text
   REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM DO CONGRESSO NACIONAL E 
   CÓDIGO DE ÉTICA: 1 Regimento Interno da Câmara dos Deputados...
   ```
   Como o `PADRAO_MATERIA` era restrito a uma única linha, ele capturava apenas `CÓDIGO DE ÉTICA:`. A linha precedente (`REGIMENTO INTERNO... E`) ficava solta entre o cabeçalho do cargo e a matéria e, por não conter numerais de itens, era incorporada indevidamente pelo algoritmo de chunking ao rótulo do próprio cargo.

2. **Omissão de dois-pontos delimitadores antes do primeiro item numerado:**
   No Cargo 2 (Técnico Legislativo), o edital do CEBRASPE omitiu os dois-pontos (`:`) no cabeçalho da primeira matéria específica:
   ```text
   NOÇÕES DE DIREITO CONSTITUCIONAL E DE REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS 1 
   Constituição Federal de 1988: conceito, contexto histórico...
   ```
   Como o delimitador `:` não existia, o `PADRAO_MATERIA` não reconhecia a matéria. Ao detectar o item programático `1`, o parser inferia que se tratava de um cargo de especialidade sem matéria nomeada (como os cargos médicos do `PF_25_ADM`), atribuindo à matéria o próprio nome do cargo e empurrando o título da matéria para dentro do texto do primeiro chunk.

3. **Falsos positivos na classificação de editais no crawler:**
   Na página do concurso no portal do CEBRASPE, editais administrativos de retificação como `Edital nº 8 - Retificação do resultado provisório na prova discursiva e reabertura do período de acesso à imagem...` eram classificados incorretamente como editais de abertura porque a regex `re.search(r'EDITAL.*?ABERTURA', text)` casava a substring contida na palavra `REABERTURA`.

## Decisão

1. **Reconhecimento de quebras de linha conectivas em cabeçalhos de matéria (`PADRAO_MATERIA`):**
   A regex foi estendida para suportar quebras de linha em títulos de matéria exclusivamente quando a linha anterior é finalizada por conectivos, preposições ou vírgulas:
   ```python
   PADRAO_MATERIA = re.compile(
       r'\n(?!CARGO\s+\d)'
       r'('
       r'[A-ZÀ-Ú][A-ZÀ-Ú0-9 /,–\-]{2,90}'
       r'(?:(?:,\s*|\s+(?:E|OU|DE|DA|DO|DOS|DAS))\s*\n\s*[A-ZÀ-Ú0-9 /,–\-]{2,90})?'
       r'(?:\s*\([^)]*\))?'
       r'):\s*'
   )
   ```
   Dessa forma, títulos longos continuados como `... CONGRESSO NACIONAL E\nCÓDIGO DE ÉTICA:` são casados integralmente como uma única matéria, normalizando os espaços em branco sem absorver linhas soltas de cargos multi-linha (preservando o comportamento validado no edital do IBAMA).

2. **Detecção determinística de matéria sem dois-pontos em blocos de cargo:**
   Em `dividir_por_cargo_e_materia` (`src/edital_parser.py`), ao analisar um bloco sob `tipo == "cargo"` que contenha itens numerados imediatos, o parser inspeciona o texto precedente ao primeiro item (`PADRAO_ITEM_NUMERADO.search(texto_bloco)`). Se houver um prefixo textual em caixa alta (tamanho >= 3), ele é extraído como nome da matéria e o corpo do chunk passa a iniciar a partir do item `1`:
   ```python
   m_primeiro_item = PADRAO_ITEM_NUMERADO.search(texto_bloco)
   prefixo_materia = texto_bloco[:m_primeiro_item.start()].strip() if m_primeiro_item else ""
   if prefixo_materia and len(prefixo_materia) >= 3 and prefixo_materia.isupper():
       materia_nome = re.sub(r"\s+", " ", prefixo_materia)
       texto_final = texto_bloco[m_primeiro_item.start():].strip()
   else:
       materia_nome = cargo_atual.split(": ", 1)[-1]
       texto_final = texto_bloco
   ```

3. **Fronteira de palavra na classificação de editais de abertura:**
   Em `src/spider.py`, a regex foi refinada para exigir fronteira de palavra:
   ```python
   re.search(r'EDITAL.*?\bABERTURA\b', text)
   ```
   impedindo que retificações citando "reabertura" sejam tratadas como cadernos normativos de abertura.

4. **Coleta e extração completa da Câmara dos Deputados (`CD_25_NS`):**
   Execução ponta a ponta do crawler, download de 2 editais, 7 cadernos de provas e 4 gabaritos em `data/2025/CEBRASPE/CD/`, e extração via LLM (`z-ai/glm-5.3-flash` com telemetria Langfuse OTel) para os 15 chunks do edital de abertura atualizado.

## Alternativas Descartadas

- **Hardcoding dos títulos da Câmara no parser:** Inserir substituições manuais de string para o concurso específico resolveria o problema pontual, mas acumularia débito técnico e violaria o princípio de generalização do parser para os demais editais do CEBRASPE.
- **Permitir quebra de linha irrestrita em `PADRAO_MATERIA`:** Aceitar qualquer `\n` dentro da regex fez o parser engolir a segunda linha de cargos multi-linha do IBAMA (ex.: `QUALIDADE AMBIENTAL`), gerando regressão na suite de testes. A exigência de conectivos (`E|OU|DE|...`) provou ser o filtro discriminante exato.

## Consequências

### Positivas
- **100% de sucesso na extração:** Os 15 chunks do `CD_25_NS` foram processados sem nenhuma falha de inferência ou timeout no OpenRouter.
- **Zero alertas de validação:** A validação heurística de-para confirmou total aderência entre o texto original do edital e a taxonomia extraída (`total_alertas: 0`).
- **Base consolidada de 2025 expandida:** A base agora totaliza 5 concursos (`PF_25_ADM`, `TCU_25_TEFC`, `IBAMA_25`, `STM_25` e `CD_25_NS`) com 150 chunks catalogados no Datasette.
- **Suite de testes robustecida:** Expansão para 165 testes automatizados cobrindo as novas variantes de parsing e classificação no `pytest`.
