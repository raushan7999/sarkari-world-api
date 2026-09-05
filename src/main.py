"""Application factory. Run with `uvicorn src.main:app`."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import Settings, settings
from src.db.session import dispose_engine
from src.exceptions import register_exception_handlers
from src.middleware import setup_middleware
from src.routers import api_router, health_router
from src.utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Startup and shutdown. The pool is drained before the process exits."""
    logger.info(
        "application_started",
        version=settings.version,
        environment=settings.environment,
    )
    yield
    await dispose_engine()
    logger.info("application_stopped")


def create_app(config: Settings | None = None) -> FastAPI:
    """Build the application. A factory keeps tests free to build their own."""
    config = config or settings
    configure_logging(level=config.log_level, json_logs=config.log_json)

    app = FastAPI(
        title=config.project_name,
        version=config.version,
        description=config.description,
        debug=config.debug,
        lifespan=lifespan,
        docs_url="/docs" if config.enable_docs else None,
        # ReDoc is not mounted: it is a second rendering of the same document
        # that /docs already serves interactively.
        redoc_url=None,
        # Swagger UI fetches this; setting it to None disables /docs as well.
        openapi_url="/openapi.json" if config.enable_docs else None,
        servers=[{"url": config.base_url, "description": config.environment}],
    )

    setup_middleware(app, config)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=config.api_v1_prefix)

    return app


app = create_app()
