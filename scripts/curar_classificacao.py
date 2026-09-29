"""CLI de curadoria e deliberação humana da classificação de questões (Etapa 5D, ADR-030).

Permite a intervenção pontual e em lote do dono do projeto na base canônica
`canonico/classificacao_questoes.json`. O banco PostgreSQL é derivado e recarregável.

Invariante soberana: Toda alteração de status ('aprovado'/'rejeitado') ou novo mapeamento
humano é executado exclusivamente mediante comando explícito do usuário.

Uso:
    python -m scripts.curar_classificacao --mapear 'CHAVE:NO1[,NO2]'
    python -m scripts.curar_classificacao --aprovar 'CHAVE:NO'
    python -m scripts.curar_classificacao --rejeitar 'CHAVE:NO'
    python -m scripts.curar_classificacao --aprovar-lote [--confianca alta|media|baixa] [--caderno CODIGO]
    python -m scripts.curar_classificacao --pendentes
    python -m scripts.curar_classificacao --html
    python -m scripts.curar_classificacao --aplicar-banco
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gerar_relatorio_classificacao import (
    REVISAO_DIR_PADRAO,
    gerar_relatorio_classificacao,
)
from src import arvore as arv_mod
from src import classificacao as classif_mod
from src import stats_writer


def _dividir_chave_valor(
    arg: str, formato: str = "CHAVE:VALOR"
) -> tuple[str, str]:
    """Divide pelo último ':' separando a chave natural dos nós."""
    chave, sep, valor = arg.rpartition(":")
    if not sep or not chave.strip() or not valor.strip():
        raise classif_mod.ClassificacaoInvalida(
            f"Formato esperado: {formato} (recebido {arg!r})"
        )
    return chave.strip(), valor.strip()


def listar_pendentes(
    cq: classif_mod.ClassificacaoQuestoes, arv: arv_mod.ArvoreMestre
) -> None:
    """Imprime no terminal o resumo detalhado de itens aguardando decisão humana."""
    total = len(cq.registros)
    sem_no_itens = [r for r in cq.registros.values() if r.sem_no]

    baixa_itens = []
    totais_status = {"proposto": 0, "aprovado": 0, "rejeitado": 0}
    totais_conf = {"alta": 0, "media": 0, "baixa": 0}

    for r in cq.registros.values():
        for ap in r.apontamentos:
            totais_status[ap.status] = totais_status.get(ap.status, 0) + 1
            totais_conf[ap.confianca] = totais_conf.get(ap.confianca, 0) + 1
            if ap.confianca == "baixa" and ap.status == "proposto":
                baixa_itens.append((r.chave, ap))

    print("=" * 80)
    print("PAINEL DE PENDÊNCIAS — CLASSIFICAÇÃO DE QUESTÕES (Etapa 5D)")
    print("=" * 80)
    print(f"Total de questões: {total}")
    print(
        f"Status: {totais_status['proposto']} propostos | "
        f"{totais_status['aprovado']} aprovados | {totais_status['rejeitado']} rejeitados"
    )
    print(
        f"Confiança: {totais_conf['alta']} alta | "
        f"{totais_conf['media']} média | {totais_conf['baixa']} baixa | "
        f"{len(sem_no_itens)} sem nó"
    )
    print("-" * 80)

    if sem_no_itens:
        print(f"\n🚨 ITENS SEM NÓ NA ÁRVORE ({len(sem_no_itens)}):")
        for r in sem_no_itens:
            print(f"  • Chave: {r.chave}")
            print(f"    Comando sugerido: python -m scripts.curar_classificacao --mapear '{r.chave}:NO_ID'")
    else:
        print("\n✅ Nenhum item pendente marcado como 'sem_no'.")

    if baixa_itens:
        print(f"\n⚠️  PROPOSTAS COM CONFIANÇA BAIXA ({len(baixa_itens)}):")
        for chave, ap in baixa_itens:
            no_obj = arv.nos.get(arv_mod.resolver_no(arv, ap.no_id))
            nome_no = no_obj.nome if no_obj else ap.no_id
            print(f"  • Chave: {chave}")
            print(f"    Nó proposto: {nome_no} ({ap.no_id}) [{ap.papel}]")
            print(
                f"    Comandos: python -m scripts.curar_classificacao --aprovar '{chave}:{ap.no_id}'\n"
                f"              python -m scripts.curar_classificacao --rejeitar '{chave}:{ap.no_id}'"
            )
    else:
        print("\n✅ Nenhuma proposta pendente com confiança baixa.")

    print("\n" + "=" * 80)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CLI de curadoria humana da classificação de questões na árvore mestre."
    )
    parser.add_argument(
        "--classificacao",
        type=Path,
        default=classif_mod.CLASSIFICACAO_PADRAO,
        help="Caminho para canonico/classificacao_questoes.json",
    )
    parser.add_argument(
        "--arvore",
        type=Path,
        default=arv_mod.ARVORE_PADRAO,
        help="Caminho para canonico/arvore.json",
    )
    parser.add_argument(
        "--revisao-dir",
        type=Path,
        default=REVISAO_DIR_PADRAO,
        help="Diretório de revisão piloto para relatórios",
    )

    # Operações
    parser.add_argument(
        "--mapear",
        action="append",
        default=[],
        metavar="CHAVE:NO1[,NO2]",
        help="Mapeia manualmente uma questão a 1 ou 2 nós (sai aprovado)",
    )
    parser.add_argument(
        "--aprovar",
        action="append",
        default=[],
        metavar="CHAVE:NO",
        help="Aprova uma proposta específica de classificação",
    )
    parser.add_argument(
        "--rejeitar",
        action="append",
        default=[],
        metavar="CHAVE:NO",
        help="Rejeita uma proposta específica de classificação",
    )
    parser.add_argument(
        "--aprovar-lote",
        action="store_true",
        help="Aprova em lote propostas com a confiança indicada",
    )
    parser.add_argument(
        "--confianca",
        choices=["alta", "media", "baixa"],
        default="alta",
        help="Nível de confiança para aprovação em lote (padrão: alta)",
    )
    parser.add_argument(
        "--caderno",
        type=str,
        default=None,
        help="Restringe a aprovação em lote a um caderno específico",
    )
    parser.add_argument(
        "--pendentes",
        action="store_true",
        help="Lista no terminal o resumo de itens aguardando decisão humana",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Regenera o relatório visual classificacao.html",
    )
    parser.add_argument(
        "--aplicar-banco",
        action="store_true",
        help="Aplica as classificações do arquivo canônico no PostgreSQL",
    )

    args = parser.parse_args(argv)

    cq = classif_mod.carregar(args.classificacao)
    arv = arv_mod.carregar(args.arvore)

    houve_alteracao = False
    mensagens: list[str] = []

    try:
        # 1. Mapeamento manual
        for item in args.mapear:
            chave, nos_str = _dividir_chave_valor(item, "CHAVE:NO1[,NO2]")
            nos_ids = [n.strip() for n in nos_str.split(",") if n.strip()]
            if not nos_ids:
                raise classif_mod.ClassificacaoInvalida(
                    f"Nenhum nó informado em {item!r}"
                )

            # Buscar hash existente ou calcular
            reg_existente = cq.registros.get(chave)
            hash_enun = reg_existente.hash_enunciado if reg_existente else ""

            classif_mod.mapear_questao(
                cq,
                arv,
                chave=chave,
                hash_enunciado=hash_enun,
                nos=nos_ids,
                confianca="alta",
                fora_do_edital=False,
                origem="humano",
                status="aprovado",
            )
            mensagens.append(
                f"[MAPEAR] {chave} mapeada para {nos_ids} (origem: humano, status: aprovado)"
            )
            houve_alteracao = True

        # 2. Aprovação pontual
        for item in args.aprovar:
            chave, no_id = _dividir_chave_valor(item, "CHAVE:NO")
            classif_mod.aprovar_apontamento(cq, chave, no_id)
            mensagens.append(f"[APROVAR] {chave} -> nó {no_id} aprovado")
            houve_alteracao = True

        # 3. Rejeição pontual
        for item in args.rejeitar:
            chave, no_id = _dividir_chave_valor(item, "CHAVE:NO")
            classif_mod.rejeitar_apontamento(cq, chave, no_id)
            mensagens.append(f"[REJEITAR] {chave} -> nó {no_id} rejeitado")
            houve_alteracao = True

        # 4. Aprovação em lote
        if args.aprovar_lote:
            total_aprov = classif_mod.aprovar_lote(
                cq, confianca=args.confianca, caderno=args.caderno
            )
            alvo = f"caderno {args.caderno}" if args.caderno else "todos os cadernos"
            mensagens.append(
                f"[APROVAR-LOTE] {total_aprov} apontamento(s) com confiança '{args.confianca}' "
                f"aprovados em {alvo}."
            )
            houve_alteracao = True

    except (classif_mod.ClassificacaoInvalida, arv_mod.ArvoreInvalida) as e:
        print(f"Erro de integridade/curadoria: {e}", file=sys.stderr)
        return 1

    # Salvar alterações canônicas
    if houve_alteracao:
        classif_mod.salvar(cq, args.classificacao)
        for msg in mensagens:
            print(msg)
        # Manter o relatório HTML sempre sincronizado
        gerar_relatorio_classificacao(
            revisao_dir=args.revisao_dir,
            classificacao_path=args.classificacao,
            arvore_path=args.arvore,
        )

    # Listar pendências
    if args.pendentes:
        listar_pendentes(cq, arv)

    # Regenerar HTML explícito
    if args.html and not houve_alteracao:
        gerar_relatorio_classificacao(
            revisao_dir=args.revisao_dir,
            classificacao_path=args.classificacao,
            arvore_path=args.arvore,
        )
        print("[HTML] Relatório classificacao.html atualizado.")

    # Carga no PostgreSQL
    if args.aplicar_banco:
        try:
            conn = stats_writer.conectar()
            totais = stats_writer.aplicar_classificacao(conn, args.classificacao)
            conn.close()
            print(
                f"[BANCO] Classificação sincronizada no PostgreSQL: "
                f"{totais['questao_no']} apontamentos em questao_no, "
                f"{totais['discursiva_no']} em discursiva_no."
            )
        except Exception as e:  # noqa: BLE001
            print(f"Aviso ao sincronizar no PostgreSQL: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
