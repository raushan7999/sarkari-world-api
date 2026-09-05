"""Dashboard counters and the constants the admin SPA needs to validate forms."""

from fastapi import APIRouter

from sarkariworld.constants import article as caps
from sarkariworld.constants.article import CATEGORY_SLUGS
from sarkariworld.constants.auth import AUTH_PROVIDERS
from sarkariworld.dependencies import SessionDep
from sarkariworld.models.enums import ArticleStatus, UserRole
from sarkariworld.schemas.article import DashboardResponse, MetaLimits, MetaResponse
from sarkariworld.services import articles

router = APIRouter(tags=["admin"])


@router.get("/dashboard", summary="Article counters")
async def dashboard(session: SessionDep) -> DashboardResponse:
    """Article counts per workflow status."""
    stats = await articles.get_admin_stats(session)
    return DashboardResponse(**stats)


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
