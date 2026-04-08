from __future__ import annotations

import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str = Field(description="文档标题")
    summary: str = Field(description="简单描述（摘要）")
    category: str | None = None
    score: float | None = None
    tags: list[str] | None = None
    can_view: bool
    created_at: datetime = Field(description="创建/上传时间")
    updated_at: datetime
    # 有权限时：拉取正文用（需带 Bearer）；相对站点根路径
    content_url: str | None = None
    # 有权限时：相对仓库 docs/ 的路径，便于展示或排查
    docs_relpath: str | None = None
    content_source: Literal["repo", "upload", "inline"] = "inline"
    # 当前用户为 admin 时可调用删除接口（仓库文档仅删库记录，不删 git 内文件）
    can_delete: bool = False
    # 上传类文档：公开静态 URL（无需鉴权；有查看权限时返回，与 content_url 二选一或并存）
    static_url: str | None = None


class DocListResponse(BaseModel):
    items: list[DocListItemOut]
    total: int = Field(ge=0)


class DocDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str = Field(description="文档标题")
    summary: str = Field(description="简单描述（摘要）")
    category: str | None = None
    score: float | None = None
    tags: list[str] | None = None
    can_view: bool
    created_at: datetime = Field(description="创建/上传时间")
    updated_at: datetime
    content_url: str | None = None
    docs_relpath: str | None = None
    content_source: Literal["repo", "upload", "inline"] = "inline"
    body: str | None = None
    can_delete: bool = False
    static_url: str | None = None


class DocUploadResponse(BaseModel):
    id: uuid.UUID
    title: str = Field(description="文档标题")
    summary: str = Field(description="简单描述（入库后的摘要）")
    category: str | None = None
    created_at: datetime = Field(description="上传时间")
    updated_at: datetime
    static_url: str | None = Field(default=None, description="公开静态地址，可直接浏览器访问")
