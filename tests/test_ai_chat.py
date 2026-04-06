import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_quick_questions(client: TestClient) -> None:
    r = client.get("/api/v1/ai/quick-questions")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert any(i.get("id") == "what_is_it" for i in data["items"])


def test_chat_human_handoff_no_llm_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": None}),
    )
    r = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "转人工"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["message"]["role"] == "assistant"
    assert "人工" in body["message"]["content"]
    assert body.get("route") == "human_handoff"
    assert body["sources"] == []


def test_chat_quick_transfer_human_without_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": None}),
    )
    r = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "转人工"}],
            "quick_question_id": "transfer_human",
        },
    )
    assert r.status_code == 200
    assert r.json()["route"] == "human_handoff"


def test_chat_answer_requires_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": None}),
    )
    r = client.post(
        "/api/v1/ai/chat",
        json={
            "messages": [{"role": "user", "content": "你好，介绍一下产品"}],
            "quick_question_id": "what_is_it",
        },
    )
    assert r.status_code == 503
    assert "OPENAI_API_KEY" in r.json().get("detail", "")


def test_chat_answer_mock_graph(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": "sk-test"}),
    )

    async def _fake_run(*_a, **_k):
        return {
            "assistant_content": "模拟回复",
            "route": "answer",
            "sources": [{"title": "节选", "path": "docs/ai问答需求/x.md"}],
        }

    monkeypatch.setattr("app.api.v1.ai_chat.run_chat_graph", AsyncMock(side_effect=_fake_run))
    r = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": "测试"}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["message"]["content"] == "模拟回复"
    assert body["sources"][0]["title"] == "节选"


def _parse_sse_events(raw: bytes) -> list[dict]:
    events: list[dict] = []
    for block in raw.split(b"\n\n"):
        line = block.strip()
        if not line.startswith(b"data: "):
            continue
        events.append(json.loads(line[6:].decode("utf-8")))
    return events


def test_chat_stream_human_handoff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": None}),
    )
    with client.stream(
        "POST",
        "/api/v1/ai/chat/stream",
        json={"messages": [{"role": "user", "content": "转人工"}]},
    ) as r:
        assert r.status_code == 200
        body = r.read()
    ev = _parse_sse_events(body)
    assert ev[0]["type"] == "meta"
    assert ev[0]["route"] == "human_handoff"
    assert any(e["type"] == "delta" for e in ev)
    assert ev[-1]["type"] == "done"
    assert "人工" in ev[-1]["message"]["content"]


def test_chat_stream_mock_llm(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from langchain_core.messages import AIMessageChunk

    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": "sk-test"}),
    )

    class _FakeStreamLLM:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def astream(self, _messages):
            yield AIMessageChunk(content="模")
            yield AIMessageChunk(content="拟")

    monkeypatch.setattr("app.ai.chat_graph.ChatOpenAI", _FakeStreamLLM)

    with client.stream(
        "POST",
        "/api/v1/ai/chat/stream",
        json={"messages": [{"role": "user", "content": "hi"}]},
    ) as r:
        assert r.status_code == 200
        body = r.read()
    ev = _parse_sse_events(body)
    assert ev[0]["type"] == "meta"
    assert ev[-1]["type"] == "done"
    assert ev[-1]["message"]["content"] == "模拟"


def test_chat_stream_requires_key(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": None}),
    )
    r = client.post(
        "/api/v1/ai/chat/stream",
        json={"messages": [{"role": "user", "content": "需要模型的问题"}]},
    )
    assert r.status_code == 503


def test_chat_message_too_long(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.ai_chat.settings",
        settings.model_copy(update={"openai_api_key": "sk-test"}),
    )
    big = "a" * 70_000
    r = client.post(
        "/api/v1/ai/chat",
        json={"messages": [{"role": "user", "content": big}]},
    )
    assert r.status_code == 422
