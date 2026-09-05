"""Article queries.

All database access for articles lives here; routers deal in HTTP and Pydantic.
Only `published` rows are ever returned by the public helpers.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.constants.article import SEARCH_QUERY_MAX, SEARCH_RESULT_MAX
from src.models.article import Article
from src.models.enums import ArticleCategory, ArticleStatus
from src.utils.dates import ist_day_bounds, now_ist
from src.utils.slugs import category_enum_to_slug

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE = re.compile(r"\s+")

# Ported verbatim from the Node service. Three index-driven legs — exact
# tsvector match, trigram typo tolerance, and a normalised substring ILIKE —
# blended and re-ranked. Every input is a bound parameter, never interpolated.
_SEARCH_SQL = text("""
WITH params AS (
    SELECT
        plainto_tsquery('simple', :q)::tsquery AS tsq,
        CAST(:qnorm AS text)                   AS qnorm,
        CAST(:tokens AS text[])                AS tokens
),
candidates AS (
    SELECT
        a."id", a."title", a."slug", a."description", a."category",
        a."html_content", a."article_status",
        a."published_at", a."created_at", a."updated_at",
        a."author_id", a."author_name",
        a."instagram_post_url", a."youtube_video_url", a."faq",
        a."cover_image_url", a."links",
        a."search_keyword", a."meta_title", a."meta_description",
        a."title_normalized",
        (a."title_search" @@ p.tsq)                        AS exact_hit,
        (a."title_normalized" ILIKE '%' || p.qnorm || '%') AS substr_hit,
        ts_rank(a."title_search", p.tsq)                   AS exact_score,
        word_similarity(p.qnorm, a."title_normalized")     AS fuzzy_score
    FROM "Article" a
    CROSS JOIN params p
    WHERE a."article_status" = 'published'
      AND (
        a."title_search" @@ p.tsq
        OR p.qnorm <% a."title_normalized"
        OR a."title_normalized" ILIKE '%' || p.qnorm || '%'
      )
    ORDER BY exact_hit DESC, substr_hit DESC
    LIMIT 200
)
SELECT
    c."id", c."title", c."description", c."slug",
    c."category"::text AS "category",
    c."html_content",
    c."article_status"::text AS "article_status",
    c."published_at", c."created_at", c."updated_at",
    c."author_id", c."author_name",
    c."instagram_post_url", c."youtube_video_url", c."faq",
    c."cover_image_url", c."links",
    c."search_keyword", c."meta_title", c."meta_description"
FROM candidates c
ORDER BY
    c.substr_hit DESC,
    (
        SELECT COUNT(*)::int
        FROM unnest((SELECT tokens FROM params)) AS token
        WHERE c."title_normalized" ILIKE '%' || token || '%'
    ) DESC,
    (c.exact_score * 0.65 + c.fuzzy_score * 0.35) DESC,
    c.fuzzy_score DESC,
    c.published_at DESC NULLS LAST
LIMIT :limit
""")


def _normalise_query(query: str) -> str:
    """Mirror the `title_normalized` column expression so comparisons line up."""
    lowered = query.lower()
    return _WHITESPACE.sub(" ", _NON_ALNUM.sub(" ", lowered)).strip()


async def search_published(
    session: AsyncSession, query: str, limit: int = SEARCH_RESULT_MAX
) -> list[dict[str, Any]]:
    """Fuzzy search over published articles. Returns [] for a too-short query."""
    trimmed = str(query or "").strip()[:SEARCH_QUERY_MAX]
    # Single-character queries match too much to be useful.
    if len(trimmed) < 2:
        return []

    normalized = _normalise_query(trimmed)
    if not normalized:
        return []

    result = await session.execute(
        _SEARCH_SQL,
        {
            "q": trimmed,
            "qnorm": normalized,
            "tokens": normalized.split(" "),
            "limit": max(1, min(limit, SEARCH_RESULT_MAX)),
        },
    )
    return [dict(row) for row in result.mappings()]


def _published() -> Select[tuple[Article]]:
    return select(Article).where(Article.article_status == ArticleStatus.PUBLISHED)


async def find_published_by_slug(session: AsyncSession, slug: str) -> Article | None:
    result = await session.execute(_published().where(Article.slug == slug))
    return result.scalar_one_or_none()


async def find_category_page(
    session: AsyncSession, category: ArticleCategory, *, limit: int, offset: int
) -> tuple[list[Article], int]:
    """One page of published articles in a category, newest first."""
    statement = _published().where(Article.category == category)

    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    result = await session.execute(
        statement.order_by(Article.published_at.desc().nulls_last())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


# --- Admin -------------------------------------------------------------------


async def find_by_slug(session: AsyncSession, slug: str) -> Article | None:
    """Any status — admin callers see drafts and archived rows."""
    result = await session.execute(select(Article).where(Article.slug == slug))
    return result.scalar_one_or_none()


async def slug_exists(
    session: AsyncSession, slug: str, *, except_id: int | None = None
) -> bool:
    statement = select(Article.id).where(Article.slug == slug)
    if except_id is not None:
        statement = statement.where(Article.id != except_id)
    return await session.scalar(statement) is not None


async def find_for_admin_page(
    session: AsyncSession,
    *,
    query: str | None,
    category: ArticleCategory | None,
    status: ArticleStatus | None,
    date_field: str,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Article], int]:
    """Filtered admin listing across every status."""
    statement = select(Article)

    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(Article.title.ilike(pattern), Article.slug.ilike(pattern))
        )
    # The source compares a hyphenated slug against underscore enum values here
    # and silently drops the filter; callers pass a converted enum instead.
    if category is not None:
        statement = statement.where(Article.category == category)
    if status is not None:
        statement = statement.where(Article.article_status == status)

    column = Article.updated_at if date_field == "updated_at" else Article.created_at
    if date_from:
        statement = statement.where(column >= ist_day_bounds(date_from)[0])
    if date_to:
        statement = statement.where(column < ist_day_bounds(date_to)[1])

    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    result = await session.execute(
        statement.order_by(column.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def find_recent_for_admin(session: AsyncSession, limit: int) -> list[Article]:
    result = await session.execute(
        select(Article).order_by(Article.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


# A draft nobody has touched in this long is backlog, not work in progress.
STALE_DRAFT_DAYS = 30
# The window the dashboard's "recent activity" counters cover.
ACTIVITY_WINDOW_DAYS = 7


async def get_admin_stats(session: AsyncSession) -> dict[str, int]:
    """Counters for the dashboard's KPI row.

    Deliberately one round trip of cheap aggregates: this is the first thing
    the console renders, so it must not wait on the heavier breakdowns below.
    """
    now = now_ist()
    activity_since = now - timedelta(days=ACTIVITY_WINDOW_DAYS)
    stale_before = now - timedelta(days=STALE_DRAFT_DAYS)
    published = Article.article_status == ArticleStatus.PUBLISHED
    draft = Article.article_status == ArticleStatus.DRAFT

    row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(published).label("published"),
                func.count().filter(draft).label("draft"),
                func.count()
                .filter(Article.article_status == ArticleStatus.ARCHIVED)
                .label("archived"),
                # A subset of `published`, not a fourth status: the row is
                # published but dated forward, so the public site has not
                # surfaced it yet.
                func.count()
                .filter(published, Article.published_at > now)
                .label("scheduled"),
                func.count()
                .filter(draft, Article.updated_at < stale_before)
                .label("stale_drafts"),
                func.count()
                .filter(Article.created_at >= activity_since)
                .label("created_recently"),
                func.count()
                .filter(published, Article.published_at >= activity_since)
                .filter(Article.published_at <= now)
                .label("published_recently"),
            )
        )
    ).one()

    return {
        **dict(row._mapping),
        "activity_window_days": ACTIVITY_WINDOW_DAYS,
        "stale_draft_days": STALE_DRAFT_DAYS,
    }


async def get_category_breakdown(session: AsyncSession) -> list[dict[str, Any]]:
    """Article counts per category, split by workflow status.

    The editorial question this answers is "where is the backlog?" — a
    category with thirty drafts and two published rows is a different problem
    from one with neither.
    """
    rows = (
        await session.execute(
            select(
                Article.category,
                func.count().label("total"),
                func.count()
                .filter(Article.article_status == ArticleStatus.PUBLISHED)
                .label("published"),
                func.count()
                .filter(Article.article_status == ArticleStatus.DRAFT)
                .label("draft"),
                func.count()
                .filter(Article.article_status == ArticleStatus.ARCHIVED)
                .label("archived"),
            )
            .group_by(Article.category)
            .order_by(func.count().desc())
        )
    ).all()

    return [
        {
            # Hyphenated public slug, as everywhere else on the wire.
            "category": category_enum_to_slug(category),
            "total": total,
            "published": published,
            "draft": draft,
            "archived": archived,
        }
        for category, total, published, draft, archived in rows
    ]


# Days with no activity are absent from a GROUP BY, which would draw a chart
# with a missing bar rather than a zero one. generate_series supplies the
# full axis and the counts left-join onto it.
_TIMELINE_SQL = text("""
WITH days AS (
    SELECT generate_series(
        CURRENT_DATE - make_interval(days => :days - 1),
        CURRENT_DATE,
        interval '1 day'
    )::date AS day
)
SELECT
    to_char(d.day, 'YYYY-MM-DD') AS day,
    COALESCE(c.created, 0)::int  AS created,
    COALESCE(p.published, 0)::int AS published
FROM days d
LEFT JOIN (
    SELECT "created_at"::date AS day, COUNT(*) AS created
    FROM "Article"
    WHERE "created_at" >= CURRENT_DATE - make_interval(days => :days - 1)
    GROUP BY 1
) c ON c.day = d.day
LEFT JOIN (
    SELECT "published_at"::date AS day, COUNT(*) AS published
    FROM "Article"
    WHERE "article_status" = 'published'
      AND "published_at" >= CURRENT_DATE - make_interval(days => :days - 1)
      AND "published_at" <= now()
    GROUP BY 1
) p ON p.day = d.day
ORDER BY d.day ASC
""")


async def get_publishing_timeline(
    session: AsyncSession, days: int
) -> list[dict[str, Any]]:
    """Articles created and published per day, over the last `days` days."""
    rows = (await session.execute(_TIMELINE_SQL, {"days": days})).mappings().all()
    return [dict(row) for row in rows]


async def create(session: AsyncSession, data: dict[str, Any]) -> Article:
    article = Article(**data)
    session.add(article)
    await session.commit()
    await session.refresh(article)
    return article


async def update(
    session: AsyncSession, article: Article, data: dict[str, Any]
) -> Article:
    for field, value in data.items():
        setattr(article, field, value)
    await session.commit()
    await session.refresh(article)
    return article


async def set_status(
    session: AsyncSession, article: Article, status: ArticleStatus, *, now: datetime
) -> Article:
    """Change workflow status, stamping `published_at` on first publish."""
    article.article_status = status
    if status is ArticleStatus.PUBLISHED and article.published_at is None:
        article.published_at = now
    await session.commit()
    await session.refresh(article)
    return article


async def delete(session: AsyncSession, article: Article) -> None:
    await session.delete(article)
    await session.commit()
