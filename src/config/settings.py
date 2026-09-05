from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    project_name: str = "Sarkari World API"
    version: str = "0.1.0"
    description: str = "API for Sarkari World."
    environment: str = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # CORS — comma-separated in the environment, e.g. "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=list)

    # Auth — placeholder guard for admin routes; replace with real auth
    admin_token: str | None = None

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # PostgreSQL — postgresql+asyncpg://user:password@host:port/dbname
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/sarkari_world"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_recycle: int = 1800
    db_pool_timeout: int = 30
    db_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    """Cached accessor, so settings are parsed once per process."""
    return Settings()


settings = get_settings()
