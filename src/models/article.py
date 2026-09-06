"""Article ORM model, mapped onto the Prisma-managed `"Article"` table."""

from datetime import datetime
from typing import Any

from sqlalchemy import Enum, FetchedValue, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.enums import ArticleCategory, ArticleStatus


class Article(Base):
    # Quoted PascalCase — SQLAlchemy would otherwise emit `article`.
    __tablename__ = "Article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, default="Untitled")
    description: Mapped[str] = mapped_column(Text, default="")
    slug: Mapped[str] = mapped_column(Text, unique=True)
    category: Mapped[ArticleCategory] = mapped_column(
        Enum(
            ArticleCategory,
            name="ArticleCategory",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ArticleCategory.BLOG,
    )
    html_content: Mapped[str] = mapped_column(Text, default="")
    article_status: Mapped[ArticleStatus] = mapped_column(
        Enum(
            ArticleStatus,
            name="ArticleStatus",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=ArticleStatus.DRAFT,
    )
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # No `onupdate` and no trigger: the write is explicit, in
    # `services.articles.update`, so it can be conditional on something having
    # actually changed. `onupdate` would fire on every flush that touched the
    # row, including one that set every column to the value it already held.
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Loose reference to User.id, which is an Int. Stored as text by the source
    # schema, so there is no ForeignKey here on purpose.
    author_id: Mapped[str | None] = mapped_column(Text, default=None)
    author_name: Mapped[str | None] = mapped_column(Text, default=None)

    instagram_post_url: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    youtube_video_url: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    faq: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    links: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    cover_image_url: Mapped[str | None] = mapped_column(Text, default=None)

    search_keyword: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    meta_title: Mapped[str | None] = mapped_column(String(60), default=None)
    meta_description: Mapped[str | None] = mapped_column(String(160), default=None)

    # GENERATED ALWAYS ... STORED in Postgres, so they refresh on every title
    # change. Mapped so the search query can reference them; never written.
    title_search: Mapped[Any | None] = mapped_column(
        TSVECTOR, server_default=FetchedValue()
    )
    title_normalized: Mapped[str | None] = mapped_column(
        Text, server_default=FetchedValue()
    )
