"""OAuth credential verification.

Only Google is wired up today. `verify_credential` returns a provider-neutral
profile so adding a provider means adding one function, not touching routers.
"""

from __future__ import annotations

from dataclasses import dataclass

import anyio.to_thread
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from src.config import settings
from src.exceptions import AppError, UnauthorizedError
from src.utils.logger import get_logger

logger = get_logger(__name__)

GOOGLE = "google"


@dataclass(frozen=True)
class OAuthProfile:
    email: str
    name: str
    subject: str
    picture: str | None


class ProviderNotConfiguredError(AppError):
    status_code = 503
    code = "provider_not_configured"
    message = "Sign-in provider is not configured."


class UnknownProviderError(AppError):
    status_code = 404
    code = "unknown_provider"
    message = "Unknown sign-in provider."


def configured_providers() -> list[str]:
    """Providers with credentials present, so the client can render buttons."""
    return [GOOGLE] if settings.google_oauth_client_id else []


def _verify_google_credential_sync(credential: str) -> OAuthProfile:
    """Verify a Google ID token and return the verified profile.

    google-auth ships only a synchronous transport, so this is called from a
    worker thread rather than directly on the event loop.
    """
    if not settings.google_oauth_client_id:
        raise ProviderNotConfiguredError

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_oauth_client_id,
        )
    except (ValueError, GoogleAuthError) as exc:
        logger.warning("auth_failed", reason="google_token", error=str(exc))
        raise UnauthorizedError("Invalid Google credential.") from exc

    if not claims.get("email_verified"):
        raise UnauthorizedError("Google account email is not verified.")

    # Optional Workspace domain restriction.
    if settings.google_oauth_hd and claims.get("hd") != settings.google_oauth_hd:
        raise UnauthorizedError("Account is outside the allowed domain.")

    return OAuthProfile(
        email=str(claims["email"]).strip().lower(),
        name=str(claims.get("name") or ""),
        subject=str(claims["sub"]),
        picture=claims.get("picture"),
    )


async def verify_credential(provider: str, credential: str) -> OAuthProfile:
    """Verify a provider credential without blocking the event loop."""
    if provider != GOOGLE:
        raise UnknownProviderError
    return await anyio.to_thread.run_sync(_verify_google_credential_sync, credential)
