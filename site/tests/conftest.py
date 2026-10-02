import base64
import json
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from tests.test_stats_writer import _postgres_disponivel

# Credenciais das roles vêm do .env (app.config); nada de senha no teste.
pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)


def _com_csrf(c: TestClient) -> TestClient:
    # O token nasce na sessão ao renderizar qualquer página (hx-headers do body).
    html = c.get("/sobre").text
    c.headers["X-CSRFToken"] = re.search(r'"X-CSRFToken": "([^"]+)"', html).group(1)
    return c


@pytest.fixture
def cliente():
    from app.main import app

    with TestClient(app) as c:
        yield _com_csrf(c)


def _cookie_sessao(dados: dict) -> str:
    # Mesmo formato do SessionMiddleware do Starlette (JSON base64 assinado).
    from app.config import settings

    corpo = base64.b64encode(json.dumps(dados).encode())
    return TimestampSigner(settings.session_secret).sign(corpo).decode()


@pytest.fixture
def cliente_logado():
    """Cliente com sessão de um usuário de teste, apagado no fim (cascata)."""
    from app.main import app
    from app.servicos import contas_servico

    token = "token-csrf-teste"
    # Dentro do `with`: os pools do banco nascem no lifespan.
    with TestClient(app) as c:
        usuario = contas_servico.entrar_com_google(
            f"teste-{uuid.uuid4()}", "teste@example.com", "Usuário Teste"
        )
        c.cookies.set(
            "sessao",
            _cookie_sessao(
                {"usuario_id": usuario.id, "usuario_nome": usuario.nome, "csrf": token}
            ),
        )
        c.headers["X-CSRFToken"] = token
        yield c, usuario.id
        contas_servico.apagar_conta(usuario.id)
