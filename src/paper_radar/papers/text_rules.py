"""纯文本规范形式 v1;供输入与 Feed 身份规则共同使用。"""

import re

from paper_radar.papers.errors import PaperError, PaperReason

_MARKUP = re.compile(
    r"<!--|<![A-Za-z]|<\?|</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>]*|\s*/?)>"
)


def normalize_text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise PaperError(PaperReason.INVALID_TEXT, path="fields") from None
    if _MARKUP.search(value):
        raise PaperError(PaperReason.INVALID_TEXT, path="fields")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()
