"""Proposta de operações na árvore mestre pelo LLM (Etapa 5B.2, ADR-030).

Uso:
    python -m scripts.propor_arvore [--materias M-...,M-...] [--so-regras]
        [--dry-run] [--reavaliar] [--arvore caminho] [revisao_dir]

Roda a curadoria da árvore mestre por matéria via LLM (chamar_llm_json com
REASONING_PADRAO e nome_trace="propor_arvore"). A árvore é apresentada com
IDs locais curtos (n1, n2...) para economia de tokens e precisão.

Operações propostas pelo modelo:
- fundir: junta nós irmãos do mesmo nível que tratam do mesmo assunto.
- mover: ajusta granularidade/pertencimento (subassunto -> assunto, assunto -> matéria).

Validação estrita local (pos_validacao):
- ID desconhecido vira STATUS_FALHA_ID_DESCONHECIDO ("falha_id_desconhecido").
- Nível errado, ciclo ou fusão inválida vira STATUS_FALHA_OPERACAO_INVALIDA
  ("falha_operacao_invalida") via simulação em cópia isolada (copy.deepcopy).
- Em caso de falha na 1ª tentativa, a 2ª tentativa leva o erro e instruções no prompt.

Escopos especiais:
- Matérias com menos de 2 assuntos são puladas.
- Escopo coordenado da Câmara dos Deputados (M-841dde7520, M-d5adcb4de4):
  cria proposta humano para matéria "Processo Legislativo" (decisão do dono 2026-09-28),
  redistribui assuntos, remapeia 2 itens de matéria e propõe aposentadoria.
- Licitações (M-6f50f4f1dd): orienta realocação dos subassuntos de A-4529f205f7
  e propõe aposentadoria do composto uma vez liberado.

Idempotência:
- Hash SHA-1 da subárvore ativo por matéria salvo em arquivo sidecar (.propor_arvore_cache.json).
  Reexecução só reavalia matérias alteradas, a menos que --reavaliar seja passado.
- Checkpoint por lote: salva arvore.json após cada matéria avaliada.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_arvore import gerar_relatorio_arvore
from src import arvore
from src.llm_openrouter import (
    REASONING_PADRAO,
    ResultadoPosValidacao,
    chamar_llm_json,
)
from src.logger import logger

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
ARVORE_PATH_PADRAO = Path(__file__).resolve().parent.parent / "canonico" / "arvore.json"

MAX_TOKENS = 16000
TIMEOUT = 240
TENTATIVAS = 2
BACKOFF_SEGUNDOS = 5

STATUS_FALHA_ID_DESCONHECIDO = "falha_id_desconhecido"
STATUS_FALHA_OPERACAO_INVALIDA = "falha_operacao_invalida"

# Constantes de escopos especiais
MATERIAS_CD_COMPOSTAS = ("M-841dde7520", "M-d5adcb4de4")
MATERIAS_CD_DESTINO = ("M-5edb4898a0", "M-e96f4dbbb5")
ID_LICITACOES_COMPOSTO = "A-4529f205f7"
ID_LICITACOES_DESTINOS = ("A-2261b82645", "A-91e52e6c2e")
MATERIA_DIR_ADMINISTRATIVO = "M-6f50f4f1dd"

PROMPT_SISTEMA = """Você é um especialista em taxonomia e estruturação curricular de editais de concurso público brasileiro.
Seu objetivo é propor curadorias na árvore de disciplinas (matéria > assunto > subassunto), sugerindo fusões e movimentos estritamente necessários.

OPERAÇÕES PERMITIDAS:
1. "fundir" (fusão de nós equivalentes):
   - Junte APENAS nós do MESMO NÍVEL (assunto com assunto, ou subassunto com subassunto) que tratam EXATAMENTE do mesmo conteúdo com grafias ou redações diferentes.
   - NUNCA junte conceitos distintos, complementares ou vizinhos (ex: "Licitação" != "Contratos Administrativos", "Atos" != "Poderes", "Direito Constitucional" != "Processo Legislativo").
   - Na dúvida, NÃO funda: mantenha separado.
   - Em 'ids': [id_origem, id_destino]. A origem será incorporada no destino.

2. "mover" (ajuste de granularidade ou pertencimento):
   - Subassunto só pode ser movido para outro Assunto.
   - Assunto só pode ser movido para outra Matéria.
   - NUNCA crie ciclos hierárquicos e NUNCA mova um nó para um nível incompatível.
   - Em 'ids': [id_no, id_novo_pai]. O nó passará a ser filho do novo pai.

REGRAS ESTRITAS:
- Use APENAS os IDs locais listados no prompt do usuário (ex: n1, n2...). NUNCA invente novos IDs.
- Se a estrutura atual já estiver adequada e não necessitar de alterações, retorne a lista vazia: {"propostas": []}.
- Em 'justificativa', apresente uma explicação concisa e técnica.

Devolva APENAS JSON válido no seguinte formato, sem markdown:
{"propostas": [{"tipo": "fundir", "ids": ["n1", "n2"], "justificativa": "..."}, ...]}"""


class PropostaOperacaoLLM(BaseModel):
    tipo: Literal["fundir", "mover"]
    ids: list[str] = Field(min_length=2, max_length=2)
    justificativa: str = ""


class RespostaProposicaoArvore(BaseModel):
    propostas: list[PropostaOperacaoLLM] = Field(default_factory=list)


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


def calcular_hash_subarvore(arv: arvore.ArvoreMestre, materia_id: str) -> str:
    """Calcula um hash SHA-1 determinístico da subárvore ativa de uma matéria."""
    materia = arv.nos.get(materia_id)
    if not materia:
        return ""

    nos_subarvore: list[tuple[str, str, str, str, str]] = [
        (
            materia.id,
            materia.nivel,
            materia.nome,
            materia.pai or "",
            materia.status,
        )
    ]

    assuntos = [
        n
        for n in arv.nos.values()
        if n.nivel == "assunto" and n.pai == materia_id and n.status == "ativo"
    ]
    assuntos.sort(key=lambda x: x.id)
    assunto_ids = {a.id for a in assuntos}

    for a in assuntos:
        nos_subarvore.append((a.id, a.nivel, a.nome, a.pai or "", a.status))

    subassuntos = [
        n
        for n in arv.nos.values()
        if n.nivel == "subassunto" and n.pai in assunto_ids and n.status == "ativo"
    ]
    subassuntos.sort(key=lambda x: x.id)
    for s in subassuntos:
        nos_subarvore.append((s.id, s.nivel, s.nome, s.pai or "", s.status))

    conteudo = json.dumps(nos_subarvore, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(conteudo.encode("utf-8")).hexdigest()


def _calcular_hash_escopo_cd(arv: arvore.ArvoreMestre) -> str:
    """Calcula hash determinístico para o conjunto de matérias compostas do CD."""
    nos_cd: list[tuple[str, str, str, str, str]] = []
    for m_id in MATERIAS_CD_COMPOSTAS:
        m = arv.nos.get(m_id)
        if m:
            nos_cd.append((m.id, m.nivel, m.nome, m.pai or "", m.status))
            assuntos = [
                n
                for n in arv.nos.values()
                if n.nivel == "assunto" and n.pai == m_id and n.status == "ativo"
            ]
            assuntos.sort(key=lambda x: x.id)
            for a in assuntos:
                nos_cd.append((a.id, a.nivel, a.nome, a.pai or "", a.status))

    conteudo = json.dumps(nos_cd, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(conteudo.encode("utf-8")).hexdigest()


def _carregar_cache(cache_path: Path) -> dict[str, str]:
    if cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"[ARVORE] Falha ao ler cache {cache_path}: {e}")
    return {}


def _salvar_cache(cache: dict[str, str], cache_path: Path) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8"
        )
    except (OSError, TypeError) as e:
        logger.warning(f"[ARVORE] Falha ao salvar cache {cache_path}: {e}")


def montar_prompt_materia(
    arv: arvore.ArvoreMestre, materia_id: str
) -> tuple[str, dict[str, str]]:
    """Monta o prompt textual hierárquico com IDs locais para uma matéria."""
    materia = arv.nos[materia_id]
    assuntos = [
        n
        for n in arv.nos.values()
        if n.nivel == "assunto" and n.pai == materia_id and n.status == "ativo"
    ]
    assuntos.sort(key=lambda x: x.nome)

    ids_locais: dict[str, str] = {}
    contador = 1
    linhas = [
        f"Matéria: {materia.nome} ({materia_id})",
        "",
        "Estrutura da disciplina (assuntos e subassuntos):",
    ]

    for ass in assuntos:
        local_ass = f"n{contador}"
        ids_locais[local_ass] = ass.id
        contador += 1
        linhas.append(f"- {local_ass}: [assunto] {ass.nome}")

        subassuntos = [
            n
            for n in arv.nos.values()
            if n.nivel == "subassunto" and n.pai == ass.id and n.status == "ativo"
        ]
        subassuntos.sort(key=lambda x: x.nome)
        for sub in subassuntos:
            local_sub = f"n{contador}"
            ids_locais[local_sub] = sub.id
            contador += 1
            linhas.append(f"  - {local_sub}: [subassunto] {sub.nome}")

    if materia_id == MATERIA_DIR_ADMINISTRATIVO and ID_LICITACOES_COMPOSTO in arv.nos:
        composto = arv.nos[ID_LICITACOES_COMPOSTO]
        filhos = [
            n
            for n in arv.nos.values()
            if n.nivel == "subassunto"
            and n.pai == ID_LICITACOES_COMPOSTO
            and n.status == "ativo"
        ]
        if filhos:
            linhas.extend(
                [
                    "",
                    "INSTRUÇÃO ESPECIAL PARA NÓ COMPOSTO DE LICITAÇÕES E CONTRATOS:",
                    f"O assunto '{composto.nome}' ({ID_LICITACOES_COMPOSTO}) é um nó composto que será aposentado.",
                    f"Ele possui {len(filhos)} subassuntos ativos que DEVEM ser realocados:",
                    "- Para temas de licitação/processo licitatório, mova para o assunto 'Licitação' (A-2261b82645) ou funda com subassunto equivalente;",
                    "- Para temas contratuais/execução contratual, mova para o assunto 'Contratos administrativos' (A-91e52e6c2e) ou funda com subassunto equivalente.",
                ]
            )

    return "\n".join(linhas), ids_locais


def montar_prompt_cd(
    arv: arvore.ArvoreMestre, proc_leg_id: str
) -> tuple[str, dict[str, str]]:
    """Monta o prompt para o escopo coordenado da Câmara dos Deputados (CD)."""
    ids_locais: dict[str, str] = {}
    contador = 1
    linhas = [
        "ESCOPO COORDENADO DA CÂMARA DOS DEPUTADOS (CD):",
        "As matérias compostas M-841dde7520 e M-d5adcb4de4 serão aposentadas.",
        "Todos os seus assuntos devem ser redistribuídos para as matérias adequadas:",
        "1. Se o assunto tiver correspondente EXATO em Direito Constitucional ou Regimento Interno, proponha 'fundir' (ids: [origem_local, destino_local]).",
        "2. Caso contrário, proponha 'mover' o assunto para uma das matérias de destino (ids: [assunto_local, materia_destino_local]).",
        "",
        "MATÉRIAS DE DESTINO DISPONÍVEIS:",
    ]

    # Matérias de destino
    destinos_materias = [
        ("M-5edb4898a0", "DIREITO CONSTITUCIONAL"),
        (
            "M-e96f4dbbb5",
            "REGIMENTO INTERNO DA CÂMARA DOS DEPUTADOS, REGIMENTO COMUM E CÓDIGO DE ÉTICA",
        ),
        (proc_leg_id, "Processo Legislativo"),
    ]
    for mid, mnome in destinos_materias:
        local_id = f"n{contador}"
        ids_locais[local_id] = mid
        contador += 1
        linhas.append(f"- {local_id}: [matéria] {mnome}")

    # Assuntos existentes para fusão
    linhas.extend(
        [
            "",
            "ASSUNTOS EXISTENTES EM DIREITO CONSTITUCIONAL E REGIMENTO INTERNO (DESTINOS DE FUSÃO):",
        ]
    )
    for mid in ("M-5edb4898a0", "M-e96f4dbbb5"):
        m_no = arv.nos.get(mid)
        if not m_no:
            continue
        assuntos_dest = [
            n
            for n in arv.nos.values()
            if n.nivel == "assunto" and n.pai == mid and n.status == "ativo"
        ]
        assuntos_dest.sort(key=lambda x: x.nome)
        for a in assuntos_dest:
            local_id = f"n{contador}"
            ids_locais[local_id] = a.id
            contador += 1
            linhas.append(f"- {local_id}: [assunto de {m_no.nome}] {a.nome}")

    # Assuntos a redistribuir
    linhas.extend(
        [
            "",
            "ASSUNTOS A REDISTRIBUIR DAS MATÉRIAS COMPOSTAS:",
        ]
    )
    for mid in MATERIAS_CD_COMPOSTAS:
        m_no = arv.nos.get(mid)
        if not m_no:
            continue
        assuntos_src = [
            n
            for n in arv.nos.values()
            if n.nivel == "assunto" and n.pai == mid and n.status == "ativo"
        ]
        assuntos_src.sort(key=lambda x: x.nome)
        for a in assuntos_src:
            local_id = f"n{contador}"
            ids_locais[local_id] = a.id
            contador += 1
            linhas.append(
                f"- {local_id}: [assunto a redistribuir de {m_no.nome}] {a.nome}"
            )

    return "\n".join(linhas), ids_locais


def _pos_validacao_arvore(
    arv: arvore.ArvoreMestre,
    ids_locais: dict[str, str],
    materia_id: str,
    ultimo_erro: list[str] | None = None,
):
    """Retorna função de validação semântica com verificação de IDs locais e simulação."""

    def validar(
        resposta: RespostaProposicaoArvore, _content: str
    ) -> ResultadoPosValidacao:
        # 1. Validar IDs locais desconhecidos
        desconhecidos = []
        for prop in resposta.propostas:
            for lid in prop.ids:
                if lid not in ids_locais:
                    desconhecidos.append(lid)
        if desconhecidos:
            msg = (
                f"[{STATUS_FALHA_ID_DESCONHECIDO.upper()}] IDs locais "
                f"desconhecidos ou inventados: {sorted(set(desconhecidos))}"
            )
            if ultimo_erro is not None:
                ultimo_erro[0] = msg
            return ResultadoPosValidacao(
                motivo=STATUS_FALHA_ID_DESCONHECIDO,
                erro=msg,
                metadata={
                    "tipo_erro": STATUS_FALHA_ID_DESCONHECIDO,
                    "ids": desconhecidos,
                },
            )

        # 2. Simulação em cópia isolada (copy.deepcopy)
        copia = copy.deepcopy(arv)
        for prop in resposta.propostas:
            id1 = ids_locais[prop.ids[0]]
            id2 = ids_locais[prop.ids[1]]
            if prop.tipo == "fundir":
                args = {"origem": id1, "destino": id2}
            elif prop.tipo == "mover":
                args = {"no": id1, "pai": id2}
            else:
                msg = f"[{STATUS_FALHA_OPERACAO_INVALIDA.upper()}] Tipo de operação desconhecido: {prop.tipo}"
                if ultimo_erro is not None:
                    ultimo_erro[0] = msg
                return ResultadoPosValidacao(
                    motivo=STATUS_FALHA_OPERACAO_INVALIDA,
                    erro=msg,
                    metadata={"tipo_erro": STATUS_FALHA_OPERACAO_INVALIDA},
                )

            try:
                arvore.propor(
                    copia,
                    tipo=prop.tipo,
                    args=args,
                    origem="llm",
                    justificativa=prop.justificativa or "",
                    materia=materia_id if materia_id != "ESCOPO_CD" else "",
                )
            except arvore.ArvoreInvalida as e:
                msg = f"[{STATUS_FALHA_OPERACAO_INVALIDA.upper()}] {e}"
                if ultimo_erro is not None:
                    ultimo_erro[0] = msg
                return ResultadoPosValidacao(
                    motivo=STATUS_FALHA_OPERACAO_INVALIDA,
                    erro=msg,
                    metadata={
                        "tipo_erro": STATUS_FALHA_OPERACAO_INVALIDA,
                        "detalhe": str(e),
                    },
                )

        return ResultadoPosValidacao(objeto=resposta, metadata={"status": "ok"})

    return validar


def propor_lote(
    arv: arvore.ArvoreMestre,
    prompt: str,
    ids_locais: dict[str, str],
    materia_id: str,
    conta: Contabilidade,
    dry_run: bool = False,
) -> int:
    """Executa o loop de 2 tentativas de proposta do LLM com validação e feedback de erro."""
    if dry_run:
        logger.info(
            f"[ARVORE] (dry-run) Matéria {materia_id}: {len(ids_locais)} nós no lote.\n{prompt}"
        )
        return 0

    resultado = None
    correcao = ""
    ultimo_erro = [""]
    for tentativa in range(1, TENTATIVAS + 1):
        conta.chamadas += 1
        prompt_envio = prompt + correcao
        resultado = chamar_llm_json(
            PROMPT_SISTEMA,
            prompt_envio,
            RespostaProposicaoArvore,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT,
            reasoning=REASONING_PADRAO,
            extras_payload={"usage": {"include": True}},
            metadata={
                "etapa": "5B.2",
                "materia": materia_id,
                "itens": len(ids_locais),
                "tentativa": tentativa,
            },
            pos_validacao=_pos_validacao_arvore(
                arv, ids_locais, materia_id, ultimo_erro
            ),
            nome_generation=f"propor_arvore_{materia_id}",
            nome_trace="propor_arvore",
        )
        conta.registrar_usage(resultado.usage)
        if resultado.motivo is None:
            break

        conta.falhas[resultado.motivo] += 1
        if resultado.motivo in (
            STATUS_FALHA_ID_DESCONHECIDO,
            STATUS_FALHA_OPERACAO_INVALIDA,
        ):
            correcao = (
                f"\n\nATENÇÃO: uma resposta anterior foi rejeitada ({resultado.motivo}). "
                f"Detalhe: {ultimo_erro[0]}\n"
                "Por favor, revise a taxonomia e corrija os erros:\n"
                "- Use APENAS os IDs locais listados acima, sem inventar nenhum ID.\n"
                "- Fusões ('fundir') só podem ser feitas entre nós do mesmo nível.\n"
                "- Movimentos ('mover') devem respeitar a hierarquia (subassunto -> assunto, assunto -> matéria) e nunca criar ciclos.\n"
                '- Se não houver fusões ou movimentos claros e seguros, retorne lista vazia: {"propostas": []}.'
            )
        if tentativa < TENTATIVAS:
            time.sleep(BACKOFF_SEGUNDOS)

    if resultado is None or resultado.motivo is not None:
        conta.lotes_falhos += 1
        logger.error(
            f"[ARVORE] Matéria {materia_id} falhou ({resultado.motivo if resultado else 'sem_resultado'})."
        )
        return 0

    conta.lotes_ok += 1
    gravadas = 0
    for prop in resultado.objeto.propostas:
        id1 = ids_locais[prop.ids[0]]
        id2 = ids_locais[prop.ids[1]]
        if prop.tipo == "fundir":
            args = {"origem": id1, "destino": id2}
        elif prop.tipo == "mover":
            args = {"no": id1, "pai": id2}
        else:
            continue

        try:
            prop_id = arvore.propor(
                arv,
                tipo=prop.tipo,
                args=args,
                origem="llm",
                justificativa=prop.justificativa or "",
                materia=materia_id if materia_id != "ESCOPO_CD" else "",
            )
            gravadas += 1
            conta.propostas[prop.tipo] += 1
            logger.info(
                f"[ARVORE] Proposta {prop_id} ({prop.tipo}): {args} - {prop.justificativa}"
            )
        except arvore.ArvoreInvalida as e:
            logger.warning(f"[ARVORE] Proposta rejeitada na gravação final: {e}")

    return gravadas


def _tratar_aposentadoria_licitacoes(
    arv: arvore.ArvoreMestre, materia_id: str, conta: Contabilidade
) -> None:
    """Tenta propor aposentadoria do nó de licitações se seus filhos foram realocados."""
    if ID_LICITACOES_COMPOSTO not in arv.nos:
        return
    no = arv.nos[ID_LICITACOES_COMPOSTO]
    if no.status != "ativo":
        return

    try:
        prop_id = arvore.propor(
            arv,
            tipo="aposentar",
            args={"no": ID_LICITACOES_COMPOSTO},
            origem="regra",
            justificativa=(
                f"Aposentadoria de nó composto {ID_LICITACOES_COMPOSTO} "
                "após redistribuição de seus subassuntos"
            ),
            materia=materia_id,
        )
        conta.propostas["aposentar"] += 1
        logger.info(
            f"[ARVORE] Proposta de aposentadoria gerada para {ID_LICITACOES_COMPOSTO}: {prop_id}"
        )
    except arvore.ArvoreInvalida as e:
        logger.info(
            f"[ARVORE] Aposentadoria de {ID_LICITACOES_COMPOSTO} ainda não permitida: {e}"
        )


def _processar_escopo_cd(
    arv: arvore.ArvoreMestre,
    conta: Contabilidade,
    cache: dict[str, str],
    cache_path: Path,
    arvore_path: Path,
    dry_run: bool = False,
) -> int:
    """Processa o escopo coordenado da Câmara dos Deputados (CD)."""
    # 1. Proposta humano para criação da matéria "Processo Legislativo"
    proc_leg = next(
        (
            n
            for n in arv.nos.values()
            if n.nivel == "materia" and n.nome.strip().lower() == "processo legislativo"
        ),
        None,
    )
    if proc_leg is None:
        if not dry_run:
            prop_proc = arvore.propor(
                arv,
                tipo="criar",
                args={"nivel": "materia", "nome": "Processo Legislativo"},
                origem="humano",
                justificativa="Criação da matéria Processo Legislativo conforme decisão do dono (2026-09-28)",
            )
            conta.propostas["criar"] += 1
            logger.info(
                f"[ARVORE] Proposta de criação da matéria Processo Legislativo: {prop_proc}"
            )
            proc_leg = next(
                (
                    n
                    for n in arv.nos.values()
                    if n.nivel == "materia"
                    and n.nome.strip().lower() == "processo legislativo"
                ),
                None,
            )
        else:
            # Em dry-run gera o ID determinístico em memória
            nome_proc = "Processo Legislativo"
            digest = hashlib.sha1(f"|{nome_proc}".encode()).hexdigest()[:10]
            proc_leg_id = f"NM-{digest}"
            proc_leg = arvore.NoArvore(
                id=proc_leg_id,
                nivel="materia",
                nome=nome_proc,
                pai=None,
                origem="humano",
                status="proposto",
            )

    proc_leg_id = (
        proc_leg.id
        if proc_leg
        else f"NM-{hashlib.sha1(b'|Processo Legislativo').hexdigest()[:10]}"
    )

    # 2. Montar prompt e chamar LLM para redistribuição dos assuntos
    prompt, ids_locais = montar_prompt_cd(arv, proc_leg_id)
    gravadas = propor_lote(arv, prompt, ids_locais, "ESCOPO_CD", conta, dry_run=dry_run)

    if not dry_run:
        # 3. Propor remapeamento dos 2 itens de nível matéria
        if "direito constitucional e processo legislativo" in arv.mapeamentos:
            try:
                prop_rem1 = arvore.propor(
                    arv,
                    tipo="remapear",
                    args={
                        "item": "direito constitucional e processo legislativo",
                        "de": "M-841dde7520",
                        "para": ["M-5edb4898a0", proc_leg_id],
                    },
                    origem="regra",
                    justificativa="Remapeamento de matéria composta para Direito Constitucional e Processo Legislativo",
                    materia="M-841dde7520",
                )
                conta.propostas["remapear"] += 1
                logger.info(
                    f"[ARVORE] Remapeamento proposto para direito constitucional e processo legislativo: {prop_rem1}"
                )
            except arvore.ArvoreInvalida as e:
                logger.info(f"[ARVORE] Remapeamento M-841dde7520 ignorado: {e}")

        if (
            "nocoes de direito constitucional e de regimento interno da camara dos deputados"
            in arv.mapeamentos
        ):
            try:
                prop_rem2 = arvore.propor(
                    arv,
                    tipo="remapear",
                    args={
                        "item": "nocoes de direito constitucional e de regimento interno da camara dos deputados",
                        "de": "M-d5adcb4de4",
                        "para": ["M-5edb4898a0", "M-e96f4dbbb5"],
                    },
                    origem="regra",
                    justificativa="Remapeamento de matéria composta para Direito Constitucional e Regimento Interno",
                    materia="M-d5adcb4de4",
                )
                conta.propostas["remapear"] += 1
                logger.info(
                    f"[ARVORE] Remapeamento proposto para regimento interno: {prop_rem2}"
                )
            except arvore.ArvoreInvalida as e:
                logger.info(f"[ARVORE] Remapeamento M-d5adcb4de4 ignorado: {e}")

        # 4. Propor aposentadoria das 2 matérias compostas
        for mid in MATERIAS_CD_COMPOSTAS:
            if mid in arv.nos and arv.nos[mid].status == "ativo":
                try:
                    prop_ap = arvore.propor(
                        arv,
                        tipo="aposentar",
                        args={"no": mid},
                        origem="regra",
                        justificativa=(
                            f"Aposentadoria de matéria composta {mid} após "
                            "redistribuição de assuntos e remapeamento"
                        ),
                        materia=mid,
                    )
                    conta.propostas["aposentar"] += 1
                    logger.info(
                        f"[ARVORE] Proposta de aposentadoria gerada para {mid}: {prop_ap}"
                    )
                except arvore.ArvoreInvalida as e:
                    logger.info(
                        f"[ARVORE] Aposentadoria de {mid} ainda não permitida: {e}"
                    )

        # 5. Checkpoint
        hash_cd = _calcular_hash_escopo_cd(arv)
        cache["ESCOPO_CD"] = hash_cd
        cache["M-841dde7520"] = hash_cd
        cache["M-d5adcb4de4"] = hash_cd
        _salvar_cache(cache, cache_path)
        arvore.salvar(arv, arvore_path)

    return gravadas


def propor_arvore(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    arvore_path: Path | None = None,
    materias: str = "",
    so_regras: bool = False,
    dry_run: bool = False,
    reavaliar: bool = False,
) -> Contabilidade:
    """Função principal de proposição de árvore."""
    arvore_path = arvore_path or ARVORE_PATH_PADRAO
    arv = arvore.carregar(arvore_path)
    conta = Contabilidade()

    if so_regras:
        logger.info(
            "[ARVORE] Executando detecção determinística de compostos (--so-regras)..."
        )
        detectados = arvore.detectar_compostos(arv)
        logger.info(f"[ARVORE] Compostos detectados: {detectados}")
        homonimos = arvore.detectar_homonimos(arv)
        logger.info(f"[ARVORE] Irmãos homônimos detectados: {homonimos}")
        if not dry_run:
            arvore.salvar(arv, arvore_path)
            try:
                gerar_relatorio_arvore(revisao_dir, arvore_path)
            except (OSError, ValueError, KeyError) as e:
                logger.warning(
                    f"[ARVORE] Não foi possível gerar relatório arvore.html: {e}"
                )
        return conta

    cache_path = arvore_path.parent / ".propor_arvore_cache.json"
    cache = _carregar_cache(cache_path)

    # Filtrar matérias
    if materias.strip():
        ids_alvo = [m.strip() for m in materias.split(",") if m.strip()]
    else:
        ids_alvo = [
            m_id
            for m_id, n in arv.nos.items()
            if n.nivel == "materia" and n.status == "ativo"
        ]

    executar_cd = any(m in MATERIAS_CD_COMPOSTAS for m in ids_alvo)
    materias_padrao = [m for m in ids_alvo if m not in MATERIAS_CD_COMPOSTAS]

    # Processar matérias padrão
    for m_id in materias_padrao:
        m_no = arv.nos.get(m_id)
        if not m_no or m_no.status != "ativo":
            continue

        assuntos_ativos = [
            n
            for n in arv.nos.values()
            if n.nivel == "assunto" and n.pai == m_id and n.status == "ativo"
        ]
        if len(assuntos_ativos) < 2:
            logger.info(
                f"[ARVORE] Matéria {m_id} ('{m_no.nome}') possui {len(assuntos_ativos)} "
                "assunto(s) ativo(s) (< 2). Pulando."
            )
            continue

        hash_atual = calcular_hash_subarvore(arv, m_id)
        if not reavaliar and cache.get(m_id) == hash_atual:
            logger.info(
                f"[ARVORE] Matéria {m_id} inalterada (hash {hash_atual[:8]}). "
                "Pulando (--reavaliar não definido)."
            )
            continue

        prompt, ids_locais = montar_prompt_materia(arv, m_id)
        propor_lote(arv, prompt, ids_locais, m_id, conta, dry_run=dry_run)

        if not dry_run:
            if m_id == MATERIA_DIR_ADMINISTRATIVO:
                _tratar_aposentadoria_licitacoes(arv, m_id, conta)

            cache[m_id] = hash_atual
            _salvar_cache(cache, cache_path)
            # Checkpoint por lote
            arvore.salvar(arv, arvore_path)

    # Processar escopo coordenado CD
    if executar_cd:
        hash_cd = _calcular_hash_escopo_cd(arv)
        if not reavaliar and cache.get("ESCOPO_CD") == hash_cd:
            logger.info(
                f"[ARVORE] Escopo CD inalterado (hash {hash_cd[:8]}). "
                "Pulando (--reavaliar não definido)."
            )
        else:
            _processar_escopo_cd(
                arv,
                conta,
                cache,
                cache_path,
                arvore_path,
                dry_run=dry_run,
            )

    if not dry_run:
        arvore.salvar(arv, arvore_path)
        try:
            gerar_relatorio_arvore(revisao_dir, arvore_path)
        except (OSError, ValueError, KeyError) as e:
            logger.warning(
                f"[ARVORE] Não foi possível gerar relatório arvore.html: {e}"
            )

    logger.info(
        f"[ARVORE] Fim: {conta.chamadas} chamadas, {conta.lotes_ok} lotes ok, "
        f"{conta.lotes_falhos} falhos, falhas por tipo {dict(conta.falhas)}, "
        f"propostas {dict(conta.propostas)}, tokens {conta.tokens_entrada} entrada / "
        f"{conta.tokens_saida} saída, custo US$ {conta.custo_usd:.4f}."
    )
    return conta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("revisao_dir", nargs="?", type=Path, default=REVISAO_DIR_PADRAO)
    parser.add_argument(
        "--arvore",
        type=Path,
        default=None,
        help="Caminho alternativo para arvore.json",
    )
    parser.add_argument(
        "--materias",
        default="",
        help="IDs de matérias separados por vírgula (ex: M-5edb4898a0,M-841dde7520)",
    )
    parser.add_argument(
        "--so-regras",
        action="store_true",
        help="Executa apenas a detecção determinística de compostos, sem chamar LLM",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Monta e loga os prompts sem chamar o OpenRouter nem gravar propostas",
    )
    parser.add_argument(
        "--reavaliar",
        action="store_true",
        help="Reavalia matérias mesmo se o hash da subárvore não tiver mudado",
    )
    args = parser.parse_args(argv)

    conta = propor_arvore(
        revisao_dir=args.revisao_dir,
        arvore_path=args.arvore,
        materias=args.materias,
        so_regras=args.so_regras,
        dry_run=args.dry_run,
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
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
