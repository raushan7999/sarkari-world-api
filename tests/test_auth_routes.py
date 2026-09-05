"""Auth route tests.

These exercise the guards and credential resolution. No database is touched:
an anonymous request short-circuits before any query, and the session factory
is lazy.
"""

from httpx import AsyncClient

from src.config import settings

V1 = settings.api_v1_prefix


async def test_providers_lists_only_configured(client: AsyncClient) -> None:
    response = await client.get(f"{V1}/auth/providers")

    assert response.status_code == 200
    # No GOOGLE_OAUTH_CLIENT_ID in the test environment.
    assert response.json() == {"providers": []}


async def test_me_is_null_when_anonymous(client: AsyncClient) -> None:
    response = await client.get(f"{V1}/auth/me")

    assert response.status_code == 200
    assert response.json() is None


async def test_logout_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(f"{V1}/auth/logout")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_unknown_provider_is_404(client: AsyncClient) -> None:
    response = await client.post(
        f"{V1}/auth/facebook", json={"credential": "irrelevant"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_provider"


async def test_sign_in_rejects_unknown_body_fields(client: AsyncClient) -> None:
    """Bodies are extra="forbid" — the anti mass-assignment guard."""
    response = await client.post(
        f"{V1}/auth/google", json={"credential": "x", "role": "admin"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_garbage_session_cookie_is_anonymous_not_500(
    client: AsyncClient,
) -> None:
    """A bad credential must resolve to anonymous, never raise."""
    client.cookies.set("sw_session", "totally.invalid.token")
    response = await client.get(f"{V1}/auth/me")

    assert response.status_code == 200
    assert response.json() is None
