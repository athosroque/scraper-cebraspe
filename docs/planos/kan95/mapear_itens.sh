#!/usr/bin/env bash
# RASCUNHO NÃO EXECUTADO (KAN-95). Rodar só depois de aplicar proposta_kan95_lote.json
# e da decisão do dono sobre as dúvidas Q1-Q12. As chaves são as de 2026-11-02; a M7/M8
# (KAN-93/94) muda as chaves dos itens em cadeia e com ';' (refazer esses depois).
set -euo pipefail
cd /home/athos/homelab/scraper_cebraspe

# --- titulo ---
venv/bin/python -m scripts.curar_arvore --mapear 'conceitos basicos:M-41f37f57d8'  # CONCEITOS BÁSICOS
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao:NA-870524a5bf'  # TÉCNICAS E LINGUAGENS DE PROGRAMAÇÃO
venv/bin/python -m scripts.curar_arvore --mapear 'modelagem de dados:A-e02df9d2b4'  # MODELAGEM DE DADOS
venv/bin/python -m scripts.curar_arvore --mapear 'administracao de banco de dados relacionais:A-e02df9d2b4'  # ADMINISTRAÇÃO DE BANCO DE DADOS RELACIONAIS
venv/bin/python -m scripts.curar_arvore --mapear 'performance e tuning:A-e02df9d2b4'  # PERFORMANCE E TUNING
venv/bin/python -m scripts.curar_arvore --mapear arquitetura:NA-870524a5bf  # ARQUITETURA
venv/bin/python -m scripts.curar_arvore --mapear 'tecnologias emergentes:NA-07a7c2b773'  # TECNOLOGIAS EMERGENTES
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes:A-4b13bcdab5'  # INFRAESTRUTURA DE REDES
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais:NA-e8ea9374ad'  # SISTEMAS OPERACIONAIS
venv/bin/python -m scripts.curar_arvore --mapear servidores:NA-e8ea9374ad  # SERVIDORES
venv/bin/python -m scripts.curar_arvore --mapear armazenamento:NA-e8ea9374ad  # ARMAZENAMENTO
venv/bin/python -m scripts.curar_arvore --mapear 'computacao em nuvem:NA-e8ea9374ad'  # COMPUTAÇÃO EM NUVEM
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos:NA-e4ab58963f'  # GESTÃO DE PRODUTOS
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca:NA-8a2987f6b8'  # GESTÃO E GOVERNANÇA
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro:NA-6e1171de9d'  # INOVAÇÃO EM TI NO SISTEMA FINANCEIRO

# --- novo ---
venv/bin/python -m scripts.curar_arvore --mapear 'legislacao|politica nacional para as mulheres:NS-4dbc364e45'  # Política Nacional para as Mulheres
venv/bin/python -m scripts.curar_arvore --mapear 'legislacao|politica nacional de enfrentamento a violencia contra as mulheres:NS-6893f32e2a'  # Política Nacional de Enfrentamento à Violência contra as Mul
venv/bin/python -m scripts.curar_arvore --mapear 'legislacao|estatuto nacional da igualdade racial lei federal no 12 288 2010:NS-f6dcebd7b0'  # Estatuto Nacional da Igualdade Racial — Lei Federal nº 12.28
venv/bin/python -m scripts.curar_arvore --mapear 'legislacao|estatuto estadual da igualdade racial lei estadual no 13 694 2011:NA-9993a2c5d3'  # Estatuto Estadual da Igualdade Racial — Lei Estadual nº 13.6
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|organizacao fisica e metodos de acesso:NS-7a537f09a6'  # Organização física e métodos de acesso
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|concorrencia recuperacao e integridade:NS-84742764b0,NS-56d6ecb70c'  # Concorrência, recuperação e integridade
venv/bin/python -m scripts.curar_arvore --mapear 'administracao de banco de dados relacionais|controle de protecao integridade e concorrencia:A-2777136b57,NS-84742764b0'  # Controle de proteção, integridade e concorrência
venv/bin/python -m scripts.curar_arvore --mapear 'performance e tuning|indices e otimizacao de acesso:NS-7a537f09a6,NS-839d3b0755'  # Índices e otimização de acesso
venv/bin/python -m scripts.curar_arvore --mapear 'performance e tuning|indices e otimizacao de acesso|otimizacao de codigo sql ansi tuning uso do join union exists e subconsultas:NS-839d3b0755,S-551a90e864'  # Otimização de código SQL ANSI: tuning, uso do join, union, e
venv/bin/python -m scripts.curar_arvore --mapear 'performance e tuning|indices e otimizacao de acesso|uso de variaveis bind:NS-839d3b0755'  # Uso de variáveis Bind
venv/bin/python -m scripts.curar_arvore --mapear 'performance e tuning|indices e otimizacao de acesso|desempenho e deteccao de problemas:NS-839d3b0755'  # Desempenho e detecção de problemas
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|indices e otimizacao de acesso:NS-7a537f09a6,NS-839d3b0755'  # Índices e otimização de acesso
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|programacao orientada a objetos:NS-ee97a45438'  # Programação orientada à objetos
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|programacao orientada a objetos|classes heranca composicao interfaces polimorfismo:NS-ee97a45438'  # Classes, Herança, Composição, Interfaces, Polimorfismo
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|boas praticas de programacao:NS-5a7ae88c4e,NS-7658f2bc38'  # Boas práticas de programação
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|boas praticas de programacao|solid:NS-5a7ae88c4e'  # SOLID
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|boas praticas de programacao|design patterns:NS-7658f2bc38'  # Design Patterns
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|implementacao|orientacao a objetos:NS-ee97a45438'  # orientação a objetos
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|implementacao|estrutura de dados e algoritmos:NS-525402b8a4'  # estrutura de dados e algoritmos
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|servicos de diretorio:NS-f4b3c0cf4b'  # Serviços de diretório
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|servicos de diretorio|active directory e ldap:NS-f4b3c0cf4b'  # Active Directory e LDAP
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|servicos de diretorio|interoperabilidade:NS-f4b3c0cf4b'  # Interoperabilidade
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|referencial estrategico das organizacoes|modelo de negocios e quadro de modelo de negocios business model canvas:NS-ae746b6bf4'  # Modelo de negócios e quadro de modelo de negócios (Business 
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de projetos|indicadores lead time delivery rate net promoter score nps metricas de ux para produtos digitais objectives and key results okr e key performance indicator kpi:NS-94de5d3b25,A-834a863292,A-b34798e56a'  # Indicadores: Lead Time, Delivery Rate, Net Promoter Score (N
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos:NA-e4ab58963f'  # Produtos
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|ciclo de vida do produto:NS-91f271365d'  # Ciclo de vida do produto
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|roadmap de produto:NS-7207b23a2b'  # Roadmap de Produto
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|releases:NS-9ed794912d'  # Releases
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|design de produto:NS-8646654fd2'  # Design de Produto
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|processo de desenvolvimento de produtos digitais:NA-e4ab58963f'  # Processo de Desenvolvimento de Produtos digitais
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux:NS-8646654fd2'  # User Experience (UX)
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|acessibilidade e usabilidade:NS-1443abd08a'  # acessibilidade e usabilidade
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|task flow:NS-ff5734059f'  # Task Flow
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario:NS-8646654fd2,A-441ecdfb0c'  # Metodologias ágeis e experiência do usuário
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario conceitos basicos e aplicacoes:NS-8646654fd2'  # Metodologias ágeis e experiência do usuário - Conceitos bási
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario storytelling:NS-49a5087cf0'  # Metodologias ágeis e experiência do usuário - Storytelling
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario research user interface:NS-d5580e802e'  # Metodologias ágeis e experiência do usuário - Research, user
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario research user interface lean concept discovery sprint:NS-8204a47f30,NS-d5580e802e'  # Metodologias ágeis e experiência do usuário - Research, user
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario prototipacao:NS-efd10cc0ac'  # Metodologias ágeis e experiência do usuário - Prototipação
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|tecnicas de facilitacao e mediacao de atividades co criativas e design sprints:NS-8204a47f30'  # Técnicas de facilitação e mediação de atividades co-criativa
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|lei no 13 303 2016:NS-7b822710b6'  # Lei nº 13.303/2016
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|licenciamento de software:NS-6add27d99d'  # Licenciamento de software
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|novas tecnologias|blockchain iot fintechs inteligencia artificial e machine learning aplicados ao setor financeiro:NS-9ac3b019f5,A-067cc93992,A-bfc314b10d'  # Blockchain, IoT, fintechs, inteligência artificial, e machin
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|transformacao digital:NS-5574f8fe8f'  # Transformação Digital
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|transformacao digital|estrategias e praticas para digitalizacao de servicos financeiros:NS-5574f8fe8f'  # Estratégias e práticas para digitalização de serviços financ
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|transformacao digital|open finance:NS-69ea62a7ae'  # Open finance
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|gestao da inovacao:NS-d21876b429'  # Gestão da Inovação
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|gestao da inovacao|metodos para fomentar a inovacao dentro das instituicoes financeiras incluindo laboratorios de inovacao hackathons e parcerias com startups:NS-d21876b429'  # Métodos para fomentar a inovação dentro das instituições fin
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|tendencias de mercado|acompanhamento e identificacao de novas tecnologias e oportunidades de negocio no setor financeiro como criptomoedas pagamentos digitais e digital banking:NS-9ac3b019f5,NS-df52f4afb3,NS-f7a6982126'  # Acompanhamento e identificação de novas tecnologias e oportu

# --- dt ---
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|user experience ux|metodologias ageis e experiencia do usuario design thinking:S-eb23e19ae9'  # Metodologias ágeis e experiência do usuário - Design thinkin

# --- d3 ---
venv/bin/python -m scripts.curar_arvore --mapear 'raciocinio logico|razoes e proporcoes:A-d4f5c80605'  # Razões e proporções
venv/bin/python -m scripts.curar_arvore --mapear 'raciocinio logico|razoes e proporcoes|divisao proporcional:A-d4f5c80605'  # Divisão proporcional
venv/bin/python -m scripts.curar_arvore --mapear 'raciocinio logico|razoes e proporcoes|regras de tres simples e compostas:A-d4f5c80605'  # Regras de três simples e compostas
venv/bin/python -m scripts.curar_arvore --mapear 'legislacao|lei no 13 709 2018 lei geral de protecao de dados pessoais:NS-11c10a8ea6'  # Lei nº 13.709/2018 (Lei Geral de Proteção de Dados Pessoais)
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|gestao de contratacao de solucoes de ti:A-424f65c051'  # Gestão de contratação de soluções de TI
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes:A-424f65c051'  # Legislação aplicável à contratação de bens e serviços de TI 
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|elaboracao e fiscalizacao de contratos:S-43918fdbe8'  # Elaboração e fiscalização de contratos
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|clausulas e indicadores de nivel de servico:S-87dabcd1d9'  # Cláusulas e indicadores de nível de serviço
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|papel do fiscalizador do contrato:S-81d5169c67'  # Papel do fiscalizador do contrato
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|papel do preposto da contratada:S-b1d7bd5120'  # Papel do preposto da contratada
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|acompanhamento da execucao contratual:S-0be4918914'  # Acompanhamento da execução contratual
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|registro e notificacao de irregularidades:S-b56196a0f2'  # Registro e notificação de irregularidades
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|legislacao aplicavel a contratacao de bens e servicos de ti e suas alteracoes|definicao e aplicacao de penalidades e sancoes administrativas:S-b02401c9bd'  # Definição e aplicação de penalidades e sanções administrativ
venv/bin/python -m scripts.curar_arvore --mapear 'gestao e governanca|principios fundamentais da administracao publica:S-20e16b751f'  # Princípios fundamentais da administração pública

# --- composto ---
venv/bin/python -m scripts.curar_arvore --mapear 'seguranca da informacao|aspectos da classificacao das informacoes seguranca de ambientes fisicos e logicos controles de acesso gestao de politicas de seguranca:A-3fc8e1543c,A-8763b26044,A-bf492b5cfb'  # Aspectos da classificação das informações, segurança de ambi
venv/bin/python -m scripts.curar_arvore --mapear 'seguranca da informacao|algoritmos de criptografia simetrica assimetrica e hash certificacao digital infraestrutura de chaves publicas:A-805590e68b,A-4e29084c17'  # Algoritmos de Criptografia Simétrica, Assimétrica e Hash; Ce
venv/bin/python -m scripts.curar_arvore --mapear 'seguranca da informacao|seguranca em redes de computadores e tecnicas de ataque cibernetico resposta a incidentes resiliencia cibernetica firewalls ids ips proxies nat e vpn spoofing flood ddos phishing malwares adware spyware backdoors keylogger worms ransonware:A-f2edc4437f,A-addef0af06,A-a72164a20c,S-35ab3a8c71'  # Segurança em redes de computadores e técnicas de ataque cibe
venv/bin/python -m scripts.curar_arvore --mapear 'computacao em nuvem|cloud computing virtualizacao:A-0d5ca71b92,A-8dfc6f53da'  # Cloud computing; virtualização.
venv/bin/python -m scripts.curar_arvore --mapear 'computacao em nuvem|conteinerizacao de aplicacoes e devsecops:A-2d664f1470,A-7704ba4ec9'  # Conteinerização de aplicações e DeVSecOps.
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|referencial estrategico das organizacoes|ferramentas de analise de ambiente analise swot analise de cenarios matriz gut:S-bcd5e45306,A-7e84a0b377'  # Ferramentas de análise de ambiente: análise SWOT, análise de
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de projetos|projetos|gerenciamento de projetos conceitos basicos areas de conhecimento projetos programas portfolio:S-66e4a7f6e3,S-0d78a6b816'  # Gerenciamento de projetos: conceitos básicos; áreas de conhe
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de projetos|tipos de abordagem tradicional hibrida e agil framework scrum metodologia lean e metodo kanban:S-2eda8c5abd,S-774833cfc8'  # Tipos de Abordagem: tradicional, hibrida e ágil (Framework S

# --- duvida ---
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|user story map usm:A-6a5ad94fa5'  # User Story Map (USM)
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|user story us:A-6a5ad94fa5'  # User Story (US)
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|minimum viable product mvp:A-6a5ad94fa5'  # Minimum Viable Product (MVP)
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|gerenciamento de backlog:A-6a5ad94fa5'  # Gerenciamento de Backlog

# --- existente ---
venv/bin/python -m scripts.curar_arvore --mapear 'lingua portuguesa|redacao oficial conforme manual de redacao da presidencia da republica:AL-d25ac0285d'  # Redação oficial, conforme Manual de Redação da Presidência d
venv/bin/python -m scripts.curar_arvore --mapear 'lingua inglesa|itens gramaticais relevantes para o entendimento dos sentidos dos textos:AL-f7d4935fd3'  # Itens gramaticais relevantes para o entendimento dos sentido
venv/bin/python -m scripts.curar_arvore --mapear 'raciocinio logico|compreensao de estruturas logicas:A-05d3a2c440'  # Compreensão de estruturas lógicas
venv/bin/python -m scripts.curar_arvore --mapear 'raciocinio logico|logica de argumentacao analogias inferencias deducoes e conclusoes:A-acff47b763'  # Lógica de argumentação: analogias, inferências, deduções e c
venv/bin/python -m scripts.curar_arvore --mapear 'conceitos basicos|concorrencia esquemas de sincronizacao deadlocks:A-b7f5d728c0'  # Concorrência (esquemas de sincronização, deadlocks)
venv/bin/python -m scripts.curar_arvore --mapear 'conceitos basicos|redes locais:A-5cc2d6e82a'  # Redes Locais
venv/bin/python -m scripts.curar_arvore --mapear 'conceitos basicos|web services apis rest:A-0d5791ace5'  # Web Services, APIs REST
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|programacao estruturada:A-3408fede43'  # Programação estruturada
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|componentizacao:A-f57e5aa487'  # Componentização
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|sub rotinas:A-3408fede43'  # Sub-rotinas
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|sub rotinas|passagem de parametros por endereco:A-3408fede43'  # passagem de parâmetros por endereço
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|sub rotinas|passagem de parametros por referencia:A-3408fede43'  # passagem de parâmetros por referência
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|sub rotinas|passagem de parametros por valor:A-3408fede43'  # passagem de parâmetros por valor
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|escopo de variaveis:A-3408fede43'  # Escopo de Variáveis
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|tipos de dados:A-3408fede43'  # Tipos de dados
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|tipos de dados|vinculacao:A-3408fede43'  # vinculação
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|tipos de dados|verificacao de tipos:A-3408fede43'  # verificação de tipos
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|tipos de dados|tipificacao forte:A-3408fede43'  # tipificação forte
venv/bin/python -m scripts.curar_arvore --mapear 'modelagem de dados|fundamentos de administracao de dados:S-abaaaebdfc'  # Fundamentos de administração de dados
venv/bin/python -m scripts.curar_arvore --mapear 'modelagem de dados|fundamentos de administracao de dados|seguranca controle de acesso aos dados:A-8763b26044'  # Segurança/Controle de acesso aos dados
venv/bin/python -m scripts.curar_arvore --mapear 'modelagem de dados|modelagem de dados:A-48c7cb56b8'  # Modelagem de dados
venv/bin/python -m scripts.curar_arvore --mapear 'modelagem de dados|modelagem de dados|modelo entidade relacionamento entidades atributos chaves e relacionamentos:A-48c7cb56b8'  # Modelo entidade-relacionamento (entidades, atributos, chaves
venv/bin/python -m scripts.curar_arvore --mapear 'modelagem de dados|modelagem de dados|normalizacao:A-48c7cb56b8'  # Normalização
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|sistemas de gerencia de banco de dados sgbd:A-2777136b57'  # Sistemas de gerência de banco de dados (SGBD)
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|arquitetura:S-abaaaebdfc'  # Arquitetura
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|modelos logicos e representacao fisica:A-48c7cb56b8'  # Modelos lógicos e representação física
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|conceito de transacao:S-551a90e864'  # Conceito de transação
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|linguagens de definicao ddl e manipulacao de dados dml em sgbds relacionais:S-551a90e864'  # Linguagens de definição (DDL) e manipulação de dados (DML) e
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|procedimentos stored procedures:S-551a90e864'  # Procedimentos (stored procedures)
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|visoes views:S-551a90e864'  # Visões (views)
venv/bin/python -m scripts.curar_arvore --mapear 'fundamentos de banco de dados|gatilhos triggers:S-551a90e864'  # Gatilhos (triggers)
venv/bin/python -m scripts.curar_arvore --mapear 'administracao de banco de dados relacionais|projeto e implantacao de sgbds relacionais:A-2777136b57'  # Projeto e implantação de SGBDs relacionais
venv/bin/python -m scripts.curar_arvore --mapear 'administracao de banco de dados relacionais|administracao de usuarios e perfis de acesso:A-2777136b57'  # Administração de usuários e perfis de acesso
venv/bin/python -m scripts.curar_arvore --mapear 'administracao de banco de dados relacionais|backup e restauracao de dados:A-268e85e223'  # Backup e restauração de dados
venv/bin/python -m scripts.curar_arvore --mapear 'administracao de banco de dados relacionais|tolerancia a falhas e continuidade de operacao:A-d831972bed'  # Tolerância a falhas e continuidade de operação
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|banco de dados oracle 19c mysql v8 e ms sql server 2019:S-fed7e2d779'  # Banco de Dados: Oracle 19c, MySQL v8 e MS SQL Server 2019
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|banco de dados oracle 19c mysql v8 e ms sql server 2019|instalacao configuracao e administracao:A-2777136b57'  # Instalação, configuração e administração
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|banco de dados oracle 19c mysql v8 e ms sql server 2019|replicacao de banco de dados:A-2777136b57'  # Replicação de banco de dados
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|banco de dados oracle 19c mysql v8 e ms sql server 2019|suporte ao uso dos bancos de dados para os desenvolvedores:A-2777136b57'  # Suporte ao uso dos bancos de dados para os desenvolvedores
venv/bin/python -m scripts.curar_arvore --mapear 'processo|ciclos de vida:A-1a727febee'  # Ciclos de vida
venv/bin/python -m scripts.curar_arvore --mapear 'processo|ciclos de vida|modelo cascata:A-1a727febee'  # Modelo cascata
venv/bin/python -m scripts.curar_arvore --mapear 'processo|ciclos de vida|modelo agil:A-441ecdfb0c'  # Modelo ágil
venv/bin/python -m scripts.curar_arvore --mapear 'processo|metodologias ageis de desenvolvimento:A-441ecdfb0c'  # Metodologias ágeis de desenvolvimento
venv/bin/python -m scripts.curar_arvore --mapear 'processo|metodologias ageis de desenvolvimento|scrum tdd modelagem agil e kanban:A-441ecdfb0c'  # Scrum, TDD, Modelagem Ágil e Kanban
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|arquitetura de banco de dados relacional:S-abaaaebdfc'  # Arquitetura de banco de dados relacional
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|modelagem de dados fisico logico e conceitual:A-48c7cb56b8'  # Modelagem de dados: físico, lógico e conceitual
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|modelagem de dados fisico logico e conceitual|fisico:A-48c7cb56b8'  # físico
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|modelagem de dados fisico logico e conceitual|logico:A-48c7cb56b8'  # lógico
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|modelagem de dados fisico logico e conceitual|conceitual:A-48c7cb56b8'  # conceitual
venv/bin/python -m scripts.curar_arvore --mapear 'banco de dados|sql ansi:S-551a90e864'  # SQL/ANSI
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|linguagens:A-3408fede43'  # Linguagens
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|linguagens|java javascript c:A-3408fede43'  # Java, JavaScript, C#
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|linguagens|html5 css3:A-75c9ae985d'  # HTML5, CSS3
venv/bin/python -m scripts.curar_arvore --mapear 'tecnicas e linguagens de programacao|processamento assincrono e mensageria:A-0d5791ace5'  # Processamento assíncrono e mensageria
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|analise e projeto:A-1a727febee'  # Análise e projeto
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|implementacao:NA-5ea6287326'  # Implementação
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|qualidade:S-afc6a31091'  # Qualidade
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|qualidade|analise de codigo:S-afc6a31091'  # Análise de código
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|qualidade|teste unitario:S-afc6a31091'  # Teste unitário
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|qualidade|teste de integracao:S-afc6a31091'  # Teste de integração
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|qualidade|teste de carga estresse:S-afc6a31091'  # Teste de carga, estresse
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|devsecops:A-7704ba4ec9'  # DevSecOps
venv/bin/python -m scripts.curar_arvore --mapear 'engenharia de software|seguranca da informacao|confiabilidade integridade e disponibilidade:A-e82b500a76'  # Confiabilidade, integridade e disponibilidade
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|tecnologias de integracao:A-0d5791ace5'  # Tecnologias de integração
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|tecnologias de integracao|web services e apis:A-0d5791ace5'  # Web services e APIs
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|tecnologias de integracao|restful:A-0d5791ace5'  # RESTful
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|tecnologias de integracao|mensageria:A-0d5791ace5'  # Mensageria
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura:A-f57e5aa487'  # Padrões de arquitetura
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura|arquitetura em camadas:A-f57e5aa487'  # Arquitetura em Camadas
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura|arquitetura cliente servidor:A-f57e5aa487'  # Arquitetura Cliente-servidor
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura|arquitetura orientada a servicos:A-f57e5aa487'  # Arquitetura orientada a serviços
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura|arquitetura de microsservicos:A-505e7be779'  # Arquitetura de microsserviços
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura|arquitetura orientada a eventos:A-f57e5aa487'  # Arquitetura orientada a eventos
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|padroes de arquitetura|front end back end e full stack:A-75c9ae985d'  # Front end, Back end e Full stack
venv/bin/python -m scripts.curar_arvore --mapear 'arquitetura|transacoes distribuidas:A-505e7be779'  # Transações distribuídas
venv/bin/python -m scripts.curar_arvore --mapear 'tecnologias emergentes|inteligencia artificial fundamentos e aplicacoes:S-fe253f32ca'  # Inteligência artificial: Fundamentos e aplicações
venv/bin/python -m scripts.curar_arvore --mapear 'tecnologias emergentes|aprendizado de maquina:A-bfc314b10d'  # Aprendizado de máquina
venv/bin/python -m scripts.curar_arvore --mapear 'tecnologias emergentes|ia generativa:A-048ceace24'  # IA generativa
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes|redes de computadores:A-4b13bcdab5'  # Redes de computadores
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes|gerenciamento de redes tcp ip:A-a67f9900ba'  # Gerenciamento de redes TCP/IP
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes|gerenciamento de redes tcp ip|arquitetura de gerenciamento smi snmp e mib:A-a67f9900ba'  # Arquitetura de gerenciamento, SMI, SNMP e MIB
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes|redes locais e de longa distancia:A-5cc2d6e82a'  # Redes Locais e de longa distância
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes|redes locais e de longa distancia|mpls redes cabeadas redes sem fio padroes 802 11 protocolos 802 1x eap wep wpa e wpa2:A-7060542510'  # MPLS. Redes cabeadas, Redes sem fio: padrões 802.11, protoco
venv/bin/python -m scripts.curar_arvore --mapear 'infraestrutura de redes|redes locais e de longa distancia|conceitos basicos de routing e switching:A-4391a841ed'  # Conceitos básicos de routing e switching
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|sistemas operacionais:A-b7f5d728c0'  # Sistemas operacionais
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|sistemas operacionais|fundamentos:A-b7f5d728c0'  # fundamentos
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|sistemas operacionais|gestao de processos:A-b7f5d728c0'  # gestão de processos
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|sistemas operacionais|gestao de memoria:A-b7f5d728c0'  # gestão de memória
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|sistemas operacionais|gestao de entrada e saida:A-b7f5d728c0'  # gestão de entrada e saída
venv/bin/python -m scripts.curar_arvore --mapear 'sistemas operacionais|sistemas operacionais|instalacao configuracao e administracao de sistemas operacionais windows server 2019 ou superior e redhat enterprise linux versoes 8 ou superior:A-b7f5d728c0'  # instalação, configuração e administração de sistemas operaci
venv/bin/python -m scripts.curar_arvore --mapear 'servidores|servidores de aplicacao:A-32f00392f2'  # Servidores de aplicação
venv/bin/python -m scripts.curar_arvore --mapear 'servidores|servidores de aplicacao|conceitos basicos:A-32f00392f2'  # Conceitos básicos
venv/bin/python -m scripts.curar_arvore --mapear 'servidores|servidores de aplicacao|nocoes de administracao:A-32f00392f2'  # Noções de administração
venv/bin/python -m scripts.curar_arvore --mapear 'servidores|servidores de aplicacao|topologia tipica de ambientes com alta disponibilidade e escalabilidade:A-d831972bed'  # Topologia típica de ambientes com alta disponibilidade e esc
venv/bin/python -m scripts.curar_arvore --mapear 'servidores|servidores de aplicacao|balanceamento de carga fail over e replicacao de estado:A-d831972bed'  # Balanceamento de carga, fail-over e replicação de estado
venv/bin/python -m scripts.curar_arvore --mapear 'servidores|servidores de aplicacao|tecnicas para deteccao de problemas e otimizacao de desempenho:A-32f00392f2'  # Técnicas para detecção de problemas e otimização de desempen
venv/bin/python -m scripts.curar_arvore --mapear 'armazenamento|armazenamento:A-27cb1a6971'  # Armazenamento
venv/bin/python -m scripts.curar_arvore --mapear 'armazenamento|armazenamento|servicos de armazenamento padroes de disco e de interfaces:A-27cb1a6971'  # Serviços de armazenamento, padrões de disco e de interfaces
venv/bin/python -m scripts.curar_arvore --mapear 'armazenamento|armazenamento|raid:A-27cb1a6971'  # RAID
venv/bin/python -m scripts.curar_arvore --mapear 'armazenamento|armazenamento|tecnologias de armazenamento nas e san:A-27cb1a6971'  # Tecnologias de armazenamento NAS e SAN
venv/bin/python -m scripts.curar_arvore --mapear 'armazenamento|armazenamento|tecnologias de backup:A-268e85e223'  # Tecnologias de backup
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|principais conceitos:S-7a0d161260'  # principais conceitos
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|aplicacoes:S-7a0d161260'  # aplicações
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|mapa estrategico:S-7a0d161260'  # mapa estratégico
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|perspectivas:S-7a0d161260'  # perspectivas
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|temas estrategicos:S-7a0d161260'  # temas estratégicos
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|objetivos estrategicos:S-7a0d161260'  # objetivos estratégicos
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|relacoes de causa e efeito:S-7a0d161260'  # relações de causa e efeito
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|indicadores:S-7a0d161260'  # indicadores
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|metas:S-7a0d161260'  # metas
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|balanced scorecard bsc|iniciativas estrategicas:S-7a0d161260'  # iniciativas estratégicas
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|referencial estrategico das organizacoes:S-aedc8bb2b0'  # Referencial Estratégico das Organizações
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|referencial estrategico das organizacoes|analise de ambiente interno e externo:A-7e84a0b377'  # Análise de ambiente interno e externo
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|referencial estrategico das organizacoes|negocio missao visao de futuro valores:S-4fbb5eef47'  # Negócio, missão, visão de futuro, valores
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|indicadores de desempenho:A-b34798e56a'  # Indicadores de desempenho
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|indicadores de desempenho|tipos de indicadores:S-def3f14b7c'  # Tipos de indicadores
venv/bin/python -m scripts.curar_arvore --mapear 'estrategia|indicadores de desempenho|variaveis componentes dos indicadores:S-1af6ddeb5c'  # Variáveis componentes dos indicadores
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de projetos|projetos:S-4edb6e0be3'  # Projetos
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de projetos|projetos|ciclo de vida do projeto:S-a36d8a0434'  # Ciclo de vida do projeto
venv/bin/python -m scripts.curar_arvore --mapear 'gestao de produtos|produtos|tecnicas de levantamento de requisitos:A-6a5ad94fa5'  # Técnicas de levantamento de requisitos
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|novas tecnologias:A-067cc93992'  # Novas Tecnologias
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|transformacao digital|integracao de apis:A-0d5791ace5'  # Integração de APIs
venv/bin/python -m scripts.curar_arvore --mapear 'inovacao em ti no sistema financeiro|tendencias de mercado:A-067cc93992'  # Tendências de Mercado
