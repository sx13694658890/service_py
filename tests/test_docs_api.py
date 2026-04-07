import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.main import app


class _DummyDB:
    pass


def test_docs_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/docs").status_code == 401
    assert client.get(f"/api/v1/docs/{uuid.uuid4()}").status_code == 401
    assert client.get(f"/api/v1/docs/{uuid.uuid4()}/content").status_code == 401


def test_docs_list_success(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    did = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    ts = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    doc = SimpleNamespace(
        id=did,
        title="Windows教程",
        summary="摘要",
        category="使用文档",
        score=4.8,
        tags=["E", "C"],
        required_role_codes=None,
        docs_relpath=None,
        body="x",
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_count(_db, *, keyword, category):
        assert keyword is None
        assert category is None
        return 1

    async def _fake_list(_db, *, limit, offset, keyword, category):
        assert limit == 20
        assert offset == 0
        assert keyword is None
        assert category is None
        return [doc]

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.count_help_documents", _fake_count)
    monkeypatch.setattr("app.api.v1.docs.list_help_documents_page", _fake_list)
    try:
        r = client.get("/api/v1/docs?limit=20&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    it = body["items"][0]
    assert it["id"] == str(did)
    assert it["title"] == "Windows教程"
    assert it["can_view"] is True
    assert it["content_url"] == f"/api/v1/docs/{did}/content"
    assert it["docs_relpath"] is None


def test_docs_list_keyword_passed(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    captured = {}

    async def _fake_count(_db, *, keyword, category):
        captured["keyword"] = keyword
        captured["category"] = category
        return 0

    async def _fake_list(_db, *, limit, offset, keyword, category):
        captured["list_kw"] = keyword
        captured["list_cat"] = category
        return []

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.count_help_documents", _fake_count)
    monkeypatch.setattr("app.api.v1.docs.list_help_documents_page", _fake_list)
    try:
        r = client.get("/api/v1/docs?keyword=hello")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert captured["keyword"] == "hello"
    assert captured["list_kw"] == "hello"
    assert captured["category"] is None
    assert captured["list_cat"] is None


def test_docs_list_category_passed(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    captured = {}

    async def _fake_count(_db, *, keyword, category):
        captured["category"] = category
        return 0

    async def _fake_list(_db, *, limit, offset, keyword, category):
        captured["list_cat"] = category
        return []

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.count_help_documents", _fake_count)
    monkeypatch.setattr("app.api.v1.docs.list_help_documents_page", _fake_list)
    try:
        r = client.get("/api/v1/docs?category=%E7%94%A8%E6%88%B7")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert captured["category"] == "用户"
    assert captured["list_cat"] == "用户"


def test_docs_list_can_view_false_without_role(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    did = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    doc = SimpleNamespace(
        id=did,
        title="内部",
        summary="s",
        category=None,
        score=None,
        tags=None,
        required_role_codes=["admin"],
        docs_relpath="secret.md",
        body="secret",
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_count(_db, *, keyword, category):
        return 1

    async def _fake_list(_db, *, limit, offset, keyword, category):
        return [doc]

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.count_help_documents", _fake_count)
    monkeypatch.setattr("app.api.v1.docs.list_help_documents_page", _fake_list)
    try:
        r = client.get("/api/v1/docs")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    item = r.json()["items"][0]
    assert item["can_view"] is False
    assert item["content_url"] is None
    assert item["docs_relpath"] is None


def test_doc_detail_not_found(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    doc_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    async def _fake_get(_db, _doc_id):
        assert _doc_id == doc_id
        return None

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.get_help_document_by_id", _fake_get)
    try:
        r = client.get(f"/api/v1/docs/{doc_id}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404


def test_doc_detail_forbidden(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    doc_id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    doc = SimpleNamespace(
        id=doc_id,
        title="内部",
        summary="s",
        category=None,
        score=None,
        tags=None,
        required_role_codes=["admin"],
        body="secret",
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_get(_db, _doc_id):
        return doc

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.get_help_document_by_id", _fake_get)
    try:
        r = client.get(f"/api/v1/docs/{doc_id}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 403


def test_doc_detail_ok(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    doc_id = uuid.UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    doc = SimpleNamespace(
        id=doc_id,
        title="公开",
        summary="s",
        category="使用文档",
        score=3.0,
        tags=["x"],
        required_role_codes=None,
        docs_relpath=None,
        body="正文",
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_get(_db, _doc_id):
        return doc

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.get_help_document_by_id", _fake_get)
    try:
        r = client.get(f"/api/v1/docs/{doc_id}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    b = r.json()
    assert b["body"] == "正文"
    assert b["can_view"] is True
    assert b["content_url"] == f"/api/v1/docs/{doc_id}/content"


def test_doc_content_ok(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    doc_id = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    ts = datetime(2026, 4, 1, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    doc = SimpleNamespace(
        id=doc_id,
        title="公开",
        summary="s",
        category=None,
        score=None,
        tags=None,
        required_role_codes=None,
        docs_relpath=None,
        body="# hi",
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_get(_db, _doc_id):
        return doc

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.docs.get_help_document_by_id", _fake_get)
    try:
        r = client.get(f"/api/v1/docs/{doc_id}/content")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.text == "# hi"
    assert "text/markdown" in r.headers.get("content-type", "")
