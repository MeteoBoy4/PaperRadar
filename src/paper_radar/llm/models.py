"""单次调用的不可变描述;协议内核只消费这些普通值。"""

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

# 只声明离线协议支持;不授予真实 RPC 或生产执行资格。
PROTOCOL_PROFILES = MappingProxyType({"1.4.0": "pi-rpc-1.4.0-v1"})
RENDER_FORMAT = 1
MAX_REQUEST_BYTES = 256 * 1024
REQUEST_HEADER = "PaperRadar bounded-rpc-v1\n"


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
    thinking_level: str
    temperature: float
    top_p: float
    policy_json: str = field(repr=False)
    system_prompt: bytes = field(repr=False)
    stage_input_payload: bytes = field(repr=False)
    user_payload_json: str = field(repr=False)
    render_format: Literal[1] = field(default=1, init=False)
