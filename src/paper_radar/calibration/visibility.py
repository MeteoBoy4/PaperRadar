"""对调用方装配的隐藏事实判定展示与动作许可。"""

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never


class HiddenCondition(StrEnum):
    WAITING_CALIBRATION = "waiting_calibration"
    UNREVEALED = "unrevealed"


class VisibilityCapability(StrEnum):
    PAPER_FACTS = "paper_facts"
    TASK_DETAILS = "task_details"
    AGENT_CONTENT = "agent_content"
    SET_DECISION = "set_decision"
    READING_REQUEST = "reading_request"
    CALIBRATION_REVIEW = "calibration_review"


class VisibilityPermission(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    DEDICATED_PATH = "dedicated_path"


@dataclass(frozen=True)
class Visibility:
    """许可及其受控原因;不携带任何论文或 Agent 载荷。"""

    hidden_conditions: frozenset[HiddenCondition]

    def permission(self, capability: VisibilityCapability) -> VisibilityPermission:
        match capability:
            case VisibilityCapability.PAPER_FACTS | VisibilityCapability.TASK_DETAILS:
                return VisibilityPermission.ALLOWED
            case VisibilityCapability.CALIBRATION_REVIEW:
                return VisibilityPermission.DEDICATED_PATH
            case (
                VisibilityCapability.AGENT_CONTENT
                | VisibilityCapability.SET_DECISION
                | VisibilityCapability.READING_REQUEST
            ):
                return (
                    VisibilityPermission.DENIED
                    if self.hidden_conditions
                    else VisibilityPermission.ALLOWED
                )
            case _:
                assert_never(capability)


def evaluate_visibility(hidden_conditions: frozenset[HiddenCondition]) -> Visibility:
    """输入须沿 Paper 身份/合并链汇总;只计算本次事实的许可。"""
    return Visibility(hidden_conditions)
