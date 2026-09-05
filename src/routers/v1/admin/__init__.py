"""Admin endpoints.

The `require_admin` dependency is declared once on this router, so every route
added under it inherits the guard — that is the main reason to group by
audience rather than scattering `Depends(require_admin)` over each handler.
"""

from fastapi import APIRouter, Depends

from src.dependencies import require_admin
from src.routers.v1.admin import users

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
router.include_router(users.router)

__all__ = ["router"]
