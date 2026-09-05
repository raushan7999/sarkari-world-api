"""Web URL wire shapes."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from src.constants.article import WEB_URL_MAX, WEB_URL_TITLE_MAX
from src.utils.dates import to_ist_iso


class WebUrlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    domain: str
    last_viewed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("last_viewed_at", "created_at", "updated_at")
    def _ist(self, value: datetime | None) -> str | None:
        return to_ist_iso(value)


class WebUrlCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=WEB_URL_MAX)
    title: str | None = Field(default=None, max_length=WEB_URL_TITLE_MAX)


class MarkAllViewedResponse(BaseModel):
    count: int
