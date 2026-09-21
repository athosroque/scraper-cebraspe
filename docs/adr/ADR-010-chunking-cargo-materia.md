# ADR-010: Chunking em Dois Níveis (Cargo + Matéria), Não Só Matéria

## Status
Aceito

## Data
2026-09-19

## Contexto
O texto da seção "OBJETOS DE AVALIAÇÃO" precisa ser dividido em pedaços (*chunks*) gerenciáveis para submissão ao modelo de linguagem. Editais reais apresentam estruturas mistas: cargos administrativos contêm múltiplas disciplinas nomeadas (ex: Língua Portuguesa, Direito Constitucional), enquanto cargos especializados (ex: Médicos por especialidade) trazem apenas o cabeçalho do cargo seguido diretamente do conteúdo programático unificado.

## Decisão
A função `dividir_por_cargo_e_materia` em `src/edital_parser.py` rastreia conjuntamente cabeçalhos de cargo (`CARGO N: <nome>`) e cabeçalhos de matéria, mantendo o cargo corrente. Ela produz 1 chunk por matéria identificada ou 1 chunk pelo próprio cargo quando este não define matérias segregadas.

## Consequências
### Positivas
- Preserva a associação estrita entre o cargo e o conteúdo exigido (essencial para as chaves estrangeiras na Fase 5).
- Garante granularidade adequada tanto para editais com dezenas de disciplinas comuns quanto para certames de especialidades técnicas/médicas.

### Alternativas Descartadas
- **Chunking unicamente por matéria:** Provou-se falho em testes reais, agrupando inadvertidamente 14 cargos médicos inteiros dentro de um único chunk gigante de mais de 41 mil caracteres.
