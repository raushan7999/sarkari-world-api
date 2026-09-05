"""Application factory. Run with `uvicorn sarkariworld.main:app`."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sarkariworld.config import Settings, settings
from sarkariworld.db.session import dispose_engine
from sarkariworld.exceptions import register_exception_handlers
from sarkariworld.middleware import setup_middleware
from sarkariworld.routers import api_router, health_router
from sarkariworld.utils.logger import configure_logging, get_logger

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
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    setup_middleware(app, config)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=config.api_v1_prefix)

    return app


app = create_app()
