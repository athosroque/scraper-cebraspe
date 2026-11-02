# Passagem de bastão: Dagster (D5a fechada, D5b a seguir)

Atualizado em 2026-10-21. Para abrir uma sessão nova sem depender da conversa anterior.
Cards: D5a = KAN-31, D5b = KAN-32 (etapa-mãe: Etapa 9, KAN-67; a C2 da 8.C).

> Ao abrir a sessão, ler só este arquivo. Os detalhes estão em `prompt-dagster-d5.md`
> (escopo da D5b, na "Rodada 2") e em `plano-etapa-9.md` (seção "D5b").

## Estado: D5a entregue e validada

Commit `c3a6eb9` (`feat(scraper-cebraspe): Dagster como C2, infra e assets (KAN-31)`), no
`master`, sem o ADR-042. Contém `Dockerfile.dagster`, `dagster_home/dagster.yaml`,
`src/c2/` (`assets.py`, `definitions.py`, `partitions.py`), `scripts/executar_c2.py`,
`tests/test_c2_dagster.py`, os serviços webserver (`127.0.0.1:8014`) e daemon no
`docker-compose.yml`, o `--concurso` em `scripts/classificar_questoes.py`, o registro
(`src/registro/`), o teste guarda do Dagster (fora do `skip`) e as páginas geradas.

**Validado de forma independente (2026-10-21):**

- Instalação limpa de `requirements.txt` resolve (`pip check` limpo); suíte do C2 e do
  registro com 38 testes verdes nesse ambiente; container com `dagster` 1.9.13,
  `protobuf` 5.29.6 e `langfuse` 4.18.0.
- Lote da C1 (`SEFA_PR_25` + `BANRISUL_25`) em conferência: saída 0 na 1.9.13; contagens
  iguais antes e depois (610 questões nos dois concursos, 180 na fila, 3.410 questões no
  total, 7 concursos); piloto inalterado (2.800 itens, 129 anuladas, 3.029 apontamentos,
  hash `3257ba6ba525fdd6b4492733b50882f2`).
- Banco do Dagster fora: `executar_c2` sai com código 1, sem fallback efêmero.
- Portão P3: `_buscar_edital` acha os 7 concursos reais por `concurso.slug` (regra P41).
  `SEFA_PR_25` e `BANRISUL_25` estão `PENDENTE` (falta o dono aprovar, KAN-56).
- Assets sem lógica ainda (P0, P2, P4b, P5, P6, P7, P9, P11) devolvem `nao_implementado`.
- `dagster.projetoathos.com.br` publicado no túnel e atrás do Cloudflare Access (302 para
  o login, inclusive em `/graphql`).

## Versões do Dagster: fixadas em 1.9.13 (de propósito)

`requirements.txt` tem `dagster==1.9.13`, `dagster-webserver==1.9.13` e
`dagster-postgres==0.25.13`. **Não voltar para a 1.8.13:** o `dagster` 1.8.13 exige
`protobuf<5` e o `langfuse` (via `opentelemetry-proto`) exige `protobuf>=5`, então uma
instalação limpa dá `ResolutionImpossible`. A 1.9 renomeou `AssetGraph.all_asset_keys` para
`get_all_asset_keys`; os testes já usam o novo nome, com fallback.

**Atenção ao venv local (`venv/`):** ele ainda tem `protobuf` 4.25.9 e o `pip check` acusa
conflito com `opentelemetry-proto`. Os testes passam nele, mas ele diverge do container e de
uma instalação limpa. Realinhar com `venv/bin/pip install -r requirements.txt` antes de
trabalhar, e rodar `venv/bin/pip check`.

## Próximo passo: D5b (KAN-32)

Seguir `prompt-dagster-d5.md`, "Rodada 2": asset checks, invariante do piloto antes e depois
de cada lote, portões humanos como checks bloqueantes, detector de dispersão como asset,
pendências do §7 do runbook e o relatório `inventario/lotes/lote_NN.md`.

**Cuidados:**

- **`--no-conferencia` não é seguro ainda.** Os assets P4 e P10 chamam funções globais
  (`gravar_estatisticas()`, `processar_fila()`, `atualizar_artefatos_revisao()`) por
  partição, sem K22–K24 antes e depois. A D5b é quem põe essa guarda.
- Piloto inalterado (P71): nada grava nele; testar só em conferência.
- Sem credencial no código (A07); não aprovar nada em nome do dono (A25, A27, A30).
- Não editar à mão `docs/tecnico/` (A62), `docs/adr/`, `CLAUDE.md` nem `mkdocs.yml`.
- Não mexer no Jira: quem valida comenta e move os cards.
- A validação refaz tudo do zero: busca de edital sem `patch` nos slugs reais, instalação
  limpa, lote em conferência com contagens antes e depois, e o invariante do piloto por SQL.

## Depois da D5b

- Reescrever o ADR-042 (Dagster como C2) e incluí-lo no `docs/adr/README.md` e no `nav`. O
  texto proposto antes prometia "retomada granular" e "linhagem" que ainda não existem.
- Página do Dagster no guia (onda 4 do `plano-documentacao.md`).
- KAN-66, parte 1 (mover as questões 56 a 58 de `STM_25` para a LAI): grava no banco do
  piloto, então só com K22–K24.
- Lotes C3 a C7 no Dagster (C3 = `SEBRAE_25_PSE_1` + `UNIVESP_25_PSS`) e C8, em
  `plano-etapa-8c.md`.

## Dependências do dono (fora desta sessão)

- C1a (KAN-56): aprovar os editais de `SEFA_PR_25` e `BANRISUL_25` (hoje `PENDENTE`).
- C1b (KAN-57): árvore, classificação e site dos dois concursos; pelo plano da Etapa 9,
  vem antes da C2, e continua pendente.
- D4 (KAN-71): visão executiva e PDF, em análise.
