"""Independent D1: fixed recovery exception, fixture and mocks only."""

import json
from pathlib import Path
from typing import cast

import pytest

from scripts import issue167_h1_recovery_once as recovery

FIXTURE = Path(__file__).parent / "fixtures" / "issue167_v4_recovery_table.json"


def snapshot() -> object:
    return json.loads(FIXTURE.read_text())


def test_actual_export_is_exact_fixed_exception() -> None:
    recovery.require_table(snapshot())


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('"handle": 23', '"handle": 24'),
        ('"844648"', '"844649"'),
        ('"844648"', "844648"),
        ('"packets": 8', '"packets": 9'),
        ('"bytes": 512', '"bytes": 513'),
        ('"prio": 10', '"prio": 11'),
        ('"right": 38167', '"right": 38169'),
        ('"admin-prohibited"', '"port-unreachable"'),
        ('"policy": "accept"', '"policy": "drop"'),
    ],
)
def test_no_snapshot_drift_is_implicitly_accepted(before: str, after: str) -> None:
    original = FIXTURE.read_text()
    assert before in original
    changed = json.loads(original.replace(before, after))
    with pytest.raises(recovery.RecoveryRejected, match=r"^recovery_snapshot_changed$"):
        recovery.require_table(changed)


class FakeOperations:
    def __init__(self, failure: str = "") -> None:
        self.events: list[str] = []
        self.failure = failure
        self.reserved = False
        self.tables_read = 0

    def event(self, name: str) -> None:
        self.events.append(name)
        if name == self.failure:
            raise recovery.RecoveryRejected("injected_unknown")

    def preflight(self) -> None:
        self.event("preflight")

    def reserve(self) -> None:
        self.event("reserve")
        if self.reserved:
            raise FileExistsError("already_reserved")
        self.reserved = True

    def table(self) -> object:
        self.event("table")
        self.tables_read += 1
        if self.failure == "second_snapshot" and self.tables_read == 2:
            return {"nftables": []}
        return snapshot()

    def delete_table(self) -> None:
        self.event("delete_table")

    def remove_units(self) -> None:
        self.event("remove_units")

    def verify_restored(self) -> None:
        self.event("verify_restored")


def test_recovery_is_independent_of_experiment_success() -> None:
    operations = FakeOperations()
    result = recovery.recover(operations)
    assert result["restoration_result"] == "host_policy_restored"
    assert result["experiment_result"] == "unknown"
    assert result["original_numeric_binding"] == "unknown_owner_exception"
    assert result["probe_attempts"] == 0
    assert operations.events == [
        "preflight",
        "table",
        "reserve",
        "preflight",
        "table",
        "delete_table",
        "remove_units",
        "verify_restored",
    ]


@pytest.mark.parametrize("failure", ["preflight", "reserve", "second_snapshot"])
def test_failures_before_mutation_do_not_delete(failure: str) -> None:
    operations = FakeOperations(failure)
    with pytest.raises(
        recovery.RecoveryRejected,
        match=r"^(injected_unknown|recovery_snapshot_changed)$",
    ):
        recovery.recover(operations)
    assert "delete_table" not in operations.events
    assert "remove_units" not in operations.events
    assert operations.reserved is (failure == "second_snapshot")


@pytest.mark.parametrize("failure", ["delete_table", "remove_units", "verify_restored"])
def test_failure_after_reservation_never_retries(failure: str) -> None:
    operations = FakeOperations(failure)
    with pytest.raises(recovery.RecoveryRejected, match=r"^injected_unknown$"):
        recovery.recover(operations)
    assert operations.reserved
    operations.events.clear()
    with pytest.raises(FileExistsError, match=r"^already_reserved$"):
        recovery.recover(operations)
    assert operations.events == ["preflight", "table", "reserve"]


def test_partial_recovery_reports_stage_without_claiming_restored() -> None:
    progress: dict[str, str] = {}
    operations = FakeOperations("remove_units")
    with pytest.raises(recovery.RecoveryRejected, match=r"^injected_unknown$"):
        recovery.recover(operations, progress)
    assert progress == {"stage": "remove_units", "last_completed_stage": "delete_table"}
    assert operations.events[-2:] == ["delete_table", "remove_units"]


def test_root_reservation_is_persistent_exclusive_and_private(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "recovery.json"
    monkeypatch.setattr(recovery, "RESERVATION", marker)
    monkeypatch.setattr(recovery, "LEDGER_ROOT", tmp_path)
    operations = object.__new__(recovery.RootOperations)
    operations.ledger_sha = "synthetic-ledger-digest"
    operations.reserve()
    assert marker.stat().st_mode & 0o777 == 0o600
    assert marker.stat().st_nlink == 1
    value = json.loads(marker.read_bytes())
    assert value["state"] == "reserved_unknown"
    assert value["ledger_sha256"] == "synthetic-ledger-digest"
    original = marker.read_bytes()
    with pytest.raises(FileExistsError, match=r"recovery\.json"):
        operations.reserve()
    assert marker.read_bytes() == original


def test_unknown_output_never_contains_exception_text(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail() -> recovery.RootOperations:
        raise RuntimeError("PRIVATE_EXCEPTION_SENTINEL")

    monkeypatch.setattr(recovery, "RootOperations", fail)
    assert recovery.main() == 1
    output = capsys.readouterr()
    value = cast(dict[str, object], json.loads(output.out))
    assert value["restoration_result"] == "unknown"
    assert value["failure_reason"] == "fixed_recovery_incomplete"
    assert value["no_retry"] is True
    assert "PRIVATE_EXCEPTION_SENTINEL" not in output.out + output.err
