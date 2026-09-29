import pytest
from fastapi.testclient import TestClient

from tests.test_stats_writer import _postgres_disponivel

# Credenciais das roles vêm do .env (app.config); nada de senha no teste.
pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(), reason="scraper-cebraspe-db indisponível"
)


@pytest.fixture
def cliente():
    from app.main import app

    with TestClient(app) as c:
        yield c
