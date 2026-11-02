# KAN-95 (Etapa 5B.4, C1): proposta de curadoria da árvore para o BANRISUL_25

Data: 2026-11-02. Somente leitura e redação. Nada do repositório foi editado e não houve commit
nem chamada de LLM. `canonico/arvore.json` não mudou: md5 `f43f36e7…` antes e depois de todas as
medições e da simulação. `git status canonico/ revisao_piloto/` ficou limpo e o
`logs/scraper_cebraspe.log` continuou com 11.787 linhas (rodei com `logging` desligado). Tudo foi
calculado com as funções do projeto (`src/arvore.py`, `canonico.arvore_apos_passo`,
`novidades_do_edital`, `classificar_itens`) sobre cópias em memória.

Base: `plano-etapa-5b4.md` (seções 3, (c) e (d)), `julgamento.json` (216 itens), decisões D3 e D5
do KAN-96, convenções da 5B.3 e os lotes de `canonico/lotes/`.

## Resumo

- **Estado atual, diferente do levantamento:** os commits do KAN-80 (`dd8c2a9`, `ef80124`) e do
  KAN-93 (`0eb6b81`) mudaram a árvore e o JSON. Depois do passo determinístico em memória, sobram
  **214 itens pendentes** (eram 216) e **15 títulos sem destino** (eram 16), que travam **124 itens**.
  `FUNDAMENTOS DE BANCO DE DADOS` e `Conceitos de Banco de Dados` já saem resolvidos pelo passo
  (`auto` → `A-e02df9d2b4`). `PROCESSO` já foi decidido no KAN-80 (`NA-5ea6287326`).
- **Nós novos:** os ~14 conceitos do levantamento viram **35 nós**: 3 assuntos e 32 subassuntos.
  São mais nós que conceitos porque a D5 pede subassuntos pequenos (Gestão de produtos e Inovação no
  sistema financeiro, 19 nós) e porque cada conceito ganha seu próprio nó. Não há disciplina nova
  (43 → 43).
- **Destino dos 214 itens:** 15 títulos, 49 itens para nós novos, 1 Design thinking
  (`S-eb23e19ae9`), 14 pela D3 (nó do conceito em outra disciplina), 8 compostos (2 a 4 nós),
  4 que dependem da dúvida Q1 e 123 em nó existente, conforme o julgamento.
- **Simulação** (`curar_arvore --lote … --simular`): 35 nós criados, disciplinas 43 → 43,
  **0 nós com questão fundidos**, "nada foi gravado". Os detectores de compostos, homônimos e norma
  repetida não acusam nada novo.
- **Efeito medido** (lote mais mapeamentos, seguido do passo, numa cópia em memória): os pendentes
  do BANRISUL vão de **214 para 0**. Só o lote dá 213, porque o passo casa `GESTÃO DE PRODUTOS`
  pelo nome. O lote com os 15 títulos dá 194. Somando os novos, a D3, os compostos e as dúvidas
  (91 comandos), ficam 118, que são os "existentes": esses a M4/M5/M14 (D2) devem resolver sozinhas
  ou, se não, os 123 `--mapear` restantes.
- **12 dúvidas para o dono** (Q1 a Q12, seção 4). As operações do lote que dependem delas estão
  marcadas com `[DÚVIDA Qn]` no comentário.

---

## 1. Destino dos títulos de bloco sem destino

"Destrava" é o `itens_travados` de `novidades_do_edital`, depois do passo. Todo nó de destino é
existente e ativo (conferido por código), com exceção dos dois assuntos novos da D5.

| Título no edital | Destrava | Destino (ID, caminho, nível) |
|---|---|---|
| GESTÃO DE PRODUTOS | 22 | **novo assunto em Tecnologia da Informação**: `NA-e4ab58963f` Gestão de produtos (D5) |
| TÉCNICAS E LINGUAGENS DE PROGRAMAÇÃO | 20 | `NA-870524a5bf` TI › Desenvolvimento de sistemas (assunto) |
| ARQUITETURA | 12 | `NA-870524a5bf` TI › Desenvolvimento de sistemas (assunto) |
| GESTÃO E GOVERNANÇA | 12 | `NA-8a2987f6b8` TI › Governança e gestão de TI (assunto). Os subitens jurídicos vão para Direito Administrativo (D3, seção 3) |
| INOVAÇÃO EM TI NO SISTEMA FINANCEIRO | 10 | **novo assunto em Tecnologia da Informação**: `NA-6e1171de9d` Inovação no sistema financeiro (D5) |
| SISTEMAS OPERACIONAIS | 9 | `NA-e8ea9374ad` TI › Infraestrutura de TI (assunto). O bloco tem "Serviços de diretório", que não é sistema operacional. Por isso aponto para o assunto, não para o subassunto `A-b7f5d728c0` |
| INFRAESTRUTURA DE REDES | 6 | `A-4b13bcdab5` TI › Redes de computadores (assunto) |
| SERVIDORES | 6 | `NA-e8ea9374ad` TI › Infraestrutura de TI (assunto) |
| MODELAGEM DE DADOS | 5 | `A-e02df9d2b4` TI › Banco de dados (assunto) |
| ADMINISTRAÇÃO DE BANCO DE DADOS RELACIONAIS | 5 | `A-e02df9d2b4` TI › Banco de dados (assunto) |
| ARMAZENAMENTO | 5 | `NA-e8ea9374ad` TI › Infraestrutura de TI (assunto) |
| PERFORMANCE E TUNING | 4 | `A-e02df9d2b4` TI › Banco de dados (assunto) |
| CONCEITOS BÁSICOS | 3 | `M-41f37f57d8` Tecnologia da Informação (disciplina existente). Os filhos espalham-se por SO, redes e integração |
| TECNOLOGIAS EMERGENTES | 3 | `NA-07a7c2b773` TI › Ciência de dados e inteligência artificial (assunto). Os filhos são IA, ML e IA generativa. Descartei `A-48f6fa3bf6` "Tecnologias emergentes no setor público", que é homônimo, mas o enfoque é o setor público |
| COMPUTAÇÃO EM NUVEM | 2 | `NA-e8ea9374ad` TI › Infraestrutura de TI (assunto) |
| *(FUNDAMENTOS DE BANCO DE DADOS)* | 0 | já resolvido pelo passo: `A-e02df9d2b4` |
| *(PROCESSO)* | — | já decidido no KAN-80: `NA-5ea6287326` TI › Engenharia de software |

Soma: 124 itens destravados. Com só o lote e os títulos, o passo atual (sem M4/M5/M14) casa mais
2 filhos por nome. O resto depende das regras da D2 ou do `--mapear` (seção 5).

---

## 2. Nós novos a criar (35)

Convenção usada, a dos vizinhos: nome curto em caixa de frase, sigla ou exemplo entre parênteses
só quando desambigua, e norma no padrão `Lei nº N/AAAA (apelido)`, como em `Estatuto da Pessoa
Idosa (Lei nº 10.741/2003)` e `Lei nº 13.445/2017 (Lei de Migração)`. Os IDs são determinísticos
(`_gerar_id(nivel, "pai|nome")`) e foram confirmados pela simulação. A busca foi feita por regex
sem acento sobre todos os nós ativos (`kan95/busca.py`).

### 2.1 Assuntos novos (D5)

| Nó | Nível | Pai | Itens (chave) |
|---|---|---|---|
| `NA-e4ab58963f` **Gestão de produtos** | assunto | `M-41f37f57d8` TI | `gestao de produtos`; `gestao de produtos\|produtos`; `gestao de produtos\|produtos\|processo de desenvolvimento de produtos digitais` |
| `NA-6e1171de9d` **Inovação no sistema financeiro** | assunto | `M-41f37f57d8` TI | `inovacao em ti no sistema financeiro` |
| `NA-9993a2c5d3` **Lei estadual nº 13.694/2011 (Estatuto Estadual da Igualdade Racial do RS)** | assunto | `M-90dd4ae301` Legislação Específica | `legislacao\|estatuto estadual da igualdade racial lei estadual no 13 694 2011` [Q8] |

Busca para as duas primeiras: `produto`, `roadmap|backlog|user stor|mvp`, `inovac`, `fintech`,
`blockchain`, `open finance`, `sistema financeiro`, `transformac.*digital`. Candidatos:
- `A-1a727febee` TI › Engenharia de software › "Processos de software, gestão de projetos e produtos
  de software": subassunto composto, que não comporta subassuntos (ver Q11);
- `A-51c66be0c2` Administração Pública › Inovação na gestão pública: enfoque público;
- `S-b37a322e5a` Direito Constitucional › Sistema Financeiro Nacional: enfoque jurídico.

Todos descartados. Para a norma do RS, a busca por `12\.288|13\.694|racial|igualdade` só achou
`S-0ed8fb8f31` (Ética › Promoção de Igualdade e Diversidade) e `S-0c78ec01ba` (resolução do CFP),
que são outros conceitos.

### 2.2 Subassuntos de Gestão de produtos (`NA-e4ab58963f`)

| Nó | Itens (chave) | Busca e descarte |
|---|---|---|
| `NS-91f271365d` Ciclo de vida do produto | `gestao de produtos\|produtos\|ciclo de vida do produto` | `A-1a727febee` (composto, ver Q11); `S-a36d8a0434` é o ciclo de vida do **projeto** |
| `NS-7207b23a2b` Roadmap de produto | `…\|produtos\|roadmap de produto` | nenhum nó com `roadmap` |
| `NS-9ed794912d` Planejamento de releases | `…\|produtos\|releases` | `release` só casa `S-8d0c65da36` (release de imprensa, Comunicação Social) |
| `NS-94de5d3b25` Métricas de produtos digitais [Q4] | `gestao de projetos\|indicadores lead time … kpi` (+ `A-834a863292` OKR, + `A-b34798e56a` Indicadores de desempenho) | `metrica` só casa métricas de ML e de resultado no setor público (`S-684bc78b7e`); `\bnps\b\|lead time` não tem nó |
| `NS-8646654fd2` Experiência do usuário (UX) | `gestao de produtos\|user experience ux`; `…\|metodologias ageis e experiencia do usuario` (+ `A-441ecdfb0c`); `…\|… conceitos basicos e aplicacoes`; `…\|produtos\|design de produto` | `\bux\b\|experiencia do usuario`, `interface`: nada em TI |
| `NS-1443abd08a` Acessibilidade e usabilidade | `…\|user experience ux\|acessibilidade e usabilidade` | `A-7bb7b5cbc0` Administração Pública › Acessibilidade (sem filhos, semente de "noções de governança pública"): enfoque público, e a D5 lista "acessibilidade e usabilidade" como subassunto real (ver Q3) |
| `NS-ff5734059f` Task flow | `…\|user experience ux\|task flow` | nenhum |
| `NS-d5580e802e` Pesquisa com usuários e interface (UI) | `…\|… research user interface`; `…\|… research user interface lean concept discovery sprint` (+ Design sprint) | `pesquisa` só casa Arquivologia e "sítios de busca" |
| `NS-efd10cc0ac` Prototipação | `…\|… prototipacao` | `prototip`: nada |
| `NS-8204a47f30` Design sprint | `…\|tecnicas de facilitacao e mediacao de atividades co criativas e design sprints`; `…\|… lean concept discovery sprint` | `sprint`, `facilita`: nada |
| `NS-49a5087cf0` Storytelling em UX [Q2] | `…\|… storytelling` | `S-a67331fcbe` "Storytelling para visualização de dados" (Ciência de dados): enfoque de dados |

Na tabela, `…` abrevia `gestao de produtos|user experience ux|metodologias ageis e experiencia do
usuario`. As chaves completas estão em `proposta_kan95_itens.json`.

### 2.3 Subassuntos de Inovação no sistema financeiro (`NA-6e1171de9d`)

| Nó | Itens (chave) | Busca e descarte |
|---|---|---|
| `NS-5574f8fe8f` Transformação digital de serviços financeiros | `inovacao em ti no sistema financeiro\|transformacao digital`; `…\|transformacao digital\|estrategias e praticas para digitalizacao de servicos financeiros` | `digitaliz` só casa Arquivologia; `A-43596837f2` Serviços públicos digitais tem enfoque público |
| `NS-69ea62a7ae` Open finance | `…\|transformacao digital\|open finance` | nenhum |
| `NS-9ac3b019f5` Fintechs e bancos digitais | `…\|novas tecnologias\|blockchain iot fintechs …` (+ `A-067cc93992`, + `A-bfc314b10d`); `…\|tendencias de mercado\|acompanhamento … criptomoedas pagamentos digitais e digital banking` (+ Pagamentos, + Criptomoedas) | `fintech`, `banc.*digita`: nada. O blockchain já vive em `A-067cc93992` (semente "blockchain: conceitos e aplicações"), por isso o composto aponta para lá |
| `NS-df52f4afb3` Pagamentos digitais | item `…criptomoedas pagamentos digitais…` (composto) | `pagamento` só casa AFO e desapropriação |
| `NS-f7a6982126` Criptomoedas | item `…criptomoedas…` (composto) | `cripto` só casa criptografia |
| `NS-d21876b429` Gestão da inovação [Q5] | `…\|gestao da inovacao`; `…\|gestao da inovacao\|metodos para fomentar a inovacao … startups` | `A-51c66be0c2` Inovação na gestão pública (o julgamento a sugeria): enfoque público |

### 2.4 Subassuntos em assuntos existentes

| Nó | Pai | Itens (chave) | Busca e descarte |
|---|---|---|---|
| `NS-ee97a45438` Programação orientada a objetos | `NA-870524a5bf` Desenvolvimento de sistemas | `tecnicas e linguagens de programacao\|programacao orientada a objetos`; `…\|programacao orientada a objetos\|classes heranca composicao interfaces polimorfismo`; `engenharia de software\|implementacao\|orientacao a objetos` | `objeto`, `orientad`: só NoSQL e Direito. `A-3408fede43` Linguagens de programação trata da linguagem, não do paradigma (o encaixe forçado que o plano previa no LLM) |
| `NS-7658f2bc38` Padrões de projeto (design patterns) | `NA-870524a5bf` | `…\|boas praticas de programacao\|design patterns`; `…\|boas praticas de programacao` (+ SOLID) | `padr(ao\|oes) de projeto\|design pattern`: nada. `A-f57e5aa487` Arquitetura de software cobre padrões de **arquitetura** (camadas, SOA), que não são os padrões GoF |
| `NS-5a7ae88c4e` Princípios SOLID [Q9] | `NA-870524a5bf` | `…\|boas praticas de programacao\|solid`; `…\|boas praticas de programacao` (+ Padrões) | `solid` só casa "consolidação" (Contabilidade) |
| `NS-525402b8a4` Estruturas de dados e algoritmos | `NA-870524a5bf` | `engenharia de software\|implementacao\|estrutura de dados e algoritmos` | `S-9748b0df89` (listas e tuplas em Python, básico); `A-5e1328dca4` e `S-08a82eb8fb` (algoritmos de ML e IA) |
| `NS-7a537f09a6` Organização física e índices | `A-e02df9d2b4` Banco de dados | `fundamentos de banco de dados\|organizacao fisica e metodos de acesso`; `performance e tuning\|indices e otimizacao de acesso` (+ Tuning); `banco de dados\|indices e otimizacao de acesso` (+ Tuning) | `indice`, `organizacao fisica\|metodos de acesso`: nada em TI |
| `NS-839d3b0755` Otimização de consultas e tuning | `A-e02df9d2b4` | os dois `…\|indices e otimizacao de acesso`; `performance e tuning\|indices e otimizacao de acesso\|otimizacao de codigo sql ansi …` (+ `S-551a90e864`); `…\|uso de variaveis bind`; `…\|desempenho e deteccao de problemas` | `tuning\|otimiza`: nada. `S-551a90e864` é a linguagem SQL (entra só como segundo nó do item com join e subconsultas) |
| `NS-84742764b0` Controle de concorrência [Q10] | `A-e02df9d2b4` | `fundamentos de banco de dados\|concorrencia recuperacao e integridade` (+ Recuperação); `administracao de banco de dados relacionais\|controle de protecao integridade e concorrencia` (+ `A-2777136b57`) | `concorrencia`: nada. `S-551a90e864` cobre ACID, não bloqueio nem escalonamento. `A-b7f5d728c0` é concorrência em SO |
| `NS-56d6ecb70c` Recuperação após falhas [Q10] | `A-e02df9d2b4` | `fundamentos de banco de dados\|concorrencia recuperacao e integridade` (+ Concorrência) | `recupera`: só "recuperação de dados" (ETL) e Contabilidade. `A-268e85e223` Backup é infraestrutura |
| `NS-f4b3c0cf4b` Serviços de diretório (LDAP e Active Directory) | `NA-e8ea9374ad` Infraestrutura de TI | `sistemas operacionais\|servicos de diretorio`; `…\|active directory e ldap`; `…\|interoperabilidade` | `diretorio`, `ldap\|active directory`, `interoperab`: nada. `A-25c805b189` (gestão de identidades e autenticação) tem enfoque de segurança, e o edital põe o tema em SO e servidores |
| `NS-6add27d99d` Licenciamento de software [Q6] | `NA-8a2987f6b8` Governança e gestão de TI | `gestao e governanca\|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes\|licenciamento de software` | `licenc`, `software livre\|9\.609\|direito autoral`: nada, nem em Direito. A D3 manda para o nó jurídico **se ele existir**, e ele não existe |
| `NS-7b822710b6` Lei nº 13.303/2016 (Lei das Estatais) | `A-424f65c051` Direito Administrativo › Legislação aplicável à contratação de bens e serviços | `gestao e governanca\|…\|lei no 13 303 2016` | `13\.303\|estata`: só "entidades paraestatais". `S-cb05530ea1`/`S-d0252d71a4` (empresas públicas e SEM) tratam da organização administrativa, não do regime de licitações. Fica ao lado de `S-bf1fb476cd` Lei nº 14.133/2021 (D3). `nos_da_mesma_norma` não acusa repetição |
| `NS-4dbc364e45` Política Nacional para as Mulheres [Q7] | `A-ea208d484c` Serviço Social › Políticas Sociais | `legislacao\|politica nacional para as mulheres` | `mulher`: nada |
| `NS-6893f32e2a` Política Nacional de Enfrentamento à Violência contra as Mulheres [Q7] | `A-ea208d484c` | `legislacao\|politica nacional de enfrentamento a violencia contra as mulheres` | `violencia`: assédio no trabalho (Psicologia, Serviço Social), outro conceito |
| `NS-f6dcebd7b0` Estatuto da Igualdade Racial (Lei nº 12.288/2010) [Q7] | `A-ea208d484c` | `legislacao\|estatuto nacional da igualdade racial lei federal no 12 288 2010` | `racial\|igualdade`, `discrimina`: `A-b7ddafa18f` (Ética › Discriminação no serviço público) e `A-9a6d0222c0` (assédio e discriminação no trabalho), outros conceitos |
| `NS-ae746b6bf4` Modelo de negócios (Business Model Canvas) | `A-fdd929e9b9` Administração Geral › Gestão estratégica | `estrategia\|referencial estrategico das organizacoes\|modelo de negocios … business model canvas` | `modelo de negocio\|canvas`: nada. `S-655449dbb0` "Ferramentas de planejamento estratégico" é agregador amplo, e o BMC é cobrado isoladamente |

---

## 3. Itens que vão para nós existentes

### 3.1 Design thinking (D5) e D3 (nó do conceito em outra disciplina)

| Regra | Bloco | Item | Nó |
|---|---|---|---|
| D5 | GESTÃO DE PRODUTOS | Metodologias ágeis e experiência do usuário - Design thinking | `S-eb23e19ae9` Administração Pública › Inovação na gestão pública › Design Thinking |
| D3 | GESTÃO E GOVERNANÇA | Gestão de contratação de soluções de TI | `A-424f65c051` Direito Administrativo › Legislação aplicável à contratação de bens e serviços (busca `contratac.*ti`: não há nó de TI) |
| D3 | GESTÃO E GOVERNANÇA | Legislação aplicável à contratação de bens e serviços de TI e suas alterações | `A-424f65c051` |
| D3 | GESTÃO E GOVERNANÇA | Elaboração e fiscalização de contratos | `S-43918fdbe8` Dir. Adm. › Contratos administrativos › Elaboração e fiscalização de contratos |
| D3 | GESTÃO E GOVERNANÇA | Cláusulas e indicadores de nível de serviço | `S-87dabcd1d9` … › Cláusulas e indicadores de nível de serviço |
| D3 | GESTÃO E GOVERNANÇA | Papel do fiscalizador do contrato | `S-81d5169c67` … › Papel do fiscalizador do contrato |
| D3 | GESTÃO E GOVERNANÇA | Papel do preposto da contratada | `S-b1d7bd5120` … › Papel do preposto da contratada |
| D3 | GESTÃO E GOVERNANÇA | Acompanhamento da execução contratual | `S-0be4918914` … › Acompanhamento da execução contratual |
| D3 | GESTÃO E GOVERNANÇA | Registro e notificação de irregularidades | `S-b56196a0f2` … › Registro e notificação de irregularidades |
| D3 | GESTÃO E GOVERNANÇA | Definição e aplicação de penalidades e sanções administrativas | `S-b02401c9bd` … › Definição e aplicação de penalidades e sanções administrativas |
| D3 | GESTÃO E GOVERNANÇA | Princípios fundamentais da administração pública | `S-20e16b751f` Dir. Adm. › Regime jurídico-administrativo › Princípios expressos e implícitos da Administração Pública |
| D3 | GESTÃO E GOVERNANÇA | Lei nº 13.303/2016 | nó novo `NS-7b822710b6` (seção 2.4) |
| D3 | LEGISLAÇÃO | Lei nº 13.709/2018 (LGPD) | `NS-11c10a8ea6` Dir. Adm. › Acesso à informação e proteção de dados › LGPD |
| D3 | RACIOCÍNIO LÓGICO | Razões e proporções; Divisão proporcional; Regras de três simples e compostas | `A-d4f5c80605` Matemática Financeira › Regra de três simples e composta, proporcionalidades e porcentagens (assunto) |

### 3.2 Itens compostos (N:N, até 4 nós)

| Item (resumo) | Nós |
|---|---|
| Classificação das informações, ambientes físicos e lógicos, controle de acesso; políticas | `A-3fc8e1543c` Gestão de SI; `A-8763b26044` Controle de acesso; `A-bf492b5cfb` Políticas de SI |
| Criptografia simétrica, assimétrica e hash; certificação digital; ICP | `A-805590e68b` Criptografia; `A-4e29084c17` PKI/ICP-Brasil |
| Segurança em redes, ataques, incidentes, firewalls…, malwares | `A-f2edc4437f` Prevenção de ataques; `A-addef0af06` Ameaças em redes; `A-a72164a20c` Incidentes; `S-35ab3a8c71` malware |
| Cloud computing; virtualização | `A-0d5ca71b92` Serviços de nuvem; `A-8dfc6f53da` Virtualização |
| Conteinerização de aplicações e DevSecOps | `A-2d664f1470` Contêineres; `A-7704ba4ec9` DevOps |
| Ferramentas de análise de ambiente: SWOT, cenários, GUT | `S-bcd5e45306` Análise SWOT; `A-7e84a0b377` Análise de cenário |
| Gerenciamento de projetos: áreas de conhecimento, programas, portfólio | `S-66e4a7f6e3` Áreas de conhecimento; `S-0d78a6b816` Programas e portfólio (Adm. Geral › Gestão de Projetos, `A-2c9c7eb394`, D5) |
| Tipos de abordagem: tradicional, híbrida e ágil (Scrum, Lean, Kanban) | `S-2eda8c5abd` Modelos de gestão de projetos; `S-774833cfc8` Metodologia ágil |

Os compostos com ";" serão divididos pela M8 (KAN-94), e então as chaves mudam (Q12).

### 3.3 Os outros 123 itens

Seguem o `no_alvo` do julgamento: 50 equivalentes diretos e o resto por abrangência. Exemplos:
as 10 facetas do BSC vão para `S-7a0d161260`, os subitens de TÉCNICAS E LINGUAGENS para
`A-3408fede43`, os de SO para `A-b7f5d728c0`, MVP e Backlog para `A-6a5ad94fa5` (Q1). A lista
completa, com chave, nó e caminho, está em `proposta_kan95_itens.json` (campo `categoria`).
Conferência por código (`kan95/conferir_ids.py`): este documento e o `.sh` citam 139 IDs. Os 104
existentes, contando os nós descartados na busca, existem e estão `ativo`. Os 35 novos são
exatamente os do lote.

---

## 4. Dúvidas que dependem do dono

| # | Dúvida | Opções | Recomendação |
|---|---|---|---|
| Q1 | MVP, Gerenciamento de backlog, User story e User story map | (a) ficam em `A-6a5ad94fa5` Engenharia de requisitos, onde a semente já pôs "gestão de backlog" e "produto mínimo viável (MVP)"; (b) viram subassuntos de Gestão de produtos e os itens da semente são remapeados | **(a)**: um conceito, um nó, sem mexer nos mapeamentos da semente (P71). Se o dono quiser (b), são 3 `criar` e 2 `remapear` da semente, com K22–K24 antes e depois |
| Q2 | Storytelling (faceta UX) | (a) nó novo `Storytelling em UX`; (b) reaproveitar `S-a67331fcbe` "Storytelling para visualização de dados" (como a D5 fez com Design thinking); (c) cair no nó `Experiência do usuário (UX)` | **(a)**: o enfoque de dados e o de UX dão questões diferentes. (b) é aceitável pela analogia com a D5 |
| Q3 | Onde ficam as facetas de UX | (a) subassuntos de Gestão de produtos, que é onde o edital as põe; (b) um terceiro assunto "Experiência do usuário (UX)" em TI; (c) "Acessibilidade" reaproveita `A-7bb7b5cbc0` (Administração Pública, sem filhos) | **(a)**: a D5 citou só dois assuntos novos. Manter `A-7bb7b5cbc0` à parte (enfoque de governança pública) |
| Q4 | "Indicadores: Lead Time, Delivery Rate, NPS, Métricas de UX, OKR e KPI" (bloco GESTÃO DE PROJETOS) | (a) novo `Métricas de produtos digitais` em Gestão de produtos, mais OKR e Indicadores de desempenho; (b) novo subassunto em Adm. Geral › Gestão de Projetos | **(a)**: NPS e métricas de UX são de produto. OKR (`A-834a863292`) e KPI (`A-b34798e56a`) já existem e entram como nós adicionais |
| Q5 | Gestão da inovação (laboratórios, hackathons, startups) | (a) novo subassunto em Inovação no sistema financeiro; (b) `A-51c66be0c2` Adm. Pública › Inovação na gestão pública (julgamento original) | **(a)**: o enfoque é a instituição financeira. (b) segue a analogia do Design thinking |
| Q6 | Licenciamento de software | (a) TI › Governança e gestão de TI; (b) Direito Administrativo › Contratos | **(a)**: não existe nó jurídico de licença, e o tema é cobrado em TI (tipos de licença) |
| Q7 | Políticas para as mulheres e Estatuto da Igualdade Racial | (a) Serviço Social › Políticas Sociais (precedente D6 da 5B.3: Estatuto da Pessoa Idosa, ECA); (b) Legislação Específica (a D2 diz "só normas do órgão", e estas não são); (c) Ética › Discriminação | **(a)** |
| Q8 | Estatuto Estadual da Igualdade Racial (Lei RS 13.694/2011) | (a) assunto em Legislação Específica (norma local); (b) subassunto em Políticas Sociais, ao lado do federal | **(a)**: norma estadual, específica do órgão (banco do RS), e uma norma por nó |
| Q9 | SOLID e padrões de projeto | (a) dois nós; (b) um nó "Boas práticas, SOLID e padrões de projeto" | **(a)**: a questão testa um ou outro. "Boas práticas de programação" aponta para os dois |
| Q10 | Concorrência e recuperação em SGBD | (a) dois nós; (b) um nó "Controle de concorrência e recuperação" | **(a)**, pelo mesmo motivo |
| Q11 | `A-1a727febee` "Processos de software, gestão de projetos e produtos de software" (subassunto composto, com questões do piloto) sobrepõe o novo Gestão de produtos e Adm. Geral › Gestão de Projetos | (a) não mexer agora e anotar como pendência de nó composto da 5B.3; (b) renomear para "Processos de software" e mover o resto | **(a)**: renomear ou fundir mexe na classificação 5D do piloto (P71/K22) |
| Q12 | Ordem de aplicação com M5/M7/M8 | A M7/M8 (KAN-93/94) vai reprocessar o BANRISUL: as 6 facetas UX "em cadeia" e os tópicos com ";" mudam de chave. A M5 (herança da folha) faz o filho sem mapeamento herdar o nó-folha do pai. Exemplo: as facetas UX herdariam `NS-8646654fd2` se o `--mapear` delas não viesse antes | **Aplicar o lote (nós) já**, antes da 5D. Aplicar os `--mapear` dos itens só depois da M7/M8, em dry-run e conferindo as chaves. Com os nós no lugar, a M14 casa por nome sozinha parte das facetas limpas ("Prototipação", "Task flow", "Acessibilidade e usabilidade") |

---

## 5. Rascunho de lote (NÃO aplicado) e simulação

Arquivos (no scratchpad):
- `/tmp/claude-1000/-home-athos-homelab-scraper-cebraspe/aadcdf4f-8e37-4736-962f-8b137e0bd2c5/scratchpad/proposta_kan95_lote.json`:
  35 operações `criar`, com `apelido` para os dois assuntos novos (os filhos citam
  `@gestao_produtos` e `@inovacao_financeira`). As que dependem de dúvida trazem `[DÚVIDA Qn]` no
  `comentario`.
- `/tmp/claude-1000/-home-athos-homelab-scraper-cebraspe/aadcdf4f-8e37-4736-962f-8b137e0bd2c5/scratchpad/proposta_kan95_mapear.sh`:
  214 comandos `curar_arvore --mapear 'chave:ID[,ID]'`, agrupados por categoria (titulo, novo, dt,
  d3, composto, duvida, existente). **Não executado.**
- `/tmp/claude-1000/-home-athos-homelab-scraper-cebraspe/aadcdf4f-8e37-4736-962f-8b137e0bd2c5/scratchpad/proposta_kan95_itens.json`:
  os 214 itens com chave, categoria, nós e caminhos, mais o mapa apelido → ID.

Simulação (`venv/bin/python -m scripts.curar_arvore --lote <lote> --simular`, rc 0):

```
1: criado NA-e4ab58963f (assunto) 'Gestão de produtos'
2: criado NA-6e1171de9d (assunto) 'Inovação no sistema financeiro'
… (35 linhas, uma por nó; saída completa em kan95/simulacao.txt)
Disciplinas ativas: 43 → 43
Nós com questão que fundem (perdem detalhe): 0
Simulação: nada foi gravado.
```

Depois disso: md5 da árvore igual, `git status canonico/` limpo e log sem linhas novas.

**Limitação do formato:** `aplicar_lote` (`_executar_operacao`) aceita `criar`, `fundir`, `mover`,
`renomear`, `remapear`, `aposentar` e `rebaixar`, mas não aceita `mapear`. `remapear` exige um
mapeamento anterior. Por isso os itens novos precisam de 214 chamadas `--mapear`, e cada uma grava
e regera o `arvore.html`. Isso não é tudo ou nada. Sugestão para a C1: acrescentar o tipo `mapear`
ao lote, com `make docs-gerar` (P70), e aplicar nós e mapeamentos numa operação só.

**Na aplicação real (P71):** rodar K22–K24 antes e depois. O lote só cria nós (sem fusão nem
movimento), então não deve mudar os apontamentos do piloto. Antes de aprovar o `BANRISUL_25`
(P41), rodar também o `auditar_arvore.py`.

Scripts desta proposta, todos só de leitura: `kan95/estado.py`, `pend_atual.py`, `busca.py`,
`dump.py`, `montar.py`, `auditar.py`, `medir_parcial.py` e `tabelas.py`.
