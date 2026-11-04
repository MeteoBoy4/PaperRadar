"""normalization v1 与 v2 接收器共享的字符可靠性规则。"""

import unicodedata

UNRELIABLE_RULE_VERSION = "normalization-v1-unreliable"


def is_unreliable(text: str, *, declared: bool = False) -> bool:
    return declared or any(
        char == "\ufffd"
        or unicodedata.category(char) in ("Cs", "Co")
        or (unicodedata.category(char) == "Cc" and char not in "\t\r\n")
        for char in text
    )
