import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.main import app


class _DummyDB:
    pass


def test_users_requires_auth() -> None:
    client = TestClient(app)
    r = client.get("/api/v1/users")
    assert r.status_code == 401


def test_users_list_success(monkeypatch) -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="me@example.com",
            roles=["admin", "user"],
        )

    async def _fake_list_users(_db, *, limit: int, offset: int):
        assert limit == 20
        assert offset == 0
        return [
            SimpleNamespace(
                user_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                email="u1@example.com",
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            SimpleNamespace(
                user_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
                email="u2@example.com",
                created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
        ]

    async def _fake_role_map(_db, user_ids):
        assert len(user_ids) == 2
        return {
            user_ids[0]: ["user"],
            user_ids[1]: ["admin", "user"],
        }

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.users.list_users", _fake_list_users)
    monkeypatch.setattr("app.api.v1.users.get_role_codes_map_for_users", _fake_role_map)
    try:
        r = client.get("/api/v1/users?limit=20&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    body = r.json()
    assert body["current_user"]["email"] == "me@example.com"
    assert body["current_user"]["roles"] == ["admin", "user"]
    assert body["total"] == 2
    assert body["users"][0]["email"] == "u1@example.com"
    assert body["users"][0]["roles"] == ["user"]


def test_delete_user_requires_admin_dependency() -> None:
    """集成 require_roles：非 admin 返回 403。"""
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current_user_only():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="me@example.com",
            roles=["user"],
        )

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current_user_only
    try:
        r = client.delete("/api/v1/users/22222222-2222-2222-2222-222222222222")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 403


def test_delete_user_cannot_delete_self() -> None:
    client = TestClient(app)

    async def _fake_db():
        yield _DummyDB()

    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")

    async def _fake_current():
        return AuthUser(user_id=uid, email="me@example.com", roles=["admin"])

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    try:
        r = client.delete(f"/api/v1/users/{uid}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 400


def test_delete_user_success(monkeypatch) -> None:
    client = TestClient(app)
    target = uuid.UUID("22222222-2222-2222-2222-222222222222")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="admin@example.com",
            roles=["admin"],
        )

    async def _fake_delete(_db, user_id: uuid.UUID) -> bool:
        assert user_id == target
        return True

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.users.delete_user_by_id", _fake_delete)
    try:
        r = client.delete(f"/api/v1/users/{target}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 204
    assert r.content == b""


def test_delete_user_not_found(monkeypatch) -> None:
    client = TestClient(app)
    target = uuid.UUID("22222222-2222-2222-2222-222222222222")

    async def _fake_db():
        yield _DummyDB()

    async def _fake_current():
        return AuthUser(
            user_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            email="admin@example.com",
            roles=["admin"],
        )

    async def _fake_delete(_db, user_id: uuid.UUID) -> bool:
        return False

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.users.delete_user_by_id", _fake_delete)
    try:
        r = client.delete(f"/api/v1/users/{target}")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 404

