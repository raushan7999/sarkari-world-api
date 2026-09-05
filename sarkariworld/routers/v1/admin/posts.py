"""Article CRUD and the publishing workflow."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from sarkariworld.constants.article import SLUG_MAX
from sarkariworld.dependencies import ManageUser, SessionDep
from sarkariworld.exceptions import ConflictError, NotFoundError
from sarkariworld.models.enums import ArticleStatus
from sarkariworld.schemas.article import (
    AdminArticle,
    ArticleCard,
    ArticleCreate,
    ArticlePublish,
    ArticleStatusUpdate,
    ArticleUpdate,
)
from sarkariworld.schemas.pagination import AdminPage, admin_page_params
from sarkariworld.services import articles
from sarkariworld.services.article_writes import build_article_data
from sarkariworld.utils.dates import now_ist
from sarkariworld.utils.logger import get_logger
from sarkariworld.utils.slugs import category_slug_to_enum

logger = get_logger(__name__)

router = APIRouter(prefix="/posts", tags=["admin:posts"])


@router.get("", summary="List articles")
async def list_posts(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query()] = None,
    article_status: Annotated[ArticleStatus | None, Query(alias="status")] = None,
    date_field: Annotated[Literal["created_at", "updated_at"], Query()] = "created_at",
    date_from: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    date_to: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")] = None,
    page: Annotated[int | None, Query(ge=1)] = None,
    per_page: Annotated[int | None, Query(ge=1)] = None,
) -> AdminPage[ArticleCard]:
    """Filtered listing across every status.

    `category` takes a public hyphen slug and is converted before querying —
    the source compares the raw slug against underscore enum values and
    silently drops the filter.
    """
    params = admin_page_params(page, per_page)
    rows, total = await articles.find_for_admin_page(
        session,
        query=q,
        category=category_slug_to_enum(category) if category else None,
        status=article_status,
        date_field=date_field,
        date_from=date_from,
        date_to=date_to,
        limit=params.per_page,
        offset=params.offset,
    )
    return AdminPage[ArticleCard].build(
        [ArticleCard.model_validate(row) for row in rows], total, params
    )


@router.get("/recent", summary="Recently created articles")
async def recent_posts(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[ArticleCard]:
    """Newest articles regardless of status. Declared before `/{slug}`."""
    rows = await articles.find_recent_for_admin(session, limit)
    return [ArticleCard.model_validate(row) for row in rows]


@router.get("/{slug}", summary="Get an article")
async def get_post(slug: str, session: SessionDep) -> AdminArticle:
    """Any status, unlike the public detail route."""
    article = await articles.find_by_slug(session, slug)
    if article is None:
        raise NotFoundError(f"Article not found: {slug}")
    return AdminArticle.model_validate(article)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create an article")
async def create_post(
    payload: ArticleCreate, session: SessionDep, actor: ManageUser
) -> AdminArticle:
    """Create from sanitised HTML. Publishing without a date stamps it now."""
    if await articles.slug_exists(session, payload.slug):
        raise ConflictError(f"Slug already in use: {payload.slug}")

    data = build_article_data(payload.model_dump(exclude_unset=True), author=actor)
    if data.get("article_status") is ArticleStatus.PUBLISHED and not data.get(
        "published_at"
    ):
        data["published_at"] = now_ist()

    article = await articles.create(session, data)
    logger.info("admin_post_create", slug=article.slug, article_id=article.id)
    return AdminArticle.model_validate(article)


@router.put("/{slug}", summary="Update an article")
async def update_post(
    slug: str,
    payload: ArticleUpdate,
    session: SessionDep,
    actor: ManageUser,
) -> AdminArticle:
    """Partial update merged over the existing row.

    Only keys actually sent are applied, so omitting a field leaves it alone
    rather than blanking it.
    """
    article = await articles.find_by_slug(session, slug)
    if article is None:
        raise NotFoundError(f"Article not found: {slug}")

    body = payload.model_dump(exclude_unset=True)
    if body.get("slug") and await articles.slug_exists(
        session, body["slug"], except_id=article.id
    ):
        raise ConflictError(f"Slug already in use: {body['slug']}")

    data = build_article_data(body, author=actor)
    # First transition to published stamps the date.
    if (
        data.get("article_status") is ArticleStatus.PUBLISHED
        and article.published_at is None
        and not data.get("published_at")
    ):
        data["published_at"] = now_ist()

    updated = await articles.update(session, article, data)
    logger.info("admin_post_update", slug=slug, article_id=updated.id)
    return AdminArticle.model_validate(updated)


@router.patch("/{slug}/status", summary="Change article status")
async def update_post_status(
    slug: str, payload: ArticleStatusUpdate, session: SessionDep
) -> AdminArticle:
    """Move an article through draft -> published -> archived."""
    article = await articles.find_by_slug(session, slug)
    if article is None:
        raise NotFoundError(f"Article not found: {slug}")

    updated = await articles.set_status(session, article, payload.status, now=now_ist())
    logger.info("admin_post_status", slug=slug, status=payload.status.value)
    return AdminArticle.model_validate(updated)


@router.delete(
    "/{slug}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an article"
)
async def delete_post(slug: str, session: SessionDep) -> None:
    """Admin only — `require_manage` restricts every DELETE to admins."""
    article = await articles.find_by_slug(session, slug)
    if article is None:
        raise NotFoundError(f"Article not found: {slug}")
    await articles.delete(session, article)
    logger.info("admin_post_delete", slug=slug)


publish_router = APIRouter(prefix="/publish", tags=["admin:publish"])


@publish_router.post(
    "/articles",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a markdown article",
)
async def publish_article(
    payload: ArticlePublish, session: SessionDep, actor: ManageUser
) -> AdminArticle:
    """Server-to-server markdown ingest, typically driven by an API key.

    Always created as a draft: automated content goes through human review
    before it can appear publicly. The body accepts neither `html_content` nor
    `article_status`, so a caller cannot self-publish.
    """
    if len(payload.slug) > SLUG_MAX:
        raise ConflictError("Slug is too long.")
    if await articles.slug_exists(session, payload.slug):
        raise ConflictError(f"Slug already in use: {payload.slug}")

    body = payload.model_dump(exclude_unset=True)
    content = body.pop("content", None)
    data = build_article_data(body, author=actor, markdown_content=content or "")
    data["article_status"] = ArticleStatus.DRAFT

    article = await articles.create(session, data)
    logger.info("publish_article", slug=article.slug, article_id=article.id)
    return AdminArticle.model_validate(article)
