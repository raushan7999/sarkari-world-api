"""User-facing endpoints."""

from fastapi import APIRouter

from src.routers.v1.users import profile

router = APIRouter(prefix="/users")
router.include_router(profile.router)

__all__ = ["router"]
