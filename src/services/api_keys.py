"""API-key authentication for server-to-server callers.

Keys look like `sw_<token>`. Only a bcrypt hash is stored; the indexed 11-char
prefix (`sw_` + 8 characters) narrows the lookup to one row before the hash is
compared. Keys are issued out-of-band by the Node service's operator CLI, so
this side only ever verifies them.
"""

from __future__ import annotations

import re

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.auth import API_KEY_LOOKUP_PREFIX_LENGTH, API_KEY_PREFIX
from src.models.user import User

API_KEY_RE = re.compile(rf"^{API_KEY_PREFIX}[A-Za-z0-9_-]{{20,}}$")

# Compared against when no row matches, so a prefix miss costs the same as a
# wrong secret. Without this, response timing leaks which prefixes exist.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equalisation", bcrypt.gensalt(rounds=12))


def looks_like_api_key(candidate: str | None) -> bool:
    return bool(candidate and API_KEY_RE.match(candidate))


async def resolve_api_key(session: AsyncSession, candidate: str) -> User | None:
    """Return the owning user, or None if the key is unknown or revoked."""
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

    if not user or not user.api_key_hash or not matches:
        return None
    if user.api_key_revoked_at is not None:
        return None
    return user
