"""Dashboard counters, content analytics, and the constants the admin SPA
needs to validate forms client-side."""

from typing import Annotated

from fastapi import APIRouter, Query

from src.constants import article as caps
from src.constants.article import CATEGORY_SLUGS
from src.constants.auth import AUTH_PROVIDERS
from src.dependencies import SessionDep
from src.models.enums import ArticleStatus, UserRole
from src.schemas.article import (
    CategoryBreakdownRow,
    DashboardResponse,
    MetaLimits,
    MetaResponse,
    TimelinePoint,
)
from src.services import articles

router = APIRouter(tags=["admin"])


@router.get("/dashboard", summary="Article counters")
async def dashboard(session: SessionDep) -> DashboardResponse:
    """Article counts per workflow status, plus the backlog and activity
    counters the console's KPI row shows.

    Kept to one round trip of cheap aggregates: this is the first thing the
    dashboard renders, and it must not wait on the breakdowns below.
    """
    stats = await articles.get_admin_stats(session)
    return DashboardResponse(**stats)


@router.get("/analytics/categories", summary="Article counts per category")
async def category_breakdown(session: SessionDep) -> list[CategoryBreakdownRow]:
    """Where the content — and the backlog — actually sits.

    Separate from `/dashboard` so a heavier group-by cannot delay the KPI row.
    """
    rows = await articles.get_category_breakdown(session)
    return [CategoryBreakdownRow.model_validate(row) for row in rows]


@router.get("/analytics/timeline", summary="Publishing activity per day")
async def publishing_timeline(
    session: SessionDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> list[TimelinePoint]:
    """Articles created and published per day, for the publishing-rate chart."""
    rows = await articles.get_publishing_timeline(session, days)
    return [TimelinePoint.model_validate(row) for row in rows]


@router.get("/meta", summary="Enums and field limits")
async def meta() -> MetaResponse:
    """Everything the admin form needs to validate client-side.

    Served from the same constants the API enforces, so the two cannot drift.
    """
    return MetaResponse(
        categories=list(CATEGORY_SLUGS),
        article_statuses=[status.value for status in ArticleStatus],
        user_roles=[role.value for role in UserRole],
        auth_providers=list(AUTH_PROVIDERS),
        limits=MetaLimits(
            faq_max_items=caps.FAQ_MAX_ITEMS,
            faq_max_question_len=caps.FAQ_QUESTION_MAX,
            faq_max_answer_len=caps.FAQ_ANSWER_MAX,
            meta_title_max_len=caps.META_TITLE_MAX,
            meta_description_max_len=caps.META_DESCRIPTION_MAX,
            search_keyword_item_max_len=caps.SEARCH_KEYWORD_ITEM_MAX,
            search_keyword_max_items=caps.SEARCH_KEYWORD_MAX_ITEMS,
            article_links_max=caps.LINKS_MAX,
            article_link_cta_max=caps.LINK_CTA_MAX,
            article_link_url_max=caps.LINK_URL_MAX,
            url_title_list_max=caps.URL_TITLE_LIST_MAX,
            url_title_title_max=caps.URL_TITLE_TITLE_MAX,
            cover_image_url_max=caps.COVER_IMAGE_URL_MAX,
        ),
    )
