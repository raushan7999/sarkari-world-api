"""Bookmark wire shapes."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from src.utils.dates import to_ist_iso


class BookmarkedArticle(BaseModel):
    """The article a bookmark points at, when it still exists."""

    slug: str
    title: str
    category: str


class BookmarkItem(BaseModel):
    article_id: int
    created_at: datetime | None = None
    # Null when the article was deleted or unpublished after bookmarking.
    article: BookmarkedArticle | None = None

    @field_serializer("created_at")
    def _ist(self, value: datetime | None) -> str | None:
        # The source returns this one field as raw UTC, unlike every other
        # endpoint. Emitting IST here keeps the contract consistent.
        return to_ist_iso(value)


class BookmarkToggleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=200)


class BookmarkToggleResponse(BaseModel):
    slug: str
    bookmarked: bool


class BookmarkRow(BaseModel):
    """Raw row for the admin listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    article_id: int
    created_at: datetime | None = None

    @field_serializer("created_at")
    def _ist(self, value: datetime | None) -> str | None:
        return to_ist_iso(value)


class BookmarkTotals(BaseModel):
    bookmarks: int
    users: int
    articles: int


class TopArticle(BaseModel):
    article_id: int
    count: int
    slug: str | None = None
    title: str | None = None
    # Present so a client can build the article's public URL, which is
    # /{category}/{slug}. Null when the article has since been deleted.
    category: str | None = None

    @field_validator("category")
    @classmethod
    def _slugify_category(cls, value: str | None) -> str | None:
        """Emit the hyphenated public slug, matching every other endpoint."""
        return value.replace("_", "-") if value else value


class TopUser(BaseModel):
    user_id: int
    count: int
    email: str | None = None


class RecentBookmark(BaseModel):
    user_id: int
    article_id: int
    created_at: datetime | None = None

    @field_serializer("created_at")
    def _ist(self, value: datetime | None) -> str | None:
        return to_ist_iso(value)


class TimelinePoint(BaseModel):
    day: str
    count: int


class BookmarkOverview(BaseModel):
    totals: BookmarkTotals
    top_articles: list[TopArticle]
    top_users: list[TopUser]
    recent: list[RecentBookmark]
    timeline: list[TimelinePoint]
    window_days: int
