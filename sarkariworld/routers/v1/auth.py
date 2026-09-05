"""Sign-in, sign-out and identity.

There is no registration or password login — an account is created implicitly
on first verified OAuth sign-in, always at the `user` role. Staff are promoted
deliberately via the admin API.
"""

from fastapi import APIRouter, Response, status

from sarkariworld.config import settings
from sarkariworld.constants.auth import SESSION_COOKIE
from sarkariworld.dependencies import AuthedUser, CurrentUser, SessionDep
from sarkariworld.models.user import User
from sarkariworld.schemas.auth import (
    AuthPrincipal,
    OAuthSignInRequest,
    ProvidersResponse,
    SignInResponse,
)
from sarkariworld.schemas.common import PUBLIC_RESPONSES
from sarkariworld.services import oauth, tokens, users
from sarkariworld.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"], responses=PUBLIC_RESPONSES)


def _principal(user: User, via: str) -> AuthPrincipal:
    return AuthPrincipal(
        id=str(user.id),
        email=user.email,
        name=user.name,
        picture=user.picture_url,
        role=user.role,
        via=via,
    )


def _set_session_cookie(response: Response, token: str, role: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=tokens.ttl_for_role(role),
        httponly=True,
        samesite="lax",
        secure=settings.behind_tls_proxy,
        path="/",
        domain=settings.cookie_domain,
    )


@router.get("/providers", summary="Configured sign-in providers")
async def list_providers() -> ProvidersResponse:
    """Providers that have credentials configured, for rendering sign-in buttons."""
    return ProvidersResponse(providers=oauth.configured_providers())


@router.get("/me", summary="Current user")
async def read_me(user: CurrentUser) -> AuthPrincipal | None:
    """The signed-in caller, or null when anonymous. Never 401s."""
    if user is None:
        return None
    return _principal(user, "session")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Sign out")
async def logout(user: AuthedUser, session: SessionDep, response: Response) -> None:
    """Sign out of every device by stamping the revocation column."""
    await users.invalidate_sessions(session, user)
    response.delete_cookie(SESSION_COOKIE, path="/", domain=settings.cookie_domain)
    logger.info("user_logout", user_id=user.id)


@router.post("/{provider}", summary="Sign in with an OAuth provider")
async def sign_in(
    provider: str,
    payload: OAuthSignInRequest,
    session: SessionDep,
    response: Response,
) -> SignInResponse:
    """Verify an OAuth credential, link or create the account, and issue a session.

    404 for an unknown provider, 503 if the provider has no credentials
    configured, 401 if the credential does not verify.
    """
    profile = await oauth.verify_credential(provider, payload.credential)

    user = await users.upsert_oauth_user(
        session,
        email=profile.email,
        name=profile.name,
        google_id=profile.subject,
        picture_url=profile.picture,
    )

    token = tokens.mint_session_token(user.id, user.email, user.role.value)
    _set_session_cookie(response, token, user.role.value)
    logger.info("user_login", user_id=user.id, provider=provider)

    return SignInResponse(token=token, user=_principal(user, provider))
