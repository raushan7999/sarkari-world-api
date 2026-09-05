"""Admin-side user management."""

from fastapi import APIRouter

from src.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["admin:users"])


@router.get("", summary="List all users")
async def list_users() -> list[UserRead]:
    """Every user in the system. Admin only."""
    return []
