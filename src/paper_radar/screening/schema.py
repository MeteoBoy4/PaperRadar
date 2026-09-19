"""Screening 结构输出的权威 Pydantic 定义。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class BoundaryOutput(BaseModel):
    """Screening 第一阶段的研究边界判断。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    boundary: Literal["in_scope", "out_of_scope", "uncertain"]
    reason_zh: str
