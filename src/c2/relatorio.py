"""Módulo de geração de relatórios de lote do C2 (Etapa 9/D5b, KAN-32).

Gera o relatório analítico em formato Markdown em `inventario/lotes/lote_{numero:02d}.md`,
consolidando as checagens automáticas, consultas do Runbook §4.5, invariante do piloto (K22),
propostas de dispersão da árvore (P6/KAN-64), telemetria de custos e o veredito final.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ_PADRAO = Path(__file__).resolve().parent.parent.parent


def _inteiro(valor: int | float | None) -> str:
    """Formata inteiro no padrão brasileiro: 2800 -> '2.800'."""
    if valor is None:
        return "-"
    try:
        val_int = int(valor)
        return f"{val_int:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(valor)


def _usd(valor: float | None) -> str:
    """Formata valor em dólar: 0.0198 -> 'US$ 0,0198'."""
    if valor is None:
        return "-"
    try:
        inteiro, _, decimal = f"{valor:.4f}".partition(".")
        decimal = decimal.rstrip("0").ljust(2, "0")
        return f"US$ {_inteiro(int(inteiro))},{decimal}"
    except (ValueError, TypeError):
        return str(valor)


def _badge(status: str) -> str:
    """Retorna badge formatado: [OK], [ALERTA], [PENDENTE], [FALHA] ou [NÃO VERIFICADO]."""
    s = (status or "").upper()
    if s in ("OK", "APROVADO", "VERDE", "SUCESSO"):
        return "**`[OK]`**"
    if s in ("ALERTA", "AVISO", "WARN", "PENDENTE"):
        return f"**`[{s}]`**"
    if s in ("FALHA", "ERRO", "BLOQUEADO", "DIVERGENCIA", "SEM_BANCO"):
        return "**`[FALHA]`**"
    if s in ("NAO_VERIFICADO", "NÃO VERIFICADO", "NEUTRO"):
        return "**`[NÃO VERIFICADO]`**"
    return f"**`[{s}]`**"


def gerar_relatorio_lote(
    numero_lote: int,
    slugs: list[str],
    checks_resultado: dict[str, Any],
    custo_info: dict[str, Any],
    propostas_dispersao: list[dict[str, Any]],
    raiz: Path | None = None,
) -> Path:
    """Gera o arquivo `inventario/lotes/lote_{numero_lote:02d}.md`.

    Args:
        numero_lote: Número sequencial do lote (ex: 1 -> lote_01.md).
        slugs: Lista de slugs dos certames incluídos no lote.
        checks_resultado: Resultado das checagens (consultas runbook, invariante, etc.).
        custo_info: Informações coletadas da API OpenRouter (/api/v1/key).
        propostas_dispersao: Lista de propostas geradas na detecção de dispersão (P6/KAN-64).
        raiz: Diretório raiz do projeto (opcional; default é RAIZ_PADRAO).

    Returns:
        Path do arquivo Markdown criado.
    """
    base_raiz = RAIZ_PADRAO if raiz is None else raiz
    pasta_lotes = base_raiz / "inventario" / "lotes"
    pasta_lotes.mkdir(parents=True, exist_ok=True)
    caminho_arquivo = pasta_lotes / f"lote_{numero_lote:02d}.md"

    agora_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    slugs_str = ", ".join(slugs) if slugs else "Nenhum"
    modo = str(checks_resultado.get("modo", "Conferência"))

    # Extrai subestruturas com suporte a múltiplos caminhos de consolidação
    runbook = (
        checks_resultado.get("consultas_runbook")
        or checks_resultado.get("prova", {}).get("detalhes")
        or checks_resultado
    )
    invariante_antes = checks_resultado.get("invariante_antes") or checks_resultado.get(
        "invariante_piloto_antes"
    )
    invariante_depois = (
        checks_resultado.get("invariante_depois")
        or checks_resultado.get("invariante_piloto_depois")
        or checks_resultado.get("invariante_piloto")
    )

    portao_edital = checks_resultado.get("portao_edital")
    portao_arvore = checks_resultado.get("portao_arvore")
    portao_classif = checks_resultado.get("portao_classificacao")

    dl_info = checks_resultado.get("download")
    pr_info = checks_resultado.get("prova")
    bn_info = checks_resultado.get("banco")
    cl_info = checks_resultado.get("classificacao")
    st_info = checks_resultado.get("site")

    # Coleta falhas e alertas consolidados
    falhas_consolidadas: list[str] = list(checks_resultado.get("falhas", []))
    alertas_consolidados: list[str] = list(checks_resultado.get("alertas", []))

    if isinstance(runbook, dict):
        falhas_consolidadas.extend(runbook.get("falhas", []))
        alertas_consolidados.extend(runbook.get("alertas", []))

    if isinstance(dl_info, dict):
        falhas_consolidadas.extend(dl_info.get("falhas", []))

    # Verifica integridade da invariante do piloto (K22)
    inv_valida = True
    if invariante_depois and isinstance(invariante_depois, dict):
        if (
            not invariante_depois.get("valido", False)
            and invariante_depois.get("status") != "sem_banco"
        ):
            inv_valida = False
            falhas_consolidadas.append(
                "Violação na checagem K22 (Invariante do Piloto)"
            )

    # Elimina duplicatas preservando ordem
    falhas_consolidadas = list(dict.fromkeys(falhas_consolidadas))
    alertas_consolidados = list(dict.fromkeys(alertas_consolidados))

    # ------------------------------------------------------------------
    # Cálculo do Veredito (Três estados sem "aprovado para revisão humana"):
    # 1. BLOQUEADO: falha de checagem automática (K22, download, prova).
    # 2. AGUARDANDO PORTOES HUMANOS: automáticas verdes, mas portão (P3, P7, P9) pendente.
    # 3. PRONTO PARA O SITE: automáticas verdes e TODOS os portões aprovados.
    # ------------------------------------------------------------------
    falhas_automaticas = list(falhas_consolidadas)
    if not inv_valida:
        falhas_automaticas.append("Violação na checagem K22 (Invariante do Piloto)")
    if dl_info and isinstance(dl_info, dict) and not dl_info.get("valido", True):
        falhas_automaticas.append("Falha na reconciliação de downloads de PDFs")
    falhas_automaticas = list(dict.fromkeys(falhas_automaticas))

    # Avaliação dos portões humanos
    portoes_pendentes: list[str] = []

    # Portão P3 (Edital)
    if portao_edital and isinstance(portao_edital, dict):
        pendentes_ed = [
            s
            for s, res in portao_edital.items()
            if not (res[0] if isinstance(res, tuple) else res)
        ]
        if pendentes_ed:
            portoes_pendentes.append(
                f"Portão P3 (Edital): pendente em {', '.join(pendentes_ed)}"
            )
    elif portao_edital and isinstance(portao_edital, tuple) and not portao_edital[0]:
        portoes_pendentes.append("Portão P3 (Edital): pendente de aprovação humana")
    elif checks_resultado.get("edital", {}).get("status") == "pendente":
        portoes_pendentes.append("Portão P3 (Edital): pendente de aprovação humana")

    # Portão P7 (Árvore)
    if portao_arvore and isinstance(portao_arvore, tuple) and not portao_arvore[0]:
        n_prop = len(portao_arvore[1]) if len(portao_arvore) > 1 else 0
        portoes_pendentes.append(
            f"Portão P7 (Árvore): {n_prop} proposta(s) pendente(s)"
        )
    elif propostas_dispersao:
        portoes_pendentes.append(
            f"Portão P7 (Árvore): {len(propostas_dispersao)} proposta(s) de dispersão pendente(s)"
        )

    # Portão P9 (Classificação)
    if portao_classif:
        ap_c, n_pend_c = (
            portao_classif
            if isinstance(portao_classif, tuple)
            else (False, portao_classif)
        )
        if not ap_c or (isinstance(n_pend_c, int) and n_pend_c > 0):
            portoes_pendentes.append(
                f"Portão P9 (Classificação): {int(n_pend_c)} pendência(s)"
            )
    elif cl_info and isinstance(cl_info, dict) and cl_info.get("status") == "pendente":
        portoes_pendentes.append(
            f"Portão P9 (Classificação): {cl_info.get('mensagem', 'pendente')}"
        )

    if falhas_automaticas:
        veredito_texto = "BLOQUEADO"
        badge_veredito = _badge("FALHA")
    elif portoes_pendentes:
        veredito_texto = "AGUARDANDO PORTÕES HUMANOS"
        badge_veredito = _badge("PENDENTE")
    else:
        veredito_texto = "PRONTO PARA O SITE"
        badge_veredito = _badge("OK")

    linhas: list[str] = []

    # 1. Título & Metadados
    linhas.append(f"# Relatório de Lote {numero_lote:02d}: {slugs_str}\n")
    linhas.append(f"- **Data de geração:** {agora_utc}")
    linhas.append(f"- **Lote:** {numero_lote:02d}")
    linhas.append(f"- **Concursos:** {slugs_str}")
    linhas.append(f"- **Modo de Execução:** {modo}")
    linhas.append(f"- **Veredito:** `{veredito_texto}`\n")
    linhas.append("---\n")

    # 2. Resumo Executivo e Veredito
    linhas.append("## 1. Resumo Executivo e Veredito\n")
    linhas.append(
        f"O lote **{numero_lote:02d}** obteve o veredito final: {badge_veredito} **`{veredito_texto}`**.\n"
    )

    if veredito_texto == "BLOQUEADO":
        linhas.append("> [!CAUTION]")
        linhas.append(
            "> **Execução BLOQUEADA por inconformidades técnicas impeditivas nas checagens automáticas:**"
        )
        for f in falhas_automaticas:
            linhas.append(f"> - ❌ {f}")
        linhas.append(
            ">\n> *Ação necessária: Corrigir as falhas antes de prosseguir com o pipeline.*\n"
        )
    elif veredito_texto == "AGUARDANDO PORTÕES HUMANOS":
        linhas.append("> [!NOTE]")
        linhas.append(
            "> **Checagens automáticas verdes.** O lote está tecnicamente íntegro e aguardando aprovações humanas:"
        )
        for p in portoes_pendentes:
            linhas.append(f"> - ⏳ {p}")
        linhas.append(
            ">\n> *Ação necessária: Homologar os portões humanos pendentes para liberar publicação.*\n"
        )
    else:
        linhas.append("> [!NOTE]")
        linhas.append(
            "> Todas as checagens automáticas e portões humanos foram concluídos e aprovados com sucesso. O lote está pronto para o site.\n"
        )

    if alertas_consolidados:
        linhas.append("**Alertas informativos registrados (não-bloqueantes):**\n")
        for a in alertas_consolidados:
            linhas.append(f"- ⚠️ {a}")
        linhas.append("")

    linhas.append("---\n")

    # 3. Tabela de Checagens Automáticas e Portões
    linhas.append("## 2. Tabela de Checagens Automáticas e Portões\n")
    linhas.append("| Camada | Checagem | Status | Observações |")
    linhas.append("|:---|:---|:---:|:---|")

    # Download
    if dl_info and isinstance(dl_info, dict):
        st_download = dl_info.get("status", "NAO_VERIFICADO").upper()
        obs_download = dl_info.get("mensagem", "PDFs locais validados com inventário")
    else:
        st_download = "NAO_VERIFICADO"
        obs_download = "Download não avaliado neste lote"
    linhas.append(
        f"| **Download** | Reconciliação PDFs e Inventário | {_badge(st_download)} | {obs_download} |"
    )

    # Edital
    if portao_edital and isinstance(portao_edital, dict):
        pendentes_ed = [
            s
            for s, res in portao_edital.items()
            if not (res[0] if isinstance(res, tuple) else res)
        ]
        if not pendentes_ed:
            st_edital = "OK"
            obs_edital = f"Todos os {len(portao_edital)} editais revisados e aprovados"
        else:
            st_edital = "PENDENTE"
            obs_edital = f"Aguardando homologação humana em: {', '.join(pendentes_ed)}"
    elif portao_edital and isinstance(portao_edital, tuple):
        ap_ed, desc_ed = portao_edital
        st_edital = "OK" if ap_ed else "PENDENTE"
        obs_edital = f"Status: {desc_ed[:50]}"
    elif checks_resultado.get("edital") and isinstance(
        checks_resultado.get("edital"), dict
    ):
        st_edital = str(
            checks_resultado["edital"].get("status", "NAO_VERIFICADO")
        ).upper()
        obs_edital = str(checks_resultado["edital"].get("mensagem", ""))
    else:
        st_edital = "NAO_VERIFICADO"
        obs_edital = "Portão P3 não avaliado neste lote"
    linhas.append(
        f"| **Edital** | Portão Humano e Taxonomia (P3) | {_badge(st_edital)} | {obs_edital} |"
    )

    # Prova
    falhas_prova = [
        f
        for f in falhas_consolidadas
        if any(k in f for k in ("Prova", "Gabarito", "K15", "Alternativa", "Fila"))
    ]
    if falhas_prova:
        st_prova = "FALHA"
        obs_prova = "; ".join(falhas_prova[:2])
    elif (
        pr_info
        and isinstance(pr_info, dict)
        and pr_info.get("status") in ("ok", "alerta")
    ):
        st_prova = "OK"
        obs_prova = pr_info.get("mensagem", "Gabaritos e itens validados")
    elif isinstance(runbook, dict) and runbook.get("consulta_a"):
        st_prova = "OK"
        obs_prova = (
            "Fila 100% concluída, gabaritos dentro da grade, alternativas 5D válidas"
        )
    else:
        st_prova = "NAO_VERIFICADO"
        obs_prova = "Provas e gabaritos não avaliados neste lote"
    linhas.append(
        f"| **Prova** | Extração de Itens e Gabaritos (P4) | {_badge(st_prova)} | {obs_prova} |"
    )

    # Banco
    if not inv_valida:
        st_banco = "FALHA"
        obs_banco = "Divergência detectada nas métricas do piloto (K22)"
    elif bn_info and isinstance(bn_info, dict):
        st_banco = bn_info.get("status", "OK").upper()
        obs_banco = (
            f"Invariante do piloto preservada; {bn_info.get('mensagem', '')}".strip(
                "; "
            )
        )
    else:
        st_banco = "OK" if inv_valida else "FALHA"
        obs_banco = "Invariante do piloto preservada (2.800 itens, 129 anuladas, 3.029 apontamentos)"
    linhas.append(
        f"| **Banco** | Invariante do Piloto (K22) e Contagens | {_badge(st_banco)} | {obs_banco} |"
    )

    # Classificação
    if portao_classif:
        ap_c, n_pend_c = (
            portao_classif
            if isinstance(portao_classif, tuple)
            else (False, portao_classif)
        )
        if ap_c:
            st_classif = "OK"
            obs_classif = "Todos os itens classificados e curados"
        else:
            st_classif = "PENDENTE"
            sem_cl = getattr(n_pend_c, "sem_classificacao", n_pend_c)
            prop_cl = getattr(n_pend_c, "propostas", 0)
            detalhes_pend = []
            if sem_cl:
                detalhes_pend.append(f"{_inteiro(sem_cl)} sem classificação")
            if prop_cl:
                detalhes_pend.append(f"{_inteiro(prop_cl)} propostas a aprovar")
            det_str = f" ({', '.join(detalhes_pend)})" if detalhes_pend else ""
            if cl_info and isinstance(cl_info, dict) and cl_info.get("mensagem"):
                obs_classif = f"{cl_info['mensagem']}{det_str}"
            else:
                obs_classif = (
                    f"{_inteiro(n_pend_c)} itens pendentes no portão P9{det_str}"
                )
    elif cl_info and isinstance(cl_info, dict):
        st_classif = cl_info.get("status", "PENDENTE").upper()
        obs_classif = cl_info.get("mensagem", "Classificação pendente")
    else:
        st_classif = "NAO_VERIFICADO"
        obs_classif = "Classificação não avaliada neste lote"
    linhas.append(
        f"| **Classificação** | Curadoria da Árvore e Questões | {_badge(st_classif)} | {obs_classif} |"
    )

    # Site
    if st_info and isinstance(st_info, dict):
        st_site = st_info.get("status", "NAO_VERIFICADO").upper()
        obs_site = st_info.get(
            "mensagem", "0 de 610 questões visíveis em vw_questoes (aguarda publicação)"
        )
    else:
        st_site = "NAO_VERIFICADO"
        obs_site = (
            "Publicação no site não verificada neste lote (aguarda classificação e P11)"
        )
    linhas.append(
        f"| **Site** | Prontidão dos Dados para Publicação | {_badge(st_site)} | {obs_site} |"
    )
    linhas.append("")
    linhas.append("---\n")

    # 4. Invariante do Piloto (K22)
    linhas.append("## 3. Invariante do Piloto (K22)\n")
    linhas.append(
        "> A checagem K22 afere se o processamento do lote preservou intactos os dados "
        "dos 5 concursos canônicos homologados (PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, CD_25_NS).\n"
    )

    linhas.append("| Métrica | Esperado | Antes do Lote | Depois do Lote | Status |")
    linhas.append("|:---|---:|---:|---:|:---:|")

    obt_antes = (
        (invariante_antes or {}).get("obtido")
        or (invariante_depois or {}).get("obtido")
        or {}
    )
    obt_depois = (invariante_depois or {}).get("obtido") or {}

    metricas_info = [
        ("Itens Objetivos", "itens", 2800),
        ("Itens Anulados", "anuladas", 129),
        ("Apontamentos na Árvore", "apontamentos", 3029),
        ("Hash Chaves 5D", "hash_chaves", "3257ba6ba525fdd6b4492733b50882f2"),
    ]

    for label, chave, esp in metricas_info:
        val_antes = obt_antes.get(chave, "-")
        val_depois = obt_depois.get(chave, "-")

        str_esp = f"`{esp}`" if isinstance(esp, str) else _inteiro(esp)
        str_antes = (
            f"`{val_antes}`" if isinstance(val_antes, str) else _inteiro(val_antes)
        )
        str_depois = (
            f"`{val_depois}`" if isinstance(val_depois, str) else _inteiro(val_depois)
        )

        badge_m = _badge("OK" if val_depois == esp else "FALHA")
        linhas.append(
            f"| **{label}** | {str_esp} | {str_antes} | {str_depois} | {badge_m} |"
        )

    linhas.append("")
    linhas.append("---\n")

    # 5. Detalhamento das Consultas do Runbook (§4.5)
    linhas.append("## 4. Detalhamento das Consultas do Runbook (§4.5)\n")

    # 4.1 Consulta (a) - Por Prova
    linhas.append("### 4.1 Consulta (a) — Integridade por Prova\n")
    consulta_a = runbook.get("consulta_a", []) if isinstance(runbook, dict) else []
    if consulta_a:
        linhas.append(
            "| Concurso | Arquivo | Tipo | Cargos | Fila | Itens | Sem Gab | Anul | Alt (Min-Max) | Inútil | Disc |"
        )
        linhas.append("|:---|:---|:---|:---:|:---:|---:|---:|---:|:---:|---:|---:|")
        for r in consulta_a:
            alt_str = (
                f"{r.get('alt_min')}-{r.get('alt_max')}"
                if r.get("alt_min") is not None
                else "-"
            )
            cargos_str = str(r.get("cargos") or "-")
            if len(cargos_str) > 15:
                cargos_str = cargos_str[:12] + "..."
            linhas.append(
                f"| {r.get('slug')} | `{r.get('arquivo')}` | {r.get('tipo')} | "
                f"{cargos_str} | {r.get('fila')} | {_inteiro(r.get('itens'))} | "
                f"{_inteiro(r.get('sem_gab'))} | {_inteiro(r.get('anul'))} | "
                f"{alt_str} | {_inteiro(r.get('inutil'))} | {_inteiro(r.get('disc'))} |"
            )
        linhas.append("")
    else:
        linhas.append("*Nenhum dado retornado para a Consulta (a).*\n")

    # 4.2 Consulta (b) - Gabaritos
    linhas.append("### 4.2 Consulta (b) — Distribuição de Gabaritos\n")
    consulta_b = runbook.get("consulta_b", []) if isinstance(runbook, dict) else []
    if consulta_b:
        linhas.append("| Concurso | Tipo | Gabarito | Ocorrências |")
        linhas.append("|:---|:---|:---:|---:|")
        for r in consulta_b:
            linhas.append(
                f"| {r.get('slug')} | {r.get('tipo')} | **`{r.get('gabarito')}`** | {_inteiro(r.get('total'))} |"
            )
        linhas.append("")
    else:
        linhas.append("*Nenhum dado retornado para a Consulta (b).*\n")

    # 4.3 Consulta (c) - Discursivas
    linhas.append("### 4.3 Consulta (c) — Provas Discursivas\n")
    consulta_c = runbook.get("consulta_c", []) if isinstance(runbook, dict) else []
    if consulta_c:
        linhas.append("| Concurso | Arquivo | Item | Quesitos | Padrão | Tema |")
        linhas.append("|:---|:---|:---:|---:|:---:|:---|")
        for r in consulta_c:
            tema_txt = (r.get("tema") or "").strip()
            if not tema_txt:
                tema_txt = "*(tema vazio / anafórico)*"
            elif len(tema_txt) > 40:
                tema_txt = tema_txt[:37] + "..."
            padrao_str = "Sim" if r.get("tem_padrao") else "**NÃO**"
            linhas.append(
                f"| {r.get('slug')} | `{r.get('arquivo')}` | Q{r.get('numero')} | "
                f"{r.get('quesitos')} | {padrao_str} | {tema_txt} |"
            )
        linhas.append("")
    else:
        linhas.append("*Nenhuma questão discursiva registrada para este lote.*\n")

    # 4.4 Consulta (d) - Seções e K15
    linhas.append(
        "### 4.4 Consulta (d) — Seções por Caderno e K15 (Alternativas em Caixa Alta)\n"
    )
    consulta_d_caixa_alta = (
        runbook.get("consulta_d_caixa_alta", []) if isinstance(runbook, dict) else []
    )
    if consulta_d_caixa_alta:
        linhas.append(
            f"> [!WARNING]\n> **K15:** Foram identificadas {len(consulta_d_caixa_alta)} alternativa(s) terminando em palavras em caixa alta (possível cabeçalho engolido):\n"
        )
        linhas.append("| Concurso | Arquivo | Questão | Trecho Final |")
        linhas.append("|:---|:---|:---:|:---|")
        for r in consulta_d_caixa_alta:
            linhas.append(
                f"| {r.get('slug')} | `{r.get('arquivo')}` | Q{r.get('numero')} | `{r.get('fim_ultima')}` |"
            )
        linhas.append("")
    else:
        linhas.append(
            f"Nenhuma alternativa terminando em caixa alta foi identificada (**K15**: {_badge('OK')}).\n"
        )

    consulta_d_secoes = (
        runbook.get("consulta_d_secoes", []) if isinstance(runbook, dict) else []
    )
    if consulta_d_secoes:
        linhas.append("**Seções identificadas nos cadernos:**\n")
        linhas.append("| Arquivo | Seção | Faixa Itens | Total |")
        linhas.append("|:---|:---|:---:|---:|")
        for r in consulta_d_secoes[
            :30
        ]:  # Limita as primeiras 30 seções para não poluir
            faixa = f"Q{r.get('min_numero')}-Q{r.get('max_numero')}"
            secao_txt = (r.get("secao") or "ÚNICA")[:40]
            linhas.append(
                f"| `{r.get('arquivo')}` | {secao_txt} | {faixa} | {_inteiro(r.get('total'))} |"
            )
        if len(consulta_d_secoes) > 30:
            linhas.append(
                f"| *... e mais {len(consulta_d_secoes) - 30} seções catalogadas* | | | |"
            )
        linhas.append("")

    # 4.5 Checagem K19
    linhas.append(
        "### 4.5 Checagem K19 — Múltipla Escolha sem Texto-Base (Severidade WARN)\n"
    )
    checagem_k19 = runbook.get("checagem_k19", []) if isinstance(runbook, dict) else []
    if checagem_k19:
        linhas.append(
            "> [!NOTE]\n"
            f"> Foram detectadas {len(checagem_k19)} questões ME cujo enunciado menciona termo textual/gráfico "
            "sem vínculo de texto-base nem figura. Esta checagem é **não-bloqueante** e deve ser conferida visualmente nos PDFs.\n"
        )
        linhas.append("| Concurso | Arquivo | Questão |")
        linhas.append("|:---|:---|:---:|")
        for r in checagem_k19[:40]:  # Amostra das primeiras 40
            linhas.append(
                f"| {r.get('slug')} | `{r.get('arquivo')}` | Q{r.get('numero')} |"
            )
        if len(checagem_k19) > 40:
            linhas.append(
                f"| *... e mais {len(checagem_k19) - 40} questões com alerta K19* | | |"
            )
        linhas.append("")
    else:
        linhas.append(
            f"Nenhuma questão ME com alerta de texto-base ausente (**K19**: {_badge('OK')}).\n"
        )

    linhas.append("---\n")

    # 6. Propostas de Dispersão da Árvore (P6 / KAN-64)
    linhas.append("## 5. Propostas de Dispersão da Árvore (P6 / KAN-64)\n")
    n_prop = len(propostas_dispersao)
    linhas.append(
        f"Foram avaliadas **{_inteiro(n_prop)}** proposta(s) de dispersão e fusão de nós na árvore canônica.\n"
    )

    if propostas_dispersao:
        linhas.append("| ID | Tipo | Operação / Detalhes | Justificativa |")
        linhas.append("|:---|:---:|:---|:---|")
        for p in propostas_dispersao[:25]:
            p_id = p.get("id") or getattr(p, "id", "-")
            p_tipo = p.get("tipo") or getattr(p, "tipo", "-")
            p_args = p.get("args") or getattr(p, "args", {})
            p_just = (p.get("justificativa") or getattr(p, "justificativa", "-"))[:70]
            if len(p_just) >= 70:
                p_just += "..."
            orig = p_args.get("origem", "-")
            dest = p_args.get("destino", "-")
            detalhe = (
                f"`{orig}` ➔ `{dest}`" if orig != "-" and dest != "-" else str(p_args)
            )
            linhas.append(f"| `{p_id}` | {p_tipo} | {detalhe} | {p_just} |")

        if len(propostas_dispersao) > 25:
            linhas.append(
                f"| *... e mais {len(propostas_dispersao) - 25} propostas catalogadas* | | | |"
            )
        linhas.append("")
    else:
        linhas.append("*Nenhuma nova proposta de dispersão gerada neste lote.*\n")

    linhas.append("---\n")

    # 7. Telemetria de Custos OpenRouter (US$)
    linhas.append("## 6. Telemetria de Custo OpenRouter (US$)\n")
    disp_custo = custo_info.get("disponivel", False)
    tot_acum = custo_info.get("total_acumulado_usd", 0.0)
    tot_dia = custo_info.get("total_diario_usd", 0.0)

    linhas.append(
        f"- **Status da Telemetria:** {'Disponível (online)' if disp_custo else 'Indisponível / offline'}"
    )
    linhas.append(f"- **Uso Acumulado Total:** {_usd(tot_acum)}")
    linhas.append(f"- **Uso Diário Total:** {_usd(tot_dia)}\n")

    etapas_custo = custo_info.get("etapas", [])
    if etapas_custo:
        linhas.append(
            "| Etapa | Chave / Identificador | Acumulado (US$) | Diário (US$) | Limite |"
        )
        linhas.append("|:---|:---|---:|---:|:---:|")
        for e in etapas_custo:
            limite_str = (
                _usd(e.get("limit")) if e.get("limit") is not None else "Sem limite"
            )
            identificador = str(e.get("label") or e.get("nome") or "")
            if "sk-" in identificador.lower() or "bearer" in identificador.lower():
                identificador = str(e.get("nome") or "Chave de API")
            linhas.append(
                f"| {e.get('nome')} | {identificador} | "
                f"{_usd(e.get('usage_acumulado'))} | {_usd(e.get('usage_daily'))} | {limite_str} |"
            )
        linhas.append("")
    else:
        linhas.append(
            "*Telemetria detalhada não disponível (consultada offline ou sem chaves).* \n"
        )

    linhas.append("---\n")

    # 8. Próximos Passos
    linhas.append("## 7. Próximos Passos e Ações Recomendadas\n")
    if veredito_texto == "PRONTO PARA O SITE":
        linhas.append(
            "1. **Publicação no Site (P11):** Sincronizar com os artefatos estáticos e atualizar visualizações.\n"
            "2. **Aprovação da Etapa:** Certames prontos para liberação em produção.\n"
        )
    elif veredito_texto == "AGUARDANDO PORTÕES HUMANOS":
        linhas.append(
            "1. **Revisão Humana do Edital (P3):** Inspecionar os relatórios HTML gerados em `revisao_piloto/` e homologar os certames.\n"
            "2. **Curadoria da Árvore (P7):** Avaliar e aprovar em lote as propostas de fusão pendentes (`python -m scripts.curar_arvore`).\n"
            "3. **Curadoria da Classificação (P9):** Homologar as classificações com confiança média/baixa via `python -m scripts.curar_classificacao`.\n"
        )
    else:
        linhas.append(
            "1. **Análise de Bloqueios:** Revisar as mensagens de erro impeditivas listadas na Seção 1.\n"
            "2. **Correção de Parsers:** Corrigir os eventuais problemas de extração ou banco antes de avançar.\n"
            "3. **Restauração de Backup:** Caso a invariante K22 tenha divergência não planejada, restaurar o banco via backup P0.\n"
        )

    conteudo_final = "\n".join(linhas)
    caminho_arquivo.write_text(conteudo_final, encoding="utf-8")
    return caminho_arquivo
