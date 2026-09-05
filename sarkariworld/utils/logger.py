"""Structured logging built on structlog.

`configure_logging()` runs once at startup and routes *both* structlog and the
standard library (uvicorn, sqlalchemy, asyncpg) through one processor chain, so
every line on stdout has the same shape.

    from sarkariworld.utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("job_created", job_id=42)

`logger.bind(...)` attaches values to that logger; `bind_request_context(...)`
binds to the current async task via contextvars, so every line emitted while
handling a request carries them regardless of which module wrote it.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

_configured = False

# Uvicorn installs its own handlers and sets propagate=False; clear them so its
# records reach the root handler configured below.
_STDLIB_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine")


def configure_logging(
    *, level: str = "INFO", json_logs: bool = True, force: bool = False
) -> None:
    """Configure structlog and the stdlib logging bridge. Idempotent."""
    global _configured
    if _configured and not force:
        return

    level = level.upper()

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            # Hands the event dict to ProcessorFormatter below.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # Applied to records from the standard library only.
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in _STDLIB_LOGGERS:
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = True

    _configured = True


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a logger, optionally pre-bound with `initial_values`."""
    logger = structlog.stdlib.get_logger(name)
    return logger.bind(**initial_values) if initial_values else logger


def bind_request_context(**values: Any) -> None:
    """Bind values to the current async task; every logger picks them up."""
    structlog.contextvars.bind_contextvars(**values)


def clear_request_context() -> None:
    """Drop everything bound by `bind_request_context`."""
    structlog.contextvars.clear_contextvars()


def get_request_id() -> str | None:
    """Return the request id bound to the current context, if any."""
    value = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None
