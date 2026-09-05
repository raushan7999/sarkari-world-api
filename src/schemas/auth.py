"""Authentication request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import UserRole


class OAuthSignInRequest(BaseModel):
    """Body for `POST /v1/auth/{provider}`."""

    # extra="forbid" is the anti mass-assignment guard on every request body.
    model_config = ConfigDict(extra="forbid")

    credential: str = Field(min_length=1, max_length=8192)


class AuthPrincipal(BaseModel):
    """The signed-in caller, as returned by `/v1/auth/me`."""

    id: str
    email: str
    name: str | None = None
    picture: str | None = None
    role: UserRole
    via: str


class SignInResponse(BaseModel):
    token: str
    user: AuthPrincipal


class ProvidersResponse(BaseModel):
    providers: list[str]
