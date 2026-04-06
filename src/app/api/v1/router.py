from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.ai_chat import router as ai_chat_router
from app.api.v1.auth import router as auth_router
from app.core.db import get_db

router = APIRouter(tags=["v1"])
router.include_router(auth_router)
router.include_router(ai_chat_router)


@router.get("/ping", summary="连通性测试（不访问数据库）")
def ping() -> dict[str, str]:
    return {"message": "pong"}


@router.get("/db-check", summary="数据库连接测试")
async def db_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"database": "ok"}
