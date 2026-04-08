from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.knowledge.tokenize import tokenize


@dataclass
class RetrievedChunk:
    path: str
    title: str
    text: str
    score: float


def _title_query_overlap_boost(title: str, query: str) -> float:
    """标题与查询共有词越多，略抬高得分（有限上限）。"""
    tset = set(tokenize(title))
    qset = set(tokenize(query))
    if not tset or not qset:
        return 1.0
    n = len(tset & qset)
    return 1.0 + min(n, 5) * 0.06


class BM25KnowledgeIndex:
    def __init__(self, documents: list[dict]) -> None:
        self._documents = documents
        self._tokenized = [tokenize(f"{d['title']}\n{d['text']}") for d in documents]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def search(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k if top_k is not None else settings.ai_top_k
        excerpt = max(500, settings.ai_kb_excerpt_chars)
        min_ratio = settings.ai_kb_min_score_ratio
        max_per_path = max(1, settings.ai_kb_max_per_path)

        if not self._bm25 or not query.strip():
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        best = float(ranked[0][1]) if ranked else 0.0
        floor = (best * min_ratio) if (min_ratio > 0 and best > 0) else None

        out: list[RetrievedChunk] = []
        per_path: dict[str, int] = {}
        for idx, raw_score in ranked:
            if len(out) >= top_k:
                break
            if raw_score <= 0:
                continue
            if floor is not None and float(raw_score) < floor:
                continue
            d = self._documents[idx]
            path = str(d["path"])
            if per_path.get(path, 0) >= max_per_path:
                continue
            boosted = float(raw_score) * _title_query_overlap_boost(str(d["title"]), query)
            per_path[path] = per_path.get(path, 0) + 1
            out.append(
                RetrievedChunk(
                    path=path,
                    title=str(d["title"]),
                    text=str(d["text"])[:excerpt],
                    score=boosted,
                )
            )
        return out
