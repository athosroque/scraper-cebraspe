# ADR-037: Escopo do site no inventário (o que fica fora) e correção da coleta

## Status
Aceito (implementado e validado em 2026-10-09)

## Data
2026-10-09

## Contexto

O `inventario/RELATORIO.md` da Etapa 8.0 listava 55 concursos de 2020+ em
"Alertas e Casos Especiais": 10 sem edital de abertura e 46 sem caderno ou sem
gabarito. Os alertas saíam só do texto do link, e não estava claro quais
concursos de fato não têm arquivo e quais foram mal classificados.

Em 2026-10-08 as 55 páginas foram abertas ao vivo (Playwright, todos os `<a>`
da página):

- A contagem de PDFs bate **exatamente** com o `concursos.jsonl` nas 55. O
  scraper não perdeu nenhum arquivo; fora PDF, só há versões acessíveis
  (`.html` Vlibras, `.mp3`, `.docx`) e links de consulta.
- **9 alertas eram falsos** (classificador):
  - SEBRAE (5): a abertura é "Comunicado nº 1 – Abertura", e o caderno
    discursivo é "QUESTÃO DISCURSIVA (ESTUDO DE CASO) – PERFIL N", sem a
    palavra "prova".
  - AGSUS_25_CCE, AGSUS_25_EC, AGSUS_26_RD, AGU_23_ESTAGIARIO: o PDF "PROVA E
    GABARITO DEFINITIVO" traz as questões e o gabarito de cada uma, mas era
    contado só como gabarito. O mesmo formato ("PROVA OBJETIVA (P1) E
    GABARITO PRELIMINAR COM JUSTIFICATIVAS") aparece em mais 11 concursos
    (CAESB_24, que é ME, PC_DF_24_ADM, TC_DF_23...). Em 8 deles a prova
    objetiva ficava fora do lote sem alerta nenhum.
- Os outros 46 eram verdadeiros, por motivos diferentes: prova ainda não
  aplicada (26), concurso cancelado (4), seleção só por títulos (4), página
  vazia (1), só discursiva (o padrão de resposta faz o papel do gabarito: 4),
  discursiva sem caderno publicado (2), exame de certificação (1) e página só
  de curso de formação (4).
- Também havia "Justificativas de alterações de gabarito" e comunicados de
  recurso contados como gabarito (~370 links), e editais que só **citam** o
  edital de abertura ("Edital nº 21 – Prorrogação … do edital de abertura")
  contados como abertura.

## Decisão

1. **Fonte única do que fica fora do site:** `inventario/exclusoes.json`
   (versionado, editado à mão), com `slug`, `categoria` e `motivo`. Ele é lido
   por `src/inventario.carregar_exclusoes`, que valida a categoria contra
   `CATEGORIAS_EXCLUSAO`, exige motivo e recusa slug repetido. As categorias
   são:
   - `cancelado`
   - `sem_prova`
   - `pagina_vazia`
   - `discursiva_sem_caderno`
   - `nao_e_concurso`
   - `curso_formacao`

   O `--mapear` e o `--reclassificar` aplicam a lista (`aplicar_exclusao`).
   Concurso listado fica `incluir=false` com `exclusao: {categoria, motivo}`.
   Os demais ficam `incluir=true` (decisão do dono: o restante entra e a
   coleta é corrigida).
2. **Concurso excluído não é buscado de novo.** O `--mapear` pula o concurso,
   mesmo com `--refazer`. Ele também não entra na amostra de formato nem em
   lote (a 8.1 seleciona só `incluir=true`) e sai dos alertas do relatório,
   que ganha a seção "Fora do Site" com o motivo.
3. **Curso de formação fica fora do site** (decisão do dono, 2026-10-09). A
   prova cobra o conteúdo do curso, não o edital, então não cabe em "edital ×
   prova". Isso vale em dois níveis:
   - as 4 páginas só de curso de formação (ANEEL_25_CF, ANS_25_CF,
     ANTAQ_25_CF, MTE_25) entram na lista de exclusões;
   - dentro de concurso incluído, o PDF com "curso de formação" no link fica
     no inventário, mas não conta nem vai para o lote (`pdf_vai_para_o_site`).
     São 97 PDFs em 19 concursos (INSS_22, PRF_21, ANAC_23…). **Esses
     concursos entram no site**: edital, cadernos e gabaritos do concurso são
     coletados; só a prova do curso de formação fica de fora.
   - Concurso de ingresso com nome de curso (PM_DF_25_CFO, PM_PA_23_CFO/CFP,
     CBM_PA_23_CFO/CFP) é concurso normal e entra inteiro. O alerta
     `curso_formacao` compara o segmento `CF` do slug, não a substring `_CF`.
4. **Prova ainda não aplicada não é pendência.** O alerta `aguardando_prova`
   vale para concurso não encerrado sem caderno, gabarito ou padrão; ele
   substitui `sem_caderno` e `sem_gabarito`. Esses concursos entram quando o
   remapeamento mostrar a prova.
5. **"Sem gabarito" só com caderno objetivo.** Concurso só discursivo tem
   padrão de resposta, não gabarito.
6. **Correções do classificador** (`classificar_link_pdf`), validadas com os
   textos reais:
   - Tipo novo `caderno_com_gabarito`, que conta como caderno objetivo e como
     gabarito. O parser da 8.1/8.M tem de ler esse layout ("ITEM 1 GABARITO:
     CERTO …", "1 J2418111 - ERRADO | …").
   - Gabarito citado por justificativa, recurso, prorrogação, consulta ou link
     vira `administrativo`. A exceção é o título que começa com "gabarito": o
     nome do cargo pode ter "recursos" ("SALAS DE RECURSOS").
   - O edital de abertura exige "abertura" logo depois de "Edital/Comunicado
     nº N" e recusa "abertura do/da/de…" (prazo, link, portões). Isso aceita
     "Comunicado nº 1 – Abertura" e "Edital nº 1 – Abertura, conforme
     retificações".
   - "QUESTÃO DISCURSIVA …" no início do título vira caderno discursivo.
7. **Banco:**
   - `inv_concurso` ganha `categoria_exclusao` e `motivo_exclusao`;
   - `inv_pdf` ganha `curso_formacao`;
   - `vw_inventario_ano` ganha `concursos_fora_do_site`.

## Consequências

- O relatório fica com 0 alertas reais. Os 16 excluídos aparecem com motivo,
  e os 26 que aguardam prova ficam em seção própria. Quem abrir o relatório
  depois não refaz essa verificação.
- Mudança no mesmo corpus (18.248 PDFs, reclassificação offline):
  - `gabarito`: 3.329 → 2.803;
  - `caderno_com_gabarito`: 0 → 158;
  - `caderno_discursivo`: 1.015 → 1.037;
  - `edital_abertura`: 525 → 509;
  - `administrativo`: 8.478 → 8.855.

  A amostra de formato perdeu as 4 páginas de curso de formação (79
  concursos: 39 CE, 40 ME). Os cadernos ME de calibração não mudaram, e o
  piloto continua com 2.800 questões.
- Para tirar um concurso do site, basta acrescentar uma linha no
  `exclusoes.json` e rodar `--reclassificar`. Para devolver, basta apagar a
  linha. O teste `test_arquivo_real_bate_com_o_inventario` garante que a
  lista e o `concursos.jsonl` concordam.
- Concurso novo só de curso de formação aparece como `sem_caderno` (todo PDF
  de prova é de curso de formação), e o dono decide se entra na lista.
