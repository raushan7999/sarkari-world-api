"""User and role administration.

Admin-only: the guard is declared on the router, so editors get 403 on this
whole subtree even though they pass the surrounding `require_manage`.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.dependencies import AuthedUser, SessionDep, require_role
from src.exceptions import ConflictError, NotFoundError
from src.models.enums import UserRole
from src.schemas.pagination import AdminPage, admin_page_params
from src.schemas.user import AdminUser, UserRoleUpdate
from src.services import users
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["admin:users"],
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)


@router.get("", summary="List users")
async def list_users(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    role: Annotated[UserRole | None, Query()] = None,
    page: Annotated[int | None, Query(ge=1)] = None,
    per_page: Annotated[int | None, Query(ge=1)] = None,
) -> AdminPage[AdminUser]:
    """Users, newest first, optionally filtered by name/email or role."""
    params = admin_page_params(page, per_page)
    rows, total = await users.list_users(session, query=q, role=role, params=params)
    return AdminPage[AdminUser].build(
        [AdminUser.model_validate(row) for row in rows], total, params
    )


@router.get("/{user_id}", summary="Get a user")
async def get_user(user_id: int, session: SessionDep) -> AdminUser:
    user = await users.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError(f"User not found: {user_id}")
    return AdminUser.model_validate(user)


@router.patch("/{user_id}/role", summary="Change a user's role")
async def update_role(
    user_id: int,
    payload: UserRoleUpdate,
    session: SessionDep,
    actor: AuthedUser,
) -> AdminUser:
    """Promote or demote a user.

    Changing your own role is refused: an admin who demotes themselves could
    lock the last administrator out of the console.
    """
    if actor.id == user_id:
        raise ConflictError("You cannot change your own role.")

    user = await users.get_by_id(session, user_id)
    if user is None:
        raise NotFoundError(f"User not found: {user_id}")

    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    logger.info("admin_user_role_change", user_id=user_id, role=payload.role.value)
    return AdminUser.model_validate(user)
