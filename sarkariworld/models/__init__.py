"""SQLAlchemy ORM models, mapped onto the existing Prisma-managed tables."""

from sarkariworld.db.base import Base
from sarkariworld.models.article import Article
from sarkariworld.models.bookmark import Bookmark
from sarkariworld.models.enums import ArticleCategory, ArticleStatus, UserRole
from sarkariworld.models.user import User
from sarkariworld.models.web_url import WebUrl

__all__ = [
    "Article",
    "ArticleCategory",
    "ArticleStatus",
    "Base",
    "Bookmark",
    "User",
    "UserRole",
    "WebUrl",
]
