"""单次调用的不可变描述;协议内核只消费这些普通值。"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, get_args

from paper_radar.pi_protocol import PROTOCOL_PROFILES as PROTOCOL_PROFILES

RENDER_FORMAT = 1
MAX_REQUEST_BYTES = 256 * 1024
REQUEST_HEADER = "PaperRadar bounded-rpc-v1\n"
ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh", "max"]
THINKING_LEVELS: frozenset[str] = frozenset(get_args(ThinkingLevel))


class DescriptionReason(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    PROJECTION_MISMATCH = "projection_mismatch"
    CORRUPT_REFERENCE = "corrupt_reference"


class CallDescriptionError(ValueError):
    """只携封闭原因;不保留提交值或外部异常。"""

    def __init__(self, reason: DescriptionReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True, slots=True)
class CallDescription:
    stage: Literal["boundary", "value"]
    fingerprint: str
    projection_id: str
    semantic_snapshot_id: str
    audit_snapshot_id: str
    pi_version: str
    adapter_version: str
    protocol_profile: str
    provider: str = field(repr=False)
    model: str = field(repr=False)
    protocol: Literal["prompt_only"]
    thinking_level: ThinkingLevel
    temperature: float | None
    top_p: float | None
    policy_json: str = field(repr=False)
    system_prompt: bytes = field(repr=False)
    stage_input_payload: bytes = field(repr=False)
    user_payload_json: str = field(repr=False)
    sampling: Literal["explicit", "provider_default"] = "explicit"
    render_format: Literal[1] = field(default=1, init=False)
