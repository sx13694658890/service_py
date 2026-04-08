import re

# 中文连续字 + 英文/数字词（含点号、连字符、下划线）
_TOKEN_RE = re.compile(
    r"[\u4e00-\u9fff]+|[a-z0-9][a-z0-9._-]*",
    re.IGNORECASE,
)
_IS_CJK = re.compile(r"^[\u4e00-\u9fff]+$")


def _expand_cjk(seg: str) -> list[str]:
    """长中文串补充二元组，便于 BM25 命中查询中的子串（如「登录密码」）。"""
    if len(seg) <= 1:
        return [seg] if seg else []
    if len(seg) == 2:
        return [seg]
    parts = [seg]
    for i in range(len(seg) - 1):
        parts.append(seg[i : i + 2])
    return parts


def tokenize(text: str) -> list[str]:
    """中英文分词，供 BM25 使用。"""
    if not text:
        return []
    out: list[str] = []
    for m in _TOKEN_RE.finditer(text.lower()):
        g = m.group(0)
        if _IS_CJK.match(g):
            out.extend(_expand_cjk(g))
        else:
            out.append(g)
    return out
