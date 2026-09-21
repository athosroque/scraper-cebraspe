# ADR-005: Idempotência via Registro JSON Local, Não Pasta em data/

## Status
Aceito

## Data
2026-09-19

## Contexto
O crawler precisa ser idempotente para permitir reexecuções parciais ou incrementais sem repetir trabalho já concluído ou refazer requisições de rede pesadas.

## Decisão
Manter um arquivo local `data/processed_concursos.json` (lista JSON de slugs concluídos), consultado antes de iniciar a extração de cada concurso e atualizado logo após o término com sucesso.

## Consequências
### Positivas
- A estrutura física de pastas `data/<ano>/CEBRASPE/<orgao>/` só é criada na Etapa 3 (Downloader); checar diretórios no disco seria inviável para o crawler durante a Etapa 2.
- Mecanismo leve, direto e transparente para inspeção humana.

### Alternativas Descartadas
- **Adiar o controle de idempotência para o Downloader:** Descartado porque a navegação Playwright (stealth wait, renderização de DOM) é onerosa e deve ser pulada quando o concurso já foi finalizado.
