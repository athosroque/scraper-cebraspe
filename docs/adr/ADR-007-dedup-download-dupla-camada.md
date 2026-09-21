# ADR-007: Dedup de Download em Duas Camadas (URL + Hash de Conteúdo)

## Status
Aceito

## Data
2026-09-19

## Contexto
O download de arquivos PDF (editais, cadernos de prova e gabaritos) precisa evitar transferências de rede redundantes e prevenir duplicação de arquivos idênticos no disco (por exemplo, retificações que apontam para o mesmo PDF ou links múltiplos para um mesmo documento).

## Decisão
Implementar um sistema de desduplicação em duas camadas no `src/downloader.py`:
1. **Camada 1 (Manifesto de URL):** Manter um `.manifest.json` na pasta do concurso mapeando `URL → {hash, path}`. Antes de iniciar o download, checa se a URL já foi baixada.
2. **Camada 2 (Hash SHA256 do Conteúdo):** Após o stream do arquivo, calcula o hash do binário e verifica se já existe outro arquivo com o mesmo hash salvo no diretório.

## Consequências
### Positivas
- Economia significativa de tráfego de rede e tempo de execução.
- Eliminação de duplicatas reais no sistema de arquivos.

### Alternativas Descartadas
- **Dedup exclusivo por nome de arquivo:** Propenso a falsos-positivos (nomes iguais com conteúdo diferente) e falsos-negativos (URLs com nomes alterados mas conteúdo idêntico).
- **Dedup exclusivo por hash:** Exigiria baixar o arquivo inteiro pela rede antes de poder calcular o hash.
