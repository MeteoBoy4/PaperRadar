"""复用升级使用的受控摘录种类 vocabulary。"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator


class ExcerptKind(StrEnum):
    """复用升级输出允许声明的摘录种类。"""

    AVAILABILITY = "availability"
    METHODS = "methods"
    BOTH = "both"


def _require_excerpt_kind_string(value: object) -> object:
    if isinstance(value, ExcerptKind) or type(value) is str:
        return value
    raise ValueError("摘录种类必须使用字符串序列化值")


def _require_context_excerpt_kind(value: ExcerptKind) -> ExcerptKind:
    if value is ExcerptKind.BOTH:
        raise ValueError("上下文摘录种类只允许 availability 或 methods")
    return value


StrictExcerptKind = Annotated[
    ExcerptKind,
    BeforeValidator(_require_excerpt_kind_string),
]
ContextExcerptKind = Annotated[
    StrictExcerptKind,
    AfterValidator(_require_context_excerpt_kind),
]
