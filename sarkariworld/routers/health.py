"""Liveness and dependency health checks."""

from fastapi import APIRouter

from sarkariworld.config import settings
from sarkariworld.db.session import check_connection
from sarkariworld.schemas.health import DatabaseHealthResponse, HealthResponse
from sarkariworld.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def health() -> HealthResponse:
    """Report that the service is up. Used by uptime and container probes."""
    return HealthResponse(version=settings.version, environment=settings.environment)


@router.get("/health/db", summary="Database readiness check")
async def health_db() -> DatabaseHealthResponse:
    """Round-trip a query through the connection pool."""
    try:
        await check_connection()
    except Exception as exc:
        logger.warning("db_health_check_failed", error=str(exc))
        return DatabaseHealthResponse(database="down", detail=str(exc))
    return DatabaseHealthResponse(database="up")
