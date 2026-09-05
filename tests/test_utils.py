"""Unit tests for the pure helpers. No database required."""

from datetime import UTC, datetime, timedelta

import pytest

from src.schemas.pagination import admin_page_params, public_page_params
from src.services.tokens import (
    is_revoked,
    mint_session_token,
    verify_session_token,
)
from src.utils.article_payload import (
    normalise_article_links,
    normalise_faq_list,
    normalise_search_keyword,
)
from src.utils.dates import to_ist_iso
from src.utils.html import render_markdown, sanitize_article_html
from src.utils.slugs import (
    category_enum_to_slug,
    category_slug_to_enum,
    slugify,
)
from src.utils.urls import parse_http_url, valid_http_url


class TestDates:
    def test_emits_ist_offset_never_z(self) -> None:
        rendered = to_ist_iso(datetime(2024, 5, 1, 10, 30, 15, 123456))
        assert rendered == "2024-05-01T10:30:15.123+05:30"
        assert not rendered.endswith("Z")

    def test_none_passes_through(self) -> None:
        assert to_ist_iso(None) is None


class TestSlugs:
    def test_round_trips_hyphen_and_underscore(self) -> None:
        category = category_slug_to_enum("latest-job")
        assert category is not None
        assert category.value == "latest_job"
        assert category_enum_to_slug(category) == "latest-job"

    def test_unknown_slug_is_none(self) -> None:
        assert category_slug_to_enum("not-a-category") is None

    def test_slugify_strips_diacritics_and_punctuation(self) -> None:
        assert slugify("  UPSC Résultat 2024!! ") == "upsc-resultat-2024"


class TestPagination:
    def test_public_defaults_and_clamps(self) -> None:
        assert public_page_params(None, None).per_page == 15
        assert public_page_params(None, 999).per_page == 50
        assert public_page_params(0, None).page == 1
        assert public_page_params(99_999, None).page == 1000

    def test_admin_defaults_and_clamps(self) -> None:
        assert admin_page_params(None, None).per_page == 24
        assert admin_page_params(None, 999).per_page == 100

    def test_total_pages_is_at_least_one(self) -> None:
        assert public_page_params(1, 15).total_pages(0) == 1
        assert public_page_params(1, 15).total_pages(87) == 6


class TestHtmlSanitisation:
    @pytest.mark.parametrize(
        "payload",
        [
            "<script>alert(1)</script>",
            '<p onclick="steal()">x</p>',
            '<a href="javascript:alert(1)">x</a>',
        ],
    )
    def test_strips_script_vectors(self, payload: str) -> None:
        cleaned = sanitize_article_html(payload)
        assert "script" not in cleaned.lower()
        assert "onclick" not in cleaned.lower()
        assert "javascript:" not in cleaned.lower()

    def test_downgrades_h1_to_h2(self) -> None:
        assert sanitize_article_html("<h1>T</h1>") == "<h2>T</h2>"

    def test_anchors_get_rel_and_target(self) -> None:
        cleaned = sanitize_article_html('<a href="https://x.com">x</a>')
        assert 'rel="nofollow noopener noreferrer"' in cleaned
        assert 'target="_blank"' in cleaned

    def test_markdown_is_rendered_then_sanitised(self) -> None:
        cleaned = render_markdown("# Heading\n\n<script>bad()</script>")
        assert "<h2>Heading</h2>" in cleaned
        assert "script" not in cleaned.lower()


class TestUrls:
    def test_rejects_non_http_schemes(self) -> None:
        assert valid_http_url("javascript:alert(1)") is None
        assert valid_http_url("data:text/html,x") is None

    def test_bare_host_gets_https(self) -> None:
        parsed = parse_http_url("example.com/page")
        assert parsed is not None
        assert parsed.url == "https://example.com/page"
        assert parsed.domain == "example.com"


class TestArticlePayload:
    def test_keywords_lowercase_dedupe_and_cap(self) -> None:
        assert normalise_search_keyword(["SSC", "ssc", " CGL "]) == ["ssc", "cgl"]
        assert normalise_search_keyword("a,b,a") == ["a", "b"]
        assert len(normalise_search_keyword([str(n) for n in range(100)])) == 24

    def test_links_drop_bad_urls_and_default_cta(self) -> None:
        links = normalise_article_links(
            [{"url": "javascript:x"}, {"url": "https://ok.com"}]
        )
        assert links == [{"cta": "View", "url": "https://ok.com"}]

    def test_faq_requires_both_sides(self) -> None:
        assert normalise_faq_list([{"question": "q", "answer": ""}]) == []
        assert normalise_faq_list([{"question": " a  b ", "answer": "x"}]) == [
            {"question": "a b", "answer": "x"}
        ]


class TestSessionTokens:
    def test_round_trip(self) -> None:
        token = mint_session_token(42, "A@B.com", "user")
        claims = verify_session_token(token)
        assert claims is not None
        assert claims.sub == "42"
        assert claims.email == "a@b.com"  # lower-cased at mint

    def test_tampered_signature_rejected(self) -> None:
        token = mint_session_token(42, "a@b.com", "user")
        assert verify_session_token(token[:-4] + "aaaa") is None

    def test_garbage_rejected(self) -> None:
        assert verify_session_token("not-a-token") is None
        assert verify_session_token("") is None

    def test_revocation_uses_issued_at(self) -> None:
        token = mint_session_token(42, "a@b.com", "user")
        claims = verify_session_token(token)
        assert claims is not None
        assert is_revoked(claims, datetime.now(UTC) + timedelta(hours=1)) is True
        assert is_revoked(claims, datetime.now(UTC) - timedelta(hours=1)) is False
        assert is_revoked(claims, None) is False
