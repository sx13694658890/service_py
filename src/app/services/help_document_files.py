from __future__ import annotations

from pathlib import Path

from app.core.paths import project_root


def docs_root() -> Path:
    return project_root() / "docs"


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
