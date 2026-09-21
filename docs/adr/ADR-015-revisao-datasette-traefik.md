# ADR-015: Revisão Navegável via Datasette, Traefik e Cloudflare Tunnel

## Status
Aceito

## Data
2026-09-20

## Contexto
O checkpoint humano da Etapa 4 (`status_revisao_humana: PENDENTE`) requer que um especialista revise os tópicos extraídos e compare o texto do edital com a árvore gerada pelo LLM. Criar uma aplicação web própria exigiria frontend dedicado, autenticação e esforço desproporcional para a fase piloto.

## Decisão
1. Desenvolver o script `scripts/gerar_db_datasette.py` para converter os arquivos JSON de dados e auditoria em um banco SQLite (`revisao_piloto/revisao.db`) com tabelas normalizadas e índices de busca textual (FTS5).
2. Subir uma instância Docker oficial do Datasette (`datasetteproject/datasette`), servindo o banco gerado em modo somente-leitura.
3. Conectar o container à rede `homelab_default`, integrando-o ao roteador Traefik e expondo-o publicamente sob o domínio `datasette.projetoathos.com.br`, protegido por autenticação Cloudflare Access SSO (com fallback local em `http://127.0.0.1:8011`).

## Consequências
### Positivas
- Fornece instantaneamente uma interface rica com filtros SQL, paginação, busca Full-Text Search e visualização tabular sem a necessidade de codificar componentes de interface gráfica.
- Viabiliza auditoria remota segura sem expor dados não aprovados sem controle de acesso.
- O banco SQLite é descartável e totalmente derivado dos JSONs da pasta `revisao_piloto/`.

### Alternativas Descartadas
- **Desenvolver um frontend customizado:** Complexidade e tempo elevados para a finalidade de validação do piloto.
- **Utilizar o banco Postgres de produção para a ferramenta de revisão:** Acoplaria a ferramenta descartável da Etapa 4 ao schema definitivo da Fase 5.
