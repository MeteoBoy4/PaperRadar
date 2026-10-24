"""独立 Pi 1.4.0 合成字节会话;只替换外部通信边界。"""

import copy
import json
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc_types import SessionEvent

BOUNDARY_RAW = ' \n{"boundary":"in_scope","reason_zh":"论文研究天气过程。"}\n '
COMMANDS = (
    "new_session",
    "set_auto_retry",
    "set_auto_compaction",
    "set_model",
    "get_available_thinking_levels",
    "set_thinking_level",
    "get_commands",
    "get_state",
    "prompt",
)


def wire(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
        for record in records
    )


def run_records(
    message: str, system_prompt: str, raw: str, thinking_level: str = "low"
) -> list[dict[str, Any]]:
    """DERIVED-01/03/04:按随包源码独立编写,没有调用产品渲染/解析。"""
    system = {
        "role": "system",
        "content": "",
        "sections": {
            "preamble": system_prompt,
            "cwd": "<cwd>\n/synthetic-neutral\n</cwd>",
        },
        "timestamp": 1,
    }
    user = {
        "role": "user",
        "content": [{"type": "text", "text": message}],
        "timestamp": 2,
    }
    assistant = {
        "role": "assistant",
        "content": [{"type": "text", "text": raw}],
        "api": "openai-completions",
        "provider": "provider-a",
        "model": "real-model",
        "thinkingLevel": thinking_level,
        "stopReason": "stop",
        "timestamp": 3,
        "usage": {
            "input": 4,
            "output": 2,
            "cacheRead": 1,
            "cacheWrite": 0,
            "totalTokens": 7,
            "cost": {
                "input": 0,
                "output": 0,
                "cacheRead": 0,
                "cacheWrite": 0,
                "total": 0,
            },
        },
    }
    partial = {**assistant, "content": [], "stopReason": "pending"}
    return copy.deepcopy(
        [
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "message_start", "message": system},
            {"type": "message_end", "message": system},
            {"type": "message_start", "message": user},
            {"type": "message_end", "message": user},
            {"type": "message_start", "message": partial},
            {"type": "message_end", "message": assistant},
            {"type": "turn_end", "message": assistant, "toolResults": []},
            {
                "type": "agent_end",
                "messages": [system, user, assistant],
                "willRetry": False,
            },
            {"type": "agent_settled", "aborted": False},
        ]
    )


@dataclass
class FakeClock:
    now: float = 0.0

    def __call__(self) -> float:
        return self.now


@dataclass(repr=False)
class ScriptedSession:
    description: CallDescription
    raw: str = BOUNDARY_RAW
    clock: FakeClock = field(default_factory=FakeClock)
    mutate: Callable[[str, list[dict[str, Any]]], list[dict[str, Any]]] | None = None
    fragment: int = 0
    pending: deque[bytes] = field(default_factory=deque)
    commands: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False
    terminated: bool = False
    input_buffer: bytearray = field(default_factory=bytearray)
    encoded_mutate: Callable[[str, bytes], bytes] | None = None
    exit_when_drained: bool = False

    def pump(self, pending: bytes, timeout: float) -> SessionEvent:
        if self.pending:
            assert not pending, "控制命令在上条响应完全消费前到达"
            return SessionEvent(stdout=self.pending.popleft())
        if pending:
            self.input_buffer.extend(pending)
            if self.input_buffer.endswith(b"\n"):
                command = json.loads(self.input_buffer)
                self.input_buffer.clear()
                assert command["type"] == COMMANDS[len(self.commands)]
                self.commands.append(command)
                records = self.responses(command)
                if self.mutate:
                    records = self.mutate(command["type"], records)
                encoded = wire(records)
                if self.encoded_mutate:
                    encoded = self.encoded_mutate(command["type"], encoded)
                if self.fragment:
                    self.pending.extend(
                        encoded[i : i + self.fragment]
                        for i in range(0, len(encoded), self.fragment)
                    )
                elif encoded:
                    self.pending.append(encoded)
            return SessionEvent(written=len(pending))
        if self.closed or (self.exit_when_drained and self.commands):
            return SessionEvent(stdout_eof=True, stderr_eof=True, exit_code=0)
        self.clock.now += timeout
        return SessionEvent()

    def responses(self, command: dict[str, Any]) -> list[dict[str, Any]]:
        name = command["type"]
        response: dict[str, Any] = {
            "id": command["id"],
            "type": "response",
            "command": name,
            "success": True,
        }
        data: dict[str, Any] | None = None
        if name == "new_session":
            data = {"cancelled": False}
        elif name == "set_model":
            assert (
                command["provider"] == "provider-a"
                and command["modelId"] == "real-model"
            )
            data = {"provider": "provider-a", "id": "real-model"}
        elif name == "get_available_thinking_levels":
            data = {"levels": ["off", "low", "high"]}
        elif name == "get_commands":
            data = {"commands": []}
        elif name == "get_state":
            data = {
                "model": {"provider": "provider-a", "id": "real-model"},
                "thinkingLevel": self.description.thinking_level,
                "autoCompactionEnabled": False,
                "isStreaming": False,
                "isCompacting": False,
                "messageCount": 0,
                "pendingMessageCount": 0,
            }
        elif name == "set_thinking_level":
            assert command["level"] == self.description.thinking_level
        elif name in {"set_auto_retry", "set_auto_compaction"}:
            assert command["enabled"] is False
        elif name == "prompt":
            data = {"disposition": "started"}
        if data is not None:
            response["data"] = data
        if name == "prompt":
            return [
                response,
                *run_records(
                    command["message"],
                    self.description.system_prompt.decode(),
                    self.raw,
                    self.description.thinking_level,
                ),
            ]
        if name == "set_model":
            # set_model 重置档位的源码推导通知;客户端随后必须重新设置请求的档位。
            return [{"type": "thinking_level_changed", "level": "off"}, response]
        if name == "set_thinking_level":
            return [
                {
                    "type": "thinking_level_changed",
                    "level": self.description.thinking_level,
                },
                response,
            ]
        return [response]

    def close_stdin(self) -> None:
        self.closed = True

    def terminate(self, timeout: float) -> None:
        self.terminated = True
        self.closed = True


@dataclass(repr=False)
class FakeFactory:
    clock: FakeClock = field(default_factory=FakeClock)
    raw: str = BOUNDARY_RAW
    mutate: Callable[[str, list[dict[str, Any]]], list[dict[str, Any]]] | None = None
    fragment: int = 0
    sessions: list[ScriptedSession] = field(default_factory=list)
    encoded_mutate: Callable[[str, bytes], bytes] | None = None
    exit_when_drained: bool = False
    prelude: bytes = b""

    def __call__(self, description: CallDescription) -> ScriptedSession:
        session = ScriptedSession(
            description, self.raw, self.clock, self.mutate, self.fragment
        )
        session.encoded_mutate = self.encoded_mutate
        session.exit_when_drained = self.exit_when_drained
        if self.prelude:
            size = self.fragment or len(self.prelude)
            session.pending.extend(
                self.prelude[i : i + size] for i in range(0, len(self.prelude), size)
            )
        self.sessions.append(session)
        return session
