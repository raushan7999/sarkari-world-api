"""User wire shapes.

Never exposes API-key secrets (`api_key`, `api_key_prefix`, `api_key_hash`) or
session internals. Key state is surfaced as a derived boolean plus non-secret
metadata.
"""

from datetime import datetime, timedelta

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
)

from src.constants.auth import API_KEY_TTL_DAYS
from src.models.enums import UserRole
from src.utils.dates import to_ist_iso


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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def api_key_expires_at(self) -> str | None:
        """Derived from the issue date — the schema has no expiry column."""
        if self.api_key_created_at is None or self.api_key_revoked_at is not None:
            return None
        return to_ist_iso(self.api_key_created_at + timedelta(days=API_KEY_TTL_DAYS))

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


class ApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=100)


class ApiKeyIssued(BaseModel):
    """The one and only time the secret is returned.

    Only a bcrypt hash is stored, so a lost key cannot be recovered — it has
    to be rotated.
    """

    api_key: str
    prefix: str
    name: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None

    @field_serializer("created_at", "expires_at")
    def _ist(self, value: datetime | None) -> str | None:
        return to_ist_iso(value)


class UserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole
