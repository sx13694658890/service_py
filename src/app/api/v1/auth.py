import logging
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.config import settings
from app.core.db import get_db
from app.core.db_errors import is_users_email_unique_violation
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.message_repo import create_message_and_dispatch
from app.services.roles_repo import assign_default_role_to_user, get_role_codes_for_user
from app.services.user_repo import get_user_by_email, get_user_by_id, update_user_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="注册",
    responses={
        409: {"description": "该邮箱已被注册"},
    },
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> RegisterResponse:
    email = str(body.username).strip().lower()
    if await get_user_by_email(db, email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册")

    # 应用层生成主键，避免依赖 DB 回填 user_id；否则 user_roles 插入时易触发 IntegrityError 被误报为「邮箱已注册」
    user = User(
        user_id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        await db.flush()
        try:
            await assign_default_role_to_user(db, user)
        except RuntimeError:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统未初始化角色数据，请先执行数据库迁移",
            ) from None
        await db.commit()
        await db.refresh(user)
    except IntegrityError as e:
        await db.rollback()
        if is_users_email_unique_violation(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该邮箱已注册") from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试或联系管理员",
        ) from e
    return RegisterResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="登录",
    responses={
        404: {"description": "用户名（邮箱）不存在"},
        401: {"description": "密码错误"},
    },
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    email = str(body.username).strip().lower()
    user = await get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户名不存在")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码错误")

    role_codes = await get_role_codes_for_user(db, user.user_id)
    expires = timedelta(days=settings.jwt_access_token_expire_days)
    token = create_access_token(
        user_id=user.user_id,
        email=user.email,
        roles=role_codes,
        expires_delta=expires,
    )
    return TokenResponse(
        access_token=token,
        expires_in=int(expires.total_seconds()),
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="修改当前用户密码",
    responses={
        401: {"description": "未登录或当前密码错误"},
        400: {"description": "新密码与当前密码相同"},
        404: {"description": "用户不存在"},
    },
)
async def change_password(
    body: ChangePasswordRequest,
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    user = await get_user_by_id(db, current.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="当前密码错误")

    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与当前密码相同",
        )

    await update_user_password(db, user, body.new_password)
    try:
        await create_message_and_dispatch(
            db,
            user_ids=[current.user_id],
            category="security",
            title="密码已更新",
            content="您的账户密码刚刚已修改。如非本人操作，请立即联系管理员。",
            payload={"kind": "password_changed"},
            priority="high",
            created_by=current.user_id,
        )
    except Exception:
        logger.exception("改密后站内通知投递失败")
    return MessageResponse(message="密码已更新")
