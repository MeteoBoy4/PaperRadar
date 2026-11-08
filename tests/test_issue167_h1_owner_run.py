"""Independent D1 owner automation; no root, service, nft, network or credentials."""

from __future__ import annotations

import copy
import hashlib
import json
import signal
import time
from pathlib import Path
from typing import ClassVar, cast

import pytest

from scripts import issue167_h1_owner_ops as owner
from scripts import issue167_h1_owner_run as runner
from scripts.issue167_h1_phase import Plan


@pytest.fixture
def plan() -> Plan:
    return Plan("74da91c0be23", 1000, 1000)


def record(run_id: str, *, successful: bool = True) -> dict[str, object]:
    data: dict[str, object] = {
        "scope": "h1_synthetic_local_only",
        "run_id": run_id,
        "result": "observed_expected" if successful else "unknown",
        "phase_counts": {
            "a": {"allowed_packet_delta": 4, "rejected_packet_delta": 8},
            "b": {"allowed_packet_delta": 4, "rejected_packet_delta": 8},
        },
        "leftover_refused": True,
        "cleanup_complete": True,
        "table_may_remain": False,
        "auth_calls": 0,
        "model_calls": 0,
        "guardian_metadata": {
            "uid_is_root": True,
            "core_limits": [0, 0],
            "no_new_privs": True,
            "capabilities": dict.fromkeys(
                ("chown", "dac_read_search", "kill", "setgid", "setuid", "net_admin"),
                True,
            ),
        },
    }
    if not successful:
        data["phase_counts"] = {}
        data["leftover_refused"] = False
        data["failure_reason"] = "observer_failure"
        data["failure_stage"] = "peer_start"
        data["os_error_category"] = "permission_denied"
    return data


class MockOperations:
    def __init__(
        self,
        plan: Plan,
        *,
        fail: str = "",
        interrupt: bool = False,
        unknown: bool = False,
    ) -> None:
        self.plan = plan
        self.fail = fail
        self.interrupt = interrupt
        self.unknown = unknown
        self.events: list[str] = []

    def event(self, name: str) -> None:
        self.events.append(name)
        if name == self.fail:
            if self.interrupt:
                raise runner.OwnerInterrupted
            raise RuntimeError("external-error-must-not-leak")

    def preflight(self) -> None:
        self.event("preflight")

    def install(self) -> None:
        self.event("install")

    def verify(self) -> None:
        self.event("verify")

    def start(self) -> None:
        self.event("start")

    def wait(self) -> None:
        self.event("wait")

    def collect(self) -> runner.Collected:
        self.event("collect")
        value = record(self.plan.run_id, successful=not self.unknown)
        return runner.Collected(value, copy.deepcopy(value))

    def restore(self) -> dict[str, object]:
        self.event("restore")
        return {
            "result": "host_policy_restored",
            "ledger_retained": True,
            "runtime_retained": True,
            "code_retained": True,
            "auth_calls": 0,
            "model_calls": 0,
        }

    def finish(self) -> dict[str, object]:
        self.event("finish")
        return {
            "result": "successful_artifacts_removed",
            "ledger_retained": True,
            "auth_calls": 0,
            "model_calls": 0,
        }


def test_success_caches_records_before_restore_and_finish(plan: Plan) -> None:
    operations = MockOperations(plan)
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert operations.events == [
        "preflight",
        "install",
        "verify",
        "start",
        "wait",
        "collect",
        "restore",
        "finish",
    ]
    assert result["owner_result"] == "observed_expected_and_restored"
    assert result["guardian_result"] == result["ledger"] == record(plan.run_id)


@pytest.mark.parametrize(
    "failure", ["preflight", "install", "verify", "start", "wait", "collect"]
)
def test_failure_never_restarts_or_finishes_and_cleans_only_after_preflight(
    plan: Plan,
    failure: str,
) -> None:
    operations = MockOperations(plan, fail=failure)
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert result["owner_result"] == "unknown"
    assert result["failure_stage"] == failure
    assert "finish" not in operations.events
    assert operations.events.count("start") <= 1
    assert operations.events.count("install") <= 1
    assert ("restore" in operations.events) is (failure != "preflight")
    assert "external-error" not in json.dumps(result)


def test_partial_install_failure_uses_scope_checked_restore(plan: Plan) -> None:
    operations = MockOperations(plan, fail="install")
    runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert operations.events == ["preflight", "install", "restore"]


def test_unknown_probe_preserves_records_and_skips_finish(plan: Plan) -> None:
    operations = MockOperations(plan, unknown=True)
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert result["owner_result"] == "unknown"
    assert result["guardian_result"] == record(plan.run_id, successful=False)
    assert operations.events[-1] == "restore"


def test_interrupt_runs_restore_once_and_does_not_finish(plan: Plan) -> None:
    operations = MockOperations(plan, fail="wait", interrupt=True)
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert result["owner_result"] == "interrupted"
    assert operations.events.count("restore") == 1
    assert "finish" not in operations.events


def test_restore_failure_retains_unknown_and_never_finishes(plan: Plan) -> None:
    operations = MockOperations(plan, fail="restore")
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert result["owner_result"] == "unknown"
    assert result["restoration_error"] == "restoration_unknown"
    assert "finish" not in operations.events


def test_finish_failure_does_not_repeat_any_operation(plan: Plan) -> None:
    operations = MockOperations(plan, fail="finish")
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert result["owner_result"] == "unknown"
    assert result["failure_stage"] == "finish"
    assert operations.events.count("finish") == 1


@pytest.mark.parametrize(
    "tamper", ["bool_count", "extra", "missing_fact", "bad_reason", "float_core"]
)
def test_root_record_rejects_wrong_types_and_unbounded_text(
    plan: Plan, tamper: str
) -> None:
    value = record(plan.run_id)
    if tamper == "bool_count":
        value["auth_calls"] = False
    elif tamper == "extra":
        value["arbitrary"] = "external-secret-like-text"
    elif tamper == "missing_fact":
        del value["guardian_metadata"]
    elif tamper == "bad_reason":
        value["failure_reason"] = "external-secret-like-text"
    else:
        facts = cast(dict[str, object], value["guardian_metadata"])
        facts["core_limits"] = [0.0, 0]
    with pytest.raises(runner.OwnerRunRejected, match=r"^probe_metadata_invalid$"):
        runner.guardian_record(value, run_id=plan.run_id)


def test_bad_collector_cannot_export_raw_extra_metadata(plan: Plan) -> None:
    operations = MockOperations(plan)
    value = record(plan.run_id)
    value["raw"] = "external-data-must-not-leak"
    operations.collect = lambda: runner.Collected(value, copy.deepcopy(value))  # type: ignore[method-assign]
    result = runner.run_owner(plan, operations, manifest_sha256="a" * 64)
    assert result["guardian_result"] is None
    assert result["ledger"] is None
    assert operations.events[-1] == "restore"
    assert "external-data" not in repr(result)


def test_retry_verifies_readonly_old_ledger_and_never_changes_it(
    plan: Plan,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_run = "6e70b5a31d42"
    raw = json.dumps(record(old_run, successful=False), sort_keys=True).encode()
    value = {
        "kind": "additional_attempt_after_unknown",
        "predecessor_run_id": old_run,
        "predecessor_manifest_sha256": "b" * 64,
        "predecessor_ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "additional_attempts": 1,
    }
    reads: list[Path] = []
    monkeypatch.setattr(runner, "read_json", lambda _path, **_kwargs: value)
    monkeypatch.setattr(runner, "protected_path", lambda _path: None)

    def read(path: Path, *, limit: int) -> bytes:
        reads.append(path)
        assert limit == 16384
        return raw

    monkeypatch.setattr(runner, "protected_file_bytes", read)
    result = runner.validate_retry(tmp_path, plan)
    assert result["history_verified"] is True
    assert reads == [owner.LEDGER_ROOT / f"issue167-{old_run}.json"]


@pytest.mark.parametrize(
    "tamper", ["same_id", "bool_attempt", "wrong_hash", "prior_success"]
)
def test_retry_rejects_reset_or_unbound_history(
    plan: Plan,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
) -> None:
    old_run = "6e70b5a31d42"
    raw = json.dumps(record(old_run, successful=tamper == "prior_success")).encode()
    value = {
        "kind": "additional_attempt_after_unknown",
        "predecessor_run_id": old_run,
        "predecessor_manifest_sha256": "b" * 64,
        "predecessor_ledger_sha256": hashlib.sha256(raw).hexdigest(),
        "additional_attempts": 1,
    }
    expected = "retry_context_invalid"
    if tamper == "same_id":
        value["predecessor_run_id"] = plan.run_id
    elif tamper == "bool_attempt":
        value["additional_attempts"] = True
    elif tamper == "wrong_hash":
        value["predecessor_ledger_sha256"] = "0" * 64
        expected = "retry_history_mismatch"
    else:
        expected = "retry_history_invalid"
    monkeypatch.setattr(runner, "read_json", lambda _path, **_kwargs: value)
    monkeypatch.setattr(runner, "protected_path", lambda _path: None)
    monkeypatch.setattr(runner, "protected_file_bytes", lambda *_args, **_kwargs: raw)
    with pytest.raises(runner.OwnerRunRejected, match=f"^{expected}$"):
        runner.validate_retry(tmp_path, plan)


def test_signal_context_and_cleanup_shield_restore_handlers() -> None:
    original = {
        number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)
    }
    with runner.signal_cleanup():
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        with pytest.raises(runner.OwnerInterrupted):
            handler(signal.SIGINT, None)
        with runner.cleanup_signal_shield():
            assert signal.getsignal(signal.SIGINT) == signal.SIG_IGN
            assert signal.getsignal(signal.SIGTERM) == signal.SIG_IGN
    assert {number: signal.getsignal(number) for number in original} == original


class MetadataCommands:
    tools: ClassVar[dict[str, Path]] = {"systemctl": Path("/usr/bin/systemctl")}

    def __init__(self, plan: Plan) -> None:
        self.plan = plan
        self.calls: list[tuple[str, ...]] = []
        self.guardian_reads = 0

    def _run(self, argv: tuple[str, ...], data: bytes = b"") -> bytes:
        self.calls.append(argv)
        if "show" in argv:
            unit = argv[2]
            if unit == self.plan.guardian_unit:
                self.guardian_reads += 1
            active = self.guardian_reads < 2
            state = "active" if active else "failed"
            return (
                f"LoadState=loaded\nActiveState={state}\n"
                "SubState=running\nResult=success\n"
            ).encode()
        return b""


def test_live_wrapper_verifies_then_starts_exact_units_once(
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.issue167_h1_guardian import Commands

    commands = MetadataCommands(plan)
    live = runner.LiveRunner(plan, cast(Commands, commands))
    monkeypatch.setattr(runner, "protected_path", lambda _path: None)
    monkeypatch.setattr(
        owner, "check_units", lambda *args, **kwargs: {plan.unit, plan.guardian_unit}
    )
    live.verify()
    live.start()
    assert commands.calls[0] == (
        "/usr/bin/systemd-analyze",
        "verify",
        "--man=no",
        str(plan.install_root / plan.unit),
        str(plan.install_root / plan.guardian_unit),
    )
    assert commands.calls[1:] == [
        ("/usr/bin/systemctl", "start", plan.guardian_unit),
        ("/usr/bin/systemctl", "start", plan.unit),
    ]


def test_live_wait_is_bounded_and_only_queries_exact_units(
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.issue167_h1_guardian import Commands

    commands = MetadataCommands(plan)
    live = runner.LiveRunner(plan, cast(Commands, commands))
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    live.wait()
    assert len(commands.calls) == 4
    assert {call[2] for call in commands.calls} == {plan.unit, plan.guardian_unit}
    before = len(commands.calls)
    with pytest.raises(runner.OwnerRunRejected, match=r"^unit_scope_unknown$"):
        live.state("foreign.service")
    assert len(commands.calls) == before
    ticks = iter((0.0, 211.0))
    monkeypatch.setattr(time, "monotonic", lambda: next(ticks))
    with pytest.raises(runner.OwnerRunRejected, match=r"^guardian_timeout$"):
        live.wait()


def test_live_collect_requires_matching_root_records(
    plan: Plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.issue167_h1_guardian import Commands

    commands = MetadataCommands(plan)
    live = runner.LiveRunner(plan, cast(Commands, commands))
    monkeypatch.setattr(runner, "protected_path", lambda _path: None)
    value = record(plan.run_id)
    monkeypatch.setattr(
        runner, "read_json", lambda *args, **kwargs: copy.deepcopy(value)
    )
    assert live.collect().successful is True

    def mismatched(path: Path, **kwargs: object) -> object:
        return (
            value
            if path.name == "guardian-result.json"
            else record(plan.run_id, successful=False)
        )

    monkeypatch.setattr(runner, "read_json", mismatched)
    assert live.collect().successful is False


def test_root_metadata_loader_rejects_symlinks_before_reading(tmp_path: Path) -> None:
    import errno

    target = tmp_path / "synthetic-only"
    target.write_text("synthetic-data")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError) as error:
        runner.protected_file_bytes(link, limit=16)
    assert error.value.errno == errno.ELOOP
    with pytest.raises(runner.OwnerRunRejected, match=r"^root_metadata_invalid$"):
        runner.protected_file_bytes(target, limit=16)


@pytest.mark.parametrize("missing", ["guardian", "ledger", "reserved"])
def test_collect_attempts_both_sources_and_retains_unknown_durable_state(
    plan: Plan, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    from scripts.issue167_h1_guardian import Commands

    live = runner.LiveRunner(plan, cast(Commands, MetadataCommands(plan)))
    reads = []

    def read(path: Path, **kwargs: object) -> object:
        is_guardian = path.name == "guardian-result.json"
        reads.append("guardian" if is_guardian else "ledger")
        if (is_guardian and missing in {"guardian", "reserved"}) or (
            not is_guardian and missing == "ledger"
        ):
            raise FileNotFoundError
        if not is_guardian and missing == "reserved":
            return {"run_id": plan.run_id, "state": "reserved_unknown"}
        return record(plan.run_id, successful=False)

    monkeypatch.setattr(runner, "read_json", read)
    monkeypatch.setattr(runner, "protected_path", lambda _path: None)
    result = live.collect()
    assert reads == ["guardian", "ledger"]
    assert result.successful is False
    if missing == "reserved":
        assert result.ledger == {"run_id": plan.run_id, "state": "reserved_unknown"}
