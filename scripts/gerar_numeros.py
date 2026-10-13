"""Gera a página de números da visão executiva (`docs/executivo/numeros.md`).

A página é o único lugar em que o PDF executivo busca números: cobertura do
inventário e da base, questões, árvore de assuntos e o custo acumulado de LLM.
Como as páginas técnicas, ela sai de uma consulta ao banco, não de digitação.

Uso:
    python -m scripts.gerar_numeros                  consulta o banco e o custo e grava
    python -m scripts.gerar_numeros --sem-custo      não consulta o OpenRouter
    python -m scripts.gerar_numeros --saida CAMINHO  grava em outro arquivo

As consultas ao banco são só de leitura e sempre no schema `public`. O custo
é lido do endpoint `/api/v1/key` do OpenRouter, uma chave por etapa; a chave
nunca é impressa, gravada nem repetida em mensagem de erro.
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

from src.stats_writer import conectar

PROJETO_DIR = Path(__file__).resolve().parent.parent
DESTINO = PROJETO_DIR / "docs" / "executivo" / "numeros.md"
URL_CHAVE_OPENROUTER = "https://openrouter.ai/api/v1/key"
TIMEOUT_CUSTO = 15

CABECALHO = (
    "<!-- Gerado por scripts/gerar_numeros.py. "
    "Não edite à mão: rode make docs-gerar. -->\n\n"
)

# Ordem da tabela de custo. Cada variável é uma etapa; a chave geral entra por
# último, para que uma chave repetida seja atribuída à etapa específica.
CHAVES_ETAPAS = (
    ("OPENROUTER_KEY_TAXONOMIA_EDITAL", "Taxonomia do edital"),
    ("OPENROUTER_KEY_SINONIMOS", "Sinônimos"),
    ("OPENROUTER_KEY_CURADORIA_ARVORE", "Curadoria da árvore"),
    ("OPENROUTER_KEY_CLASSIFICACAO_QUESTOES", "Classificação das questões"),
    ("OPENROUTER_KEY_TELEGRAM", "Bot do Telegram"),
    ("OPENROUTER_API_KEY", "Chave geral (fallback e etapas antigas)"),
)


class ErroCusto(RuntimeError):
    """Falha ao consultar o custo no OpenRouter. A mensagem nunca traz a chave."""


# ------------------------------------------------------------------ banco


SQL_INVENTARIO = (
    "select ano, count(*) from public.inv_concurso group by ano order by ano"
)
SQL_CONCURSOS = (
    "select status_revisao, count(*) from public.concursos group by status_revisao"
)
SQL_CARGOS = "select count(*) from public.cargos_editais"
SQL_CADERNOS = "select count(*) from public.provas"
SQL_QUESTOES_TOTAL = "select count(*) from public.questoes"
SQL_QUESTOES_TIPO = "select tipo, count(*) from public.questoes group by tipo"
SQL_QUESTOES_ANULADAS = "select count(*) from public.questoes where anulada"
SQL_QUESTOES_UTILIZAVEIS = "select count(*) from public.vw_questoes_utilizaveis"
SQL_DISCURSIVAS = "select count(*) from public.discursivas"
SQL_ARVORE = (
    "select nivel, count(*) from public.no_arvore where status = 'ativo' group by nivel"
)
SQL_ITENS_EDITAL = "select count(*) from public.taxonomia_itens"
SQL_SUBITENS_EDITAL = "select count(*) from public.taxonomia_subitens"
SQL_APONTAMENTOS = "select count(*) from public.questao_no"


def _um_valor(cur, sql: str) -> int:
    cur.execute(sql)
    return int(cur.fetchone()[0])


def _pares(cur, sql: str) -> dict:
    cur.execute(sql)
    return {chave: int(total) for chave, total in cur.fetchall()}


def coletar_banco(conn) -> dict:
    """Números do banco, só com leituras no schema `public`.

    Devolve um dict com: `inventario` (lista de (ano, total)), `concursos`
    (status -> total), `cargos`, `cadernos`, `questoes` (total, tipo,
    anuladas, utilizaveis, discursivas), `arvore` (nível -> total ativo),
    `itens_edital`, `subitens_edital` e `apontamentos`.
    """
    # Transação só de leitura: nenhuma consulta abaixo pode gravar.
    conn.set_session(readonly=True)
    cur = conn.cursor()
    try:
        cur.execute(SQL_INVENTARIO)
        inventario = [(int(ano), int(total)) for ano, total in cur.fetchall()]
        por_tipo = _pares(cur, SQL_QUESTOES_TIPO)
        return {
            "inventario": inventario,
            "concursos": _pares(cur, SQL_CONCURSOS),
            "cargos": _um_valor(cur, SQL_CARGOS),
            "cadernos": _um_valor(cur, SQL_CADERNOS),
            "questoes": {
                "total": _um_valor(cur, SQL_QUESTOES_TOTAL),
                "certo_errado": por_tipo.get("certo_errado", 0),
                "multipla_escolha": por_tipo.get("multipla_escolha", 0),
                "anuladas": _um_valor(cur, SQL_QUESTOES_ANULADAS),
                "utilizaveis": _um_valor(cur, SQL_QUESTOES_UTILIZAVEIS),
                "discursivas": _um_valor(cur, SQL_DISCURSIVAS),
            },
            "arvore": _pares(cur, SQL_ARVORE),
            "itens_edital": _um_valor(cur, SQL_ITENS_EDITAL),
            "subitens_edital": _um_valor(cur, SQL_SUBITENS_EDITAL),
            "apontamentos": _um_valor(cur, SQL_APONTAMENTOS),
        }
    finally:
        cur.close()
        conn.rollback()


# ------------------------------------------------------------------ custo


def _custo_da_chave(chave: str, nome: str) -> float:
    """US$ acumulado da chave, lido de `data.usage` do OpenRouter."""
    try:
        resposta = requests.get(
            URL_CHAVE_OPENROUTER,
            headers={"Authorization": f"Bearer {chave}"},
            timeout=TIMEOUT_CUSTO,
        )
    except requests.RequestException as exc:
        raise ErroCusto(
            f"{nome}: falha de rede ao consultar o OpenRouter ({type(exc).__name__})"
        ) from None
    if resposta.status_code != 200:
        raise ErroCusto(f"{nome}: o OpenRouter respondeu HTTP {resposta.status_code}")
    try:
        return float(resposta.json()["data"]["usage"])
    except (ValueError, KeyError, TypeError):
        raise ErroCusto(f"{nome}: resposta do OpenRouter sem data.usage") from None


def coletar_custo() -> dict:
    """Custo acumulado de LLM por etapa, em US$.

    Lê as chaves do `.env`. Variável vazia é ignorada, e uma chave que aparece
    em duas variáveis conta uma vez só (vale a primeira, na ordem de
    `CHAVES_ETAPAS`). Devolve `{"etapas": [{"nome", "usd"}], "total": float}`.
    """
    load_dotenv(PROJETO_DIR / ".env")
    etapas = []
    vistas: set[str] = set()
    for variavel, nome in CHAVES_ETAPAS:
        chave = os.getenv(variavel, "").strip()
        if not chave or chave in vistas:
            continue
        vistas.add(chave)
        etapas.append({"nome": nome, "usd": _custo_da_chave(chave, nome)})
    return {"etapas": etapas, "total": sum(e["usd"] for e in etapas)}


# ------------------------------------------------------------------ formato


def _inteiro(valor: int) -> str:
    """Número no formato brasileiro: 3410 -> 3.410."""
    return f"{valor:,}".replace(",", ".")


def _usd(valor: float) -> str:
    """Dólar no formato brasileiro, com 2 a 4 casas: 0.31 -> US$ 0,31; 0.0042 -> US$ 0,0042."""
    inteiro, _, decimal = f"{valor:.4f}".partition(".")
    decimal = decimal.rstrip("0").ljust(2, "0")
    return f"US$ {_inteiro(int(inteiro))},{decimal}"


def _data(dia: date) -> str:
    return dia.strftime("%d/%m/%Y")


def _tabela(cabecalhos: tuple[str, str], linhas: list[tuple[str, str]]) -> list[str]:
    saida = [f"| {cabecalhos[0]} | {cabecalhos[1]} |", "|---|---:|"]
    saida += [f"| {nome} | {valor} |" for nome, valor in linhas]
    return [*saida, ""]


# ------------------------------------------------------------------ página


def pagina_numeros(banco: dict, custo: dict | None, gerado_em: date) -> str:
    """Markdown da página de números. Função pura: não lê banco nem rede.

    `custo=None` quer dizer que a consulta ao OpenRouter não foi feita nesta
    geração (`--sem-custo`), e a seção de custo diz isso.
    """
    concursos = banco["concursos"]
    total_concursos = sum(concursos.values())
    total_inventario = sum(total for _, total in banco["inventario"])
    questoes = banco["questoes"]
    arvore = banco["arvore"]

    linhas = [
        CABECALHO.rstrip("\n"),
        "",
        "# Números",
        "",
        f"Atualizado em {_data(gerado_em)}, a partir do banco do projeto.",
        "",
        "## Cobertura",
        "",
        "O inventário lista os concursos encerrados do CEBRASPE a partir de 2020, "
        "ano a ano. A base mostra quantos desses já foram carregados: cada concurso "
        "tem cargos e cadernos de prova. Os concursos carregados entram na conta de "
        "aprovados quando o dono revisa e aprova cada um.",
        "",
        "| Ano | Concursos no inventário |",
        "|---|---:|",
        *[f"| {ano} | {_inteiro(total)} |" for ano, total in banco["inventario"]],
        f"| **Total** | **{_inteiro(total_inventario)}** |",
        "",
    ]
    linhas += _tabela(
        ("Indicador", "Quantidade"),
        [
            ("Concursos carregados na base", _inteiro(total_concursos)),
            (
                "Concursos aprovados pelo dono",
                _inteiro(concursos.get("aprovado", 0)),
            ),
            ("Cargos dos editais", _inteiro(banco["cargos"])),
            ("Cadernos de prova", _inteiro(banco["cadernos"])),
        ],
    )

    linhas += [
        "## Questões",
        "",
        "As questões saem das provas já extraídas. Certo ou errado (C/E) é o formato "
        "em que cada afirmativa é julgada certa ou errada. Múltipla escolha tem "
        "alternativas de A a E. Uma questão anulada foi cancelada pela banca. "
        "Utilizável é a questão que passou pela checagem da extração e pode aparecer "
        "no site. Discursivas são as questões dissertativas, que não entram na conta "
        "de C/E e de múltipla escolha.",
        "",
    ]
    linhas += _tabela(
        ("Indicador", "Quantidade"),
        [
            ("Total de questões", _inteiro(questoes["total"])),
            ("Certo ou errado (C/E)", _inteiro(questoes["certo_errado"])),
            ("Múltipla escolha", _inteiro(questoes["multipla_escolha"])),
            ("Anuladas", _inteiro(questoes["anuladas"])),
            ("Utilizáveis no site", _inteiro(questoes["utilizaveis"])),
            ("Discursivas", _inteiro(questoes["discursivas"])),
        ],
    )

    linhas += [
        "## Árvore de assuntos",
        "",
        "O conteúdo é organizado em três níveis: a matéria é a disciplina (por "
        "exemplo, Língua Portuguesa), o assunto é um tema dentro dela e o subassunto "
        "é o ponto mais fino, que é a unidade de estudo do site. Os itens do edital "
        "são os tópicos que o edital diz que a banca cobra. Um apontamento liga uma "
        "questão a um nó da árvore (matéria, assunto ou subassunto), e uma questão "
        "pode ter até dois.",
        "",
    ]
    linhas += _tabela(
        ("Indicador", "Quantidade"),
        [
            ("Matérias ativas", _inteiro(arvore.get("materia", 0))),
            ("Assuntos ativos", _inteiro(arvore.get("assunto", 0))),
            ("Subassuntos ativos", _inteiro(arvore.get("subassunto", 0))),
            ("Itens do edital", _inteiro(banco["itens_edital"])),
            ("Subitens do edital", _inteiro(banco["subitens_edital"])),
            (
                "Apontamentos questão → nó da árvore",
                _inteiro(banco["apontamentos"]),
            ),
        ],
    )

    linhas += ["## Custo do LLM", ""]
    if custo is None:
        linhas += [
            "O custo não foi consultado nesta geração (`--sem-custo`). Os valores "
            "abaixo ficam de fora até a próxima geração com consulta.",
            "",
        ]
    else:
        linhas += [
            "Quanto o projeto gastou com modelo de linguagem, em dólar. Cada valor é o "
            "total acumulado pela chave de API da etapa, lido no OpenRouter. "
            "O modelo usado é o `z-ai/glm-5.3-flash`. As etapas listadas são as que "
            "chamam o modelo: taxonomia dos editais, sinônimos, curadoria da árvore, "
            "classificação das questões e o bot do Telegram. A leitura das questões e "
            "do gabarito e a estatística que alimenta o site são feitas por regra, sem "
            "modelo. Uma chave trocada recomeça o acumulado do zero, então o total é "
            "um piso do gasto desde o início do projeto.",
            "",
        ]
        # O total entra como última linha da tabela: fora dela, a quebra de
        # página do PDF deixava o total sozinho numa folha.
        linhas += _tabela(
            ("Etapa", "Custo acumulado"),
            [
                *[(e["nome"], _usd(e["usd"])) for e in custo["etapas"]],
                ("**Total**", f"**{_usd(custo['total'])}**"),
            ],
        )

    return "\n".join(linhas).rstrip() + "\n"


# ------------------------------------------------------------------ CLI


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Gera a página de números da visão executiva a partir do banco "
        "e do custo de LLM no OpenRouter."
    )
    ap.add_argument(
        "--sem-custo",
        action="store_true",
        help="não consulta o OpenRouter; a seção de custo diz que não foi consultada",
    )
    ap.add_argument(
        "--saida",
        type=Path,
        default=DESTINO,
        help="arquivo Markdown a gravar (padrão: docs/executivo/numeros.md)",
    )
    args = ap.parse_args(argv)

    conn = conectar()
    try:
        banco = coletar_banco(conn)
    finally:
        conn.close()

    custo = None
    if not args.sem_custo:
        try:
            custo = coletar_custo()
        except ErroCusto as exc:
            print(
                f"Erro ao consultar o custo: {exc}. Rode com --sem-custo para gerar "
                "a página sem a seção de custo.",
                file=sys.stderr,
            )
            return 1

    texto = pagina_numeros(banco, custo, date.today())
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(texto, encoding="utf-8")
    print(f"Página gravada em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
