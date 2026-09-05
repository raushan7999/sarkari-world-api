"""Bookmark queries.

`Bookmark` has no foreign keys in this database, so joins are done explicitly
and a row may reference an article that no longer exists or is no longer
published. Callers must tolerate `article: null`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.article import Article
from src.models.bookmark import Bookmark
from src.models.enums import ArticleStatus
from src.schemas.pagination import PageParams


async def list_by_user(
    session: AsyncSession, user_id: int, params: PageParams
) -> tuple[list[tuple[Bookmark, Article | None]], int]:
    """One page of a user's bookmarks, newest first, with the article if it exists."""
    base = select(Bookmark).where(Bookmark.user_id == user_id)

    total = await session.scalar(select(func.count()).select_from(base.subquery()))

    # Outer join: the article may have been deleted since it was bookmarked.
    result = await session.execute(
        select(Bookmark, Article)
        .outerjoin(Article, Article.id == Bookmark.article_id)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc(), Bookmark.id.desc())
        .limit(params.per_page)
        .offset(params.offset)
    )
    return [(row[0], row[1]) for row in result.all()], int(total or 0)


async def toggle(session: AsyncSession, user_id: int, article_id: int) -> bool:
    """Add or remove a bookmark. Returns True if it is now bookmarked."""
    existing = await session.scalar(
        select(Bookmark).where(
            Bookmark.user_id == user_id, Bookmark.article_id == article_id
        )
    )
    if existing is not None:
        await session.delete(existing)
        await session.commit()
        return False

    session.add(Bookmark(user_id=user_id, article_id=article_id))
    await session.commit()
    return True


async def find_published_article_by_slug(
    session: AsyncSession, slug: str
) -> Article | None:
    result = await session.execute(
        select(Article).where(
            Article.slug == slug,
            Article.article_status == ArticleStatus.PUBLISHED,
        )
    )
    return result.scalar_one_or_none()


# --- Admin analytics ---------------------------------------------------------

_OVERVIEW_TOTALS = text("""
SELECT
    COUNT(*)::int                        AS bookmarks,
    COUNT(DISTINCT "user_id")::int       AS users,
    COUNT(DISTINCT "article_id")::int    AS articles
FROM "Bookmark"
""")

# `category` is cast to text because the column is a Postgres enum and this is
# raw SQL — without the cast the driver hands back the native enum value.
_TOP_ARTICLES = text("""
SELECT b."article_id", COUNT(*)::int AS count,
       a."slug", a."title", a."category"::text AS category
FROM "Bookmark" b
LEFT JOIN "Article" a ON a."id" = b."article_id"
GROUP BY b."article_id", a."slug", a."title", a."category"
ORDER BY count DESC, b."article_id" ASC
LIMIT :limit
""")

_TOP_USERS = text("""
SELECT b."user_id", COUNT(*)::int AS count, u."email"
FROM "Bookmark" b
LEFT JOIN "User" u ON u."id" = b."user_id"
GROUP BY b."user_id", u."email"
ORDER BY count DESC, b."user_id" ASC
LIMIT :limit
""")

_RECENT = text("""
SELECT "user_id", "article_id", "created_at"
FROM "Bookmark"
ORDER BY "created_at" DESC
LIMIT :limit
""")

_TIMELINE = text("""
SELECT to_char("created_at", 'YYYY-MM-DD') AS day, COUNT(*)::int AS count
FROM "Bookmark"
WHERE "created_at" >= (CURRENT_DATE - make_interval(days => :days))
GROUP BY day
ORDER BY day ASC
""")


async def overview(
    session: AsyncSession,
    *,
    article_limit: int,
    user_limit: int,
    recent_limit: int,
    days: int,
) -> dict[str, Any]:
    """Engagement rollup for the admin dashboard."""
    totals = (await session.execute(_OVERVIEW_TOTALS)).mappings().one()
    top_articles = (
        (await session.execute(_TOP_ARTICLES, {"limit": article_limit}))
        .mappings()
        .all()
    )
    top_users = (
        (await session.execute(_TOP_USERS, {"limit": user_limit})).mappings().all()
    )
    recent = (await session.execute(_RECENT, {"limit": recent_limit})).mappings().all()
    timeline = (await session.execute(_TIMELINE, {"days": days})).mappings().all()

    return {
        "totals": dict(totals),
        "top_articles": [dict(row) for row in top_articles],
        "top_users": [dict(row) for row in top_users],
        "recent": [dict(row) for row in recent],
        "timeline": [dict(row) for row in timeline],
        "window_days": days,
    }


async def list_all(
    session: AsyncSession,
    *,
    user_id: int | None,
    article_id: int | None,
    params: PageParams,
) -> tuple[list[Bookmark], int]:
    """Raw bookmark rows, newest first, optionally filtered."""
    statement = select(Bookmark)
    if user_id is not None:
        statement = statement.where(Bookmark.user_id == user_id)
    if article_id is not None:
        statement = statement.where(Bookmark.article_id == article_id)

    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    result = await session.execute(
        statement.order_by(Bookmark.created_at.desc(), Bookmark.id.desc())
        .limit(params.per_page)
        .offset(params.offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def delete_for_article(session: AsyncSession, article_id: int) -> None:
    """Clear bookmarks pointing at an article that is being deleted."""
    await session.execute(delete(Bookmark).where(Bookmark.article_id == article_id))
