"""Pi 1.4.0 单回合事件核对;只提取完整最终文本与安全观察。"""

import math
from typing import Any

from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc_types import (
    MAX_CANDIDATE_BYTES,
    RpcCandidate,
    RpcProblem,
    RpcReason,
)

_EVENTS = (
    "agent_start",
    "turn_start",
    "message_start",
    "message_end",
    "message_start",
    "message_end",
    "message_start",
    "message_end",
    "turn_end",
    "agent_end",
    "agent_settled",
)
_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh", "max"}
_STOPS = {"pending", "stop", "length", "toolUse", "error", "aborted", "deferred"}


def _string(value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _number(value: object) -> bool:
    if type(value) is int:
        return value >= 0
    return type(value) is float and math.isfinite(value) and value >= 0


def _same_json(left: object, right: object) -> bool:
    """完整副本比较保留 JSON 类型,不把 true/1 或 false/0 合并。"""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _same_json(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _same_json(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _timestamp(message: dict[str, Any]) -> None:
    if not _number(message.get("timestamp")):
        raise RpcProblem(RpcReason.MESSAGE_SHAPE)


def _usage(message: dict[str, Any]) -> tuple[int | None, int | None]:
    usage = message.get("usage")
    names = ("input", "output", "cacheRead", "cacheWrite", "totalTokens")
    if not isinstance(usage, dict) or any(
        type(usage.get(name)) is not int or usage[name] < 0 for name in names
    ):
        raise RpcProblem(RpcReason.USAGE_SHAPE)
    if any(
        name in usage and (type(usage[name]) is not int or usage[name] < 0)
        for name in ("reasoning", "cacheWrite1h")
    ):
        raise RpcProblem(RpcReason.USAGE_SHAPE)
    cost = usage.get("cost")
    if not isinstance(cost, dict) or any(
        not _number(cost.get(name))
        for name in ("input", "output", "cacheRead", "cacheWrite", "total")
    ):
        raise RpcProblem(RpcReason.USAGE_SHAPE)
    total = usage["input"] + usage["output"] + usage["cacheRead"] + usage["cacheWrite"]
    if usage["totalTokens"] != total:
        raise RpcProblem(RpcReason.USAGE_SHAPE)
    if not total:
        return None, None
    return usage["input"] + usage["cacheRead"] + usage["cacheWrite"], usage["output"]


class RunEvents:
    def __init__(self, description: CallDescription, user_message: str) -> None:
        self._description = description
        self._user_message = user_message
        self._position = 0
        self._system: dict[str, Any] | None = None
        self._user: dict[str, Any] | None = None
        self._final: dict[str, Any] | None = None
        self.candidate: RpcCandidate | None = None

    @property
    def settled(self) -> bool:
        return self._position == len(_EVENTS)

    def accept(self, record: dict[str, Any]) -> None:
        kind = record.get("type")
        if kind == "message_update" and self._position == 7:
            self._update(record)
            return
        if kind not in _EVENTS:
            raise RpcProblem(RpcReason.EVENT_NOT_ALLOWED)
        if self.settled or kind != _EVENTS[self._position]:
            raise RpcProblem(RpcReason.EVENT_SEQUENCE)
        if self._position in (2, 3):
            self._system_message(record)
        elif self._position in (4, 5):
            self._user_message_event(record)
        elif self._position in (6, 7):
            self._assistant_message(record)
        elif self._position == 8:
            if (
                not _same_json(record.get("message"), self._final)
                or record.get("toolResults") != []
            ):
                raise RpcProblem(RpcReason.MESSAGE_MISMATCH)
        elif self._position == 9:
            if not _same_json(
                record.get("messages"), [self._system, self._user, self._final]
            ):
                raise RpcProblem(RpcReason.MESSAGE_MISMATCH)
            if record.get("willRetry") is not False:
                raise RpcProblem(RpcReason.EVENT_SEQUENCE)
        elif self._position == 10 and record.get("aborted") is not False:
            raise RpcProblem(RpcReason.EVENT_SEQUENCE)
        self._position += 1

    def _message(self, record: dict[str, Any], role: str) -> dict[str, Any]:
        message = record.get("message")
        if not isinstance(message, dict) or message.get("role") != role:
            raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        _timestamp(message)
        return message

    def _system_message(self, record: dict[str, Any]) -> None:
        message = self._message(record, "system")
        sections = message.get("sections")
        if (
            message.get("content") != ""
            or "toolsAdded" in message
            or "toolsRemoved" in message
            or not isinstance(sections, dict)
            or set(sections) != {"preamble", "cwd"}
            or sections.get("preamble")
            != self._description.system_prompt.decode("utf-8")
            or not isinstance(sections.get("cwd"), str)
        ):
            raise RpcProblem(RpcReason.SYSTEM_MISMATCH)
        if self._system is None:
            self._system = message
        elif not _same_json(message, self._system):
            raise RpcProblem(RpcReason.MESSAGE_MISMATCH)

    def _user_message_event(self, record: dict[str, Any]) -> None:
        message = self._message(record, "user")
        content = message.get("content")
        if (
            not isinstance(content, list)
            or len(content) != 1
            or not isinstance(content[0], dict)
            or content[0].get("type") != "text"
            or content[0].get("text") != self._user_message
        ):
            raise RpcProblem(RpcReason.USER_MISMATCH)
        if self._user is None:
            self._user = message
        elif not _same_json(message, self._user):
            raise RpcProblem(RpcReason.MESSAGE_MISMATCH)

    def _assistant_message(self, record: dict[str, Any]) -> None:
        message = self._message(record, "assistant")
        if any(not _string(message.get(name)) for name in ("api", "provider", "model")):
            raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        if (
            not isinstance(message.get("stopReason"), str)
            or message["stopReason"] not in _STOPS
        ):
            raise RpcProblem(RpcReason.STOP_REASON)
        level = message.get("thinkingLevel")
        if "thinkingLevel" in message and (
            not isinstance(level, str)
            or level not in _LEVELS
            or level != self._description.thinking_level
        ):
            raise RpcProblem(RpcReason.THINKING_STATE)
        for name in ("responseModel", "responseId", "providerThinkingLevel"):
            if name in message and not _string(message[name]):
                raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        content = message.get("content")
        if not isinstance(content, list):
            raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        texts = []
        for block in content:
            if (
                not isinstance(block, dict)
                or not isinstance(block.get("type"), str)
                or block["type"] not in {"text", "thinking"}
            ):
                raise RpcProblem(RpcReason.CHANNEL)
            name = "text" if block["type"] == "text" else "thinking"
            if not isinstance(block.get(name), str):
                raise RpcProblem(RpcReason.MESSAGE_SHAPE)
            signature = "textSignature" if name == "text" else "thinkingSignature"
            if signature in block and not isinstance(block[signature], str):
                raise RpcProblem(RpcReason.MESSAGE_SHAPE)
            if (
                name == "thinking"
                and "redacted" in block
                and type(block["redacted"]) is not bool
            ):
                raise RpcProblem(RpcReason.MESSAGE_SHAPE)
            if name == "text":
                texts.append(block[name])
        tokens = _usage(message)
        if self._position == 6:
            if message["stopReason"] != "pending":
                raise RpcProblem(RpcReason.STOP_REASON)
            return
        if message["stopReason"] != "stop":
            raise RpcProblem(RpcReason.STOP_REASON)
        if not texts:
            raise RpcProblem(RpcReason.CHANNEL)
        try:
            raw = "".join(texts).encode("utf-8")
        except UnicodeError:
            raise RpcProblem(RpcReason.MESSAGE_SHAPE) from None
        if len(raw) > MAX_CANDIDATE_BYTES:
            raise RpcProblem(RpcReason.CANDIDATE_LIMIT)
        self._final = message
        self.candidate = RpcCandidate(
            raw,
            message["provider"],
            message.get("responseModel", message["model"]),
            *tokens,
        )

    def _update(self, record: dict[str, Any]) -> None:
        event = record.get("assistantMessageEvent")
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("type"), str)
            or event["type"]
            not in {
                "text_start",
                "text_delta",
                "text_end",
                "thinking_start",
                "thinking_delta",
                "thinking_end",
            }
        ):
            raise RpcProblem(RpcReason.EVENT_NOT_ALLOWED)
        if type(event.get("contentIndex")) is not int or event["contentIndex"] < 0:
            raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        kind = event["type"]
        if kind.endswith("_delta") and not isinstance(event.get("delta"), str):
            raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        if kind.endswith("_end") and not isinstance(event.get("content"), str):
            raise RpcProblem(RpcReason.MESSAGE_SHAPE)
        _usage(record)
