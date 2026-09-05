"""Bookmark engagement analytics. Read-only."""

from typing import Annotated

from fastapi import APIRouter, Query

from src.dependencies import SessionDep
from src.schemas.bookmark import BookmarkOverview, BookmarkRow
from src.schemas.pagination import AdminPage, admin_page_params
from src.services import bookmarks

router = APIRouter(prefix="/bookmarks", tags=["admin:bookmarks"])


@router.get("/overview", summary="Engagement rollup")
async def overview(
    session: SessionDep,
    article_limit: Annotated[int, Query(ge=1, le=200)] = 20,
    user_limit: Annotated[int, Query(ge=1, le=200)] = 20,
    recent_limit: Annotated[int, Query(ge=1, le=200)] = 30,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> BookmarkOverview:
    """Totals, most-bookmarked articles, most active users, and a daily timeline."""
    data = await bookmarks.overview(
        session,
        article_limit=article_limit,
        user_limit=user_limit,
        recent_limit=recent_limit,
        days=days,
    )
    return BookmarkOverview.model_validate(data)


@router.get("", summary="List bookmark rows")
async def list_bookmarks(
    session: SessionDep,
    user_id: Annotated[int | None, Query(ge=1)] = None,
    article_id: Annotated[int | None, Query(ge=1)] = None,
    page: Annotated[int | None, Query(ge=1)] = None,
    per_page: Annotated[int | None, Query(ge=1)] = None,
) -> AdminPage[BookmarkRow]:
    """Raw bookmark rows, newest first."""
    params = admin_page_params(page, per_page)
    rows, total = await bookmarks.list_all(
        session, user_id=user_id, article_id=article_id, params=params
    )
    return AdminPage[BookmarkRow].build(
        [BookmarkRow.model_validate(row) for row in rows], total, params
    )
