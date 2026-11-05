"""single/chunking v1 的冻结完整帧预算。纯计算,不查库、不调用模型。"""

from dataclasses import dataclass
from typing import Literal

from paper_radar.llm import (
    CallDescription,
    CallDescriptionError,
    DescriptionReason,
    render_request,
)
from paper_radar.llm.read_limits import (
    CORRECTION_SLOT_BYTES,
    SINGLE_FRAME_BYTES,
)
from paper_radar.llm.rpc_frames import command_frame


@dataclass(frozen=True, slots=True)
class ReadInputBudget:
    accepted: bool
    first_frame_bytes: int
    correction_frame_bytes: int
    cumulative_frame_bytes: int
    reason: Literal["read_input_over_budget"] | None


def read_input_budget(description: CallDescription) -> ReadInputBudget:
    """两次独立会话的帧都安全才允许领取;修正槽预留覆盖整个外层编码。"""
    if type(description) is not CallDescription or description.stage != "read":
        raise CallDescriptionError(DescriptionReason.INVALID_CONTEXT)
    first = len(
        command_frame(
            "rpc-9", "prompt", message=render_request(description).decode("utf-8")
        )
    )
    # null 替换为双引号字符串,其内容的两层 JSON 编码上界已由槽预算覆盖。
    second = first + CORRECTION_SLOT_BYTES
    accepted = second <= SINGLE_FRAME_BYTES
    return ReadInputBudget(
        accepted,
        first,
        second,
        first + second,
        None if accepted else "read_input_over_budget",
    )
