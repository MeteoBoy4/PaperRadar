"""Independent D1: prospective exit diagnostics; mock lifecycle only."""

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scripts import issue167_live_case as contract
from scripts import issue167_live_owner as owner
from scripts import issue167_resolver_owner as base


class Lifecycle:
    def __init__(self, stage: str = "", error: BaseException | None = None) -> None:
        self.stage = stage
        self.error = error
        self.finished = False
        self.published = False

    def preflight(self) -> None:
        pass

    reserve = install = start = activate = preflight

    def ready(self) -> dict[str, object]:
        return {}

    exercise_rules = preflight_result = ready

    def phase_gate(self, category: str, sequence: int) -> None:
        if category == "exit":
            self.published = True
            if self.stage == "exit_gate" and self.error is not None:
                raise self.error

    def auth_ready(self, sequence: int) -> None:
        pass

    def cell_result(self, sequence: int) -> dict[str, object]:
        return {"sequence": sequence}

    def collect(self) -> dict[str, object]:
        return {
            "cases": [self.cell_result(n) for n in range(1, 7)],
            "preflight": {},
            "selection_journal": [],
        }

    def wait_exit(self) -> None:
        if self.stage == "exit_wait" and self.error is not None:
            raise self.error

    def restore(self) -> dict[str, object]:
        return {
            "result": "host_policy_restored",
            "global_resolver_unchanged": True,
            "ledger_retained": True,
            "table_absent": True,
            "unit_absent": True,
        }

    def finish(self) -> dict[str, object]:
        self.finished = True
        return {"result": "successful_artifacts_removed", "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        pass

    def selection_journal(self) -> dict[str, object]:
        return {"entries": [], "completeness": "captured"}

    def database_restoration(self) -> dict[str, object]:
        return {
            "result": "original_selection_restored",
            "append_only_history_retained": True,
            "source": "trusted_worker_public_API_CAS",
        }


@pytest.mark.parametrize("stage", ["exit_gate", "exit_wait"])
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (OSError("external-private-stderr"), "owner_os_error"),
        (KeyboardInterrupt("external-private-stderr"), "owner_interrupted"),
        (SystemExit("external-private-stderr"), "owner_system_exit"),
        (RuntimeError("external-private-stderr"), "owner_operation_unknown"),
        (base.OwnerRejected("external-private-stderr"), "owner_operation_unknown"),
        (base.OwnerRejected("worker_exit_unknown"), "worker_exit_unknown"),
    ],
)
def test_owner_distinguishes_gate_and_wait_without_exporting_exception(
    stage: str, error: BaseException, reason: str
) -> None:
    ops = Lifecycle(stage, error)
    case = contract.Case("123456abcdef", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    result = owner.run_owner(case, ops)
    assert result["failure_stage"] == stage
    assert result["failure_reason"] == reason
    assert result["result"] == "unknown" and not ops.finished and ops.published
    assert result["restoration"] == ops.restore()
    assert "external-private-stderr" not in json.dumps(result)


def test_owner_success_control_still_requires_restoration() -> None:
    ops = Lifecycle()
    case = contract.Case("123456abcdef", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    result = owner.run_owner(case, ops)
    assert result["result"] == "observed_expected_and_restored"
    assert result["restoration"] == ops.restore() and ops.finished


def manager(**changes: str) -> bytes:
    state = {
        "ActiveState": "active",
        "SubState": "exited",
        "Result": "success",
        "ExecMainCode": "1",
        "ExecMainStatus": "0",
        "MainPID": "0",
        "ControlGroup": "/system.slice/synthetic.service",
    }
    state.update(changes)
    return "\n".join(f"{key}={value}" for key, value in state.items()).encode()


def live_ops(
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
    *,
    cgroup_error: bool = False,
    pids: frozenset[int] = frozenset(),
) -> owner.LiveOperations:
    # Never initialize the real host-bound implementation or invoke a command.
    ops = cast(Any, object.__new__(owner.LiveOperations))
    ops.case = SimpleNamespace(unit="synthetic.service")
    ops.plan = SimpleNamespace(cgroup="/system.slice/synthetic.service")
    ops.ready_metadata = {"pid": 123}
    ops.exit_metadata = owner.new_exit_metadata()
    ops.deadline = 3.0

    def cgroup(*args: object, **kwargs: object) -> object:
        if cgroup_error:
            raise ValueError("external-private-cgroup")
        return SimpleNamespace(pids=pids)

    ops.phase = SimpleNamespace(read_cgroup_state=cgroup)
    ops._systemctl = lambda *args: raw
    clock = iter(range(10))
    monkeypatch.setattr(
        "scripts.issue167_live_owner.time.monotonic", lambda: float(next(clock))
    )
    monkeypatch.setattr("scripts.issue167_live_owner.time.sleep", lambda seconds: None)
    return cast(owner.LiveOperations, ops)


@pytest.mark.parametrize("cgroup", ["", "/system.slice/synthetic.service"])
def test_exact_exit_control_retains_closed_manager_evidence(
    monkeypatch: pytest.MonkeyPatch, cgroup: str
) -> None:
    ops = live_ops(monkeypatch, manager(ControlGroup=cgroup))
    ops.wait_exit()
    value = ops.exit_metadata
    assert value["wait_checkpoint"] == "complete"
    assert value["cgroup_empty"] is True
    assert value["manager"] == {
        "ActiveState": "active",
        "SubState": "exited",
        "Result": "success",
        "ExecMainCode": 1,
        "ExecMainStatus": 0,
        "main_pid_zero": True,
        "main_pid_expected": False,
        "control_group_expected": cgroup != "",
        "control_group_empty": cgroup == "",
    }


@pytest.mark.parametrize(
    "raw",
    [
        manager(ExecMainStatus="1", Result="exit-code"),
        manager(ExecMainCode="2", ExecMainStatus="9", Result="signal"),
        manager(ActiveState="failed", SubState="failed"),
        manager(MainPID="123"),
        manager(ControlGroup="/unexpected/private-group"),
        manager(ActiveState="external-private-value"),
        manager(SubState="external-private-value"),
        manager(Result="external-private-value"),
        manager(ExecMainCode="external-private-value"),
        manager(ExecMainStatus="-1"),
        manager(MainPID="01"),
        manager() + b"\nResult=success",
        b"ActiveState=active\n",
        b"\xff",
    ],
)
def test_nonzero_killed_unknown_or_malformed_exit_never_passes(
    monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    ops = live_ops(monkeypatch, raw)
    with pytest.raises(base.OwnerRejected, match="worker_exit_unknown"):
        ops.wait_exit()
    assert ops.exit_metadata["wait_checkpoint"] == "waiting"
    assert ops.exit_metadata["failure_reason"] in {
        "worker_exit_unknown",
        "manager_metadata_unknown",
    }
    assert "private" not in json.dumps(ops.exit_metadata)


@pytest.mark.parametrize("partial", [False, True])
def test_cgroup_absence_or_incomplete_observation_is_not_exit_evidence(
    monkeypatch: pytest.MonkeyPatch, partial: bool
) -> None:
    ops = live_ops(monkeypatch, manager(), cgroup_error=partial, pids=frozenset({123}))
    with pytest.raises((base.OwnerRejected, ValueError)):
        ops.wait_exit()
    assert ops.exit_metadata["manager"] is None
    assert ops.exit_metadata["wait_checkpoint"] == "waiting"
    assert ops.exit_metadata["failure_reason"] in {
        "worker_exit_unknown",
        "owner_operation_unknown",
    }


def test_missing_manager_cannot_become_exit_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ops = live_ops(monkeypatch, b"")
    with pytest.raises(base.OwnerRejected, match="worker_exit_unknown"):
        ops.wait_exit()
    assert ops.exit_metadata["manager"] is None
    assert ops.exit_metadata["failure_reason"] == "manager_metadata_unknown"


@pytest.mark.parametrize("failure", ["before_link", "directory_fsync", "none"])
def test_actual_gate_publication_is_separate_from_write_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    ops = gate_ops(tmp_path)
    fsync = os.fsync

    def synthetic_fsync(fd: int) -> None:
        if failure == "directory_fsync" and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("external-private-fsync")
        fsync(fd)

    def refused_link(*args: object, **kwargs: object) -> None:
        raise OSError("external-private-link")

    monkeypatch.setattr(os, "fsync", synthetic_fsync)
    if failure == "before_link":
        monkeypatch.setattr(os, "link", refused_link)
    if failure == "none":
        ops.phase_gate("exit", 7)
    else:
        with pytest.raises(OSError):
            ops.phase_gate("exit", 7)
    assert ops.exit_metadata["gate_published"] is (failure != "before_link")
    assert ops.exit_metadata["gate_checkpoint"] == (
        "write_complete" if failure == "none" else "write_intent"
    )
    assert "private" not in json.dumps(ops.exit_metadata)


def gate_ops(tmp_path: Path, supplied: object | None = None) -> Any:
    ops = (
        cast(Any, supplied)
        if supplied is not None
        else cast(Any, object.__new__(owner.LiveOperations))
    )
    ops.case = SimpleNamespace(runtime_root=tmp_path, run_id="synthetic")
    ops.ready_metadata = {"pid": 123}
    ops.plan = SimpleNamespace()
    ops.exit_metadata = owner.new_exit_metadata()
    ops.commands = SimpleNamespace(unit_state=lambda: SimpleNamespace(pid=123))
    ops.phase = SimpleNamespace(
        read_cgroup_state=lambda plan: SimpleNamespace(pids=frozenset({123}))
    )
    ops._verify = lambda: None

    def read_control(path: Path, *, owner: int) -> object:
        assert owner == 0 and path == tmp_path / "gate-exit.json"
        return json.loads(path.read_text())

    ops.contract = SimpleNamespace(read_metadata=read_control)
    return ops


@pytest.mark.parametrize("failure", ["directory_fsync", "manager_query", "none"])
def test_real_gate_and_wait_methods_are_recorded_by_owner_lifecycle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    class RootMock(Lifecycle, owner.LiveOperations):
        def phase_gate(self, category: str, sequence: int) -> None:
            if category == "exit":
                owner.LiveOperations.phase_gate(self, category, sequence)

        def wait_exit(self) -> None:
            owner.LiveOperations.wait_exit(self)

    ops = gate_ops(tmp_path, RootMock())
    ops.case.unit = "synthetic.service"
    ops.plan.cgroup = "/system.slice/synthetic.service"
    ops.deadline = 1.0
    ops.phase.read_cgroup_state = lambda plan, **kwargs: SimpleNamespace(
        pids=frozenset() if kwargs.get("allow_absent") else frozenset({123})
    )
    fsync = os.fsync

    def synthetic_fsync(fd: int) -> None:
        if failure == "directory_fsync" and stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError("external-private-fsync")
        fsync(fd)

    def systemctl(*args: object) -> bytes:
        if failure == "manager_query":
            raise OSError("external-private-stderr")
        return manager()

    ops._systemctl = systemctl
    monkeypatch.setattr(os, "fsync", synthetic_fsync)
    monkeypatch.setattr("scripts.issue167_live_owner.time.monotonic", lambda: 0.0)
    case = contract.Case("123456abcdef", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    result = owner.run_owner(case, ops)
    diagnostic = cast(dict[str, Any], result["exit_diagnostics"])
    assert diagnostic["gate_published"] is True
    assert result["restoration"] == ops.restore()
    if failure == "none":
        assert result["result"] == "observed_expected_and_restored" and ops.finished
        assert diagnostic["wait_checkpoint"] == "complete"
    else:
        assert result["result"] == "unknown" and not ops.finished
        assert result["failure_stage"] == (
            "exit_gate" if failure == "directory_fsync" else "exit_wait"
        )
        assert diagnostic["failure_reason"] == "owner_os_error"
    assert "private" not in json.dumps(result)
