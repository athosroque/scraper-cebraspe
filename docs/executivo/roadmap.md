# Roadmap

Onde o projeto está, o que está em andamento e o que vem depois. A ordem dos próximos passos segue as prioridades do dono.

!!! note "Cards do Jira"

    Os números KAN-N citados aqui são cards do Jira. Eles são de acesso interno, e os links só abrem para quem tem acesso ao workspace do projeto.

## Concluído

- **Coleta e download.** Crawler que percorre os concursos encerrados, filtra por ano e órgão e baixa editais, provas e gabaritos, sem repetir arquivos.
- **Extração de editais com revisão humana.** A taxonomia de cada edital é extraída com LLM, validada por regras e aprovada pelo dono. A base de 2025 foi aprovada em 23 de setembro de 2026.
- **Banco de estatísticas.** Postgres próprio, com modelagem dimensional e cargas idempotentes.
- **Extração e classificação de questões.** Questões, gabaritos e discursivas extraídas dos cadernos, classificadas na árvore de assuntos, com a árvore mestre semeada e curada pelo dono.
- **Piloto de cinco concursos de 2025.** Validado do início ao fim, da coleta ao site.
- **Site com contas, estatísticas e simulado.** Páginas de questões com filtros, login Google, histórico, páginas de estatística e simulado com a correção do CEBRASPE para certo ou errado.
- **Suporte a múltipla escolha.** Tipo de questão, alternativas de A a E, gabarito e site adaptado ao tipo. Incidência calculada em dois níveis, com cada edital pesando como um só.
- **Documentação técnica viva.** Site de documentação com as páginas técnicas geradas do código e um índice por tarefa para quem mexe no projeto.

## Em andamento

- **Coleta dos 11 concursos de múltipla escolha de 2025** (Etapa 8.C, [KAN-55](https://athoslobin.atlassian.net/browse/KAN-55)). O download guiado pelo inventário já está pronto ([KAN-30](https://athoslobin.atlassian.net/browse/KAN-30)). O primeiro lote de calibração, com os concursos `SEFA_PR_25` e `BANRISUL_25`, está em análise ([KAN-56](https://athoslobin.atlassian.net/browse/KAN-56)). As etapas seguintes ([KAN-57](https://athoslobin.atlassian.net/browse/KAN-57) a [KAN-63](https://athoslobin.atlassian.net/browse/KAN-63)) levam os demais concursos ao banco e ao site, em lotes de dois.
- **Documentação executiva** ([KAN-71](https://athoslobin.atlassian.net/browse/KAN-71)). Esta seção, com o PDF para quem está de fora.
- **Orquestrador Dagster** ([KAN-31](https://athoslobin.atlassian.net/browse/KAN-31) e [KAN-32](https://athoslobin.atlassian.net/browse/KAN-32)). Ferramenta que organiza as etapas do pipeline como tarefas, roda cada lote com checagens automáticas e para em cada ponto em que o dono precisa aprovar. É a próxima peça de infraestrutura.

## Próximos passos

- **Estatísticas por recorte.** Drill-down de matéria até subassunto, com filtros por banca, ano, órgão e nível. Permite perguntas como "o que o CEBRASPE cobrou em Língua Portuguesa nos concursos de nível superior de 2024".
- **Expansão para 2020 a 2026.** Os anos já estão inventariados, com os concursos que entram no site e os que ficam de fora, com motivo registrado. A ingestão segue em lotes, com revisão do dono em cada um.
- **Cruzamento com o projeto de estudo.** Ligar os tópicos cobrados em concursos aos itens de estudo de outro projeto do portfólio, para montar um plano de estudo priorizado.
- **Deploy público.** Colocar o site no ar. É opcional, por decisão do dono, que quer mudar bastante o site antes disso.
