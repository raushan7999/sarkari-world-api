"""Version 1 of the API.

Mount order matters: `public.router` owns `/{category}`, a parameterised path
that would shadow any literal prefix declared after it. Everything else is
registered first.
"""

from fastapi import APIRouter

from src.routers.v1 import account, admin, auth, public

router = APIRouter()
router.include_router(auth.router)
router.include_router(account.router)
router.include_router(admin.router)
# Last: this router's `/{category}` catch-all would swallow the prefixes above.
router.include_router(public.router)

__all__ = ["router"]
