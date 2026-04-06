from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.paths import project_root
from app.knowledge.bm25_index import BM25KnowledgeIndex
from app.knowledge.loader import load_markdown_dir
from app.knowledge.quick_questions import QuickQuestionItem, load_quick_questions


class KnowledgeBundle:
    def __init__(
        self,
        index: BM25KnowledgeIndex,
        quick_items: list[QuickQuestionItem],
        quick_by_id: dict[str, QuickQuestionItem],
    ) -> None:
        self.index = index
        self.quick_items = quick_items
        self.quick_by_id = quick_by_id


_bundle: KnowledgeBundle | None = None


def default_knowledge_dir() -> Path:
    if settings.ai_knowledge_dir:
        return Path(settings.ai_knowledge_dir).expanduser().resolve()
    return project_root() / "docs" / "ai问答需求"


def init_knowledge_bundle() -> KnowledgeBundle:
    global _bundle
    kdir = default_knowledge_dir()
    docs = load_markdown_dir(kdir)
    index = BM25KnowledgeIndex(docs)
    items, by_id = load_quick_questions(kdir / "quick_questions.yaml")
    _bundle = KnowledgeBundle(index=index, quick_items=items, quick_by_id=by_id)
    return _bundle


def get_knowledge_bundle() -> KnowledgeBundle:
    global _bundle
    if _bundle is None:
        return init_knowledge_bundle()
    return _bundle
