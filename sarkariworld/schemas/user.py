"""User wire shapes.

Never exposes API-key secrets (`api_key`, `api_key_prefix`, `api_key_hash`) or
session internals. Key state is surfaced as a derived boolean plus non-secret
metadata.
"""

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
)

from sarkariworld.models.enums import UserRole
from sarkariworld.utils.dates import to_ist_iso


class AdminUser(BaseModel):
    """Admin-facing user detail."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: UserRole
    auth_provider: str
    picture_url: str | None = None
    api_key_name: str | None = None
    api_key_created_at: datetime | None = None
    api_key_last_used_at: datetime | None = None
    api_key_revoked_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Excluded from the response; only the derived flag below is exposed.
    api_key_prefix: str | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_prefix) and self.api_key_revoked_at is None

    @field_serializer(
        "api_key_created_at",
        "api_key_last_used_at",
        "api_key_revoked_at",
        "last_login_at",
        "created_at",
        "updated_at",
    )
    def _ist(self, value: datetime | None) -> str | None:
        return to_ist_iso(value)


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole
