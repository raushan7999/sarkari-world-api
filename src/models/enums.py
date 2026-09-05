"""Domain enums.

Values mirror the Postgres enum types created by Prisma exactly — underscore
form, PascalCase type names. The public API speaks hyphenated slugs; convert
with `src.utils.slugs`.
"""

from enum import StrEnum


class ArticleCategory(StrEnum):
    LATEST_JOB = "latest_job"
    ADMIT_CARD = "admit_card"
    RESULT = "result"
    ANSWER_KEY = "answer_key"
    ADMISSION = "admission"
    SYLLABUS = "syllabus"
    SCHOLARSHIP = "scholarship"
    TENDER = "tender"
    SARKARI_WEBSITE = "sarkari_website"
    SARKARI_MOBILE_APP = "sarkari_mobile_app"
    BLOG = "blog"


class ArticleStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class UserRole(StrEnum):
    USER = "user"
    EDITOR = "editor"
    ADMIN = "admin"
