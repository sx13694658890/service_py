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
    # 有权限时：拉取正文用（需带 Bearer）；相对站点根路径
    content_url: str | None = None
    # 有权限时：相对仓库 docs/ 的路径，便于展示或排查
    docs_relpath: str | None = None


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
    content_url: str | None = None
    docs_relpath: str | None = None
    body: str | None = None
