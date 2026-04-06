from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.db import engine
from app.knowledge.bundle import init_knowledge_bundle


def _package_version() -> str:
    try:
        return version("server-python")
    except PackageNotFoundError:
        return "0.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_knowledge_bundle()
    yield
    await engine.dispose()


app = FastAPI(
    title="Server Python API",
    description="FastAPI + PostgreSQL 服务骨架",
    version=_package_version(),
    lifespan=lifespan,
)

app.include_router(v1_router, prefix=settings.api_v1_prefix)


@app.get("/health", summary="存活探针（不访问数据库）")
def health() -> dict[str, str]:
    return {"status": "ok"}


def run() -> None:
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
