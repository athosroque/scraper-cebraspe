<!-- Gerado por scripts/gerar_numeros.py. Não edite à mão: rode make docs-gerar. -->

# Números

Atualizado em 21/10/2026, a partir do banco do projeto.

## Cobertura

O inventário lista os concursos encerrados do CEBRASPE a partir de 2020, ano a ano. A base mostra quantos desses já foram carregados: cada concurso tem cargos e cadernos de prova. Os concursos carregados entram na conta de aprovados quando o dono revisa e aprova cada um.

| Ano | Concursos no inventário |
|---|---:|
| 2020 | 26 |
| 2021 | 60 |
| 2022 | 49 |
| 2023 | 57 |
| 2024 | 50 |
| 2025 | 52 |
| 2026 | 52 |
| **Total** | **346** |

| Indicador | Quantidade |
|---|---:|
| Concursos carregados na base | 7 |
| Concursos aprovados pelo dono | 5 |
| Cargos dos editais | 41 |
| Cadernos de prova | 87 |

## Questões

As questões saem das provas já extraídas. Certo ou errado (C/E) é o formato em que cada afirmativa é julgada certa ou errada. Múltipla escolha tem alternativas de A a E. Uma questão anulada foi cancelada pela banca. Utilizável é a questão que passou pela checagem da extração e pode aparecer no site. Discursivas são as questões dissertativas, que não entram na conta de C/E e de múltipla escolha.

| Indicador | Quantidade |
|---|---:|
| Total de questões | 3.410 |
| Certo ou errado (C/E) | 2.800 |
| Múltipla escolha | 610 |
| Anuladas | 152 |
| Utilizáveis no site | 3.391 |
| Discursivas | 39 |

## Árvore de assuntos

O conteúdo é organizado em três níveis: a matéria é a disciplina (por exemplo, Língua Portuguesa), o assunto é um tema dentro dela e o subassunto é o ponto mais fino, que é a unidade de estudo do site. Os itens do edital são os tópicos que o edital diz que a banca cobra. Um apontamento liga uma questão a um nó da árvore (matéria, assunto ou subassunto), e uma questão pode ter até dois.

| Indicador | Quantidade |
|---|---:|
| Matérias ativas | 74 |
| Assuntos ativos | 1.016 |
| Subassuntos ativos | 2.255 |
| Itens do edital | 1.812 |
| Subitens do edital | 3.936 |
| Apontamentos questão → nó da árvore | 2.965 |

## Custo do LLM

Quanto o projeto gastou com modelo de linguagem, em dólar. Cada valor é o total acumulado pela chave de API da etapa, lido no OpenRouter. O modelo usado é o `z-ai/glm-5.3-flash`. As etapas listadas são as que chamam o modelo: taxonomia dos editais, sinônimos, curadoria da árvore, classificação das questões e o bot do Telegram. A leitura das questões e do gabarito e a estatística que alimenta o site são feitas por regra, sem modelo. Uma chave trocada recomeça o acumulado do zero, então o total é um piso do gasto desde o início do projeto.

| Etapa | Custo acumulado |
|---|---:|
| Taxonomia do edital | US$ 0,0198 |
| Sinônimos | US$ 0,0001 |
| Curadoria da árvore | US$ 0,0002 |
| Classificação das questões | US$ 0,0001 |
| Bot do Telegram | US$ 0,0002 |
| Chave geral (fallback e etapas antigas) | US$ 0,2907 |
| **Total** | **US$ 0,3111** |
