from httpx import AsyncClient

from sarkariworld.config import settings
from sarkariworld.constants import REQUEST_ID_HEADER


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
    }


async def test_health_echoes_request_id(client: AsyncClient) -> None:
    response = await client.get("/health", headers={REQUEST_ID_HEADER: "abc123"})

    assert response.headers[REQUEST_ID_HEADER] == "abc123"


async def test_unknown_route_uses_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
