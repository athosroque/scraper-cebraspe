"""Valida se a taxonomia extraída pelo LLM capturou todos os tópicos numerados
presentes no texto-fonte do edital (Etapa 4 — checkpoint de revisão humana).

Compara, por chunk, os itens de primeiro nível encontrados em
`texto_enviado_llm` (`.auditoria.json`) contra os `topico["nome"]`
extraídos (`.json`). O `taxonomia_extractor.py` instrui o LLM a preservar a
numeração original do edital, mas na prática ele **nem sempre obedece**
(achado ao vivo: no mesmo edital piloto, chunk 0 preserva "1 Compreensão...",
chunk 1 devolve só "Estruturas lógicas", sem número) — por isso a
comparação usa o **texto normalizado do item** como chave (número de prefixo
descartado dos dois lados), não o número em si. O número extraído do
texto-fonte só é usado para contexto no alerta (`numero_item`) e para achar
o corte de cada item na fonte.

Um item de primeiro nível presente na fonte e sem correspondência normalizada
em nenhum `topico_nome` é candidato a tópico que o LLM deixou de fora
(`topico_ausente`); o inverso (`topico_extra`) sinaliza possível erro de
chunking/alucinação. Um quarto tipo, `topico_nome_numerico`, sinaliza
separadamente quando `topico["nome"]` é puramente numérico — sintoma de o
LLM ter confundido o numeral do item da fonte com o texto do tópico (ver
ADR-021); é aditivo, não substitui os dois alertas acima para o mesmo caso.

Severidade (ADR-025): um tópico sem casamento estrito mas que é paráfrase
leve de um item da fonte (qualificador entre parênteses acrescentado, erro de
digitação da fonte corrigido pelo LLM — `comparacao_texto.divergencia_leve`)
vira `topico_divergencia_leve` com `severidade: "informativo"`, em vez de
`topico_extra`. Continua no `.validacao.json`/relatório/Datasette, mas fica
fora de `total_alertas` (contado em `total_informativos`). Todo alerta sem
`severidade` é bloqueante.

Forma (KAN-94, M8), sempre informativa: `topico_lista_nao_dividida` (nome com ";"
fora de parênteses e sem subtópicos), `subtopico_faceta_solta` (palavra de
`FACETAS_GENERICAS` como subtópico: "conceito", "metas"...) e `topico_frase_longa`
(nome com mais de `TAMANHO_FRASE_LONGA` caracteres). O reparo determinístico
(`normalizar_listas_e_facetas`) trata o que é seguro; estes alertas listam o
que sobrou para o dono decidir.

Heurística, não prova formal: matérias sem numeração no PDF não geram itens
de fonte (nada a comparar, sem alerta); numeração colada sem espaço ao texto
anterior (ex.: "...lógicos.4 Lógica...") e correspondência textual imperfeita
podem gerar falso positivo/negativo — todo alerta é candidato a revisão
humana, não erro confirmado.

Uso:
    python -m scripts.validar_taxonomia [revisao_piloto_dir]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.comparacao_texto import (
    TAMANHO_FRASE_LONGA,
    contido,
    divergencia_leve,
    eh_faceta_generica,
    item_coberto,
    normalizar,
    partes_por_ponto_e_virgula,
)
from src.edital_parser import extrair_itens_numerados, extrair_subitens_numerados
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"

# Alerta informativo: divergência explicável entre fonte e extração (paráfrase
# leve, erro de digitação da fonte corrigido pelo LLM) — continua visível no
# relatório/Datasette, mas não conta em `total_alertas` (ver ADR-025).
SEVERIDADE_INFORMATIVO = "informativo"
SEVERIDADE_BLOQUEANTE = "bloqueante"


def severidade(alerta: dict) -> str:
    return alerta.get("severidade", SEVERIDADE_BLOQUEANTE)


def alertas_de_forma(base: dict, topicos: list[dict]) -> list[dict]:
    """Alertas informativos sobre a forma dos nomes (KAN-94, M8)."""

    def alerta(tipo: str, topico: str, texto: str) -> dict:
        return {
            **base,
            "tipo": tipo,
            "severidade": SEVERIDADE_INFORMATIVO,
            "numero_item": None,
            "texto_item_origem": texto[:200],
            "topico_nome_extraido": topico,
        }

    alertas = []
    for topico in topicos:
        nome = topico.get("nome", "")
        subs = [s for s in topico.get("subtopicos", []) if s]
        if not subs and len(partes_por_ponto_e_virgula(nome)) > 1:
            alertas.append(alerta("topico_lista_nao_dividida", nome, nome))
        if len(nome) > TAMANHO_FRASE_LONGA:
            alertas.append(
                alerta("topico_frase_longa", nome, f"{len(nome)} caracteres")
            )
        for sub in subs:
            if eh_faceta_generica(sub):
                alertas.append(alerta("subtopico_faceta_solta", nome, sub))
    return alertas


def comparar_chunk(chunk_auditoria: dict, resultado_chunk: dict | None) -> list[dict]:
    """Gera alertas para um chunk, comparando itens numerados da fonte com a taxonomia extraída."""
    base = {
        "chunk_index": chunk_auditoria.get("chunk_index"),
        "cargo": chunk_auditoria.get("cargo"),
        "materia": chunk_auditoria.get("materia"),
    }
    texto_fonte = chunk_auditoria.get("texto_enviado_llm") or ""
    itens_fonte = extrair_itens_numerados(texto_fonte)

    alertas = []
    # Só audita classificação quando o chunk já tem os campos (auditoria
    # gerada/backfilled depois do ADR-020) — formato legado não tem nada a
    # comparar. Chunk sem bloco ou sem nível não entra nos filtros por
    # nível/tipo de conhecimento, e isso não pode passar em silêncio.
    if "tipo_conhecimento" in chunk_auditoria and (
        chunk_auditoria.get("tipo_conhecimento") is None
        or chunk_auditoria.get("nivel") is None
    ):
        alertas.append(
            {
                **base,
                "tipo": "chunk_sem_classificacao",
                "numero_item": None,
                "texto_item_origem": (
                    f"tipo_conhecimento={chunk_auditoria.get('tipo_conhecimento')}, "
                    f"nivel={chunk_auditoria.get('nivel')}"
                ),
                "topico_nome_extraido": None,
            }
        )

    if chunk_auditoria.get("status") == "falha" or resultado_chunk is None:
        if not itens_fonte:
            return alertas
        return alertas + [
            {
                **base,
                "tipo": "chunk_sem_extracao",
                "numero_item": ", ".join(numero for numero, _ in itens_fonte),
                "texto_item_origem": None,
                "topico_nome_extraido": None,
            }
        ]

    taxonomia = resultado_chunk.get("taxonomia_extraida") or {}
    topicos = taxonomia.get("topicos", [])
    # A forma dos nomes não depende de numeração na fonte.
    alertas += alertas_de_forma(base, topicos)

    if not itens_fonte:
        # Matéria sem numeração no texto-fonte: nada a comparar em nenhuma
        # direção (não dá pra saber se a extração é completa sem uma
        # referência numerada) — melhor não opinar do que gerar ruído.
        return alertas

    # Rede de segurança para dados persistidos antes do reforço de prompt/
    # checagem semântica em `taxonomia_extractor.py` (ver ADR-021) — sinaliza
    # separado de `topico_ausente`/`topico_extra` porque a causa aqui é
    # sempre a mesma (LLM preencheu "nome" com o numeral do item da fonte em
    # vez do texto do tópico), e o alerta genérico de "extra" some no meio de
    # dezenas de outros sem apontar a causa raiz.
    for topico in topicos:
        nome = topico.get("nome", "")
        if nome.strip().isdigit():
            alertas.append(
                {
                    **base,
                    "tipo": "topico_nome_numerico",
                    "numero_item": None,
                    "texto_item_origem": None,
                    "topico_nome_extraido": nome,
                }
            )

    texto_fonte_norm = normalizar(texto_fonte)

    # Coleta tanto tópicos quanto subtópicos extraídos para comparação
    # Se constar em tópico OU subtópico, o item da fonte é considerado coberto
    todos_extraidos = []
    topicos_extraidos = []
    for t_idx, topico in enumerate(topicos):
        t_nome = topico.get("nome", "")
        if t_nome and not t_nome.strip().isdigit():
            topicos_extraidos.append((t_idx, t_nome))
            todos_extraidos.append(
                {
                    "texto": t_nome,
                    "norm": normalizar(t_nome),
                    "tipo": "topico",
                    "topico_idx": t_idx,
                }
            )
        for s in topico.get("subtopicos", []):
            if s and isinstance(s, str) and not s.strip().isdigit():
                todos_extraidos.append(
                    {
                        "texto": s,
                        "norm": normalizar(s),
                        "tipo": "subtopico",
                        "topico_idx": t_idx,
                    }
                )

    topicos_usados: set[int] = set()

    for posicao, (numero, item_texto) in enumerate(itens_fonte):
        item_norm = normalizar(item_texto)
        match_encontrado = False
        for el in todos_extraidos:
            if contido(el["norm"], item_norm):
                match_encontrado = True
                if el["tipo"] == "topico":
                    topicos_usados.add(el["topico_idx"])

        if not match_encontrado and any(
            divergencia_leve(el["texto"], [item_texto], item_norm)
            for el in todos_extraidos
        ):
            # O mesmo par (item, tópico parafraseado) já gera um
            # `topico_divergencia_leve` do lado do tópico — alertar aqui
            # também como `topico_ausente` duplicaria o caso como bloqueante.
            match_encontrado = True

        if not match_encontrado:
            alertas.append(
                {
                    **base,
                    "tipo": "topico_ausente",
                    "numero_item": numero,
                    "posicao_item": posicao,
                    "texto_item_origem": item_texto[:200],
                    "topico_nome_extraido": None,
                }
            )

    # Subitens (2º nível em diante): o LLM costuma descartar os níveis mais
    # fundos sem que o 1º nível acuse nada. Mesma regra de cobertura da
    # reinjeção (`item_coberto`) sobre todos os tópicos e subtópicos do chunk.
    textos_extraidos = [el["texto"] for el in todos_extraidos]
    for numero, subitem_texto in extrair_subitens_numerados(texto_fonte):
        if not item_coberto(subitem_texto, textos_extraidos):
            alertas.append(
                {
                    **base,
                    "tipo": "subitem_ausente",
                    "numero_item": numero,
                    "texto_item_origem": subitem_texto[:200],
                    "topico_nome_extraido": None,
                }
            )

    # Tópicos puramente numéricos geram topico_extra
    for topico in topicos:
        nome = topico.get("nome", "")
        if nome.strip().isdigit():
            alertas.append(
                {
                    **base,
                    "tipo": "topico_extra",
                    "numero_item": None,
                    "texto_item_origem": None,
                    "topico_nome_extraido": nome,
                }
            )

    # Tópicos textuais só são extra se não foram casados e não estão no texto da fonte
    for t_idx, t_nome in topicos_extraidos:
        if t_idx not in topicos_usados:
            t_norm = normalizar(t_nome)
            if contido(t_norm, texto_fonte_norm):
                continue
            if divergencia_leve(
                t_nome, [texto for _, texto in itens_fonte], texto_fonte_norm
            ):
                alertas.append(
                    {
                        **base,
                        "tipo": "topico_divergencia_leve",
                        "severidade": SEVERIDADE_INFORMATIVO,
                        "numero_item": None,
                        "texto_item_origem": None,
                        "topico_nome_extraido": t_nome,
                    }
                )
            else:
                alertas.append(
                    {
                        **base,
                        "tipo": "topico_extra",
                        "numero_item": None,
                        "texto_item_origem": None,
                        "topico_nome_extraido": t_nome,
                    }
                )

    return alertas


def validar_arquivos_concurso(
    resultado: dict, data_dir: Path | None = None
) -> list[dict]:
    """Verifica se os PDFs de Provas e Gabaritos, o arquivo de metadados dos links
    (provas_texto_link.json) e o registro em processed_concursos.json existem.

    Garante que o pipeline seja resiliente contra editais extraídos sem o download
    completo do concurso (ausência silenciosa de provas/gabaritos).
    """
    concurso = resultado.get("concurso")
    if not concurso or not isinstance(concurso, dict) or not concurso.get("slug"):
        return []

    from src.downloader import DATA_DIR, slugify
    from src.spider import load_processed_slugs

    base_dir = data_dir if data_dir is not None else DATA_DIR
    slug = concurso["slug"]
    orgao = concurso.get("orgao") or ""
    ano = concurso.get("ano") or 2025

    orgao_slug = slugify(orgao)
    concurso_dir = base_dir / str(ano) / "CEBRASPE" / orgao_slug

    alertas = []
    base = {
        "chunk_index": None,
        "cargo": None,
        "materia": None,
    }

    # 1. Provas
    provas_dir = concurso_dir / "Provas"
    provas_pdfs = list(provas_dir.glob("*.pdf")) if provas_dir.exists() else []
    if not provas_pdfs:
        alertas.append(
            {
                **base,
                "tipo": "alerta_ausencia_provas",
                "numero_item": None,
                "texto_item_origem": f"Nenhuma prova baixada encontrada em {provas_dir}",
                "topico_nome_extraido": None,
            }
        )

    # 2. Gabaritos
    gabaritos_dir = concurso_dir / "Gabaritos"
    gabaritos_pdfs = list(gabaritos_dir.glob("*.pdf")) if gabaritos_dir.exists() else []
    if not gabaritos_pdfs:
        alertas.append(
            {
                **base,
                "tipo": "alerta_ausencia_gabaritos",
                "numero_item": None,
                "texto_item_origem": f"Nenhum gabarito baixado encontrado em {gabaritos_dir}",
                "topico_nome_extraido": None,
            }
        )

    # 3. provas_texto_link.json
    provas_texto_path = concurso_dir / "provas_texto_link.json"
    if not provas_texto_path.exists():
        alertas.append(
            {
                **base,
                "tipo": "alerta_ausencia_provas_texto_link",
                "numero_item": None,
                "texto_item_origem": f"Arquivo provas_texto_link.json ausente em {concurso_dir}",
                "topico_nome_extraido": None,
            }
        )

    # 4. processed_concursos.json
    processed_slugs = load_processed_slugs()
    if slug not in processed_slugs:
        alertas.append(
            {
                **base,
                "tipo": "concurso_nao_registrado_processed",
                "numero_item": None,
                "texto_item_origem": f"Concurso '{slug}' não registrado em processed_concursos.json",
                "topico_nome_extraido": None,
            }
        )

    return alertas


def validar_edital(
    resultado: dict, auditoria: dict, data_dir: Path | None = None
) -> dict:
    resultado_por_index = {
        item["chunk_index"]: item
        for item in resultado["resultados"]
        if item.get("chunk_index") is not None
    }

    alertas = []
    # Alertas estruturais do concurso (ausência de provas, gabaritos ou registro de processamento)
    alertas.extend(validar_arquivos_concurso(resultado, data_dir))

    for chunk_auditoria in auditoria["chunks"]:
        resultado_chunk = resultado_por_index.get(chunk_auditoria.get("chunk_index"))
        alertas.extend(comparar_chunk(chunk_auditoria, resultado_chunk))

    informativos = sum(1 for a in alertas if severidade(a) == SEVERIDADE_INFORMATIVO)
    return {
        "edital": resultado["edital"],
        "total_chunks_analisados": len(auditoria["chunks"]),
        "total_alertas": len(alertas) - informativos,
        "total_informativos": informativos,
        "alertas": alertas,
    }


def _carregar_par(json_path: Path) -> tuple[dict, dict | None]:
    resultado = json.loads(json_path.read_text(encoding="utf-8"))
    auditoria_path = json_path.parent / f"{json_path.stem}.auditoria.json"
    if auditoria_path.exists():
        return resultado, json.loads(auditoria_path.read_text(encoding="utf-8"))
    return resultado, None


def main(revisao_dir: Path = REVISAO_DIR_PADRAO) -> None:
    jsons = sorted(
        p
        for p in revisao_dir.glob("*.json")
        if not p.name.endswith(".auditoria.json")
        and not p.name.endswith(".validacao.json")
    )
    if not jsons:
        logger.warning(f"Nenhum <edital>.json encontrado em {revisao_dir}.")
        return

    for json_path in jsons:
        resultado, auditoria = _carregar_par(json_path)
        if auditoria is None:
            logger.warning(
                f"{resultado['edital']}: sem .auditoria.json — pulando validação (formato legado)."
            )
            continue

        validacao = validar_edital(resultado, auditoria)
        out_path = json_path.parent / f"{json_path.stem}.validacao.json"
        out_path.write_text(
            json.dumps(validacao, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(
            f"{validacao['edital']}: {validacao['total_alertas']} alerta(s) de validação "
            f"+ {validacao['total_informativos']} informativo(s) em {out_path}."
        )


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    main(diretorio)
