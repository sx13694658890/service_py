from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_deps import AuthUser, get_current_auth_user
from app.core.config import settings
from app.core.db import get_db
from app.models.help_document import HelpDocument
from app.schemas.docs import DocDetailOut, DocListItemOut, DocListResponse
from app.services.help_document_files import read_doc_file
from app.services.help_document_repo import (
    count_help_documents,
    get_help_document_by_id,
    list_help_documents_page,
)

router = APIRouter(prefix="/docs", tags=["docs"])


def _content_url(doc_id: uuid.UUID) -> str:
    return f"{settings.api_v1_prefix}/docs/{doc_id}/content"


def _resolved_body(doc: HelpDocument) -> str | None:
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
        body=body,
    )
