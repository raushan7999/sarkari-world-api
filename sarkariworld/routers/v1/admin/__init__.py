"""Admin surface.

`require_manage` is declared once on this router, so every route added
underneath inherits it — staff only, and DELETE restricted to admins. That
guarantee is why the guard lives here rather than on each endpoint: a new
route cannot be added without it.
"""

from fastapi import APIRouter, Depends

from sarkariworld.dependencies import require_manage
from sarkariworld.routers.v1.admin import analytics, bookmarks, posts, users, web_urls
from sarkariworld.schemas.common import ADMIN_RESPONSES

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_manage)],
    responses=ADMIN_RESPONSES,
)
router.include_router(analytics.router)
router.include_router(posts.router)
router.include_router(posts.publish_router)
router.include_router(users.router)
router.include_router(web_urls.router)
router.include_router(bookmarks.router)

__all__ = ["router"]
