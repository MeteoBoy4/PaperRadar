"""价值预测使用的受控价值类型 vocabulary。"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType


class ValueType(StrEnum):
    """价值预测允许返回的七类受控价值。"""

    METHOD = "method"
    DATA = "data"
    CODE_TOOL = "code_tool"
    THEORY_MECHANISM = "theory_mechanism"
    EVIDENCE_CONCLUSION = "evidence_conclusion"
    QUESTION_HYPOTHESIS = "question_hypothesis"
    REVIEW_KNOWLEDGE_MAP = "review_knowledge_map"


VALUE_TYPE_DESCRIPTIONS_ZH = MappingProxyType(
    {
        ValueType.METHOD: "方法",
        ValueType.DATA: "数据",
        ValueType.CODE_TOOL: "代码/工具",
        ValueType.THEORY_MECHANISM: "理论/机制",
        ValueType.EVIDENCE_CONCLUSION: "证据/结论",
        ValueType.QUESTION_HYPOTHESIS: "问题/假设",
        ValueType.REVIEW_KNOWLEDGE_MAP: "综述/知识地图",
    }
)
