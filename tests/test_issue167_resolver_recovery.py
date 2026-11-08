"""Independent D1: fixed recovery control and safe readers, never root commands."""

import os
from pathlib import Path

import pytest

from scripts import issue167_resolver_recovery as recovery


class FakeOperations:
    def __init__(self, failure: str = "") -> None:
        self.events: list[str] = []
        self.failure = failure

    def event(self, name: str) -> None:
        self.events.append(name)
        if self.failure == name:
            raise recovery.RecoveryRejected("injected_unknown")

    def inspect(self) -> None:
        self.event("inspect")

    def remove_table_if_bound(self) -> None:
        self.event("table")

    def remove_unit(self) -> None:
        self.event("unit")

    def verify(self) -> None:
        self.event("verify")


def test_policy_cleanup_never_promotes_original_case() -> None:
    ops = FakeOperations()
    result = recovery.recover(ops, {})
    assert ops.events == ["inspect", "table", "unit", "verify"]
    assert result["restoration_result"] == "project_resources_removed"
    assert result["original_experiment_result"] == "unknown"
    assert (
        result["original_global_resolver_baseline"] == "unavailable_not_reconstructed"
    )
    assert result["synthetic_reexecs"] == 0


@pytest.mark.parametrize("failure", ["inspect", "table", "unit", "verify"])
def test_recovery_stops_at_first_failure_without_retry(failure: str) -> None:
    ops = FakeOperations(failure)
    progress: dict[str, str] = {}
    with pytest.raises(recovery.RecoveryRejected, match=r"^injected_unknown$"):
        recovery.recover(ops, progress)
    assert (
        ops.events
        == ["inspect", "table", "unit", "verify"][: ops.events.index(failure) + 1]
    )
    assert progress["stage"] == failure


@pytest.mark.parametrize("kind", ["symlink", "fifo", "hardlink"])
def test_reader_rejects_nonunique_or_nonregular_before_contents(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "record"
    target = tmp_path / "synthetic-outside"
    target.write_bytes(b"fixed-synthetic-data")
    target.chmod(0o600)
    if kind == "symlink":
        path.symlink_to(target)
    elif kind == "fifo":
        os.mkfifo(path, 0o600)
    else:
        os.link(target, path)
    with pytest.raises(recovery.RecoveryRejected, match=r"^recovery_metadata_unknown$"):
        recovery.read_record(path, owner=os.getuid())


def test_root_gate_refuses_ordinary_user_before_any_installed_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with pytest.raises(recovery.RecoveryRejected, match=r"^owner_root_required$"):
        recovery.RootOperations()
