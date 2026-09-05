"""Every protected route must reject anonymous callers before touching the DB.

These run without a database: the guards raise during dependency resolution,
so no query is ever issued.
"""

import pytest
from httpx import AsyncClient

from sarkariworld.config import settings

V1 = settings.api_v1_prefix

PROTECTED = [
    ("get", f"{V1}/account/bookmarks"),
    ("post", f"{V1}/account/bookmarks/toggle"),
    ("get", f"{V1}/admin/dashboard"),
    ("get", f"{V1}/admin/meta"),
    ("get", f"{V1}/admin/posts"),
    ("post", f"{V1}/admin/posts"),
    ("get", f"{V1}/admin/posts/recent"),
    ("get", f"{V1}/admin/posts/some-slug"),
    ("put", f"{V1}/admin/posts/some-slug"),
    ("delete", f"{V1}/admin/posts/some-slug"),
    ("patch", f"{V1}/admin/posts/some-slug/status"),
    ("post", f"{V1}/admin/publish/articles"),
    ("get", f"{V1}/admin/users"),
    ("get", f"{V1}/admin/users/1"),
    ("patch", f"{V1}/admin/users/1/role"),
    ("get", f"{V1}/admin/web-urls"),
    ("post", f"{V1}/admin/web-urls"),
    ("post", f"{V1}/admin/web-urls/mark-all-viewed"),
    ("post", f"{V1}/admin/web-urls/1/view"),
    ("delete", f"{V1}/admin/web-urls/1"),
    ("get", f"{V1}/admin/bookmarks"),
    ("get", f"{V1}/admin/bookmarks/overview"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
async def test_requires_authentication(
    client: AsyncClient, method: str, path: str
) -> None:
    response = await getattr(client, method)(path)

    assert response.status_code == 401, f"{method.upper()} {path} was not gated"
    assert response.json()["error"]["code"] == "unauthorized"


async def test_category_list_is_public(client: AsyncClient) -> None:
    response = await client.get(f"{V1}/category")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 11
    assert body[0] == {"slug": "latest-job", "name": "Latest Job"}


async def test_unknown_category_is_404(client: AsyncClient) -> None:
    response = await client.get(f"{V1}/not-a-real-category")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_search_requires_a_query(client: AsyncClient) -> None:
    response = await client.get(f"{V1}/search")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_openapi_documents_every_route(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert f"{V1}/admin/publish/articles" in paths
    assert f"{V1}/article/{{slug}}" in paths
