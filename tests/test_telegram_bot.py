import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.telegram_bot import chamar_openrouter, is_allowed, load_project_context


def test_chamar_openrouter_sucesso():
    fake_response_data = {
        "choices": [
            {"message": {"content": "Resposta do modelo"}}
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: fake_response_data

    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_resp)), \
         patch("src.telegram_bot._registrar_langfuse") as mock_langfuse:
        messages = [{"role": "user", "content": "Olá"}]
        resposta = asyncio.run(
            chamar_openrouter(
                messages=messages,
                api_key="sk-or-test-key",
                base_url="https://openrouter.ai/api/v1",
                model="z-ai/glm-5.3-flash",
                user_id=123,
            )
        )

        assert resposta == "Resposta do modelo"
        mock_langfuse.assert_called_once()
        assert mock_langfuse.call_args[1]["sucesso"] is True
        assert mock_langfuse.call_args[1]["user_id"] == 123


def test_chamar_openrouter_sem_chave():
    with pytest.raises(ValueError, match="Chave da API do OpenRouter não configurada"):
        asyncio.run(
            chamar_openrouter(
                messages=[{"role": "user", "content": "Teste"}],
                api_key="",
            )
        )


def test_is_allowed():
    from unittest.mock import MagicMock
    update = MagicMock()
    update.effective_user.id = 1871867397

    with patch("src.telegram_bot.ALLOWED_USER_ID", 1871867397):
        assert is_allowed(update) is True

    with patch("src.telegram_bot.ALLOWED_USER_ID", 999999999):
        assert is_allowed(update) is False

    with patch("src.telegram_bot.ALLOWED_USER_ID", None):
        assert is_allowed(update) is True


def test_load_project_context():
    contexto = load_project_context()
    assert isinstance(contexto, str)
    assert len(contexto) > 0
    assert "spider.py" in contexto
    assert "downloader.py" in contexto
    assert "edital_parser.py" in contexto
    assert "taxonomia_extractor.py" in contexto
    assert "OpenRouter" in contexto
    assert "Langfuse" in contexto
