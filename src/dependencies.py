"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import get_session
from src.exceptions import UnauthorizedError

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_admin(x_admin_token: Annotated[str | None, Header()] = None) -> None:
    """Guard for admin routes.

    Placeholder: swap the token check for real authentication (JWT, session
    lookup, whatever you land on) without touching any router.
    """
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise UnauthorizedError("Admin credentials required")
