from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str
    category: str | None = None
    score: float | None = None
    tags: list[str] | None = None
    can_view: bool
    created_at: datetime
    updated_at: datetime


class DocListResponse(BaseModel):
    items: list[DocListItemOut]
    total: int = Field(ge=0)


class DocDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    summary: str
    category: str | None = None
    score: float | None = None
    tags: list[str] | None = None
    can_view: bool
    created_at: datetime
    updated_at: datetime
    body: str | None = None
