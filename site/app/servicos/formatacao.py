ROTULO_NIVEL = {
    "superior": "Superior",
    "medio": "Médio"
}

_MAPA_CONCURSOS = {
    "CD_25_NS": "CD 2025 — Nível Superior"
}

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
