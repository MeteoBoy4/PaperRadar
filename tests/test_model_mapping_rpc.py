"""B-E6 独立 D1:公共无 prompt RPC 的合成字节故障对端。"""

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from paper_radar.llm.models import MappingDescription
from paper_radar.llm.rpc import probe_mapping
from paper_radar.llm.rpc_types import RpcFailure, RpcLimits, SessionEvent
from tests.a8_rpc_support import FakeClock


@dataclass
class Peer:
    mode: str
    clock: FakeClock = field(default_factory=FakeClock)
    commands: list[dict[str, Any]] = field(default_factory=list)
    closed: bool = False
    terminated: bool = False

    def pump(self, pending: bytes, timeout: float, /) -> SessionEvent:
        self.clock.now += timeout
        if self.closed:
            return SessionEvent(stdout_eof=True, stderr_eof=True, exit_code=0)
        if not pending:
            return SessionEvent()
        command = json.loads(pending)
        self.commands.append(command)
        kind = command["type"]
        assert kind != "prompt", "映射探测发送了 prompt"
        if self.mode == "timeout":
            return SessionEvent(written=len(pending))
        data: dict[str, Any] = {}
        if kind == "new_session":
            data = {"cancelled": False}
        elif kind == "set_model":
            data = {"provider": "openai", "id": "synthetic-model"}
            if self.mode == "model_unavailable":
                data["id"] = "unselected-model"
        elif kind == "get_available_thinking_levels":
            data = {"levels": ["off"] if self.mode == "unsupported" else ["low"]}
        elif kind == "get_commands":
            data = {"commands": []}
        elif kind == "get_state":
            data = {
                "model": {"provider": "openai", "id": "synthetic-model"},
                "thinkingLevel": "low",
                "autoCompactionEnabled": False,
                "isStreaming": False,
                "isCompacting": False,
                "messageCount": 0,
                "pendingMessageCount": 0,
            }
            if self.mode == "dirty":
                data["messageCount"] = 1
        response = {
            "id": command["id"],
            "type": "response",
            "command": kind,
            "success": not (kind == "set_model" and self.mode == "rejected"),
            "data": data,
        }
        return SessionEvent(
            written=len(pending), stdout=(json.dumps(response) + "\n").encode()
        )

    def close_stdin(self) -> None:
        self.closed = True

    def terminate(self, timeout: float, /) -> None:
        self.terminated = True
        assert 0 <= timeout <= 0.5
        if self.mode == "cleanup_failed":
            raise OSError("PRIVATE_CLEANUP_FAILURE")


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("timeout", "timeout"),
        ("cleanup_failed", "transport_error"),
        ("rejected", "model_rejected"),
        ("model_unavailable", "model_state"),
        ("unsupported", "thinking_unsupported"),
        ("dirty", "dirty_state"),
    ],
)
def test_mapping_faults_never_send_prompt_and_always_reclaim(
    mode: str, reason: str
) -> None:
    peer = Peer(mode)
    description = MappingDescription(
        "screening",
        "a" * 64,
        "1.4.0",
        "pi-rpc-1.4.0-v1",
        "openai",
        "synthetic-model",
        "low",
        b"Public probe instruction\n",
    )
    result = probe_mapping(
        description,
        lambda _: peer,
        clock=peer.clock,
        limits=RpcLimits(initialization=1, total=2, close=0.5, terminate=0.5),
    )
    assert isinstance(result, RpcFailure) and result.reason.value == reason
    assert peer.closed and peer.terminated
    assert {command["type"] for command in peer.commands} <= {
        "new_session",
        "set_auto_retry",
        "set_auto_compaction",
        "set_model",
        "get_available_thinking_levels",
        "set_thinking_level",
        "get_commands",
        "get_state",
    }
    assert all("message" not in command for command in peer.commands)
    assert "PRIVATE_CLEANUP_FAILURE" not in repr(result)


@pytest.mark.parametrize(
    "field,value",
    [("slot", []), ("pi_version", []), ("thinking_level", []), ("provider", 12)],
)
def test_invalid_mapping_description_is_rejected_without_starting_session(
    field: str, value: Any
) -> None:
    from typing import NoReturn

    values: dict[str, Any] = dict(
        slot="screening",
        audit_snapshot_id="a" * 64,
        pi_version="1.4.0",
        protocol_profile="pi-rpc-1.4.0-v1",
        provider="openai",
        model="synthetic-model",
        thinking_level="low",
        system_prompt=b"Public probe instruction\n",
    )
    values[field] = value

    def forbidden(_: MappingDescription) -> NoReturn:
        pytest.fail("非法描述启动了外部会话")

    result = probe_mapping(MappingDescription(**values), forbidden)
    assert (
        isinstance(result, RpcFailure) and result.reason.value == "invalid_description"
    )
