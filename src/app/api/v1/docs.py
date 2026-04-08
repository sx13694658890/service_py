from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user, require_roles
from app.core.config import settings
from app.core.db import get_db
from app.models.help_document import HelpDocument
from app.schemas.docs import DocDetailOut, DocListItemOut, DocListResponse, DocUploadResponse
from app.services.help_document_files import (
    public_static_url_for_upload,
    read_doc_file,
    read_uploaded_doc_file,
    resolve_safe_upload_path,
    uploaded_help_docs_root,
)
from app.services.help_document_repo import (
    count_help_documents,
    delete_help_document_row,
    get_help_document_by_id,
    insert_help_document,
    list_help_documents_page,
)
from app.services.upload_markdown_convert import (
    UploadMarkdownConvertError,
    convert_upload_to_markdown,
    max_upload_bytes_for_filename,
)

router = APIRouter(prefix="/docs", tags=["docs"])
logger = logging.getLogger(__name__)


def _is_admin(roles: list[str]) -> bool:
    return "admin" in roles


def _content_url(doc_id: uuid.UUID) -> str:
    return f"{settings.api_v1_prefix}/docs/{doc_id}/content"


def _content_source(doc: HelpDocument) -> Literal["repo", "upload", "inline"]:
    if doc.upload_storage_path:
        return "upload"
    if doc.docs_relpath:
        return "repo"
    return "inline"


def _resolved_body(doc: HelpDocument) -> str | None:
    if doc.upload_storage_path:
        text = read_uploaded_doc_file(doc.upload_storage_path)
        if text is not None:
            return text
    if doc.docs_relpath:
        text = read_doc_file(doc.docs_relpath)
        if text is not None:
            return text
    return doc.body


def _list_item(doc: HelpDocument, user_roles: list[str]) -> DocListItemOut:
    can = HelpDocument.can_user_view(doc.required_role_codes, user_roles)
    return DocListItemOut(
        id=doc.id,
        title=doc.title,
        summary=doc.summary,
        category=doc.category,
        score=doc.score,
        tags=doc.tags,
        can_view=can,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        content_url=_content_url(doc.id) if can else None,
        docs_relpath=doc.docs_relpath if can else None,
        content_source=_content_source(doc),
        can_delete=_is_admin(user_roles),
        static_url=(
            public_static_url_for_upload(doc.upload_storage_path)
            if can and doc.upload_storage_path
            else None
        ),
    )


@router.get(
    "",
    response_model=DocListResponse,
    summary="文档中心列表（需登录）",
)
async def list_docs(
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    keyword: str | None = Query(None, description="标题或摘要模糊匹配"),
    category: str | None = Query(None, description="分类精确匹配，与库中 category 字段一致"),
) -> DocListResponse:
    total = await count_help_documents(db, keyword=keyword, category=category)
    rows = await list_help_documents_page(
        db, limit=limit, offset=offset, keyword=keyword, category=category
    )
    items = [_list_item(d, current.roles) for d in rows]
    return DocListResponse(items=items, total=total)


@router.post(
    "/upload",
    response_model=DocUploadResponse,
    summary="上传文档并落盘为 Markdown（仅 admin）",
    responses={413: {"description": "文件过大"}, 422: {"description": "格式或参数错误"}},
)
async def upload_help_document(
    _admin: AuthUser = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(..., description="支持 .md（UTF-8）或 .docx（Word，服务端转为 Markdown）"),
    title: str = Form(..., min_length=1, max_length=255, description="文档标题"),
    description: str = Form(
        "",
        max_length=4000,
        description="简单描述（列表摘要）；可选，优先于 summary",
    ),
    summary: str = Form(
        "",
        max_length=4000,
        description="简单描述（与 description 二选一；description 非空时忽略本字段）",
    ),
    category: str | None = Form(None, max_length=128),
    tags: str | None = Form(None, description='JSON 数组字符串，如 ["标签1"]'),
) -> DocUploadResponse:
    fn = (file.filename or "").lower()
    max_bytes = max_upload_bytes_for_filename(fn)
    raw = await file.read()
    if len(raw) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小不能超过 {mb}MB",
        )
    try:
        text = convert_upload_to_markdown(raw, file.filename or "")
    except UploadMarkdownConvertError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=e.detail,
        ) from e

    tags_list: list[str] | None = None
    if tags is not None and str(tags).strip():
        try:
            parsed = json.loads(tags)
            if not isinstance(parsed, list):
                raise ValueError
            tags_list = [str(x) for x in parsed]
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="tags 须为 JSON 数组字符串",
            ) from e

    new_id = uuid.uuid4()
    storage_name = f"{new_id}.md"
    root = uploaded_help_docs_root()
    root.mkdir(parents=True, exist_ok=True)
    dest = root / storage_name

    desc = (description or "").strip()
    sum_alt = (summary or "").strip()
    sum_text = desc or sum_alt
    if not sum_text:
        t = title.strip()
        sum_text = (t[:500] + ("…" if len(t) > 500 else "")) or t

    doc = HelpDocument(
        id=new_id,
        title=title.strip(),
        summary=sum_text,
        category=category.strip() if category and category.strip() else None,
        score=None,
        tags=tags_list,
        required_role_codes=None,
        docs_relpath=None,
        upload_storage_path=storage_name,
        body=None,
    )

    try:
        dest.write_text(text, encoding="utf-8")
        await insert_help_document(db, doc)
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    return DocUploadResponse(
        id=doc.id,
        title=doc.title,
        summary=doc.summary,
        category=doc.category,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        static_url=public_static_url_for_upload(storage_name),
    )


def _unlink_upload_file(upload_relpath: str | None) -> None:
    if not upload_relpath:
        return
    try:
        resolve_safe_upload_path(upload_relpath).unlink(missing_ok=True)
    except ValueError:
        logger.warning("删除上传文件时路径非法: %s", upload_relpath)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除文档（仅 admin）",
    responses={403: {"description": "非管理员"}, 404: {"description": "文档不存在"}},
)
async def delete_help_document_endpoint(
    doc_id: uuid.UUID,
    _admin: AuthUser = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
) -> None:
    doc = await get_help_document_by_id(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    upload_rel = doc.upload_storage_path
    await delete_help_document_row(db, doc_id)
    _unlink_upload_file(upload_rel)


@router.get(
    "/{doc_id}/content",
    summary="文档正文（Markdown 文本，需登录且有查看权限）",
    response_class=Response,
    responses={
        200: {"content": {"text/markdown": {}}},
        403: {"description": "无查看权限"},
        404: {"description": "文档不存在或正文不可用"},
    },
)
async def get_doc_content(
    doc_id: uuid.UUID,
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    doc = await get_help_document_by_id(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    if not HelpDocument.can_user_view(doc.required_role_codes, current.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="暂无访问权限")
    body = _resolved_body(doc)
    if body is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档正文不可用")
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
    )


@router.get(
    "/{doc_id}",
    response_model=DocDetailOut,
    summary="文档详情（需登录且有查看权限）",
    responses={403: {"description": "无查看权限"}, 404: {"description": "文档不存在"}},
)
async def get_doc_detail(
    doc_id: uuid.UUID,
    current: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> DocDetailOut:
    doc = await get_help_document_by_id(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    if not HelpDocument.can_user_view(doc.required_role_codes, current.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="暂无访问权限")
    body = _resolved_body(doc)
    if body is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档正文不可用")
    return DocDetailOut(
        id=doc.id,
        title=doc.title,
        summary=doc.summary,
        category=doc.category,
        score=doc.score,
        tags=doc.tags,
        can_view=True,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        content_url=_content_url(doc.id),
        docs_relpath=doc.docs_relpath,
        content_source=_content_source(doc),
        body=body,
        can_delete=_is_admin(current.roles),
        static_url=public_static_url_for_upload(doc.upload_storage_path),
    )
