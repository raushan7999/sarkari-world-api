from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    environment: str


class DatabaseHealthResponse(BaseModel):
    database: Literal["up", "down"]
    detail: str | None = None
