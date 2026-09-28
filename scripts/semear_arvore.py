import logging
from pathlib import Path

from src.arvore import ARVORE_PADRAO, ArvoreMestre, criar_no, mapear, salvar
from src.canonico import SINONIMOS_PADRAO, carregar, indice_aprovado

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def _chave_natural(chave_tupla) -> str:
    if isinstance(chave_tupla, str):
        return chave_tupla
    return "|".join(chave_tupla)

def semear(sinonimos_path: Path = SINONIMOS_PADRAO, arvore_path: Path = ARVORE_PADRAO) -> None:
    estado_sin = carregar(sinonimos_path)
    indice = indice_aprovado(estado_sin)
    
    arvore = ArvoreMestre()
    
    # Criar os nós:
    for nivel in ["materia", "assunto", "subassunto"]:
        for gid, info in indice.grupos.get(nivel, {}).items():
            criar_no(
                arvore=arvore,
                nivel=nivel,
                nome=info["nome"],
                pai=info["pai"],
                origem="semente",
                status="ativo",
                id_override=gid
            )
            
    # Criar mapeamentos
    for chave, gid in indice.materia.items():
        mapear(arvore, _chave_natural(chave), [gid], origem="semente", status="aprovado")
        
    for chave, gid in indice.assunto.items():
        mapear(arvore, _chave_natural(chave), [gid], origem="semente", status="aprovado")
        
    for chave, gid in indice.subassunto.items():
        mapear(arvore, _chave_natural(chave), [gid], origem="semente", status="aprovado")
        
    salvar(arvore, arvore_path)
    logger.info("Semeada arvore.json com sucesso.")

if __name__ == "__main__":
    semear()
