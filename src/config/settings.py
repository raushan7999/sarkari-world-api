import secrets
from functools import lru_cache

from pydantic import Field, model_validator
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
    # Advertised in the OpenAPI document as the server URL, so an imported
    # Postman/client collection points at the right host instead of guessing.
    base_url: str = "http://127.0.0.1:8000"
    # Interactive docs. /openapi.json is what Swagger UI fetches, so disabling
    # it disables /docs too. Turn the whole lot off in production if the API
    # surface should not be publicly browsable.
    enable_docs: bool = True
    enable_redoc: bool = True

    # CORS — comma-separated in the environment, e.g. "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=list)

    # Auth
    # HS256 signing key for session JWTs. Must be >=32 chars in production.
    session_secret: str = ""
    cookie_domain: str | None = None
    behind_tls_proxy: bool = False
    google_oauth_client_id: str | None = None
    # Optional Google Workspace domain restriction.
    google_oauth_hd: str | None = None

    # CORS — public routes and the authenticated/admin surface use different
    # allow-lists; the admin surface accepts the union.
    admin_cors_origins: list[str] = Field(default_factory=list)

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
    db_timezone: str = "Asia/Kolkata"

    @model_validator(mode="after")
    def _check_session_secret(self) -> Settings:
        """Fail closed in production; mint an ephemeral key for local dev.

        A short or missing signing key would let anyone forge a session, so
        production refuses to boot rather than start insecure.
        """
        if self.environment == "production":
            if len(self.session_secret) < 32:
                raise ValueError(
                    "SESSION_SECRET must be at least 32 characters in production"
                )
        elif not self.session_secret:
            # Ephemeral: restarting invalidates every dev session, which is fine.
            object.__setattr__(self, "session_secret", secrets.token_urlsafe(48))
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor, so settings are parsed once per process."""
    return Settings()


settings = get_settings()
