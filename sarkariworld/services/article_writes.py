"""Article write-path payload construction.

Shared by the admin editor and the publishing API so a tightened rule applies
to both. This is the second validation layer: Pydantic has already rejected
unknown keys and bad types, and every value is now allow-listed field by field
and normalised before it can reach the database.

Never build an Article from a spread request body.
"""

from __future__ import annotations

from typing import Any

from sarkariworld.models.enums import ArticleCategory
from sarkariworld.models.user import User
from sarkariworld.utils.article_payload import (
    normalise_article_links,
    normalise_cover_image_url,
    normalise_faq_list,
    normalise_meta_description,
    normalise_meta_title,
    normalise_search_keyword,
    normalise_url_title_list,
)
from sarkariworld.utils.html import render_markdown, sanitize_article_html
from sarkariworld.utils.slugs import category_slug_to_enum

# Fields copied through with only whitespace trimming.
_PLAIN_FIELDS = ("title", "description")


def build_article_data(
    payload: dict[str, Any],
    *,
    author: User | None = None,
    markdown_content: str | None = None,
) -> dict[str, Any]:
    """Turn a validated request body into safe ORM keyword arguments.

    Only keys present in `payload` are returned, so a partial update merges
    cleanly over the existing row instead of blanking absent fields.
    """
    data: dict[str, Any] = {}

    for field in _PLAIN_FIELDS:
        if field in payload:
            data[field] = str(payload[field] or "").strip()

    if payload.get("slug"):
        data["slug"] = str(payload["slug"]).strip().lower()

    if "category" in payload and payload["category"] is not None:
        resolved = category_slug_to_enum(str(payload["category"]))
        data["category"] = resolved if resolved is not None else ArticleCategory.BLOG

    if "article_status" in payload and payload["article_status"] is not None:
        data["article_status"] = payload["article_status"]

    if "published_at" in payload:
        data["published_at"] = payload["published_at"]

    # Body: markdown is rendered then sanitised; raw HTML is sanitised. Both
    # go through the same allow-list, so stored HTML is identical either way.
    if markdown_content is not None:
        data["html_content"] = render_markdown(markdown_content)
    elif "html_content" in payload:
        data["html_content"] = sanitize_article_html(payload.get("html_content"))

    if "meta_title" in payload:
        data["meta_title"] = normalise_meta_title(payload["meta_title"])
    if "meta_description" in payload:
        data["meta_description"] = normalise_meta_description(
            payload["meta_description"]
        )
    if "search_keyword" in payload:
        data["search_keyword"] = normalise_search_keyword(payload["search_keyword"])
    if "links" in payload:
        data["links"] = normalise_article_links(_as_dicts(payload["links"]))
    if "faq" in payload:
        data["faq"] = normalise_faq_list(_as_dicts(payload["faq"]))
    if "instagram_post_url" in payload:
        data["instagram_post_url"] = normalise_url_title_list(
            payload["instagram_post_url"]
        )
    if "youtube_video_url" in payload:
        data["youtube_video_url"] = normalise_url_title_list(
            payload["youtube_video_url"]
        )
    if "cover_image_url" in payload:
        data["cover_image_url"] = normalise_cover_image_url(payload["cover_image_url"])

    if author is not None:
        data["author_id"] = str(author.id)
        data["author_name"] = author.name

    return data


def _as_dicts(value: Any) -> Any:
    """Accept Pydantic items or plain dicts; the normalisers expect dicts."""
    if isinstance(value, list):
        return [
            item.model_dump() if hasattr(item, "model_dump") else item for item in value
        ]
    return value
