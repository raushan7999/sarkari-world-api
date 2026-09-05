"""ASGI middleware."""

from __future__ import annotations

import time
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.constants import REQUEST_ID_HEADER
from src.utils.logger import (
    bind_request_context,
    clear_request_context,
    get_logger,
)

logger = get_logger(__name__)


class RequestContextMiddleware:
    """Assign a request id, bind it to the log context, log one line per request.

    Written as raw ASGI rather than `BaseHTTPMiddleware`, which buffers the
    response and interferes with streaming responses and background tasks.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(REQUEST_ID_HEADER) or uuid4().hex

        clear_request_context()
        bind_request_context(
            request_id=request_id,
            method=scope["method"],
            path=scope["path"],
        )

        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("request_failed", duration_ms=self._elapsed_ms(started))
            raise
        else:
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_ms=self._elapsed_ms(started),
            )
        finally:
            clear_request_context()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)
