import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.main import app


class _DummyDB:
    pass


def test_messages_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/messages").status_code == 401
    assert client.get("/api/v1/messages/unread-count").status_code == 401


def test_messages_list_success(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    mid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    m = SimpleNamespace(
        id=mid,
        category="security",
        title="t",
        content="c",
        payload={"k": 1},
        priority="high",
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    um = SimpleNamespace(
        is_read=False,
        read_at=None,
    )

    async def _fake_list(_db, user_id, *, limit, offset, only_unread):
        assert user_id == uid
        assert limit == 20
        assert offset == 0
        assert only_unread is False
        return [(m, um)]

    async def _fake_count_inbox(_db, user_id, *, only_unread):
        assert user_id == uid
        return 1

    async def _fake_unread(_db, user_id):
        assert user_id == uid
        return 3

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.messages.list_inbox_page", _fake_list)
    monkeypatch.setattr("app.api.v1.messages.count_inbox_for_user", _fake_count_inbox)
    monkeypatch.setattr("app.api.v1.messages.count_unread_for_user", _fake_unread)
    try:
        r = client.get("/api/v1/messages?limit=20&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["unread_count"] == 3
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(mid)
    assert body["items"][0]["title"] == "t"


def test_messages_read_one_not_found(monkeypatch) -> None:
    client = TestClient(app)
    mid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="me@example.com",
            roles=["user"],
        )

    async def _fake_mark(_db, user_id, message_id):
        return False

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.messages.mark_message_read", _fake_mark)
    try:
        r = client.post(f"/api/v1/messages/{mid}/read")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404


def test_messages_read_one_ok(monkeypatch) -> None:
    client = TestClient(app)
    mid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="me@example.com",
            roles=["user"],
        )

    async def _fake_mark(_db, user_id, message_id):
        assert message_id == mid
        return True

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.messages.mark_message_read", _fake_mark)
    try:
        r = client.post(f"/api/v1/messages/{mid}/read")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"message": "ok"}
