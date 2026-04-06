from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, UserMessage
from app.services import message_hub


def _priority(p: str) -> str:
    p = (p or "normal").strip().lower()
    if p not in ("low", "normal", "high"):
        return "normal"
    return p


async def create_message_and_dispatch(
    db: AsyncSession,
    *,
    user_ids: list[uuid.UUID],
    category: str,
    title: str,
    content: str,
    payload: dict | None = None,
    priority: str = "normal",
    created_by: uuid.UUID | None = None,
) -> uuid.UUID:
    msg = Message(
        category=category[:64],
        title=title[:120],
        content=content,
        payload=payload,
        priority=_priority(priority),
        created_by=created_by,
    )
    db.add(msg)
    await db.flush()

    for uid in {u for u in user_ids}:
        db.add(
            UserMessage(
                user_id=uid,
                message_id=msg.id,
            ),
        )
    await db.commit()
    await db.refresh(msg)

    item = notification_item_from_message(msg, is_read=False, read_at=None)
    for uid in {u for u in user_ids}:
        await message_hub.publish(uid, {"type": "notification", "item": item})
        n = await count_unread_for_user(db, uid)
        await message_hub.publish(uid, {"type": "unread_count", "unread_count": n})

    return msg.id


def notification_item_from_message(
    msg: Message,
    *,
    is_read: bool,
    read_at: datetime | None,
) -> dict:
    return {
        "id": str(msg.id),
        "category": msg.category,
        "title": msg.title,
        "content": msg.content,
        "payload": msg.payload,
        "priority": msg.priority,
        "is_read": is_read,
        "read_at": read_at.isoformat() if read_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


async def count_unread_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    q = await db.execute(
        select(func.count())
        .select_from(UserMessage)
        .where(
            and_(
                UserMessage.user_id == user_id,
                UserMessage.is_deleted.is_(False),
                UserMessage.is_read.is_(False),
            ),
        ),
    )
    return int(q.scalar_one() or 0)


async def count_inbox_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    only_unread: bool,
) -> int:
    conds = [
        UserMessage.user_id == user_id,
        UserMessage.is_deleted.is_(False),
    ]
    if only_unread:
        conds.append(UserMessage.is_read.is_(False))
    q = await db.execute(select(func.count()).select_from(UserMessage).where(and_(*conds)))
    return int(q.scalar_one() or 0)


async def list_inbox_page(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    only_unread: bool,
) -> list[tuple[Message, UserMessage]]:
    conds = [
        UserMessage.user_id == user_id,
        UserMessage.is_deleted.is_(False),
    ]
    if only_unread:
        conds.append(UserMessage.is_read.is_(False))

    stmt = (
        select(Message, UserMessage)
        .join(UserMessage, UserMessage.message_id == Message.id)
        .where(and_(*conds))
        .order_by(UserMessage.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.all())


async def mark_message_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(UserMessage).where(
            and_(
                UserMessage.user_id == user_id,
                UserMessage.message_id == message_id,
                UserMessage.is_deleted.is_(False),
            ),
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    if not row.is_read:
        row.is_read = True
        row.read_at = datetime.now(timezone.utc)
        await db.commit()
        n = await count_unread_for_user(db, user_id)
        await message_hub.publish(user_id, {"type": "unread_count", "unread_count": n})
    return True


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    stmt = (
        update(UserMessage)
        .where(
            and_(
                UserMessage.user_id == user_id,
                UserMessage.is_deleted.is_(False),
                UserMessage.is_read.is_(False),
            ),
        )
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    result = await db.execute(stmt)
    await db.commit()
    updated = int(result.rowcount or 0)
    await message_hub.publish(
        user_id,
        {"type": "unread_count", "unread_count": await count_unread_for_user(db, user_id)},
    )
    return updated


async def soft_delete_user_message(
    db: AsyncSession,
    user_id: uuid.UUID,
    message_id: uuid.UUID,
) -> bool:
    result = await db.execute(
        select(UserMessage).where(
            and_(
                UserMessage.user_id == user_id,
                UserMessage.message_id == message_id,
                UserMessage.is_deleted.is_(False),
            ),
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    row.is_deleted = True
    await db.commit()
    await message_hub.publish(
        user_id,
        {"type": "unread_count", "unread_count": await count_unread_for_user(db, user_id)},
    )
    return True
