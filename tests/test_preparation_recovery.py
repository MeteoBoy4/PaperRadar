"""D1:公开check/prepare的一跳准备恢复与原记录保全。"""

import json
from pathlib import Path

import pytest

from tests.preparation_recovery_support import assert_preserved, recovery_case


def test_new_payload_recovers_failed_preflight_with_same_policy_and_untouched_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    assert model.gate.check(recover=True) is True
    assert not model.gate.journal.exists()
    assert model.original.io.writes == []
    events = []
    assert (
        model.gate.prepare(
            lambda: events.append("preflight"),
            lambda: events.append("idle"),
            recover=True,
        )
        is True
    )
    assert events == ["idle", "preflight"]
    assert model.original.io.writes == []
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert model.gate.check() is False
    assert_preserved(model)


def test_explicit_recovery_is_required_even_before_own_journal_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
        model.gate.prepare(lambda: pytest.fail("no preflight"), lambda: None)
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)


@pytest.mark.parametrize(
    "point", ["before-own", "after-own", "new-prepared", "own-prepared"]
)
def test_interruption_windows_resume_with_exact_source_without_kernel_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    from paper_radar.live_evidence import live_install, preparation_retirement

    model = recovery_case(tmp_path, monkeypatch)
    interrupted = False
    real = live_install.publish

    def publish(
        path: Path, raw: bytes, *, replace: bool = False, mode: int = 0o644
    ) -> None:
        nonlocal interrupted
        own = path == model.gate.journal
        phase = json.loads(raw)["phase"]
        matches = (
            own and phase == "preparing"
            if point in {"before-own", "after-own"}
            else path == model.original.new.journal and phase == "prepared"
            if point == "new-prepared"
            else own and phase == "prepared"
        )
        if matches and not interrupted and point == "before-own":
            interrupted = True
            raise ValueError("synthetic_power_loss")
        real(path, raw, replace=replace, mode=mode)
        if matches and not interrupted:
            interrupted = True
            raise ValueError("synthetic_power_loss")

    with monkeypatch.context() as crash:
        crash.setattr(live_install, "publish", publish)
        crash.setattr(preparation_retirement, "publish", publish)
        with pytest.raises(ValueError, match=r"^synthetic_power_loss$"):
            model.gate.prepare(lambda: None, lambda: None, recover=True)
    assert interrupted
    if point != "own-prepared":
        assert model.gate.prepare(lambda: None, lambda: None, recover=True) is True
    else:
        assert (
            model.gate.prepare(lambda: pytest.fail("normal lifecycle"), lambda: None)
            is False
        )
    assert model.original.io.writes == []
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert_preserved(model)


def test_new_preflight_failure_preserves_original_and_owns_only_current_preparing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)

    def refused() -> None:
        raise ValueError("placement_preflight_refused")

    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        model.gate.prepare(refused, lambda: None, recover=True)
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "preparing"
    assert model.original.io.writes == []
    assert_preserved(model)
    # 原候选看到新增本次journal后拒绝,不能并行退役或重取恢复权。
    with pytest.raises(ValueError, match=r"^failed_preparation_journal_conflict$"):
        model.source.check(recover=True)


def test_idle_and_reauthentication_precede_first_own_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)

    def active() -> None:
        assert not model.gate.journal.exists()
        raise ValueError("project_scope_not_idle")

    with pytest.raises(ValueError, match=r"^project_scope_not_idle$"):
        model.gate.prepare(lambda: pytest.fail("no preflight"), active, recover=True)
    assert not model.gate.journal.exists()
    assert_preserved(model)

    def changed() -> None:
        model.source.journal.write_bytes(b"changed after idle check\n")

    with pytest.raises(ValueError, match=r"^preparation_recovery_source$"):
        model.gate.prepare(lambda: pytest.fail("no preflight"), changed, recover=True)
    assert not model.gate.journal.exists() and model.original.io.writes == []
