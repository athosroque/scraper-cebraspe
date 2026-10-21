# KAN-65: mapeamento da gestão estratégica na árvore mestre

Data: 2026-10-21. Tipo: mapeamento e proposta, somente leitura. Nada foi aplicado.
Nenhuma alteração em `canonico/arvore.json`, nenhum script de curadoria rodado, nenhuma escrita no banco, nenhum commit e nenhuma aprovação em nome do dono (A30).

Fontes: `src/arvore.carregar()` (A28) sobre `canonico/arvore.json` (3.732 nós, 3.345 ativos); consultas de leitura ao banco `cebraspe` (views `vw_questao_no`, `vw_edital_cobra_base`, `vw_taxonomia_detalhe`, `vw_arvore_edital_por_cargo`); edital BANRISUL_25 em `revisao_piloto/` (leitura do JSON).

## 1. Nós encontrados

Contagens: "questões" = questões com vínculo aprovado ao nó (`vw_questao_no`); "itens" = itens de edital ligados diretamente ao nó, só `aprovado` (`vw_edital_cobra_base`, mesmo nível). Itens ligados a subníveis não sobem para o assunto nesta contagem.

| Id | Nível | Status | Nome (resumido) | Pai | Q | Itens | Situação proposta |
|---|---|---|---|---|---|---|---|
| A-fdd929e9b9 | assunto | ativo | Gestão estratégica | Administração Geral | 0 | 6 | casa (manter) |
| A-49f101efee | assunto | ativo | Balanced scorecard | Administração Geral | 1 | 2 | fundir no BSC |
| A-7e84a0b377 | assunto | ativo | Ferramentas de análise de cenário interno e externo | Administração Geral | 1 | 2 | virar subassunto da casa |
| A-834a863292 | assunto | ativo | OKR | Administração Geral | 0 | 1 | virar subassunto da casa |
| A-b34798e56a | assunto | ativo | Indicadores de desempenho | Administração Geral | 2 | 2 | fundir em "Indicadores" |
| A-a5928b006b | assunto | ativo | Governança | Administração Pública | 4 | 7 | manter; só saem subs de ferramentas |
| A-c415e4b4f5 | assunto | ativo | Processo administrativo | Administração Geral | 0 | 3 | manter; saem subs de ferramentas |
| A-5e4dff788c | assunto | ativo | Gestão da qualidade e modelo de excelência | Administração Geral | 0 | 2 | fora (qualidade) |
| A-9579bc2a33 | assunto | ativo | Planejamento estratégico de TIC | Governança e Gestão de TIC | 0 | 2 | fora (TIC), ver dúvida 4 |
| A-9dbfe15626 | assunto | ativo | Governança de TIC | Governança e Gestão de TIC | 0 | 2 | fora (TIC), ver dúvida 4 |
| S-7a0d161260 | subassunto | ativo | BSC: principais conceitos, aplicações, mapa estratégico... | Gestão estratégica | 1 | 1 | destino do BSC (renomear) |
| S-5d901cc3bc | subassunto | ativo | Balanced scorecard | Processo administrativo | 0 | 1 | fundir no BSC |
| S-bcd5e45306 | subassunto | ativo | Análise SWOT | Gestão estratégica | 1 | 1 | destino da SWOT |
| S-4fbb5eef47 | subassunto | ativo | Planejamento estratégico: visão, missão e análise SWOT | Gestão estratégica | 1 | 1 | nome composto: reapontar e aposentar |
| S-71b651de26 | subassunto | ativo | Ferramentas de planejamento estratégico: Análise SWOT; BSC... | Governança | 2 | 1 | nome composto: reapontar e aposentar |
| S-655449dbb0 | subassunto | ativo | Ferramentas de planejamento estratégico | Gestão estratégica | 0 | 1 | genérico, dúvida 6 |
| S-8ee3df7025 | subassunto | ativo | Metodologias de indicadores OKR, PKI e BSC | Governança de TIC | 2 | 2 | nome composto de TIC, dúvida 4 |
| S-9ac1356984 | subassunto | ativo | Análise SWOT aplicados à TIC | Governança de TIC | 2 | 2 | TIC, dúvida 4 |
| S-1d811c97a0 | subassunto | ativo | Indicadores e sistema de medição de desempenho organizacional | Gestão estratégica | 0 | 1 | destino de "Indicadores" |
| S-def3f14b7c | subassunto | ativo | Tipos de indicadores | Gestão estratégica | 1 | 1 | fundir em "Indicadores" |
| S-1af6ddeb5c | subassunto | ativo | Variáveis componentes dos indicadores | Gestão estratégica | 0 | 1 | fundir em "Indicadores" |
| S-9e3a88bbc7 | subassunto | ativo | Indicadores de desempenho: tipos; variáveis componentes | Governança | 0 | 1 | fundir em "Indicadores" |
| S-5feb256b72 | subassunto | ativo | Sistema de medição de desempenho organizacional | Processo administrativo | 1 | 1 | fundir em "Indicadores" |
| S-b99aec5724 | subassunto | ativo | Indicadores de desempenho de TIC e alinhamento | Planejamento estratégico de TIC | 1 | 2 | TIC, dúvida 4 |
| S-aedc8bb2b0 | subassunto | ativo | Planejamento estratégico | Gestão estratégica | 2 | 2 | destino de "Planejamento estratégico" |
| S-68fb64a623 | subassunto | ativo | Planejamento estratégico: conceitos, métodos e técnicas | Governança | 0 | 1 | fundir em S-aedc8bb2b0 (mesmo conceito) |
| S-fef2d1ec7f | subassunto | ativo | Fundamentos de estratégia | Gestão estratégica | 0 | 1 | destino (nome igual ao S-9ac59debbd) |
| S-9ac59debbd | subassunto | ativo | Fundamentos de estratégia | Governança | 0 | 1 | fundir em S-fef2d1ec7f (nome igual) |
| S-47a964b70f | subassunto | ativo | Análise competitiva e estratégias genéricas | Processo administrativo | 0 | 1 | dúvida 5 |
| S-63086724f1 | subassunto | ativo | Ciclo PDCA | Gestão da qualidade | 1 | 1 | fora (qualidade) |
| S-9c83d6e476 | subassunto | ativo | Ferramentas de gestão da qualidade | Gestão da qualidade | 1 | 2 | fora; dúvida 7 (pode conter GUT) |
| S-6f4a0abb1f | subassunto | ativo | Metas estratégicas e resultados pretendidos | Gestão estratégica | 2 | 1 | manter (conceito) |
| S-421fd7188f | subassunto | ativo | Monitoramento da estratégia | Gestão estratégica | 1 | 1 | manter (conceito) |
| S-de8eae3985 | subassunto | ativo | Execução da estratégia | Gestão estratégica | 1 | 1 | manter (conceito) |
| S-d8694317ea | subassunto | ativo | Diagnóstico estratégico | Gestão estratégica | 0 | 1 | manter (conceito) |
| S-e76dc0b6b0 | subassunto | ativo | Condições necessárias para se desenvolver a estratégia | Gestão estratégica | 2 | 2 | manter (conceito) |
| S-0d8add731a | subassunto | ativo | Questões-chave em estratégia | Gestão estratégica | 0 | 2 | manter (conceito) |
| S-52926ecfde | subassunto | ativo | Definições de estratégia | Gestão estratégica | 0 | 1 | manter (conceito) |
| S-6910bcb129 | subassunto | ativo | Escolas de planejamento estratégico | Gestão estratégica | 0 | 1 | manter (conceito) |
| S-9b253f200e | subassunto | ativo | Planejamento institucional | Gestão estratégica | 1 | 1 | dúvida 3 |
| S-58805db2eb | subassunto | ativo | Estratégia Nacional do Poder Judiciário | Gestão estratégica | 0 | 1 | fora? dúvida 3 |
| S-2edc57a338 | subassunto | ativo | Conceitos, métodos e técnicas | Gestão estratégica | 1 | 2 | dúvida 3 (nome genérico) |
| S-8e2fc5016f | subassunto | ativo | Conceito | Gestão estratégica | 1 | 1 | dúvida 3 (nome genérico) |
| S-ed20626c5c | subassunto | ativo | Modelos de gestão e estruturas organizacionais | Gestão estratégica | 0 | 1 | dúvida 3 |

Os nós fundidos que já apontam para a casa (sem ação): A-22f7c4d32e, A-9358b3c779, A-5ab639a326 e M-d8b759a97c (para A-fdd929e9b9); S-c0c367d2db, S-f1a090d081, S-5e1da8adc2 (para subs de Gestão estratégica); S-b3005f70bf (para S-2edc57a338).

## 2. Ferramentas sem nó

| Ferramenta | Nó na árvore | Questões no banco | Itens de edital | Observação |
|---|---|---|---|---|
| BSC | A-49f101efee (1 q), S-7a0d161260 (1 q), S-5d901cc3bc (0 q); compostos S-71b651de26 e S-8ee3df7025 | soma dos nós simples: 2 q (os compostos não foram separados) | 1 SEFA_PR_25 (sem nó na árvore) e 1 BANRISUL_25, ambos sem vínculo | 3 nós duplicados |
| SWOT | S-bcd5e45306 (1 q); compostos S-4fbb5eef47 (1 q) e S-71b651de26 (2 q); TIC S-9ac1356984 (2 q) | soma dos nós: 6 q | item BANRISUL no tópico "Ferramentas de análise de ambiente" | |
| Análise de cenário | A-7e84a0b377 | 1 | 2 itens (vínculos diretos) | ponto de partida para o bloco "análise de ambiente" |
| GUT (matriz) | nenhum | 0 | 1 item BANRISUL (dentro de "Ferramentas de análise de ambiente") | lacuna |
| 5W2H | nenhum | 0 | 0 | não existe nem no banco nem na árvore |
| Business Model Canvas | nenhum | 2 questões BANRISUL sem vínculo (74176, 74177) | 1 item BANRISUL | lacuna |
| Referencial estratégico (negócio, missão, visão, valores) | nenhum (só parte em S-4fbb5eef47) | 0 | 1 item BANRISUL | lacuna |
| Indicadores de desempenho | A-b34798e56a e 5 subs (6 nós) | soma dos nós: 4 q | soma dos nós: 6 itens | 6 nós com nome parecido |
| OKR | A-834a863292 (0 q, 1 item); composto TIC S-8ee3df7025 (2 q) | 2 | 1 | |
| PKI | nenhum nó próprio | 0 | 0 | citado só em S-8ee3df7025 |

Questões de BANRISUL_25 (caderno 077_BANRISUL_004_01) citando BSC, SWOT ou Canvas (74171, 74174, 74176, 74177): não há nenhuma linha em `questao_no` para elas, então ficam sem nó. Isto é coerente com a C1b ainda pendente.

## 3. Estrutura proposta (somente proposta)

Casa: `A-fdd929e9b9` "Gestão estratégica" (já tem 3 fusões e 6 itens). Um subassunto por ferramenta:

1. Balanced Scorecard (BSC): destino `S-7a0d161260` (renomear para "Balanced Scorecard (BSC)"). Recebe A-49f101efee e S-5d901cc3bc.
2. Análise SWOT: destino `S-bcd5e45306`. Recebe a parte SWOT de S-4fbb5eef47 e S-71b651de26 (por reapontamento de itens e questões).
3. Análise de cenários e de ambiente interno/externo: a partir de A-7e84a0b377 (vira subassunto sob a casa).
4. Matriz GUT: novo subassunto (sem nó hoje).
5. Business Model Canvas: novo subassunto.
6. Referencial estratégico (negócio, missão, visão de futuro, valores): novo subassunto. Substitui o trecho "visão, missão" de S-4fbb5eef47.
7. OKR: a partir de A-834a863292 (vira subassunto sob a casa).
8. Indicadores de desempenho: destino `S-1d811c97a0`. Recebe A-b34798e56a, S-def3f14b7c, S-1af6ddeb5c, S-9e3a88bbc7, S-5feb256b72 (dúvida 1).
9. Planejamento estratégico (conceitos): destino `S-aedc8bb2b0`. Recebe S-68fb64a623.
10. Fundamentos de estratégia: destino `S-fef2d1ec7f`. Recebe S-9ac59debbd.
11. Demais conceitos (metas, monitoramento, execução, diagnóstico, condições, questões-chave, definições, escolas): mantidos como estão.

Fora da casa (domínios próprios, com referência cruzada): TIC (A-9579bc2a33, A-9dbfe15626 e seus subs), qualidade (A-5e4dff788c, PDCA, ferramentas de qualidade), S-47a964b70f (dúvida 5).

Ordem sugerida (cada etapa passa por `src/arvore.py` ou `scripts/curar_arvore.py`, P51; antes e depois, K22–K24 conforme P71):
a. `renomear_no` S-7a0d161260 para "Balanced Scorecard (BSC)".
b. `fundir_nos` A-49f101efee → S-7a0d161260 (entre níveis: permitido, KAN-64, pois o assunto não tem filhos ativos). Depois S-5d901cc3bc → S-7a0d161260 (mesmo nível).
c. `fundir_nos` S-68fb64a623 → S-aedc8bb2b0; S-9ac59debbd → S-fef2d1ec7f; S-1af6ddeb5c, S-def3f14b7c, S-9e3a88bbc7, S-5feb256b72 → S-1d811c97a0 (mesmo nível).
d. Criar GUT, Canvas e Referencial sob a casa (`criar_no`).
e. Reapontar itens e questões de S-4fbb5eef47 e S-71b651de26 (`desmapear` e `mapear`), e só então `aposentar_no` (aposentar exige zero mapeamento aprovado, arvore.py linha ~245). Não fundir o composto numa das partes, pois o ADR-030 (item 1) rejeita isso.
f. A-7e84a0b377 e A-834a863292 viram subassuntos: criar o subassunto sob a casa e fundir o assunto nele (entre níveis, sem filhos).

## 4. Dúvidas que dependem do dono

1. "Indicadores de desempenho" é ferramenta ou tema? Se é tema, pode ficar fora do BSC e a estrutura muda pouco. Se é ferramenta, fica como subassunto próprio.
2. GUT, Canvas e Referencial têm item de edital só no BANRISUL. Criar os três nós já agora? 5W2H não tem nenhum item nem questão: criar ou não?
3. Os subassuntos de conceito (Conceito, Conceitos, métodos e técnicas, Modelos de gestão, Planejamento institucional, ENJ) são "conceitos" da casa ou saem para outro lugar?
4. TIC: "SWOT aplicados à TIC", "OKR, PKI e BSC" e "Indicadores de TIC" ficam no domínio TIC (com referência cruzada) ou entram na casa? PKI não tem nó.
5. "Análise competitiva e estratégias genéricas" (Porter) entra na casa como ferramenta?
6. "Ferramentas de planejamento estratégico" (S-655449dbb0, genérico, 1 item) vira "outras" ou é aposentado depois de reapontar o item?
7. "Ferramentas de gestão da qualidade" (S-9c83d6e476) pode conter GUT ou 5W2H. Precisa ler o conteúdo dos itens dela antes de decidir.
8. Confirmar a fusão entre níveis (assunto → subassunto, KAN-64) para A-7e84a0b377 e A-834a863292: as contagens por nível precisam ser conferidas depois (ver seção 5).
9. Nomes compostos: confirmar que os compostos S-4fbb5eef47 e S-71b651de26 podem ser aposentados (e não mantidos como nó "de ligação") depois de reapontados.

## 5. Não verificado

- Não li o texto dos itens de edital de todos os concursos; só as contagens. O conteúdo de "Ferramentas de gestão da qualidade" e de outros itens com GUT/5W2H não foi conferido.
- A busca por GUT, 5W2H, Canvas e SWOT/BSC usou regex no enunciado de `questoes` (13 hits, listados acima) e em `vw_taxonomia_detalhe` (2 hits: SEFA_PR_25 e BANRISUL_25 para BSC). Não busquei em outros campos.
- A coluna "Itens" conta só vínculos diretos aprovados (`vw_edital_cobra_base`). Itens de subníveis não sobem para o assunto nessa conta. O total "todos os status" também existe no banco, mas não foi usado.
- Não verifiquei como as questões ficam vinculadas (`questao_no`) quando um nó é aposentado, nem se a classificação 5D (`canonico/classificacao_questoes.json`) precisa ser regerada. Não rodei `detectar_homonimos` nem `detectar_dispersos`.
- O `detectar_compostos` devolveu só 1 caso em toda a árvore e nenhum dos compostos desta lista. Não investiguei a regra dele; os compostos foram achados por leitura dos nomes.
- Não verifiquei se a fusão entre níveis (KAN-64) mantém a contagem de itens por nível depois da execução. Isso precisa de teste, não de leitura.
- BANRISUL_25: o item de ESTRATÉGIA no JSON (`revisao_piloto/Ed_1_2025_Banrisul_Abertura_atualizado_ate_ret_4.json`, resultado 23) tem 3 tópicos: BSC; Referencial Estratégico (análise de ambiente interno/externo; "ferramentas: SWOT, análise de cenários, matriz GUT"; Business Model Canvas; "negócio, missão, visão de futuro, valores"); Indicadores de desempenho. No banco aparecem 3 linhas de taxonomia, sem vínculo com nós.
