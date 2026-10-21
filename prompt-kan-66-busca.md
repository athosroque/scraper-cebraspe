# Prompt de delegação: busca do site (KAN-66, partes 2, 3 e 4)

Criado em 2026-10-21. Roda numa worktree própria, em paralelo ao Dagster (D5a e D5b,
`prompt-dagster-d5.md`). A parte 1 do KAN-66 (mover questões de norma para o nó da LAI) fica
de fora: grava no banco do piloto e espera a D5a.

---

# Tarefa: busca do site, palavra-chave com classificação (KAN-66, partes 2 a 4)

Trabalhe em /home/athos/homelab/scraper_cebraspe, na worktree desta sessão.
Leia só a seção "Busca do site" de `task.md` (em "Pendências posteriores"), o ADR-035
(`docs/adr/ADR-035-card-e-filtros-formato-gran.md`, em especial a "Revisão do painel
(5H.3)") e `docs/tecnico/tarefas.md` (tarefa "mexer no site"). Responda em português do
Brasil, com acentos.

## Contexto

Hoje a palavra-chave procura só no enunciado e no comando da questão. Questões de norma
consolidada (LGPD, LAI, LRF) ficam de fora quando o termo não aparece no texto, mesmo
estando classificadas no nó da norma. O `/api/v1/busca` já casa nome e apelido de nó
(`site/app/servicos/estatisticas_servico.py`, `buscar_nos`), e a lista de questões usa
`buscar_questoes` (`site/app/repositorio/questoes_repo.py`).

## O que fazer

1. **Palavra-chave = texto + classificação.** O termo que casa nome ou apelido de um nó (regra
   do `/api/v1/busca`) passa a trazer também as questões classificadas nesse nó e nos
   descendentes, somadas às que já casam pelo texto. Sigla curta vale como palavra inteira
   ("LAI" não casa "laicização"). Ponto de milhar e "nº" ficam fora da comparação, igual à
   busca rápida ("12.527", "12527" e "nº 12.527" dão o mesmo resultado).
2. **Sugestões ao digitar** na palavra-chave: lista de assuntos que casam, com caminho e
   total (ex.: "LGPD → Dir. Administrativo › Acesso à informação e proteção de dados (13)").
   O clique marca o filtro. A lista de questões continua só no botão Filtrar (ADR-035).
3. **Tirar a trava da cascata.** Assunto e Subassunto passam a aceitar busca e marcação sem
   disciplina marcada (hoje ficam desabilitados até marcar o pai, 5H.3). Com o pai marcado, a
   lista segue restrita aos filhos.
4. Atualizar o ADR-035 com uma seção "Atualização" (não reescrever o texto antigo) e
   ajustar `site/tests/test_filtros_cascata.py`.

## Testes

- Novos testes em `site/tests/` para: termo que casa só pela classificação, sigla como
  palavra inteira, variações de número da lei, sugestões, e a cascata sem trava.
- Fora desta tarefa: o teste guarda "questão cujo enunciado cita a norma tem o nó da norma
  entre os apontamentos". Ele depende da parte 1, que grava no banco.
- Conferir no Chromium headless (1280 e 390 px): 0 erro de JavaScript.
- Se mudar rota ou modelo: `python site/scripts/exportar_openapi.py`, senão
  `test_openapi_versionado_em_dia` falha.

**Pronto quando:** "LGPD", "LAI", "12527" e "LRF" na palavra-chave trazem as questões
classificadas no nó (os números exatos de LAI e de 7.724 só fecham depois da parte 1);
`make check` verde; piloto inalterado (2.800 itens, 129 anuladas).

## Proibições

- **Só leitura no banco.** Nada de `UPDATE`, `curar_classificacao`, `stats_writer` ou
  qualquer passo que grave. Piloto inalterado (P71).
- Não tocar nos arquivos da outra worktree (Dagster): `Dockerfile.dagster`,
  `docker-compose.yml`, `requirements.txt`, `.env.example`, `src/registro/`,
  `tests/test_registro*.py`, `scripts/classificar_questoes.py`, `docs/tecnico/`.
- **Não rodar `make docs-gerar`** (colide com `docs/tecnico/` da outra worktree); eu rodo na
  integração. Não editar `docs/tecnico/`, `CLAUDE.md`, `mkdocs.yml` nem outros ADRs.
- Sem credencial no código (A07). Não commitar e não mexer no Jira: eu valido e faço os dois.

## Relatório final (obrigatório, para eu validar)

1. Lista de arquivos criados e alterados.
2. Saída de `make check` e dos testes novos de `site/tests/`.
3. Evidência do critério "pronto quando": o termo buscado, quantas questões vieram antes e
   depois, e o resultado do Chromium (1280 e 390 px).
4. O que ficou de fora ou diferente do plano, e por quê (em especial dependências da parte 1).

---

## Validação (feita por quem delegou)

- Diff: nenhum arquivo proibido tocado e nenhuma escrita no banco.
- `make check` e `make test-all` verdes; `test_openapi_versionado_em_dia` em dia.
- Reexecutar as buscas ("LGPD", "LAI", "12527", "LRF") e conferir contra o nó no banco.
- Conferir que "LAI" não casa "laicização" e que a cascata continua restrita com o pai
  marcado.
- Depois de validar: commit, comentário no KAN-66, e a parte 1 entra depois da D5a.
