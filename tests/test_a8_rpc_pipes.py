"""同一产品包装器的实际管道背压、退出与整组回收。"""

import os
import select
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc import run_call
from paper_radar.llm.rpc_types import RpcCandidate, RpcFailure, RpcLimits, RpcReason
from paper_radar.screening_tasks import ScreeningTasks, SuccessReceipt
from tests.a8_call_support import archive, prepare_call, request_for
from tests.a8_pipe_support import fixture_factory
from tests.a8_rpc_support import BOUNDARY_RAW, FakeClock
from tests.a8_rpc_task_support import run_attempt

FAST = RpcLimits(initialization=0.5, total=0.5, close=0.3, terminate=0.5, poll=0.01)


@pytest.fixture(scope="module")
def description(tmp_path_factory: pytest.TempPathFactory) -> CallDescription:
    data = archive(tmp_path_factory.mktemp("rpc-pipes"))
    tasks = ScreeningTasks(data.database)
    return prepare_call(tasks, tasks.register(request_for(data)).receipt_id)


def test_real_pipe_candidate_reaches_existing_task_acceptance(tmp_path: Path) -> None:
    data = archive(tmp_path / "archive")
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    directory = tmp_path / "fixture"
    directory.mkdir()
    with fixture_factory(directory, "normal") as factory:
        result = run_attempt(tasks, receipt.receipt_id, factory, limits=FAST)
        assert isinstance(result, SuccessReceipt)
        assert (
            tasks.load_success(result.success_id).raw_response == BOUNDARY_RAW.encode()
        )
        assert result.executor_kind == "test"
        factory.assert_reclaimed()


def test_real_hung_process_is_killed_at_deadline(
    description: CallDescription, tmp_path: Path
) -> None:
    with fixture_factory(tmp_path, "hang") as factory:
        assert run_call(description, b"request", factory, limits=FAST) == RpcFailure(
            RpcReason.TIMEOUT
        )
        factory.assert_reclaimed()


def test_real_early_exit_cannot_return_candidate(
    description: CallDescription, tmp_path: Path
) -> None:
    with fixture_factory(tmp_path, "early_exit") as factory:
        result = run_call(description, b"request", factory, limits=FAST)
        assert isinstance(result, RpcFailure)
        assert result.reason in {RpcReason.EOF, RpcReason.UNEXPECTED_EXIT}
        factory.assert_reclaimed()


def test_shared_process_group_is_rejected_before_any_rpc_command(
    description: CallDescription, tmp_path: Path
) -> None:
    with fixture_factory(tmp_path, "normal", own_group=False) as factory:
        result = run_call(description, b"request", factory, limits=FAST)
        assert result == RpcFailure(RpcReason.STARTUP_ERROR)
        assert factory.session is None
        assert factory.notices == ["R"]
        # 拒绝接管的句柄仍由启动方回收,产品不能 kill 未验证的共享组。
        assert factory.child is not None and factory.child.poll() is None


@pytest.mark.parametrize("scenario", ["backpressure", "flood"])
def test_real_dual_pipe_backpressure_and_stderr_discard(
    description: CallDescription, tmp_path: Path, scenario: str
) -> None:
    with fixture_factory(tmp_path, scenario) as factory:
        result = run_call(description, b"x" * (180 * 1024), factory, limits=FAST)
        if scenario == "backpressure":
            assert isinstance(result, RpcCandidate)
            assert result.raw_response == BOUNDARY_RAW.encode()
        else:
            assert result == RpcFailure(RpcReason.STDERR_LIMIT)
        assert "STDERR_SECRET" not in repr(result)
        factory.assert_reclaimed()


def test_real_cancellation_clears_queue_before_abort(
    description: CallDescription, tmp_path: Path
) -> None:
    with fixture_factory(tmp_path, "cancel") as factory:
        result = run_call(
            description, b"request", factory, limits=FAST, cancelled=factory.cancelled
        )
        assert result == RpcFailure(RpcReason.CANCELLED)
        factory.assert_reclaimed()
        assert factory.notices[-2:] == ["Cclear_queue", "Cabort"]
        assert "QUEUE_SECRET" not in repr(result)


@pytest.mark.parametrize("scenario", ["grandchild_holds", "grandchild_closed"])
def test_real_group_reclaims_grandchild_even_after_leader_exit(
    description: CallDescription, tmp_path: Path, scenario: str
) -> None:
    with fixture_factory(tmp_path, scenario) as factory:
        result = run_call(description, b"request", factory, limits=FAST)
        if scenario == "grandchild_holds":
            assert result == RpcFailure(RpcReason.TIMEOUT)
        else:
            assert isinstance(result, RpcCandidate)
        factory.assert_reclaimed()


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(42)])
@pytest.mark.parametrize("phase", ["killpg", "wait", "pidfd_close", "killpg_deadline"])
def test_real_termination_interruption_still_reclaims_closed_pipe_grandchild(
    description: CallDescription,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: BaseException,
    phase: str,
) -> None:
    clock = FakeClock()
    with fixture_factory(tmp_path, "grandchild_closed", clock=clock) as factory:
        session = factory(description)
        killpg = os.killpg
        assert factory.child is not None
        wait = factory.child.wait
        close = os.close
        injected = False
        waited = False

        def interrupted_killpg(pid: int, sig: int) -> None:
            nonlocal injected
            if phase in {"killpg", "killpg_deadline"} and not injected:
                injected = True
                if phase == "killpg_deadline":
                    clock.now = 0.5
                raise interruption
            killpg(pid, sig)

        def interrupted_wait(timeout: float | None = None) -> int:
            nonlocal injected, waited
            if phase == "wait" and not injected:
                injected = True
                raise interruption
            if phase == "killpg_deadline":
                assert timeout == 0.0
                waited = True
            result = wait(timeout)
            waited = True
            return result

        def interrupted_close(fd: int) -> None:
            nonlocal injected
            if (
                phase == "pidfd_close"
                and not injected
                and os.readlink(f"/proc/self/fd/{fd}") == "anon_inode:[pidfd]"
            ):
                injected = True
                raise interruption
            close(fd)

        with monkeypatch.context() as patch:
            patch.setattr(os, "killpg", interrupted_killpg)
            patch.setattr(os, "close", interrupted_close)
            patch.setattr(factory.child, "wait", interrupted_wait)
            with pytest.raises(type(interruption)) as caught:
                session.terminate(0.5)
            assert caught.value is interruption
            assert injected and waited
            # 等待观测pidfd只用于测试证据,产品在耗尽预算时只能wait(timeout=0)。
            assert all(select.select([fd], [], [], 1)[0] for fd in factory.pidfds)
            # pidfd/关闭断言在fixture兜底之前执行,不靠重调terminate制造通过。
            factory.assert_reclaimed()
        if phase != "killpg_deadline":
            session.terminate(0.5)


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(42)])
def test_zero_wait_budget_still_kills_closes_and_attempts_direct_child_wait(
    description: CallDescription,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: BaseException,
) -> None:
    with fixture_factory(tmp_path, "grandchild_closed") as factory:
        session = factory(description)
        killpg = os.killpg
        injected = False
        assert factory.child is not None
        wait = factory.child.wait
        wait_attempted = False

        def interrupted_killpg(pid: int, sig: int) -> None:
            nonlocal injected
            if not injected:
                injected = True
                raise interruption
            killpg(pid, sig)

        def immediate_wait(timeout: float | None = None) -> int:
            nonlocal wait_attempted
            assert timeout == 0.0
            wait_attempted = True
            return wait(timeout)

        with monkeypatch.context() as patch:
            patch.setattr(os, "killpg", interrupted_killpg)
            patch.setattr(factory.child, "wait", immediate_wait)
            with pytest.raises(type(interruption)) as caught:
                session.terminate(0.0)
            assert caught.value is interruption
            assert wait_attempted
            assert all(select.select([fd], [], [], 1)[0] for fd in factory.pidfds)
            factory.assert_reclaimed()
