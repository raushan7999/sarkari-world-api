"""Endpoints a signed-in reader calls for themselves.

Every route here requires authentication — the dependency is declared on the
router so a new endpoint cannot accidentally be public.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.dependencies import AuthedUser, SessionDep, require_auth
from src.exceptions import NotFoundError
from src.schemas.bookmark import (
    BookmarkedArticle,
    BookmarkItem,
    BookmarkToggleRequest,
    BookmarkToggleResponse,
)
from src.schemas.pagination import PublicPage, public_page_params
from src.services import bookmarks
from src.utils.logger import get_logger
from src.utils.slugs import category_enum_to_slug

logger = get_logger(__name__)

router = APIRouter(
    prefix="/account", tags=["account"], dependencies=[Depends(require_auth)]
)


@router.get("/bookmarks", summary="List my bookmarks")
async def list_bookmarks(
    user: AuthedUser,
    session: SessionDep,
    page: Annotated[int | None, Query(ge=1)] = None,
    per_page: Annotated[int | None, Query(ge=1)] = None,
) -> PublicPage[BookmarkItem]:
    """The caller's bookmarks, newest first."""
    params = public_page_params(page, per_page)
    rows, total = await bookmarks.list_by_user(session, user.id, params)

    items = [
        BookmarkItem(
            article_id=bookmark.article_id,
            created_at=bookmark.created_at,
            article=(
                BookmarkedArticle(
                    slug=article.slug,
                    title=article.title,
                    category=category_enum_to_slug(article.category),
                )
                if article is not None
                else None
            ),
        )
        for bookmark, article in rows
    ]
    return PublicPage[BookmarkItem].build(items, total, params)


@router.post("/bookmarks/toggle", summary="Bookmark or un-bookmark an article")
async def toggle_bookmark(
    payload: BookmarkToggleRequest,
    user: AuthedUser,
    session: SessionDep,
) -> BookmarkToggleResponse:
    """Toggle by slug. Only published articles can be bookmarked."""
    article = await bookmarks.find_published_article_by_slug(session, payload.slug)
    if article is None:
        raise NotFoundError(f"Article not found: {payload.slug}")

    bookmarked = await bookmarks.toggle(session, user.id, article.id)
    logger.info(
        "bookmark_toggle",
        user_id=user.id,
        article_id=article.id,
        bookmarked=bookmarked,
    )
    return BookmarkToggleResponse(slug=payload.slug, bookmarked=bookmarked)
