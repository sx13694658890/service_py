from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MessageItemOut(BaseModel):
    id: UUID
    category: str
    title: str
    content: str
    payload: dict[str, Any] | None = None
    priority: Literal["low", "normal", "high"] = "normal"
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageItemOut]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class ReadAllResponse(BaseModel):
    updated: int


class MessageOkResponse(BaseModel):
    message: str = "ok"
