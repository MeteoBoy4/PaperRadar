"""D1:一跳认证失败必须在任何业务/kernel写入之前保全拒绝。"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.placement_policy import MEMBERS
from paper_radar.live_evidence.preparation_retirement import (
    FailedPreparationRetirement,
    describe_preparation_recovery,
)
from tests.preparation_recovery_support import (
    RecoveryCase,
    assert_preserved,
    recovery_case,
)
from tests.preparation_retirement_support import reseal


def refresh_gate(model: RecoveryCase) -> None:
    reseal(model.gate.staged)
    model.gate = FailedPreparationRetirement(
        model.gate.staged,
        model.gate.paths,
        owner_uid=os.getuid(),
        kernel_io=model.original.io,
    )


def update_spec(model: RecoveryCase, update: object) -> None:
    # Mutations below are explicit test inputs, never a production descriptor source.
    path = model.gate.staged / "deployment.json"
    spec = json.loads(path.read_bytes())
    assert callable(update)
    update(spec)
    path.write_bytes(json_bytes(spec))
    refresh_gate(model)


@pytest.mark.parametrize("member", MEMBERS)
def test_every_placement_member_requires_original_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, member: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    path = model.gate.staged / member
    path.write_bytes(path.read_bytes() + b"changed member")
    with pytest.raises(ValueError, match=r"^preparation_recovery_policy_change$"):
        describe_preparation_recovery(
            model.source.staged, model.gate.staged, model.source.journal.read_bytes()
        )
    refresh_gate(model)
    with pytest.raises(ValueError, match=r"^preparation_recovery_policy_change$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize(
    "field", ["payload_sha256", "runtime_manifest_sha256", "journal_sha256"]
)
def test_each_sealed_source_digest_is_reauthenticated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    update_spec(
        model, lambda spec: spec["preparation_recovery"].__setitem__(field, "f" * 64)
    )
    reason = (
        "No such file"
        if field == "payload_sha256"
        else "runtime_manifest_identity"
        if field == "runtime_manifest_sha256"
        else "preparation_recovery_source"
    )
    with pytest.raises((ValueError, FileNotFoundError), match=reason):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize(
    "malformed",
    [
        "prepared",
        "installed",
        "unknown",
        "bool",
        "float",
        "noncanonical",
        "extra",
        "missing",
        "list",
    ],
)
def test_even_resealed_tuple_cannot_authorize_other_original_journal_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, malformed: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    value = json.loads(model.source.journal.read_bytes())
    if malformed in {"prepared", "installed", "unknown"}:
        value["phase"] = malformed
    elif malformed in {"bool", "float"}:
        value["format_version"] = True if malformed == "bool" else 1.0
    elif malformed == "extra":
        value["untrusted"] = "extra"
    elif malformed == "missing":
        value.pop("descriptor")
    elif malformed == "list":
        value = []
    raw = (
        json.dumps(value).encode() if malformed == "noncanonical" else json_bytes(value)
    )
    model.source.journal.write_bytes(raw)
    update_spec(
        model,
        lambda spec: spec["preparation_recovery"].__setitem__(
            "journal_sha256", hashlib.sha256(raw).hexdigest()
        ),
    )
    with pytest.raises(ValueError, match=r"^preparation_recovery_journal$"):
        model.gate.check(recover=True)
    assert model.source.journal.read_bytes() == raw
    assert not model.gate.journal.exists() and model.original.io.writes == []


@pytest.mark.parametrize(
    "target", ["source-journal", "own-journal", "snapshot", "old-marker", "new-marker"]
)
def test_pending_publication_is_never_guessed_or_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    path = {
        "source-journal": model.source.journal,
        "own-journal": model.gate.journal,
        "snapshot": model.source.snapshot,
        "old-marker": model.original.old.journal,
        "new-marker": model.original.new.journal,
    }[target]
    pending = path.with_name(path.name + ".new")
    pending.write_bytes(b"pending, ownership unknown\n")
    pending.chmod(0o644)
    with pytest.raises(ValueError, match=r"^failed_preparation_pending_file$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert pending.read_bytes() == b"pending, ownership unknown\n"
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize(
    "change",
    [
        "journal-other",
        "snapshot-missing",
        "snapshot-wrong",
        "new-prepared",
        "kernel-absent",
        "kernel-partial",
        "old-marker",
        "main",
    ],
)
def test_unknown_or_non_initial_state_cannot_claim_preparing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    reason = {
        "journal-other": "failed_preparation_journal_conflict",
        "snapshot-missing": "failed_preparation_snapshot_missing",
        "snapshot-wrong": "failed_preparation_snapshot",
        "new-prepared": "failed_preparation_new_marker",
        "kernel-absent": "preparation_recovery_policy_missing",
        "kernel-partial": "apparmor_partial_policy",
        "old-marker": "failed_preparation_marker",
        "main": "failed_preparation_main",
    }[change]
    if change == "journal-other":
        path = model.gate.paths.ledger / (
            "placement-retirement-v1-" + "f" * 64 + ".json"
        )
        path.write_bytes(b"{}\n")
        path.chmod(0o644)
    elif change == "snapshot-missing":
        model.source.snapshot.unlink()
    elif change == "snapshot-wrong":
        model.source.snapshot.write_bytes(b"wrong snapshot\n")
    elif change in {"old-marker", "new-prepared"}:
        path = (
            model.original.old.journal
            if change == "old-marker"
            else model.original.new.journal
        )
        value = json.loads(path.read_bytes())
        value["phase"] = "prepared"
        path.write_bytes(json_bytes(value))
    elif change == "kernel-absent":
        model.original.io.profiles.clear()
    elif change == "kernel-partial":
        model.original.io.profiles.pop("1")
    else:
        path = model.gate.paths.journal
        value = json.loads(path.read_bytes())
        value["payload"] = "f" * 64
        path.write_bytes(json_bytes(value))
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert not model.gate.journal.exists() and model.original.io.writes == []


@pytest.mark.parametrize("untrusted", ["symlink", "mode", "hardlink", "oversize"])
def test_original_journal_requires_protected_regular_single_link_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, untrusted: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    path = model.source.journal
    reason = "failed_preparation_record"
    if untrusted == "symlink":
        destination = tmp_path / "untrusted-record"
        destination.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(destination)
        reason = "protected_identity"
    elif untrusted == "mode":
        path.chmod(0o600)
    elif untrusted == "hardlink":
        os.link(path, tmp_path / "extra-link")
    else:
        path.write_bytes(b"x" * 16385)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.check(recover=True)
    assert not model.gate.journal.exists() and model.original.io.writes == []


def test_source_tree_trust_precedes_recovery_policy_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    (model.source.staged / "entry.py").chmod(0o666)
    with pytest.raises(ValueError, match=r"^protected_identity$"):
        model.gate.check(recover=True)
    assert not model.gate.journal.exists() and model.original.io.writes == []


@pytest.mark.parametrize("change", ["descriptor", "epoch", "upgrade", "host-tools"])
def test_original_retirement_and_full_deployment_continuity_are_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)

    def mutate(spec: dict[str, Any]) -> None:
        if change == "descriptor":
            spec["failed_preparation"]["marker_sha256"] = "f" * 64
        elif change == "epoch":
            spec["epoch_upgrade"]["deployed_at"] = "2026-01-01T00:00:00Z"
        elif change == "upgrade":
            spec["upgrade_from"][0] = "f" * 64
        else:
            spec["host_tools"]["/usr/bin/busctl"]["sha256"] = "f" * 64

    update_spec(model, mutate)
    with pytest.raises(ValueError, match=r"^preparation_recovery_continuity$"):
        model.gate.check(recover=True)
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize(
    "malformed", ["missing", "extra", "null", "integer", "without-retirement"]
)
def test_recovery_descriptor_is_exactly_three_typed_digests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, malformed: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)

    def mutate(spec: dict[str, Any]) -> None:
        if malformed == "missing":
            spec["preparation_recovery"].pop("journal_sha256")
        elif malformed == "extra":
            spec["preparation_recovery"]["runtime"] = "/arbitrary/path"
        elif malformed == "null":
            spec["preparation_recovery"] = None
        elif malformed == "integer":
            spec["preparation_recovery"]["journal_sha256"] = 1
        else:
            spec.pop("failed_preparation")

    reason = (
        "preparation_recovery_requires_retirement"
        if malformed == "without-retirement"
        else "journal_sha256|runtime|PreparationRecovery"
    )
    with pytest.raises(ValueError, match=reason):
        update_spec(model, mutate)
    assert model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize(
    "phase", ["intent", "snapshotted", "removed", "preparing-no-recovery"]
)
def test_own_journal_cannot_drop_recovery_identity_or_invent_other_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.gate.prepare(refused, lambda: None, recover=True)
    value = json.loads(model.gate.journal.read_bytes())
    if phase == "preparing-no-recovery":
        value.pop("preparation_recovery")
    else:
        value["phase"] = phase
    model.gate.journal.write_bytes(json_bytes(value))
    with pytest.raises(ValueError, match=r"^failed_preparation_journal$"):
        model.gate.check(recover=True)
    assert model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize("kind", ["self", "chain"])
def test_read_only_derivation_refuses_self_and_recursive_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    old = model.source.staged
    raw = model.source.journal.read_bytes()
    new = old if kind == "self" else model.gate.staged
    if kind == "chain":
        path = old / "deployment.json"
        spec = json.loads(path.read_bytes())
        spec["preparation_recovery"] = json.loads(
            (new / "deployment.json").read_bytes()
        )["preparation_recovery"]
        path.write_bytes(json_bytes(spec))
        reseal(old)
    with pytest.raises(ValueError, match=r"^preparation_recovery_one_hop$"):
        describe_preparation_recovery(old, new, raw)
    assert not model.gate.journal.exists() and model.original.io.writes == []


def test_journal_read_race_is_detected_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    original = Path.read_bytes
    path = model.source.journal

    def read(target: Path) -> bytes:
        raw = original(target)
        if target == path:
            target.write_bytes(raw + b"race\n")
        return raw

    with monkeypatch.context() as race:
        race.setattr(Path, "read_bytes", read)
        with pytest.raises(ValueError, match=r"^failed_preparation_record_changed$"):
            model.gate.check(recover=True)
    assert not model.gate.journal.exists() and model.original.io.writes == []


def test_existing_global_stop_and_budget_history_cannot_be_reset_by_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from paper_radar.live_evidence.collection import ProtectedCollection
    from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
    from paper_radar.live_evidence.model_manifest import parse_manifest
    from tests.test_live_epoch_upgrade import BINDING

    model = recovery_case(tmp_path, monkeypatch)
    paths = model.gate.paths
    ledger = EvidenceLedger(
        paths.ledger, trust=LedgerTrust(owner_uid=os.getuid(), anchor=paths.anchor)
    )
    collection = ProtectedCollection(ledger)
    manifest = parse_manifest((paths.runtime / "model-manifest.json").read_bytes())
    now = datetime.now(UTC)
    plan = manifest.cells[0].plan
    collection.approve_plan(plan, now=now)
    run = collection.start_round(plan.plan_id, binding=BINDING, now=now)
    collection.reserve(run.round_id, plan.cases[0], "auth", now=now)
    collection.recover_interrupted(now=now)
    before = collection.status(plan.plan_id, now=now)
    database = ledger.database.read_bytes()
    with pytest.raises(ValueError, match=r"^failed_preparation_stopped$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert before.stopped and before.network_used == 1
    assert collection.status(plan.plan_id, now=now) == before
    assert ledger.database.read_bytes() == database
    assert not model.gate.journal.exists() and model.original.io.writes == []


def test_new_payload_without_handoff_descriptor_keeps_original_journal_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    update_spec(model, lambda spec: spec.pop("preparation_recovery"))
    with pytest.raises(ValueError, match=r"^failed_preparation_journal_conflict$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize("change", ["site", "owner-input", "window"])
def test_site_owner_input_and_original_window_cannot_change_during_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    root = model.gate.staged
    reason = "preparation_recovery_continuity"
    if change == "site":
        path = root / "site.json"
        value = json.loads(path.read_bytes())
        value["product_gid"] += 1
    elif change == "owner-input":
        path = root / "network-owner-confirmation.json"
        value = json.loads(path.read_bytes())
        value["owner_input"]["owner_statement"] += " changed"
        reason = "epoch_upgrade_continuity"
    else:
        path = root / "model-manifest.json"
        value = json.loads(path.read_bytes())
        value["network"]["ends_at"] = "2030-01-01T00:00:00Z"
        reason = "epoch_upgrade_continuity"
    path.write_bytes(json_bytes(value))
    refresh_gate(model)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)
