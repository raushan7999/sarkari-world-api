"""Public, anonymous, read-only content.

Only `published` articles are ever exposed here.

Route order is load-bearing: the literal paths must be declared before
`/{category}` and `/{slug}`, or the catch-alls swallow them. FastAPI matches in
declaration order, so moving a route up or down changes behaviour.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from sarkariworld.constants.article import (
    CATEGORY_LABELS,
    CATEGORY_SLUGS,
    SEARCH_QUERY_MAX,
)
from sarkariworld.dependencies import SessionDep
from sarkariworld.exceptions import NotFoundError
from sarkariworld.schemas.article import (
    ArticleCard,
    CategoryItem,
    CategoryPage,
    PublicArticle,
    SearchResponse,
)
from sarkariworld.schemas.common import PUBLIC_RESPONSES
from sarkariworld.schemas.pagination import public_page_params
from sarkariworld.services import articles
from sarkariworld.utils.logger import get_logger
from sarkariworld.utils.slugs import category_slug_to_enum

logger = get_logger(__name__)

router = APIRouter(tags=["public"], responses=PUBLIC_RESPONSES)


@router.get("/category", summary="List categories")
async def list_categories() -> list[CategoryItem]:
    """The fixed category taxonomy, for building navigation."""
    return [
        CategoryItem(slug=slug, name=CATEGORY_LABELS[slug]) for slug in CATEGORY_SLUGS
    ]


@router.get("/search", summary="Search published articles")
async def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=SEARCH_QUERY_MAX)],
) -> SearchResponse:
    """Fuzzy title search. Typo-tolerant; a query under 2 characters returns none."""
    rows = await articles.search_published(session, q)
    logger.info("search_submit", query_length=len(q), results=len(rows))
    return SearchResponse(
        query=q.strip(),
        total=len(rows),
        articles=[ArticleCard.model_validate(row) for row in rows],
    )


@router.get("/{category}", summary="List articles in a category")
async def list_category(
    category: str,
    session: SessionDep,
    page: Annotated[int | None, Query(ge=1)] = None,
    per_page: Annotated[int | None, Query(ge=1)] = None,
) -> CategoryPage:
    """One page of published articles, newest first.

    404 for an unknown category slug. The source falls through to the article
    detail route here; an explicit 404 is clearer and the client can retry
    against `/{slug}`.
    """
    resolved = category_slug_to_enum(category)
    if resolved is None:
        raise NotFoundError(f"Unknown category: {category}")

    params = public_page_params(page, per_page)
    rows, total = await articles.find_category_page(
        session, resolved, limit=params.per_page, offset=params.offset
    )

    total_pages = params.total_pages(total)
    has_more = params.page < total_pages
    return CategoryPage(
        category=category,
        page=params.page,
        per_page=params.per_page,
        total=total,
        total_pages=total_pages,
        has_more=has_more,
        next_page=params.page + 1 if has_more else None,
        articles=[ArticleCard.model_validate(row) for row in rows],
    )


@router.get("/article/{slug}", summary="Article detail")
async def get_article(slug: str, session: SessionDep) -> PublicArticle:
    """Full detail for one published article.

    Namespaced under `/article/` rather than sitting at the root: a bare
    `/{slug}` catch-all cannot coexist with `/{category}` without one
    shadowing the other.
    """
    article = await articles.find_published_by_slug(session, slug)
    if article is None:
        raise NotFoundError(f"Article not found: {slug}")

    logger.info("article_open", slug=slug)
    return PublicArticle.model_validate(article)
