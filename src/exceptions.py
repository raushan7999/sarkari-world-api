"""Application exceptions and the handlers that turn them into responses."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.schemas.common import ErrorDetail, ErrorResponse
from src.utils.logger import get_logger, get_request_id

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for errors this application raises deliberately."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        self.message = message or self.message
        self.code = code or self.code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Resource already exists"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    message = "Not authenticated"


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Every error leaves through here, so the shape can never drift."""
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=get_request_id())
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """Give every error path the same JSON shape."""

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("app_error", code=exc.code, message=exc.message)
        return _error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "Request validation failed",
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception")
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "Internal server error",
        )
