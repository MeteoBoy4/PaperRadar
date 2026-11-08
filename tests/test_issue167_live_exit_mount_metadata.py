"""Independent D1: fixed synthetic mount metadata and temporary owned trees."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scripts import issue167_live_exit_probe as probe
from scripts import issue167_live_owner as live
from scripts import issue167_resolver_owner as base


def mount_row(
    *,
    root: str = "mnt:[1]",
    point: str = "/synthetic/outside",
    filesystem: str = "nsfs",
) -> bytes:
    return f"12 1 0:4 {root} {point} rw - {filesystem} synthetic rw\n".encode()


def temporary_artifacts(tmp_path: Path) -> Any:
    """The actual remove_artifacts caller with only synthetic ownership projected."""
    operations = cast(Any, object.__new__(probe.HostOperations))
    runtime, code = tmp_path / "runtime", tmp_path / "code"
    runtime.mkdir(mode=0o755)
    code.mkdir(mode=0o755)
    (runtime / "worker").mkdir(mode=0o700)
    for path in [
        runtime / "worker/ready.json",
        runtime / "worker/terminal.json",
        runtime / "gate-exit.json",
    ]:
        path.write_bytes(b"public synthetic metadata")
        path.chmod(0o600 if path.parent.name == "worker" else 0o644)
    operations.files = {"public.py": b"# public synthetic code\n"}
    (code / "public.py").write_bytes(operations.files["public.py"])
    (code / "public.py").chmod(0o644)
    operations.case = SimpleNamespace(runtime_root=runtime, code_root=code)
    operations.created = {
        path: (path.stat().st_dev, path.stat().st_ino) for path in (runtime, code)
    }
    operations.unit_checks = []

    def absent_unit(*, absent: bool = False) -> dict[str, str]:
        assert absent is True
        operations.unit_checks.append(absent)
        return {}

    operations.check_unit = absent_unit
    return operations


def synthetic_mounts(monkeypatch: pytest.MonkeyPatch, raw: bytes) -> None:
    original = Path.open

    def opened(path: Path, *args: Any, **kwargs: Any) -> Any:
        if path == Path("/proc/self/mountinfo"):
            assert args == ("rb",) and not kwargs
            return io.BytesIO(raw)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)


def project_synthetic_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    original = probe.remove_flat_tree

    def remove(
        root: Path,
        allowed: dict[str, tuple[int, bool]],
        expected: tuple[int, int] | None,
    ) -> None:
        # No host chown/root operation: both roles are this test's own UID.
        original(
            root,
            {
                name: (os.getuid(), directory)
                for name, (_, directory) in allowed.items()
            },
            expected,
            root_uid=os.getuid(),
        )

    monkeypatch.setattr(probe, "remove_flat_tree", remove)


@pytest.mark.parametrize("root", ["/", "mnt:[1]", "mnt:[4026531840]"])
def test_real_two_tree_cleanup_accepts_observed_nsfs_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root: str
) -> None:
    operations = temporary_artifacts(tmp_path)
    synthetic_mounts(monkeypatch, mount_row(root=root))
    project_synthetic_ownership(monkeypatch)
    assert operations.remove_artifacts() == {
        "code_runtime_removed": True,
        "ledger_retained": True,
    }
    assert operations.unit_checks == [True]
    assert not operations.case.runtime_root.exists()
    assert not operations.case.code_root.exists()


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"not mount metadata\n",
        mount_row(root="garbage"),
        mount_row(root="net:[1]"),
        mount_row(root="mnt:[0]"),
        mount_row(root="mnt:[01]"),
        mount_row(root="mnt:[1]", filesystem="tmpfs"),
        mount_row(point="relative"),
        mount_row(point=r"/synthetic/unknown\777escape"),
        mount_row(root=r"/synthetic/unknown\777escape"),
        mount_row(point="/synthetic/\x00target"),
        mount_row(root="/synthetic/\x00root"),
        mount_row(point="/synthetic/../target"),
        mount_row(point="//synthetic/target"),
        mount_row(root="//synthetic/root"),
        b"12 1 0:4 / /synthetic/outside rw - nsfs synthetic rw extra\n",
        b"12 1 0:4 / /synthetic/outside rw nsfs synthetic rw\n",
        b"12 1 0:4 / /synthetic/outside rw - nsfs synthetic \xff\n",
        b"x" * 1048577,
    ],
)
def test_invalid_mount_observation_blocks_actual_caller_before_any_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    operations = temporary_artifacts(tmp_path)
    synthetic_mounts(monkeypatch, raw)
    project_synthetic_ownership(monkeypatch)
    monkeypatch.setattr(os, "unlink", lambda *a, **kw: pytest.fail("unexpected unlink"))
    with pytest.raises(probe.ProbeRejected, match="mount_metadata_unknown"):
        operations.remove_artifacts()
    assert (operations.case.runtime_root / "worker/ready.json").exists()
    assert (operations.case.runtime_root / "gate-exit.json").exists()
    assert (operations.case.code_root / "public.py").exists()


def test_valid_nsfs_target_inside_tree_still_blocks_before_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operations = temporary_artifacts(tmp_path)
    synthetic_mounts(
        monkeypatch, mount_row(point=str(operations.case.runtime_root / "worker"))
    )
    project_synthetic_ownership(monkeypatch)
    monkeypatch.setattr(os, "unlink", lambda *a, **kw: pytest.fail("unexpected unlink"))
    with pytest.raises(probe.ProbeRejected, match="artifact_mount_unknown"):
        operations.remove_artifacts()
    assert (operations.case.runtime_root / "worker/terminal.json").exists()
    assert (operations.case.code_root / "public.py").exists()


def test_double_anchor_target_alias_is_unknown_before_any_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operations = temporary_artifacts(tmp_path)
    target = "//" + str(operations.case.runtime_root / "worker").lstrip("/")
    synthetic_mounts(monkeypatch, mount_row(point=target))
    project_synthetic_ownership(monkeypatch)
    monkeypatch.setattr(os, "unlink", lambda *a, **kw: pytest.fail("unexpected unlink"))
    with pytest.raises(probe.ProbeRejected, match="mount_metadata_unknown"):
        operations.remove_artifacts()
    assert (operations.case.runtime_root / "worker/terminal.json").exists()
    assert (operations.case.code_root / "public.py").exists()


def test_known_mount_escapes_are_decoded_once() -> None:
    assert probe.mount_points(
        mount_row(root=r"/synthetic/root\040space", point=r"/synthetic/a\040b\134040")
    ) == {Path(r"/synthetic/a b\040")}


class Runner:
    def __init__(self, failure: str = "", error: BaseException | None = None) -> None:
        self.failure = failure
        self.error = error or probe.ProbeRejected("mount_metadata_unknown")
        self.events: list[str] = []
        self.ledger: object = None
        self.seam = SimpleNamespace(
            phase_gate=lambda *args: self.events.append("gate"),
            wait_exit=lambda: self.events.append("exit"),
            exit_metadata=live.new_exit_metadata(),
        )

    def preflight(self) -> None:
        self.events.append("preflight")

    def reserve(self) -> None:
        self.events.append("reserve")

    def install(self) -> None:
        self.events.append("install")

    def start(self) -> None:
        self.events.append("start")

    def checkpoint(self, name: str) -> dict[str, object]:
        self.events.append(name)
        return {"count": 1, "integrity": "complete"}

    def restore(self) -> dict[str, object]:
        self.events.append("restore")
        if self.failure == "restore":
            raise self.error
        return {"unit_absent": True, "cgroup_empty": True}

    def remove_artifacts(self) -> dict[str, object]:
        self.events.append("artifacts")
        if self.failure == "artifacts":
            raise self.error
        return {"code_runtime_removed": True, "ledger_retained": True}

    def write_ledger(self, value: object) -> None:
        self.events.append("ledger")
        self.ledger = value


def test_real_runner_reaches_both_tree_cleanup_with_observed_nsfs_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host = temporary_artifacts(tmp_path)
    synthetic_mounts(monkeypatch, mount_row())
    project_synthetic_ownership(monkeypatch)
    operations = Runner()
    cast(Any, operations).remove_artifacts = host.remove_artifacts
    result = probe.run_probe(operations)
    assert result["result"] == "observed_expected_and_restored"
    assert result["restoration"] == {"unit_absent": True, "cgroup_empty": True}
    assert result["artifacts"] == {
        "code_runtime_removed": True,
        "ledger_retained": True,
    }
    assert not host.case.runtime_root.exists() and not host.case.code_root.exists()
    assert operations.ledger is result


def test_artifact_failure_preserves_explicit_unit_restoration_success() -> None:
    operations = Runner("artifacts")
    result = probe.run_probe(operations)
    assert result["result"] == "unknown" and result["artifacts"] is None
    assert result["restoration"] == {"unit_absent": True, "cgroup_empty": True}
    assert result["restoration_error"] == "restoration_unknown"  # Legacy aggregate.
    assert result["artifact_error"] == "mount_metadata_unknown"
    assert result["cleanup_diagnostics"] == {
        "unit_restoration": "complete",
        "artifacts": "unknown",
        "failure_stage": "artifacts",
        "failure_reason": "mount_metadata_unknown",
    }
    assert operations.events[-3:] == ["restore", "artifacts", "ledger"]
    assert operations.ledger is result


def test_unit_restoration_failure_never_attempts_artifact_cleanup() -> None:
    operations = Runner("restore", probe.ProbeRejected("unit_scope_unknown"))
    result = probe.run_probe(operations)
    assert result["result"] == "unknown" and result["restoration"] is None
    assert "artifact_error" not in result
    assert result["cleanup_diagnostics"] == {
        "unit_restoration": "unknown",
        "artifacts": "not_started",
        "failure_stage": "unit_restoration",
        "failure_reason": "unit_scope_unknown",
    }
    assert operations.events[-2:] == ["restore", "ledger"]


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (probe.ProbeRejected("private /unreviewed/path"), "cleanup_operation_unknown"),
        (RuntimeError("private exception text"), "cleanup_operation_unknown"),
        (OSError("private os details"), "cleanup_os_error"),
        (KeyboardInterrupt("private interruption"), "cleanup_interrupted"),
        (SystemExit("private system exit"), "cleanup_system_exit"),
    ],
)
def test_cleanup_failure_projection_never_emits_exception_text(
    error: BaseException, reason: str
) -> None:
    operations = Runner("artifacts", error)
    result = probe.run_probe(operations)
    assert result["result"] == "unknown"
    assert result["artifact_error"] == reason
    assert (
        cast(dict[str, object], result["cleanup_diagnostics"])["failure_reason"]
        == reason
    )
    assert "private" not in json.dumps(result)
    assert operations.events[-1] == "ledger"


def test_exception_with_unavailable_string_cannot_skip_ledger() -> None:
    class Unrenderable(probe.ProbeRejected):
        def __str__(self) -> str:
            raise RuntimeError("private string failure")

    operations = Runner("artifacts", Unrenderable("mount_metadata_unknown"))
    result = probe.run_probe(operations)
    assert result["result"] == "unknown"
    assert result["artifact_error"] == "cleanup_operation_unknown"
    assert operations.events[-1] == "ledger" and operations.ledger is result
    assert "private" not in json.dumps(result)


def test_invalid_artifact_return_cannot_pass_or_mask_unit_restore() -> None:
    operations = Runner()
    cast(Any, operations).remove_artifacts = lambda: {
        "code_runtime_removed": 1,
        "ledger_retained": True,
    }
    result = probe.run_probe(operations)
    assert result["result"] == "unknown"
    assert result["restoration"] == {"unit_absent": True, "cgroup_empty": True}
    assert result["artifact_error"] == "artifact_cleanup_unknown"
    assert (
        cast(dict[str, object], result["cleanup_diagnostics"])["unit_restoration"]
        == "complete"
    )
    assert operations.events[-1] == "ledger"


def test_signal_scope_failure_does_not_relabel_completed_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @contextmanager
    def failing_scope() -> Iterator[None]:
        yield
        raise OSError("private signal cleanup failure")

    monkeypatch.setattr(base, "cleanup_signals", failing_scope)
    operations = Runner()
    result = probe.run_probe(operations)
    assert result["result"] == "unknown"
    assert result["cleanup_diagnostics"] == {
        "unit_restoration": "complete",
        "artifacts": "complete",
        "failure_stage": "signal_scope",
        "failure_reason": "cleanup_os_error",
    }
    assert "artifact_error" not in result
    assert operations.events[-1] == "ledger"


def test_success_remains_strict_and_cleanup_diagnostics_are_complete() -> None:
    operations = Runner()
    result = probe.run_probe(operations)
    assert result["result"] == "observed_expected_and_restored"
    assert result["cleanup_diagnostics"] == {
        "unit_restoration": "complete",
        "artifacts": "complete",
        "failure_stage": None,
        "failure_reason": None,
    }
    assert "artifact_error" not in result and "restoration_error" not in result


def test_exit_diagnostic_observation_failure_still_runs_both_cleanups() -> None:
    class Unavailable:
        def keys(self) -> None:
            raise RuntimeError("private diagnostic failure")

    operations = Runner()
    operations.seam.exit_metadata = Unavailable()
    result = probe.run_probe(operations)
    assert result["result"] == "unknown"
    assert result["diagnostic_error"] == "exit_metadata_unknown"
    assert (
        cast(dict[str, object], result["cleanup_diagnostics"])["artifacts"]
        == "complete"
    )
    assert operations.events[-3:] == ["restore", "artifacts", "ledger"]
    assert "private" not in json.dumps(result)
