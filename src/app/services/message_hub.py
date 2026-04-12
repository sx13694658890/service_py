"""站内通知实时分发：优先 Redis Pub/Sub（跨 Worker），无 Redis 时回退进程内队列。

投递侧同时写入 Redis Stream ``msg:bus``（轻量消息总线，便于观测与未来消费扩展）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_lock = asyncio.Lock()
_subscribers: dict[uuid.UUID, list[asyncio.Queue[str]]] = {}

_redis: redis.Redis | None = None
_MSG_BUS_STREAM = "msg:bus"
# 无业务消息时周期性 heartbeat，避免代理/客户端长时间无首包；亦便于自动化测试在数秒内读到首块。
_SSE_IDLE_SEC = 5.0


def notify_channel(user_id: uuid.UUID) -> str:
    return f"msg:notify:{user_id}"


def heartbeat_payload() -> dict[str, Any]:
    return {"type": "heartbeat", "ts": datetime.now(timezone.utc).isoformat()}


def redis_enabled() -> bool:
    return _redis is not None


async def init_redis(url: str | None) -> None:
    """应用启动时调用；``url`` 为空或连接失败时回退内存模式。"""
    global _redis
    async with _lock:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
            _redis = None
        if not (url or "").strip():
            logger.info("REDIS_URL 未配置，站内通知使用进程内 Pub/Sub（仅单进程内 SSE 实时）")
            return
        try:
            client = redis.from_url(
                url.strip(),
                decode_responses=True,
                socket_connect_timeout=3.0,
            )
            await client.ping()
            _redis = client
            logger.info("站内通知已接入 Redis（Pub/Sub + Stream msg:bus）")
        except Exception as e:
            logger.warning("Redis 不可用，回退进程内消息总线: %s", e)
            _redis = None


async def close_redis() -> None:
    global _redis
    async with _lock:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
            _redis = None


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
    r = _redis
    if r is not None:
        try:
            await r.publish(notify_channel(user_id), line)
            await r.xadd(
                _MSG_BUS_STREAM,
                {"user_id": str(user_id), "data": line},
                maxlen=8000,
                approximate=True,
            )
        except Exception:
            logger.exception("Redis publish 失败，尝试进程内投递 user_id=%s", user_id)
    async with _lock:
        queues = list(_subscribers.get(user_id, []))
    for q in queues:
        try:
            q.put_nowait(line)
        except asyncio.QueueFull:
            pass


async def iter_sse_payload_lines(user_id: uuid.UUID):
    """异步迭代 SSE 的 ``data:`` 后单行 JSON 文本（不含 ``data:`` 前缀与换行）。"""
    if _redis is not None:
        async for line in _iter_redis_sse(user_id):
            yield line
        return
    q = await subscribe(user_id)
    try:
        while True:
            try:
                line = await asyncio.wait_for(q.get(), timeout=_SSE_IDLE_SEC)
                yield line
            except asyncio.TimeoutError:
                yield json.dumps(heartbeat_payload(), ensure_ascii=False)
    finally:
        await unsubscribe(user_id, q)


async def _iter_redis_sse(user_id: uuid.UUID):
    assert _redis is not None
    pubsub = _redis.pubsub()
    ch = notify_channel(user_id)
    await pubsub.subscribe(ch)
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=_SSE_IDLE_SEC)
            if msg is None:
                yield json.dumps(heartbeat_payload(), ensure_ascii=False)
                continue
            if msg.get("type") != "message":
                continue
            data = msg.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            if data:
                yield data
    finally:
        try:
            await pubsub.unsubscribe(ch)
        except Exception:
            pass
        try:
            await pubsub.aclose()
        except Exception:
            pass
