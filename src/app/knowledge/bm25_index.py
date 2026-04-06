from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.knowledge.tokenize import tokenize


@dataclass
class RetrievedChunk:
    path: str
    title: str
    text: str
    score: float


class BM25KnowledgeIndex:
    def __init__(self, documents: list[dict]) -> None:
        self._documents = documents
        self._tokenized = [tokenize(f"{d['title']}\n{d['text']}") for d in documents]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def search(self, query: str, top_k: int = 5) -> list[RetrievedChunk]:
        if not self._bm25 or not query.strip():
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        out: list[RetrievedChunk] = []
        for idx, score in ranked:
            if score <= 0:
                continue
            d = self._documents[idx]
            out.append(
                RetrievedChunk(
                    path=d["path"],
                    title=d["title"],
                    text=d["text"][:2000],
                    score=float(score),
                )
            )
        return out
