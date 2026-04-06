import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.db import get_db
from app.main import app


def test_change_password_requires_auth() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "a", "new_password": "123456"},
    )
    assert r.status_code == 401


def test_change_password_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user = SimpleNamespace(user_id=uid, password_hash="stored")

    async def _fake_db():
        yield object()

    async def _fake_current() -> AuthUser:
        return AuthUser(user_id=uid, email="a@b.com", roles=["user"])

    async def _fake_get_user(_db, got_uid: uuid.UUID):
        assert got_uid == uid
        return user

    async def _fake_update(_db, u, new_p: str) -> None:
        assert u is user
        assert new_p == "newsecret"

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.auth.get_user_by_id", _fake_get_user)
    monkeypatch.setattr(
        "app.api.v1.auth.verify_password",
        lambda cur, h: cur == "oldpass" and h == "stored",
    )
    monkeypatch.setattr("app.api.v1.auth.update_user_password", _fake_update)
    try:
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "oldpass", "new_password": "newsecret"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200
    assert r.json() == {"message": "密码已更新"}


def test_change_password_wrong_current(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user = SimpleNamespace(user_id=uid, password_hash="stored")

    async def _fake_db():
        yield object()

    async def _fake_current() -> AuthUser:
        return AuthUser(user_id=uid, email="a@b.com", roles=["user"])

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.auth.get_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr("app.api.v1.auth.verify_password", lambda _c, _h: False)
    try:
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrong", "new_password": "123456"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 401


def test_change_password_same_as_current(monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    uid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user = SimpleNamespace(user_id=uid, password_hash="stored")

    async def _fake_db():
        yield object()

    async def _fake_current() -> AuthUser:
        return AuthUser(user_id=uid, email="a@b.com", roles=["user"])

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_current_auth_user] = _fake_current
    monkeypatch.setattr("app.api.v1.auth.get_user_by_id", AsyncMock(return_value=user))
    monkeypatch.setattr(
        "app.api.v1.auth.verify_password",
        lambda cur, h: cur == "secret12" and h == "stored",
    )
    try:
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "secret12", "new_password": "secret12"},
        )
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 400
