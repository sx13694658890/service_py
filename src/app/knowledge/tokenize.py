import re


def tokenize(text: str) -> list[str]:
    """中英文简单分词，供 BM25 使用。"""
    return re.findall(r"[\u4e00-\u9fff]+|\w+", text.lower())
