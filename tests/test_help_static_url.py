from app.services.help_document_files import public_static_url_for_upload


def test_public_static_url_for_upload() -> None:
    u = public_static_url_for_upload("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.md")
    assert u == "/static/help-documents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa.md"


def test_public_static_url_none() -> None:
    assert public_static_url_for_upload(None) is None
    assert public_static_url_for_upload("") is None
