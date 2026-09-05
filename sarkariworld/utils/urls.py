"""URL allow-listing.

Only `http`/`https` survive — `javascript:`, `data:`, `file:` and friends are
rejected. Ports `validHttpUrl`/`parseHttpUrl` from the Node service.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from sarkariworld.constants.article import WEB_URL_MAX

# Codepoints that carry no intent when pasted into a URL field: control bytes,
# zero-width characters and the BOM. Built from ordinals so this file holds no
# literal invisible bytes.
_INVISIBLE_RANGES: tuple[tuple[int, int], ...] = (
    (0x0000, 0x001F),  # C0 controls
    (0x007F, 0x009F),  # DEL + C1 controls
    (0x200B, 0x200D),  # zero-width space/non-joiner/joiner
    (0x2060, 0x2060),  # word joiner
    (0xFEFF, 0xFEFF),  # BOM
)
_INVISIBLE = re.compile(
    "[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in _INVISIBLE_RANGES) + "]"
)

# Homoglyphs that users paste from rich text editors.
_NBSP = chr(0x00A0)
_FULLWIDTH_COLON = chr(0xFF1A)
_FULLWIDTH_SLASH = chr(0xFF0F)

_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedUrl:
    url: str
    domain: str


def _normalize_input(value: str | None) -> str:
    capped = str(value or "")[:WEB_URL_MAX]
    cleaned = _INVISIBLE.sub("", capped)
    cleaned = (
        cleaned.replace(_NBSP, " ")
        .replace(_FULLWIDTH_COLON, ":")
        .replace(_FULLWIDTH_SLASH, "/")
    )
    return cleaned.strip()[:2048]


def valid_http_url(value: str | None) -> str | None:
    """Return the canonical URL if it is http(s), else None. No auto-scheme."""
    trimmed = str(value or "").strip()
    if not trimmed:
        return None
    try:
        parsed = urlparse(trimmed)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return urlunparse(parsed)


def parse_http_url(value: str | None) -> ParsedUrl | None:
    """Parse a user-supplied URL, auto-prefixing `https://` for a bare host."""
    cleaned = _normalize_input(value)
    if not cleaned:
        return None
    candidate = cleaned if _SCHEME.match(cleaned) else f"https://{cleaned}"
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return ParsedUrl(url=urlunparse(parsed), domain=parsed.hostname.lower())
