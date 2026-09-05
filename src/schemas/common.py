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


# Reusable OpenAPI response documentation. Without these, the generated spec
# advertises only 200 and FastAPI's own HTTPValidationError, neither of which
# matches what the handlers in `src.exceptions` actually return.
_ERROR = {"model": ErrorResponse}

VALIDATION_RESPONSE: dict[int | str, dict[str, object]] = {
    422: {**_ERROR, "description": "Request validation failed"},
}

AUTH_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {**_ERROR, "description": "Not authenticated"},
    403: {**_ERROR, "description": "Insufficient permissions"},
    **VALIDATION_RESPONSE,
}

NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    404: {**_ERROR, "description": "Resource not found"},
}

PUBLIC_RESPONSES: dict[int | str, dict[str, object]] = {
    **NOT_FOUND_RESPONSE,
    **VALIDATION_RESPONSE,
}

ADMIN_RESPONSES: dict[int | str, dict[str, object]] = {
    **AUTH_RESPONSES,
    **NOT_FOUND_RESPONSE,
    409: {**_ERROR, "description": "Conflicts with an existing resource"},
}
