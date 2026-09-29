"""Proposta de sinônimos pelo LLM, sobre lista fechada de IDs (Etapa 5B, ADR-029).

Roda **só quando chamado explicitamente**: custa tokens, então não faz parte
de `scripts/atualizar_revisao.py` (que roda só as regras determinísticas e o
relatório, sem LLM).

Três passos, em ordem: (1) matérias; (2) assuntos dentro de cada matéria
canônica; (3) subassuntos dentro de cada assunto. Em cada passo, o LLM recebe
blocos (escopos) com os grupos aprovados que as regras não juntaram, cada um
com um ID local curto, e devolve grupos com nome canônico. Validação local
(`canonico.validar_agrupamento`): cada ID em exatamente um grupo, sem ID
desconhecido e sem grupo misturando blocos — senão é falha tipada. Se a
resposta falhar nessa validação, a segunda tentativa leva o erro no prompt
(não é retry cego, ADR-021).

Tudo sai `proposto` (origem `llm`): nada muda no banco até o dono aprovar
com `scripts/aprovar_sinonimos.py`.

Uso:
    python -m scripts.propor_sinonimos [--niveis materia,assunto,subassunto]
        [--limite-itens 90] [--reavaliar] [--dry-run]

Reexecução só paga pelos blocos com item ainda não avaliado
(`avaliados_llm` no JSON); `--reavaliar` força todos.
"""

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_sinonimos import gerar_relatorio_sinonimos
from src import canonico, llm_openrouter
from src.llm_openrouter import (
    ResultadoPosValidacao,
    chamar_llm_json,
)
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"

# Itens por chamada ao juntar escopos pequenos. Um escopo sozinho só é
# dividido acima de `LIMITE_ITENS_ESCOPO` (loga aviso: sinônimo entre pedaços
# diferentes não é visto) — as ~93 matérias vão numa chamada só.
LIMITE_ITENS_LOTE = 90
LIMITE_ITENS_ESCOPO = 200
MAX_TOKENS = 16000
TIMEOUT = 240
TENTATIVAS = 2
BACKOFF_SEGUNDOS = 5

DESCRICAO_NIVEL = {
    "materia": "matérias (disciplinas) de editais de concurso",
    "assunto": "assuntos (tópicos de primeiro nível) de uma mesma matéria",
    "subassunto": "subassuntos (itens de segundo nível) de um mesmo assunto",
}

PROMPT_SISTEMA = """Você agrupa sinônimos em taxonomias de editais de concurso público brasileiro.
Recebe blocos de nomes; cada nome tem um ID. Junte num mesmo grupo SOMENTE nomes que
designam exatamente o mesmo conteúdo, escrito de outra forma: ordem diferente das
palavras ("Administração Financeira e Orçamentária" = "Administração Orçamentária e
Financeira"), nome oficial × nome usual ("Contabilidade Pública" = "Contabilidade
Aplicada ao Setor Público"), sigla × nome por extenso, número de norma × nome da norma.

NUNCA junte:
- conceitos vizinhos ou do mesmo campo ("atos administrativos" × "contratos
  administrativos", "mensuração de ativos" × "mensuração de passivos", "gestão de
  processos" × "gestão de pessoas");
- um tema amplo com um subtema ou com uma parte dele ("Direito Constitucional" ×
  "Direito Constitucional e Processo Legislativo");
- nomes só parecidos na escrita.
Na dúvida, deixe separado: um agrupamento errado corrompe a estatística; um sinônimo
não agrupado só fica para a revisão humana.

Regras da resposta:
- Todo ID recebido aparece em exatamente um grupo. Nome sem sinônimo vira grupo de 1 ID.
- Nunca invente ID e nunca junte IDs de blocos diferentes.
- "nome_canonico": o nome mais claro e completo do grupo, em português, sem numeração.
- "justificativa": curta, só para grupos com 2 ou mais IDs.
Devolva APENAS JSON, sem markdown:
{"grupos": [{"ids": ["i1", "i7"], "nome_canonico": "...", "justificativa": "..."}, ...]}"""


class GrupoProposto(BaseModel):
    ids: list[str] = Field(min_length=1)
    # Opcional: o modelo às vezes omite o nome nos grupos de 1 ID (achado na
    # execução real de 2026-09-25, `falha_validacao_schema` num lote inteiro).
    # Grupo de 2+ IDs sem nome recebe o nome determinístico da regra.
    nome_canonico: str = ""
    justificativa: str | None = None


class RespostaAgrupamento(BaseModel):
    grupos: list[GrupoProposto]


@dataclass
class Lote:
    nivel: str
    blocos: list[tuple[canonico.Escopo, list[str]]]  # (escopo, IDs de grupo do bloco)
    ids_locais: dict[str, str] = field(default_factory=dict)  # local -> gid


@dataclass
class Contabilidade:
    chamadas: int = 0
    falhas: Counter = field(default_factory=Counter)
    lotes_ok: int = 0
    lotes_falhos: int = 0
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0
    propostas: Counter = field(default_factory=Counter)

    def registrar_usage(self, usage: dict | None) -> None:
        usage = usage or {}
        self.tokens_entrada += usage.get("prompt_tokens", 0) or 0
        self.tokens_saida += usage.get("completion_tokens", 0) or 0
        self.custo_usd += float(usage.get("cost", 0) or 0)


def montar_lotes(
    escopos: list[canonico.Escopo],
    limite: int = LIMITE_ITENS_LOTE,
    limite_escopo: int = LIMITE_ITENS_ESCOPO,
) -> list[Lote]:
    """Empacota escopos em lotes de até `limite` itens, sem quebrar escopo
    (salvo o que sozinho passa de `limite_escopo`)."""
    pedacos: list[tuple[canonico.Escopo, list[str]]] = []
    for esc in escopos:
        if len(esc.itens) > limite_escopo:
            logger.warning(
                f"[SINONIMOS] {esc.nivel} '{esc.rotulo}': {len(esc.itens)} itens, dividido em "
                f"pedaços de {limite_escopo} — sinônimo entre pedaços diferentes não é visto."
            )
        for i in range(0, len(esc.itens), limite_escopo):
            pedacos.append((esc, esc.itens[i : i + limite_escopo]))

    lotes: list[Lote] = []
    atual: list[tuple[canonico.Escopo, list[str]]] = []
    for pedaco in pedacos:
        if atual and sum(len(p[1]) for p in atual) + len(pedaco[1]) > limite:
            lotes.append(Lote(pedaco[0].nivel, atual))
            atual = []
        atual.append(pedaco)
    if atual:
        lotes.append(Lote(atual[0][0].nivel, atual))
    return lotes


def _rotulo_item(estado: dict, nivel: str, gid: str) -> str:
    g = estado[nivel]["grupos"][gid]
    variantes = sorted(
        {
            n["nome"]
            for e in g["membros"]
            for n in estado[nivel]["entradas"].get(e, {}).get("nomes", [])
        }
        - {g["nome"]}
    )
    texto = g["nome"]
    if variantes:
        texto += f"  [também escrito: {'; '.join(variantes[:2])}]"
    if nivel == "materia":
        # Alguns assuntos ajudam a separar matéria de nome genérico
        # ("LEGISLAÇÃO", "LEGISLAÇÃO ESPECIAL").
        assuntos = [
            e["nomes"][0]["nome"]
            for e in estado["assunto"]["entradas"].values()
            if e["pai"] in g["membros"] and e.get("presente") and e["nomes"]
        ]
        if assuntos:
            exemplos = sorted(
                {canonico.PADRAO_NUMERACAO.sub("", a).strip() for a in assuntos}
            )[:3]
            texto += f"  (ex.: {'; '.join(exemplos)})"
    return texto


def montar_prompt(estado: dict, lote: Lote) -> tuple[str, dict[str, list[str]]]:
    """Texto do usuário e IDs locais por bloco (a lista fechada)."""
    linhas = [f"Agrupe os sinônimos entre {DESCRICAO_NIVEL[lote.nivel]}.", ""]
    ids_por_bloco: dict[str, list[str]] = {}
    contador = 0
    for b_idx, (esc, itens) in enumerate(lote.blocos, start=1):
        bloco = f"B{b_idx}"
        linhas.append(f"### Bloco {bloco} — {esc.rotulo}")
        ids_por_bloco[bloco] = []
        for gid in itens:
            contador += 1
            local = f"i{contador}"
            lote.ids_locais[local] = gid
            ids_por_bloco[bloco].append(local)
            linhas.append(f"- {local}: {_rotulo_item(estado, lote.nivel, gid)}")
        linhas.append("")
    return "\n".join(linhas), ids_por_bloco


def _pos_validacao(ids_por_bloco: dict[str, list[str]]):
    def validar(resposta: RespostaAgrupamento, _content: str) -> ResultadoPosValidacao:
        motivo, detalhe = canonico.validar_agrupamento(
            ids_por_bloco, [g.ids for g in resposta.grupos]
        )
        if motivo:
            return ResultadoPosValidacao(
                motivo=motivo,
                erro=f"[SINONIMOS_{motivo.upper()}] {detalhe}",
                metadata={
                    "validacao_lista_fechada": {"status": motivo, "detalhe": detalhe}
                },
            )
        return ResultadoPosValidacao(
            objeto=resposta, metadata={"validacao_lista_fechada": {"status": "ok"}}
        )

    return validar


def propor_lote(
    estado: dict, lote: Lote, conta: Contabilidade, dry_run: bool = False
) -> int:
    """Chama o LLM para um lote e grava as propostas (grupos com 2+ itens).
    Retorna o número de propostas gravadas."""
    prompt, ids_por_bloco = montar_prompt(estado, lote)
    if dry_run:
        logger.info(
            f"[SINONIMOS] (dry-run) {lote.nivel}: lote com {len(lote.ids_locais)} itens.\n{prompt}"
        )
        return 0

    resultado = None
    correcao = ""
    for tentativa in range(1, TENTATIVAS + 1):
        conta.chamadas += 1
        resultado = chamar_llm_json(
            PROMPT_SISTEMA,
            prompt + correcao,
            RespostaAgrupamento,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT,
            extras_payload={"usage": {"include": True}},
            metadata={
                "etapa": "5B",
                "nivel": lote.nivel,
                "itens": len(lote.ids_locais),
                "tentativa": tentativa,
            },
            pos_validacao=_pos_validacao(ids_por_bloco),
            nome_generation=f"propor_sinonimos_{lote.nivel}",
            nome_trace=llm_openrouter.ETAPA_SINONIMOS[1],
            api_key=llm_openrouter.chave_openrouter(llm_openrouter.ETAPA_SINONIMOS),
        )
        conta.registrar_usage(resultado.usage)
        if resultado.motivo is None:
            break
        conta.falhas[resultado.motivo] += 1
        if (
            resultado.motivo.startswith("falha_id")
            or resultado.motivo == canonico.STATUS_FALHA_GRUPO_ENTRE_BLOCOS
        ):
            # Segunda tentativa com o erro no prompt (não é retry cego).
            correcao = (
                f"\n\nATENÇÃO: uma resposta anterior foi rejeitada ({resultado.motivo}). "
                "Use todos os IDs listados, cada um exatamente uma vez, sem inventar ID e sem "
                "misturar blocos."
            )
        if tentativa < TENTATIVAS:
            time.sleep(BACKOFF_SEGUNDOS)

    if resultado is None or resultado.motivo is not None:
        conta.lotes_falhos += 1
        logger.error(
            f"[SINONIMOS] {lote.nivel}: lote de {len(lote.ids_locais)} itens falhou ({resultado.motivo})."
        )
        return 0

    conta.lotes_ok += 1
    for esc, itens in lote.blocos:
        canonico.marcar_avaliados(estado, lote.nivel, itens, esc.escopo_id)
    bloco_do_local = {i: b for b, ids in ids_por_bloco.items() for i in ids}
    escopo_do_bloco = {
        f"B{i}": esc.escopo_id for i, (esc, _) in enumerate(lote.blocos, start=1)
    }
    gravadas = 0
    for grupo in resultado.objeto.grupos:
        if len(grupo.ids) < 2:
            continue
        gids = [lote.ids_locais[i] for i in grupo.ids]
        membros = sorted(
            {e for gid in gids for e in estado[lote.nivel]["grupos"][gid]["membros"]}
        )
        escopo = escopo_do_bloco[bloco_do_local[grupo.ids[0]]]
        nome = grupo.nome_canonico.strip() or canonico.nome_exibicao(
            estado, lote.nivel, membros
        )
        gid_novo = canonico.registrar_proposta(
            estado,
            lote.nivel,
            membros,
            nome,
            escopo,
            grupo.justificativa,
        )
        if gid_novo:
            gravadas += 1
            logger.info(
                f"[SINONIMOS] proposto {gid_novo} ({lote.nivel}) '{nome}': "
                + " | ".join(estado[lote.nivel]["grupos"][g]["nome"] for g in gids)
            )
    conta.propostas[lote.nivel] += gravadas
    return gravadas


def propor_sinonimos(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    niveis: tuple[str, ...] = canonico.NIVEIS,
    limite: int = LIMITE_ITENS_LOTE,
    dry_run: bool = False,
    sinonimos_path: Path | None = None,
    reavaliar: bool = False,
) -> Contabilidade:
    sinonimos_path = sinonimos_path or canonico.caminho_sinonimos(revisao_dir)
    estado = canonico.carregar(sinonimos_path)
    nomes = canonico.coletar_nomes(revisao_dir)
    canonico.aplicar_regras(estado, nomes)
    conta = Contabilidade()
    for nivel in niveis:
        escopos = canonico.montar_escopos(estado, nivel, nomes, reavaliar=reavaliar)
        lotes = montar_lotes(escopos, limite)
        logger.info(
            f"[SINONIMOS] {nivel}: {len(escopos)} escopos, {sum(len(e.itens) for e in escopos)} itens, "
            f"{len(lotes)} lotes."
        )
        for lote in lotes:
            propor_lote(estado, lote, conta, dry_run=dry_run)
            if not dry_run:
                # Checkpoint por lote: uma falha adiante não perde o que já foi pago.
                canonico.salvar(estado, sinonimos_path)
    if not dry_run:
        canonico.salvar(estado, sinonimos_path)
        gerar_relatorio_sinonimos(revisao_dir, sinonimos_path)
    logger.info(
        f"[SINONIMOS] Fim: {conta.chamadas} chamadas, {conta.lotes_ok} lotes ok, {conta.lotes_falhos} falhos, "
        f"falhas por tipo {dict(conta.falhas)}, propostas {dict(conta.propostas)}, "
        f"tokens {conta.tokens_entrada} entrada / {conta.tokens_saida} saída, custo US$ {conta.custo_usd:.4f}."
    )
    return conta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("revisao_dir", nargs="?", type=Path, default=REVISAO_DIR_PADRAO)
    parser.add_argument("--niveis", default=",".join(canonico.NIVEIS))
    parser.add_argument("--limite-itens", type=int, default=LIMITE_ITENS_LOTE)
    parser.add_argument(
        "--reavaliar",
        action="store_true",
        help="manda de novo ao LLM blocos já avaliados (padrão: só blocos com item novo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="só monta e loga os prompts, sem chamar o LLM",
    )
    args = parser.parse_args(argv)
    niveis = tuple(n.strip() for n in args.niveis.split(",") if n.strip())
    invalidos = set(niveis) - set(canonico.NIVEIS)
    if invalidos:
        parser.error(f"níveis inválidos: {sorted(invalidos)}")
    conta = propor_sinonimos(
        args.revisao_dir,
        niveis,
        args.limite_itens,
        args.dry_run,
        reavaliar=args.reavaliar,
    )
    print(
        json.dumps(
            {
                **conta.__dict__,
                "falhas": dict(conta.falhas),
                "propostas": dict(conta.propostas),
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
