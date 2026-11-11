"""D1:真实LinuxLiveHost接线与部署公共install/uninstall/recover,OS操作全部模型化。"""

import os
from pathlib import Path

import pytest

from paper_radar.live_evidence import placement_policy, preparation_retirement
from paper_radar.live_evidence.live_apparmor_kernel import AppArmorKernel
from paper_radar.live_evidence.live_host import LinuxLiveHost
from paper_radar.live_evidence.live_install import LiveDeployment
from paper_radar.live_evidence.placement_policy import (
    PlacementPolicyLifecycle,
    read_placement_policy,
)
from tests.preparation_retirement_support import (
    RetirementCase,
    assert_business_unchanged,
    case,
)


def wire_linux_placement(
    model: RetirementCase,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_preflight: bool = False,
) -> list[str]:
    events: list[str] = []
    original_gate = preparation_retirement.FailedPreparationRetirement
    monkeypatch.setattr(
        preparation_retirement,
        "FailedPreparationRetirement",
        lambda root, paths: original_gate(
            root, paths, owner_uid=os.getuid(), kernel_io=model.io
        ),
    )
    monkeypatch.setattr(placement_policy, "verify_host_security", lambda sealed: None)
    linux = LinuxLiveHost(model.gate.paths, source=model.gate.staged)

    def lifecycle(root: Path) -> PlacementPolicyLifecycle:
        sealed = read_placement_policy(root)
        assert sealed is not None
        return PlacementPolicyLifecycle(
            root,
            model.gate.paths.ledger,
            owner_uid=os.getuid(),
            anchor=model.gate.paths.anchor,
            kernel=AppArmorKernel(model.io, sealed.parser),
        )

    monkeypatch.setattr(linux, "_placement_lifecycle", lifecycle)
    monkeypatch.setattr(
        linux, "verify_preparation_idle", lambda site: events.append("idle")
    )

    def preflight(*args: object, **kwargs: object) -> None:
        if not events.count("native"):
            assert_business_unchanged(model)
            assert model.gate.snapshot.read_bytes() == model.before[model.old.journal]
            assert [kind for kind, _ in model.io.writes] == ["remove", "remove", "add"]
        events.append("native")
        if fail_preflight:
            raise ValueError("placement_preflight_refused")

    monkeypatch.setattr(placement_policy, "native_preflight", preflight)
    monkeypatch.setattr(model.host, "preflight_placement", linux.preflight_placement)
    monkeypatch.setattr(model.host, "prepare_placement", linux.prepare_placement)
    model.host.policy_os = model.io
    return events


def test_new_preflight_precedes_business_first_write_and_same_sha_reentry_is_normal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    events = wire_linux_placement(model, monkeypatch)
    deployment = LiveDeployment(
        model.gate.staged,
        paths=model.gate.paths,
        host=model.host,
        owner_uid=os.getuid(),
    )
    assert deployment.install() == "installed"
    assert events[:2] == ["idle", "native"]
    snapshot = model.gate.snapshot.read_bytes()
    journal = model.gate.journal.read_bytes()
    writes = list(model.io.writes)
    assert deployment.install() == "already_installed"
    assert model.io.writes == writes
    assert model.gate.snapshot.read_bytes() == snapshot
    assert model.gate.journal.read_bytes() == journal
    assert deployment.uninstall() == "uninstalled"
    assert deployment.install(recover=True) == "installed"
    assert model.gate.snapshot.read_bytes() == snapshot
    assert model.gate.journal.read_bytes() == journal
    assert all(
        path.read_bytes() == raw
        for path, raw in model.before.items()
        if path.is_relative_to(model.old.root)
    )


def test_failed_preflight_preserves_main_epoch_budget_history_and_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = case(tmp_path, monkeypatch)
    wire_linux_placement(model, monkeypatch, fail_preflight=True)
    deployment = LiveDeployment(
        model.gate.staged,
        paths=model.gate.paths,
        host=model.host,
        owner_uid=os.getuid(),
    )
    with pytest.raises(ValueError, match=r"^placement_preflight_refused$"):
        deployment.install()
    assert_business_unchanged(model)
    assert model.gate.snapshot.read_bytes() == model.before[model.old.journal]
