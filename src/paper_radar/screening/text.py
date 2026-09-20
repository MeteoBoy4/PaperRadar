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

INSUFFICIENT_INPUT_MARKERS = frozenset(
    {
        "当前输入不足",
        "信息不足",
        "摘要未说明",
        "摘要未提供",
        "摘要未披露",
        "仅凭摘要无法判断",
        "无法从摘要判断",
        "insufficient information",
        "not reported in the abstract",
        "not provided in the abstract",
        "not disclosed in the abstract",
        "unclear from the abstract",
    }
)


def is_meaningful_text(value: str) -> bool:
    """判断文本是否既非空白且不是完整的明确占位文本。"""
    comparison_value = value.strip().casefold()
    return bool(comparison_value) and comparison_value not in EXPLICIT_PLACEHOLDER_TEXTS


def states_input_is_insufficient(value: str) -> bool:
    """按固定短语判定理由是否明确说明摘要层输入不足。"""
    comparison_value = value.casefold()
    return any(marker in comparison_value for marker in INSUFFICIENT_INPUT_MARKERS)
