"""Relatório visual de classificação de questões na árvore mestre (Etapa 5D, ADR-030).

Gera `revisao_piloto/relatorio/classificacao.html`, servido pelo Datasette/Traefik
e linkado em `index.html`. Apresenta:
- Indicadores agregados no topo (total de itens, propostos, aprovados, rejeitados,
  sem nó, fora do edital e distribuição por confiança: alta, média, baixa);
- Agrupamento por caderno com índice rápido de navegação;
- Ordenação por criticidade de atenção humana:
  1. Itens sem nó (`sem_no = true`) no topo absoluto;
  2. Questões com confiança `baixa`;
  3. Questões com confiança `media`;
  4. Questões com confiança `alta`;
- Exibição de cada item: enunciado completo, gabarito oficial, seção contextual,
  texto-base expansível em <details>, caminho completo na árvore mestre
  (Matéria › Assunto › Subassunto), selo de 'fora do edital' e comandos CLI sugeridos.

Uso:
    python -m scripts.gerar_relatorio_classificacao [revisao_piloto_dir]
"""

from __future__ import annotations

import sys
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_revisao import CSS, RELATORIO_SUBDIR
from src import arvore as arv_mod
from src import classificacao as classif_mod
from src.logger import logger
from src.stats_writer import conectar

REVISAO_DIR_PADRAO = Path(__file__).resolve().parent.parent / "revisao_piloto"
ARQUIVO_HTML = "classificacao.html"

CSS_CLASSIFICACAO = """
.totais-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
.total-card { background: color-mix(in srgb, CanvasText 6%, Canvas); border-radius: 8px; padding: 0.8rem 1rem; text-align: center; }
.total-card strong { display: block; font-size: 1.4rem; margin-bottom: 0.2rem; }
.total-card.destaque-alerta strong { color: #dc2626; }
.total-card.destaque-aviso strong { color: #ea580c; }
.total-card.destaque-sucesso strong { color: #16a34a; }

.indice-cadernos { background: color-mix(in srgb, CanvasText 4%, Canvas); border-radius: 8px; padding: 1rem; margin-bottom: 2rem; border: 1px solid color-mix(in srgb, CanvasText 12%, Canvas); }
.indice-cadernos summary { font-weight: 600; cursor: pointer; font-size: 1.05rem; }
.lista-indice-cadernos { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 0.5rem; list-style: none; padding: 0.8rem 0 0 0; margin: 0; }
.lista-indice-cadernos li { font-size: 0.85rem; padding: 0.3rem 0.5rem; border-radius: 4px; background: color-mix(in srgb, CanvasText 3%, Canvas); }
.lista-indice-cadernos a { text-decoration: none; font-weight: 500; }
.lista-indice-cadernos a:hover { text-decoration: underline; }

.secao-caderno { margin-bottom: 3rem; border-top: 2px solid color-mix(in srgb, CanvasText 20%, Canvas); padding-top: 1.5rem; }
.caderno-header { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.8rem; margin-bottom: 1rem; }
.caderno-titulo { font-size: 1.25rem; font-weight: 700; margin: 0; }
.caderno-meta { font-size: 0.85rem; opacity: 0.8; }

.questao-card { border: 1px solid color-mix(in srgb, CanvasText 15%, Canvas); border-radius: 8px; margin-bottom: 1.2rem; padding: 1rem; background: color-mix(in srgb, CanvasText 2%, Canvas); }
.questao-card.crit-sem-no { border-left: 6px solid #dc2626; background: color-mix(in srgb, #dc2626 4%, Canvas); }
.questao-card.crit-baixa { border-left: 6px solid #ea580c; background: color-mix(in srgb, #ea580c 4%, Canvas); }
.questao-card.crit-media { border-left: 4px solid #0284c7; }
.questao-card.crit-alta { border-left: 3px solid color-mix(in srgb, CanvasText 20%, Canvas); }

.questao-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.6rem; }
.questao-id { font-weight: 700; font-size: 1rem; }
.questao-badges { display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }

.badge-conf { padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
.badge-conf.alta { background: #16a34a; color: #ffffff; }
.badge-conf.media { background: #0284c7; color: #ffffff; }
.badge-conf.baixa { background: #ea580c; color: #ffffff; }
.badge-conf.sem_no { background: #dc2626; color: #ffffff; }

.badge-fora { background: #b45309; color: #ffffff; padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }

.badge-status { padding: 0.15rem 0.45rem; border-radius: 4px; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
.badge-status.proposto { background: color-mix(in srgb, #f59e0b 20%, Canvas); color: #b45309; }
.badge-status.aprovado { background: color-mix(in srgb, #10b981 20%, Canvas); color: #059669; }
.badge-status.rejeitado { background: color-mix(in srgb, #ef4444 20%, Canvas); color: #dc2626; }

.gabarito-tag { font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; }
.gabarito-C { background: color-mix(in srgb, #16a34a 20%, Canvas); color: #16a34a; border: 1px solid #16a34a; }
.gabarito-E { background: color-mix(in srgb, #dc2626 20%, Canvas); color: #dc2626; border: 1px solid #dc2626; }
.gabarito-X { background: color-mix(in srgb, #6b7280 20%, Canvas); color: #6b7280; text-decoration: line-through; border: 1px solid #6b7280; }

.secao-enunciado { font-size: 0.85rem; font-style: italic; opacity: 0.85; margin: 0.3rem 0; padding-left: 0.5rem; border-left: 2px solid color-mix(in srgb, CanvasText 25%, Canvas); }
.texto-base-box { background: color-mix(in srgb, CanvasText 5%, Canvas); padding: 0.8rem; border-radius: 6px; font-size: 0.88rem; margin: 0.6rem 0; line-height: 1.45; white-space: pre-wrap; border: 1px dashed color-mix(in srgb, CanvasText 15%, Canvas); }
.enunciado-texto { font-size: 0.95rem; line-height: 1.5; margin: 0.8rem 0; white-space: pre-wrap; }

.apontamento-item { background: color-mix(in srgb, CanvasText 4%, Canvas); padding: 0.6rem 0.8rem; border-radius: 6px; margin-top: 0.6rem; border: 1px solid color-mix(in srgb, CanvasText 10%, Canvas); }
.apontamento-topo { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.3rem; }
.caminho-no { font-weight: 600; font-size: 0.92rem; }
.papel-tag { font-size: 0.75rem; text-transform: uppercase; font-weight: 600; opacity: 0.75; }

.cmd-sugestao { display: block; font-family: monospace; font-size: 0.8rem; padding: 0.3rem 0.6rem; background: color-mix(in srgb, CanvasText 8%, Canvas); border-radius: 4px; margin-top: 0.4rem; overflow-x: auto; color: CanvasText; }
"""


def caminho_no(arv: arv_mod.ArvoreMestre, no_id: str) -> str:
    """Retorna o caminho hierárquico resolvido (Matéria › Assunto › Subassunto)."""
    no_efetivo = arv_mod.resolver_no(arv, no_id)
    partes = []
    curr = no_efetivo
    visitados = set()
    while curr and curr not in visitados:
        visitados.add(curr)
        no = arv.nos.get(curr)
        if not no:
            partes.append(curr)
            break
        partes.append(no.nome)
        curr = no.pai
    return " › ".join(reversed(partes))


def carregar_contexto_questoes(conn=None) -> dict[str, dict[str, Any]]:
    """Carrega dados contextuais de todas as questões e discursivas do Postgres.

    Retorna dicionário indexado pela chave estável:
    `<concurso>|<caderno>|<numero>` ou `<concurso>|<caderno>|D<numero>`.
    """
    if conn is None:
        try:
            conn = conectar()
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"[RELATORIO_CLASSIFICACAO] Banco inacessível ({e}); gerando sem enunciados completos."
            )
            return {}

    contexto: dict[str, dict[str, Any]] = {}
    try:
        with conn.cursor() as cur:
            # 1. Questões objetivas
            cur.execute(
                """
                SELECT c.slug, p.codigo_caderno, q.numero, q.enunciado, q.gabarito, q.anulada, q.secao,
                       tb.texto AS texto_base, o.sigla AS orgao,
                       array_agg(DISTINCT ce.nome) FILTER (WHERE ce.nome IS NOT NULL) AS cargos
                FROM questoes q
                JOIN provas p ON p.id = q.prova_id
                JOIN concursos c ON c.id = p.concurso_id
                JOIN dim_orgao o ON o.id = c.orgao_id
                LEFT JOIN textos_base tb ON tb.id = q.texto_base_id AND tb.prova_id = p.id
                LEFT JOIN provas_cargos pc ON pc.prova_id = p.id
                LEFT JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id
                GROUP BY c.slug, p.codigo_caderno, q.numero, q.enunciado, q.gabarito, q.anulada, q.secao, tb.texto, o.sigla
                """
            )
            for row in cur.fetchall():
                slug, cod_cad, num, enun, gab, anulada, sec, tb_txt, orgao, cargos = row
                chave = f"{slug}|{cod_cad}|{num}"
                contexto[chave] = {
                    "tipo": "objetiva",
                    "concurso": slug,
                    "caderno": cod_cad,
                    "numero": num,
                    "enunciado": enun,
                    "gabarito": "X" if anulada else (gab or ""),
                    "anulada": bool(anulada),
                    "secao": sec or "",
                    "texto_base": tb_txt or "",
                    "orgao": orgao or "",
                    "cargos": cargos or [],
                }

            # 2. Questões discursivas
            cur.execute(
                """
                SELECT c.slug, p.codigo_caderno, d.numero, d.titulo, d.tema, d.enunciado, d.quesitos,
                       o.sigla AS orgao,
                       array_agg(DISTINCT ce.nome) FILTER (WHERE ce.nome IS NOT NULL) AS cargos
                FROM discursivas d
                JOIN provas p ON p.id = d.prova_id
                JOIN concursos c ON c.id = p.concurso_id
                JOIN dim_orgao o ON o.id = c.orgao_id
                LEFT JOIN provas_cargos pc ON pc.prova_id = p.id
                LEFT JOIN cargos_editais ce ON ce.id = pc.cargo_edital_id
                GROUP BY c.slug, p.codigo_caderno, d.numero, d.titulo, d.tema, d.enunciado, d.quesitos, o.sigla
                """
            )
            for row in cur.fetchall():
                slug, cod_cad, num, tit, tema, enun, ques, orgao, cargos = row
                chave = f"{slug}|{cod_cad}|D{num}"
                partes_enun = []
                if tit:
                    partes_enun.append(f"Título: {tit}")
                if tema:
                    partes_enun.append(f"Tema: {tema}")
                if enun:
                    partes_enun.append(enun)
                if ques:
                    partes_enun.append(f"Quesitos:\n{ques}")
                contexto[chave] = {
                    "tipo": "discursiva",
                    "concurso": slug,
                    "caderno": cod_cad,
                    "numero": f"D{num}",
                    "enunciado": "\n\n".join(partes_enun),
                    "gabarito": "Discursiva",
                    "anulada": False,
                    "secao": "",
                    "texto_base": "",
                    "orgao": orgao or "",
                    "cargos": cargos or [],
                }
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[RELATORIO_CLASSIFICACAO] Falha ao consultar questões no banco: {e}"
        )
    return contexto


def _extrair_caderno_chave(chave: str) -> tuple[str, str]:
    """Retorna (concurso_slug, codigo_caderno) a partir da chave estável."""
    partes = chave.split("|")
    if len(partes) >= 2:
        return partes[0], partes[1]
    return partes[0], ""


def _prioridade_item(reg: classif_mod.RegistroQuestao) -> tuple[int, int, int]:
    """Calcula a ordem de prioridade de atenção humana para o item.

    0 = sem_no (topo absoluto)
    1 = baixa
    2 = media
    3 = alta
    """
    partes = reg.chave.split("|")
    num_str = partes[-1] if partes else "0"
    is_disc = num_str.startswith("D")
    try:
        num_val = int(num_str[1:] if is_disc else num_str)
    except ValueError:
        num_val = 9999

    if reg.sem_no or not reg.apontamentos:
        return (0, 1 if is_disc else 0, num_val)

    confs = [ap.confianca for ap in reg.apontamentos]
    if "baixa" in confs:
        prio = 1
    elif "media" in confs:
        prio = 2
    else:
        prio = 3

    return (prio, 1 if is_disc else 0, num_val)


def renderizar_relatorio(
    cq: classif_mod.ClassificacaoQuestoes,
    arv: arv_mod.ArvoreMestre,
    contexto: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Renderiza a página HTML completa de auditoria da classificação."""
    contexto = contexto or {}

    total_registros = len(cq.registros)
    total_sem_no = sum(1 for r in cq.registros.values() if r.sem_no)
    total_fora_edital = 0

    cont_conf: dict[str, int] = defaultdict(int)
    cont_status: dict[str, int] = defaultdict(int)

    # Agrupar registros por caderno
    cadernos_map: dict[str, list[classif_mod.RegistroQuestao]] = defaultdict(list)

    for reg in cq.registros.values():
        _, cod_cad = _extrair_caderno_chave(reg.chave)
        cadernos_map[cod_cad].append(reg)

        for ap in reg.apontamentos:
            cont_conf[ap.confianca] += 1
            cont_status[ap.status] += 1
            if ap.fora_do_edital:
                total_fora_edital += 1

    # Totais de status
    total_propostos = cont_status.get("proposto", 0)
    total_aprovados = cont_status.get("aprovado", 0)
    total_rejeitados = cont_status.get("rejeitado", 0)

    # Ordenar cadernos: primeiro os que têm itens sem_no ou baixa confiança
    def _ordem_caderno(cod: str) -> tuple[int, str]:
        itens = cadernos_map[cod]
        tem_sem_no = any(r.sem_no for r in itens)
        tem_baixa = any(
            any(a.confianca == "baixa" for a in r.apontamentos) for r in itens
        )
        if tem_sem_no:
            return (0, cod)
        if tem_baixa:
            return (1, cod)
        return (2, cod)

    cadernos_ordenados = sorted(cadernos_map.keys(), key=_ordem_caderno)

    # Montar índice de cadernos
    itens_indice = []
    for cod in cadernos_ordenados:
        itens = cadernos_map[cod]
        slug_conc, _ = _extrair_caderno_chave(itens[0].chave)
        qtd_sem_no = sum(1 for r in itens if r.sem_no)
        qtd_baixa = sum(
            1
            for r in itens
            if any(a.confianca == "baixa" for a in r.apontamentos) and not r.sem_no
        )

        tags_alerta = []
        if qtd_sem_no > 0:
            tags_alerta.append(
                f"<span class='badge-conf sem_no'>{qtd_sem_no} sem nó</span>"
            )
        if qtd_baixa > 0:
            tags_alerta.append(
                f"<span class='badge-conf baixa'>{qtd_baixa} baixa</span>"
            )

        tags_str = (" " + " ".join(tags_alerta)) if tags_alerta else ""
        itens_indice.append(
            f"<li><a href='#caderno-{escape(cod)}'><code>{escape(cod)}</code> ({escape(slug_conc)})</a> "
            f"<span>{len(itens)} itens</span>{tags_str}</li>"
        )

    # Montar blocos de cada caderno
    blocos_cadernos = []
    for cod in cadernos_ordenados:
        regs = sorted(cadernos_map[cod], key=_prioridade_item)
        slug_conc, _ = _extrair_caderno_chave(regs[0].chave)

        # Informações contextuais do caderno a partir do primeiro item
        ctx_primeiro = contexto.get(regs[0].chave, {})
        orgao = ctx_primeiro.get("orgao", "")
        cargos = ctx_primeiro.get("cargos", [])
        cargos_str = ", ".join(cargos) if cargos else "Não informado"

        cards_itens = []
        for reg in regs:
            ctx = contexto.get(reg.chave, {})
            prio_classe, _, _ = _prioridade_item(reg)
            crit_classes = {
                0: "crit-sem-no",
                1: "crit-baixa",
                2: "crit-media",
                3: "crit-alta",
            }
            card_classe = crit_classes.get(prio_classe, "crit-alta")

            # Header do card
            partes_chave = reg.chave.split("|")
            item_num = partes_chave[-1] if len(partes_chave) >= 3 else reg.chave

            gabarito = ctx.get("gabarito", "")
            gab_html = ""
            if gabarito:
                gab_classe = (
                    f"gabarito-{gabarito}"
                    if gabarito in ("C", "E", "X")
                    else "badge-conf media"
                )
                gab_rotulo = (
                    f"Gabarito: {gabarito}"
                    if gabarito != "X"
                    else "Gabarito: Anulada (X)"
                )
                gab_html = (
                    f"<span class='gabarito-tag {gab_classe}'>{gab_rotulo}</span>"
                )

            badges_header = [gab_html]
            if reg.sem_no:
                badges_header.append(
                    "<span class='badge-conf sem_no'>⚠️ SEM NÓ NA ÁRVORE</span>"
                )

            # Seção contextual
            secao = ctx.get("secao")
            secao_html = (
                f"<div class='secao-enunciado'>📌 {escape(secao)}</div>"
                if secao
                else ""
            )

            # Texto-base expansível
            tb_txt = ctx.get("texto_base")
            tb_html = ""
            if tb_txt:
                tb_html = (
                    f"<details><summary>📄 Ver Texto-base associado</summary>"
                    f"<div class='texto-base-box'>{escape(tb_txt)}</div></details>"
                )

            # Enunciado
            enunciado = ctx.get("enunciado", "")
            if not enunciado:
                enunciado = (
                    f"[Enunciado não carregado do banco. Hash: {reg.hash_enunciado}]"
                )
            enun_html = f"<div class='enunciado-texto'>{escape(enunciado)}</div>"

            # Apontamentos
            apontamentos_html = []
            if reg.sem_no:
                apontamentos_html.append(
                    f"<div class='apontamento-item'>"
                    f"<em>Nenhum nó serviu na lista preferencial nem na de reserva. Aguarda decisão humana.</em>"
                    f"<pre class='cmd-sugestao'><code>python -m scripts.curar_classificacao --mapear '{escape(reg.chave)}:NO_ID'</code></pre>"
                    f"</div>"
                )
            else:
                for ap in reg.apontamentos:
                    caminho = caminho_no(arv, ap.no_id)
                    no_obj = arv.nos.get(arv_mod.resolver_no(arv, ap.no_id))
                    nivel_str = f"({no_obj.nivel})" if no_obj else ""

                    fora_html = (
                        "<span class='badge-fora'>FORA DO EDITAL</span> "
                        if ap.fora_do_edital
                        else ""
                    )
                    conf_badge = f"<span class='badge-conf {escape(ap.confianca)}'>Confiança: {escape(ap.confianca)}</span>"
                    status_badge = f"<span class='badge-status {escape(ap.status)}'>{escape(ap.status)}</span>"
                    papel_badge = f"<span class='papel-tag'>[{escape(ap.papel)}]</span>"

                    cmd_aprovar = f"python -m scripts.curar_classificacao --aprovar '{escape(reg.chave)}:{escape(ap.no_id)}'"
                    cmd_rejeitar = f"python -m scripts.curar_classificacao --rejeitar '{escape(reg.chave)}:{escape(ap.no_id)}'"

                    apontamentos_html.append(
                        f"<div class='apontamento-item'>"
                        f"  <div class='apontamento-topo'>"
                        f"    <span class='caminho-no'>🌳 {escape(caminho)} <small>{nivel_str}</small> <code>{escape(ap.no_id)}</code></span>"
                        f"    <div>{papel_badge} {fora_html}{conf_badge} {status_badge}</div>"
                        f"  </div>"
                        f"  <pre class='cmd-sugestao'><code>{cmd_aprovar}</code><br><code>{cmd_rejeitar}</code></pre>"
                        f"</div>"
                    )

            cards_itens.append(
                f"<div class='questao-card {card_classe}'>"
                f"  <div class='questao-header'>"
                f"    <span class='questao-id'>Item {escape(item_num)} "
                f"      <small style='opacity:0.75;'>({escape(reg.chave)})</small></span>"
                f"    <div class='questao-badges'>{' '.join(badges_header)}</div>"
                f"  </div>"
                f"  {secao_html}"
                f"  {tb_html}"
                f"  {enun_html}"
                f"  {''.join(apontamentos_html)}"
                f"</div>"
            )

        blocos_cadernos.append(
            f"<section class='secao-caderno' id='caderno-{escape(cod)}'>"
            f"  <div class='caderno-header'>"
            f"    <div>"
            f"      <h2 class='caderno-titulo'>Caderno <code>{escape(cod)}</code></h2>"
            f"      <div class='caderno-meta'>Concurso: <strong>{escape(slug_conc)}</strong> | "
            f"Órgão: <strong>{escape(orgao)}</strong> | Cargos: <em>{escape(cargos_str)}</em></div>"
            f"    </div>"
            f"    <div class='caderno-meta'><a href='#top'>↑ Voltar ao índice</a></div>"
            f"  </div>"
            f"  {''.join(cards_itens)}"
            f"</section>"
        )

    # HTML final
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Classificação de Questões na Árvore Mestre</title>
<style>
{CSS}
{CSS_CLASSIFICACAO}
</style>
</head>
<body id="top">
<p><a href="index.html">← Índice de relatórios</a> | <a href="arvore.html">Árvore Mestre</a></p>

<h1>Classificação de Questões na Árvore Mestre (Etapa 5D)</h1>
<p>Auditoria visual das <strong>{total_registros}</strong> questões extraídas e classificadas por modelo de linguagem estruturado. Fonte canônica: <code>canonico/classificacao_questoes.json</code>.</p>

<div class="totais-grid">
  <div class="total-card"><strong>{total_registros}</strong>Total Itens</div>
  <div class="total-card {"destaque-aviso" if total_propostos else ""}"><strong>{total_propostos}</strong>Propostos</div>
  <div class="total-card {"destaque-sucesso" if total_aprovados else ""}"><strong>{total_aprovados}</strong>Aprovados</div>
  <div class="total-card"><strong>{total_rejeitados}</strong>Rejeitados</div>
  <div class="total-card {"destaque-alerta" if total_sem_no else ""}"><strong>{total_sem_no}</strong>Sem Nó</div>
  <div class="total-card"><strong>{total_fora_edital}</strong>Fora do Edital</div>
  <div class="total-card destaque-sucesso"><strong>{cont_conf.get("alta", 0)}</strong>Confiança Alta</div>
  <div class="total-card"><strong>{cont_conf.get("media", 0)}</strong>Confiança Média</div>
  <div class="total-card {"destaque-aviso" if cont_conf.get("baixa", 0) else ""}"><strong>{cont_conf.get("baixa", 0)}</strong>Confiança Baixa</div>
</div>

<details class="indice-cadernos" open>
  <summary>Índice de Cadernos ({len(cadernos_ordenados)} cadernos extraídos)</summary>
  <ul class="lista-indice-cadernos">
    {"".join(itens_indice)}
  </ul>
</details>

{"".join(blocos_cadernos)}

<hr>
<p><small>Relatório gerado automaticamente por <code>scripts/gerar_relatorio_classificacao.py</code>.</small></p>
</body>
</html>
"""


def gerar_relatorio_classificacao(
    revisao_dir: Path = REVISAO_DIR_PADRAO,
    classificacao_path: Path = classif_mod.CLASSIFICACAO_PADRAO,
    arvore_path: Path = arv_mod.ARVORE_PADRAO,
    conn=None,
) -> Path:
    """Gera o arquivo HTML `revisao_piloto/relatorio/classificacao.html`."""
    cq = classif_mod.carregar(classificacao_path)
    arv = arv_mod.carregar(arvore_path)
    contexto = carregar_contexto_questoes(conn=conn)

    html = renderizar_relatorio(cq, arv, contexto=contexto)
    saida = revisao_dir / RELATORIO_SUBDIR / ARQUIVO_HTML
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")
    logger.info(f"[CLASSIFICACAO] Relatório HTML gerado em {saida}")
    return saida


if __name__ == "__main__":
    diretorio = Path(sys.argv[1]) if len(sys.argv) > 1 else REVISAO_DIR_PADRAO
    gerar_relatorio_classificacao(diretorio)
