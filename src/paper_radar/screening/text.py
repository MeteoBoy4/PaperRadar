"""Screening 输出共用的确定性文本规则。"""

from __future__ import annotations

EXPLICIT_PLACEHOLDER_TEXTS = frozenset(
    {
        "无",
        "暂无",
        "未知",
        "待定",
        "待补充",
        "稍后补充",
        "占位",
        "无内容",
        "不详",
        "-",
        "--",
        "...",
        "…",
        "n/a",
        "na",
        "tbd",
        "todo",
        "placeholder",
    }
)


def is_meaningful_text(value: str) -> bool:
    """判断文本是否既非空白且不是完整的明确占位文本。"""
    comparison_value = value.strip().casefold()
    return bool(comparison_value) and comparison_value not in EXPLICIT_PLACEHOLDER_TEXTS
