from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    user_id: uuid.UUID
    email: str
    roles: list[str]


def _unauthorized(detail: str = "未登录或令牌无效") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_auth_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as e:
        raise _unauthorized("登录已过期，请重新登录") from e
    except jwt.InvalidTokenError as e:
        raise _unauthorized() from e

    sub = payload.get("sub")
    email = payload.get("email")
    roles = payload.get("roles") or []
    if not isinstance(sub, str) or not isinstance(email, str) or not isinstance(roles, list):
        raise _unauthorized()

    try:
        user_id = uuid.UUID(sub)
    except ValueError as e:
        raise _unauthorized() from e

    return AuthUser(
        user_id=user_id,
        email=email,
        roles=[str(r) for r in roles],
    )


def _forbidden(detail: str = "权限不足") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_roles(*required: str):
    """要求当前用户至少拥有 `required` 中任一角色 code。"""

    async def _dep(current: AuthUser = Depends(get_current_auth_user)) -> AuthUser:
        if not required:
            return current
        allowed = set(required)
        if not allowed.intersection(current.roles):
            raise _forbidden()
        return current

    return _dep
