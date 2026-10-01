"""Sessão, CSRF e Google OAuth (5F.3).

A sessão é um cookie assinado (SessionMiddleware): guarda só o id do usuário,
o nome para o cabeçalho e o token CSRF. Todo POST/DELETE confere o token,
vindo do header `X-CSRFToken` (HTMX e API) ou do campo `csrf_token` (form).
"""

import secrets

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request

from app.config import settings

oauth = OAuth()
if settings.google_client_id:
    oauth.register(
        "google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def login_habilitado() -> bool:
    return bool(settings.google_client_id)


def token_csrf(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


async def verificar_csrf(request: Request) -> None:
    esperado = request.session.get("csrf")
    enviado = request.headers.get("X-CSRFToken")
    if not enviado and request.headers.get("content-type", "").startswith(
        ("application/x-www-form-urlencoded", "multipart/form-data")
    ):
        enviado = (await request.form()).get("csrf_token")
    if not esperado or not enviado or not secrets.compare_digest(esperado, enviado):
        raise HTTPException(status_code=403, detail="Token CSRF inválido")


def usuario_id_atual(request: Request) -> int | None:
    return request.session.get("usuario_id")


def exigir_usuario_id(request: Request) -> int:
    usuario_id = usuario_id_atual(request)
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Login necessário")
    return usuario_id


def iniciar_sessao(request: Request, usuario_id: int, nome: str) -> None:
    # Sessão nova no login (evita fixação): descarta o token CSRF anônimo.
    request.session.clear()
    request.session["usuario_id"] = usuario_id
    request.session["usuario_nome"] = nome
    token_csrf(request)


def destino_seguro(destino: str | None) -> str:
    """Só caminho local (`/...`, nunca `//host`), contra open redirect."""
    if destino and destino.startswith("/") and not destino.startswith(("//", "/\\")):
        return destino
    return "/"
