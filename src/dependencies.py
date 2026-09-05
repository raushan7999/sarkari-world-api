"""Shared FastAPI dependencies: database sessions and authentication.

Credential resolution never rejects. `current_user` returns `None` for an
anonymous or bad credential and the request continues; the guards below decide
whether that is acceptable. This mirrors the Node service, where `authenticate`
runs globally and authorization lives entirely in the route guards.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.auth import SESSION_COOKIE, STAFF_ROLES
from src.db.session import get_session
from src.exceptions import ForbiddenError, UnauthorizedError
from src.models.enums import UserRole
from src.models.user import User
from src.services import api_keys, tokens, users
from src.utils.logger import get_logger

logger = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization") or ""
    scheme, _, value = header.partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


async def current_user(request: Request, session: SessionDep) -> User | None:
    """Resolve the caller from an API key, a session JWT, or nothing.

    Priority: API key, then JWT (header or cookie). Never raises — a bad
    credential resolves to anonymous, and the guards produce the 401/403.
    The role is re-read from the database on every request, so a promotion or
    demotion takes effect immediately.
    """
    bearer = _bearer_token(request)

    # 1. API key — `X-API-Key: sw_...` or `Authorization: Bearer sw_...`
    candidate = request.headers.get("x-api-key") or bearer
    if api_keys.looks_like_api_key(candidate):
        assert candidate is not None
        user = await api_keys.resolve_api_key(session, candidate)
        if user is not None:
            request.state.auth_via = "api_key"
            return user
        logger.warning("auth_failed", reason="api_key")
        return None

    # 2. Session JWT — Authorization header, else the httpOnly cookie.
    token = bearer or request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    claims = tokens.verify_session_token(token)
    if claims is None:
        logger.warning("auth_failed", reason="session_token")
        return None

    try:
        user_id = int(claims.sub)
    except ValueError:
        return None

    user = await users.get_by_id(session, user_id)
    if user is None:
        return None
    if tokens.is_revoked(claims, user.session_invalidated_at):
        logger.warning("auth_failed", reason="session_revoked")
        return None

    request.state.auth_via = "cookie" if not bearer else "bearer"
    return user


CurrentUser = Annotated[User | None, Depends(current_user)]


async def require_auth(user: CurrentUser) -> User:
    """401 unless the caller is signed in."""
    if user is None:
        raise UnauthorizedError("Login required.")
    return user


AuthedUser = Annotated[User, Depends(require_auth)]


def require_role(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """403 unless the caller holds one of `roles`."""

    async def guard(user: AuthedUser) -> User:
        if user.role not in roles:
            logger.warning("role_denied", required=[r.value for r in roles])
            raise ForbiddenError("Insufficient permissions.")
        return user

    return guard


async def require_manage(request: Request, user: AuthedUser) -> User:
    """Staff-only guard for the whole admin surface.

    Editors may read and write, but deletion is reserved for admins — the same
    rule the Node service applies across `/v1/admin`.
    """
    if user.role.value not in STAFF_ROLES:
        logger.warning("role_denied", required=list(STAFF_ROLES))
        raise ForbiddenError("Insufficient permissions.")
    if request.method == "DELETE" and user.role is not UserRole.ADMIN:
        logger.warning("role_denied", required=["admin"], reason="delete")
        raise ForbiddenError("Only an admin may delete.")
    return user


ManageUser = Annotated[User, Depends(require_manage)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
