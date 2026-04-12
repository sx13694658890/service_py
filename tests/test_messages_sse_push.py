"""验证站内通知推送链路：message_hub.subscribe + publish（内存 / Redis 逻辑一致）。

说明：``httpx.ASGITransport`` 对长连接 SSE 与 ASGI 的配合在部分版本下会阻塞，
完整浏览器/``curl -N`` 对运行中服务的验证请用 ``scripts/messages_sse_smoke.py``。
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from app.services import message_hub


@pytest.mark.anyio
async def test_message_hub_publish_reaches_subscriber_queue() -> None:
    """subscribe → publish 后应立刻收到同一 JSON 行（与 SSE 内部队列同源）。"""
    uid = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    q = await message_hub.subscribe(uid)
    try:
        await message_hub.publish(uid, {"type": "unread_count", "unread_count": 77})
        line = await asyncio.wait_for(q.get(), timeout=2.0)
        j = json.loads(line)
        assert j["type"] == "unread_count"
        assert j["unread_count"] == 77
    finally:
        await message_hub.unsubscribe(uid, q)


@pytest.mark.anyio
async def test_message_hub_notification_payload_roundtrip() -> None:
    uid = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    q = await message_hub.subscribe(uid)
    try:
        item = {"id": str(uuid.uuid4()), "title": "推送标题", "category": "system"}
        await message_hub.publish(uid, {"type": "notification", "item": item})
        line = await asyncio.wait_for(q.get(), timeout=2.0)
        j = json.loads(line)
        assert j["type"] == "notification"
        assert j["item"]["title"] == "推送标题"
    finally:
        await message_hub.unsubscribe(uid, q)
