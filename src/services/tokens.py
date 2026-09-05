"""Session JWTs.

HS256 tokens carrying `{sub, email, iat, exp}`. Revocation reuses the existing
`User.session_invalidated_at` column: a token whose `iat` is at or before that
timestamp is rejected, which signs the user out of every device at once.

These are NOT interchangeable with the Node service's hand-rolled HMAC tokens —
that was a deliberate choice, and it means existing sessions do not carry over.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import jwt

from src.config import settings
from src.constants.auth import (
    STAFF_ROLES,
    STAFF_SESSION_TTL_SECONDS,
    USER_SESSION_TTL_SECONDS,
)

ALGORITHM = "HS256"


@dataclass(frozen=True)
class SessionClaims:
    sub: str
    email: str
    issued_at: datetime


def ttl_for_role(role: str) -> int:
    """Staff sessions are shorter-lived than reader sessions."""
    return (
        STAFF_SESSION_TTL_SECONDS if role in STAFF_ROLES else USER_SESSION_TTL_SECONDS
    )


def mint_session_token(user_id: int | str, email: str, role: str) -> str:
    """Issue a session JWT. Email is lower-cased, matching the source service."""
    now = datetime.now(UTC)
    issued_at = int(now.timestamp())
    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "iat": issued_at,
        "exp": issued_at + ttl_for_role(role),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)


def verify_session_token(token: str) -> SessionClaims | None:
    """Validate a session JWT. Returns None on any failure — never raises."""
    if not token or len(token) > 4096:
        return None
    try:
        payload = jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None

    subject = payload.get("sub")
    issued_at = payload.get("iat")
    if not subject or not isinstance(issued_at, int):
        return None

    return SessionClaims(
        sub=str(subject),
        email=str(payload.get("email") or ""),
        issued_at=datetime.fromtimestamp(issued_at, UTC),
    )


def is_revoked(claims: SessionClaims, invalidated_at: datetime | None) -> bool:
    """True if the token predates the user's last global sign-out."""
    if invalidated_at is None:
        return False
    reference = (
        invalidated_at
        if invalidated_at.tzinfo is not None
        else invalidated_at.replace(tzinfo=UTC)
    )
    return claims.issued_at <= reference
