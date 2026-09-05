"""Fixtures for tests that need a real database.

The whole package is skipped when `DATABASE_URL` points nowhere reachable, so
`pytest` still passes on a machine without Postgres.

Every test that writes cleans up after itself; these run against a developer
database with real data and must leave it exactly as they found it.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncGenerator

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from sarkariworld.db.session import async_session_factory, check_connection
from sarkariworld.main import create_app
from sarkariworld.models.enums import UserRole
from sarkariworld.models.user import User
from sarkariworld.services.tokens import mint_session_token

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
    """Provision a real API key on the admin, then remove it."""
    key = "sw_" + secrets.token_hex(16)
    hashed = bcrypt.hashpw(key.encode(), bcrypt.gensalt(rounds=12)).decode()

    async with async_session_factory() as session:
        user = await session.get(User, admin_user.id)
        assert user is not None
        user.api_key_prefix = key[:11]
        user.api_key_hash = hashed
        user.api_key_name = "pytest"
        user.api_key_revoked_at = None
        await session.commit()

    yield key

    async with async_session_factory() as session:
        user = await session.get(User, admin_user.id)
        assert user is not None
        user.api_key_prefix = None
        user.api_key_hash = None
        user.api_key_name = None
        user.api_key_revoked_at = None
        await session.commit()
