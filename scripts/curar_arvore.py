#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import json

PROJETO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJETO_DIR))

try:
    from src import arvore
except ImportError:
    arvore = None

from scripts.gerar_relatorio_arvore import gerar_relatorio_arvore

def parse_item(item_str):
    parts = item_str.split("|")
    return parts[0] if len(parts) == 1 else tuple(parts)

def main():
    parser = argparse.ArgumentParser(description="CLI de curadoria da árvore mestre")
    parser.add_argument("--mapear", help="Mapeia um item de edital para um ou mais nós: ITEM:NO1,NO2 (ex: 'Matéria|Assunto:A-123,A-456')")
    parser.add_argument("--desmapear", help="Remove o mapeamento de um item: ITEM")
    parser.add_argument("--fundir", help="Funde dois nós: ORIGEM:DESTINO")
    parser.add_argument("--mover", help="Move um nó para outro pai: NO:PAI")
    parser.add_argument("--criar", help="Cria um novo nó: NIVEL:PAI=Nome (use PAI nulo ou vazio para matéria, ex: materia:=Nova Matéria)")
    parser.add_argument("--renomear", help="Renomeia um nó: NO=Nome")
    parser.add_argument("--aprovar", help="Aprova o mapeamento de um item ou um nó proposto", action="store_true")
    parser.add_argument("--rejeitar", help="Rejeita o mapeamento de um item ou um nó proposto", action="store_true")
    parser.add_argument("--html", help="Gera o relatório arvore.html", action="store_true")

    args = parser.parse_args()

    # Operações de curadoria
    if any([args.mapear, args.desmapear, args.fundir, args.mover, args.criar, args.renomear, args.aprovar, args.rejeitar]):
        if arvore is None:
            print("Erro: src.arvore não encontrado. Certifique-se de que o outro agente já criou o arquivo.", file=sys.stderr)
            sys.exit(1)

        arv = arvore.carregar()

        if args.mapear:
            item_str, nos_str = args.mapear.split(":", 1)
            item = parse_item(item_str)
            nos = nos_str.split(",")
            arvore.mapear(arv, item, nos)
            # aprova automaticamente o mapeamento manual
            if item in arv.get("mapeamentos", {}):
                for m in arv["mapeamentos"][item]:
                    if [n["id"] for n in m.get("nos", [])] == nos or m.get("no") in nos or m.get("nos") == nos:
                        m["status"] = "aprovado"

        if args.desmapear:
            item = parse_item(args.desmapear)
            arvore.desmapear(arv, item)

        if args.fundir:
            origem, destino = args.fundir.split(":")
            arvore.fundir_nos(arv, origem, destino)

        if args.mover:
            no, pai = args.mover.split(":")
            if pai.lower() in ("null", "none", ""):
                pai = None
            arvore.mover_no(arv, no, pai)

        if args.criar:
            nivel_pai, nome = args.criar.split("=", 1)
            nivel, pai = nivel_pai.split(":", 1)
            if pai.lower() in ("null", "none", ""):
                pai = None
            arvore.criar_no(arv, nivel, pai, nome)

        if args.renomear:
            no, nome = args.renomear.split("=", 1)
            arvore.renomear_no(arv, no, nome)
            
        arvore.salvar(arv)
        print("Árvore salva com sucesso.")

    if args.html:
        gerar_relatorio_arvore()
        print("Relatório arvore.html gerado.")

if __name__ == "__main__":
    main()
