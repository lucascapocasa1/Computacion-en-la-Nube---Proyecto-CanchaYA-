"""
core/config.py — Configuración global cargada desde .env
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str

    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    MP_ACCESS_TOKEN: str = "TEST-fake-token-for-local-dev"

    FRONTEND_URL: str = "http://localhost:5500"
    BACKEND_URL:  str = "http://localhost:8000"

    RESEND_API_KEY: str = ""
    FROM_EMAIL:     str = "noreply@example.com"

    ENV: str = "development"

    # JWT — cambiala por algo largo y aleatorio en producción
    SECRET_KEY: str = "dev-secret-key-change-in-production-please"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"


settings = Settings()
