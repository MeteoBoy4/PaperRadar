"""D1:真实LinuxLiveHost接线的公开新payload恢复/卸载/再安装。"""

import json
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
from tests.preparation_recovery_support import (
    RecoveryCase,
    assert_preserved,
    recovery_case,
)


def wire(model: RecoveryCase, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    gate_type = preparation_retirement.FailedPreparationRetirement
    monkeypatch.setattr(
        preparation_retirement,
        "FailedPreparationRetirement",
        lambda root, paths: gate_type(
            root, paths, owner_uid=os.getuid(), kernel_io=model.original.io
        ),
    )
    monkeypatch.setattr(placement_policy, "verify_host_security", lambda sealed: None)
    linux = LinuxLiveHost(model.gate.paths, source=model.gate.staged)
    events = []

    def lifecycle(root: Path) -> PlacementPolicyLifecycle:
        sealed = read_placement_policy(root)
        assert sealed is not None
        return PlacementPolicyLifecycle(
            root,
            model.gate.paths.ledger,
            owner_uid=os.getuid(),
            anchor=model.gate.paths.anchor,
            kernel=AppArmorKernel(model.original.io, sealed.parser),
        )

    def native(*args: object, **kwargs: object) -> None:
        if "native" not in events:
            assert_preserved(model)
            assert model.original.io.writes == []
            assert json.loads(model.gate.journal.read_bytes())["phase"] == "preparing"
        events.append("native")

    monkeypatch.setattr(linux, "_placement_lifecycle", lifecycle)
    monkeypatch.setattr(
        linux, "verify_preparation_idle", lambda site: events.append("idle")
    )
    monkeypatch.setattr(placement_policy, "native_preflight", native)
    monkeypatch.setattr(
        model.original.host, "preflight_placement", linux.preflight_placement
    )
    monkeypatch.setattr(
        model.original.host, "prepare_placement", linux.prepare_placement
    )
    model.original.host.policy_os = model.original.io
    return events


def test_public_recover_returns_to_normal_same_payload_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = recovery_case(tmp_path, monkeypatch)
    events = wire(model, monkeypatch)
    deployment = LiveDeployment(
        model.gate.staged,
        paths=model.gate.paths,
        host=model.original.host,
        owner_uid=os.getuid(),
    )
    with pytest.raises(ValueError, match=r"^failed_preparation_recovery_required$"):
        deployment.install()
    assert not model.gate.journal.exists() and model.original.io.writes == []
    assert_preserved(model)
    assert deployment.install(recover=True) == "installed"
    assert events[:2] == ["idle", "native"]
    assert model.original.io.writes == []
    original_records = {
        p: raw
        for p, (raw, _) in model.preserved.items()
        if p.is_relative_to(model.source.staged)
        or p.is_relative_to(model.original.old.root)
        or p
        in {model.source.journal, model.source.snapshot, model.original.old.journal}
    }
    own = model.gate.journal.read_bytes()
    assert deployment.install() == "already_installed"
    assert deployment.uninstall() == "uninstalled"
    assert deployment.install(recover=True) == "installed"
    assert model.gate.journal.read_bytes() == own
    assert all(path.read_bytes() == raw for path, raw in original_records.items())
    with pytest.raises(ValueError, match=r"^failed_preparation_journal_conflict$"):
        model.source.check(recover=True)


@pytest.mark.parametrize("checkpoint", ["retiring", "archived", "runtime", "resources"])
def test_deployment_interruptions_after_own_prepared_use_existing_main_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checkpoint: str
) -> None:
    from paper_radar.live_evidence import live_install

    model = recovery_case(tmp_path, monkeypatch)
    wire(model, monkeypatch)
    deployment = LiveDeployment(
        model.gate.staged,
        paths=model.gate.paths,
        host=model.original.host,
        owner_uid=os.getuid(),
    )
    real = live_install.publish
    hit = False

    def publish(
        path: Path, raw: bytes, *, replace: bool = False, mode: int = 0o644
    ) -> None:
        nonlocal hit
        real(path, raw, replace=replace, mode=mode)
        if (
            path == model.gate.paths.journal
            and json.loads(raw)["phase"] == checkpoint
            and not hit
        ):
            hit = True
            raise ValueError("synthetic_deployment_crash")

    with monkeypatch.context() as crash:
        crash.setattr(live_install, "publish", publish)
        with pytest.raises(ValueError, match=r"^synthetic_deployment_crash$"):
            deployment.install(recover=True)
    assert hit
    assert json.loads(model.gate.journal.read_bytes())["phase"] == "prepared"
    assert deployment.install(recover=True) == "installed"
    assert model.original.io.writes == []
    assert model.source.journal.read_bytes() == model.preserved[model.source.journal][0]
