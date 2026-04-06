from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

_lock = asyncio.Lock()
_subscribers: dict[uuid.UUID, list[asyncio.Queue[str]]] = {}


async def subscribe(user_id: uuid.UUID) -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
    async with _lock:
        _subscribers.setdefault(user_id, []).append(q)
    return q


async def unsubscribe(user_id: uuid.UUID, q: asyncio.Queue[str]) -> None:
    async with _lock:
        lst = _subscribers.get(user_id)
        if not lst:
            return
        if q in lst:
            lst.remove(q)
        if not lst:
            del _subscribers[user_id]


async def publish(user_id: uuid.UUID, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False, default=str)
    async with _lock:
        queues = list(_subscribers.get(user_id, []))
    for q in queues:
        try:
            q.put_nowait(line)
        except asyncio.QueueFull:
            pass


def heartbeat_payload() -> dict[str, Any]:
    return {"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()}
