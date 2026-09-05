"""ASGI middleware, one module per concern.

Registration order matters. Starlette applies middleware outermost-last, so
`RequestContextMiddleware` is added last to make it the outermost layer: its
request id is bound before anything else can log.
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.config import Settings
from src.middleware.csrf import CsrfMiddleware
from src.middleware.request_context import RequestContextMiddleware

__all__ = ["CsrfMiddleware", "RequestContextMiddleware", "setup_middleware"]


def setup_middleware(app: FastAPI, config: Settings) -> None:
    """Attach every middleware the application uses."""
    # The authenticated surface accepts the union of both allow-lists; the
    # public read-only surface only needs the public one.
    allowed_origins = sorted({*config.cors_origins, *config.admin_cors_origins})

    app.add_middleware(CsrfMiddleware, allowed_origins=allowed_origins)

    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=[
                "Content-Type",
                "Authorization",
                "X-API-Key",
                "X-Request-ID",
            ],
            expose_headers=["X-Request-ID"],
        )

    app.add_middleware(RequestContextMiddleware)
