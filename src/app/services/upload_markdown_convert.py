"""将管理员上传的文件统一转为 Markdown 文本（.md 原文 / .docx 经 mammoth）。"""

from __future__ import annotations

import io
import logging

import mammoth

logger = logging.getLogger(__name__)

# .md 保持较小；.docx 可能含样式与嵌入内容，单独放宽
MAX_UPLOAD_BYTES_MD = 2 * 1024 * 1024
MAX_UPLOAD_BYTES_DOCX = 10 * 1024 * 1024


class UploadMarkdownConvertError(Exception):
    """无法得到可用的 Markdown 正文（供接口返回 422）。"""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def max_upload_bytes_for_filename(filename: str) -> int:
    fn = (filename or "").lower()
    if fn.endswith(".docx"):
        return MAX_UPLOAD_BYTES_DOCX
    return MAX_UPLOAD_BYTES_MD


def convert_upload_to_markdown(raw: bytes, filename: str) -> str:
    """
    - `.md`：按 UTF-8 解码。
    - `.docx`：使用 mammoth 转为 Markdown（版式为近似，复杂表格/文本框可能需人工校对）。
    - `.doc`：不支持，提示另存为 .docx。
    """
    fn = (filename or "").lower()
    if fn.endswith(".md"):
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise UploadMarkdownConvertError("文件须为 UTF-8 编码的 Markdown") from e

    if fn.endswith(".docx"):
        try:
            result = mammoth.convert_to_markdown(io.BytesIO(raw))
        except Exception as e:
            logger.warning("mammoth convert failed: %s", e)
            raise UploadMarkdownConvertError(
                "Word 文档无法解析，请确认是否为有效的 .docx 文件"
            ) from e
        if result.messages:
            logger.debug("mammoth messages: %s", result.messages)
        md = (result.value or "").strip()
        if not md:
            raise UploadMarkdownConvertError(
                "Word 转 Markdown 结果为空（可能仅有图片或无正文），请补充文字或改用 .md"
            )
        return md

    if fn.endswith(".doc"):
        raise UploadMarkdownConvertError(
            "暂不支持旧版 .doc，请在 Word 中「另存为」.docx，或导出为 Markdown 后再上传"
        )

    raise UploadMarkdownConvertError("仅支持 .md 或 .docx（Word 2007+）")
