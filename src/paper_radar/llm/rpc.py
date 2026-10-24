"""有界单次 Pi RPC;不构造进程、读取配置或决定业务成功。"""

import math
import sys
from collections import deque
from contextlib import suppress
from time import monotonic
from typing import Any

from paper_radar.llm.models import (
    MAX_REQUEST_BYTES,
    PROTOCOL_PROFILES,
    THINKING_LEVELS,
    CallDescription,
)
from paper_radar.llm.rpc_frames import FrameDecoder, command_frame
from paper_radar.llm.rpc_messages import RunEvents
from paper_radar.llm.rpc_types import (
    DEFAULT_LIMITS,
    MAX_STDERR_BYTES,
    MAX_STDOUT_BYTES,
    ByteSession,
    Cancellation,
    MonotonicClock,
    RpcCandidate,
    RpcFailure,
    RpcLimits,
    RpcProblem,
    RpcReason,
    SessionEvent,
    SessionFactory,
)

_PROMPT_COMMAND_NO = 9
_PROMPT_COMMAND_ID = f"rpc-{_PROMPT_COMMAND_NO}"
_PROMPT_COMMAND_NAME = "prompt"


def _prompt_frame(user_message: bytes) -> bytes:
    if type(user_message) is not bytes:
        raise RpcProblem(RpcReason.INVALID_DESCRIPTION)
    try:
        message = user_message.decode("utf-8")
    except UnicodeError:
        raise RpcProblem(RpcReason.INVALID_DESCRIPTION) from None
    frame = command_frame(_PROMPT_COMMAND_ID, _PROMPT_COMMAND_NAME, message=message)
    if len(frame) > MAX_REQUEST_BYTES:
        raise RpcProblem(RpcReason.REQUEST_LIMIT)
    return frame


def validate_request(user_message: bytes) -> RpcFailure | None:
    """领取前可检查真实 prompt 帧大小;不创建会话或检查任务状态。"""
    try:
        _prompt_frame(user_message)
    except RpcProblem as error:
        return RpcFailure(error.reason)
    return None


class _Connection:
    def __init__(
        self,
        session: ByteSession,
        clock: MonotonicClock,
        cancelled: Cancellation,
        limits: RpcLimits,
        started: float,
    ) -> None:
        self.session = session
        self.clock = clock
        self.cancelled = cancelled
        self.limits = limits
        self.total_deadline = started + limits.total
        self.decoder = FrameDecoder()
        self.records: deque[dict[str, Any]] = deque()
        self.stdout_bytes = 0
        self.stderr_bytes = 0
        self.stdout_eof = False
        self.stderr_eof = False
        self.exit_code: int | None = None
        self.command_no = 0
        self.expected_level: str | None = None
        self.write_pending = False
        self.awaiting: tuple[str, str] | None = None
        self.settled = False

    def check(self, deadline: float, *, closing: bool = False) -> float:
        if self.cancelled():
            raise RpcProblem(RpcReason.CANCELLED)
        left = min(deadline, self.total_deadline) - self.clock()
        if left <= 0:
            raise RpcProblem(RpcReason.CLOSE_TIMEOUT if closing else RpcReason.TIMEOUT)
        return left

    def pump(
        self,
        pending: bytes,
        deadline: float,
        *,
        immediate: bool = False,
        closing: bool = False,
    ) -> int:
        left = self.check(deadline, closing=closing)
        event = self.session.pump(
            pending, 0.0 if immediate else min(left, self.limits.poll)
        )
        if (
            type(event) is not SessionEvent
            or type(event.written) is not int
            or not 0 <= event.written <= len(pending)
            or type(event.stdout) is not bytes
            or type(event.stderr_bytes) is not int
            or event.stderr_bytes < 0
            or type(event.stdout_eof) is not bool
            or type(event.stderr_eof) is not bool
            or (event.exit_code is not None and type(event.exit_code) is not int)
        ):
            raise RpcProblem(RpcReason.TRANSPORT_ERROR)
        self.write_pending = event.written < len(pending)
        self.check(deadline, closing=closing)
        if self.stdout_eof and event.stdout:
            raise RpcProblem(RpcReason.TRANSPORT_ERROR)
        self.stdout_bytes += len(event.stdout)
        self.stderr_bytes += event.stderr_bytes
        if self.stdout_bytes > MAX_STDOUT_BYTES:
            raise RpcProblem(RpcReason.STDOUT_LIMIT)
        if self.stderr_bytes > MAX_STDERR_BYTES:
            raise RpcProblem(RpcReason.STDERR_LIMIT)
        self.records.extend(self.decoder.feed(event.stdout))
        if event.stdout_eof:
            self.decoder.finish()
            self.stdout_eof = True
        self.stderr_eof |= event.stderr_eof
        if event.exit_code is not None:
            if self.exit_code is not None and event.exit_code != self.exit_code:
                raise RpcProblem(RpcReason.TRANSPORT_ERROR)
            self.exit_code = event.exit_code
        if self.exit_code is not None and self.exit_code != 0:
            raise RpcProblem(RpcReason.UNEXPECTED_EXIT)
        return event.written

    def send(self, frame: bytes, deadline: float) -> None:
        if self.stdout_eof or self.exit_code is not None:
            raise RpcProblem(RpcReason.EOF)
        pending = frame
        while pending:
            self.write_pending = True
            written = self.pump(pending, deadline)
            pending = pending[written:]

    def read(self, deadline: float) -> dict[str, Any]:
        while not self.records:
            if self.stdout_eof:
                raise RpcProblem(RpcReason.EOF)
            self.pump(b"", deadline)
        self.check(deadline)
        return self.records.popleft()

    def response(
        self, record: dict[str, Any], command_id: str, name: str
    ) -> dict[str, Any]:
        if (
            record.get("type") != "response"
            or record.get("id") != command_id
            or record.get("command") != name
            or type(record.get("success")) is not bool
        ):
            raise RpcProblem(RpcReason.RESPONSE_MISMATCH)
        if record["success"] is not True:
            reason = (
                RpcReason.MODEL_REJECTED
                if name == "set_model"
                else RpcReason.COMMAND_REJECTED
            )
            raise RpcProblem(reason)
        data = record.get("data", {})
        if not isinstance(data, dict):
            raise RpcProblem(RpcReason.RESPONSE_MISMATCH)
        return data

    def exchange(self, name: str, deadline: float, **fields: object) -> dict[str, Any]:
        self.before_command(deadline)
        self.command_no += 1
        command_id = f"rpc-{self.command_no}"
        self.awaiting = (command_id, name)
        self.send(command_frame(command_id, name, **fields), deadline)
        while True:
            record = self.read(deadline)
            if record.get("type") == "thinking_level_changed":
                self.notification(record)
                continue
            data = self.response(record, command_id, name)
            self.awaiting = None
            return data

    def before_command(self, deadline: float) -> None:
        while True:
            if self.command_no == 0 and (self.records or self.decoder.has_tail):
                raise RpcProblem(RpcReason.EARLY_RECORD)
            while self.records:
                record = self.records.popleft()
                if record.get("type") != "thinking_level_changed":
                    raise RpcProblem(RpcReason.RESPONSE_MISMATCH)
                self.notification(record)
            before = (self.stdout_bytes, self.stderr_bytes)
            self.pump(b"", deadline, immediate=not self.decoder.has_tail)
            if self.stdout_eof or self.exit_code is not None:
                raise RpcProblem(RpcReason.EOF)
            if (
                not self.records
                and not self.decoder.has_tail
                and before == (self.stdout_bytes, self.stderr_bytes)
            ):
                return

    def notification(self, record: dict[str, Any]) -> None:
        level = record.get("level")
        if (
            type(level) is not str
            or level not in THINKING_LEVELS
            or (self.expected_level is not None and level != self.expected_level)
        ):
            raise RpcProblem(RpcReason.THINKING_STATE)


def _initialize(
    connection: _Connection, description: CallDescription, deadline: float
) -> None:
    data = connection.exchange("new_session", deadline)
    if data.get("cancelled") is not False:
        if data.get("cancelled") is True:
            raise RpcProblem(RpcReason.SESSION_CANCELLED)
        raise RpcProblem(RpcReason.RESPONSE_MISMATCH)
    connection.exchange("set_auto_retry", deadline, enabled=False)
    connection.exchange("set_auto_compaction", deadline, enabled=False)
    model = connection.exchange(
        "set_model", deadline, provider=description.provider, modelId=description.model
    )
    _match_model(model, description)
    levels = connection.exchange("get_available_thinking_levels", deadline).get(
        "levels"
    )
    if (
        not isinstance(levels, list)
        or not levels
        or any(
            type(level) is not str or level not in THINKING_LEVELS for level in levels
        )
        or description.thinking_level not in levels
    ):
        raise RpcProblem(RpcReason.THINKING_UNSUPPORTED)
    connection.expected_level = description.thinking_level
    connection.exchange(
        "set_thinking_level", deadline, level=description.thinking_level
    )
    commands = connection.exchange("get_commands", deadline)
    if commands.get("commands") != []:
        raise RpcProblem(RpcReason.COMMANDS_PRESENT)
    state = connection.exchange("get_state", deadline)
    _match_model(state.get("model"), description)
    if state.get("thinkingLevel") != description.thinking_level:
        raise RpcProblem(RpcReason.THINKING_STATE)
    if (
        any(
            state.get(name) is not False
            for name in ("autoCompactionEnabled", "isStreaming", "isCompacting")
        )
        or any(
            type(state.get(name)) is not int or state[name] != 0
            for name in ("messageCount", "pendingMessageCount")
        )
        or state.get("sessionFile") is not None
    ):
        raise RpcProblem(RpcReason.DIRTY_STATE)
    # 同包尾部的无主记录必须先拒绝,不能把它解释为下一命令的响应。
    if connection.records:
        raise RpcProblem(RpcReason.RESPONSE_MISMATCH)


def _match_model(model: object, description: CallDescription) -> None:
    if (
        not isinstance(model, dict)
        or model.get("provider") != description.provider
        or model.get("id") != description.model
    ):
        raise RpcProblem(RpcReason.MODEL_STATE)


def _run(
    connection: _Connection, description: CallDescription, user_message: bytes
) -> RpcCandidate:
    events = RunEvents(description, user_message.decode("utf-8"))
    connection.before_command(connection.total_deadline)
    connection.command_no = _PROMPT_COMMAND_NO
    connection.awaiting = (_PROMPT_COMMAND_ID, _PROMPT_COMMAND_NAME)
    connection.send(_prompt_frame(user_message), connection.total_deadline)
    acked = False
    closed = False
    while not (acked and events.settled):
        record = connection.read(connection.total_deadline)
        if record.get("type") == "response":
            if acked:
                raise RpcProblem(RpcReason.RESPONSE_MISMATCH)
            data = connection.response(record, _PROMPT_COMMAND_ID, _PROMPT_COMMAND_NAME)
            if data.get("disposition") != "started":
                raise RpcProblem(RpcReason.PROMPT_DISPOSITION)
            acked = True
            connection.awaiting = None
        else:
            events.accept(record)
        if events.settled and not closed:
            connection.settled = True
            connection.session.close_stdin()
            closed = True
    deadline = min(
        connection.total_deadline, connection.clock() + connection.limits.close
    )
    while True:
        if connection.records:
            raise RpcProblem(RpcReason.EVENT_SEQUENCE)
        if (
            connection.stdout_eof
            and connection.stderr_eof
            and connection.exit_code == 0
        ):
            break
        connection.pump(b"", deadline, closing=True)
    if events.candidate is None:
        raise RpcProblem(RpcReason.EVENT_SEQUENCE)
    return events.candidate


def _cancel(connection: _Connection) -> None:
    """终局已锁定;只在完整帧边界做有限取消握手,不再解释候选。"""
    if (
        connection.write_pending
        or connection.stdout_eof
        or connection.exit_code is not None
        or connection.settled
    ):
        return
    connection.cancelled = lambda: False
    deadline = connection.clock() + connection.limits.close
    connection.total_deadline = deadline
    outstanding = connection.awaiting
    try:
        for name in ("clear_queue", "abort"):
            connection.command_no += 1
            command_id = f"rpc-{connection.command_no}"
            connection.send(command_frame(command_id, name), deadline)
            while True:
                record = connection.read(deadline)
                if record.get("type") != "response":
                    continue
                if outstanding is not None and record.get("id") == outstanding[0]:
                    connection.response(record, *outstanding)
                    outstanding = None
                    continue
                data = connection.response(record, command_id, name)
                if name == "clear_queue" and any(
                    not isinstance(data.get(field), list)
                    or any(type(text) is not str for text in data[field])
                    for field in ("steering", "followUp")
                ):
                    raise RpcProblem(RpcReason.RESPONSE_MISMATCH)
                # clear_queue 的文本只在当前帧短暂存在,不恢复/传出队列。
                del data, record
                break
    finally:
        connection.records.clear()


def _cleanup(session: ByteSession, clock: MonotonicClock, deadline: float) -> None:
    """清理中断延迟上抛;每步至多补做一次,始终共用首次绝对期限。"""
    interruption: KeyboardInterrupt | SystemExit | None = None
    failure: Exception | None = None
    for operation in (
        session.close_stdin,
        lambda: session.terminate(max(0.0, deadline - clock())),
    ):
        for _attempt in range(2):
            try:
                operation()
                break
            except (KeyboardInterrupt, SystemExit) as error:
                if interruption is None:
                    interruption = error
            except Exception as error:
                failure = error
                break
    if interruption is not None:
        raise interruption
    if failure is not None:
        raise failure


def run_call(
    description: CallDescription,
    user_message: bytes,
    factory: SessionFactory,
    *,
    clock: MonotonicClock = monotonic,
    cancelled: Cancellation = lambda: False,
    limits: RpcLimits = DEFAULT_LIMITS,
) -> RpcCandidate | RpcFailure:
    """一次调用仅一个显式会话/一条prompt,失败不携原文或自动重发。"""
    session: ByteSession | None = None
    connection: _Connection | None = None
    cleanup_finished = False
    cleanup_deadline: float | None = None
    try:
        if (
            type(description) is not CallDescription
            or type(limits) is not RpcLimits
            or type(description.pi_version) is not str
            or PROTOCOL_PROFILES.get(description.pi_version)
            != description.protocol_profile
            or description.protocol != "prompt_only"
            or type(description.thinking_level) is not str
            or description.thinking_level not in THINKING_LEVELS
            or type(description.system_prompt) is not bytes
            or not description.system_prompt
            or any(
                type(value) is not str or not value
                for value in (description.provider, description.model)
            )
            or any(
                type(value) not in (int, float)
                or not math.isfinite(value)
                or value <= 0
                for value in (
                    limits.initialization,
                    limits.total,
                    limits.close,
                    limits.terminate,
                    limits.poll,
                )
            )
        ):
            raise RpcProblem(RpcReason.INVALID_DESCRIPTION)
        try:
            description.system_prompt.decode("utf-8")
        except UnicodeError:
            raise RpcProblem(RpcReason.INVALID_DESCRIPTION) from None
        defaults = RpcLimits()
        if (
            limits.initialization > defaults.initialization
            or limits.total > defaults.total
            or limits.close > defaults.close
            or limits.terminate > defaults.terminate
            or limits.poll > defaults.poll
        ):
            raise RpcProblem(RpcReason.INVALID_DESCRIPTION)
        _prompt_frame(user_message)
        started = clock()
        if cancelled():
            raise RpcProblem(RpcReason.CANCELLED)
        try:
            session = factory(description)
        except Exception:
            raise RpcProblem(RpcReason.STARTUP_ERROR) from None
        connection = _Connection(session, clock, cancelled, limits, started)
        initialization = min(connection.total_deadline, started + limits.initialization)
        connection.pump(b"", initialization, immediate=True)
        if connection.records or connection.decoder.has_tail:
            raise RpcProblem(RpcReason.EARLY_RECORD)
        _initialize(connection, description, initialization)
        result = _run(connection, description, user_message)
        connection.check(connection.total_deadline, closing=True)
        cleanup_deadline = clock() + limits.terminate
        _cleanup(session, clock, cleanup_deadline)
        cleanup_finished = True
        connection.check(connection.total_deadline, closing=True)
        return result
    except RpcProblem as error:
        if error.reason is RpcReason.CANCELLED and connection is not None:
            with suppress(Exception):
                _cancel(connection)
        return RpcFailure(error.reason)
    except Exception:
        return RpcFailure(RpcReason.TRANSPORT_ERROR)
    finally:
        if session is not None and not cleanup_finished:
            original = sys.exception()
            interruption = (
                original
                if isinstance(original, (KeyboardInterrupt, SystemExit))
                else None
            )
            # 依据完成状态补偿;helper入口/时钟或循环间隙的中断也不能跳过清理。
            # 补偿至多两次,任何已取得的首次绝对期限都不重置。
            for _attempt in range(2):
                try:
                    if cleanup_deadline is None:
                        cleanup_deadline = clock() + limits.terminate
                    _cleanup(session, clock, cleanup_deadline)
                    break
                except (KeyboardInterrupt, SystemExit) as error:
                    if interruption is None:
                        interruption = error
                except Exception:
                    break
            if interruption is not None and interruption is not original:
                raise interruption from None
