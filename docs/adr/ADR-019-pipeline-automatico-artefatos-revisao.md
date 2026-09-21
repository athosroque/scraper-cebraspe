# ADR-019: Pipeline Automático dos Artefatos de Revisão a Cada Extração

## Status
Aceito

## Data
2026-09-21

## Contexto

Os ADR-017 (validação heurística de-para) e ADR-018 (relatório HTML +
schema `alertas_validacao`) introduziram três passos manuais que precisavam
ser rodados **depois de toda extração ou reprocessamento**:

```bash
python -m scripts.validar_taxonomia
python -m scripts.gerar_relatorio_revisao
python -m scripts.gerar_db_datasette
docker compose restart scraper-cebraspe-datasette
```

Isso já era um problema latente mesmo antes destes dois ADRs: o achado do
ADR-013 (`run()` nunca chamava o downloader) e a auditoria de 2026-09-19
sobre href relativo mostram que este projeto já foi mordido por etapas do
pipeline desconectadas entre si, silenciosamente. Exigir 4 comandos manuais
toda vez que `scripts/revisar_taxonomia_piloto.py` ou
`scripts/reprocessar_falhas_piloto.py` rodam é o mesmo tipo de risco:
esquecer um passo deixa o Datasette (tabelas e relatório) desatualizado em
relação ao `<edital>.json` mais recente, sem nenhum sinal de erro — mesma
classe de falha silenciosa já documentada `n` vezes neste projeto.

## Decisão

Criar `scripts/atualizar_revisao.py`, com a função
`atualizar_artefatos_revisao(revisao_dir, reiniciar_datasette=True)` que
encapsula a sequência completa:

```python
def atualizar_artefatos_revisao(revisao_dir=REVISAO_DIR_PADRAO, reiniciar_datasette=True):
    validar_taxonomia(revisao_dir)      # scripts.validar_taxonomia.main
    gerar_relatorios(revisao_dir)       # scripts.gerar_relatorio_revisao.gerar_relatorios
    gerar_db(revisao_dir)               # scripts.gerar_db_datasette.gerar_db
    if reiniciar_datasette:
        _reiniciar_datasette()          # docker compose restart scraper-cebraspe-datasette
```

E chamá-la automaticamente nos dois pontos de entrada do pipeline de
extração:

1. `scripts/revisar_taxonomia_piloto.py` — `revisar_edital_piloto()` chama
   `atualizar_artefatos_revisao(saida_path.parent)` logo após escrever
   `<edital>.json` e `<edital>.auditoria.json`.
2. `scripts/reprocessar_falhas_piloto.py` — `reprocessar_falhas()` chama o
   mesmo helper quando `sucessos_novos > 0` (substitui a chamada duplicada
   a `gerar_db` + `subprocess.run(docker compose restart...)` que já
   existia só neste script, desde o ADR-016).

O restart do container é **best-effort**: `_reiniciar_datasette()` captura
`OSError` (Docker não instalado/não no PATH) e `returncode != 0`
(container não está no ar, nome errado, etc.) e só loga `warning` — nunca
lança exceção. **Decisão deliberada:** o pipeline de extração (que já fez
chamadas de API pagas ao LLM) não pode falhar ou perder o resultado só
porque o container Datasette local não está rodando (ex.: ambiente sem
Docker, CI, ou o serviço momentaneamente parado). Os JSONs já foram salvos
em disco antes desta etapa; o pior caso é o Datasette ficar servindo uma
versão anterior até o próximo restart manual.

Os três passos internos (`validar_taxonomia`, `gerar_relatorios`,
`gerar_db`) continuam **idempotentes e reconstroem do zero** a cada
chamada (mesma filosofia do ADR-015) — rodar `atualizar_artefatos_revisao`
mais de uma vez seguida é seguro e barato (sem chamada LLM, só leitura de
JSON + escrita local).

## Consequências

### Positivas
- Elimina a classe de bug "esqueci de rodar um dos 4 comandos depois da
  extração" — a mesma categoria de falha silenciosa já registrada 2x neste
  projeto (ADR-008, achado do href relativo; e o achado de 2026-09-19 sobre
  `run()` nunca chamar `download_concurso_pdfs`, CLAUDE.md §12).
- `scripts/reprocessar_falhas_piloto.py` perde ~20 linhas de lógica
  duplicada de restart de container (agora só chama o helper compartilhado)
  e, de quebra, corrige dois avisos de lint pré-existentes nesse arquivo
  (`except Exception` genérico → `except OSError`; `subprocess.run` sem
  `check` explícito → `check=False` explícito).
- `scripts/atualizar_revisao.py` também funciona como comando standalone
  (`python -m scripts.atualizar_revisao`) para quando alguém editar um
  `.json` manualmente fora do pipeline de extração e precisar só re-sincronizar
  os artefatos derivados sem rodar o LLM de novo.

### Alternativas Descartadas
- **Hook de `git commit` / pre-commit:** descartado — os JSONs de
  `revisao_piloto/` nem sempre mudam via commit (o fluxo típico é rodar o
  script e revisar antes de decidir commitar), e acoplar a atualização do
  Datasette ao Git criaria uma dependência estranha entre controle de
  versão e infraestrutura local.
- **Cron/systemd timer regenerando tudo periodicamente:** descartado por
  desperdiçar ciclos (o piloto tem 1 edital, mudanças são raras e
  disparadas por ação humana) e por atrasar a atualização (o objetivo é
  "logo depois da extração", não "na próxima janela do timer").
- **Deixar o restart do Datasette falhar ruidosamente (propagar exceção):**
  descartado — quebraria o retorno de `revisar_edital_piloto()`/
  `reprocessar_falhas()` por um problema de infraestrutura local não
  relacionado ao resultado da extração em si, que já está salvo em disco
  nesse ponto.
