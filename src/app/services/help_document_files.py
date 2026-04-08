from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.paths import project_root


def docs_root() -> Path:
    return project_root() / "docs"


def uploaded_help_docs_root() -> Path:
    """文档中心「上传」文件根目录（默认在仓库 static/ 下，便于作为静态资源托管）。"""
    if settings.help_docs_upload_dir:
        return Path(settings.help_docs_upload_dir).expanduser().resolve()
    return (project_root() / "static" / "help_documents").resolve()


def public_static_url_for_upload(storage_relpath: str | None) -> str | None:
    """上传文件的公开 HTTP 路径（相对站点根，无需 Bearer；仅当存在 upload_storage_path 时有值）。"""
    if not storage_relpath or not str(storage_relpath).strip():
        return None
    base = (settings.help_docs_static_mount_path or "/static/help-documents").strip()
    if not base.startswith("/"):
        base = "/" + base
    name = str(storage_relpath).replace("\\", "/").lstrip("/")
    return f"{base.rstrip('/')}/{name}"


def resolve_safe_doc_path(relpath: str) -> Path:
    """将库中相对路径解析为 `docs/` 下绝对路径；禁止跳出 `docs/`。"""
    if not relpath or not str(relpath).strip():
        raise ValueError("empty_relpath")
    parts: list[str] = []
    for p in str(relpath).replace("\\", "/").strip().split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            raise ValueError("path_traversal")
        parts.append(p)
    if not parts:
        raise ValueError("empty_relpath")
    root = docs_root().resolve()
    full = (root.joinpath(*parts)).resolve()
    full.relative_to(root)
    return full


def read_doc_file(relpath: str) -> str | None:
    try:
        path = resolve_safe_doc_path(relpath)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def resolve_safe_upload_path(relpath: str) -> Path:
    """上传区相对路径，禁止跳出上传根目录。"""
    if not relpath or not str(relpath).strip():
        raise ValueError("empty_upload_path")
    parts: list[str] = []
    for p in str(relpath).replace("\\", "/").strip().split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            raise ValueError("path_traversal")
        parts.append(p)
    if len(parts) != 1 or not parts[0].endswith(".md"):
        raise ValueError("invalid_upload_name")
    root = uploaded_help_docs_root().resolve()
    full = (root / parts[0]).resolve()
    full.relative_to(root)
    return full


def read_uploaded_doc_file(storage_relpath: str) -> str | None:
    try:
        path = resolve_safe_upload_path(storage_relpath)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")
