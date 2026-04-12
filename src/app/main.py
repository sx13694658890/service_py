from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

from app.api.v1.router import router as v1_router
from app.core.config import settings
from app.core.db import engine
from app.knowledge.bundle import init_knowledge_bundle
from app.services import message_hub
from app.services.help_document_files import uploaded_help_docs_root


def _package_version() -> str:
    try:
        return version("server-python")
    except PackageNotFoundError:
        return "0.1.0"


_DOCS_UPLOAD_PATH_SUFFIX = "/docs/upload"

_DOCS_UPLOAD_MULTIPART_HINT = (
    "文档上传接口必须使用 multipart/form-data：用 FormData 追加字段 "
    '"title"（字符串）与 "file"（二进制文件，字段名须为 file）。'
    "不要发送 application/json；使用 fetch/axios 时不要手写 "
    'Content-Type: multipart/form-data（须由客户端自动生成 boundary，'
    "否则服务端无法解析，会报 file/title 缺失）。"
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_knowledge_bundle()
    await message_hub.init_redis(settings.redis_url)
    yield
    await message_hub.close_redis()
    await engine.dispose()


app = FastAPI(
    title="Server Python API",
    description="FastAPI + PostgreSQL 服务骨架",
    version=_package_version(),
    lifespan=lifespan,
)


@app.middleware("http")
async def _reject_json_body_on_docs_upload(request: Request, call_next):
    """上传接口若误发 JSON 或无 boundary 的 multipart，提前返回明确说明（避免仅见 422 missing）。"""
    if request.method != "POST":
        return await call_next(request)
    path = request.url.path.rstrip("/")
    if not path.endswith(_DOCS_UPLOAD_PATH_SUFFIX):
        return await call_next(request)
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" in ct and "multipart" not in ct:
        return JSONResponse(
            status_code=415,
            content={"detail": _DOCS_UPLOAD_MULTIPART_HINT},
        )
    if ct.startswith("multipart/form-data") and "boundary=" not in ct:
        return JSONResponse(
            status_code=415,
            content={"detail": _DOCS_UPLOAD_MULTIPART_HINT},
        )
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def _docs_upload_validation_hint(request: Request, exc: RequestValidationError):
    if request.method == "POST" and request.url.path.rstrip("/").endswith(_DOCS_UPLOAD_PATH_SUFFIX):
        errors = exc.errors()
        missing = {
            e["loc"][-1]
            for e in errors
            if e.get("type") == "missing" and e.get("loc") and e["loc"][0] == "body"
        }
        if missing & {"file", "title"}:
            return JSONResponse(
                status_code=422,
                content={"detail": errors, "hint": _DOCS_UPLOAD_MULTIPART_HINT},
            )
    return await request_validation_exception_handler(request, exc)


app.include_router(v1_router, prefix=settings.api_v1_prefix)

# 文档中心上传的 Markdown：匿名可通过 GET {mount}/{uuid}.md 访问（与 help_docs_static_mount_path、上传目录一致）
_upload_dir = uploaded_help_docs_root()
_upload_dir.mkdir(parents=True, exist_ok=True)
_mount = (settings.help_docs_static_mount_path or "/static/help-documents").strip() or "/static/help-documents"
if not _mount.startswith("/"):
    _mount = "/" + _mount
app.mount(
    _mount,
    StaticFiles(directory=str(_upload_dir)),
    name="help_documents_static",
)


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
