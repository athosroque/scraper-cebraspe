# KAN-88 (M11): heranças de títulos genéricos já gravadas

Somente leitura: nada foi alterado em `canonico/arvore.json`. Gerado em 2026-11-03 sobre
os 7 editais de `revisao_piloto/`.

## Como a herança acontece de fato

- A chave do item de matéria é só `normalizar(título)`. Dois editais com o mesmo título
  genérico usam **a mesma chave** e, portanto, o mesmo mapeamento. Isso não passa pelo passo
  determinístico: é compartilhamento por chave, e só se desfaz na curadoria.
- Nos níveis assunto e subassunto a chave inclui o bloco-pai, que costuma ser específico
  do edital. A herança entre editais só ocorre pelos ramos de nome e de memória (P52, P73),
  e é isso que a M11 (P78) barra.

## Itens genéricos com mapeamento (55 linhas; só as relevantes)

| Edital(is) | Chave | Aponta para | Origem/status | Veredito |
|---|---|---|---|---|
| BANRISUL_25, STM_25, TCU_25_TEFC | `legislacao` (matéria) | Legislação Específica | semente/aprovado | **Errado para o BANRISUL_25**, legítimo para STM e TCU. O bloco do BANRISUL traz políticas para mulheres, igualdade racial e LGPD, que a D2 diz que não são Legislação Específica; STM (lei do órgão, RISTM, CNJ) e TCU (regimento interno) são normas do órgão. |
| BANRISUL_25 | `estrategia` (matéria) | Administração Geral › Gestão estratégica | regra/aprovado | Legítimo: o bloco traz BSC, referencial estratégico e indicadores. Vem do assunto `estrategia` semeado em CD_25_NS, mas o conteúdo confere. |
| BANRISUL_25 | `processo` (matéria) | Tecnologia da Informação › Engenharia de software (aprovado); Direito Processual Civil › Processo (rejeitado) | humano | Legítimo: ciclos de vida, metodologias ágeis. O par com Processo Civil está vetado. |
| SEFA_PR_25 | `administracao\|processo administrativo\|controle` | Processo administrativo › Controle | regra/aprovado | Legítimo: mesmo pai semântico (processo administrativo) do subitem semeado em PF_25_ADM. |
| STM_25, IBAMA_25, PF_25_ADM, SEFA_PR_25, CD_25_NS | demais subassuntos `conceito`, `tipos`, `procedimento`, `planejamento` etc. | nó de mesmo pai | semente/aprovado | Legítimos: a chave inclui o assunto-pai e o destino é o filho de mesmo nome daquele pai. |
| CD_25_NS, PF_25_ADM | assuntos `dados`, `governanca`, `estrategia` | TI › Dados; Adm. Pública › Governança; Adm. Geral › Gestão estratégica | semente/aprovado | Legítimos (chave por bloco do próprio edital). |

Nenhuma outra herança de título genérico entre editais, por regra ou memória, está gravada
hoje. Os editais aprovados (PF, STM, CD, IBAMA, TCU) foram mapeados por semente.

## O que desfazer (decisão do dono)

Só o `legislacao` do BANRISUL_25 é errado, e ele não se desfaz sem afetar STM e TCU, porque a
chave é a mesma. Opções, em ordem de custo:

1. Aceitar o mapeamento da matéria e mapear os 5 assuntos do BANRISUL (todos sem entrada hoje)
   direto para os nós certos, por exemplo
   `venv/bin/python scripts/curar_arvore.py --mapear "legislacao|politica nacional para as mulheres:<NO>"`
   (conferir a chave exata e o nó com `--propostas` antes). O pai continuará "Legislação
   Específica", o que é o problema de contexto da D2.
2. Dar título diferente ao bloco no `<edital>.json` do BANRISUL (por exemplo, "Legislação e
   políticas aplicáveis"), que gera uma chave própria. Exige reprocessar o edital.
3. Mudar a chave natural do item de matéria para incluir o edital quando o título é genérico:
   mexe no writer, no banco e no K22; fora do escopo do card.

Desmapear `legislacao` direto
(`scripts/curar_arvore.py --desmapear legislacao:M-90dd4ae301`) quebra STM_25 e TCU_25_TEFC e
**não é recomendado**.
