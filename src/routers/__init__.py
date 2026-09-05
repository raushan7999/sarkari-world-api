"""Router registry.

`health_router` stays unversioned — infrastructure probes should not have to
follow API version bumps. Everything else hangs off `api_router`, which
`create_app` mounts under `settings.api_v1_prefix`.
"""

from src.routers import health, v1

health_router = health.router
api_router = v1.router

__all__ = ["api_router", "health_router"]
