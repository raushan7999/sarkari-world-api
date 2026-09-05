"""Version 1 of the API.

Add a new area by creating a package beside `admin` and `users`, then
including its router here. Nothing else in the app needs to change.
"""

from fastapi import APIRouter

from src.routers.v1 import admin, users

router = APIRouter()
router.include_router(admin.router)
router.include_router(users.router)

__all__ = ["router"]
