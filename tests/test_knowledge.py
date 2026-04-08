from pathlib import Path

from app.knowledge.bm25_index import BM25KnowledgeIndex
from app.knowledge.loader import load_markdown_dir
from app.knowledge.tokenize import tokenize


def test_tokenize_mixed() -> None:
    assert "hello" in tokenize("Hello API-key_v2")
    assert any("\u4e2d" in t or t == "中文" for t in tokenize("中文测试"))


def test_loader_splits_h2_and_respects_max_chunk(tmp_path: Path) -> None:
    d = tmp_path / "kb"
    d.mkdir()
    big = "段落A\n\n" + ("x" * 500 + "\n\n") * 30
    (d / "a.md").write_text(
        f"# DocTitle\n\nintro line\n\n## Sec1\n\n{big}\n\n## Sec2\n\nshort",
        encoding="utf-8",
    )
    chunks = load_markdown_dir(d, chunk_max_chars=800)
    titles = [c["title"] for c in chunks]
    assert any("DocTitle" in t or "1/" in t for t in titles)
    assert all(len(c["text"]) <= 850 for c in chunks)


def test_bm25_search_filters_and_diversifies() -> None:
    docs = [
        {"path": "a.md", "title": "登录 密码", "text": "如何重置登录密码与账号安全"},
        {"path": "a.md", "title": "其他", "text": "无关内容香蕉苹果"},
        {"path": "b.md", "title": "订阅", "text": "套餐与续费说明"},
    ]
    idx = BM25KnowledgeIndex(docs)
    hits = idx.search("登录密码怎么改", top_k=5)
    paths = [h.path for h in hits]
    assert paths.count("a.md") <= 2
    assert any("登录" in h.title for h in hits)
