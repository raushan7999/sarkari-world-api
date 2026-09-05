"""Article payload normalisation.

The second of two validation layers. Pydantic rejects unknown keys and bad
types; these helpers then coerce every accepted field into a canonical, capped,
storage-safe shape. Both write paths (admin editor and the publishing API) run
through here, so tightening a rule tightens it everywhere.

Never build an Article from a spread request body — go through
`build_article_data`, which allow-lists field by field.
"""

import re
from typing import Any

from src.constants.article import (
    COVER_IMAGE_URL_MAX,
    FAQ_ANSWER_MAX,
    FAQ_MAX_ITEMS,
    FAQ_QUESTION_MAX,
    LINK_CTA_MAX,
    LINK_URL_MAX,
    LINKS_MAX,
    META_DESCRIPTION_MAX,
    META_TITLE_MAX,
    SEARCH_KEYWORD_ITEM_MAX,
    SEARCH_KEYWORD_MAX_ITEMS,
    URL_TITLE_LIST_MAX,
    URL_TITLE_TITLE_MAX,
)
from src.utils.urls import valid_http_url

_WHITESPACE = re.compile(r"\s+")


def _collapse(value: Any) -> str:
    """Collapse runs of whitespace and trim."""
    return _WHITESPACE.sub(" ", str(value or "")).strip()


def normalise_url_title_list(value: Any) -> list[dict[str, str]]:
    """Accept `["https://..."]` or `[{url, title}]`; return `[{url, title}]`."""
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        raw, title = "", ""
        if isinstance(item, str):
            raw = item
        elif isinstance(item, dict):
            raw = str(item.get("url") or item.get("link") or "")
            title = str(item.get("title") or "")
        safe = valid_http_url(raw)
        if not safe:
            continue
        out.append({"url": safe, "title": title.strip()[:URL_TITLE_TITLE_MAX]})
        if len(out) >= URL_TITLE_LIST_MAX:
            break
    return out


def normalise_cover_image_url(value: Any) -> str | None:
    safe = valid_http_url(value)
    return safe[:COVER_IMAGE_URL_MAX] if safe else None


def normalise_faq_list(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        question = _collapse(item.get("question"))[:FAQ_QUESTION_MAX]
        answer = str(item.get("answer") or "").strip()[:FAQ_ANSWER_MAX]
        if not question or not answer:
            continue
        out.append({"question": question, "answer": answer})
        if len(out) >= FAQ_MAX_ITEMS:
            break
    return out


def normalise_meta_title(value: Any) -> str | None:
    collapsed = _collapse(value)
    return collapsed[:META_TITLE_MAX] if collapsed else None


def normalise_meta_description(value: Any) -> str | None:
    collapsed = _collapse(value)
    return collapsed[:META_DESCRIPTION_MAX] if collapsed else None


def normalise_search_keyword(value: Any) -> list[str]:
    """Accept a list or a comma-separated string; lowercase and de-duplicate."""
    if isinstance(value, list):
        raw: list[Any] = value
    elif isinstance(value, str):
        raw = value.split(",")
    else:
        return []

    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        collapsed = _collapse(item).lower()
        if not collapsed:
            continue
        capped = collapsed[:SEARCH_KEYWORD_ITEM_MAX]
        if capped in seen:
            continue
        seen.add(capped)
        out.append(capped)
        if len(out) >= SEARCH_KEYWORD_MAX_ITEMS:
            break
    return out


def normalise_article_links(value: Any) -> list[dict[str, str]]:
    """Return `[{cta, url}]`; `cta` falls back to "View"."""
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        safe = valid_http_url(item.get("url"))
        if not safe:
            continue
        cta = str(item.get("cta") or "").strip()[:LINK_CTA_MAX] or "View"
        out.append({"cta": cta, "url": safe[:LINK_URL_MAX]})
        if len(out) >= LINKS_MAX:
            break
    return out
