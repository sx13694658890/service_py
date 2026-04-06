from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.ai.chat_graph import iter_chat_sse, run_chat_graph
from app.core.config import settings
from app.knowledge.bundle import get_knowledge_bundle
from app.schemas.ai_chat import (
    AssistantMessageOut,
    ChatRequest,
    ChatResponse,
    QuickQuestionItemOut,
    QuickQuestionsResponse,
    SourceOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

MAX_TOTAL_CHARS = 64_000


def _total_message_chars(messages: list) -> int:
    return sum(len(m.content) for m in messages)


def _validate_chat_body(body: ChatRequest) -> None:
    if _total_message_chars(body.messages) > MAX_TOTAL_CHARS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="消息总长度超出限制",
        )


def _preflight_requires_openai_key(body: ChatRequest) -> bool:
    """转人工路径不调用 LLM，可不配置 Key。"""
    bundle = get_knowledge_bundle()
    if body.quick_question_id:
        item = bundle.quick_by_id.get(body.quick_question_id)
        if item and item.graph_route == "human_handoff":
            return False
    if body.messages:
        last = body.messages[-1]
        if last.role == "user" and ("转人工" in last.content or "人工客服" in last.content):
            return False
    return True


@router.get(
    "/quick-questions",
    response_model=QuickQuestionsResponse,
    summary="快捷问题列表（供前端 chip）",
)
def list_quick_questions() -> QuickQuestionsResponse:
    bundle = get_knowledge_bundle()
    items = [QuickQuestionItemOut(id=i.id, label=i.label) for i in bundle.quick_items]
    return QuickQuestionsResponse(items=items)


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="AI 问答（LangGraph + 知识库 + DeepSeek）",
    responses={
        503: {"description": "未配置 API Key 或上游不可用"},
        413: {"description": "消息过长"},
    },
)
async def chat(body: ChatRequest) -> ChatResponse:
    _validate_chat_body(body)

    if _preflight_requires_openai_key(body) and not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务未配置（缺少 OPENAI_API_KEY）",
        )

    initial = {
        "messages": [m.model_dump() for m in body.messages],
        "quick_question_id": body.quick_question_id,
        "conversation_id": body.conversation_id,
    }

    try:
        final = await run_chat_graph(initial, settings)
    except RuntimeError as e:
        if str(e) == "OPENAI_API_KEY_NOT_CONFIGURED":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI 服务未配置（缺少 OPENAI_API_KEY）",
            ) from e
        logger.exception("ai chat graph failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务暂时不可用",
        ) from e
    except Exception:
        logger.exception("ai chat graph failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务暂时不可用",
        ) from None

    content = str(final.get("assistant_content", "")).strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 未返回有效内容",
        )

    route = final.get("route")
    raw_sources = final.get("sources") or []
    sources = [SourceOut(title=s["title"], path=s["path"]) for s in raw_sources]

    return ChatResponse(
        message=AssistantMessageOut(content=content),
        sources=sources,
        route=route,
    )


@router.post(
    "/chat/stream",
    summary="AI 问答（SSE 流式，text/event-stream）",
    responses={
        200: {
            "description": "SSE 流：每行 `data: <JSON>`，事件类型见 `type` 字段",
            "content": {"text/event-stream": {}},
        },
        503: {"description": "未配置 API Key（在建立流之前返回）"},
        413: {"description": "消息过长"},
    },
)
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    """前端请用 `fetch` + `ReadableStream` 解析 SSE（`EventSource` 不支持 POST）。"""
    _validate_chat_body(body)

    if _preflight_requires_openai_key(body) and not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 服务未配置（缺少 OPENAI_API_KEY）",
        )

    initial = {
        "messages": [m.model_dump() for m in body.messages],
        "quick_question_id": body.quick_question_id,
        "conversation_id": body.conversation_id,
    }

    async def event_bytes():
        async for chunk in iter_chat_sse(initial, settings):
            yield chunk

    return StreamingResponse(
        event_bytes(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
