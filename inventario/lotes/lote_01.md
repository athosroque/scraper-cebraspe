# Relatório de Lote 01: SEFA_PR_25, BANRISUL_25

- **Data de geração:** 2026-10-21 21:59:17 UTC
- **Lote:** 01
- **Concursos:** SEFA_PR_25, BANRISUL_25
- **Modo de Execução:** Conferência
- **Veredito:** `AGUARDANDO PORTÕES HUMANOS`

---

## 1. Resumo Executivo e Veredito

O lote **01** obteve o veredito final: **`[PENDENTE]`** **`AGUARDANDO PORTÕES HUMANOS`**.

> [!NOTE]
> **Checagens automáticas verdes.** O lote está tecnicamente íntegro e aguardando aprovações humanas:
> - ⏳ Portão P3 (Edital): pendente em SEFA_PR_25, BANRISUL_25
> - ⏳ Portão P7 (Árvore): 183 proposta(s) pendente(s)
> - ⏳ Portão P9 (Classificação): 615 pendência(s)
>
> *Ação necessária: Homologar os portões humanos pendentes para liberar publicação.*

**Alertas informativos registrados (não-bloqueantes):**

- ⚠️ K19: 61 questões ME citam texto/tabela/figura sem vínculo no banco (severidade WARN)

---

## 2. Tabela de Checagens Automáticas e Portões

| Camada | Checagem | Status | Observações |
|:---|:---|:---:|:---|
| **Download** | Reconciliação PDFs e Inventário | **`[OK]`** | SEFA_PR_25: 19 PDFs íntegros (%PDF-); BANRISUL_25: 22 PDFs íntegros (%PDF-) |
| **Edital** | Portão Humano e Taxonomia (P3) | **`[PENDENTE]`** | Aguardando homologação humana em: SEFA_PR_25, BANRISUL_25 |
| **Prova** | Extração de Itens e Gabaritos (P4) | **`[OK]`** | 17 provas validadas, gabaritos na grade e 5 discursivas com padrão |
| **Banco** | Invariante do Piloto (K22) e Contagens | **`[OK]`** | Invariante do piloto preservada; 17 provas, 610 questões, 5 discursivas gravadas |
| **Classificação** | Curadoria da Árvore e Questões | **`[PENDENTE]`** | BANRISUL_25: 0 de 230; SEFA_PR_25: 0 de 380 (total: 0 de 610 classificadas) (615 sem classificação) |
| **Site** | Prontidão dos Dados para Publicação | **`[NÃO VERIFICADO]`** | 0 de 610 questões visíveis em vw_questoes. Justificativa: as questões só ingressam na view pública após classificação na árvore e curadoria (P8/P9). |

---


---

## 3. Invariante do Piloto (K22)

> A checagem K22 afere se o processamento do lote preservou intactos os dados dos 5 concursos canônicos homologados (PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, CD_25_NS).

| Métrica | Esperado | Antes do Lote | Depois do Lote | Status |
|:---|---:|---:|---:|:---:|
| **Itens Objetivos** | 2.800 | 2.800 | 2.800 | **`[OK]`** |
| **Itens Anulados** | 129 | 129 | 129 | **`[OK]`** |
| **Apontamentos na Árvore** | 3.029 | 3.029 | 3.029 | **`[OK]`** |
| **Hash Chaves 5D** | `3257ba6ba525fdd6b4492733b50882f2` | `3257ba6ba525fdd6b4492733b50882f2` | `3257ba6ba525fdd6b4492733b50882f2` | **`[OK]`** |

---

## 4. Detalhamento das Consultas do Runbook (§4.5)

### 4.1 Consulta (a) — Integridade por Prova

| Concurso | Arquivo | Tipo | Cargos | Fila | Itens | Sem Gab | Anul | Alt (Min-Max) | Inútil | Disc |
|:---|:---|:---|:---:|:---:|---:|---:|---:|:---:|---:|---:|
| BANRISUL_25 | `077_BANRISUL_001_DISC.pdf` | discursiva | 1 | concluido | 0 | 0 | 0 | - | 0 | 1 |
| BANRISUL_25 | `077_BANRISUL_002_DISC.pdf` | discursiva | 2 | concluido | 0 | 0 | 0 | - | 0 | 1 |
| BANRISUL_25 | `077_BANRISUL_003_DISC.pdf` | discursiva | 3 | concluido | 0 | 0 | 0 | - | 0 | 1 |
| BANRISUL_25 | `077_BANRISUL_004_DISC.pdf` | discursiva | 4 | concluido | 0 | 0 | 0 | - | 0 | 1 |
| BANRISUL_25 | `077_BANRISUL_CB1_01.pdf` | objetiva_basica | 1,2,3,4 | concluido | 30 | 0 | 1 | 5-5 | 0 | 0 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | objetiva_especifica | 1 | concluido | 50 | 0 | 1 | 5-5 | 0 | 0 |
| BANRISUL_25 | `077_BANRISUL_002_01.pdf` | objetiva_especifica | 2 | concluido | 50 | 0 | 3 | 5-5 | 0 | 0 |
| BANRISUL_25 | `077_BANRISUL_003_01.pdf` | objetiva_especifica | 3 | concluido | 50 | 0 | 0 | 5-5 | 0 | 0 |
| BANRISUL_25 | `077_BANRISUL_004_01.pdf` | objetiva_especifica | 4 | concluido | 50 | 0 | 0 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `C755AC0EC03CD62E8802C6DFF89130043E61CE191AD3673D2A017293C5CFBB6E.pdf` | discursiva | 1,2,3,4,5,6 | concluido | 0 | 0 | 0 | - | 0 | 1 |
| SEFA_PR_25 | `B7881240CC60CF1CEA5C2A42F3CBC018457E96D6D02200151544B9F654265839.pdf` | objetiva_basica | 1,2,3,4,5,6 | concluido | 80 | 0 | 4 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `2F58995126C3CE0CD3ED52F1A50A1158B2AD11CC1A73B73D20B9B3308C4F549C.pdf` | objetiva_especifica | 2 | concluido | 50 | 0 | 3 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | objetiva_especifica | 6 | concluido | 50 | 0 | 2 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `8D38D9B4E6BDACCA8D659BC004169BF70CC3A1B32BBBA9FE95ABA1A84A0B6EE2.pdf` | objetiva_especifica | 5 | concluido | 50 | 0 | 0 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `90ECB71259732E8F2E4407EDA63B6754CADD1809D7F1A2741FB1422320521691.pdf` | objetiva_especifica | 1 | concluido | 50 | 0 | 2 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `9A9608A616856A6A1D56FC902BFB9123EF6D7FADBAF60956903E32D73001B8C8.pdf` | objetiva_especifica | 4 | concluido | 50 | 0 | 5 | 5-5 | 0 | 0 |
| SEFA_PR_25 | `B8C5A504FAFC1AA1291C24E0EF65F853FD627198946D73AA9C28270FE383201A.pdf` | objetiva_especifica | 3 | concluido | 50 | 0 | 2 | 5-5 | 0 | 0 |

### 4.2 Consulta (b) — Distribuição de Gabaritos

| Concurso | Tipo | Gabarito | Ocorrências |
|:---|:---|:---:|---:|
| BANRISUL_25 | multipla_escolha | **`A`** | 46 |
| BANRISUL_25 | multipla_escolha | **`B`** | 39 |
| BANRISUL_25 | multipla_escolha | **`C`** | 56 |
| BANRISUL_25 | multipla_escolha | **`D`** | 47 |
| BANRISUL_25 | multipla_escolha | **`E`** | 37 |
| BANRISUL_25 | multipla_escolha | **`X`** | 5 |
| SEFA_PR_25 | multipla_escolha | **`A`** | 75 |
| SEFA_PR_25 | multipla_escolha | **`B`** | 63 |
| SEFA_PR_25 | multipla_escolha | **`C`** | 69 |
| SEFA_PR_25 | multipla_escolha | **`D`** | 85 |
| SEFA_PR_25 | multipla_escolha | **`E`** | 70 |
| SEFA_PR_25 | multipla_escolha | **`X`** | 18 |

### 4.3 Consulta (c) — Provas Discursivas

| Concurso | Arquivo | Item | Quesitos | Padrão | Tema |
|:---|:---|:---:|---:|:---:|:---|
| BANRISUL_25 | `077_BANRISUL_001_DISC.pdf` | Q1 | 3 | Sim | banco de dados relacional |
| BANRISUL_25 | `077_BANRISUL_002_DISC.pdf` | Q1 | 3 | Sim | importância dos princípios SOLID na c... |
| BANRISUL_25 | `077_BANRISUL_003_DISC.pdf` | Q1 | 3 | Sim | *(tema vazio / anafórico)* |
| BANRISUL_25 | `077_BANRISUL_004_DISC.pdf` | Q1 | 4 | Sim | levantamento de requisitos no process... |
| SEFA_PR_25 | `C755AC0EC03CD62E8802C6DFF89130043E61CE191AD3673D2A017293C5CFBB6E.pdf` | Q1 | 3 | Sim | *(tema vazio / anafórico)* |

### 4.4 Consulta (d) — Seções por Caderno e K15 (Alternativas em Caixa Alta)

Nenhuma alternativa terminando em caixa alta foi identificada (**K15**: **`[OK]`**).

**Seções identificadas nos cadernos:**

| Arquivo | Seção | Faixa Itens | Total |
|:---|:---|:---:|---:|
| `077_BANRISUL_001_01.pdf` | CONCEITOS BÁSICOS | Q31-Q32 | 2 |
| `077_BANRISUL_001_01.pdf` | TÉCNICAS E LINGUAGENS DE PROGRAMAÇÃO | Q33-Q34 | 2 |
| `077_BANRISUL_001_01.pdf` | MODELAGEM DE DADOS | Q35-Q43 | 9 |
| `077_BANRISUL_001_01.pdf` | FUNDAMENTOS DE BANCO DE DADOS | Q44-Q62 | 19 |
| `077_BANRISUL_001_01.pdf` | ADMINISTRAÇÃO DE BANCO DE DADOS RELACION | Q63-Q69 | 7 |
| `077_BANRISUL_001_01.pdf` | BANCO DE DADOS | Q70-Q74 | 5 |
| `077_BANRISUL_001_01.pdf` | PERFORMANCE E TUNING | Q75-Q80 | 6 |
| `077_BANRISUL_002_01.pdf` | PROCESSO | Q31-Q34 | 4 |
| `077_BANRISUL_002_01.pdf` | BANCO DE DADOS | Q35-Q42 | 8 |
| `077_BANRISUL_002_01.pdf` | TÉCNICAS E LINGUAGENS DE PROGRAMAÇÃO | Q43-Q66 | 24 |
| `077_BANRISUL_002_01.pdf` | ENGENHARIA DE SOFTWARE | Q67-Q72 | 6 |
| `077_BANRISUL_002_01.pdf` | ARQUITETURA | Q73-Q77 | 5 |
| `077_BANRISUL_002_01.pdf` | TECNOLOGIAS EMERGENTES | Q78-Q80 | 3 |
| `077_BANRISUL_003_01.pdf` | SEGURANÇA DA INFORMAÇÃO | Q31-Q37 | 7 |
| `077_BANRISUL_003_01.pdf` | INFRAESTRUTURA DE REDES | Q38-Q47 | 10 |
| `077_BANRISUL_003_01.pdf` | SISTEMAS OPERACIONAIS | Q48-Q62 | 15 |
| `077_BANRISUL_003_01.pdf` | SERVIDORES | Q63-Q66 | 4 |
| `077_BANRISUL_003_01.pdf` | ARMAZENAMENTO | Q67-Q70 | 4 |
| `077_BANRISUL_003_01.pdf` | COMPUTAÇÃO EM NUVEM | Q71-Q80 | 10 |
| `077_BANRISUL_004_01.pdf` | ESTRATÉGIA | Q31-Q39 | 9 |
| `077_BANRISUL_004_01.pdf` | GESTÃO DE PROJETOS | Q40-Q49 | 10 |
| `077_BANRISUL_004_01.pdf` | GESTÃO DE PRODUTOS | Q50-Q72 | 23 |
| `077_BANRISUL_004_01.pdf` | GESTÃO E GOVERNANÇA | Q73-Q76 | 4 |
| `077_BANRISUL_004_01.pdf` | INOVAÇÃO EM TI NO SISTEMA FINANCEIRO | Q77-Q80 | 4 |
| `077_BANRISUL_CB1_01.pdf` | LÍNGUA PORTUGUESA | Q1-Q10 | 10 |
| `077_BANRISUL_CB1_01.pdf` | LÍNGUA INGLESA | Q11-Q15 | 5 |
| `077_BANRISUL_CB1_01.pdf` | RACIOCÍNIO LÓGICO | Q16-Q26 | 11 |
| `077_BANRISUL_CB1_01.pdf` | LEGISLAÇÃO | Q27-Q30 | 4 |
| `2F58995126C3CE0CD3ED52F1A50A1158B2AD11CC1A73B73D20B9B3308C4F549C.pdf` | ANALISTA FAZENDÁRIO | Q1-Q50 | 50 |
| `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | TECNOLOGIA DA INFORMAÇÃO | Q1-Q50 | 50 |
| *... e mais 14 seções catalogadas* | | | |

### 4.5 Checagem K19 — Múltipla Escolha sem Texto-Base (Severidade WARN)

> [!NOTE]
> Foram detectadas 61 questões ME cujo enunciado menciona termo textual/gráfico sem vínculo de texto-base nem figura. Esta checagem é **não-bloqueante** e deve ser conferida visualmente nos PDFs.

| Concurso | Arquivo | Questão |
|:---|:---|:---:|
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q35 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q37 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q39 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q40 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q43 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q44 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q56 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q57 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q58 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q59 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q60 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q69 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q76 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q77 |
| BANRISUL_25 | `077_BANRISUL_001_01.pdf` | Q78 |
| BANRISUL_25 | `077_BANRISUL_002_01.pdf` | Q31 |
| BANRISUL_25 | `077_BANRISUL_002_01.pdf` | Q37 |
| BANRISUL_25 | `077_BANRISUL_002_01.pdf` | Q42 |
| BANRISUL_25 | `077_BANRISUL_002_01.pdf` | Q80 |
| BANRISUL_25 | `077_BANRISUL_003_01.pdf` | Q34 |
| BANRISUL_25 | `077_BANRISUL_003_01.pdf` | Q41 |
| BANRISUL_25 | `077_BANRISUL_003_01.pdf` | Q51 |
| BANRISUL_25 | `077_BANRISUL_003_01.pdf` | Q56 |
| BANRISUL_25 | `077_BANRISUL_003_01.pdf` | Q60 |
| BANRISUL_25 | `077_BANRISUL_004_01.pdf` | Q51 |
| BANRISUL_25 | `077_BANRISUL_004_01.pdf` | Q62 |
| BANRISUL_25 | `077_BANRISUL_004_01.pdf` | Q69 |
| SEFA_PR_25 | `2F58995126C3CE0CD3ED52F1A50A1158B2AD11CC1A73B73D20B9B3308C4F549C.pdf` | Q29 |
| SEFA_PR_25 | `2F58995126C3CE0CD3ED52F1A50A1158B2AD11CC1A73B73D20B9B3308C4F549C.pdf` | Q31 |
| SEFA_PR_25 | `2F58995126C3CE0CD3ED52F1A50A1158B2AD11CC1A73B73D20B9B3308C4F549C.pdf` | Q35 |
| SEFA_PR_25 | `2F58995126C3CE0CD3ED52F1A50A1158B2AD11CC1A73B73D20B9B3308C4F549C.pdf` | Q40 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q2 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q4 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q5 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q8 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q10 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q12 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q15 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q37 |
| SEFA_PR_25 | `34B92116AFD6A45F9DBF6735630F19C6A93B48B83D62DDF91F810C9C102F79E8.pdf` | Q42 |
| *... e mais 21 questões com alerta K19* | | |

---

## 5. Propostas de Dispersão da Árvore (P6 / KAN-64)

Foram avaliadas **183** proposta(s) de dispersão e fusão de nós na árvore canônica.

| ID | Tipo | Operação / Detalhes | Justificativa |
|:---|:---:|:---|:---|
| `P-02a6e78849` | fundir | `S-31051a8057` ➔ `A-564f15a1ae` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-03f5141e9d` | fundir | `A-14a2673393` ➔ `S-c54fa43b29` | Conceito disperso (cita a mesma norma, confiança alta, chave 'decreto ... |
| `P-041eb84795` | fundir | `S-9748bdccef` ➔ `S-3fc78aabd9` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-04f5ac36d4` | fundir | `S-6c5a3e9c3f` ➔ `S-e7986333eb` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-094dd36238` | fundir | `SL-42e925ffc4` ➔ `A-2f451322bf` | Conceito disperso (cita a mesma norma, confiança alta, chave 'lei 8112... |
| `P-0c9942b632` | fundir | `S-e7986333eb` ➔ `A-99c9a06d12` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-0ca031d811` | fundir | `S-15b4e945c7` ➔ `A-4c006b192d` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-0e3a24e7fe` | fundir | `S-86e0da1cf3` ➔ `S-1c70e095aa` | Conceito disperso (cita a mesma norma, confiança alta, chave 'lei 1074... |
| `P-0e5cb1b962` | fundir | `A-c3f41ab58f` ➔ `S-e02c45cebe` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-0ed7e26103` | fundir | `S-aba3b71611` ➔ `S-87ee90c4fe` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-104df6beb5` | fundir | `S-a16b2491b7` ➔ `S-e1f995cd41` | Conceito disperso (cita a mesma norma, confiança alta, chave 'decreto ... |
| `P-1560db1f02` | fundir | `S-ebf0ae7f49` ➔ `S-5cc260e2d9` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-158e1f42e0` | fundir | `A-77b2b224ae` ➔ `S-acf7c06d18` | Conceito disperso (cita a mesma norma, confiança alta, chave 'decreto ... |
| `P-16bb9895a0` | fundir | `S-a649ea8b0f` ➔ `AL-d3f0a1724f` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-170bb36167` | fundir | `S-fb441690fe` ➔ `S-de96054091` | Conceito disperso (cita a mesma norma, confiança alta, chave 'lei 5197... |
| `P-1aa2e902bd` | fundir | `S-8fbd0d2554` ➔ `S-ea1413fe47` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-1c78d04d85` | fundir | `S-118c1d5531` ➔ `S-1873949dfa` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-1dde39682f` | fundir | `S-41bf56e94c` ➔ `SL-6f213d5cd7` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-20d531ec90` | fundir | `A-7e93595e9c` ➔ `SL-ddc4fce8dd` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-23ccc79600` | fundir | `A-6b83d84d34` ➔ `S-8538189a7e` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-24447d11ea` | fundir | `A-4b13bcdab5` ➔ `A-43bae408c0` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-24bf9d9cba` | fundir | `S-b4ba760ed5` ➔ `SL-6d3f949b2d` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-250c6ea66b` | fundir | `S-674794e3b4` ➔ `AL-528d504ae8` | Conceito disperso (cita a mesma norma, confiança alta, chave 'lei 4320... |
| `P-255ee1aa38` | fundir | `S-d9a5ebfeb3` ➔ `S-397e736766` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| `P-25aa4e25b4` | fundir | `S-b4b44b6568` ➔ `A-5ebac8ab8e` | Conceito disperso (mesmo nome sob pais diferentes, confiança alta, cha... |
| *... e mais 158 propostas catalogadas* | | | |

---

## 6. Telemetria de Custo OpenRouter (US$)

- **Status da Telemetria:** Disponível (online)
- **Uso Acumulado Total:** US$ 0,3111
- **Uso Diário Total:** US$ 0,00

| Etapa | Chave / Identificador | Acumulado (US$) | Diário (US$) | Limite |
|:---|:---|---:|---:|:---:|
| Taxonomia do edital | Taxonomia do edital | US$ 0,0198 | US$ 0,00 | US$ 50,00 |
| Sinônimos | Sinônimos | US$ 0,0001 | US$ 0,00 | US$ 50,00 |
| Curadoria da árvore | Curadoria da árvore | US$ 0,0002 | US$ 0,00 | US$ 50,00 |
| Classificação das questões | Classificação das questões | US$ 0,0001 | US$ 0,00 | US$ 50,00 |
| Bot do Telegram | Bot do Telegram | US$ 0,0002 | US$ 0,00 | US$ 50,00 |
| Chave geral (fallback e etapas antigas) | Chave geral (fallback e etapas antigas) | US$ 0,2907 | US$ 0,00 | Sem limite |

---

## 7. Próximos Passos e Ações Recomendadas

1. **Revisão Humana do Edital (P3):** Inspecionar os relatórios HTML gerados em `revisao_piloto/` e homologar os certames.
2. **Curadoria da Árvore (P7):** Avaliar e aprovar em lote as propostas de fusão pendentes (`python -m scripts.curar_arvore`).
3. **Curadoria da Classificação (P9):** Homologar as classificações com confiança média/baixa via `python -m scripts.curar_classificacao`.
