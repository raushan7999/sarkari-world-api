"""Article wire shapes.

These own the response contract. Never return an ORM row directly — a column
added by a future migration would leak into every response.

Three tiers, each widening the one above:
  ArticleCard    list endpoints
  PublicArticle  + body and rich fields, published rows only
  AdminArticle   + workflow and authorship fields
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from src.constants.article import (
    DESCRIPTION_MAX,
    HTML_CONTENT_MAX,
    SLUG_MAX,
    TITLE_MAX,
)
from src.models.article import Article
from src.models.enums import ArticleStatus
from src.utils.dates import to_ist_iso
from src.utils.slugs import category_enum_to_slug

CategorySlug = str


class ArticleCard(BaseModel):
    """Compact shape for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    title: str
    description: str
    category: CategorySlug
    cover_image_url: str | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _slugify_category(cls, data: Any) -> Any:
        """Emit the hyphenated public slug rather than the underscore enum."""
        if isinstance(data, Article):
            return {
                **{
                    field: getattr(data, field)
                    for field in cls.model_fields
                    if field != "category"
                },
                "category": category_enum_to_slug(data.category),
            }
        if isinstance(data, dict) and data.get("category"):
            return {**data, "category": str(data["category"]).replace("_", "-")}
        return data

    @field_serializer("published_at", "created_at", "updated_at")
    def _ist(self, value: datetime | None) -> str | None:
        """Every timestamp leaves as IST with an explicit +05:30 offset."""
        return to_ist_iso(value)


class PublicArticle(ArticleCard):
    """Full detail for a published article."""

    html_content: str
    search_keyword: list[str] = Field(default_factory=list)
    instagram_post_url: list[Any] = Field(default_factory=list)
    youtube_video_url: list[Any] = Field(default_factory=list)
    faq: list[Any] = Field(default_factory=list)
    links: list[Any] = Field(default_factory=list)
    author_name: str | None = None


class AdminArticle(PublicArticle):
    """Adds the workflow and authorship fields hidden from the public."""

    article_status: ArticleStatus
    author_id: str | None = None


# --- Request bodies ----------------------------------------------------------


class FaqItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=1500)


class LinkItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cta: str | None = Field(default=None, max_length=60)
    url: str = Field(max_length=2048)


class ArticleBase(BaseModel):
    """Fields shared by create, update and publish.

    `extra="forbid"` rejects unknown keys — the anti mass-assignment guard.
    Values that survive are still normalised by `utils.article_payload` before
    they reach the database.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=TITLE_MAX)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    category: CategorySlug | None = None
    meta_title: str | None = None
    meta_description: str | None = None
    search_keyword: list[str] | str | None = None
    links: list[LinkItem] | None = None
    faq: list[FaqItem] | None = None
    instagram_post_url: list[Any] | None = None
    youtube_video_url: list[Any] | None = None
    cover_image_url: str | None = None
    published_at: datetime | None = None


class ArticleCreate(ArticleBase):
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    slug: str = Field(min_length=1, max_length=SLUG_MAX, pattern=r"^[a-z0-9-]+$")
    html_content: str | None = Field(default=None, max_length=HTML_CONTENT_MAX)
    article_status: ArticleStatus | None = None


class ArticleUpdate(ArticleBase):
    """Every field optional — the body is merged over the existing row."""

    slug: str | None = Field(
        default=None, min_length=1, max_length=SLUG_MAX, pattern=r"^[a-z0-9-]+$"
    )
    html_content: str | None = Field(default=None, max_length=HTML_CONTENT_MAX)
    article_status: ArticleStatus | None = None


class ArticlePublish(ArticleBase):
    """Server-to-server markdown ingest.

    Deliberately accepts neither `html_content` nor `article_status`: the body
    is rendered from markdown and the row is always created as a draft.
    """

    title: str = Field(min_length=1, max_length=TITLE_MAX)
    slug: str = Field(min_length=1, max_length=SLUG_MAX, pattern=r"^[a-z0-9-]+$")
    content: str | None = Field(default=None, max_length=HTML_CONTENT_MAX)


class ArticleStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ArticleStatus


class CategoryItem(BaseModel):
    slug: str
    name: str


class SearchResponse(BaseModel):
    query: str
    total: int
    articles: list[ArticleCard]


class CategoryPage(BaseModel):
    """Public category listing. Mirrors the source envelope key-for-key."""

    category: str
    page: int
    per_page: int
    total: int
    total_pages: int
    has_more: bool
    next_page: int | None
    articles: list[ArticleCard]


class DashboardResponse(BaseModel):
    """The console's KPI row.

    Every field is a cheap counter over one table, so this stays the fast
    first paint; the breakdowns below are separate endpoints precisely so a
    slow chart cannot hold up the numbers.
    """

    total: int
    published: int
    draft: int
    archived: int
    # A subset of `published`, not a fourth status: published but dated
    # forward, so the public site has not surfaced it yet.
    scheduled: int
    # Drafts untouched for `stale_draft_days` — backlog, not work in progress.
    stale_drafts: int
    created_recently: int
    published_recently: int
    # The windows the two `*_recently` counters cover, so the client can label
    # them without hard-coding a number the server might change.
    activity_window_days: int
    stale_draft_days: int


class CategoryBreakdownRow(BaseModel):
    """One category's article counts, split by workflow status."""

    category: CategorySlug
    total: int
    published: int
    draft: int
    archived: int


class TimelinePoint(BaseModel):
    """One day on the publishing timeline. Days with no activity are present
    with zeroes rather than absent, so a chart draws a continuous axis."""

    day: str
    created: int
    published: int


class MetaLimits(BaseModel):
    faq_max_items: int
    faq_max_question_len: int
    faq_max_answer_len: int
    meta_title_max_len: int
    meta_description_max_len: int
    search_keyword_item_max_len: int
    search_keyword_max_items: int
    article_links_max: int
    article_link_cta_max: int
    article_link_url_max: int
    url_title_list_max: int
    url_title_title_max: int
    cover_image_url_max: int


class MetaResponse(BaseModel):
    """Enums and field limits, so the admin form can validate client-side."""

    categories: list[str]
    article_statuses: list[str]
    user_roles: list[str]
    auth_providers: list[str]
    limits: MetaLimits


class DeletedResponse(BaseModel):
    deleted: Literal[True] = True

    @classmethod
    def ok(cls) -> Self:
        return cls()
