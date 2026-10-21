# Árvore Mestre e Curadoria Taxonômica

Estrutura hierárquica canônica de taxonomia (Nó → Matéria → Assunto → Subassunto), persistência em disco, mapeamento relacional em banco de dados e ciclo de vida de semeadura, proposição e curadoria humana.

**Para que serve:** Explicar a arquitetura taxonômica da árvore mestre, detalhar o formato de armazenamento em JSON e sincronização com o banco relacional, e orientar sobre a operação segura de curadoria, semeadura e proposição de novos conceitos. **Quando ler:** Antes de manipular a árvore de conteúdos, executar scripts de curadoria taxonômica, aprovar propostas de fusão ou migração de nós, e implementar regras de mapeamento de editais ou questões.

## 1. Modelo da Árvore Taxonômica

A árvore mestre organiza os conhecimentos cobrados em três níveis hierárquicos estritos: `materia`, `assunto` e `subassunto`. Cada nó de nível `subassunto` deve possuir como pai obrigatório um nó de nível `assunto`, e cada nó de nível `assunto` deve ter como pai um nó de nível `materia`. Nós de nível `materia` atuam como raízes da hierarquia e não podem possuir pai.
Fonte: src/arvore.py:14-16

A fonte primária da verdade da árvore reside no arquivo versionado `canonico/arvore.json`. Esse repositório desacopla a árvore taxonômica do modelo descritivo dos editais, permitindo que a classificação das questões seja realizada de forma estável e independente das variações terminológicas entre bancas e concursos.
Fonte: docs/adr/ADR-030-arvore-mestre-e-site-de-questoes.md:55-70

Cada nó da hierarquia é representado pela estrutura de dados `NoArvore`, contendo os campos `id`, `nivel`, `nome`, `pai`, `origem` (`semente`, `humano` ou `llm`; `regra` existe só nos mapeamentos e nas propostas), `status` (`ativo`, `proposto`, `fundido` ou `aposentado`) e `fundido_em`. Os identificadores de novos nós seguem um padrão determinístico e estável composto por prefixos de nível (`NM-` para matéria, `NA-` para assunto e `NS-` para subassunto) seguidos pelos primeiros 10 dígitos do hash SHA-1 do identificador do pai combinado com o nome do nó.
Fonte: src/arvore.py:22-31, src/arvore.py:73-76

Os nós históricos mantêm integridade referencial imutável: nós fundidos nunca são excluídos da árvore mestre, recebendo `status = "fundido"` e gravando o identificador do nó sucessor em `fundido_em`. Toda consulta ou resolução de apontamentos aciona recursivamente a função `resolver_no`, que percorre a cadeia de fusões até atingir o nó ativo correspondente e previne ativamente a ocorrência de ciclos.
Fonte: src/arvore.py:58-70, src/arvore.py:211-220

Os mapeamentos de itens de edital para a árvore são armazenados sob a chave `mapeamentos` do JSON canônico, onde a chave do item une as chaves naturais do edital separadas por `|` (`materia`, `materia|topico` ou `materia|topico|subtopico`), permitindo relações de cardinalidade N:N em que termos compostos ou matérias híbridas podem apontar simultaneamente para múltiplos nós canônicos da árvore.
Fonte: src/arvore.py:34-38, src/arvore.py:329-335, docs/adr/ADR-030-arvore-mestre-e-site-de-questoes.md:60-65

Para estatísticas quantitativas sobre o volume consolidado de matérias, assuntos e subassuntos ativos na base, consulte os dados canônicos em [docs/executivo/numeros.md](../executivo/numeros.md).
Fonte: docs/executivo/numeros.md:42-54

## 2. Integração com o Banco de Dados

A sincronização entre o arquivo canônico em disco e o banco relacional PostgreSQL é executada pela função `aplicar_arvore` durante a carga do banco. Todos os nós de `canonico/arvore.json` são persistidos na tabela `no_arvore` com seus respectivos metadados, enquanto a tabela normalizada `dim_materia` recebe o flag booleano `nocoes` calculado deterministicamente a partir de sua nomenclatura.
Fonte: src/stats_writer.py:997-1044

As associações entre os itens do edital e os nós taxonômicos são gravadas nas tabelas de ponte relacionais `materia_no`, `topico_no` e `subtopico_no`. Essa carga filtra rigorosamente os apontamentos, inserindo nas pontes apenas os registros com `status = "aprovado"` e resolvendo previamente qualquer nó de destino fundido para o seu nó ativo final por meio de `resolver_no`.
Fonte: src/stats_writer.py:1061-1088, src/sql/schema_estatisticas.sql:74-90

A resolução hierárquica e semântica no banco é centralizada na view `vw_no_caminho`. Através de uma Expressão de Tabela Comum (CTE) recursiva, a view reconstrói o caminho textual hierárquico delimitado por `>` apenas para os nós com `status = 'ativo'`, resolve encadeamentos de nós fundidos apontando para seu `no_efetivo`, e expõe diretamente as chaves de matérias e assuntos ancestrais.
Fonte: src/sql/schema_estatisticas.sql:481-526

A view `vw_no_apelidos` agrega sinônimos e termos de busca para cada nó efetivo. Ela consolida os nomes de nós históricos fundidos que apontam para o nó principal e os nomes de itens de edital que mapeiam de forma unívoca para aquele único nó, descartando termos compostos que apontem para mais de um destino.
Fonte: src/sql/schema_estatisticas.sql:531-565

A distribuição curricular e a incidência programática são modeladas pela view `vw_arvore_edital_por_cargo`, que expande os blocos taxonômicos básicos dos editais para cada cargo respeitando restrições de nível e `cargos_restritos`, integrando as três pontes relacionais (`materia_no`, `topico_no`, `subtopico_no`) e conectando os editais à view `vw_no_caminho`.
Fonte: src/sql/schema_estatisticas.sql:647-726

O cálculo de incidência dos editais é estruturado pela view `vw_edital_cobra_base` e materializado nas views agregadoras `vw_edital_cobra_subassunto`, `vw_edital_cobra_assunto` e `vw_edital_cobra_materia`. O cálculo agrega a ocorrência por `taxonomia_itens.id` distinto em cada nível hierárquico subindo a árvore, o que impede a contagem duplicada quando um item composto mapeia para múltiplos nós irmãos sob o mesmo tema. As versões oficiais filtram apenas concursos com `status_revisao = 'aprovado'`, enquanto as variantes com sufixo `_todas` permanecem disponíveis para inspeção e auditoria.
Fonte: src/sql/schema_estatisticas.sql:731-787

## 3. Ciclo de Vida da Árvore Taxonômica

### Semeadura Inicial

A árvore mestre foi originada na Etapa 5B através do script `scripts/semear_arvore.py`, que migrou deterministicamente os grupos taxonômicos aprovados de `sinonimos.json` para nós de `canonico/arvore.json`, preservando integralmente os identificadores estáveis gerados anteriormente. Cada entrada de origem gerou um mapeamento com `origem = "semente"` e `status = "aprovado"`.
Fonte: scripts/semear_arvore.py:1-12, scripts/semear_arvore.py:35-54, docs/adr/ADR-030-arvore-mestre-e-site-de-questoes.md:66-70

Após a execução da semeadura, o arquivo histórico de sinônimos foi congelado e `canonico/arvore.json` assumiu a condição de única fonte da verdade taxonômica do projeto. Como mecanismo de segurança operacional, o script `semear_arvore.py` bloqueia execuções subsequentes caso a árvore em disco já tenha recebido curadoria e divirja da semente, exigindo intervenção explícita.
Fonte: scripts/semear_arvore.py:57-73, docs/tecnico/regras.md:1162-1166

### Proposição Automatizada e por LLM

Novas operações estruturais podem ser propostas por rotinas determinísticas baseadas em regras de negócio ou por agentes acoplados a modelos de linguagem (LLM). As propostas são registradas em `arvore.propostas` com identificador `P-<sha1>`, tipo de operação (`fundir`, `mover`, `criar`, `remapear`, `aposentar`), argumentos canônicos e justificativa técnica.
Fonte: src/arvore.py:41-49, src/arvore.py:530-586

A detecção por regras determinísticas abrange três cenários principais: detecção de homônimos (`arvore.detectar_homonimos`), que propõe a fusão de nós irmãos que compartilham a mesma chave canônica; detecção de compostos (`arvore.detectar_compostos`), que identifica termos separados por conectivos e gera propostas de remapeamento para os irmãos atômicos seguido da aposentadoria do composto; e detecção de dispersão (`arvore.detectar_dispersos` e `scripts/detectar_dispersao_arvore.py`), que identifica normas e conceitos idênticos espalhados sob pais de matérias distintas.
Fonte: src/arvore.py:779-864, src/arvore.py:867-912, src/arvore.py:1402-1519, scripts/detectar_dispersao_arvore.py:1-24

O subsistema `scripts/propor_arvore.py` processa a curadoria taxonômica auxiliada por LLM com representação compacta de IDs locais (`n1`, `n2`), submetendo as propostas geradas à validação estrita em cópia isolada (`copy.deepcopy`). Qualquer falha semântica, ciclo ou criação de nível inválido invalida a proposta na pré-avaliação antes de qualquer modificação em disco.
Fonte: scripts/propor_arvore.py:1-33, src/arvore.py:588-644

Um princípio arquitetural fundamental estabelece que nenhuma operação com status `proposto` altera o cálculo de incidência nem afeta as tabelas relacionais do banco de dados. Até que ocorra aprovação formal, itens mapeados continuam apontando exclusivamente para nós ativos preexistentes.
Fonte: docs/adr/ADR-029-camada-canonica-sinonimos.md:68-74, docs/adr/ADR-030-arvore-mestre-e-site-de-questoes.md:74-79

### Curadoria Humana e CLI

A tomada de decisão humana é operacionalizada por meio da interface de linha de comando `scripts/curar_arvore.py` e das primitivas de `src/arvore.py`. O utilitário expõe comandos para criação de nós (`--criar`), renomeação (`--renomear`), movimentação entre pais (`--mover`), fusão (`--fundir`), alteração de apontamentos (`--mapear`, `--desmapear`) e julgamento de propostas (`--aprovar-proposta`, `--rejeitar-proposta`).
Fonte: scripts/curar_arvore.py:10-21, scripts/curar_arvore.py:146-231

A aprovação de propostas em lote é processada pela rotina `arvore.aprovar_propostas` sob semântica transacional atômica (tudo ou nada). O motor resolve dependências internas do lote — como criar um nó antes de mover filhos para ele, ou remapear itens antes de aposentar um nó — através de passagens iterativas sobre um snapshot isolado da árvore, abortando integralmente a operação em caso de falha de qualquer invariante.
Fonte: src/arvore.py:657-703, scripts/curar_arvore.py:199-204

Toda alteração bem-sucedida gravada pela CLI `curar_arvore.py` invoca automaticamente a rotina `gerar_relatorio_arvore`, que regenera o artefato visual `arvore.html` com a listagem atualizada de nós ativos, pendências e itens agrupados por concurso e cargo.
Fonte: scripts/curar_arvore.py:306-319

## 4. O que NUNCA fazer (Regras de Segurança)

Nunca edite manualmente o arquivo `canonico/arvore.json` utilizando editores de texto ou rotinas diretas com `json.load`/`json.dump` fora das APIs de `src/arvore.py`. A serialização manual ignora as regras de normalização de chaves (`chave_item`), campos obrigatórios de apontamento e a ordenação estável por linhas, introduzindo inconsistências silenciosas na taxonomia.
Fonte: docs/tecnico/regras.md:1148-1155, src/arvore.py:356-397

Nunca aprove sinônimos, crie nós ou modifique mapeamentos taxonômicos através de instruções `UPDATE` ou `INSERT` executadas diretamente no banco de dados. A fonte canônica da verdade é exclusivamente o arquivo `canonico/arvore.json`, e qualquer alteração realizada à margem do arquivo em disco é irremediavelmente sobrescrita na recarga seguinte do pipeline.
Fonte: docs/tecnico/regras.md:1136-1141, src/stats_writer.py:1023-1035

Nunca execute o comando `python -m scripts.semear_arvore --forcar` após o início da curadoria da base. A flag `--forcar` reconstrói a árvore a partir do estado zero de `sinonimos.json` e apaga definitivamente todas as decisões taxonômicas, fusões, renomeações e ajustes estruturais decididos pelo proprietário do sistema.
Fonte: docs/tecnico/regras.md:1162-1166, scripts/semear_arvore.py:63-67

Nunca execute alterações estruturais na árvore fora do CLI `scripts/curar_arvore.py` ou das funções de manipulação em `src/arvore.py`. Toda operação humana executada por esses canais nasce com status aprovado ou ativo, e qualquer violação de regra de validação cancela a execução sem persistir dados inválidos em disco.
Fonte: docs/tecnico/regras.md:642-649, scripts/curar_arvore.py:306-314

Nunca tente fundir nós com status aposentado ou que pertençam a níveis taxonômicos incompatíveis. A fusão entre níveis hierárquicos distintos (assunto com subassunto) é restrita aos casos em que o nó de origem não possui filhos ativos, sendo terminantemente proibida a fusão entre nós de nível matéria e outros níveis.
Fonte: src/arvore.py:180-209

Nunca aposente um nó taxonômico que ainda possua nós filhos ativos ou propostos vinculados a ele, ou que mantenha mapeamentos de itens de edital com status aprovado. Qualquer tentativa de aposentadoria de nó em uso levanta exceção de integridade `ArvoreInvalida` para evitar a geração de registros órfãos.
Fonte: src/arvore.py:222-254

Nunca mova um nó para dentro de sua própria linhagem descendente ou para um nó pai de nível taxonômico inconsistente. A função `mover_no` realiza a validação antecipada de ciclos e exige estrita conformidade entre o nível do nó e a hierarquia esperada do novo pai.
Fonte: src/arvore.py:126-165

## Referências e Regras Relacionadas

- Regra de curadoria segura: [P51 - Decisão do dono na árvore só via curar_arvore ou src/arvore.py](../tecnico/regras.md#p51)
- Regra de persistência no banco: [A27 - Nunca aprovar sinônimo ou mapeamento com UPDATE no banco](../tecnico/regras.md#a27)
- Regra de integridade do arquivo canônico: [A28 - Nunca ler ou escrever arvore.json com json.load/dump direto](../tecnico/regras.md#a28)
- Regra de proteção à semeadura: [A29 - Nunca rodar semear_arvore.py --forcar depois da curadoria](../tecnico/regras.md#a29)
- Decisão arquitetural de sinônimos: [ADR-029 - Camada Canônica de Sinônimos com Aprovação Humana](../adr/ADR-029-camada-canonica-sinonimos.md)
- Decisão arquitetural da árvore mestre: [ADR-030 - Árvore Mestre de Assuntos e Site Público de Questões](../adr/ADR-030-arvore-mestre-e-site-de-questoes.md)
- Indicadores globais consolidados: [docs/executivo/numeros.md](../executivo/numeros.md)

---
_Verificado em 2026-10-21 contra commit 6a9e448._
