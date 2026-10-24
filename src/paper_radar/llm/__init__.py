"""有界模型调用的公共描述边界;当前只支持离线协议组合。"""

from paper_radar.llm.calls import build_call, render_request
from paper_radar.llm.models import (
    MAX_REQUEST_BYTES,
    PROTOCOL_PROFILES,
    RENDER_FORMAT,
    REQUEST_HEADER,
    CallDescription,
    CallDescriptionError,
    DescriptionReason,
)

__all__ = [
    "MAX_REQUEST_BYTES",
    "PROTOCOL_PROFILES",
    "RENDER_FORMAT",
    "REQUEST_HEADER",
    "CallDescription",
    "CallDescriptionError",
    "DescriptionReason",
    "build_call",
    "render_request",
]
