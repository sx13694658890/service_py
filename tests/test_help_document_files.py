import pytest

from app.services.help_document_files import read_doc_file, resolve_safe_doc_path


def test_resolve_rejects_parent_segments() -> None:
    with pytest.raises(ValueError):
        resolve_safe_doc_path("../pyproject.toml")
    with pytest.raises(ValueError):
        resolve_safe_doc_path("foo/../../etc/passwd")


def test_read_doc_file_real_repo_file() -> None:
    text = read_doc_file("文档需求/REQUIREMENTS.md")
    assert text is not None
    assert "文档中心" in text
