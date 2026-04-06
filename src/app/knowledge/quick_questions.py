from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class QuickQuestionItem:
    id: str
    label: str
    retrieval_query: str | None
    graph_route: str | None


def load_quick_questions(yaml_path: Path) -> tuple[list[QuickQuestionItem], dict[str, QuickQuestionItem]]:
    if not yaml_path.is_file():
        return [], {}
    data: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    raw_items = data.get("items") or []
    items: list[QuickQuestionItem] = []
    by_id: dict[str, QuickQuestionItem] = {}
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        qid = str(row.get("id", "")).strip()
        label = str(row.get("label", "")).strip()
        if not qid or not label:
            continue
        rq = row.get("retrieval_query")
        gr = row.get("graph_route")
        item = QuickQuestionItem(
            id=qid,
            label=label,
            retrieval_query=str(rq).strip() if rq else None,
            graph_route=str(gr).strip() if gr else None,
        )
        items.append(item)
        by_id[qid] = item
    return items, by_id
