"""ASGI middleware, one module per concern.

Registration order matters — `setup_middleware` adds them outermost-first, so
`RequestContextMiddleware` wraps everything else and its request id is bound
before any other middleware logs.
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.config import Settings
from src.middleware.request_context import RequestContextMiddleware

__all__ = ["RequestContextMiddleware", "setup_middleware"]


def setup_middleware(app: FastAPI, config: Settings) -> None:
    """Attach every middleware the application uses."""
    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(RequestContextMiddleware)
