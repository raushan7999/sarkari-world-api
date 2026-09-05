"""Shared FastAPI dependencies: database sessions and authentication.

Credential resolution never rejects. `current_user` returns `None` for an
anonymous or bad credential and the request continues; the guards below decide
whether that is acceptable. This mirrors the Node service, where `authenticate`
runs globally and authorization lives entirely in the route guards.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from sarkariworld.constants.auth import SESSION_COOKIE, STAFF_ROLES
from sarkariworld.db.session import get_session
from sarkariworld.exceptions import ForbiddenError, UnauthorizedError
from sarkariworld.models.enums import UserRole
from sarkariworld.models.user import User
from sarkariworld.services import api_keys, tokens, users
from sarkariworld.utils.logger import get_logger

logger = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Declared as Security schemes so they appear in the OpenAPI document and
# Swagger UI renders an Authorize button. `auto_error=False` keeps credential
# resolution non-raising — the guards below decide what a missing or bad
# credential means for a given route.
bearer_scheme = HTTPBearer(
    scheme_name="Session JWT",
    description="A session JWT, or an `sw_` API key.",
    auto_error=False,
)
api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    scheme_name="API key",
    description="Server-to-server key issued by the operator CLI.",
    auto_error=False,
)

BearerDep = Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)]
ApiKeyDep = Annotated[str | None, Security(api_key_scheme)]


async def current_user(
    request: Request,
    session: SessionDep,
    credentials: BearerDep = None,
    header_key: ApiKeyDep = None,
) -> User | None:
    """Resolve the caller from an API key, a session JWT, or nothing.

    Priority: API key, then JWT (header or cookie). Never raises — a bad
    credential resolves to anonymous, and the guards produce the 401/403.
    The role is re-read from the database on every request, so a promotion or
    demotion takes effect immediately.
    """
    bearer = credentials.credentials.strip() if credentials else None

    # 1. API key — `X-API-Key: sw_...` or `Authorization: Bearer sw_...`
    candidate = header_key or bearer
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
