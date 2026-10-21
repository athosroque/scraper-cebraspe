# Prompt de correção: Dagster D5a (KAN-31), devolução da rodada 1

Criado em 2026-10-21. Para o mesmo agente que entregou a rodada 1 (`prompt-dagster-d5.md`).
A D5b (KAN-32) só começa depois que estas correções forem revalidadas.

---

# Tarefa: corrigir a rodada 1 da D5a e devolver para nova validação

Trabalhe em /home/athos/homelab/scraper_cebraspe, no mesmo checkout onde a rodada 1 está
(sem commit). Leia só este arquivo, `src/c2/assets.py`, `scripts/executar_c2.py`,
`tests/test_c2_dagster.py` e, em `src/stats_writer.py`, `listar_jsons_edital`,
`status_revisao` e `montar_carga_concurso`. Responda em português do Brasil, com acentos.

A validação encontrou que a infra está certa (containers, banco `dagster` separado, piloto
inalterado, 53 testes verdes), mas o pipeline tem um defeito real e a prova de "não muda
nada" é frágil. Corrija os itens abaixo, nesta ordem.

## 1. Obrigatório: o portão P3 não encontra o edital de nenhum concurso

`_buscar_edital_json` devolve `None` para `SEFA_PR_25`, `BANRISUL_25`, `PF_25_ADM` e
`STM_25` (conferido). Causa: o slug está em `resultado["concurso"]["slug"]` (um dict), e o
código compara `dados.get("concurso") == slug` (dict contra str) ou procura o slug no nome
do arquivo, que é o nome do PDF ou um hash. Efeito: o P3 devolve "ok" com `PENDENTE` para
qualquer concurso, e `--exigir-aprovacao` bloquearia até o `PF_25_ADM`, que está aprovado.

- Reaproveite o que o writer já faz (regra P41, não reimplemente): `listar_jsons_edital`
  para listar, `resultado["concurso"]["slug"]` para casar e `status_revisao(resultado)`
  para decidir aprovado ou pendente. Um slug pode não ter edital: trate esse caso de forma
  explícita (abaixo).
- Edital não encontrado deixa de ser "ok": o P3 devolve `status="sem_edital"` e, com
  `exigir_aprovacao=True`, levanta `PortaoHumanoBloqueado`.
- Modo produção (`conferencia=False`): não chame o LLM (`revisar_edital_piloto`) nem procure
  PDF com `glob` por padrão de pasta. O layout real é `data/<ano>/CEBRASPE/<ÓRGÃO>/Editais/`.
  Se o edital não existe, pare com mensagem clara; a extração por LLM gasta tokens e só
  roda com ordem explícita minha.
- **Teste que não use `patch` em `_buscar_edital_json`.** Use um `revisao_dir` temporário
  com JSONs no formato real (`{"concurso": {"slug": ...}, "status_revisao_humana": ...}`)
  e cubra: aprovado, pendente e sem edital. Mais um teste de contrato que roda a função
  contra o `revisao_piloto/` real e exige que `PF_25_ADM` e `STM_25` sejam achados e
  aprovados (marque como `db`/integração se precisar do disco).

## 2. Obrigatório: `dagster` não está no `requirements.txt`

Hoje só o `Dockerfile.dagster` o instala, e o venv local o tem por instalação manual. Num
checkout limpo, `tests/test_c2_dagster.py` e `tests/test_registro.py` quebram no import.

- Acrescente `dagster==1.8.13`, `dagster-webserver==1.8.13` e `dagster-postgres==0.24.13` ao
  `requirements.txt` e remova a linha `pip install` duplicada do `Dockerfile.dagster`.
- Confirme que a imagem ainda constrói (`docker compose build scraper-cebraspe-dagster-webserver`)
  e que os dois serviços sobem de novo com `docker compose up -d`.

## 3. Obrigatório: nada de sucesso silencioso em `executar_c2`

`obter_instancia` cai para `DagsterInstance.ephemeral()` se o banco do Dagster estiver fora.
O lote roda sem registro nenhum e o script ainda sai com código 0. Troque por falha com
mensagem clara e `sys.exit(1)`. Ephemeral só dentro dos testes, passando `instance=`
explicitamente. Teste: banco inalcançável → código de saída diferente de zero.

## 4. Status honesto nos assets que ainda não fazem nada

Os assets P0, P2, P4b, P5, P6, P7, P9 e P11 só registram log e devolvem `"ok"`. Parte disso é
da D5b, mas "ok" não pode significar "não fez nada".

- Os que são da D5b (P5, P6, P7, P9, P11) devolvem `status="nao_implementado"` e registram um
  aviso no log. O P0 (backup) e o P2 (chunking) também, até serem ligados de verdade.
- O P1 em conferência sem arquivos devolve `status="conferencia_sem_arquivos"` e, com
  `exigir_aprovacao=True`, falha.
- Atualize `tests/test_c2_dagster.py` para refletir esses status. Não afirme no relatório
  que "os 13 assets materializaram com sucesso" como prova de idempotência.

## 5. Prova de "não muda nada" com números

Antes e depois de materializar `SEFA_PR_25` + `BANRISUL_25` em conferência, rode estas contagens
(read-only) e cole as duas saídas no relatório: linhas de `questoes`, `discursivas`,
`questao_no` e `provas` desses 2 concursos, mais o invariante do piloto (consulta
`_SQL_INVARIANTE_PILOTO` de `src/registro/checagens.py`, deve devolver 0 linhas). Diferença
em qualquer contagem é falha.

## 6. Só uma nota: modo produção ainda não é seguro

Os assets P4 e P10 chamam funções globais (`gravar_estatisticas()`, `processar_fila()`,
`atualizar_artefatos_revisao()`) por partição. Não mude isso agora. Acrescente um comentário
curto no código dizendo que `--no-conferencia` não deve ser usado antes da D5b (K22–K24 antes
e depois do lote), e repita o aviso no `--help` do `executar_c2`.

## Proibições (as mesmas da rodada 1)

- Nada grava no banco do piloto nem em produção. Só conferência.
- Sem credencial no código (A07). Não aprovar nada em nome do dono.
- Não editar à mão `docs/tecnico/` (A62), `docs/adr/`, `CLAUDE.md` nem `mkdocs.yml`. O ADR-042
  proposto no relatório **não** entra agora: o texto prometia "retomada granular" e
  "linhagem" que ainda não existem. Eu reescrevo depois da D5b.
- Não mexer em `site/`: os 3 arquivos que o `ruff format` reclama hoje são do KAN-66.
- Não commitar e não mexer no Jira.

## Relatório final (obrigatório)

1. Arquivos alterados, por item (1 a 6).
2. Saída de `make test-fast`, `ruff check` e `ruff format --check` **só dos arquivos que você
   tocou** (os de `site/` ficam fora).
3. O resultado do teste de contrato do item 1 (quais concursos foram achados e o status de
   cada um).
4. As duas saídas do item 5 (antes e depois).
5. O que ficou de fora ou diferente, e por quê.

---

## Revalidação (por quem delegou)

- `_buscar_edital_json` (ou o que o substituir) contra os 5 slugs reais, sem `patch`.
- Checkout limpo: `pip install -r requirements.txt` e `pytest tests/test_c2_dagster.py` verdes.
- Banco do Dagster fora → `executar_c2` sai com código 1.
- Contagens antes e depois iguais, e K22–K24 sem diferença.
- Nenhum arquivo proibido tocado. Depois disso, commit e liberação da D5b.
