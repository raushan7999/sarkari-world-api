"""User queries and OAuth account linking."""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import UserRole
from src.models.user import User
from src.schemas.pagination import PageParams
from src.utils.dates import now_ist, utc_now


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email.strip().lower())
    )
    return result.scalar_one_or_none()


async def upsert_oauth_user(
    session: AsyncSession,
    *,
    email: str,
    name: str,
    google_id: str | None,
    picture_url: str | None,
) -> User:
    """Link an OAuth identity to a user, creating one on first sign-in.

    Accounts are matched by verified email. A new row always starts at the
    `user` role — staff are promoted deliberately, never by signing in.
    """
    normalized = email.strip().lower()
    user = await get_by_email(session, normalized)

    if user is None:
        user = User(
            email=normalized,
            name=name or normalized.split("@")[0],
            google_id=google_id,
            picture_url=picture_url,
            auth_provider="google",
            role=UserRole.USER,
        )
        session.add(user)
    else:
        # Refresh the profile, but never touch `role` here.
        if google_id:
            user.google_id = google_id
        if picture_url:
            user.picture_url = picture_url
        if name:
            user.name = name
        user.auth_provider = "google"

    user.last_login_at = now_ist()
    await session.commit()
    await session.refresh(user)
    return user


async def invalidate_sessions(session: AsyncSession, user: User) -> None:
    """Sign the user out everywhere by stamping the revocation column."""
    user.session_invalidated_at = utc_now()
    await session.commit()


async def touch_api_key_usage(session: AsyncSession, user: User) -> None:
    user.api_key_last_used_at = now_ist()
    await session.commit()


def build_user_list_query(
    query: str | None, role: UserRole | None
) -> Select[tuple[User]]:
    """Filtered user listing, newest first."""
    statement = select(User)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(User.name.ilike(pattern), User.email.ilike(pattern))
        )
    if role is not None:
        statement = statement.where(User.role == role)
    # Unique tiebreaker: `created_at` collides for users created in the same
    # transaction, and paged results must not repeat or drop rows.
    return statement.order_by(User.created_at.desc(), User.id.desc())


async def list_users(
    session: AsyncSession,
    *,
    query: str | None,
    role: UserRole | None,
    params: PageParams,
) -> tuple[list[User], int]:
    statement = build_user_list_query(query, role)

    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    result = await session.execute(
        statement.limit(params.per_page).offset(params.offset)
    )
    return list(result.scalars().all()), int(total or 0)
