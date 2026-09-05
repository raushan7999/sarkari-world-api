"""Category slug conversion and slug sanitisation.

The public API speaks hyphenated slugs (`latest-job`); the Postgres enum uses
underscores (`latest_job`).
"""

import re
import unicodedata

from sarkariworld.constants.article import CATEGORY_SLUGS, SLUG_MAX
from sarkariworld.models.enums import ArticleCategory

_SLUG_ALLOWED = re.compile(r"[^a-z0-9-]+")
_DASH_RUN = re.compile(r"-{2,}")


def category_slug_to_enum(slug: str | None) -> ArticleCategory | None:
    """`latest-job` -> ArticleCategory.LATEST_JOB. None if not a known slug."""
    if not slug:
        return None
    try:
        return ArticleCategory(slug.strip().lower().replace("-", "_"))
    except ValueError:
        return None


def category_enum_to_slug(category: ArticleCategory | str) -> str:
    """ArticleCategory.LATEST_JOB -> `latest-job`."""
    value = category.value if isinstance(category, ArticleCategory) else str(category)
    return value.replace("_", "-")


def is_known_category(slug: str) -> bool:
    return slug in CATEGORY_SLUGS


def slugify(value: str) -> str:
    """Lowercase, strip diacritics, collapse to `a-z0-9-`, cap at 200 chars."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    hyphenated = ascii_only.strip().lower().replace(" ", "-")
    cleaned = _DASH_RUN.sub("-", _SLUG_ALLOWED.sub("-", hyphenated))
    return cleaned.strip("-")[:SLUG_MAX]
