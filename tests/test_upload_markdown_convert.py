import io

import pytest

from app.services.upload_markdown_convert import (
    UploadMarkdownConvertError,
    convert_upload_to_markdown,
    max_upload_bytes_for_filename,
)


def test_max_bytes_docx_vs_md() -> None:
    assert max_upload_bytes_for_filename("a.docx") > max_upload_bytes_for_filename("a.md")


def test_convert_md_utf8() -> None:
    assert convert_upload_to_markdown("# 标题\n\n正文".encode("utf-8"), "x.md") == "# 标题\n\n正文"


def test_convert_rejects_doc() -> None:
    with pytest.raises(UploadMarkdownConvertError) as e:
        convert_upload_to_markdown(b"x", "old.doc")
    assert "docx" in e.value.detail


def test_convert_docx_uses_mammoth(monkeypatch: pytest.MonkeyPatch) -> None:
    class _R:
        value = "## Hello\n\nworld"
        messages: list = []

    def _fake(_bio: io.BytesIO):
        return _R()

    monkeypatch.setattr("mammoth.convert_to_markdown", _fake)
    out = convert_upload_to_markdown(b"fakezip", "f.docx")
    assert "Hello" in out
