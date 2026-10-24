"""RPC 单次调用的封闭结果、有限资源与显式字节会话。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from paper_radar.llm.models import CallDescription

MAX_FRAME_BYTES = 4 * 1024 * 1024
MAX_STDOUT_BYTES = 16 * 1024 * 1024
MAX_STDERR_BYTES = 1024 * 1024
MAX_CANDIDATE_BYTES = 64 * 1024
INITIALIZATION_SECONDS = 30.0
TOTAL_SECONDS = 300.0
CLOSE_SECONDS = 10.0
TERMINATE_SECONDS = 10.0


class RpcCategory(StrEnum):
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    ENVIRONMENT = "environment"
    PROTOCOL = "protocol"


class RpcReason(StrEnum):
    INVALID_DESCRIPTION = "invalid_description"
    INVALID_UTF8 = "invalid_utf8"
    INVALID_JSON = "invalid_json"
    NON_OBJECT = "non_object"
    DUPLICATE_KEY = "duplicate_key"
    NON_FINITE = "non_finite"
    FRAME_LIMIT = "frame_limit"
    STDOUT_LIMIT = "stdout_limit"
    STDERR_LIMIT = "stderr_limit"
    REQUEST_LIMIT = "request_limit"
    CANDIDATE_LIMIT = "candidate_limit"
    PARTIAL_FRAME = "partial_frame"
    EARLY_RECORD = "early_record"
    RESPONSE_MISMATCH = "response_mismatch"
    COMMAND_REJECTED = "command_rejected"
    MODEL_REJECTED = "model_rejected"
    SESSION_CANCELLED = "session_cancelled"
    MODEL_STATE = "model_state"
    THINKING_UNSUPPORTED = "thinking_unsupported"
    THINKING_STATE = "thinking_state"
    DIRTY_STATE = "dirty_state"
    COMMANDS_PRESENT = "commands_present"
    PROMPT_DISPOSITION = "prompt_disposition"
    EVENT_SEQUENCE = "event_sequence"
    EVENT_NOT_ALLOWED = "event_not_allowed"
    MESSAGE_SHAPE = "message_shape"
    MESSAGE_MISMATCH = "message_mismatch"
    SYSTEM_MISMATCH = "system_mismatch"
    USER_MISMATCH = "user_mismatch"
    STOP_REASON = "stop_reason"
    CHANNEL = "channel"
    USAGE_SHAPE = "usage_shape"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    STARTUP_ERROR = "startup_error"
    TRANSPORT_ERROR = "transport_error"
    EOF = "eof"
    UNEXPECTED_EXIT = "unexpected_exit"
    CLOSE_TIMEOUT = "close_timeout"


@dataclass(frozen=True, slots=True)
class RpcFailure:
    reason: RpcReason

    @property
    def category(self) -> RpcCategory:
        if self.reason in {RpcReason.TIMEOUT, RpcReason.CLOSE_TIMEOUT}:
            return RpcCategory.TIMEOUT
        if self.reason is RpcReason.CANCELLED:
            return RpcCategory.CANCELLED
        if self.reason in {
            RpcReason.SESSION_CANCELLED,
            RpcReason.MODEL_REJECTED,
            RpcReason.STARTUP_ERROR,
            RpcReason.TRANSPORT_ERROR,
            RpcReason.EOF,
            RpcReason.UNEXPECTED_EXIT,
        }:
            return RpcCategory.ENVIRONMENT
        return RpcCategory.PROTOCOL


@dataclass(frozen=True, slots=True)
class RpcCandidate:
    raw_response: bytes = field(repr=False)
    provider: str = field(repr=False)
    model: str = field(repr=False)
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True, slots=True)
class RpcLimits:
    initialization: float = INITIALIZATION_SECONDS
    total: float = TOTAL_SECONDS
    close: float = CLOSE_SECONDS
    terminate: float = TERMINATE_SECONDS
    poll: float = 0.05


DEFAULT_LIMITS = RpcLimits()


@dataclass(frozen=True, slots=True)
class SessionEvent:
    """一次有限推进的观察;stderr 原文由会话丢弃。"""

    written: int = 0
    stdout: bytes = field(default=b"", repr=False)
    stderr_bytes: int = 0
    stdout_eof: bool = False
    stderr_eof: bool = False
    exit_code: int | None = None


class ByteSession(Protocol):
    def pump(self, pending: bytes, timeout: float, /) -> SessionEvent:
        """至多等待 timeout,同时消费两条读管道与部分写;空 pending 不关闭。"""
        ...

    def close_stdin(self) -> None:
        """立即关闭输入,不等待进程。"""
        ...

    def terminate(self, timeout: float, /) -> None:
        """在 timeout 内终止并回收整组,包括已退出 leader 的子孙。"""
        ...


class SessionFactory(Protocol):
    def __call__(self, description: CallDescription, /) -> ByteSession:
        """显式创建专属会话,系统指令作为启动输入;构造须有界。"""
        ...


MonotonicClock = Callable[[], float]
Cancellation = Callable[[], bool]


class RpcProblem(Exception):
    """内部安全控制流;公共入口把它换为 RpcFailure。"""

    def __init__(self, reason: RpcReason) -> None:
        self.reason = reason
        super().__init__(reason.value)
