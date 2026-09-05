from pydantic import BaseModel, Field


class FieldError(BaseModel):
    """One failed field, so a client can highlight the offending input."""

    path: str = Field(examples=["faq.0.question"])
    message: str = Field(examples=["String should have at least 1 character"])


class ErrorDetail(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["Resource not found"])
    request_id: str | None = None
    details: list[FieldError] | None = None


class ErrorResponse(BaseModel):
    """Envelope returned for every non-2xx response."""

    error: ErrorDetail
