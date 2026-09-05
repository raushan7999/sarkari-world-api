"""Article content pipeline: markdown rendering and HTML sanitisation.

Both write paths (the admin editor posting HTML, and the publishing API posting
markdown) run through the same allow-list, so the stored HTML is identical
regardless of origin. This is the stored-XSS defence (CWE-79).
"""

import re

import nh3
from markdown_it import MarkdownIt

_ALLOWED_TAGS: set[str] = {
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "blockquote",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "code",
    "pre",
    "br",
    "hr",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "span",
    "div",
    "figure",
    "figcaption",
}

_ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    # `rel` is managed by nh3 via link_rel; `target` is forced on below.
    "a": {"href", "title"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
    "*": {"class"},
}

_ALLOWED_SCHEMES: set[str] = {"http", "https", "mailto"}

_ANCHOR_OPEN = re.compile(r"<a\s", re.IGNORECASE)

_markdown = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("table")


def sanitize_article_html(html: str | None) -> str:
    """Sanitise HTML against the article allow-list.

    `<h1>` is downgraded to `<h2>` — the page's own `<h1>` is the article
    title. Anchors get `rel="nofollow noopener noreferrer"` and open in a new
    tab, matching the Node service.
    """
    if not html:
        return ""
    # nh3 has no tag-rename hook, so rewrite h1 before sanitising. The tag is
    # not in the allow-list, so any h1 that survives this would be stripped.
    downgraded = (
        html.replace("<h1", "<h2")
        .replace("</h1>", "</h2>")
        .replace("<H1", "<h2")
        .replace("</H1>", "</h2>")
    )
    cleaned = nh3.clean(
        downgraded,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_SCHEMES,
        link_rel="nofollow noopener noreferrer",
    )
    # nh3 cannot add attributes, so force target after cleaning. Any incoming
    # target was already stripped, so this cannot be overridden by input.
    return _ANCHOR_OPEN.sub('<a target="_blank" ', cleaned)


def render_markdown(markdown: str | None) -> str:
    """Render markdown to sanitised article HTML."""
    if not markdown:
        return ""
    return sanitize_article_html(_markdown.render(markdown))
