# API do site

Rotas HTTP e serviços da aplicação FastAPI que alimentam o site público e fornecem endpoints de consulta, autenticação e resolução.

**Para que serve:** Documentar a especificação, padrões de resposta, rotas e autenticação da API. **Quando ler:** Antes de integrar novos endpoints, modificar contratos de rota ou inspecionar a API FastAPI.

## Visão Geral e Contrato OpenAPI

A API REST do projeto é implementada em FastAPI e formalmente documentada na especificação OpenAPI 3.1.0 disponível em `site/openapi.json` e interativamente em `/docs` (Swagger UI) e `/redoc`. Ela atua como camada de serviços padronizada para consumo pelo frontend interno em HTMX e por potenciais clientes desacoplados ou futuras migrações SPA.
Fonte: site/app/main.py:34-100

As rotas públicas e autenticadas da aplicação são organizadas sob o prefixo `/api/v1` em grupos funcionais bem definidos pelas tags OpenAPI: Questões, Árvore, Facetas, Disciplinas, Conta, Estatísticas, Simulado, Autenticação e Infra.
Fonte: site/app/main.py:58-92

As entidades de questões são universalmente indexadas pela chave composta estável `<concurso>|<caderno>|<numero>` (ex.: `PF_25_ADM|094_PF_CB1_01|1`), que deve ter o caractere `|` codificado como `%7C` quando transmitido em caminhos de URL. Identificadores seriais do banco (`questao_id`) são tratados como variáveis internas sujeitas a recargas e nunca como referências persistentes na API.
Fonte: site/app/main.py:43-47

## Endpoints de Questões, Árvore e Facetas

O endpoint `GET /api/v1/questoes` realiza a consulta paginada de questões objetivas (formato Certo/Errado ou múltipla escolha), aceitando múltiplos filtros cumulativos em que repetições do mesmo parâmetro combinam em OU e parâmetros diferentes combinam em E. A listagem devolve modelos `PaginaQuestoes` ordenados por concurso, caderno e número, cobrindo o acervo cujos totais consolidados constam em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: site/app/api/v1/rotas_questoes.py:36-158

Os filtros da listagem suportam restrição por `banca`, `orgao`, `ano`, `concurso` (slug), `cargo` (no formato `CONCURSO:NUMERO`), `nivel` (`superior` ou `medio`), `tipo_conhecimento` (`basico` ou `especifico`), `tipo` (`certo_errado` ou `multipla_escolha`), `no_id` (nó taxonômico da árvore), `anuladas` (`incluir`, `excluir` ou `so`), `utilizaveis` (`so` ou `todas`), `texto` (busca textual sem acentos até 100 caracteres ou ID curto) e `com` (`texto_base` e/ou `figuras`). Usuários autenticados podem ainda aplicar o filtro `historico` (`todas`, `resolvidas`, `nao_resolvidas`, `certas`, `erradas`).
Fonte: site/app/api/v1/rotas_questoes.py:50-134

O detalhe individual de um item é servido em `GET /api/v1/questoes/{chave}`, retornando o modelo `QuestaoDetalhe` que engloba texto do enunciado, comando da seção, gabarito oficial, lista de cargos associados, apontamentos na árvore com rótulos e lista de figuras e texto-base anexos.
Fonte: site/app/api/v1/rotas_questoes.py:160-177

A rota `GET /api/v1/questoes/{chave}/parecidas` retorna até 20 questões correlatas que compartilham o mesmo nó taxonômico principal da árvore, desduplicando enunciados canônicos repetidos em múltiplos cadernos e excluindo a própria questão consultada.
Fonte: site/app/api/v1/rotas_questoes.py:179-210

A rota `GET /api/v1/arvore` expõe a árvore mestre completa no formato hierárquico disciplina → assunto → subassunto através de instâncias de `NoArvore`, contendo a contagem de questões válidas desduplicadas que sobe a hierarquia a partir dos subassuntos.
Fonte: site/app/api/v1/rotas_questoes.py:212-227

O endpoint `GET /api/v1/facetas` processa os mesmos parâmetros de filtro da listagem de questões e devolve o modelo `FacetasResponse` contendo todas as opções disponíveis e os totais de itens correspondentes, permitindo a renderização reativa dos seletores de interface.
Fonte: site/app/api/v1/rotas_questoes.py:229-298

O grupo de disciplinas é atendido por `GET /api/v1/materias`, que lista todas as matérias ativas com seus respectivos totais de questões e percentual de incidência média entre provas, e por `GET /api/v1/materias/{materia_id}`, que traz a ficha analítica da matéria e o ranking dos seus subassuntos mais recorrentes.
Fonte: site/app/api/v1/rotas_materias.py:16-67

A busca textual em nós taxonômicos é fornecida por `GET /api/v1/busca`, que pesquisa nomes e termos normalizados de disciplinas, assuntos e subassuntos com limite de até 20 correspondências.
Fonte: site/app/api/v1/rotas_materias.py:69-83

## Endpoints de Simulado e Estatísticas de Desempenho

O endpoint `GET /api/v1/simulados/prova` constrói a prova de um cargo indicado (`concurso` e `cargo_numero`), devolvendo o modelo `ProvaSimulado` com os itens na ordem canônica de aplicação da prova e as questões discursivas, omitindo estritamente gabaritos e critérios de correção.
Fonte: site/app/api/v1/rotas_simulados.py:28-46

A correção avulsa e anônima de simulados é executada via `POST /api/v1/simulados/correcao`, que processa o mapa de respostas e devolve o `ResultadoSimulado` com pontuação líquida por formato (certo/errado: +1 certo, −1 errado, 0 branco; múltipla escolha: +1 certo, 0 errado, 0 branco) e desempenho por matéria sem gravar dados no banco.
Fonte: site/app/api/v1/rotas_simulados.py:48-63

Para usuários autenticados, o ciclo de vida do simulado é gerenciado por `POST /api/v1/simulados` (criação do simulado com registro de início), `GET /api/v1/simulados` (listagem dos simulados realizados pelo usuário), `POST /api/v1/simulados/{simulado_id}/correcao` (finalização atômica, cálculo da nota e persistência de respostas) e `GET /api/v1/simulados/{simulado_id}` (consulta ao resultado consolidado).
Fonte: site/app/api/v1/rotas_simulados.py:65-120

A rota `GET /api/v1/simulados/{simulado_id}/questoes` entrega a listagem paginada no formato `PaginaQuestoes` contendo apenas os itens que o estudante errou (`situacao=errado`) ou deixou em branco (`situacao=branco`) no simulado encerrado, viabilizando fluxos de revisão direcionada.
Fonte: site/app/api/v1/rotas_simulados.py:122-159

A incidência empírica de conteúdo cobrado nas provas é consultada em `GET /api/v1/estatisticas/prova-cobra`, operando sobre a função SQL `fn_prova_cobra` para calcular a média ponderada em dois níveis (fatia na prova do cargo e média balanceada entre concursos com peso 1), evitando distorções decorrentes de itens básicos compartilhados entre múltiplos cargos.
Fonte: site/app/api/v1/rotas_estatisticas.py:36-61

Os endpoints analíticos complementares `GET /api/v1/estatisticas/edital-cobra` e `GET /api/v1/estatisticas/edital-vs-prova` entregam, respectivamente, o volume de menções de assuntos em editais publicados e o confronto comparativo discriminando quais conteúdos previstos no edital foram efetivamente cobrados em prova ou permaneceram sem questões.
Fonte: site/app/api/v1/rotas_estatisticas.py:63-101

## Endpoints de Autenticação e Perfil do Usuário

O fluxo de autenticação baseia-se em redirecionamentos HTTP gerenciados pelas rotas `GET /entrar` (início do fluxo Google OAuth via Authlib), `GET /auth/google` (recebimento do código e criação da sessão) e `POST /sair` (invalidação do cookie de sessão e descarte de tokens).
Fonte: site/app/web/rotas_web.py:958-1025

A submissão individual de resolução de questão é realizada por `POST /api/v1/respostas`, que valida a formatação da alternativa submetida, afere se a escolha corresponde ao gabarito oficial e, caso exista usuário autenticado na sessão, persiste o registro na tabela `app.resposta`. Questões anuladas não são gravadas no histórico.
Fonte: site/app/api/v1/rotas_conta.py:26-48

Os dados cadastrais e as configurações da conta logada são acessíveis em `GET /api/v1/eu`, enquanto a remoção irrevogável dos dados pessoais e de todo o histórico de resoluções e simulados em observância à LGPD é disparada pelo endpoint `DELETE /api/v1/eu`.
Fonte: site/app/api/v1/rotas_conta.py:50-82

As métricas consolidadas do estudante são agrupadas em `GET /api/v1/eu/resumo` (indicadores de acertos, erros, nota líquida CEBRASPE, volume de erros pendentes de revisão e ofensiva de dias consecutivos de estudo no fuso de Brasília) e `GET /api/v1/eu/desempenho` (percentual de aproveitamento detalhado por nó taxonômico).
Fonte: site/app/api/v1/rotas_conta.py:84-165

A priorização de estudo é orientada pelos endpoints `GET /api/v1/eu/prioridades` (subassuntos críticos ranqueados pelo cruzamento entre peso na prova e taxa de erro individual), `GET /api/v1/eu/concurso-alvo` e `PUT /api/v1/eu/concurso-alvo` (definição do cargo e concurso foco) e `GET /api/v1/eu/plano` (plano de matérias ordenado por prioridade de estudo para o cargo pretendido).
Fonte: site/app/api/v1/rotas_conta.py:101-120

## Padrão de Respostas de Erro, Paginação e Infraestrutura

Todas as respostas de erro emitidas pelos endpoints da API seguem rigorosamente o modelo estruturado `Erro`, apresentando o corpo `{"detail": "..."}` em conformidade com as convenções do FastAPI, acompanhado dos códigos de status HTTP 401 (ausência de sessão autenticada), 403 (falha na validação do token CSRF), 404 (recurso inexistente), 409 (conflito de estado, como tentativa de reencerrar simulado) e 422 (parâmetro inválido ou resposta fora do formato da questão).
Fonte: site/app/api/v1/respostas_comuns.py:10-36

As listagens de itens com grande volume de dados implementam paginação uniforme padronizada no modelo `PaginaQuestoes`, informando `total` de itens atendidos pelos filtros, `pagina` corrente (iniciando em 1), `tamanho_pagina` (limitado ao máximo de 50 registros por consulta), `total_paginas` calculadas e a lista `itens`.
Fonte: site/app/modelos.py:368-376

O tratamento de exceções HTTP da aplicação intercepta requisições direcionadas para caminhos iniciados por `/api/` ou clientes com cabeçalho `Accept` JSON para assegurar que falhas nunca devolvam templates HTML acidentalmente, mantendo a integridade do contrato REST.
Fonte: site/app/main.py:108-132

A checagem operacional de infraestrutura é provida pelo endpoint público `GET /saude`, que testa ativamente a conectividade ao banco de leitura PostgreSQL executando uma consulta rápida (`SELECT 1`), retornando status HTTP 200 com `{"status": "ok"}` em condições normais ou status HTTP 503 com `{"status": "erro"}` em caso de indisponibilidade da base.
Fonte: site/app/main.py:174-190

## Referências e Regras Relacionadas

- Regra de cálculo de incidência por prova: [P63 - Estatística de Prova com fn_prova_cobra](../tecnico/regras.md#p63)
- Regra de segurança de credenciais em roles: [A44 - Senhas de Role fora do SQL](../tecnico/regras.md#a44)
- Regra de preservação de GRANTs entre cargas: [A57 - Sobrevivência de GRANTs](../tecnico/regras.md#a57)
- Decisão sobre stack, auth e deploy: [ADR-033 - Site Público de Questões](../adr/ADR-033-site-publico-stack-e-deploy.md)
- Decisão sobre fidelidade ao caderno e filtros: [ADR-034 - Fidelidade ao Caderno e Filtros](../adr/ADR-034-fidelidade-ao-caderno-e-filtros.md)
- Decisão sobre card e filtros formato Gran: [ADR-035 - Card e Filtros Formato Gran](../adr/ADR-035-card-e-filtros-formato-gran.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
