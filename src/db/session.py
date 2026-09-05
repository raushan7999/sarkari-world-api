"""Database engine and session management.

The `AsyncEngine` owns the connection pool, so exactly one is created per
process. Creating it is cheap and lazy — no socket is opened until the first
query — so building it at import time is safe.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    # The Node service pins every pooled connection to IST. Timestamps in this
    # database are naive and IST-relative, so omitting this shifts every value
    # by 5h30m.
    connect_args={"server_settings": {"timezone": settings.db_timezone}},
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=settings.db_pool_recycle,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession]:
    """Yield a session backed by the pool, rolling back on error."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_connection() -> None:
    """Round-trip a trivial query. Raises if the database is unreachable."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def dispose_engine() -> None:
    """Close every pooled connection. Called on application shutdown."""
    await engine.dispose()
    logger.info("db_engine_disposed")
