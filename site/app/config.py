from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJETO_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5435
    postgres_db: str = "cebraspe"

    site_db_leitura_user: str = "site_leitura"
    site_db_leitura_password: str

    site_db_app_user: str = "site_app"
    site_db_app_password: str

    figuras_dir: Path = PROJETO_DIR / "data"

    # 5F.3: sessão em cookie assinado e Google OAuth (vazio = login desligado)
    session_secret: str
    session_https_only: bool = False
    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=str(PROJETO_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
