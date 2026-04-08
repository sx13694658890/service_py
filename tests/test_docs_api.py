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
    assert client.delete(f"/api/v1/docs/{uuid.uuid4()}").status_code == 401


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
        upload_storage_path=None,
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
    assert it["content_source"] == "inline"
    assert it["can_delete"] is False
    assert it.get("static_url") is None


def test_docs_list_static_url_when_upload_and_can_view(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    did = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    ts = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["user"])

    doc = SimpleNamespace(
        id=did,
        title="上传文",
        summary="摘要",
        category=None,
        score=None,
        tags=None,
        required_role_codes=None,
        docs_relpath=None,
        upload_storage_path=f"{did}.md",
        body=None,
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
    u = r.json()["items"][0]["static_url"]
    assert u is not None
    assert str(did) in u
    assert u.endswith(".md")


def test_docs_list_admin_can_delete_flag(monkeypatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    did = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    ts = datetime(2026, 4, 6, 12, 0, tzinfo=timezone.utc)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_admin():
        return AuthUser(user_id=uid, email="a@example.com", roles=["admin", "user"])

    doc = SimpleNamespace(
        id=did,
        title="T",
        summary="S",
        category=None,
        score=None,
        tags=None,
        required_role_codes=None,
        docs_relpath=None,
        upload_storage_path=None,
        body="b",
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_count(_db, *, keyword, category):
        return 1

    async def _fake_list(_db, *, limit, offset, keyword, category):
        return [doc]

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_admin
    monkeypatch.setattr("app.api.v1.docs.count_help_documents", _fake_count)
    monkeypatch.setattr("app.api.v1.docs.list_help_documents_page", _fake_list)
    try:
        r = client.get("/api/v1/docs")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json()["items"][0]["can_delete"] is True


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
        upload_storage_path=None,
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
    assert item["content_source"] == "repo"
    assert item["can_delete"] is False


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
        docs_relpath=None,
        upload_storage_path=None,
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
        upload_storage_path=None,
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
    assert b["content_source"] == "inline"
    assert b["can_delete"] is False
    assert b.get("static_url") is None


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
        upload_storage_path=None,
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


def test_docs_upload_json_body_returns_415() -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_admin():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="a@example.com",
            roles=["admin"],
        )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_admin
    try:
        r = client.post(
            "/api/v1/docs/upload",
            json={"title": "T", "file": "wrong"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 415
    assert "multipart" in r.json()["detail"]


def test_docs_upload_validation_422_includes_hint_when_missing_file() -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_admin():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="a@example.com",
            roles=["admin"],
        )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_admin
    try:
        r = client.post(
            "/api/v1/docs/upload",
            data={"title": "T"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 422
    body = r.json()
    assert "hint" in body
    assert "FormData" in body["hint"] or "multipart" in body["hint"]


def test_docs_upload_requires_admin() -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_user():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="u@example.com",
            roles=["user"],
        )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_user
    try:
        r = client.post(
            "/api/v1/docs/upload",
            data={"title": "T", "summary": "S"},
            files={"file": ("x.md", b"# hi", "text/markdown")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 403


def test_docs_upload_rejects_unsupported_ext() -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_admin():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="a@example.com",
            roles=["admin"],
        )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_admin
    try:
        r = client.post(
            "/api/v1/docs/upload",
            data={"title": "T"},
            files={"file": ("x.pdf", b"%PDF", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 422


def test_docs_delete_requires_admin() -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_user():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="u@example.com",
            roles=["user"],
        )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_user
    try:
        r = client.delete(f"/api/v1/docs/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 403


def test_docs_delete_not_found(monkeypatch) -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_admin():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="a@example.com",
            roles=["admin"],
        )

    async def _fake_get(_db, _did):
        return None

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_admin
    monkeypatch.setattr("app.api.v1.docs.get_help_document_by_id", _fake_get)
    try:
        r = client.delete(f"/api/v1/docs/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404


def test_docs_delete_success_removes_upload_file(monkeypatch, tmp_path) -> None:
    client = TestClient(app)
    doc_id = uuid.UUID("f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0")
    fn = f"{doc_id}.md"
    (tmp_path / fn).write_text("# x", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.help_document_files.uploaded_help_docs_root",
        lambda: tmp_path,
    )

    async def _fake_db():
        yield _DummyDB()

    async def _fake_admin():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="a@example.com",
            roles=["admin"],
        )

    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
    doc = SimpleNamespace(
        id=doc_id,
        title="t",
        summary="s",
        category=None,
        score=None,
        tags=None,
        required_role_codes=None,
        docs_relpath=None,
        upload_storage_path=fn,
        body=None,
        created_at=ts,
        updated_at=ts,
    )

    async def _fake_get(_db, did):
        return doc if did == doc_id else None

    async def _fake_del(_db, did):
        return did == doc_id

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_admin
    monkeypatch.setattr("app.api.v1.docs.get_help_document_by_id", _fake_get)
    monkeypatch.setattr("app.api.v1.docs.delete_help_document_row", _fake_del)
    try:
        r = client.delete(f"/api/v1/docs/{doc_id}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 204
    assert not (tmp_path / fn).exists()
