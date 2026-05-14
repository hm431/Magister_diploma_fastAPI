"""
core/config.py — настройки приложения через pydantic-settings.
"""
from __future__ import annotations

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

## TODO добавить корректные данные в env
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # --- API ---
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- База данных ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://vodokanal:vodokanal@localhost:5432/vodokanal_db"
    )
    DB_ECHO: bool = False           # True только локально для отладки SQL

    # --- JWT ---
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7


settings = Settings()