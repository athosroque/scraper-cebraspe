# ADR-041: Registro do pipeline em Python e páginas técnicas geradas do código

- **Status:** Aceito
- **Data:** 2026-10-13
- **Etapa:** 9, sessão D2 (KAN-69; plano em `plano-etapa-9.md`, card KAN-67)
- **Decisores:** Dono do produto
- **Relaciona-se com:** ADR-040 (site MkDocs com `--strict`), ADR-036 (etapas de teste e
  markers `unit`/`db`)

---

## 1. Contexto

O pipeline é uma sequência de CLIs `python -m ...` rodados à mão, sem registro de etapas.
As regras do projeto estão em cerca de 130 bullets do `CLAUDE.md` (§6 e §7), e parte das
checagens só aparece na saída do pytest ou no log. O diagrama de `docs/architecture.md`
parou na fase 5. Documentação escrita à mão sobre o pipeline envelhece a cada mudança.

O dono pediu que a documentação reflita o projeto sempre que ele mudar, e o Dagster (D5a,
KAN-31) precisa de uma lista de etapas para montar os assets.

## 2. Decisão

1. **Registro em `src/registro/`, um pacote.** `modelo.py` define as dataclasses congeladas
   `Script`, `Etapa`, `Checagem` e `Regra`, que validam a forma no import. O conteúdo fica
   em módulos irmãos (`scripts.py`, `etapas.py`, `checagens.py`, `regras_*.py`), e o
   `__init__.py` exporta `SCRIPTS`, `ETAPAS`, `CHECAGENS`, `REGRAS` e `REGISTRO`. O D5a lê
   as etapas daqui: uma fonte só para o pipeline documentado e o executado.
2. **Páginas geradas e versionadas em `docs/tecnico/`** (`pipeline`, `comandos`, `regras`,
   `checagens`, `banco`) por `scripts/gerar_docs.py` (`make docs-gerar`). Cada página abre
   com um comentário "não editar à mão". Versionar deixa o `.md` legível direto na
   worktree por um agente, sem plugin novo no MkDocs.
3. **Argumentos dos scripts lidos por AST**, sem importar nem executar o script. Rodar
   `--help` não é seguro: vários scripts leem `sys.argv` na mão e tratariam `--help` como
   caminho. Para esses, o uso fica escrito no registro (`cli="argv"`, `uso_argv`).
4. **Schema do banco via `information_schema`**, numa sessão só leitura. Só o
   `make docs-gerar` e o teste `db` tocam no banco.
5. **Checagens com resultado consultável.** Cada `Checagem` diz onde ver o resultado: uma
   consulta SQL (`onde="banco"`, devolve as linhas problemáticas; zero linhas é verde), um
   teste do pytest ou um comando. O estado ao vivo fica para as asset checks do D5b.
6. **Regras com o texto literal do `CLAUDE.md`**, id estável (`P01`… do §6, `A01`… do §7),
   área, ADRs e teste guarda quando existir. Regra sem teste aparece como "sem teste
   guarda". O `CLAUDE.md` só fica mais curto na D3 (KAN-70), que aponta para a página.
7. **Testes guarda** em `tests/test_registro.py` (unit) e `tests/test_registro_banco.py`
   (db): script em `scripts/` ou módulo de `src/` com `__main__` fora do registro, etapa que
   cita script não registrado, `depois_de` inválido ou com ciclo, ADR ou teste citado
   inexistente, id repetido, página gerada diferente do disco, schema diferente de
   `banco.md` e consulta de checagem inválida (`EXPLAIN`). O teste do Dagster fica em
   `skip` até o D5a.

## 3. Consequências

- Script novo exige uma entrada em `src/registro/scripts.py` e `make docs-gerar`; sem isso
  o `make check` falha. Mudar o argparse de um script também exige regerar as páginas.
- Mudança de schema exige `make docs-gerar` (o teste `db` acusa).
- O texto das regras existe em dois lugares até a D3: o `CLAUDE.md` e o registro. Até lá,
  quem mudar uma regra no `CLAUDE.md` muda também o registro.
- O diagrama de `docs/architecture.md` foi trocado por um link para a página gerada.

### 3.1 Alternativas descartadas

- **Páginas geradas só no build (`mkdocs-gen-files`):** mais uma dependência, e o agente
  não vê o `.md` sem rodar o build.
- **`--help` em subprocesso:** executa scripts que não usam `argparse`.
- **YAML no lugar de Python:** perde a validação no import e o uso direto pelo Dagster.
- **Arquivo único `src/registro.py`:** com cerca de 200 entradas, fica grande demais para
  ler e editar em paralelo.
