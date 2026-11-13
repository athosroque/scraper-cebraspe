# O que o edital cobra, e quanto disso cai

Este projeto reúne os editais, as provas e os gabaritos dos concursos do CEBRASPE, liga cada linha do conteúdo programático aos assuntos que de fato aparecem nas provas, e publica o resultado como um site de questões.

<div class="de-para">
<figure class="de-para__peca de-para__peca--edital">
<span class="de-para__fonte">No edital do STM de 2025, analista judiciário administrativo</span>
<p class="de-para__texto">Licitações e contratos administrativos: legislação pertinente; Lei nº 14.133/2021; elaboração e fiscalização de contratos; papel do fiscalizador do contrato… — um bloco com 14 itens, numa lista de 53 blocos do edital.</p>
</figure>
<figure class="de-para__peca de-para__peca--no">
<span class="de-para__fonte">Virou este nó da árvore de assuntos</span>
<p class="de-para__caminho"><span class="de-para__nivel">Direito Administrativo</span><span class="de-para__nivel">Contratos administrativos</span><span class="de-para__nivel">Lei nº 14.133/2021</span></p>
</figure>
<figure class="de-para__peca de-para__peca--prova">
<span class="de-para__fonte">E pesa, na prova desse cargo</span>
<p class="de-para__texto"><span class="de-para__numero">16,2%</span></p>
<p class="de-para__detalhe">11 das 68 questões do caderno. É o assunto mais cobrado do cargo.</p>
</figure>
</div>

Essa passagem — linha de edital, nó de assunto, peso na prova — é o que o projeto automatiza. Esta página resume o problema, a solução e o estágio atual; as outras páginas da seção detalham a arquitetura, os números, as decisões principais e o roadmap.

<a href="scraper-cebraspe-executivo.pdf" class="md-button so-tela">Baixar esta visão em PDF</a>

## O problema

Quem estuda para um concurso do CEBRASPE precisa saber o que mais cai na prova. O edital, porém, lista centenas de itens, e a banca não diz quais deles vão cair em cada certame. As questões de provas anteriores ficam em PDFs, sem ligação com o item do edital a que se referem. Na prática, o candidato resolve questões soltas, sem saber se o assunto é recorrente, se o edital o cobra ou quanto da prova ele representa.

## A solução

O projeto automatiza essa ligação em etapas:

1. **Coleta.** Um robô percorre a lista de concursos encerrados, baixa os editais, as provas e os gabaritos, e confere se cada arquivo é um PDF válido, sem baixar o mesmo arquivo duas vezes.
2. **Taxonomia do edital.** Um modelo de linguagem (LLM) lê o conteúdo cobrado no edital e propõe a lista de matérias, assuntos e subassuntos. Um humano revisa o resultado antes de ele entrar no banco.
3. **Questões e gabarito.** O texto das provas é separado em questões, com o enunciado, as alternativas e o gabarito, por leitura direta do PDF, sem LLM.
4. **Classificação.** Cada questão é ligada aos nós da árvore de assuntos. O LLM só escolhe entre opções fechadas, e o cálculo de quais assuntos estão ou não no edital é feito por regra.
5. **Estatísticas.** Com as questões classificadas, o sistema calcula o que mais cai na prova, o que o edital cobra, o cruzamento entre edital e prova e o desempenho de cada candidato.
6. **Site de questões.** As questões aparecem com filtros por matéria, assunto, banca, ano e órgão. Há contas com login Google, histórico de respostas e simulado. No simulado, as questões certo ou errado seguem a regra do CEBRASPE: uma resposta errada anula uma certa.

## Para quem

- **O estudante** que quer estudar pelo que cai, com o edital como referência.
- **O curador**, que é o dono do projeto. Ele aprova a taxonomia de cada edital e decide as mudanças na árvore de assuntos que o LLM propõe.
- **Quem avalia o portfólio** de Data Science e Data Engineering, para ver como o projeto foi construído.

## O que o projeto mostra

- **Engenharia de dados.** Coleta reexecutável, cargas idempotentes (que podem rodar de novo sem duplicar dados) e um banco Postgres próprio com modelagem dimensional (star schema).
- **LLM com controle de custo e revisão humana.** O modelo só faz tarefas delimitadas, com lista fechada de opções e checagens determinísticas depois. Cada chamada é registrada para auditoria e para medir o custo.
- **Modelagem de domínio.** Uma árvore de assuntos curada, em que um item do edital e uma questão apontam para os mesmos nós, e as estatísticas somam os resultados subindo na árvore.
- **Testes e documentação viva.** Testes automatizados e uma documentação gerada a partir do próprio código, que é verificada a cada mudança.

## Onde está hoje

O piloto com cinco concursos de 2025 foi validado do início ao fim, da coleta ao site. A coleta dos concursos de múltipla escolha de 2025 está em andamento. Os números atuais, como concursos, questões e custo de LLM, estão em [Números](numeros.md). O que vem a seguir está em [Roadmap](roadmap.md).

<div class="grid cards so-tela" markdown>

-   :material-sitemap-outline: **[Arquitetura](arquitetura.md)**

    ---

    Como as peças se encaixam, da listagem do CEBRASPE até o site, em diagramas.

-   :material-chart-bar: **[Números](numeros.md)**

    ---

    Concursos, questões, cargos e custo de LLM, lidos do banco e atualizados a cada geração.

-   :material-scale-balance: **[Decisões principais](decisoes.md)**

    ---

    As escolhas que mais pesam no projeto, com o problema, a decisão e o trade-off de cada uma.

-   :material-map-marker-path: **[Roadmap](roadmap.md)**

    ---

    O que já foi entregue, o que está em andamento e os próximos passos.

</div>
