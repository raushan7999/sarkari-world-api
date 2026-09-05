from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["Resource not found"])
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Envelope returned for every non-2xx response."""

    error: ErrorDetail
