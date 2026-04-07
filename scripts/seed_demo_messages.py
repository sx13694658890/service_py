#!/usr/bin/env python3
"""向指定用户收件箱写入演示用站内通知（供前端联调）。

用法（在项目根目录 server_python 下）：

    PYTHONPATH=src uv run python scripts/seed_demo_messages.py <用户邮箱>

或设置环境变量：

    SEED_DEMO_MESSAGES_EMAIL=user@example.com PYTHONPATH=src uv run python scripts/seed_demo_messages.py

说明：
- 会删除该用户名下 `payload.seed == "frontend_demo"` 的历史演示消息后重新插入，可重复执行。
- 不经过 SSE 广播，仅写库。
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_src = _ROOT / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from sqlalchemy import and_, delete, select

from app.core.db import AsyncSessionLocal
from app.models.message import Message, UserMessage
from app.services.user_repo import get_user_by_email

SEED_TAG = "frontend_demo"


def _demo_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "category": "security",
            "title": "[演示] 密码已成功修改",
            "content": "这是一条安全类未读通知，模拟改密后的站内提醒。",
            "priority": "high",
            "is_read": False,
            "read_at": None,
            "payload": {"seed": SEED_TAG, "kind": "password_changed"},
        },
        {
            "category": "system",
            "title": "[演示] 系统维护预告",
            "content": "本周日凌晨 2:00–4:00 将进行例行维护，期间可能出现短暂不可用。",
            "priority": "normal",
            "is_read": False,
            "read_at": None,
            "payload": {"seed": SEED_TAG, "kind": "maintenance"},
        },
        {
            "category": "business",
            "title": "[演示] 审批已通过",
            "content": "您提交的「示例申请」已审批通过，可前往业务页查看详情。",
            "priority": "normal",
            "is_read": False,
            "read_at": None,
            "payload": {"seed": SEED_TAG, "kind": "approval_ok", "ref": "DEMO-001"},
        },
        {
            "category": "security",
            "title": "[演示] 新设备登录提醒（已读）",
            "content": "此条为已读示例，用于前端样式对比。",
            "priority": "high",
            "is_read": True,
            "read_at": now,
            "payload": {"seed": SEED_TAG, "kind": "new_device"},
        },
        {
            "category": "system",
            "title": "[演示] 低优先级提示",
            "content": "这是一条低优先级未读消息。",
            "priority": "low",
            "is_read": False,
            "read_at": None,
            "payload": {"seed": SEED_TAG, "kind": "hint"},
        },
    ]


async def _clear_demo_for_user(db, user_id: uuid.UUID) -> int:
    seed_key = Message.payload["seed"].as_string()
    ids_result = await db.execute(
        select(Message.id)
        .join(UserMessage, UserMessage.message_id == Message.id)
        .where(
            and_(
                UserMessage.user_id == user_id,
                seed_key == SEED_TAG,
            ),
        ),
    )
    ids = list(ids_result.scalars().all())
    if not ids:
        return 0
    await db.execute(delete(UserMessage).where(UserMessage.message_id.in_(ids)))
    await db.execute(delete(Message).where(Message.id.in_(ids)))
    return len(ids)


async def _insert_demo_for_user(db, user_id: uuid.UUID) -> int:
    n = 0
    for row in _demo_rows():
        msg = Message(
            category=row["category"][:64],
            title=row["title"][:120],
            content=row["content"],
            payload=row["payload"],
            priority=row["priority"],
            created_by=None,
        )
        db.add(msg)
        await db.flush()
        db.add(
            UserMessage(
                user_id=user_id,
                message_id=msg.id,
                is_read=row["is_read"],
                read_at=row["read_at"],
            ),
        )
        n += 1
    return n


async def main() -> None:
    parser = argparse.ArgumentParser(description="写入演示用站内通知")
    parser.add_argument(
        "email",
        nargs="?",
        default=os.environ.get("SEED_DEMO_MESSAGES_EMAIL", "").strip() or None,
        help="目标用户邮箱（与登录账号一致）",
    )
    args = parser.parse_args()
    if not args.email:
        parser.error("请传入邮箱，或设置环境变量 SEED_DEMO_MESSAGES_EMAIL")

    email = str(args.email).strip().lower()

    async with AsyncSessionLocal() as db:
        user = await get_user_by_email(db, email)
        if user is None:
            print(f"未找到用户: {email}，请先注册。", file=sys.stderr)
            sys.exit(1)

        removed = await _clear_demo_for_user(db, user.user_id)
        inserted = await _insert_demo_for_user(db, user.user_id)
        await db.commit()

    print(f"用户 {email}：已移除旧演示 {removed} 条，新插入 {inserted} 条。")


if __name__ == "__main__":
    asyncio.run(main())
