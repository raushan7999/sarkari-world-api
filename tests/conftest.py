from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import create_app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """An HTTP client wired straight to the ASGI app — no network, no server."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
