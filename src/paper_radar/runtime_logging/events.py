"""封闭事件、可注入时钟和诊断降级;不接触业务载荷。"""

import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from time import monotonic as system_monotonic
from types import MappingProxyType
from typing import Protocol
from uuid import uuid4

from paper_radar.runtime_logging.schema import safe_event

Clock = Callable[[], datetime]
MonotonicClock = Callable[[], float]
WARNING = "运行日志写入失败，业务继续。\n"
_warned_pid: int | None = None


def warn_once() -> None:
    global _warned_pid
    pid = os.getpid()
    if _warned_pid != pid:
        _warned_pid = pid
        with suppress(OSError):
            os.write(2, WARNING.encode("utf-8"))


class Sink(Protocol):
    def emit(self, event: Mapping[str, object]) -> None: ...


class NullSink:
    def emit(self, event: Mapping[str, object]) -> None:
        pass


class RuntimeLog:
    def __init__(
        self,
        sink: Sink | None = None,
        *,
        clock: Clock | None = None,
        monotonic: MonotonicClock | None = None,
    ) -> None:
        self.sink = sink if sink is not None else NullSink()
        self.clock = clock if clock is not None else lambda: datetime.now(UTC)
        self.monotonic = monotonic if monotonic is not None else system_monotonic
        self.context: ContextVar[Mapping[str, object]] = ContextVar(
            "runtime", default=MappingProxyType({})
        )
        self.started: ContextVar[float | None] = ContextVar("started", default=None)

    @property
    def active(self) -> bool:
        return bool(self.context.get())

    def bind(self, **fields: object) -> None:
        if self.active:
            self.context.set({**self.context.get(), **fields})

    def emit(self, event: str, **fields: object) -> None:
        if isinstance(self.sink, NullSink):
            return
        try:
            started = self.started.get()
            elapsed = (
                max(0, round((self.monotonic() - started) * 1000))
                if started is not None
                else 0
            )
            self.sink.emit(
                safe_event(
                    {
                        "format_version": 1,
                        **self.context.get(),
                        "event": event,
                        **fields,
                        "timestamp": self.clock().astimezone(UTC).isoformat(),
                        "elapsed_ms": elapsed,
                    }
                )
            )
        except Exception:
            warn_once()

    @contextmanager
    def operation(
        self,
        component: str,
        *,
        controlled: tuple[type[Exception], ...] = (),
        run: bool = False,
        **fields: object,
    ) -> Iterator[None]:
        if isinstance(self.sink, NullSink):
            yield
            return
        if self.context.get().get("component") == component:
            self.bind(**fields)
            yield
            return
        token = self.context.set(
            {"component": component, "run_id": uuid4().hex, **fields}
        )
        started = self.started.set(None)
        try:
            # 诊断时钟失效不能抢占业务执行。
            try:
                self.started.set(self.monotonic())
            except Exception:
                warn_once()
            if run:
                self.emit("run_started")
            try:
                yield
            except controlled:
                if run:
                    self.emit("run_finished", category="controlled_failure")
                raise
            except Exception:
                self.emit("unexpected_error")
                raise
            except BaseException:
                self.emit("interrupted", category="outcome_unknown")
                raise
            else:
                if run:
                    self.emit("run_finished", category="completed")
        finally:
            self.started.reset(started)
            self.context.reset(token)

    @contextmanager
    def execution(
        self,
        component: str,
        *,
        controlled: tuple[type[Exception], ...] = (),
        **fields: object,
    ) -> Iterator[None]:
        with self.operation(component, controlled=controlled, run=True, **fields):
            yield
