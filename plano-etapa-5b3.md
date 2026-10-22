# Plano da Etapa 5B.3: Auditoria da hierarquia da árvore (disciplina → assunto → subassunto)

> Pedido do dono em 2026-10-22: "existem disciplinas que não deveriam ser disciplinas, essa é
> nossa maior pendência hoje". Exemplos dados: Controle Externo não é disciplina; DevOps é
> subassunto de TI; proteção ambiental, licenciamento ambiental e incêndios são subassuntos;
> as outras matérias de tecnologia da informação vão para TI.
>
> Este arquivo é o **levantamento** (só leitura, nada foi alterado na árvore nem no banco). A
> decisão de cada linha é do dono (A30, P51). A aplicação usa `scripts/curar_arvore.py`, nunca
> `UPDATE` no banco (A27).

## Como o levantamento foi feito

- Fonte: `canonico/arvore.json` via `src/arvore.carregar()`, só nós `ativo` (74 matérias, 1.016
  assuntos, 2.255 subassuntos), mais `questao_no` do `scraper-cebraspe-db` (apontamentos não
  rejeitados, resolvidos pelo `fundido_em`) e os mapeamentos aprovados de item de edital.
- Nas tabelas, **q** = questões distintas na subárvore do nó e **A/S** = assuntos/subassuntos
  ativos abaixo dele.
- A origem do problema: a matéria da árvore nasceu do **título de bloco do edital** (5B/5B.1).
  O IBAMA divide o conhecimento específico em 12 blocos, o TRF/CNJ em "Arquitetura da PDPJ-Br",
  o STM em "Legislação" etc. Cada título virou disciplina. Falta uma **lista fechada de
  disciplinas canônicas** (estilo Gran) e uma regra para o título de edital que não está nela.

## Fase 1 — Disciplinas (matérias que deixam de ser disciplina)

Proposta: de 74 para **43 disciplinas**. 34 matérias saem; 3 são criadas (Meio Ambiente, Direito
Ambiental, Segurança Institucional); `LEGISLAÇÃO` é renomeada para Legislação Específica.

### 1.1 Tecnologia da informação → `TECNOLOGIA DA INFORMAÇÃO` (M-41f37f57d8)

| Matéria hoje | id | q | A/S | Vira, dentro de TI |
|---|---|---|---|---|
| DEVOPS | M-8208b586db | 3 | 3/0 | subassunto **DevOps** (pedido do dono); os 3 assuntos fundem nele. Kubernetes, Rancher, Git e Deploy da PDPJ vêm junto |
| DESENVOLVIMENTO DE SISTEMAS | M-d1e5eecf98 | 13 | 11/45 | assunto **Desenvolvimento de sistemas**; "Bancos de dados" vai para Banco de dados, "Testes de software" para Engenharia de software |
| ENGENHARIA DE SOFTWARE | M-bcbbff2a4e | 8 | 3/7 | assunto **Engenharia de software** |
| BANCO DE DADOS E CIÊNCIA DE DADOS | M-7781ab0e4a | 11 | 6/11 | dividir: SGBD e modelagem → assunto **Banco de dados**; o resto → **Ciência de dados e IA** |
| CIÊNCIA DE DADOS E INTELIGÊNCIA ARTIFICIAL | M-5915f10b0b | 8 | 10/4 | assunto **Ciência de dados e IA** (junta com "Ciência de Dados", "Inteligência Artificial", "Big Data", "Visualização de dados" que já estão em TI) |
| GOVERNANÇA E GESTÃO DE TIC | M-66eaf29c30 | 22 | 5/13 | assunto **Governança e gestão de TI** (recebe ITIL v4 e ISO/IEC 20000 da infraestrutura) |
| INFRAESTRUTURA DE TIC | M-511092b0f7 | 12 | 26/51 | dividir: redes → assunto **Redes de computadores** (já existe, A-4b13bcdab5); virtualização, nuvem, servidores, backup e storage → assunto **Infraestrutura** |
| SEGURANÇA DA INFORMAÇÃO | M-902042b57b | 20 | 24/44 | assunto **Segurança da informação** (já existe em TI, A-8bc51b3a2f) |
| INFORMÁTICA | M-7f77004bff | 17 | 5/10 | os 5 assuntos já têm homônimo em TI (Office, organização de arquivos, Redes, Segurança, Windows): **fundir assunto com assunto**, sem perda |
| ARQUITETURA DE DESENVOLVIMENTO DA PDPJ-Br | M-9c049f21d8 | 24 | 10/31 | distribuir os 10 assuntos: Kubernetes/Rancher/Git/Deploy → DevOps; microsserviços/mensageria → Desenvolvimento; Banco de dados/Persistência → Banco de dados; autenticação → Segurança |

### 1.2 Meio ambiente (IBAMA) → disciplinas novas **Meio Ambiente** e **Direito Ambiental**

| Matéria hoje | id | q | A/S | Vira |
|---|---|---|---|---|
| BIODIVERSIDADE E FLORESTAS | M-101f78b6a6 | 9 | 38/4 | Meio Ambiente › assunto **Biodiversidade e florestas** (os assuntos jurídicos — "Responsabilidade por dano", "Tutela processual", "Fiscalização e poder de polícia" — vão para Direito Ambiental) |
| MANEJO, CONSERVAÇÃO E REABILITAÇÃO DA FAUNA SILVESTRE | M-d5c7c5aa73 | 70 | 13/19 | Meio Ambiente › assunto **Fauna silvestre** |
| PROTEÇÃO DA FAUNA | M-e108dff811 | 7 | 1/4 | Meio Ambiente › assunto **Proteção ambiental** › subassunto **Proteção da fauna** (já duplica A-91cce72b3a do Manejo) |
| PROTEÇÃO DE RECURSOS GENÉTICOS | M-8a07dde87a | 6 | 1/7 | › Proteção ambiental › subassunto **Recursos genéticos** |
| PROTEÇÃO DE RECURSOS PESQUEIROS | M-4173e90b1d | 6 | 1/5 | › Proteção ambiental › subassunto **Recursos pesqueiros** |
| INCÊNDIOS FLORESTAIS | M-fb47b107ac | 6 | 6/0 | Meio Ambiente › assunto **Incêndios florestais** (ou subassunto de Biodiversidade e florestas, como o dono citou); "Lei nº 14.944/2024" vai para Direito Ambiental |
| EMERGÊNCIAS CLIMÁTICAS E AMBIENTAIS | M-7338c4af73 | 5 | 5/7 | Meio Ambiente › assunto **Mudanças climáticas e emergências ambientais** |
| MONITORAMENTO AMBIENTAL | M-bd114fcd2d | 8 | 5/9 | Meio Ambiente › assunto **Monitoramento ambiental e geoprocessamento** (recebe "Geoprocessamento" e "Monitoramento ambiental" da Biodiversidade) |
| QUALIDADE AMBIENTAL | M-1b403fbbda | 6 | 9/45 | Meio Ambiente › assunto **Qualidade ambiental**; as resoluções CONAMA vão para Direito Ambiental |
| LICENCIAMENTO AMBIENTAL FEDERAL | M-bd593f39c8 | 6 | 6/30 | Direito Ambiental › assunto **Licenciamento ambiental** (pedido do dono); os assuntos socioeconômicos (Demografia, Sociologia, Cartografia) ficam como subassuntos dele |
| LEGISLAÇÃO AMBIENTAL | M-9f80b62f5e | 16 | 9/32 | Direito Ambiental: cada lei vira assunto (6.938, 9.605 + Decreto 6.514, LC 140, 12.651, 7.735) |
| PROCESSO SANCIONADOR AMBIENTAL | M-c85488b734 | 5 | 8/0 | Direito Ambiental › assunto **Processo sancionador ambiental**; as leis repetidas (LC 140, 7.735, 9.605, 6.514, 9.784) fundem no nó único da norma |

### 1.3 Controle, contratos, orçamento e tributos → disciplinas que já existem

| Matéria hoje | id | q | A/S | Vira |
|---|---|---|---|---|
| CONTROLE EXTERNO | M-fb0015bfb3 | 15 | 7/1 | DIREITO ADMINISTRATIVO › assunto **Controle da administração pública** (A-3b6e7bebd4); os 7 assuntos viram subassuntos. Também entram ali "Conceito e finalidade do controle" e "Controle interno e controle externo" da Auditoria Governamental. Obs.: no Gran, "Controle Externo" é disciplina dos concursos de TCU; aqui segue a decisão do dono |
| LICITAÇÕES E CONTRATOS | M-6aec103f43 | 20 | 5/18 | DIREITO ADMINISTRATIVO: "Lei 14.133" → **Licitação** (A-2261b82645); contratos → **Contratos administrativos** (A-91e52e6c2e), mesma divisão da 5B.2 |
| EXECUÇÃO ORÇAMENTÁRIA E FINANCEIRA | M-d4c1e1a200 | 14 | 4/6 | AFO: "Programação, execução e controle…" e "Retenção e recolhimento…" já existem lá (A-9ced69392e, A-709c7502bc); "MCASP 11ª" → Contabilidade Pública |
| LEGISLAÇÃO TRIBUTÁRIA APLICADA ÀS CONTRATAÇÕES PÚBLICAS | M-0037626047 | 12 | 4/12 | CONTABILIDADE TRIBUTÁRIA: os mesmos 3 assuntos já existem lá (Legislação básica, Retenções na fonte, Tributos) e os subassuntos repetem (IN RFB 1.234, LC 116, COFINS, CSLL, INSS, ISS) |
| LOGÍSTICA E PATRIMÔNIO | M-16ee66fc6f | 5 | 1/7 | GESTÃO DE CONTRATOS E RECURSOS MATERIAIS, renomeada **Administração de Recursos Materiais**; os assuntos de contrato dela ("Elaboração e fiscalização de contratos", "Licitações e contratos administrativos", "Decreto 11.462", "Legislação aplicável") vão para Direito Administrativo |

### 1.4 Legislação → cada norma na disciplina natural; o resto em **Legislação Específica**

`LEGISLAÇÃO` (M-90dd4ae301) é renomeada para **Legislação Específica** e recebe só as normas do
órgão (regimentos, resoluções do CNJ, portarias). Lei com casa natural sai dela (regra do
KAN-66: norma consolidada num lugar só).

| Matéria hoje | id | q | A/S | Destino de cada assunto |
|---|---|---|---|---|
| LEGISLAÇÃO | M-90dd4ae301 | 71 | 9/0 | 8.112 → Dir. Adm. › Agentes públicos; 9.784 → Dir. Adm. › Processo Administrativo Federal (AL-fe35b41dc5); 8.457/1992 → Dir. Proc. Penal Militar; RI STM, RI TCU, 11.416 e Res. CNJ 351/400/401 ficam |
| LEGISLAÇÃO RELACIONADA | M-7d86b9b968 | 15 | 11/0 | abuso de autoridade, 7.716, 9.099, 10.826 → Direito Penal › Crimes da legislação especial (A-0990a61102); Estatuto da Pessoa Idosa → decidir (hoje está em 4 disciplinas); cerimonial e Res. CNJ 344/383/435/467 → Legislação Específica |
| LEGISLAÇÃO ESPECIAL | M-32d286f4d6 | 5 | 2/0 | 12.016 (mandado de segurança) → Dir. Constitucional (remédios) ou Proc. Civil; 11.418 (repercussão geral) → Proc. Civil |
| LEGISLAÇÃO APLICADA À POLÍCIA FEDERAL | M-7b1ac274e0 | 21 | 5/4 | 10.826 e 10.357 → Direito Penal › legislação especial; 12.830, 13.445 e 14.967 → Legislação Específica |
| NORMATIVOS DA PDPJ-BR | M-7501f95a27 | 18 | 7/10 | Legislação Específica › assunto **Normativos do CNJ** (junto com as outras resoluções CNJ) |

### 1.5 Outras matérias que são título de edital

| Matéria hoje | id | q | A/S | Vira |
|---|---|---|---|---|
| REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM DO CONGRESSO NACIONAL E CÓDIGO DE ÉTICA | M-e96f4dbbb5 | 14 | 3/8 | Processo Legislativo (criada na 5B.2): os 3 assuntos (RICD, RCCN, Código de Ética) entram como assuntos, sem perda |
| SEGURANÇA DE DIGNITÁRIOS | M-2b484e23d1 | 18 | 17/22 | nova **Segurança Institucional** › assunto Segurança de dignitários |
| SEGURANÇA ORGÂNICA | M-4b496a8352 | 18 | 12/14 | Segurança Institucional › assunto Segurança orgânica ("Análise de riscos" e "Planejamento de contingências" repetem entre as duas) |

### 1.6 Ficam como disciplina (com ajuste de nome)

Administração Geral; Administração Pública; **Administração Financeira e Orçamentária** (hoje
"Administração Orçamentária e Financeira"); Arquivologia; Atualidades; Auditoria Governamental;
Ciência Política; Comunicação Social; Comércio Exterior; Contabilidade Geral e Societária;
**Contabilidade Pública** (hoje "Contabilidade Aplicada ao Setor Público"); Contabilidade
Tributária; os 8 Direitos; Enfermagem; Estatística; Farmácia; Gestão de Pessoas; Língua Inglesa;
Língua Portuguesa; Matemática Financeira; Nutrição; Pedagogia; Processo Legislativo; Psicologia;
Raciocínio Lógico; Serviço Social; Tecnologia da Informação; Ética no Serviço Público; Clínica
Médica, Ortopedia e Psiquiatria (ver D4). Padronizar a caixa dos nomes (hoje metade está em
maiúsculas, metade não).

### Decisões do dono (Fase 1)

- **D0 — como rebaixar.** A árvore tem 3 níveis fixos. Rebaixar uma matéria para assunto
  transforma os assuntos dela em subassuntos, e os subassuntos dela precisam **fundir no pai**
  (perda de detalhe). Alternativa sem perda: fundir matéria com matéria (já existe hoje), e os
  assuntos dela ficam soltos dentro da disciplina destino, sem o agrupamento. Perda medida se
  rebaixar: Seg. da Informação 44 subassuntos (11 com questão), Infraestrutura 51 (10),
  Desenvolvimento 45 (11), PDPJ 31 (14), Licenciamento 30 (2), Qualidade Ambiental 45 (3),
  Legislação Ambiental 32 (12), Fauna silvestre 19 (17). **Recomendação:** rebaixar (é o que o
  dono pediu) e, onde o subassunto tem questão e conteúdo próprio, fundir num subassunto
  irmão em vez de no pai.
- **D1 — ambiental:** duas disciplinas (Meio Ambiente + Direito Ambiental, recomendado, porque
  Direito Constitucional e Biodiversidade já têm assunto jurídico ambiental) ou uma só (Meio
  Ambiente).
- **D2 — Legislação Específica:** manter uma disciplina para normas do órgão (recomendado; é
  disciplina comum no Gran) ou espalhar tudo nas disciplinas jurídicas.
- **D3 — Regimento da Câmara:** dentro de Processo Legislativo (recomendado) ou disciplina
  própria "Regimento Interno".
- **D4 — Medicina:** manter Clínica Médica, Ortopedia e Psiquiatria como disciplinas
  (recomendado: cada uma tem 70 questões e mais de 100 subassuntos, rebaixar apaga detalhe) ou
  criar "Medicina" com elas como assuntos.
- **D5 — Segurança Institucional:** juntar Dignitários + Orgânica (recomendado) ou manter as duas.
- **D6 — Estatuto da Pessoa Idosa** (Leg. Relacionada, Serviço Social, Direito Civil, Direito
  Penal): um nó só, em qual disciplina.

## Fase 2 — Assuntos fora do lugar

Assuntos que ficam depois da Fase 1, mas estão na disciplina errada ou repetem um nó de outra.

### 2.1 Assunto na disciplina errada

| Assunto | id | Hoje em | q | Vai para |
|---|---|---|---|---|
| Conceitos básicos de Python | A-7e8ffad663 | Estatística | 6 | TI › Desenvolvimento |
| Conceitos básicos de SQL | A-35db77563d | Estatística | 5 | TI › Banco de dados |
| Estatística e probabilidade básicas | A-b09e8402bb | TI | 9 | Estatística |
| estatística: média, moda, mediana e desvio padrão | A-ca68c34731 | Raciocínio Lógico | 3 | Estatística › Estatística descritiva (A-6fe50ec934) |
| Certificação digital (ICP-Brasil, assinatura, criptografia) | A-d8c9b18de0 | Arquivologia | 3 | TI › Segurança (já há A-4e29084c17, ICP-Brasil) |
| Segurança da informação | A-2356bc9bf9 | Segurança Orgânica | 1 | TI › Segurança, ou fica (decidir: no contexto é sigilo de informação institucional) |
| Licitações e contratos | A-2ad18c5e46 | Contabilidade Geral | 0 | Dir. Adm. › Licitação |
| licitação, pregão e registro de preços | A-15f28c0ed0 | AFO | 0 | Dir. Adm. › Licitação |
| Conceito e instrumentos de execução financeira | A-9a585c0013 | Dir. Constitucional | 0 | AFO |
| Constituição Federal de 1988, art. 70 a 74 | A-2247a0ee91 | Contabilidade Pública | 0 | Dir. Constitucional › Fiscalização Contábil, Financeira e Orçamentária (A-807d3737d2) |
| Dos crimes contra as finanças públicas | A-07f0442a79 | AFO | 0 | Direito Penal (decidir) |
| Convenção americana sobre direitos humanos | A-6492133c08 | Direito Penal | 0 | Dir. Constitucional › Direitos e garantias (não há Direitos Humanos) |
| Lei nº 8.112/1990 | A-b756f76410 | Ética no Serviço Público | 7 | Dir. Adm. › Agentes públicos (8.112 está em 3 lugares) |
| Despesas com Pessoal / Tópicos selecionados da LC 101 | A-e3710b2743, A-98c597bbfc | Contabilidade Pública | 0 | AFO › LRF (AL-02b4bc3a67) |
| Proteção da Fauna | A-91cce72b3a | Manejo da fauna | 8 | funde com o nó de Proteção da fauna (1.2) |

### 2.2 O mesmo assunto em duas disciplinas (escolher um nó)

- **AFO × Contabilidade Pública:** Créditos adicionais (A-6046b68747 × A-1d5569887f), Conta
  única do Tesouro (A-99661a58c5 × A-d8dc49fd7b), Despesa pública (AL-baa42ce1dc ×
  A-56cb844488), Receita pública (AL-49fc7bbd0b × A-8d3ef86100), Restos a pagar (A-7e93595e9c ×
  A-c4940b4cdd), Lei 4.320 (AL-528d504ae8 × AL-d92ca18389), Manual de Demonstrativos Fiscais
  (A-f4cc228836 × A-8e9ed56866). **Recomendação:** o enfoque orçamentário fica na AFO; em
  Contabilidade Pública fica só o enfoque patrimonial ("Receita e despesa sob o enfoque
  patrimonial", "Variações patrimoniais").
- **Contabilidade Tributária × Contabilidade Pública:** "Tratamento contábil aplicável aos
  impostos e contribuições" (A-79802a31bc × AL-eaef011f6c).
- **Gestão de Pessoas × Psicologia:** Qualidade de vida no trabalho (A-564f15a1ae ×
  A-024bdafe23), Recrutamento e seleção (A-252bd3d3fe em Psicologia, subassuntos em GP),
  Gerenciamento de conflitos, Gestão por competências. Decidir se Psicologia mantém um assunto
  "Psicologia organizacional e do trabalho" com esses subassuntos (recomendado: o cargo é de
  psicólogo e o recorte por prova importa) ou se tudo vai para Gestão de Pessoas.
- **Pedagogia × Gestão de Pessoas:** Educação corporativa (A-a5fe133e1c × S-ff6da2f639),
  Treinamento e desenvolvimento.
- **Assédio** em 4 disciplinas: Psicologia (2 assuntos, A-e2c3b292d2 e A-a975086630), Serviço
  Social (A-9a6d0222c0), Ética (A-431d196f4d), Legislação (Res. CNJ 351/2020, A-dc49021eb1).

### 2.3 Assunto repetido dentro da mesma disciplina

- Contabilidade Geral: Ativo Intangível × Ativos intangíveis; Empréstimos e financiamentos (2
  variações); Mensuração do valor justo (2); Receita de vendas × Receitas de vendas de produtos e
  serviços; Tributos sobre a renda × Tributos sobre o Lucro; Consolidação × Demonstrações
  Consolidadas; Estrutura Conceitual × NBC TG Estrutura Conceitual; "Contabilidade Geral e
  Societária" (homônimo da disciplina).
- Direito Administrativo: Poderes da administração × Poderes e deveres; Processo administrativo
  × Processo Administrativo Federal; Direito administrativo × Introdução ao direito
  administrativo; Contratos administrativos × Contrato administrativo para compras.
- Direito Constitucional: "Constituição", "CRFB de 1988" e "CRFB de 1988 e emendas" (3 nós
  genéricos); Princípios fundamentais × "Princípios Fundamentais. Direitos e garantias";
  Organização do Estado × Organização político-administrativa do Estado.
- Língua Portuguesa: Redação Oficial × Redação oficial: Manual da Presidência.
- TI: Aplicativos Office 365 × Edição de textos × "sistema operacional (Windows 10 e 11) e
  MSOffice" × sistema operacional (Windows).
- Psicologia: Ética profissional × Ética profissional do psicólogo; os 2 de assédio.
- Assunto homônimo da disciplina (sinal de que o edital não detalhou): Comércio Exterior,
  Qualidade Ambiental, Gestão de Pessoas (37 questões num assunto genérico), Ciência Política.

## Fase 3 — Subassuntos (levantamento inicial)

A Fase 3 completa roda **depois** das decisões das Fases 1 e 2, porque o rebaixamento cria
subassuntos novos (os assuntos das matérias rebaixadas) e funde outros. O que já aparece hoje:

- **Norma em mais de uma disciplina** (subassunto ou assunto): Lei 14.133 em 6 lugares
  (inclusive Contabilidade Geral, S-17bddd6e82, e Governança de TIC, S-f778630a9e); Lei 4.320
  em 7; 8.112 em 3; 9.784 em 3; 13.869 (abuso de autoridade) em 3; 10.826 em 4; 5.197 (fauna) em
  3; 14.785 (agrotóxicos) em 2; Decreto 70.235 em Legislação Ambiental e AFO; IN RFB 1.234 e LC
  116 em Contabilidade Tributária e Legislação Tributária; Decretos 11.462 e 11.531 em Gestão de
  Contratos e Dir. Adm.
- **Subassunto que é assunto em outra disciplina:** "Processo legislativo" em Dir.
  Constitucional (S-cf159107c7) × a disciplina Processo Legislativo; LDO e LOA em Processo
  Legislativo (S-6c5a3e9c3f, S-24b3b29511) × assuntos da AFO; "Incêndios florestais" em
  Emergências Climáticas (S-b971e4020f); "Monitoramento Ambiental" em Licenciamento
  (S-65336f2f6d); "Big data" em BD e Ciência de Dados (S-c9eb4ae688) × A-e93da13346 de TI;
  Balanço patrimonial e DMPL em Contabilidade Geral × assuntos de Contabilidade Pública.
- **Repetição esperada, não é erro:** "Conceito", "Disposições gerais", "Princípios", "Ação
  penal", "Penas", "Medidas de segurança" em Penal × Penal Militar, ADI/ADC/ADPF em
  Constitucional × Processo Civil. O nome é igual, mas o conteúdo depende da disciplina.

Script do levantamento (reproduzível, só leitura): ver "Sessão 1" abaixo.

## Sessões (uma por conversa)

1. **Sessão 1 — Disciplinas.** Dono decide D0–D6 e cada linha da Fase 1. Implementar a
   operação de rebaixar em `src/arvore.py` (hoje `mover_no` recusa matéria e `fundir_nos`
   recusa matéria entre níveis): permitir fundir matéria sem filhos ativos num nó de outro nível
   e um comando `--rebaixar MATERIA:DESTINO` em `scripts/curar_arvore.py` que faz, em uma
   operação tudo ou nada, subassuntos → pai, assuntos → subassuntos novos sob o destino, matéria
   → destino. Criar as disciplinas novas. Script de auditoria versionado
   (`scripts/auditar_arvore.py`, registrar em `src/registro/scripts.py`, P70) que gera esta
   tabela e falha se aparecer matéria fora da lista fechada.
2. **Sessão 2 — Assuntos.** Dono decide a Fase 2; aplicar fusões e movimentos como propostas
   (`P-…`) aprovadas em lote.
3. **Sessão 3 — Subassuntos.** Rodar o levantamento de novo na árvore nova e fazer a Fase 3.
4. **Sessão 4 — Banco, site e regra de ingestão.** Recarga, views e site; lista fechada de
   disciplinas canônicas (`canonico/`), e título de bloco de edital fora da lista passa a mapear
   para assunto (o `materia_no` aceita qualquer nó; conferir `vw_edital_cobra_materia` e o
   filtro "Disciplina" do site). Vale para os concursos novos da 8.C.

## Riscos

- **P71/K22:** o piloto tem invariante de 3.029 apontamentos. Fundir dois nós que a mesma
  questão aponta pode reduzir essa contagem. As chaves da 5D não mudam (o
  `classificacao_questoes.json` resolve pelo `fundido_em`). Se a contagem mudar, o dono precisa
  aprovar a nova linha de base do K22 antes de aplicar.
- Fusão é reversível só por novo `--renomear`/`--mover`: o nó fundido fica no JSON, mas o
  agrupamento antigo se perde. Fazer o backup de `canonico/arvore.json` antes de cada sessão.
- O site mostra a disciplina pelo nó matéria: depois da Fase 1, rodar o Chromium headless no
  filtro de disciplina e nas páginas de estatística.

## Pronto quando

- Nenhuma matéria ativa fora da lista fechada aprovada pelo dono; `scripts/auditar_arvore.py`
  verde.
- Nenhuma norma consolidada em dois nós (8.112, 9.784, 4.320, LC 101, 14.133, LC 140, 7.735,
  9.605/6.514, 10.826, 5.197).
- Piloto: 2.800 itens e 129 anuladas inalterados; apontamentos e hash do K22 conferidos (ou
  nova linha de base aprovada); `make test-all` verde; site conferido no Chromium headless.
