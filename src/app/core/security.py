import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(
    *,
    user_id: uuid.UUID,
    email: str,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    delta = expires_delta or timedelta(days=settings.jwt_access_token_expire_days)
    now = datetime.now(timezone.utc)
    expire = now + delta
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
