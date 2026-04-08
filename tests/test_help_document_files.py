import pytest

from app.services.help_document_files import (
    read_doc_file,
    read_uploaded_doc_file,
    resolve_safe_doc_path,
)


def test_resolve_rejects_parent_segments() -> None:
    with pytest.raises(ValueError):
        resolve_safe_doc_path("../pyproject.toml")
    with pytest.raises(ValueError):
        resolve_safe_doc_path("foo/../../etc/passwd")


def test_read_doc_file_real_repo_file() -> None:
    text = read_doc_file("文档需求/REQUIREMENTS.md")
    assert text is not None
    assert "文档中心" in text


def test_read_uploaded_doc_file(tmp_path, monkeypatch) -> None:
    uid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    p = tmp_path / f"{uid}.md"
    p.write_text("# 上传", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.help_document_files.uploaded_help_docs_root",
        lambda: tmp_path,
    )
    t = read_uploaded_doc_file(f"{uid}.md")
    assert t == "# 上传"


def test_read_uploaded_rejects_traversal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.services.help_document_files.uploaded_help_docs_root", lambda: tmp_path)
    assert read_uploaded_doc_file("../x.md") is None
