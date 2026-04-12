from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.models.message import Message, UserMessage
from app.schemas.messages import (
    MessageItemOut,
    MessageListResponse,
    MessageOkResponse,
    ReadAllResponse,
    UnreadCountResponse,
)
from app.services import message_hub
from app.services.message_repo import (
    count_inbox_for_user,
    count_unread_for_user,
    list_inbox_page,
    mark_all_read,
    mark_message_read,
    soft_delete_user_message,
)


router = APIRouter(prefix="/messages", tags=["messages"])


def _coerce_priority(p: str) -> str:
    if p in ("low", "normal", "high"):
        return p
    return "normal"


def _item_out(msg: Message, um: UserMessage) -> MessageItemOut:
    return MessageItemOut(
        id=msg.id,
        category=msg.category,
        title=msg.title,
        content=msg.content,
        payload=msg.payload,
        priority=_coerce_priority(msg.priority),  # type: ignore[arg-type]
        is_read=um.is_read,
        read_at=um.read_at,
        created_at=msg.created_at,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="未读通知数量",
)
async def unread_count(
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    n = await count_unread_for_user(db, current.user_id)
    return UnreadCountResponse(unread_count=n)


@router.get(
    "",
    response_model=MessageListResponse,
    summary="通知列表（当前用户）",
)
async def list_messages(
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    only_unread: bool = Query(False),
) -> MessageListResponse:
    rows = await list_inbox_page(
        db,
        current.user_id,
        limit=limit,
        offset=offset,
        only_unread=only_unread,
    )
    total = await count_inbox_for_user(db, current.user_id, only_unread=only_unread)
    unread = await count_unread_for_user(db, current.user_id)
    items = [_item_out(m, um) for m, um in rows]
    return MessageListResponse(items=items, total=total, unread_count=unread)


@router.get(
    "/stream",
    summary="通知 SSE（text/event-stream）",
    responses={
        200: {
            "description": "SSE：`data` 行为 JSON，`type` 为 notification | unread_count | heartbeat",
            "content": {"text/event-stream": {}},
        },
    },
)
async def messages_stream(current: AuthUser = Depends(get_current_auth_user)) -> StreamingResponse:
    uid = current.user_id

    async def event_bytes():
        async for line in message_hub.iter_sse_payload_lines(uid):
            yield f"data: {line}\n\n"

    return StreamingResponse(
        event_bytes(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/read-all",
    response_model=ReadAllResponse,
    summary="全部标记已读",
)
async def read_all(
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> ReadAllResponse:
    updated = await mark_all_read(db, current.user_id)
    return ReadAllResponse(updated=updated)


@router.post(
    "/{message_id}/read",
    response_model=MessageOkResponse,
    summary="单条标记已读（幂等）",
    responses={404: {"description": "通知不存在或已删除"}},
)
async def read_one(
    message_id: uuid.UUID,
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> MessageOkResponse:
    ok = await mark_message_read(db, current.user_id, message_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
    return MessageOkResponse()


@router.delete(
    "/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除通知（用户侧软删除）",
    responses={404: {"description": "通知不存在或已删除"}},
)
async def delete_one(
    message_id: uuid.UUID,
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ok = await soft_delete_user_message(db, current.user_id, message_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在")
