"""Unbound issue 167 synthetic observations; no live Pi or credentials."""

import struct
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.issue167_observation import (
    FileObserver,
    Layer,
    Phase,
    RequestEvent,
    RequestLedger,
)


def test_transient_file_in_descendant_is_seen_with_empty_terminal(
    tmp_path: Path,
) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    sessions = root / "sessions"
    sessions.mkdir()
    with FileObserver(root) as observer:
        observer.launch_started()
        subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; import sys; "
                    "p=Path(sys.argv[1])/'sentinel'; "
                    "p.write_text('synthetic'); p.unlink()"
                ),
                str(sessions),
            ],
            check=True,
        )
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "observed_mutation"
    assert receipt.mutation_events > 0
    assert receipt.terminal_regular_files == 0
    assert not receipt.directory_deleted


def test_directory_deletion_separate_from_terminal_file_count(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    with FileObserver(root) as observer:
        observer.launch_started()
        root.rmdir()
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.directory_deleted
    assert receipt.terminal_regular_files is None
    assert receipt.terminal_status == "terminal_scan_failed"
    # IN_IGNORED means coverage ended; directory absence never proves history zero.
    assert receipt.history == "unknown"
    assert "event_coverage_lost" in receipt.reasons


def test_no_activity_with_full_synthetic_window(tmp_path: Path) -> None:
    with FileObserver(tmp_path) as observer:
        observer.launch_started()
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "zero_observed"
    assert receipt.reasons == ()


def test_missing_reaping_window(tmp_path: Path) -> None:
    with FileObserver(tmp_path) as observer:
        observer.launch_started()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "unknown"
    assert "incomplete_process_window" in receipt.reasons


@pytest.mark.parametrize(
    "payload,reason",
    [
        (struct.pack("iIII", -1, 0x4000, 0, 0), "event_coverage_lost"),
        (b"short", "truncated_event"),
        (struct.pack("iIII", 1, 0x100, 0, 10), "truncated_event"),
    ],
)
def test_event_loss_fails_closed(tmp_path: Path, payload: bytes, reason: str) -> None:
    with FileObserver(tmp_path) as observer:
        observer.launch_started()
        observer.ingest(payload)
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "unknown"
    assert reason in receipt.reasons


def test_new_directory_race_not_treated_as_recursive_coverage(tmp_path: Path) -> None:
    with FileObserver(tmp_path) as observer:
        observer.launch_started()
        child = tmp_path / "new"
        child.mkdir()
        (child / "sentinel").write_text("synthetic")
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "unknown"
    assert "new_directory_race" in receipt.reasons
    assert receipt.terminal_regular_files == 1


def synthetic_peer() -> tuple[RequestLedger, dict[Layer, int]]:
    ledger = RequestLedger(frozenset(Layer))
    # One prompt/CLI can produce several HTTP operations on a reused connection.
    expected = {layer: 1 for layer in Layer}
    expected[Layer.MODEL_HTTP] = 3
    expected[Layer.PACKET] = 4
    for layer in Layer:
        for sequence in range(1, expected[layer] + 1):
            phase = Phase.FOREGROUND
            if layer == Layer.MODEL_HTTP:
                phase = (Phase.FOREGROUND, Phase.WARMUP, Phase.RETRY)[sequence - 1]
            ledger.record(RequestEvent(layer, sequence, phase))
    return ledger, expected


def test_independent_counts_include_warmup_retry_and_refresh() -> None:
    ledger, expected = synthetic_peer()
    receipt = ledger.reconcile(expected)
    assert receipt["status"] == "synthetic_reconciled"
    assert receipt["counts"] == {
        "prompt": 1,
        "cli": 1,
        "tls_connection": 1,
        "packet": 4,
        "model_http": 3,
        "model_ws_connect": 1,
        "model_ws_create": 1,
        "auth_refresh_http": 1,
    }
    assert receipt["phases"]["model_http:warmup"] == 1
    assert receipt["phases"]["model_http:retry"] == 1


@pytest.mark.parametrize(
    "failure,reason",
    [
        ("duplicate", "duplicate_event"),
        ("loss", "independent_count_mismatch"),
        ("observer", "observer_failed"),
        ("unobservable", "layer_unobservable"),
        ("reference", "independent_reference_missing"),
        ("gap", "sequence_gap"),
    ],
)
def test_counter_failure_is_unknown(failure: str, reason: str) -> None:
    ledger, expected = synthetic_peer()
    if failure == "duplicate":
        ledger.record(RequestEvent(Layer.PROMPT, 1, Phase.FOREGROUND))
    elif failure == "loss":
        expected[Layer.MODEL_HTTP] += 1
    elif failure == "observer":
        ledger.observation_failed()
    elif failure == "unobservable":
        ledger.available = frozenset({Layer.PROMPT, Layer.CLI})
    elif failure == "reference":
        del expected[Layer.MODEL_HTTP]
    else:
        ledger.record(RequestEvent(Layer.PROMPT, 3, Phase.FOREGROUND))
    receipt = ledger.reconcile(expected)
    assert receipt["status"] == "unknown"
    assert reason in receipt["reasons"]


def test_replaced_root_is_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_text("synthetic")
    with FileObserver(root) as observer:
        observer.launch_started()
        root.rmdir()
        root.symlink_to(outside, target_is_directory=True)
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "unknown"
    assert receipt.terminal_status == "terminal_root_replaced"
    assert receipt.terminal_regular_files is None


def test_terminal_member_ids_do_not_export_unregistered_names(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    with FileObserver(tmp_path) as observer:
        observer.launch_started()
        (sessions / "sentinel").write_text("synthetic")
        (sessions / "arbitrary-private-name").write_text("synthetic")
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.terminal_members is not None
    assert len(receipt.terminal_members) == 3
    assert all(len(identity) == 64 for _, identity in receipt.terminal_members)
    assert receipt.terminal_regular_files == 2
    assert receipt.terminal_status == "synthetic_snapshot"
    assert "arbitrary-private-name" not in repr(receipt)


def test_snapshot_survives_cleanup_and_has_per_run_path_ids(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    settings = root / "settings.json"
    settings.write_text("synthetic")
    with FileObserver(root) as first, FileObserver(root) as second:
        for observer in (first, second):
            observer.launch_started()
            observer.descendants_reaped()
            observer.snapshot_terminal()
        before = first.receipt()
        independent = second.receipt()
        assert before.terminal_members != independent.terminal_members
        settings.unlink()
        root.rmdir()
        after = first.receipt()
    assert before.terminal_regular_files == 1
    assert not before.directory_deleted
    assert after.directory_deleted
    assert after.terminal_regular_files == 1
    assert after.terminal_members == before.terminal_members
    assert "settings.json" not in repr(after)


def test_cleanup_without_snapshot_preserves_unknown(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    with FileObserver(root) as observer:
        observer.launch_started()
        observer.descendants_reaped()
        root.rmdir()
        receipt = observer.receipt()
    assert receipt.directory_deleted
    assert receipt.terminal_members is None
    assert receipt.terminal_regular_files is None
    assert receipt.terminal_status == "terminal_unknown"


def test_cleanup_loss_does_not_replace_completed_history(tmp_path: Path) -> None:
    root = tmp_path / "attempt"
    root.mkdir()
    with FileObserver(root) as observer:
        observer.launch_started()
        observer.descendants_reaped()
        observer.snapshot_terminal()
        root.rmdir()
        receipt = observer.receipt()
    assert receipt.history == "zero_observed"
    assert receipt.mutation_events == 0
    assert receipt.directory_deleted
    assert receipt.terminal_members == ()
    assert receipt.reasons == ()
    assert "event_coverage_lost" in receipt.cleanup_reasons


def test_running_loss_cannot_be_repaired_by_snapshot(tmp_path: Path) -> None:
    with FileObserver(tmp_path) as observer:
        observer.launch_started()
        observer.ingest(struct.pack("iIII", 1, 0x8000, 0, 0))
        observer.descendants_reaped()
        observer.snapshot_terminal()
        receipt = observer.receipt()
    assert receipt.history == "unknown"
    assert "event_coverage_lost" in receipt.reasons
    assert receipt.cleanup_reasons == ()
