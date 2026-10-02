"""Cache em memória com validade curta para leituras que só mudam na carga do pipeline."""

import functools
import threading
import time

_trava = threading.Lock()
_registro: list = []


def cache_ttl(segundos: float = 300):
    """Memoriza o resultado (sem argumentos ou com argumentos hasheáveis) por `segundos`."""

    def decorador(funcao):
        guardado: dict = {}

        @functools.wraps(funcao)
        def interno(*args, **kwargs):
            chave = (args, tuple(sorted(kwargs.items())))
            agora = time.monotonic()
            with _trava:
                item = guardado.get(chave)
                if item and agora - item[0] < segundos:
                    return item[1]
            valor = funcao(*args, **kwargs)
            with _trava:
                guardado[chave] = (agora, valor)
            return valor

        interno.limpar = guardado.clear
        _registro.append(interno)
        return interno

    return decorador


def limpar_tudo() -> None:
    for f in _registro:
        f.limpar()
