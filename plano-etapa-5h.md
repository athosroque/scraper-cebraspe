# Plano — Etapa 5H: card da questão e filtros no formato Gran (cor teal)

> **Documento autocontido, uma sessão (sub-agente) por subetapa (5H.1 a 5H.5).**
> Base normativa: ADR-033 (stack e camadas do site), ADR-034 (5G: comando no
> topo, filtros multisseleção). Não é preciso reler o `task.md`.

---

## 1. Contexto e objetivo

O dono quer o card da questão e o painel de filtros do site (`site/`) no
formato do Gran Questões (prints de 2026-10-06), trocando o laranja do Gran
por **teal**. Hoje o card é um bloco único (`_card_questao.html`) com
cabeçalho "Questão N · órgão ano · banca", assunto em selos e botões
Certo/Errado de um clique. Os filtros (5G.4) ficam numa barra lateral de
`<details>` que filtra a cada checkbox.

**Decisões do dono (2026-10-06):**
- Cor de destaque **teal**, no site inteiro, via token `destaque`.
- **ID curto estável** da questão = `Q` + 8 hex (maiúsculos) do SHA-1 de
  `concurso|caderno|numero` (o `questao_id` muda a cada recarga).
- Resposta no padrão Gran: **círculo Certo/Errado + botão Responder**.
- Filtros em **dropdowns no topo**, aplicados só no **botão Filtrar**.

**Regras que continuam valendo** (ver `CLAUDE.md` §7): nada de valor da query
string dentro de expressão Alpine (usar `data-*`/JSON); `dom_id(chave)` como id
HTML; fragmento só sem `HX-History-Restore-Request`; gatilho HTMX no `<form>`,
nunca no `<select>`/input; contrato `site/openapi.json` reexportado a cada
mudança de rota/modelo; `localStorage` sempre em `try/catch`.

---

## 2. Design

### Card da questão

```
┌───┬──────────┬──────────────────────────────────────────────────────┐ cinza
│ 5 │ Q7F3A2C1 │ Administração Geral ▸ Gestão de processos             │ (slate-100)
└───┴──────────┴──────────────────────────────────────────────────────┘
 Ano: 2025  Banca: CEBRASPE  Órgão: PF  Prova: CEBRASPE - 2025 - PF - Cargo 1…   [Anulada] [Mais cai]
 ────────────────────────────────────────────────────────────────────── (links em teal)
 Texto associado ⊕                     (details, carrega /anexos sob demanda)
 │ Julgue os itens… (comando, data-comando)
 Enunciado…
   ◯ Certo
   ◯ Errado
 [Responder]  (teal, desabilitado até marcar)
 ──────────────────────────────────────────────────────────────────────
 ▤ Estatísticas da matéria  ≋ Questões parecidas  ⧉ Caderno (PDF)  ⚑ Notificar erro
 Fonte: CEBRASPE — PF 2025, caderno 094_PF_CB2_01, item 24.
```

- **Barra cinza:** posição na página (`(pagina-1)*tamanho + loop.index`, só na
  lista; detalhe e simulado escondem a caixa), ID curto, e o caminho do nó
  principal com `▸` (secundário depois de vírgula, como no print). Cada parte
  do caminho linka `/questoes?no_id=<id>`. Mantém `data-assunto-topo`.
- **Linha de metadados:** `Ano`, `Banca` (→ `?banca=`), `Órgão` (→ `?orgao=`),
  `Prova` (→ `?concurso=`). Com 1 cargo: `CEBRASPE - 2025 - PF - Cargo 1:
  Agente…`; com vários (caderno básico): rótulo do concurso + "N cargos" com a
  lista no `title`/`<details>`. Selos Anulada e "Mais cai" vão à direita.
- **Texto associado ⊕** em teal, mesmo `<details>` + `hx-get .../anexos`
  `toggle once` de hoje. Comando (`secao`) e "mesmo comando/mesmo texto da
  anterior" mantidos como na 5G.2.
- **Resposta:** `<fieldset>` (legend `sr-only` "Sua resposta") com dois radios
  `name="resposta"` estilizados como círculo grande teal; Alpine
  `x-data="{ r: null }"` e `:disabled="!r"` no Responder (sem JS o botão fica
  habilitado). POST `/q/correcao` inalterado no servidor; só tratar resposta
  ausente com fragmento amigável em vez de 422. Extrair o form numa macro
  `form_resposta(chave)` em `_componentes.html`, usada pelo card e pelo
  "Tentar de novo" de `_correcao.html` (hoje duplicado).
- **Barra de ações (SVG inline, sem lib):** só o que existe — Estatísticas
  (→ `/materias/<materia_id>`), Questões parecidas (toggle do painel que hoje
  está no rodapé), Caderno PDF (só quando há `link_pdf`), Notificar erro
  (`mailto:` do canal de remoção do `/sobre`, assunto com o ID curto). Nada de
  botão falso (gabarito comentado, aulas, anotações). Linha "Fonte: CEBRASPE"
  fica (crédito obrigatório, ADR-033, e testada).
- **Mobile:** barra cinza e metadados quebram linha; ações em 2 colunas.

### ID curto (5H.1)

- `questoes_servico.codigo_curto(chave)` → `"Q" + sha1(chave)[:8].upper()`
  (mesma família do `dom_id` em `rotas_web.py:32`, reaproveitar o hash).
- Campo novo `codigo: str` em `QuestaoResumo` (aditivo no contrato; reexportar
  `site/openapi.json` com `python site/scripts/exportar_openapi.py`).
- `GET /q/{codigo}` (padrão `Q[0-9A-F]{8}`) → 301 para a URL canônica
  `/q/<concurso>/<caderno>/<numero>`. Resolução: mapa em memória montado uma
  vez das chaves (`site/app/cache.py`), invalidado junto do resto do cache.
- Teste guarda: as 2.800 chaves geram 2.800 códigos distintos.

### Filtros

```
 Questões de Concurso                         (breadcrumb: Início / Questões)
 Sobre administração geral                    (subtítulo quando há 1 matéria)
┌─────────────────────────────────────────────────────────────────────────┐
│ [Palavra-chave 🔍] [Matéria ▾1] [Assunto ▾] [Subassunto ▾] [Banca ▾] [Órgão ▾] │  simples
│ [Ano ▾] [Concurso ▾] [Cargo ▾] [Nível ▾] [Conhecimento ▾]               │  avançado
│ Excluir questões   ☐ Anuladas  ☐ Fora do edital  ☐ Já resolvidas*       │
│ Questões com       ☐ Texto associado  ☐ Figuras   ☐ Que errei*          │
│                                          Mostrar filtro simples ⊖       │
│ Filtrar por: [Matéria: Administração Geral ⊗]   ↺ Limpar   [Filtrar]    │
└─────────────────────────────────────────────────────────────────────────┘
 * desabilitado (cinza) sem login, como no Gran
```

- **Dropdown** (reaproveita o `Alpine.data("faceta")` de
  `lista_questoes.html`): botão com título e "N selecionado(s)"; painel
  absoluto `w-72` com "Busca rápida" + lista de checkbox rolável (`max-h-72`),
  `@click.outside`/`Esc` fecham, foco volta ao botão. Grade
  `grid-cols-2 md:grid-cols-3 xl:grid-cols-6`; no mobile o painel ocupa a
  largura toda. Checkbox marcado continua no DOM com `name` (regra da 5G.4).
- **Aplicação:** form com `hx-trigger="submit"` (sai o `change`), mesmo
  `hx-get="/questoes"`, `hx-target="#lista-conteudo"`, `hx-push-url`,
  `hx-history="false"`. Página volta a 1 (o form não manda `pagina`).
- **Recontagem:** ao fechar um dropdown, dispara `recontar`; um elemento oculto
  faz `hx-get="/questoes/facetas"` com `hx-include="#form-filtros"` e recebe só
  `_dados_facetas.html` com `hx-swap-oob` (o store já relê no
  `htmx:afterSettle`). Rota nova fina em `rotas_web.py` sobre
  `questoes_servico.obter_facetas` (mesma montagem de `FiltroQuestoes` da
  rota `/questoes` — extrair para uma função `_filtros_da_query`).
- **"Filtrar por:"**: chips da seleção do form (store Alpine `selecao`,
  inicializado de `#dados-selecao`; rótulo vem da própria faceta). × desmarca
  (pendente até Filtrar). Os chips do servidor (`_chips`) ficam num
  `<noscript>` para quem está sem JS (o teste de "um chip por valor" continua
  valendo).
- **Limpar** = link `/questoes` (aplica na hora, como hoje).
- **Filtro simples/avançado:** toggle Alpine, lembrado em `localStorage` com
  `try/catch` (padrão do `base.html`); abre no avançado se algum filtro
  avançado estiver ativo.
- **Mapeamento Gran → nosso dado:** Disciplina→Matéria, Instituição→Órgão,
  Assunto→Assunto+Subassunto, Modalidade/Área/Dificuldade → **fora** (não
  temos o dado). "Excluir: Anuladas" = `anuladas=excluir`; "Fora do edital" =
  `fora_do_edital=nao`; "Já resolvidas" = `historico=nao_resolvidas`; "Que
  errei" = `historico=erradas` (os dois de histórico são exclusivos: marcar um
  desmarca o outro). "Só anuladas" sai da UI (continua aceito na URL).
- **Filtros novos no backend (5H.4):** `texto` (palavra-chave) e `com`
  (`texto_base`, `figuras`) em `FiltroQuestoes`, `questoes_repo.buscar_questoes`
  e `obter_facetas`, API `/api/v1/questoes` e `openapi.json`. Palavra-chave:
  `unaccent(enunciado || secao) ILIKE unaccent('%termo%')` (extensão
  `unaccent` criada em `src/sql/schema_estatisticas.sql`; conferir que o
  GRANT/`criar_schema` não a afeta). Termo que casa `^Q[0-9A-F]{8}$` redireciona
  para a questão (atalho do ID curto).
- **Fora do escopo:** abas Objetivas/Exercícios, "Salvar filtros", "dos meus
  cadernos/simulados", dificuldade.

### Cor (5H.1)

- `tailwind.config.js`: `colors: { destaque: colors.teal }`; trocar os 39 usos
  de `*-blue-*` em 11 arquivos (templates, `rotas_web.py`, `estilos/entrada.css`
  — `.btn-primario`, `.campo`, `.link`) por `*-destaque-*`, para a próxima
  troca de cor ser uma linha. Ajustar `favicon.svg`/`og.png` se forem azuis.
  Contraste: texto teal em fundo branco usa `destaque-700` (AA).
- Rebuild: `site/bin/tailwindcss -i estilos/entrada.css -o app/static/tailwind.css --minify`
  (o `test_tailwind.py` acusa CSS desatualizado).

---

## 3. Sessões

| Sessão | Escopo | Arquivos principais |
|---|---|---|
| 5H.1 | Token `destaque` (teal) no site todo + ID curto (`codigo`, `/q/{codigo}`, teste de colisão, openapi) | `tailwind.config.js`, `estilos/entrada.css`, templates, `modelos.py`, `questoes_servico.py`, `cache.py`, `rotas_web.py` |
| 5H.2 | Card novo: barra cinza, metadados com links, Texto associado, radios + Responder, barra de ações, macro `form_resposta`; `_correcao.html` restilizado | `_card_questao.html`, `_correcao.html`, `_componentes.html`, `_lista_parcial.html` (posição), `questao_detalhe.html`, `simulado_revisar.html` |
| 5H.3 | Filtros no topo: dropdowns, botão Filtrar, "Filtrar por", simples/avançado, rota `/questoes/facetas`, Excluir/Questões com com os filtros existentes | `lista_questoes.html`, `_lista_parcial.html`, `rotas_web.py` |
| 5H.4 | Backend dos filtros novos: `texto` (unaccent) e `com`, atalho do ID na palavra-chave, API + openapi | `modelos.py`, `questoes_repo.py`, `questoes_servico.py`, `api/v1/rotas_questoes.py`, `src/sql/schema_estatisticas.sql` |
| 5H.5 | Validação no Chromium headless (desktop 1280 e mobile 390), atualizar `guia-teste-navegador.md` §2, ADR-035, `CLAUDE.md` §5 | docs |

**Pronto quando:** o card da lista, do detalhe e da revisão do simulado segue o
layout acima em teal; toda questão tem ID curto único e `/q/<ID>` abre a
questão; filtrar por 2 matérias + 1 órgão + "excluir anuladas" + palavra-chave
só busca ao clicar Filtrar e dá o mesmo total que o SQL; nenhum `blue-` sobra
nos templates; ruff e pytest verdes.

## 4. Verificação

- `cd site && pytest` + `ruff check .` (+ suíte da raiz se tocar `src/sql`).
- Testes novos/ajustados em `site/tests/`: `test_web.py`
  (`data-assunto-topo` antes de `data-comando`, ordem mantida; radios e
  Responder; ID curto no card; `/q/{codigo}` → 301; Responder sem resposta não
  dá 422), `test_filtros_multi.py` (form sem `change` no `hx-trigger`;
  `/questoes/facetas` devolve só o OOB; `texto` e `com` contra SQL),
  colisão do ID curto, `test_openapi*` com o contrato reexportado,
  `test_tailwind.py` com o CSS refeito.
- Navegador (Chromium headless, `uvicorn app.main:app` em `site/`): abrir/fechar
  dropdown, buscar dentro dele, marcar e ver o chip, recontagem ao fechar,
  Filtrar, voltar do navegador, responder certo/errado/tentar de novo, abrir
  texto associado, console sem erro de JS, 390 px sem rolagem horizontal.
