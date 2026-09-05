"""Web URL triage queries.

A curated backlog of URLs an editor works through. `last_viewed_at` is the
triage marker: never-viewed rows sort first so nothing sits unseen.
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sarkariworld.models.web_url import WebUrl
from sarkariworld.schemas.pagination import PageParams
from sarkariworld.utils.dates import now_ist


async def list_urls(
    session: AsyncSession,
    *,
    query: str | None,
    sort: str,
    params: PageParams,
) -> tuple[list[WebUrl], int]:
    """One page of the triage list.

    Default order is `oldest`: unviewed rows (NULL `last_viewed_at`) first,
    then least-recently viewed. `domain` and `id` break ties so paging is
    stable.
    """
    statement = select(WebUrl)
    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(
            or_(
                WebUrl.url.ilike(pattern),
                WebUrl.title.ilike(pattern),
                WebUrl.domain.ilike(pattern),
            )
        )

    if sort == "newest":
        order = WebUrl.last_viewed_at.desc().nulls_last()
    else:
        order = WebUrl.last_viewed_at.asc().nulls_first()

    total = await session.scalar(select(func.count()).select_from(statement.subquery()))
    result = await session.execute(
        statement.order_by(order, WebUrl.domain.asc(), WebUrl.id.asc())
        .limit(params.per_page)
        .offset(params.offset)
    )
    return list(result.scalars().all()), int(total or 0)


async def get_by_id(session: AsyncSession, url_id: int) -> WebUrl | None:
    return await session.get(WebUrl, url_id)


async def find_by_url(session: AsyncSession, url: str) -> WebUrl | None:
    result = await session.execute(select(WebUrl).where(WebUrl.url == url))
    return result.scalar_one_or_none()


async def create(session: AsyncSession, *, url: str, domain: str, title: str) -> WebUrl:
    web_url = WebUrl(url=url, domain=domain, title=title)
    session.add(web_url)
    await session.commit()
    await session.refresh(web_url)
    return web_url


async def mark_viewed(session: AsyncSession, web_url: WebUrl) -> WebUrl:
    web_url.last_viewed_at = now_ist()
    await session.commit()
    await session.refresh(web_url)
    return web_url


async def mark_all_viewed(session: AsyncSession) -> int:
    """Stamp every row as viewed. Returns how many were updated."""
    stamped = now_ist()
    result = cast(
        "CursorResult[Any]",
        await session.execute(update(WebUrl).values(last_viewed_at=stamped)),
    )
    await session.commit()
    return int(result.rowcount)


async def delete(session: AsyncSession, web_url: WebUrl) -> None:
    await session.delete(web_url)
    await session.commit()
