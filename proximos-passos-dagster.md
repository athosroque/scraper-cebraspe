# Passagem de bastão: Dagster (D5a em fechamento, D5b a seguir)

Criado em 2026-10-21. Para abrir uma sessão nova sem depender da conversa anterior.
Cards: D5a = KAN-31, D5b = KAN-32 (etapa-mãe: Etapa 9, KAN-67; a C2 da 8.C).

> Ao abrir a sessão, ler só este arquivo. Os detalhes estão em `prompt-dagster-d5.md`
> (escopo da D5b, na "Rodada 2") e em `plano-etapa-9.md` (seções "D5a" e "D5b").

## Estado da D5a (validado em 2026-10-21)

O trabalho está **sem commit** no checkout principal (`master`), junto com a infra:

- Novos: `Dockerfile.dagster`, `dagster_home/dagster.yaml`, `src/c2/` (`assets.py`,
  `definitions.py`, `partitions.py`), `scripts/executar_c2.py`, `tests/test_c2_dagster.py`.
- Alterados: `docker-compose.yml` (webserver em `127.0.0.1:8014` e daemon), `.env.example`,
  `.gitignore`, `pyproject.toml`, `requirements.txt`, `scripts/classificar_questoes.py`
  (`--concurso`), `src/registro/scripts.py`, `src/registro/tarefas.py`,
  `tests/test_registro.py` (o teste guarda do Dagster saiu do `skip`),
  `tests/test_classificar_questoes.py` e as páginas geradas de `docs/tecnico/` e
  `docs/executivo/numeros.md`.

**Confirmado:**

- Containers `scraper-cebraspe-dagster-webserver` e `-daemon` de pé; storage no banco
  `dagster`, separado do `cebraspe` (0 tabelas do Dagster em `cebraspe`).
- Portão P3 corrigido: `_buscar_edital` acha os 7 concursos reais por
  `concurso.slug` (via `listar_jsons_edital` e `status_revisao`, regra P41); devolve `None`
  para slug inexistente. `PF_25_ADM`, `TCU_25_TEFC`, `IBAMA_25`, `STM_25` e `CD_25_NS` estão
  aprovados; `SEFA_PR_25` e `BANRISUL_25` estão `PENDENTE` (falta o dono aprovar, KAN-56).
- `executar_c2` sai com código 1 se o banco do Dagster estiver fora (sem fallback efêmero).
- Assets sem lógica ainda (P0, P2, P4b, P5, P6, P7, P9, P11) devolvem `nao_implementado`,
  com aviso no log.
- Lote da C1 em conferência: saída 0; contagens antes e depois iguais (17 provas, 610
  questões, 5 discursivas, 0 apontamentos, 180 na fila, 3.410 questões, 7 concursos); piloto
  inalterado (2.800 itens, 129 anuladas, hash `3257ba6ba525fdd6b4492733b50882f2`).
- Domínio `dagster.projetoathos.com.br` publicado no túnel e atrás do Cloudflare Access
  (302 para o login, inclusive em `/graphql`). Passos manuais do dono: feitos.

## O que falta fechar na D5a

**Versões do `dagster` desalinhadas (bloqueia o commit).** O `requirements.txt` está com
`dagster>=1.8.13,<=1.9.13` (e o mesmo para `dagster-webserver`; `dagster-postgres>=0.24.13,<=0.25.13`).
O venv do projeto, onde os testes rodaram, tem **1.8.13**; uma instalação limpa e a imagem
já reconstruída usam **1.9.13**. Na 1.9.13, 2 testes falham
(`test_c2_dagster.py::test_definitions_carrega_e_valida_estrutura` e
`test_registro.py::test_dagster_definitions_batem_com_o_registro`): a 1.9 renomeou
`AssetGraph.all_asset_keys` para `get_all_asset_keys`. O argumento do range (conflito de
`protobuf` com o `langfuse`) não se sustenta: o venv já roda 1.8.13 com `protobuf` 4.25.9 e
`langfuse`.

## Ordem

1. **Pins exatos** no `requirements.txt`: `dagster==1.8.13`, `dagster-webserver==1.8.13`,
   `dagster-postgres==0.24.13`.
2. **Reconstruir a imagem:** `docker compose build scraper-cebraspe-dagster-webserver` e
   `docker compose up -d`; conferir `curl http://127.0.0.1:8014/server_info` mostrando 1.8.13.
3. **Suíte** (`pytest` e `ruff` não estão no `requirements.txt`, já era assim):
   `make test-fast`, `ruff format --check` nos arquivos tocados,
   `venv/bin/python -m scripts.gerar_docs --verificar` (se divergir, `make docs-gerar`) e
   `make docs-build`. Opcional e mais forte: venv novo, `pip install -r requirements.txt` e
   `pytest tests/test_c2_dagster.py tests/test_registro.py` nele.
4. **Commit da D5a**, sem o ADR-042 (o texto proposto prometia "retomada granular" e
   "linhagem" que ainda não existem; reescrever depois da D5b). Mensagem sugerida:
   `feat(scraper-cebraspe): Dagster como C2, infra e assets (KAN-31)`.
5. **D5b (KAN-32):** seguir `prompt-dagster-d5.md`, "Rodada 2".

## Cuidados que valem para a D5b

- **`--no-conferencia` não é seguro ainda.** Os assets P4 e P10 chamam funções globais
  (`gravar_estatisticas()`, `processar_fila()`, `atualizar_artefatos_revisao()`) por
  partição, sem K22–K24 antes e depois. A D5b é quem põe essa guarda.
- Piloto inalterado (P71): nada grava nele; testar só em conferência.
- Sem credencial no código (A07); não aprovar nada em nome do dono (A25, A27, A30).
- Não editar à mão `docs/tecnico/` (A62), `docs/adr/`, `CLAUDE.md` nem `mkdocs.yml`.
- Não mexer no Jira: quem valida comenta e move os cards.

## Depois da D5b

- Reescrever o ADR-042 (Dagster como C2) e incluí-lo no `docs/adr/README.md` e no `nav`.
- Página do Dagster no guia (onda 4 do `plano-documentacao.md`).
- KAN-66, parte 1 (mover as questões 56 a 58 de `STM_25` para a LAI): grava no banco do
  piloto, então só depois da D5a e com K22–K24.
- Lotes C3 a C7 no Dagster (C3 = `SEBRAE_25_PSE_1` + `UNIVESP_25_PSS`) e C8, em
  `plano-etapa-8c.md`.

## Dependências do dono (fora desta sessão)

- C1a (KAN-56): aprovar os editais de `SEFA_PR_25` e `BANRISUL_25` (hoje `PENDENTE`).
- C1b (KAN-57): árvore, classificação e site dos dois concursos; pelo plano da Etapa 9,
  vem antes da C2, e continua pendente.
- D4 (KAN-71): visão executiva e PDF, em análise.
