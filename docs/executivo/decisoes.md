# Decisões principais

Doze decisões que mais pesam no projeto, agrupadas por tema. Cada bloco traz o problema, a decisão tomada e o resultado ou o trade-off. As ADRs (registros de decisão de arquitetura) guardam o contexto completo e as alternativas descartadas.

## Coleta e download

### Ano e órgão vêm do endereço da página

- **Problema.** Na listagem do CEBRASPE, o texto de todos os links é o mesmo ("MAIS INFORMAÇÕES"). Um filtro de ano feito sobre esse texto não achava nenhum concurso, sem dar erro.
- **Decisão.** O ano (por exemplo, `_25` para 2025) e o nome do órgão são lidos do endereço da página, que segue um padrão fixo. Assim o crawler ignora o texto do link ([ADR-001](../adr/ADR-001-filtro-ano-slug-url.md), [ADR-006](../adr/ADR-006-extracao-orgao-slug.md)).
- **Trade-off.** A leitura depende do padrão do endereço. Se o CEBRASPE mudar o padrão, o filtro precisa ser revisto. O trecho é curto e fica num ponto só do código.

### Download sem repetição, em duas camadas

- **Problema.** Rodar a coleta de novo não pode baixar os mesmos PDFs outra vez, nem guardar duas cópias do mesmo arquivo com nomes diferentes.
- **Decisão.** Um manifesto registra a URL de cada arquivo já baixado. Depois do download, um hash do conteúdo (SHA-256) identifica arquivos idênticos vindos de endereços diferentes ([ADR-007](../adr/ADR-007-dedup-download-dupla-camada.md)).
- **Trade-off.** O hash exige ler o arquivo inteiro uma vez. Em troca, a coleta pode ser reexecutada sem custo nem duplicação.

## Extração do edital

### Recorte e chunking pela seção certa do edital

- **Problema.** O edital tem anexos administrativos que não interessam à taxonomia. Um modelo de linguagem que lê o documento inteiro gasta tokens e erra mais.
- **Decisão.** O parser recorta só a seção "objetos de avaliação", e o texto é dividido em trechos por cargo e por matéria ([ADR-009](../adr/ADR-009-recorte-objetos-avaliacao.md), [ADR-010](../adr/ADR-010-chunking-cargo-materia.md)).
- **Trade-off.** O recorte depende dos marcadores do texto do PDF. Um edital com layout fora do padrão pode exigir ajuste no parser.

### LLM por chamada HTTP direta e telemetria no Langfuse

- **Problema.** O modelo precisa ser trocado ou medido sem que o código dependa de uma biblioteca que muda com frequência.
- **Decisão.** As chamadas ao OpenRouter são feitas por HTTP direto, sem camada de abstração de terceiros. A telemetria usa o SDK oficial do Langfuse, que registra cada chamada com a entrada, a saída e os tokens ([ADR-011](../adr/ADR-011-extracao-llm-requests-direto.md), [ADR-023](../adr/ADR-023-migracao-langfuse-sdk-oficial.md)).
- **Trade-off.** O tratamento de erros e de nova tentativa fica no código do projeto. Em troca, cada chamada fica visível e fácil de auditar.

### Revisão humana com artefatos que se atualizam sozinhos

- **Problema.** O dono precisa revisar a taxonomia de cada edital, e a revisão só vale se estiver em dia com o último resultado da extração.
- **Decisão.** A revisão é feita numa interface navegável (Datasette), com um relatório por edital. A validação de-para (conferência de que cada item do edital existe na taxonomia) e a geração dos artefatos rodam sozinhas ao fim de cada extração ([ADR-015](../adr/ADR-015-revisao-datasette-traefik.md), [ADR-019](../adr/ADR-019-pipeline-automatico-artefatos-revisao.md)).
- **Trade-off.** A revisão é trabalho manual do dono. O projeto reduz o volume dela, com alertas, mas não a elimina.

### Reconciliação determinística antes de pedir nova chamada ao LLM

- **Problema.** Às vezes o LLM omite um item do edital. Chamar o modelo de novo custa tempo e dinheiro, e pode trazer outro erro.
- **Decisão.** Um item simples que faltou é reinserido por regra, sem nova chamada. Itens que não podem ser reinseridos com segurança viram alerta com severidade ([ADR-025](../adr/ADR-025-reconciliacao-deterministica-severidade-alertas.md)).
- **Trade-off.** A reinserção só vale para itens simples. Itens compostos continuam dependendo de revisão.

## Banco e árvore de assuntos

### Banco próprio e modelagem dimensional

- **Problema.** Os dados do projeto precisam de um banco estável, que não dependa de outro projeto, e que sirva bem às estatísticas.
- **Decisão.** O projeto tem um Postgres próprio, sem chave estrangeira para outros bancos. A carga segue um modelo estrela (star schema), com tabelas de fatos e dimensões, e é idempotente ([ADR-026](../adr/ADR-026-banco-postgres-proprio.md), [ADR-027](../adr/ADR-027-star-schema-estatisticas.md)).
- **Trade-off.** O cruzamento com o projeto de estudo (o `study-rag-agent`) fica para uma etapa futura, feito pela chave natural normalizada. Não há ligação direta entre os bancos.

### Árvore de assuntos curada, com aprovação do dono

- **Problema.** Editais diferentes nomeiam o mesmo assunto de formas diferentes. Sem uma árvore comum, as estatísticas de um concurso não se comparam com as de outro.
- **Decisão.** A árvore mestre tem matéria, assunto e subassunto. O LLM propõe agrupamentos, e só o dono aprova. Item de edital e questão apontam para nós da árvore, numa relação de muitos para muitos ([ADR-029](../adr/ADR-029-camada-canonica-sinonimos.md), [ADR-030](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)).
- **Trade-off.** A curadoria é manual e leva tempo. Em troca, a árvore fica estável e as estatísticas entre concursos ficam comparáveis.

## Questões e estatísticas

### Questões lidas do PDF, sem LLM, e classificação com lista fechada

- **Problema.** Um erro na leitura da questão ou do gabarito contamina todas as estatísticas.
- **Decisão.** O enunciado, as alternativas e o gabarito são lidos do PDF por regras, sem LLM. Na classificação, o modelo escolhe entre candidatos de uma lista fechada, com confiança em três níveis e no máximo dois nós por questão. Se a questão está ou não no edital é calculado por regra, e não pelo modelo ([ADR-031](../adr/ADR-031-extracao-questoes-cadernos.md), [ADR-032](../adr/ADR-032-classificacao-questoes-arvore.md)).
- **Trade-off.** Layouts de caderno fora do padrão exigem parser novo. A lista fechada limita o modelo, o que torna a classificação previsível e auditável, ao custo de alguma perda de nuance.

### Incidência em dois níveis

- **Problema.** Um caderno básico é aplicado a vários cargos. Se cada cargo pesar igual, o mesmo caderno entra na média várias vezes, e um concurso com muitos cargos domina o resultado.
- **Decisão.** A incidência é calculada por prova (concurso e cargo) e depois, por concurso, com média simples das provas. Assim cada edital pesa como um só, e o caderno compartilhado conta uma vez ([ADR-039](../adr/ADR-039-incidencia-em-dois-niveis.md)).
- **Trade-off.** O número de "o que mais cai" depende dessa regra, que está documentada para que a leitura dos números seja consistente.

### Múltipla escolha sem quebrar o que já existia

- **Problema.** O sistema foi construído para questões certo ou errado. Cerca de metade dos cadernos amostrados no inventário de 2020 a 2026 usa múltipla escolha.
- **Decisão.** O tipo da questão passa a ser registrado em cada item, com alternativas de A a E e gabarito próprio. O que já existia continua valendo para as questões certo ou errado ([ADR-038](../adr/ADR-038-suporte-multipla-escolha-retrocompativel.md)).
- **Trade-off.** Cada parte do pipeline, do banco ao site, precisa conhecer o tipo da questão. Em troca, o histórico não é reprocessado.

## Site

### Site em três camadas, com a migração garantida

- **Problema.** O site precisa de páginas, filtros, contas e uma API, sem exigir uma aplicação de frontend separada agora.
- **Decisão.** FastAPI com páginas renderizadas no servidor, HTMX e Alpine.js para a interação. O código é dividido em três camadas (repositório, serviços e rotas), o que torna barata uma futura migração do frontend, já que a API é a mesma ([ADR-033](../adr/ADR-033-site-publico-stack-e-deploy.md)).
- **Trade-off.** A interface é mais simples do que uma aplicação de página única. Em troca, a stack é pequena e fácil de manter por uma pessoa.

## Documentação

### Documentação gerada a partir do código

- **Problema.** Documentação escrita à mão sobre um pipeline envelhece a cada mudança. As regras do projeto estavam espalhadas num arquivo de instruções longo.
- **Decisão.** Um registro em código descreve os scripts, as etapas, as checagens e as regras. As páginas técnicas são geradas desse registro, e um teste recusa a publicação se a página gerada estiver desatualizada ([ADR-040](../adr/ADR-040-site-documentacao-mkdocs.md), [ADR-041](../adr/ADR-041-registro-e-paginas-geradas.md)).
- **Trade-off.** Quem muda o pipeline precisa atualizar o registro e rodar o gerador. O teste torna essa exigência visível, em vez de deixá-la à memória de quem mexe.

---

Todas as decisões do projeto, inclusive as que não entram nesta página, estão nas [ADRs](../adr/README.md), com data, status e tema.
