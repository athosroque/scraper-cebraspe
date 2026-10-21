# Site público

Interface web pública do acervo de questões de concursos do CEBRASPE, focada em resolução de questões, simulados e estatísticas de incidência.

**Para que serve:** Apresentar a arquitetura, funcionalidades, rotas e componentes da interface web pública. **Quando ler:** Antes de alterar telas, adicionar funcionalidades interativas ou consultar a estrutura do frontend.

## Visão Geral e Stack Tecnológica

O frontend do site público foi concebido para entregar resolução de questões, simulados cronometrados e painéis analíticos com foco em SEO, renderização no servidor (SSR) e simplicidade operacional, adotando FastAPI, Jinja2, HTMX e Alpine.js. A estilização visual foi inicialmente estruturada em Pico.css na etapa inicial e evoluiu na Etapa 5H para Tailwind CSS compilado, com paleta customizada no tom `destaque` (teal) e tipografia Public Sans.
Fonte: site/app/templates/base.html:1-42

As trocas parciais de interface (aplicação de filtros sem recarga total da tela, submissão de respostas Certo/Errado e paginação de itens) são operadas via HTMX, enquanto o Alpine.js gerencia exclusivamente o estado dinâmico local no navegador, como a abertura de dropdowns de filtros, cronômetro de prova e manipulação de stores em memória.
Fonte: docs/adr/ADR-033-site-publico-stack-e-deploy.md:36-45

A compilação de ativos CSS dispensa servidores Node.js permanentes em produção, utilizando o binário standalone do Tailwind CSS configurado para emitir o arquivo final estático em `/static/tailwind.css`, com proibição de classes azuis genéricas em favor do token de cor teal.
Fonte: docs/adr/ADR-035-card-e-filtros-formato-gran.md:20-25

## Arquitetura em Três Camadas e Estrutura de Páginas

O backend e o frontend seguem rigorosamente a separação em três camadas para desacoplar regras de negócio de adaptadores de apresentação: `repositorio/` executa consultas SQL diretamente sobre as views analíticas e o schema de aplicação; `servicos/` concentra regras de domínio, filtros, cálculos estatísticos e validações Pydantic; e `api/` juntamente com `web/` atuam como adaptadores finos que consomem os serviços.
Fonte: docs/adr/ADR-033-site-publico-stack-e-deploy.md:46-60

A rota inicial `/` renderiza o catálogo de disciplinas ativas da árvore mestre com contagens de questões associadas e percentuais médios de incidência histórica, servindo como porta de entrada para a navegação hierárquica por assuntos.
Fonte: site/app/web/rotas_web.py:147-185

A rota `/questoes` gerencia a listagem geral com paginação, filtros por múltiplos critérios e substituição parcial do fragmento `#lista-questoes` via HTMX, complementada pelo endpoint `/questoes/facetas` que recomputa as contagens de opções pendentes sem interferir na listagem de cards. O total de questões e concursos cobertos pelo acervo é reportado em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: site/app/web/rotas_web.py:228-340

A visualização unitária de itens é servida em rotas canônicas no formato `/q/{concurso}/{caderno}/{numero}`, enquanto o endpoint `/q/{codigo}` intercepta buscas pelo ID curto de 8 caracteres hexadecimais e devolve redirecionamento permanente (HTTP 301) para a URL canônica correspondente.
Fonte: site/app/web/rotas_web.py:545-605

Os textos-base e figuras de cada questão são carregados sob demanda via HTMX na rota `/q/{concurso}/{caderno}/{numero}/anexos`, evitando tráfego de dados volumosos durante a paginação primária da lista de questões.
Fonte: site/app/web/rotas_web.py:558-570

A seção analítica é segmentada nas rotas `/estatisticas` (ranking das matérias e assuntos mais cobrados em prova), `/estatisticas/edital` (tópicos mais frequentes em editais) e `/estatisticas/edital-vs-prova` (cruzamento de itens previstos versus cobrados por cargo), todas espelhadas por endpoints JSON na API.
Fonte: site/app/web/rotas_web.py:665-725

O módulo de simulados opera em `/simulado` para configuração e seleção de cadernos por concurso e cargo, `/simulado/prova` para renderização da prova em ordem original, `/simulado/{id}` para exibição de placares pós-conclusão e `/simulado/{id}/revisar` para revisão individual de erros e itens em branco.
Fonte: site/app/web/rotas_web.py:771-850

A rota `/conta` concentra a área do usuário autenticado ("Meu desempenho"), apresentando o painel de KPIs pessoais, caderno de erros pendentes, plano de estudos com base no concurso-alvo e ranking de prioridades de estudo.
Fonte: site/app/web/rotas_web.py:1031-1064

A página `/materias/{no_id}` oferece um painel focado em uma única disciplina, destacando os subassuntos com maior índice de cobrança e facilitando o início imediato de sessões de estudo segmentadas.
Fonte: site/app/web/rotas_web.py:1076-1110

## Autenticação, Sessão e Dados de Usuário

O acesso ao acervo e a resolução interativa de questões na web são abertos e completamente anônimos, sendo a autenticação exigida apenas para persistência do histórico individual de respostas, criação de simulados oficiais e acompanhamento de métricas de evolução na conta.
Fonte: docs/adr/ADR-033-site-publico-stack-e-deploy.md:66-75

A autenticação opera com provedor Google OAuth via biblioteca Authlib, dispensando armazenamento de credenciais de login ou envio de e-mails transacionais e preservando unicamente identificador `sub`, e-mail e nome fornecidos pelo Google.
Fonte: site/app/auth.py:8-25

A sessão do usuário é trafegada em cookie assinado nomeado `sessao` configurado com `HttpOnly`, `SameSite=Lax` e validade de 30 dias, guardando internamente apenas o id do usuário, seu primeiro nome e o segredo CSRF gerado.
Fonte: site/app/main.py:134-142

Toda operação de mutação HTTP (`POST` e `DELETE`) exige verificação obrigatória de token CSRF fornecido via header `X-CSRFToken` em requisições HTMX e chamadas de API, ou pelo campo oculto `csrf_token` em formulários convencionais.
Fonte: site/app/auth.py:54-72

A persistência dos dados de navegação e histórico do usuário é isolada no schema `app` do PostgreSQL, composto pelas tabelas `app.usuario`, `app.resposta` e `app.simulado`, com indexação voltada à recuperação cronológica decrescente das respostas mais recentes.
Fonte: site/sql/app_schema.sql:7-57

A segurança de banco segue o princípio de menor privilégio mediante a segregação de duas roles distintas: `site_leitura`, restrita a consultas em views de conteúdo e execução de funções estatísticas no schema `public`, e `site_app`, autorizada para operações de leitura e escrita unicamente nas tabelas do schema `app`.
Fonte: site/sql/app_schema.sql:61-96

Em conformidade com a LGPD, a funcionalidade de exclusão de conta em `/conta/apagar` (e endpoint `DELETE /api/v1/eu`) executa a remoção completa do registro do usuário e de todo o seu histórico de respostas e simulados em cascata.
Fonte: site/app/web/rotas_web.py:1065-1074

## Simulado e Correção no Padrão CEBRASPE

O simulado monta a prova integral de determinado concurso e cargo na ordem fidedigna do caderno oficial, agrupando primeiro as questões de conhecimentos básicos seguidas pelos conhecimentos específicos, omitindo gabaritos e padrões de resposta durante a resolução.
Fonte: site/app/servicos/simulados_servico.py:36-54

A apuração de pontuação segue a fórmula clássica do CEBRASPE para provas no formato Certo/Errado, atribuindo +1 ponto por item correto, subtraindo −1 ponto por item incorreto e conferindo 0 pontos para respostas deixadas em branco. Em questões de múltipla escolha eventuais, o acerto confere +1 ponto e o erro 0 pontos.
Fonte: site/app/servicos/simulados_servico.py:64-100

Questões formalmente anuladas pela banca examinadora são neutralizadas na pontuação do simulado, não concedendo pontos e sendo subtraídas tanto da pontuação final quanto da nota máxima possível da prova.
Fonte: site/app/servicos/simulados_servico.py:87-99

Quando realizado com autenticação ativa, o simulado registra o início na tabela `app.simulado` para aferição do tempo total e é encerrado de forma atômica no banco com a gravação das respostas não nulas e não anuladas, impedindo submissões duplicadas concorrentes.
Fonte: site/app/servicos/simulados_servico.py:156-184

A nota e a situação dos itens de simulados finalizados são recalculadas dinamicamente com base no gabarito corrente das questões a cada consulta de resultado, garantindo atualização automática caso ocorra alteração posterior ou retificação de gabarito pela banca.
Fonte: site/app/servicos/simulados_servico.py:201-218

Itens com pendências técnicas de extração catalogados como não utilizáveis são omitidos da prova do simulado, sendo sua quantidade e numeração devidamente informadas ao usuário no aviso de itens omitidos.
Fonte: site/app/servicos/simulados_servico.py:36-48

## Filtros de Questões e Formato Gran (Fidelidade ao Caderno)

O design dos cards de questões adota o padrão estrutural do Gran Questões com adaptação para o design system do projeto, organizando a informação em faixas limpas com identificador estável, trilha de navegação hierárquica e botões Certo/Errado estilizados.
Fonte: docs/adr/ADR-035-card-e-filtros-formato-gran.md:25-33

Cada questão exibe um código curto estável no padrão `Q` acompanhado de 8 dígitos hexadecimais, gerado a partir do hash SHA-1 de sua chave composta (`<concurso>|<caderno>|<numero>`), contornando a volatilidade do identificador numérico interno gerado em recargas de banco.
Fonte: site/app/servicos/formatacao.py:65-67

A barra superior do card consolida a posição sequencial do item na listagem, o botão com o código curto e a trilha de disciplina e assunto, exibindo apenas o ramo diferencial caso existam apontamentos secundários na questão.
Fonte: site/app/templates/_card_questao.html:6-25

A linha de metadados resume Ano, Banca, Órgão e Prova/Cargo com hiperlinks clicáveis que aplicam o respectivo filtro na listagem geral, além de destacar selos de anulação ou indicadores de alta incidência na prova (top 3 da disciplina).
Fonte: site/app/templates/_card_questao.html:27-47

Para máxima fidelidade ao caderno de prova original, o texto-base preserva os parágrafos originais reconstruídos pela análise de recuo horizontal da primeira linha em relação à margem das colunas, enquanto tabelas e diagramas vetoriais são renderizados como recortes gráficos em PNG.
Fonte: docs/adr/ADR-034-fidelidade-ao-caderno-e-filtros.md:45-85

O comando do grupo de questões ("Julgue os itens...") é apresentado em destaque itálico com borda lateral colorida acima do enunciado, recolhendo-se automaticamente em acordeão expansível quando idêntico ao comando do item imediatamente anterior no mesmo caderno.
Fonte: site/app/templates/_card_questao.html:64-73

O painel de filtros superiores organiza as opções em modo simples e avançado, operando com estado reativo gerenciado pelo Alpine.js e disparando requisições de recontagem de facetas via HTMX apenas ao fechar os menus dropdown, consolidando a aplicação dos filtros somente no clique explícito do botão "Filtrar".
Fonte: site/app/templates/lista_questoes.html:43-105

A seleção de filtros de taxonomia opera em cascata estrita (Disciplina → Assunto → Subassunto), onde a marcação de assuntos é restrita às disciplinas selecionadas e, na composição da consulta de banco, a regra de refino considera unicamente o nó mais específico de cada ramo taxonômico.
Fonte: site/app/servicos/questoes_servico.py:272-344

## Referências e Regras Relacionadas

- Regra de cálculo de incidência por prova: [P63 - Estatística de Prova com fn_prova_cobra](../tecnico/regras.md#p63)
- Regra de segurança de credenciais em roles: [A44 - Senhas de Role fora do SQL](../tecnico/regras.md#a44)
- Regra de preservação de GRANTs entre cargas: [A57 - Sobrevivência de GRANTs](../tecnico/regras.md#a57)
- Decisão sobre stack, auth e deploy: [ADR-033 - Site Público de Questões](../adr/ADR-033-site-publico-stack-e-deploy.md)
- Decisão sobre fidelidade ao caderno e filtros: [ADR-034 - Fidelidade ao Caderno e Filtros](../adr/ADR-034-fidelidade-ao-caderno-e-filtros.md)
- Decisão sobre card e filtros formato Gran: [ADR-035 - Card e Filtros Formato Gran](../adr/ADR-035-card-e-filtros-formato-gran.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
