"""公共验证入口支持的输出种类。"""

from __future__ import annotations

from enum import StrEnum


class OutputKind(StrEnum):
    """已实现的结构输出种类。后续 ticket 只在此追加成员。"""

    BOUNDARY = "boundary"
