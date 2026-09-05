"""Pagination parameters and envelopes.

Page parameters are *clamped*, never rejected — an out-of-range `page` or
`per_page` silently snaps into range, matching the Node service.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from src.constants.article import (
    ADMIN_PAGE_SIZE,
    ADMIN_PAGE_SIZE_MAX,
    MAX_LIST_PAGE,
    PUBLIC_PAGE_SIZE,
    PUBLIC_PAGE_SIZE_MAX,
)


@dataclass(frozen=True)
class PageParams:
    page: int
    per_page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page

    def total_pages(self, total: int) -> int:
        return max(1, -(-total // self.per_page))  # ceil division


def _clamp(value: int | None, default: int, low: int, high: int) -> int:
    if value is None:
        return default
    return max(low, min(high, value))


def public_page_params(page: int | None, per_page: int | None) -> PageParams:
    return PageParams(
        page=_clamp(page, 1, 1, MAX_LIST_PAGE),
        per_page=_clamp(per_page, PUBLIC_PAGE_SIZE, 1, PUBLIC_PAGE_SIZE_MAX),
    )


def admin_page_params(page: int | None, per_page: int | None) -> PageParams:
    return PageParams(
        page=_clamp(page, 1, 1, MAX_LIST_PAGE),
        per_page=_clamp(per_page, ADMIN_PAGE_SIZE, 1, ADMIN_PAGE_SIZE_MAX),
    )


class PublicPage[T](BaseModel):
    """Public list envelope — carries `has_more`/`next_page` for infinite scroll."""

    items: list[T]
    page: int
    per_page: int
    total: int
    total_pages: int
    has_more: bool
    next_page: int | None

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> PublicPage[T]:
        total_pages = params.total_pages(total)
        has_more = params.page < total_pages
        return cls(
            items=items,
            page=params.page,
            per_page=params.per_page,
            total=total,
            total_pages=total_pages,
            has_more=has_more,
            next_page=params.page + 1 if has_more else None,
        )


class AdminPage[T](BaseModel):
    """Admin list envelope. Deliberately has no `has_more`/`next_page`."""

    items: list[T]
    total: int
    page: int
    per_page: int
    total_pages: int

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> AdminPage[T]:
        return cls(
            items=items,
            total=total,
            page=params.page,
            per_page=params.per_page,
            total_pages=params.total_pages(total),
        )
