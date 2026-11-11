"""D1:退役公开接缝严格认证恢复消费的旧/新policy marker;无现场操作。"""

import json
from pathlib import Path

import pytest

from paper_radar.live_evidence import live_install, preparation_retirement
from paper_radar.live_evidence.live_install import json_bytes
from paper_radar.live_evidence.live_install import publish as publish_record
from tests.preparation_retirement_support import (
    RetirementCase,
    assert_business_unchanged,
    case,
)


def interrupted_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, window: str
) -> RetirementCase:
    model = case(tmp_path, monkeypatch)

    def publish(
        path: Path, raw: bytes, *, replace: bool = False, mode: int = 0o644
    ) -> None:
        phase = json.loads(raw)["phase"]
        if (
            window == "new-prepared"
            and path == model.gate.journal
            and phase == "prepared"
        ):
            raise ValueError("synthetic_durable_stop")
        publish_record(path, raw, replace=replace, mode=mode)
        if (
            (path == model.gate.journal and phase == window)
            or (
                window == "old-removing"
                and path == model.old.journal
                and phase == "removing"
            )
            or (
                window == "old-removed"
                and path == model.old.journal
                and phase == "removed"
            )
        ):
            raise ValueError("synthetic_durable_stop")

    def preflight() -> None:
        if window == "new-preparing":
            raise ValueError("synthetic_durable_stop")

    with monkeypatch.context() as crash:
        crash.setattr(preparation_retirement, "publish", publish)
        crash.setattr(live_install, "publish", publish)
        with pytest.raises(ValueError, match=r"^synthetic_durable_stop$"):
            model.gate.prepare(preflight, lambda: None)
    return model


def ledger_state(root: Path) -> dict[Path, tuple[int, int, int, bytes | None]]:
    result = {}
    for path in (root, *root.rglob("*")):
        info = path.lstat()
        result[path] = (
            info.st_mode,
            info.st_mtime_ns,
            info.st_ctime_ns,
            path.read_bytes() if path.is_file() else None,
        )
    return result


def assert_refused_without_write(model: RetirementCase, reason: str) -> None:
    before = ledger_state(model.gate.paths.ledger)
    writes = list(model.io.writes)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.check(recover=True)
    with pytest.raises(ValueError, match="^" + reason + "$"):
        model.gate.prepare(
            lambda: pytest.fail("no preflight"),
            lambda: pytest.fail("no idle callback"),
            recover=True,
        )
    assert ledger_state(model.gate.paths.ledger) == before
    assert model.io.writes == writes
    assert_business_unchanged(model)


@pytest.mark.parametrize("version", [True, 1.0])
def test_removing_refuses_noninteger_old_marker_before_any_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, version: object
) -> None:
    model = interrupted_case(tmp_path, monkeypatch, "removing")
    marker = json.loads(model.old.journal.read_bytes())
    marker["format_version"] = version
    model.old.journal.write_bytes(json_bytes(marker))
    assert_refused_without_write(model, "failed_preparation_marker")


@pytest.mark.parametrize(
    ("window", "target"),
    [
        ("removing", "old"),
        ("preparing", "old"),
        ("new-preparing", "new"),
        ("new-prepared", "new"),
        ("prepared", "new"),
    ],
)
@pytest.mark.parametrize(
    "malformed",
    [
        "null",
        "list",
        "boolean-version",
        "float-version",
        "null-version",
        "list-version",
        "unknown-phase",
        "list-phase",
        "foreign-identity",
        "extra-field",
        "noncanonical",
    ],
)
def test_recovery_refuses_unknown_policy_metadata_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    window: str,
    target: str,
    malformed: str,
) -> None:
    model = interrupted_case(tmp_path, monkeypatch, window)
    path = model.old.journal if target == "old" else model.new.journal
    marker = json.loads(path.read_bytes())
    if malformed == "null":
        raw = b"null\n"
    elif malformed == "list":
        raw = b"[]\n"
    else:
        if malformed.endswith("-version"):
            marker["format_version"] = {
                "boolean-version": True,
                "float-version": 1.0,
                "null-version": None,
                "list-version": [],
            }[malformed]
        elif malformed == "unknown-phase":
            marker["phase"] = "unknown"
        elif malformed == "list-phase":
            marker["phase"] = []
        elif malformed == "foreign-identity":
            marker["identity"] = "f" * 64
        elif malformed == "extra-field":
            marker["unexpected"] = 1
        raw = json_bytes(marker)
        if malformed == "noncanonical":
            raw += b"\n"
    path.write_bytes(raw)
    reason = (
        "failed_preparation_marker"
        if target == "old"
        else "failed_preparation_new_marker"
    )
    assert_refused_without_write(model, reason)


@pytest.mark.parametrize(
    "window",
    [
        "removing",
        "old-removing",
        "old-removed",
        "removed",
        "preparing",
        "new-preparing",
        "new-prepared",
        "prepared",
    ],
)
def test_strict_marker_authentication_preserves_owned_recovery_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, window: str
) -> None:
    model = interrupted_case(tmp_path, monkeypatch, window)
    before = ledger_state(model.gate.paths.ledger)
    writes = list(model.io.writes)
    assert model.gate.check(recover=True) is (window != "prepared")
    assert ledger_state(model.gate.paths.ledger) == before
    assert model.io.writes == writes
    assert model.gate.prepare(lambda: None, lambda: None, recover=True) is (
        window != "prepared"
    )
    assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
    assert_business_unchanged(model)


@pytest.mark.parametrize(
    ("window", "target", "phase"),
    [
        ("removing", "new", "preparing"),
        ("removing", "new", "prepared"),
        ("removed", "new", "preparing"),
        ("removed", "old", "preparing"),
        ("preparing", "old", "removing"),
        ("new-preparing", "new", "removing"),
        ("new-prepared", "new", "removed"),
        ("prepared", "old", "preparing"),
    ],
)
def test_known_policy_phase_must_belong_to_retirement_window(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    window: str,
    target: str,
    phase: str,
) -> None:
    model = interrupted_case(tmp_path, monkeypatch, window)
    lifecycle = model.old if target == "old" else model.new
    assert lifecycle.sealed is not None
    lifecycle.journal.write_bytes(
        json_bytes(
            {
                "format_version": 1,
                "identity": lifecycle.sealed.identity,
                "phase": phase,
            }
        )
    )
    lifecycle.journal.chmod(0o644)
    reason = (
        "failed_preparation_marker"
        if target == "old"
        else "failed_preparation_new_marker"
    )
    assert_refused_without_write(model, reason)


@pytest.mark.parametrize("phase", ["preparing", "prepared", "removing", "removed"])
def test_prepared_retirement_hands_owned_new_lifecycle_back_without_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    from paper_radar.live_evidence.live_apparmor_kernel import AppArmorKernel
    from paper_radar.live_evidence.placement_policy import PlacementPolicyLifecycle

    model = interrupted_case(tmp_path, monkeypatch, "prepared")
    assert model.new.sealed is not None
    lifecycle = PlacementPolicyLifecycle(
        model.new.root,
        model.gate.paths.ledger,
        owner_uid=model.gate.owner_uid,
        anchor=model.gate.paths.anchor,
        kernel=AppArmorKernel(model.io, model.new.sealed.parser),
    )
    if phase in {"preparing", "removed"}:
        lifecycle.remove()
        if phase == "preparing":

            def preflight() -> None:
                raise ValueError("synthetic_new_preflight_stop")

            with pytest.raises(ValueError, match=r"^synthetic_new_preflight_stop$"):
                lifecycle.prepare(preflight, recover=True)
    elif phase == "removing":
        remove = model.io.remove_profile

        def interrupted_remove(name: str) -> None:
            remove(name)
            raise ValueError("synthetic_new_remove_stop")

        with monkeypatch.context() as crash:
            crash.setattr(model.io, "remove_profile", interrupted_remove)
            with pytest.raises(ValueError, match=r"^synthetic_new_remove_stop$"):
                lifecycle.remove()
    assert lifecycle.phase() == phase
    before = ledger_state(model.gate.paths.ledger)
    writes = list(model.io.writes)
    assert model.gate.check(recover=True) is False
    assert (
        model.gate.prepare(
            lambda: pytest.fail("no retirement preflight"),
            lambda: pytest.fail("no retirement idle"),
            recover=True,
        )
        is False
    )
    assert ledger_state(model.gate.paths.ledger) == before
    assert model.io.writes == writes
    lifecycle.prepare(lambda: None, recover=True)
    assert lifecycle.phase() == "prepared"
    assert_business_unchanged(model)


@pytest.mark.parametrize(
    ("window", "target"),
    [("removing", "old"), ("prepared", "old"), ("prepared", "new")],
)
def test_required_missing_marker_refusal_names_exact_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, window: str, target: str
) -> None:
    import errno

    model = interrupted_case(tmp_path, monkeypatch, window)
    path = model.old.journal if target == "old" else model.new.journal
    path.unlink()
    before = ledger_state(model.gate.paths.ledger)
    writes = list(model.io.writes)
    with pytest.raises(FileNotFoundError) as error:
        model.gate.prepare(
            lambda: pytest.fail("no preflight"),
            lambda: pytest.fail("no idle"),
            recover=True,
        )
    assert error.value.errno == errno.ENOENT
    assert error.value.filename == str(path)
    assert ledger_state(model.gate.paths.ledger) == before
    assert model.io.writes == writes
    assert_business_unchanged(model)
