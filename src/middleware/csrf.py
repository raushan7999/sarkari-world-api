"""CSRF protection for cookie-authenticated writes.

Only unsafe methods carrying a session cookie are checked. API-key callers,
mobile apps and server-to-server traffic send no cookie, so the browser's
ambient-credential problem does not apply to them and they are exempt.

`Origin` is preferred; `Referer` is the fallback for the browsers that omit it.
"""

from __future__ import annotations

from urllib.parse import urlparse

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from src.constants.auth import SESSION_COOKIE
from src.schemas.common import ErrorDetail, ErrorResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CsrfMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed_origins = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.allowed_origins:
            await self.app(scope, receive, send)
            return

        if scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        # No session cookie means no ambient credential to abuse.
        if SESSION_COOKIE not in headers.get("cookie", ""):
            await self.app(scope, receive, send)
            return

        origin = headers.get("origin")
        if origin is None and (referer := headers.get("referer")):
            parsed = urlparse(referer)
            origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else None

        if origin not in self.allowed_origins:
            logger.warning("csrf_rejected", origin=origin, path=scope["path"])
            payload = ErrorResponse(
                error=ErrorDetail(
                    code="csrf_rejected",
                    message="Cross-origin request rejected.",
                )
            )
            response = JSONResponse(status_code=403, content=payload.model_dump())
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
