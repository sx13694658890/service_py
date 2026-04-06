import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.models.user import User

client = TestClient(app)

UID_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
UID_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
UID_REG = uuid.UUID("99999999-9999-4999-8999-999999999999")
UID_SHORT = uuid.UUID("33333333-3333-4333-8333-333333333333")

# bcrypt 对明文 "secret" 的哈希（仅用于单测，勿用于生产）
_HASH_SECRET = (
    "$2b$12$MJm3b4cdyA3YB/DWsSoLoOivu1llW4um8T8IFVw0w7TOC8kdRvKfi"
)


def _user(**kwargs: object) -> User:
    base = {
        "user_id": uuid.uuid4(),
        "created_at": datetime.now(UTC),
        "password_hash": _HASH_SECRET,
    }
    base.update(kwargs)
    return User(**base)


def test_login_user_not_found() -> None:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "missing@example.com", "password": "secret"},
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "用户名不存在"
    finally:
        app.dependency_overrides.clear()


def test_login_wrong_password() -> None:
    user = _user(user_id=UID_A, email="a@example.com")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "a@example.com", "password": "wrong-password"},
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "密码错误"
    finally:
        app.dependency_overrides.clear()


def test_login_success_returns_token() -> None:
    user = _user(user_id=UID_B, email="ok@example.com")
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = user
    mock_roles_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = ["user"]
    mock_roles_result.scalars.return_value = mock_scalars

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_user_result, mock_roles_result])

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/login",
            json={"username": "ok@example.com", "password": "secret"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert data["expires_in"] == 7 * 24 * 60 * 60
        payload = jwt.decode(
            data["access_token"],
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload["roles"] == ["user"]
        assert payload["sub"] == str(UID_B)
    finally:
        app.dependency_overrides.clear()


def test_register_conflict() -> None:
    existing = _user(user_id=UID_A, email="taken@example.com")
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/register",
            json={"username": "taken@example.com", "password": "longenough"},
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "该邮箱已注册"
    finally:
        app.dependency_overrides.clear()


@patch("app.api.v1.auth.assign_default_role_to_user", new_callable=AsyncMock)
def test_register_success(_mock_assign: AsyncMock) -> None:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    async def refresh_side_effect(u: User) -> None:
        u.user_id = UID_REG
        u.email = "new@example.com"

    mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/register",
            json={"username": "new@example.com", "password": "longpassword"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["user_id"] == str(UID_REG)
        assert data["email"] == "new@example.com"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()
        _mock_assign.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


class _EmailUniqueViolationOrig(Exception):
    sqlstate = "23505"

    def __str__(self) -> str:
        return 'duplicate key value violates unique constraint "users_email_key"'


@patch("app.api.v1.auth.assign_default_role_to_user", new_callable=AsyncMock)
def test_register_integrity_error_email_returns_409(_mock_assign: AsyncMock) -> None:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock(
        side_effect=IntegrityError("stmt", None, _EmailUniqueViolationOrig()),
    )
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/register",
            json={"username": "race@example.com", "password": "longenough1"},
        )
        assert r.status_code == 409
        assert r.json()["detail"] == "该邮箱已注册"
        mock_session.rollback.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.v1.auth.assign_default_role_to_user", new_callable=AsyncMock)
def test_register_integrity_error_other_returns_500(_mock_assign: AsyncMock) -> None:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock(side_effect=IntegrityError("stmt", None, Exception("fk")))
    mock_session.rollback = AsyncMock()
    mock_session.add = MagicMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/register",
            json={"username": "other@example.com", "password": "longenough1"},
        )
        assert r.status_code == 500
        assert "注册失败" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_register_invalid_email() -> None:
    r = client.post(
        "/api/v1/auth/register",
        json={"username": "not-an-email", "password": "longenough"},
    )
    assert r.status_code == 422


@patch("app.api.v1.auth.assign_default_role_to_user", new_callable=AsyncMock)
def test_register_allows_short_password(_mock_assign: AsyncMock) -> None:
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    async def refresh_side_effect(u: User) -> None:
        u.user_id = UID_SHORT
        u.email = "short@example.com"

    mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        r = client.post(
            "/api/v1/auth/register",
            json={"username": "short@example.com", "password": "x"},
        )
        assert r.status_code == 201
        assert r.json()["email"] == "short@example.com"
        assert r.json()["user_id"] == str(UID_SHORT)
        mock_session.refresh.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
