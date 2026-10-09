# Plano de Implementação — Etapa 8.M: Suporte a Múltipla Escolha

## Goal
Tornar o pipeline, o banco de dados e a interface web totalmente compatíveis com questões de Múltipla Escolha (A–E) do CEBRASPE, preservando 100% da integridade e retrocompatibilidade das questões Certo/Errado existentes.

## Tasks
- [x] Task 1: **Modelagem e Schema no Banco** — Adicionar `tipo` (`certo_errado` | `multipla_escolha`), `alternativas` (`jsonb`) e estender check de gabarito para `A–E` em `src/sql/schema_estatisticas.sql`, `src/questoes_writer.py` e `src/stats_writer.py`, mantendo hash SHA-1 das 2.800 questões existentes → Verify: `venv/bin/pytest tests/test_questoes_writer.py` passa e chaves 5D do piloto continuam idênticas.
- [x] Task 2: **Parser de Gabaritos ME** — Ajustar `src/gabarito_parser.py` para validar letras `A–E` (mais `X` para anuladas) dependendo do tipo do caderno, sem perder validações de erro bloqueante → Verify: `venv/bin/pytest tests/test_gabarito_parser.py` passa com gabaritos C/E e gabaritos A–E.
- [x] Task 3: **Parser de Caderno ME** — Implementar segmentação de enunciados e alternativas `(A)–(E)` em `src/prova_parser.py` (multilinha, figuras e tabelas), calibrado com os 3 PDFs reais em `data/inventario_amostra/` (`BANRISUL_25`, `SEBRAE_26_PSE_1`, `SEFA_PR_25`) → Verify: Testes unitários com trechos dos 3 PDFs confirmam 4–5 alternativas por questão e 0 cortes indevidos.
- [x] Task 4: **Classificação 5D com Alternativas** — Adaptar `src/candidatos_questao.py` e `scripts/classificar_questoes.py` para injetar o texto das alternativas no prompt de classificação para questões do tipo `multipla_escolha` → Verify: Testes unitários de prompt confirmam presença de alternativas para ME e ausência para CE.
- [x] Task 5: **Serviços do Site e Simulado** — Atualizar `site/app/modelos.py`, `site/sql/app_schema.sql` e serviços (`contas_servico`, `simulados_servico`) para suportar respostas `A–E` conferidas pelo tipo da questão, pontuação por formato (+1/−1 para CE e +1/0 para ME) e reexportar `site/openapi.json` → Verify: `venv/bin/pytest site/tests/` passa sem divergência no contrato OpenAPI.
- [/] Task 6: **Templates e UI do Site** — Renderizar alternativas como radio buttons em `site/app/templates/_componentes.html`, `_card_questao.html`, `_correcao.html`, atualizar tela de correção e adicionar faceta de filtro por tipo (`certo_errado` / `multipla_escolha`) → Verify: Teste com Chromium headless valida renderização e submissão de questão ME e CE.
  - Implementado e coberto em `site/tests/test_multipla_escolha.py` (questão ME simulada). Falta o Chromium headless, que depende de questão ME no banco.
- [ ] Task 7: **Gate da 8.M e ADR-038** — Homologar piloto inalterado (2.800 itens, 129 anuladas, 3.029 apontamentos), validar 1 concurso ME de ponta a ponta e formalizar ADR-038 → Verify: `make test-all` verde e relatório de conferência do piloto sem divergências.
  - Feito: ADR-038 (o ADR-037 é o do escopo do site no inventário), `make test-all` e ruff verdes.
  - Falta: ligação prova ME ↔ gabarito (`task.md`), carga de 1 concurso ME e a validação dele no site; relatório de conferência do piloto.

## Done When
- [x] Os 3 cadernos ME reais da amostra são parseados com 100% de sucesso (enunciado + alternativas A–E).
- [ ] O banco e o site suportam responder e pontuar questões tanto de Certo/Errado quanto de Múltipla Escolha (código e testes prontos; falta conferir com um concurso ME real carregado).
- [ ] O piloto existente de 2025 (5 concursos, 2.800 questões) permanece 100% intocado em contagens, hashes e apontamentos (chaves 5D conferidas em teste; falta o relatório de conferência do Gate).
- [x] `make test-all` e checagens de linter estão 100% verdes.

## Notes
- Colisão das letras `C` e `E`: no banco e na API, `gabarito` e `resposta` só devem ser interpretados em conjunto com `tipo`.
- Cadernos mistos: o tipo é definido a nível de questão (`questoes.tipo`), nunca a nível de concurso inteiro.
- PDFs de referência já disponíveis localmente:
  1. *Com figuras:* `data/inventario_amostra/BANRISUL_25_077_BANRISUL_CB1_01.pdf`
  2. *Básico:* `data/inventario_amostra/SEBRAE_26_PSE_1_2F270C9D0984DBDB129163E0C92DDE43057DFC1637D6342D91B41790C26EAB2E.pdf`
  3. *Específico:* `data/inventario_amostra/SEFA_PR_25_90ECB71259732E8F2E4407EDA63B6754CADD1809D7F1A2741FB1422320521691.pdf`
