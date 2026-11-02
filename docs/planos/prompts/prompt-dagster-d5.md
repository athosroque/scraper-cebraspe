# Prompt de delegação: Dagster como C2 (D5a e D5b)

Criado em 2026-10-21. Cards: D5a = KAN-31, D5b = KAN-32 (etapa-mãe: Etapa 9, KAN-67).
Para colar numa sessão de execução. A D5b depende da D5a, então são duas rodadas, e a
segunda só começa depois que a primeira for validada.

---

# Tarefa: Dagster como C2 do scraper_cebraspe (D5a, depois D5b)

Trabalhe em /home/athos/homelab/scraper_cebraspe, de preferência numa worktree própria.
Leia só `plano-etapa-9.md` (seções "D5a", "D5b" e "Decisões do dono"), `plano-etapa-8c.md`,
`docs/tecnico/tarefas.md` e `CLAUDE.md`. Responda em português do Brasil, com acentos.

## Contexto

Hoje o lote de concursos roda à mão, com scripts e `docs/runbook-lote.md`. O Dagster passa
a orquestrar esse pipeline, no lugar do `scripts/lote_concursos.py`. Os assets nascem do
registro `src/registro/` (D2, ADR-041): uma fonte só para o pipeline documentado e o
executado.

## Rodada 1: D5a (KAN-31), infra e assets

1. `Dockerfile.dagster`: requirements do projeto + `dagster`, `dagster-webserver`,
   `dagster-postgres` e o Chromium do Playwright.
2. `docker-compose.yml`: serviços webserver e daemon, código por bind mount (como o bot),
   `data/`, `inventario/` e `revisao_piloto/` montados, credenciais do `.env`.
3. Storage do Dagster num banco `dagster` **separado**, dentro do `scraper-cebraspe-db`.
   Nunca no banco `cebraspe`.
4. Rótulos do Traefik para `dagster.projetoathos.com.br`. A aplicação no Cloudflare Access é
   passo manual do dono: liste-o no relatório, não tente fazer.
5. Assets gerados do registro, particionados por concurso (partições dinâmicas vindas do
   inventário). Eles **chamam as funções atuais, sem reescrevê-las**: `process_contest`,
   `revisar_edital_piloto`, `processar_fila` / `atualizar_artefatos_revisao`,
   `classificar_todas_questoes`. Acrescente `--concurso` ao `classificar_questoes` (hoje só
   tem `--caderno`).
6. Lote = uma execução com 2 partições. O estado vem do Dagster (materializações) e do
   banco (`status_revisao_humana`); o `inventario/lotes.json` deixa de ser necessário.
7. Testes: `Definitions` carrega; assets com as funções mockadas (retomada, parada no
   portão, aprovação). Tire o `skip` do teste guarda do Dagster em `tests/test_registro.py`.
8. Script novo entra em `src/registro/scripts.py` (P70); depois rode `make docs-gerar`.

**Pronto quando:** materializar o lote da C1 (`SEFA_PR_25` + `BANRISUL_25`) em **modo
conferência** não muda nada (idempotente), e a interface abre no domínio com Access.

## Rodada 2: D5b (KAN-32), só depois de eu validar a rodada 1

1. Asset checks: tabela "Checagens automáticas por lote" do `plano-etapa-8.md` (download,
   edital, prova, banco, classificação, site), consultas a–e do `docs/runbook-lote.md`,
   alternativa terminando em caixa alta, custo pelo OpenRouter (`/api/v1/key`) e o alerta
   "ME sem texto-base" (não bloqueia; exceções BANRISUL Q22, SEFA_PR Q11 e Q50).
2. Invariante do piloto (K22–K24) antes e depois de cada lote; diferença bloqueia o lote.
3. Portões humanos como checks bloqueantes: leem `status_revisao_humana` e as pendências da
   curadoria; a etapa seguinte não roda até o dono aprovar.
4. `detectar_dispersao_arvore --propor` como asset depois da carga; propostas novas vão para
   o relatório (KAN-64).
5. Pendências do §7 do runbook: chunking sem LLM (`--so-chunking`) e todos os editais do
   lote extraídos antes de uma carga só.
6. Relatório `inventario/lotes/lote_NN.md` gerado dos resultados das checks.

**Pronto quando:** o relatório do lote da C1 sai com as checagens verdes e um teste mostra o
portão travando a etapa seguinte.

## Proibições (valem nas duas rodadas)

- **Piloto inalterado (P71):** nada grava no piloto (2.800 itens, 129 anuladas, 3.029
  apontamentos, chaves da 5D). Teste só em modo conferência; nunca materialize contra
  produção sem eu pedir.
- Sem credencial no código ou no compose (A07); tudo no `.env`, com `.env.example`
  atualizado.
- Não aprovar nada em nome do dono (A25, A27, A30): sem `UPDATE` de aprovação no banco.
- Não editar à mão `docs/tecnico/` (A62), `docs/adr/`, `CLAUDE.md`, `mkdocs.yml`.
  O ADR novo (Dagster como C2) vem do registro de decisões: proponha o texto no relatório.
- Não usar `json.load`/`json.dump` direto em `canonico/arvore.json` (A28).
- Não commitar, não mexer no Jira. Eu valido e faço os dois.

## Relatório final (obrigatório, para eu validar)

1. Lista de arquivos criados e alterados.
2. Saída de `make test-fast`, `make docs-gerar` com `--verificar` e `make docs-build`.
3. Evidência do critério "pronto quando": comando rodado e resultado.
4. Passos manuais que ficam com o dono (Cloudflare Access, túnel).
5. O que ficou de fora ou diferente do plano, e por quê.

---

## Validação (feita por quem delegou, depois de cada rodada)

- Diff da branch: nenhum arquivo proibido tocado.
- `make check` e `make test-all` verdes; `--verificar` do registro em dia.
- Reexecutar a materialização da C1 em modo conferência e confirmar que K22–K24 não mudam.
- Na rodada 2, abrir o teste do portão e confirmar que a etapa seguinte trava de fato.
- Depois de validar: commit, comentário no card (KAN-31 ou KAN-32) e liberar a página do
  Dagster no guia (onda 4 do `plano-documentacao.md`).
