from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import settings
from app.core.paths import project_root
from app.knowledge.bm25_index import BM25KnowledgeIndex
from app.knowledge.loader import load_markdown_dir
from app.knowledge.quick_questions import QuickQuestionItem, load_quick_questions

logger = logging.getLogger(__name__)


def _source_display_prefix(kdir: Path) -> str:
    """用于前端展示的源路径前缀（相对仓库根）。"""
    try:
        rel = kdir.resolve().relative_to(project_root().resolve())
        s = str(rel).replace("\\", "/").strip("/")
        return f"{s}/" if s else ""
    except ValueError:
        return ""


class KnowledgeBundle:
    def __init__(
        self,
        index: BM25KnowledgeIndex,
        quick_items: list[QuickQuestionItem],
        quick_by_id: dict[str, QuickQuestionItem],
        *,
        knowledge_dir: Path,
        source_prefix: str,
        chunk_count: int,
    ) -> None:
        self.index = index
        self.quick_items = quick_items
        self.quick_by_id = quick_by_id
        self.knowledge_dir = knowledge_dir
        self.source_prefix = source_prefix
        self.chunk_count = chunk_count


_bundle: KnowledgeBundle | None = None


def default_knowledge_dir() -> Path:
    if settings.ai_knowledge_dir:
        return Path(settings.ai_knowledge_dir).expanduser().resolve()
    return project_root() / "docs" / "knowledge-base"


def init_knowledge_bundle() -> KnowledgeBundle:
    global _bundle
    kdir = default_knowledge_dir()
    docs = load_markdown_dir(kdir, chunk_max_chars=settings.ai_kb_chunk_max_chars)
    index = BM25KnowledgeIndex(docs)
    items, by_id = load_quick_questions(kdir / "quick_questions.yaml")
    prefix = _source_display_prefix(kdir)
    _bundle = KnowledgeBundle(
        index=index,
        quick_items=items,
        quick_by_id=by_id,
        knowledge_dir=kdir,
        source_prefix=prefix,
        chunk_count=len(docs),
    )
    logger.info(
        "知识库已加载：目录=%s，切块数=%s，快捷问题=%s",
        kdir,
        len(docs),
        len(items),
    )
    return _bundle


def reload_knowledge_bundle() -> KnowledgeBundle:
    """开发或热更新场景下重建索引（会替换全局单例）。"""
    global _bundle
    _bundle = None
    return init_knowledge_bundle()


def get_knowledge_bundle() -> KnowledgeBundle:
    global _bundle
    if _bundle is None:
        return init_knowledge_bundle()
    return _bundle
