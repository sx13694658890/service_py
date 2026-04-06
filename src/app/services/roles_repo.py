import uuid

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role, user_roles_table
from app.models.user import User

DEFAULT_ROLE_CODE = "user"


async def get_role_by_code(db: AsyncSession, code: str) -> Role | None:
    result = await db.execute(select(Role).where(Role.code == code))
    return result.scalar_one_or_none()


async def get_role_codes_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    result = await db.execute(
        select(Role.code)
        .join(user_roles_table, user_roles_table.c.role_id == Role.uid)
        .where(user_roles_table.c.user_id == user_id)
        .order_by(Role.code),
    )
    return list(result.scalars().all())


async def assign_default_role_to_user(db: AsyncSession, user: User) -> None:
    role = await get_role_by_code(db, DEFAULT_ROLE_CODE)
    if role is None:
        msg = "数据库缺少预置角色 'user'，请先执行 alembic upgrade"
        raise RuntimeError(msg)
    # AsyncSession 下避免 user.roles.append()，否则易触发 MissingGreenlet
    await db.execute(
        insert(user_roles_table).values(user_id=user.user_id, role_id=role.uid),
    )
