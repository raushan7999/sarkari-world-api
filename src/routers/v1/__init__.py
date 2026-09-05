"""Version 1 of the API.

Routers are registered here; `src.routers` re-exports this as `api_router` and
`create_app` mounts it under `settings.api_v1_prefix`.
"""

from fastapi import APIRouter

from src.routers.v1 import auth

router = APIRouter()
router.include_router(auth.router)

__all__ = ["router"]
