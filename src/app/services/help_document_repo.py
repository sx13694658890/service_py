from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.help_document import HelpDocument


def _apply_category(stmt, category: str | None):
    if category is None:
        return stmt
    c = category.strip()
    if not c:
        return stmt
    return stmt.where(HelpDocument.category == c)


async def count_help_documents(
    db: AsyncSession,
    *,
    keyword: str | None,
    category: str | None,
) -> int:
    stmt = select(func.count()).select_from(HelpDocument)
    stmt = _apply_category(stmt, category)
    stmt = _apply_keyword(stmt, keyword)
    r = await db.execute(stmt)
    return int(r.scalar_one())


def _apply_keyword(stmt, keyword: str | None):
    if keyword is None:
        return stmt
    k = keyword.strip()
    if not k:
        return stmt
    pattern = f"%{k}%"
    return stmt.where(
        or_(
            HelpDocument.title.ilike(pattern),
            HelpDocument.summary.ilike(pattern),
        )
    )


async def list_help_documents_page(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
    keyword: str | None,
    category: str | None,
) -> list[HelpDocument]:
    stmt = select(HelpDocument).order_by(HelpDocument.updated_at.desc())
    stmt = _apply_category(stmt, category)
    stmt = _apply_keyword(stmt, keyword)
    stmt = stmt.offset(offset).limit(limit)
    r = await db.execute(stmt)
    return list(r.scalars().all())


async def get_help_document_by_id(db: AsyncSession, doc_id: uuid.UUID) -> HelpDocument | None:
    r = await db.execute(select(HelpDocument).where(HelpDocument.id == doc_id))
    return r.scalar_one_or_none()
