"""Endpoints a signed-in user calls for themselves."""

from fastapi import APIRouter

from src.schemas.user import UserRead

router = APIRouter(tags=["users"])


@router.get("/me", summary="Current user")
async def read_current_user() -> UserRead:
    """The caller's own profile."""
    return UserRead(id=1, email="user@example.com", is_admin=False)
