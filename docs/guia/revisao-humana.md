# Revisão humana e portões

O processo de revisão humana e os portões de qualidade garantem a validação e a homologação dos dados extraídos de editais e cadernos pelo pipeline, unindo auditoria visual no Datasette, relatórios HTML estáticos e regras estritas de bloqueio contra contaminação da base de produção.
Fonte: CLAUDE.md:208-215

**Para que serve:** Explicar o funcionamento dos portões humanos, a ferramenta Datasette, a geração de relatórios por edital e as regras de bloqueio. **Quando ler:** Antes de operar a revisão de editais, ajustar o esquema de status de revisão ou alterar os portões de liberação.

## Infraestrutura de revisão com Datasette

O Datasette atua como a interface de exploração e auditoria somente-leitura dos resultados brutos e intermediários da Etapa 4, permitindo navegar lado a lado a trilha de entrada e saída do parser, a divisão em chunks e as estruturas taxonômicas geradas pelo modelo de linguagem. Essa abordagem descarta a necessidade de manter uma aplicação frontend dedicada com controle de acesso customizado durante as etapas de validação e piloto, mantendo um isolamento absoluto em relação ao banco relacional de produção da Fase 5 (`scraper-cebraspe-db`).
Fonte: docs/adr/ADR-015-revisao-datasette-traefik.md:9-25

A base de dados de suporte à revisão é o arquivo SQLite descartável `revisao_piloto/revisao.db`, reconstruído do zero a cada execução pelo módulo `scripts/gerar_db_datasette.py` com o auxílio da biblioteca `sqlite-utils`. O script lê diretamente os arquivos canônicos de cada edital processado (`<edital>.json`, `<edital>.auditoria.json` e `<edital>.validacao.json`) em `revisao_piloto/`, dispensando rotinas de atualização incremental e garantindo que o banco de consulta reflita fielmente os arquivos em disco sem resíduos obsoletos.
Fonte: scripts/gerar_db_datasette.py:1-15

O esquema gerado no SQLite normaliza os dados nas tabelas `editais`, `chunks`, `taxonomia_topicos`, `taxonomia_subtopicos`, `alertas_validacao` e `cargos`, amarrando-as por chaves estrangeiras apropriadas. Para viabilizar buscas textuais rápidas diretamente na interface web sem joins complexos, o script ativa índices FTS5 nas colunas de texto das tabelas `chunks` (`texto_enviado_llm`, `materia`, `cargo`), `taxonomia_topicos` (`topico_nome`, `materia_extraida`, `materia_chunk`) e `taxonomia_subtopicos` (`subtopico_nome`).
Fonte: scripts/gerar_db_datasette.py:286-332

No ambiente operacional, o serviço `scraper-cebraspe-datasette` roda em container Docker baseado na imagem oficial `datasetteproject/datasette`, montando a pasta `./revisao_piloto` em modo somente-leitura (`:ro`). Ele expõe localmente a porta `127.0.0.1:8011` e integra-se à rede `homelab_default`, sendo roteado externamente pelo Traefik sob o domínio `https://datasette.projetoathos.com.br` e protegido pela camada de autenticação Cloudflare Access SSO com autorização restrita ao operador.
Fonte: docker-compose.yml:83-111

## Relatórios HTML de revisão

Para contornar o esforço de realizar o de-para manual entre tabelas relacionais do Datasette, o módulo `scripts/gerar_relatorio_revisao.py` sintetiza visualmente a comparação entre o edital e a taxonomia extraída em arquivos HTML estáticos de página única por edital. A geração adota HTML puro da biblioteca padrão Python (utilizando `html.escape` e interpolação de strings), sem acoplar mecanismos de templates como Jinja2, preservando a diretriz de dependências mínimas do projeto.
Fonte: scripts/gerar_relatorio_revisao.py:1-18

A visualização de cada edital é organizada em cartões sequenciais correspondentes a cada chunk avaliado, divididos em um layout responsivo de duas colunas: à esquerda é exibido o texto integral enviado ao modelo (`texto_enviado_llm`), contendo os itens numerados não identificados realçados visualmente com a tag `<mark>` a partir das posições calculadas pelo validador heurístico; à direita é renderizada a árvore hierárquica de tópicos e subtópicos extraídos, acompanhada de um banner superior com metadados de classificação e eventuais alertas associados.
Fonte: scripts/gerar_relatorio_revisao.py:180-218

Os arquivos gerados são salvos no subdiretório `revisao_piloto/relatorio/` e expostos pelo próprio contêiner Datasette por meio da flag `--static relatorio:/data/relatorio`. O ponto de entrada principal em `/relatorio/index.html` lista todos os editais disponíveis com contagens de chunks e alertas, além de conter links diretos para os relatórios complementares da camada canônica, como a árvore mestre (`arvore.html`) e o relatório de classificação de questões (`classificacao.html`).
Fonte: scripts/gerar_relatorio_revisao.py:274-295

O script orquestrador `scripts/atualizar_revisao.py` automatiza todo esse fluxo, executando em sequência a validação de-para de itens, a geração dos relatórios HTML, a atualização determinística das regras da árvore, a classificação visual, a reconstrução do SQLite `revisao.db` e o reinício do contêiner Datasette. O reinício do contêiner é tratado em modo *best-effort*, registrando alertas em log caso o serviço Docker esteja inativo ou ocorra timeout de 30 segundos, sem interromper ou falhar o pipeline de extração principal que já incorreu em custos de tokens.
Fonte: scripts/atualizar_revisao.py:55-73

## Estados de revisão e ciclo de aprovação

O ciclo de vida de aprovação de um edital apoia-se no campo `status_revisao_humana`, gravado no corpo de cada arquivo `<edital>.json` presente em `revisao_piloto/`. Este campo textual funciona como o ponto central de auditoria e controle de integridade da taxonomia de um concurso antes de sua promoção para o banco de estatísticas e posterior consumo por provas e questões.
Fonte: scripts/revisar_taxonomia_piloto.py:121-128

Durante a extração automatizada, o pipeline atribui a cada novo edital o valor inicial padronizado pela constante `STATUS_REVISAO_PENDENTE`, indicando explicitamente que o conteúdo ainda não foi homologado por um operador humano e não deve ser promovido para consumo irrestrito em produção. A transição para o estado aprovado ocorre exclusivamente por intervenção manual do operador, que insere uma declaração textual iniciada pelo prefixo `APROVADO` (por exemplo, `APROVADO — revisão humana da Fase 4 concluída...`) diretamente no arquivo JSON do edital após a conferência visual dos relatórios.
Fonte: scripts/revisar_taxonomia_piloto.py:44-47

A consolidação desse estado no banco relacional ocorre durante a execução do gravador `src/stats_writer.py`, por meio da função `status_revisao()`. A função inspeciona se o valor de `status_revisao_humana` inicia com a palavra `"APROVADO"`; em caso afirmativo, atribui o valor canônico `'aprovado'` à coluna `status_revisao` da tabela `concursos`, ou `'pendente'` caso contrário, persistindo o estado mediante operações de upsert na chave única do concurso (`slug`).
Fonte: src/stats_writer.py:190-196

Em concordância com a regra de integridade do projeto, a aprovação de concursos nunca pode ser efetuada via comandos manuais `UPDATE` diretamente no banco PostgreSQL. Como o `stats_writer` relê os arquivos JSON do disco a cada execução e propaga os dados via cláusula `ON CONFLICT (slug) DO UPDATE`, qualquer modificação manual isolada no banco relacional é imediatamente revertida pelo conteúdo original do arquivo JSON, garantindo que o arquivo versionado seja a única fonte da verdade.
Fonte: docs/adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md:20-23

## Portões humanos ("Gates") e bloqueios no pipeline

O pipeline estabelece portões humanos obrigatórios em marcos críticos do processamento para impedir a progressão cega de dados que apresentem inconsistências ou alucinações. Na taxonomia de editais (marco P3), o operador valida itens omitidos e divergências heurísticas no relatório estático antes de gravar a aprovação; na carga e conferência de questões (etapa P4), realiza-se a checagem manual de consultas de integridade e fidelidade aos cadernos de prova; na árvore mestre (etapas P5 e P6), o operador aprova ou rejeita propostas de novos nós individualmente; e na classificação de questões (etapa P8), analisa-se a aderência de questões marcadas com confiança média ou baixa.
Fonte: docs/tecnico/pipeline.md:137-294

O mecanismo de proteção contra contaminação do banco de produção (`scraper-cebraspe-db`) opera no nível das visões e consultas analíticas. Embora concursos com revisão pendente possam ser carregados em tabelas de apoio para possibilitar inspeção, todas as visões fundamentais de incidência de tópicos, cobertura de editais, contexto de questões e questões discursivas incluem cláusulas explícitas filtrando exclusivamente registros com `status_revisao = 'aprovado'`.
Fonte: src/sql/schema_estatisticas.sql:955-962

Dessa forma, questões vinculadas a editais ainda pendentes não entram no cálculo de incidência, não participam da contagem estatística e não são exibidas na aplicação pública de estudos até que ocorra a aprovação formal do respectivo edital. O total de concursos carregados no sistema e a quantidade restrita de concursos já homologados pelo operador podem ser acompanhados nos indicadores consolidados em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: docs/executivo/numeros.md:22-25

## Referências e Regras Relacionadas

- Regra relacionada: [P41 - Aprovação no JSON do edital](../tecnico/regras.md#p41)
- Regra relacionada: [A25 - Proibição de aprovação via UPDATE no banco](../tecnico/regras.md#a25)
- Regra relacionada: [A30 - Aprovação de propostas exclusiva do dono](../tecnico/regras.md#a30)
- Decisão de arquitetura: [ADR-015 - Revisão Navegável via Datasette, Traefik e Cloudflare Tunnel](../adr/ADR-015-revisao-datasette-traefik.md)
- Decisão de arquitetura: [ADR-018 - Relatório HTML de Página Única e Extensão do Schema de Revisão](../adr/ADR-018-relatorio-html-e-extensao-schema-revisao.md)
- Decisão de arquitetura: [ADR-019 - Pipeline Automático dos Artefatos de Revisão a Cada Extração](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md)
- Decisão de arquitetura: [ADR-025 - Reconciliação Determinística e Severidade de Alertas](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)
- Decisão de arquitetura: [ADR-028 - Restrição de Cargo Fora do Nome da Matéria e Registro da Aprovação da Fase 4](../adr/ADR-028-cargos-restritos-e-aprovacao-fase4.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
