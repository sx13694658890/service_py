from __future__ import annotations

import re
from pathlib import Path


def _strip_frontmatter(lines: list[str]) -> list[str]:
    if not lines or lines[0].strip() != "---":
        return lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[i + 1 :]
    return lines


def _pop_doc_h1(lines: list[str]) -> tuple[str | None, list[str]]:
    """取出首个一级标题 `# `（非 `##`），并从正文中移除该行。"""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines):
        return None, lines
    line = lines[i]
    if line.startswith("# ") and not line.startswith("## "):
        return line[2:].strip(), lines[:i] + lines[i + 1 :]
    return None, lines


def _split_by_h2(text: str, source_path: str, doc_title: str | None) -> list[tuple[str, str]]:
    """按 `## ` 二级标题切块；第一个块前的正文使用 doc_title 或文件名。"""
    lines = text.splitlines()
    chunks: list[tuple[str, str]] = []
    stem = Path(source_path).stem
    default_title = (doc_title or stem).strip() or stem
    current_title = default_title
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_title
        body = "\n".join(buf).strip()
        if body:
            chunks.append((current_title, body))
        buf = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("###"):
            buf.append(line)
        elif stripped.startswith("##"):
            flush()
            current_title = stripped[2:].lstrip() or default_title
        else:
            buf.append(line)
    flush()
    return chunks


def _split_oversized(title: str, body: str, max_chars: int) -> list[tuple[str, str]]:
    """按段落切分超长块，必要时对单段硬切。"""
    body = body.strip()
    if len(body) <= max_chars:
        return [(title, body)]

    paras = [p.strip() for p in body.split("\n\n") if p.strip()]
    segments: list[str] = []
    cur: list[str] = []
    cur_len = 0

    def flush_cur() -> None:
        nonlocal cur, cur_len
        if cur:
            segments.append("\n\n".join(cur))
            cur = []
            cur_len = 0

    for p in paras:
        sep = 2 if cur else 0
        if cur_len + sep + len(p) <= max_chars:
            cur.append(p)
            cur_len += sep + len(p)
        else:
            flush_cur()
            if len(p) <= max_chars:
                cur = [p]
                cur_len = len(p)
            else:
                for i in range(0, len(p), max_chars):
                    segments.append(p[i : i + max_chars])
    flush_cur()

    if len(segments) == 1:
        return [(title, segments[0])]
    return [(f"{title}（{i + 1}/{len(segments)}）", seg) for i, seg in enumerate(segments)]


def load_markdown_dir(directory: Path, *, chunk_max_chars: int = 4000) -> list[dict]:
    """加载目录下所有 `.md`，返回 `{path, title, text}` 列表。"""
    out: list[dict] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*.md")):
        if any(part.startswith(".") for part in path.parts):
            continue
        # 维护说明不参与检索，避免与业务 FAQ 抢相关度
        if path.name.lower() == "readme.md":
            continue
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        rel = str(path.relative_to(directory))
        lines = raw.splitlines()
        lines = _strip_frontmatter(lines)
        doc_h1, lines = _pop_doc_h1(lines)
        text = "\n".join(lines)
        base_chunks = _split_by_h2(text, rel, doc_h1)
        for title, body in base_chunks:
            for st, chunk_body in _split_oversized(title, body, chunk_max_chars):
                if chunk_body.strip():
                    out.append({"path": rel, "title": st, "text": chunk_body})
    return out
