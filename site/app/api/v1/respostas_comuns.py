"""Respostas de erro compartilhadas pelas rotas da API (5F.6).

Todo erro da API sai no formato padrão do FastAPI (`{"detail": "..."}`), aqui
descrito pelo modelo `Erro` para aparecer no Swagger.
"""

from pydantic import BaseModel, Field


class Erro(BaseModel):
    """Corpo de erro padrão da API."""

    detail: str = Field(
        description="Mensagem do erro, em português.",
        examples=["Login necessário"],
    )


def _resposta(descricao: str) -> dict:
    return {"model": Erro, "description": descricao}


R401 = {401: _resposta("Login necessário (cookie `sessao` ausente ou sem usuário).")}
R403 = {
    403: _resposta(
        "Token CSRF inválido: envie o header `X-CSRFToken` com o token da sessão."
    )
}


def r404(descricao: str = "Recurso não encontrado.") -> dict:
    return {404: _resposta(descricao)}


def r409(descricao: str) -> dict:
    return {409: _resposta(descricao)}
