"""End-to-end tests against a real database.

Skipped automatically when no database is reachable. Writes clean up after
themselves so the developer database is left untouched.
"""

from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from src.config import settings
from src.db.session import async_session_factory
from src.models.article import Article
from src.models.enums import UserRole
from src.models.user import User
from src.utils.dates import now_ist

V1 = settings.api_v1_prefix
IST_SUFFIX = re.compile(r"\+05:30$")


class TestPublic:
    async def test_health_reports_database_up(self, api: AsyncClient) -> None:
        response = await api.get("/health/db")
        assert response.json() == {"database": "up", "detail": None}

    async def test_category_listing_paginates(self, api: AsyncClient) -> None:
        response = await api.get(f"{V1}/latest-job", params={"per_page": 2})

        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "latest-job"
        assert body["per_page"] == 2
        assert len(body["articles"]) <= 2
        assert body["total_pages"] >= 1
        if body["has_more"]:
            assert body["next_page"] == body["page"] + 1

    async def test_every_timestamp_is_ist(self, api: AsyncClient) -> None:
        """The contract is +05:30, never Z. Asserted on real rows.

        Categories are looked up rather than hard-coded — not every category
        has published articles in a given database.
        """
        categories = [c["slug"] for c in (await api.get(f"{V1}/category")).json()]
        stamps: list[str] = []
        for slug in categories:
            body = (await api.get(f"{V1}/{slug}", params={"per_page": 5})).json()
            stamps += [
                article[field]
                for article in body["articles"]
                for field in ("published_at", "created_at", "updated_at")
                if article[field] is not None
            ]
            if stamps:
                break

        assert stamps, "no published articles anywhere to check"
        for stamp in stamps:
            assert IST_SUFFIX.search(stamp), stamp
            assert not stamp.endswith("Z")

    async def test_listing_returns_only_its_category(self, api: AsyncClient) -> None:
        body = (await api.get(f"{V1}/tender", params={"per_page": 10})).json()
        assert {a["category"] for a in body["articles"]} <= {"tender"}

    async def test_unknown_category_is_404(self, api: AsyncClient) -> None:
        response = await api.get(f"{V1}/not-a-category")
        assert response.status_code == 404

    async def test_sitemap_lists_every_published_article(
        self, api: AsyncClient
    ) -> None:
        body = (await api.get(f"{V1}/sitemap")).json()

        assert body["total"] > 0
        assert body["truncated"] is False
        # The whole catalogue in one response is the point of the endpoint --
        # a client should never have to page it.
        assert len(body["articles"]) == body["total"]

    async def test_sitemap_carries_only_what_a_sitemap_needs(
        self, api: AsyncClient
    ) -> None:
        entry = (await api.get(f"{V1}/sitemap")).json()["articles"][0]

        assert set(entry) == {"slug", "category", "published_at", "updated_at"}
        assert "-" in entry["category"] or entry["category"].isalpha()
        assert "_" not in entry["category"]

    async def test_sitemap_agrees_with_the_category_listings(
        self, api: AsyncClient
    ) -> None:
        """The old sitemap paged every category; this must not lose anyone."""
        listed: set[str] = set()
        for slug in (await api.get(f"{V1}/category")).json():
            page = 1
            while True:
                body = (
                    await api.get(
                        f"{V1}/{slug['slug']}", params={"page": page, "per_page": 50}
                    )
                ).json()
                listed.update(a["slug"] for a in body["articles"])
                if not body["has_more"]:
                    break
                page += 1

        from_sitemap = {
            a["slug"] for a in (await api.get(f"{V1}/sitemap")).json()["articles"]
        }
        assert from_sitemap == listed

    async def test_search_finds_by_title(self, api: AsyncClient) -> None:
        response = await api.get(f"{V1}/search", params={"q": "recruitment"})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] > 0
        assert len(body["articles"]) == body["total"]

    async def test_search_tolerates_a_typo(self, api: AsyncClient) -> None:
        """The trigram leg of the hybrid query, exercised against real titles."""
        response = await api.get(f"{V1}/search", params={"q": "recruitmnt"})
        assert response.json()["total"] > 0

    async def test_search_ignores_single_character(self, api: AsyncClient) -> None:
        assert (await api.get(f"{V1}/search", params={"q": "a"})).json()["total"] == 0

    async def test_detail_hides_workflow_fields(self, api: AsyncClient) -> None:
        listing = (await api.get(f"{V1}/latest-job", params={"per_page": 1})).json()
        slug = listing["articles"][0]["slug"]

        body = (await api.get(f"{V1}/article/{slug}")).json()

        assert body["slug"] == slug
        assert "html_content" in body
        # Public callers must never see status or authorship.
        assert "article_status" not in body
        assert "author_id" not in body


class TestAdminReads:
    async def test_dashboard_counts(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        body = (await api.get(f"{V1}/admin/dashboard", headers=admin_headers)).json()
        assert body["total"] == (body["published"] + body["draft"] + body["archived"])

    async def test_meta_matches_enforced_limits(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        body = (await api.get(f"{V1}/admin/meta", headers=admin_headers)).json()
        assert len(body["categories"]) == 11
        assert body["article_statuses"] == ["draft", "published", "archived"]
        assert body["limits"]["search_keyword_max_items"] == 24

    async def test_category_filter_actually_filters(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """The source drops this filter silently; here it must apply."""
        response = await api.get(
            f"{V1}/admin/posts",
            headers=admin_headers,
            params={"category": "latest-job", "per_page": 10},
        )

        body = response.json()
        assert body["total"] > 0
        assert {item["category"] for item in body["items"]} == {"latest-job"}
        # The admin envelope deliberately omits these.
        assert "has_more" not in body
        assert "next_page" not in body

    async def test_user_listing_never_leaks_key_material(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        body = (
            await api.get(
                f"{V1}/admin/users", headers=admin_headers, params={"per_page": 5}
            )
        ).json()

        for user in body["items"]:
            for secret in (
                "api_key",
                "api_key_hash",
                "api_key_prefix",
                "session_invalidated_at",
            ):
                assert secret not in user, f"leaked {secret}"
            assert "has_api_key" in user

    async def test_bookmark_overview_rollup(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        body = (
            await api.get(f"{V1}/admin/bookmarks/overview", headers=admin_headers)
        ).json()
        assert set(body["totals"]) == {"bookmarks", "users", "articles"}
        assert body["window_days"] == 30

    async def test_web_urls_default_to_oldest_first(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        body = (
            await api.get(
                f"{V1}/admin/web-urls", headers=admin_headers, params={"per_page": 5}
            )
        ).json()
        stamps = [row["last_viewed_at"] for row in body["items"]]
        # Never-viewed rows surface first so nothing sits unseen.
        assert stamps == sorted(stamps, key=lambda s: (s is not None, s or ""))


class TestArticleLifecycle:
    SLUG = "pytest-lifecycle-article"

    @pytest.fixture(autouse=True)
    async def _cleanup(self, _database: None) -> AsyncGenerator[None]:
        yield
        async with async_session_factory() as session:
            result = await session.execute(
                select(Article).where(Article.slug == self.SLUG)
            )
            if (article := result.scalar_one_or_none()) is not None:
                await session.delete(article)
                await session.commit()

    async def test_create_normalises_and_sanitises(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        response = await api.post(
            f"{V1}/admin/posts",
            headers=admin_headers,
            json={
                "title": "Pytest Lifecycle",
                "slug": self.SLUG,
                "category": "result",
                "html_content": '<h1>T</h1><script>x()</script><p onclick="y()">b</p>',
                "search_keyword": ["SSC", "ssc", " CGL "],
                "links": [{"url": "javascript:alert(1)"}, {"url": "https://ok.com"}],
                "faq": [{"question": "  q   spaced ", "answer": "a"}],
            },
        )

        assert response.status_code == 201
        body = response.json()
        # New articles are drafts until explicitly published.
        assert body["article_status"] == "draft"
        assert body["html_content"] == "<h2>T</h2><p>b</p>"
        assert body["search_keyword"] == ["ssc", "cgl"]
        assert body["links"] == [{"cta": "View", "url": "https://ok.com"}]
        assert body["faq"] == [{"question": "q spaced", "answer": "a"}]

    async def test_publish_then_archive(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await api.post(
            f"{V1}/admin/posts",
            headers=admin_headers,
            json={"title": "P", "slug": self.SLUG, "category": "blog"},
        )

        published = await api.patch(
            f"{V1}/admin/posts/{self.SLUG}/status",
            headers=admin_headers,
            json={"status": "published"},
        )
        stamped_at = published.json()["published_at"]
        assert stamped_at is not None
        assert (await api.get(f"{V1}/article/{self.SLUG}")).status_code == 200

        archived = await api.patch(
            f"{V1}/admin/posts/{self.SLUG}/status",
            headers=admin_headers,
            json={"status": "archived"},
        )
        # Archiving must not re-stamp the original publication date.
        assert archived.json()["published_at"] == stamped_at
        assert (await api.get(f"{V1}/article/{self.SLUG}")).status_code == 404

    async def test_update_is_partial(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await api.post(
            f"{V1}/admin/posts",
            headers=admin_headers,
            json={
                "title": "Original",
                "slug": self.SLUG,
                "category": "blog",
                "description": "keep me",
                "search_keyword": ["alpha"],
            },
        )

        body = (
            await api.put(
                f"{V1}/admin/posts/{self.SLUG}",
                headers=admin_headers,
                json={"title": "Renamed"},
            )
        ).json()

        assert body["title"] == "Renamed"
        # Omitted fields must survive rather than being blanked.
        assert body["description"] == "keep me"
        assert body["search_keyword"] == ["alpha"]

    async def test_duplicate_slug_conflicts(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        payload = {"title": "A", "slug": self.SLUG, "category": "blog"}
        assert (
            await api.post(f"{V1}/admin/posts", headers=admin_headers, json=payload)
        ).status_code == 201

        response = await api.post(
            f"{V1}/admin/posts", headers=admin_headers, json=payload
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    async def test_validation_error_names_the_field(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        response = await api.post(
            f"{V1}/admin/posts",
            headers=admin_headers,
            json={
                "title": "x",
                "slug": self.SLUG,
                "faq": [{"question": "", "answer": "a"}],
            },
        )

        assert response.status_code == 422
        details = response.json()["error"]["details"]
        assert details[0]["path"] == "faq.0.question"


class TestPublishEndpoint:
    SLUG = "pytest-markdown-ingest"

    @pytest.fixture(autouse=True)
    async def _cleanup(self, _database: None) -> AsyncGenerator[None]:
        yield
        async with async_session_factory() as session:
            result = await session.execute(
                select(Article).where(Article.slug == self.SLUG)
            )
            if (article := result.scalar_one_or_none()) is not None:
                await session.delete(article)
                await session.commit()

    async def test_markdown_is_rendered_and_forced_to_draft(
        self, api: AsyncClient, api_key: str
    ) -> None:
        response = await api.post(
            f"{V1}/admin/publish/articles",
            headers={"X-API-Key": api_key},
            json={
                "title": "Ingest",
                "slug": self.SLUG,
                "category": "blog",
                "content": "# Heading\n\n<script>bad()</script>\n\n[l](https://a.com)",
            },
        )

        assert response.status_code == 201
        body = response.json()
        # Automated content is always reviewed before it can go public.
        assert body["article_status"] == "draft"
        assert "<h2>Heading</h2>" in body["html_content"]
        assert "script" not in body["html_content"].lower()
        assert 'rel="nofollow noopener noreferrer"' in body["html_content"]

    async def test_cannot_self_publish(self, api: AsyncClient, api_key: str) -> None:
        """`article_status` is not an accepted field, so a bot cannot go live."""
        response = await api.post(
            f"{V1}/admin/publish/articles",
            headers={"X-API-Key": api_key},
            json={
                "title": "x",
                "slug": self.SLUG,
                "article_status": "published",
            },
        )

        assert response.status_code == 422
        paths = {d["path"] for d in response.json()["error"]["details"]}
        assert "article_status" in paths


class TestRoleGuards:
    @pytest.fixture
    async def editor(self, _database: None) -> AsyncGenerator[User]:
        """Temporarily promote a plain user, then restore their role."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(User)
                .where(User.role == UserRole.USER)
                .order_by(User.id)
                .limit(1)
            )
            user = result.scalar_one_or_none()
            if user is None:
                pytest.skip("no plain user to promote")
            user_id = user.id
            user.role = UserRole.EDITOR
            await session.commit()
            await session.refresh(user)
            promoted = user

        yield promoted

        async with async_session_factory() as session:
            restored = await session.get(User, user_id)
            assert restored is not None
            restored.role = UserRole.USER
            await session.commit()

    def _headers(self, user: User, role: str) -> dict[str, str]:
        from src.services.tokens import mint_session_token

        return {
            "Authorization": f"Bearer {mint_session_token(user.id, user.email, role)}"
        }

    async def test_editor_may_read_and_write(
        self, api: AsyncClient, editor: User
    ) -> None:
        headers = self._headers(editor, "editor")
        assert (
            await api.get(f"{V1}/admin/posts", headers=headers, params={"per_page": 1})
        ).status_code == 200

    async def test_editor_may_not_delete(self, api: AsyncClient, editor: User) -> None:
        """DELETE is admin-only across the whole admin surface."""
        response = await api.delete(
            f"{V1}/admin/posts/anything", headers=self._headers(editor, "editor")
        )
        assert response.status_code == 403
        assert response.json()["error"]["message"] == "Only an admin may delete."

    async def test_editor_may_not_touch_users(
        self, api: AsyncClient, editor: User
    ) -> None:
        response = await api.get(
            f"{V1}/admin/users", headers=self._headers(editor, "editor")
        )
        assert response.status_code == 403

    async def test_role_comes_from_the_database_not_the_token(
        self, api: AsyncClient, admin_user: User
    ) -> None:
        """A token claiming admin gets no access if the row says otherwise."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(User)
                .where(User.role == UserRole.USER)
                .order_by(User.id)
                .limit(1)
            )
            plain = result.scalar_one_or_none()
            if plain is None:
                pytest.skip("no plain user available")

        response = await api.get(
            f"{V1}/admin/dashboard", headers=self._headers(plain, "admin")
        )
        assert response.status_code == 403

    async def test_self_role_change_is_refused(
        self, api: AsyncClient, admin_user: User, admin_headers: dict[str, str]
    ) -> None:
        """An admin demoting themselves could lock out the last administrator."""
        response = await api.patch(
            f"{V1}/admin/users/{admin_user.id}/role",
            headers=admin_headers,
            json={"role": "editor"},
        )
        assert response.status_code == 409


class TestGoogleSignInRoles:
    """Google is the only human sign-in, and it never grants privilege.

    New accounts always start at `user`; an existing account keeps whatever
    role an admin gave it. Signing in must never be a way to change your own
    role, so these two rules are asserted against the real database.
    """

    EMAIL = "pytest-signin@example.com"

    @pytest.fixture(autouse=True)
    async def _cleanup(self, _database: None) -> AsyncGenerator[None]:
        yield
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.email == self.EMAIL))
            if (user := result.scalar_one_or_none()) is not None:
                await session.delete(user)
                await session.commit()

    async def test_only_google_is_offered(self, api: AsyncClient) -> None:
        body = (await api.get(f"{V1}/auth/providers")).json()
        assert body["providers"] == ["google"]

    async def test_other_providers_are_refused(self, api: AsyncClient) -> None:
        for provider in ("facebook", "github", "password"):
            response = await api.post(f"{V1}/auth/{provider}", json={"credential": "x"})
            assert response.status_code == 404, provider

    async def test_first_sign_in_creates_a_plain_user(self) -> None:
        from src.services.users import upsert_oauth_user

        async with async_session_factory() as session:
            created = await upsert_oauth_user(
                session,
                email=self.EMAIL,
                name="Pytest Signin",
                google_id="pytest-google-id",
                picture_url=None,
            )
            assert created.role is UserRole.USER
            assert created.auth_provider == "google"

    async def test_signing_in_again_never_changes_role(self) -> None:
        """An admin who signs in stays admin; a user cannot self-promote."""
        from src.services.users import upsert_oauth_user

        async with async_session_factory() as session:
            user = await upsert_oauth_user(
                session,
                email=self.EMAIL,
                name="Pytest Signin",
                google_id="pytest-google-id",
                picture_url=None,
            )
            # An admin grants a role manually.
            user.role = UserRole.EDITOR
            await session.commit()

        async with async_session_factory() as session:
            again = await upsert_oauth_user(
                session,
                email=self.EMAIL,
                name="Renamed By Google",
                google_id="pytest-google-id",
                picture_url="https://example.com/p.png",
            )
            # Profile fields refresh; the granted role survives.
            assert again.role is UserRole.EDITOR
            assert again.name == "Renamed By Google"

    async def test_admin_can_change_a_role(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        from src.services.users import upsert_oauth_user

        async with async_session_factory() as session:
            user = await upsert_oauth_user(
                session,
                email=self.EMAIL,
                name="Pytest Signin",
                google_id="pytest-google-id",
                picture_url=None,
            )
            user_id = user.id

        promoted = await api.patch(
            f"{V1}/admin/users/{user_id}/role",
            headers=admin_headers,
            json={"role": "editor"},
        )
        assert promoted.status_code == 200
        assert promoted.json()["role"] == "editor"

        demoted = await api.patch(
            f"{V1}/admin/users/{user_id}/role",
            headers=admin_headers,
            json={"role": "user"},
        )
        assert demoted.json()["role"] == "user"

    async def test_a_plain_user_reaches_nothing_privileged(
        self, api: AsyncClient
    ) -> None:
        from src.services.tokens import mint_session_token
        from src.services.users import upsert_oauth_user

        async with async_session_factory() as session:
            user = await upsert_oauth_user(
                session,
                email=self.EMAIL,
                name="Pytest Signin",
                google_id="pytest-google-id",
                picture_url=None,
            )
            headers = {
                "Authorization": "Bearer "
                + mint_session_token(user.id, user.email, "user")
            }

        # Their own account works.
        assert (
            await api.get(f"{V1}/account/bookmarks", headers=headers)
        ).status_code == 200
        # Staff and admin surfaces do not.
        for path in ("/admin/dashboard", "/admin/posts", "/admin/users"):
            assert (await api.get(f"{V1}{path}", headers=headers)).status_code == 403, (
                path
            )


class TestApiKeys:
    """Keys are staff-only, expire after 30 days, and die on demotion."""

    EMAIL = "pytest-apikey@example.com"

    @pytest.fixture(autouse=True)
    async def _cleanup(self, _database: None) -> AsyncGenerator[None]:
        yield
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.email == self.EMAIL))
            if (user := result.scalar_one_or_none()) is not None:
                await session.delete(user)
                await session.commit()

    async def _make_user(self, role: UserRole) -> int:
        from src.services.users import upsert_oauth_user

        async with async_session_factory() as session:
            user = await upsert_oauth_user(
                session,
                email=self.EMAIL,
                name="Pytest Key Holder",
                google_id="pytest-apikey-id",
                picture_url=None,
            )
            user.role = role
            await session.commit()
            return user.id

    async def test_plain_users_are_refused_a_key(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id = await self._make_user(UserRole.USER)

        response = await api.post(
            f"{V1}/admin/users/{user_id}/api-key", headers=admin_headers, json={}
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"

    async def test_editor_gets_a_working_key_valid_30_days(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id = await self._make_user(UserRole.EDITOR)

        issued = await api.post(
            f"{V1}/admin/users/{user_id}/api-key",
            headers=admin_headers,
            json={"name": "content-agent"},
        )

        assert issued.status_code == 200
        body = issued.json()
        key = body["api_key"]
        assert key.startswith("sw_")
        assert body["prefix"] == key[:11]
        assert body["name"] == "content-agent"

        created = datetime.fromisoformat(body["created_at"])
        expires = datetime.fromisoformat(body["expires_at"])
        assert (expires - created).days == 30

        # The key actually authenticates.
        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": key})
        ).status_code == 200

    async def test_rotation_invalidates_the_previous_key(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id = await self._make_user(UserRole.ADMIN)
        url = f"{V1}/admin/users/{user_id}/api-key"

        first = (await api.post(url, headers=admin_headers, json={})).json()["api_key"]
        second = (await api.post(url, headers=admin_headers, json={})).json()["api_key"]

        assert first != second
        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": first})
        ).status_code == 401
        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": second})
        ).status_code == 200

    async def test_demotion_kills_the_key(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """A key must not outlive the privilege it was issued against."""
        user_id = await self._make_user(UserRole.EDITOR)
        key = (
            await api.post(
                f"{V1}/admin/users/{user_id}/api-key", headers=admin_headers, json={}
            )
        ).json()["api_key"]
        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": key})
        ).status_code == 200

        await api.patch(
            f"{V1}/admin/users/{user_id}/role",
            headers=admin_headers,
            json={"role": "user"},
        )

        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": key})
        ).status_code == 401

    async def test_expired_key_is_refused(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id = await self._make_user(UserRole.EDITOR)
        key = (
            await api.post(
                f"{V1}/admin/users/{user_id}/api-key", headers=admin_headers, json={}
            )
        ).json()["api_key"]

        # Backdate past the 30-day window.
        async with async_session_factory() as session:
            user = await session.get(User, user_id)
            assert user is not None
            user.api_key_created_at = now_ist() - timedelta(days=31)
            await session.commit()

        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": key})
        ).status_code == 401

    async def test_revoke_stops_the_key(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id = await self._make_user(UserRole.EDITOR)
        url = f"{V1}/admin/users/{user_id}/api-key"
        key = (await api.post(url, headers=admin_headers, json={})).json()["api_key"]

        assert (await api.delete(url, headers=admin_headers)).status_code == 204
        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": key})
        ).status_code == 401

    async def test_wrong_secret_with_valid_prefix_is_rejected(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id = await self._make_user(UserRole.EDITOR)
        key = (
            await api.post(
                f"{V1}/admin/users/{user_id}/api-key", headers=admin_headers, json={}
            )
        ).json()["api_key"]

        forged = key[:11] + "0" * 24
        assert (
            await api.get(f"{V1}/admin/posts", headers={"X-API-Key": forged})
        ).status_code == 401


class TestGoogleOnlyInvariant:
    """Every account is a Google account. Nothing should reintroduce another."""

    async def test_no_non_google_accounts_remain(self, _database: None) -> None:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User.auth_provider, func.count())
                .where(User.auth_provider != "google")
                .group_by(User.auth_provider)
            )
            assert result.all() == []

    async def test_meta_advertises_google_alone(
        self, api: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        body = (await api.get(f"{V1}/admin/meta", headers=admin_headers)).json()
        assert body["auth_providers"] == ["google"]
