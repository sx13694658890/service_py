from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any, Literal, TypedDict

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.core.config import Settings, settings
from app.knowledge.bundle import get_knowledge_bundle

logger = logging.getLogger(__name__)

HANDOFF_REPLY = (
    "正在为您转接人工客服，请稍候。人工服务时间以页面公告为准；"
    "若当前非服务时段，请留下联系方式或稍后再试。"
)

SYSTEM_PREFIX = """你是产品站内的 AI 助手。请用简体中文、简洁友好地回答。
规则：
1. 优先依据下方「知识库摘录」；摘录不足以回答时，请明确说明不确定，并建议用户查看文档或联系人工客服。
2. 不要编造政策、价格或功能；不要冒充人工已接入。
3. 回答末尾可加一句：以上内容仅供参考，请以官方说明为准。"""


class ChatGraphState(TypedDict, total=False):
    messages: list[dict[str, str]]
    quick_question_id: str | None
    conversation_id: str | None
    retrieval_hint: str | None
    retrieved_chunks: list[dict[str, Any]]
    route: Literal["answer", "human_handoff"]
    assistant_content: str
    sources: list[dict[str, str]]


def _last_user_text(messages: list[dict[str, str]]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            return str(m.get("content", "")).strip()
    return ""


def hydrate_quick_question(state: ChatGraphState) -> dict[str, Any]:
    qid = state.get("quick_question_id")
    bundle = get_knowledge_bundle()
    hint: str | None = None
    if qid and qid in bundle.quick_by_id:
        rq = bundle.quick_by_id[qid].retrieval_query
        hint = rq if rq else None
    return {"retrieval_hint": hint}


def retrieve_kb(state: ChatGraphState) -> dict[str, Any]:
    bundle = get_knowledge_bundle()
    user_q = _last_user_text(state.get("messages", []))
    hint = state.get("retrieval_hint") or ""
    query = f"{user_q} {hint}".strip()
    hits = bundle.index.search(query, top_k=settings.ai_top_k)
    chunks = [
        {
            "text": h.text,
            "source_path": h.path,
            "title": h.title,
            "score": h.score,
        }
        for h in hits
    ]
    return {"retrieved_chunks": chunks}


def decide_route(state: ChatGraphState) -> dict[str, Any]:
    bundle = get_knowledge_bundle()
    qid = state.get("quick_question_id")
    if qid and qid in bundle.quick_by_id:
        gr = bundle.quick_by_id[qid].graph_route
        if gr == "human_handoff":
            return {"route": "human_handoff"}
    last = _last_user_text(state.get("messages", []))
    if last and ("转人工" in last or "人工客服" in last):
        return {"route": "human_handoff"}
    return {"route": "answer"}


def human_handoff_reply(_state: ChatGraphState) -> dict[str, Any]:
    return {"assistant_content": HANDOFF_REPLY}


def _format_kb_excerpt(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "（当前无高相关度知识库摘录，请如实说明不确定之处。）"
    lim = settings.ai_kb_excerpt_chars
    parts: list[str] = []
    for c in chunks:
        body = str(c.get("text", ""))[:lim]
        title = c.get("title", "")
        sp = c.get("source_path", "")
        parts.append(f"### {title} ({sp})\n{body}")
    return "\n\n".join(parts)


def build_lc_messages(state: ChatGraphState) -> list:
    chunks = state.get("retrieved_chunks") or []
    kb_block = _format_kb_excerpt(chunks)
    system_text = f"{SYSTEM_PREFIX}\n\n## 知识库摘录\n{kb_block}"
    lc_messages: list = [SystemMessage(content=system_text)]
    for m in state.get("messages", []):
        role = m.get("role")
        content = str(m.get("content", ""))
        if role == "system":
            continue
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
    return lc_messages


def sources_payload(state: ChatGraphState) -> list[dict[str, str]]:
    route = state.get("route", "answer")
    if route == "human_handoff":
        return []
    bundle = get_knowledge_bundle()
    prefix = bundle.source_prefix or "docs/knowledge-base/"
    chunks = state.get("retrieved_chunks") or []
    return [
        {
            "title": str(c.get("title", "")),
            "path": f"{prefix}{c.get('source_path', '')}",
        }
        for c in chunks
    ]


def merge_pre_llm_state(initial: ChatGraphState) -> ChatGraphState:
    state: ChatGraphState = {**initial}
    state.update(hydrate_quick_question(state))
    state.update(retrieve_kb(state))
    state.update(decide_route(state))
    return state


def _aimessagechunk_text(chunk: AIMessageChunk) -> str:
    c = chunk.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict) and "text" in block:
                parts.append(str(block["text"]))
            elif isinstance(block, str):
                parts.append(block)
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(c) if c else ""


def _stream_chunk_text(chunk: Any) -> str:
    if isinstance(chunk, AIMessageChunk):
        return _aimessagechunk_text(chunk)
    c = getattr(chunk, "content", None)
    if c is None:
        return ""
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return _aimessagechunk_text(AIMessageChunk(content=c))
    return str(c)


def format_sse_json(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def iter_chat_sse(initial: ChatGraphState, app_settings: Settings) -> AsyncIterator[bytes]:
    """SSE：`meta` → 若干 `delta` → `done`（含完整 message 与 sources）；错误为 `error`。"""
    state = merge_pre_llm_state(dict(initial))
    route = state.get("route", "answer")
    yield format_sse_json({"type": "meta", "route": route})

    if route == "human_handoff":
        text = HANDOFF_REPLY
        yield format_sse_json({"type": "delta", "text": text})
        yield format_sse_json(
            {
                "type": "done",
                "sources": [],
                "message": {"role": "assistant", "content": text},
                "route": route,
            }
        )
        return

    if not app_settings.openai_api_key:
        yield format_sse_json(
            {"type": "error", "detail": "AI 服务未配置（缺少 OPENAI_API_KEY）"}
        )
        return

    lc_messages = build_lc_messages(state)
    llm = ChatOpenAI(
        model=app_settings.ai_chat_model,
        api_key=app_settings.openai_api_key,
        base_url=app_settings.openai_api_base,
        temperature=0.3,
        streaming=True,
    )
    parts: list[str] = []
    try:
        async for chunk in llm.astream(lc_messages):
            t = _stream_chunk_text(chunk)
            if not t:
                continue
            parts.append(t)
            yield format_sse_json({"type": "delta", "text": t})
    except Exception:
        logger.exception("ai chat stream failed")
        yield format_sse_json({"type": "error", "detail": "AI 服务暂时不可用"})
        return

    content = "".join(parts).strip()
    if not content:
        yield format_sse_json({"type": "error", "detail": "AI 未返回有效内容"})
        return

    sources = sources_payload(state)
    yield format_sse_json(
        {
            "type": "done",
            "sources": sources,
            "message": {"role": "assistant", "content": content},
            "route": route,
        }
    )


async def call_llm(state: ChatGraphState, config: RunnableConfig) -> dict[str, Any]:
    cfg = config.get("configurable") or {}
    app_settings: Settings = cfg["settings"]

    if not app_settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY_NOT_CONFIGURED")

    lc_messages = build_lc_messages(state)
    llm = ChatOpenAI(
        model=app_settings.ai_chat_model,
        api_key=app_settings.openai_api_key,
        base_url=app_settings.openai_api_base,
        temperature=0.3,
    )
    resp = await llm.ainvoke(lc_messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return {"assistant_content": text}


def build_response(state: ChatGraphState) -> dict[str, Any]:
    return {"sources": sources_payload(state)}


def _route_after_decide(state: ChatGraphState) -> Literal["answer", "human_handoff"]:
    return state.get("route", "answer")


def build_chat_graph() -> Any:
    g = StateGraph(ChatGraphState)
    g.add_node("hydrate_quick_question", hydrate_quick_question)
    g.add_node("retrieve_kb", retrieve_kb)
    g.add_node("decide_route", decide_route)
    g.add_node("human_handoff_reply", human_handoff_reply)
    g.add_node("call_llm", call_llm)
    g.add_node("build_response", build_response)

    g.add_edge(START, "hydrate_quick_question")
    g.add_edge("hydrate_quick_question", "retrieve_kb")
    g.add_edge("retrieve_kb", "decide_route")
    g.add_conditional_edges(
        "decide_route",
        _route_after_decide,
        {
            "answer": "call_llm",
            "human_handoff": "human_handoff_reply",
        },
    )
    g.add_edge("call_llm", "build_response")
    g.add_edge("human_handoff_reply", "build_response")
    g.add_edge("build_response", END)
    return g.compile()


_graph: Any | None = None


def get_compiled_graph() -> Any:
    global _graph
    if _graph is None:
        _graph = build_chat_graph()
    return _graph


async def run_chat_graph(initial: ChatGraphState, app_settings: Settings) -> ChatGraphState:
    graph = get_compiled_graph()
    return await graph.ainvoke(
        initial,
        config={"configurable": {"settings": app_settings}},
    )
