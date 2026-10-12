# Conceitos dispersos na árvore mestre — 2026-10-12

KAN-64, Fase 1. Detecção por regra (`arvore.detectar_dispersos`), sem LLM. As propostas abaixo foram GRAVADAS como `proposto` na árvore mestre. Aprovação é do dono, em lote.

## Resumo

| Motivo | Confiança | Grupos |
|---|---|---|
| `mesma_norma` | alta | 20 |
| `mesma_norma` | media | 14 |
| `mesmo_nome` | alta | 138 |
| `mesmo_nome` | media | 26 |
| `nome_contido` | media | 117 |

- Propostas `fundir` gravadas: 175 (só confiança alta). Grupos de confiança alta sem operação possível: 11.
- Erros ao propor: 0.

## Critérios

- **Operação.** Todo membro funde no destino do grupo. `fundir_nos` aceita nó de nível diferente (assunto/subassunto) quando a origem não tem filhos ativos (ADR-030, atualização de 2026-10-12). O nó de nível diferente que tem filhos fica como *sem operação*: o dono decide (mover os filhos ou fundi-los antes).
- **Destino.** Mais questões (`questao_no` aprovadas, por nó resolvido), depois mais itens de edital aprovados, depois nível mais alto (assunto > subassunto) e menor ID.
- **`mesma_norma`.** Lei/LC/decreto/EC/MP + número (ano ignorado; "LC 101" = "Lei Complementar nº 101/2000 e suas alterações"; apelidos LRF, LGPD e LAI). Alta só quando o nó é essencialmente a norma (uma norma só, sem recorte do tema, sem lista ":"/";"/"," fora do parêntese); o resto do grupo vai para média.
- **`mesmo_nome`.** Mesma `chave_regra` sob pais diferentes, fora os nomes genéricos (`NOMES_GENERICOS_DISPERSAO`, nomes só de palavras genéricas e nome curto de uma palavra). Vira média se as matérias são de ramos diferentes (Penal × Penal Militar × Processual).
- **`nome_contido`.** O termo antes de ":" ou "(" de um nó é o início do nome de outro em outro pai. Sempre média, nunca proposto.

## Ajustes feitos após a primeira medição

- Primeira versão dava 171 grupos `mesmo_nome` alta e 149 fusões: falso positivo em Direito Penal × Penal Militar × Processual ("Ação penal", "Livramento condicional"), e nomes como "Conceito e objetivos" ou "Jurisprudência aplicada dos tribunais superiores". Entraram `RAMOS_DISPERSAO` (ramo diferente vira média) e `TOKENS_GENERICOS_DISPERSAO` (nome só de palavras genéricas).
- `mesma_norma` alta aceitava "Tipos de penalidades previstas na Lei nº 14.133", "Crimes tipificados no Estatuto do Desarmamento (Lei nº 10.826)" e nomes com duas normas ("Decreto ... e Portaria Conjunta ..."). Entrou a lista de palavras de recorte e a recusa de outro tipo de norma no nome.
- `nome_contido` repetia o mesmo conjunto por âncoras diferentes e usava como âncora termos genéricos ("Classificação: ..."): agora o genérico é testado no termo principal e o conjunto contido em outro grupo é descartado.
- Depois da regra de fusão entre níveis (KAN-64, 2026-10-12) o detector passou a propor `fundir` também para nó de nível diferente sem filhos. Os grupos de LGPD, LRF e suprimento de fundos foram consolidados pelo dono na mesma data e não aparecem mais.

## Grupos de confiança alta (ordenados por questões)

### Lei nº 9.784/1999 (processo administrativo) — `mesma_norma`, 23 questão(ões)

- Chave: `lei 9784`
- Nós:
  - `A-839c897054` [assunto] LEGISLAÇÃO › Lei nº 9.784/1999 (processo administrativo) — 17 questão(ões), 1 item(ns) de edital **(destino)**
  - `AL-fe35b41dc5` [assunto] DIREITO ADMINISTRATIVO › Processo Administrativo Federal (Lei nº 9.784/1999) — 6 questão(ões), 3 item(ns) de edital
  - `S-5a7e2f3f47` [subassunto] DIREITO ADMINISTRATIVO › Processo administrativo › Lei n.º 9.784/1999 — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-839c897054`
- Operações propostas (`fundir`):
  - `AL-fe35b41dc5` → `A-839c897054` — P-e41ee18f67
  - `S-5a7e2f3f47` → `A-839c897054` — P-9d742468c7

### Lei nº 8.429/1992 e suas alterações — `mesma_norma`, 19 questão(ões)

- Chave: `lei 8429`
- Nós:
  - `A-aed23dfa13` [assunto] DIREITO ADMINISTRATIVO › Improbidade Administrativa (Lei nº 8.429/1992) — 7 questão(ões), 5 item(ns) de edital
  - `S-064141b0b0` [subassunto] ÉTICA NO SERVIÇO PÚBLICO › Ética no setor público › Lei nº 8.429/1992 e suas alterações — 12 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-064141b0b0`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-aed23dfa13`

### Lei nº 8.112/1990 (Regime Jurídico Único) — `mesma_norma`, 14 questão(ões)

- Chave: `lei 8112`
- Nós:
  - `A-2f451322bf` [assunto] LEGISLAÇÃO › Lei nº 8.112/1990 (Regime Jurídico Único) — 11 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-b756f76410` [assunto] ÉTICA NO SERVIÇO PÚBLICO › Lei nº 8.112/1990 e alterações (Regime Jurídico dos Servidores Públicos Civis da União) — 0 questão(ões), 1 item(ns) de edital
  - `SL-42e925ffc4` [subassunto] DIREITO ADMINISTRATIVO › Agentes públicos › Lei nº 8.112/1990 (Regime Jurídico dos Servidores Públicos Civis da União) — 3 questão(ões), 4 item(ns) de edital
- Destino sugerido: `A-2f451322bf`
- Operações propostas (`fundir`):
  - `A-b756f76410` → `A-2f451322bf` — P-600e445117
  - `SL-42e925ffc4` → `A-2f451322bf` — P-094dd36238

### Gestão por competências — `mesmo_nome`, 11 questão(ões)

- Chave: `gestao por competencia`
- Nós:
  - `A-c3f41ab58f` [assunto] GESTÃO DE PESSOAS › Gestão por competências — 4 questão(ões), 3 item(ns) de edital
  - `S-23743b08cb` [subassunto] ADMINISTRAÇÃO PÚBLICA › Excelência nos serviços públicos › Gestão por competências — 2 questão(ões), 1 item(ns) de edital
  - `S-e02c45cebe` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Gestão por competências — 5 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-e02c45cebe`
- Operações propostas (`fundir`):
  - `A-c3f41ab58f` → `S-e02c45cebe` — P-0e5cb1b962
  - `S-23743b08cb` → `S-e02c45cebe` — P-95ebee37be

### Restos a pagar — `mesmo_nome`, 10 questão(ões)

- Chave: `resto a pagar`
- Nós:
  - `A-7e93595e9c` [assunto] Administração Orçamentária e Financeira › Restos a pagar — 2 questão(ões), 1 item(ns) de edital
  - `A-c4940b4cdd` [assunto] Contabilidade Aplicada ao Setor Público › Restos a pagar — 1 questão(ões), 1 item(ns) de edital
  - `SL-ddc4fce8dd` [subassunto] Administração Orçamentária e Financeira › Despesa pública › Restos a pagar — 7 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-ddc4fce8dd`
- Operações propostas (`fundir`):
  - `A-7e93595e9c` → `SL-ddc4fce8dd` — P-20d531ec90
  - `A-c4940b4cdd` → `SL-ddc4fce8dd` — P-faff52b3dc

### Impostos, taxas e contribuições — `mesmo_nome`, 9 questão(ões)

- Chave: `imposto taxa e contribuicao`
- Nós:
  - `S-c582d93e13` [subassunto] CONTABILIDADE TRIBUTÁRIA › tributos › Impostos, taxas e contribuições — 2 questão(ões), 1 item(ns) de edital
  - `S-cbbbb3a3ab` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Tributos › Impostos, taxas e contribuições — 7 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-cbbbb3a3ab`
- Operações propostas (`fundir`):
  - `S-c582d93e13` → `S-cbbbb3a3ab` — P-74503a1c22

### Lei nº 5.197/1967 — `mesma_norma`, 9 questão(ões)

- Chave: `lei 5197`
- Nós:
  - `S-bbf300b6a9` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei de Proteção à Fauna (Lei nº 5.197/1967) — 2 questão(ões), 1 item(ns) de edital
  - `S-de96054091` [subassunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Proteção da Fauna › Lei nº 5.197/1967 — 4 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-fb441690fe` [subassunto] PROTEÇÃO DA FAUNA › Proteção da Fauna › Lei nº 5.197/1967 — 3 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-de96054091`
- Operações propostas (`fundir`):
  - `S-bbf300b6a9` → `S-de96054091` — P-57dd4524c4
  - `S-fb441690fe` → `S-de96054091` — P-170bb36167

### Controle e pagamento de restos a pagar e de despesas de exercícios anteriores — `mesmo_nome`, 8 questão(ões)

- Chave: `controle e pagamento de resto a pagar e de despesa de exercicio anteriore`
- Nós:
  - `S-77be9f1aaa` [subassunto] Administração Orçamentária e Financeira › Programação, execução e controle de recursos orçamentários e financeiros › Controle e pagamento de restos a pagar e de despesas de exercícios anteriores — 4 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f05c5bf0a8` [subassunto] EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA › Programação, execução e controle de recursos orçamentários e financeiros › Controle e pagamento de restos a pagar e de despesas de exercícios anteriores — 4 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-77be9f1aaa`
- Operações propostas (`fundir`):
  - `S-f05c5bf0a8` → `S-77be9f1aaa` — P-7d34ed312b

### Lei de Acesso à Informação (Lei nº 12.527/2011) — `mesma_norma`, 8 questão(ões)

- Chave: `lei 12527`
- Nós:
  - `AL-c962e98e16` [assunto] DIREITO ADMINISTRATIVO › Lei de Acesso à Informação (Lei nº 12.527/2011) — 4 questão(ões), 5 item(ns) de edital **(destino)**
  - `S-256fbea4b7` [subassunto] DIREITO ADMINISTRATIVO › Lei de Acesso à Informação (Lei nº 12.527/2011) › Lei n.º 12.527/2011 (Lei de Acesso à Informação) — 4 questão(ões), 3 item(ns) de edital
- Destino sugerido: `AL-c962e98e16`
- Operações propostas (`fundir`):
  - `S-256fbea4b7` → `AL-c962e98e16` — P-9912f49f49

### Gestão de desempenho — `mesmo_nome`, 7 questão(ões)

- Chave: `gestao de desempenho`
- Nós:
  - `A-ddc2858431` [assunto] GESTÃO DE PESSOAS › Gestão de desempenho — 1 questão(ões), 1 item(ns) de edital
  - `S-7897996a2f` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Gestão de desempenho — 6 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-7897996a2f`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-ddc2858431`

### Ativo imobilizado — `mesmo_nome`, 6 questão(ões)

- Chave: `ativo imobilizado`
- Nós:
  - `A-951c1fd186` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Ativo Imobilizado — 1 questão(ões), 2 item(ns) de edital
  - `SL-710739892e` [subassunto] Contabilidade Aplicada ao Setor Público › Mensuração de ativos › Ativo imobilizado — 5 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-710739892e`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-951c1fd186`

### Ciclo orçamentário — `mesmo_nome`, 6 questão(ões)

- Chave: `ciclo orcamentario`
- Nós:
  - `A-e46d2efa1f` [assunto] Administração Orçamentária e Financeira › Ciclo orçamentário — 0 questão(ões), 2 item(ns) de edital
  - `SL-deacd8ffdb` [subassunto] Administração Orçamentária e Financeira › Orçamento público › Ciclo orçamentário — 6 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `SL-deacd8ffdb`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-e46d2efa1f`

### Empreendedorismo governamental e novas lideranças no setor público — `mesmo_nome`, 6 questão(ões)

- Chave: `empreendedorismo governamental e nova lideranca no setor publico`
- Nós:
  - `A-bc39d16392` [assunto] ADMINISTRAÇÃO PÚBLICA › Empreendedorismo governamental e novas lideranças no setor público — 1 questão(ões), 1 item(ns) de edital
  - `S-20a4d5051b` [subassunto] ADMINISTRAÇÃO PÚBLICA › A evolução da administração pública e a reforma do Estado › Empreendedorismo governamental e novas lideranças no setor público — 5 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-20a4d5051b`
- Operações propostas (`fundir`):
  - `A-bc39d16392` → `S-20a4d5051b` — P-aca8c0bcf7

### Classificações orçamentárias — `mesmo_nome`, 5 questão(ões)

- Chave: `classificacao orcamentaria`
- Nós:
  - `A-bafe9d9954` [assunto] Administração Orçamentária e Financeira › Classificações orçamentárias — 0 questão(ões), 1 item(ns) de edital
  - `SL-26343e233a` [subassunto] Administração Orçamentária e Financeira › Orçamento público no Brasil › Classificações orçamentárias — 5 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `SL-26343e233a`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-bafe9d9954`

### Comunicação interna e endomarketing — `mesmo_nome`, 5 questão(ões)

- Chave: `comunicacao interna e endomarketing`
- Nós:
  - `S-8a531032e3` [subassunto] COMUNICAÇÃO SOCIAL › Jornalismo institucional › Comunicação interna e endomarketing — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-e2784e35fc` [subassunto] COMUNICAÇÃO SOCIAL › Comunicação nas organizações › Comunicação interna e endomarketing — 2 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-8a531032e3`
- Operações propostas (`fundir`):
  - `S-e2784e35fc` → `S-8a531032e3` — P-e3605231bf

### Conceito, etapas, estágios e categorias econômicas — `mesmo_nome`, 5 questão(ões)

- Chave: `conceito etapa estagio e categoria economica`
- Nós:
  - `S-26865bee27` [subassunto] Contabilidade Aplicada ao Setor Público › Receita pública › Conceito, etapas, estágios e categorias econômicas — 4 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-dc9d094f20` [subassunto] Contabilidade Aplicada ao Setor Público › Despesa pública › Conceito, etapas, estágios e categorias econômicas — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-26865bee27`
- Operações propostas (`fundir`):
  - `S-dc9d094f20` → `S-26865bee27` — P-e44065f695

### Demonstração das variações patrimoniais — `mesmo_nome`, 5 questão(ões)

- Chave: `demonstracao das variacao patrimoniais`
- Nós:
  - `A-2c793cbbd0` [assunto] Contabilidade Aplicada ao Setor Público › Demonstração das variações patrimoniais — 2 questão(ões), 1 item(ns) de edital
  - `SL-b6bc85f7b8` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Demonstração das variações patrimoniais — 3 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-b6bc85f7b8`
- Operações propostas (`fundir`):
  - `A-2c793cbbd0` → `SL-b6bc85f7b8` — P-3d78ae470f

### Direitos e deveres individuais e coletivos — `mesmo_nome`, 5 questão(ões)

- Chave: `direito e devere individuais e coletivo`
- Nós:
  - `S-329ac8e3a2` [subassunto] DIREITO CONSTITUCIONAL › Direitos e garantias fundamentais › Direitos e deveres individuais e coletivos — 4 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-bed6cebe50` [subassunto] DIREITO CONSTITUCIONAL › Princípios Fundamentais. Direitos e garantias fundamentais › direitos e deveres individuais e coletivos — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-329ac8e3a2`
- Operações propostas (`fundir`):
  - `S-bed6cebe50` → `S-329ac8e3a2` — P-713677d9b2

### Ilícitos contra a fauna: tráfico, maus-tratos, caça, espécies exóticas — `mesmo_nome`, 5 questão(ões)

- Chave: `ilicito contra a fauna trafico maus trato caca especie exotica`
- Nós:
  - `S-92b109d6f0` [subassunto] PROTEÇÃO DA FAUNA › Proteção da Fauna › Ilícitos contra a fauna: tráfico, maus-tratos, caça, espécies exóticas — 2 questão(ões), 1 item(ns) de edital
  - `S-e44977db0a` [subassunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Proteção da Fauna › Ilícitos contra a fauna: tráfico, maus-tratos, caça, espécies exóticas — 3 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-e44977db0a`
- Operações propostas (`fundir`):
  - `S-92b109d6f0` → `S-e44977db0a` — P-6a450dea6f

### Papel do fiscalizador do contrato — `mesmo_nome`, 5 questão(ões)

- Chave: `papel do fiscalizador do contrato`
- Nós:
  - `S-81d5169c67` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos › Papel do fiscalizador do contrato — 5 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-8e673810b1` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Papel do fiscalizador do contrato — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-81d5169c67`
- Operações propostas (`fundir`):
  - `S-8e673810b1` → `S-81d5169c67` — P-3097a07e80

### Plano plurianual — `mesmo_nome`, 5 questão(ões)

- Chave: `plano plurianual`
- Nós:
  - `S-6f92815025` [subassunto] Administração Orçamentária e Financeira › Processo de planejamento orçamentário › Plano Plurianual — 0 questão(ões), 1 item(ns) de edital
  - `S-b4ba760ed5` [subassunto] Processo Legislativo › Processo Legislativo Orçamentário › Plano Plurianual (PPA). — 0 questão(ões), 1 item(ns) de edital
  - `SL-6d3f949b2d` [subassunto] Administração Orçamentária e Financeira › Orçamento público no Brasil › Plano plurianual — 5 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `SL-6d3f949b2d`
- Operações propostas (`fundir`):
  - `S-6f92815025` → `SL-6d3f949b2d` — P-c0ecc40420
  - `S-b4ba760ed5` → `SL-6d3f949b2d` — P-24bf9d9cba

### Programas de navegação (Microsoft Edge, Mozilla Firefox, Google Chrome e similares) — `mesmo_nome`, 5 questão(ões)

- Chave: `programa de navegacao`
- Nós:
  - `S-2c687e1a9a` [subassunto] INFORMÁTICA › Redes de computadores › Programas de navegação (Microsoft Edge, Mozilla Firefox, Google Chrome e similares) — 1 questão(ões), 1 item(ns) de edital
  - `S-342020e49a` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores › Programas de navegação (Microsoft Edge, Mozilla Firefox, Google Chrome e similares) — 4 questão(ões), 5 item(ns) de edital **(destino)**
- Destino sugerido: `S-342020e49a`
- Operações propostas (`fundir`):
  - `S-2c687e1a9a` → `S-342020e49a` — P-6d38568f2e

### Retenção e recolhimento de tributos incidentes sobre bens e serviços — `mesmo_nome`, 5 questão(ões)

- Chave: `retencao e recolhimento de tributo incidente sobre bem e servico`
- Nós:
  - `A-01bc744804` [assunto] EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA › Retenção e recolhimento de tributos incidentes sobre bens e serviços — 0 questão(ões), 1 item(ns) de edital
  - `A-709c7502bc` [assunto] Administração Orçamentária e Financeira › Retenção e recolhimento de tributos incidentes sobre bens e serviços — 5 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `A-709c7502bc`
- Operações propostas (`fundir`):
  - `A-01bc744804` → `A-709c7502bc` — P-776218ed78

### Retenções na fonte realizadas pela administração pública federal — `mesmo_nome`, 5 questão(ões)

- Chave: `retencao na fonte realizada pela administracao publica federal`
- Nós:
  - `A-5f4f5ad4f4` [assunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Retenções na fonte realizadas pela administração pública federal — 2 questão(ões), 1 item(ns) de edital
  - `A-6580fd8ec8` [assunto] CONTABILIDADE TRIBUTÁRIA › Retenções na fonte realizadas pela administração pública federal — 3 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `A-6580fd8ec8`
- Operações propostas (`fundir`):
  - `A-5f4f5ad4f4` → `A-6580fd8ec8` — P-eae1f0061d

### sistema operacional (ambiente Windows) — `mesmo_nome`, 5 questão(ões)

- Chave: `sistema operacional`
- Nós:
  - `A-1491e5b864` [assunto] INFORMÁTICA › sistema operacional (ambiente Windows) — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-4ff1e02efb` [assunto] TECNOLOGIA DA INFORMAÇÃO › sistema operacional (Windows) — 2 questão(ões), 3 item(ns) de edital
- Destino sugerido: `A-1491e5b864`
- Operações propostas (`fundir`):
  - `A-4ff1e02efb` → `A-1491e5b864` — P-9b7f41ed76

### Acompanhamento da execução contratual — `mesmo_nome`, 4 questão(ões)

- Chave: `acompanhamento da execucao contratual`
- Nós:
  - `S-0be4918914` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos › Acompanhamento da execução contratual — 4 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-fda50e8d63` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Acompanhamento da execução contratual — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-0be4918914`
- Operações propostas (`fundir`):
  - `S-fda50e8d63` → `S-0be4918914` — P-61e236c291

### Aplicativos para segurança (antivírus, firewall, anti-spyware etc.) — `mesmo_nome`, 4 questão(ões)

- Chave: `aplicativo para seguranca`
- Nós:
  - `S-139229c406` [subassunto] INFORMÁTICA › Segurança da informação › Aplicativos para segurança (antivírus, firewall, anti-spyware etc.) — 2 questão(ões), 1 item(ns) de edital
  - `S-b9c40349f1` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Segurança da informação › Aplicativos para segurança (antivírus, firewall, anti-spyware etc.) — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-b9c40349f1`
- Operações propostas (`fundir`):
  - `S-139229c406` → `S-b9c40349f1` — P-2a2192044c

### Ativo intangível — `mesmo_nome`, 4 questão(ões)

- Chave: `ativo intangivel`
- Nós:
  - `A-d738e3771b` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Ativo Intangível — 1 questão(ões), 1 item(ns) de edital
  - `SL-91b70bfb30` [subassunto] Contabilidade Aplicada ao Setor Público › Mensuração de ativos › Ativo intangível — 3 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-91b70bfb30`
- Operações propostas (`fundir`):
  - `A-d738e3771b` → `SL-91b70bfb30` — P-5acf64d430

### Comportamento, clima e cultura organizacional — `mesmo_nome`, 4 questão(ões)

- Chave: `comportamento clima e cultura organizacional`
- Nós:
  - `A-4c006b192d` [assunto] GESTÃO DE PESSOAS › Comportamento, clima e cultura organizacional — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-15b4e945c7` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Comportamento, clima e cultura organizacional — 2 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-4c006b192d`
- Operações propostas (`fundir`):
  - `S-15b4e945c7` → `A-4c006b192d` — P-0ca031d811

### Gerenciamento de conflitos — `mesmo_nome`, 4 questão(ões)

- Chave: `gerenciamento de conflito`
- Nós:
  - `A-26490d5751` [assunto] GESTÃO DE PESSOAS › Gerenciamento de conflitos — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-85e7dd27de` [subassunto] Psicologia › Gestão de pessoas nas organizações › Gerenciamento de conflitos — 1 questão(ões), 1 item(ns) de edital
  - `S-f06ff8a230` [subassunto] GESTÃO DE PESSOAS › O indivíduo e o contexto organizacional: variáveis individuais, grupais e organizacionais › Gerenciamento de conflitos — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-26490d5751`
- Operações propostas (`fundir`):
  - `S-85e7dd27de` → `A-26490d5751` — P-9e54104394
  - `S-f06ff8a230` → `A-26490d5751` — P-3c25287eba

### Gestão de conflito — `mesmo_nome`, 4 questão(ões)

- Chave: `gestao de conflito`
- Nós:
  - `A-be43ba5543` [assunto] SEGURANÇA DE DIGNITÁRIOS › gestão de conflitos — 0 questão(ões), 1 item(ns) de edital
  - `S-f6cf9a40fe` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Gestão de conflito — 4 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-f6cf9a40fe`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-be43ba5543`

### Treinamento e Desenvolvimento — `mesmo_nome`, 4 questão(ões)

- Chave: `treinamento e desenvolvimento`
- Nós:
  - `S-a4eeb7ac63` [subassunto] GESTÃO DE PESSOAS › Processos de gestão de pessoas › Treinamento e Desenvolvimento — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-b5c315a585` [subassunto] Pedagogia › Educação corporativa › Treinamento e Desenvolvimento — 2 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-a4eeb7ac63`
- Operações propostas (`fundir`):
  - `S-b5c315a585` → `S-a4eeb7ac63` — P-7e2c877d42

### Accountability — `mesmo_nome`, 3 questão(ões)

- Chave: `accountability`
- Nós:
  - `S-39f2cd6d84` [subassunto] ADMINISTRAÇÃO PÚBLICA › Transparência da administração pública › Accountability — 1 questão(ões), 1 item(ns) de edital
  - `S-68a76ed346` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governo eletrônico › Accountability — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-68a76ed346`
- Operações propostas (`fundir`):
  - `S-39f2cd6d84` → `S-68a76ed346` — P-ece2c0c7e0

### Computação na nuvem (cloud computing) — `mesmo_nome`, 3 questão(ões)

- Chave: `computacao na nuvem`
- Nós:
  - `S-118c1d5531` [subassunto] INFORMÁTICA › Redes de computadores › Computação na nuvem (cloud computing) — 1 questão(ões), 1 item(ns) de edital
  - `S-1873949dfa` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores › Computação na nuvem (cloud computing) — 2 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `S-1873949dfa`
- Operações propostas (`fundir`):
  - `S-118c1d5531` → `S-1873949dfa` — P-1c78d04d85

### Conceitos básicos de inteligência artificial — `mesmo_nome`, 3 questão(ões)

- Chave: `conceito basico de inteligencia artificial`
- Nós:
  - `S-37df583de2` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Tecnologias emergentes no setor público › Conceitos básicos de inteligência artificial — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-fe253f32ca` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Inteligência Artificial › Conceitos Básicos de Inteligência Artificial — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-37df583de2`
- Operações propostas (`fundir`):
  - `S-fe253f32ca` → `S-37df583de2` — P-d5dd4049de

### Conceitos biológicos e taxonomia de fauna — `mesmo_nome`, 3 questão(ões)

- Chave: `conceito biologico e taxonomia de fauna`
- Nós:
  - `S-5cc260e2d9` [subassunto] PROTEÇÃO DA FAUNA › Proteção da Fauna › Conceitos biológicos e taxonomia de fauna — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ebf0ae7f49` [subassunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Proteção da Fauna › Conceitos biológicos e taxonomia de fauna — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-5cc260e2d9`
- Operações propostas (`fundir`):
  - `S-ebf0ae7f49` → `S-5cc260e2d9` — P-1560db1f02

### Contribuição Previdenciária (INSS) — `mesmo_nome`, 3 questão(ões)

- Chave: `contribuicao previdenciaria`
- Nós:
  - `S-6d18b39d2a` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Retenções na fonte realizadas pela administração pública federal › Contribuição previdenciária (INSS) — 1 questão(ões), 1 item(ns) de edital
  - `S-bb72202a0b` [subassunto] CONTABILIDADE TRIBUTÁRIA › Retenções na fonte realizadas pela administração pública federal › Contribuição Previdenciária (INSS) — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-bb72202a0b`
- Operações propostas (`fundir`):
  - `S-6d18b39d2a` → `S-bb72202a0b` — P-678e5d32cc

### Controle social e cidadania — `mesmo_nome`, 3 questão(ões)

- Chave: `controle social e cidadania`
- Nós:
  - `S-2f482d5039` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governo eletrônico › Controle social e cidadania — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-5227794828` [subassunto] ADMINISTRAÇÃO PÚBLICA › Transparência da administração pública › Controle social e cidadania — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-2f482d5039`
- Operações propostas (`fundir`):
  - `S-5227794828` → `S-2f482d5039` — P-a50b22650d

### Despesa de exercícios anteriores — `mesmo_nome`, 3 questão(ões)

- Chave: `despesa de exercicio anteriore`
- Nós:
  - `A-25cda6b4f4` [assunto] Administração Orçamentária e Financeira › Despesa de exercícios anteriores — 2 questão(ões), 3 item(ns) de edital **(destino)**
  - `SL-0b8742283d` [subassunto] Administração Orçamentária e Financeira › Despesa pública › Despesas de exercícios anteriores — 1 questão(ões), 3 item(ns) de edital
- Destino sugerido: `A-25cda6b4f4`
- Operações propostas (`fundir`):
  - `SL-0b8742283d` → `A-25cda6b4f4` — P-c21c0f04c2

### Edição de textos, planilhas e apresentações (ambiente Microsoft Office) — `mesmo_nome`, 3 questão(ões)

- Chave: `edicao de texto planilha e apresentacao`
- Nós:
  - `A-978f55faf0` [assunto] INFORMÁTICA › Edição de textos, planilhas e apresentações (ambiente Microsoft Office) — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-c94346bfdf` [assunto] TECNOLOGIA DA INFORMAÇÃO › Edição de textos, planilhas e apresentações (ambiente Microsoft Office) — 1 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-978f55faf0`
- Operações propostas (`fundir`):
  - `A-c94346bfdf` → `A-978f55faf0` — P-57b9cfb74d

### Educação corporativa — `mesmo_nome`, 3 questão(ões)

- Chave: `educacao corporativa`
- Nós:
  - `A-a5fe133e1c` [assunto] Pedagogia › Educação corporativa — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-ff6da2f639` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Educação corporativa — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-a5fe133e1c`
- Operações propostas (`fundir`):
  - `S-ff6da2f639` → `A-a5fe133e1c` — P-d09cb05fab

### Emprego de tempos e modos verbais — `mesmo_nome`, 3 questão(ões)

- Chave: `emprego de tempo e modo verbais`
- Nós:
  - `A-36cf1b7c35` [assunto] LÍNGUA PORTUGUESA › Emprego de tempos e modos verbais — 0 questão(ões), 1 item(ns) de edital
  - `S-af705f78a3` [subassunto] LÍNGUA PORTUGUESA › Domínio dos mecanismos de coesão textual › Emprego de tempos e modos verbais — 3 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-af705f78a3`
- Operações propostas (`fundir`):
  - `A-36cf1b7c35` → `S-af705f78a3` — P-b4b55de65b

### Gestão do conhecimento — `mesmo_nome`, 3 questão(ões)

- Chave: `gestao do conhecimento`
- Nós:
  - `A-f63bbab19f` [assunto] GESTÃO DE PESSOAS › Gestão do conhecimento — 1 questão(ões), 2 item(ns) de edital
  - `S-f918993828` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Gestão do conhecimento — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-f918993828`
- Operações propostas (`fundir`):
  - `A-f63bbab19f` → `S-f918993828` — P-f598fd0d51

### Lei nº 14.133/2021 — `mesma_norma`, 3 questão(ões)

- Chave: `lei 14133`
- Nós:
  - `A-ceea19ae78` [assunto] LICITAÇÕES E CONTRATOS › Lei nº 14.133/2021 — 0 questão(ões), 1 item(ns) de edital
  - `S-bf1fb476cd` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Legislação aplicável à contratação de bens e serviços › Lei nº 14.133/2021 — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f778630a9e` [subassunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Governança e Gestão de TIC › Lei nº 14.133/2021 — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-bf1fb476cd`
- Operações propostas (`fundir`):
  - `S-f778630a9e` → `S-bf1fb476cd` — P-bb21a3aa90
- Sem operação (nível diferente com filhos, decisão do dono): `A-ceea19ae78`

### Lei de Diretrizes Orçamentárias (LDO) — `mesmo_nome`, 3 questão(ões)

- Chave: `lei de diretrize orcamentaria`
- Nós:
  - `A-99c9a06d12` [assunto] Administração Orçamentária e Financeira › Lei de Diretrizes Orçamentárias (LDO) — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-6c5a3e9c3f` [subassunto] Processo Legislativo › Processo Legislativo Orçamentário › Lei de Diretrizes Orçamentárias (LDO). — 0 questão(ões), 1 item(ns) de edital
  - `S-e7986333eb` [subassunto] Administração Orçamentária e Financeira › Processo de planejamento orçamentário › Lei de Diretrizes Orçamentárias — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-99c9a06d12`
- Operações propostas (`fundir`):
  - `S-6c5a3e9c3f` → `A-99c9a06d12` — P-dff02aca55
  - `S-e7986333eb` → `A-99c9a06d12` — P-0c9942b632

### Ações em tesouraria — `mesmo_nome`, 2 questão(ões)

- Chave: `acao em tesouraria`
- Nós:
  - `S-8836d8315d` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Ações em tesouraria — 0 questão(ões), 1 item(ns) de edital
  - `S-c2bcb46b92` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio líquido › Ações em tesouraria — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c2bcb46b92`
- Operações propostas (`fundir`):
  - `S-8836d8315d` → `S-c2bcb46b92` — P-d1c7394c2f

### Armazenamento de dados na nuvem (cloud storage) — `mesmo_nome`, 2 questão(ões)

- Chave: `armazenamento de dado na nuvem`
- Nós:
  - `S-b82119f540` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores › Armazenamento de dados na nuvem (cloud storage) — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-c72a6c4a00` [subassunto] INFORMÁTICA › Segurança da informação › Armazenamento de dados na nuvem (cloud storage) — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-b82119f540`
- Operações propostas (`fundir`):
  - `S-c72a6c4a00` → `S-b82119f540` — P-c5eaf3a25f

### Avaliação psicológica dos fatores psicossociais do trabalho — `mesmo_nome`, 2 questão(ões)

- Chave: `avaliacao psicologica dos fatore psicossociais do trabalho`
- Nós:
  - `S-87ee90c4fe` [subassunto] Psicologia › Psicologia social e aplicação no trabalho › Avaliação psicológica dos fatores psicossociais do trabalho — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-aba3b71611` [subassunto] Psicologia › Psicodinâmica do trabalho: promoção da saúde do trabalhador nas organizações › Avaliação psicológica dos fatores psicossociais do trabalho — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-87ee90c4fe`
- Operações propostas (`fundir`):
  - `S-aba3b71611` → `S-87ee90c4fe` — P-0ed7e26103

### Big data — `mesmo_nome`, 2 questão(ões)

- Chave: `big data`
- Nós:
  - `A-e93da13346` [assunto] TECNOLOGIA DA INFORMAÇÃO › Big Data — 0 questão(ões), 1 item(ns) de edital
  - `S-c9eb4ae688` [subassunto] BANCO DE DADOS E CIÊNCIA DE DADOS › Ciência de dados › Big data — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c9eb4ae688`
- Operações propostas (`fundir`):
  - `A-e93da13346` → `S-c9eb4ae688` — P-8c530b7d13

### Crimes contra a administração pública — `mesmo_nome`, 2 questão(ões)

- Chave: `crime contra a administracao publica`
- Nós:
  - `A-564f19e124` [assunto] DIREITO PENAL › Crimes contra a administração pública — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-fd4cac0e9b` [subassunto] DIREITO PENAL › Crimes em espécie do Código Penal › Crimes contra a administração pública — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-564f19e124`
- Operações propostas (`fundir`):
  - `S-fd4cac0e9b` → `A-564f19e124` — P-efd6a25167

### Demonstração dos fluxos de caixa — `mesmo_nome`, 2 questão(ões)

- Chave: `demonstracao dos fluxo de caixa`
- Nós:
  - `S-41bf56e94c` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis pela legislação societária e pelas Normas Brasileiras de Contabilidade › Demonstração dos Fluxos de Caixa — 0 questão(ões), 1 item(ns) de edital
  - `S-4925059bb1` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis conforme a legislação societária, os princípios fundamentais da contabilidade e os pronunciamentos contábeis do Comitê de Pronunciamentos Contábeis (CPC) › Demonstração dos fluxos de caixa (métodos direto e indireto) — 1 questão(ões), 1 item(ns) de edital
  - `SL-6f213d5cd7` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Demonstração dos fluxos de caixa — 1 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `SL-6f213d5cd7`
- Operações propostas (`fundir`):
  - `S-41bf56e94c` → `SL-6f213d5cd7` — P-1dde39682f
  - `S-4925059bb1` → `SL-6f213d5cd7` — P-ac6220b4e5

### Design thinking — `mesmo_nome`, 2 questão(ões)

- Chave: `design thinking`
- Nós:
  - `S-7258e86b3c` [subassunto] COMUNICAÇÃO SOCIAL › Comunicação nas organizações › Design thinking — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-eb23e19ae9` [subassunto] ADMINISTRAÇÃO PÚBLICA › Inovação na gestão pública › Design Thinking — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-7258e86b3c`
- Operações propostas (`fundir`):
  - `S-eb23e19ae9` → `S-7258e86b3c` — P-7121abd643

### Diagnóstico diferencial — `mesmo_nome`, 2 questão(ões)

- Chave: `diagnostico diferencial`
- Nós:
  - `S-3fc78aabd9` [subassunto] Psicologia › Psicopatologia › Diagnóstico diferencial — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-9748bdccef` [subassunto] Psicologia › Avaliação psicológica e psicodiagnóstico › Diagnóstico diferencial — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-3fc78aabd9`
- Operações propostas (`fundir`):
  - `S-9748bdccef` → `S-3fc78aabd9` — P-041eb84795

### direitos sociais — `mesmo_nome`, 2 questão(ões)

- Chave: `direito sociais`
- Nós:
  - `S-1054529bc2` [subassunto] DIREITO CONSTITUCIONAL › Princípios Fundamentais. Direitos e garantias fundamentais › direitos sociais — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-426e838f92` [subassunto] DIREITO CONSTITUCIONAL › Direitos e garantias fundamentais › Direitos sociais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-1054529bc2`
- Operações propostas (`fundir`):
  - `S-426e838f92` → `S-1054529bc2` — P-cf2e8e9ca8

### Dívida ativa — `mesmo_nome`, 2 questão(ões)

- Chave: `divida ativa`
- Nós:
  - `A-68a52d046c` [assunto] Administração Orçamentária e Financeira › Dívida ativa — 0 questão(ões), 1 item(ns) de edital
  - `SL-7bc2e81a2b` [subassunto] Administração Orçamentária e Financeira › Receita pública › Dívida ativa — 2 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-7bc2e81a2b`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-68a52d046c`

### Evolução da proteção, defesa e direitos dos animais — `mesmo_nome`, 2 questão(ões)

- Chave: `evolucao da protecao defesa e direito dos animais`
- Nós:
  - `S-03bfe7e415` [subassunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Proteção da Fauna › Evolução da proteção, defesa e direitos dos animais — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-a28906fca2` [subassunto] PROTEÇÃO DA FAUNA › Proteção da Fauna › Evolução da proteção, defesa e direitos dos animais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-03bfe7e415`
- Operações propostas (`fundir`):
  - `S-a28906fca2` → `S-03bfe7e415` — P-aba61180c0

### Fiscalização Contábil, Financeira e Orçamentária — `mesmo_nome`, 2 questão(ões)

- Chave: `fiscalizacao contabil financeira e orcamentaria`
- Nós:
  - `A-807d3737d2` [assunto] DIREITO CONSTITUCIONAL › Fiscalização Contábil, Financeira e Orçamentária — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-1bb4378a46` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Fiscalização contábil, financeira e orçamentária — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-807d3737d2`
- Operações propostas (`fundir`):
  - `S-1bb4378a46` → `A-807d3737d2` — P-6b78bc963b

### Fornecedores, obrigações fiscais e outras obrigações — `mesmo_nome`, 2 questão(ões)

- Chave: `fornecedore obrigacao fiscais e outra obrigacao`
- Nós:
  - `A-48cc447a15` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Fornecedores, obrigações fiscais e outras obrigações — 0 questão(ões), 2 item(ns) de edital
  - `S-6811408864` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Passivo exigível › Fornecedores, obrigações fiscais e outras obrigações — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-6811408864`
- Operações propostas (`fundir`):
  - `A-48cc447a15` → `S-6811408864` — P-6d0f375cff

### Guia de Recolhimento da União (GRU) — `mesmo_nome`, 2 questão(ões)

- Chave: `guia de recolhimento da uniao`
- Nós:
  - `S-8fbd0d2554` [subassunto] EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA › Programação, execução e controle de recursos orçamentários e financeiros › Guia de Recolhimento da União (GRU) — 0 questão(ões), 1 item(ns) de edital
  - `S-ea1413fe47` [subassunto] Administração Orçamentária e Financeira › Programação, execução e controle de recursos orçamentários e financeiros › Guia de Recolhimento da União (GRU) — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-ea1413fe47`
- Operações propostas (`fundir`):
  - `S-8fbd0d2554` → `S-ea1413fe47` — P-1aa2e902bd

### Indicadores de endividamento — `mesmo_nome`, 2 questão(ões)

- Chave: `indicadore de endividamento`
- Nós:
  - `A-9c94e8feaf` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Indicadores de endividamento — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d3cdae7a96` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise econômico-financeira › Indicadores de endividamento — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-9c94e8feaf`
- Operações propostas (`fundir`):
  - `S-d3cdae7a96` → `A-9c94e8feaf` — P-a4582e330d

### Indicadores de liquidez — `mesmo_nome`, 2 questão(ões)

- Chave: `indicadore de liquidez`
- Nós:
  - `A-02711a7519` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Indicadores de liquidez — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-73293ed643` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise econômico-financeira › Indicadores de liquidez — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-02711a7519`
- Operações propostas (`fundir`):
  - `S-73293ed643` → `A-02711a7519` — P-82659e76cc

### Estatuto da Pessoa Idosa (Lei nº 10.741/2003 e suas alterações) — `mesma_norma`, 2 questão(ões)

- Chave: `lei 10741`
- Nós:
  - `A-1d78a93881` [assunto] LEGISLAÇÃO RELACIONADA › Estatuto da Pessoa Idosa (Lei nº 10.741/2003 e suas alterações) — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-1c70e095aa` [subassunto] Serviço Social › Políticas Sociais › Estatuto da Pessoa Idosa (Lei nº 10.741/2003) — 1 questão(ões), 1 item(ns) de edital
  - `S-86e0da1cf3` [subassunto] DIREITO CIVIL › Legislação especial › Lei nº 10.741/2003 (Estatuto da Pessoa Idosa) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-1d78a93881`
- Operações propostas (`fundir`):
  - `S-1c70e095aa` → `A-1d78a93881` — P-7f634ddf3c
  - `S-86e0da1cf3` → `A-1d78a93881` — P-a5be14263c

### Lei nº 4.320/1964 e suas alterações — `mesma_norma`, 2 questão(ões)

- Chave: `lei 4320`
- Nós:
  - `AL-528d504ae8` [assunto] Administração Orçamentária e Financeira › Lei nº 4.320/1964 e suas alterações — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `AL-d92ca18389` [assunto] Contabilidade Aplicada ao Setor Público › Lei nº 4.320/1964 — 0 questão(ões), 2 item(ns) de edital
  - `S-674794e3b4` [subassunto] Contabilidade Aplicada ao Setor Público › Definições, finalidade, componentes, estrutura e conteúdo das demonstrações › de acordo com a Lei nº 4.320/1964 e suas alterações — 0 questão(ões), 1 item(ns) de edital
  - `S-7eb8abf86d` [subassunto] Administração Orçamentária e Financeira › Lei nº 4.320/1964 e suas alterações › Lei nº 4.320/1964 — 1 questão(ões), 1 item(ns) de edital
  - `S-c60607b2f3` [subassunto] Administração Orçamentária e Financeira › Direito Financeiro e Tributário › Lei nº 4.320/1964 (Normas Gerais de Direito Financeiro) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-528d504ae8`
- Operações propostas (`fundir`):
  - `AL-d92ca18389` → `AL-528d504ae8` — P-2f06c206d7
  - `S-674794e3b4` → `AL-528d504ae8` — P-250c6ea66b
  - `S-7eb8abf86d` → `AL-528d504ae8` — P-634eb8b149
  - `S-c60607b2f3` → `AL-528d504ae8` — P-dc412fa78e

### Procedimentos de backup — `mesmo_nome`, 2 questão(ões)

- Chave: `procedimento de backup`
- Nós:
  - `S-1e33c3aa43` [subassunto] INFORMÁTICA › Segurança da informação › Procedimentos de backup — 1 questão(ões), 1 item(ns) de edital
  - `S-408baf00c1` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Segurança da informação › Procedimentos de backup — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-408baf00c1`
- Operações propostas (`fundir`):
  - `S-1e33c3aa43` → `S-408baf00c1` — P-c724a26438

### Qualidade de vida no trabalho — `mesmo_nome`, 2 questão(ões)

- Chave: `qualidade de vida no trabalho`
- Nós:
  - `A-024bdafe23` [assunto] Psicologia › Qualidade de vida no trabalho — 1 questão(ões), 1 item(ns) de edital
  - `A-564f15a1ae` [assunto] GESTÃO DE PESSOAS › Qualidade de vida no trabalho — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-31051a8057` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Qualidade de vida no trabalho — 0 questão(ões), 1 item(ns) de edital
  - `S-6e9a2a7f98` [subassunto] Psicologia › Psicologia social e aplicação no trabalho › Qualidade de Vida no trabalho — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-564f15a1ae`
- Operações propostas (`fundir`):
  - `A-024bdafe23` → `A-564f15a1ae` — P-c37199232b
  - `S-31051a8057` → `A-564f15a1ae` — P-02a6e78849
  - `S-6e9a2a7f98` → `A-564f15a1ae` — P-b20b27c531

### Redes de computadores — `mesmo_nome`, 2 questão(ões)

- Chave: `rede de computadore`
- Nós:
  - `A-43bae408c0` [assunto] INFORMÁTICA › Redes de computadores — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-4b13bcdab5` [assunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores — 0 questão(ões), 4 item(ns) de edital
- Destino sugerido: `A-43bae408c0`
- Operações propostas (`fundir`):
  - `A-4b13bcdab5` → `A-43bae408c0` — P-24447d11ea

### Transparência da administração pública — `mesmo_nome`, 2 questão(ões)

- Chave: `transparencia da administracao publica`
- Nós:
  - `A-1e3a391b16` [assunto] ADMINISTRAÇÃO PÚBLICA › Transparência da administração pública — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-5a45296072` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governo eletrônico › Transparência da administração pública — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-1e3a391b16`
- Operações propostas (`fundir`):
  - `S-5a45296072` → `A-1e3a391b16` — P-7efb0dc891

### Ajustes de avaliação patrimonial — `mesmo_nome`, 1 questão(ões)

- Chave: `ajuste de avaliacao patrimonial`
- Nós:
  - `S-620354442a` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Ajustes de avaliação patrimonial — 0 questão(ões), 1 item(ns) de edital
  - `S-8c1e381570` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio líquido › Ajustes de avaliação patrimonial — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-8c1e381570`
- Operações propostas (`fundir`):
  - `S-620354442a` → `S-8c1e381570` — P-6ddb168675

### Análise de Agrupamento — `mesmo_nome`, 1 questão(ões)

- Chave: `analise de agrupamento`
- Nós:
  - `S-011f890085` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Técnicas para pré-processamento de dados › Análise de agrupamentos (clusterização) — 0 questão(ões), 1 item(ns) de edital
  - `S-c2069058fb` [subassunto] Estatística › Análise Multivariada › Análise de Agrupamento — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c2069058fb`
- Operações propostas (`fundir`):
  - `S-011f890085` → `S-c2069058fb` — P-7ed081a8ef

### Análise de variância — `mesmo_nome`, 1 questão(ões)

- Chave: `analise de variancia`
- Nós:
  - `S-eb4d69ec7f` [subassunto] Estatística › Análise de regressão linear › Análise de variância — 0 questão(ões), 1 item(ns) de edital
  - `S-ef1b68b83c` [subassunto] Farmácia › Métodos estatísticos aplicados à farmacologia › Análise de variância — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-ef1b68b83c`
- Operações propostas (`fundir`):
  - `S-eb4d69ec7f` → `S-ef1b68b83c` — P-ad006be455

### Balanced scorecard — `mesmo_nome`, 1 questão(ões)

- Chave: `balanced scorecard`
- Nós:
  - `A-49f101efee` [assunto] ADMINISTRAÇÃO GERAL › Balanced scorecard — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-5d901cc3bc` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Balanced scorecard — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-49f101efee`
- Operações propostas (`fundir`):
  - `S-5d901cc3bc` → `A-49f101efee` — P-58f57f8ba0

### Balanço financeiro — `mesmo_nome`, 1 questão(ões)

- Chave: `balanco financeiro`
- Nós:
  - `A-9c2a16f9e9` [assunto] Contabilidade Aplicada ao Setor Público › Balanço Financeiro — 0 questão(ões), 1 item(ns) de edital
  - `SL-7465938133` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Balanço financeiro — 1 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-7465938133`
- Operações propostas (`fundir`):
  - `A-9c2a16f9e9` → `SL-7465938133` — P-6fe13791e5

### Balanço patrimonial — `mesmo_nome`, 1 questão(ões)

- Chave: `balanco patrimonial`
- Nós:
  - `A-39d48d8e2d` [assunto] Contabilidade Aplicada ao Setor Público › Balanço patrimonial — 0 questão(ões), 1 item(ns) de edital
  - `S-21a4e5471a` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis conforme a legislação societária, os princípios fundamentais da contabilidade e os pronunciamentos contábeis do Comitê de Pronunciamentos Contábeis (CPC) › Balanço patrimonial — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-31e8c972af` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis pela legislação societária e pelas Normas Brasileiras de Contabilidade › Balanço Patrimonial — 0 questão(ões), 1 item(ns) de edital
  - `SL-c61768d51f` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Balanço patrimonial — 0 questão(ões), 3 item(ns) de edital
- Destino sugerido: `S-21a4e5471a`
- Operações propostas (`fundir`):
  - `A-39d48d8e2d` → `S-21a4e5471a` — P-bca6f9c427
  - `S-31e8c972af` → `S-21a4e5471a` — P-fc716f9dd5
  - `SL-c61768d51f` → `S-21a4e5471a` — P-58659e0253

### Conceitos de organização e de gerenciamento de informações, arquivos, pastas e programas — `mesmo_nome`, 1 questão(ões)

- Chave: `conceito de organizacao e de gerenciamento de informacao arquivo pasta e programa`
- Nós:
  - `A-02cea950e3` [assunto] INFORMÁTICA › Conceitos de organização e de gerenciamento de informações, arquivos, pastas e programas — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-3154ea9de3` [assunto] TECNOLOGIA DA INFORMAÇÃO › Conceitos de organização e de gerenciamento de informações, arquivos, pastas e programas — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-02cea950e3`
- Operações propostas (`fundir`):
  - `A-3154ea9de3` → `A-02cea950e3` — P-69242552bb

### Contagem de prazo — `mesmo_nome`, 1 questão(ões)

- Chave: `contagem de prazo`
- Nós:
  - `S-397e736766` [subassunto] DIREITO PENAL › Código Penal › Contagem de prazo — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d9a5ebfeb3` [subassunto] DIREITO PENAL › Aplicação da lei penal › Contagem de prazo — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-397e736766`
- Operações propostas (`fundir`):
  - `S-d9a5ebfeb3` → `S-397e736766` — P-255ee1aa38

### Convergências e diferenças entre a gestão pública e a gestão privada — `mesmo_nome`, 1 questão(ões)

- Chave: `convergencia e diferenca entre a gestao publica e a gestao privada`
- Nós:
  - `A-88802b0275` [assunto] ADMINISTRAÇÃO PÚBLICA › Convergências e diferenças entre a gestão pública e a gestão privada — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-317ebe2fda` [subassunto] ADMINISTRAÇÃO PÚBLICA › A evolução da administração pública e a reforma do Estado › Convergências e diferenças entre a gestão pública e a gestão privada — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-88802b0275`
- Operações propostas (`fundir`):
  - `S-317ebe2fda` → `A-88802b0275` — P-9bb7d38d00

### Créditos adicionais — `mesmo_nome`, 1 questão(ões)

- Chave: `credito adicionais`
- Nós:
  - `A-1d5569887f` [assunto] Contabilidade Aplicada ao Setor Público › Créditos Adicionais — 0 questão(ões), 1 item(ns) de edital
  - `A-6046b68747` [assunto] Administração Orçamentária e Financeira › Créditos adicionais — 0 questão(ões), 1 item(ns) de edital
  - `S-97ff1bc235` [subassunto] Administração Orçamentária e Financeira › Orçamento público no Brasil › Créditos adicionais — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-97ff1bc235`
- Operações propostas (`fundir`):
  - `A-1d5569887f` → `S-97ff1bc235` — P-c6cb042933
- Sem operação (nível diferente com filhos, decisão do dono): `A-6046b68747`

### Crimes contra a fé pública — `mesmo_nome`, 1 questão(ões)

- Chave: `crime contra a fe publica`
- Nós:
  - `A-6913a5d111` [assunto] DIREITO PENAL › Crimes contra a fé pública — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-14a65c5811` [subassunto] DIREITO PENAL › Crimes em espécie do Código Penal › Crimes contra a fé pública — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-6913a5d111`
- Operações propostas (`fundir`):
  - `S-14a65c5811` → `A-6913a5d111` — P-e49f731077

### Decreto nº 11.367/2023 (Comissão Interministerial Permanente para prevenir e controlar o d — `mesma_norma`, 1 questão(ões)

- Chave: `decreto 11367`
- Nós:
  - `A-14a2673393` [assunto] LEGISLAÇÃO AMBIENTAL › Decreto nº 11.367/2023 — 0 questão(ões), 1 item(ns) de edital
  - `S-c54fa43b29` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Decreto nº 11.367/2023 (Comissão Interministerial Permanente para prevenir e controlar o desmatamento, entre outros) — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-c54fa43b29`
- Operações propostas (`fundir`):
  - `A-14a2673393` → `S-c54fa43b29` — P-03f5141e9d

### Decreto nº 11.462/2023 — `mesma_norma`, 1 questão(ões)

- Chave: `decreto 11462`
- Nós:
  - `A-77b2b224ae` [assunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Decreto nº 11.462/2023 — 0 questão(ões), 1 item(ns) de edital
  - `S-acf7c06d18` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Licitações e contratos administrativos › Decreto nº 11.462/2023 — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ae05bb9298` [subassunto] DIREITO ADMINISTRATIVO › Licitação › Decreto nº 11.462/2023 — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `S-acf7c06d18`
- Operações propostas (`fundir`):
  - `A-77b2b224ae` → `S-acf7c06d18` — P-158e1f42e0
  - `S-ae05bb9298` → `S-acf7c06d18` — P-48ffdcfe27

### Decreto nº 70.235/1972 e suas alterações (Processo Administrativo Fiscal) — `mesma_norma`, 1 questão(ões)

- Chave: `decreto 70235`
- Nós:
  - `S-a16b2491b7` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Decreto nº 70.235/1972 (Processo Administrativo Fiscal) — 0 questão(ões), 1 item(ns) de edital
  - `S-e1f995cd41` [subassunto] Administração Orçamentária e Financeira › Direito Financeiro e Tributário › Decreto nº 70.235/1972 e suas alterações (Processo Administrativo Fiscal) — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-e1f995cd41`
- Operações propostas (`fundir`):
  - `S-a16b2491b7` → `S-e1f995cd41` — P-104df6beb5

### Demonstração das mutações do patrimônio líquido — `mesmo_nome`, 1 questão(ões)

- Chave: `demonstracao das mutacao do patrimonio liquido`
- Nós:
  - `A-66ad1f59ec` [assunto] Contabilidade Aplicada ao Setor Público › Demonstração das Mutações do Patrimônio Líquido — 0 questão(ões), 1 item(ns) de edital
  - `S-85ebbd88e8` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis conforme a legislação societária, os princípios fundamentais da contabilidade e os pronunciamentos contábeis do Comitê de Pronunciamentos Contábeis (CPC) › Demonstração das mutações do patrimônio líquido — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-9095aa5170` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis pela legislação societária e pelas Normas Brasileiras de Contabilidade › Demonstração das Mutações do Patrimônio Líquido — 0 questão(ões), 1 item(ns) de edital
  - `SL-dafa265fea` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Demonstração das mutações do patrimônio líquido — 0 questão(ões), 3 item(ns) de edital
- Destino sugerido: `S-85ebbd88e8`
- Operações propostas (`fundir`):
  - `A-66ad1f59ec` → `S-85ebbd88e8` — P-ea7ca8313c
  - `S-9095aa5170` → `S-85ebbd88e8` — P-e678c1d6e9
  - `SL-dafa265fea` → `S-85ebbd88e8` — P-280eae521a

### Demonstração de fluxos de caixa (métodos direto e indireto) — `mesmo_nome`, 1 questão(ões)

- Chave: `demonstracao de fluxo de caixa`
- Nós:
  - `A-9d18b050f0` [assunto] Contabilidade Aplicada ao Setor Público › Demonstração de fluxos de caixa — 0 questão(ões), 1 item(ns) de edital
  - `S-fdc66541fc` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis conforme a legislação societária, os princípios fundamentais da contabilidade e os pronunciamentos contábeis do Comitê de Pronunciamentos Contábeis (CPC) › Demonstração de fluxos de caixa (métodos direto e indireto) — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-fdc66541fc`
- Operações propostas (`fundir`):
  - `A-9d18b050f0` → `S-fdc66541fc` — P-a08b14f89b

### Demonstração do valor adicionado — `mesmo_nome`, 1 questão(ões)

- Chave: `demonstracao do valor adicionado`
- Nós:
  - `S-58bdf78b4b` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis conforme a legislação societária, os princípios fundamentais da contabilidade e os pronunciamentos contábeis do Comitê de Pronunciamentos Contábeis (CPC) › Demonstração do valor adicionado — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-83d3373a86` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis pela legislação societária e pelas Normas Brasileiras de Contabilidade › Demonstração do Valor Adicionado — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-58bdf78b4b`
- Operações propostas (`fundir`):
  - `S-83d3373a86` → `S-58bdf78b4b` — P-9dde7820bc

### Depreciação, exaustão e amortização — `mesmo_nome`, 1 questão(ões)

- Chave: `depreciacao exaustao e amortizacao`
- Nós:
  - `A-78ae4ebacf` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Depreciação, exaustão e amortização — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-93d4990ef1` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Ativo Imobilizado › Depreciação, exaustão e amortização — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-78ae4ebacf`
- Operações propostas (`fundir`):
  - `S-93d4990ef1` → `A-78ae4ebacf` — P-8bd969fde1

### Distribuição de probabilidade — `mesmo_nome`, 1 questão(ões)

- Chave: `distribuicao de probabilidade`
- Nós:
  - `S-73b1f667cc` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Estatística e probabilidade básicas › Distribuição de probabilidade — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-9d7cd4e680` [subassunto] Estatística › Probabilidade › Distribuição de probabilidade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-73b1f667cc`
- Operações propostas (`fundir`):
  - `S-9d7cd4e680` → `S-73b1f667cc` — P-8a2e972fe5

### Grandes modelos de linguagem (LLM), IA generativa — `mesmo_nome`, 1 questão(ões)

- Chave: `grande modelo de linguagem ia generativa`
- Nós:
  - `A-048ceace24` [assunto] CIÊNCIA DE DADOS E INTELIGÊNCIA ARTIFICIAL › Grandes modelos de linguagem (LLM), IA generativa — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-85076bb3ef` [assunto] BANCO DE DADOS E CIÊNCIA DE DADOS › Grandes modelos de linguagem (LLM), IA generativa — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-048ceace24`
- Operações propostas (`fundir`):
  - `A-85076bb3ef` → `A-048ceace24` — P-da16c24b54

### Imposto sobre serviços (ISS) — `mesmo_nome`, 1 questão(ões)

- Chave: `imposto sobre servico`
- Nós:
  - `S-259658ef04` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Retenções na fonte realizadas pela administração pública federal › Imposto sobre serviços (ISS) — 0 questão(ões), 1 item(ns) de edital
  - `S-5adcb908e8` [subassunto] CONTABILIDADE TRIBUTÁRIA › Retenções na fonte realizadas pela administração pública federal › Imposto sobre serviços (ISS) — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-5adcb908e8`
- Operações propostas (`fundir`):
  - `S-259658ef04` → `S-5adcb908e8` — P-9b45060fa0

### Indicadores de estrutura de capitais — `mesmo_nome`, 1 questão(ões)

- Chave: `indicadore de estrutura de capitais`
- Nós:
  - `A-6b83d84d34` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Indicadores de estrutura de capitais — 0 questão(ões), 1 item(ns) de edital
  - `S-8538189a7e` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise econômico-financeira › Indicadores de estrutura de capitais — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-8538189a7e`
- Operações propostas (`fundir`):
  - `A-6b83d84d34` → `S-8538189a7e` — P-23ccc79600

### Indicadores de lucratividade — `mesmo_nome`, 1 questão(ões)

- Chave: `indicadore de lucratividade`
- Nós:
  - `A-5e458fd261` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Indicadores de lucratividade — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-30f066798f` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise econômico-financeira › Indicadores de lucratividade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-5e458fd261`
- Operações propostas (`fundir`):
  - `S-30f066798f` → `A-5e458fd261` — P-a5e4dec519

### Indicadores de rentabilidade — `mesmo_nome`, 1 questão(ões)

- Chave: `indicadore de rentabilidade`
- Nós:
  - `A-c84db33883` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Indicadores de rentabilidade — 0 questão(ões), 1 item(ns) de edital
  - `S-e5a881aea7` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise econômico-financeira › Indicadores de rentabilidade — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-e5a881aea7`
- Operações propostas (`fundir`):
  - `A-c84db33883` → `S-e5a881aea7` — P-a81a2b0d91

### Instrução Normativa da Receita Federal do Brasil nº 1.234/2012 — `mesmo_nome`, 1 questão(ões)

- Chave: `instrucao normativa da receita federal do brasil no 1 234 2012`
- Nós:
  - `S-24c2903654` [subassunto] CONTABILIDADE TRIBUTÁRIA › Legislação básica e suas atualizações › Instrução Normativa da Receita Federal do Brasil nº 1.234/2012 — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-41376b8be5` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Legislação básica e suas atualizações › Instrução Normativa da Receita Federal do Brasil nº 1.234/2012 — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-24c2903654`
- Operações propostas (`fundir`):
  - `S-41376b8be5` → `S-24c2903654` — P-45e6cd9714

### Inteligência Artificial — `mesmo_nome`, 1 questão(ões)

- Chave: `inteligencia artificial`
- Nós:
  - `A-35d753a1f0` [assunto] TECNOLOGIA DA INFORMAÇÃO › Inteligência Artificial — 0 questão(ões), 1 item(ns) de edital
  - `S-d4bb119012` [subassunto] ADMINISTRAÇÃO PÚBLICA › Inovação na gestão pública › Inteligência Artificial — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-d4bb119012`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-35d753a1f0`

### sistema de planejamento e orçamento e de programação financeira constantes da Lei nº 10.18 — `mesma_norma`, 1 questão(ões)

- Chave: `lei 10180`
- Nós:
  - `A-eabcd3fa3e` [assunto] Contabilidade Aplicada ao Setor Público › Lei nº 10.180/2001 — 0 questão(ões), 1 item(ns) de edital
  - `S-779cf1610f` [subassunto] Administração Orçamentária e Financeira › Gestão organizacional das finanças públicas › sistema de planejamento e orçamento e de programação financeira constantes da Lei nº 10.180/2001 — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-779cf1610f`
- Operações propostas (`fundir`):
  - `A-eabcd3fa3e` → `S-779cf1610f` — P-4679deeeec

### Lei nº 12.651/2012 (proteção da vegetação nativa) — `mesma_norma`, 1 questão(ões)

- Chave: `lei 12651`
- Nós:
  - `A-d68f615334` [assunto] LEGISLAÇÃO AMBIENTAL › Lei nº 12.651/2012 — 0 questão(ões), 1 item(ns) de edital
  - `S-85d6f7ed08` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 12.651/2012 (proteção da vegetação nativa) — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-85d6f7ed08`
- Operações propostas (`fundir`):
  - `A-d68f615334` → `S-85d6f7ed08` — P-5b922a6445

### Abuso de autoridade (Lei nº 13.869/2019 e suas alterações) — `mesma_norma`, 1 questão(ões)

- Chave: `lei 13869`
- Nós:
  - `A-11b8e758a1` [assunto] LEGISLAÇÃO RELACIONADA › Abuso de autoridade (Lei nº 13.869/2019 e suas alterações) — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-3e414756d4` [subassunto] DIREITO CONSTITUCIONAL › Crimes de Responsabilidade e abuso de autoridade › Lei nº 13.869/2019 (crimes de abuso de autoridade). — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-11b8e758a1`
- Operações propostas (`fundir`):
  - `S-3e414756d4` → `A-11b8e758a1` — P-4f844452ff

### Lei nº 6.938/1981 e suas alterações (Política Nacional do Meio Ambiente) — `mesma_norma`, 1 questão(ões)

- Chave: `lei 6938`
- Nós:
  - `A-8f52b6ce7e` [assunto] LEGISLAÇÃO AMBIENTAL › Lei nº 6.938/1981 e suas alterações — 0 questão(ões), 1 item(ns) de edital
  - `S-dbdf8411e1` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 6.938/1981 e suas alterações (Política Nacional do Meio Ambiente) — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-dbdf8411e1`
- Operações propostas (`fundir`):
  - `A-8f52b6ce7e` → `S-dbdf8411e1` — P-c8c8b10098

### Lei nº 7.735/1989 (criação do IBAMA) — `mesma_norma`, 1 questão(ões)

- Chave: `lei 7735`
- Nós:
  - `A-9b60cc24cb` [assunto] PROCESSO SANCIONADOR AMBIENTAL › Lei nº 7.735/1989 — 0 questão(ões), 1 item(ns) de edital
  - `A-e27e752fe7` [assunto] LEGISLAÇÃO AMBIENTAL › Lei nº 7.735/1989 — 0 questão(ões), 1 item(ns) de edital
  - `S-65e72df941` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 7.735/1989 (criação do IBAMA) — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-65e72df941`
- Operações propostas (`fundir`):
  - `A-9b60cc24cb` → `S-65e72df941` — P-a54009215e
  - `A-e27e752fe7` → `S-65e72df941` — P-93ec442061

### Lei Complementar nº 140/2011 — `mesma_norma`, 1 questão(ões)

- Chave: `lei complementar 140`
- Nós:
  - `A-555d07f10d` [assunto] LEGISLAÇÃO AMBIENTAL › Lei Complementar nº 140/2011 — 0 questão(ões), 1 item(ns) de edital
  - `A-b8162a557a` [assunto] PROCESSO SANCIONADOR AMBIENTAL › Lei Complementar nº 140/2011 — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-3e9e06cde3` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei Complementar nº 140/2011 (Competências ambientais) — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-b8162a557a`
- Operações propostas (`fundir`):
  - `A-555d07f10d` → `A-b8162a557a` — P-d8745afc7e
  - `S-3e9e06cde3` → `A-b8162a557a` — P-2dd8e222bc

### Lei Orçamentária Anual (LOA). — `mesmo_nome`, 1 questão(ões)

- Chave: `lei orcamentaria anual`
- Nós:
  - `A-c38427c027` [assunto] Administração Orçamentária e Financeira › Lei Orçamentária Anual (LOA) — 0 questão(ões), 1 item(ns) de edital
  - `S-24b3b29511` [subassunto] Processo Legislativo › Processo Legislativo Orçamentário › Lei Orçamentária Anual (LOA). — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f8900b3ab2` [subassunto] Administração Orçamentária e Financeira › Processo de planejamento orçamentário › Lei Orçamentária Anual — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-24b3b29511`
- Operações propostas (`fundir`):
  - `A-c38427c027` → `S-24b3b29511` — P-b08fd05666
  - `S-f8900b3ab2` → `S-24b3b29511` — P-e6a9174014

### Mensuração do Valor Justo — `mesmo_nome`, 1 questão(ões)

- Chave: `mensuracao do valor justo`
- Nós:
  - `A-49a4585d99` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Mensuração do valor justo — 0 questão(ões), 1 item(ns) de edital
  - `S-c0f7d82f17` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Mensuração do Valor Justo. Receita de Contrato com Cliente › Mensuração do Valor Justo — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c0f7d82f17`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-49a4585d99`

### Planejamento de contingências — `mesmo_nome`, 1 questão(ões)

- Chave: `planejamento de contingencia`
- Nós:
  - `A-67f605f494` [assunto] SEGURANÇA ORGÂNICA › Planejamento de contingências — 0 questão(ões), 1 item(ns) de edital
  - `A-93633d735e` [assunto] SEGURANÇA DE DIGNITÁRIOS › Planejamento de contingências — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `A-93633d735e`
- Operações propostas (`fundir`):
  - `A-67f605f494` → `A-93633d735e` — P-c06e22f072

### Poder Judiciário — `mesmo_nome`, 1 questão(ões)

- Chave: `poder judiciario`
- Nós:
  - `A-21377c6c46` [assunto] DIREITO CONSTITUCIONAL › Poder Judiciário — 0 questão(ões), 3 item(ns) de edital
  - `S-523600c0df` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Poder Judiciário — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-523600c0df`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-21377c6c46`

### Procedimentos de segurança — `mesmo_nome`, 1 questão(ões)

- Chave: `procedimento de seguranca`
- Nós:
  - `S-55c93600ca` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Segurança da informação › Procedimentos de segurança — 0 questão(ões), 2 item(ns) de edital
  - `S-c1d0865c06` [subassunto] INFORMÁTICA › Segurança da informação › Procedimentos de segurança — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c1d0865c06`
- Operações propostas (`fundir`):
  - `S-55c93600ca` → `S-c1d0865c06` — P-3b46f1b61d

### Processo decisório — `mesmo_nome`, 1 questão(ões)

- Chave: `processo decisorio`
- Nós:
  - `A-35230b45ff` [assunto] ADMINISTRAÇÃO GERAL › Processo decisório — 0 questão(ões), 1 item(ns) de edital
  - `S-0b390137b4` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Processo decisório — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-0b390137b4`
- Operações propostas: nenhuma (nós de nível diferente com filhos ativos).
- Sem operação (nível diferente com filhos, decisão do dono): `A-35230b45ff`

### Recrutamento e seleção — `mesmo_nome`, 1 questão(ões)

- Chave: `recrutamento e selecao`
- Nós:
  - `A-608e6fac70` [assunto] GESTÃO DE PESSOAS › Recrutamento e seleção — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d07ed7604f` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Recrutamento e seleção — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-608e6fac70`
- Operações propostas (`fundir`):
  - `S-d07ed7604f` → `A-608e6fac70` — P-57674f7ffd

### Recrutamento e seleção de pessoas — `mesmo_nome`, 1 questão(ões)

- Chave: `recrutamento e selecao de pessoa`
- Nós:
  - `A-252bd3d3fe` [assunto] Psicologia › Recrutamento e seleção de pessoas — 0 questão(ões), 1 item(ns) de edital
  - `S-28e27fcd34` [subassunto] GESTÃO DE PESSOAS › Processos de gestão de pessoas › Recrutamento e seleção de pessoas — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-a26b3a7b47` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Recrutamento e seleção de pessoas — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `S-28e27fcd34`
- Operações propostas (`fundir`):
  - `S-a26b3a7b47` → `S-28e27fcd34` — P-35a8d3f061
- Sem operação (nível diferente com filhos, decisão do dono): `A-252bd3d3fe`

### Redes sociais — `mesmo_nome`, 1 questão(ões)

- Chave: `rede sociais`
- Nós:
  - `S-0da4ddc89c` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores › Redes sociais — 1 questão(ões), 4 item(ns) de edital **(destino)**
  - `S-83010aef1a` [subassunto] INFORMÁTICA › Redes de computadores › Redes sociais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-0da4ddc89c`
- Operações propostas (`fundir`):
  - `S-83010aef1a` → `S-0da4ddc89c` — P-4124a35fdf

### Reservas de capital — `mesmo_nome`, 1 questão(ões)

- Chave: `reserva de capital`
- Nós:
  - `S-494385ce04` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio líquido › Reservas de capital — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-be76773216` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Reservas de capital — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-494385ce04`
- Operações propostas (`fundir`):
  - `S-be76773216` → `S-494385ce04` — P-b60cc09153

### Sistemas de informações — `mesmo_nome`, 1 questão(ões)

- Chave: `sistema de informacao`
- Nós:
  - `S-2b4abd0f8c` [subassunto] EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA › Programação, execução e controle de recursos orçamentários e financeiros › Sistemas de informações — 0 questão(ões), 1 item(ns) de edital
  - `S-d4b5530f95` [subassunto] Administração Orçamentária e Financeira › Programação, execução e controle de recursos orçamentários e financeiros › Sistemas de informações — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `SL-dede19b25f` [subassunto] Administração Orçamentária e Financeira › Programação e execução orçamentária e financeira › Sistemas de informações — 0 questão(ões), 3 item(ns) de edital
- Destino sugerido: `S-d4b5530f95`
- Operações propostas (`fundir`):
  - `S-2b4abd0f8c` → `S-d4b5530f95` — P-e1675c102e
  - `SL-dede19b25f` → `S-d4b5530f95` — P-8fc6b05104

### Ambiente da informação de custos — `mesmo_nome`, 0 questão(ões)

- Chave: `ambiente da informacao de custo`
- Nós:
  - `A-6c5cdb5037` [assunto] Contabilidade Aplicada ao Setor Público › Ambiente da informação de custos — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ae042b7bfc` [subassunto] Contabilidade Aplicada ao Setor Público › Sistema de custos › Ambiente da informação de custos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-6c5cdb5037`
- Operações propostas (`fundir`):
  - `S-ae042b7bfc` → `A-6c5cdb5037` — P-91e5b61171

### Análise de riscos — `mesmo_nome`, 0 questão(ões)

- Chave: `analise de risco`
- Nós:
  - `A-4cb333ef80` [assunto] SEGURANÇA ORGÂNICA › Análise de riscos — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-4df10fa14a` [assunto] SEGURANÇA DE DIGNITÁRIOS › Análise de riscos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-4cb333ef80`
- Operações propostas (`fundir`):
  - `A-4df10fa14a` → `A-4cb333ef80` — P-ec2db8ff35

### Análise vertical e horizontal — `mesmo_nome`, 0 questão(ões)

- Chave: `analise vertical e horizontal`
- Nós:
  - `A-4134c51a8a` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise vertical e horizontal — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d99861516a` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Análise econômico-financeira › Análise vertical e horizontal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-4134c51a8a`
- Operações propostas (`fundir`):
  - `S-d99861516a` → `A-4134c51a8a` — P-e4cdb2b5ac

### Anterioridade da lei — `mesmo_nome`, 0 questão(ões)

- Chave: `anterioridade da lei`
- Nós:
  - `S-b6303f2e84` [subassunto] DIREITO PENAL › Código Penal › Anterioridade da lei — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-c37c92a5f2` [subassunto] DIREITO PENAL › Aplicação da lei penal › Anterioridade da lei — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-b6303f2e84`
- Operações propostas (`fundir`):
  - `S-c37c92a5f2` → `S-b6303f2e84` — P-bb83405489

### Aplicabilidade das normas constitucionais — `mesmo_nome`, 0 questão(ões)

- Chave: `aplicabilidade das norma constitucionais`
- Nós:
  - `A-5ebac8ab8e` [assunto] DIREITO CONSTITUCIONAL › Aplicabilidade das normas constitucionais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-b4b44b6568` [subassunto] DIREITO CONSTITUCIONAL › Constituição › Aplicabilidade das normas constitucionais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-5ebac8ab8e`
- Operações propostas (`fundir`):
  - `S-b4b44b6568` → `A-5ebac8ab8e` — P-25aa4e25b4

### Arquitetura distribuída de microsserviços — `mesmo_nome`, 0 questão(ões)

- Chave: `arquitetura distribuida de microsservico`
- Nós:
  - `A-505e7be779` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Arquitetura distribuída de microsserviços — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-ed6af708f7` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Arquitetura distribuída de microsserviços › Arquitetura distribuída de microsserviços — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-505e7be779`
- Operações propostas (`fundir`):
  - `S-ed6af708f7` → `A-505e7be779` — P-285248c7b3

### Artrite reumatoide — `mesmo_nome`, 0 questão(ões)

- Chave: `artrite reumatoide`
- Nós:
  - `S-60425fbeea` [subassunto] Clínica Médica › Reumatologia › Artrite reumatoide — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-7c3471cdcf` [subassunto] Ortopedia › Infecções e alterações inflamatórias osteoarticulares › Artrite Reumatóide — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-60425fbeea`
- Operações propostas (`fundir`):
  - `S-7c3471cdcf` → `S-60425fbeea` — P-b347a52301

### Aspectos legais do sistema de custos — `mesmo_nome`, 0 questão(ões)

- Chave: `aspecto legais do sistema de custo`
- Nós:
  - `A-3ce8e0de20` [assunto] Contabilidade Aplicada ao Setor Público › Aspectos legais do sistema de custos — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-cae16ad361` [subassunto] Contabilidade Aplicada ao Setor Público › Sistema de custos › Aspectos legais do sistema de custos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-3ce8e0de20`
- Operações propostas (`fundir`):
  - `S-cae16ad361` → `A-3ce8e0de20` — P-ed3a641941

### Banco de dados — `mesmo_nome`, 0 questão(ões)

- Chave: `banco de dado`
- Nós:
  - `A-3ed5e6700c` [assunto] DESENVOLVIMENTO DE SISTEMAS › Bancos de dados — 0 questão(ões), 1 item(ns) de edital
  - `A-7736014b5b` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Banco de dados — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-1825cbd184` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Banco de dados › Banco de dados — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-7736014b5b`
- Operações propostas (`fundir`):
  - `A-3ed5e6700c` → `A-7736014b5b` — P-2d9727e5d8
  - `S-1825cbd184` → `A-7736014b5b` — P-3f1845ff47

### Ciência de Dados — `mesmo_nome`, 0 questão(ões)

- Chave: `ciencia de dado`
- Nós:
  - `A-064b407242` [assunto] TECNOLOGIA DA INFORMAÇÃO › Ciência de Dados — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-0cac37ea33` [assunto] BANCO DE DADOS E CIÊNCIA DE DADOS › Ciência de dados — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-064b407242`
- Operações propostas (`fundir`):
  - `A-0cac37ea33` → `A-064b407242` — P-9b42602ceb

### Competência Interpessoal — `mesmo_nome`, 0 questão(ões)

- Chave: `competencia interpessoal`
- Nós:
  - `A-35757d0cdf` [assunto] GESTÃO DE PESSOAS › Competência interpessoal — 0 questão(ões), 1 item(ns) de edital
  - `S-8123798742` [subassunto] GESTÃO DE PESSOAS › O indivíduo e o contexto organizacional: variáveis individuais, grupais e organizacionais › Competência Interpessoal — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-8123798742`
- Operações propostas (`fundir`):
  - `A-35757d0cdf` → `S-8123798742` — P-2b95e529cb

### Conceitos básicos, ferramentas, aplicativos e procedimentos de Internet e intranet — `mesmo_nome`, 0 questão(ões)

- Chave: `conceito basico ferramenta aplicativo e procedimento de internet e intranet`
- Nós:
  - `S-43ed8a5b23` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores › Conceitos básicos, ferramentas, aplicativos e procedimentos de Internet e intranet — 0 questão(ões), 4 item(ns) de edital **(destino)**
  - `S-90c20db8d6` [subassunto] INFORMÁTICA › Redes de computadores › Conceitos básicos, ferramentas, aplicativos e procedimentos de Internet e intranet — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-43ed8a5b23`
- Operações propostas (`fundir`):
  - `S-90c20db8d6` → `S-43ed8a5b23` — P-7c7a5fc890

### Consolidação das demonstrações contábeis — `mesmo_nome`, 0 questão(ões)

- Chave: `consolidacao das demonstracao contabeis`
- Nós:
  - `A-fb9b8ac273` [assunto] Contabilidade Aplicada ao Setor Público › Consolidação das demonstrações contábeis — 0 questão(ões), 1 item(ns) de edital
  - `S-f293322cbf` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Consolidação das demonstrações contábeis — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-f293322cbf`
- Operações propostas (`fundir`):
  - `A-fb9b8ac273` → `S-f293322cbf` — P-96bfa62d7a

### Conta Única do Tesouro Nacional — `mesmo_nome`, 0 questão(ões)

- Chave: `conta unica do tesouro nacional`
- Nós:
  - `A-99661a58c5` [assunto] Administração Orçamentária e Financeira › Conta Única do Tesouro Nacional — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-d8dc49fd7b` [assunto] Contabilidade Aplicada ao Setor Público › Conta única do Tesouro Nacional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-99661a58c5`
- Operações propostas (`fundir`):
  - `A-d8dc49fd7b` → `A-99661a58c5` — P-7e966027b2

### Contribuição para o financiamento da seguridade social (COFINS) — `mesmo_nome`, 0 questão(ões)

- Chave: `contribuicao para o financiamento da seguridade social`
- Nós:
  - `S-7775c4582a` [subassunto] CONTABILIDADE TRIBUTÁRIA › Retenções na fonte realizadas pela administração pública federal › Contribuição para o financiamento da seguridade social (COFINS) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-797608fd46` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Retenções na fonte realizadas pela administração pública federal › Contribuição para o financiamento da seguridade social (COFINS) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-7775c4582a`
- Operações propostas (`fundir`):
  - `S-797608fd46` → `S-7775c4582a` — P-5731887041

### Contribuição social sobre o lucro líquido (CSLL) — `mesmo_nome`, 0 questão(ões)

- Chave: `contribuicao social sobre o lucro liquido`
- Nós:
  - `S-425de8a279` [subassunto] CONTABILIDADE TRIBUTÁRIA › Retenções na fonte realizadas pela administração pública federal › Contribuição social sobre o lucro líquido (CSLL) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-c44c09add4` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Retenções na fonte realizadas pela administração pública federal › Contribuição social sobre o lucro líquido (CSLL) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-425de8a279`
- Operações propostas (`fundir`):
  - `S-c44c09add4` → `S-425de8a279` — P-ba7556fc23

### Cultura organizacional — `mesmo_nome`, 0 questão(ões)

- Chave: `cultura organizacional`
- Nós:
  - `S-3dd08a2a50` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Cultura organizacional — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f8fa829de5` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Cultura organizacional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-3dd08a2a50`
- Operações propostas (`fundir`):
  - `S-f8fa829de5` → `S-3dd08a2a50` — P-592dcfb7b1

### Deploy de aplicações — `mesmo_nome`, 0 questão(ões)

- Chave: `deploy de aplicacao`
- Nós:
  - `A-14e4537cf0` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Deploy de aplicações — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-f99f646a55` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Deploy de aplicações › Deploy de aplicações — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-14e4537cf0`
- Operações propostas (`fundir`):
  - `S-f99f646a55` → `A-14e4537cf0` — P-f1f101f179

### Desenvolvimento sustentável — `mesmo_nome`, 0 questão(ões)

- Chave: `desenvolvimento sustentavel`
- Nós:
  - `A-d6618cb1ed` [assunto] BIODIVERSIDADE E FLORESTAS › Desenvolvimento sustentável — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-aa5a87936c` [subassunto] ATUALIDADES › Tópicos relevantes e atuais de diversas áreas › desenvolvimento sustentável — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-d6618cb1ed`
- Operações propostas (`fundir`):
  - `S-aa5a87936c` → `A-d6618cb1ed` — P-4a26bd92a3

### Despesa pública — `mesmo_nome`, 0 questão(ões)

- Chave: `despesa publica`
- Nós:
  - `A-56cb844488` [assunto] Contabilidade Aplicada ao Setor Público › Despesa pública — 0 questão(ões), 1 item(ns) de edital
  - `AL-baa42ce1dc` [assunto] Administração Orçamentária e Financeira › Despesa pública — 0 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-34c4218bb5` [subassunto] Administração Orçamentária e Financeira › Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000) › Despesa Pública — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-baa42ce1dc`
- Operações propostas (`fundir`):
  - `A-56cb844488` → `AL-baa42ce1dc` — P-d519974957
  - `S-34c4218bb5` → `AL-baa42ce1dc` — P-ba02155cdc

### Empréstimos e financiamentos, debêntures e outros títulos de dívida — `mesmo_nome`, 0 questão(ões)

- Chave: `emprestimo e financiamento debenture e outro titulo de divida`
- Nós:
  - `A-6bc1c3dec9` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ec6bbd71e3` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Empréstimos e financiamentos, debêntures e outros títulos de dívida — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-6bc1c3dec9`
- Operações propostas (`fundir`):
  - `S-ec6bbd71e3` → `A-6bc1c3dec9` — P-9da1521256

### Entrevista motivacional — `mesmo_nome`, 0 questão(ões)

- Chave: `entrevista motivacional`
- Nós:
  - `A-1d0eda9b64` [assunto] Psicologia › Entrevista motivacional — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ad6c022ecb` [subassunto] Psicologia › Avaliação psicológica e psicodiagnóstico › Entrevista motivacional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-1d0eda9b64`
- Operações propostas (`fundir`):
  - `S-ad6c022ecb` → `A-1d0eda9b64` — P-42d456d583

### Fundamentos de estratégia — `mesmo_nome`, 0 questão(ões)

- Chave: `fundamento de estrategia`
- Nós:
  - `S-9ac59debbd` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governança › Fundamentos de estratégia — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-fef2d1ec7f` [subassunto] ADMINISTRAÇÃO GERAL › Gestão estratégica › Fundamentos de estratégia — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-9ac59debbd`
- Operações propostas (`fundir`):
  - `S-fef2d1ec7f` → `S-9ac59debbd` — P-e7912676f1

### Fundamentos e etapas da medida psicológica — `mesmo_nome`, 0 questão(ões)

- Chave: `fundamento e etapa da medida psicologica`
- Nós:
  - `S-566fcc1fba` [subassunto] Psicologia › psicometria › Fundamentos e etapas da medida psicológica — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d11e9900d1` [subassunto] Psicologia › Avaliação psicológica e psicodiagnóstico › Fundamentos e etapas da medida psicológica — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-566fcc1fba`
- Operações propostas (`fundir`):
  - `S-d11e9900d1` → `S-566fcc1fba` — P-37a05e006e

### Legislação básica e suas atualizações — `mesmo_nome`, 0 questão(ões)

- Chave: `legislacao basica e sua atualizacao`
- Nós:
  - `A-018b6b56e3` [assunto] CONTABILIDADE TRIBUTÁRIA › Legislação básica e suas atualizações — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-f00640d0d9` [assunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Legislação básica e suas atualizações — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-018b6b56e3`
- Operações propostas (`fundir`):
  - `A-f00640d0d9` → `A-018b6b56e3` — P-52158e9e93

### Lei nº 10.410/2002 (Criação da carreira de especialista em meio ambiente) — `mesma_norma`, 0 questão(ões)

- Chave: `lei 10410`
- Nós:
  - `A-58ed036e3d` [assunto] LEGISLAÇÃO AMBIENTAL › Lei nº 10.410/2002 — 0 questão(ões), 1 item(ns) de edital
  - `S-8879a2371a` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 10.410/2002 (Criação da carreira de especialista em meio ambiente) — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-8879a2371a`
- Operações propostas (`fundir`):
  - `A-58ed036e3d` → `S-8879a2371a` — P-9fcff5b1af

### Lei nº 14.785/2023 (agrotóxicos) — `mesma_norma`, 0 questão(ões)

- Chave: `lei 14785`
- Nós:
  - `S-46a4517320` [subassunto] QUALIDADE AMBIENTAL › Agrotóxicos, seus componentes e afins › Lei nº 14.785/2023 (agrotóxicos) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-5c9a2aa1f0` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 14.785/2023 (agrotóxicos) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-46a4517320`
- Operações propostas (`fundir`):
  - `S-5c9a2aa1f0` → `S-46a4517320` — P-ba4200ff3f

### Lei Complementar nº 116/2003 — `mesma_norma`, 0 questão(ões)

- Chave: `lei complementar 116`
- Nós:
  - `S-1cf3886726` [subassunto] CONTABILIDADE TRIBUTÁRIA › Legislação básica e suas atualizações › Lei Complementar nº 116/2003 — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-e241375229` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Legislação básica e suas atualizações › Lei Complementar nº 116/2003 — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-1cf3886726`
- Operações propostas (`fundir`):
  - `S-e241375229` → `S-1cf3886726` — P-a76f031eda

### Manual de Demonstrativos Fiscais, 14ª edição — `mesmo_nome`, 0 questão(ões)

- Chave: `manual de demonstrativo fiscais 14a edicao`
- Nós:
  - `A-8e9ed56866` [assunto] Contabilidade Aplicada ao Setor Público › Manual de Demonstrativos Fiscais, 14ª edição — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-f4cc228836` [assunto] Administração Orçamentária e Financeira › Manual de Demonstrativos Fiscais, 14ª edição — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-8e9ed56866`
- Operações propostas (`fundir`):
  - `A-f4cc228836` → `A-8e9ed56866` — P-cf05c4aa29

### Mensageria e webhooks — `mesmo_nome`, 0 questão(ões)

- Chave: `mensageria e webhooks`
- Nós:
  - `A-123fde88cd` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Mensageria e webhooks — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-65ef36facb` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Mensageria e webhooks › Mensageria e webhooks — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-123fde88cd`
- Operações propostas (`fundir`):
  - `S-65ef36facb` → `A-123fde88cd` — P-f5167db85c

### Notas explicativas às demonstrações contábeis — `mesmo_nome`, 0 questão(ões)

- Chave: `nota explicativa as demonstracao contabeis`
- Nós:
  - `A-b8a505ccf9` [assunto] Contabilidade Aplicada ao Setor Público › Notas explicativas às demonstrações contábeis — 0 questão(ões), 1 item(ns) de edital
  - `SL-e55da70bf6` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Notas explicativas às demonstrações contábeis — 0 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-e55da70bf6`
- Operações propostas (`fundir`):
  - `A-b8a505ccf9` → `SL-e55da70bf6` — P-f7474ef19e

### Patrimônio público — `mesmo_nome`, 0 questão(ões)

- Chave: `patrimonio publico`
- Nós:
  - `AL-d3f0a1724f` [assunto] Contabilidade Aplicada ao Setor Público › Patrimônio público — 0 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-a649ea8b0f` [subassunto] Contabilidade Aplicada ao Setor Público › Composição do patrimônio público › Patrimônio público — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-d3f0a1724f`
- Operações propostas (`fundir`):
  - `S-a649ea8b0f` → `AL-d3f0a1724f` — P-16bb9895a0

### Poder Executivo — `mesmo_nome`, 0 questão(ões)

- Chave: `poder executivo`
- Nós:
  - `A-8099862644` [assunto] DIREITO CONSTITUCIONAL › Poder Executivo — 0 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-9031f712ff` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Poder Executivo — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-8099862644`
- Operações propostas (`fundir`):
  - `S-9031f712ff` → `A-8099862644` — P-ae5e457c60

### Poder Legislativo — `mesmo_nome`, 0 questão(ões)

- Chave: `poder legislativo`
- Nós:
  - `A-ec54223f0c` [assunto] DIREITO CONSTITUCIONAL › Poder Legislativo — 0 questão(ões), 4 item(ns) de edital **(destino)**
  - `S-b08d8a7140` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Poder Legislativo — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-ec54223f0c`
- Operações propostas (`fundir`):
  - `S-b08d8a7140` → `A-ec54223f0c` — P-d71899e70e

### Prejuízos acumulados — `mesmo_nome`, 0 questão(ões)

- Chave: `prejuizo acumulado`
- Nós:
  - `S-1a2dace327` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio líquido › Prejuízos acumulados — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-c856111a36` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Prejuízos acumulados — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-1a2dace327`
- Operações propostas (`fundir`):
  - `S-c856111a36` → `S-1a2dace327` — P-9890bc4282

### Programação, execução e controle de recursos orçamentários e financeiros — `mesmo_nome`, 0 questão(ões)

- Chave: `programacao execucao e controle de recurso orcamentario e financeiro`
- Nós:
  - `A-9ced69392e` [assunto] Administração Orçamentária e Financeira › Programação, execução e controle de recursos orçamentários e financeiros — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-e4f463135a` [assunto] EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA › Programação, execução e controle de recursos orçamentários e financeiros — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-9ced69392e`
- Operações propostas (`fundir`):
  - `A-e4f463135a` → `A-9ced69392e` — P-3c13460d85

### Proteção da Fauna — `mesmo_nome`, 0 questão(ões)

- Chave: `protecao da fauna`
- Nós:
  - `A-91cce72b3a` [assunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Proteção da Fauna — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-cb2b937751` [assunto] PROTEÇÃO DA FAUNA › Proteção da Fauna — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-91cce72b3a`
- Operações propostas (`fundir`):
  - `A-cb2b937751` → `A-91cce72b3a` — P-65e8a34828

### Receita pública — `mesmo_nome`, 0 questão(ões)

- Chave: `receita publica`
- Nós:
  - `A-8d3ef86100` [assunto] Contabilidade Aplicada ao Setor Público › Receita pública — 0 questão(ões), 1 item(ns) de edital
  - `AL-49fc7bbd0b` [assunto] Administração Orçamentária e Financeira › Receita pública — 0 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-dd04d7428b` [subassunto] Administração Orçamentária e Financeira › Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000) › Receita Pública — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-49fc7bbd0b`
- Operações propostas (`fundir`):
  - `A-8d3ef86100` → `AL-49fc7bbd0b` — P-d0c39b4be4
  - `S-dd04d7428b` → `AL-49fc7bbd0b` — P-eae2a1c385

### Reservas de lucros — `mesmo_nome`, 0 questão(ões)

- Chave: `reserva de lucro`
- Nós:
  - `S-6d49e96860` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio líquido › Reservas de lucros — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-b85b25211c` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Reservas de lucros — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-6d49e96860`
- Operações propostas (`fundir`):
  - `S-b85b25211c` → `S-6d49e96860` — P-c9b6749526

### Saldo patrimonial — `mesmo_nome`, 0 questão(ões)

- Chave: `saldo patrimonial`
- Nós:
  - `S-2b9c9b13e0` [subassunto] Contabilidade Aplicada ao Setor Público › Composição do patrimônio público › Saldo patrimonial — 0 questão(ões), 1 item(ns) de edital
  - `S-b5a3879396` [subassunto] Contabilidade Aplicada ao Setor Público › Patrimônio público › Saldo patrimonial — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-b5a3879396`
- Operações propostas (`fundir`):
  - `S-2b9c9b13e0` → `S-b5a3879396` — P-c29a8ab9d0

### Segurança da informação — `mesmo_nome`, 0 questão(ões)

- Chave: `seguranca da informacao`
- Nós:
  - `A-2356bc9bf9` [assunto] SEGURANÇA ORGÂNICA › Segurança da informação — 0 questão(ões), 1 item(ns) de edital
  - `A-8bc51b3a2f` [assunto] TECNOLOGIA DA INFORMAÇÃO › Segurança da informação — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `A-abb1e7cea2` [assunto] INFORMÁTICA › Segurança da informação — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-8bc51b3a2f`
- Operações propostas (`fundir`):
  - `A-2356bc9bf9` → `A-8bc51b3a2f` — P-5f9b1219d7
  - `A-abb1e7cea2` → `A-8bc51b3a2f` — P-4df017df53

### Serviços de autenticação — `mesmo_nome`, 0 questão(ões)

- Chave: `servico de autenticacao`
- Nós:
  - `A-ef31a46945` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Serviços de autenticação — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-b11d8058bc` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Serviços de autenticação › Serviços de autenticação — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-ef31a46945`
- Operações propostas (`fundir`):
  - `S-b11d8058bc` → `A-ef31a46945` — P-9f82d4d84e

### Shell Script (Bash) — `mesmo_nome`, 0 questão(ões)

- Chave: `shell script`
- Nós:
  - `S-27921a4299` [subassunto] DESENVOLVIMENTO DE SISTEMAS › Linguagens de script › Shell Script (Bash) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-fc54143a84` [subassunto] INFRAESTRUTURA DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Sistemas operacionais › Shell Script — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-27921a4299`
- Operações propostas (`fundir`):
  - `S-fc54143a84` → `S-27921a4299` — P-70f7669695

### Sistema Financeiro Nacional — `mesmo_nome`, 0 questão(ões)

- Chave: `sistema financeiro nacional`
- Nós:
  - `A-58a2ea0f4f` [assunto] DIREITO CONSTITUCIONAL › Sistema Financeiro Nacional — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-b37a322e5a` [subassunto] DIREITO CONSTITUCIONAL › Ordem econômica e financeira › Sistema Financeiro Nacional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-58a2ea0f4f`
- Operações propostas (`fundir`):
  - `S-b37a322e5a` → `A-58a2ea0f4f` — P-2e5e91bf5c

### Sítios de busca e pesquisa na Internet — `mesmo_nome`, 0 questão(ões)

- Chave: `sitio de busca e pesquisa na internet`
- Nós:
  - `S-1316b4abb1` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Redes de computadores › Sítios de busca e pesquisa na Internet — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-f6ad04f9fc` [subassunto] INFORMÁTICA › Redes de computadores › Sítios de busca e pesquisa na Internet — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-1316b4abb1`
- Operações propostas (`fundir`):
  - `S-f6ad04f9fc` → `S-1316b4abb1` — P-cf171e7f68

### Spring Boot — `mesmo_nome`, 0 questão(ões)

- Chave: `spring boot`
- Nós:
  - `S-1a4de18798` [subassunto] DESENVOLVIMENTO DE SISTEMAS › Frameworks e toolkits › Spring Boot — 0 questão(ões), 1 item(ns) de edital
  - `S-363a91d3ee` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Arquitetura distribuída de microsserviços › Spring Boot — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-363a91d3ee`
- Operações propostas (`fundir`):
  - `S-1a4de18798` → `S-363a91d3ee` — P-662d06376d

### Trabalho em equipe — `mesmo_nome`, 0 questão(ões)

- Chave: `trabalho em equipe`
- Nós:
  - `A-996a591664` [assunto] SEGURANÇA DE DIGNITÁRIOS › Trabalho em equipe — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-93ef321903` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Trabalho em equipe — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-996a591664`
- Operações propostas (`fundir`):
  - `S-93ef321903` → `A-996a591664` — P-d71fa0c74c

### Tratamento contábil aplicável aos impostos e contribuições — `mesmo_nome`, 0 questão(ões)

- Chave: `tratamento contabil aplicavel aos imposto e contribuicao`
- Nós:
  - `A-79802a31bc` [assunto] CONTABILIDADE TRIBUTÁRIA › Tratamento contábil aplicável aos impostos e contribuições — 0 questão(ões), 1 item(ns) de edital
  - `AL-eaef011f6c` [assunto] Contabilidade Aplicada ao Setor Público › Tratamento contábil aplicável aos impostos e contribuições — 0 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `AL-eaef011f6c`
- Operações propostas (`fundir`):
  - `A-79802a31bc` → `AL-eaef011f6c` — P-4114ae0f46


## Grupos de confiança média (só relatório)

### Compreensão e interpretação de textos — `nome_contido`, 49 questão(ões)

- Chave: `compreensao e interpretacao de texto`
- Nós:
  - `A-24f6586fef` [assunto] LÍNGUA INGLESA › Compreensão e interpretação de textos variados — 1 questão(ões), 3 item(ns) de edital
  - `AL-c07f603352` [assunto] LÍNGUA PORTUGUESA › Compreensão e interpretação de textos — 48 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `AL-c07f603352`
- Fusões possíveis se o dono decidir: `A-24f6586fef`→`AL-c07f603352`

### Lei nº 9.784/1999 (processo administrativo) — `mesma_norma`, 24 questão(ões)

- Chave: `lei 9784`
- Nós:
  - `A-839c897054` [assunto] LEGISLAÇÃO › Lei nº 9.784/1999 (processo administrativo) — 17 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-a540ddad8e` [assunto] PROCESSO SANCIONADOR AMBIENTAL › Lei nº 9.784/1999 e Lei nº 9.873/1999 — 1 questão(ões), 1 item(ns) de edital
  - `AL-fe35b41dc5` [assunto] DIREITO ADMINISTRATIVO › Processo Administrativo Federal (Lei nº 9.784/1999) — 6 questão(ões), 3 item(ns) de edital
  - `S-5a7e2f3f47` [subassunto] DIREITO ADMINISTRATIVO › Processo administrativo › Lei n.º 9.784/1999 — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-839c897054`
- Fusões possíveis se o dono decidir: `A-a540ddad8e`→`A-839c897054`, `AL-fe35b41dc5`→`A-839c897054`, `S-5a7e2f3f47`→`A-839c897054`

### Legislação pertinente: Lei nº 14.133/2021 e suas alterações — `mesma_norma`, 22 questão(ões)

- Chave: `lei 14133`
- Nós:
  - `A-ceea19ae78` [assunto] LICITAÇÕES E CONTRATOS › Lei nº 14.133/2021 — 0 questão(ões), 1 item(ns) de edital
  - `S-17bddd6e82` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Licitações e contratos › § 1º do Art. 65 e Art. 69 da Lei nº 14.133/2021 — 0 questão(ões), 1 item(ns) de edital
  - `S-23893486a3` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Licitações e contratos administrativos › Lei nº 14.133/2021, conceito, princípios, contratação direta, modalidades, tipos e aspectos procedimentais — 6 questão(ões), 2 item(ns) de edital
  - `S-492515805c` [subassunto] DIREITO ADMINISTRATIVO › Contratos administrativos › Legislação pertinente: Lei nº 14.133/2021 e suas alterações — 12 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-7920a91591` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Tipos de penalidades previstas na Lei nº 14.133/2021 — 1 questão(ões), 1 item(ns) de edital
  - `S-bf1fb476cd` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Legislação aplicável à contratação de bens e serviços › Lei nº 14.133/2021 — 2 questão(ões), 1 item(ns) de edital
  - `S-f591ab620e` [subassunto] DIREITO ADMINISTRATIVO › Licitação › Legislação pertinente: Lei nº 14.133/2021 e suas alterações — 0 questão(ões), 1 item(ns) de edital
  - `S-f778630a9e` [subassunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Governança e Gestão de TIC › Lei nº 14.133/2021 — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-492515805c`
- Fusões possíveis se o dono decidir: `S-17bddd6e82`→`S-492515805c`, `S-23893486a3`→`S-492515805c`, `S-7920a91591`→`S-492515805c`, `S-bf1fb476cd`→`S-492515805c`, `S-f591ab620e`→`S-492515805c`, `S-f778630a9e`→`S-492515805c`
- Sem operação (nível diferente com filhos, decisão do dono): `A-ceea19ae78`

### Lei nº 8.429/1992 e suas alterações — `mesma_norma`, 20 questão(ões)

- Chave: `lei 8429`
- Nós:
  - `A-aed23dfa13` [assunto] DIREITO ADMINISTRATIVO › Improbidade Administrativa (Lei nº 8.429/1992) — 7 questão(ões), 5 item(ns) de edital
  - `S-064141b0b0` [subassunto] ÉTICA NO SERVIÇO PÚBLICO › Ética no setor público › Lei nº 8.429/1992 e suas alterações — 12 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-7518929608` [subassunto] DIREITO ADMINISTRATIVO › Improbidade Administrativa (Lei nº 8.429/1992) › Improbidade administrativa: Lei n.º 8.429/1992 e suas alterações — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-064141b0b0`
- Fusões possíveis se o dono decidir: `S-7518929608`→`S-064141b0b0`
- Sem operação (nível diferente com filhos, decisão do dono): `A-aed23dfa13`

### Direitos e deveres individuais e coletivos, direitos sociais, direitos de nacionalidade, d — `nome_contido`, 14 questão(ões)

- Chave: `direito e devere`
- Nós:
  - `S-329ac8e3a2` [subassunto] DIREITO CONSTITUCIONAL › Direitos e garantias fundamentais › Direitos e deveres individuais e coletivos — 4 questão(ões), 1 item(ns) de edital
  - `S-402b99af6f` [subassunto] DIREITO CONSTITUCIONAL › Direitos e garantias fundamentais › Direitos e deveres individuais e coletivos, direitos sociais, nacionalidade, cidadania, direitos políticos, partidos políticos. — 0 questão(ões), 1 item(ns) de edital
  - `S-a6b78a5568` [subassunto] DIREITO ADMINISTRATIVO › Agentes públicos › Direitos e deveres — 0 questão(ões), 2 item(ns) de edital
  - `S-bed6cebe50` [subassunto] DIREITO CONSTITUCIONAL › Princípios Fundamentais. Direitos e garantias fundamentais › direitos e deveres individuais e coletivos — 1 questão(ões), 1 item(ns) de edital
  - `SL-2a563462b9` [subassunto] DIREITO CONSTITUCIONAL › Direitos e garantias fundamentais › Direitos e deveres individuais e coletivos, direitos sociais, direitos de nacionalidade, direitos políticos, partidos políticos — 9 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-2a563462b9`
- Fusões possíveis se o dono decidir: `S-329ac8e3a2`→`SL-2a563462b9`, `S-402b99af6f`→`SL-2a563462b9`, `S-a6b78a5568`→`SL-2a563462b9`, `S-bed6cebe50`→`SL-2a563462b9`

### Gestão por competências — `nome_contido`, 12 questão(ões)

- Chave: `gestao por competencia`
- Nós:
  - `A-18731e453a` [assunto] Psicologia › Gestão por competências: objetivos estratégicos, definição de competências, avaliação de desempenho por competências, gestão do desempenho e feedback — 0 questão(ões), 1 item(ns) de edital
  - `A-c3f41ab58f` [assunto] GESTÃO DE PESSOAS › Gestão por competências — 4 questão(ões), 3 item(ns) de edital
  - `S-23743b08cb` [subassunto] ADMINISTRAÇÃO PÚBLICA › Excelência nos serviços públicos › Gestão por competências — 2 questão(ões), 1 item(ns) de edital
  - `S-43005656d8` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Gestão por competências: abordagens e ferramentas, mapeamento e desenvolvimento das competências — 1 questão(ões), 2 item(ns) de edital
  - `S-e02c45cebe` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Gestão por competências — 5 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-e02c45cebe`
- Fusões possíveis se o dono decidir: `A-18731e453a`→`S-e02c45cebe`, `A-c3f41ab58f`→`S-e02c45cebe`, `S-23743b08cb`→`S-e02c45cebe`, `S-43005656d8`→`S-e02c45cebe`

### Código de Ética Profissional do Servidor Público Civil do Poder Executivo Federal (Decreto — `mesma_norma`, 11 questão(ões)

- Chave: `decreto 1171`
- Nós:
  - `A-80249666b2` [assunto] ÉTICA NO SERVIÇO PÚBLICO › Código de Ética Profissional do Servidor Público Civil do Poder Executivo Federal (Decreto nº 1.171/1994) — 6 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-d7e3575a95` [subassunto] ÉTICA NO SERVIÇO PÚBLICO › Código de Ética Profissional do Servidor Público Civil do Poder Executivo Federal (Decreto nº 1.171/1994) › Código de Ética Profissional do Serviço Público (Decreto nº 1.171/1994) — 5 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-80249666b2`
- Fusões possíveis se o dono decidir: `S-d7e3575a95`→`A-80249666b2`

### Lei de Acesso à Informação (Lei nº 12.527/2011) — `mesma_norma`, 8 questão(ões)

- Chave: `lei 12527`
- Nós:
  - `A-2ab02b7fee` [assunto] TECNOLOGIA DA INFORMAÇÃO › Acesso à informação (Lei nº 12.527/2011 e Decreto nº 7.724/2012) — 0 questão(ões), 1 item(ns) de edital
  - `AL-c962e98e16` [assunto] DIREITO ADMINISTRATIVO › Lei de Acesso à Informação (Lei nº 12.527/2011) — 4 questão(ões), 5 item(ns) de edital **(destino)**
  - `S-256fbea4b7` [subassunto] DIREITO ADMINISTRATIVO › Lei de Acesso à Informação (Lei nº 12.527/2011) › Lei n.º 12.527/2011 (Lei de Acesso à Informação) — 4 questão(ões), 3 item(ns) de edital
  - `S-d723487337` [subassunto] ARQUIVOLOGIA › Legislação pertinente › Lei nº 12.527/2011 e Decreto nº 7.724/2012 — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-c962e98e16`
- Fusões possíveis se o dono decidir: `A-2ab02b7fee`→`AL-c962e98e16`, `S-256fbea4b7`→`AL-c962e98e16`, `S-d723487337`→`AL-c962e98e16`

### Normas Brasileiras de Contabilidade Técnicas de Auditoria de Informação Contábil Histórica — `nome_contido`, 8 questão(ões)

- Chave: `norma brasileira de contabilidade`
- Nós:
  - `A-477c1de1c1` [assunto] AUDITORIA GOVERNAMENTAL › Normas Brasileiras de Contabilidade Técnicas de Auditoria de Informação Contábil Histórica Aplicável ao Setor Público - NBC TASP — 7 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-b8ca33bcc7` [assunto] AUDITORIA GOVERNAMENTAL › Normas Brasileiras de Contabilidade Técnicas de Auditoria Interna - NBC TI — 1 questão(ões), 1 item(ns) de edital
  - `A-eff517d483` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Norma Brasileira de Contabilidade (NBC TG Estrutura Conceitual) — 0 questão(ões), 2 item(ns) de edital
  - `S-cd1a887ef3` [subassunto] Contabilidade Aplicada ao Setor Público › NBC TSP Estrutura Conceitual › Normas Brasileiras de Contabilidade Aplicadas ao Setor Público – NBC TSP — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-477c1de1c1`
- Fusões possíveis se o dono decidir: `A-b8ca33bcc7`→`A-477c1de1c1`, `A-eff517d483`→`A-477c1de1c1`, `S-cd1a887ef3`→`A-477c1de1c1`

### Plano plurianual — `nome_contido`, 7 questão(ões)

- Chave: `plano plurianual`
- Nós:
  - `S-6f92815025` [subassunto] Administração Orçamentária e Financeira › Processo de planejamento orçamentário › Plano Plurianual — 0 questão(ões), 1 item(ns) de edital
  - `S-b4ba760ed5` [subassunto] Processo Legislativo › Processo Legislativo Orçamentário › Plano Plurianual (PPA). — 0 questão(ões), 1 item(ns) de edital
  - `S-f9d4aed838` [subassunto] ADMINISTRAÇÃO PÚBLICA › Ciclo de planejamento governamental › Plano Plurianual (PPA) 2024-2027: modelo de planejamento, megaobjetivos, dimensões, programa e ação — 2 questão(ões), 2 item(ns) de edital
  - `SL-6d3f949b2d` [subassunto] Administração Orçamentária e Financeira › Orçamento público no Brasil › Plano plurianual — 5 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `SL-6d3f949b2d`
- Fusões possíveis se o dono decidir: `S-6f92815025`→`SL-6d3f949b2d`, `S-b4ba760ed5`→`SL-6d3f949b2d`, `S-f9d4aed838`→`SL-6d3f949b2d`

### Restos a pagar — `nome_contido`, 7 questão(ões)

- Chave: `resto a pagar`
- Nós:
  - `A-8f7f0e91ed` [assunto] Contabilidade Aplicada ao Setor Público › Restos a pagar, empenho, liquidação e pagamento (Lei nº 4.320/1964 e MCASP) — 0 questão(ões), 1 item(ns) de edital
  - `SL-ddc4fce8dd` [subassunto] Administração Orçamentária e Financeira › Despesa pública › Restos a pagar — 7 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-ddc4fce8dd`
- Fusões possíveis se o dono decidir: `A-8f7f0e91ed`→`SL-ddc4fce8dd`

### Processo Administrativo Federal (Lei nº 9.784/1999) — `nome_contido`, 6 questão(ões)

- Chave: `processo administrativo`
- Nós:
  - `A-c415e4b4f5` [assunto] ADMINISTRAÇÃO GERAL › Processo administrativo — 0 questão(ões), 4 item(ns) de edital
  - `AL-fe35b41dc5` [assunto] DIREITO ADMINISTRATIVO › Processo Administrativo Federal (Lei nº 9.784/1999) — 6 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-721455144a` [subassunto] DIREITO ADMINISTRATIVO › Agentes públicos › Processo administrativo disciplinar — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `AL-fe35b41dc5`
- Fusões possíveis se o dono decidir: `A-c415e4b4f5`→`AL-fe35b41dc5`, `S-721455144a`→`AL-fe35b41dc5`

### Comportamento organizacional: relações indivíduo/organização, motivação, desempenho, engaj — `nome_contido`, 5 questão(ões)

- Chave: `comportamento organizacional`
- Nós:
  - `A-b846308eab` [assunto] GESTÃO DE PESSOAS › Comportamento organizacional — 0 questão(ões), 1 item(ns) de edital
  - `S-70c016a556` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Comportamento organizacional: relações indivíduo/organização, motivação, desempenho, engajamento, trabalho em equipe e colaboração — 3 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-8d204f5a8c` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Comportamento organizacional: relações indivíduo/organização, motivação, liderança, desempenho — 2 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-70c016a556`
- Fusões possíveis se o dono decidir: `S-8d204f5a8c`→`S-70c016a556`
- Sem operação (nível diferente com filhos, decisão do dono): `A-b846308eab`

### Evolução da Administração Pública no Brasil (após 1930); reformas administrativas; a nova  — `nome_contido`, 5 questão(ões)

- Chave: `evolucao da administracao`
- Nós:
  - `A-26ae9a012e` [assunto] ADMINISTRAÇÃO GERAL › Evolução da administração — 0 questão(ões), 4 item(ns) de edital
  - `A-9b014a88e2` [assunto] ADMINISTRAÇÃO PÚBLICA › A evolução da administração pública e a reforma do Estado — 1 questão(ões), 3 item(ns) de edital
  - `S-1e3bfe8c59` [subassunto] ADMINISTRAÇÃO GERAL › Evolução da administração › Evolução da Administração Pública no Brasil (após 1930); reformas administrativas; a nova gestão pública — 4 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-1e3bfe8c59`
- Sem operação (nível diferente com filhos, decisão do dono): `A-26ae9a012e`, `A-9b014a88e2`

### Inquérito policial militar — `nome_contido`, 5 questão(ões)

- Chave: `inquerito policial`
- Nós:
  - `A-538fd2c91b` [assunto] DIREITO PROCESSUAL PENAL › Inquérito policial — 0 questão(ões), 1 item(ns) de edital
  - `A-b8bf55774e` [assunto] DIREITO PROCESSUAL PENAL MILITAR › Inquérito policial militar — 5 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `A-b8bf55774e`
- Fusões possíveis se o dono decidir: `A-538fd2c91b`→`A-b8bf55774e`

### Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000) — `mesma_norma`, 5 questão(ões)

- Chave: `lei complementar 101`
- Nós:
  - `A-98c597bbfc` [assunto] Contabilidade Aplicada ao Setor Público › Tópicos selecionados da Lei Complementar nº 101/2000 e suas alterações — 0 questão(ões), 1 item(ns) de edital
  - `AL-02b4bc3a67` [assunto] Administração Orçamentária e Financeira › Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000) — 4 questão(ões), 13 item(ns) de edital **(destino)**
  - `S-64d625133c` [subassunto] Processo Legislativo › Processo Legislativo Orçamentário › As interfaces entre LDO, LOA, Lei nº 4.320/1964 e Lei Complementar nº 101/2000 (Lei de Responsabilidade Fiscal). — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-02b4bc3a67`
- Fusões possíveis se o dono decidir: `A-98c597bbfc`→`AL-02b4bc3a67`, `S-64d625133c`→`AL-02b4bc3a67`

### Medidas de dispersão: amplitude, variância, desvio-padrão, coeficiente de variação, amplit — `nome_contido`, 5 questão(ões)

- Chave: `medida de dispersao`
- Nós:
  - `S-162ca078a9` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Estatística e probabilidade básicas › Medidas de dispersão — 2 questão(ões), 1 item(ns) de edital
  - `S-7292baab88` [subassunto] Estatística › Estatística descritiva e análise exploratória de dados › Medidas de dispersão: amplitude, variância, desvio-padrão, coeficiente de variação, amplitude interquartil — 3 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-7292baab88`
- Fusões possíveis se o dono decidir: `S-162ca078a9`→`S-7292baab88`

### Primeiros socorros psicológicos — `nome_contido`, 5 questão(ões)

- Chave: `primeiro socorro`
- Nós:
  - `A-6238361bb5` [assunto] SEGURANÇA DE DIGNITÁRIOS › primeiros socorros — 1 questão(ões), 1 item(ns) de edital
  - `S-11e6f0b72d` [subassunto] Psicologia › Intervenção psicológica em problemas específicos › Primeiros socorros psicológicos — 4 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-11e6f0b72d`
- Sem operação (nível diferente com filhos, decisão do dono): `A-6238361bb5`

### Responsabilidade civil do Estado — `nome_contido`, 5 questão(ões)

- Chave: `responsabilidade civil`
- Nós:
  - `A-5679a0c6b3` [assunto] DIREITO ADMINISTRATIVO › Responsabilidade civil do Estado — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `A-967c777b91` [assunto] DIREITO CIVIL › Responsabilidade civil — 0 questão(ões), 1 item(ns) de edital
  - `S-66eca7322c` [subassunto] DIREITO ADMINISTRATIVO › Responsabilidade civil do Estado › Responsabilidade civil do Estado no direito brasileiro: responsabilidade por ato comissivo do Estado, responsabilidade por omissão do Estado — 1 questão(ões), 1 item(ns) de edital
  - `S-e6f4da2cd5` [subassunto] DIREITO ADMINISTRATIVO › Responsabilidade civil do Estado › Responsabilidade civil do Estado no direito brasileiro — 2 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-5679a0c6b3`
- Fusões possíveis se o dono decidir: `A-967c777b91`→`A-5679a0c6b3`, `S-66eca7322c`→`A-5679a0c6b3`, `S-e6f4da2cd5`→`A-5679a0c6b3`

### sistema operacional (ambiente Windows) — `nome_contido`, 5 questão(ões)

- Chave: `sistema operacional`
- Nós:
  - `A-1491e5b864` [assunto] INFORMÁTICA › sistema operacional (ambiente Windows) — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-5b2d07610c` [assunto] TECNOLOGIA DA INFORMAÇÃO › sistema operacional (ambiente Windows 10 e 11) e MSOffice M365 (Word, Excel, PowerPoint, OneDrive, Sharepoint e Teams) — 2 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-1491e5b864`
- Fusões possíveis se o dono decidir: `A-5b2d07610c`→`A-1491e5b864`

### Ação penal militar — `nome_contido`, 4 questão(ões)

- Chave: `acao penal`
- Nós:
  - `A-00cb8a6bf1` [assunto] DIREITO PROCESSUAL PENAL MILITAR › Ação penal militar — 4 questão(ões), 2 item(ns) de edital **(destino)**
  - `A-325398b100` [assunto] DIREITO PROCESSUAL PENAL › Ação penal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-00cb8a6bf1`
- Fusões possíveis se o dono decidir: `A-325398b100`→`A-00cb8a6bf1`

### Ação penal militar — `nome_contido`, 4 questão(ões)

- Chave: `acao penal`
- Nós:
  - `A-00cb8a6bf1` [assunto] DIREITO PROCESSUAL PENAL MILITAR › Ação penal militar — 4 questão(ões), 2 item(ns) de edital **(destino)**
  - `A-4f7e2b964a` [assunto] DIREITO PENAL MILITAR › Ação penal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-00cb8a6bf1`
- Fusões possíveis se o dono decidir: `A-4f7e2b964a`→`A-00cb8a6bf1`

### Ação penal militar — `nome_contido`, 4 questão(ões)

- Chave: `acao penal`
- Nós:
  - `A-00cb8a6bf1` [assunto] DIREITO PROCESSUAL PENAL MILITAR › Ação penal militar — 4 questão(ões), 2 item(ns) de edital **(destino)**
  - `A-65b5e1aa5c` [assunto] DIREITO PENAL › Ação penal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-00cb8a6bf1`
- Fusões possíveis se o dono decidir: `A-65b5e1aa5c`→`A-00cb8a6bf1`

### Acompanhamento da execução contratual — `nome_contido`, 4 questão(ões)

- Chave: `acompanhamento da execucao`
- Nós:
  - `S-0be4918914` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos › Acompanhamento da execução contratual — 4 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-fda50e8d63` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Acompanhamento da execução contratual — 0 questão(ões), 1 item(ns) de edital
  - `SL-1a55fbe838` [subassunto] Administração Orçamentária e Financeira › Programação e execução orçamentária e financeira › Acompanhamento da execução — 0 questão(ões), 3 item(ns) de edital
- Destino sugerido: `S-0be4918914`
- Fusões possíveis se o dono decidir: `S-fda50e8d63`→`S-0be4918914`, `SL-1a55fbe838`→`S-0be4918914`

### Aplicação da lei penal militar — `nome_contido`, 4 questão(ões)

- Chave: `aplicacao da lei penal`
- Nós:
  - `A-4ff77e52a4` [assunto] DIREITO PENAL MILITAR › Aplicação da lei penal militar — 4 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-de28e5f4a7` [assunto] DIREITO PENAL › Aplicação da lei penal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-4ff77e52a4`
- Fusões possíveis se o dono decidir: `A-de28e5f4a7`→`A-4ff77e52a4`

### Cláusulas e indicadores de nível de serviço — `mesmo_nome`, 4 questão(ões)

- Chave: `clausula e indicadore de nivel de servico`
- Nós:
  - `S-7b8cc40dfe` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Cláusulas e indicadores de nível de serviço — 1 questão(ões), 1 item(ns) de edital
  - `S-87dabcd1d9` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos › Cláusulas e indicadores de nível de serviço — 3 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-daa946eba6` [subassunto] DIREITO ADMINISTRATIVO › Contratos administrativos › Cláusulas e indicadores de nível de serviço — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-87dabcd1d9`
- Fusões possíveis se o dono decidir: `S-7b8cc40dfe`→`S-87dabcd1d9`, `S-daa946eba6`→`S-87dabcd1d9`

### Comportamento humano no trabalho: satisfação e comprometimento — `nome_contido`, 4 questão(ões)

- Chave: `comportamento humano no trabalho`
- Nós:
  - `A-8c413ec0bb` [assunto] Psicologia › Comportamento humano no trabalho: motivação e significado do trabalho, satisfação, comprometimento, envolvimento e engajamento no trabalho — 2 questão(ões), 1 item(ns) de edital
  - `S-94be688f36` [subassunto] GESTÃO DE PESSOAS › O indivíduo e o contexto organizacional: variáveis individuais, grupais e organizacionais › Comportamento humano no trabalho: satisfação e comprometimento — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-94be688f36`
- Fusões possíveis se o dono decidir: `A-8c413ec0bb`→`S-94be688f36`

### condutas preventivas, condutas protetivas, identificação de ameaças e vulnerabilidades, pl — `nome_contido`, 4 questão(ões)

- Chave: `conduta preventiva`
- Nós:
  - `S-343205dc12` [subassunto] SEGURANÇA DE DIGNITÁRIOS › Segurança de pessoas › condutas preventivas, condutas protetivas, identificação de ameaças e vulnerabilidades, planejamento e execução da proteção de dignitários — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ff94589314` [subassunto] SEGURANÇA ORGÂNICA › prevenção e combate a incêndio › Condutas preventivas — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-343205dc12`
- Fusões possíveis se o dono decidir: `S-ff94589314`→`S-343205dc12`

### Corredores ecológicos — `nome_contido`, 4 questão(ões)

- Chave: `corredore ecologico`
- Nós:
  - `A-23ec6a658c` [assunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Corredores ecológicos — 4 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-2d9ed3bea3` [assunto] BIODIVERSIDADE E FLORESTAS › Corredores ecológicos, dispersão de fauna e flora e trocas genéticas — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-23ec6a658c`
- Fusões possíveis se o dono decidir: `A-2d9ed3bea3`→`A-23ec6a658c`

### Ferramenta de versionamento Git — `nome_contido`, 4 questão(ões)

- Chave: `ferramenta de versionamento git`
- Nós:
  - `A-d2840d96b5` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Ferramenta de versionamento Git — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-65ee08bc23` [subassunto] INFRAESTRUTURA DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Virtualização de desktop › Ferramenta de versionamento Git: configuração e utilização — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-d2840d96b5`
- Fusões possíveis se o dono decidir: `S-65ee08bc23`→`A-d2840d96b5`

### gestão de riscos de TIC — `nome_contido`, 4 questão(ões)

- Chave: `gestao de risco`
- Nós:
  - `A-5f8fb9dc53` [assunto] ADMINISTRAÇÃO GERAL › Gestão de risco — 1 questão(ões), 2 item(ns) de edital
  - `A-86e8c9e653` [assunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › gestão de riscos de TIC — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-c700f36823` [assunto] SEGURANÇA DA INFORMAÇÃO › Gestão de riscos de SI — 0 questão(ões), 1 item(ns) de edital
  - `S-0b50b1da53` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governança › Gestão de riscos e integridade — 1 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-86e8c9e653`
- Fusões possíveis se o dono decidir: `A-5f8fb9dc53`→`A-86e8c9e653`, `A-c700f36823`→`A-86e8c9e653`, `S-0b50b1da53`→`A-86e8c9e653`

### Resoluções CNJ nº 467/2022 e CNJ nº 566/2024 (regulamentam, no âmbito do Poder Judiciário, — `mesma_norma`, 4 questão(ões)

- Chave: `lei 10826`
- Nós:
  - `A-11de92af33` [assunto] LEGISLAÇÃO RELACIONADA › Resoluções CNJ nº 467/2022 e CNJ nº 566/2024 (regulamentam, no âmbito do Poder Judiciário, o disposto nos artigos 6º, inciso XI, e 7ºA da Lei nº 10.826/2003, com as alterações promovidas pela Lei nº 12.694/2012 e suas alterações) — 3 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-53910a9ccc` [assunto] LEGISLAÇÃO RELACIONADA › Registro, posse e comercialização de armas de fogo e munição, Sistema Nacional de Armas – SINARM (Lei nº 10.826/2003 e suas alterações) — 1 questão(ões), 1 item(ns) de edital
  - `A-c2c9bf0f86` [assunto] LEGISLAÇÃO APLICADA À POLÍCIA FEDERAL › Lei nº 10.826/2003 — 0 questão(ões), 1 item(ns) de edital
  - `S-e54afe3dd3` [subassunto] DIREITO PENAL › Crimes constantes de legislação especial › Crimes tipificados no Estatuto do Desarmamento (Lei nº 10.826/2003 e suas alterações) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-11de92af33`
- Fusões possíveis se o dono decidir: `A-53910a9ccc`→`A-11de92af33`, `A-c2c9bf0f86`→`A-11de92af33`, `S-e54afe3dd3`→`A-11de92af33`

### Transtornos de personalidade e transtorno de conduta antissocial — `nome_contido`, 4 questão(ões)

- Chave: `transtorno de personalidade`
- Nós:
  - `A-9292ea9c3b` [assunto] Psiquiatria › Transtornos de personalidade e transtorno de conduta antissocial — 4 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f924c362fc` [subassunto] Psicologia › Psicopatologia › Transtornos de personalidade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-9292ea9c3b`
- Fusões possíveis se o dono decidir: `S-f924c362fc`→`A-9292ea9c3b`

### Tribunal de Contas da União (TCU), tribunais de contas dos estados, municípios e do Distri — `nome_contido`, 4 questão(ões)

- Chave: `tribunal de conta da uniao`
- Nós:
  - `A-50b1b56021` [assunto] CONTROLE EXTERNO › Tribunal de Contas da União (TCU), tribunais de contas dos estados, municípios e do Distrito Federal — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-343681ef99` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Tribunal de Contas da União (TCU) — 2 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-50b1b56021`
- Fusões possíveis se o dono decidir: `S-343681ef99`→`A-50b1b56021`

### Análise SWOT aplicados à TIC — `nome_contido`, 3 questão(ões)

- Chave: `analise swot`
- Nós:
  - `S-9ac1356984` [subassunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Governança de TIC › Análise SWOT aplicados à TIC — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-bcd5e45306` [subassunto] ADMINISTRAÇÃO GERAL › Gestão estratégica › Análise SWOT — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-9ac1356984`
- Fusões possíveis se o dono decidir: `S-bcd5e45306`→`S-9ac1356984`

### Crimes contra o patrimônio — `mesmo_nome`, 3 questão(ões)

- Chave: `crime contra o patrimonio`
- Nós:
  - `A-1e4b99a376` [assunto] DIREITO PENAL MILITAR › Crimes contra o patrimônio — 0 questão(ões), 1 item(ns) de edital
  - `A-ee140fcf09` [assunto] DIREITO PENAL › Crimes contra o patrimônio — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-dabdb2c144` [subassunto] DIREITO PENAL › Crimes em espécie do Código Penal › Crimes contra o patrimônio — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-ee140fcf09`
- Fusões possíveis se o dono decidir: `A-1e4b99a376`→`A-ee140fcf09`, `S-dabdb2c144`→`A-ee140fcf09`

### Lei nº 9.605/1998 (Lei dos Crimes Ambientais) e Decreto nº 6.514/2008 — `mesma_norma`, 3 questão(ões)

- Chave: `decreto 6514`
- Nós:
  - `A-a98298ec31` [assunto] LEGISLAÇÃO AMBIENTAL › Lei nº 9.605/1998 e Decreto nº 6.514/2008 — 0 questão(ões), 1 item(ns) de edital
  - `A-e3b8290592` [assunto] PROCESSO SANCIONADOR AMBIENTAL › Decreto nº 6.514/2008 — 1 questão(ões), 1 item(ns) de edital
  - `S-238d031496` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 9.605/1998 (Lei dos Crimes Ambientais) e Decreto nº 6.514/2008 — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-238d031496`
- Fusões possíveis se o dono decidir: `A-a98298ec31`→`S-238d031496`, `A-e3b8290592`→`S-238d031496`

### Indicadores de desempenho — `nome_contido`, 3 questão(ões)

- Chave: `indicadore de desempenho`
- Nós:
  - `A-b34798e56a` [assunto] ADMINISTRAÇÃO GERAL › Indicadores de desempenho — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-9e3a88bbc7` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governança › Indicadores de desempenho: tipos de indicadores; variáveis componentes dos indicadores — 0 questão(ões), 1 item(ns) de edital
  - `S-b99aec5724` [subassunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Planejamento estratégico de TIC › Indicadores de desempenho de TIC e alinhamento com objetivos organizacionais — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-b34798e56a`
- Fusões possíveis se o dono decidir: `S-9e3a88bbc7`→`A-b34798e56a`, `S-b99aec5724`→`A-b34798e56a`

### Inteligência artificial e produção de conteúdo — `nome_contido`, 3 questão(ões)

- Chave: `inteligencia artificial`
- Nós:
  - `S-b8d9d1eb97` [subassunto] COMUNICAÇÃO SOCIAL › Novas tecnologias de comunicação › Inteligência artificial e produção de conteúdo — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-d4bb119012` [subassunto] ADMINISTRAÇÃO PÚBLICA › Inovação na gestão pública › Inteligência Artificial — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-b8d9d1eb97`
- Fusões possíveis se o dono decidir: `S-d4bb119012`→`S-b8d9d1eb97`

### Lei nº 4.320/1964 e suas alterações — `mesma_norma`, 3 questão(ões)

- Chave: `lei 4320`
- Nós:
  - `A-8f7f0e91ed` [assunto] Contabilidade Aplicada ao Setor Público › Restos a pagar, empenho, liquidação e pagamento (Lei nº 4.320/1964 e MCASP) — 0 questão(ões), 1 item(ns) de edital
  - `AL-528d504ae8` [assunto] Administração Orçamentária e Financeira › Lei nº 4.320/1964 e suas alterações — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `AL-d92ca18389` [assunto] Contabilidade Aplicada ao Setor Público › Lei nº 4.320/1964 — 0 questão(ões), 2 item(ns) de edital
  - `S-64d625133c` [subassunto] Processo Legislativo › Processo Legislativo Orçamentário › As interfaces entre LDO, LOA, Lei nº 4.320/1964 e Lei Complementar nº 101/2000 (Lei de Responsabilidade Fiscal). — 1 questão(ões), 1 item(ns) de edital
  - `S-674794e3b4` [subassunto] Contabilidade Aplicada ao Setor Público › Definições, finalidade, componentes, estrutura e conteúdo das demonstrações › de acordo com a Lei nº 4.320/1964 e suas alterações — 0 questão(ões), 1 item(ns) de edital
  - `S-7eb8abf86d` [subassunto] Administração Orçamentária e Financeira › Lei nº 4.320/1964 e suas alterações › Lei nº 4.320/1964 — 1 questão(ões), 1 item(ns) de edital
  - `S-c60607b2f3` [subassunto] Administração Orçamentária e Financeira › Direito Financeiro e Tributário › Lei nº 4.320/1964 (Normas Gerais de Direito Financeiro) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-528d504ae8`
- Fusões possíveis se o dono decidir: `A-8f7f0e91ed`→`AL-528d504ae8`, `AL-d92ca18389`→`AL-528d504ae8`, `S-64d625133c`→`AL-528d504ae8`, `S-674794e3b4`→`AL-528d504ae8`, `S-7eb8abf86d`→`AL-528d504ae8`, `S-c60607b2f3`→`AL-528d504ae8`

### Lei nº 9.605/1998 (Lei dos Crimes Ambientais) e Decreto nº 6.514/2008 — `mesma_norma`, 3 questão(ões)

- Chave: `lei 9605`
- Nós:
  - `A-a98298ec31` [assunto] LEGISLAÇÃO AMBIENTAL › Lei nº 9.605/1998 e Decreto nº 6.514/2008 — 0 questão(ões), 1 item(ns) de edital
  - `A-f50a3a70d2` [assunto] PROCESSO SANCIONADOR AMBIENTAL › Lei nº 9.605/1998 — 1 questão(ões), 1 item(ns) de edital
  - `S-238d031496` [subassunto] LEGISLAÇÃO AMBIENTAL › Leis, decretos, resoluções e portarias › Lei nº 9.605/1998 (Lei dos Crimes Ambientais) e Decreto nº 6.514/2008 — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-238d031496`
- Fusões possíveis se o dono decidir: `A-a98298ec31`→`S-238d031496`, `A-f50a3a70d2`→`S-238d031496`

### Planejamento estratégico — `nome_contido`, 3 questão(ões)

- Chave: `planejamento estrategico`
- Nós:
  - `A-9579bc2a33` [assunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Planejamento estratégico de TIC — 0 questão(ões), 1 item(ns) de edital
  - `A-ee3b7a3ec6` [assunto] Psicologia › Planejamento estratégico da gestão de pessoas — 0 questão(ões), 1 item(ns) de edital
  - `S-4fbb5eef47` [subassunto] ADMINISTRAÇÃO GERAL › Gestão estratégica › Planejamento estratégico: visão, missão e análise SWOT — 1 questão(ões), 1 item(ns) de edital
  - `S-68fb64a623` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governança › Planejamento estratégico: conceitos, métodos e técnicas — 0 questão(ões), 1 item(ns) de edital
  - `S-aedc8bb2b0` [subassunto] ADMINISTRAÇÃO GERAL › Gestão estratégica › Planejamento estratégico — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-aedc8bb2b0`
- Fusões possíveis se o dono decidir: `S-4fbb5eef47`→`S-aedc8bb2b0`, `S-68fb64a623`→`S-aedc8bb2b0`
- Sem operação (nível diferente com filhos, decisão do dono): `A-9579bc2a33`, `A-ee3b7a3ec6`

### Accountability — `nome_contido`, 2 questão(ões)

- Chave: `accountability`
- Nós:
  - `A-2b0ce986c1` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Accountability e competência da contabilidade — 0 questão(ões), 1 item(ns) de edital
  - `S-68a76ed346` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governo eletrônico › Accountability — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-68a76ed346`
- Fusões possíveis se o dono decidir: `A-2b0ce986c1`→`S-68a76ed346`

### Ajuste a valor presente — `nome_contido`, 2 questão(ões)

- Chave: `ajuste a valor presente`
- Nós:
  - `A-a3d65f4c71` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Ajuste a valor presente — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-9141861365` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Realizável a longo prazo (não circulante) › Ajuste a valor presente: cálculo — 0 questão(ões), 1 item(ns) de edital
  - `S-b7e9764425` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Realizável a longo prazo (não circulante) › Ajuste a valor presente: conceito e metodologia — 0 questão(ões), 1 item(ns) de edital
  - `S-cc71558ec7` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Realizável a longo prazo (não circulante) › Ajuste a valor presente: contabilização — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-a3d65f4c71`
- Fusões possíveis se o dono decidir: `S-9141861365`→`A-a3d65f4c71`, `S-b7e9764425`→`A-a3d65f4c71`, `S-cc71558ec7`→`A-a3d65f4c71`

### Balanced scorecard — `nome_contido`, 2 questão(ões)

- Chave: `balanced scorecard`
- Nós:
  - `A-49f101efee` [assunto] ADMINISTRAÇÃO GERAL › Balanced scorecard — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-5d901cc3bc` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Balanced scorecard — 0 questão(ões), 2 item(ns) de edital
  - `S-7a0d161260` [subassunto] ADMINISTRAÇÃO GERAL › Gestão estratégica › Balanced Scorecard (BSC): principais conceitos, aplicações, mapa estratégico, perspectivas, temas estratégicos, objetivos estratégicos, relações de causa e efeito, indicadores, metas, iniciativas estratégicas — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-49f101efee`
- Fusões possíveis se o dono decidir: `S-5d901cc3bc`→`A-49f101efee`, `S-7a0d161260`→`A-49f101efee`

### Classificação da receita pública: institucional, por categorias econômicas, por fontes — `nome_contido`, 2 questão(ões)

- Chave: `classificacao da receita publica`
- Nós:
  - `S-0b4eecb0b1` [subassunto] Administração Orçamentária e Financeira › Classificações orçamentárias › Classificação da receita pública: institucional, por categorias econômicas, por fontes — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-da427a7c3d` [subassunto] Administração Orçamentária e Financeira › Manual Técnico do Orçamento - MTO 2024 › Classificação da receita pública: institucional, por categorias econômicas, por fontes e classificações adicionais previstas no Manual Técnico de Orçamento (MTO) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-0b4eecb0b1`
- Fusões possíveis se o dono decidir: `S-da427a7c3d`→`S-0b4eecb0b1`

### Cultura organizacional: paradigmas, conceitos, elementos e dinâmica. Clima organizacional: — `nome_contido`, 2 questão(ões)

- Chave: `cultura organizacional`
- Nós:
  - `A-a0150ddd87` [assunto] Psicologia › Cultura organizacional: paradigmas, conceitos, elementos e dinâmica. Clima organizacional: evolução conceitual, componentes e estratégias de gestão — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-3dd08a2a50` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Cultura organizacional — 0 questão(ões), 1 item(ns) de edital
  - `S-f8fa829de5` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Cultura organizacional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-a0150ddd87`
- Fusões possíveis se o dono decidir: `S-3dd08a2a50`→`A-a0150ddd87`, `S-f8fa829de5`→`A-a0150ddd87`

### Escritório de projetos – PMO e gestão de portfólio de projetos — `nome_contido`, 2 questão(ões)

- Chave: `escritorio de projeto`
- Nós:
  - `S-b6954abc23` [subassunto] ADMINISTRAÇÃO GERAL › Gestão de Projetos › Escritório de projetos — 0 questão(ões), 3 item(ns) de edital
  - `S-c4267a628f` [subassunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Gerenciamento de projetos de TIC › Escritório de projetos – PMO e gestão de portfólio de projetos — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c4267a628f`
- Fusões possíveis se o dono decidir: `S-b6954abc23`→`S-c4267a628f`

### Ferramentas de planejamento estratégico: Análise SWOT; Balanced scorecard (BSC): principai — `nome_contido`, 2 questão(ões)

- Chave: `ferramenta de planejamento estrategico`
- Nós:
  - `S-655449dbb0` [subassunto] ADMINISTRAÇÃO GERAL › Gestão estratégica › Ferramentas de planejamento estratégico — 0 questão(ões), 1 item(ns) de edital
  - `S-71b651de26` [subassunto] ADMINISTRAÇÃO PÚBLICA › Governança › Ferramentas de planejamento estratégico: Análise SWOT; Balanced scorecard (BSC): principais conceitos, aplicações, mapa estratégico, perspectivas, temas estratégicos, objetivos estratégicos, relações de causa e efeito, indicadores, metas, iniciativas estratégicas — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-71b651de26`
- Fusões possíveis se o dono decidir: `S-655449dbb0`→`S-71b651de26`

### Gestão de pessoas nas organizações — `nome_contido`, 2 questão(ões)

- Chave: `gestao de pessoa`
- Nós:
  - `A-4af1eec8dc` [assunto] GESTÃO DE PESSOAS › Gestão de pessoas — 0 questão(ões), 6 item(ns) de edital
  - `A-d267e58ee7` [assunto] Psicologia › Gestão de pessoas nas organizações — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `A-d267e58ee7`
- Fusões possíveis se o dono decidir: `A-4af1eec8dc`→`A-d267e58ee7`

### Gestão estratégica de pessoas — `nome_contido`, 2 questão(ões)

- Chave: `gestao estrategica`
- Nós:
  - `A-fdd929e9b9` [assunto] ADMINISTRAÇÃO GERAL › Gestão estratégica — 0 questão(ões), 4 item(ns) de edital
  - `S-0d402d57eb` [subassunto] GESTÃO DE PESSOAS › Modelos de gestão de pessoas › Gestão estratégica de pessoas — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-0d402d57eb`
- Sem operação (nível diferente com filhos, decisão do dono): `A-fdd929e9b9`

### Inteligência artificial e produção de conteúdo — `nome_contido`, 2 questão(ões)

- Chave: `inteligencia artificial`
- Nós:
  - `A-35d753a1f0` [assunto] TECNOLOGIA DA INFORMAÇÃO › Inteligência Artificial — 0 questão(ões), 1 item(ns) de edital
  - `S-b8d9d1eb97` [subassunto] COMUNICAÇÃO SOCIAL › Novas tecnologias de comunicação › Inteligência artificial e produção de conteúdo — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-b8d9d1eb97`
- Sem operação (nível diferente com filhos, decisão do dono): `A-35d753a1f0`

### Estatuto da Pessoa Idosa (Lei nº 10.741/2003 e suas alterações) — `mesma_norma`, 2 questão(ões)

- Chave: `lei 10741`
- Nós:
  - `A-1d78a93881` [assunto] LEGISLAÇÃO RELACIONADA › Estatuto da Pessoa Idosa (Lei nº 10.741/2003 e suas alterações) — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-1c70e095aa` [subassunto] Serviço Social › Políticas Sociais › Estatuto da Pessoa Idosa (Lei nº 10.741/2003) — 1 questão(ões), 1 item(ns) de edital
  - `S-86e0da1cf3` [subassunto] DIREITO CIVIL › Legislação especial › Lei nº 10.741/2003 (Estatuto da Pessoa Idosa) — 0 questão(ões), 1 item(ns) de edital
  - `S-8ae0b24bf6` [subassunto] DIREITO PENAL › Crimes constantes de legislação especial › Crimes tipificados no Estatuto da Pessoa Idosa (Lei nº 10.741/2003) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-1d78a93881`
- Fusões possíveis se o dono decidir: `S-1c70e095aa`→`A-1d78a93881`, `S-86e0da1cf3`→`A-1d78a93881`, `S-8ae0b24bf6`→`A-1d78a93881`

### Abuso de autoridade (Lei nº 13.869/2019 e suas alterações) — `mesma_norma`, 2 questão(ões)

- Chave: `lei 13869`
- Nós:
  - `A-11b8e758a1` [assunto] LEGISLAÇÃO RELACIONADA › Abuso de autoridade (Lei nº 13.869/2019 e suas alterações) — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-3e414756d4` [subassunto] DIREITO CONSTITUCIONAL › Crimes de Responsabilidade e abuso de autoridade › Lei nº 13.869/2019 (crimes de abuso de autoridade). — 0 questão(ões), 1 item(ns) de edital
  - `S-9664b6c557` [subassunto] DIREITO PENAL › Crimes constantes de legislação especial › Crime de abuso de autoridade (Lei nº 13.869/2019) — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-11b8e758a1`
- Fusões possíveis se o dono decidir: `S-3e414756d4`→`A-11b8e758a1`, `S-9664b6c557`→`A-11b8e758a1`

### Estatuto da Criança e do Adolescente- ECA (Lei nº 8.069/1990) — `mesma_norma`, 2 questão(ões)

- Chave: `lei 8069`
- Nós:
  - `S-0754c3760b` [subassunto] Serviço Social › Políticas Sociais › Estatuto da Criança e do Adolescente- ECA (Lei nº 8.069/1990) — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ca6d59d2a8` [subassunto] DIREITO PENAL › Crimes constantes de legislação especial › Crimes e infrações administrativas tipificados no Estatuto da Criança e do Adolescente (Lei nº 8.069/1990 e suas alterações) — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-0754c3760b`
- Fusões possíveis se o dono decidir: `S-ca6d59d2a8`→`S-0754c3760b`

### Linguagens de programação — `nome_contido`, 2 questão(ões)

- Chave: `linguagem de programacao`
- Nós:
  - `A-3408fede43` [assunto] DESENVOLVIMENTO DE SISTEMAS › Linguagens de programação — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-a57b011cd2` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Linguagem de programação Java — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-3408fede43`
- Fusões possíveis se o dono decidir: `A-a57b011cd2`→`A-3408fede43`

### Ministério Público — `nome_contido`, 2 questão(ões)

- Chave: `ministerio publico`
- Nós:
  - `S-659d0e6459` [subassunto] DIREITO CONSTITUCIONAL › Funções essenciais à justiça › Ministério Público — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-7eb58d8de4` [subassunto] DIREITO PROCESSUAL CIVIL › Sujeitos do processo › Ministério Público, advocacia pública e Defensoria Pública — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-659d0e6459`
- Fusões possíveis se o dono decidir: `S-7eb58d8de4`→`S-659d0e6459`

### Papel do preposto da contratada — `mesmo_nome`, 2 questão(ões)

- Chave: `papel do preposto da contratada`
- Nós:
  - `S-4292869e2f` [subassunto] DIREITO ADMINISTRATIVO › Contratos administrativos › Papel do preposto da contratada — 0 questão(ões), 1 item(ns) de edital
  - `S-b1d7bd5120` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos › Papel do preposto da contratada — 2 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-eb10d36bff` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Papel do preposto da contratada — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-b1d7bd5120`
- Fusões possíveis se o dono decidir: `S-4292869e2f`→`S-b1d7bd5120`, `S-eb10d36bff`→`S-b1d7bd5120`

### PMBOK 7ª edição: conceitos, grupos de processos e áreas de conhecimento — `nome_contido`, 2 questão(ões)

- Chave: `pmbok 7a edicao`
- Nós:
  - `S-c741425bc1` [subassunto] ADMINISTRAÇÃO GERAL › Gestão de Projetos › PMBOK 7ª edição — 0 questão(ões), 1 item(ns) de edital
  - `S-c950876d09` [subassunto] GOVERNANÇA E GESTÃO DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Gerenciamento de projetos de TIC › PMBOK 7ª edição: conceitos, grupos de processos e áreas de conhecimento — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c950876d09`
- Fusões possíveis se o dono decidir: `S-c741425bc1`→`S-c950876d09`

### Poder constituinte derivado — `nome_contido`, 2 questão(ões)

- Chave: `poder constituinte`
- Nós:
  - `A-dcc99f7cec` [assunto] DIREITO CONSTITUCIONAL › Poder constituinte — 0 questão(ões), 2 item(ns) de edital
  - `S-72f93331fa` [subassunto] DIREITO CONSTITUCIONAL › Poder constituinte › Poder constituinte originário — 0 questão(ões), 1 item(ns) de edital
  - `S-c87e72d97e` [subassunto] DIREITO CONSTITUCIONAL › Poder constituinte › Poder constituinte derivado — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c87e72d97e`
- Fusões possíveis se o dono decidir: `S-72f93331fa`→`S-c87e72d97e`
- Sem operação (nível diferente com filhos, decisão do dono): `A-dcc99f7cec`

### Qualidade de vida no trabalho — `nome_contido`, 2 questão(ões)

- Chave: `qualidade de vida`
- Nós:
  - `A-024bdafe23` [assunto] Psicologia › Qualidade de vida no trabalho — 1 questão(ões), 1 item(ns) de edital
  - `A-564f15a1ae` [assunto] GESTÃO DE PESSOAS › Qualidade de vida no trabalho — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-31051a8057` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Qualidade de vida no trabalho — 0 questão(ões), 1 item(ns) de edital
  - `S-6e9a2a7f98` [subassunto] Psicologia › Psicologia social e aplicação no trabalho › Qualidade de Vida no trabalho — 0 questão(ões), 1 item(ns) de edital
  - `S-d2d1b6f764` [subassunto] GESTÃO DE PESSOAS › Comportamento organizacional › Qualidade de vida — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-564f15a1ae`
- Fusões possíveis se o dono decidir: `A-024bdafe23`→`A-564f15a1ae`, `S-31051a8057`→`A-564f15a1ae`, `S-6e9a2a7f98`→`A-564f15a1ae`, `S-d2d1b6f764`→`A-564f15a1ae`

### Recrutamento e seleção — `nome_contido`, 2 questão(ões)

- Chave: `recrutamento e selecao`
- Nós:
  - `A-252bd3d3fe` [assunto] Psicologia › Recrutamento e seleção de pessoas — 0 questão(ões), 1 item(ns) de edital
  - `A-608e6fac70` [assunto] GESTÃO DE PESSOAS › Recrutamento e seleção — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-28e27fcd34` [subassunto] GESTÃO DE PESSOAS › Processos de gestão de pessoas › Recrutamento e seleção de pessoas — 1 questão(ões), 1 item(ns) de edital
  - `S-a26b3a7b47` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Recrutamento e seleção de pessoas — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-608e6fac70`
- Fusões possíveis se o dono decidir: `A-252bd3d3fe`→`A-608e6fac70`, `S-28e27fcd34`→`A-608e6fac70`, `S-a26b3a7b47`→`A-608e6fac70`

### Redução ao Valor Recuperável de Ativos — `nome_contido`, 2 questão(ões)

- Chave: `reducao ao valor recuperavel`
- Nós:
  - `A-f1b3c39d52` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Redução ao Valor Recuperável de Ativos — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f9a9f94282` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Ativo Imobilizado › Redução ao valor recuperável — 1 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-f1b3c39d52`
- Fusões possíveis se o dono decidir: `S-f9a9f94282`→`A-f1b3c39d52`

### Restos a pagar — `nome_contido`, 2 questão(ões)

- Chave: `resto a pagar`
- Nós:
  - `A-7e93595e9c` [assunto] Administração Orçamentária e Financeira › Restos a pagar — 2 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-8f7f0e91ed` [assunto] Contabilidade Aplicada ao Setor Público › Restos a pagar, empenho, liquidação e pagamento (Lei nº 4.320/1964 e MCASP) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-7e93595e9c`
- Fusões possíveis se o dono decidir: `A-8f7f0e91ed`→`A-7e93595e9c`

### Segurança da informação: procedimentos de cópia de segurança (backup), noções de vírus, wo — `nome_contido`, 2 questão(ões)

- Chave: `seguranca da informacao`
- Nós:
  - `A-2356bc9bf9` [assunto] SEGURANÇA ORGÂNICA › Segurança da informação — 0 questão(ões), 1 item(ns) de edital
  - `A-8bc51b3a2f` [assunto] TECNOLOGIA DA INFORMAÇÃO › Segurança da informação — 0 questão(ões), 2 item(ns) de edital
  - `A-abb1e7cea2` [assunto] INFORMÁTICA › Segurança da informação — 0 questão(ões), 1 item(ns) de edital
  - `A-e922060053` [assunto] SEGURANÇA DA INFORMAÇÃO › Segurança da informação e desenvolvimento de software seguro — 0 questão(ões), 1 item(ns) de edital
  - `S-0a80488ff9` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Conceitos gerais de segurança e governança digital › Segurança da informação: procedimentos de cópia de segurança (backup), noções de vírus, worms e pragas virtuais — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-0a80488ff9`
- Sem operação (nível diferente com filhos, decisão do dono): `A-2356bc9bf9`, `A-8bc51b3a2f`, `A-abb1e7cea2`, `A-e922060053`

### Sistema Integrado de Administração Financeira do Governo Federal (SIAFI) — `nome_contido`, 2 questão(ões)

- Chave: `sistema integrado de administracao financeira do governo federal`
- Nós:
  - `AL-3f2f77bd7c` [assunto] Contabilidade Aplicada ao Setor Público › Sistema Integrado de Administração Financeira do Governo Federal (SIAFI) — 2 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-1c0b9b5770` [subassunto] Contabilidade Aplicada ao Setor Público › Sistema de contabilidade federal › Sistema Integrado de Administração Financeira do Governo Federal (SIAFI): conceito, objetivos, usuários e segurança do sistema (princípios e instrumentos) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `AL-3f2f77bd7c`
- Fusões possíveis se o dono decidir: `S-1c0b9b5770`→`AL-3f2f77bd7c`

### Transferências voluntárias e legislação sobre o tema — `nome_contido`, 2 questão(ões)

- Chave: `transferencia voluntaria`
- Nós:
  - `S-260e3c2569` [subassunto] Administração Orçamentária e Financeira › Lei de Responsabilidade Fiscal (Lei Complementar nº 101/2000) › transferências voluntárias — 0 questão(ões), 1 item(ns) de edital
  - `S-28597f42de` [subassunto] Administração Orçamentária e Financeira › Ciclo orçamentário › Transferências voluntárias e legislação sobre o tema — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-28597f42de`
- Fusões possíveis se o dono decidir: `S-260e3c2569`→`S-28597f42de`

### Treinamento e Desenvolvimento — `nome_contido`, 2 questão(ões)

- Chave: `treinamento e desenvolvimento`
- Nós:
  - `S-5db2e48980` [subassunto] Psicologia › Análise e desenvolvimento organizacional › Treinamento e desenvolvimento de pessoal: levantamento de necessidades, planejamento, execução e avaliação — 0 questão(ões), 1 item(ns) de edital
  - `S-a4eeb7ac63` [subassunto] GESTÃO DE PESSOAS › Processos de gestão de pessoas › Treinamento e Desenvolvimento — 2 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-a4eeb7ac63`
- Fusões possíveis se o dono decidir: `S-5db2e48980`→`S-a4eeb7ac63`

### Treinamento e Desenvolvimento — `nome_contido`, 2 questão(ões)

- Chave: `treinamento e desenvolvimento`
- Nós:
  - `S-5db2e48980` [subassunto] Psicologia › Análise e desenvolvimento organizacional › Treinamento e desenvolvimento de pessoal: levantamento de necessidades, planejamento, execução e avaliação — 0 questão(ões), 1 item(ns) de edital
  - `S-b5c315a585` [subassunto] Pedagogia › Educação corporativa › Treinamento e Desenvolvimento — 2 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-b5c315a585`
- Fusões possíveis se o dono decidir: `S-5db2e48980`→`S-b5c315a585`

### Ação direta de inconstitucionalidade — `mesmo_nome`, 1 questão(ões)

- Chave: `acao direta de inconstitucionalidade`
- Nós:
  - `S-8261cb365a` [subassunto] DIREITO PROCESSUAL CIVIL › Ações diversas › Ação direta de inconstitucionalidade — 0 questão(ões), 1 item(ns) de edital
  - `S-87fcde9dbc` [subassunto] DIREITO CONSTITUCIONAL › Controle de constitucionalidade › Ação direta de inconstitucionalidade — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-87fcde9dbc`
- Fusões possíveis se o dono decidir: `S-8261cb365a`→`S-87fcde9dbc`

### Accountability — `nome_contido`, 1 questão(ões)

- Chave: `accountability`
- Nós:
  - `A-2b0ce986c1` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Accountability e competência da contabilidade — 0 questão(ões), 1 item(ns) de edital
  - `S-39f2cd6d84` [subassunto] ADMINISTRAÇÃO PÚBLICA › Transparência da administração pública › Accountability — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-39f2cd6d84`
- Fusões possíveis se o dono decidir: `A-2b0ce986c1`→`S-39f2cd6d84`

### Análise de dados: Agrupamentos; Tendências. Projeções — `nome_contido`, 1 questão(ões)

- Chave: `analise de dado`
- Nós:
  - `A-0541a694f4` [assunto] GESTÃO DE PESSOAS › Análise de dados de pessoas — 0 questão(ões), 1 item(ns) de edital
  - `S-2f0b5c64a1` [subassunto] TECNOLOGIA DA INFORMAÇÃO › Dados › Análise de dados: Agrupamentos; Tendências. Projeções — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-2f0b5c64a1`
- Fusões possíveis se o dono decidir: `A-0541a694f4`→`S-2f0b5c64a1`

### Análise e descrição de cargos: objetivos, métodos, vantagens e desvantagens — `nome_contido`, 1 questão(ões)

- Chave: `analise e descricao de cargo`
- Nós:
  - `A-e5126ec569` [assunto] GESTÃO DE PESSOAS › Análise e descrição de cargos: objetivos, métodos, vantagens e desvantagens — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-4a3ded0852` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Análise e descrição de cargos — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `A-e5126ec569`
- Fusões possíveis se o dono decidir: `S-4a3ded0852`→`A-e5126ec569`

### Aplicação da pena — `mesmo_nome`, 1 questão(ões)

- Chave: `aplicacao da pena`
- Nós:
  - `S-6f75bcc7a8` [subassunto] DIREITO PENAL MILITAR › Penas › Aplicação da pena — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ef81107869` [subassunto] DIREITO PENAL › Penas › Aplicação da pena — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-6f75bcc7a8`
- Fusões possíveis se o dono decidir: `S-ef81107869`→`S-6f75bcc7a8`

### Arguição de descumprimento de preceito fundamental — `mesmo_nome`, 1 questão(ões)

- Chave: `arguicao de descumprimento de preceito fundamental`
- Nós:
  - `S-988d2eb654` [subassunto] DIREITO PROCESSUAL CIVIL › Ações diversas › Arguição de descumprimento de preceito fundamental — 0 questão(ões), 1 item(ns) de edital
  - `S-ccb9fefa33` [subassunto] DIREITO CONSTITUCIONAL › Controle de constitucionalidade › Arguição de descumprimento de preceito fundamental — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-ccb9fefa33`
- Fusões possíveis se o dono decidir: `S-988d2eb654`→`S-ccb9fefa33`

### Aspectos qualitativos e quantitativos do patrimônio — `nome_contido`, 1 questão(ões)

- Chave: `aspecto qualitativo e quantitativo`
- Nós:
  - `S-178be6c778` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio e Variações patrimoniais › Aspecto qualitativo e quantitativo — 0 questão(ões), 1 item(ns) de edital
  - `S-275d050035` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Patrimônio › Aspectos qualitativos e quantitativos do patrimônio — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-275d050035`
- Fusões possíveis se o dono decidir: `S-178be6c778`→`S-275d050035`

### Ato administrativo — `nome_contido`, 1 questão(ões)

- Chave: `ato administrativo`
- Nós:
  - `A-eb4a85393a` [assunto] DIREITO ADMINISTRATIVO › Ato administrativo — 1 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-6658665ab8` [subassunto] DIREITO ADMINISTRATIVO › Ato administrativo › Atos administrativos em espécie — 0 questão(ões), 1 item(ns) de edital
  - `S-d4f9eafeef` [subassunto] DIREITO ADMINISTRATIVO › Ato administrativo › Atos administrativos nulos, anuláveis e inexistentes — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-eb4a85393a`
- Fusões possíveis se o dono decidir: `S-6658665ab8`→`A-eb4a85393a`, `S-d4f9eafeef`→`A-eb4a85393a`

### Campo de aplicação da contabilidade — `nome_contido`, 1 questão(ões)

- Chave: `campo de aplicacao`
- Nós:
  - `A-47a2739790` [assunto] Contabilidade Aplicada ao Setor Público › Campo de aplicação — 0 questão(ões), 1 item(ns) de edital
  - `A-a2e768a198` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Campo de aplicação da contabilidade — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `A-a2e768a198`
- Fusões possíveis se o dono decidir: `A-47a2739790`→`A-a2e768a198`

### Classificação da despesa pública: institucional, funcional, programática, pela natureza — `nome_contido`, 1 questão(ões)

- Chave: `classificacao da despesa publica`
- Nós:
  - `S-4ef449f480` [subassunto] Administração Orçamentária e Financeira › Manual Técnico do Orçamento - MTO 2024 › Classificação da despesa pública: institucional, funcional, programática, pela natureza e classificações adicionais previstas no Manual Técnico de Orçamento (MTO) — 0 questão(ões), 1 item(ns) de edital
  - `S-cf8438998b` [subassunto] Administração Orçamentária e Financeira › Classificações orçamentárias › Classificação da despesa pública: institucional, funcional, programática, pela natureza — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-cf8438998b`
- Fusões possíveis se o dono decidir: `S-4ef449f480`→`S-cf8438998b`

### Conflitos de competência — `nome_contido`, 1 questão(ões)

- Chave: `conflito de competencia`
- Nós:
  - `S-539cd4e700` [subassunto] DIREITO PROCESSUAL PENAL MILITAR › Competência em geral › Conflitos de competência — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-5c3d29d220` [subassunto] DIREITO PROCESSUAL CIVIL › Jurisdição e competência › Conflitos de competência e de atribuição — 0 questão(ões), 1 item(ns) de edital
  - `S-933cd9e461` [subassunto] DIREITO PROCESSUAL PENAL › Competência penal › Conflitos de competência e de atribuição — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-539cd4e700`
- Fusões possíveis se o dono decidir: `S-5c3d29d220`→`S-539cd4e700`, `S-933cd9e461`→`S-539cd4e700`

### Constituição da República Federativa do Brasil de 1988: Capítulo III Segurança Pública: ar — `nome_contido`, 1 questão(ões)

- Chave: `constituicao da republica`
- Nós:
  - `A-a3a5007f7e` [assunto] DIREITO CONSTITUCIONAL › Constituição da República Federativa do Brasil de 1988 e emendas — 0 questão(ões), 1 item(ns) de edital
  - `A-e642b967a1` [assunto] DIREITO CONSTITUCIONAL › Constituição da República Federativa do Brasil de 1988: Capítulo III Segurança Pública: artigo 144 — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `AL-efc5bfb214` [assunto] DIREITO CONSTITUCIONAL › Constituição da República Federativa do Brasil de 1988 — 0 questão(ões), 5 item(ns) de edital
  - `S-669f061cdf` [subassunto] Pedagogia › Fundamentos da educação › Constituição da República — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-e642b967a1`
- Fusões possíveis se o dono decidir: `A-a3a5007f7e`→`A-e642b967a1`, `AL-efc5bfb214`→`A-e642b967a1`, `S-669f061cdf`→`A-e642b967a1`

### Contratos administrativos — `mesmo_nome`, 1 questão(ões)

- Chave: `contrato administrativo`
- Nós:
  - `A-90da2a8e17` [assunto] LICITAÇÕES E CONTRATOS › Contratos administrativos — 0 questão(ões), 1 item(ns) de edital
  - `A-91e52e6c2e` [assunto] DIREITO ADMINISTRATIVO › Contratos administrativos — 1 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `A-91e52e6c2e`
- Fusões possíveis se o dono decidir: `A-90da2a8e17`→`A-91e52e6c2e`

### Crimes contra a incolumidade pública — `mesmo_nome`, 1 questão(ões)

- Chave: `crime contra a incolumidade publica`
- Nós:
  - `A-dcc04a2965` [assunto] DIREITO PENAL MILITAR › Crimes contra a incolumidade pública — 0 questão(ões), 1 item(ns) de edital
  - `S-1919551869` [subassunto] DIREITO PENAL › Crimes em espécie do Código Penal › Crimes contra a incolumidade pública — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-1919551869`
- Sem operação (nível diferente com filhos, decisão do dono): `A-dcc04a2965`

### Demonstração do resultado do exercício — `nome_contido`, 1 questão(ões)

- Chave: `demonstracao do resultado do exercicio`
- Nós:
  - `S-97f26522fe` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis pela legislação societária e pelas Normas Brasileiras de Contabilidade › Demonstração do Resultado do Exercício e Demonstração do Resultado Abrangente — 0 questão(ões), 1 item(ns) de edital
  - `S-a41e5fa58f` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis conforme a legislação societária, os princípios fundamentais da contabilidade e os pronunciamentos contábeis do Comitê de Pronunciamentos Contábeis (CPC) › Demonstração do resultado do exercício — 1 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-a41e5fa58f`
- Fusões possíveis se o dono decidir: `S-97f26522fe`→`S-a41e5fa58f`

### Design thinking — `nome_contido`, 1 questão(ões)

- Chave: `design thinking`
- Nós:
  - `A-be3647481c` [assunto] Pedagogia › Design thinking na educação — 0 questão(ões), 1 item(ns) de edital
  - `S-7258e86b3c` [subassunto] COMUNICAÇÃO SOCIAL › Comunicação nas organizações › Design thinking — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-7258e86b3c`
- Fusões possíveis se o dono decidir: `A-be3647481c`→`S-7258e86b3c`

### Design Thinking — `nome_contido`, 1 questão(ões)

- Chave: `design thinking`
- Nós:
  - `A-be3647481c` [assunto] Pedagogia › Design thinking na educação — 0 questão(ões), 1 item(ns) de edital
  - `S-eb23e19ae9` [subassunto] ADMINISTRAÇÃO PÚBLICA › Inovação na gestão pública › Design Thinking — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-eb23e19ae9`
- Fusões possíveis se o dono decidir: `A-be3647481c`→`S-eb23e19ae9`

### Direitos humanos — `nome_contido`, 1 questão(ões)

- Chave: `direito humano`
- Nós:
  - `S-8aa1c4aa58` [subassunto] Psicologia › Psicologia e desafios contemporâneos › Direitos humanos — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-fb045a86f0` [subassunto] LICENCIAMENTO AMBIENTAL FEDERAL › Demografia, Economia e Sociologia › Direitos Humanos e Políticas Públicas: Políticas sociais, Estado de bem-estar social, desenvolvimento agrário, economia do setor público — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-8aa1c4aa58`
- Fusões possíveis se o dono decidir: `S-fb045a86f0`→`S-8aa1c4aa58`

### Disponibilidades: caixa e equivalentes de caixa — `nome_contido`, 1 questão(ões)

- Chave: `disponibilidade`
- Nós:
  - `A-b715bd80be` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Disponibilidades: caixa e equivalentes de caixa — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-6db5c31c63` [subassunto] SEGURANÇA DA INFORMAÇÃO › Conceitos básicos › Disponibilidade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-b715bd80be`
- Fusões possíveis se o dono decidir: `S-6db5c31c63`→`A-b715bd80be`

### documento de arquivo — `nome_contido`, 1 questão(ões)

- Chave: `documento de arquivo`
- Nós:
  - `A-02319323fa` [assunto] ARQUIVOLOGIA › Documentos de arquivos: características e especificidades — 0 questão(ões), 1 item(ns) de edital
  - `S-23527db129` [subassunto] ARQUIVOLOGIA › Documentos de arquivos: características e especificidades › documento de arquivo — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-23527db129`
- Sem operação (nível diferente com filhos, decisão do dono): `A-02319323fa`

### Efeitos da condenação — `mesmo_nome`, 1 questão(ões)

- Chave: `efeito da condenacao`
- Nós:
  - `S-23f44121da` [subassunto] DIREITO PENAL › Penas › Efeitos da condenação — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-71387f8387` [subassunto] DIREITO PENAL MILITAR › Penas › Efeitos da condenação — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-23f44121da`
- Fusões possíveis se o dono decidir: `S-71387f8387`→`S-23f44121da`

### Formas e tipos de Auditoria — `nome_contido`, 1 questão(ões)

- Chave: `forma e tipo de auditoria`
- Nós:
  - `A-e017e815ca` [assunto] AUDITORIA GOVERNAMENTAL › Formas e tipos de Auditoria. Normas relativas à execução dos trabalhos — 0 questão(ões), 1 item(ns) de edital
  - `S-1092178b94` [subassunto] AUDITORIA GOVERNAMENTAL › Formas e tipos de Auditoria. Normas relativas à execução dos trabalhos › Formas e tipos de Auditoria — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-1092178b94`
- Sem operação (nível diferente com filhos, decisão do dono): `A-e017e815ca`

### IN/MPOG nº 5/2017 e IN/SEGES/ME nº 98/2022 — `mesmo_nome`, 1 questão(ões)

- Chave: `in mpog no 5 2017 e in sege me no 98 2022`
- Nós:
  - `S-48e6b961bb` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Licitações e contratos administrativos › IN/MPOG nº 5/2017 e IN/SEGES/ME nº 98/2022 — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-4a556c269d` [subassunto] DIREITO ADMINISTRATIVO › Contratos administrativos › IN/MPOG nº 5/2017 e IN/SEGES/ME nº 98/2022 — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-48e6b961bb`
- Fusões possíveis se o dono decidir: `S-4a556c269d`→`S-48e6b961bb`

### Instrução Normativa IBAMA nº 17/2011 (Regulamentação da TCFA – Taxa de Controle e Fiscaliz — `mesmo_nome`, 1 questão(ões)

- Chave: `instrucao normativa ibama no 17 2011`
- Nós:
  - `S-be6db68d34` [subassunto] QUALIDADE AMBIENTAL › Qualidade Ambiental › Instrução Normativa IBAMA nº 17/2011 (Taxa de Controle e Fiscalização Ambiental – TCFA) — 0 questão(ões), 1 item(ns) de edital
  - `S-bea2d0615f` [subassunto] Administração Orçamentária e Financeira › Direito Financeiro e Tributário › Instrução Normativa IBAMA nº 17/2011 (Regulamentação da TCFA – Taxa de Controle e Fiscalização Ambiental) — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-bea2d0615f`
- Fusões possíveis se o dono decidir: `S-be6db68d34`→`S-bea2d0615f`

### sistema de planejamento e orçamento e de programação financeira constantes da Lei nº 10.18 — `mesma_norma`, 1 questão(ões)

- Chave: `lei 10180`
- Nós:
  - `A-eabcd3fa3e` [assunto] Contabilidade Aplicada ao Setor Público › Lei nº 10.180/2001 — 0 questão(ões), 1 item(ns) de edital
  - `S-779cf1610f` [subassunto] Administração Orçamentária e Financeira › Gestão organizacional das finanças públicas › sistema de planejamento e orçamento e de programação financeira constantes da Lei nº 10.180/2001 — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-de6f6672d3` [subassunto] Contabilidade Aplicada ao Setor Público › Sistema de contabilidade federal › Organização e competências (Lei nº 10.180/2021 e Decreto nº 6.976/2009) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-779cf1610f`
- Fusões possíveis se o dono decidir: `A-eabcd3fa3e`→`S-779cf1610f`, `S-de6f6672d3`→`S-779cf1610f`

### Lei penal no tempo — `nome_contido`, 1 questão(ões)

- Chave: `lei penal no tempo`
- Nós:
  - `S-36940ebaa3` [subassunto] DIREITO PENAL › Código Penal › Lei penal no tempo — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-492e8fe96c` [subassunto] DIREITO PENAL › Aplicação da lei penal › Lei penal no tempo e no espaço — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-36940ebaa3`
- Fusões possíveis se o dono decidir: `S-492e8fe96c`→`S-36940ebaa3`

### Mensuração do Valor Justo — `nome_contido`, 1 questão(ões)

- Chave: `mensuracao do valor justo`
- Nós:
  - `A-a50edd7988` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Mensuração do Valor Justo. Receita de Contrato com Cliente — 0 questão(ões), 1 item(ns) de edital
  - `S-c0f7d82f17` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Mensuração do Valor Justo. Receita de Contrato com Cliente › Mensuração do Valor Justo — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-c0f7d82f17`
- Sem operação (nível diferente com filhos, decisão do dono): `A-a50edd7988`

### Organização político-administrativa do Estado — `nome_contido`, 1 questão(ões)

- Chave: `organizacao politico administrativa`
- Nós:
  - `AL-74a8d407db` [assunto] DIREITO CONSTITUCIONAL › Organização político-administrativa do Estado — 1 questão(ões), 4 item(ns) de edital **(destino)**
  - `S-09b573ab36` [subassunto] DIREITO CONSTITUCIONAL › Organização do Estado › Organização político-administrativa — 0 questão(ões), 2 item(ns) de edital
- Destino sugerido: `AL-74a8d407db`
- Fusões possíveis se o dono decidir: `S-09b573ab36`→`AL-74a8d407db`

### Processo Legislativo — `mesmo_nome`, 1 questão(ões)

- Chave: `processo legislativo`
- Nós:
  - `A-de2fd9af0b` [assunto] Processo Legislativo › Processo Legislativo — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-cf159107c7` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Processo legislativo — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-de2fd9af0b`
- Fusões possíveis se o dono decidir: `S-cf159107c7`→`A-de2fd9af0b`

### Recrutamento e seleção de pessoas — `nome_contido`, 1 questão(ões)

- Chave: `recrutamento e selecao`
- Nós:
  - `A-252bd3d3fe` [assunto] Psicologia › Recrutamento e seleção de pessoas — 0 questão(ões), 1 item(ns) de edital
  - `S-28e27fcd34` [subassunto] GESTÃO DE PESSOAS › Processos de gestão de pessoas › Recrutamento e seleção de pessoas — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d07ed7604f` [subassunto] GESTÃO DE PESSOAS › Gestão de pessoas › Recrutamento e seleção — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-28e27fcd34`
- Fusões possíveis se o dono decidir: `S-d07ed7604f`→`S-28e27fcd34`
- Sem operação (nível diferente com filhos, decisão do dono): `A-252bd3d3fe`

### Registro e notificação de irregularidades — `mesmo_nome`, 1 questão(ões)

- Chave: `registro e notificacao de irregularidade`
- Nós:
  - `S-b01b3e71fd` [subassunto] DIREITO ADMINISTRATIVO › Contratos administrativos › Registro e notificação de irregularidades — 0 questão(ões), 1 item(ns) de edital
  - `S-b56196a0f2` [subassunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos › Registro e notificação de irregularidades — 1 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-c7d6f85346` [subassunto] LICITAÇÕES E CONTRATOS › Contratos administrativos › Registro e notificação de irregularidades — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-b56196a0f2`
- Fusões possíveis se o dono decidir: `S-b01b3e71fd`→`S-b56196a0f2`, `S-c7d6f85346`→`S-b56196a0f2`

### Sistemas de informações — `nome_contido`, 1 questão(ões)

- Chave: `sistema de informacao`
- Nós:
  - `A-3e04ed2d75` [assunto] Contabilidade Aplicada ao Setor Público › Sistema de Informações Contábeis e Fiscais do Setor Público Brasileiro (SICONFI) — 0 questão(ões), 1 item(ns) de edital
  - `A-61e8a5afa3` [assunto] MONITORAMENTO AMBIENTAL › Sistemas de Informação Geográfica (SIG) — 0 questão(ões), 1 item(ns) de edital
  - `S-d4b5530f95` [subassunto] Administração Orçamentária e Financeira › Programação, execução e controle de recursos orçamentários e financeiros › Sistemas de informações — 1 questão(ões), 1 item(ns) de edital **(destino)**
- Destino sugerido: `S-d4b5530f95`
- Fusões possíveis se o dono decidir: `A-3e04ed2d75`→`S-d4b5530f95`
- Sem operação (nível diferente com filhos, decisão do dono): `A-61e8a5afa3`

### Territorialidade e extraterritorialidade da lei penal — `nome_contido`, 1 questão(ões)

- Chave: `territorialidade`
- Nós:
  - `S-97625189b3` [subassunto] DIREITO PENAL › Aplicação da lei penal › Territorialidade e extraterritorialidade da lei penal — 1 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-c4f4e4cdce` [subassunto] DIREITO PENAL › Código Penal › Territorialidade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-97625189b3`
- Fusões possíveis se o dono decidir: `S-c4f4e4cdce`→`S-97625189b3`

### Ação declaratória de constitucionalidade — `mesmo_nome`, 0 questão(ões)

- Chave: `acao declaratoria de constitucionalidade`
- Nós:
  - `S-37cdfa966e` [subassunto] DIREITO PROCESSUAL CIVIL › Ações diversas › Ação declaratória de constitucionalidade — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-fbb278a6ec` [subassunto] DIREITO CONSTITUCIONAL › Controle de constitucionalidade › Ação declaratória de constitucionalidade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-37cdfa966e`
- Fusões possíveis se o dono decidir: `S-fbb278a6ec`→`S-37cdfa966e`

### Ação direta de inconstitucionalidade por omissão — `nome_contido`, 0 questão(ões)

- Chave: `acao direta de inconstitucionalidade`
- Nós:
  - `S-507a913124` [subassunto] DIREITO CONSTITUCIONAL › Controle de constitucionalidade › Ação direta de inconstitucionalidade por omissão — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-8261cb365a` [subassunto] DIREITO PROCESSUAL CIVIL › Ações diversas › Ação direta de inconstitucionalidade — 0 questão(ões), 1 item(ns) de edital
  - `S-cf2b859895` [subassunto] DIREITO CONSTITUCIONAL › Controle de constitucionalidade › Ação direta de inconstitucionalidade interventiva — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-507a913124`
- Fusões possíveis se o dono decidir: `S-8261cb365a`→`S-507a913124`, `S-cf2b859895`→`S-507a913124`

### Ação penal — `mesmo_nome`, 0 questão(ões)

- Chave: `acao penal`
- Nós:
  - `A-325398b100` [assunto] DIREITO PROCESSUAL PENAL › Ação penal — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-4f7e2b964a` [assunto] DIREITO PENAL MILITAR › Ação penal — 0 questão(ões), 1 item(ns) de edital
  - `A-65b5e1aa5c` [assunto] DIREITO PENAL › Ação penal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-325398b100`
- Fusões possíveis se o dono decidir: `A-4f7e2b964a`→`A-325398b100`, `A-65b5e1aa5c`→`A-325398b100`

### Acesso à informação (Lei nº 12.527/2011 e Decreto nº 7.724/2012) — `nome_contido`, 0 questão(ões)

- Chave: `acesso a informacao`
- Nós:
  - `A-2ab02b7fee` [assunto] TECNOLOGIA DA INFORMAÇÃO › Acesso à informação (Lei nº 12.527/2011 e Decreto nº 7.724/2012) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-73eefa53ea` [assunto] DIREITO ADMINISTRATIVO › Acesso à informação e proteção de dados — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-2ab02b7fee`
- Fusões possíveis se o dono decidir: `A-73eefa53ea`→`A-2ab02b7fee`

### administração de recursos materiais — `nome_contido`, 0 questão(ões)

- Chave: `administracao de recurso materiais`
- Nós:
  - `A-a80c3d64ea` [assunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › administração de recursos materiais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-ad7c69f8cb` [assunto] LOGÍSTICA E PATRIMÔNIO › Administração de Recursos Materiais e Patrimoniais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-a80c3d64ea`
- Fusões possíveis se o dono decidir: `A-ad7c69f8cb`→`A-a80c3d64ea`

### Atos processuais — `mesmo_nome`, 0 questão(ões)

- Chave: `ato processuais`
- Nós:
  - `A-6f73a38bfe` [assunto] DIREITO PROCESSUAL CIVIL › Atos processuais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-b55f2afaae` [assunto] DIREITO PROCESSUAL PENAL › Atos processuais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-6f73a38bfe`
- Fusões possíveis se o dono decidir: `A-b55f2afaae`→`A-6f73a38bfe`

### Bancos de dados — `nome_contido`, 0 questão(ões)

- Chave: `banco de dado`
- Nós:
  - `A-3ed5e6700c` [assunto] DESENVOLVIMENTO DE SISTEMAS › Bancos de dados — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-e02df9d2b4` [assunto] TECNOLOGIA DA INFORMAÇÃO › bancos de dados relacionais — 0 questão(ões), 1 item(ns) de edital
  - `S-d5fc6db6ad` [subassunto] DESENVOLVIMENTO DE SISTEMAS › Bancos de dados › bancos de dados NoSQL (orientados a documento, chave-valor, grafo e colunar) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-3ed5e6700c`
- Fusões possíveis se o dono decidir: `A-e02df9d2b4`→`A-3ed5e6700c`, `S-d5fc6db6ad`→`A-3ed5e6700c`

### Banco de dados — `nome_contido`, 0 questão(ões)

- Chave: `banco de dado`
- Nós:
  - `A-7736014b5b` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Banco de dados — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `A-e02df9d2b4` [assunto] TECNOLOGIA DA INFORMAÇÃO › bancos de dados relacionais — 0 questão(ões), 1 item(ns) de edital
  - `S-d5fc6db6ad` [subassunto] DESENVOLVIMENTO DE SISTEMAS › Bancos de dados › bancos de dados NoSQL (orientados a documento, chave-valor, grafo e colunar) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-7736014b5b`
- Fusões possíveis se o dono decidir: `A-e02df9d2b4`→`A-7736014b5b`, `S-d5fc6db6ad`→`A-7736014b5b`

### bancos de dados relacionais — `nome_contido`, 0 questão(ões)

- Chave: `banco de dado`
- Nós:
  - `A-e02df9d2b4` [assunto] TECNOLOGIA DA INFORMAÇÃO › bancos de dados relacionais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-1825cbd184` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Banco de dados › Banco de dados — 0 questão(ões), 1 item(ns) de edital
  - `S-d5fc6db6ad` [subassunto] DESENVOLVIMENTO DE SISTEMAS › Bancos de dados › bancos de dados NoSQL (orientados a documento, chave-valor, grafo e colunar) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-e02df9d2b4`
- Fusões possíveis se o dono decidir: `S-1825cbd184`→`A-e02df9d2b4`, `S-d5fc6db6ad`→`A-e02df9d2b4`

### Conexão e continência — `mesmo_nome`, 0 questão(ões)

- Chave: `conexao e continencia`
- Nós:
  - `S-310b7d9143` [subassunto] DIREITO PROCESSUAL CIVIL › Ação › Conexão e continência — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d5d99bc6a6` [subassunto] DIREITO PROCESSUAL PENAL › Competência penal › Conexão e continência — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-310b7d9143`
- Fusões possíveis se o dono decidir: `S-d5d99bc6a6`→`S-310b7d9143`

### Conflitos de competência e de atribuição — `mesmo_nome`, 0 questão(ões)

- Chave: `conflito de competencia e de atribuicao`
- Nós:
  - `S-5c3d29d220` [subassunto] DIREITO PROCESSUAL CIVIL › Jurisdição e competência › Conflitos de competência e de atribuição — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-933cd9e461` [subassunto] DIREITO PROCESSUAL PENAL › Competência penal › Conflitos de competência e de atribuição — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-5c3d29d220`
- Fusões possíveis se o dono decidir: `S-933cd9e461`→`S-5c3d29d220`

### Consolidação das demonstrações contábeis e demonstrações separadas — `nome_contido`, 0 questão(ões)

- Chave: `consolidacao das demonstracao contabeis`
- Nós:
  - `A-4a2df0effe` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Consolidação das demonstrações contábeis e demonstrações separadas — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-fb9b8ac273` [assunto] Contabilidade Aplicada ao Setor Público › Consolidação das demonstrações contábeis — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-4a2df0effe`
- Fusões possíveis se o dono decidir: `A-fb9b8ac273`→`A-4a2df0effe`

### Consolidação das demonstrações contábeis — `nome_contido`, 0 questão(ões)

- Chave: `consolidacao das demonstracao contabeis`
- Nós:
  - `A-4a2df0effe` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Consolidação das demonstrações contábeis e demonstrações separadas — 0 questão(ões), 1 item(ns) de edital
  - `S-f293322cbf` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Consolidação das demonstrações contábeis — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-f293322cbf`
- Fusões possíveis se o dono decidir: `A-4a2df0effe`→`S-f293322cbf`

### Contratos administrativos — `nome_contido`, 0 questão(ões)

- Chave: `contrato administrativo`
- Nós:
  - `A-90da2a8e17` [assunto] LICITAÇÕES E CONTRATOS › Contratos administrativos — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-c3921a1df9` [assunto] DIREITO ADMINISTRATIVO › Contrato administrativo para compras na administração pública — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-90da2a8e17`
- Fusões possíveis se o dono decidir: `A-c3921a1df9`→`A-90da2a8e17`

### Controle de acesso — `nome_contido`, 0 questão(ões)

- Chave: `controle de acesso`
- Nós:
  - `A-8763b26044` [assunto] SEGURANÇA DA INFORMAÇÃO › Controle de acesso — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d30e1fb994` [subassunto] SEGURANÇA DA INFORMAÇÃO › Controle de acesso › Controle de acesso baseado em papéis — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-8763b26044`
- Fusões possíveis se o dono decidir: `S-d30e1fb994`→`A-8763b26044`

### Deploy de aplicações — `nome_contido`, 0 questão(ões)

- Chave: `deploy de aplicacao`
- Nós:
  - `A-14e4537cf0` [assunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Deploy de aplicações — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-86aa8fec3c` [subassunto] INFRAESTRUTURA DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Virtualização de desktop › Deploy de aplicações; continuous delivery e continuous integration (CI/CD) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-14e4537cf0`
- Fusões possíveis se o dono decidir: `S-86aa8fec3c`→`A-14e4537cf0`

### Deploy de aplicações; continuous delivery e continuous integration (CI/CD) — `nome_contido`, 0 questão(ões)

- Chave: `deploy de aplicacao`
- Nós:
  - `S-86aa8fec3c` [subassunto] INFRAESTRUTURA DE TECNOLOGIA DA INFORMAÇÃO E COMUNICAÇÃO › Virtualização de desktop › Deploy de aplicações; continuous delivery e continuous integration (CI/CD) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f99f646a55` [subassunto] ARQUITETURA DE DESENVOLVIMENTO DA PLATAFORMA DIGITAL DO PODER JUDICIÁRIO BRASILEIRO (PDPJ-Br) › Deploy de aplicações › Deploy de aplicações — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-86aa8fec3c`
- Fusões possíveis se o dono decidir: `S-f99f646a55`→`S-86aa8fec3c`

### direitos políticos e partidos políticos — `nome_contido`, 0 questão(ões)

- Chave: `direito politico`
- Nós:
  - `S-7a1c3efbea` [subassunto] DIREITO CONSTITUCIONAL › Princípios Fundamentais. Direitos e garantias fundamentais › direitos políticos e partidos políticos — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d4b4927ae0` [subassunto] DIREITO CONSTITUCIONAL › Direitos e garantias fundamentais › Direitos políticos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-7a1c3efbea`
- Fusões possíveis se o dono decidir: `S-d4b4927ae0`→`S-7a1c3efbea`

### Eficácia da sentença estrangeira — `nome_contido`, 0 questão(ões)

- Chave: `eficacia da sentenca`
- Nós:
  - `S-682269b24c` [subassunto] DIREITO PENAL › Aplicação da lei penal › Eficácia da sentença estrangeira — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-72b24f8c12` [subassunto] DIREITO PENAL › Código Penal › Eficácia da sentença — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-682269b24c`
- Fusões possíveis se o dono decidir: `S-72b24f8c12`→`S-682269b24c`

### Elaboração e fiscalização de contratos — `mesmo_nome`, 0 questão(ões)

- Chave: `elaboracao e fiscalizacao de contrato`
- Nós:
  - `A-63b01c2c75` [assunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Elaboração e fiscalização de contratos — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-43918fdbe8` [subassunto] DIREITO ADMINISTRATIVO › Contratos administrativos › Elaboração e fiscalização de contratos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-63b01c2c75`
- Fusões possíveis se o dono decidir: `S-43918fdbe8`→`A-63b01c2c75`

### Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido — `nome_contido`, 0 questão(ões)

- Chave: `emprestimo e financiamento debenture e outro titulo de divida`
- Nós:
  - `A-89a46c189f` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-ec6bbd71e3` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Empréstimos e financiamentos, debêntures e outros títulos de dívida; Patrimônio Líquido › Empréstimos e financiamentos, debêntures e outros títulos de dívida — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-89a46c189f`
- Fusões possíveis se o dono decidir: `S-ec6bbd71e3`→`A-89a46c189f`

### Estrutura organizacional — `nome_contido`, 0 questão(ões)

- Chave: `estrutura organizacional`
- Nós:
  - `S-6e1d90a296` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Estrutura organizacional — 0 questão(ões), 3 item(ns) de edital **(destino)**
  - `S-71c356f64c` [subassunto] Enfermagem › Atendimento a pacientes em situações de urgência e emergência › Estrutura organizacional do serviço de emergência hospitalar e pré-hospitalar — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-6e1d90a296`
- Fusões possíveis se o dono decidir: `S-71c356f64c`→`S-6e1d90a296`

### Finalidades e objetivos da auditoria governamental. Abrangência de atuação — `nome_contido`, 0 questão(ões)

- Chave: `finalidade e objetivo da auditoria governamental`
- Nós:
  - `A-63e1339273` [assunto] AUDITORIA GOVERNAMENTAL › Finalidades e objetivos da auditoria governamental. Abrangência de atuação — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d528f8a9b5` [subassunto] AUDITORIA GOVERNAMENTAL › Finalidades e objetivos da auditoria governamental. Abrangência de atuação › Finalidades e objetivos da auditoria governamental — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-63e1339273`
- Fusões possíveis se o dono decidir: `S-d528f8a9b5`→`A-63e1339273`

### Geoprocessamento e Análise de dados — `nome_contido`, 0 questão(ões)

- Chave: `geoprocessamento`
- Nós:
  - `A-179a5a9c7d` [assunto] MONITORAMENTO AMBIENTAL › Geoprocessamento e Análise de dados — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-da6fa2814d` [assunto] BIODIVERSIDADE E FLORESTAS › Geoprocessamento — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-179a5a9c7d`
- Fusões possíveis se o dono decidir: `A-da6fa2814d`→`A-179a5a9c7d`

### Gestão organizacional das finanças públicas — `nome_contido`, 0 questão(ões)

- Chave: `gestao organizacional`
- Nós:
  - `A-0cce2271e3` [assunto] Administração Orçamentária e Financeira › Gestão organizacional das finanças públicas — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-9467d431a1` [assunto] ADMINISTRAÇÃO GERAL › Gestão organizacional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-0cce2271e3`
- Fusões possíveis se o dono decidir: `A-9467d431a1`→`A-0cce2271e3`

### Imputabilidade penal — `mesmo_nome`, 0 questão(ões)

- Chave: `imputabilidade penal`
- Nós:
  - `A-3947100589` [assunto] DIREITO PENAL MILITAR › Imputabilidade penal — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-82eef8dbae` [assunto] DIREITO PENAL › Imputabilidade penal — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-3947100589`
- Fusões possíveis se o dono decidir: `A-82eef8dbae`→`A-3947100589`

### Incidente de insanidade mental do acusado e incidente de falsidade de documento — `nome_contido`, 0 questão(ões)

- Chave: `incidente de insanidade mental do acusado`
- Nós:
  - `A-ee405a3ab0` [assunto] DIREITO PROCESSUAL PENAL MILITAR › Incidente de insanidade mental do acusado e incidente de falsidade de documento — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d5e9aef55c` [subassunto] DIREITO PROCESSUAL PENAL › Questões e processos incidentes › Incidente de insanidade mental do acusado — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-ee405a3ab0`
- Fusões possíveis se o dono decidir: `S-d5e9aef55c`→`A-ee405a3ab0`

### O indivíduo e o contexto organizacional: variáveis individuais, grupais e organizacionais — `nome_contido`, 0 questão(ões)

- Chave: `individuo e o contexto organizacional`
- Nós:
  - `A-e5cf9f8b34` [assunto] GESTÃO DE PESSOAS › O indivíduo e o contexto organizacional: variáveis individuais, grupais e organizacionais — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-2a5ac95e25` [subassunto] Psicologia › Planejamento estratégico da gestão de pessoas › O indivíduo e o contexto organizacional: percepção, atitudes, valores e diferenças individuais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-e5cf9f8b34`
- Fusões possíveis se o dono decidir: `S-2a5ac95e25`→`A-e5cf9f8b34`

### Licitações e contratos administrativos — `nome_contido`, 0 questão(ões)

- Chave: `licitacao e contrato`
- Nós:
  - `A-2ad18c5e46` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Licitações e contratos — 0 questão(ões), 1 item(ns) de edital
  - `A-402fcb34b6` [assunto] GESTÃO DE CONTRATOS E RECURSOS MATERIAIS › Licitações e contratos administrativos — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `A-402fcb34b6`
- Fusões possíveis se o dono decidir: `A-2ad18c5e46`→`A-402fcb34b6`

### Livramento condicional — `mesmo_nome`, 0 questão(ões)

- Chave: `livramento condicional`
- Nós:
  - `S-7a99793c63` [subassunto] DIREITO PENAL › Penas › Livramento condicional — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-adf12f5b6f` [subassunto] DIREITO PENAL MILITAR › Penas › Livramento condicional — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-7a99793c63`
- Fusões possíveis se o dono decidir: `S-adf12f5b6f`→`S-7a99793c63`

### Manejo de fauna — `nome_contido`, 0 questão(ões)

- Chave: `manejo de fauna`
- Nós:
  - `A-af65658fef` [assunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Manejo de fauna — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f5f06e2490` [subassunto] MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE › Manejo de fauna › Manejo de fauna silvestre, suas populações e de metapopulações in situ e ex situ — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-af65658fef`
- Fusões possíveis se o dono decidir: `S-f5f06e2490`→`A-af65658fef`

### Manual de Contabilidade Aplicada ao Setor Público (MCASP), 10ª edição — `nome_contido`, 0 questão(ões)

- Chave: `manual de contabilidade aplicada ao setor publico`
- Nós:
  - `A-0dcd05d4dd` [assunto] Contabilidade Aplicada ao Setor Público › Manual de Contabilidade Aplicada ao Setor Público (MCASP) 11ª edição — 0 questão(ões), 1 item(ns) de edital
  - `A-90f96c99ae` [assunto] Administração Orçamentária e Financeira › Manual de Contabilidade Aplicada ao Setor Público (MCASP) 10ª ed - Parte I - Procedimentos Contábeis Orçamentários, aprovada pela Portaria Conjunta STN/SOF nº 23, de 11 de dezembro de 2023 — 0 questão(ões), 1 item(ns) de edital
  - `AL-ceee9dd21f` [assunto] Contabilidade Aplicada ao Setor Público › Manual de Contabilidade Aplicada ao Setor Público (MCASP), 10ª edição — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `AL-ceee9dd21f`
- Fusões possíveis se o dono decidir: `A-0dcd05d4dd`→`AL-ceee9dd21f`, `A-90f96c99ae`→`AL-ceee9dd21f`

### Medidas de segurança — `mesmo_nome`, 0 questão(ões)

- Chave: `medida de seguranca`
- Nós:
  - `A-3ac6246da8` [assunto] DIREITO PENAL MILITAR › Medidas de segurança — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-794bf97b29` [assunto] DIREITO PENAL › Medidas de segurança — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-3ac6246da8`
- Fusões possíveis se o dono decidir: `A-794bf97b29`→`A-3ac6246da8`

### Modelagens de dados — `nome_contido`, 0 questão(ões)

- Chave: `modelagem de dado`
- Nós:
  - `A-48c7cb56b8` [assunto] BANCO DE DADOS E CIÊNCIA DE DADOS › Modelagens de dados — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-1368848222` [subassunto] MONITORAMENTO AMBIENTAL › Estrutura de dados espaciais › Modelagem de dados em geoprocessamento — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-48c7cb56b8`
- Fusões possíveis se o dono decidir: `S-1368848222`→`A-48c7cb56b8`

### Monitoramento ambiental: conceitos, objetivos e suas aplicações no solo, ar, água, fauna,  — `nome_contido`, 0 questão(ões)

- Chave: `monitoramento ambiental`
- Nós:
  - `A-0f9220de34` [assunto] BIODIVERSIDADE E FLORESTAS › Monitoramento ambiental: conceitos, objetivos e suas aplicações no solo, ar, água, fauna, flora e ecossistemas — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-65336f2f6d` [subassunto] LICENCIAMENTO AMBIENTAL FEDERAL › Licenciamento Ambiental e Avaliação de Impacto › Monitoramento Ambiental — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-0f9220de34`
- Fusões possíveis se o dono decidir: `S-65336f2f6d`→`A-0f9220de34`

### Notas explicativas às demonstrações contábeis — `nome_contido`, 0 questão(ões)

- Chave: `nota explicativa`
- Nós:
  - `A-b8a505ccf9` [assunto] Contabilidade Aplicada ao Setor Público › Notas explicativas às demonstrações contábeis — 0 questão(ões), 1 item(ns) de edital
  - `S-78a9bdced7` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Elaboração de demonstrações contábeis pela legislação societária e pelas Normas Brasileiras de Contabilidade › Notas explicativas — 0 questão(ões), 1 item(ns) de edital
  - `SL-e55da70bf6` [subassunto] Contabilidade Aplicada ao Setor Público › Demonstrações contábeis aplicadas ao setor público › Notas explicativas às demonstrações contábeis — 0 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-e55da70bf6`
- Fusões possíveis se o dono decidir: `A-b8a505ccf9`→`SL-e55da70bf6`, `S-78a9bdced7`→`SL-e55da70bf6`

### Organização e competências; Conselho Nacional de Justiça — `nome_contido`, 0 questão(ões)

- Chave: `organizacao e competencia`
- Nós:
  - `S-9536f60809` [subassunto] DIREITO CONSTITUCIONAL › Poder Judiciário › Organização e competências; Conselho Nacional de Justiça — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-c773fa0c48` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Organização e competências — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-9536f60809`
- Fusões possíveis se o dono decidir: `S-c773fa0c48`→`S-9536f60809`

### Organização e competências; Conselho Nacional de Justiça — `nome_contido`, 0 questão(ões)

- Chave: `organizacao e competencia`
- Nós:
  - `S-9536f60809` [subassunto] DIREITO CONSTITUCIONAL › Poder Judiciário › Organização e competências; Conselho Nacional de Justiça — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-de6f6672d3` [subassunto] Contabilidade Aplicada ao Setor Público › Sistema de contabilidade federal › Organização e competências (Lei nº 10.180/2021 e Decreto nº 6.976/2009) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-9536f60809`
- Fusões possíveis se o dono decidir: `S-de6f6672d3`→`S-9536f60809`

### Políticas de saúde do serviço público federal — `nome_contido`, 0 questão(ões)

- Chave: `politica de saude`
- Nós:
  - `S-98ddc4a6e9` [subassunto] Psicologia › Psicologia da saúde › Políticas de saúde do serviço público federal — 0 questão(ões), 2 item(ns) de edital **(destino)**
  - `S-98e60de9fa` [subassunto] Enfermagem › Sistema Único de Saúde (SUS) › Políticas de saúde — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-98ddc4a6e9`
- Fusões possíveis se o dono decidir: `S-98e60de9fa`→`S-98ddc4a6e9`

### Políticas públicas — `nome_contido`, 0 questão(ões)

- Chave: `politica publica`
- Nós:
  - `A-36bce4a6a2` [assunto] ADMINISTRAÇÃO PÚBLICA › Políticas públicas — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-3c8eb2496b` [assunto] BIODIVERSIDADE E FLORESTAS › Políticas públicas de controle e prevenção do desmatamento — 0 questão(ões), 1 item(ns) de edital
  - `A-8a2851bca6` [assunto] ARQUIVOLOGIA › Políticas públicas dos arquivos permanentes: ações culturais, educativas e de preservação do patrimônio arquivístico — 0 questão(ões), 1 item(ns) de edital
  - `S-37399be5f4` [subassunto] ADMINISTRAÇÃO PÚBLICA › Políticas públicas › Políticas públicas no Estado brasileiro contemporâneo — 0 questão(ões), 1 item(ns) de edital
  - `S-74176eb08c` [subassunto] Enfermagem › Sistema Único de Saúde (SUS) › Políticas públicas do SUS para gestão de recursos físicos, financeiros, materiais e humanos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-36bce4a6a2`
- Fusões possíveis se o dono decidir: `A-3c8eb2496b`→`A-36bce4a6a2`, `A-8a2851bca6`→`A-36bce4a6a2`, `S-37399be5f4`→`A-36bce4a6a2`, `S-74176eb08c`→`A-36bce4a6a2`

### Processo administrativo — `mesmo_nome`, 0 questão(ões)

- Chave: `processo administrativo`
- Nós:
  - `A-a978f3ed66` [assunto] DIREITO ADMINISTRATIVO › Processo administrativo — 0 questão(ões), 1 item(ns) de edital
  - `A-c415e4b4f5` [assunto] ADMINISTRAÇÃO GERAL › Processo administrativo — 0 questão(ões), 4 item(ns) de edital **(destino)**
- Destino sugerido: `A-c415e4b4f5`
- Fusões possíveis se o dono decidir: `A-a978f3ed66`→`A-c415e4b4f5`

### Processo administrativo disciplinar — `nome_contido`, 0 questão(ões)

- Chave: `processo administrativo`
- Nós:
  - `A-a978f3ed66` [assunto] DIREITO ADMINISTRATIVO › Processo administrativo — 0 questão(ões), 1 item(ns) de edital
  - `S-721455144a` [subassunto] DIREITO ADMINISTRATIVO › Agentes públicos › Processo administrativo disciplinar — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-721455144a`
- Sem operação (nível diferente com filhos, decisão do dono): `A-a978f3ed66`

### Processo de planejamento — `nome_contido`, 0 questão(ões)

- Chave: `processo de planejamento`
- Nós:
  - `A-854af298d2` [assunto] Administração Orçamentária e Financeira › Processo de planejamento orçamentário — 0 questão(ões), 1 item(ns) de edital
  - `S-ebcf932a2e` [subassunto] ADMINISTRAÇÃO GERAL › Processo administrativo › Processo de planejamento — 0 questão(ões), 2 item(ns) de edital **(destino)**
- Destino sugerido: `S-ebcf932a2e`
- Sem operação (nível diferente com filhos, decisão do dono): `A-854af298d2`

### Processo Legislativo Orçamentário — `nome_contido`, 0 questão(ões)

- Chave: `processo legislativo`
- Nós:
  - `A-fcd9499dfd` [assunto] Processo Legislativo › Processo Legislativo Orçamentário — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-cf159107c7` [subassunto] DIREITO CONSTITUCIONAL › Organização dos poderes no Estado › Processo legislativo — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-fcd9499dfd`
- Fusões possíveis se o dono decidir: `S-cf159107c7`→`A-fcd9499dfd`

### Programas de integração social e de formação do patrimônio do servidor público (PIS/PASEP) — `nome_contido`, 0 questão(ões)

- Chave: `programa de integracao social`
- Nós:
  - `S-61e3cef25d` [subassunto] CONTABILIDADE TRIBUTÁRIA › Retenções na fonte realizadas pela administração pública federal › Programas de integração social e de formação do patrimônio do servidor público (PIS/PASEP) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-c6a40c48d9` [subassunto] LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS › Retenções na fonte realizadas pela administração pública federal › Programa de Integração Social (PIS) — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-61e3cef25d`
- Fusões possíveis se o dono decidir: `S-c6a40c48d9`→`S-61e3cef25d`

### Questões prejudiciais — `mesmo_nome`, 0 questão(ões)

- Chave: `questao prejudiciais`
- Nós:
  - `A-d7aacb1231` [assunto] DIREITO PROCESSUAL PENAL MILITAR › Questões prejudiciais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-e5e1aba4ea` [subassunto] DIREITO PROCESSUAL PENAL › Questões e processos incidentes › Questões prejudiciais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-d7aacb1231`
- Fusões possíveis se o dono decidir: `S-e5e1aba4ea`→`A-d7aacb1231`

### Relação jurídica processual — `nome_contido`, 0 questão(ões)

- Chave: `relacao juridica processual`
- Nós:
  - `S-dd3aacd88f` [subassunto] DIREITO PROCESSUAL CIVIL › Processo › Relação jurídica processual — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f4436e2f41` [subassunto] DIREITO PROCESSUAL PENAL › Sujeitos e partes do processo › Relação jurídica processual penal: finalidade, natureza jurídica, características, conteúdo, objeto, início, suspensão e fim — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-dd3aacd88f`
- Fusões possíveis se o dono decidir: `S-f4436e2f41`→`S-dd3aacd88f`

### Serviços públicos digitais — `nome_contido`, 0 questão(ões)

- Chave: `servico publico`
- Nós:
  - `A-43596837f2` [assunto] TECNOLOGIA DA INFORMAÇÃO › Serviços públicos digitais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-4560a11578` [assunto] DIREITO ADMINISTRATIVO › Serviços públicos — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-43596837f2`
- Fusões possíveis se o dono decidir: `A-4560a11578`→`A-43596837f2`

### Sistema de custos — `nome_contido`, 0 questão(ões)

- Chave: `sistema de custo`
- Nós:
  - `A-d03a41732b` [assunto] Contabilidade Aplicada ao Setor Público › Sistema de custos — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d9ed0c970f` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Custo das mercadorias e dos produtos vendidos e dos serviços prestados › Sistemas de custos e informações gerenciais — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-d03a41732b`
- Fusões possíveis se o dono decidir: `S-d9ed0c970f`→`A-d03a41732b`

### Sistema de Informações Contábeis e Fiscais do Setor Público Brasileiro (SICONFI) — `nome_contido`, 0 questão(ões)

- Chave: `sistema de informacao`
- Nós:
  - `A-3e04ed2d75` [assunto] Contabilidade Aplicada ao Setor Público › Sistema de Informações Contábeis e Fiscais do Setor Público Brasileiro (SICONFI) — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-61e8a5afa3` [assunto] MONITORAMENTO AMBIENTAL › Sistemas de Informação Geográfica (SIG) — 0 questão(ões), 1 item(ns) de edital
  - `S-2b4abd0f8c` [subassunto] EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA › Programação, execução e controle de recursos orçamentários e financeiros › Sistemas de informações — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-3e04ed2d75`
- Fusões possíveis se o dono decidir: `A-61e8a5afa3`→`A-3e04ed2d75`, `S-2b4abd0f8c`→`A-3e04ed2d75`

### Sistemas de informações — `nome_contido`, 0 questão(ões)

- Chave: `sistema de informacao`
- Nós:
  - `A-3e04ed2d75` [assunto] Contabilidade Aplicada ao Setor Público › Sistema de Informações Contábeis e Fiscais do Setor Público Brasileiro (SICONFI) — 0 questão(ões), 1 item(ns) de edital
  - `A-61e8a5afa3` [assunto] MONITORAMENTO AMBIENTAL › Sistemas de Informação Geográfica (SIG) — 0 questão(ões), 1 item(ns) de edital
  - `SL-dede19b25f` [subassunto] Administração Orçamentária e Financeira › Programação e execução orçamentária e financeira › Sistemas de informações — 0 questão(ões), 3 item(ns) de edital **(destino)**
- Destino sugerido: `SL-dede19b25f`
- Fusões possíveis se o dono decidir: `A-3e04ed2d75`→`SL-dede19b25f`
- Sem operação (nível diferente com filhos, decisão do dono): `A-61e8a5afa3`

### Súmulas e jurisprudência do STF e STJ — `mesmo_nome`, 0 questão(ões)

- Chave: `sumula e jurisprudencia do stf e stj`
- Nós:
  - `A-28c8982ae9` [assunto] DIREITO PENAL › Súmulas e jurisprudência do STF e STJ — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `A-6f82594ae2` [assunto] DIREITO PROCESSUAL PENAL › Súmulas e jurisprudência do STF e STJ — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-28c8982ae9`
- Fusões possíveis se o dono decidir: `A-6f82594ae2`→`A-28c8982ae9`

### Suspensão condicional da pena — `mesmo_nome`, 0 questão(ões)

- Chave: `suspensao condicional da pena`
- Nós:
  - `S-8b09c801a9` [subassunto] DIREITO PENAL › Penas › Suspensão condicional da pena — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-d74a97e5fe` [subassunto] DIREITO PENAL MILITAR › Penas › Suspensão condicional da pena — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `S-8b09c801a9`
- Fusões possíveis se o dono decidir: `S-d74a97e5fe`→`S-8b09c801a9`

### Transações entre partes relacionadas. Arrendamentos. Subvenção e Assistência Governamentai — `nome_contido`, 0 questão(ões)

- Chave: `transacao entre parte relacionada`
- Nós:
  - `A-45eb6cf57f` [assunto] CONTABILIDADE GERAL E SOCIETÁRIA › Transações entre partes relacionadas. Arrendamentos. Subvenção e Assistência Governamentais — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-a87d8a3372` [subassunto] CONTABILIDADE GERAL E SOCIETÁRIA › Transações entre partes relacionadas. Arrendamentos. Subvenção e Assistência Governamentais › Transações entre partes relacionadas — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-45eb6cf57f`
- Fusões possíveis se o dono decidir: `S-a87d8a3372`→`A-45eb6cf57f`

### Transtorno de ansiedade generalizada, Transtorno de pânico, Agorafobia — `nome_contido`, 0 questão(ões)

- Chave: `transtorno de ansiedade`
- Nós:
  - `A-d5fe0490a1` [assunto] Psiquiatria › Transtorno de ansiedade generalizada, Transtorno de pânico, Agorafobia — 0 questão(ões), 1 item(ns) de edital **(destino)**
  - `S-f04d24b3b7` [subassunto] Psicologia › Psicopatologia › Transtornos de ansiedade — 0 questão(ões), 1 item(ns) de edital
- Destino sugerido: `A-d5fe0490a1`
- Fusões possíveis se o dono decidir: `S-f04d24b3b7`→`A-d5fe0490a1`
