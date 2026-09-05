"""Fixtures for tests that need a real database.

The whole package is skipped when `DATABASE_URL` points nowhere reachable, so
`pytest` still passes on a machine without Postgres.

Every test that writes cleans up after itself; these run against a developer
database with real data and must leave it exactly as they found it.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.db.session import async_session_factory, check_connection
from src.main import create_app
from src.models.enums import UserRole
from src.models.user import User
from src.services import api_keys
from src.services.tokens import mint_session_token

# Cached so the reachability probe runs once per session even though the
# fixture is function-scoped (pytest-asyncio ties fixture scope to loop scope).
_DB_STATUS: str | None = None


@pytest.fixture
async def _database() -> None:
    global _DB_STATUS
    if _DB_STATUS is None:
        try:
            await check_connection()
            _DB_STATUS = "up"
        except Exception as exc:
            _DB_STATUS = f"no database available: {exc}"
    if _DB_STATUS != "up":
        pytest.skip(_DB_STATUS)


@pytest.fixture
async def api(_database: None) -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def admin_user(_database: None) -> User:
    """An existing admin. These tests read real data rather than seeding it."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.ADMIN).order_by(User.id).limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            pytest.skip("no admin user in the database")
        return user


@pytest.fixture
def admin_headers(admin_user: User) -> dict[str, str]:
    token = mint_session_token(admin_user.id, admin_user.email, "admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def api_key(admin_user: User) -> AsyncGenerator[str]:
    """Issue a real key through the service, then clear it.

    Goes through `api_keys.issue` rather than writing columns by hand so the
    fixture exercises the same path the endpoint uses — including the issue
    timestamp the 30-day expiry is derived from.
    """
    async with async_session_factory() as session:
        user = await session.get(User, admin_user.id)
        assert user is not None
        key = await api_keys.issue(session, user, name="pytest")

    yield key

    async with async_session_factory() as session:
        user = await session.get(User, admin_user.id)
        assert user is not None
        user.api_key_prefix = None
        user.api_key_hash = None
        user.api_key_name = None
        user.api_key_created_at = None
        user.api_key_last_used_at = None
        user.api_key_revoked_at = None
        await session.commit()
