"""Independent D1: future recovery contract, temporary metadata and mocked commands."""

import io
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

from scripts import issue167_h1_owner_ops as old_owner
from scripts import issue167_resolver_owner as owner
from scripts.issue167_h1_phase import Plan
from scripts.issue167_resolver_case import Case
from tests.test_issue167_service_egress import (
    HOST,
    bind,
    fixture,
    match,
    profile,
    rules,
)

BEFORE = "d" * 64


def reserve_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[owner.LiveOperations, list[str], Path]:
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(Case, "runtime_root", property(lambda _self: runtime))
    case = Case("ab1234567890", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    ledger = tmp_path / "var" / "runs"
    events: list[str] = []
    ops = object.__new__(owner.LiveOperations)
    ops.case = case
    ops.owner = ModuleType("synthetic_owner")
    monkeypatch.setattr(ops.owner, "LEDGER_ROOT", ledger, raising=False)
    monkeypatch.setattr(ops.owner, "absent", lambda p: not p.exists(), raising=False)
    ops.guard = ModuleType("synthetic_guard")
    monkeypatch.setattr(
        ops.guard, "protected_path", lambda *_a, **_kw: None, raising=False
    )

    def claim(*_args: object) -> io.StringIO:
        events.append("claim")
        return io.StringIO()

    monkeypatch.setattr(ops.guard, "claim_anchor", claim, raising=False)
    ops.root_namespaces = {"mnt": "mnt:[1]", "pid": "pid:[1]"}
    ops.global_resolver_sha = BEFORE
    ops.anchor = None
    original_write = ops._write

    def write(path: Path, value: object, mode: int = 0o644) -> None:
        events.append("publish:" + path.name)
        original_write(path, value, mode)

    monkeypatch.setattr(ops, "_write", write)
    monkeypatch.setattr(os, "chown", lambda *_a: None)
    return ops, events, runtime / "resolver-baseline.json"


def test_reserve_persists_private_baseline_before_other_runtime_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops, events, baseline = reserve_fixture(tmp_path, monkeypatch)
    ops.reserve()
    assert events[:2] == ["claim", "publish:resolver-baseline.json"]
    assert events.index("publish:resolver-baseline.json") < events.index(
        "publish:owner-namespaces.json"
    )
    assert baseline.stat().st_mode & 0o777 == 0o600
    assert baseline.stat().st_nlink == 1
    assert json.loads(baseline.read_text()) == {
        "run_id": ops.case.run_id,
        "sha256": BEFORE,
    }


@pytest.mark.parametrize("bad", [None, "", "not-a-sha", True])
def test_invalid_baseline_is_rejected_before_claim_or_runtime_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: object
) -> None:
    ops, events, baseline = reserve_fixture(tmp_path, monkeypatch)
    ops.global_resolver_sha = cast(str | None, bad)
    with pytest.raises(owner.OwnerRejected, match=r"^resolver_baseline_unknown$"):
        ops.reserve()
    assert events == []
    assert not baseline.parent.exists()


def restore_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    active: str = "inactive",
    reset_clears: bool = True,
) -> tuple[owner.LiveOperations, list[str], Path, Path]:
    from scripts import issue167_service_egress as egress

    code, units, runtime = (tmp_path / name for name in ("code", "units", "runtime"))
    for directory in (code, units, runtime):
        directory.mkdir()
    p = profile().process
    case = Case(p.run_id, p.uid, p.gid, "a" * 64, "b" * 64, "c" * 64)
    monkeypatch.setattr(Plan, "install_root", property(lambda _self: code))
    monkeypatch.setattr(Case, "runtime_root", property(lambda _self: runtime))
    monkeypatch.setattr(old_owner, "UNIT_ROOT", units)
    monkeypatch.setattr(old_owner, "UNIT_SEARCH", (units,))
    monkeypatch.setattr(old_owner, "protected_path", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        old_owner,
        "manager_scope",
        lambda _commands, unit: {
            "LoadState": "loaded" if (units / unit).exists() else "not-found",
            "FragmentPath": str(units / unit) if (units / unit).exists() else "",
            "DropInPaths": "",
        },
    )
    for directory in (code, units):
        (directory / case.unit).write_bytes(b"owned-fixed-fixture")
    baseline = runtime / "resolver-baseline.json"
    baseline.write_text(json.dumps({"run_id": case.run_id, "sha256": BEFORE}))
    baseline.chmod(0o600)
    state = {"active": active, "present": True}
    events: list[str] = []
    payload = fixture(True)
    rows = payload["nftables"]
    assert isinstance(rows, list)
    for row in rows:
        if "counter" in row:
            row["counter"]["packets"] = row["counter"]["bytes"] = 0
    match(rules(payload)[0])["right"] = "844648"

    def command(argv: tuple[str, ...], data: bytes = b"") -> bytes:
        assert not data
        if "stop" in argv:
            events.append("stop")
        if "show" in argv:
            events.append("state:" + str(state["active"]))
            failed = state["active"] == "failed"
            return (
                f"ActiveState={state['active']}\n"
                f"SubState={'failed' if failed else 'dead'}\nMainPID=0\nControlGroup=\n"
            ).encode()
        if "reset-failed" in argv:
            events.append("reset")
            if state["active"] == "inactive":
                raise owner.OwnerRejected("SYNTHETIC_MANAGER_NO_LONGER_LOADED")
            if reset_clears:
                state["active"] = "inactive"
        if "daemon-reload" in argv:
            events.append("reload")
        if argv[-2:] == ("list", "tables"):
            return json.dumps(
                {
                    "nftables": [{"table": {"family": "inet", "name": p.table}}]
                    if state["present"]
                    else []
                }
            ).encode()
        return b""

    def delete() -> None:
        events.append("delete")
        state["present"] = False

    ops = object.__new__(owner.LiveOperations)
    ops.case, ops.plan, ops.profile = case, p, profile()
    ops.binding, ops.table_created, ops.create_uncertain = bind(), True, False
    ops.enabled, ops.unit_owned, ops.global_resolver_sha = True, True, BEFORE
    ops.snapshots, ops.owner, ops.egress = [], old_owner, egress
    ops.phase = ModuleType("synthetic_phase")
    monkeypatch.setattr(
        ops.phase,
        "read_cgroup_state",
        lambda *_a, **_kw: SimpleNamespace(pids=frozenset()),
        raising=False,
    )
    ops.contract = ModuleType("synthetic_contract")
    monkeypatch.setattr(
        ops.contract, "current_host_context", lambda: HOST, raising=False
    )
    monkeypatch.setattr(
        ops.contract,
        "read_metadata",
        lambda path, **_kw: json.loads(path.read_text()),
        raising=False,
    )
    ops.commands = SimpleNamespace(
        tools={"nft": Path("/usr/sbin/nft"), "systemctl": Path("/usr/bin/systemctl")},
        _run=command,
        snapshot=lambda: payload,
        delete=delete,
    )
    monkeypatch.setattr(ops, "_resolver_digest", lambda: BEFORE)
    return ops, events, units / case.unit, baseline


def test_inactive_manager_gc_does_not_require_reset_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops, events, unit, _baseline = restore_fixture(tmp_path, monkeypatch)
    assert ops.restore()["global_resolver_unchanged"] is True
    assert "reset" not in events
    assert "state:inactive" in events
    assert events.index("delete") < events.index("reload")
    assert not unit.exists()
    assert ops.resolver_check == {
        "run_id": ops.case.run_id,
        "before_sha256": BEFORE,
        "after_sha256": BEFORE,
        "comparison": "same",
        "source": "root_baseline_file_and_post_restore_read",
    }


def test_failed_unit_is_reset_and_checked_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops, events, unit, _baseline = restore_fixture(
        tmp_path, monkeypatch, active="failed"
    )
    ops.restore()
    assert (
        events.index("state:failed")
        < events.index("reset")
        < events.index("state:inactive")
    )
    assert not unit.exists()


def test_failed_reset_state_cannot_unlink_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops, events, unit, _baseline = restore_fixture(
        tmp_path, monkeypatch, active="failed", reset_clears=False
    )
    with pytest.raises(owner.OwnerRejected, match=r"^unit_reset_unknown$"):
        ops.restore()
    assert unit.exists()
    assert events.count("reset") == 1
    assert ops.restoration_stage == "reset_state"


@pytest.mark.parametrize("drift", ["missing", "wrong_run", "wrong_sha", "wrong_mode"])
def test_missing_or_changed_persistent_baseline_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    ops, _events, _unit, baseline = restore_fixture(tmp_path, monkeypatch)
    if drift == "missing":
        baseline.unlink()
    elif drift == "wrong_mode":
        baseline.chmod(0o644)
    else:
        baseline.write_text(
            json.dumps(
                {
                    "run_id": "000000000000"
                    if drift == "wrong_run"
                    else ops.case.run_id,
                    "sha256": "f" * 64 if drift == "wrong_sha" else BEFORE,
                }
            )
        )
    with pytest.raises(owner.OwnerRejected, match=r"^resolver_baseline_unknown$"):
        ops.restore()
    assert ops.restoration_stage == "resolver_baseline"
    assert ops.resolver_check is None


def test_original_global_hash_comparison_is_not_relaxed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops, _events, _unit, _baseline = restore_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(ops, "_resolver_digest", lambda: "e" * 64)
    with pytest.raises(owner.OwnerRejected, match=r"^host_resolver_changed$"):
        ops.restore()
    assert ops.restoration_stage == "global_resolver_compare"
    check = ops.resolver_check
    assert check is not None
    assert check["comparison"] == "changed"


def test_restore_failure_keeps_only_controlled_stage_and_no_external_error() -> None:
    class Fake:
        restoration_stage = "table_delete"
        resolver_check = None

        def __init__(self) -> None:
            self.ledgers: list[dict[str, object]] = []

        def preflight(self) -> None:
            pass

        def reserve(self) -> None:
            pass

        def install(self) -> None:
            pass

        def start(self) -> None:
            pass

        def ready(self) -> dict[str, object]:
            return {}

        def exercise_rules(self) -> dict[str, object]:
            return {}

        def gate(self, sequence: int) -> None:
            pass

        def collect(self) -> dict[str, object]:
            return {}

        def wait_exit(self) -> None:
            pass

        def restore(self) -> dict[str, object]:
            raise RuntimeError("RAW_PRIVATE_EXCEPTION_SENTINEL")

        def finish(self) -> dict[str, object]:
            raise AssertionError("no finish after unknown")

        def write_ledger(self, value: object) -> None:
            self.ledgers.append(json.loads(json.dumps(value)))

    fake = Fake()
    case = Case("ab1234567890", 1000, 1000, "a" * 64, "b" * 64, "c" * 64)
    result = owner.run_owner(case, fake)
    assert result["result"] == "unknown"
    assert result["restoration_stage"] == "table_delete"
    assert fake.ledgers[-1]["restoration_stage"] == "table_delete"
    assert result["resolver_check"] is None
    assert "RAW_PRIVATE_EXCEPTION_SENTINEL" not in json.dumps(result)


def test_diagnostic_unknown_stage_and_self_claimed_check_are_omitted() -> None:
    untrusted = SimpleNamespace(
        restoration_stage="RAW_PRIVATE_DIAGNOSTIC",
        resolver_check={
            "run_id": "ab1234567890",
            "before_sha256": BEFORE,
            "after_sha256": BEFORE,
            "comparison": "changed",
            "source": "root_baseline_file_and_post_restore_read",
        },
    )
    assert owner.restoration_metadata(untrusted, "ab1234567890") == (None, None)
    assert owner.restoration_metadata(SimpleNamespace(), "ab1234567890") == (None, None)


def test_successful_read_check_is_bound_to_run_and_survives_result_copy() -> None:
    value = {
        "run_id": "ab1234567890",
        "before_sha256": BEFORE,
        "after_sha256": BEFORE,
        "comparison": "same",
        "source": "root_baseline_file_and_post_restore_read",
    }
    trusted = SimpleNamespace(restoration_stage="complete", resolver_check=value)
    assert owner.restoration_metadata(trusted, "ab1234567890") == ("complete", value)
    assert owner.restoration_metadata(trusted, "000000000000") == ("complete", None)
