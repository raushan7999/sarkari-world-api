"""Bookmark ORM model, mapped onto the Prisma-managed `"Bookmark"` table."""

from datetime import datetime

from sqlalchemy import Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Bookmark(Base):
    __tablename__ = "Bookmark"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="Bookmark_user_article_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # No ForeignKey: the source schema declares none, and rows may reference
    # deleted articles. Joins are done explicitly in the service layer.
    user_id: Mapped[int] = mapped_column(Integer)
    article_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
