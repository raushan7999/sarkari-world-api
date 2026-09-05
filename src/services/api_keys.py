"""API keys for server-to-server callers.

Keys look like `sw_<token>`. Only a bcrypt hash is stored; the indexed 11-char
prefix (`sw_` + 8 characters) narrows the lookup to one row before the hash is
compared, so verification stays a single indexed read plus one bcrypt call.

Three rules govern validity, all checked on every request:

* the owner must still be staff — demoting someone kills their key immediately
* the key must not be revoked
* the key must be younger than `API_KEY_TTL_DAYS`; rotation is manual
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.auth import (
    API_KEY_ENTROPY_BYTES,
    API_KEY_LOOKUP_PREFIX_LENGTH,
    API_KEY_PREFIX,
    API_KEY_TTL_DAYS,
    STAFF_ROLES,
)
from src.exceptions import ForbiddenError
from src.models.user import User
from src.utils.dates import now_ist

API_KEY_RE = re.compile(rf"^{API_KEY_PREFIX}[A-Za-z0-9_-]{{20,}}$")

# Compared against when no row matches, so a prefix miss costs the same as a
# wrong secret. Without this, response timing leaks which prefixes exist.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalisation", bcrypt.gensalt(rounds=12))

TTL = timedelta(days=API_KEY_TTL_DAYS)


def looks_like_api_key(candidate: str | None) -> bool:
    return bool(candidate and API_KEY_RE.match(candidate))


def expires_at(user: User) -> object | None:
    """When the user's key stops working, or None if they hold none."""
    if user.api_key_created_at is None:
        return None
    return user.api_key_created_at + TTL


def is_expired(user: User) -> bool:
    if user.api_key_created_at is None:
        return True
    return now_ist() >= user.api_key_created_at + TTL


def is_active(user: User) -> bool:
    """A key is usable only while the owner is staff and it is fresh."""
    return (
        user.api_key_hash is not None
        and user.api_key_revoked_at is None
        and user.role.value in STAFF_ROLES
        and not is_expired(user)
    )


async def resolve_api_key(session: AsyncSession, candidate: str) -> User | None:
    """Return the owning user, or None if the key is unknown or unusable."""
    lookup_prefix = candidate[:API_KEY_LOOKUP_PREFIX_LENGTH]

    result = await session.execute(
        select(User).where(User.api_key_prefix == lookup_prefix)
    )
    user = result.scalar_one_or_none()

    # Always run bcrypt, even on a miss, to keep the timing flat.
    stored_hash = (
        user.api_key_hash.encode() if user and user.api_key_hash else _DUMMY_HASH
    )
    matches = bcrypt.checkpw(candidate.encode(), stored_hash)

    if not user or not matches:
        return None
    if not is_active(user):
        return None
    return user


async def issue(session: AsyncSession, user: User, name: str | None = None) -> str:
    """Mint a key for a staff user and return the secret — shown only once.

    Rotation is the same call: it overwrites the stored hash, so the previous
    key stops working immediately.
    """
    if user.role.value not in STAFF_ROLES:
        raise ForbiddenError("API keys are only issued to editors and admins.")

    secret = f"{API_KEY_PREFIX}{secrets.token_urlsafe(API_KEY_ENTROPY_BYTES)}"
    user.api_key_prefix = secret[:API_KEY_LOOKUP_PREFIX_LENGTH]
    user.api_key_hash = bcrypt.hashpw(
        secret.encode(), bcrypt.gensalt(rounds=12)
    ).decode()
    user.api_key_name = name
    user.api_key_created_at = now_ist()
    user.api_key_last_used_at = None
    user.api_key_revoked_at = None
    await session.commit()
    return secret


async def revoke(session: AsyncSession, user: User) -> None:
    """Stop a key working without clearing its metadata, so the audit trail stays."""
    user.api_key_revoked_at = now_ist()
    await session.commit()
