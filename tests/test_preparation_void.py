"""D1: 原记录保全、显式作废和候选失败无策略回滚。"""

import json
import os
from pathlib import Path

import pytest

from tests.preparation_void_support import assert_void_preserved, void_case


class PowerLoss(BaseException):
    pass


def test_failed_native_preflight_rolls_back_to_clean_absence_and_preserves_originals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = void_case(tmp_path, monkeypatch)
    assert model.gate.check() is True
    assert model.original.original.io.writes == []

    def refused() -> None:
        assert all(
            path.read_bytes() == raw for path, raw in model.gate.archives().items()
        )
        assert_void_preserved(model)
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.gate.prepare(refused, lambda: None)
    assert not model.original.original.io.profiles
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "clean"
    assert_void_preserved(model)
    with pytest.raises(ValueError, match=r"^preparation_void_recovery_required$"):
        model.gate.check()
    assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert model.gate.check() is False
    assert_void_preserved(model)


@pytest.mark.parametrize(
    "point",
    [
        "archive",
        "void_intent",
        "failed_policy_removing",
        "clean",
        "candidate_preparing",
        "prepared",
    ],
)
def test_durable_checkpoint_crashes_restore_only_known_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    from paper_radar.live_evidence import preparation_void

    model = void_case(tmp_path, monkeypatch)
    from paper_radar.live_evidence.live_install import publish

    real = publish
    cut = False

    def interrupted(
        path: Path, raw: bytes, *, replace: bool = False, mode: int = 0o644
    ) -> None:
        nonlocal cut
        real(path, raw, replace=replace, mode=mode)
        matches = (
            path in model.gate.archives()
            if point == "archive"
            else path == model.gate.journal and json.loads(raw)["phase"] == point
        )
        if matches and not cut:
            cut = True
            raise PowerLoss()

    with monkeypatch.context() as crash:
        crash.setattr(preparation_void, "publish", interrupted)
        with pytest.raises(PowerLoss):
            model.gate.prepare(lambda: None, lambda: None)
    assert cut
    restored = preparation_void.FailedPreparationVoid(
        model.gate.staged,
        model.gate.paths,
        owner_uid=os.getuid(),
        kernel_io=model.original.original.io,
    )
    handled = restored.prepare(lambda: None, lambda: None, recover=True)
    assert handled is (point != "prepared")
    assert json.loads(restored.journal.read_bytes())["phase"] == "prepared"
    assert_void_preserved(model)


@pytest.mark.parametrize(
    "operation", ["remove-first", "remove-second", "add-full", "add-partial"]
)
def test_kernel_crash_restore_reauthenticates_partial_exact_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    model = void_case(tmp_path, monkeypatch)
    io = model.original.original.io
    real_remove, real_add = io.remove_profile, io.load_binary
    removes = 0

    def remove(name: str) -> None:
        nonlocal removes
        real_remove(name)
        removes += 1
        if removes == (1 if operation == "remove-first" else 2):
            raise PowerLoss()

    def add(binary: bytes) -> None:
        real_add(binary)
        if operation == "add-partial":
            io.profiles.pop("1")
        raise PowerLoss()

    with monkeypatch.context() as crash:
        if operation.startswith("remove-"):
            crash.setattr(io, "remove_profile", remove)
        else:
            crash.setattr(io, "load_binary", add)
        with pytest.raises(PowerLoss):
            model.gate.prepare(lambda: None, lambda: None)
    assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert_void_preserved(model)


def test_failed_rollback_is_explicit_and_recovery_removes_only_owned_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = void_case(tmp_path, monkeypatch)
    io = model.original.original.io
    real_remove = io.remove_profile

    def refused() -> None:
        def blocked(name: str) -> None:
            raise ValueError("synthetic_remove_refused")

        monkeypatch.setattr(io, "remove_profile", blocked)
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^preparation_void_rollback_failed$"):
        model.gate.prepare(refused, lambda: None)
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "rollback_failed"
    assert io.profiles
    monkeypatch.setattr(io, "remove_profile", real_remove)
    assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    assert_void_preserved(model)


def test_power_loss_during_candidate_rollback_restores_known_partial_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = void_case(tmp_path, monkeypatch)
    io = model.original.original.io
    real_remove = io.remove_profile

    def interrupted(name: str) -> None:
        real_remove(name)
        raise PowerLoss()

    def refused() -> None:
        monkeypatch.setattr(io, "remove_profile", interrupted)
        raise ValueError("placement_preflight_refused")

    with pytest.raises(PowerLoss):
        model.gate.prepare(refused, lambda: None)
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "candidate_rollback"
    assert len(io.profiles) == 1
    monkeypatch.setattr(io, "remove_profile", real_remove)
    assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert_void_preserved(model)


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("foreign", "preparation_void_journal_conflict"),
        ("pending", "preparation_void_pending_file"),
        ("original", "preparation_void_source_journal"),
        ("unknown-policy", "apparmor_blob_mismatch"),
        ("partial-policy", "apparmor_partial_policy"),
    ],
)
def test_unknown_or_changed_state_refuses_before_any_kernel_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, reason: str
) -> None:
    model = void_case(tmp_path, monkeypatch)
    io = model.original.original.io
    if mutation == "foreign":
        (
            model.gate.paths.ledger / ("placement-void-v1-" + "a" * 64 + ".json")
        ).write_bytes(b"unknown\n")
    elif mutation == "pending":
        model.gate.journal.with_name(model.gate.journal.name + ".new").write_bytes(
            b"uncommitted\n"
        )
    elif mutation == "original":
        model.original.source.journal.write_bytes(b"changed\n")
    elif mutation == "unknown-policy":
        io.profiles["0"]["raw_data"] = b"unknown-policy"
    else:
        io.profiles.pop("1")
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"), lambda: None, recover=True
        )
    assert io.writes == []
    assert not model.gate.journal.exists()


@pytest.mark.parametrize("value", [True, 1.0, 2, "1"])
def test_prepared_candidate_marker_still_has_strict_integer_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    from paper_radar.live_evidence.live_install import json_bytes
    from paper_radar.live_evidence.placement_policy import PlacementPolicyLifecycle

    model = void_case(tmp_path, monkeypatch)
    model.gate.prepare(lambda: None, lambda: None)
    marker = PlacementPolicyLifecycle(
        model.gate.staged,
        model.gate.paths.ledger,
        owner_uid=os.getuid(),
        anchor=model.gate.paths.anchor,
    ).journal
    raw = json.loads(marker.read_bytes())
    raw["format_version"] = value
    marker.write_bytes(json_bytes(raw))
    writes = list(model.original.original.io.writes)
    with pytest.raises(ValueError, match=r"^preparation_void_candidate_marker$"):
        model.gate.check(recover=True)
    assert model.original.original.io.writes == writes
