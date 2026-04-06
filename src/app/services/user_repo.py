from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    normalized = str(email).strip().lower()
    result = await db.execute(select(User).where(User.email == normalized))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.user_id == user_id))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, *, limit: int = 50, offset: int = 0) -> list[User]:
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset),
    )
    return list(result.scalars().all())


async def delete_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> bool:
    result = await db.execute(delete(User).where(User.user_id == user_id))
    await db.commit()
    return (result.rowcount or 0) > 0


async def update_user_password(db: AsyncSession, user: User, new_plain_password: str) -> None:
    user.password_hash = hash_password(new_plain_password)
    await db.commit()
