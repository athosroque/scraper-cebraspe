# ADR-009: Recorte Exclusivo da Seção "OBJETOS DE AVALIAÇÃO" no Parser

## Status
Aceito

## Data
2026-09-19

## Contexto
Os editais de abertura de concursos do CEBRASPE possuem grande volume de texto (frequentemente entre 50 e 100 páginas), contendo requisitos de posse, atribuições de cargos, modelos de declaração, cronogramas e critérios de desempate.

## Decisão
Configurar o `src/edital_parser.py` para recortar exclusivamente o trecho iniciado pelo marcador `"OBJETOS DE AVALIAÇÃO (HABILIDADES E CONHECIMENTOS)"` até o início da próxima seção administrativa ou final do anexo programático.

## Consequências
### Positivas
- Reduz drasticamente o consumo de tokens e o custo de inferência no LLM Gateway.
- Foca 100% no objetivo de negócio do projeto: mapear a taxonomia de matérias, temas e subtemas exigidos nas provas.
- Isola o extrator de ruídos administrativos do certame.

### Alternativas Descartadas
- **Extrair o edital completo:** Inviável pelo custo, latência e propensão a alucinações em textos não programáticos.
- **Extrair requisitos e atribuições de cargos:** Requisitos operacionais não agregam valor à matriz de conteúdo programático para estudos neste momento.
