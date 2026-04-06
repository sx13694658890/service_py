from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user, require_roles
from app.core.db import get_db
from app.schemas.users import CurrentUserOut, UserListItemOut, UserListResponse
from app.services.roles_repo import get_role_codes_map_for_users
from app.services.user_repo import delete_user_by_id, list_users

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "",
    response_model=UserListResponse,
    summary="获取用户列表（含当前用户角色）",
    responses={401: {"description": "未登录或令牌无效"}},
)
async def get_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    users = await list_users(db, limit=limit, offset=offset)
    user_ids = [u.user_id for u in users]
    role_map = await get_role_codes_map_for_users(db, user_ids)

    return UserListResponse(
        current_user=CurrentUserOut(
            user_id=current.user_id,
            email=current.email,
            roles=current.roles,
        ),
        users=[
            UserListItemOut(
                user_id=u.user_id,
                email=u.email,
                created_at=u.created_at,
                roles=role_map.get(u.user_id, []),
            )
            for u in users
        ],
        total=len(users),
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除用户（需 admin）",
    responses={
        401: {"description": "未登录或令牌无效"},
        403: {"description": "非管理员"},
        404: {"description": "用户不存在"},
    },
)
async def delete_user(
    user_id: uuid.UUID,
    current: AuthUser = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user_id == current.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录账号",
        )
    deleted = await delete_user_by_id(db, user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
