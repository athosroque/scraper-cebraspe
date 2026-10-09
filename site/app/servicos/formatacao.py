import hashlib

ROTULO_NIVEL = {"superior": "Superior", "medio": "Médio"}

ROTULO_TIPO_CONHECIMENTO = {"basico": "Básico", "especifico": "Específico"}

ROTULO_TIPO_QUESTAO = {
    "certo_errado": "Certo/Errado",
    "multipla_escolha": "Múltipla Escolha",
}

LETRAS_CERTO_ERRADO = ("C", "E")
LETRAS_MULTIPLA_ESCOLHA = ("A", "B", "C", "D", "E")

_MAPA_CONCURSOS = {"CD_25_NS": "CD 2025 — Nível Superior"}


def letras_validas(tipo: str, alternativas=None) -> tuple[str, ...]:
    """Respostas aceitas pela questão. `C` e `E` só têm sentido junto com o tipo
    (no ME são alternativas), então a letra é sempre conferida contra ele (ADR-038).
    No ME valem as letras das alternativas extraídas; lista vazia aceita A–E."""
    if tipo != "multipla_escolha":
        return LETRAS_CERTO_ERRADO
    letras = tuple(
        a["letra"] if isinstance(a, dict) else a.letra for a in alternativas or ()
    )
    return letras or LETRAS_MULTIPLA_ESCOLHA


def rotulo_concurso(slug: str) -> str:
    if not slug:
        return ""
    if slug in _MAPA_CONCURSOS:
        return _MAPA_CONCURSOS[slug]
    partes = slug.split("_")
    if len(partes) >= 2 and partes[1].isdigit():
        orgao = partes[0]
        ano = f"20{partes[1]}" if len(partes[1]) == 2 else partes[1]
        return f"{orgao} {ano}"
    return slug


def rotulo_nivel(valor: str) -> str:
    return ROTULO_NIVEL.get(valor, str(valor).capitalize())


def rotulo_tipo_conhecimento(valor: str) -> str:
    return ROTULO_TIPO_CONHECIMENTO.get(valor, str(valor).capitalize())


def rotulo_tipo_questao(valor: str) -> str:
    return ROTULO_TIPO_QUESTAO.get(valor, str(valor).replace("_", " ").capitalize())


def rotulo_materia(nome: str, nome_de_cargo: bool = False) -> str:
    """Matéria que é o nome de um cargo vira "Conhecimentos específicos — <cargo>"."""
    return f"Conhecimentos específicos — {nome}" if nome_de_cargo else nome


def hash_chave(chave: str) -> str:
    """SHA-1 (hex) da chave estável `concurso|caderno|numero`."""
    return hashlib.sha1(chave.encode()).hexdigest()


def codigo_curto(chave: str) -> str:
    """ID curto estável da questão (`Q` + 8 hex maiúsculos do SHA-1 da chave)."""
    return "Q" + hash_chave(chave)[:8].upper()
