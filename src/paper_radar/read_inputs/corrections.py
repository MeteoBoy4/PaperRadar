"""Read 任务唯一使用的安全修正构造;不复制坏 ID、原文或自由键。"""

import re
from collections.abc import Iterable

from paper_radar.llm import CallDescriptionError, DescriptionReason
from paper_radar.llm.read_limits import (
    CORRECTION_CATEGORIES,
    CORRECTION_CATEGORY_SLOTS,
    CORRECTION_PATH_CHARACTERS,
)
from paper_radar.reading.acceptance_v2 import ReadV2Category, ReadV2Issue

# v1 的安全字段集合独立冻结,自由键或未来字段折叠至根位置。
_FIELDS = frozenset(
    {
        "language",
        "summary",
        "main_findings",
        "research_value",
        "research_value_reason",
        "reuse_feasibility",
        "reuse_feasibility_reason",
        "value_types",
        "reusable_points",
        "key_limitations",
        "required_adaptations",
        "open_questions",
        "degraded_content_warnings",
        "text",
        "evidence",
        "evidence_id",
        "kind",
        "description",
        "reason",
        "title",
    }
)
_PATH = re.compile(r"\$(?:\.[a-z_]+|\[[0-9]{1,19}\])*")


def build_read_correction(issues: Iterable[ReadV2Issue]) -> str:
    """每安全类别至多一位置;长/自由路径统一折叠为 $,不截取原文。"""
    selected: dict[str, str] = {}
    for issue in issues:
        if type(issue) is not ReadV2Issue or type(issue.category) is not ReadV2Category:
            raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
        location = issue.location
        if (
            type(location) is not str
            or len(location) > CORRECTION_PATH_CHARACTERS
            or not _PATH.fullmatch(location)
            or any(part not in _FIELDS for part in re.findall(r"\.([a-z_]+)", location))
        ):
            location = "$"
        category = issue.category.value
        if category not in CORRECTION_CATEGORIES:
            raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
        selected[category] = min(selected.get(category, location), location)
    if len(selected) > CORRECTION_CATEGORY_SLOTS:
        raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
    return "请修正以下 Read 输出类别与位置，重新提交完整 JSON：\n" + "\n".join(
        f"{category}: {selected[category]}" for category in sorted(selected)
    )
