"""Web URL triage backlog."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from src.constants.article import WEB_URL_DOMAIN_MAX, WEB_URL_TITLE_MAX
from src.dependencies import SessionDep
from src.exceptions import ConflictError, NotFoundError, ValidationError
from src.schemas.pagination import AdminPage, admin_page_params
from src.schemas.web_url import MarkAllViewedResponse, WebUrlCreate, WebUrlRead
from src.services import web_urls
from src.utils.logger import get_logger
from src.utils.urls import parse_http_url

logger = get_logger(__name__)

router = APIRouter(prefix="/web-urls", tags=["admin:web-urls"])


@router.get("", summary="List web URLs")
async def list_web_urls(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    # Defaults to `oldest` so never-viewed rows surface first.
    sort: Annotated[Literal["oldest", "newest"], Query()] = "oldest",
    viewed: Annotated[Literal["all", "yes", "no"], Query()] = "all",
    not_viewed_since: Annotated[
        str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$")
    ] = None,
    page: Annotated[int | None, Query(ge=1)] = None,
    per_page: Annotated[int | None, Query(ge=1)] = None,
) -> AdminPage[WebUrlRead]:
    """The triage list. Unviewed URLs sort first by default.

    `viewed` splits the backlog into seen and unseen; `not_viewed_since` takes
    an IST calendar day and keeps rows last viewed before it, plus every row
    never viewed at all. The two compose.
    """
    params = admin_page_params(page, per_page)
    rows, total = await web_urls.list_urls(
        session,
        query=q,
        sort=sort,
        viewed=viewed,
        not_viewed_since=not_viewed_since,
        params=params,
    )
    return AdminPage[WebUrlRead].build(
        [WebUrlRead.model_validate(row) for row in rows], total, params
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add a web URL")
async def create_web_url(payload: WebUrlCreate, session: SessionDep) -> WebUrlRead:
    """Add a URL to the backlog. Only http(s) is accepted."""
    parsed = parse_http_url(payload.url)
    if parsed is None:
        raise ValidationError("A valid http(s) URL is required.")
    if len(parsed.domain) > WEB_URL_DOMAIN_MAX:
        raise ValidationError("Domain is too long.")

    if await web_urls.find_by_url(session, parsed.url) is not None:
        raise ConflictError("That URL is already in the list.")

    web_url = await web_urls.create(
        session,
        url=parsed.url,
        domain=parsed.domain,
        title=(payload.title or "").strip()[:WEB_URL_TITLE_MAX],
    )
    logger.info("admin_web_url_create", web_url_id=web_url.id, domain=parsed.domain)
    return WebUrlRead.model_validate(web_url)


@router.post("/mark-all-viewed", summary="Mark every URL viewed")
async def mark_all_viewed(session: SessionDep) -> MarkAllViewedResponse:
    """Clear the backlog in one action."""
    count = await web_urls.mark_all_viewed(session)
    logger.info("admin_web_url_mark_all", count=count)
    return MarkAllViewedResponse(count=count)


@router.post("/{web_url_id}/view", summary="Mark one URL viewed")
async def mark_viewed(web_url_id: int, session: SessionDep) -> WebUrlRead:
    web_url = await web_urls.get_by_id(session, web_url_id)
    if web_url is None:
        raise NotFoundError(f"Web URL not found: {web_url_id}")
    return WebUrlRead.model_validate(await web_urls.mark_viewed(session, web_url))


@router.delete(
    "/{web_url_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a web URL",
)
async def delete_web_url(web_url_id: int, session: SessionDep) -> None:
    """Admin only — `require_manage` restricts every DELETE to admins."""
    web_url = await web_urls.get_by_id(session, web_url_id)
    if web_url is None:
        raise NotFoundError(f"Web URL not found: {web_url_id}")
    await web_urls.delete(session, web_url)
    logger.info("admin_web_url_delete", web_url_id=web_url_id)
