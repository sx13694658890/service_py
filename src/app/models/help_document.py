from __future__ import annotations

import uuid
from datetime import datetime
from sqlalchemy import DateTime, Float, String, Text, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HelpDocument(Base):
    """文档中心列表/详情用内容（与知识库检索模块独立）。"""

    __tablename__ = "help_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    required_role_codes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @staticmethod
    def can_user_view(required_role_codes: list[str] | None, user_roles: list[str]) -> bool:
        if not required_role_codes:
            return True
        need = {str(c) for c in required_role_codes}
        if not need:
            return True
        return bool(need.intersection(user_roles))
