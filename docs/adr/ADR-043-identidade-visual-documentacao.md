# ADR-043: Identidade visual do site de documentação ("folha de leitura ótica")

- **Status:** Aceito
- **Data:** 2026-11-13
- **Etapa:** 10, sessão P1 (KAN-103; plano em `plano-etapa-10.md`)
- **Decisores:** Dono do produto
- **Relaciona-se com:** ADR-040 (MkDocs Material, `font: false` e `--strict`), ADR-041
  (páginas técnicas geradas de `src/registro/`), ADR-035 (formato Gran em teal, no site
  de questões — outro front, outra identidade)

---

## 1. Contexto

O site de documentação nasceu com o tema Material em paleta neutra de zinco (ADR-040),
escolhida por legibilidade. Ele cumpre a função técnica, mas não tem identidade: é o
tema de prateleira que qualquer projeto gera, e não diz nada sobre o assunto.

Em 2026-11-13 o dono decidiu transformar o projeto em portfólio público (Etapa 10):
repositório aberto, documentação como vitrine e os dois fronts redesenhados, a
documentação primeiro. A partir daqui o site de documentação é lido por quem avalia o
trabalho, não só por quem o mantém.

A direção foi construída com a skill `frontend-design`, que exige plano de design
revisado contra o brief antes do código, e lista os padrões em que o design gerado por
IA costuma cair.

## 2. Decisão

**Direção "folha de leitura ótica".** O vernáculo vem do material impresso de concurso:
caderno em preto sobre branco, item de edital numerado, folha de leitura ótica com
marcas de registro nos cantos, pasta de arquivo em ocre. Nada imita a identidade do
CEBRASPE: o site afirma que não tem vínculo com a banca, e usar a marca dela
contradiria isso.

1. **Preto e branco reais, um acento só.** `#ffffff` e `#000000` no modo claro, o
   negativo exato no escuro (`#000000` e `#f2f2f0`), sem cinza-quase-preto fazendo papel
   de preto. O único acento é o ocre de pasta de arquivo: `#92670a` no claro, `#e8b931`
   no escuro. Nada mais no site é colorido.
2. **Spectral no texto, IBM Plex Mono só em código.** Serifada de talho forte, entrelinha
   1,75 e coluna de 68 caracteres no texto corrido; tabela, diagrama e bloco de código
   continuam usando a largura inteira. Mono em rótulo pequeno é enfeite, e não entra.
3. **O Mermaid fica fora da fonte web.** `--md-mermaid-font-family` aponta para a fonte
   do sistema. O motivo é o do ADR-040: o Mermaid mede o rótulo antes de a fonte web
   carregar, e o texto saía do quadro. A fonte web é carregada por `@import` no
   `tema.css`, com `font: false` mantido no `mkdocs.yml`.
4. **Raio por hierarquia.** Réguas e listas sem raio, código inline 2px, bloco de código
   e tabela 4px. Um raio único em tudo apaga a hierarquia.
5. **Os cartões viram lista com régua.** Nas páginas de abertura, os cartões do Material
   perdem a caixa e ficam separados por uma régua. Seis caixas idênticas escondiam a
   diferença entre os caminhos; a lista mostra. Vale para todas as páginas de abertura,
   por CSS, sem editar os `.md`.
6. **Herói da visão executiva: o de-para.** A página abre com uma passagem real, lida do
   banco: o bloco do edital do STM de 2025, o nó da árvore em que ele caiu e o peso do
   assunto na prova daquele cargo (11 de 68 questões, 16,2%). A terceira peça é a única
   com fundo de acento. É o projeto inteiro em três peças, no lugar de um número grande
   com rótulo pequeno.
7. **Diagramas na mesma paleta.** As `classDef` do Mermaid passam a ocre com alfa
   (interno) e cinza (externo), em `docs/executivo/arquitetura.md` e em
   `scripts/gerar_docs.py`. Alfa em vez de cor sólida porque o mesmo valor precisa
   funcionar no modo claro e no escuro: o SVG do Mermaid fica em shadow root, e o CSS do
   tema não o alcança.
8. **Numeração de seção só onde há sequência.** A classe `.secoes-numeradas` existe para
   as páginas de processo (pipeline, runbook), e não é global: numerar o que não é
   sequência informaria algo falso.
9. **Papéis separados entre as duas aberturas.** O `docs/index.md` é o roteador e o
   `docs/executivo/index.md` é a apresentação. Em vez de remover uma delas, saiu o
   parágrafo técnico do `index.md`, que repetia o que a visão executiva e o guia do
   pipeline já contam.

O piso de qualidade é parte da decisão, não um extra: responsivo até a largura de
celular, foco visível no teclado em ocre, `prefers-reduced-motion` respeitado e contraste
conferido nos dois modos.

## 3. Alternativas descartadas

- **Direção "mesa de curadoria"** (papel frio, tinta grafite, acento índigo e marca-texto
  amarelo, Literata e Inter). Boa, e mais próxima do tom de estudo do site de questões.
  Descartada pelo dono em favor do tom de arquivo normativo, que combina com ADRs,
  regras e trilha de auditoria — o que esta documentação de fato é.
- **Manter o tema zinco do ADR-040.** Legível, mas é o resultado padrão: não diz nada
  sobre o assunto e não serve de vitrine.
- **Fundo creme com serifada de alto contraste e acento terracota.** É hoje o padrão mais
  reconhecível de página gerada por IA. O branco e o preto reais existem justamente para
  não cair nele, e são coerentes com a impressão a laser do caderno de prova.
- **Numerar as seções de todas as páginas.** Numeração é informação de sequência; ligada
  em tudo, vira enfeite.

## 4. Consequências

- O `tema.css` passa a carregar duas famílias do Google Fonts por `@import`. Sem rede, a
  página cai no fallback (Georgia e mono do sistema) e continua legível; o PDF executivo,
  gerado pelo Chromium do Playwright, depende da mesma rede para sair com a Spectral.
- O teste `test_pipeline_mermaid_tem_arestas_e_portao` deixou de fixar o hex do portão:
  a cor é decisão de tema, e travá-la num teste de estrutura obrigaria a mudar o teste a
  cada troca de paleta.
- O CSS do herói (`.de-para`) só existe para a visão executiva. Se outra página quiser o
  mesmo tratamento, o bloco é reaproveitável como está.
- O site de questões continua em teal (ADR-035). As duas identidades convivem até a
  sessão 10/P4 decidir o que muda lá.
- O cache do Cloudflare guarda o CSS por 4 h: depois de publicar, a primeira visita pode
  precisar de Ctrl+Shift+R para ver o tema novo.
