"""D1:公开退役check/prepare的真实合成封印与有限崩溃恢复;无现场策略操作。"""

import json
from pathlib import Path

import pytest

from paper_radar.live_evidence import preparation_retirement
from paper_radar.live_evidence.live_install import json_bytes
from tests.preparation_retirement_support import assert_business_unchanged, case


def test_check_is_read_only_and_prepare_preserves_original_before_policy_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    before = dict(model.before)
    assert model.gate.check() is True
    assert model.io.writes == []
    assert not model.gate.journal.exists() and not model.gate.snapshot.exists()
    assert all(path.read_bytes() == raw for path, raw in before.items())
    events = []

    def preflight() -> None:
        assert model.gate.snapshot.read_bytes() == before[model.old.journal]
        assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
        events.append("no-secret-preflight")

    assert model.gate.prepare(preflight, lambda: events.append("idle")) is True
    assert events == ["idle", "no-secret-preflight"]
    assert json.loads(model.old.journal.read_bytes())["phase"] == "removed"
    assert json.loads(model.new.journal.read_bytes())["phase"] == "prepared"
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert model.gate.check() is False
    assert (
        model.gate.prepare(
            lambda: pytest.fail("normal lifecycle handles reentry"), lambda: None
        )
        is False
    )
    assert_business_unchanged(model)


@pytest.mark.parametrize(
    "phase",
    [
        "intent",
        "snapshot",
        "snapshotted",
        "removing",
        "removed",
        "preparing",
        "prepared",
    ],
)
def test_durable_phase_recovery_never_retires_new_policy_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    model = case(tmp_path, monkeypatch)
    real_publish = preparation_retirement.publish
    interrupted = False

    def publish(path: Path, raw: bytes, **kwargs: object) -> None:
        nonlocal interrupted
        real_publish(path, raw, **kwargs)
        matched = (
            path == model.gate.snapshot
            if phase == "snapshot"
            else path == model.gate.journal and json.loads(raw)["phase"] == phase
        )
        if matched and not interrupted:
            interrupted = True
            raise ValueError("synthetic_power_loss")

    with monkeypatch.context() as crash:
        crash.setattr(preparation_retirement, "publish", publish)
        with pytest.raises(ValueError, match=r"^synthetic_power_loss$"):
            model.gate.prepare(lambda: None, lambda: None)
    assert interrupted
    if phase != "prepared":
        with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
            model.gate.prepare(lambda: None, lambda: None)
        assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    else:
        assert model.gate.prepare(lambda: None, lambda: None) is False
    assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
    assert model.gate.snapshot.read_bytes() == model.before[model.old.journal]
    assert_business_unchanged(model)


def test_partial_old_remove_requires_exact_retirement_journal_and_explicit_recover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    real_remove = model.io.remove_profile

    def remove(name: str) -> None:
        real_remove(name)
        raise ValueError("synthetic_remove_interruption")

    with monkeypatch.context() as crash:
        crash.setattr(model.io, "remove_profile", remove)
        with pytest.raises(ValueError, match=r"^synthetic_remove_interruption$"):
            model.gate.prepare(lambda: None, lambda: None)
    with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
        model.gate.prepare(lambda: None, lambda: None)
    model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
    assert_business_unchanged(model)


@pytest.mark.parametrize(
    "change",
    [
        "prepared",
        "missing",
        "unknown",
        "new-file",
        "snapshot",
        "kernel-partial",
        "kernel-extra",
        "kernel-bytes",
        "kernel-unreadable",
    ],
)
def test_unknown_or_installed_preparation_never_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    model = case(tmp_path, monkeypatch)
    reason = "failed_preparation_marker"
    if change in {"prepared", "unknown"}:
        marker = json.loads(model.old.journal.read_bytes())
        marker["phase" if change == "prepared" else "identity"] = (
            "prepared" if change == "prepared" else "f" * 64
        )
        model.old.journal.write_bytes(json_bytes(marker))
    elif change == "missing":
        model.old.journal.unlink()
        reason = "No such file"
    elif change == "new-file":
        model.old.journal.with_name(model.old.journal.name + ".new").write_bytes(
            b"unknown"
        )
        reason = "failed_preparation_pending_file"
    elif change == "snapshot":
        model.gate.snapshot.write_bytes(b"unknown")
        model.gate.snapshot.chmod(0o644)
        reason = "failed_preparation_snapshot"
    elif change == "kernel-partial":
        model.io.profiles.pop(next(iter(model.io.profiles)))
        reason = "apparmor_partial_policy"
    elif change == "kernel-extra":
        model.io.profiles["extra"] = dict(model.io.profiles["0"])
        reason = "apparmor_profile_set_mismatch"
    elif change == "kernel-bytes":
        model.io.profiles["0"]["raw_data"] = b"other bytes"
        reason = "apparmor_blob_mismatch"
    else:
        model.io.unavailable = True
        reason = "apparmor_readback_unavailable"
    with pytest.raises((ValueError, FileNotFoundError), match=reason):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert model.io.writes == []
    assert not model.gate.journal.exists()


def test_active_project_refuses_before_any_retirement_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)

    def active() -> None:
        raise ValueError("project_scope_not_idle")

    with pytest.raises(ValueError, match=r"^project_scope_not_idle$"):
        model.gate.prepare(lambda: None, active)
    assert model.io.writes == [] and not model.gate.journal.exists()
    assert_business_unchanged(model)


def test_installed_main_placement_is_not_failed_preparation_eligibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch, main_policy=True)
    with pytest.raises(ValueError, match=r"^failed_preparation_main_placement$"):
        model.gate.prepare(lambda: None, lambda: None)
    assert model.io.writes == [] and not model.gate.journal.exists()


def test_failed_new_preflight_keeps_original_and_requires_explicit_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.gate.prepare(refused, lambda: None)
    snapshot = model.gate.snapshot.read_bytes()
    with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
        model.gate.prepare(lambda: None, lambda: None)
    model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert (
        model.gate.snapshot.read_bytes() == snapshot == model.before[model.old.journal]
    )
    assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
    assert_business_unchanged(model)


def test_partial_new_add_is_recovered_by_exact_new_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    real_load = model.io.load_binary

    def partial(binary: bytes) -> None:
        real_load(binary)
        model.io.profiles.pop("1")
        raise ValueError("synthetic_add_interruption")

    with monkeypatch.context() as crash:
        crash.setattr(model.io, "load_binary", partial)
        with pytest.raises(ValueError, match=r"^synthetic_add_interruption$"):
            model.gate.prepare(lambda: None, lambda: None)
    model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert [kind for kind, _ in model.io.writes] == [
        "remove",
        "remove",
        "add",
        "remove",
        "add",
    ]
    assert_business_unchanged(model)


@pytest.mark.parametrize(
    "target", ["old-source", "new-source", "main", "journal", "snapshot"]
)
def test_missing_original_or_unknown_retirement_record_never_allows_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    model = case(tmp_path, monkeypatch)
    reason = "runtime_member_identity"
    if target == "old-source":
        (model.old.root / "placement/apparmor.source").write_bytes(b"changed")
        reason = "placement_seal_identity"
    elif target == "new-source":
        (model.new.root / "entry.py").write_bytes(b"changed")
    elif target == "main":
        state = json.loads(model.gate.paths.journal.read_bytes())
        state["payload"] = "f" * 64
        model.gate.paths.journal.write_bytes(json_bytes(state))
        reason = "failed_preparation_main"
    elif target == "journal":
        model.gate.journal.write_bytes(b"{}\n")
        model.gate.journal.chmod(0o644)
        reason = "failed_preparation_journal"
    else:
        model.gate.snapshot.write_bytes(model.before[model.old.journal])
        model.gate.snapshot.chmod(0o644)
        reason = "failed_preparation_snapshot_unowned"
    with pytest.raises(ValueError, match=reason):
        model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert model.io.writes == []


def test_snapshot_changed_after_retirement_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    model.gate.prepare(lambda: None, lambda: None)
    model.gate.snapshot.write_bytes(b"unknown replacement\n")
    writes = list(model.io.writes)
    with pytest.raises(ValueError, match=r"^failed_preparation_snapshot$"):
        model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert model.gate.snapshot.read_bytes() == b"unknown replacement\n"
    assert model.io.writes == writes


@pytest.mark.parametrize(
    "which,phase",
    [
        ("old", "removing"),
        ("old", "removed"),
        ("new", "preparing"),
        ("new", "prepared"),
    ],
)
def test_owned_marker_write_windows_resume_without_overwriting_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, which: str, phase: str
) -> None:
    model = case(tmp_path, monkeypatch)
    # Lifecycle通过公共持久化OS接缝的局部import发布;替换该OS接缝而非内部状态。
    from paper_radar.live_evidence import live_install

    original = live_install.publish
    marker = model.old.journal if which == "old" else model.new.journal
    interrupted = False

    def publish(path: Path, raw: bytes, **kwargs: object) -> None:
        nonlocal interrupted
        original(path, raw, **kwargs)
        if path == marker and json.loads(raw)["phase"] == phase and not interrupted:
            interrupted = True
            raise ValueError("synthetic_marker_interruption")

    with monkeypatch.context() as crash:
        crash.setattr(live_install, "publish", publish)
        with pytest.raises(ValueError, match=r"^synthetic_marker_interruption$"):
            model.gate.prepare(lambda: None, lambda: None)
    assert interrupted
    with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
        model.gate.prepare(lambda: None, lambda: None)
    model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
    assert model.gate.snapshot.read_bytes() == model.before[model.old.journal]
    assert_business_unchanged(model)


@pytest.mark.parametrize("record", ["journal", "snapshot", "new-marker"])
def test_uncommitted_new_file_is_preserved_and_refused_even_in_explicit_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record: str
) -> None:
    model = case(tmp_path, monkeypatch)
    path = {
        "journal": model.gate.journal,
        "snapshot": model.gate.snapshot,
        "new-marker": model.new.journal,
    }[record]
    pending = path.with_name(path.name + ".new")
    pending.write_bytes(b"uncommitted publication; ownership is not guessed\n")
    pending.chmod(0o644)
    for recover in (False, True):
        with pytest.raises(ValueError, match=r"^failed_preparation_pending_file$"):
            model.gate.prepare(lambda: None, lambda: None, recover=recover)
    assert (
        pending.read_bytes() == b"uncommitted publication; ownership is not guessed\n"
    )
    assert model.io.writes == []
    assert_business_unchanged(model)


def test_stopped_old_collection_refuses_and_preserves_original_budget_and_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    from datetime import UTC, datetime

    from paper_radar.live_evidence.collection import ProtectedCollection
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.model_manifest import parse_manifest
    from tests.test_live_epoch_upgrade import BINDING

    model = case(tmp_path, monkeypatch)
    paths = model.gate.paths
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=paths.anchor)
    )
    old = parse_manifest((paths.runtime / "model-manifest.json").read_bytes())
    collection = ProtectedCollection(ledger)
    now = datetime.now(UTC)
    plan = old.cells[0].plan
    collection.approve_plan(plan, now=now)
    run = collection.start_round(plan.plan_id, binding=BINDING, now=now)
    collection.reserve(run.round_id, plan.cases[0], "auth", now=now)
    collection.recover_interrupted(now=now)
    before = collection.status(plan.plan_id, now=now)
    database = ledger.database.read_bytes()
    assert before.stopped and before.network_used == 1
    with pytest.raises(ValueError, match=r"^failed_preparation_stopped$"):
        model.gate.prepare(lambda: None, lambda: None)
    assert collection.status(plan.plan_id, now=now) == before
    assert ledger.database.read_bytes() == database
    assert model.io.writes == [] and not model.gate.journal.exists()
