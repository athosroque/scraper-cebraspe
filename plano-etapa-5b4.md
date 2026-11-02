# Levantamento: validação do edital BANRISUL_25 (TI) e melhorias de extração e mapeamento

Data: 2026-11-02. Escopo: só leitura (nenhum arquivo do repositório editado, sem commit, sem LLM pago, `canonico/arvore.json` intacto: md5 `27608ffd…` antes e depois). Edital: `revisao_piloto/Ed_1_2025_Banrisul_Abertura_atualizado_ate_ret_4.json` (28 chunks, 26 blocos, 4 cargos de TI, `PENDENTE`).

Como medi: chamei as funções reais (`novidades_do_edital`, `classificar_itens`, `canonico.mapear_novos_itens(gravar=False, arvore_mem=…)`) sobre a árvore carregada por `src/arvore.py`, comparei com o texto enviado ao LLM (`.auditoria.json`) e julguei à mão cada um dos 216 pendentes contra a árvore. Scripts e saídas intermediárias estão no mesmo scratchpad (`pend.json`, `julgamento.json`, `sim.txt`, `subarvores.txt`).

Efeito colateral: as funções do projeto escrevem no log de produção, então 6 linhas `[ARVORE] Passo determinístico…` (13:46 a 13:52 UTC) em `logs/scraper_cebraspe.log` vieram destas simulações (todas com `gravar=False`). Dois JSON de saída caíram por engano na raiz do projeto e foram movidos para o scratchpad no mesmo minuto. O `git status` não mudou.

---

## (a) Resumo executivo

1. Os "103 novos" do relatório são **219 itens** (17 títulos de bloco, 86 assuntos e 116 subassuntos escondidos dentro dos assuntos). Depois do passo determinístico, que ainda não foi gravado na árvore, sobram **216**.
2. Pelo meu julgamento manual dos 216: **50 (23%) têm nó equivalente direto** e **124 (57%) cabem num nó existente** (por abrangência, item composto, herança do nó do tópico ou título de bloco). **Só 42 (19%) são conceitos realmente novos**, que se agrupam em uns 14 conceitos.
3. A causa principal da inflação está no desenho do detector: **16 títulos de bloco sem destino travam 135 dos 216 itens (62%)**. Enquanto o pai não tem nó, `novidades_edital` e `mapear_novos_itens` nunca comparam os filhos com a árvore.
4. O rótulo "DISCIPLINA" contradiz a P72 e vem só da apresentação: `novidades_edital` devolve `disciplinas_novas` e `gerar_relatorio_revisao.py` imprime a tag `DISCIPLINA`. Pela regra, esses itens são títulos de bloco que viram assunto.
5. **Falso positivo grave:** o bloco `PROCESSO` (processo de software) casa por nome com `Direito Processual Civil › Processo` (`A-ad3fa21488`). Na próxima vez que o pipeline rodar, o passo determinístico grava esse par como `regra/aprovado`, e os 5 filhos dele vão parar em Direito Processual Civil no LLM.
6. O relatório roda **antes** do passo determinístico (`atualizar_artefatos_revisao`: `gerar_relatorios` → `atualizar_arvore`). Por isso mostra itens que a regra já resolveria. Além disso, `classificar_itens`/`novidades` usam uma equivalência (nome de nó-filho) diferente da de `mapear_novos_itens` (item aprovado de mesmo nome). No SEFA_PR_25, **9 itens** aparecem como "automático por equivalência de nome" mas nunca são gravados e não chegam ao banco.
7. **Extração:** os nomes em cadeia `"A - B"` vêm da reinjeção determinística (`_nome_em_cadeia`, KAN-56): 6 no BANRISUL e **134 no SEFA**. A divisão por ";" é inconsistente (4 tópicos com ";" sem subtópicos) e listas de facetas viram fragmentos ("aplicações", "metas", "físico", "lógico"). Nenhum desses padrões cria conceito novo, mas todos impedem o casamento.
8. As regras determinísticas novas de maior ganho são: destino do título de bloco pelo cargo (TI em 15 de 16 blocos), herança do nó-folha pelo subtópico (**55 dos 116 subassuntos**) e casamento global por nome exato com trava de especificidade (20 no BANRISUL, 15 deles corretos; 127 no SEFA).
9. O LLM de mapeamento, como está, deve propor algo para cerca de 55–70% dos 216 (hipótese). Vai errar ou dizer "nenhum" nos casos entre disciplinas (7 itens de contratos idênticos em Direito Administrativo, LGPD, razões e proporções), nos itens compostos (regra de um nó por item), nos filhos de `PROCESSO` e nos títulos cujo nó natural é um subassunto (o nível matéria só aceita matéria ou assunto).

---

## (b) Tabela priorizada de melhorias

| ID | Problema | Evidência | Correção proposta | Esforço | Ganho esperado | Arquivo(s) |
|---|---|---|---|---|---|---|
| M1 | O relatório é calculado antes do passo determinístico, e a equivalência do relatório diverge da gravada | `atualizar_artefatos_revisao`: `gerar_relatorios` (l.154) antes de `atualizar_arvore` (l.155). O dry-run gravaria 44 mapeamentos e o BANRISUL cai de 219 para 216. SEFA: 9 itens `regra_nome` que `mapear_novos_itens` não grava (ele casa por item aprovado, não por nome de nó-filho), então somem da carga, que só lê `aprovado` | Rodar `atualizar_arvore` antes de `gerar_relatorios`. Uma única função de equivalência, usada pelo relatório, pela tabela do Datasette e pela gravação: ou `mapear_novos_itens` passa a gravar o "filho ativo de mesmo `chave_regra`" (é o que o relatório já promete), ou o relatório deixa de considerar resolvido o que não grava | P | Fim do falso "resolvido" (9 no SEFA). O relatório passa a refletir o estado gravado | `scripts/atualizar_revisao.py`, `src/canonico.py`, `src/novidades_edital.py`, `src/mapeamento_revisao.py` |
| M2 | Título de bloco genérico casa com assunto homônimo de outra disciplina e é aprovado automaticamente | Dry-run: `processo → A-ad3fa21488 Direito Processual Civil › Processo (regra, aprovado)`. Os 5 filhos (Ciclos de vida, Metodologias ágeis…) passam a ter Direito Processual Civil como único candidato no LLM (log do dry-run: "Tópico \| Direito Processual Civil: 2 itens") | Título → assunto por nome só com o assunto **na disciplina inferida do contexto** (M4) ou com nome de 2 ou mais tokens significativos. Caso contrário, `proposto` (ou pendente). Lista de títulos genéricos que nunca casam sozinhos (PROCESSO, ARQUITETURA, CONCEITOS BÁSICOS, LEGISLAÇÃO, ESTRATÉGIA…) | P | Evita um erro aprovado silenciosamente e 5 itens desviados agora. Protege os próximos editais de TI | `src/canonico.py` (`mapear_novos_itens`, ramo de matéria), `src/novidades_edital.py`, `src/mapeamento_revisao.py` |
| M3 | O rótulo "DISCIPLINA nova" contradiz a P72 e engana o dono | `novidades_edital.py` l.151 (`disciplinas.setdefault`) → `disciplinas_novas`. `gerar_relatorio_revisao.py` l.447 imprime `novo-tag DISCIPLINA`. `mapeamento_revisao` usa `nivel="disciplina"`. O contador "103" esconde 116 subassuntos | Tag "TÍTULO DE BLOCO sem destino (vira assunto)", com "destrava N itens". Cabeçalho com itens (219) e entradas (103). Renomear a chave para `titulos_sem_destino` (mantendo um alias para não quebrar testes) | P | O dono deixa de achar que precisa criar disciplina. Prioriza as 16 decisões que destravam 135 itens | `src/novidades_edital.py`, `scripts/gerar_relatorio_revisao.py`, `src/mapeamento_revisao.py` |
| M4 | Título de bloco sem destino trava os descendentes | 16 títulos sem nó → 135 dos 216 pendentes (62%) nunca são comparados com a árvore (`filho_equivalente(nos_m=∅)`; `assinatura` devolve `None` sem pai aprovado). Os 4 cargos são "TÉCNICO EM TECNOLOGIA DA INFORMAÇÃO" e 15 dos 16 blocos são TI | **Disciplina inferida pelo cargo:** em chunk `especifico` de cargo cujo nome contém uma disciplina da lista fechada, o título sem destino recebe essa disciplina (`M-41f37f57d8`) como pai provisório para buscar equivalentes dos filhos (relatório e LLM). Gravar como `proposto` até o dono aprovar, ou `regra/aprovado` se ele decidir | M | 135 itens passam a ser comparados com a subárvore de TI. Pelo julgamento, cerca de 100 deles têm nó | `src/novidades_edital.py`, `src/mapeamento_revisao.py`, `src/canonico.py`, `src/mapeamento_llm.py` (`_grupos`/`disciplinas_do_pendente`) |
| M5 | O subtópico abaixo de tópico mapeado para folha fica "novo" | A árvore tem 3 níveis. Quando o tópico do edital aponta para um subassunto, o subtópico não tem filho onde cair. Exemplo: BSC (`S-7a0d161260`, já resolvido) com 10 facetas "novas". A semente já usa a convenção (`banco de dados e ciencia de dados\|administracao de sgbd\|mysql oracle e postgresql → A-2777136b57`) | **Herança de folha:** sem filho equivalente, o subtópico herda o nó do tópico quando esse nó é subassunto. Vale no relatório e no passo determinístico; a origem (`regra` ou `proposto`) fica para o dono decidir | P | 55 dos 116 subassuntos pendentes do BANRISUL (10 imediatos: as facetas do BSC) | `src/canonico.py`, `src/novidades_edital.py`, `src/mapeamento_revisao.py` |
| M6 | O equivalente exato em outro ponto da árvore é ignorado (a busca só olha os filhos do pai) | BANRISUL: 20 itens com `chave_regra` igual a um único nó ativo ou apelido, como os 5 subitens de contratos, idênticos a `Direito Administrativo › Contratos administrativos › …` (`S-81d5169c67`, `S-b1d7bd5120`, `S-0be4918914`, `S-b56196a0f2`, `S-87dabcd1d9`), e a LGPD → `NS-11c10a8ea6`. 15 de 20 corretos; os 5 erros são nomes genéricos ("aplicações", "gestão de processos", "Noções de administração", "Instalação, configuração e administração"). No SEFA são 127 casos (amostra também com erros genéricos, como `ECONOMIA → Atualidades › economia`) | Casamento global com travas: candidato único; 3 ou mais tokens significativos para atravessar disciplina; nome curto só dentro da disciplina inferida; norma (lei nº/ano) casa globalmente, conforme o ADR-030 (KAN-64: "norma vive em um nó só"); lista de rótulos genéricos que nunca casam ("Conceito", "Aplicações", "Definição", "Tipos"…) | M | BANRISUL: cerca de 15 itens com precisão perto de 100% depois das travas. SEFA: dezenas (hipótese) | `src/memoria_mapeamento.py` (apelidos hoje só de nó fundido e da mesma disciplina do pai), `src/canonico.py` |
| M7 | Os nomes em cadeia `"Pai - Filho"` da reinjeção impedem o casamento | `_nome_em_cadeia` (commit c4bfa1e, KAN-56). BANRISUL: 6 itens "Metodologias ágeis e experiência do usuário - Storytelling/Design thinking/…" e um de 3 níveis ("… - Research, user interface - Lean Concept, Discovery Sprint"). SEFA: **134** subtópicos em cadeia | Gravar o **texto próprio** do subitem como nome e a cadeia num campo de contexto (`caminho_origem`), ou fazer o normalizador remover o prefixo quando ele é igual a um subtópico irmão | M | 6 itens aqui e cerca de 134 no SEFA voltam a ser comparáveis ("Design thinking" passa a casar com nó existente) | `src/taxonomia_extractor.py` (**tem alteração não commitada de outra pessoa: coordenar antes**) |
| M8 | A divisão de listas é inconsistente na extração | BANRISUL chunk 17: 3 tópicos-frase com ";" (o maior com 230 caracteres e cerca de 20 conceitos), sem subtópicos. O chunk 19/20/21 dividiu o mesmo padrão em subtópicos. "Cloud computing; virtualização." mantém o ponto final. BSC quebrado em 10 facetas soltas ("aplicações", "metas", "perspectivas"). "Modelagem de dados: físico, lógico e conceitual" → subtópicos "físico/lógico/conceitual". Nos 7 editais há tópicos com ";" sem subtópicos (SEFA 9, BANRISUL 4, STM 4, CD 2) e fragmentos de 1 palavra minúscula (PF 14, BANRISUL 9, CD 8) | Pós-processamento determinístico: tópico sem subtópicos com 2 ou mais partes separadas por ";" → partes viram subtópicos; tirar pontuação final; fragmento de 1 palavra (adjetivo ou faceta) volta para o pai. No prompt: "aspectos de um mesmo conceito (ex.: BSC – conceitos, aplicações, mapa…) não viram subtópicos" | M | Itens compostos passam a casar parte a parte; somem cerca de 13 fragmentos sem sentido no BANRISUL | `src/taxonomia_extractor.py` (coordenar), validador `scripts/validar_taxonomia.py` |
| M9 | O desenho do LLM de mapeamento esbarra nos mesmos problemas | (a) No nível matéria, `selecionaveis_por_tema` ranqueia só pelo nome do título (`contexto` vazio; os subitens não entram no ranking): para SERVIDORES ou CONCEITOS BÁSICOS, os assuntos de TI relevantes não entram. (b) `NIVEIS_ALVO["materia"]=("materia","assunto")`: os nós naturais `Sistemas operacionais A-b7f5d728c0`, `Modelagens de dados A-48c7cb56b8` e `Linguagens de programação A-3408fede43` são subassuntos e não são oferecidos. (c) Candidatos restritos à disciplina do pai: GESTÃO E GOVERNANÇA→TI esconde os 7 nós idênticos de Direito Administrativo, LEGISLAÇÃO→Legislação Específica esconde a LGPD e RACIOCÍNIO LÓGICO esconde `A-d4f5c80605` (Matemática Financeira). (d) "No máximo UM nó" para item composto. (e) O prompt não ensina a herança de folha | (a) Incluir os tokens dos subitens no ranking do nível matéria e colocar a disciplina inferida (M4) no topo. (b) No nível matéria, aceitar subassunto como alvo de título (ou mapear para o assunto pai e dar o subassunto como dica). (c) Somar aos candidatos da disciplina os top-k globais por similaridade (com M6). (d) Permitir até 3 nós em item composto (a árvore já é N:N). (e) Regra no prompt: "sem nó mais específico, o subtópico aponta para o nó do tópico". Rodar o LLM só **depois** de M1, M2, M4, M5 e M6 | M | Menos "nenhum" falso e menos lotes. Hipótese: de cerca de 55–70% para 80% ou mais dos 216 com proposta útil | `src/mapeamento_llm.py` |
| M10 | A UX de revisão faz o dono ler 103 linhas soltas | Lista plana, sem sugestão. "Índices e otimização de acesso" aparece duas vezes (cargos 1 e 2). A tabela `mapeamento_itens` só tem `edital, nivel, item, no_id, no_caminho, origem, status, confianca, justificativa, disciplina`, sem pai, sem chave e sem sugestão. A similaridade simples acerta o nó em 35 de 50 equivalentes no top-1 (70%) e em 40 de 50 no top-3 (80%) | Agrupar por título de bloco, com "destrava N". Separar "travado pelo pai", "sugestão com score ≥ X" e "novo de verdade". Sugestão top-1/top-3 por similaridade sempre visível, sem LLM. Juntar o mesmo item repetido entre cargos (chave + lista de cargos). Colunas `assunto`, `chave`, `disciplina_do_no`, `sugestao_no`, `score` e `cargos` no Datasette, com facetas e consultas salvas ("pendentes por bloco", "sugestões ≥ 0,8") | M | A leitura cai de 103 entradas para cerca de 16 decisões de bloco, mais cerca de 14 conceitos novos, mais a conferência de sugestões | `scripts/gerar_relatorio_revisao.py`, `src/mapeamento_revisao.py`, `scripts/gerar_db_datasette.py` |
| M11 | A chave natural de título genérico é global e herda decisão de outro edital | A chave do item matéria é só `normalizar(titulo)`: `legislacao` → `Legislação Específica` (semente) vale para o BANRISUL, cujo bloco tem políticas para mulheres, igualdade racial e LGPD, conteúdo fora da D2 ("só normas do órgão"). `processo` aprovado agora valeria para qualquer edital futuro | Lista de títulos genéricos cuja decisão não é herdada sem confirmação (ou chave escopada por concurso só nesses títulos) | M/G | Evita erro que se propaga entre editais | `src/canonico.py`, `src/memoria_mapeamento.py` (decisão do dono, toca ADR-026/030) |
| M12 | Normalização sem prefixos e sinônimos comuns | "FUNDAMENTOS DE BANCO DE DADOS" e "Conceitos de Banco de Dados" não casam com `Banco de dados`/`Conceitos e fundamentos`. "Gerenciamento de Backlog" ≠ "gestão de backlog" (já aprovado na semente → `A-6a5ad94fa5`). "Minimum Viable Product (MVP)" ≠ "produto mínimo viável (MVP)" | Ampliar `PADRAO_NOCOES` para "fundamentos de", "conceitos (básicos) de", "introdução a". Pequeno dicionário de sinônimos (gerenciamento→gestão; termos EN↔PT de sigla igual: casar pela sigla entre parênteses quando é única) | P | Uns 4 a 6 itens por edital de TI, com baixo risco | `src/canonico.py` (`chave_regra`) |
| M13 | O dry-run do LLM superestima "sem disciplina" | No dry-run nada é proposto, então tópicos e subtópicos ficam todos em "sem disciplina: <bloco>" com até 120 candidatos por tema, o que não acontece na execução real (cascata) | No dry-run, simular a cascata com a sugestão top-1 (M10) ou relatar "depende do nível acima" | P | Estimativa de custo e de lotes fiel | `src/mapeamento_llm.py` |

Ordem recomendada: M1 → M2 → M3 (correções baratas que tiram ruído e evitam erro aprovado) → M4 + M5 (maior ganho) → M6 + M12 → M10 → só então rodar `mapear_itens_novos` (M9) → M7/M8 na extração (coordenar com quem mexe em `taxonomia_extractor.py`).

---

## 1. Qualidade da extração (BANRISUL, conferida contra `texto_enviado_llm`)

O texto da fonte foi capturado sem falhas (28/28 chunks `sucesso`), e a numeração de 1º nível foi respeitada. Os problemas são de forma:

| Padrão | Exemplos reais | Efeito |
|---|---|---|
| Tópico-frase com ";" sem subtópicos | chunk 17: "Segurança em redes de computadores e técnicas de ataque cibernético, resposta a incidentes, resiliência cibernética; firewalls, IDS, IPS, proxies, NAT e VPN; spoofing, flood, DDoS, phishing; malwares; adware, spyware, backdoors, keylogger, worms, ransonware" (1 tópico); "Aspectos da classificação das informações…; gestão de políticas de segurança"; "Algoritmos de Criptografia…; Certificação Digital; infraestrutura de chaves públicas"; chunk 22 "Cloud computing; virtualização." | Cada um cobre 3 a 6 nós existentes (`A-f2edc4437f`, `A-a72164a20c`, `A-addef0af06`, `S-35ab3a8c71`, `A-5189323947`…), mas vira 1 item "novo". O mesmo padrão foi dividido nos chunks 19, 20 e 21 ("Sistemas operacionais: fundamentos; gestão de processos; …"), o que confirma a inconsistência |
| Facetas de um conceito viram subtópicos soltos | BSC: "principais conceitos", "aplicações", "mapa estratégico", "perspectivas", "temas estratégicos", "objetivos estratégicos", "relações de causa e efeito", "indicadores", "metas", "iniciativas estratégicas" (fonte: "Balanced Scorecard (BSC) – principais conceitos, aplicações, …"); "Modelagem de dados: físico, lógico e conceitual" → "físico", "lógico", "conceitual" | Fragmentos sem sentido isolado. "aplicações" casaria por nome com `TI › Ciência de dados e IA › Aplicações` (erro). A árvore guarda o BSC como **um** subassunto (`S-7a0d161260`) |
| Nome em cadeia da reinjeção (4º nível) | "Metodologias ágeis e experiência do usuário - Conceitos básicos e aplicações", "… - Storytelling", "… - Design thinking", "… - Research, user interface", "… - Research, user interface - Lean Concept, Discovery Sprint", "… - Prototipação", mais o próprio "Metodologias ágeis e experiência do usuário" como irmão | Origem: `reinjetar_subitens_ausentes`/`_nome_em_cadeia` (o LLM descartou 2.3.1 a 2.3.5 e o reparo determinístico reinjetou com o caminho no nome). O prefixo repetido impede casar "Design thinking" |
| Listas desiguais | "Gerenciamento de projetos: conceitos básicos; áreas de conhecimento, projetos, programas, portfólio" (1 subtópico); "Indicadores: Lead Time, Delivery Rate, NPS, …, OKR e KPI" (1 tópico) contra o BSC quebrado em 10 | Mesmo tipo de lista tratado de 3 formas |
| `materia` do LLM inútil | O LLM pôs a lista de tópicos ("Concorrência (…). Redes Locais. Web Services, APIs REST.") ou o 1º tópico ("Programação estruturada", "Índices e otimização de acesso") como matéria, e "" no chunk 22 | Não afeta a carga (usa `materia_normalizada`), mas confunde o `_chunks_da_disciplina` do relatório. Já está sendo corrigido na alteração **não commitada** (`reparar_materia_extraida`; o diff do JSON trocou dois valores por "CONCEITOS BÁSICOS" e "COMPUTAÇÃO EM NUVEM") |
| Repetição entre chunks | "Índices e otimização de acesso" (chunk 10, cargo 1, PERFORMANCE E TUNING; chunk 12, cargo 2, BANCO DE DADOS); "TÉCNICAS E LINGUAGENS DE PROGRAMAÇÃO" e "BANCO DE DADOS" em 2 cargos; DevSecOps em ENGENHARIA DE SOFTWARE e em COMPUTAÇÃO EM NUVEM; "Web Services, APIs REST" (chunk 4) × "Web services e APIs/RESTful" (chunk 15) × "Integração de APIs" (chunk 27) | Repetição legítima do edital (cargos diferentes), mas o dono vê a mesma decisão várias vezes |
| Subitem virando assunto | Não vi caso de nível invertido no BANRISUL: o 1º nível virou tópico e o 2º virou subtópico. O "nível errado" percebido vem do título de bloco ser tratado como disciplina (item 2) | — |

Generalização para os 7 editais (script `padroes.py`):

| Edital | tópicos com ";" sem subtópicos | nomes > 120 caracteres | subtópicos em cadeia " - " | fragmentos de 1 palavra minúscula |
|---|---|---|---|---|
| SEFA_PR_25 (pendente) | 9 | 23 | **134** | 0 |
| BANRISUL_25 (pendente) | 4 | 7 | 6 | 9 |
| PF_25_ADM | 0 | 45 | 1 | 14 |
| STM_25 | 4 | 47 | 0 | 6 |
| CD_25_NS | 2 | 21 | 0 | 8 |
| IBAMA_25 | 0 | 16 | 1 | 4 |
| TCU_25_TEFC | 0 | 4 | 0 | 0 |

## 2. Normalização e detector

### 2.1 Números

- `novidades_do_edital` (estado atual da árvore): 17 títulos, 86 entradas de assunto, `total_itens_novos` 219 (17 + 86 assuntos novos + 116 subassuntos).
- `classificar_itens`: 260 itens distintos, sendo 37 `dono`, 1 `auto`, 3 `regra_nome` (BANCO DE DADOS → `A-e02df9d2b4`, PROCESSO → `A-ad3fa21488` **errado** e GESTÃO DE PROJETOS → `A-2c9c7eb394`) e 219 `sem_equivalente`.
- O passo determinístico em dry-run gravaria 44 mapeamentos em todo `revisao_piloto/` (32 por nome e 12 por memória). Os do BANRISUL: `banco de dados`, `processo` (**errado**), `estrategia → A-fdd929e9b9 Gestão estratégica`, `gestao de projetos`, `engenharia de software|seguranca da informacao → A-8bc51b3a2f` e `estrategia|balanced scorecard bsc → S-7a0d161260`. Depois disso: 16 títulos e **216** itens; `classificar` e `novidades` concordam (216 = 216).
- O log mostra o passo rodando em 2026-11-02 às 13:37 (32/12/839), mas `canonico/arvore.json` é de 2026-10-29 e o `git status` está limpo. Ou seja, esses 44 mapeamentos ainda não foram gravados (só houve execuções que não gravaram). **Hipótese:** o relatório e o `revisao.db` foram regerados por outro caminho que não chama `atualizar_arvore`.

### 2.2 Os 216 contra a árvore (julgamento manual)

| Julgamento | Disciplina (título) | Assunto | Subassunto | Total |
|---|---|---|---|---|
| E: equivalente direto (mesmo conceito, outro nome) | 3 | 26 | 21 | **50** |
| A: cabe em nó existente (abrangência, composto, herança de folha, título genérico) | 12 | 44 | 68 | **124** |
| N: realmente novo | 1 | 14 | 27 | **42** |

Tipos de diferença de nome nos E e A:
- **Paráfrase ou forma:** "Compreensão de estruturas lógicas" × "Estruturas lógicas"; "Redação oficial, conforme Manual…" × "Redação oficial: Manual…"; "Itens gramaticais relevantes para o entendimento dos sentidos dos textos" × "…para a compreensão dos conteúdos semânticos".
- **Prefixo:** "Fundamentos de"/"Conceitos de" (FUNDAMENTOS DE BANCO DE DADOS → `Banco de dados`).
- **Sinônimo:** gerenciamento×gestão (Backlog); EN×PT com a mesma sigla (MVP).
- **Cabeça antes de ":":** "Lógica de argumentação: analogias…" → `A-acff47b763`, cujo filho `S-4e4ac31f38` é o resto.
- **Norma:** "Lei nº 13.709/2018 (…)" → `NS-11c10a8ea6`.
- **Ruído "em DISCIPLINA":** é só a apresentação ("Segurança da Informação em ENGENHARIA DE SOFTWARE" é resolvido por memória no passo determinístico, que ainda não foi gravado).

### 2.3 Divergência entre `novidades_edital`/`mapeamento_revisao` e `mapear_novos_itens`

- **Relatório e Datasette:** item conhecido quando há (a) mapeamento aprovado ou (b) **nó-filho ativo de mesmo `chave_regra`** sob o nó do pai.
- **Gravação (`mapear_novos_itens`):** (1) **outro item aprovado** de mesmo `chave_regra` sob os mesmos nós-pai; (2) memória (decisão aprovada ou apelido de nó **fundido** na disciplina do pai); (3) só no nível matéria, nó de matéria ou assunto de mesmo nome, se for único.
- **Consequência:** o item cujo nome bate com um nó-filho, mas que nunca foi decidido antes, fica "resolvido" no relatório e pendente na gravação. Medido: **SEFA_PR_25, 9 itens** (`administracao publica|governo eletronico`, 3 subitens dele, `administracao|evolucao da administracao`…). O BANRISUL tem 0 hoje (o caso dele são os 3 títulos, que a gravação também resolve).
- **Divergência menor:** no nível matéria, o relatório aceita **qualquer** número de assuntos homônimos (`assuntos_por_regra` devolve um conjunto), enquanto a gravação exige **um só**. Com dois homônimos, o relatório diz "resolvido" e a gravação deixa pendente.

### 2.4 P72 e o rótulo "DISCIPLINA"

A regra é respeitada na gravação: nada cria disciplina, e o título sem equivalente fica pendente. O erro é de apresentação. `novidades_do_edital` põe o título sem destino em `disciplinas_novas` (`novidades_edital.py` l.151), `_bloco_o_que_revisar` imprime `<span class='novo-tag'>DISCIPLINA</span>` (`gerar_relatorio_revisao.py` l.447), e a legenda diz "Novo = nenhum nó equivalente; será preciso criar". Somado, isso induz o dono a pensar em criar disciplina, o que a P72 proíbe. O correto é "título de bloco sem destino: aponte para um assunto ou disciplina existente". Pelo julgamento, 15 dos 16 têm destino: 3 equivalentes diretos e 12 por abrangência, quase todos em TI (`M-41f37f57d8`, `NA-e8ea9374ad`, `NA-870524a5bf`, `A-e02df9d2b4`…).

## 3. O que é realmente novo (42 itens, cerca de 14 conceitos)

| Conceito novo | Itens do edital | Destino sugerido |
|---|---|---|
| Programação orientada a objetos | "Programação orientada à objetos", "Classes, Herança, Composição, Interfaces, Polimorfismo", "orientação a objetos" (ENG. SOFTWARE) | TI › Desenvolvimento de sistemas › (novo subassunto) |
| Boas práticas, SOLID e padrões de projeto | "Boas práticas de programação", "SOLID", "Design Patterns" | TI › Desenvolvimento de sistemas (ou fundir em `A-f57e5aa487` Arquitetura de software: decisão do dono) |
| Estruturas de dados e algoritmos | "estrutura de dados e algoritmos" | TI › Desenvolvimento de sistemas |
| Índices, otimização e tuning de SQL | "Índices e otimização de acesso" (×2), "Otimização de código SQL ANSI…", "Uso de variáveis Bind", "Desempenho e detecção de problemas" | TI › Banco de dados (novo subassunto) |
| Controle de concorrência, recuperação e organização física em SGBD | "Organização física e métodos de acesso", "Concorrência, recuperação e integridade" | TI › Banco de dados (ou em `S-abaaaebdfc` Conceitos e fundamentos) |
| Serviços de diretório (AD/LDAP) | "Serviços de diretório", "Active Directory e LDAP", "Interoperabilidade" | TI › Infraestrutura de TI |
| UX/UI e design de produto digital | "User Experience (UX)", "acessibilidade e usabilidade", "Task Flow", "Metodologias ágeis e experiência do usuário" e as 5 variantes em cadeia, "Técnicas de facilitação… Design Sprints" (11 itens) | TI › Engenharia de software (novo subassunto "Experiência do usuário (UX)"). "Design thinking" já existe em 3 nós por enfoque: o dono decide se UX é um 4º enfoque |
| Inovação e tecnologia no sistema financeiro | título "INOVAÇÃO EM TI NO SISTEMA FINANCEIRO", "Blockchain, IoT, fintechs…", "Transformação Digital", "Estratégias… digitalização de serviços financeiros", "Open finance", "… criptomoedas, pagamentos digitais, digital banking" (6) | TI › (novo assunto) ou dentro de `A-48f6fa3bf6` "Tecnologias emergentes no setor público", renomeado. Decisão do dono |
| Lei nº 13.303/2016 (Lei das Estatais) | "Lei nº 13.303/2016" | Direito Administrativo (norma ausente na árvore; regra "norma em um nó só") |
| Licenciamento de software | "Licenciamento de software" | TI › Governança e gestão de TI |
| Modelo de negócios (Business Model Canvas) | "Modelo de negócios e quadro de modelo de negócios (Business Model Canvas)" | Administração Geral › Gestão estratégica |
| Métricas de produto e ágeis | "Indicadores: Lead Time, Delivery Rate, NPS, Métricas de UX…, OKR e KPI" (composto; OKR já existe em `A-834a863292`) | Administração Geral (OKR) mais um novo subassunto de métricas, ou TI › Engenharia de software |
| Políticas para as mulheres | "Política Nacional para as Mulheres", "Política Nacional de Enfrentamento à Violência contra as Mulheres" | Serviço Social › Políticas Sociais `A-ea208d484c` (precedente D6: Estatuto da Pessoa Idosa) |
| Estatutos da Igualdade Racial | "Estatuto Nacional… Lei 12.288/2010", "Estatuto Estadual… Lei 13.694/2011 (RS)" | Nacional: Serviço Social › Políticas Sociais (ou Direito Constitucional). Estadual: Legislação Específica (norma local). Decisão do dono |

## 4. Efeito esperado do LLM (`mapear_itens_novos`)

Não chamei o LLM. A estimativa abaixo é **hipótese**, apoiada no código e no log do dry-run de 2026-11-02 13:23.

- **Nível matéria (16 títulos, 1 lote por título, 43 a 79 candidatos):** os candidatos são as 43 disciplinas mais os assuntos que compartilham palavra com o **nome do título** (os subitens não entram no ranking). O LLM deve devolver `Tecnologia da Informação` (matéria) na maioria, o que é aceitável, porque os filhos passam a ter os candidatos de TI. Riscos:
  - CONCEITOS BÁSICOS e ARQUITETURA podem receber "nenhum" (o prompt manda responder "nenhum" na ambiguidade).
  - SISTEMAS OPERACIONAIS pode cair em `sistema operacional (Windows)` (`A-4ff1e02efb`), porque o nó natural `A-b7f5d728c0` é subassunto e não é oferecido.
  - INOVAÇÃO EM TI NO SISTEMA FINANCEIRO pode cair em "Tecnologias emergentes no setor público".
- **Tópicos (cerca de 86) e subtópicos (cerca de 116):** com o pai proposto em TI, os 134 a 158 candidatos de TI cobrem a maior parte dos 50 E e dos 124 A. Os E de TI devem sair com confiança "alta". Os A que dependem de abrangência ("Escopo de Variáveis" → Linguagens de programação; "Concorrência (deadlocks)" → Sistemas operacionais) devem sair "media"/"baixa" ou "nenhum", porque o prompt pede o "mesmo conceito".
- **Onde deve errar ou dizer "nenhum":**
  1. **Entre disciplinas:** os 7 subitens idênticos de contratos (o pai GESTÃO E GOVERNANÇA aponta para TI e Direito Administrativo não é oferecido), a LGPD (o pai LEGISLAÇÃO aponta para Legislação Específica) e "Razões e proporções"/"Regras de três" (o nó está em Matemática Financeira). São cerca de 10 itens com equivalente exato perdidos.
  2. **Filhos de PROCESSO:** candidatos só de Direito Processual Civil, então "nenhum" ou proposta absurda (5 itens).
  3. **Compostos:** "um nó por item" faz o LLM escolher uma parte (5 itens).
  4. **Frases longas e fragmentos:** "aplicações", "metas" e "físico" dependem da dica "o pai foi mapeado para", que existe e ajuda.
  5. **Os 42 novos:** "nenhum" correto, com risco de encaixe forçado. Exemplos: POO → Linguagens de programação; Serviços de diretório → "Gestão de identidades, acesso e serviços de autenticação".
- **Total estimado:** proposta para cerca de 120 a 150 dos 216 (55–70%), das quais cerca de 15–25% "media/baixa" que pedem conferência; "nenhum" em cerca de 65 a 95 (42 corretos).
- **Lotes no dry-run:** cerca de 54 lotes listados para o BANRISUL. Na execução real são menos, pela cascata.

Ajustes concretos no desenho (detalhados em M9):
1. Rodar o LLM depois de M1, M2, M4, M5 e M6, para que ele só veja o resto difícil.
2. No nível matéria, ranquear também pelos subitens e aceitar subassunto como alvo, ou o assunto pai com o subassunto como dica.
3. Somar candidatos globais top-k por similaridade (de outras disciplinas) em todos os níveis.
4. Permitir até 3 nós em item composto.
5. Explicitar no prompt a herança de folha.
6. Passar o cargo (`cargo_chunk`) no contexto do item.

## 5. UX da validação (Datasette e relatório)

1. **Rotular certo** (M3): "Título de bloco sem destino (vira assunto)" mais "destrava N itens"; contador com itens e entradas.
2. **Agrupar por título de bloco**, colapsado. Mostrar no topo as 16 decisões de bloco, que destravam 135 itens, e esconder os filhos travados até o bloco ter destino.
3. **Sugestão sem LLM** (similaridade de tokens, como `sim.py`): top-1 com score e caminho, top-3 ao expandir. Medido nos 50 E: 70% de acerto no top-1 e 80% no top-3. Nos A, só 29% sem contexto do pai, o que cresce com M4/M5.
4. **Colapsar duplicatas:** mesmo `chave_regra` em cargos diferentes vira uma linha com a lista de cargos ("Índices e otimização de acesso" ×2; TÉCNICAS E LINGUAGENS e BANCO DE DADOS em 2 cargos).
5. **Esconder ruído:** fragmentos de 1 palavra e facetas ficam numa seção "herdam o nó do tópico" (M5), com um botão de confirmar o lote.
6. **Tabela `mapeamento_itens`:** acrescentar `assunto` (pai), `chave`, `disciplina_do_no` (hoje `disciplina` é o título do bloco, não a disciplina do nó), `sugestao_no`, `sugestao_caminho`, `score` e `cargos`. Criar facetas e consultas salvas ("pendentes por bloco", "sugestões ≥ 0,8", "travados pelo pai").
7. **Comando pronto para a decisão:** junto de cada sugestão, a linha `curar_arvore` correspondente (o dono aprova copiando, sem `UPDATE`, conforme a A27).

## 6. Pipeline

1. **Ordem:** extração → reparos determinísticos (`;`, fragmentos, nome em cadeia) → validação → **passo determinístico** (regra, memória, herança de folha, global com travas, disciplina inferida pelo cargo) → **relatório e Datasette** → LLM de mapeamento (só o resto) → relatório de novo. Hoje o relatório vem antes do passo determinístico (M1).
2. **Automação que mais poupa revisão**, medida no BANRISUL:
   - destino do título pelo cargo: destrava 135;
   - herança de folha: 55 subassuntos;
   - global exato com travas: cerca de 15;
   - normalização de prefixos e sinônimos: cerca de 5.
3. **Aprender com o dono:** a memória (P73) só generaliza com o **mesmo pai**. Uma decisão sobre um título de bloco (ex.: SERVIDORES → Infraestrutura de TI) deveria valer, como sugestão, para o mesmo título em outro edital do mesmo tipo de cargo; hoje vale para qualquer edital, porque a chave é global (M11), sem olhar o cargo. O inverso também vale: o dono rejeitar `processo → Processo (DPC)` precisa virar veto, que a memória já respeita (`rejeicoes`).
4. **Guarda contra aprovação errada automática:** todo `regra/aprovado` que atravessa disciplina ou vem de título genérico deve sair como `proposto` (M2, M6).
5. **Dry-run fiel** (M13), para estimar custo e lotes do LLM.

---

## (c) Itens do BANRISUL que já têm equivalente na árvore (50 diretos; amostra completa)

| Nível | Bloco | Item do edital | Nó alvo (caminho) | ID |
|---|---|---|---|---|
| assunto | LÍNGUA PORTUGUESA | Redação oficial, conforme Manual de Redação da Presidência da República | Língua Portuguesa › Redação oficial: Manual de Redação da Presidência da República | AL-d25ac0285d |
| assunto | LÍNGUA INGLESA | Itens gramaticais relevantes para o entendimento dos sentidos dos textos | Língua Inglesa › Itens gramaticais relevantes para a compreensão dos conteúdos semânticos | AL-f7d4935fd3 |
| subassunto | RACIOCÍNIO LÓGICO | Regras de três simples e compostas | Matemática Financeira › Regra de três simples e composta, proporcionalidades e porcentagens | A-d4f5c80605 |
| assunto | RACIOCÍNIO LÓGICO | Compreensão de estruturas lógicas | Raciocínio Lógico › Estruturas lógicas | A-05d3a2c440 |
| assunto | RACIOCÍNIO LÓGICO | Lógica de argumentação: analogias, inferências, deduções e conclusões | Raciocínio Lógico › Lógica de argumentação (filho: Analogias, inferências… S-4e4ac31f38) | A-acff47b763 |
| assunto | LEGISLAÇÃO | Lei nº 13.709/2018 (Lei Geral de Proteção de Dados Pessoais) | Direito Administrativo › Acesso à informação e proteção de dados › LGPD (Lei nº 13.709/2018) | NS-11c10a8ea6 |
| título | FUNDAMENTOS DE BANCO DE DADOS | FUNDAMENTOS DE BANCO DE DADOS | Tecnologia da Informação › Banco de dados | A-e02df9d2b4 |
| título | INFRAESTRUTURA DE REDES | INFRAESTRUTURA DE REDES | Tecnologia da Informação › Redes de computadores | A-4b13bcdab5 |
| título | GESTÃO E GOVERNANÇA | GESTÃO E GOVERNANÇA | Tecnologia da Informação › Governança e gestão de TI | NA-8a2987f6b8 |
| assunto | MODELAGEM DE DADOS | Modelagem de dados | TI › Banco de dados › Modelagens de dados | A-48c7cb56b8 |
| assunto | BANCO DE DADOS | Modelagem de dados: físico, lógico e conceitual | TI › Banco de dados › Modelagens de dados | A-48c7cb56b8 |
| assunto | FUNDAMENTOS DE BANCO DE DADOS | Conceitos de Banco de Dados | TI › Banco de dados › Conceitos e fundamentos | S-abaaaebdfc |
| assunto | BANCO DE DADOS | Banco de Dados: Oracle 19c, MySQL v8 e MS SQL Server 2019 | TI › Banco de dados › SGBD Oracle, MySQL e PostgreSQL | S-fed7e2d779 |
| assunto | BANCO DE DADOS | SQL/ANSI | TI › Banco de dados › Conceitos e propriedades das transações (ACID); linguagem SQL (padrão ANSI)… | S-551a90e864 |
| assunto | ADMIN. DE BD RELACIONAIS | Tolerância a falhas e continuidade de operação | TI › Infraestrutura de TI › alta disponibilidade e tolerância a falhas | A-d831972bed |
| assunto | PROCESSO | Metodologias ágeis de desenvolvimento | TI › Engenharia de software › Metodologias ágeis para o desenvolvimento de software | A-441ecdfb0c |
| subassunto | ENGENHARIA DE SOFTWARE | Teste unitário | TI › Engenharia de software › Testes de unidade, integração, sistema; testes automatizados… | S-afc6a31091 |
| subassunto | ENGENHARIA DE SOFTWARE | Teste de integração | idem | S-afc6a31091 |
| subassunto | ENGENHARIA DE SOFTWARE | Confiabilidade, integridade e disponibilidade | TI › Segurança da informação › Princípios de segurança da informação | A-e82b500a76 |
| assunto | ARQUITETURA | Tecnologias de integração | TI › Desenvolvimento de sistemas › Integração de sistemas | A-0d5791ace5 |
| assunto | ARQUITETURA | Padrões de arquitetura | TI › Desenvolvimento de sistemas › Arquitetura de software | A-f57e5aa487 |
| subassunto | ARQUITETURA | Arquitetura de microsserviços | TI › Desenvolvimento de sistemas › Arquitetura distribuída de microsserviços | A-505e7be779 |
| assunto | TECNOLOGIAS EMERGENTES | Inteligência artificial: Fundamentos e aplicações | TI › Ciência de dados e IA › Conceitos Básicos de Inteligência Artificial | S-fe253f32ca |
| assunto | TECNOLOGIAS EMERGENTES | Aprendizado de máquina | TI › Ciência de dados e IA › Conceitos e tecnologias de IA, redes neurais, aprendizado de máquina… | A-bfc314b10d |
| assunto | TECNOLOGIAS EMERGENTES | IA generativa | TI › Ciência de dados e IA › Grandes modelos de linguagem (LLM), IA generativa | A-048ceace24 |
| assunto | INFRAESTRUTURA DE REDES | Redes de computadores | TI › Redes de computadores | A-4b13bcdab5 |
| assunto | INFRAESTRUTURA DE REDES | Gerenciamento de redes TCP/IP | TI › Redes de computadores › Gerenciamento de redes | A-a67f9900ba |
| assunto | INFRAESTRUTURA DE REDES | Redes Locais e de longa distância | TI › Redes de computadores › Tecnologias, protocolos e elementos de redes locais e de longa distância… | A-5cc2d6e82a |
| assunto | SISTEMAS OPERACIONAIS | Sistemas operacionais | TI › Infraestrutura de TI › Sistemas operacionais | A-b7f5d728c0 |
| assunto | SERVIDORES | Servidores de aplicação | TI › Infraestrutura de TI › Servidores de aplicação (JBoss, Apache HTTP Server, IIS) | A-32f00392f2 |
| assunto | ARMAZENAMENTO | Armazenamento | TI › Infraestrutura de TI › Armazenamento de dados em rede | A-27cb1a6971 |
| subassunto | ARMAZENAMENTO | Tecnologias de armazenamento NAS e SAN | idem | A-27cb1a6971 |
| subassunto | ARMAZENAMENTO | Tecnologias de backup | TI › Infraestrutura de TI › Backup | A-268e85e223 |
| subassunto | ESTRATÉGIA | Análise de ambiente interno e externo | Administração Geral › Ferramentas de análise de cenário interno e externo | A-7e84a0b377 |
| assunto | ESTRATÉGIA | Indicadores de desempenho | Administração Geral › Indicadores de desempenho | A-b34798e56a |
| subassunto | ESTRATÉGIA | Tipos de indicadores | Administração Geral › Gestão estratégica › Tipos de indicadores | S-def3f14b7c |
| subassunto | ESTRATÉGIA | Variáveis componentes dos indicadores | Administração Geral › Gestão estratégica › Variáveis componentes dos indicadores | S-1af6ddeb5c |
| subassunto | GESTÃO DE PROJETOS | Ciclo de vida do projeto | Administração Geral › Gestão de Projetos › Ciclo de vida e organização do projeto | S-a36d8a0434 |
| subassunto | GESTÃO DE PRODUTOS | Técnicas de levantamento de requisitos | TI › Engenharia de software › Engenharia de requisitos | A-6a5ad94fa5 |
| subassunto | GESTÃO DE PRODUTOS | Minimum Viable Product (MVP) | idem (semente: "produto mínimo viável (MVP)") | A-6a5ad94fa5 |
| subassunto | GESTÃO DE PRODUTOS | Gerenciamento de Backlog | idem (semente: "gestão de backlog") | A-6a5ad94fa5 |
| assunto | GESTÃO E GOVERNANÇA | Legislação aplicável à contratação de bens e serviços de TI e suas alterações | Direito Administrativo › Legislação aplicável à contratação de bens e serviços | A-424f65c051 |
| subassunto | GESTÃO E GOVERNANÇA | Elaboração e fiscalização de contratos | Direito Administrativo › Contratos administrativos › Elaboração e fiscalização de contratos | S-43918fdbe8 |
| subassunto | GESTÃO E GOVERNANÇA | Cláusulas e indicadores de nível de serviço | … › Contratos administrativos › Cláusulas e indicadores de nível de serviço | S-87dabcd1d9 |
| subassunto | GESTÃO E GOVERNANÇA | Papel do fiscalizador do contrato | … › Contratos administrativos › Papel do fiscalizador do contrato | S-81d5169c67 |
| subassunto | GESTÃO E GOVERNANÇA | Papel do preposto da contratada | … › Contratos administrativos › Papel do preposto da contratada | S-b1d7bd5120 |
| subassunto | GESTÃO E GOVERNANÇA | Acompanhamento da execução contratual | … › Contratos administrativos › Acompanhamento da execução contratual | S-0be4918914 |
| subassunto | GESTÃO E GOVERNANÇA | Registro e notificação de irregularidades | … › Contratos administrativos › Registro e notificação de irregularidades | S-b56196a0f2 |
| subassunto | GESTÃO E GOVERNANÇA | Definição e aplicação de penalidades e sanções administrativas | … › Contratos administrativos › Definição e aplicação de penalidades e sanções administrativas | S-b02401c9bd |
| assunto | GESTÃO E GOVERNANÇA | Princípios fundamentais da administração pública | Direito Administrativo › Regime jurídico-administrativo › Princípios expressos e implícitos da Administração Pública | S-20e16b751f |

Os 124 "A" (abrangidos) e o destino proposto de cada um estão em `julgamento.json` (campo `julgamento` = `A`/`AR`, com `no_alvo` e `caminho`). Exemplos:
- os 9 subitens de TÉCNICAS E LINGUAGENS → `A-3408fede43` Linguagens de programação;
- as 10 facetas do BSC → `S-7a0d161260`;
- Gatilhos, Visões e Procedimentos → `S-551a90e864`;
- os 5 subitens de Servidores de aplicação → `A-32f00392f2`/`A-d831972bed`;
- CONCEITOS BÁSICOS → `M-41f37f57d8`.

Lista curta dos realmente novos: seção 3 (42 itens, cerca de 14 conceitos).

---

## (d) Riscos e decisões que dependem do dono

1. **PROCESSO → Direito Processual Civil › Processo:** o próximo `atualizar_revisao` grava como `regra/aprovado`. Decidir se esse par deve ser rejeitado (vira veto na memória) antes de rodar o pipeline ou o LLM. Até lá, convém não rodar `atualizar_arvore`/`mapear_itens_novos` no estado atual.
2. **Título de bloco → disciplina inferida pelo cargo (M4):** aprovação automática (`regra`) ou só proposta? Os títulos de TI apontam para a disciplina TI ou para assuntos de TI (SERVIDORES → `NA-e8ea9374ad`)? A P72 aceita os dois.
3. **Herança de folha (M5):** é convenção da semente, mas automatizar muda a P52/P73 e pede atualização da regra no registro (`make docs-gerar`, P70).
4. **Casamento entre disciplinas (M6):** os 7 subitens de contratos de um bloco de TI passam a contar em Direito Administrativo. Isso segue o "um conceito, um nó" (ADR-030), mas muda a leitura por disciplina do edital de TI.
5. **LEGISLAÇÃO → Legislação Específica (semente):** o bloco do BANRISUL tem políticas para mulheres, igualdade racial e LGPD. Pela D2 ("só normas do órgão"), as políticas iriam para Serviço Social › Políticas Sociais e a LGPD para Direito Administrativo. Decidir também se títulos genéricos deixam de herdar decisão entre editais (M11; toca a chave natural, ADR-026).
6. **Novos conceitos:** criar POO, SOLID/padrões, estruturas de dados, tuning de SQL, serviços de diretório, UX, inovação financeira, Lei 13.303 etc. (seção 3). Especialmente: "Design thinking" de UX vira um 4º nó por enfoque ou funde num existente? Inovação financeira vira assunto próprio de TI?
7. **Extração (M7/M8):** `src/taxonomia_extractor.py` e o JSON do BANRISUL têm alterações **não commitadas de outra pessoa** (`reparar_materia_extraida`, hífen de quebra de linha). Qualquer mudança no nome em cadeia ou na divisão por ";" precisa ser coordenada e implica reprocessar o SEFA (134 itens em cadeia) e o BANRISUL antes da aprovação, o que muda as chaves (`chave_item`) desses itens.
8. **P71/K22:** nenhuma das melhorias toca o piloto, mas M6 (casamento global) e M11 (chave) devem rodar o K22–K24 antes e depois. A carga só lê `aprovado`, então o risco está em `regra/aprovado` automático errado.
9. **Hipóteses marcadas:** a estimativa do LLM (seção 4), o ganho de M6 no SEFA (a precisão não foi medida item a item lá) e a causa de o relatório estar defasado em relação à árvore (2.1).
