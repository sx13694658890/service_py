import re
from pathlib import Path


def _split_chunks(text: str, source_path: str) -> list[tuple[str, str]]:
    """按 `## ` 标题切块；无标题时整篇一块。"""
    lines = text.splitlines()
    chunks: list[tuple[str, str]] = []
    current_title = ""
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, current_title
        body = "\n".join(buf).strip()
        if body:
            title = current_title or Path(source_path).stem
            chunks.append((title, body))
        buf = []

    for line in lines:
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
        else:
            buf.append(line)
    flush()
    return chunks


def load_markdown_dir(directory: Path) -> list[dict]:
    """加载目录下所有 `.md`，返回 `{path, title, text}` 列表。"""
    out: list[dict] = []
    if not directory.is_dir():
        return out
    for path in sorted(directory.rglob("*.md")):
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(directory))
        for title, body in _split_chunks(raw, rel):
            out.append({"path": rel, "title": title, "text": body})
    return out
